"""
Pydantic Schemas for System Diagnostics & Platform Analytics (SystemStatusResponse, SystemStatsResponse).
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class SystemStatusResponse(BaseModel):
    status: str = Field(..., json_schema_extra={"example": "OPERATIONAL"}, description="System operational status")
    version: str = Field(..., json_schema_extra={"example": "1.0.0"}, description="Application version")
    environment: str = Field(..., json_schema_extra={"example": "production"}, description="Runtime environment")
    active_cameras_count: int = Field(..., description="Number of currently running camera ingestion workers")
    total_cameras_count: int = Field(..., description="Total registered cameras in system")
    ai_detection_enabled: bool = Field(..., description="Global AI model inference status flag")
    email_alerts_enabled: bool = Field(..., description="Global email notification dispatch status flag")
    timestamp: datetime = Field(..., description="Current system UTC timestamp")


class SystemStatsResponse(BaseModel):
    total_cameras: int = Field(..., description="Total registered cameras count")
    active_cameras: int = Field(..., description="Active running streams count")
    online_cameras: int = Field(default=0, description="Online enabled cameras count")
    offline_cameras: int = Field(default=0, description="Offline disabled cameras count")
    active_alerts_count: int = Field(..., description="Currently active unresolved incident alerts")
    active_fire_alerts: int = Field(default=0, description="Active fire incidents count")
    active_smoke_alerts: int = Field(default=0, description="Active smoke incidents count")
    total_alerts_recorded: int = Field(..., description="Lifetime total verified alert count")
    total_detections_count: int = Field(..., description="Lifetime total raw AI prediction frames recorded")
    total_evidence_files: int = Field(..., description="Total stored evidence files count")
    uptime_seconds: float = Field(..., description="Application backend uptime in seconds")
    timestamp: datetime


class VerificationSettingsResponse(BaseModel):
    fire_min_confidence: float = Field(..., description="Minimum AI confidence for fire detection")
    fire_min_consecutive_frames: int = Field(..., description="Consecutive frames required for fire verification")
    fire_min_duration_seconds: float = Field(..., description="Minimum fire persistence duration in seconds")
    smoke_min_confidence: float = Field(..., description="Minimum AI confidence for smoke detection")
    smoke_min_consecutive_frames: int = Field(..., description="Consecutive frames required for smoke verification")
    smoke_min_duration_seconds: float = Field(..., description="Minimum smoke persistence duration in seconds")
    ppe_verification_frames: int = Field(..., description="Consecutive frames required for PPE violation verification")
    ppe_verification_duration_seconds: float = Field(..., description="Minimum PPE violation duration in seconds")
    verification_cooldown_seconds: float = Field(..., description="Alert suppression cooldown duration in seconds")


class VerificationSettingsUpdate(BaseModel):
    fire_min_confidence: Optional[float] = Field(None, ge=0.05, le=1.0, description="Confidence threshold for fire")
    fire_min_consecutive_frames: Optional[int] = Field(None, ge=1, le=30, description="Consecutive frames for fire")
    fire_min_duration_seconds: Optional[float] = Field(None, ge=0.1, le=10.0, description="Minimum duration for fire in seconds")
    smoke_min_confidence: Optional[float] = Field(None, ge=0.05, le=1.0, description="Confidence threshold for smoke")
    smoke_min_consecutive_frames: Optional[int] = Field(None, ge=1, le=30, description="Consecutive frames for smoke")
    smoke_min_duration_seconds: Optional[float] = Field(None, ge=0.1, le=10.0, description="Minimum duration for smoke in seconds")
    ppe_verification_frames: Optional[int] = Field(None, ge=1, le=30, description="Consecutive frames for PPE")
    ppe_verification_duration_seconds: Optional[float] = Field(None, ge=0.1, le=10.0, description="Minimum duration for PPE in seconds")
    verification_cooldown_seconds: Optional[float] = Field(None, ge=1.0, le=300.0, description="Cooldown in seconds")

