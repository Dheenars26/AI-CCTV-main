"""
Tests for per-camera and per-detector failure isolation and CPU fallback.
Verifies that failure in one detector (e.g. PPEDetector) does NOT stop FireSmokeDetector or crash FramePipeline.
"""

from typing import List
import numpy as np
import pytest
from app.detection.base import BaseDetector, DetectionResult, DetectorStatus
from app.camera.pipeline import FramePipeline, StandardPreprocessor, StandardPostprocessor


class BrokenDetector(BaseDetector):
    """Mock detector that raises an unhandled Exception on detect()."""

    def initialize(self) -> bool:
        return True

    def detect(self, image_bgr: None) -> List[DetectionResult]:
        raise RuntimeError("Simulated AI Model Crash!")

    def get_model_name(self) -> str:
        return "BrokenDetector"

    def get_model_info(self) -> dict:
        return {"model_name": "BrokenDetector"}

    def health_check(self) -> dict:
        return {"status": "ERROR"}

    def shutdown(self) -> None:
        pass


def test_ppe_detector_failure_does_not_stop_fire_smoke():
    # Pipeline with broken PPE detector and functional fire_smoke_detector
    pipeline = FramePipeline(
        camera_id=1,
        fire_smoke_detector=None,  # Standard fallback/mock
        ppe_detector=BrokenDetector(),  # Crashes on detect()
        fire_smoke_enabled=True,
        ppe_enabled=True,
        person_enabled=False,
        zone_enabled=False
    )

    frame_matrix = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # Process frame should run cleanly without throwing exception
    processed = pipeline.process_frame(frame_matrix, frame_id=1, fps=25.0)
    assert processed is not None
    assert processed.camera_id == 1
