from datetime import datetime, timezone
from typing import Any
import uuid

import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.system_user import SystemUser, SystemUserRole
from src.repositories import user_repository

async def list_users(db: AsyncSession) -> list[SystemUser]:
    return await user_repository.get_all_active(db)

async def get_user(db: AsyncSession, user_id: uuid.UUID) -> SystemUser:
    user = await user_repository.get_by_id(db, user_id)

    if user is None or user.deleted_at is not None:
        raise ValueError("User not found.")

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
        raise ValueError(f"Username '{username}' is already taken.")

    password_hash = bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")

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
        raise ValueError("User not found.")

    if "password" in update_data:
        raw_password = update_data.pop("password")
        update_data["password_hash"] = bcrypt.hashpw(
            raw_password.encode("utf-8"),
            bcrypt.gensalt(),
        ).decode("utf-8")

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
    return user

async def soft_delete_user(db: AsyncSession, user_id: uuid.UUID) -> SystemUser:
    user = await user_repository.get_by_id(db, user_id)

    if user is None or user.deleted_at is not None:
        raise ValueError("User not found.")

    user.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    return user