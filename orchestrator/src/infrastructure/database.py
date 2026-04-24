from structlog import get_logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.core.config import EnvironmentOption, settings

log = get_logger(__name__)

db_engine: AsyncEngine = create_async_engine(
    settings.db.URI,
    pool_size=settings.db.POOL_MIN_SIZE,
    max_overflow=settings.db.POOL_MAX_SIZE - settings.db.POOL_MIN_SIZE,
    pool_pre_ping=True,
    pool_recycle=settings.db.POOL_RECYCLE_SECONDS,
    pool_timeout=settings.db.POOL_TIMEOUT_SECONDS,
    echo=settings.app.ENVIRONMENT is EnvironmentOption.DEVELOPMENT,
)

db_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=db_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

async def engine_health_check() -> bool:
    try:
        async with db_engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        log.error(
            "database.db_check_failed", 
            error=str(exc),
        )
        return False