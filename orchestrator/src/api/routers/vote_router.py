import uuid
from decimal import Decimal

from fastapi import APIRouter, BackgroundTasks, Depends, status

from src.api.dependencies.auth_deps import check_access
from src.api.dependencies.common_deps import DbSessionDep
from src.api.exceptions import (
    BadRequestException,
    ConflictException,
    InternalServerException,
)
from src.core.websocket import manager
from src.models.system_user import SystemUserRole
from src.models.voting_round import RoundStatus
from src.models.nominal_vote import VoteValue
from src.models.voting_type import CalculationBase
from src.schemas.vote_schemas import (
    NominalVote,
    NominalVoteResponse,
    TieBreakerVote,
    VotingRoundTallyResponse,
    VoteAuthorizeRequest,
    VoteAuthorizeResponse,
    VoteCastRequest,
    VoteCastResponse,
)
from src.schemas.voting_round_schemas import VotingRoundResponse
from src.services import vote_service, voting_round_service
from src.services.quorum_service import calculate_effective_denominator
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
    try:
        vote = await vote_service.cast_nominal_vote(
            db_session,
            raw_payload_string=body.raw_payload_string,
            cryptographic_signature=body.cryptographic_signature,
        )
        current_votes = await vote_repository.count_votes_received(db_session, vote.voting_round_id)
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
            "current_votes": current_votes,
        },
    )

    return response

@vote_router.post(
    "/votes/authorize",
    response_model=VoteAuthorizeResponse,
    status_code=status.HTTP_200_OK,
    summary="Authorize a non-nominal vote (Phase 1)",
    description=(
        "Zero-trust: Idempotent JIT Authorization. Verifies the Keystore ECDSA signature "
        "and blind signs the token for Phase 2 without revealing intent."
    ),
)
async def authorize_vote(
    db_session: DbSessionDep,
    background_tasks: BackgroundTasks,
    body: VoteAuthorizeRequest,
) -> VoteAuthorizeResponse:
    try:
        signed_token, voting_round_id = await vote_service.authorize_vote(
            db_session,
            raw_payload_string=body.raw_payload_string,
            ecdsa_signature=body.ecdsa_signature,
        )
        current_tokens = await vote_repository.count_tokens_issued(db_session, voting_round_id)
    except ValueError as exc:
        raise ConflictException(str(exc))

    background_tasks.add_task(
        manager.broadcast,
        "NON_NOMINAL_VOTE_AUTHORIZED",
        {
            "voting_round_id": str(voting_round_id),
            "current_tokens": current_tokens,
        },
    )

    return VoteAuthorizeResponse(signed_blinded_token=signed_token)


@vote_router.post(
    "/votes/cast",
    response_model=VoteCastResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cast an anonymous vote (Phase 2)",
    description=(
        "Zero-trust: Anonymous vote cast via blind signatures. "
        "Strictly contains NO legislator_id or biometric signature."
    ),
)
async def cast_anonymous_vote(
    db_session: DbSessionDep,
    background_tasks: BackgroundTasks,
    body: VoteCastRequest,
) -> VoteCastResponse:
    try:
        await vote_service.cast_anonymous_vote(
            db_session,
            voting_round_id=body.voting_round_id,
            vote_value=body.vote_value,
            ephemeral_pub=body.ephemeral_pub,
            server_signature=body.server_signature,
            vote_signature=body.vote_signature,
        )
        current_votes = await vote_repository.count_votes_received(db_session, body.voting_round_id)
    except ValueError as exc:
        raise ConflictException(str(exc))

    background_tasks.add_task(
        manager.broadcast,
        "NON_NOMINAL_VOTE_CAST",
        {
            "voting_round_id": str(body.voting_round_id),
            "current_votes": current_votes,
        },
    )

    return VoteCastResponse(status="success", message="Voto emitido anónimamente")

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

    allowed_statuses = [
        RoundStatus.VOTING_CLOSED,
        RoundStatus.RESOLVED,
        RoundStatus.TIED,
        RoundStatus.ABORTED,
        RoundStatus.VOIDED
    ]
    if voting_round.status not in allowed_statuses:
        raise BadRequestException("Tally is only available after voting is closed.")

    if voting_round.is_nominal:
        vote_counts = await vote_repository.count_nominal_votes_by_round(db_session, voting_round_id)
    else:
        vote_counts = await vote_service.get_non_nominal_tallies(db_session, voting_round_id)

    aff = vote_counts.get(VoteValue.AFFIRMATIVE, 0)
    neg = vote_counts.get(VoteValue.NEGATIVE, 0)
    abs_count = vote_counts.get(VoteValue.ABSTENTION, 0)

    if voting_round.status in [RoundStatus.RESOLVED, RoundStatus.ABORTED, RoundStatus.VOIDED]:
        return VotingRoundTallyResponse(
            affirmative=aff,
            negative=neg,
            abstentions=abs_count,
            suggested_result=voting_round.result or "UNKNOWN",
        )

    # Compute suggested result
    voting_type = await voting_round_service.get_voting_type_for_round(db_session, voting_round_id)
    leg_session = await legislative_session_repository.get_by_id(db_session, voting_round.legislative_session_id)
    total_members = await legislator_repository.count_active_legislators(db_session)
    
    quorum_present = voting_round.certified_quorum_count or voting_round.quorum_present_count or 0

    if voting_type and leg_session:
        total_members = calculate_effective_denominator(
            calculation_base=CalculationBase.TOTAL_MEMBERS,
            president_type=leg_session.pres_type,
            president_votes_ordinarily=voting_round.president_votes_ordinarily,
            raw_quorum=quorum_present,
            raw_total_members=total_members,
            votes_cast=aff + neg,
        )

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
    try:
        voting_round = await vote_service.cast_tie_breaker_vote(
            db_session,
            raw_payload_string=body.raw_payload_string,
            cryptographic_signature=body.cryptographic_signature,
        )
        await db_session.commit()
    except ValueError as exc:
        await db_session.rollback()
        raise ConflictException(str(exc))
    except Exception as exc:
        await db_session.rollback()
        raise InternalServerException(str(exc))

    response = VotingRoundResponse.model_validate(voting_round)

    background_tasks.add_task(
        manager.broadcast,
        "TIE_BREAKER_VOTE_CAST",
        {
            "id": str(voting_round.id),
            "result": response.result,
            "new_status": response.status.value,
            "legislative_session_id": str(response.legislative_session_id),
        },
    )

    return response