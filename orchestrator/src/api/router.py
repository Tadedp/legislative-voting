from collections.abc import Callable, Coroutine
from time import perf_counter
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException as StarletteHTTPException
from structlog import get_logger

from src.api.routers.auth_router import auth_router
from src.api.routers.device_router import device_router
from src.api.routers.health_router import health_router
from src.api.routers.legislative_session_router import legislative_session_router
from src.api.routers.attendance_router import attendance_router
from src.api.routers.agenda_item_router import agenda_item_router
from src.api.routers.legislator_router import legislator_router
from src.api.routers.voting_round_router import voting_round_router
from src.api.routers.user_router import user_router
from src.api.routers.voting_type_router import voting_type_router
from src.api.routers.websocket_router import websocket_router
from src.api.routers.vote_router import vote_router
from src.api.routers.public_audit_router import public_audit_router

log = get_logger(__name__)

class LoggingRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            start_time = perf_counter()
            
            try:
                response = await original_route_handler(request)
                
                process_time = (perf_counter() - start_time) * 1000
                            
                log.info(
                    "http.request",
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    duration_ms=f"{process_time:.2f}ms",
                    usuario=getattr(request.state, "usuario", "unknown"),
                )
                return response
                
            except Exception as exc:
                process_time = (perf_counter() - start_time) * 1000
                
                status_code = 500
                if isinstance(exc, StarletteHTTPException):
                    status_code = exc.status_code
                elif isinstance(exc, RequestValidationError):
                    status_code = 422
                    
                log.error(
                    "http.request",
                    method=request.method,
                    path=request.url.path,
                    status_code=status_code,
                    duration_ms=f"{process_time:.2f}ms",
                    usuario=getattr(request.state, "usuario", "unknown"),
                    error=f"{exc.__class__.__name__}"
                )
                
                raise exc

        return custom_route_handler
    
router = APIRouter(route_class=LoggingRoute)

router.include_router(auth_router)
router.include_router(device_router)
router.include_router(health_router)
router.include_router(legislative_session_router)
router.include_router(attendance_router)
router.include_router(legislator_router)
router.include_router(agenda_item_router)
router.include_router(voting_round_router)
router.include_router(user_router)
router.include_router(voting_type_router)
router.include_router(websocket_router)
router.include_router(vote_router)
router.include_router(public_audit_router)