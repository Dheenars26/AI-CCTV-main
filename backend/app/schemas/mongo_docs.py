"""
MongoDB Document Schemas & API Data Transfer Objects (DTOs).
Simplified alert-focused schema storing only essential incident data per camera.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class AlertEventDoc(BaseModel):
    """
    Stored MongoDB alert event document for the 'alert_events' collection.

    Each document represents a single verified safety incident with
    camera context, alert classification, detection snapshot path, and timestamp.
    """
    camera_id: int
    camera_name: str = "Unknown Camera"
    location: Optional[str] = None
    alert_type: str                        # e.g. "fire", "smoke", "ppe_violation", "zone_violation"
    confidence: float = 0.0
    snapshot_path: Optional[str] = None    # Relative path to the detection JPEG snapshot
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class AlertEventQueryFilter(BaseModel):
    """Query parameters for retrieving alert events from MongoDB."""
    camera_id: Optional[int] = None
    alert_type: Optional[str] = None
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
