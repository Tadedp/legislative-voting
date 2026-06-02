import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agenda_item import AgendaItem

async def get_all_active(db: AsyncSession) -> list[AgendaItem]:
    stmt = select(AgendaItem).where(AgendaItem.deleted_at.is_(None))
    result = await db.execute(stmt)
    return list(result.scalars().all())

async def get_by_id(
    db: AsyncSession,
    item_id: uuid.UUID,
) -> AgendaItem | None:
    stmt = select(AgendaItem).where(AgendaItem.id == item_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def create(
    db: AsyncSession,
    *,
    item: AgendaItem,
) -> AgendaItem:
    db.add(item)
    await db.flush()
    return item

async def get_active_on_floor(db: AsyncSession) -> AgendaItem | None:
    from src.models.agenda_item import ItemStatus
    stmt = select(AgendaItem).where(
        AgendaItem.deleted_at.is_(None),
        AgendaItem.status.in_([ItemStatus.DEBATE, ItemStatus.APPROVED_IN_GENERAL])
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
