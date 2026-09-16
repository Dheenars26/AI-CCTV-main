"""
Unit & Integration Test Suite for Phase 4 YOLO Fire & Smoke Detection Engine.
"""

import os
import pytest
import numpy as np
from datetime import datetime, timezone

from app.config.settings import settings
from app.detection.base import BoundingBox, DetectionResult
from app.detection.yolo import YOLODetector, _YOLO_MODEL_CACHE
from app.camera.pipeline import Frame, FramePipeline, StandardPostprocessor


def test_yolo_detector_initialization_and_caching():
    """
    Tests YOLODetector initialization, configurable parameters, and model registry caching (loads ONCE).
    """
    detector1 = YOLODetector(
        model_path="models/fire_smoke.pt",
        conf_threshold=0.5,
        iou_threshold=0.4,
        device="cpu"
    )
    assert detector1.conf_threshold == 0.5
    assert detector1.iou_threshold == 0.4
    assert detector1.device == "cpu"

    # Verify global registry cache is populated
    cache_key = "models/fire_smoke.pt_cpu"
    assert cache_key in _YOLO_MODEL_CACHE

    # Second instance should reuse cached model state
    detector2 = YOLODetector(
        model_path="models/fire_smoke.pt",
        conf_threshold=0.5,
        device="cpu"
    )
    assert detector2.model_path == detector1.model_path


def test_yolo_detector_safe_fallback():
    """
    Tests YOLODetector safe fallback execution on missing model weights file (no server crash).
    """
    detector = YOLODetector(model_path="non_existent_weights_path.pt")
    assert detector._is_mock_fallback is True

    # Detection on blank image should safely return empty list
    dummy_img = np.zeros((480, 640, 3), dtype=np.uint8)
    results = detector.detect(dummy_img)
    assert isinstance(results, list)
    assert len(results) == 0


def test_detection_result_structure():
    """
    Tests DetectionResult data model structure and serialization format.
    """
    bbox = BoundingBox(x_min=0.1, y_min=0.2, x_max=0.5, y_max=0.6)
    det = DetectionResult(
        label="fire",
        confidence=0.89,
        bbox=bbox,
        camera_id=1,
        timestamp="2026-08-18T09:00:00Z",
        frame_info={"frame_id": 100, "fps": 25.0}
    )

    assert det.class_name == "fire"
    assert det.confidence == 0.89
    assert det.camera_id == 1
    assert det.bbox.to_pixel_coords(1000, 1000) == (100, 200, 500, 600)

    serialized = det.to_dict()
    assert serialized["class_name"] == "fire"
    assert serialized["confidence"] == 0.89
    assert serialized["bbox"]["x_min"] == 0.1
    assert serialized["camera_id"] == 1


def test_pipeline_with_yolo_detector():
    """
    Integration test verifying FramePipeline executing YOLODetector and postprocessing metadata.
    """
    yolo_detector = YOLODetector(model_path="models/fire_smoke.pt")
    pipeline = FramePipeline(
        camera_id=2,
        detector=yolo_detector,
        postprocessor=StandardPostprocessor(debug_overlay=True)
    )

    raw_img = np.zeros((480, 640, 3), dtype=np.uint8)
    processed_frame = pipeline.process_frame(raw_image=raw_img, frame_id=1, fps=25.0)

    assert isinstance(processed_frame, Frame)
    assert processed_frame.camera_id == 2
    assert "processed_at" in processed_frame.metadata
