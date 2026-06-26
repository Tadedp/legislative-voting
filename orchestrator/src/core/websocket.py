import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket
from structlog import get_logger

log = get_logger(__name__)

background_tasks = set()

class ConnectionManager:
    """Manages WebSocket connections for all connected voter terminals and dashboards.

    Connections are keyed by device_token for targeted messaging to Edge devices.
    A parallel mapping tracks the legislator_id behind each token.
    Passive clients (web dashboards) are stored separately.
    """

    def __init__(self) -> None:
        self._active_edge_devices: dict[str, WebSocket] = {}
        self._token_to_legislator_id: dict[str, uuid.UUID] = {}
        self._active_dashboards: set[WebSocket] = set()
        self._queues: dict[WebSocket, asyncio.Queue] = {}

    async def connect(
        self,
        websocket: WebSocket,
        device_token: str | None = None,
        *,
        legislator_id: uuid.UUID | None = None,
    ) -> None:
        """Accept a WebSocket and register it as an active Edge or passive client."""
        await websocket.accept()
        queue: asyncio.Queue = asyncio.Queue()
        self._queues[websocket] = queue
        
        worker_task = asyncio.create_task(self._worker(websocket, queue))
        background_tasks.add(worker_task)
        worker_task.add_done_callback(background_tasks.discard)
        
        if device_token and legislator_id:
            if device_token in self._active_edge_devices:
                existing_ws = self._active_edge_devices.pop(device_token)
                self._token_to_legislator_id.pop(device_token, None)
                try:
                    await existing_ws.close(code=1008, reason="Concurrent login detected.")
                except Exception:
                    pass
                self.disconnect(existing_ws)

            self._active_edge_devices[device_token] = websocket
            self._token_to_legislator_id[device_token] = legislator_id
            log.info(
                "Active WebSocket connected. Active connections: %d",
                len(self._active_edge_devices),
            )
        else:
            self._active_dashboards.add(websocket)
            log.info(
                "Passive WebSocket connected. Passive connections: %d",
                len(self._active_dashboards),
            )

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        try:
            if websocket in self._queues:
                queue = self._queues.pop(websocket)
                queue.put_nowait(None)
        except (KeyError, ValueError):
            pass

        try:
            if websocket in self._active_dashboards:
                self._active_dashboards.remove(websocket)
                log.info(
                    "Passive WebSocket disconnected. Passive connections: %d",
                    len(self._active_dashboards),
                )
                return
        except (KeyError, ValueError):
            pass

        token_to_remove: str | None = None
        for token, ws in list(self._active_edge_devices.items()):
            if ws is websocket:
                token_to_remove = token
                break

        if token_to_remove is not None:
            try:
                del self._active_edge_devices[token_to_remove]
                self._token_to_legislator_id.pop(token_to_remove, None)
                log.info(
                    "Active WebSocket disconnected. Active connections: %d",
                    len(self._active_edge_devices),
                )
            except (KeyError, ValueError):
                pass

    async def force_disconnect_device(self, device_token: str) -> None:
        """Forcefully disconnect an edge device by its token (e.g. upon wipe)."""
        websocket = self._active_edge_devices.get(device_token)
        if websocket:
            try:
                await websocket.close()
            except Exception:
                pass
            self.disconnect(websocket)

    async def _worker(self, websocket: WebSocket, queue: asyncio.Queue) -> None:
        """Dedicated background task to guarantee FIFO message delivery per client."""
        try:
            while True:
                message = await queue.get()
                if message is None:
                    queue.task_done()
                    break
                await websocket.send_json(message)
                queue.task_done()
        except Exception:
            try:
                await websocket.close()
            except Exception:
                pass
            self.disconnect(websocket)

    async def _send_safe(self, websocket: WebSocket, message: dict[str, Any]) -> None:
        """Queue the message for the websocket worker to send."""
        queue = self._queues.get(websocket)
        if queue is not None:
            queue.put_nowait(message)

    async def broadcast(
        self,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        """Send a JSON event to every connected terminal and passive client."""
        message: dict[str, Any] = {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }

        all_connections = list(self._active_edge_devices.values()) + list(self._active_dashboards)

        for ws in all_connections:
            await self._send_safe(ws, message)

    async def send_to_device(
        self,
        device_token: str,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        """Send a targeted JSON event to a specific device."""
        websocket = self._active_edge_devices.get(device_token)
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
            try:
                await websocket.close()
            except Exception:
                pass
            self.disconnect(websocket)

    @property
    def active_count(self) -> int:
        """Return the number of currently active Edge WebSocket connections."""
        return len(self._active_edge_devices)

    @property
    def connected_legislator_ids(self) -> set[uuid.UUID]:
        """Return the set of legislator UUIDs with active WebSocket connections."""
        return set(self._token_to_legislator_id.values())

manager: ConnectionManager = ConnectionManager()