import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.legislative_session import LegislativeSession, LegSessionStatus
from src.models.voting_round import VotingRound
from src.models.session_attendance import SessionAttendance, AttendanceStatus
from src.repositories import (
    agenda_item_repository,
    legislative_session_repository, 
    legislator_repository,
    voting_round_repository,
) 
from src.services.quorum_service import compute_quorum_minimum, get_certified_quorum
    
async def list_legislative_sessions(db: AsyncSession) -> list[LegislativeSession]:
    return await legislative_session_repository.get_all_active(db)

async def get_legislative_session(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> LegislativeSession:
    session = await legislative_session_repository.get_by_id(db, session_id)

    if session is None or session.deleted_at is not None:
        raise ValueError("Sesión legislativa no encontrada.")

    return session

async def create_legislative_session(
    db: AsyncSession,
    *,
    title: str,
    pres_type: str | None = None,
    presiding_officer_id: uuid.UUID | None = None,
) -> LegislativeSession:
    current_session = await legislative_session_repository.get_current_active(db)
    if current_session is not None:
        raise ValueError(f"Ya existe una sesión ({current_session.status.value}). Debe cerrarla primero.")

    kwargs: dict[str, Any] = {"title": title}
    if pres_type is not None:
        kwargs["pres_type"] = pres_type
    if presiding_officer_id is not None:
        kwargs["presiding_officer_id"] = presiding_officer_id

    session = LegislativeSession(**kwargs)
    session = await legislative_session_repository.create(db, session=session)

    # Initialize the attendance ledger for all active legislators
    active_legislators = await legislator_repository.get_all_active(db)
    attendance_records: list[SessionAttendance] = []
    
    for leg in active_legislators:
        status = AttendanceStatus.ABSENT
        if presiding_officer_id and leg.id == presiding_officer_id:
            status = AttendanceStatus.PRESENT
            
        record = SessionAttendance(
            legislative_session_id=session.id,
            legislator_id=leg.id,
            status=status
        )
        attendance_records.append(record)
        
    if attendance_records:
        db.add_all(attendance_records)
        await db.flush()
        
    return session

async def update_legislative_session(
    db: AsyncSession,
    session_id: uuid.UUID,
    *,
    update_data: dict[str, Any],
) -> LegislativeSession:
    session = await legislative_session_repository.get_by_id(db, session_id)

    if session is None or session.deleted_at is not None:
        raise ValueError("Sesión legislativa no encontrada.")

    if session.status != LegSessionStatus.PENDING:
        raise ValueError(
            "No se puede actualizar la sesión: solo las sesiones en estado "
            "'PENDING' pueden ser modificadas.",
        )

    for field, value in update_data.items():
        setattr(session, field, value)

    await db.flush()
    return session

async def soft_delete_legislative_session(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> LegislativeSession:
    session = await legislative_session_repository.get_by_id(db, session_id)

    if session is None or session.deleted_at is not None:
        raise ValueError("Sesión legislativa no encontrada.")

    if session.status != LegSessionStatus.PENDING:
        raise ValueError(
            "No se puede eliminar la sesión: solo las sesiones en estado "
            "'PENDING' pueden ser eliminadas.",
        )

    session.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    return session

async def set_ephemeral_key(
    db: AsyncSession,
    session_id: uuid.UUID,
    *,
    ephemeral_public_key: str,
) -> LegislativeSession:
    session = await legislative_session_repository.get_by_id(db, session_id)

    if session is None or session.deleted_at is not None:
        raise ValueError("Sesión legislativa no encontrada.")

    session.ephemeral_public_key = ephemeral_public_key
    await db.flush()
    return session

async def update_legislative_session_status(
    db: AsyncSession,
    session_id: uuid.UUID,
    *,
    new_status: LegSessionStatus,
) -> LegislativeSession:
    session = await legislative_session_repository.get_by_id(db, session_id)

    if session is None or session.deleted_at is not None:
        raise ValueError("Sesión legislativa no encontrada.")

    now = datetime.now(timezone.utc)

    # Quorum guard: prevent activation without sufficient legislators.
    if new_status == LegSessionStatus.ACTIVE:
        # A Legislator-President ALWAYS counts towards general session quorum.
        quorum_present, total_members = await get_certified_quorum(
            db, session, president_votes_ordinarily=True
        )
        quorum_minimum = compute_quorum_minimum(total_members)

        if quorum_present < quorum_minimum:
            raise ValueError(
                f"Sin quórum: {quorum_present} legisladores presentes, "
                f"se requieren {quorum_minimum} (de un total de {total_members}).",
            )

        if session.opened_at is None:
            session.opened_at = now

    elif new_status == LegSessionStatus.CLOSED:
        session.closed_at = now

    session.status = new_status
    await db.flush()
    return session

async def get_current_legislative_session(
    db: AsyncSession,
) -> tuple[LegislativeSession, VotingRound | None, Any | None]:
    session = await legislative_session_repository.get_current_active(db)

    if session is None:
        raise ValueError("No hay ninguna sesión legislativa activa.")

    active_round = await voting_round_repository.get_open_round_in_session(
        db, session.id,
    )
    
    active_item = await agenda_item_repository.get_active_on_floor(db)

    return session, active_round, active_item