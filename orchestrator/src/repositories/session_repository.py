import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.models.system_user_session import SystemUserSession

async def create_session(
    db: AsyncSession,
    *,
    session_id: str,
    user_id: uuid.UUID,
    ip_address: str | None,
    user_agent: str | None,
    expires_at: datetime,
) -> SystemUserSession:
    session_row = SystemUserSession(
        session_id=session_id,
        user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        expires_at=expires_at,
    )
    db.add(session_row)
    await db.flush()
    return session_row

async def get_session_with_user(
    db: AsyncSession,
    session_id: str,
) -> SystemUserSession | None:
    stmt = (
        select(SystemUserSession)
        .options(joinedload(SystemUserSession.user))
        .where(
            SystemUserSession.session_id == session_id,
            SystemUserSession.expires_at > datetime.now().astimezone(),
        )
    )
    result = await db.execute(stmt)
    session_row = result.scalar_one_or_none()

    if session_row is None:
        return None

    if not session_row.user.deleted_at is None:
        return None

    return session_row

async def delete_session(
    db: AsyncSession,
    session_id: str,
) -> None:
    stmt = (
        select(SystemUserSession)
        .where(
            SystemUserSession.session_id == session_id,
        )
    )
    result = await db.execute(stmt)
    session_row = result.scalar_one_or_none()

    if session_row is not None:
        await db.delete(session_row)
        await db.flush()
