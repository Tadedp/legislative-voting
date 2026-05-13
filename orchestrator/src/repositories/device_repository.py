import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.models.device import Device

async def get_active_device_by_token(
    db: AsyncSession,
    token: str,
) -> Device | None:
    stmt = (
        select(Device)
        .where(
            Device.device_token == token,
            Device.deleted_at.is_(None)
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def get_by_id(
    db: AsyncSession,
    device_id: uuid.UUID,
) -> Device | None:
    stmt = (
        select(Device)
        .options(joinedload(Device.legislator))
        .where(
            Device.id == device_id,
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()