import base64
import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from ecdsa import SECP256k1, BadSignatureError, VerifyingKey # type: ignore
from starlette.concurrency import run_in_threadpool
from structlog import get_logger

from src.core.config import settings

log = get_logger(__name__)

_hasher = PasswordHasher(
    time_cost=settings.security.ARGON2_TIME_COST,
    memory_cost=settings.security.ARGON2_MEMORY_COST,
    parallelism=settings.security.ARGON2_PARALLELISM,
    hash_len=32,
    salt_len=16,
)

async def hash_password(plain: str) -> str:
    return await run_in_threadpool(_hasher.hash, plain)

async def verify_password(plain: str, hashed: str) -> bool:
    try:
        return await run_in_threadpool(_hasher.verify, hashed, plain)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False

def generate_session_token() -> str:
    return secrets.token_hex(32)

def extract_public_key_from_cert(cert_b64: str) -> str:
    """Extract the uncompressed secp256k1 public key hex from a Base64-encoded X.509 certificate.

    Attempts DER decoding first (most common for Android attestation chains),
    then falls back to PEM.  Raises ValueError on any parsing or curve mismatch.
    """
    try:
        cert_bytes = base64.b64decode(cert_b64)
    except Exception as exc:
        raise ValueError(f"Invalid Base64 certificate data: {exc}") from exc

    # Try DER first; if it fails, attempt PEM.
    cert: x509.Certificate | None = None
    try:
        cert = x509.load_der_x509_certificate(cert_bytes)
    except Exception:
        try:
            cert = x509.load_pem_x509_certificate(cert_bytes)
        except Exception as exc:
            raise ValueError(
                f"Certificate could not be parsed as DER or PEM: {exc}",
            ) from exc

    public_key = cert.public_key()

    if not isinstance(public_key, ec.EllipticCurvePublicKey):
        raise ValueError(
            "Certificate does not contain an Elliptic Curve public key.",
        )

    if not isinstance(public_key.curve, ec.SECP256K1):
        raise ValueError(
            f"Expected SECP256K1 curve, got {public_key.curve.name}.",
        )

    uncompressed_bytes = public_key.public_bytes(
        Encoding.X962,
        PublicFormat.UncompressedPoint,
    )
    return uncompressed_bytes.hex()

def verify_secp256k1_signature(
    public_key_hex: str,
    payload: bytes,
    signature_hex: str,
) -> bool:
    try:
        public_key_bytes = bytes.fromhex(public_key_hex)
        signature_bytes = bytes.fromhex(signature_hex)

        vk = VerifyingKey.from_string( # type: ignore
            public_key_bytes,
            curve=SECP256k1,
            hashfunc=hashlib.sha256,
        )

        vk.verify( # type: ignore
            signature_bytes,
            payload,
            hashfunc=hashlib.sha256,
        )
        return True

    except BadSignatureError:
        log.error("Signature verification failed: invalid signature.")
        return False
    except Exception:
        log.error(
            "Signature verification failed: malformed key or signature.",
            exc_info=True,
        )
        return False