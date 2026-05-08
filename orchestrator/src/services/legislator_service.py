from datetime import datetime, timezone
import secrets
from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.device import Device
from src.models.legislator import Legislator
from src.repositories import legislator_repository

async def list_legislators(db: AsyncSession) -> list[Legislator]:
    return await legislator_repository.get_all_active(db)

async def get_legislator(
    db: AsyncSession,
    legislator_id: uuid.UUID,
) -> Legislator:
    legislator = await legislator_repository.get_by_id(db, legislator_id)

    if legislator is None or legislator.deleted_at is not None:
        raise ValueError("Legislator not found.")

    return legislator

async def enroll_legislator(
    db: AsyncSession,
    *,
    national_id: str,
    full_name: str,
    device_public_key: str,
    mac_address: str,
) -> Legislator:
    existing = await legislator_repository.get_by_national_id(db, national_id)
    if existing is not None:
        raise ValueError(
            f"Legislator with national_id '{national_id}' already exists.",
        )

    legislator = Legislator(
        national_id=national_id,
        full_name=full_name,
        current_public_key=device_public_key,
    )
    legislator = await legislator_repository.create(db, legislator=legislator)

    device_token = secrets.token_urlsafe(32)

    device = Device(
        legislator_id=legislator.id,
        mac_address=mac_address,
        device_token=device_token,
    )
    await legislator_repository.create_device(db, device=device)

    legislator = await legislator_repository.get_by_id(db, legislator.id)
    return legislator  # type: ignore[return-value]

async def update_legislator(
    db: AsyncSession,
    legislator_id: uuid.UUID,
    *,
    update_data: dict[str, Any],
) -> Legislator:
    legislator = await legislator_repository.get_by_id(db, legislator_id)

    if legislator is None or legislator.deleted_at is not None:
        raise ValueError("Legislator not found.")

    if (
        "national_id" in update_data
        and update_data["national_id"] != legislator.national_id
    ):
        existing = await legislator_repository.get_by_national_id(
            db, update_data["national_id"],
        )
        if existing is not None:
            raise ValueError(
                f"National ID '{update_data['national_id']}' is already registered.",
            )

    for field, value in update_data.items():
        setattr(legislator, field, value)

    await db.flush()
    await db.refresh(legislator)
    return legislator

async def soft_delete_legislator(
    db: AsyncSession,
    legislator_id: uuid.UUID,
) -> Legislator:
    legislator = await legislator_repository.get_by_id(db, legislator_id)

    if legislator is None or legislator.deleted_at is not None:
        raise ValueError("Legislator not found.")

    now = datetime.now(timezone.utc)
        
    legislator.deleted_at = now

    if legislator.device is not None:
        legislator.device.deleted_at = now

    await db.flush()
    await db.refresh(legislator)
    return legislator