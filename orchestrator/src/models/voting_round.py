import uuid
from datetime import datetime
from enum import unique, StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Text,
    false,
    func,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, SoftDeleteMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.agenda_item import AgendaItem
    from src.models.legislative_session import LegislativeSession
    from src.models.nominal_vote import NominalVote
    from src.models.non_nominal_voter import NonNominalVoter
    from src.models.non_nominal_tally import NonNominalTally
    from src.models.voting_type import VotingType

@unique
class RoundStage(StrEnum):
    SINGLE = "SINGLE"
    GENERAL = "GENERAL"
    SPECIFIC = "SPECIFIC"

@unique
class RoundStatus(StrEnum):
    DRAFT = "DRAFT"
    VOTING_OPEN = "VOTING_OPEN"
    VOTING_CLOSED = "VOTING_CLOSED"
    RESOLVED = "RESOLVED"
    TIED = "TIED"
    ABORTED = "ABORTED"
    VOIDED = "VOIDED"

class VotingRound(UUIDPrimaryKeyMixin, SoftDeleteMixin, Base):
    __tablename__ = "voting_rounds"

    agenda_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agenda_items.id"),
        nullable=False,
    )
    legislative_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("legislative_sessions.id"),
        nullable=False,
    )
    stage: Mapped[RoundStage] = mapped_column(
        Enum(RoundStage, name="round_stage"),
        nullable=False,
    )
    specific_reference: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    voting_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("voting_types.id"),
        nullable=False,
    )
    is_nominal: Mapped[bool] = mapped_column(
        Boolean,
        server_default=true(),
        nullable=False,
    )
    status: Mapped[RoundStatus] = mapped_column(
        Enum(RoundStatus, name="round_status"),
        server_default=text("'DRAFT'"),
        nullable=False,
    )
    result: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    quorum_present_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    certified_quorum_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    time_limit_seconds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    president_votes_ordinarily: Mapped[bool] = mapped_column(
        Boolean,
        server_default=false(),
        nullable=False,
    )
    tie_breaker_vote_value: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    tie_breaker_signature: Mapped[str | None] = mapped_column(
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

    agenda_item: Mapped["AgendaItem"] = relationship(
        "AgendaItem",
        back_populates="voting_rounds",
        lazy="raise_on_sql",
    )
    legislative_session: Mapped["LegislativeSession"] = relationship(
        "LegislativeSession",
        back_populates="voting_rounds",
        lazy="raise_on_sql",
    )
    voting_type: Mapped["VotingType"] = relationship(
        "VotingType",
        back_populates="voting_rounds",
        lazy="raise_on_sql",
    )
    nominal_votes: Mapped[list["NominalVote"]] = relationship(
        "NominalVote",
        back_populates="voting_round",
        lazy="raise_on_sql",
    )
    non_nominal_voters: Mapped[list["NonNominalVoter"]] = relationship(
        "NonNominalVoter",
        back_populates="voting_round",
        lazy="raise_on_sql",
    )
    non_nominal_tallies: Mapped[list["NonNominalTally"]] = relationship(
        "NonNominalTally",
        back_populates="voting_round",
        lazy="raise_on_sql",
    )

    __table_args__ = (
        Index("idx_voting_rounds_session_id", "legislative_session_id"),
    )
