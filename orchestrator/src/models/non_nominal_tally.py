import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Text, text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base
from src.models.nominal_vote import VoteValue

if TYPE_CHECKING:
    from src.models.voting_round import VotingRound

class NonNominalTally(Base):
    __tablename__ = "non_nominal_tallies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    voting_round_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("voting_rounds.id", ondelete="RESTRICT"),
        nullable=False,
    )
    vote_value: Mapped[VoteValue] = mapped_column(
        Enum(VoteValue, name="vote_value"),
        nullable=False,
    )
    ephemeral_public_key: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    server_signature: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    vote_signature: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    voting_round: Mapped["VotingRound"] = relationship(
        "VotingRound",
        back_populates="non_nominal_tallies",
        lazy="raise_on_sql",
    )

    __table_args__ = (
        UniqueConstraint("ephemeral_public_key", name="uq_non_nominal_tallies_ephemeral_pub"),
    )
