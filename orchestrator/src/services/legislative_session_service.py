import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.legislative_session import LegislativeSession, LegSessionStatus
from src.models.motion import Motion
from src.repositories import legislative_session_repository, motion_repository

async def list_legislative_sessions(db: AsyncSession) -> list[LegislativeSession]:
    return await legislative_session_repository.get_all_active(db)

async def get_legislative_session(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> LegislativeSession:
    session = await legislative_session_repository.get_by_id(db, session_id)

    if session is None or session.deleted_at is not None:
        raise ValueError("Legislative session not found.")

    return session

async def create_legislative_session(
    db: AsyncSession,
    *,
    title: str,
) -> LegislativeSession:
    session = LegislativeSession(title=title)
    return await legislative_session_repository.create(db, session=session)

async def update_legislative_session(
    db: AsyncSession,
    session_id: uuid.UUID,
    *,
    update_data: dict[str, Any],
) -> LegislativeSession:
    session = await legislative_session_repository.get_by_id(db, session_id)

    if session is None or session.deleted_at is not None:
        raise ValueError("Legislative session not found.")

    if session.status != LegSessionStatus.PENDING:
        raise ValueError(
            "Cannot update session: only sessions with status "
            "'PENDING' can be modified.",
        )

    for field, value in update_data.items():
        setattr(session, field, value)

    await db.flush()
    return session

async def soft_delete_legislative_session(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> LegislativeSession:
    session = await legislative_session_repository.get_by_id(db, session_id)

    if session is None or session.deleted_at is not None:
        raise ValueError("Legislative session not found.")

    if session.status != LegSessionStatus.PENDING:
        raise ValueError(
            "Cannot delete session: only sessions with status "
            "'PENDING' can be deleted.",
        )

    session.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    return session

async def set_ephemeral_key(
    db: AsyncSession,
    session_id: uuid.UUID,
    *,
    ephemeral_public_key: str,
) -> LegislativeSession:
    session = await legislative_session_repository.get_by_id(db, session_id)

    if session is None or session.deleted_at is not None:
        raise ValueError("Legislative session not found.")

    session.ephemeral_public_key = ephemeral_public_key
    await db.flush()
    return session

async def update_legislative_session_status(
    db: AsyncSession,
    session_id: uuid.UUID,
    *,
    new_status: LegSessionStatus,
) -> LegislativeSession:
    session = await legislative_session_repository.get_by_id(db, session_id)

    if session is None or session.deleted_at is not None:
        raise ValueError("Legislative session not found.")

    now = datetime.now(timezone.utc)

    if new_status == LegSessionStatus.ACTIVE and session.opened_at is None:
        session.opened_at = now
    elif new_status == LegSessionStatus.CLOSED:
        session.closed_at = now

    session.status = new_status
    await db.flush()
    return session

async def get_current_legislative_session(
    db: AsyncSession,
) -> tuple[LegislativeSession, Motion | None]:
    session = await legislative_session_repository.get_current_active(db)

    if session is None:
        raise ValueError("No active legislative session.")

    active_motion = await motion_repository.get_open_motion_in_session(
        db, session.id,
    )

    return session, active_motion