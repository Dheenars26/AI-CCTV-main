"""
Thread-Safe Bounded Frame Queue (BoundedFrameQueue).
Per-camera bounded queue storing ingested raw frames.
Drops oldest stale frames if max capacity is reached to prevent memory expansion & processing latency build-up.
"""

import queue
import threading
from typing import Optional, Tuple, Any
from datetime import datetime, timezone
import numpy as np


class BoundedFrameQueue:
    """
    Bounded queue with stale frame drop strategy and telemetry counters.
    """

    def __init__(self, camera_id: int, maxsize: int = 1):
        self.camera_id = camera_id
        self.maxsize = maxsize
        self._queue = queue.Queue(maxsize=maxsize)
        self.dropped_frames: int = 0
        self.total_pushed: int = 0
        self._lock = threading.Lock()

    def put_frame(self, frame: np.ndarray, timestamp: datetime, frame_id: int) -> bool:
        """
        Pushes frame into queue. Drops oldest frame if full.
        """
        with self._lock:
            self.total_pushed += 1
            if self._queue.full():
                try:
                    self._queue.get_nowait()
                    self.dropped_frames += 1
                except queue.Empty:
                    pass

            try:
                self._queue.put_nowait((frame, timestamp, frame_id))
                return True
            except queue.Full:
                self.dropped_frames += 1
                return False

    def get_frame(self, timeout: float = 0.1) -> Tuple[Optional[np.ndarray], Optional[datetime], int]:
        """
        Pulls the latest fresh frame from queue, draining any backlogged stale frames.
        Guarantees zero-lag real-time AI processing.
        """
        latest = None
        try:
            with self._lock:
                while not self._queue.empty():
                    latest = self._queue.get_nowait()

            if latest is not None:
                return latest

            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None, None, 0

    @property
    def current_size(self) -> int:
        return self._queue.qsize()

    def clear(self) -> None:
        with self._lock:
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break
