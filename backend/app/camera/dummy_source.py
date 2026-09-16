"""
Synthetic Dummy Camera Source Driver for Fast Testing & Development.
Generates synthetic color matrix frames in memory with 0ms I/O latency.
"""

import time
import numpy as np
from typing import Tuple, Optional
from datetime import datetime, timezone

from app.camera.base import CameraSource, CameraStatus, CameraRuntimeState


class SyntheticDummyCamera(CameraSource):
    """
    Synthetic camera driver producing in-memory BGR numpy arrays.
    Requires no RTSP network socket or video file on disk.
    """

    def __init__(
        self,
        camera_id: int = 0,
        rtsp_url: str = "dummy",
        fps_limit: int = 25,
        timeout_seconds: int = 10
    ):
        super().__init__(
            camera_id=camera_id,
            rtsp_url=rtsp_url,
            fps_limit=fps_limit,
            timeout_seconds=timeout_seconds
        )
        self._connected = False
        self._frame_count = 0

    def connect(self) -> bool:
        self._connected = True
        self.state.connection_status = CameraStatus.CONNECTED
        self.state.reconnect_attempts = 0
        self.state.resolution = (640, 480)
        return True

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        if not self._connected:
            return False, None

        import cv2
        self._frame_count += 1

        # High-definition industrial facility surveillance frame (480x640)
        img = np.full((480, 640, 3), (22, 18, 16), dtype=np.uint8)

        # Perspective warehouse floor & grid lines
        for x in range(0, 640, 80):
            cv2.line(img, (x, 200), (int(x * 1.3 - 96), 480), (38, 32, 28), 1)
        for y in range(200, 480, 40):
            cv2.line(img, (0, y), (640, y), (38, 32, 28), 1)

        # Ceiling rafters & architectural lines
        cv2.line(img, (0, 100), (640, 100), (45, 40, 35), 1)
        cv2.line(img, (120, 0), (120, 100), (45, 40, 35), 1)
        cv2.line(img, (520, 0), (520, 100), (45, 40, 35), 1)

        # Animated vertical scan line sweep
        scan_y = int((self._frame_count * 3) % 480)
        cv2.line(img, (0, scan_y), (640, scan_y), (60, 50, 40), 1)

        # Center viewfinder crosshair
        cx, cy = 320, 240
        cv2.line(img, (cx - 15, cy), (cx + 15, cy), (0, 180, 220), 1)
        cv2.line(img, (cx, cy - 15), (cx, cy + 15), (0, 180, 220), 1)
        cv2.circle(img, (cx, cy), 8, (0, 180, 220), 1)

        # CCTV Viewfinder Corner Brackets
        c_len, c_pad = 20, 20
        # Top-Left
        cv2.line(img, (c_pad, c_pad), (c_pad + c_len, c_pad), (80, 80, 80), 1)
        cv2.line(img, (c_pad, c_pad), (c_pad, c_pad + c_len), (80, 80, 80), 1)
        # Top-Right
        cv2.line(img, (640 - c_pad, c_pad), (640 - c_pad - c_len, c_pad), (80, 80, 80), 1)
        cv2.line(img, (640 - c_pad, c_pad), (640 - c_pad, c_pad + c_len), (80, 80, 80), 1)
        # Bottom-Left
        cv2.line(img, (c_pad, 480 - c_pad), (c_pad + c_len, 480 - c_pad), (80, 80, 80), 1)
        cv2.line(img, (c_pad, 480 - c_pad), (c_pad, 480 - c_pad - c_len), (80, 80, 80), 1)
        # Bottom-Right
        cv2.line(img, (640 - c_pad, 480 - c_pad), (640 - c_pad - c_len, 480 - c_pad), (80, 80, 80), 1)
        cv2.line(img, (640 - c_pad, 480 - c_pad), (640 - c_pad, 480 - c_pad - c_len), (80, 80, 80), 1)

        # Smooth moving simulated target / personnel in warehouse
        target_x = int(220 + 180 * np.sin(self._frame_count * 0.04))
        target_y = 230
        cv2.rectangle(img, (target_x - 22, target_y - 45), (target_x + 22, target_y + 45), (0, 200, 120), 1)
        cv2.circle(img, (target_x, target_y - 32), 10, (220, 180, 0), -1) # hardhat
        cv2.rectangle(img, (target_x - 12, target_y - 20), (target_x + 12, target_y + 15), (0, 215, 255), -1) # vest
        cv2.putText(img, "WORKER 01", (target_x - 26, target_y - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 220, 120), 1)

        # Live HUD Top Bar
        now_dt = datetime.now(timezone.utc)
        ts_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
        ms_str = f"{int(now_dt.microsecond / 10000):02d}"

        cv2.rectangle(img, (14, 14), (430, 46), (12, 12, 12), -1)
        cv2.rectangle(img, (14, 14), (430, 46), (0, 200, 230), 1)

        # Blinking REC dot
        is_blink_on = (self._frame_count // 12) % 2 == 0
        dot_color = (30, 30, 240) if is_blink_on else (60, 60, 120)
        cv2.circle(img, (28, 30), 5, dot_color, -1)

        hud_text = f"REC  CAM-{self.camera_id:02d} LIVE | {ts_str}.{ms_str} UTC"
        cv2.putText(img, hud_text, (40, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (255, 255, 255), 1, cv2.LINE_AA)

        # Bottom stats
        cv2.putText(img, f"640x480 @ {self.fps_limit}FPS | AI CCTV SOC GATEWAY", (20, 465), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (140, 140, 140), 1, cv2.LINE_AA)

        return True, img

    def disconnect(self) -> None:
        self._connected = False
        self.state.connection_status = CameraStatus.DISCONNECTED

    def is_connected(self) -> bool:
        return self._connected
