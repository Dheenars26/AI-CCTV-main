"""
Browser Streaming Abstraction Service (StreamService).
Provides stream token authorization, hides raw DVR/NVR credentials, and orchestrates browser-compatible streaming endpoints (MJPEG, HLS, WebRTC).
"""

import time
import base64
import hmac
import hashlib
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

from app.config.settings import settings
from app.models.camera import Camera
from app.schemas.stream import StreamConfigResponse
from app.camera.manager import CameraManager
from app.utils.logger import logger


class StreamService:
    """
    Service managing streaming security, authorization tokens, and browser protocol abstraction.
    """

    def __init__(self, camera_manager: Optional[CameraManager] = None):
        self.camera_manager = camera_manager

    def generate_stream_token(self, camera_id: int, user_id: Optional[str] = None, expires_hours: int = 24) -> str:
        """
        Generates a secure HMAC-SHA256 stream session token (st_...).
        Allows authorized frontends to stream video without receiving DVR usernames or passwords.
        """
        exp_ts = int((datetime.now(timezone.utc) + timedelta(hours=expires_hours)).timestamp())
        payload = {
            "camera_id": camera_id,
            "user_id": user_id or "anonymous",
            "exp": exp_ts
        }
        payload_bytes = json.dumps(payload).encode("utf-8")
        payload_b64 = base64.urlsafe_b64encode(payload_bytes).rstrip(b"=").decode("utf-8")
        
        sig = hmac.new(settings.SECRET_KEY.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
        return f"st_{payload_b64}.{sig}"

    def validate_stream_token(self, token: str, expected_camera_id: int) -> bool:
        """
        Validates stream authorization token.
        """
        if not token or not token.startswith("st_"):
            return False

        try:
            raw_token = token[3:]
            parts = raw_token.split(".")
            if len(parts) != 2:
                return False

            payload_b64, sig = parts
            expected_sig = hmac.new(settings.SECRET_KEY.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
            if not hmac.compare_digest(sig, expected_sig):
                return False

            padding = "=" * (4 - len(payload_b64) % 4)
            payload_bytes = base64.urlsafe_b64decode(payload_b64 + padding)
            payload = json.loads(payload_bytes.decode("utf-8"))

            if payload.get("camera_id") != expected_camera_id:
                return False

            if int(time.time()) > payload.get("exp", 0):
                return False

            return True
        except Exception as e:
            logger.warning(f"StreamService: Invalid stream token format: {str(e)}")
            return False

    def get_stream_config(self, camera: Camera, user_id: Optional[str] = None) -> StreamConfigResponse:
        """
        Generates authorized StreamConfigResponse for frontend client.
        Hides raw RTSP credentials completely.
        """
        token = self.generate_stream_token(camera_id=camera.id, user_id=user_id)
        
        is_active = False
        if self.camera_manager and camera.id in self.camera_manager._threads:
            is_active = self.camera_manager._threads[camera.id].is_alive()

        mjpeg_url = f"/api/v1/cameras/{camera.id}/stream?stream_token={token}"
        hls_url = f"/api/v1/cameras/{camera.id}/stream/hls/index.m3u8?stream_token={token}"
        webrtc_url = f"/api/v1/cameras/{camera.id}/stream/webrtc?stream_token={token}"

        return StreamConfigResponse(
            camera_id=camera.id,
            camera_name=camera.name,
            stream_token=token,
            mjpeg_url=mjpeg_url,
            hls_url=hls_url,
            webrtc_url=webrtc_url,
            supported_protocols=["mjpeg", "hls", "webrtc"],
            resolution="640x480",
            fps_limit=camera.fps_limit,
            is_active=is_active,
            created_at=datetime.now(timezone.utc)
        )

    def generate_hls_playlist(self, camera_id: int, stream_token: str, segment_count: int = 3) -> str:
        """
        Generates an HTTP Live Streaming (HLS) M3U8 Master Playlist.
        """
        now = int(time.time())
        target_duration = 2
        lines = [
            "#EXTM3U",
            "#EXT-X-VERSION:3",
            f"#EXT-X-TARGETDURATION:{target_duration}",
            f"#EXT-X-MEDIA-SEQUENCE:{now - segment_count}",
        ]

        for i in range(segment_count):
            seg_idx = now - segment_count + i
            lines.append(f"#EXTINF:{target_duration}.0,")
            lines.append(f"/api/v1/cameras/{camera_id}/stream/hls/segment_{seg_idx}.ts?stream_token={stream_token}")

        return "\n".join(lines) + "\n"
