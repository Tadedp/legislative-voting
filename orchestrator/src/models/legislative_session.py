import uuid
from datetime import datetime
from enum import unique, StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, func, text, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, SoftDeleteMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.legislator import Legislator
    from src.models.session_attendance import SessionAttendance
    from src.models.voting_round import VotingRound

@unique
class LegSessionStatus(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    CLOSED = "CLOSED"
    
@unique
class PresidentType(StrEnum):
    """Defines the constitutional role of the presiding officer.

    EX_OFFICIO: External president; does not count toward quorum or vote
                ordinarily. May only cast a tie-breaking vote.
    LEGISLATOR: President who is also a member of the legislative body.
                Counts toward quorum and may vote ordinarily.
    """

    EX_OFFICIO = "EX_OFFICIO"
    LEGISLATOR = "LEGISLATOR"

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
    pres_type: Mapped[PresidentType] = mapped_column(
        Enum(PresidentType, name="president_type"),
        server_default=text("'EX_OFFICIO'"),
        nullable=False,
    )
    presiding_officer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("legislators.id", ondelete="SET NULL"),
        nullable=True,
    )

    voting_rounds: Mapped[list["VotingRound"]] = relationship(
        "VotingRound",
        back_populates="legislative_session",
        lazy="raise_on_sql",
    )
    presiding_officer: Mapped[Legislator | None] = relationship(
        "Legislator",
        foreign_keys=[presiding_officer_id],
        lazy="raise_on_sql",
    )
    session_attendances: Mapped[list["SessionAttendance"]] = relationship(
        "SessionAttendance",
        back_populates="legislative_session",
        lazy="raise_on_sql",
    )