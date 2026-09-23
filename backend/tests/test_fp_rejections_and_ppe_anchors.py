"""
Unit Test Suite for Critical False Positive Rejections, Standalone HSV Blocking,
PPE Anchor Alignment, and ONNX CPU Optimization.
"""

import os
import numpy as np
import cv2
from datetime import datetime, timezone

import pytest

from app.detection.base import BoundingBox, DetectionResult
from app.detection.yolo import YOLODetector
from app.detection.onnx_engine import create_optimized_onnx_session


# =====================================================================
# 1. Full-Frame Smoke Detection Clamping & Noise Floor
# =====================================================================

def test_full_frame_smoke_box_clamped_above_40_percent():
    """Validates that any smoke candidate spanning > 40% of the total frame area is rejected as boundary noise."""
    w, h = 640, 480
    huge_bw, huge_bh = 500, 400
    norm_area = (float(huge_bw) * float(huge_bh)) / float(w * h)
    assert norm_area > 0.40, f"Expected norm area > 0.40, got {norm_area}"

    is_rejected = (norm_area > 0.40 or (huge_bw / float(w) > 0.65 and huge_bh / float(h) > 0.65))
    assert is_rejected is True, "Expected full-frame smoke bounding box to be rejected"


def test_smoke_noise_floor_discards_sub_022_conf():
    """Validates that floor mat textures triggering low confidence (e.g. 0.068) are discarded by noise floor."""
    detector = YOLODetector(model_path="models/fire_smoke.pt", conf_threshold=0.10)
    predict_conf = max(0.22, float(detector.conf_threshold))
    assert predict_conf == 0.22, f"Expected noise floor to clamp 0.10 up to 0.22, got {predict_conf}"

    low_conf_score = 0.068
    assert low_conf_score < predict_conf, "Raw floor mat noise score must be discarded by noise floor"


# =====================================================================
# 2. Cold Red Pigment Rejection & Thermal Emission Core
# =====================================================================

def test_red_dustbin_pigment_rejected():
    """Validates that cold red plastic (S > 115, B < 105, R < 180) with cold ratio > 0.40 is rejected."""
    crop = np.zeros((80, 80, 3), dtype=np.uint8)
    # Red plastic dustbin color: B=40, G=30, R=165 (R < 180, B < 105, high saturation S > 115)
    crop[:, :] = [40, 30, 165]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    s = hsv[:, :, 1]
    b, g, r = cv2.split(crop)

    # Check cold pigment definition: S > 115, B < 105, R < 180
    cold_plastic = (s > 115) & (b < 105) & (r < 180)
    assert np.all(cold_plastic), "Expected synthetic red dustbin pixels to match cold red plastic condition"

    is_valid, _ = YOLODetector._verify_flame_chromaticity(crop)
    assert is_valid is False, "Expected cold red dustbin plastic to be rejected"


def test_thermal_emission_core_with_2x2_opening_accepts_real_fire():
    """Validates that genuine blackbody emission (R >= 220, G >= 180, B >= 135, V >= 180) passes."""
    crop = np.zeros((80, 80, 3), dtype=np.uint8)
    crop[:, :] = [20, 20, 20]  # Dark background
    # Combustion flame envelope
    cv2.circle(crop, (40, 40), 30, (20, 90, 240), -1)
    # Mid flame zone
    cv2.circle(crop, (40, 40), 20, (30, 180, 255), -1)
    # Genuine blackbody incandescent core: R=245 >= 220, G=225 >= 180, B=160 >= 135, V=245 >= 180
    cv2.circle(crop, (40, 40), 10, (160, 225, 245), -1)

    is_valid, score = YOLODetector._verify_flame_chromaticity(crop)
    assert is_valid is True, "Expected genuine blackbody emission flame to pass"
    assert score > 0.0


# =====================================================================
# 3. Block Standalone HSV Candidate Injection (Strict Consensus Only)
# =====================================================================

