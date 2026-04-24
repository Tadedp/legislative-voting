import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from starlette.concurrency import run_in_threadpool

from src.core.config import settings

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
