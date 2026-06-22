import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import String, Boolean, BigInteger, DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base

class AuditLedger(Base):
    __tablename__ = "audit_ledgers"

    voting_round_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("voting_rounds.id"),
        primary_key=True,
    )
    is_nominal: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    nominal_merkle_root: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    tally_merkle_root: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    eligibility_merkle_root: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    transaction_hash: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    block_number: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    tally_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )
