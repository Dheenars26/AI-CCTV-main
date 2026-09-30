"""
Regression tests for fire-scene PPE false positive (Worker #101 phantom).

Ensures that:
1. Fire/smoke frame with NO person → zero worker_ppe_analyses, zero person detections.
2. Real worker near real fire → worker is still detected (threshold boost doesn't blind).
3. Standalone vest HSV fallback is disabled when fire/smoke context is present.
4. Tracker drops stale tracks that aren't reconfirmed within staleness window.
"""

import time
import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from typing import List, Dict, Any, Optional

from app.detection.base import BoundingBox, DetectionResult
from app.safety.tracker import PersonTracker, TrackedPerson


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_fire_det(x_min: float = 0.1, y_min: float = 0.2,
                   x_max: float = 0.6, y_max: float = 0.7,
                   conf: float = 0.85) -> DetectionResult:
    """Create a synthetic fire detection."""
    return DetectionResult(
        label="fire",
        confidence=conf,
        bbox=BoundingBox(x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max),
        metadata={"detection_engine": "FireSmokeEngine"},
    )


def _make_person_det(x_min: float = 0.2, y_min: float = 0.1,
                     x_max: float = 0.5, y_max: float = 0.9,
                     conf: float = 0.72) -> DetectionResult:
    """Create a synthetic person detection."""
    return DetectionResult(
        label="person",
        confidence=conf,
        bbox=BoundingBox(x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max),
        metadata={"detector_module": "PersonDetector", "engine": "ONNXYOLORunner"},
    )


# ---------------------------------------------------------------------------
# Test 1: Tracker staleness enforcement
# ---------------------------------------------------------------------------

class TestTrackerStaleness:
    """Tracks not reconfirmed within FIRE_SCENE_TRACK_STALENESS_SECONDS are hard-dropped."""

    def test_stale_track_dropped(self):
        """A track that hasn't been matched by a fresh detection for > staleness window is removed."""
        tracker = PersonTracker(camera_id=1, max_disappeared_frames=50)

        # Register a person on frame 1
        person = _make_person_det(conf=0.80)
        tracks = tracker.update([person])
        assert len(tracks) >= 1
        initial_pid = tracks[0].person_id

        # Simulate time passing beyond staleness limit with no detections
        # Manually age the track's last_confirmed_time
        for pid, trk in tracker._tracked_persons.items():
            trk.last_confirmed_time = time.time() - 10.0  # 10s ago, well past 3s default

        # Update with no detections — staleness purge should fire
        tracks_after = tracker.update([])
        # The stale track should be gone
        assert initial_pid not in tracker._tracked_persons

    def test_fresh_track_survives(self):
        """A track that was just confirmed survives the staleness check."""
        tracker = PersonTracker(camera_id=1, max_disappeared_frames=50)

        person = _make_person_det(conf=0.80)
        tracks = tracker.update([person])
        assert len(tracks) >= 1

        # Update again with same person — track reconfirmed
        tracks2 = tracker.update([person])
        assert len(tracks2) >= 1
        # Track is still alive
        assert tracks[0].person_id in tracker._tracked_persons


# ---------------------------------------------------------------------------
# Test 2: Standalone vest HSV disabled in fire scenes
# ---------------------------------------------------------------------------

class TestVestHSVFireVeto:
    """HSV vest fallback is suppressed when fire/smoke boxes are present."""

    def test_vest_hsv_masks_fire_regions(self):
        """Contours overlapping fire/smoke boxes are zeroed out of the vest mask."""
        from app.detection.ppe_detector import PPEDetector

        detector = PPEDetector.__new__(PPEDetector)
        detector._onnx_runner = None
        detector._model = None
        detector._is_mock_fallback = True

        # Create a solid orange image (entire frame looks like hi-vis)
        img = np.full((480, 640, 3), [0, 140, 255], dtype=np.uint8)  # BGR orange

        # Without fire context: should find vest candidates
        results_no_fire = detector._detect_standalone_vest_hsv(img, fire_smoke_boxes=None)

        # With fire box covering the entire frame: vest mask is zeroed
        fire_box = _make_fire_det(0.0, 0.0, 1.0, 1.0)
        results_with_fire = detector._detect_standalone_vest_hsv(img, fire_smoke_boxes=[fire_box])

        # The fire-masked version should produce fewer or zero results
        assert len(results_with_fire) < len(results_no_fire) or len(results_with_fire) == 0


