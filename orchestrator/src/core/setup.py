from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from typing import Any

from structlog import get_logger
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import settings
from src.infrastructure.database import engine_health_check, db_engine
from src.schemas.common_schemas import ResponseEnvelope

log = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    log.info(
        "app.starting",
        name=settings.app.NAME,
        version=settings.app.VERSION,
        env=settings.app.ENVIRONMENT,
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

    @app.get(
        "", 
        status_code=status.HTTP_204_NO_CONTENT,
    )
    async def liveness() -> None:
        return None

    @app.get(
        "/ready", 
        status_code=status.HTTP_200_OK,
        response_model=ResponseEnvelope[dict[str, Any]],
    )
    async def readiness() -> dict[str, Any]:
        db_healthy = await engine_health_check()

        return {
            "data": {"db_healthy": db_healthy}
        }

    return app
