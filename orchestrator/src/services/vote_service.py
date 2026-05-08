import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import verify_secp256k1_signature
from src.models.nominal_vote import NominalVote, NominalVoteValue
from src.models.non_nominal_vote import NonNominalVote
from src.repositories import legislator_repository, vote_repository

async def cast_nominal_vote(
    db_session: AsyncSession,
    *,
    motion_id: uuid.UUID,
    legislator_id: uuid.UUID,
    vote_value: NominalVoteValue,
    cryptographic_signature: str,
) -> NominalVote:
    legislator = await legislator_repository.get_by_id(db_session, legislator_id)

    if legislator is None or legislator.deleted_at is not None:
        raise ValueError("Legislator not found.")

    if legislator.current_public_key is None:
        raise ValueError("Legislator has no registered public key.")

    canonical_payload = json.dumps(
        {
            "motion_id": str(motion_id),
            "legislator_id": str(legislator_id),
            "vote_value": vote_value.value,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    if not verify_secp256k1_signature(
        public_key_hex=legislator.current_public_key,
        payload=canonical_payload,
        signature_hex=cryptographic_signature,
    ):
        raise ValueError("Cryptographic signature verification failed.")

    vote = NominalVote(
        motion_id=motion_id,
        legislator_id=legislator_id,
        vote_value=vote_value,
        cryptographic_signature=cryptographic_signature,
    )

    return await vote_repository.create_nominal_vote(db_session, vote=vote)

async def cast_non_nominal_vote(
    db_session: AsyncSession,
    *,
    motion_id: uuid.UUID,
    legislator_id: uuid.UUID,
    encrypted_payload: str,
    cryptographic_signature: str,
) -> NonNominalVote:
    legislator = await legislator_repository.get_by_id(db_session, legislator_id)

    if legislator is None or legislator.deleted_at is not None:
        raise ValueError("Legislator not found.")

    if legislator.current_public_key is None:
        raise ValueError("Legislator has no registered public key.")

    canonical_payload = json.dumps(
        {
            "encrypted_payload": encrypted_payload,
            "legislator_id": str(legislator_id),
            "motion_id": str(motion_id),
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    if not verify_secp256k1_signature(
        public_key_hex=legislator.current_public_key,
        payload=canonical_payload,
        signature_hex=cryptographic_signature,
    ):
        raise ValueError("Cryptographic signature verification failed.")

    vote = NonNominalVote(
        motion_id=motion_id,
        legislator_id=legislator_id,
        encrypted_payload=encrypted_payload,
        cryptographic_signature=cryptographic_signature,
    )

    return await vote_repository.create_non_nominal_vote(db_session, vote=vote)

async def get_non_nominal_votes(
    db_session: AsyncSession,
    motion_id: uuid.UUID,
) -> list[NonNominalVote]:
    return await vote_repository.get_non_nominal_votes_by_motion(db_session, motion_id)