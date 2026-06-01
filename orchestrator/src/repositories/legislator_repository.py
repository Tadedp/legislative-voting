import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.models.device import Device
from src.models.legislator import Legislator

async def get_all_active(db: AsyncSession) -> list[Legislator]:
    stmt = (
        select(Legislator)
        .options(joinedload(Legislator.device))
        .where(
            Legislator.deleted_at.is_(None),
        )
    )
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())

async def get_by_id(
    db: AsyncSession,
    legislator_id: uuid.UUID,
) -> Legislator | None:
    stmt = (
        select(Legislator)
        .options(joinedload(Legislator.device))
        .where(
            Legislator.id == legislator_id,
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def get_by_national_id(
    db: AsyncSession,
    national_id: str,
) -> Legislator | None:
    stmt = (
        select(Legislator)
        .where(
            Legislator.national_id == national_id,
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def create(db: AsyncSession, *, legislator: Legislator) -> Legislator:
    db.add(legislator)
    await db.flush()
    return legislator

async def create_device(db: AsyncSession, *, device: Device) -> Device:
    db.add(device)
    await db.flush()
    return device

async def count_active_legislators(db: AsyncSession) -> int:    
    stmt = (
        select(func.count(Legislator.id))
        .where(Legislator.deleted_at.is_(None))
    )
    result = await db.execute(stmt)
    return result.scalar_one()