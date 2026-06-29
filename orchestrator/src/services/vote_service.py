import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.security import verify_secp256r1_signature, extract_hex_from_pem_public_key
from src.models.agenda_item import ItemStatus
from src.models.nominal_vote import NominalVote, VoteValue
from src.models.non_nominal_tally import NonNominalTally
from src.models.non_nominal_voter import NonNominalVoter
from src.models.voting_round import RoundStage, RoundStatus, VotingRound
from src.models.session_attendance import SessionAttendance, AttendanceStatus
from src.services import audit_ledger_service
from src.repositories import (
    agenda_item_repository,
    legislator_repository,
    legislative_session_repository,
    vote_repository,
    device_repository,
)

async def _get_device_hex_key(db_session: AsyncSession, legislator_id: uuid.UUID) -> tuple[str, uuid.UUID]:
    device = await device_repository.get_active_device_by_legislator_id(db_session, legislator_id)
    if device is None:
        raise ValueError("El legislador no tiene una terminal activa.")
    
    return extract_hex_from_pem_public_key(device.public_key_pem), device.id

async def cast_nominal_vote(
    db_session: AsyncSession,
    *,
    raw_payload_string: str,
    cryptographic_signature: str,
) -> NominalVote:
    try:
        data = json.loads(raw_payload_string)
    except json.JSONDecodeError:
        raise ValueError("Payload JSON inválido.")
        
    legislator_id_str = data.get("legislator_id")
    voting_round_id_str = data.get("voting_round_id")
    vote_value_str = data.get("vote_value")
    raw_timestamp = data.get("timestamp")
    
    if not all([legislator_id_str, voting_round_id_str, vote_value_str, raw_timestamp]):
        raise ValueError("Faltan campos en el payload criptográfico.")
        
    try:
        timestamp = int(raw_timestamp)
    except (TypeError, ValueError):
        raise ValueError("El timestamp debe ser un número entero válido.")
        
    legislator_id = uuid.UUID(legislator_id_str)
    voting_round_id = uuid.UUID(voting_round_id_str)
    vote_value = VoteValue(vote_value_str)

    public_key_hex, device_id = await _get_device_hex_key(db_session, legislator_id)

    if not verify_secp256r1_signature(
        public_key_hex=public_key_hex,
        payload=raw_payload_string.encode("utf-8"),
        signature_hex=cryptographic_signature,
    ):
        raise ValueError("Falló la verificación de la firma criptográfica.")

    legislator = await legislator_repository.get_by_id(db_session, legislator_id)
    if legislator is None or legislator.deleted_at is not None:
        raise ValueError("Legislador no encontrado.")

    stmt = select(VotingRound).where(VotingRound.id == voting_round_id).with_for_update(read=True)
    result = await db_session.execute(stmt)
    voting_round = result.scalar_one_or_none()
    if voting_round is None or voting_round.deleted_at is not None:
        raise ValueError("Votación no encontrada.")

    if not voting_round.is_nominal:
        raise ValueError("Esta votación es secreta, no puede emitir un voto nominal.")

    if voting_round.status != RoundStatus.VOTING_OPEN:
        raise ValueError("La votación no se encuentra abierta.")

    attendance_stmt = select(SessionAttendance).where(
        SessionAttendance.legislative_session_id == voting_round.legislative_session_id,
        SessionAttendance.legislator_id == legislator_id
    )
    res = await db_session.execute(attendance_stmt)
    attendance = res.scalar_one_or_none()
    if attendance is None or attendance.status != AttendanceStatus.PRESENT:
        raise ValueError("El legislador está ausente y no puede votar.")

    current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    if timestamp > current_time_ms + 5000 or timestamp < current_time_ms - settings.security.ANTI_REPLAY_WINDOW_MILLISECONDS:
        raise ValueError("La carga útil criptográfica ha caducado (TTL superado) o viene del futuro.")

    vote = NominalVote(
        voting_round_id=voting_round_id,
        legislator_id=legislator_id,
        vote_value=vote_value,
        cryptographic_signature=cryptographic_signature,
        raw_payload=raw_payload_string,
        client_timestamp=timestamp,
        device_id=device_id,
    )

    try:
        result = await vote_repository.create_nominal_vote(db_session, vote=vote)
        await db_session.commit()
        return result
    except IntegrityError:
        await db_session.rollback()
        raise ValueError("El legislador ya ha emitido un voto para esta ronda.")


