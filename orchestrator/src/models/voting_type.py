from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Numeric, Text, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, SoftDeleteMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.motion import Motion

class VotingType(Base, UUIDPrimaryKeyMixin, SoftDeleteMixin):
    __tablename__ = "voting_types"

    name: Mapped[str] = mapped_column(
        Text,
        unique=True,
        nullable=False,
    )
    allows_abstentions: Mapped[bool] = mapped_column(
        Boolean,
        server_default=true(),
        nullable=False,
    )
    approval_threshold: Mapped[float] = mapped_column(
        Numeric(precision=5, scale=2),
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

    motions: Mapped[list[Motion]] = relationship(
        "Motion",
        back_populates="voting_type",
        lazy="raise_on_sql",
    )
