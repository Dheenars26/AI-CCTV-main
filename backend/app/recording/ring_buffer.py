"""
Thread-safe Rolling Frame Ring Buffer for Pre-Event Video Clip Recording.
Maintains a sliding temporal window of recent decoded video frames in memory.
"""

import threading
from collections import deque
from datetime import datetime, timezone
from typing import List, Tuple, Optional
import numpy as np


class RollingFrameRingBuffer:
    """
    Circular ring buffer holding rolling pre-event video frames.
    Allows capturing the N seconds preceding a confirmed fire or smoke detection event.
    """

    def __init__(self, max_seconds: float = 5.0, default_fps: float = 25.0):
        """
        :param max_seconds: Temporal window capacity in seconds.
        :param default_fps: Estimated stream frame rate for sizing buffer capacity.
        """
        self.max_seconds = max_seconds
        self.default_fps = min(60.0, max(1.0, default_fps))
        self.max_capacity = int(self.max_seconds * self.default_fps * 1.5)  # Headroom factor
        self._buffer: deque = deque(maxlen=self.max_capacity)
        self._lock = threading.Lock()

    def update_fps(self, fps: float) -> None:
        """
        Dynamically adjusts buffer capacity if stream FPS changes.
        """
        if fps > 0:
            clamped_fps = min(60.0, max(1.0, fps))
            self.default_fps = clamped_fps
            new_capacity = int(self.max_seconds * self.default_fps * 1.5)
            with self._lock:
                if new_capacity != self._buffer.maxlen:
                    self._buffer = deque(self._buffer, maxlen=new_capacity)

    def add_frame(self, frame: np.ndarray, timestamp: Optional[datetime] = None) -> None:
        """
        Pushes a new decoded video frame matrix into the rolling buffer.
        """
        if frame is None or frame.size == 0:
            return

        ts = timestamp or datetime.now(timezone.utc)
        # Store non-blocking copy or reference under lock
        with self._lock:
            self._buffer.append((frame.copy(), ts))

    def get_pre_event_frames(self, duration_seconds: Optional[float] = None) -> List[Tuple[np.ndarray, datetime]]:
        """
        Extracts pre-event frames corresponding to the requested duration (seconds) preceding current time.
        Returns a list of (image_matrix, timestamp) tuples sorted chronologically.
        """
        target_dur = duration_seconds if duration_seconds is not None else self.max_seconds
        now_dt = datetime.now(timezone.utc)

        with self._lock:
            buffer_snapshot = list(self._buffer)

        if not buffer_snapshot:
            return []

        # Filter frames falling within the target duration window
        result = []
        for img, ts in buffer_snapshot:
            age_sec = (now_dt - ts).total_seconds()
            if age_sec <= target_dur:
                result.append((img.copy(), ts))

        return result

    def clear(self) -> None:
        """
        Clears ring buffer memory.
        """
        with self._lock:
            self._buffer.clear()
