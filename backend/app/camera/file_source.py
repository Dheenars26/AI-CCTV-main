"""
Video File Camera Source Driver (Test Mode).
Consumes local MP4/AVI/MKV video files with auto-looping for hardware-independent development and testing.
If the specified video file path does not exist, generates synthetic test frames.
"""

import os
import time
from typing import Optional, Tuple
import cv2
import numpy as np
from app.camera.base import CameraSource, CameraStatus
from app.utils.logger import logger


class VideoFileCamera(CameraSource):
    """
    Video File Camera Source implementation for offline testing.
    Reads local video files and loops continuously upon EOF.
    """

    def __init__(
        self,
        camera_id: int,
        rtsp_url: str,
        fps_limit: int = 25,
        timeout_seconds: int = 10,
        loop: bool = True
    ):
        super().__init__(camera_id=camera_id, rtsp_url=rtsp_url, fps_limit=fps_limit, timeout_seconds=timeout_seconds)
        self.loop = loop
        self.cap: Optional[cv2.VideoCapture] = None
        self._synthetic_mode: bool = False
        self._synthetic_frame_index: int = 0

    def connect(self) -> bool:
        """
        Opens local video file or initializes synthetic test frame generator if file absent.
        """
        file_path = self.raw_rtsp_url
        logger.info(f"Connecting Camera {self.camera_id} to file source: {file_path}")
        self.state.connection_status = CameraStatus.CONNECTING

        if not os.path.exists(file_path):
            logger.warning(f"Video file '{file_path}' not found. Initializing Synthetic Test Generator mode for Camera {self.camera_id}.")
            self._synthetic_mode = True
            self.state.resolution = (1280, 720)
            self.state.current_fps = float(self.fps_limit)
            self.state.connection_status = CameraStatus.CONNECTED
            self.state.error_message = None
            return True

        try:
            self._synthetic_mode = False
            self.cap = cv2.VideoCapture(file_path)

            if not self.cap.isOpened():
                error_msg = f"Failed to open video file source at {file_path}"
                logger.error(f"Camera {self.camera_id}: {error_msg}")
                self.state.connection_status = CameraStatus.ERROR
                self.state.error_message = error_msg
                return False

            width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            stream_fps = self.cap.get(cv2.CAP_PROP_FPS)

            self.state.resolution = (width, height) if width > 0 and height > 0 else (1280, 720)
            self.state.current_fps = stream_fps if stream_fps > 0 else float(self.fps_limit)
            self.state.connection_status = CameraStatus.CONNECTED
            self.state.error_message = None
            self.state.reconnect_attempts = 0

            logger.info(f"Camera {self.camera_id} connected to video file '{file_path}'. Resolution: {self.state.resolution} @ {self.state.current_fps} FPS")
            return True

        except Exception as e:
            error_msg = f"Exception opening video file: {str(e)}"
            logger.error(f"Camera {self.camera_id}: {error_msg}")
            self.state.connection_status = CameraStatus.ERROR
            self.state.error_message = error_msg
            return False

    def disconnect(self) -> None:
        """
        Releases video capture resources.
        """
        self._synthetic_mode = False
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            finally:
                self.cap = None

        self.state.connection_status = CameraStatus.DISCONNECTED

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Reads next frame. Rewinds file to start upon EOF if loop=True.
        Generates synthetic frame if in synthetic mode.
        """
        if self._synthetic_mode:
            # Generate synthetic test pattern image (BGR)
            self._synthetic_frame_index += 1
            width, height = self.state.resolution or (1280, 720)
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            
            # Draw gradient background and test text
            color = (0, int((self._synthetic_frame_index * 5) % 255), 200)
            cv2.rectangle(frame, (50, 50), (width - 50, height - 50), color, 3)
            timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S")
            cv2.putText(
                frame,
                f"CAM-{self.camera_id} [SYNTHETIC TEST STREAM] {timestamp_str}",
                (80, 100),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                2
            )
            return True, frame

        if self.cap is None or not self.cap.isOpened():
            self.state.connection_status = CameraStatus.DISCONNECTED
            return False, None

        ret, frame = self.cap.read()
        if not ret or frame is None:
            if self.loop:
                # Rewind to frame 0
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    return True, frame
            logger.warning(f"Camera {self.camera_id}: Reached end of video file.")
            return False, None

        return True, frame

    def is_connected(self) -> bool:
        if self.state.connection_status != CameraStatus.CONNECTED:
            return False
        return self._synthetic_mode or (self.cap is not None and self.cap.isOpened())
