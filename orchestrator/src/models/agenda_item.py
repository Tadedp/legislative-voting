from datetime import datetime
from enum import unique, StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, func, Text, text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, SoftDeleteMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.voting_round import VotingRound

@unique
class ItemCategory(StrEnum):
    PROJECT = "PROJECT"
    MOTION = "MOTION"

@unique
class ParliamentaryStage(StrEnum):
    INITIAL = "INITIAL"
    REVISION = "REVISION"

@unique
class ItemStatus(StrEnum):
    DRAFT = "DRAFT"
    DEBATE = "DEBATE"
    APPROVED_IN_GENERAL = "APPROVED_IN_GENERAL"
    APPROVED = "APPROVED"
    SANCTIONED = "SANCTIONED"
    REJECTED = "REJECTED"
    POSTPONED = "POSTPONED"

class AgendaItem(UUIDPrimaryKeyMixin, SoftDeleteMixin, Base):
    __tablename__ = "agenda_items"

    category: Mapped[ItemCategory] = mapped_column(
        Enum(ItemCategory, name="item_category"),
        nullable=False,
    )
    file_number: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    parliamentary_stage: Mapped[ParliamentaryStage] = mapped_column(
        Enum(ParliamentaryStage, name="parliamentary_stage"),
        server_default=text("'INITIAL'"),
        nullable=False,
    )
    status: Mapped[ItemStatus] = mapped_column(
        Enum(ItemStatus, name="item_status"),
        server_default=text("'DRAFT'"),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        server_default=true(),
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
        back_populates="agenda_item",
        lazy="raise_on_sql",
    )
