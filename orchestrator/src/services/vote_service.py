import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import verify_secp256r1_signature
from src.models.nominal_vote import NominalVote, VoteValue
from src.models.non_nominal_tally import NonNominalTally
from src.models.non_nominal_voter import NonNominalVoter
from src.models.voting_round import RoundStatus, VotingRound
from src.repositories import (
    legislator_repository,
    legislative_session_repository,
    vote_repository,
    voting_round_repository,
)

async def cast_nominal_vote(
    db_session: AsyncSession,
    *,
    voting_round_id: uuid.UUID,
    legislator_id: uuid.UUID,
    vote_value: VoteValue,
    timestamp: int,
    cryptographic_signature: str,
) -> NominalVote:
    legislator = await legislator_repository.get_by_id(db_session, legislator_id)

    if legislator is None or legislator.deleted_at is not None:
        raise ValueError("Legislator not found.")

    if legislator.current_public_key is None:
        raise ValueError("Legislator has no registered public key.")

    canonical_payload = json.dumps(
        {
            "legislator_id": str(legislator_id),
            "timestamp": timestamp,
            "vote_value": vote_value.value,
            "voting_round_id": str(voting_round_id),
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    if not verify_secp256r1_signature(
        public_key_hex=legislator.current_public_key,
        payload=canonical_payload,
        signature_hex=cryptographic_signature,
    ):
        raise ValueError("Cryptographic signature verification failed.")

    vote = NominalVote(
        voting_round_id=voting_round_id,
        legislator_id=legislator_id,
        vote_value=vote_value,
        cryptographic_signature=cryptographic_signature,
    )

    return await vote_repository.create_nominal_vote(db_session, vote=vote)

async def cast_non_nominal_vote(
    db_session: AsyncSession,
    *,
    voting_round_id: uuid.UUID,
    legislator_id: uuid.UUID,
    vote_value: VoteValue,
    timestamp: int,
    cryptographic_signature: str,
) -> None:
    legislator = await legislator_repository.get_by_id(db_session, legislator_id)

    if legislator is None or legislator.deleted_at is not None:
        raise ValueError("Legislator not found.")

    if legislator.current_public_key is None:
        raise ValueError("Legislator has no registered public key.")

    canonical_payload = json.dumps(
        {
            "legislator_id": str(legislator_id),
            "timestamp": timestamp,
            "vote_value": vote_value.value,
            "voting_round_id": str(voting_round_id),
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    if not verify_secp256r1_signature(
        public_key_hex=legislator.current_public_key,
        payload=canonical_payload,
        signature_hex=cryptographic_signature,
    ):
        raise ValueError("Cryptographic signature verification failed.")

    voter = NonNominalVoter(
        voting_round_id=voting_round_id,
        legislator_id=legislator_id,
        cryptographic_signature=cryptographic_signature,
    )

    tally = NonNominalTally(
        voting_round_id=voting_round_id,
        vote_value=vote_value,
    )

    await vote_repository.create_non_nominal_voter_and_tally(
        db_session,
        voter=voter,
        tally=tally,
    )

async def cast_tie_breaker_vote(
    db_session: AsyncSession,
    *,
    voting_round_id: uuid.UUID,
    legislator_id: uuid.UUID,
    vote_value: VoteValue,
    timestamp: int,
    cryptographic_signature: str,
) -> VotingRound:
    if vote_value == VoteValue.ABSTENTION:
        raise ValueError(
            "Tie-breaker vote cannot be an abstention. "
            "Only AFFIRMATIVE or NEGATIVE are permitted.",
        )

    # Retrieve and validate the voting round.
    voting_round = await voting_round_repository.get_by_id(
        db_session, voting_round_id,
    )
    if voting_round is None or voting_round.deleted_at is not None:
        raise ValueError("Voting round not found.")

    if voting_round.status != RoundStatus.TIED:
        raise ValueError(
            "Tie-breaker vote is only allowed when voting round "
            "status is 'TIED'.",
        )

    # Retrieve the legislative session to verify presidential identity.
    leg_session = await legislative_session_repository.get_by_id(
        db_session, voting_round.legislative_session_id,
    )
    if leg_session is None:
        raise ValueError("Legislative session not found.")

    if leg_session.presiding_officer_id is None:
        raise ValueError(
            "No presiding officer configured for this session.",
        )

    if legislator_id != leg_session.presiding_officer_id:
        raise ValueError(
            "Tie-breaker vote must be cast by the presiding officer.",
        )

    # Verify the cryptographic signature.
    legislator = await legislator_repository.get_by_id(db_session, legislator_id)
    if legislator is None or legislator.deleted_at is not None:
        raise ValueError("Legislator not found.")

    if legislator.current_public_key is None:
        raise ValueError("Legislator has no registered public key.")

    canonical_payload = json.dumps(
        {
            "legislator_id": str(legislator_id),
            "timestamp": timestamp,
            "vote_value": vote_value.value,
            "voting_round_id": str(voting_round_id),
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    if not verify_secp256r1_signature(
        public_key_hex=legislator.current_public_key,
        payload=canonical_payload,
        signature_hex=cryptographic_signature,
    ):
        raise ValueError("Cryptographic signature verification failed.")

    # Record the deciding vote on the round itself.
    voting_round.tie_breaker_vote_value = vote_value.value

    # Determine the final result based on the tie-breaker.
    if vote_value == VoteValue.AFFIRMATIVE:
        voting_round.result = "PASSED"
    else:
        voting_round.result = "FAILED"

    voting_round.status = RoundStatus.RESOLVED
    await db_session.flush()
    return voting_round

async def get_non_nominal_tallies(
    db_session: AsyncSession,
    voting_round_id: uuid.UUID,
) -> dict[VoteValue, int]:
    return await vote_repository.count_non_nominal_tallies_by_round(
        db_session, voting_round_id,
    )