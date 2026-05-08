from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
