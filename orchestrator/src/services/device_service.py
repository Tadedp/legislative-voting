import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.device import Device
from src.repositories import device_repository

async def wipe_device(
    db: AsyncSession,
    device_id: uuid.UUID,
) -> tuple[Device, str]:
    device = await device_repository.get_by_id(db, device_id)

    if device is None or device.deleted_at is not None:
        raise ValueError("Device not found.")

    old_device_token = device.device_token

    now = datetime.now(timezone.utc)

    device.deleted_at = now
    device.device_token = f"REVOKED_{secrets.token_urlsafe(32)}"

    #legislator = device.legislator
    #if legislator is not None:
    #    legislator.deleted_at = now

    await db.flush()
    return device, old_device_token
