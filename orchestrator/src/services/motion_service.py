import uuid
from datetime import datetime, timezone
from decimal import Decimal
from math import ceil
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.websocket import ConnectionManager
from src.models.legislative_session import PresidentType
from src.models.motion import Motion, MotionStatus
from src.models.nominal_vote import NominalVoteValue
from src.models.voting_type import CalculationBase
from src.repositories import (
    legislative_session_repository,
    legislator_repository,
    motion_repository,
    vote_repository,
    voting_type_repository,
)
from src.services.quorum_service import compute_quorum_minimum, get_motion_quorum

def calculate_motion_result(
    affirmative: int,
    negative: int,
    calc_base: CalculationBase,
    threshold: Decimal,
    quorum_present: int,
    total_members: int,
) -> str:
    # Compute the denominator
    if calc_base == CalculationBase.VOTES_CAST:
        denominator = affirmative + negative
    elif calc_base == CalculationBase.MEMBERS_PRESENT:
        denominator = quorum_present
    else: 
        denominator = total_members

    # Guard against zero-division
    if denominator == 0:
        return "FAILED"

    # Tie always means affirmative == negative
    if affirmative == negative:
        return "TIED"

    # Simple plurality (threshold == 0)
    # Whoever has more votes wins; no fraction of denominator required.
    if threshold == Decimal(0):
        if affirmative > negative:
            return "PASSED"
        return "FAILED"

    # Threshold-based majority (absolute or special)
    # Use ceiling to compute the minimum required affirmative votes.
    required = ceil(float(denominator) * float(threshold) / 100.0)

    if affirmative >= required:
        return "PASSED"

    return "FAILED"

