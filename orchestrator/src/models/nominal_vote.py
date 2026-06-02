import uuid
from datetime import datetime
from enum import unique, StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, func, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.legislator import Legislator
    from src.models.voting_round import VotingRound

@unique
class NominalVoteValue(StrEnum):
    AFFIRMATIVE = "AFFIRMATIVE"
    NEGATIVE = "NEGATIVE"
    ABSTENTION = "ABSTENTION"

class NominalVote(Base):
    __tablename__ = "nominal_votes"

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True,
        default=uuid.uuid7,
        server_default=text("uuidv7()"),
    )
    voting_round_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("voting_rounds.id"),
        nullable=False,
    )
    legislator_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("legislators.id"),
        nullable=False,
    )
    vote_value: Mapped[NominalVoteValue] = mapped_column(
        Enum(NominalVoteValue, name="nominal_vote_value"),
        nullable=False,
    )
    cryptographic_signature: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    voting_round: Mapped[VotingRound] = relationship(
        "VotingRound",
        back_populates="nominal_votes",
        lazy="raise_on_sql",
    )
    legislator: Mapped[Legislator] = relationship(
        "Legislator",
        back_populates="nominal_votes",
        lazy="raise_on_sql",
    )
    
    __table_args__ = (
        UniqueConstraint(
            "voting_round_id",
            "legislator_id",
            name="uq_nominal_votes_voting_round_legislator",
        ),
    )