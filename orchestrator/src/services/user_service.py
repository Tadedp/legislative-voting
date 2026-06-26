from datetime import datetime, timezone
from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import hash_password
from src.models.system_user import SystemUser, SystemUserRole
from src.repositories import user_repository

async def list_users(db: AsyncSession) -> list[SystemUser]:
    return await user_repository.get_all_active(db)

async def get_user(db: AsyncSession, user_id: uuid.UUID) -> SystemUser:
    user = await user_repository.get_by_id(db, user_id)

    if user is None or user.deleted_at is not None:
        raise ValueError("Usuario no encontrado.")

    return user

async def create_user(
    db: AsyncSession,
    *,
    username: str,
    password: str,
    role: SystemUserRole,
) -> SystemUser:
    existing = await user_repository.get_by_username(db, username)
    if existing is not None:
        raise ValueError(f"El usuario '{username}' ya está en uso.")

    password_hash = await hash_password(password)

    user = SystemUser(
        username=username,
        password_hash=password_hash,
        role=role,
    )

    return await user_repository.create(db, user=user)

async def update_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    update_data: dict[str, Any],
) -> SystemUser:
    user = await user_repository.get_by_id(db, user_id)

    if user is None or user.deleted_at is not None:
        raise ValueError("Usuario no encontrado.")

    if "password" in update_data:
        raw_password = update_data.pop("password")
        update_data["password_hash"] = await hash_password(raw_password)

    if "username" in update_data and update_data["username"] != user.username:
        existing = await user_repository.get_by_username(
            db, update_data["username"],
        )
        if existing is not None:
            raise ValueError(
                f"Username '{update_data['username']}' is already taken.",
            )

    for field, value in update_data.items():
        setattr(user, field, value)

    await db.flush()
    await db.refresh(user)
    return user

async def soft_delete_user(db: AsyncSession, user_id: uuid.UUID) -> SystemUser:
    user = await user_repository.get_by_id(db, user_id)

    if user is None or user.deleted_at is not None:
        raise ValueError("Usuario no encontrado.")

    user.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(user)
    return user