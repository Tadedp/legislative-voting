from datetime import datetime
from enum import unique, StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, Numeric, Text, func, text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, SoftDeleteMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.voting_round import VotingRound

@unique
class CalculationBase(StrEnum):
    """Defines the mathematical denominator used to evaluate motion passage.

    VOTES_CAST: denominator = affirmative + negative (abstentions excluded).
    MEMBERS_PRESENT: denominator = quorum snapshot at vote start.
    TOTAL_MEMBERS: denominator = total enrolled active legislators.
    """

    VOTES_CAST = "VOTES_CAST"
    MEMBERS_PRESENT = "MEMBERS_PRESENT"
    TOTAL_MEMBERS = "TOTAL_MEMBERS"

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
    calc_base: Mapped[CalculationBase] = mapped_column(
        Enum(CalculationBase, name="calculation_base"),
        server_default=text("'VOTES_CAST'"),
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

    voting_rounds: Mapped[list["VotingRound"]] = relationship(
        "VotingRound",
        back_populates="voting_type",
        lazy="raise_on_sql",
    )