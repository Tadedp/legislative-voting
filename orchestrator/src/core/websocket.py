import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket
from structlog import get_logger

log = get_logger(__name__)

class ConnectionManager:
    """Manages WebSocket connections for all connected voter terminals.

    Connections are keyed by device_token for targeted messaging, and a
    parallel mapping tracks the legislator_id behind each token so that
    quorum logic can determine which legislators are currently online.
    """

    def __init__(self) -> None:
        self._active_connections: dict[str, WebSocket] = {}
        self._token_to_legislator_id: dict[str, uuid.UUID] = {}

    async def connect(
        self,
        websocket: WebSocket,
        device_token: str,
        *,
        legislator_id: uuid.UUID,
    ) -> None:
        """Accept a WebSocket and register the device-to-legislator mapping."""
        await websocket.accept()
        self._active_connections[device_token] = websocket
        self._token_to_legislator_id[device_token] = legislator_id
        log.info(
            "WebSocket connected. Active connections: %d",
            len(self._active_connections),
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection and its legislator mapping.

        Only removes the entry if the stored websocket is the exact same
        object being disconnected.  This prevents a stale/ghost connection
        timeout from evicting a newly reconnected device.
        """
        token_to_remove: str | None = None
        for token, ws in self._active_connections.items():
            if ws is websocket:
                token_to_remove = token
                break

        if token_to_remove is not None:
            del self._active_connections[token_to_remove]
            self._token_to_legislator_id.pop(token_to_remove, None)

        log.info(
            "WebSocket disconnected. Active connections: %d",
            len(self._active_connections),
        )

    async def broadcast(
        self,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        """Send a JSON event to every connected terminal."""
        message: dict[str, Any] = {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }

        stale: list[WebSocket] = []

        for connection in self._active_connections.values():
            try:
                await connection.send_json(message)
            except Exception:
                log.error("Failed to send to WebSocket; marking as stale.")
                stale.append(connection)

        for ws in stale:
            self.disconnect(ws)

    async def send_to_device(
        self,
        device_token: str,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        """Send a targeted JSON event to a specific device."""
        websocket = self._active_connections.get(device_token)
        if websocket is None:
            log.error(
                "ws.send_to_device.not_connected",
                device_token_prefix=device_token[:8],
            )
            return

        message: dict[str, Any] = {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }

        try:
            await websocket.send_json(message)
        except Exception:
            log.error("Failed to send targeted message; disconnecting stale WS.")
            self.disconnect(websocket)

    @property
    def active_count(self) -> int:
        """Return the number of currently active WebSocket connections."""
        return len(self._active_connections)

    @property
    def connected_legislator_ids(self) -> set[uuid.UUID]:
        """Return the set of legislator UUIDs with active WebSocket connections.

        Used by quorum logic to determine how many legislators are
        present in the chamber.
        """
        return set(self._token_to_legislator_id.values())

manager: ConnectionManager = ConnectionManager()