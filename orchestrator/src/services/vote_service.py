import json
import uuid
import base64

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import verify_secp256r1_signature, extract_public_key_from_cert
from src.models.nominal_vote import NominalVote, VoteValue
from src.models.non_nominal_tally import NonNominalTally
from src.models.non_nominal_voter import NonNominalVoter
from src.models.voting_round import RoundStatus, VotingRound
from src.repositories import (
    legislator_repository,
    legislative_session_repository,
    vote_repository,
    voting_round_repository,
    device_repository,
)

async def _get_device_hex_key(db_session: AsyncSession, legislator_id: uuid.UUID) -> str:
    device = await device_repository.get_active_device_by_legislator_id(db_session, legislator_id)
    if device is None:
        raise ValueError("El legislador no tiene una terminal activa.")
    
    cert_b64 = base64.b64encode(device.public_key_pem.encode('utf-8')).decode('utf-8')
    return extract_public_key_from_cert(cert_b64)

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
        raise ValueError("Legislador no encontrado.")

    public_key_hex = await _get_device_hex_key(db_session, legislator_id)

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
        public_key_hex=public_key_hex,
        payload=canonical_payload,
        signature_hex=cryptographic_signature,
    ):
        raise ValueError("Falló la verificación de la firma criptográfica.")

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
        raise ValueError("Legislador no encontrado.")

    public_key_hex = await _get_device_hex_key(db_session, legislator_id)

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
        public_key_hex=public_key_hex,
        payload=canonical_payload,
        signature_hex=cryptographic_signature,
    ):
        raise ValueError("Falló la verificación de la firma criptográfica.")

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
            "El voto desempate no puede ser una abstención. "
            "Solo se permiten AFIRMATIVO o NEGATIVO.",
        )

    voting_round = await voting_round_repository.get_by_id(
        db_session, voting_round_id,
    )
    if voting_round is None or voting_round.deleted_at is not None:
        raise ValueError("Votación no encontrada.")

    if voting_round.status != RoundStatus.TIED:
        raise ValueError(
            "El voto desempate solo está permitido cuando la votación "
            "está en estado 'TIED'.",
        )

    leg_session = await legislative_session_repository.get_by_id(
        db_session, voting_round.legislative_session_id,
    )
    if leg_session is None:
        raise ValueError("Sesión legislativa no encontrada.")

    if leg_session.presiding_officer_id is None:
        raise ValueError(
            "No se configuró una presidencia para esta sesión.",
        )

    if legislator_id != leg_session.presiding_officer_id:
        raise ValueError(
            "El voto desempate debe ser emitido por la presidencia.",
        )

    legislator = await legislator_repository.get_by_id(db_session, legislator_id)
    if legislator is None or legislator.deleted_at is not None:
        raise ValueError("Legislador no encontrado.")

    public_key_hex = await _get_device_hex_key(db_session, legislator_id)

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
        public_key_hex=public_key_hex,
        payload=canonical_payload,
        signature_hex=cryptographic_signature,
    ):
        raise ValueError("Falló la verificación de la firma criptográfica.")

    voting_round.tie_breaker_vote_value = vote_value.value

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