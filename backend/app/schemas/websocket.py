"""
Pydantic Event Schemas for Real-Time WebSocket Notifications (/api/v1/ws).
Frontend-independent event contract supporting standard JSON serialization and versioning.
"""

from typing import Generic, TypeVar, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field

T = TypeVar("T")


import uuid


class WSEventEnvelope(BaseModel, Generic[T]):
    """
    Standardized WebSocket event message payload structure.
    """
    event_id: str = Field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}", description="Unique WebSocket Event ID")
    seq: int = Field(default=1, description="Sequential message counter for reconnect deduplication")
    event: str = Field(..., description="Event type name (e.g., fire_detected, camera_status_changed)")
    version: str = Field(default="1.0", description="WebSocket protocol version identifier")
    timestamp: str = Field(..., description="UTC ISO 8601 event timestamp")
    data: T = Field(..., description="Event payload object")


class FireDetectedPayload(BaseModel):
    camera_id: int = Field(..., description="Camera ID where fire was detected")
    camera_name: str = Field(..., description="Camera location/name")
    confidence: float = Field(..., description="AI confidence score (0.0 to 1.0)")
    alert_id: str = Field(..., description="Associated Alert event ID (e.g. evt_9f8e7d6c5b4a)")
    bounding_box: Optional[Dict[str, float]] = Field(default=None, description="Normalized bounding box coordinates")
    snapshot_url: Optional[str] = Field(default=None, description="Public secure evidence snapshot URL")


class SmokeDetectedPayload(BaseModel):
    camera_id: int = Field(..., description="Camera ID where smoke was detected")
    camera_name: str = Field(..., description="Camera location/name")
    confidence: float = Field(..., description="AI confidence score (0.0 to 1.0)")
    alert_id: str = Field(..., description="Associated Alert event ID")
    snapshot_url: Optional[str] = Field(default=None, description="Public secure evidence snapshot URL")


class AlertStatePayload(BaseModel):
    alert_id: str = Field(..., description="Alert Event ID")
    camera_id: int = Field(..., description="Camera ID")
    class_name: str = Field(..., description="Detection class (fire, smoke)")
    state: str = Field(..., description="Updated state (POSSIBLE, CONFIRMED, ALERT_SENT, ACTIVE, CLEARED)")
    consecutive_frames: int = Field(default=1)
    max_confidence: float = Field(default=0.0)
    cleared_time: Optional[str] = None


class CameraStatusPayload(BaseModel):
    camera_id: int = Field(..., description="Target Camera ID")
    camera_name: str = Field(..., description="Camera Name")
    status: str = Field(..., description="Status (CONNECTED, DISCONNECTED, CONNECTING, RECONNECTING, ERROR)")
    reconnect_attempts: int = Field(default=0)
    fps: float = Field(default=0.0)
    error_message: Optional[str] = None


class SystemStatusPayload(BaseModel):
    status: str = Field(..., json_schema_extra={"example": "OPERATIONAL"})
    active_cameras_count: int = Field(...)
    total_cameras_count: int = Field(...)
    ai_detection_enabled: bool = Field(...)

