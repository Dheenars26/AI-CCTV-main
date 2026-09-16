"""
Dedicated Frame Scheduler Component (FrameScheduler).
Decouples camera ingestion rate (capture_fps) from AI processing rate (target_ai_fps).
Applies configurable priority sampling (HIGH, MEDIUM, LOW) and adaptive downsampling under GPU backpressure.
"""

from typing import Dict, Any


class FrameScheduler:
    """
    Schedules frame sampling for AI processing based on camera priority and target AI FPS.
    """

    def __init__(self):
        # Priority frame skip multipliers
        self._priority_multipliers: Dict[str, float] = {
            "HIGH": 1.0,    # Run at full target_ai_fps
            "MEDIUM": 0.5,  # Run at 50% target_ai_fps (every 2nd frame)
            "LOW": 0.25     # Run at 25% target_ai_fps (every 4th frame)
        }

    def should_process_frame(
        self,
        frame_index: int,
        priority: str = "HIGH",
        capture_fps: int = 25,
        target_ai_fps: int = 10,
        backpressure_level: float = 0.0
    ) -> bool:
        """
        Determines whether a specific frame index should be dispatched to the AI Worker Pool.
        Respects target_ai_fps (e.g. 10 FPS) against capture_fps (e.g. 25 FPS).
        """
        p = priority.upper() if priority else "HIGH"
        mult = self._priority_multipliers.get(p, 1.0)

        base_skip = max(1, int(round(float(capture_fps) / float(max(1, target_ai_fps)))))
        effective_skip = max(1, int(round(float(base_skip) / mult)))

        if backpressure_level > 0.5:
            effective_skip = int(effective_skip * 2)

        return (frame_index % effective_skip) == 0
