"""
WebSocket Package Initialization.
Exports ConnectionManager, global manager instance, ws_router, and event name constants.
"""

from app.websocket.connection_manager import (
    manager,
    ConnectionManager,
    EVENT_CAMERA_STATUS_CHANGED,
    EVENT_FIRE_DETECTED,
    EVENT_SMOKE_DETECTED,
    EVENT_ALERT_CREATED,
    EVENT_ALERT_UPDATED,
    EVENT_ALERT_RESOLVED,
    EVENT_CAMERA_DISCONNECTED,
    EVENT_CAMERA_RECONNECTED,
    EVENT_SYSTEM_STATUS_CHANGED
)
from app.websocket.router import ws_router

__all__ = [
    "manager",
    "ConnectionManager",
    "ws_router",
    "EVENT_CAMERA_STATUS_CHANGED",
    "EVENT_FIRE_DETECTED",
    "EVENT_SMOKE_DETECTED",
    "EVENT_ALERT_CREATED",
    "EVENT_ALERT_UPDATED",
    "EVENT_ALERT_RESOLVED",
    "EVENT_CAMERA_DISCONNECTED",
    "EVENT_CAMERA_RECONNECTED",
    "EVENT_SYSTEM_STATUS_CHANGED"
]
