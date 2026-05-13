import uuid
from datetime import datetime
from enum import unique, StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    func,
    Index,
    text,
    Text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, SoftDeleteMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.legislative_session import LegislativeSession
    from src.models.nominal_vote import NominalVote
    from src.models.non_nominal_vote import NonNominalVote
    from src.models.voting_type import VotingType
    
@unique
class MotionStatus(StrEnum):
    DRAFT = "DRAFT"
    VOTING_OPEN = "VOTING_OPEN"
    VOTING_CLOSED = "VOTING_CLOSED"
    RESOLVED = "RESOLVED"
    ABORTED = "ABORTED"

class Motion(UUIDPrimaryKeyMixin, SoftDeleteMixin, Base):
    __tablename__ = "motions"

    legislative_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("legislative_sessions.id"),
        nullable=False,
    )
    voting_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("voting_types.id"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    is_nominal: Mapped[bool] = mapped_column(
        Boolean,
        server_default=true(),
        nullable=False,
    )
    status: Mapped[MotionStatus] = mapped_column(
        Enum(MotionStatus, name="motion_status"),
        server_default=text("'DRAFT'"),
        nullable=False,
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

    legislative_session: Mapped[LegislativeSession] = relationship(
        "LegislativeSession",
        back_populates="motions",
        lazy="raise_on_sql",
    )
    voting_type: Mapped[VotingType] = relationship(
        "VotingType",
        back_populates="motions",
        lazy="raise_on_sql",
    )
    nominal_votes: Mapped[list[NominalVote]] = relationship(
        "NominalVote",
        back_populates="motion",
        lazy="raise_on_sql",
    )
    non_nominal_votes: Mapped[list[NonNominalVote]] = relationship(
        "NonNominalVote",
        back_populates="motion",
        lazy="raise_on_sql",
    )
    
    __table_args__ = (
        Index("idx_motions_session_id", "legislative_session_id"),
    )