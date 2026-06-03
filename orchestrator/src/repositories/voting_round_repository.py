import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.voting_round import RoundStatus, VotingRound

async def get_by_session_id(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> list[VotingRound]:
    stmt = select(VotingRound).where(
        VotingRound.legislative_session_id == session_id,
        VotingRound.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())

async def get_by_id(
    db: AsyncSession,
    round_id: uuid.UUID,
) -> VotingRound | None:
    stmt = select(VotingRound).where(VotingRound.id == round_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def get_open_round_in_session(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> VotingRound | None:
    stmt = (
        select(VotingRound)
        .where(
            VotingRound.legislative_session_id == session_id,
            VotingRound.status == RoundStatus.VOTING_OPEN,
            VotingRound.deleted_at.is_(None),
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def has_passed_general_round(
    db: AsyncSession,
    agenda_item_id: uuid.UUID,
) -> bool:
    stmt = (
        select(VotingRound.id)
        .where(
            VotingRound.agenda_item_id == agenda_item_id,
            VotingRound.stage == "GENERAL",
            VotingRound.result == "PASSED",
            VotingRound.deleted_at.is_(None),
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None

async def create(
    db: AsyncSession,
    *,
    voting_round: VotingRound,
) -> VotingRound:
    db.add(voting_round)
    await db.flush()
    return voting_round
