import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, func, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.system_user import SystemUser

class SystemUserSession(Base):
    __tablename__ = "system_users_sessions"

    session_id: Mapped[str] = mapped_column(
        Text,
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("system_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    ip_address: Mapped[str | None] = mapped_column(
        Text, 
        nullable=True,
    )
    user_agent: Mapped[str | None] = mapped_column(
        Text, 
        nullable=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped[SystemUser] = relationship(
        "SystemUser",
        back_populates="sessions",
        lazy="raise_on_sql",
    )
