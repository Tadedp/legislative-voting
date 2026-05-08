from typing import Any

from structlog import get_logger
from fastapi import APIRouter, status

from src.schemas.common_schemas import ResponseEnvelope
from src.core.database import engine_health_check

log = get_logger(__name__)

health_router = APIRouter(
    prefix="/health",
    tags=["Health"],
)

@health_router.get(
    "", 
    status_code=status.HTTP_204_NO_CONTENT,
)
async def liveness() -> None:
    return None

@health_router.get(
    "/ready", 
    status_code=status.HTTP_200_OK,
    response_model=ResponseEnvelope[dict[str, Any]],
)
async def readiness() -> dict[str, Any]:
    db_ok = await engine_health_check(),
    
    checks = {"database": db_ok}
    all_healthy = all(checks.values())
    return {"data": {"healthy": all_healthy, "checks": checks}}