import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.nominal_vote import NominalVote, NominalVoteValue
from src.models.non_nominal_vote import NonNominalVote

async def create_nominal_vote(
    db: AsyncSession,
    *,
    vote: NominalVote,
) -> NominalVote:
    db.add(vote)
    await db.flush()
    return vote

async def create_non_nominal_vote(
    db: AsyncSession,
    *,
    vote: NonNominalVote,
) -> NonNominalVote:
    db.add(vote)
    await db.flush()
    return vote

async def get_non_nominal_votes_by_motion(
    db: AsyncSession,
    motion_id: uuid.UUID,
) -> list[NonNominalVote]:
    stmt = (
        select(NonNominalVote)
        .where(
            NonNominalVote.motion_id == motion_id,
        )
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())

async def count_nominal_votes_by_motion(
    db: AsyncSession,
    motion_id: uuid.UUID,
) -> dict[NominalVoteValue, int]:
    stmt = (
        select(NominalVote.vote_value, func.count())
        .where(NominalVote.motion_id == motion_id)
        .group_by(NominalVote.vote_value)
    )
    result = await db.execute(stmt)
    return {row[0]: row[1] for row in result.all()}