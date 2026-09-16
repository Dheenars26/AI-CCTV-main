"""
Unit tests for PPEDetector and modular AI detector interface.
Verifies safe startup without GPU/weights, model info metadata, health checks, and detection outputs.
"""

import os
import numpy as np
import pytest

from app.detection.base import BaseDetector, DummyDetector, DetectorStatus
from app.detection.ppe_detector import PPEDetector
from app.detection.fire_smoke_detector import FireSmokeDetector
from app.detection.person_detector import PersonDetector


def test_ppe_detector_safe_initialization():
    detector = PPEDetector(model_path="models/non_existent.pt", device="cpu")
    assert detector.status in [DetectorStatus.HEALTHY, DetectorStatus.DEGRADED]
    assert detector.get_model_name().startswith("PPEDetector")
    
    info = detector.get_model_info()
    assert "model_name" in info
    assert "model_hash" in info
    assert "loaded_at" in info
    assert "target_classes" in info


def test_fire_smoke_detector_initialization():
    detector = FireSmokeDetector(device="cpu")
    assert detector.status in [DetectorStatus.HEALTHY, DetectorStatus.DEGRADED]
    health = detector.health_check()
    assert health["detector"] == "FireSmokeDetector"
    assert health["status"] in ["HEALTHY", "DEGRADED"]


def test_person_detector_initialization():
    detector = PersonDetector(device="cpu")
    assert detector.status in [DetectorStatus.HEALTHY, DetectorStatus.DEGRADED]
    health = detector.health_check()
    assert health["detector"] == "PersonDetector"


def test_detector_inference_on_dummy_frame():
    detector = PPEDetector(device="cpu")
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    detections = detector.detect(frame)
    assert isinstance(detections, list)


def test_detection_targets_smoke_fire_vest_safety_glass():
    # 1. Fire & Smoke Detector targets
    fs_detector = FireSmokeDetector(device="cpu")
    info = fs_detector.get_model_info()
    assert "fire" in info["target_classes"]
    assert "smoke" in info["target_classes"]

    # 2. PPE Detector targets (Safety Vest & Safety Glass)
    ppe_detector = PPEDetector(device="cpu")
    target_classes = ppe_detector.target_classes
    assert "vest" in target_classes or "safety_vest" in target_classes
    assert "goggles" in target_classes or "safety_glasses" in target_classes

    # Verify association normalization
    from app.safety.association import PPEAssociationEngine
    assoc = PPEAssociationEngine()
    assert assoc._normalize_label("safety_vest") == "vest"
    assert assoc._normalize_label("safety_glass") == "goggles"
    assert assoc._normalize_label("safety glasses") == "goggles"
    assert assoc._normalize_label("protective_glasses") == "goggles"
    assert assoc._normalize_label("spectacles") == "goggles"


def test_cv_ppe_safety_glasses_detection():
    """Verifies that multi-modal feature extraction identifies safety glasses with structural frame & brow bar."""
    import cv2
    from app.detection.base import BoundingBox, DetectionResult

    ppe_detector = PPEDetector(device="cpu")

    # Generate synthetic 640x480 worker image with head & safety glasses features
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    # Face skin tone
    cv2.rectangle(img, (260, 80), (380, 220), (140, 175, 225), -1)
    # Safety glasses at natural eye line (y=110): horizontal brow bar + 2 frame lenses + nasal bridge
    cv2.line(img, (280, 110), (360, 110), (30, 30, 30), 4)  # Top brow bar
    cv2.rectangle(img, (285, 110), (315, 135), (20, 20, 20), 3)  # Left frame rim
    cv2.rectangle(img, (325, 110), (355, 135), (20, 20, 20), 3)  # Right frame rim
    cv2.line(img, (315, 118), (325, 118), (20, 20, 20), 3)  # Nasal bridge
    cv2.circle(img, (300, 122), 3, (250, 250, 250), -1)  # Specular glare spot

    person_box = BoundingBox(x_min=0.30, y_min=0.10, x_max=0.70, y_max=0.90)
    person_det = DetectionResult(label="person", confidence=0.90, bbox=person_box)

    ppe_dets = ppe_detector._detect_cv_ppe_features(img, [person_det])
    labels = [d.label for d in ppe_dets]
    assert "goggles" in labels
    goggle_det = next(d for d in ppe_dets if d.label == "goggles")
    assert goggle_det.confidence >= 0.80
    assert goggle_det.metadata["detection_engine"] == "OpenCV-DeepFeature-SafetyGlass-Detector"


