"""
Webcam Camera Source Driver (Test Mode).
Consumes local USB webcam streams via device index (e.g., 0, 1) for hardware testing.
"""

import time
import threading
from typing import Optional, Tuple
import cv2
import numpy as np
from app.camera.base import CameraSource, CameraStatus
from app.utils.logger import logger


class WebcamCamera(CameraSource):
    """
    Local USB Webcam Camera Source implementation.
    """

    def __init__(self, camera_id: int, rtsp_url: str, fps_limit: int = 25, timeout_seconds: int = 10):
        super().__init__(camera_id=camera_id, rtsp_url=rtsp_url, fps_limit=fps_limit, timeout_seconds=timeout_seconds)
        # Parse device index from rtsp_url string (e.g. "0", "1", "webcam:0", "webcam:1", "/dev/video0")
        try:
            raw = self.raw_rtsp_url.strip()
            if ":" in raw:
                self.device_index = int(raw.split(":")[-1])
            else:
                self.device_index = int(raw)
        except (ValueError, TypeError):
            self.device_index = 0
        self.cap: Optional[cv2.VideoCapture] = None
        self._fallback_dummy: Optional[CameraSource] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._reader_stop_event = threading.Event()
        self._new_frame_event = threading.Event()
        self._frame_lock = threading.Lock()
        self._latest_raw_frame: Optional[np.ndarray] = None
        self._last_frame_read_time: float = 0.0

    def _reader_loop(self) -> None:
        """
        Continuous low-level camera reader loop.
        Drains OS driver queues continuously and keeps self._latest_raw_frame at 0ms latency.
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
            name=f"WebcamReader-{self.camera_id}",
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

    def connect(self) -> bool:
        logger.info(f"Connecting Camera {self.camera_id} to Webcam index: {self.device_index}")
        self.state.connection_status = CameraStatus.CONNECTING

        try:
            import os
            import sys
            from app.config.settings import settings

            if sys.platform == "win32":
                self.cap = cv2.VideoCapture(self.device_index, cv2.CAP_DSHOW)
                if not self.cap.isOpened():
                    self.cap = cv2.VideoCapture(self.device_index)
            else:
                self.cap = cv2.VideoCapture(self.device_index)

            if not self.cap.isOpened():
                is_cloud_or_headless = bool(
                    os.environ.get("RENDER")
                    or os.environ.get("CI")
                    or os.environ.get("HEADLESS")
                    or os.environ.get("DOCKER_CONTAINER")
                    or (settings.APP_ENV == "production" and not sys.platform.startswith("win"))
                )
                if is_cloud_or_headless:
                    logger.warning(
                        f"Camera {self.camera_id}: Webcam device {self.device_index} not accessible on server host "
                        f"(cloud/headless container). Engaging synthetic live CCTV stream fallback."
                    )
                    from app.camera.dummy_source import SyntheticDummyCamera
                    self._fallback_dummy = SyntheticDummyCamera(
                        camera_id=self.camera_id,
                        fps_limit=self.fps_limit,
                        timeout_seconds=self.timeout_seconds
                    )
                    self._fallback_dummy.connect()
                    self.state.resolution = (640, 480)
                    self.state.current_fps = float(self.fps_limit)
                    self.state.connection_status = CameraStatus.CONNECTED
                    self.state.error_message = None
                    self.state.reconnect_attempts = 0
                    return True

                error_msg = f"Failed to open webcam at index {self.device_index}"
                logger.error(f"Camera {self.camera_id}: {error_msg}")
                self.state.connection_status = CameraStatus.ERROR
                self.state.error_message = error_msg
                return False

            # Force single-frame buffer to eliminate camera lag & driver queuing
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_FPS, float(self.fps_limit))

            width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            stream_fps = self.cap.get(cv2.CAP_PROP_FPS)

            self.state.resolution = (width, height) if width > 0 and height > 0 else (640, 480)
            self.state.current_fps = stream_fps if stream_fps > 0 else float(self.fps_limit)
            self.state.connection_status = CameraStatus.CONNECTED
            self.state.error_message = None
            self.state.reconnect_attempts = 0
            self._fallback_dummy = None

            # Start zero-latency reader loop thread
            self._start_reader_thread()

            logger.info(f"Camera {self.camera_id} connected to webcam device index {self.device_index} (res: {self.state.resolution}, fps: {self.state.current_fps}, buffer: 1, zero-lag reader active).")
            return True

        except Exception as e:
            error_msg = f"Exception opening webcam: {str(e)}"
            logger.error(f"Camera {self.camera_id}: {error_msg}")
            self.state.connection_status = CameraStatus.ERROR
            self.state.error_message = error_msg
            return False

    def disconnect(self) -> None:
        self._stop_reader_thread()
        if self._fallback_dummy is not None:
            try:
                self._fallback_dummy.disconnect()
            except Exception:
                pass
            self._fallback_dummy = None

        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            finally:
                self.cap = None
        self.state.connection_status = CameraStatus.DISCONNECTED

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        if self._fallback_dummy is not None:
            return self._fallback_dummy.read_frame()

        if self.cap is None or not self.cap.isOpened():
            self.state.connection_status = CameraStatus.DISCONNECTED
            return False, None

        # Return latest fresh frame directly from zero-lag reader thread
        if self._reader_thread and self._reader_thread.is_alive():
            signaled = self._new_frame_event.wait(timeout=0.5)
            if not signaled:
                now_sec = time.time()
                if self._last_frame_read_time > 0 and (now_sec - self._last_frame_read_time > self.timeout_seconds):
                    return False, None
            with self._frame_lock:
                self._new_frame_event.clear()
                if self._latest_raw_frame is not None:
                    return True, self._latest_raw_frame

        # Fallback direct read during thread warm-up
        ret, frame = self.cap.read()
        if not ret or frame is None:
            return False, None
        return True, frame

    def is_connected(self) -> bool:
        if self._fallback_dummy is not None:
            return self._fallback_dummy.is_connected()
        return self.cap is not None and self.cap.isOpened() and self.state.connection_status == CameraStatus.CONNECTED

    @property
    def requires_throttling(self) -> bool:
        if self._fallback_dummy is not None:
            return True
        # Physical webcam hardware clocks frames via cap.read(); do not throttle artificially
        return False
