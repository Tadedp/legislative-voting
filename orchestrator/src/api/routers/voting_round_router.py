import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, status

from src.api.dependencies.auth_deps import get_current_user, check_access
from src.api.dependencies.common_deps import DbSessionDep
from src.api.exceptions import BadRequestException, ConflictException, NotFoundException
from src.core.websocket import manager
from src.models.system_user import SystemUserRole
from src.models.voting_round import RoundStatus
from src.schemas.voting_round_schemas import (
    VotingRoundCreate,
    VotingRoundResolveRequest,
    VotingRoundResponse,
    VotingRoundStatusUpdate,
    VotingRoundUpdate,
)
from src.services import voting_round_service

voting_round_router = APIRouter(
    tags=["Voting Rounds"],
)

@voting_round_router.get(
    "/legislative-sessions/{legislative_session_id}/voting-rounds",
    response_model=list[VotingRoundResponse],
    summary="List voting rounds in a session",
    description="Returns all active voting rounds belonging to a session.",
    dependencies=[Depends(get_current_user)],
)
async def list_voting_rounds(
    db_session: DbSessionDep,
    legislative_session_id: uuid.UUID,
) -> list[VotingRoundResponse]:
    try:
        rounds = await voting_round_service.list_rounds_by_session(
            db_session, legislative_session_id,
        )
    except ValueError as exc:
        raise NotFoundException(str(exc))

    return [VotingRoundResponse.model_validate(r) for r in rounds]

@voting_round_router.post(
    "/legislative-sessions/{legislative_session_id}/voting-rounds",
    response_model=VotingRoundResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a voting round",
    description=(
        "Creates a new voting round in DRAFT status. Enforces the "
        "Creation Constraint: SPECIFIC rounds require a prior GENERAL "
        "round that PASSED for the same agenda item."
    ),
    dependencies=[Depends(check_access([SystemUserRole.PRESIDENCY]))],
)
async def create_voting_round(
    db_session: DbSessionDep,
    legislative_session_id: uuid.UUID,
    body: VotingRoundCreate,
) -> VotingRoundResponse:
    try:
        voting_round = await voting_round_service.create_voting_round(
            db_session,
            agenda_item_id=body.agenda_item_id,
            session_id=legislative_session_id,
            stage=body.stage,
            specific_reference=body.specific_reference,
            voting_type_id=body.voting_type_id,
            is_nominal=body.is_nominal,
            president_votes_ordinarily=body.president_votes_ordinarily,
        )
    except ValueError as exc:
        if "Creation constraint" in str(exc):
            raise ConflictException(str(exc))
        raise NotFoundException(str(exc))

    return VotingRoundResponse.model_validate(voting_round)

@voting_round_router.get(
    "/voting-rounds/{voting_round_id}",
    response_model=VotingRoundResponse,
    summary="Get voting round by ID",
    dependencies=[Depends(get_current_user)],
)
async def get_voting_round(
    db_session: DbSessionDep,
    voting_round_id: uuid.UUID,
) -> VotingRoundResponse:
    try:
        voting_round = await voting_round_service.get_voting_round(
            db_session, voting_round_id,
        )
    except ValueError as exc:
        raise NotFoundException(str(exc))

    return VotingRoundResponse.model_validate(voting_round)

@voting_round_router.patch(
    "/voting-rounds/{voting_round_id}",
    response_model=VotingRoundResponse,
    summary="Update a voting round",
    description="Only allowed if status is DRAFT.",
    dependencies=[Depends(check_access([SystemUserRole.PRESIDENCY]))],
)
async def update_voting_round(
    db_session: DbSessionDep,
    voting_round_id: uuid.UUID,
    body: VotingRoundUpdate,
) -> VotingRoundResponse:
    update_data = body.model_dump(exclude_unset=True)

    if not update_data:
        raise BadRequestException("No fields provided for update.")

    try:
        voting_round = await voting_round_service.update_voting_round(
            db_session, voting_round_id, update_data=update_data,
        )
    except ValueError as exc:
        raise ConflictException(str(exc))

    return VotingRoundResponse.model_validate(voting_round)

