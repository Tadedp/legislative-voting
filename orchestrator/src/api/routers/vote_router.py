import uuid
from time import time_ns

from fastapi import APIRouter, BackgroundTasks, Depends, status

from src.api.dependencies.auth_deps import check_access
from src.api.dependencies.common_deps import DbSessionDep
from src.api.exceptions import (
    BadRequestException,
    ConflictException,
)
from src.core.config import settings
from src.core.websocket import manager
from src.models.system_user import SystemUserRole
from src.schemas.vote_schemas import (
    NominalVote,
    NominalVoteResponse,
    NonNominalVote,
    NonNominalVoteResponse,
    TieBreakerVote,
)
from src.schemas.voting_round_schemas import VotingRoundResponse
from src.services import vote_service

vote_router = APIRouter(
    tags=["Votes"],
)

@vote_router.post(
    "/votes/nominal",
    response_model=NominalVoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cast a nominal vote",
    description=(
        "Zero-trust: no session cookie required. The vote payload is "
        "cryptographically signed by the voter's secp256r1 private key."
    ),
)
async def cast_nominal_vote(
    db_session: DbSessionDep,
    background_tasks: BackgroundTasks,
    body: NominalVote,
) -> NominalVoteResponse:
    # Anti-replay window check.
    now_ms = time_ns() // 1_000_000
    if abs(now_ms - body.timestamp) > settings.security.ANTI_REPLAY_WINDOW_MS:
        raise BadRequestException("Timestamp outside allowed anti-replay window.")

    try:
        vote = await vote_service.cast_nominal_vote(
            db_session,
            voting_round_id=body.motion_id,
            legislator_id=body.legislator_id,
            vote_value=body.vote_value,
            timestamp=body.timestamp,
            cryptographic_signature=body.cryptographic_signature,
        )
    except ValueError as exc:
        raise ConflictException(str(exc))

    response = NominalVoteResponse.model_validate(vote)

    background_tasks.add_task(
        manager.broadcast,
        "NOMINAL_VOTE_CAST",
        {
            "event_id": str(vote.event_id),
            "voting_round_id": str(vote.voting_round_id),
            "legislator_id": str(vote.legislator_id),
            "vote_value": vote.vote_value.value,
        },
    )

    return response

@vote_router.post(
    "/votes/non-nominal",
    response_model=NonNominalVoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cast a non-nominal vote",
    description=(
        "Zero-trust: signed payload with encrypted vote. "
        "The orchestrator stores the ciphertext only."
    ),
)
async def cast_non_nominal_vote(
    db_session: DbSessionDep,
    background_tasks: BackgroundTasks,
    body: NonNominalVote,
) -> NonNominalVoteResponse:
    now_ms = time_ns() // 1_000_000
    if abs(now_ms - body.timestamp) > settings.security.ANTI_REPLAY_WINDOW_MS:
        raise BadRequestException("Timestamp outside allowed anti-replay window.")

    try:
        vote = await vote_service.cast_non_nominal_vote(
            db_session,
            voting_round_id=body.motion_id,
            legislator_id=body.legislator_id,
            encrypted_payload=body.encrypted_payload,
            timestamp=body.timestamp,
            cryptographic_signature=body.cryptographic_signature,
        )
    except ValueError as exc:
        raise ConflictException(str(exc))

    response = NonNominalVoteResponse.model_validate(vote)

    background_tasks.add_task(
        manager.broadcast,
        "NON_NOMINAL_VOTE_CAST",
        {
            "event_id": str(vote.event_id),
            "voting_round_id": str(vote.voting_round_id),
            "legislator_id": str(vote.legislator_id),
        },
    )

    return response

@vote_router.get(
    "/voting-rounds/{voting_round_id}/votes/non-nominal",
    response_model=list[NonNominalVoteResponse],
    summary="Get non-nominal votes for a voting round",
    description=(
        "Retrieves all non-nominal vote ciphertexts for Presidency "
        "decryption."
    ),
    dependencies=[Depends(check_access([SystemUserRole.PRESIDENCY]))],
)
async def get_non_nominal_votes(
    db_session: DbSessionDep,
    voting_round_id: uuid.UUID,
) -> list[NonNominalVoteResponse]:
    votes = await vote_service.get_non_nominal_votes(db_session, voting_round_id)
    return [NonNominalVoteResponse.model_validate(v) for v in votes]

@vote_router.post(
    "/votes/tie-breaker",
    response_model=VotingRoundResponse,
    status_code=status.HTTP_200_OK,
    summary="Cast a presidential tie-breaking vote",
    description=(
        "Zero-trust: cryptographically signed by the presiding officer. "
        "Only permitted when a voting round is in TIED status. Only "
        "AFFIRMATIVE or NEGATIVE values are accepted. The deciding vote "
        "is stored on the voting round itself (not in nominal_votes)."
    ),
)
async def cast_tie_breaker_vote(
    db_session: DbSessionDep,
    background_tasks: BackgroundTasks,
    body: TieBreakerVote,
) -> VotingRoundResponse:
    # Anti-replay window check.
    now_ms = time_ns() // 1_000_000
    if abs(now_ms - body.timestamp) > settings.security.ANTI_REPLAY_WINDOW_MS:
        raise BadRequestException("Timestamp outside allowed anti-replay window.")

    try:
        voting_round = await vote_service.cast_tie_breaker_vote(
            db_session,
            voting_round_id=body.motion_id,
            legislator_id=body.legislator_id,
            vote_value=body.vote_value,
            timestamp=body.timestamp,
            cryptographic_signature=body.cryptographic_signature,
        )
    except ValueError as exc:
        raise ConflictException(str(exc))

    response = VotingRoundResponse.model_validate(voting_round)

    background_tasks.add_task(
        manager.broadcast,
        "TIE_BREAKER_VOTE_CAST",
        {
            "voting_round_id": str(body.motion_id),
            "result": response.result,
            "new_status": response.status.value,
            "legislative_session_id": str(response.legislative_session_id),
        },
    )

    return response