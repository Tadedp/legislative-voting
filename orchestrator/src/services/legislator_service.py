import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import generate_provisioning_token
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

async def create_legislator(
    db: AsyncSession,
    *,
    national_id: str,
    full_name: str,
) -> Legislator:
    existing = await legislator_repository.get_by_national_id(db, national_id)
    if existing is not None:
        raise ValueError(
            f"Legislator with national_id '{national_id}' already exists.",
        )

    now = datetime.now(timezone.utc)
    
    token = generate_provisioning_token()

    legislator = Legislator(
        national_id=national_id,
        full_name=full_name,
        provisioning_token=token,
        provisioning_token_generated_at=now,
        provisioning_token_expires_at=now + timedelta(minutes=15),
    )
    legislator = await legislator_repository.create(db, legislator=legislator)
    return legislator

async def regenerate_provisioning_token(
    db: AsyncSession,
    legislator_id: uuid.UUID,
) -> Legislator:
    legislator = await legislator_repository.get_by_id(db, legislator_id)
    if legislator is None or legislator.deleted_at is not None:
        raise ValueError("Legislator not found.")
        
    now = datetime.now(timezone.utc)
    
    legislator.provisioning_token = generate_provisioning_token()
    legislator.provisioning_token_generated_at = now
    legislator.provisioning_token_expires_at = now + timedelta(minutes=15)
    
    await db.flush()
    await db.refresh(legislator)
    return legislator

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