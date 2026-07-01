import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from cryptography.fernet import Fernet
from Crypto.PublicKey import RSA

from src.core.config import settings
from src.models.agenda_item import AgendaItem, ItemStatus
from src.models.nominal_vote import VoteValue
from src.models.non_nominal_voter import NonNominalVoter
from src.models.voting_round import RoundStage, RoundStatus, VotingRound
from src.models.voting_type import CalculationBase
from src.repositories import (
    agenda_item_repository,
    legislative_session_repository,
    legislator_repository,
    vote_repository,
    voting_round_repository,
    voting_type_repository,
)
from src.services.quorum_service import (
    calculate_effective_denominator, 
    compute_quorum_minimum, 
    get_certified_quorum,
)

def calculate_round_result(
    affirmative: int,
    negative: int,
    calc_base: CalculationBase,
    threshold: Decimal,
    quorum_present: int,
    total_members: int,
    abstentions: int = 0,
) -> str:
    if calc_base == CalculationBase.VOTES_CAST:
        denominator = affirmative + negative
    elif calc_base == CalculationBase.MEMBERS_PRESENT:
        denominator = max(quorum_present, affirmative + negative + abstentions)
    else:
        denominator = total_members

    if denominator == 0:
        return "FAILED"

    if affirmative == negative:
        return "TIED"

    if threshold == Decimal(0):
        if affirmative > negative:
            return "PASSED"
        return "FAILED"

    if threshold == Decimal(50):
        required = (denominator // 2) + 1
    else:
        required_decimal = (Decimal(denominator) * threshold / Decimal("100.0")).to_integral_value(rounding=ROUND_CEILING)
        required = int(required_decimal)

    if affirmative >= required:
        return "PASSED"

    return "FAILED"

async def list_rounds_by_session(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> list[VotingRound]:
    session = await legislative_session_repository.get_by_id(db, session_id)

    if session is None or session.deleted_at is not None:
        raise ValueError("Legislative session not found.")

    return await voting_round_repository.get_by_session_id(db, session_id)

async def get_voting_round(
    db: AsyncSession,
    round_id: uuid.UUID,
) -> VotingRound:
    voting_round = await voting_round_repository.get_by_id(db, round_id)

    if voting_round is None or voting_round.deleted_at is not None:
        raise ValueError("Voting round not found.")

    return voting_round

async def create_voting_round(
    db: AsyncSession,
    *,
    agenda_item_id: uuid.UUID,
    session_id: uuid.UUID,
    stage: RoundStage,
    voting_type_id: uuid.UUID,
    specific_reference: str | None = None,
    is_nominal: bool = True,
    president_votes_ordinarily: bool = False,
    time_limit_seconds: int | None = None,
) -> VotingRound:
    item = await agenda_item_repository.get_by_id(db, agenda_item_id)
    if item is None or item.deleted_at is not None:
        raise ValueError("Agenda item not found.")

    session = await legislative_session_repository.get_by_id(db, session_id)
    if session is None or session.deleted_at is not None:
        raise ValueError("Legislative session not found.")

    voting_type = await voting_type_repository.get_by_id(db, voting_type_id)
    if voting_type is None or voting_type.deleted_at is not None:
        raise ValueError("Voting type not found.")

    if stage == RoundStage.SPECIFIC:
        has_passed = await voting_round_repository.has_passed_general_round(
            db, agenda_item_id,
        )
        if not has_passed:
            raise ValueError(
                "Creation constraint violated: cannot create a SPECIFIC "
                "voting round without a prior GENERAL round that has "
                "PASSED for this agenda item.",
            )

    voting_round = VotingRound(
        agenda_item_id=agenda_item_id,
        legislative_session_id=session_id,
        stage=stage,
        specific_reference=specific_reference,
        voting_type_id=voting_type_id,
        is_nominal=is_nominal,
        president_votes_ordinarily=president_votes_ordinarily,
        time_limit_seconds=time_limit_seconds,
    )
    
    key = RSA.generate(3072)
    
    # Encrypt the ephemeral private key at rest using Fernet
    pem_private = key.export_key(format='PEM')
    f = Fernet(settings.security.EPHEMERAL_KEY_ENCRYPTION_KEY.encode('utf-8'))
    voting_round.ephemeral_private_key = f.encrypt(pem_private).decode('utf-8')
    
    voting_round.ephemeral_public_key = key.publickey().export_key(format='PEM').decode('utf-8')

    return await voting_round_repository.create(db, voting_round=voting_round)

async def update_voting_round(
    db: AsyncSession,
    round_id: uuid.UUID,
    *,
    update_data: dict[str, Any],
) -> VotingRound:
    voting_round = await voting_round_repository.get_by_id(db, round_id)

    if voting_round is None or voting_round.deleted_at is not None:
        raise ValueError("Voting round not found.")

    if voting_round.status != RoundStatus.DRAFT:
        raise ValueError(
            "Cannot update voting round: only rounds with status 'DRAFT' "
            "can be modified.",
        )

    if "voting_type_id" in update_data:
        voting_type = await voting_type_repository.get_by_id(
            db, update_data["voting_type_id"],
        )
        if voting_type is None or voting_type.deleted_at is not None:
            raise ValueError("Voting type not found.")

    for field, value in update_data.items():
        setattr(voting_round, field, value)

    await db.flush()
    return voting_round

async def soft_delete_voting_round(
    db: AsyncSession,
    round_id: uuid.UUID,
) -> VotingRound:
    voting_round = await voting_round_repository.get_by_id(db, round_id)

    if voting_round is None or voting_round.deleted_at is not None:
        raise ValueError("Voting round not found.")

    if voting_round.status != RoundStatus.DRAFT:
        raise ValueError(
            "Cannot delete voting round: only rounds with status 'DRAFT' "
            "can be deleted.",
        )

    voting_round.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    return voting_round

async def open_voting_round(
    db: AsyncSession,
    round_id: uuid.UUID,
) -> VotingRound:
    stmt = select(VotingRound).with_for_update().where(VotingRound.id == round_id)
    result = await db.execute(stmt)
    voting_round = result.scalar_one_or_none()

    if voting_round is None or voting_round.deleted_at is not None:
        raise ValueError("Voting round not found.")

    if voting_round.status != RoundStatus.DRAFT:
        raise ValueError("Can only open DRAFT rounds.")

    existing_open = await voting_round_repository.get_open_round_in_session(
        db, voting_round.legislative_session_id,
    )
    if existing_open is not None and existing_open.id != voting_round.id:
        raise ValueError(
            "Cannot open voting: another voting round is already open "
            "in this session.",
        )

    leg_session = await legislative_session_repository.get_by_id(
        db, voting_round.legislative_session_id,
    )
    if leg_session is None:
        raise ValueError("Legislative session not found.")

    quorum_present, total_members = await get_certified_quorum(
        db,
        leg_session,
        president_votes_ordinarily=voting_round.president_votes_ordinarily,
    )
    quorum_minimum = compute_quorum_minimum(total_members)

    if quorum_present < quorum_minimum:
        raise ValueError(
            f"No legally certified quorum: {quorum_present} legislators present, "
            f"{quorum_minimum} required (out of {total_members} total).",
        )

    voting_round.certified_quorum_count = quorum_present
    voting_round.quorum_present_count = quorum_present
    voting_round.opened_at = datetime.now(timezone.utc)
    voting_round.status = RoundStatus.VOTING_OPEN

    await db.flush()
    return voting_round

async def close_voting_round(
    db: AsyncSession,
    round_id: uuid.UUID,
) -> VotingRound:
    stmt = select(VotingRound).where(VotingRound.id == round_id).with_for_update()
    result = await db.execute(stmt)
    voting_round = result.scalar_one_or_none()

    if voting_round is None or voting_round.deleted_at is not None:
        raise ValueError("Voting round not found.")

    if voting_round.status != RoundStatus.VOTING_OPEN:
        raise ValueError("Can only close VOTING_OPEN rounds.")

    voting_round.closed_at = datetime.now(timezone.utc)
    voting_round.status = RoundStatus.VOTING_CLOSED

    await db.flush()
    return voting_round

async def proclaim_voting_round(
    db: AsyncSession,
    round_id: uuid.UUID,
) -> VotingRound:
    stmt = select(VotingRound).where(VotingRound.id == round_id).with_for_update()
    result = await db.execute(stmt)
    voting_round = result.scalar_one_or_none()

    if voting_round is None or voting_round.deleted_at is not None:
        raise ValueError("Voting round not found.")

    if voting_round.status != RoundStatus.VOTING_CLOSED:
        raise ValueError("Cannot proclaim voting round: status must be 'VOTING_CLOSED'.")

    voting_type = await voting_type_repository.get_by_id(
        db, voting_round.voting_type_id,
    )
    if voting_type is None:
        raise ValueError("Voting type not found.")

    leg_session = await legislative_session_repository.get_by_id(
        db, voting_round.legislative_session_id,
    )
    if leg_session is None:
        raise ValueError("Legislative session not found.")

    if voting_round.is_nominal:
        vote_counts = await vote_repository.count_nominal_votes_by_round(db, round_id)
        aff = vote_counts.get(VoteValue.AFFIRMATIVE, 0)
        neg = vote_counts.get(VoteValue.NEGATIVE, 0)
        abst = vote_counts.get(VoteValue.ABSTENTION, 0)
    else:
        vote_counts = await vote_repository.count_non_nominal_tallies_by_round(db, round_id)
        aff = vote_counts.get(VoteValue.AFFIRMATIVE, 0)
        neg = vote_counts.get(VoteValue.NEGATIVE, 0)
        abst = vote_counts.get(VoteValue.ABSTENTION, 0)
        
        stmt = select(func.count(NonNominalVoter.id)).where(
            NonNominalVoter.voting_round_id == round_id,
        )
        total_votes_cast = await db.scalar(stmt)
        
        total_tallies = aff + neg + abst
        if total_tallies > total_votes_cast:
            raise ValueError("Integrity error: tally votes exceed authorized participants.")

    total_members = await legislator_repository.count_active_legislators(db)
    quorum_present = voting_round.certified_quorum_count or voting_round.quorum_present_count or 0
    
    leg_session = await legislative_session_repository.get_by_id(db, voting_round.legislative_session_id)
    if leg_session:
        total_members = calculate_effective_denominator(
            calculation_base=CalculationBase.TOTAL_MEMBERS,
            president_type=leg_session.pres_type,
            president_votes_ordinarily=voting_round.president_votes_ordinarily,
            raw_quorum=quorum_present,
            raw_total_members=total_members,
            votes_cast=aff + neg,
        )

    result = calculate_round_result(
        affirmative=aff,
        negative=neg,
        calc_base=voting_type.calc_base,
        threshold=Decimal(str(voting_type.approval_threshold)),
        quorum_present=quorum_present,
        total_members=total_members,
        abstentions=abst,
    )

    voting_round.result = result

    if result == "TIED":
        voting_round.status = RoundStatus.TIED
    else:
        voting_round.status = RoundStatus.RESOLVED

        # Update parent AgendaItem
        stmt_ai = select(AgendaItem).where(AgendaItem.id == voting_round.agenda_item_id).with_for_update()
        result_ai = await db.execute(stmt_ai)
        agenda_item = result_ai.scalar_one_or_none()
        if agenda_item:
            if result == "PASSED":
                if voting_round.stage == RoundStage.GENERAL:
                    agenda_item.status = ItemStatus.APPROVED_IN_GENERAL
                elif voting_round.stage in [RoundStage.SINGLE, RoundStage.SPECIFIC]:
                    agenda_item.status = ItemStatus.APPROVED
            else:
                if voting_round.stage in [RoundStage.SINGLE, RoundStage.GENERAL]:
                    agenda_item.status = ItemStatus.REJECTED

    await db.flush()
    return voting_round

async def rectify_voting_round(
    db: AsyncSession,
    round_id: uuid.UUID,
) -> VotingRound:
    stmt = select(VotingRound).where(VotingRound.id == round_id).with_for_update()
    result = await db.execute(stmt)
    voting_round = result.scalar_one_or_none()

    if voting_round is None or voting_round.deleted_at is not None:
        raise ValueError("Voting round not found.")

    if voting_round.status == RoundStatus.RESOLVED:
        raise ValueError("Cannot rectify a round that has already been RESOLVED.")

    # Mark the current round as ABORTED (implicit voiding of votes)
    voting_round.status = RoundStatus.ABORTED

    # Clone the round
    new_round = VotingRound(
        agenda_item_id=voting_round.agenda_item_id,
        legislative_session_id=voting_round.legislative_session_id,
        voting_type_id=voting_round.voting_type_id,
        is_nominal=voting_round.is_nominal,
        president_votes_ordinarily=voting_round.president_votes_ordinarily,
        stage=voting_round.stage,
        specific_reference=voting_round.specific_reference,
        time_limit_seconds=voting_round.time_limit_seconds,
        status=RoundStatus.DRAFT,
    )
    
    key = RSA.generate(3072)
    
    # Encrypt the ephemeral private key at rest using Fernet
    pem_private = key.export_key(format='PEM')
    f = Fernet(settings.security.EPHEMERAL_KEY_ENCRYPTION_KEY.encode('utf-8'))
    new_round.ephemeral_private_key = f.encrypt(pem_private).decode('utf-8')
    
    new_round.ephemeral_public_key = key.publickey().export_key(format='PEM').decode('utf-8')
    
    await db.flush()
    return await voting_round_repository.create(db, voting_round=new_round)

async def get_voting_type_for_round(
    db: AsyncSession,
    round_id: uuid.UUID,
):
    voting_round = await voting_round_repository.get_by_id(db, round_id)
    if voting_round is None:
        return None
    return await voting_type_repository.get_by_id(db, voting_round.voting_type_id)

async def get_session_for_round(
    db: AsyncSession,
    round_id: uuid.UUID,
):
    voting_round = await voting_round_repository.get_by_id(db, round_id)
    if voting_round is None:
        return None
    return await legislative_session_repository.get_by_id(
        db, voting_round.legislative_session_id,
    )

async def get_agenda_item_for_round(
    db: AsyncSession,
    round_id: uuid.UUID,
):
    voting_round = await voting_round_repository.get_by_id(db, round_id)
    if voting_round is None:
        return None
    return await agenda_item_repository.get_by_id(db, voting_round.agenda_item_id)
