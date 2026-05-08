from datetime import datetime
from enum import unique, StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Text, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, SoftDeleteMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.system_user_session import SystemUserSession

@unique
class SystemUserRole(StrEnum):
    ADMIN = "ADMIN"
    PRESIDENCY = "PRESIDENCY"
    AUDITOR = "AUDITOR"

class SystemUser(Base, UUIDPrimaryKeyMixin, SoftDeleteMixin):
    __tablename__ = "system_users"

    username: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    role: Mapped[SystemUserRole] = mapped_column(
        Enum(SystemUserRole, name="system_user_role"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )

    sessions: Mapped[list[SystemUserSession]] = relationship(
        "SystemUserSession",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise_on_sql",
    )
    
    __table_args__ = (
        Index(
            "uq_system_users_username_lower",
            func.lower(username),
            unique=True,
        ),
    )
