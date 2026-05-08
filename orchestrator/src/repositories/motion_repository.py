import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.motion import Motion, MotionStatus
from src.models.non_nominal_vote import NonNominalVote

async def get_by_session_id(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> list[Motion]:
    stmt = select(Motion).where(
        Motion.legislative_session_id == session_id,
        Motion.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())

async def get_by_id(
    db: AsyncSession,
    motion_id: uuid.UUID,
) -> Motion | None:
    stmt = (
        select(Motion)
        .where(
            Motion.id == motion_id,
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def get_open_motion_in_session(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> Motion | None:
    stmt = (
        select(Motion)
        .where(
            Motion.legislative_session_id == session_id,
            Motion.status == MotionStatus.VOTING_OPEN,
            Motion.deleted_at.is_(None),
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def create(db: AsyncSession, *, motion: Motion) -> Motion:
    db.add(motion)
    await db.flush()
    return motion

async def void_non_nominal_votes(
    db: AsyncSession,
    motion_id: uuid.UUID,
) -> None:
    stmt = (
        update(NonNominalVote)
        .where(NonNominalVote.motion_id == motion_id)
        .values(is_voided=True)
    )
    await db.execute(stmt)
    await db.flush()