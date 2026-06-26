import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agenda_item import AgendaItem, ItemCategory
from src.repositories import agenda_item_repository, voting_round_repository
from src.models.voting_round import RoundStatus

async def list_agenda_items(db: AsyncSession) -> list[AgendaItem]:
    return await agenda_item_repository.get_all_active(db)

async def get_agenda_item(
    db: AsyncSession,
    item_id: uuid.UUID,
) -> AgendaItem:
    item = await agenda_item_repository.get_by_id(db, item_id)

    if item is None or item.deleted_at is not None:
        raise ValueError("Tema de agenda no encontrado.")

    return item

async def create_agenda_item(
    db: AsyncSession,
    *,
    category: ItemCategory,
    title: str,
    summary: str | None = None,
    file_number: str | None = None,
) -> AgendaItem:
    item = AgendaItem(
        category=category,
        title=title,
        summary=summary,
        file_number=file_number,
    )
    return await agenda_item_repository.create(db, item=item)

async def update_agenda_item(
    db: AsyncSession,
    item_id: uuid.UUID,
    *,
    update_data: dict[str, Any],
) -> AgendaItem:
    item = await agenda_item_repository.get_by_id(db, item_id)

    if item is None or item.deleted_at is not None:
        raise ValueError("Tema de agenda no encontrado.")

    for field, value in update_data.items():
        setattr(item, field, value)

    await db.flush()
    return item

async def soft_delete_agenda_item(
    db: AsyncSession,
    item_id: uuid.UUID,
) -> AgendaItem:
    item = await agenda_item_repository.get_by_id(db, item_id)

    if item is None or item.deleted_at is not None:
        raise ValueError("Tema de agenda no encontrado.")

    # Check for active voting rounds
    rounds = await voting_round_repository.get_by_agenda_item_id(db, item_id)
    for r in rounds:
        if r.status in (RoundStatus.DRAFT, RoundStatus.VOTING_OPEN, RoundStatus.VOTING_CLOSED):
            raise ValueError(
                "No se puede eliminar el tema: posee rondas de votación "
                f"en estado activo ({r.status.value})."
            )

    item.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    return item
