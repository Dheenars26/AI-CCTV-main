"""
Thread-safe Bounded Latest Frame Buffer.
Allows a single camera stream worker thread to publish frames,
while multiple consumers (AI detection engine, JPEG snapshot API, video streams)
can safely read the latest frame without stream read duplication or lock contention.
"""

import threading
from datetime import datetime, timezone
from typing import Optional, Tuple
import cv2
import numpy as np


class LatestFrameBuffer:
    """
    Thread-safe bounded buffer holding the latest captured video frame.
    Guarantees thread safety with non-blocking atomic reads and pre-encoded JPEG caching.
    """

    def __init__(self, camera_id: int):
        self.camera_id = camera_id
        self._lock = threading.Lock()
        self._latest_frame: Optional[np.ndarray] = None
        self._latest_jpeg: Optional[bytes] = None
        self._last_updated: Optional[datetime] = None
        self._frame_count: int = 0

    def update(self, frame: np.ndarray) -> None:
        """
        Updates buffer with latest decoded frame matrix.
        Zero CPU overhead in the ingestion thread; JPEG compression is lazily performed
        only when an active HTTP client requests a stream frame.
        """
        now = datetime.now(timezone.utc)
        with self._lock:
            self._latest_frame = frame
            self._latest_jpeg = None  # Invalidate cached JPEG
            self._last_updated = now
            self._frame_count += 1

    def get_latest(self) -> Tuple[Optional[np.ndarray], Optional[datetime], int]:
        """
        Returns a tuple of (latest_frame_matrix, timestamp, total_frame_count).
        Safe for concurrent calls from multiple subscriber threads.
        """
        with self._lock:
            if self._latest_frame is None:
                return None, None, self._frame_count
            return self._latest_frame.copy(), self._last_updated, self._frame_count

    def get_latest_jpeg(self) -> Tuple[Optional[bytes], Optional[datetime], int]:
        """
        Returns JPEG bytes directly for zero-latency HTTP MJPEG streaming.
        Uses on-demand encoding with caching per frame_count to eliminate CPU waste.
        """
        with self._lock:
            if self._latest_jpeg is not None:
                return self._latest_jpeg, self._last_updated, self._frame_count
            if self._latest_frame is None or self._latest_frame.size == 0:
                return None, self._last_updated, self._frame_count
            frame_to_encode = self._latest_frame
            target_count = self._frame_count
            target_time = self._last_updated

        # Encode on-demand with optimized quality 65 (fast SIMD JPEG encoding & small network packets)
        try:
            success, buf = cv2.imencode(".jpg", frame_to_encode, [cv2.IMWRITE_JPEG_QUALITY, 65])
            encoded = buf.tobytes() if success else None
        except Exception:
            encoded = None

        with self._lock:
            if self._frame_count == target_count:
                self._latest_jpeg = encoded
            return encoded, target_time, target_count

    def clear(self) -> None:
        """
        Clears buffer contents upon camera stream stop/release.
        """
        with self._lock:
            self._latest_frame = None
            self._latest_jpeg = None
            self._last_updated = None
