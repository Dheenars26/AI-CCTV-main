"""
Generic RTSP DVR Adapter Implementation.
Standard RTSP endpoint syntax: rtsp://username:password@host:port/live/ch<channel>
"""

import time
import socket
from typing import Tuple, Optional
from app.camera.adapters.base import DVRAdapter


class GenericRTSPAdapter(DVRAdapter):

    def construct_rtsp_url(self, host: str, rtsp_port: int, username: str, password: str, channel: int) -> str:
        ch = max(1, channel)
        return f"rtsp://{username}:{password}@{host}:{rtsp_port}/live/ch{ch}"

    def perform_layered_health_check(
        self,
        host: str,
        management_port: int,
        rtsp_port: int,
        username: str,
        password: str,
        timeout: float = 3.0
    ) -> Tuple[bool, bool, bool, bool, float, Optional[str]]:
        from app.config.settings import settings
        if settings.APP_ENV == "testing":
            timeout = 0.05

        t0 = time.time()
        
        # Layer 1: Network Host & Mgmt Port TCP check
        mgmt_ok = False
        try:
            with socket.create_connection((host, management_port), timeout=timeout):
                mgmt_ok = True
        except Exception:
            mgmt_ok = False

        # Layer 2: RTSP Port TCP check
        rtsp_ok = False
        try:
            with socket.create_connection((host, rtsp_port), timeout=timeout):
                rtsp_ok = True
        except Exception:
            rtsp_ok = False

        latency_ms = round((time.time() - t0) * 1000, 2)
        net_ok = mgmt_ok or rtsp_ok
        auth_ok = net_ok  # Generic RTSP assumes auth ok if ports open

        error_msg = None
        if not net_ok:
            error_msg = f"Host {host} unreachable on ports {management_port}/{rtsp_port}"

        return net_ok, mgmt_ok, rtsp_ok, auth_ok, latency_ms, error_msg
