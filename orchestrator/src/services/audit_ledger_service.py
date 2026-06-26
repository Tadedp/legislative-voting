import os
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import AuditLedger, VotingRound, NominalVote, NonNominalVoter, NonNominalTally, Legislator, Device
from src.schemas.audit_ledger_schemas import TallyPayload, NominalVote as NominalVoteSchema, AnonymousVote as AnonymousVoteSchema, VerifiedParticipant as VerifiedParticipantSchema
from src.services.crypto_merkle import MerkleTreeGenerator
from src.services.blockchain_notary import BlockchainNotaryService
from src.core.config import settings

async def extract_snapshot_data(db: AsyncSession, round_id: uuid.UUID) -> TallyPayload:
    # Get Round & Agenda Item
    stmt = select(VotingRound).options(selectinload(VotingRound.agenda_item)).where(VotingRound.id == round_id)
    result = await db.execute(stmt)
    round_obj = result.scalar_one()

    is_nominal = round_obj.is_nominal
    
    tallies = {
        "AFFIRMATIVE": 0,
        "NEGATIVE": 0,
        "ABSTENTION": 0,
    }
    
    nominal_votes: list[NominalVoteSchema] = []
    anonymous_votes: list[AnonymousVoteSchema] = []
    verified_participants: list[VerifiedParticipantSchema] = []

    if is_nominal:
        stmt = select(NominalVote, Legislator).join(Legislator, NominalVote.legislator_id == Legislator.id).where(NominalVote.voting_round_id == round_id)
        res = await db.execute(stmt)
        vote_rows = res.all()
        
        # Bulk query for Devices (Task 4 & 5)
        legislator_ids = [leg.id for _, leg in vote_rows]
        if legislator_ids:
            # Order by assigned_at desc so we get the most recent device if multiple exist
            d_stmt = select(Device).where(Device.legislator_id.in_(legislator_ids)).order_by(Device.assigned_at.desc())
            d_res = await db.execute(d_stmt)
            # Create a dictionary mapping legislator_id to their most recent device
            device_map = {}
            for d in d_res.scalars().all():
                if d.legislator_id not in device_map:
                    device_map[d.legislator_id] = d
        else:
            device_map = {}

        for vote, leg in vote_rows:
            dev = device_map.get(leg.id)
            pem = dev.public_key_pem if dev else ""
            
            tallies[vote.vote_value.name] += 1
            
            nominal_votes.append(NominalVoteSchema(
                legislator_id=str(leg.id),
                legislator_name=f"{leg.first_name} {leg.last_name}",
                public_key_pem=pem,
                value=vote.vote_value.name,
                signature=vote.cryptographic_signature,
                timestamp=int(vote.timestamp.timestamp() * 1000)
            ))
    else:
        # Tally
        t_stmt = select(NonNominalTally).where(NonNominalTally.voting_round_id == round_id)
        t_res = await db.execute(t_stmt)
        for tally in t_res.scalars().all():
            tallies[tally.vote_value.name] += 1
            anonymous_votes.append(AnonymousVoteSchema(
                value=tally.vote_value.name,
                salt=tally.salt
            ))
            
        # Voters
        v_stmt = select(NonNominalVoter, Legislator).join(Legislator, NonNominalVoter.legislator_id == Legislator.id).where(NonNominalVoter.voting_round_id == round_id)
        v_res = await db.execute(v_stmt)
        voter_rows = v_res.all()
        
        # Bulk query for Devices (Task 4 & 5)
        legislator_ids = [leg.id for _, leg in voter_rows]
        if legislator_ids:
            d_stmt = select(Device).where(Device.legislator_id.in_(legislator_ids)).order_by(Device.assigned_at.desc())
            d_res = await db.execute(d_stmt)
            device_map = {}
            for d in d_res.scalars().all():
                if d.legislator_id not in device_map:
                    device_map[d.legislator_id] = d
        else:
            device_map = {}

        for voter, leg in voter_rows:
            dev = device_map.get(leg.id)
            pem = dev.public_key_pem if dev else ""
            
            verified_participants.append(VerifiedParticipantSchema(
                legislator_id=str(leg.id),
                legislator_name=f"{leg.first_name} {leg.last_name}",
                public_key_pem=pem,
                signature=voter.cryptographic_signature,
                timestamp=int(voter.timestamp.timestamp() * 1000)
            ))

    payload = TallyPayload(
        voting_round_id=str(round_obj.id),
        agenda_item_title=round_obj.agenda_item.title,
        is_nominal=is_nominal,
        timestamp=str(int(round_obj.closed_at.timestamp() * 1000)) if round_obj.closed_at else str(int(round_obj.created_at.timestamp() * 1000)),
        tallies=tallies,
        nominal_votes=nominal_votes,
        anonymous_votes=anonymous_votes,
        verified_participants=verified_participants
    )
    return payload

async def anchor_and_snapshot_round(db: AsyncSession, round_id: uuid.UUID, is_nominal: bool):
    payload = await extract_snapshot_data(db, round_id)
    
    # 2. Cryptographic Generation
    nominal_root = "0x" + ("00" * 32)
    tally_root = "0x" + ("00" * 32)
    eligibility_root = "0x" + ("00" * 32)

    if is_nominal:
        leaves = [
            MerkleTreeGenerator.hash_nominal_leaf(v.legislator_name, v.public_key_pem, v.value, v.signature, v.timestamp) 
            for v in payload.nominal_votes
        ]
        nominal_root = MerkleTreeGenerator.generate_tree_root(leaves)
    else:
        t_leaves = [MerkleTreeGenerator.hash_tally_leaf(v.value, v.salt) for v in payload.anonymous_votes]
        tally_root = MerkleTreeGenerator.generate_tree_root(t_leaves)
        
        e_leaves = [
            MerkleTreeGenerator.hash_eligibility_leaf(p.legislator_name, p.public_key_pem, p.signature, p.timestamp) 
            for p in payload.verified_participants
        ]
        eligibility_root = MerkleTreeGenerator.generate_tree_root(e_leaves)

    # 3. Web3 Anchoring (Double-Spend Protected)
    try:
        rpc_url = settings.blockchain.POLYGON_AMOY_RPC_URL
        private_key = settings.blockchain.ORCHESTRATOR_WALLET_PRIVATE_KEY
        contract_address = settings.blockchain.CONTRACT_ADDRESS
        abi_path = settings.blockchain.ABI_PATH
        
        if os.path.exists(abi_path) and rpc_url and private_key and contract_address:
            notary = BlockchainNotaryService(rpc_url, private_key, contract_address, abi_path)
            receipt = await notary.proclaim_round(
                round_id=str(round_id),
                title=payload.agenda_item_title,
                is_nominal=is_nominal,
                nominal_root=nominal_root,
                tally_root=tally_root,
                eligibility_root=eligibility_root
            )
        else:
            receipt: dict[str, Any] = {"transaction_hash": "0x0", "block_number": 0}
    except Exception as e:
        print(f"Blockchain anchoring failed: {e}")
        receipt: dict[str, Any] = {"transaction_hash": "0x0", "block_number": 0}

    # 4. Database Persistence
    audit_row = AuditLedger(
        voting_round_id=round_id,
        is_nominal=is_nominal,
        nominal_merkle_root=nominal_root if is_nominal else None,
        tally_merkle_root=None if is_nominal else tally_root,
        eligibility_merkle_root=None if is_nominal else eligibility_root,
        transaction_hash=receipt["transaction_hash"],
        block_number=receipt["block_number"],
        tally_payload=payload.model_dump(mode='json')
    )
    
    db.add(audit_row)
    await db.flush()