import uuid
from datetime import datetime
from enum import unique, StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, func, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.legislative_session import LegislativeSession
    from src.models.legislator import Legislator
    from src.models.system_user import SystemUser

@unique
class AttendanceStatus(StrEnum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    ON_LEAVE = "ON_LEAVE"

class SessionAttendance(Base):
    __tablename__ = "session_attendances"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid7,
        server_default=text("uuidv7()"),
    )
    legislative_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("legislative_sessions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    legislator_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("legislators.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus, name="attendance_status"),
        server_default=text("'PRESENT'"),
        nullable=False,
    )
    registered_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("system_users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    legislative_session: Mapped["LegislativeSession"] = relationship(
        "LegislativeSession",
        back_populates="session_attendances",
        lazy="raise_on_sql",
    )
    legislator: Mapped["Legislator"] = relationship(
        "Legislator",
        back_populates="session_attendances",
        lazy="raise_on_sql",
    )
    registered_by_user: Mapped["SystemUser"] = relationship(
        "SystemUser",
        back_populates="registered_attendances",
        lazy="raise_on_sql",
    )

    __table_args__ = (
        UniqueConstraint(
            "legislative_session_id",
            "legislator_id",
            name="uq_session_attendances_session_legislator",
        ),
    )
