"""
Pydantic Schemas for Browser-Compatible Video Streaming Architecture (/api/v1/cameras/{id}/stream/config).
Defines frontend-independent stream contracts hiding raw RTSP credentials.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class StreamConfigResponse(BaseModel):
    """
    Authorized Stream Configuration Envelope returned to frontend clients.
    Exposes browser-compatible streaming endpoints (MJPEG, HLS, WebRTC) without leaking DVR credentials.
    """
    camera_id: int = Field(..., description="Target Camera ID")
    camera_name: str = Field(..., description="Human-readable camera name")
    stream_token: str = Field(..., description="Secure session token for stream authorization")
    mjpeg_url: str = Field(..., description="Browser-compatible HTTP MJPEG stream URL (HTML <img>)")
    hls_url: str = Field(..., description="HTTP Live Streaming M3U8 playlist URL (HTML5 <video>)")
    webrtc_url: Optional[str] = Field(default=None, description="WebRTC SDP Offer/Answer signaling endpoint")
    supported_protocols: List[str] = Field(
        default_factory=lambda: ["mjpeg", "hls", "webrtc"],
        description="Protocols supported by streaming backend"
    )
    resolution: Optional[str] = Field(default="640x480", description="Stream resolution")
    fps_limit: int = Field(default=25, description="Target frame rate")
    is_active: bool = Field(..., description="Whether stream ingestion worker is currently running")
    created_at: datetime = Field(..., description="Token issuance timestamp")


class StreamSessionTokenPayload(BaseModel):
    camera_id: int
    user_id: Optional[str] = None
    exp: int
