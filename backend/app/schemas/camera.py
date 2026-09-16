"""
Camera Request/Response Pydantic Schemas.
Includes SourceType enum, CRUD request payload validation, and automatic RTSP credential masking.
"""

from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from app.utils.security import sanitize_rtsp_url


class SourceType(str, Enum):
    """
    Supported video source types.
    """
    RTSP = "rtsp"
    FILE = "file"
    WEBCAM = "webcam"
    DUMMY = "dummy"


class CameraBase(BaseModel):
    name: str = Field(..., json_schema_extra={"example": "Warehouse Door 01"}, description="Human-readable camera name")
    camera_number: str = Field(default="CAM-01", json_schema_extra={"example": "CAM-01"}, description="Camera designation number")
    dvr_id: Optional[int] = Field(default=None, description="Optional physical DVR/NVR association")
    dvr_channel: Optional[int] = Field(default=None, description="Physical DVR channel number (1 to 64)")
    channel_name: Optional[str] = Field(default=None)
    dvr_address: Optional[str] = Field(default=None, json_schema_extra={"example": "192.168.1.100"}, description="DVR/NVR IP or hostname")
    rtsp_url: str = Field(
        ...,
        json_schema_extra={"example": "rtsp://admin:password123@192.168.1.100:554/live/ch0"},
        description="RTSP stream URL or local file path"
    )
    source_type: SourceType = Field(default=SourceType.RTSP, description="Video source type (rtsp, file, webcam)")
    location: Optional[str] = Field(default=None, json_schema_extra={"example": "Zone A Entrance"})
    latitude: Optional[float] = Field(default=13.0827, description="GPS Latitude coordinate")
    longitude: Optional[float] = Field(default=80.2707, description="GPS Longitude coordinate")
    enabled: bool = Field(default=False, description="Whether camera ingestion worker should be active (defaults to OFF until turned ON)")
    # AI Module Toggles & Per-Camera Settings
    fire_smoke_enabled: bool = Field(default=True, description="Enable Fire & Smoke AI Detection")
    ppe_enabled: bool = Field(default=True, description="Enable PPE Safety Equipment Detection")
    person_enabled: bool = Field(default=True, description="Enable Person Tracking Engine")
    zone_enabled: bool = Field(default=True, description="Enable Safety Zone Polygon Evaluation")
    ppe_inference_interval_sec: float = Field(default=0.05, ge=0.01, le=10.0, description="PPE inference interval in seconds")

    priority: str = Field(default="HIGH", description="Priority level (HIGH, MEDIUM, LOW)")
    capture_fps: int = Field(default=25, ge=1, le=120)
    target_ai_fps: int = Field(default=15, ge=1, le=60)
    frame_skip: int = Field(default=1, ge=1, le=20)
    gpu_device_id: int = Field(default=0, description="Target GPU device ID (0, 1, -1 for CPU)")
    fps_limit: int = Field(default=25, ge=1, le=120, description="Target frame rate limit")
    connection_timeout: int = Field(default=10, ge=1, le=60, description="Stream connection timeout in seconds")
    reconnect_interval: int = Field(default=5, ge=1, le=60, description="Reconnection backoff interval in seconds")


class CameraCreate(CameraBase):
    pass


class CameraUpdate(BaseModel):
    name: Optional[str] = Field(default=None)
    camera_number: Optional[str] = Field(default=None)
    dvr_id: Optional[int] = Field(default=None)
    dvr_channel: Optional[int] = Field(default=None)
    dvr_address: Optional[str] = Field(default=None)
    rtsp_url: Optional[str] = Field(default=None)
    source_type: Optional[SourceType] = Field(default=None)
    location: Optional[str] = Field(default=None)
    latitude: Optional[float] = Field(default=None)
    longitude: Optional[float] = Field(default=None)
    enabled: Optional[bool] = Field(default=None)
    fire_smoke_enabled: Optional[bool] = Field(default=None)
    ppe_enabled: Optional[bool] = Field(default=None)
    person_enabled: Optional[bool] = Field(default=None)
    zone_enabled: Optional[bool] = Field(default=None)
    ppe_inference_interval_sec: Optional[float] = Field(default=None)
    priority: Optional[str] = Field(default=None)
    capture_fps: Optional[int] = Field(default=None, ge=1, le=120)
    target_ai_fps: Optional[int] = Field(default=None, ge=1, le=60)
    gpu_device_id: Optional[int] = Field(default=None)
    fps_limit: Optional[int] = Field(default=None, ge=1, le=120)
    connection_timeout: Optional[int] = Field(default=None, ge=1, le=60)
    reconnect_interval: Optional[int] = Field(default=None, ge=1, le=60)


class CameraResponse(BaseModel):
    id: int = Field(...)
    name: str = Field(...)
    camera_number: str = Field(...)
    dvr_id: Optional[int] = Field(default=None)
    dvr_channel: Optional[int] = Field(default=None)
    dvr_address: Optional[str] = Field(default=None)
    sanitized_rtsp_url: str = Field(...)
    source_type: SourceType = Field(...)
    location: Optional[str] = Field(default=None)
    latitude: Optional[float] = Field(default=13.0827)
    longitude: Optional[float] = Field(default=80.2707)
    enabled: bool = Field(...)
    fire_smoke_enabled: bool = Field(default=True)
    ppe_enabled: bool = Field(default=True)
    person_enabled: bool = Field(default=True)
    zone_enabled: bool = Field(default=True)
    ppe_inference_interval_sec: float = Field(default=0.5)
    priority: str = Field(default="HIGH")
    capture_fps: int = Field(default=25)
    target_ai_fps: int = Field(default=5)
    gpu_device_id: int = Field(default=0)
    fps_limit: int = Field(...)
    connection_timeout: int = Field(...)
    reconnect_interval: int = Field(...)
    created_at: datetime = Field(...)
    updated_at: datetime = Field(...)

    @field_validator("sanitized_rtsp_url", mode="before")
    @classmethod
    def mask_credentials(cls, v: str) -> str:
        """
        Enforces RTSP credential masking so passwords are NEVER exposed in API outputs.
        """
        return sanitize_rtsp_url(v) or v


class CameraRuntimeStateResponse(BaseModel):
    camera_id: int = Field(...)
    connection_status: str = Field(..., json_schema_extra={"example": "CONNECTED"}, description="CONNECTED, CONNECTING, DISCONNECTED, RECONNECTING, ERROR")
    last_frame_timestamp: Optional[str] = Field(default=None, json_schema_extra={"example": "2026-08-17T16:00:00Z"})
    current_fps: float = Field(default=0.0, json_schema_extra={"example": 24.5})
    resolution: Optional[str] = Field(default=None, json_schema_extra={"example": "1920x1080"})
    reconnect_attempts: int = Field(default=0)
    error_message: Optional[str] = Field(default=None)

