"""
Pydantic Schemas for Verified Alert Incidents.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique Alert event ID (e.g. evt_9f8e7d6c5b4a)")
    camera_id: int = Field(..., description="Camera ID where incident occurred")
    camera_name: Optional[str] = Field(default=None, description="Camera Name")
    camera_location: Optional[str] = Field(default=None, description="Camera Installed Location")
    location: Optional[str] = Field(default=None, description="Location alias")
    class_name: str = Field(..., description="Detection class (fire, smoke)")
    state: str = Field(..., description="Alert state (POSSIBLE, CONFIRMED, ALERT_SENT, ACTIVE, CLEARED)")
    consecutive_frames: int = Field(..., description="Consecutive frame detection count")
    duration_seconds: float = Field(..., description="Total active duration in seconds")
    max_confidence: float = Field(..., description="Peak confidence score recorded")
    latest_confidence: float = Field(..., description="Latest confidence score")
    evidence_id: Optional[str] = Field(default=None, description="Secure evidence token reference")
    snapshot_url: Optional[str] = Field(default=None, description="Public secure JPEG snapshot URL")
    video_url: Optional[str] = Field(default=None, description="Public secure MP4 video clip URL")
    start_time: datetime = Field(..., description="Incident start timestamp")
    cleared_time: Optional[datetime] = Field(default=None, description="Incident cleared timestamp")
    remedial_action: Optional[str] = Field(default=None, description="Remedial action taken")
    remedy_notes: Optional[str] = Field(default=None, description="Detailed operator remedy notes")
    resolved_by: Optional[str] = Field(default=None, description="Username of operator who resolved incident")
    created_at: datetime
    updated_at: datetime


class AlertUpdate(BaseModel):
    state: Optional[str] = Field(default=None, pattern="^(?i)(POSSIBLE|CONFIRMED|ALERT_SENT|ACTIVE|CLEARED|RESOLVED|ACKNOWLEDGED|NEW)$")
    remedial_action: Optional[str] = Field(default=None, max_length=100, description="Remedial action taken")
    remedy_notes: Optional[str] = Field(default=None, max_length=500, description="Operator remedy notes")
    resolved_by: Optional[str] = Field(default=None, max_length=100, description="Operator identifier")

