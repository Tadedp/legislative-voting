import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.device import Device
from src.repositories import device_repository, legislator_repository
from src.services.renaper_client import renaper_client
from src.core.websocket import manager
from src.core.security import (
    extract_public_key_pem_from_cert,
    compute_hardware_fingerprint,
    validate_attestation_chain,
    parse_attestation_extension,
    validate_attestation_properties
)

async def enroll_device(
    db: AsyncSession,
    provisioning_token: str,
    biometric_payload: str,
    hardware_fingerprint: str,
    certificate_chain: list[str],
) -> dict[str, Any]:
    # 1. Capability Check
    legislator = await legislator_repository.get_by_provisioning_token(db, provisioning_token)
    now = datetime.now(timezone.utc)
    
    if legislator is None or legislator.deleted_at is not None:
        raise PermissionError("Token de aprovisionamiento inválido.")
        
    if legislator.provisioning_token_expires_at and now > legislator.provisioning_token_expires_at:
        raise PermissionError("Token de aprovisionamiento expirado.")

    # 2. Hardware Fingerprint Check
    computed_fingerprint = compute_hardware_fingerprint(certificate_chain[0])
    if computed_fingerprint != hardware_fingerprint.lower():
        raise ValueError("Discrepancia en la huella de hardware.")

    # 3. Cryptographic Hardware Attestation Audit
    try:
        validate_attestation_chain(certificate_chain)
        ext_data = parse_attestation_extension(certificate_chain[0])
        validate_attestation_properties(ext_data, provisioning_token, "edu.um.voterterminal")
    except Exception as exc:
        raise ValueError(f"Fallo en la atestación: {str(exc)}")

    # 4. Biometric Check
    identity_ok = await renaper_client.verify_identity(legislator.national_id, biometric_payload)
    if not identity_ok:
        # Burn the token on failure
        legislator.provisioning_token = None
        legislator.provisioning_token_expires_at = None
        legislator.provisioning_token_generated_at = None
        await db.flush()
        raise PermissionError("Fallo en la verificación de identidad biométrica.")
            
    # Extract PEM for signature verification
    public_key_pem = extract_public_key_pem_from_cert(certificate_chain[0])

    # 5. Commit & Burn
    device_token = secrets.token_urlsafe(32)
    device = Device(
        legislator_id=legislator.id,
        hardware_fingerprint=computed_fingerprint,
        public_key_pem=public_key_pem,
        device_token=device_token,
    )
    await legislator_repository.create_device(db, device=device)

    # Burn token
    legislator.provisioning_token = None
    legislator.provisioning_token_expires_at = None
    legislator.provisioning_token_generated_at = None
    await db.flush()

    return {
        "device_token": device_token,
        "device_id": device.id,
        "legislator_id": legislator.id
    }

async def wipe_device(
    db: AsyncSession,
    device_id: uuid.UUID,
) -> tuple[Device, str]:
    device = await device_repository.get_by_id(db, device_id)

    if device is None or device.deleted_at is not None:
        raise ValueError("Terminal no encontrada.")

    old_device_token = device.device_token

    now = datetime.now(timezone.utc)

    device.deleted_at = now
    device.device_token = f"REVOKED_{secrets.token_urlsafe(32)}"

    await manager.force_disconnect_device(old_device_token)

    await db.flush()
    return device, old_device_token