async def list_motions_by_session(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> list[Motion]:
    session = await legislative_session_repository.get_by_id(db, session_id)

    if session is None or session.deleted_at is not None:
        raise ValueError("Legislative session not found.")

    return await motion_repository.get_by_session_id(db, session_id)

async def get_motion(db: AsyncSession, motion_id: uuid.UUID) -> Motion:
    motion = await motion_repository.get_by_id(db, motion_id)

    if motion is None or motion.deleted_at is not None:
        raise ValueError("Motion not found.")

    return motion

async def create_motion(
    db: AsyncSession,
    *,
    session_id: uuid.UUID,
    title: str,
    summary: str | None = None,
    voting_type_id: uuid.UUID,
    is_nominal: bool = True,
    president_votes_ordinarily: bool = False,
) -> Motion:
    session = await legislative_session_repository.get_by_id(db, session_id)

    if session is None or session.deleted_at is not None:
        raise ValueError("Legislative session not found.")

    voting_type = await voting_type_repository.get_by_id(db, voting_type_id)
    if voting_type is None or voting_type.deleted_at is not None:
        raise ValueError("Voting type not found.")

    motion = Motion(
        legislative_session_id=session_id,
        title=title,
        summary=summary,
        voting_type_id=voting_type_id,
        is_nominal=is_nominal,
        president_votes_ordinarily=president_votes_ordinarily,
    )
    return await motion_repository.create(db, motion=motion)

async def update_motion(
    db: AsyncSession,
    motion_id: uuid.UUID,
    *,
    update_data: dict[str, Any],
) -> Motion:
    motion = await motion_repository.get_by_id(db, motion_id)

    if motion is None or motion.deleted_at is not None:
        raise ValueError("Motion not found.")

    if motion.status != MotionStatus.DRAFT:
        raise ValueError(
            "Cannot update motion: only motions with status 'DRAFT' "
            "can be modified.",
        )

    if "voting_type_id" in update_data:
        voting_type = await voting_type_repository.get_by_id(
            db, update_data["voting_type_id"],
        )
        if voting_type is None or voting_type.deleted_at is not None:
            raise ValueError("Voting type not found.")

    for field, value in update_data.items():
        setattr(motion, field, value)

    await db.flush()
    return motion

async def soft_delete_motion(
    db: AsyncSession,
    motion_id: uuid.UUID,
) -> Motion:
    motion = await motion_repository.get_by_id(db, motion_id)

    if motion is None or motion.deleted_at is not None:
        raise ValueError("Motion not found.")

    if motion.status != MotionStatus.DRAFT:
        raise ValueError(
            "Cannot delete motion: only motions with status 'DRAFT' "
            "can be deleted.",
        )

    motion.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    return motion

async def update_motion_status(
    db: AsyncSession,
    motion_id: uuid.UUID,
    *,
    new_status: MotionStatus,
    ws_manager: ConnectionManager,
) -> Motion:
    motion = await motion_repository.get_by_id(db, motion_id)

    if motion is None or motion.deleted_at is not None:
        raise ValueError("Motion not found.")

    now = datetime.now(timezone.utc)

    if new_status == MotionStatus.VOTING_OPEN:
        existing_open = await motion_repository.get_open_motion_in_session(
            db, motion.legislative_session_id,
        )
        if existing_open is not None and existing_open.id != motion.id:
            raise ValueError(
                "Cannot open voting: another motion is already open "
                "in this session.",
            )

        # Quorum guard: validate sufficient legislators before opening.
        leg_session = await legislative_session_repository.get_by_id(
            db, motion.legislative_session_id,
        )
        if leg_session is None:
            raise ValueError("Legislative session not found.")

        quorum_present, total_members = await get_motion_quorum(
            db,
            leg_session,
            ws_manager,
            president_votes_ordinarily=motion.president_votes_ordinarily,
        )
        quorum_minimum = compute_quorum_minimum(total_members)

        if quorum_present < quorum_minimum:
            raise ValueError(
                f"No quorum: {quorum_present} legislators present, "
                f"{quorum_minimum} required (out of {total_members} total).",
            )

        # Snapshot the quorum count for use in vote calculation.
        motion.quorum_present_count = quorum_present
        motion.opened_at = now

    if new_status == MotionStatus.VOTING_CLOSED:
        motion.closed_at = now

    motion.status = new_status
    await db.flush()
    return motion

async def resolve_motion(
    db: AsyncSession,
    motion_id: uuid.UUID,
    *,
    affirmative: int | None = None,
    negative: int | None = None,
    abstentions: int | None = None,
    ws_manager: ConnectionManager,
) -> Motion:
    motion = await motion_repository.get_by_id(db, motion_id)

    if motion is None or motion.deleted_at is not None:
        raise ValueError("Motion not found.")

    if motion.status != MotionStatus.VOTING_CLOSED:
        raise ValueError(
            "Cannot resolve motion: status must be 'VOTING_CLOSED'.",
        )

    voting_type = await voting_type_repository.get_by_id(db, motion.voting_type_id)
    if voting_type is None:
        raise ValueError("Voting type not found.")

    leg_session = await legislative_session_repository.get_by_id(
        db, motion.legislative_session_id,
    )
    if leg_session is None:
        raise ValueError("Legislative session not found.")

    if motion.is_nominal:
        vote_counts = await vote_repository.count_nominal_votes_by_motion(
            db, motion_id,
        )
        aff = vote_counts.get(NominalVoteValue.AFFIRMATIVE, 0)
        neg = vote_counts.get(NominalVoteValue.NEGATIVE, 0)
    else:
        if affirmative is None or negative is None:
            raise ValueError(
                "Non-nominal motions require affirmative and negative "
                "counts to be provided.",
            )
        aff = affirmative
        neg = negative

    total_members = await legislator_repository.count_active_legislators(db)
    quorum_present = motion.quorum_present_count or 0

    if (
        leg_session.pres_type == PresidentType.EX_OFFICIO
        and leg_session.presiding_officer_id is not None
    ):
        total_members -= 1
        quorum_present -= 1
    elif (
        leg_session.pres_type == PresidentType.LEGISLATOR
        and not motion.president_votes_ordinarily
        and leg_session.presiding_officer_id is not None
    ):
        # Mathematically treated as ex-officio for this vote.
        total_members -= 1
        quorum_present -= 1

    # Ensure non-negative after adjustment.
    quorum_present = max(quorum_present, 0)
    total_members = max(total_members, 0)

    result = calculate_motion_result(
        affirmative=aff,
        negative=neg,
        calc_base=voting_type.calc_base,
        threshold=Decimal(str(voting_type.approval_threshold)),
        quorum_present=quorum_present,
        total_members=total_members,
    )

    motion.result = result

    if result == "TIED":
        motion.status = MotionStatus.TIED
    else:
        motion.status = MotionStatus.RESOLVED

    await db.flush()
    return motion

async def reopen_motion(
    db: AsyncSession,
    motion_id: uuid.UUID,
) -> Motion:
    motion = await motion_repository.get_by_id(db, motion_id)

    if motion is None or motion.deleted_at is not None:
        raise ValueError("Motion not found.")

    if motion.status != MotionStatus.TIED:
        raise ValueError(
            "Cannot reopen motion: only motions with status 'TIED' "
            "can be reopened.",
        )

    # Void non-nominal votes to prevent replay on revote.
    await motion_repository.void_non_nominal_votes(db, motion_id)

    motion.status = MotionStatus.DRAFT
    motion.opened_at = None
    motion.closed_at = None
    motion.quorum_present_count = None
    motion.result = None
    motion.tie_breaker_vote_value = None
    await db.flush()
    return motion

async def abort_motion(
    db: AsyncSession,
    motion_id: uuid.UUID,
) -> Motion:
    motion = await motion_repository.get_by_id(db, motion_id)

    if motion is None or motion.deleted_at is not None:
        raise ValueError("Motion not found.")

    await motion_repository.void_non_nominal_votes(db, motion_id)

    motion.status = MotionStatus.DRAFT
    motion.opened_at = None
    motion.closed_at = None
    motion.quorum_present_count = None
    motion.result = None
    motion.tie_breaker_vote_value = None
    await db.flush()
    return motion

async def get_voting_type_for_motion(
    db: AsyncSession,
    motion_id: uuid.UUID,
):
    motion = await motion_repository.get_by_id(db, motion_id)
    if motion is None:
        return None
    voting_type = await voting_type_repository.get_by_id(db, motion.voting_type_id)
    return voting_type

async def get_session_for_motion(
    db: AsyncSession,
    motion_id: uuid.UUID,
):
    motion = await motion_repository.get_by_id(db, motion_id)
    if motion is None:
        return None
    session = await legislative_session_repository.get_by_id(db, motion.legislative_session_id)
    return session