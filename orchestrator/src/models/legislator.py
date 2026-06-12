from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, func, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, SoftDeleteMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.device import Device
    from src.models.nominal_vote import NominalVote
    from src.models.non_nominal_voter import NonNominalVoter
    from src.models.session_attendance import SessionAttendance

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
    provisioning_token: Mapped[str | None] = mapped_column(
        Text,
        unique=True,
        nullable=True,
        index=True,
    )
    provisioning_token_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    provisioning_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
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
    non_nominal_voters: Mapped[list["NonNominalVoter"]] = relationship(
        "NonNominalVoter",
        back_populates="legislator",
        lazy="raise_on_sql",
    )
    session_attendances: Mapped[list["SessionAttendance"]] = relationship(
        "SessionAttendance",
        back_populates="legislator",
        lazy="raise_on_sql",
    )
