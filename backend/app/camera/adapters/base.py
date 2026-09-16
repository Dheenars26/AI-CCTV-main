"""
Abstract Base Class for Manufacturer-Specific DVR/NVR Adapters (DVRAdapter).
Encapsulates RTSP streaming URL construction and layered health check logic.
"""

from abc import ABC, abstractmethod
from typing import Tuple, Optional


class DVRAdapter(ABC):
    """
    Abstract Interface for Manufacturer-Specific DVR Adapters.
    """

    @abstractmethod
    def construct_rtsp_url(self, host: str, rtsp_port: int, username: str, password: str, channel: int) -> str:
        """
        Constructs manufacturer-specific RTSP stream URL for specified channel.
        """
        pass

    @abstractmethod
    def perform_layered_health_check(
        self,
        host: str,
        management_port: int,
        rtsp_port: int,
        username: str,
        password: str,
        timeout: float = 3.0
    ) -> Tuple[bool, bool, bool, bool, float, Optional[str]]:
        """
        Executes 3-layer health check:
        1. Network Host Reachable
        2. Management Port Reachable
        3. RTSP Port Reachable
        4. Device Authenticated Check
        Returns (net_ok, mgmt_ok, rtsp_ok, auth_ok, latency_ms, error_msg)
        """
        pass