@voting_round_router.delete(
    "/voting-rounds/{voting_round_id}",
    response_model=VotingRoundResponse,
    summary="Soft-delete a voting round",
    description="Only allowed if status is DRAFT.",
    dependencies=[Depends(check_access([SystemUserRole.PRESIDENCY]))],
)
async def delete_voting_round(
    db_session: DbSessionDep,
    voting_round_id: uuid.UUID,
) -> VotingRoundResponse:
    try:
        voting_round = await voting_round_service.soft_delete_voting_round(
            db_session, voting_round_id,
        )
    except ValueError as exc:
        raise ConflictException(str(exc))

    return VotingRoundResponse.model_validate(voting_round)

@voting_round_router.patch(
    "/voting-rounds/{voting_round_id}/status",
    response_model=VotingRoundResponse,
    summary="Update voting round status",
    description=(
        "Transition: VOTING_OPEN (with quorum guard), VOTING_CLOSED. "
        "Quorum is validated when transitioning to VOTING_OPEN."
    ),
    dependencies=[Depends(check_access([SystemUserRole.PRESIDENCY]))],
)
async def update_voting_round_status(
    db_session: DbSessionDep,
    background_tasks: BackgroundTasks,
    voting_round_id: uuid.UUID,
    body: VotingRoundStatusUpdate,
) -> VotingRoundResponse:
    try:
        voting_round = await voting_round_service.update_voting_round_status(
            db_session,
            voting_round_id,
            new_status=body.status,
            ws_manager=manager,
        )
    except ValueError as exc:
        raise ConflictException(str(exc))

    response = VotingRoundResponse.model_validate(voting_round)

    if body.status == RoundStatus.VOTING_OPEN:
        # Fetch ancillary data for the broadcast payload.
        voting_type = await voting_round_service.get_voting_type_for_round(
            db_session, voting_round_id,
        )
        session = await voting_round_service.get_session_for_round(
            db_session, voting_round_id,
        )
        agenda_item = await voting_round_service.get_agenda_item_for_round(
            db_session, voting_round_id,
        )

        background_tasks.add_task(
            manager.broadcast,
            "VOTING_ROUND_OPENED",
            {
                "voting_round_id": str(voting_round_id),
                "stage": voting_round.stage.value,
                "specific_reference": voting_round.specific_reference,
                "agenda_item": {
                    "id": str(agenda_item.id) if agenda_item else None,
                    "title": agenda_item.title if agenda_item else "",
                    "summary": agenda_item.summary or "" if agenda_item else "",
                    "category": agenda_item.category.value if agenda_item else None,
                    "status": agenda_item.status.value if agenda_item else None,
                },
                "is_nominal": voting_round.is_nominal,
                "allows_abstentions": (
                    voting_type.allows_abstentions if voting_type else True
                ),
                "ephemeral_public_key": (
                    session.ephemeral_public_key if session else None
                ),
                "presiding_officer_id": (
                    str(session.presiding_officer_id)
                    if session and session.presiding_officer_id
                    else None
                ),
                "president_votes_ordinarily": (
                    voting_round.president_votes_ordinarily
                ),
            },
        )
    elif body.status == RoundStatus.VOTING_CLOSED:
        background_tasks.add_task(
            manager.broadcast,
            "VOTING_ROUND_CLOSED",
            {
                "voting_round_id": str(voting_round_id),
                "legislative_session_id": str(
                    response.legislative_session_id,
                ),
            },
        )
    else:
        background_tasks.add_task(
            manager.broadcast,
            "VOTING_ROUND_STATUS_CHANGED",
            {
                "voting_round_id": str(voting_round_id),
                "new_status": body.status.value,
                "legislative_session_id": str(
                    response.legislative_session_id,
                ),
            },
        )

    return response

