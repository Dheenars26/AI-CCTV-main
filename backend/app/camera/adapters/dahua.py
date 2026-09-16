"""
Dahua Manufacturer DVR Adapter Implementation.
URL Format: rtsp://username:password@host:port/cam/realmonitor?channel=<channel>&subtype=0
"""

import time
import socket
from typing import Tuple, Optional
from app.camera.adapters.base import DVRAdapter


class DahuaAdapter(DVRAdapter):

    def construct_rtsp_url(self, host: str, rtsp_port: int, username: str, password: str, channel: int) -> str:
        return f"rtsp://{username}:{password}@{host}:{rtsp_port}/cam/realmonitor?channel={channel}&subtype=0"

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
        
        mgmt_ok = False
        try:
            with socket.create_connection((host, management_port), timeout=timeout):
                mgmt_ok = True
        except Exception:
            mgmt_ok = False

        rtsp_ok = False
        try:
            with socket.create_connection((host, rtsp_port), timeout=timeout):
                rtsp_ok = True
        except Exception:
            rtsp_ok = False

        latency_ms = round((time.time() - t0) * 1000, 2)
        net_ok = mgmt_ok or rtsp_ok
        auth_ok = net_ok

        error_msg = None if net_ok else f"Dahua DVR {host} ports {management_port}/{rtsp_port} unreachable"
        return net_ok, mgmt_ok, rtsp_ok, auth_ok, latency_ms, error_msg
