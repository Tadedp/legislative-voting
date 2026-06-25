import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket
from structlog import get_logger

log = get_logger(__name__)

class ConnectionManager:
    """Manages WebSocket connections for all connected voter terminals and dashboards.

    Connections are keyed by device_token for targeted messaging to Edge devices.
    A parallel mapping tracks the legislator_id behind each token.
    Passive clients (web dashboards) are stored separately.
    """

    def __init__(self) -> None:
        self._active_connections: dict[str, WebSocket] = {}
        self._token_to_legislator_id: dict[str, uuid.UUID] = {}
        self._passive_connections: set[WebSocket] = set()
        self._locks: dict[WebSocket, asyncio.Lock] = {}

    async def connect(
        self,
        websocket: WebSocket,
        device_token: str | None = None,
        *,
        legislator_id: uuid.UUID | None = None,
    ) -> None:
        """Accept a WebSocket and register it as an active Edge or passive client."""
        await websocket.accept()
        self._locks[websocket] = asyncio.Lock()
        
        if device_token and legislator_id:
            if device_token in self._active_connections:
                existing_ws = self._active_connections[device_token]
                try:
                    await existing_ws.close(code=1008, reason="Concurrent login detected.")
                except Exception:
                    pass
                self.disconnect(existing_ws)

            self._active_connections[device_token] = websocket
            self._token_to_legislator_id[device_token] = legislator_id
            log.info(
                "Active WebSocket connected. Active connections: %d",
                len(self._active_connections),
            )
        else:
            self._passive_connections.add(websocket)
            log.info(
                "Passive WebSocket connected. Passive connections: %d",
                len(self._passive_connections),
            )

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        if websocket in self._locks:
            del self._locks[websocket]

        if websocket in self._passive_connections:
            self._passive_connections.remove(websocket)
            log.info(
                "Passive WebSocket disconnected. Passive connections: %d",
                len(self._passive_connections),
            )
            return

        token_to_remove: str | None = None
        for token, ws in self._active_connections.items():
            if ws is websocket:
                token_to_remove = token
                break

        if token_to_remove is not None:
            del self._active_connections[token_to_remove]
            self._token_to_legislator_id.pop(token_to_remove, None)
            log.info(
                "Active WebSocket disconnected. Active connections: %d",
                len(self._active_connections),
            )

    async def _send_safe(self, websocket: WebSocket, message: dict[str, Any]) -> None:
        """Acquire the lock for the websocket before sending the JSON message."""
        lock = self._locks.get(websocket)
        if lock is None:
            return
            
        async with lock:
            await websocket.send_json(message)

    async def broadcast(
        self,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        """Send a JSON event to every connected terminal and passive client."""
        if not hasattr(self, "_broadcast_lock"):
            self._broadcast_lock = asyncio.Lock()

        message: dict[str, Any] = {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }

        async with self._broadcast_lock:
            stale: list[WebSocket] = []
            all_connections = list(self._active_connections.values()) + list(self._passive_connections)

            async def _send(ws: WebSocket) -> None:
                try:
                    await self._send_safe(ws, message)
                except Exception:
                    stale.append(ws)

            if all_connections:
                await asyncio.gather(*(_send(ws) for ws in all_connections))

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
            await self._send_safe(websocket, message)
        except Exception:
            log.error("Failed to send targeted message; disconnecting stale WS.")
            self.disconnect(websocket)

    @property
    def active_count(self) -> int:
        """Return the number of currently active Edge WebSocket connections."""
        return len(self._active_connections)

    @property
    def connected_legislator_ids(self) -> set[uuid.UUID]:
        """Return the set of legislator UUIDs with active WebSocket connections."""
        return set(self._token_to_legislator_id.values())

manager: ConnectionManager = ConnectionManager()