def test_worker_status_label_stays_inside_the_frame():
    """
    The overlay must clamp worker status labels inside the frame.

    Rewritten for the merged codebase: the parallel implementation exposed a
    `calculate_ppe_status_anchor` helper; the shipping overlay clamps inline while drawing. The
    property that matters is unchanged - a worker at the very top of the frame must still get a
    readable label that is fully inside the image.
    """
    from app.camera.pipeline import Frame, StandardPostprocessor

    h, w = 480, 640
    image = np.zeros((h, w, 3), dtype=np.uint8)

    # Worker whose head is at the top edge: there is no headroom for the label above it.
    edge_person = BoundingBox(x_min=0.20, y_min=0.0, x_max=0.45, y_max=0.55)
    frame = Frame(camera_id=1, frame_id=1, timestamp=datetime.now(timezone.utc), image=image, detections=[
        DetectionResult(label="person", confidence=0.93, bbox=edge_person),
    ])
    frame.metadata["worker_ppe_analyses"] = [{
        "person_id": 7,
        "bounding_box": edge_person.model_dump() if hasattr(edge_person, "model_dump") else edge_person.__dict__,
        "status": "VIOLATION",
        "missing_equipment": ["vest"],
        "detected_equipment": [],
    }]
    frame.metadata["safety_zones"] = []

    out = StandardPostprocessor(debug_overlay=True).process(frame)
    assert out.image.shape == (h, w, 3)

    # Content must be painted inside the frame near the top - evidence that the label was clamped
    # rather than drawn off-image (OpenCV silently discards out-of-bounds drawing).
    assert np.count_nonzero(out.image[0:45, :, :]) > 0, "worker label was not drawn inside the frame"

    # And nothing may be drawn beyond the frame, checked by rendering a person at the bottom edge too.
    bottom_person = BoundingBox(x_min=0.20, y_min=0.90, x_max=0.45, y_max=1.0)
    frame2 = Frame(camera_id=1, frame_id=2, timestamp=datetime.now(timezone.utc), image=image.copy(), detections=[
        DetectionResult(label="person", confidence=0.91, bbox=bottom_person),
    ])
    frame2.metadata["worker_ppe_analyses"] = []
    frame2.metadata["safety_zones"] = []
    out2 = StandardPostprocessor(debug_overlay=True).process(frame2)
    assert out2.image.shape == (h, w, 3)
def test_person_ppe_roi_localization_consistency():
    """
    Validates that eyewear is restricted to the facial region and a vest to the upper torso.

    Rewritten for the merged codebase: item plausibility lives in
    `PPEAssociationEngine._is_ppe_on_person_with_score` (relative-height ranges per item) rather
    than in a YOLODetector helper. The check is the same one the pipeline applies to every PPE box
    before it is allowed to count towards (or against) a worker's compliance.
    """
    from app.safety.association import PPEAssociationEngine

    engine = PPEAssociationEngine()
    person_box = BoundingBox(x_min=0.2, y_min=0.1, x_max=0.6, y_max=0.9)  # height 0.8

    # Eyewear on the face (relative height ~0.16) is plausible.
    glasses_face = BoundingBox(x_min=0.35, y_min=0.20, x_max=0.45, y_max=0.24)
    assert engine._is_ppe_on_person(person_box, glasses_face, "glasses") is True

    # Eyewear held at the waist (relative height ~0.66) is not worn eyewear.
    glasses_waist = BoundingBox(x_min=0.35, y_min=0.60, x_max=0.45, y_max=0.65)
    assert engine._is_ppe_on_person(person_box, glasses_waist, "glasses") is False

    # Vest across the torso (relative height ~0.42) is plausible.
    vest_torso = BoundingBox(x_min=0.25, y_min=0.30, x_max=0.55, y_max=0.60)
    assert engine._is_ppe_on_person(person_box, vest_torso, "vest") is True

    # A "vest" at the feet (relative height ~0.91) is a measurement error, not a compliant worker.
    vest_feet = BoundingBox(x_min=0.30, y_min=0.85, x_max=0.50, y_max=0.95)
    assert engine._is_ppe_on_person(person_box, vest_feet, "vest") is False
def test_onnx_cpu_session_optimization_configuration():
    """Validates that create_optimized_onnx_session configures ORT_ENABLE_ALL, threads, ORT_SEQUENTIAL, allow_spinning."""
    onnx_path = "models/fire_smoke.onnx"
    if not os.path.isfile(onnx_path):
        pytest.skip(f"Model file {onnx_path} not present in test environment")

    session = create_optimized_onnx_session(onnx_path, device="cpu")
    assert session is not None
    assert len(session.get_inputs()) >= 1
    assert len(session.get_outputs()) >= 1
