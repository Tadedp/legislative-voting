import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.system_user import SystemUser

async def get_all_active(db: AsyncSession) -> list[SystemUser]:
    stmt = (
        select(SystemUser)
        .where(
            SystemUser.deleted_at.is_(None),
        )
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())

async def get_by_id(db: AsyncSession, user_id: uuid.UUID) -> SystemUser | None:
    stmt = (
        select(SystemUser)
        .where(
            SystemUser.id == user_id,
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def get_by_username(db: AsyncSession, username: str) -> SystemUser | None:
    stmt = (
        select(SystemUser)
        .where(
            SystemUser.username == username,
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def create(db: AsyncSession, *, user: SystemUser) -> SystemUser:
    db.add(user)
    await db.flush()
    return user