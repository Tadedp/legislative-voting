import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.motion import Motion
from src.models.voting_type import VotingType

async def get_all_active(db: AsyncSession) -> list[VotingType]:
    stmt = (
        select(VotingType)
        .where(
            VotingType.deleted_at.is_(None),
        )
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())

async def get_by_id(
    db: AsyncSession,
    voting_type_id: uuid.UUID,
) -> VotingType | None:
    stmt = (
        select(VotingType)
        .where(
            VotingType.id == voting_type_id,
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def get_by_name(
    db: AsyncSession,
    name: str,
) -> VotingType | None:
    stmt = (
        select(VotingType)
        .where(
            VotingType.name == name,
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def has_active_motions(
    db: AsyncSession,
    voting_type_id: uuid.UUID,
) -> bool:
    stmt = (
        select(Motion.id)
        .where(
            Motion.voting_type_id == voting_type_id,
            Motion.deleted_at.is_(None),
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None

async def create(db: AsyncSession, *, voting_type: VotingType) -> VotingType:
    db.add(voting_type)
    await db.flush()
    return voting_type
