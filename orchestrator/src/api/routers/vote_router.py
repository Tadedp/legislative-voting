import uuid
from decimal import Decimal
from time import time_ns

from fastapi import APIRouter, BackgroundTasks, Depends, status, Response

from src.api.dependencies.auth_deps import check_access
from src.api.dependencies.common_deps import DbSessionDep
from src.api.exceptions import (
    BadRequestException,
    ConflictException,
)
from src.core.config import settings
from src.core.websocket import manager
from src.models.system_user import SystemUserRole
from src.models.voting_round import RoundStatus
from src.models.nominal_vote import VoteValue
from src.schemas.vote_schemas import (
    NominalVote,
    NominalVoteResponse,
    NonNominalVote,
    TieBreakerVote,
    VotingRoundTallyResponse,
)
from src.schemas.voting_round_schemas import VotingRoundResponse
from src.services import vote_service, voting_round_service
from src.repositories import vote_repository, legislative_session_repository, legislator_repository

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
            voting_round_id=body.voting_round_id,
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
    status_code=status.HTTP_201_CREATED,
    summary="Cast a non-nominal vote",
    description=(
        "Zero-trust: signed payload with plain-text vote. "
        "The orchestrator stores the vote in decoupled ledgers."
    ),
)
async def cast_non_nominal_vote(
    db_session: DbSessionDep,
    background_tasks: BackgroundTasks,
    body: NonNominalVote,
) -> Response:
    now_ms = time_ns() // 1_000_000
    if abs(now_ms - body.timestamp) > settings.security.ANTI_REPLAY_WINDOW_MS:
        raise BadRequestException("Timestamp outside allowed anti-replay window.")

    try:
        await vote_service.cast_non_nominal_vote(
            db_session,
            voting_round_id=body.voting_round_id,
            legislator_id=body.legislator_id,
            vote_value=body.vote_value,
            timestamp=body.timestamp,
            cryptographic_signature=body.cryptographic_signature,
        )
    except ValueError as exc:
        raise ConflictException(str(exc))

    background_tasks.add_task(
        manager.broadcast,
        "NON_NOMINAL_VOTE_CAST",
        {
            "voting_round_id": str(body.voting_round_id),
            "legislator_id": str(body.legislator_id),
        },
    )

    return Response(status_code=status.HTTP_201_CREATED)

@vote_router.get(
    "/voting-rounds/{voting_round_id}/tally",
    response_model=VotingRoundTallyResponse,
    summary="Get unified tally for a voting round",
    description=(
        "Retrieves the tallied results (nominal or non-nominal). "
        "Only accessible by SECRETARY or PRESIDENCY, and only if "
        "the round is VOTING_CLOSED or RESOLVED."
    ),
    dependencies=[Depends(check_access([SystemUserRole.PRESIDENCY, SystemUserRole.SECRETARY]))],
)
async def get_voting_round_tally(
    db_session: DbSessionDep,
    voting_round_id: uuid.UUID,
) -> VotingRoundTallyResponse:
    try:
        voting_round = await voting_round_service.get_voting_round(db_session, voting_round_id)
    except ValueError as exc:
        raise ConflictException(str(exc))

    if voting_round.status not in [RoundStatus.VOTING_CLOSED, RoundStatus.RESOLVED, RoundStatus.TIED]:
        raise BadRequestException("Tally is only available after voting is closed.")

    if voting_round.is_nominal:
        vote_counts = await vote_repository.count_nominal_votes_by_round(db_session, voting_round_id)
    else:
        vote_counts = await vote_service.get_non_nominal_tallies(db_session, voting_round_id)

    aff = vote_counts.get(VoteValue.AFFIRMATIVE, 0)
    neg = vote_counts.get(VoteValue.NEGATIVE, 0)
    abs_count = vote_counts.get(VoteValue.ABSTENTION, 0)

    # Compute suggested result
    voting_type = await voting_round_service.get_voting_type_for_round(db_session, voting_round_id)
    leg_session = await legislative_session_repository.get_by_id(db_session, voting_round.legislative_session_id)
    total_members = await legislator_repository.count_active_legislators(db_session)
    
    quorum_present = voting_round.certified_quorum_count or voting_round.quorum_present_count or 0
    
    # Mathematical adjustment similar to what resolve/proclaim does
    from src.models.legislative_session import PresidentType
    if leg_session and leg_session.presiding_officer_id is not None:
        if leg_session.pres_type == PresidentType.EX_OFFICIO:
            total_members -= 1
            quorum_present -= 1
        elif leg_session.pres_type == PresidentType.LEGISLATOR and not voting_round.president_votes_ordinarily:
            total_members -= 1
            quorum_present -= 1
            
    quorum_present = max(quorum_present, 0)
    total_members = max(total_members, 0)

    if voting_type:
        suggested_result = voting_round_service.calculate_round_result(
            affirmative=aff,
            negative=neg,
            calc_base=voting_type.calc_base,
            threshold=Decimal(str(voting_type.approval_threshold)),
            quorum_present=quorum_present,
            total_members=total_members,
        )
    else:
        suggested_result = "UNKNOWN"

    return VotingRoundTallyResponse(
        affirmative=aff,
        negative=neg,
        abstentions=abs_count,
        suggested_result=suggested_result,
    )

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
            voting_round_id=body.voting_round_id,
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
            "voting_round_id": str(body.voting_round_id),
            "result": response.result,
            "new_status": response.status.value,
            "legislative_session_id": str(response.legislative_session_id),
        },
    )

    return response