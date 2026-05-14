import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, status

from sqlalchemy.exc import IntegrityError

from src.api.dependencies.auth_deps import check_access
from src.api.dependencies.common_deps import DbSessionDep
from src.api.exceptions import BadRequestException, ConflictException, UnauthorizedException
from src.core.config import settings
from src.core.websocket import manager
from src.models.system_user import SystemUserRole
from src.services import vote_service
from src.schemas.vote_schemas import (
    NominalVote,
    NominalVoteResponse,
    NonNominalVote,
    NonNominalVoteResponse,
)

vote_router = APIRouter(
    tags=["Votes"],
)

@vote_router.post(
    "/votes/nominal",
    response_model=NominalVoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cast a nominal vote",
    description=(
        "Authenticated via cryptographic signature. Does NOT use session "
        "cookies. Triggers WS broadcast with legislator details + vote value."
    ),
)
async def cast_nominal_vote(
    db_session: DbSessionDep,
    body: NominalVote,
    background_tasks: BackgroundTasks,
) -> NominalVoteResponse:
    current_utc_millis = int(datetime.now(timezone.utc).timestamp() * 1000)
    if abs(current_utc_millis - body.timestamp) >= settings.security.ANTI_REPLAY_WINDOW_MS:
        raise BadRequestException("Payload expired.")

    try:
        vote = await vote_service.cast_nominal_vote(
            db_session,
            motion_id=body.motion_id,
            legislator_id=body.legislator_id,
            vote_value=body.vote_value,
            timestamp=body.timestamp,
            cryptographic_signature=body.cryptographic_signature,
        )
    except ValueError as exc:
        raise UnauthorizedException(str(exc))
    except IntegrityError:
        raise ConflictException("This legislator has already voted on this motion.")

    background_tasks.add_task(
        manager.broadcast,
        "NOMINAL_VOTE_RECEIVED",
        {
            "motion_id": str(body.motion_id),
            "legislator_id": str(body.legislator_id),
            "vote_value": body.vote_value.value,
        },
    )

    return NominalVoteResponse.model_validate(vote)

@vote_router.post(
    "/votes/non-nominal",
    response_model=NonNominalVoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cast a non-nominal vote",
    description=(
        "Authenticated via cryptographic signature. Does NOT use session "
        "cookies. Backend stores ciphertext only (zero-trust). "
        "Triggers WS broadcast with legislator details ONLY (hides vote)."
    ),
)
async def cast_non_nominal_vote(
    db_session: DbSessionDep,
    body: NonNominalVote,
    background_tasks: BackgroundTasks,
) -> NonNominalVoteResponse:
    current_utc_millis = int(datetime.now(timezone.utc).timestamp() * 1000)
    if abs(current_utc_millis - body.timestamp) >= settings.security.ANTI_REPLAY_WINDOW_MS:
        raise BadRequestException("Payload expired.")

    try:
        vote = await vote_service.cast_non_nominal_vote(
            db_session,
            motion_id=body.motion_id,
            legislator_id=body.legislator_id,
            encrypted_payload=body.encrypted_payload,
            timestamp=body.timestamp,
            cryptographic_signature=body.cryptographic_signature,
        )
    except ValueError as exc:
        raise UnauthorizedException(str(exc))
    except IntegrityError:
        raise ConflictException("This legislator has already voted on this motion.")

    background_tasks.add_task(
        manager.broadcast,
        "NON_NOMINAL_VOTE_RECEIVED",
        {
            "motion_id": str(body.motion_id),
            "legislator_id": str(body.legislator_id),
        },
    )

    return NonNominalVoteResponse.model_validate(vote)

@vote_router.get(
    "/motions/{motion_id}/votes/non-nominal",
    response_model=list[NonNominalVoteResponse],
    summary="Get non-nominal vote ciphertexts",
    description=(
        "Returns all ciphertexts for a motion so the Presidency frontend "
        "can decrypt them locally."
    ),
    dependencies=[Depends(check_access([SystemUserRole.PRESIDENCY]))],
)
async def get_non_nominal_votes(
    db_session: DbSessionDep,
    motion_id: uuid.UUID,
) -> list[NonNominalVoteResponse]:
    votes = await vote_service.get_non_nominal_votes(db_session, motion_id)
    return [NonNominalVoteResponse.model_validate(v) for v in votes]