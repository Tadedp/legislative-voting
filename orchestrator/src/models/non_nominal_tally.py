import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base
from src.models.nominal_vote import VoteValue

if TYPE_CHECKING:
    from src.models.voting_round import VotingRound

class NonNominalTally(Base):
    __tablename__ = "non_nominal_tallies"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid7,
        server_default=text("uuidv7()"),
    )
    voting_round_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("voting_rounds.id", ondelete="RESTRICT"),
        nullable=False,
    )
    vote_value: Mapped[VoteValue] = mapped_column(
        Enum(VoteValue, name="vote_value"),
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    voting_round: Mapped["VotingRound"] = relationship(
        "VotingRound",
        back_populates="non_nominal_tallies",
        lazy="raise_on_sql",
    )
