import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import extract_public_key_from_cert
from src.models.device import Device
from src.models.legislator import Legislator
from src.repositories import legislator_repository
from src.services.renaper_client import renaper_client

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
    hardware_id: uuid.UUID,
    biometric_payload: str,
    certificate_chain: list[str],
) -> Legislator | None:
    existing = await legislator_repository.get_by_national_id(db, national_id)
    if existing is not None:
        raise ValueError(
            f"Legislator with national_id '{national_id}' already exists.",
        )

    # Verify legislator identity via the national registry (RENAPER).
    identity_ok = await renaper_client.verify_identity(
        national_id, biometric_payload,
    )
    if not identity_ok:
        raise ValueError("RENAPER identity verification failed.")

    # Extract the secp256k1 public key from the leaf X.509 certificate.
    device_public_key = extract_public_key_from_cert(certificate_chain[0])

    legislator = Legislator(
        national_id=national_id,
        full_name=full_name,
        current_public_key=device_public_key,
    )
    legislator = await legislator_repository.create(db, legislator=legislator)

    device_token = secrets.token_urlsafe(32)

    # Provision the device with the Android-generated hardware UUID.
    device = Device(
        legislator_id=legislator.id,
        hardware_id=hardware_id,
        device_token=device_token,
    )
    await legislator_repository.create_device(db, device=device)

    legislator = await legislator_repository.get_by_id(db, legislator.id)
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