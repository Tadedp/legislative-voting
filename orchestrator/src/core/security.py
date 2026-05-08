import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
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