import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.session_attendance import AttendanceStatus, SessionAttendance

async def count_present_by_session(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> int:
    stmt = (
        select(func.count())
        .select_from(SessionAttendance)
        .where(
            SessionAttendance.legislative_session_id == session_id,
            SessionAttendance.status == AttendanceStatus.PRESENT,
        )
    )
    result = await db.execute(stmt)
    return result.scalar() or 0
