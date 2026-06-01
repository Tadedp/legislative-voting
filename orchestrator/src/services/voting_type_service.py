import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.voting_type import VotingType
from src.repositories import voting_type_repository

async def list_voting_types(db: AsyncSession) -> list[VotingType]:
    return await voting_type_repository.get_all_active(db)

async def get_voting_type(
    db: AsyncSession,
    voting_type_id: uuid.UUID,
) -> VotingType:
    voting_type = await voting_type_repository.get_by_id(db, voting_type_id)

    if voting_type is None or voting_type.deleted_at is not None:
        raise ValueError("Voting type not found.")

    return voting_type

async def create_voting_type(
    db: AsyncSession,
    *,
    name: str,
    allows_abstentions: bool = True,
    approval_threshold: float,
    calc_base: str | None = None,
) -> VotingType:
    existing = await voting_type_repository.get_by_name(db, name)
    if existing is not None:
        raise ValueError(f"Voting type with name '{name}' already exists.")

    kwargs: dict[str, object] = {
        "name": name,
        "allows_abstentions": allows_abstentions,
        "approval_threshold": approval_threshold,
    }
    if calc_base is not None:
        kwargs["calc_base"] = calc_base

    voting_type = VotingType(**kwargs)

    return await voting_type_repository.create(db, voting_type=voting_type)

async def update_voting_type(
    db: AsyncSession,
    voting_type_id: uuid.UUID,
    *,
    update_data: dict[str, Any],
) -> VotingType:
    voting_type = await voting_type_repository.get_by_id(db, voting_type_id)

    if voting_type is None or voting_type.deleted_at is not None:
        raise ValueError("Voting type not found.")

    if (
        "name" in update_data
        and update_data["name"] != voting_type.name
    ):
        existing = await voting_type_repository.get_by_name(
            db, update_data["name"],
        )
        if existing is not None:
            raise ValueError(
                f"Voting type with name '{update_data['name']}' already exists.",
            )

    for field, value in update_data.items():
        setattr(voting_type, field, value)

    await db.flush()
    await db.refresh(voting_type)
    return voting_type

async def soft_delete_voting_type(
    db: AsyncSession,
    voting_type_id: uuid.UUID,
) -> VotingType:
    voting_type = await voting_type_repository.get_by_id(db, voting_type_id)

    if voting_type is None or voting_type.deleted_at is not None:
        raise ValueError("Voting type not found.")

    has_motions = await voting_type_repository.has_active_motions(
        db, voting_type_id,
    )
    if has_motions:
        raise ValueError(
            "Cannot delete voting type: it is currently linked to active motions.",
        )

    voting_type.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(voting_type)
    return voting_type