"""
Unit and Integration Test Suite for Phase 3 OpenCV Camera Frame Processing Pipeline.
"""

import time
import numpy as np
import pytest
from datetime import datetime, timezone

from app.detection.base import DummyDetector, BoundingBox, DetectionResult
from app.camera.pipeline import (
    Frame,
    StandardPreprocessor,
    FreezeDetector,
    StandardPostprocessor,
    StandardEventManager,
    FramePipeline
)
from app.camera.manager import CameraManager


def test_frame_dataclass():
    """
    Tests Frame data structure instantiation and memory cleanup.
    """
    dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
    frame = Frame(
        camera_id=1,
        frame_id=42,
        image=dummy_img,
        timestamp=datetime.now(timezone.utc),
        fps=25.0
    )
    assert frame.camera_id == 1
    assert frame.frame_id == 42
    assert frame.image.shape == (100, 100, 3)
    assert frame.is_frozen is False


def test_preprocessor_resize_and_roi():
    """
    Tests StandardPreprocessor resizing and ROI cropping functionality.
    """
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    frame = Frame(camera_id=1, frame_id=1, image=img, timestamp=datetime.now(timezone.utc))

    # 1. Test Resizing
    preprocessor = StandardPreprocessor(target_size=(320, 240))
    processed = preprocessor.process(frame)
    assert processed.image.shape == (240, 320, 3)
    assert processed.metadata.get("resized") == "320x240"

    # 2. Test ROI Cropping
    img2 = np.zeros((1000, 1000, 3), dtype=np.uint8)
    frame2 = Frame(camera_id=1, frame_id=2, image=img2, timestamp=datetime.now(timezone.utc))
    preprocessor_roi = StandardPreprocessor(roi_crop=(0.1, 0.1, 0.5, 0.5))
    processed_roi = preprocessor_roi.process(frame2)
    assert processed_roi.image.shape == (400, 400, 3)
    assert processed_roi.metadata.get("roi_applied") is True


def test_freeze_detector():
    """
    Tests FreezeDetector flagging frozen streams on static frame sequence and resetting on motion.
    """
    freeze_detector = FreezeDetector(difference_threshold=0.8, freeze_threshold_seconds=0.3)

    static_img = np.zeros((200, 200, 3), dtype=np.uint8)

    # First frame initializes reference
    f1 = Frame(camera_id=1, frame_id=1, image=static_img.copy(), timestamp=datetime.now(timezone.utc))
    freeze_detector.evaluate(f1)
    assert f1.is_frozen is False

    # Static frames over 0.3 seconds should trigger freeze detection
    time.sleep(0.35)
    f2 = Frame(camera_id=1, frame_id=2, image=static_img.copy(), timestamp=datetime.now(timezone.utc))
    freeze_detector.evaluate(f2)
    assert f2.is_frozen is True
    assert "freeze_duration_sec" in f2.metadata

    # Moving frame should resolve freeze detection
    moving_img = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
    f3 = Frame(camera_id=1, frame_id=3, image=moving_img, timestamp=datetime.now(timezone.utc))
    freeze_detector.evaluate(f3)
    assert f3.is_frozen is False


def test_dummy_detector():
    """
    Tests DummyDetector passthrough and simulation modes.
    """
    detector_passthrough = DummyDetector(simulate_detection=False)
    dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
    assert detector_passthrough.detect(dummy_img) == []

    detector_sim = DummyDetector(simulate_detection=True)
    dets = detector_sim.detect(dummy_img)
    assert len(dets) == 1
    assert dets[0].label == "fire_simulated"
    assert dets[0].confidence == 0.92


def test_frame_pipeline_execution():
    """
    Tests complete end-to-end FramePipeline execution.
    """
    pipeline = FramePipeline(
        camera_id=5,
        preprocessor=StandardPreprocessor(target_size=(640, 480)),
        detector=DummyDetector(simulate_detection=True),
        ppe_enabled=False,
        postprocessor=StandardPostprocessor(debug_overlay=True)
    )

    raw_image = np.zeros((1080, 1920, 3), dtype=np.uint8)
    processed_frame = pipeline.process_frame(raw_image=raw_image, frame_id=10, fps=29.97)

    assert isinstance(processed_frame, Frame)
    assert processed_frame.camera_id == 5
    assert processed_frame.frame_id == 10
    assert processed_frame.image.shape == (480, 640, 3)
    assert len(processed_frame.detections) == 1
    assert "processed_at" in processed_frame.metadata


def test_camera_manager_pipeline_integration():
    """
    Integration test verifying CameraManager worker loop running FramePipeline on live streams.
    """
    events_captured = []

    def test_callback(event_type, payload):
        events_captured.append((event_type, payload))

    manager = CameraManager(event_callback=test_callback)

    class MockCameraConfig:
        id = 99
        name = "Pipeline Test Camera"
        rtsp_url = "non_existent.mp4"
        source_type = "file"
        fps_limit = 25
        capture_fps = 25
        target_ai_fps = 5
        frame_skip = 1
        priority = "HIGH"
        gpu_device_id = 0
        dvr_id = None
        dvr_channel = None
        connection_timeout = 5
        reconnect_interval = 2

    manager.add_camera(MockCameraConfig())
    assert manager.start_camera(99) is True

    # Allow worker thread time to process frames through pipeline
    time.sleep(0.4)

    frame, ts, count = manager.get_latest_frame(99)
    assert frame is not None
    assert count > 0
    assert ts is not None

    manager.stop_camera(99)
