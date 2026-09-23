"""
MongoDB Document Schemas & API Data Transfer Objects (DTOs).
Uses Pydantic v2 for validation and serialization of high-velocity detection telemetry.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class BoundingBoxDoc(BaseModel):
    """Normalized bounding box detection record."""
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    class_name: str
    track_id: Optional[int] = None
    attributes: Optional[Dict[str, Any]] = None


class DetectionEventDoc(BaseModel):
    """Stored MongoDB detection event document for detection_logs collection."""
    camera_id: int
    camera_name: Optional[str] = "Unknown Camera"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    frame_number: Optional[int] = 0
    fps: Optional[float] = 0.0
    module: Optional[str] = "GENERAL"  # FIRE_SMOKE, PPE, RESTRICTED_ZONE
    detections: List[BoundingBoxDoc] = []
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class CameraTelemetryDoc(BaseModel):
    """Periodic hardware and processing telemetry document for telemetry_logs collection."""
    camera_id: int
    camera_name: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ai_fps: Optional[float] = 0.0
    stream_fps: Optional[float] = 0.0
    inference_latency_ms: Optional[float] = 0.0
    active_worker_tracks: Optional[int] = 0
    active_violations: Optional[int] = 0
    status: Optional[str] = "STREAMING"


class MongoQueryFilter(BaseModel):
    """Query parameters for retrieving detection documents from MongoDB."""
    camera_id: Optional[int] = None
    class_name: Optional[str] = None
    module: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = Field(default=50, ge=1, le=1000)
    skip: int = Field(default=0, ge=0)


class MongoHealthStatus(BaseModel):
    """Real-time diagnostic health response schema for MongoDB."""
    enabled: bool
    connected: bool
    url: str
    database: str
    collections: List[str] = []
    document_counts: Dict[str, int] = {}
    error: Optional[str] = None