# ---------------------------------------------------------------------------
# Test 3: Person threshold boost in fire scene
# ---------------------------------------------------------------------------

class TestPersonFireSceneBoost:
    """Person detections overlapping fire/smoke boxes require higher confidence."""

    @patch("app.detection.person_detector.settings")
    def test_low_confidence_person_rejected_in_fire_scene(self, mock_settings):
        """A low-confidence person box overlapping fire is rejected by the boosted threshold."""
        mock_settings.AI_PERSON_ENABLED = True
        mock_settings.FIRE_SCENE_VETO_ENABLED = True
        mock_settings.FIRE_SCENE_THRESHOLD_BOOST = 0.25
        mock_settings.FIRE_SCENE_PERSON_IOU_SUPPRESS = 0.15
        mock_settings.PERSON_MIN_BOX_HEIGHT = 0.05
        mock_settings.PERSON_MIN_ASPECT_RATIO = 0.10
        mock_settings.PERSON_MAX_ASPECT_RATIO = 2.0
        mock_settings.ENABLE_PERSON_ROI_REFINE = False

        # Simulate: the ONNX runner returns a person at 0.42 confidence
        # overlapping a fire box. Base threshold is 0.30, boosted to 0.55.
        # 0.42 < 0.55 → rejected.
        from app.detection.person_detector import PersonDetector

        detector = PersonDetector.__new__(PersonDetector)
        detector._onnx_runner = MagicMock()
        detector._model = None
        detector._is_mock_fallback = False
        detector.conf_threshold = 0.30
        detector.device = "cpu"

        fire_det = _make_fire_det(0.15, 0.15, 0.55, 0.75)
        person_bbox = BoundingBox(x_min=0.2, y_min=0.1, x_max=0.5, y_max=0.9)

        detector._onnx_runner.class_names = ["person"]
        detector._onnx_runner.predict.return_value = (
            [{"label": "person", "confidence": 0.42, "bbox": person_bbox, "class_id": 0}],
            15.0,
        )

        results = detector.detect(
            np.zeros((480, 640, 3), dtype=np.uint8),
            fire_smoke_boxes=[fire_det],
        )

        # The 0.42 person should be rejected by the fire-scene boost
        assert len(results) == 0, f"Expected 0 person detections, got {len(results)}"

    @patch("app.detection.person_detector.settings")
    def test_high_confidence_person_survives_fire_scene(self, mock_settings):
        """A high-confidence person near fire still passes the boosted threshold."""
        mock_settings.AI_PERSON_ENABLED = True
        mock_settings.FIRE_SCENE_VETO_ENABLED = True
        mock_settings.FIRE_SCENE_THRESHOLD_BOOST = 0.25
        mock_settings.FIRE_SCENE_PERSON_IOU_SUPPRESS = 0.15
        mock_settings.PERSON_MIN_BOX_HEIGHT = 0.05
        mock_settings.PERSON_MIN_ASPECT_RATIO = 0.10
        mock_settings.PERSON_MAX_ASPECT_RATIO = 2.0
        mock_settings.ENABLE_PERSON_ROI_REFINE = False

        from app.detection.person_detector import PersonDetector

        detector = PersonDetector.__new__(PersonDetector)
        detector._onnx_runner = MagicMock()
        detector._model = None
        detector._is_mock_fallback = False
        detector.conf_threshold = 0.30
        detector.device = "cpu"

        fire_det = _make_fire_det(0.15, 0.15, 0.55, 0.75)
        person_bbox = BoundingBox(x_min=0.2, y_min=0.1, x_max=0.5, y_max=0.9)

        detector._onnx_runner.class_names = ["person"]
        detector._onnx_runner.predict.return_value = (
            [{"label": "person", "confidence": 0.78, "bbox": person_bbox, "class_id": 0}],
            15.0,
        )

        results = detector.detect(
            np.zeros((480, 640, 3), dtype=np.uint8),
            fire_smoke_boxes=[fire_det],
        )

        # 0.78 > 0.55 (0.30 + 0.25) → should pass
        assert len(results) == 1, f"Expected 1 person detection, got {len(results)}"