def test_safety_glasses_spatial_association_seated_worker():
    """Verifies that seated/desk workers with lower relative eye height (cy_rel=0.38) are correctly associated."""
    from app.safety.association import PPEAssociationEngine
    from app.safety.tracker import TrackedPerson
    from app.detection.base import BoundingBox, DetectionResult

    engine = PPEAssociationEngine()
    # Desk worker: bounding box from y=0.10 to y=0.70 (upper body / seated)
    person_bbox = BoundingBox(x_min=0.25, y_min=0.10, x_max=0.75, y_max=0.70)
    tracked_person = TrackedPerson(person_id=1, camera_id=1, bbox=person_bbox, confidence=0.92, last_seen_timestamp=1.0)

    # Safety glasses centered at y=0.33 -> cy_rel = (0.33 - 0.10) / (0.60) = 0.383 (within updated 0.50 range)
    goggles_bbox = BoundingBox(x_min=0.40, y_min=0.30, x_max=0.60, y_max=0.36)
    ppe_dets = [DetectionResult(label="goggles", confidence=0.92, bbox=goggles_bbox)]

    analyses = engine.associate(
        camera_id=1,
        tracked_persons=[tracked_person],
        ppe_detections=ppe_dets,
        required_equipment=["goggles"]
    )
    assert len(analyses) == 1
    assert analyses[0].status == "PASS"
    assert "goggles" in analyses[0].detected_equipment
    assert len(analyses[0].missing_equipment) == 0


def test_cv_ppe_bare_face_no_false_positive():
    """Verifies that a bare face without glasses does NOT falsely trigger safety glasses detection."""
    import cv2
    from app.detection.base import BoundingBox, DetectionResult
    from app.detection.ppe_detector import PPEDetector

    detector = PPEDetector(device="cpu")

    # Synthetic worker image with natural skin face and eyes, but NO glasses frames or bridge
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    # Natural skin tone
    cv2.rectangle(img, (260, 80), (380, 220), (140, 175, 225), -1)
    # Natural eye pupils without glasses
    cv2.circle(img, (295, 125), 5, (50, 50, 50), -1)
    cv2.circle(img, (345, 125), 5, (50, 50, 50), -1)
    # Natural curved eyebrows
    cv2.line(img, (280, 110), (315, 108), (60, 60, 60), 2)
    cv2.line(img, (325, 108), (360, 110), (60, 60, 60), 2)

    person_box = BoundingBox(x_min=0.30, y_min=0.10, x_max=0.70, y_max=0.90)
    person_det = DetectionResult(label="person", confidence=0.90, bbox=person_box)

    ppe_dets = detector._detect_cv_ppe_features(img, [person_det])
    goggles_dets = [d for d in ppe_dets if d.label == "goggles"]
    assert len(goggles_dets) == 0, f"Expected no goggles on bare face, but found {goggles_dets}"


def test_cv_ppe_glasses_detection_settings_toggle(monkeypatch):
    """Verifies that ENABLE_CV_GLASSES_DETECTION=False disables CV glasses detection completely."""
    import cv2
    from app.config.settings import settings
    from app.detection.base import BoundingBox, DetectionResult
    from app.detection.ppe_detector import PPEDetector

    monkeypatch.setattr(settings, "ENABLE_CV_GLASSES_DETECTION", False)

    detector = PPEDetector(device="cpu")
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.rectangle(img, (260, 80), (380, 220), (140, 175, 225), -1)
    cv2.line(img, (280, 110), (360, 110), (30, 30, 30), 4)

    person_box = BoundingBox(x_min=0.30, y_min=0.10, x_max=0.70, y_max=0.90)
    person_det = DetectionResult(label="person", confidence=0.90, bbox=person_box)

    ppe_dets = detector._detect_cv_ppe_features(img, [person_det])
    goggles_dets = [d for d in ppe_dets if d.label == "goggles"]
    assert len(goggles_dets) == 0


def test_cv_ppe_prescription_spectacles_detection():
    """Verifies that thin-frame prescription spectacles with nasal bridge and rims are detected."""
    import cv2
    from app.detection.base import BoundingBox, DetectionResult
    from app.detection.ppe_detector import PPEDetector

    detector = PPEDetector(device="cpu")
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    # Face skin tone
    cv2.rectangle(img, (260, 80), (380, 220), (140, 175, 225), -1)
    # Prescription spectacles: thin nasal bridge (y=118) + thin brow bar + thin orbital rims
    cv2.line(img, (280, 110), (360, 110), (45, 45, 45), 2)  # Thin brow bar
    cv2.rectangle(img, (285, 110), (315, 135), (40, 40, 40), 2)  # Thin left rim
    cv2.rectangle(img, (325, 110), (355, 135), (40, 40, 40), 2)  # Thin right rim
    cv2.line(img, (315, 118), (325, 118), (35, 35, 35), 2)  # Nasal bridge connector

    person_box = BoundingBox(x_min=0.30, y_min=0.10, x_max=0.70, y_max=0.90)
    person_det = DetectionResult(label="person", confidence=0.90, bbox=person_box)

    ppe_dets = detector._detect_cv_ppe_features(img, [person_det])
    labels = [d.label for d in ppe_dets]
    assert "goggles" in labels
    goggle_det = next(d for d in ppe_dets if d.label == "goggles")
    assert goggle_det.confidence >= 0.70




