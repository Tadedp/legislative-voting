import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, false, ForeignKey, func, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.legislator import Legislator
    from src.models.motion import Motion

class NonNominalVote(Base):
    __tablename__ = "non_nominal_votes"

    event_id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid7,
        server_default=text("uuidv7()"),
    )
    motion_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("motions.id"),
        nullable=False,
    )
    legislator_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("legislators.id"),
        nullable=False,
    )
    encrypted_payload: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    cryptographic_signature: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    is_voided: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=false(),
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    motion: Mapped[Motion] = relationship(
        "Motion",
        back_populates="non_nominal_votes",
        lazy="raise_on_sql",
    )
    legislator: Mapped[Legislator] = relationship(
        "Legislator",
        back_populates="non_nominal_votes",
        lazy="raise_on_sql",
    )

    __table_args__ = (
        UniqueConstraint(
            "motion_id",
            "legislator_id",
            name="uq_non_nominal_votes_motion_legislator",
        ),
    )