@voting_round_router.post(
    "/voting-rounds/{voting_round_id}/resolve",
    response_model=VotingRoundResponse,
    summary="Submit final tally and resolve a voting round",
    description=(
        "Runs the calculation engine on the final vote tally to determine "
        "whether the round PASSED, FAILED, or TIED. For nominal rounds, "
        "vote counts are auto-computed from the database. For non-nominal "
        "rounds, the Presidency must provide the decrypted tallies."
    ),
    dependencies=[Depends(check_access([SystemUserRole.PRESIDENCY]))],
)
async def resolve_voting_round(
    db_session: DbSessionDep,
    background_tasks: BackgroundTasks,
    voting_round_id: uuid.UUID,
    body: VotingRoundResolveRequest,
) -> VotingRoundResponse:
    try:
        voting_round = await voting_round_service.resolve_voting_round(
            db_session,
            voting_round_id,
            affirmative=body.affirmative,
            negative=body.negative,
            abstentions=body.abstentions,
            ws_manager=manager,
        )
    except ValueError as exc:
        raise ConflictException(str(exc))

    response = VotingRoundResponse.model_validate(voting_round)

    # If the result is TIED, broadcast a dedicated event for Android
    # tie-breaker UI activation.
    event_type = (
        "VOTING_ROUND_TIED"
        if response.status == RoundStatus.TIED
        else "VOTING_ROUND_RESOLVED"
    )

    session = await voting_round_service.get_session_for_round(
        db_session, voting_round_id,
    )

    background_tasks.add_task(
        manager.broadcast,
        event_type,
        {
            "voting_round_id": str(voting_round_id),
            "result": response.result,
            "new_status": response.status.value,
            "legislative_session_id": str(response.legislative_session_id),
            "presiding_officer_id": (
                str(session.presiding_officer_id)
                if session and session.presiding_officer_id
                else None
            ),
            "president_votes_ordinarily": (
                response.president_votes_ordinarily
            ),
        },
    )

    return response

@voting_round_router.post(
    "/voting-rounds/{voting_round_id}/reopen",
    response_model=VotingRoundResponse,
    summary="Reopen a tied voting round",
    description=(
        "Reverts a TIED voting round to DRAFT for renewed debate and "
        "revote. Voids existing non-nominal votes and clears temporal "
        "markers."
    ),
    dependencies=[Depends(check_access([SystemUserRole.PRESIDENCY]))],
)
async def reopen_voting_round(
    db_session: DbSessionDep,
    background_tasks: BackgroundTasks,
    voting_round_id: uuid.UUID,
) -> VotingRoundResponse:
    try:
        voting_round = await voting_round_service.reopen_voting_round(
            db_session, voting_round_id,
        )
    except ValueError as exc:
        raise ConflictException(str(exc))

    response = VotingRoundResponse.model_validate(voting_round)

    background_tasks.add_task(
        manager.broadcast,
        "VOTING_ROUND_REOPENED",
        {
            "voting_round_id": str(voting_round_id),
            "legislative_session_id": str(response.legislative_session_id),
        },
    )

    return response

@voting_round_router.post(
    "/voting-rounds/{voting_round_id}/abort",
    response_model=VotingRoundResponse,
    summary="Abort a voting round",
    description=(
        "Graceful fail-safe: voids all non-nominal votes and "
        "reverts the voting round to DRAFT."
    ),
    dependencies=[Depends(check_access([SystemUserRole.PRESIDENCY]))],
)
async def abort_voting_round(
    db_session: DbSessionDep,
    background_tasks: BackgroundTasks,
    voting_round_id: uuid.UUID,
) -> VotingRoundResponse:
    try:
        voting_round = await voting_round_service.abort_voting_round(
            db_session, voting_round_id,
        )
    except ValueError as exc:
        raise ConflictException(str(exc))

    response = VotingRoundResponse.model_validate(voting_round)

    background_tasks.add_task(
        manager.broadcast,
        "VOTING_ROUND_ABORTED",
        {
            "voting_round_id": str(voting_round_id),
            "legislative_session_id": str(response.legislative_session_id),
        },
    )

    return response
