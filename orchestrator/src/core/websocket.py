from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket
from structlog import get_logger

log = get_logger(__name__)

class ConnectionManager:
    def __init__(self) -> None:
        self._active_connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._active_connections.add(websocket)
        log.info(
            "WebSocket connected. Active connections: %d",
            len(self._active_connections),
        )

    def disconnect(self, websocket: WebSocket) -> None:
        self._active_connections.discard(websocket)
        log.info(
            "WebSocket disconnected. Active connections: %d",
            len(self._active_connections),
        )

    async def broadcast(
        self,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        message: dict[str, Any] = {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }

        stale: list[WebSocket] = []

        for connection in self._active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                log.error("Failed to send to WebSocket; marking as stale.")
                stale.append(connection)

        for ws in stale:
            self._active_connections.discard(ws)

    @property
    def active_count(self) -> int:
        return len(self._active_connections)

manager: ConnectionManager = ConnectionManager()