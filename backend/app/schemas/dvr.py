"""
Pydantic V2 Request & Response Schemas for Physical DVR/NVR Management (/api/v1/dvrs).
Passwords and raw secret blobs are NEVER returned in response models or logs.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from app.models.dvr import DVRStatus, DVRManufacturer


class DVRCreate(BaseModel):
    name: str = Field(..., json_schema_extra={"example": "Main Entrance NVR 01"}, description="DVR / NVR device name")
    management_host: str = Field(..., json_schema_extra={"example": "192.168.1.100"}, description="IP address or hostname")
    management_port: int = Field(default=80, json_schema_extra={"example": 80}, description="HTTP/HTTPS management port")
    rtsp_port: int = Field(default=554, json_schema_extra={"example": 554}, description="RTSP video stream port")
    username: str = Field(..., json_schema_extra={"example": "admin"}, description="DVR authentication username")
    password: str = Field(..., json_schema_extra={"example": "SecretDVRPass123!"}, description="DVR password (encrypted before storage)")
    manufacturer: str = Field(default=DVRManufacturer.GENERIC_RTSP.value, json_schema_extra={"example": "HIKVISION"})
    channels_count: int = Field(default=16, ge=1, le=128, json_schema_extra={"example": 16}, description="Max physical channels")
    enabled: bool = Field(default=True)



class DVRUpdate(BaseModel):
    name: Optional[str] = None
    management_host: Optional[str] = None
    management_port: Optional[int] = None
    rtsp_port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    manufacturer: Optional[str] = None
    channels_count: Optional[int] = None
    enabled: Optional[bool] = None
    version_id: Optional[int] = Field(None, description="Optimistic concurrency control version tag")


class DVRResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    management_host: str
    management_port: int
    rtsp_port: int
    username: str
    masked_credential: str = Field(default="******", description="Sanitized credential mask")
    manufacturer: str
    channels_count: int
    enabled: bool
    status: str
    last_health_check_at: Optional[datetime] = None
    last_successful_health_check_at: Optional[datetime] = None
    health_check_error: Optional[str] = None
    version_id: int
    created_at: datetime
    updated_at: datetime


class DVRHealthResponse(BaseModel):
    dvr_id: int
    name: str
    status: str
    network_reachable: bool
    management_port_reachable: bool
    rtsp_port_reachable: bool
    authenticated_check: bool
    latency_ms: float
    error_details: Optional[str] = None
