
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, status

from src.api.dependencies.auth_deps import get_current_user, check_access
from src.api.dependencies.common_deps import DbSessionDep
from src.api.exceptions import BadRequestException, ConflictException, NotFoundException
from src.core.websocket import manager
from src.models.system_user import SystemUserRole
from src.schemas.motion_schemas import (
    MotionCreate,
    MotionResponse,
    MotionStatusUpdate,
    MotionUpdate,
)
from src.services import motion_service

motion_router = APIRouter(
    tags=["Motions"],
)

@motion_router.get(
    "/legislative-sessions/{legislative_session_id}/motions",
    response_model=list[MotionResponse],
    summary="List motions in a session",
    description="Returns all active motions belonging to a session.",
    dependencies=[Depends(get_current_user)],
)
async def list_motions(
    db_session: DbSessionDep,
    legislative_session_id: uuid.UUID,
) -> list[MotionResponse]:
    try:
        motions = await motion_service.list_motions_by_session(db_session, legislative_session_id)
    except ValueError as exc:
        raise NotFoundException(str(exc))
    
    return [MotionResponse.model_validate(m) for m in motions]

@motion_router.post(
    "/legislative-sessions/{legislative_session_id}/motions",
    response_model=MotionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a motion",
    description="Status defaults to DRAFT.",
    dependencies=[Depends(check_access([SystemUserRole.PRESIDENCY]))],
)
async def create_motion(
    db_session: DbSessionDep,
    legislative_session_id: uuid.UUID,
    body: MotionCreate,
) -> MotionResponse:
    try:
        motion = await motion_service.create_motion(
            db_session,
            session_id=legislative_session_id,
            title=body.title,
            summary=body.summary,
            voting_type_id=body.voting_type_id,
            is_nominal=body.is_nominal,
        )
    except ValueError as exc:
        raise NotFoundException(str(exc))
    
    return MotionResponse.model_validate(motion)

@motion_router.get(
    "/motions/{motion_id}",
    response_model=MotionResponse,
    summary="Get motion by ID",
    dependencies=[Depends(get_current_user)],
)
async def get_motion(
    db_session: DbSessionDep,
    motion_id: uuid.UUID,
) -> MotionResponse:
    try:
        motion = await motion_service.get_motion(db_session, motion_id)
    except ValueError as exc:
        raise NotFoundException(str(exc))
    
    return MotionResponse.model_validate(motion)

@motion_router.patch(
    "/motions/{motion_id}",
    response_model=MotionResponse,
    summary="Update a motion",
    description="Only allowed if status is DRAFT.",
    dependencies=[Depends(check_access([SystemUserRole.PRESIDENCY]))],
)
async def update_motion(
    db_session: DbSessionDep,
    motion_id: uuid.UUID,
    body: MotionUpdate,
) -> MotionResponse:
    update_data = body.model_dump(exclude_unset=True)

    if not update_data:
        raise BadRequestException("No fields provided for update.")

    try:
        motion = await motion_service.update_motion(
            db_session, motion_id, update_data=update_data,
        )
    except ValueError as exc:
        raise ConflictException(str(exc))
    
    return MotionResponse.model_validate(motion)

@motion_router.delete(
    "/motions/{motion_id}",
    response_model=MotionResponse,
    summary="Soft-delete a motion",
    description="Only allowed if status is DRAFT.",
    dependencies=[Depends(check_access([SystemUserRole.PRESIDENCY]))],
)
async def delete_motion(
    db_session: DbSessionDep,
    motion_id: uuid.UUID,
) -> MotionResponse:
    try:
        motion = await motion_service.soft_delete_motion(db_session, motion_id)
    except ValueError as exc:
        raise ConflictException(str(exc))
    
    return MotionResponse.model_validate(motion)

@motion_router.patch(
    "/motions/{motion_id}/status",
    response_model=MotionResponse,
    summary="Update motion status",
    description="Transition: VOTING_OPEN, VOTING_CLOSED, RESOLVED.",
    dependencies=[Depends(check_access([SystemUserRole.PRESIDENCY]))],
)
async def update_motion_status(
    db_session: DbSessionDep,
    background_tasks: BackgroundTasks,
    motion_id: uuid.UUID,
    body: MotionStatusUpdate,
) -> MotionResponse:
    try:
        motion = await motion_service.update_motion_status(
            db_session, motion_id, new_status=body.status,
        )
    except ValueError as exc:
        raise ConflictException(str(exc))
    
    response = MotionResponse.model_validate(motion)
    
    background_tasks.add_task(
        manager.broadcast,
        "MOTION_STATUS_CHANGED",
        {
            "motion_id": str(motion_id),
            "new_status": body.status.value,
            "legislative_session_id": str(response.legislative_session_id),
        },
    )
    
    return response

@motion_router.post(
    "/motions/{motion_id}/abort",
    response_model=MotionResponse,
    summary="Abort a motion",
    description=(
        "Graceful fail-safe: voids all non-nominal votes and "
        "reverts motion to DRAFT."
    ),
    dependencies=[Depends(check_access([SystemUserRole.PRESIDENCY]))],
)
async def abort_motion(
    db_session: DbSessionDep,
    background_tasks: BackgroundTasks,
    motion_id: uuid.UUID,
) -> MotionResponse:
    try:
        motion = await motion_service.abort_motion(db_session, motion_id)
    except ValueError as exc:
        raise ConflictException(str(exc))
    
    response = MotionResponse.model_validate(motion)
    
    background_tasks.add_task(
        manager.broadcast,
        "MOTION_ABORTED",
        {
            "motion_id": str(motion_id),
            "legislative_session_id": str(response.legislative_session_id),
        },
    )

    return response