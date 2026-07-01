import asyncio
import os
import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from src.models import (
    AuditLedger, 
    VotingRound, 
    NominalVote, 
    NonNominalVoter, 
    NonNominalTally, 
    Legislator, 
    Device, 
    LegislativeSession,
)
from src.schemas.audit_ledger_schemas import (
    TallyPayload, 
    TieBreakerVote,
    NominalVote as NominalVoteSchema, 
    AnonymousVote as AnonymousVoteSchema, 
    VerifiedParticipant as VerifiedParticipantSchema, 
)
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
        stmt = select(NominalVote, Legislator, Device).join(
            Legislator, NominalVote.legislator_id == Legislator.id
        ).join(
            Device, NominalVote.device_id == Device.id
        ).where(NominalVote.voting_round_id == round_id)
        res = await db.execute(stmt)
        vote_rows = res.all()
        
        for vote, leg, dev in vote_rows:
            pem = dev.public_key_pem if dev else ""
            
            tallies[vote.vote_value.name] += 1
            
            nominal_votes.append(NominalVoteSchema(
                legislator_id=str(leg.id),
                legislator_name=f"{leg.first_name} {leg.last_name}",
                public_key_pem=pem,
                value=vote.vote_value.name,
                signature=vote.cryptographic_signature,
                timestamp=vote.client_timestamp,
                raw_payload=vote.raw_payload
            ))
    else:
        # Tally
        t_stmt = select(NonNominalTally).where(NonNominalTally.voting_round_id == round_id)
        t_res = await db.execute(t_stmt)
        for tally in t_res.scalars().all():
            tallies[tally.vote_value.name] += 1
            anonymous_votes.append(AnonymousVoteSchema(
                value=tally.vote_value.name,
                ephemeral_pub=tally.ephemeral_public_key,
                server_signature=tally.server_signature,
                vote_signature=tally.vote_signature
            ))
            
        # Voters
        v_stmt = select(NonNominalVoter, Legislator, Device).join(
            Legislator, NonNominalVoter.legislator_id == Legislator.id
        ).join(
            Device, NonNominalVoter.device_id == Device.id
        ).where(NonNominalVoter.voting_round_id == round_id)
        v_res = await db.execute(v_stmt)
        voter_rows = v_res.all()
        
        for voter, leg, dev in voter_rows:
            pem = dev.public_key_pem if dev else ""
            
            verified_participants.append(VerifiedParticipantSchema(
                legislator_id=str(leg.id),
                legislator_name=f"{leg.first_name} {leg.last_name}",
                public_key_pem=pem,
                blinded_token=voter.raw_payload,
                signature=voter.cryptographic_signature,
                timestamp=int(voter.timestamp.timestamp() * 1000)
            ))
            
        assert len(verified_participants) >= len(anonymous_votes), "Integrity error: tally votes exceed authorized participants."
        
    tie_breaker_vote = None
    if round_obj.tie_breaker_signature and round_obj.tie_breaker_vote_value:
        stmt_leg_session = select(LegislativeSession).where(LegislativeSession.id == round_obj.legislative_session_id)
        res_leg = await db.execute(stmt_leg_session)
        leg_session = res_leg.scalar_one_or_none()
        
        if leg_session and leg_session.presiding_officer_id:
            stmt_pres = select(Legislator).where(Legislator.id == leg_session.presiding_officer_id)
            res_pres = await db.execute(stmt_pres)
            pres = res_pres.scalar_one_or_none()
            if pres:
                if not round_obj.tie_breaker_device_id or not round_obj.tie_breaker_client_timestamp:
                    raise ValueError("Invalid Tie-Breaker: Missing cryptographic timestamp or device mapping")

                d_stmt = select(Device).where(Device.id == round_obj.tie_breaker_device_id)
                d_res = await db.execute(d_stmt)
                dev = d_res.scalar_one_or_none()
                if not dev:
                    raise ValueError("Invalid Tie-Breaker: Missing cryptographic timestamp or device mapping")
                
                pem = dev.public_key_pem
                
                tie_breaker_vote = TieBreakerVote(
                    legislator_id=str(pres.id),
                    legislator_name=pres.full_name,
                    public_key_pem=pem,
                    value=round_obj.tie_breaker_vote_value,
                    signature=round_obj.tie_breaker_signature,
                    timestamp=round_obj.tie_breaker_client_timestamp,
                    raw_payload=round_obj.tie_breaker_raw_payload
                )
                tallies[round_obj.tie_breaker_vote_value] += 1

    payload = TallyPayload(
        voting_round_id=str(round_obj.id),
        agenda_item_title=round_obj.agenda_item.title,
        is_nominal=is_nominal,
        timestamp=str(int(round_obj.closed_at.timestamp() * 1000)) if round_obj.closed_at else str(int(round_obj.created_at.timestamp() * 1000)),
        tallies=tallies,
        nominal_votes=nominal_votes,
        anonymous_votes=anonymous_votes,
        verified_participants=verified_participants,
        tie_breaker_vote=tie_breaker_vote,
        ephemeral_public_key=round_obj.ephemeral_public_key
    )
    return payload

