from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, func, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, SoftDeleteMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.device import Device
    from src.models.nominal_vote import NominalVote
    from src.models.non_nominal_vote import NonNominalVote

class Legislator(Base, UUIDPrimaryKeyMixin, SoftDeleteMixin):
    __tablename__ = "legislators"

    national_id: Mapped[str] = mapped_column(
        Text,
        unique=True,
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    current_public_key: Mapped[str | None] = mapped_column(
        Text,
        unique=True,
        nullable=True,
    )
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )

    device: Mapped[Device | None] = relationship(
        "Device",
        back_populates="legislator",
        uselist=False,
        lazy="raise_on_sql",
    )
    nominal_votes: Mapped[list[NominalVote]] = relationship(
        "NominalVote",
        back_populates="legislator",
        lazy="raise_on_sql",
    )
    non_nominal_votes: Mapped[list[NonNominalVote]] = relationship(
        "NonNominalVote",
        back_populates="legislator",
        lazy="raise_on_sql",
    )