async def cast_non_nominal_vote(
    db_session: AsyncSession,
    *,
    eligibility_payload: str,
    eligibility_signature: str,
    vote_data: dict[str, Any],
) -> dict[str, Any]:
    try:
        data = json.loads(eligibility_payload)
    except json.JSONDecodeError:
        raise ValueError("Payload JSON inválido.")
        
    legislator_id_str = data.get("legislator_id")
    voting_round_id_str = data.get("voting_round_id")
    raw_timestamp = data.get("timestamp")
    
    if not all([legislator_id_str, voting_round_id_str, raw_timestamp]):
        raise ValueError("Faltan campos en el payload criptográfico de elegibilidad.")
        
    try:
        timestamp = int(raw_timestamp)
    except (TypeError, ValueError):
        raise ValueError("El timestamp debe ser un número entero válido.")
        
    legislator_id = uuid.UUID(legislator_id_str)
    voting_round_id = uuid.UUID(voting_round_id_str)

    vote_value_str = vote_data.get("vote_value")
    salt = vote_data.get("salt")
    if not vote_value_str or not salt:
        raise ValueError("Faltan campos en la data del voto.")
    vote_value = VoteValue(vote_value_str)

    public_key_hex, device_id = await _get_device_hex_key(db_session, legislator_id)

    if not verify_secp256r1_signature(
        public_key_hex=public_key_hex,
        payload=eligibility_payload.encode("utf-8"),
        signature_hex=eligibility_signature,
    ):
        raise ValueError("Falló la verificación de la firma criptográfica.")

    legislator = await legislator_repository.get_by_id(db_session, legislator_id)
    if legislator is None or legislator.deleted_at is not None:
        raise ValueError("Legislador no encontrado.")

    stmt = select(VotingRound).where(VotingRound.id == voting_round_id).with_for_update(read=True)
    result = await db_session.execute(stmt)
    voting_round = result.scalar_one_or_none()
    if voting_round is None or voting_round.deleted_at is not None:
        raise ValueError("Votación no encontrada.")

    if voting_round.is_nominal:
        raise ValueError("Esta votación es nominal, no puede emitir un voto secreto.")

    if voting_round.status != RoundStatus.VOTING_OPEN:
        raise ValueError("La votación no se encuentra abierta.")

    attendance_stmt = select(SessionAttendance).where(
        SessionAttendance.legislative_session_id == voting_round.legislative_session_id,
        SessionAttendance.legislator_id == legislator_id
    )
    res = await db_session.execute(attendance_stmt)
    attendance = res.scalar_one_or_none()
    if attendance is None or attendance.status != AttendanceStatus.PRESENT:
        raise ValueError("El legislador está ausente y no puede votar.")

    current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    if timestamp > current_time_ms + 5000 or timestamp < current_time_ms - settings.security.ANTI_REPLAY_WINDOW_MILLISECONDS:
        raise ValueError("La carga útil criptográfica ha caducado (TTL superado) o viene del futuro.")

    voter = NonNominalVoter(
        voting_round_id=voting_round_id,
        legislator_id=legislator_id,
        cryptographic_signature=eligibility_signature,
        raw_payload=eligibility_payload,
        client_timestamp=timestamp,
        device_id=device_id,
    )

    tally = NonNominalTally(
        voting_round_id=voting_round_id,
        vote_value=vote_value,
        salt=salt,
    )

    try:
        await vote_repository.create_non_nominal_voter_and_tally(
            db_session,
            voter=voter,
            tally=tally,
        )
        await db_session.commit()
    except IntegrityError:
        await db_session.rollback()
        raise ValueError("El legislador ya ha emitido un voto para esta ronda.")
        
    return {"voting_round_id": voting_round_id, "legislator_id": legislator_id}


