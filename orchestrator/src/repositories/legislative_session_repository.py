import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.legislative_session import LegislativeSession, LegSessionStatus

async def get_all_active(db: AsyncSession) -> list[LegislativeSession]:
    stmt = (
        select(LegislativeSession)
        .where(
            LegislativeSession.deleted_at.is_(None),
        )
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())

async def get_by_id(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> LegislativeSession | None:
    stmt = (
        select(LegislativeSession)
        .where(
            LegislativeSession.id == session_id,
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def get_current_active(
    db: AsyncSession,
) -> LegislativeSession | None:
    stmt = (
        select(LegislativeSession)
        .where(
            LegislativeSession.status == LegSessionStatus.ACTIVE,
            LegislativeSession.deleted_at.is_(None),
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def create(
    db: AsyncSession,
    *,
    session: LegislativeSession,
) -> LegislativeSession:
    db.add(session)
    await db.flush()
    return session
