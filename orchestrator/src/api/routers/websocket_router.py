from fastapi import APIRouter, Cookie, Header, WebSocket, WebSocketDisconnect
from structlog import get_logger

from src.api.dependencies.auth_deps import get_current_user
from src.core.database import db_session_factory
from src.core.websocket import manager
from src.repositories import device_repository, legislator_repository

log = get_logger(__name__)

websocket_router = APIRouter()

@websocket_router.websocket("/ws/state")
async def ws_state(
    websocket: WebSocket,
    device_token: str | None = Header(None, alias="X-Device-Token"),
    session_id: str | None = Cookie(None),
) -> None:
    """Authenticate a voter terminal or a passive dashboard."""
    legislator_id = None

    if device_token:
        # Edge device authentication
        async with db_session_factory() as db_session:
            device = await device_repository.get_active_device_by_token(
                db_session, device_token,
            )
            if device is None:
                await websocket.close(code=1008, reason="Invalid or inactive device token.")
                return
            legislator_id = device.legislator_id
    elif session_id:
        # Passive dashboard authentication
        class FakeRequest:
            cookies = {"session_id": session_id}
            headers = {}
        
        try:
            async with db_session_factory() as db_session:
                user = await get_current_user(request=FakeRequest(), db_session=db_session, cookie_token=session_id) # type: ignore
        except Exception:
            await websocket.close(code=1008, reason="Invalid session.")
            return
    else:
        await websocket.close(code=1008, reason="Authentication required.")
        return

    await manager.connect(
        websocket,
        device_token,
        legislator_id=legislator_id,
    )
    await check_quorum_and_warn()

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await check_quorum_and_warn()
    except Exception:
        log.error("Unexpected WebSocket error.")
        manager.disconnect(websocket)
        await check_quorum_and_warn()

async def check_quorum_and_warn() -> None:
    """Check if the active connections fall below a majority and emit a warning."""
    async with db_session_factory() as db_session:
        total_members = await legislator_repository.count_active_legislators(db_session)
    
    quorum_min = total_members // 2 + 1
    active_legislators = len(manager.connected_legislator_ids)
    if active_legislators < quorum_min:
        await manager.broadcast("QUORUM_WARNING", {
            "active_terminals": active_legislators,
            "minimum_required": quorum_min,
        })