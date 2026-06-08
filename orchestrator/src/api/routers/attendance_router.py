import uuid

from fastapi import APIRouter, Depends

from src.api.dependencies.auth_deps import check_access, get_current_user
from src.api.dependencies.common_deps import DbSessionDep
from src.api.exceptions import NotFoundException
from src.models.system_user import SystemUserRole
from src.schemas.attendance_schemas import AttendanceBulkUpdate, SessionAttendanceResponse, SessionAttendanceEnriched
from src.services import attendance_service

attendance_router = APIRouter(
    prefix="/legislative-sessions/{legislative_session_id}/attendance",
    tags=["Attendance"],
)

@attendance_router.get(
    "",
    response_model=list[SessionAttendanceEnriched],
    summary="Get session attendance",
    description="Returns the attendance ledger for a legislative session.",
    dependencies=[Depends(get_current_user)],
)
async def get_attendance(
    db_session: DbSessionDep,
    legislative_session_id: uuid.UUID,
) -> list[SessionAttendanceEnriched]:
    try:
        records = await attendance_service.get_enriched_attendance_by_session(
            db_session, legislative_session_id,
        )
    except ValueError as exc:
        raise NotFoundException(str(exc))

    return [SessionAttendanceEnriched.model_validate(r) for r in records]

@attendance_router.post(
    "/bulk",
    response_model=list[SessionAttendanceResponse],
    summary="Bulk update session attendance",
    description="Used by the SECRETARY to mark legislators as PRESENT or ABSENT.",
    dependencies=[Depends(check_access([SystemUserRole.SECRETARY]))],
)
async def bulk_update_attendance(
    db_session: DbSessionDep,
    legislative_session_id: uuid.UUID,
    body: AttendanceBulkUpdate,
) -> list[SessionAttendanceResponse]:
    try:
        updates = [ # type: ignore
            {"legislator_id": item.legislator_id, "status": item.status}
            for item in body.records
        ]
        records = await attendance_service.bulk_update_attendance(
            db_session,
            legislative_session_id,
            updates=updates, # type: ignore
        )
    except ValueError as exc:
        raise NotFoundException(str(exc))

    return [SessionAttendanceResponse.model_validate(r) for r in records]
