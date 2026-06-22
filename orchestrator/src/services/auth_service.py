import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.security import verify_password
from src.models.system_user import SystemUser
from src.repositories import session_repository

async def authenticate_user(
    db: AsyncSession,
    *,
    username: str,
    password: str,
) -> SystemUser:
    stmt = select(SystemUser).where(
        SystemUser.username == username,
        SystemUser.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise ValueError("Usuario o contraseña inválidos.")

    if not await verify_password(password, user.password_hash):
        raise ValueError("Usuario o contraseña inválidos.")

    return user

async def create_session(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> str:
    session_id = secrets.token_urlsafe(64)

    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=settings.security.SESSION_EXPIRY_SECONDS,
    )

    await session_repository.create_session(
        db,
        session_id=session_id,
        user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        expires_at=expires_at,
    )

    return session_id

async def destroy_session(
    db: AsyncSession,
    *,
    session_id: str,
) -> None:
    await session_repository.delete_session(db, session_id)