async def cast_tie_breaker_vote(
    db_session: AsyncSession,
    *,
    raw_payload_string: str,
    cryptographic_signature: str,
) -> VotingRound:
    try:
        data = json.loads(raw_payload_string)
    except json.JSONDecodeError:
        raise ValueError("Payload JSON inválido.")
        
    legislator_id_str = data.get("legislator_id")
    voting_round_id_str = data.get("voting_round_id")
    vote_value_str = data.get("vote_value")
    raw_timestamp = data.get("timestamp")
    
    if not all([legislator_id_str, voting_round_id_str, vote_value_str, raw_timestamp]):
        raise ValueError("Faltan campos en el payload criptográfico.")
        
    try:
        timestamp = int(raw_timestamp)
    except (TypeError, ValueError):
        raise ValueError("El timestamp debe ser un número entero válido.")
        
    legislator_id = uuid.UUID(legislator_id_str)
    voting_round_id = uuid.UUID(voting_round_id_str)
    vote_value = VoteValue(vote_value_str)

    public_key_hex, device_id = await _get_device_hex_key(db_session, legislator_id)

    if not verify_secp256r1_signature(
        public_key_hex=public_key_hex,
        payload=raw_payload_string.encode("utf-8"),
        signature_hex=cryptographic_signature,
    ):
        raise ValueError("Falló la verificación de la firma criptográfica.")

    if vote_value == VoteValue.ABSTENTION:
        raise ValueError(
            "El voto desempate no puede ser una abstención. "
            "Solo se permiten AFIRMATIVO o NEGATIVO.",
        )

    stmt = select(VotingRound).where(VotingRound.id == voting_round_id).with_for_update()
    result = await db_session.execute(stmt)
    voting_round = result.scalar_one_or_none()
    if voting_round is None or voting_round.deleted_at is not None:
        raise ValueError("Votación no encontrada.")

    if voting_round.status != RoundStatus.TIED:
        raise ValueError(
            "El voto desempate solo está permitido cuando la votación "
            "está en estado 'TIED'.",
        )

    if voting_round.tie_breaker_vote_value is not None:
        raise ValueError("El voto desempate ya fue emitido.")

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

    attendance_stmt = select(SessionAttendance).where(
        SessionAttendance.legislative_session_id == voting_round.legislative_session_id,
        SessionAttendance.legislator_id == legislator_id
    )
    res = await db_session.execute(attendance_stmt)
    attendance = res.scalar_one_or_none()
    if attendance is None or attendance.status != AttendanceStatus.PRESENT:
        raise ValueError("El legislador está ausente y no puede votar.")

    current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    if timestamp > current_time_ms + 5000 or timestamp < current_time_ms - settings.security.ANTI_REPLAY_WINDOW_MILLISECONDS:
        raise ValueError("La carga útil criptográfica ha caducado (TTL superado) o viene del futuro.")

    voting_round.tie_breaker_vote_value = vote_value.value
    voting_round.tie_breaker_signature = cryptographic_signature
    voting_round.tie_breaker_device_id = device_id
    voting_round.tie_breaker_client_timestamp = timestamp

    if vote_value == VoteValue.AFFIRMATIVE:
        voting_round.result = "PASSED"
    else:
        voting_round.result = "FAILED"

    voting_round.status = RoundStatus.RESOLVED
    
    agenda_item = await agenda_item_repository.get_by_id(db_session, voting_round.agenda_item_id)
    if agenda_item:
        if voting_round.result == "PASSED":
            if voting_round.stage == RoundStage.GENERAL:
                agenda_item.status = ItemStatus.APPROVED_IN_GENERAL
            elif voting_round.stage in [RoundStage.SINGLE, RoundStage.SPECIFIC]:
                agenda_item.status = ItemStatus.APPROVED
        else:
            if voting_round.stage in [RoundStage.SINGLE, RoundStage.GENERAL]:
                agenda_item.status = ItemStatus.REJECTED
                
    await audit_ledger_service.anchor_and_snapshot_round(db_session, voting_round_id, voting_round.is_nominal)

    await db_session.flush()
    return voting_round

async def get_non_nominal_tallies(
    db_session: AsyncSession,
    voting_round_id: uuid.UUID,
) -> dict[VoteValue, int]:
    return await vote_repository.count_non_nominal_tallies_by_round(
        db_session, voting_round_id,
    )