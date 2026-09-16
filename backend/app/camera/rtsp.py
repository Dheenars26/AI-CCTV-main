"""
RTSP Camera Source Driver.
Uses OpenCV VideoCapture to consume RTSP streams from CCTV cameras and NVR/DVR units.
"""

import time
import threading
from typing import Optional, Tuple
import cv2
import numpy as np
from app.camera.base import CameraSource, CameraStatus
from app.utils.logger import logger


class RTSPCamera(CameraSource):
    """
    OpenCV RTSP Stream Camera Source implementation.
    Consumes live NVR/DVR streams over RTSP protocol.
    """

    def __init__(self, camera_id: int, rtsp_url: str, fps_limit: int = 25, timeout_seconds: int = 10):
        super().__init__(camera_id=camera_id, rtsp_url=rtsp_url, fps_limit=fps_limit, timeout_seconds=timeout_seconds)
        self.cap: Optional[cv2.VideoCapture] = None
        self._fallback_dummy = None
        self._reader_thread: Optional[threading.Thread] = None
        self._reader_stop_event = threading.Event()
        self._new_frame_event = threading.Event()
        self._frame_lock = threading.Lock()
        self._latest_raw_frame: Optional[np.ndarray] = None
        self._last_frame_read_time: float = 0.0

    def _reader_loop(self) -> None:
        """
        Continuous RTSP low-latency socket reader loop.
        Continuously drains OpenCV FFMPEG network buffers and stores latest real-time frame.
        """
        while not self._reader_stop_event.is_set():
            if self.cap is None or not self.cap.isOpened():
                break
            try:
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    with self._frame_lock:
                        self._latest_raw_frame = frame
                        self._last_frame_read_time = time.time()
                    self._new_frame_event.set()
                else:
                    self._reader_stop_event.wait(timeout=0.01)
            except Exception:
                self._reader_stop_event.wait(timeout=0.02)

    def _start_reader_thread(self) -> None:
        self._reader_stop_event.clear()
        self._new_frame_event.clear()
        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            name=f"RTSPReader-{self.camera_id}",
            daemon=True
        )
        self._reader_thread.start()

    def _stop_reader_thread(self) -> None:
        self._reader_stop_event.set()
        self._new_frame_event.set()
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=1.0)
        self._reader_thread = None
        with self._frame_lock:
            self._latest_raw_frame = None

    @staticmethod
    def _normalize_url(url: str) -> str:
        url = url.strip()
        if not url.startswith("rtsp://") and not url.startswith("rtsps://"):
            return url
        prefix, rest = url.split("://", 1)
        if "@" in rest:
            last_at = rest.rfind("@")
            auth_part = rest[:last_at]
            host_part = rest[last_at + 1:]
            if ":" in auth_part:
                user, pwd = auth_part.split(":", 1)
                if "@" in pwd:
                    pwd = pwd.replace("@", "%40")
                auth_part = f"{user}:{pwd}"
            return f"{prefix}://{auth_part}@{host_part}"
        return url

    def connect(self) -> bool:
        """
        Connects OpenCV VideoCapture to the RTSP stream URL.
        Engages synthetic stream driver fallback if RTSP network socket is offline.
        """
        logger.info(f"Connecting Camera {self.camera_id} to RTSP stream: {self.sanitized_url}")
        self.state.connection_status = CameraStatus.CONNECTING

        if self.raw_rtsp_url.strip().lower() in ("dummy", "synthetic", ""):
            logger.info(f"Camera {self.camera_id}: Using synthetic dummy camera feed.")
            from app.camera.dummy_source import SyntheticDummyCamera
            self._fallback_dummy = SyntheticDummyCamera(camera_id=self.camera_id, fps_limit=self.fps_limit)
            self._fallback_dummy.connect()
            self.state.connection_status = CameraStatus.CONNECTED
            self.state.resolution = (640, 480)
            return True

        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

        try:
            # Set OpenCV RTSP transport protocol flags if supported
            import os
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|fflags;nobuffer|flags;low_delay"
            url_to_open = self._normalize_url(self.raw_rtsp_url)
            self.cap = cv2.VideoCapture(url_to_open, cv2.CAP_FFMPEG)

            # Configure OpenCV timeouts & low latency 1-frame buffer
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            if self.cap.isOpened():
                # Allow a retry window for H.264/H.265 keyframe arrival (up to 4.0s)
                test_frame = None
                deadline = time.time() + 4.0
                while time.time() < deadline:
                    ret, frame = self.cap.read()
                    if ret and frame is not None:
                        test_frame = frame
                        break
                    time.sleep(0.08)

                if test_frame is not None:
                    width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    stream_fps = self.cap.get(cv2.CAP_PROP_FPS)

                    self.state.resolution = (width, height) if width > 0 and height > 0 else (1920, 1080)
                    self.state.current_fps = stream_fps if stream_fps > 0 else self.fps_limit
                    self.state.connection_status = CameraStatus.CONNECTED
                    self.state.error_message = None
                    self.state.reconnect_attempts = 0
                    self._fallback_dummy = None

                    # Start dedicated low-latency reader thread to drain network socket buffers
                    self._start_reader_thread()

                    logger.info(
                        f"Camera {self.camera_id} connected successfully to RTSP stream. "
                        f"Resolution: {self.state.resolution[0]}x{self.state.resolution[1]} @ {self.state.current_fps} FPS (zero-lag reader active)"
                    )
                    return True

            # Release VideoCapture handle immediately if initialization failed
            if self.cap is not None:
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None

            error_msg = f"RTSP stream offline or unreachable ({self.sanitized_url})"
            logger.error(f"Camera {self.camera_id}: {error_msg}")
            self.state.connection_status = CameraStatus.ERROR
            self.state.error_message = error_msg
            return False

        except Exception as e:
            if self.cap is not None:
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None
            error_msg = f"RTSP stream exception: {str(e)}"
            logger.error(f"Camera {self.camera_id}: {error_msg}")
            self.state.connection_status = CameraStatus.ERROR
            self.state.error_message = error_msg
            return False

    def disconnect(self) -> None:
        """
        Releases OpenCV VideoCapture stream and resources cleanly.
        """
        self._stop_reader_thread()
        if self._fallback_dummy:
            try:
                self._fallback_dummy.disconnect()
            except Exception:
                pass
            self._fallback_dummy = None

        if self.cap is not None:
            logger.info(f"Releasing RTSP VideoCapture for Camera {self.camera_id}")
            try:
                self.cap.release()
            except Exception as e:
                logger.warning(f"Error releasing VideoCapture for Camera {self.camera_id}: {str(e)}")
            finally:
                self.cap = None

        self.state.connection_status = CameraStatus.DISCONNECTED

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Reads next decoded video frame from RTSP VideoCapture or fallback stream.
        """
        if self._fallback_dummy:
            return self._fallback_dummy.read_frame()

        if self.cap is None or not self.cap.isOpened():
            from app.camera.dummy_source import SyntheticDummyCamera
            self._fallback_dummy = SyntheticDummyCamera(camera_id=self.camera_id, fps_limit=self.fps_limit)
            self._fallback_dummy.connect()
            return self._fallback_dummy.read_frame()

        # Return latest fresh frame directly from zero-lag reader thread
        if self._reader_thread and self._reader_thread.is_alive():
            # Wait for next fresh frame arriving from RTSP network socket
            signaled = self._new_frame_event.wait(timeout=0.5)
            with self._frame_lock:
                if self._latest_raw_frame is not None:
                    self._new_frame_event.clear()
                    return True, self._latest_raw_frame
            now_sec = time.time()
            if self._last_frame_read_time > 0 and (now_sec - self._last_frame_read_time > self.timeout_seconds):
                logger.warning(f"Camera {self.camera_id}: RTSP frame arrival timed out ({self.timeout_seconds}s)")
                return False, None
            # Return current buffer or wait
            return False, None

        try:
            ret, frame = self.cap.read()
            if not ret or frame is None:
                from app.camera.dummy_source import SyntheticDummyCamera
                self._fallback_dummy = SyntheticDummyCamera(camera_id=self.camera_id, fps_limit=self.fps_limit)
                self._fallback_dummy.connect()
                return self._fallback_dummy.read_frame()
            return True, frame
        except Exception as e:
            logger.error(f"Camera {self.camera_id} frame read exception: {str(e)}")
            from app.camera.dummy_source import SyntheticDummyCamera
            self._fallback_dummy = SyntheticDummyCamera(camera_id=self.camera_id, fps_limit=self.fps_limit)
            self._fallback_dummy.connect()
            return self._fallback_dummy.read_frame()

    def is_connected(self) -> bool:
        """
        Verifies if stream is open and connected.
        """
        if self._fallback_dummy is not None:
            return self._fallback_dummy.is_connected()
        return self.cap is not None and self.cap.isOpened() and self.state.connection_status == CameraStatus.CONNECTED

    @property
    def requires_throttling(self) -> bool:
        # RTSP network socket already paces frame arrival; throttle only when in synthetic dummy fallback
        return self._fallback_dummy is not None
