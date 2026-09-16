"""
Camera Source Abstract Base Class & Runtime State Models.
Provides pure abstraction separating frame acquisition from specific hardware/protocol drivers.
"""

from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Tuple
import numpy as np
from app.utils.security import sanitize_rtsp_url


class CameraStatus(str, Enum):
    """
    Real-time camera connection status lifecycle.
    """
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"
    ERROR = "ERROR"


@dataclass
class CameraRuntimeState:
    """
    In-memory dynamic runtime state of a camera stream.
    Separated strictly from persistent database configuration.
    """
    camera_id: int
    connection_status: CameraStatus = CameraStatus.DISCONNECTED
    last_frame_timestamp: Optional[datetime] = None
    current_fps: float = 0.0
    resolution: Optional[Tuple[int, int]] = None  # (width, height)
    reconnect_attempts: int = 0
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "camera_id": self.camera_id,
            "connection_status": self.connection_status.value,
            "last_frame_timestamp": self.last_frame_timestamp.isoformat() if self.last_frame_timestamp else None,
            "current_fps": round(self.current_fps, 2),
            "resolution": f"{self.resolution[0]}x{self.resolution[1]}" if self.resolution else None,
            "reconnect_attempts": self.reconnect_attempts,
            "error_message": self.error_message
        }


class CameraSource(ABC):
    """
    Abstract Base Class for all video input sources.
    Isolates rest of system from underlying protocol (RTSP, File, Webcam).
    """

    def __init__(self, camera_id: int, rtsp_url: str, fps_limit: int = 25, timeout_seconds: int = 10):
        self.camera_id = camera_id
        self.raw_rtsp_url = rtsp_url
        self.sanitized_url = sanitize_rtsp_url(rtsp_url)
        self.fps_limit = fps_limit if fps_limit is not None else 25
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else 10
        self.state = CameraRuntimeState(camera_id=camera_id)

    @abstractmethod
    def connect(self) -> bool:
        """
        Establishes connection to video stream source.
        Returns True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """
        Disconnects and releases video capture resources.
        """
        pass

    @abstractmethod
    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Reads next raw frame from capture source.
        Returns (success: bool, frame: Optional[np.ndarray]).
        """
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """
        Verifies whether the source connection is healthy and active.
        """
        pass

    @property
    def requires_throttling(self) -> bool:
        """
        Whether the ingestion loop should apply artificial sleep throttling.
        True for non-clocked sources (synthetic matrices, local video files).
        False for hardware/network-clocked sources (live USB webcams, live RTSP sockets).
        """
        return True

    def get_state(self) -> CameraRuntimeState:
        """
        Returns current runtime state metrics.
        """
        return self.state
