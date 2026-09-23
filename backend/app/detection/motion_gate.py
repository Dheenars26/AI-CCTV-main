"""
Motion gate: skips worker/PPE inference on frames that provably contain nobody.

Motivation
----------
Two independent problems share one solution.

**Cost.** Person detection plus PPE detection plus ROI refinement is ~150-250 ms of CPU per frame.
A camera pointed at an empty corridor spends all of it confirming emptiness.

**False positives.** The OpenCV fallbacks (Haar faces, skin-tone contours) and the PPE network
occasionally report phantom workers on scenes with no people at all - verified on warehouse-fire
photos, where the fallback returned persons at a fixed 0.86/0.88 confidence. Phantom workers then
produce phantom "missing PPE" violations, which is precisely the false-alarm class this system must
not have. Running the worker detectors only when something in the scene actually moved removes the
entire failure mode.

Safety property
---------------
The gate can only be skipped while **all** of the following hold: no motion above threshold, no
worker currently tracked, and the periodic safety sweep has fired recently. Any doubt resolves to
"run inference". The gate never affects the fire/smoke path.
"""

import time
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np

from app.utils.logger import logger


class MotionGate:
    """
    Foreground-motion estimator built on MOG2 background subtraction.

    The background model is updated on *every* frame the pipeline sees so it stays calibrated even
    when inference is being skipped, while the decision to run inference is made on the current
    frame's foreground ratio.
    """

    def __init__(
        self,
        enabled: bool = True,
        min_area_ratio: float = 0.0012,
        learning_rate: float = 0.05,
        warmup_frames: int = 8,
        hold_seconds: float = 1.5,
        sweep_interval_seconds: float = 2.5,
        max_motion_rois: int = 3,
        process_width: int = 320,
        invert_motion: bool = False,
    ):
        self.enabled = enabled
        self.min_area_ratio = min_area_ratio
        self.learning_rate = learning_rate
        self.warmup_frames = warmup_frames
        self.hold_seconds = hold_seconds
        self.sweep_interval_seconds = sweep_interval_seconds
        self.max_motion_rois = max_motion_rois
        self.process_width = process_width
        # Holiday / night mode: if the scene should be empty, treat motion as *corroboration*
        # rather than a gate, i.e. an inverted policy is available for future use.
        self.invert_motion = invert_motion

        self._subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500, varThreshold=36, detectShadows=False
        )
        self._kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

        self._frames_seen = 0
        self._last_motion_time = 0.0
        self._last_run_time = 0.0
        self._last_sweep_time = 0.0
        self._last_motion_ratio = 0.0
        self._last_rois: List[Tuple[float, float, float, float]] = []
        self._person_hold_until = 0.0

    # ------------------------------------------------------------------ #
    def update(self, frame_bgr: np.ndarray, persons_visible: bool = False) -> bool:
        """
        Feeds one frame to the background model and decides whether worker inference should run.

        :param frame_bgr: current camera frame.
        :param persons_visible: True when the pipeline already has live worker tracks; keeps the
               gate open so a temporarily still worker is not dropped.
        :returns: True if person/PPE inference should run for this frame.
        """
        if not self.enabled:
            return True
        if frame_bgr is None or getattr(frame_bgr, "size", 0) == 0:
            return True

        now = time.time()
        self._frames_seen += 1

        h, w = frame_bgr.shape[:2]
        if w > self.process_width:
            scale = self.process_width / float(w)
            small = cv2.resize(frame_bgr, (self.process_width, int(h * scale)), interpolation=cv2.INTER_AREA)
        else:
            small = frame_bgr

        try:
            mask = self._subtractor.apply(small, learningRate=self.learning_rate)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self._kernel)
            mask = cv2.dilate(mask, self._kernel, iterations=2)
            motion_ratio = float(np.count_nonzero(mask)) / float(mask.size)
        except Exception as e:  # pragma: no cover - defensive, OpenCV build issues
            logger.debug(f"MotionGate: background subtraction unavailable ({e}); running inference.")
            return True

        self._last_motion_ratio = motion_ratio
        if motion_ratio >= self.min_area_ratio:
            self._last_motion_time = now
            self._last_rois = self._extract_rois(mask)

        if persons_visible:
            self._person_hold_until = now + self.hold_seconds
            self._last_run_time = now
            return True

        # Warm-up: let the background model converge before it is trusted.
        if self._frames_seen <= self.warmup_frames:
            self._last_run_time = now
            self._last_sweep_time = now
            return True

        if (now - self._last_sweep_time) >= self.sweep_interval_seconds:
            # Periodic full sweep bounds the worst case: a fully static scene is still inspected a
            # few times per minute, so a person who entered during warm-up cannot be missed forever.
            self._last_sweep_time = now
            self._last_run_time = now
            return True

        if now <= self._person_hold_until:
            self._last_run_time = now
            return True

        if (now - self._last_motion_time) <= self.hold_seconds:
            self._last_run_time = now
            return True

        return False

    # ------------------------------------------------------------------ #
    def _extract_rois(self, mask: np.ndarray) -> List[Tuple[float, float, float, float]]:
        """
        Returns the largest moving blobs as normalised ``(x_min, y_min, x_max, y_max)`` boxes.

        These feed the person detector's second-pass refinement, which re-runs inference on an
        upscaled crop - the cheapest way to recover a distant worker that the full-frame pass missed.
        """
        try:
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        except Exception:
            return []
        if not contours:
            return []

        mh, mw = mask.shape[:2]
        ranked = sorted(contours, key=cv2.contourArea, reverse=True)[: self.max_motion_rois]
        rois: List[Tuple[float, float, float, float]] = []
        min_area = 0.0006 * mw * mh
        for contour in ranked:
            if cv2.contourArea(contour) < min_area:
                continue
            x, y, cw, ch = cv2.boundingRect(contour)
            # Pad generously: motion blobs are limb-sized, not person-sized.
            pad_x, pad_y = int(cw * 0.6), int(ch * 0.6)
            x1 = max(0, x - pad_x) / mw
            y1 = max(0, y - pad_y) / mh
            x2 = min(mw, x + cw + pad_x) / mw
            y2 = min(mh, y + ch + pad_y) / mh
            if (x2 - x1) < 0.02 or (y2 - y1) < 0.02:
                continue
            rois.append((x1, y1, x2, y2))
        return rois

    # ------------------------------------------------------------------ #
    @property
    def motion_rois(self) -> List[Tuple[float, float, float, float]]:
        """Normalised boxes of the most recent moving regions."""
        return list(self._last_rois)

    def stats(self) -> Dict[str, Any]:
        """Observability payload for the health/metrics endpoints."""
        return {
            "enabled": self.enabled,
            "frames_seen": self._frames_seen,
            "last_motion_ratio": round(self._last_motion_ratio, 5),
            "seconds_since_motion": round(time.time() - self._last_motion_time, 2) if self._last_motion_time else None,
            "motion_rois": len(self._last_rois),
        }

    def reset(self) -> None:
        """Rebuilds the background model (call on stream reconnect)."""
        self._subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500, varThreshold=36, detectShadows=False
        )
        self._frames_seen = 0
        self._last_motion_time = 0.0
        self._last_run_time = 0.0
        self._last_sweep_time = 0.0
        self._last_rois = []
        self._person_hold_until = 0.0
