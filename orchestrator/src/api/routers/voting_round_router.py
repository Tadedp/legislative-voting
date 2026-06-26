import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, status
from web3.exceptions import TimeExhausted

from src.api.dependencies.auth_deps import get_current_user, check_access
from src.api.dependencies.common_deps import DbSessionDep
from src.api.exceptions import BadRequestException, ConflictException, InternalServerException, ServiceUnavailableException, NotFoundException
from src.core.websocket import manager
from src.models.system_user import SystemUserRole
from src.models.voting_round import RoundStatus
from src.schemas.voting_round_schemas import (
    VotingRoundCreate,
    VotingRoundProclaimRequest,
    VotingRoundResponse,
    VotingRoundUpdate,
)
from src.services import audit_ledger_service, voting_round_service
from src.core.database import async_session_maker

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
            time_limit_seconds=body.time_limit_seconds,
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

@voting_round_router.post(
    "/voting-rounds/{voting_round_id}/open",
    response_model=VotingRoundResponse,
    summary="Open voting round",
    description="Transition to VOTING_OPEN. Quorum is validated.",
    dependencies=[Depends(check_access([SystemUserRole.PRESIDENCY]))],
)
async def open_voting_round(
    db_session: DbSessionDep,
    background_tasks: BackgroundTasks,
    voting_round_id: uuid.UUID,
) -> VotingRoundResponse:
    try:
        voting_round = await voting_round_service.open_voting_round(
            db_session, voting_round_id,
        )
    except ValueError as exc:
        raise ConflictException(str(exc))

    response = VotingRoundResponse.model_validate(voting_round)

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
            "time_limit_seconds": voting_round.time_limit_seconds,
        },
    )

    return response

@voting_round_router.post(
    "/voting-rounds/{voting_round_id}/close",
    response_model=VotingRoundResponse,
    summary="Close voting round",
    description="Transition to VOTING_CLOSED.",
    dependencies=[Depends(check_access([SystemUserRole.PRESIDENCY]))],
)
async def close_voting_round(
    db_session: DbSessionDep,
    background_tasks: BackgroundTasks,
    voting_round_id: uuid.UUID,
) -> VotingRoundResponse:
    try:
        voting_round = await voting_round_service.close_voting_round(
            db_session, voting_round_id,
        )
    except ValueError as exc:
        raise ConflictException(str(exc))

    response = VotingRoundResponse.model_validate(voting_round)

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

    return response

@voting_round_router.post(
    "/voting-rounds/{voting_round_id}/proclaim",
    response_model=VotingRoundResponse,
    summary="Proclaim the voting round result and anchor to blockchain",
    description=(
        "Computes the result, generates Merkle Roots, anchors to "
        "Polygon Amoy, and statically saves the snapshot to the DB."
    ),
    dependencies=[Depends(check_access([SystemUserRole.PRESIDENCY]))],
)
async def proclaim_voting_round(
    db_session: DbSessionDep,
    background_tasks: BackgroundTasks,
    voting_round_id: uuid.UUID,
    body: VotingRoundProclaimRequest,
) -> VotingRoundResponse:
    try:
        voting_round = await voting_round_service.proclaim_voting_round(
            db_session,
            voting_round_id,
            affirmative=body.affirmative,
            negative=body.negative,
            abstentions=body.abstentions,
        )
        
        # Schedule the blockchain anchoring in the background to prevent 504 Timeouts
        async def background_anchor(round_id: uuid.UUID, nominal: bool):
            async with async_session_maker() as db:
                await audit_ledger_service.anchor_and_snapshot_round(
                    db, 
                    round_id, 
                    nominal
                )
                await db.commit()
                
        background_tasks.add_task(background_anchor, voting_round_id, voting_round.is_nominal)
        
        await db_session.commit()
    
    except ValueError as exc:
        await db_session.rollback()
        raise ConflictException(str(exc))
    except Exception as exc:
        await db_session.rollback()
        raise InternalServerException(str(exc))

    response = VotingRoundResponse.model_validate(voting_round)

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
    "/voting-rounds/{voting_round_id}/rectify",
    response_model=VotingRoundResponse,
    summary="Rectify (abort and clone) a voting round",
    description="Marks current round ABORTED and returns the new cloned DRAFT round.",
    dependencies=[Depends(check_access([SystemUserRole.PRESIDENCY]))],
)
async def rectify_voting_round(
    db_session: DbSessionDep,
    background_tasks: BackgroundTasks,
    voting_round_id: uuid.UUID,
) -> VotingRoundResponse:
    try:
        new_round = await voting_round_service.rectify_voting_round(
            db_session, voting_round_id,
        )
    except ValueError as exc:
        raise ConflictException(str(exc))

    response = VotingRoundResponse.model_validate(new_round)

    # Let UI know the old round was aborted.
    background_tasks.add_task(
        manager.broadcast,
        "VOTING_ROUND_ABORTED",
        {
            "voting_round_id": str(voting_round_id),
            "new_draft_id": str(new_round.id),
            "legislative_session_id": str(response.legislative_session_id),
        },
    )

    return response