async def anchor_and_snapshot_round(db: AsyncSession, round_id: uuid.UUID, is_nominal: bool):
    payload = await extract_snapshot_data(db, round_id)
    
    nominal_root = "0x" + ("00" * 32)
    tally_root = "0x" + ("00" * 32)
    eligibility_root = "0x" + ("00" * 32)

    if is_nominal:
        leaves = [
            MerkleTreeGenerator.hash_nominal_leaf(str(round_id), v.legislator_name, v.public_key_pem, v.value, v.signature, v.timestamp) 
            for v in payload.nominal_votes
        ]
        if payload.tie_breaker_vote:
            tb = payload.tie_breaker_vote
            leaves.append(MerkleTreeGenerator.hash_tie_breaker_leaf(str(round_id), tb.legislator_id, tb.value, tb.signature, tb.timestamp))
        nominal_root = MerkleTreeGenerator.generate_tree_root(leaves)
    else:
        t_leaves = [MerkleTreeGenerator.hash_tally_leaf(str(round_id), v.value, v.ephemeral_pub, v.server_signature, v.vote_signature) for v in payload.anonymous_votes]
        if payload.tie_breaker_vote:
            tb = payload.tie_breaker_vote
            t_leaves.append(MerkleTreeGenerator.hash_tie_breaker_leaf(str(round_id), tb.legislator_id, tb.value, tb.signature, tb.timestamp))
        tally_root = MerkleTreeGenerator.generate_tree_root(t_leaves)
        
        e_leaves = [
            MerkleTreeGenerator.hash_eligibility_leaf(str(round_id), p.legislator_name, p.public_key_pem, p.blinded_token, p.signature, p.timestamp) 
            for p in payload.verified_participants
        ]
        eligibility_root = MerkleTreeGenerator.generate_tree_root(e_leaves)

    rpc_url = settings.blockchain.POLYGON_AMOY_RPC_URL
    private_key = settings.blockchain.ORCHESTRATOR_WALLET_PRIVATE_KEY
    contract_address = settings.blockchain.CONTRACT_ADDRESS
    abi_path = settings.blockchain.ABI_PATH
    
    if not (os.path.exists(abi_path) and rpc_url and private_key and contract_address):
        raise ValueError("Configuración de blockchain incompleta.")

    notary = BlockchainNotaryService(rpc_url, private_key, contract_address, abi_path)

    for attempt in range(3):
        if attempt > 0:
            try:
                round_data = await notary.contract.functions.rounds(str(round_id)).call()
                is_proclaimed = round_data[5]
                if is_proclaimed:
                    receipt = await notary.recover_from_event_logs(str(round_id))
                    break
            except Exception:
                pass
                
        try:
            receipt = await notary.proclaim_round(
                round_id=str(round_id),
                title=payload.agenda_item_title,
                is_nominal=is_nominal,
                nominal_root=nominal_root,
                tally_root=tally_root,
                eligibility_root=eligibility_root
            )
            break
        except Exception:
            await asyncio.sleep(5)
    else:
        raise Exception("Blockchain anchoring failed after 3 attempts.")

    stmt = insert(AuditLedger).values(
        voting_round_id=round_id,
        is_nominal=is_nominal,
        nominal_merkle_root=nominal_root if is_nominal else None,
        tally_merkle_root=None if is_nominal else tally_root,
        eligibility_merkle_root=None if is_nominal else eligibility_root,
        transaction_hash=receipt["transaction_hash"],
        block_number=receipt["block_number"],
        tally_payload=payload.model_dump(mode='json')
    )

    upsert_stmt = stmt.on_conflict_do_update(
        index_elements=['voting_round_id'],
        set_=dict(
            nominal_merkle_root=stmt.excluded.nominal_merkle_root,
            tally_merkle_root=stmt.excluded.tally_merkle_root,
            eligibility_merkle_root=stmt.excluded.eligibility_merkle_root,
            transaction_hash=stmt.excluded.transaction_hash,
            block_number=stmt.excluded.block_number,
            tally_payload=stmt.excluded.tally_payload
        )
    )
    
    await db.execute(upsert_stmt)
    await db.flush()