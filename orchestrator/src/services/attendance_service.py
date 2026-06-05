import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.session_attendance import AttendanceStatus, SessionAttendance
from src.repositories import legislative_session_repository

async def get_attendance_by_session(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> list[SessionAttendance]:
    session = await legislative_session_repository.get_by_id(db, session_id)
    if session is None:
        raise ValueError("Legislative session not found.")

    stmt = select(SessionAttendance).where(
        SessionAttendance.legislative_session_id == session_id,
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())

async def bulk_update_attendance(
    db: AsyncSession,
    session_id: uuid.UUID,
    updates: list[dict[str, uuid.UUID | AttendanceStatus]],
) -> list[SessionAttendance]:
    session = await legislative_session_repository.get_by_id(db, session_id)
    if session is None:
        raise ValueError("Legislative session not found.")

    # Get existing records
    existing_records = await get_attendance_by_session(db, session_id)
    existing_map = {r.legislator_id: r for r in existing_records}

    upserted_records = []
    for update in updates:
        leg_id = update["legislator_id"]
        status = update["status"]

        if leg_id in existing_map:
            record = existing_map[leg_id] # type: ignore
            record.status = status # type: ignore
            upserted_records.append(record) # type: ignore
        else:
            new_record = SessionAttendance(
                legislative_session_id=session_id,
                legislator_id=leg_id,
                status=status,
            )
            db.add(new_record)
            upserted_records.append(new_record) # type: ignore

    await db.flush()
    return upserted_records # type: ignore
