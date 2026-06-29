import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status

from src.api.dependencies.auth_deps import get_current_user, check_access, get_device_by_token
from src.api.dependencies.common_deps import DbSessionDep
from src.api.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
    UnauthorizedException,
    InternalServerException,
)
from src.core.websocket import manager
from src.models.system_user import SystemUserRole
from src.schemas.legislative_session_schemas import (
    CurrentLegislativeSessionResponse,
    EphemeralKeyRequest,
    LegislativeSessionCreate,
    LegislativeSessionResponse,
    LegislativeSessionStatusUpdate,
    LegislativeSessionUpdate,
)
from src.schemas.voting_round_schemas import VotingRoundWithItemResponse
from src.schemas.agenda_item_schemas import AgendaItemResponse
from src.services import legislative_session_service
from src.repositories import agenda_item_repository

legislative_session_router = APIRouter(
    prefix="/legislative-sessions",
    tags=["Legislative Sessions"],
)

@legislative_session_router.get(
    "",
    response_model=list[LegislativeSessionResponse],
    summary="List all legislative sessions",
    description="Returns all active legislative sessions.",
    dependencies=[Depends(get_current_user)],
)
async def list_legislative_sessions(
    db_session: DbSessionDep,
) -> list[LegislativeSessionResponse]:
    sessions = await legislative_session_service.list_legislative_sessions(db_session)
    return [LegislativeSessionResponse.model_validate(s) for s in sessions]

@legislative_session_router.get(
    "/current",
    response_model=CurrentLegislativeSessionResponse,
    summary="Get current active session",
    description=(
        "Stateless client sync. Returns the ACTIVE session, ephemeral key, "
        "and any VOTING_OPEN motion. Accepts X-Device-Token OR session cookie."
    ),
)
async def get_current_legislative_session(
    db_session: DbSessionDep,
    request: Request,
) -> CurrentLegislativeSessionResponse:
    # Attempt device-token auth first, then fall back to session cookie.
    device_token = request.headers.get("x-device-token")
    session_cookie = request.cookies.get("session_id")

    if device_token is None and session_cookie is None:
        raise UnauthorizedException(
            "Authentication required. Provide X-Device-Token header "
            "or session cookie."
        )

    if device_token is not None:
        device = await get_device_by_token( # type: ignore
            x_device_token=device_token, db_session=db_session,
        )
    else:
        user = await get_current_user(request=request, db_session=db_session, cookie_token=session_cookie) # type: ignore

    try:
        session, active_round, active_item = (
            await legislative_session_service.get_current_legislative_session(db_session)
        )
    except ValueError as exc:
        raise NotFoundException(str(exc))

    # Build the nested DTO if a voting round is currently open.
    active_voting_round_dto = None
    if active_round is not None:
        agenda_item = await agenda_item_repository.get_by_id(
            db_session, active_round.agenda_item_id,
        )
        active_voting_round_dto = VotingRoundWithItemResponse.model_validate(
            {
                **VotingRoundWithItemResponse.model_validate(
                    active_round,
                ).model_dump(exclude={"agenda_item"}),
                "agenda_item": AgendaItemResponse.model_validate(agenda_item),
            }
        )

    return CurrentLegislativeSessionResponse(
        session=LegislativeSessionResponse.model_validate(session),
        active_voting_round=active_voting_round_dto,
        active_agenda_item=AgendaItemResponse.model_validate(active_item) if active_item else None,
    )

@legislative_session_router.get(
    "/{legislative_session_id}",
    response_model=LegislativeSessionResponse,
    summary="Get legislative session by ID",
    dependencies=[Depends(get_current_user)],
)
async def get_legislative_session(
    db_session: DbSessionDep,
    legislative_session_id: uuid.UUID,
) -> LegislativeSessionResponse:
    try:
        legislative_session = await legislative_session_service.get_legislative_session(
            db_session,
            legislative_session_id,
        )
    except ValueError as exc:
        raise NotFoundException(str(exc))

    return LegislativeSessionResponse.model_validate(legislative_session)

