from datetime import datetime
from enum import unique, StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, func, text, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, SoftDeleteMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.motion import Motion

@unique
class LegSessionStatus(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    CLOSED = "CLOSED"

class LegislativeSession(UUIDPrimaryKeyMixin, SoftDeleteMixin, Base):
    __tablename__ = "legislative_sessions"

    title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    status: Mapped[LegSessionStatus] = mapped_column(
        Enum(LegSessionStatus, name="legislative_session_status"),
        server_default=text("'PENDING'"),
        nullable=False,
    )
    ephemeral_public_key: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    opened_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    motions: Mapped[list[Motion]] = relationship(
        "Motion",
        back_populates="legislative_session",
        lazy="raise_on_sql",
    )
