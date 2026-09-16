"""
Production-Grade Thread-Safe WebSocket Connection Manager (/api/v1/ws).
Manages multi-client subscriptions, heartbeat ping/pong, event serialization, versioning,
and isolated async message broadcasting with backpressure protection.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from fastapi import WebSocket, status

from app.schemas.websocket import WSEventEnvelope
from app.utils.logger import logger

# Supported System WebSocket Events
EVENT_CAMERA_STATUS_CHANGED = "camera_status_changed"
EVENT_FIRE_DETECTED = "fire_detected"
EVENT_SMOKE_DETECTED = "smoke_detected"
EVENT_ALERT_CREATED = "alert_created"
EVENT_ALERT_UPDATED = "alert_updated"
EVENT_ALERT_RESOLVED = "alert_resolved"
EVENT_CAMERA_DISCONNECTED = "camera_disconnected"
EVENT_CAMERA_RECONNECTED = "camera_reconnected"
EVENT_SYSTEM_STATUS_CHANGED = "system_status_changed"


class ConnectionManager:
    """
    Manages active client WebSocket connections and broadcast queues.
    Implements per-client send timeouts so broken/slow clients never block active connections.
    """

    def __init__(self):
        # Maps active WebSocket -> optional user_id
        self._connections: Dict[WebSocket, Optional[str]] = {}
        self._lock = asyncio.Lock()
        self._seq_counter: int = 0
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Sets main application asyncio event loop for cross-thread scheduling."""
        self._loop = loop

    async def connect(self, websocket: WebSocket, user_id: Optional[str] = None, subprotocol: Optional[str] = None) -> None:
        """
        Accepts incoming WebSocket connection and registers client in active connection map.
        """
        if not self._loop or self._loop.is_closed():
            try:
                self._loop = asyncio.get_running_loop()
            except Exception:
                pass

        if subprotocol and websocket.headers.get("Sec-WebSocket-Protocol"):
            await websocket.accept(subprotocol=subprotocol)
        else:
            await websocket.accept()

        async with self._lock:
            self._connections[websocket] = user_id
        
        logger.info(f"WebSocket Manager: Client connected (user_id={user_id}). Active clients: {len(self._connections)}")

    async def disconnect(self, websocket: WebSocket) -> None:
        """
        Unregisters client connection safely on disconnect or socket failure.
        """
        async with self._lock:
            if websocket in self._connections:
                user_id = self._connections.pop(websocket)
                logger.info(f"WebSocket Manager: Client disconnected (user_id={user_id}). Active clients: {len(self._connections)}")

    @property
    def active_count(self) -> int:
        return len(self._connections)

    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket) -> bool:
        """
        Sends JSON message to a single WebSocket client with 2.0s send timeout protection.
        """
        try:
            await asyncio.wait_for(websocket.send_json(message), timeout=2.0)
            return True
        except Exception as e:
            logger.warning(f"WebSocket Manager: Failed sending message to client: {str(e)}")
            await self.disconnect(websocket)
            return False

    async def handle_incoming_message(self, websocket: WebSocket, raw_text: str) -> None:
        """
        Parses client message, responding to ping keep-alive heartbeats.
        """
        try:
            data = json.loads(raw_text) if raw_text.startswith("{") else {"type": raw_text.strip().lower()}
            msg_type = data.get("type", "").lower() or data.get("event", "").lower()

            if msg_type in ("ping", "heartbeat"):
                pong_msg = {
                    "type": "pong",
                    "version": "1.0",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                await self.send_personal_message(pong_msg, websocket)
            else:
                ack_msg = {
                    "type": "ack",
                    "message": "Message received",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                await self.send_personal_message(ack_msg, websocket)
        except Exception as e:
            logger.debug(f"WebSocket Manager: Raw text received from client: '{raw_text}'")

    async def broadcast_event(self, event: str, data: Dict[str, Any], version: str = "1.0") -> None:
        """
        Broadcasts standardized event payload to all active WebSocket clients concurrently.
        Each client send is isolated in a try/except timeout block to prevent slow-client backpressure.
        """
        import uuid
        async with self._lock:
            sockets = list(self._connections.keys())
            self._seq_counter += 1
            current_seq = self._seq_counter

        if not sockets:
            return

        envelope = WSEventEnvelope(
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            seq=current_seq,
            event=event,
            version=version,
            timestamp=datetime.now(timezone.utc).isoformat(),
            data=data
        )
        payload_dict = envelope.model_dump()

        logger.info(f"WebSocket Manager: Broadcasting event '{event}' (v{version}) to {len(sockets)} connected client(s).")
        
        # Dispatch concurrently to all clients with isolation
        tasks = [self.send_personal_message(payload_dict, ws) for ws in sockets]
        await asyncio.gather(*tasks, return_exceptions=True)

    def broadcast_event_sync(self, event: str, data: Dict[str, Any], version: str = "1.0") -> None:
        """
        Thread-safe synchronous wrapper for scheduling broadcast from background worker threads.
        """
        try:
            loop = getattr(self, "_loop", None)
            if loop is None or loop.is_closed():
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

            if loop and loop.is_running():
                asyncio.run_coroutine_threadsafe(self.broadcast_event(event, data, version), loop)
            else:
                logger.debug(f"WebSocket Manager: No running asyncio loop available for sync broadcast of '{event}'")
        except Exception as e:
            logger.debug(f"WebSocket Manager sync broadcast note: {str(e)}")


manager = ConnectionManager()
