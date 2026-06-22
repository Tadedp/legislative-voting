import uuid
from typing import Any

from fastapi import APIRouter, status
from sqlalchemy import select

from src.api.dependencies.common_deps import DbSessionDep
from src.api.exceptions import NotFoundException
from src.models.audit_ledger import AuditLedger

public_audit_router = APIRouter(
    tags=["Public Audit"],
)

@public_audit_router.get(
    "/public/audit/{voting_round_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get public audit ledger for a voting round",
    description="Returns the cryptographically verifiable snapshot of a voting round. Publicly accessible without authentication.",
)
async def get_public_audit_ledger(
    db_session: DbSessionDep,
    voting_round_id: uuid.UUID,
) -> dict[str, Any]:
    stmt = select(AuditLedger).where(AuditLedger.voting_round_id == voting_round_id)
    result = await db_session.execute(stmt)
    ledger = result.scalar_one_or_none()
    
    if ledger is None:
        raise NotFoundException(
            detail="Audit ledger not found for the specified voting round.",
        )
        
    return {
        "voting_round_id": str(ledger.voting_round_id),
        "is_nominal": ledger.is_nominal,
        "nominal_merkle_root": ledger.nominal_merkle_root,
        "tally_merkle_root": ledger.tally_merkle_root,
        "eligibility_merkle_root": ledger.eligibility_merkle_root,
        "transaction_hash": ledger.transaction_hash,
        "block_number": ledger.block_number,
        "published_at": ledger.published_at.isoformat() if ledger.published_at else None,
        "tally_payload": ledger.tally_payload,
    }