@legislative_session_router.post(
    "",
    response_model=LegislativeSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new legislative session",
    description="Status defaults to PENDING. Accepts presidential configuration.",
    dependencies=[Depends(check_access([SystemUserRole.PRESIDENCY]))],
)
async def create_legislative_session(
    db_session: DbSessionDep,
    body: LegislativeSessionCreate,
) -> LegislativeSessionResponse:
    legislative_session = await legislative_session_service.create_legislative_session(
        db_session,
        title=body.title,
        pres_type=body.pres_type,
        presiding_officer_id=body.presiding_officer_id,
    )
    return LegislativeSessionResponse.model_validate(legislative_session)

@legislative_session_router.patch(
    "/{legislative_session_id}",
    response_model=LegislativeSessionResponse,
    summary="Update a legislative session",
    description="Only allowed if status is PENDING.",
    dependencies=[Depends(check_access([SystemUserRole.PRESIDENCY]))],
)
async def update_legislative_session(
    db_session: DbSessionDep,
    legislative_session_id: uuid.UUID,
    body: LegislativeSessionUpdate,
) -> LegislativeSessionResponse:
    update_data = body.model_dump(exclude_unset=True)

    if not update_data:
        raise BadRequestException("No fields provided for update.")

    try:
        legislative_session = await legislative_session_service.update_legislative_session(
            db_session, legislative_session_id, update_data=update_data,
        )
    except ValueError as exc:
        raise ConflictException(str(exc))

    return LegislativeSessionResponse.model_validate(legislative_session)

@legislative_session_router.delete(
    "/{legislative_session_id}",
    response_model=LegislativeSessionResponse,
    summary="Soft-delete a legislative session",
    description="Only allowed if status is PENDING.",
    dependencies=[Depends(check_access([SystemUserRole.PRESIDENCY]))],
)
async def delete_legislative_session(
    db_session: DbSessionDep,
    legislative_session_id: uuid.UUID,
) -> LegislativeSessionResponse:
    try:
        legislative_session = await legislative_session_service.soft_delete_legislative_session(
            db_session, legislative_session_id,
        )
    except ValueError as exc:
        raise ConflictException(str(exc))

    return LegislativeSessionResponse.model_validate(legislative_session)

@legislative_session_router.post(
    "/{legislative_session_id}/ephemeral-key",
    response_model=LegislativeSessionResponse,
    summary="Set ephemeral encryption key",
    description="Delivers the key used for client-side non-nominal vote encryption.",
    dependencies=[Depends(check_access([SystemUserRole.PRESIDENCY]))],
)
async def set_ephemeral_key(
    db_session: DbSessionDep,
    legislative_session_id: uuid.UUID,
    body: EphemeralKeyRequest,
) -> LegislativeSessionResponse:
    try:
        legislative_session = await legislative_session_service.set_ephemeral_key(
            db_session, legislative_session_id, ephemeral_public_key=body.ephemeral_public_key,
        )
    except ValueError as exc:
        raise NotFoundException(str(exc))

    return LegislativeSessionResponse.model_validate(legislative_session)

@legislative_session_router.patch(
    "/{legislative_session_id}/status",
    response_model=LegislativeSessionResponse,
    summary="Update legislative session status",
    description=(
        "Transition: ACTIVE, PAUSED, CLOSED. "
        "Quorum is validated when transitioning to ACTIVE."
    ),
    dependencies=[Depends(check_access([SystemUserRole.PRESIDENCY]))],
)
async def update_legislative_session_status(
    db_session: DbSessionDep,
    background_tasks: BackgroundTasks,
    legislative_session_id: uuid.UUID,
    body: LegislativeSessionStatusUpdate,
) -> LegislativeSessionResponse:
    try:
        legislative_session = await legislative_session_service.update_legislative_session_status(
            db_session,
            legislative_session_id,
            new_status=body.status,
        )
        await db_session.commit()
    except ValueError as exc:
        await db_session.rollback()
        raise ConflictException(str(exc))
    except Exception as exc:
        await db_session.rollback()
        raise InternalServerException(str(exc))

    response = LegislativeSessionResponse.model_validate(legislative_session)

    background_tasks.add_task(
        manager.broadcast,
        "SESSION_STATUS_CHANGED",
        response.model_dump(mode="json"),
    )

    return response