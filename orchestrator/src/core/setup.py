from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from structlog import get_logger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import settings
from src.infrastructure.database import engine_health_check, db_engine

log = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    log.info(
        "app.starting",
    )
    
    if not await engine_health_check():
        raise Exception("Database connection failed")

    log.info("app.started")

    yield  

    log.info("app.shutting_down")
    await db_engine.dispose()
    log.info("app.stopped")

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app.NAME,
        version=settings.app.VERSION,
        description=settings.app.DESCRIPTION,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.security.CORS_ALLOWED_ORIGINS_LIST,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    return app
