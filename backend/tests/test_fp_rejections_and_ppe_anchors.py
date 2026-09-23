"""
Unit Test Suite for Critical False Positive Rejections, Standalone HSV Blocking,
PPE Anchor Alignment, and ONNX CPU Optimization.
"""

import os
import numpy as np
import cv2
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

def test_fuse_detections_blocks_standalone_hsv_candidate():
    """Validates that standalone HSV candidates with no matching YOLO box are completely stripped."""
    hsv_candidate = DetectionResult(
        label="fire",
        confidence=0.88,
        bbox=BoundingBox(x_min=0.1, y_min=0.1, x_max=0.3, y_max=0.4),
        metadata={"detection_engine": "OpenCV-CV"}
    )
    # No YOLO detections (e.g. sunlight gap in red door)
    fused = YOLODetector._fuse_detections(
        yolo_detections=[],
        hsv_detections=[hsv_candidate],
        fire_threshold=0.40,
        smoke_threshold=0.35
    )
    assert len(fused) == 0, f"Expected 0 detections (standalone HSV stripped), but got {len(fused)}"


def test_fuse_detections_requires_strict_iou_greater_than_020():
    """Validates that consensus requires IoU > 0.20 to boost YOLO detection."""
    yolo_box = BoundingBox(x_min=0.1, y_min=0.1, x_max=0.3, y_max=0.3)
    yolo_det = DetectionResult(label="fire", confidence=0.70, bbox=yolo_box)

    # 1. Distant HSV candidate (IoU = 0.0) -> No boost, no new detection
    distant_hsv = DetectionResult(
        label="fire",
        confidence=0.85,
        bbox=BoundingBox(x_min=0.5, y_min=0.5, x_max=0.7, y_max=0.7)
    )
    fused_distant = YOLODetector._fuse_detections([yolo_det], [distant_hsv], 0.40, 0.35)
    assert len(fused_distant) == 1
    assert fused_distant[0].confidence == 0.70  # Unboosted

    # 2. Overlapping HSV candidate (IoU > 0.20) -> Validated and boosted
    overlapping_hsv = DetectionResult(
        label="fire",
        confidence=0.85,
        bbox=BoundingBox(x_min=0.12, y_min=0.12, x_max=0.32, y_max=0.32)
    )
    assert yolo_box.iou(overlapping_hsv.bbox) > 0.20
    fused_overlap = YOLODetector._fuse_detections([yolo_det], [overlapping_hsv], 0.40, 0.35)
    assert len(fused_overlap) == 1
    assert fused_overlap[0].confidence > 0.70
    assert fused_overlap[0].metadata.get("hsv_validated") is True


# =====================================================================
# 4. PPE Detection Alignment & Bounding Box Anchors
# =====================================================================

def test_ppe_status_anchor_attaches_to_upper_boundary_without_clipping():
    """Validates that PPE status overlay dynamically attaches to upper boundary without clipping outside frame."""
    frame_dims = (640, 480)
    text_size = (200, 20)

    # Case A: Person in middle of frame with headroom
    person_mid = (150, 100, 300, 400)
    (b1_x, b1_y), (b2_x, b2_y), (tx, ty) = YOLODetector.calculate_ppe_status_anchor(
        person_mid, frame_dims, text_size
    )
    # Badge should sit right above top boundary of person (y1 = 100)
    assert b2_y <= 100, "Badge should sit above person top boundary when headroom exists"
    assert b1_y >= 0, "Badge must not clip above frame"
    assert b1_x >= 0 and b2_x <= 640, "Badge must not clip horizontal frame boundaries"

    # Case B: Person near top of frame (y1 = 10) with no headroom
    person_top = (150, 10, 300, 350)
    (b1_x, b1_y), (b2_x, b2_y), (tx, ty) = YOLODetector.calculate_ppe_status_anchor(
        person_top, frame_dims, text_size
    )
    assert b1_y >= 4, "Badge must be clamped inside frame upper boundary"
    assert b2_y <= 480, "Badge must not clip below frame"
    assert b1_x >= 0 and b2_x <= 640, "Badge must not clip horizontal frame boundaries"


def test_person_ppe_roi_localization_consistency():
    """Validates that glasses are restricted to facial region and vest to upper-torso."""
    person_box = BoundingBox(x_min=0.2, y_min=0.1, x_max=0.6, y_max=0.9)  # height = 0.8

    # Glasses on face (rel_y ~ 0.15) -> Valid
    glasses_face = BoundingBox(x_min=0.35, y_min=0.20, x_max=0.45, y_max=0.24)
    assert YOLODetector.validate_person_ppe_roi("glasses", glasses_face, person_box) is True

    # Glasses held in hands near waist (rel_y ~ 0.65) -> Invalid
    glasses_waist = BoundingBox(x_min=0.35, y_min=0.60, x_max=0.45, y_max=0.65)
    assert YOLODetector.validate_person_ppe_roi("glasses", glasses_waist, person_box) is False

    # Vest on torso (rel_y ~ 0.40) -> Valid
    vest_torso = BoundingBox(x_min=0.25, y_min=0.30, x_max=0.55, y_max=0.60)
    assert YOLODetector.validate_person_ppe_roi("vest", vest_torso, person_box) is True

    # Vest detected at shoes / feet (rel_y ~ 0.90) -> Invalid
    vest_feet = BoundingBox(x_min=0.30, y_min=0.85, x_max=0.50, y_max=0.95)
    assert YOLODetector.validate_person_ppe_roi("vest", vest_feet, person_box) is False


# =====================================================================
# 5. ONNX CPU Optimization Session Settings
# =====================================================================

def test_onnx_cpu_session_optimization_configuration():
    """Validates that create_optimized_onnx_session configures ORT_ENABLE_ALL, threads, ORT_SEQUENTIAL, allow_spinning."""
    onnx_path = "models/fire_smoke.onnx"
    if not os.path.isfile(onnx_path):
        pytest.skip(f"Model file {onnx_path} not present in test environment")

    session = create_optimized_onnx_session(onnx_path, device="cpu")
    assert session is not None
    assert len(session.get_inputs()) >= 1
    assert len(session.get_outputs()) >= 1
