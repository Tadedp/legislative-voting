import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, SoftDeleteMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.legislator import Legislator

class Device(Base, UUIDPrimaryKeyMixin, SoftDeleteMixin):
    __tablename__ = "devices"

    legislator_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("legislators.id"),
        unique=True,
        nullable=False,
    )
    hardware_fingerprint: Mapped[str] = mapped_column(
        Text,
        unique=True,
        nullable=False,
    )
    public_key_pem: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    device_token: Mapped[str] = mapped_column(
        Text,
        unique=True,
        nullable=False,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    legislator: Mapped[Legislator] = relationship(
        "Legislator",
        back_populates="device",
        lazy="raise_on_sql",
    )
