from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from structlog import get_logger

from src.core.database import db_session_factory
from src.core.websocket import manager
from src.repositories import device_repository

log = get_logger(__name__)

websocket_router = APIRouter()

@websocket_router.websocket("/ws/state")
async def ws_state(
    websocket: WebSocket,
    device_token: str = Query(),
) -> None:
    async with db_session_factory() as db_session:
        device = await device_repository.get_active_device_by_token(
            db_session, device_token,
        )

    if device is None:
        await websocket.close(code=1008, reason="Invalid or inactive device token.")
        return

    await manager.connect(websocket, device_token)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        log.error("Unexpected WebSocket error.")
        manager.disconnect(websocket)