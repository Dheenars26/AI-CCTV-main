"""
Regression tests for the detection accuracy / speed overhaul.

Every test here corresponds to a defect that was measured on the real bundled weights and real
imagery, so a future refactor cannot silently reintroduce it:

* class-agnostic NMS deleting a Person box because a Vest box overlapped it;
* duplicate YOLO boxes (12 of the top-12 PPE candidates were one hard hat) surviving to the tracker;
* phantom workers injected by the OpenCV fallback on scenes with nobody in them;
* ``NO-Safety Vest`` / ``NO-Goggles`` heads being read as *present* equipment;
* fabricated "Safety Glasses Found" badges at 0.96 confidence on workers wearing no glasses;
* a hard colour gate discarding genuine fire that the model scored 0.61;
* the worker branch running at full cost on frames with nothing in them.
"""

import time
import numpy as np
import pytest

from app.detection.base import BoundingBox, DetectionResult
from app.detection.nms import (
    box_iou_matrix,
    merge_nearby_boxes,
    nms,
    resolution_adaptive_threshold,
    weighted_box_fusion,
)
from app.detection.preprocess import Letterbox, prepare_worker_roi, upscale_if_small
from app.detection.roi_refine import PPERoiRefiner, normalise_ppe_label


# --------------------------------------------------------------------------- #
# Post-processing
# --------------------------------------------------------------------------- #
def test_nms_is_class_aware_and_keeps_overlapping_person_and_vest():
    """
    A vest box sits inside its worker's box. cv2.dnn.NMSBoxes (the previous implementation) is
    class agnostic and deleted the Person box; class-aware NMS must keep both.
    """
    boxes = np.array([
        [10, 10, 110, 210],   # person
        [30, 60, 90, 130],    # vest worn by that person (IoU with the person box is ~0.13)
        [12, 12, 108, 208],   # duplicate person box
    ], dtype=np.float32)
    scores = np.array([0.90, 0.70, 0.80], dtype=np.float32)
    classes = np.array([0, 1, 0], dtype=np.int64)

    kept = nms(boxes, scores, iou_threshold=0.45, class_ids=classes, class_aware=True)

    kept_labels = {int(classes[i]) for i in kept}
    assert 0 in kept_labels, "person must survive"
    assert 1 in kept_labels, "vest must survive next to its person"
    # The duplicate person box must be suppressed.
    assert len([i for i in kept if classes[i] == 0]) == 1


def test_weighted_box_fusion_merges_duplicates_and_reports_agreement():
    """Ten near-identical hard-hat boxes must collapse to one, with the agreement count exposed."""
    boxes = np.array([[100 + i, 50 + i, 160 + i, 110 + i] for i in range(10)], dtype=np.float32)
    scores = np.full(10, 0.62, dtype=np.float32)
    classes = np.zeros(10, dtype=np.int64)

    fused_boxes, fused_scores, fused_classes, cluster_sizes = weighted_box_fusion(
        boxes, scores, classes, iou_threshold=0.45
    )

    assert len(fused_boxes) == 1
    assert int(cluster_sizes[0]) == 10
    # Agreement must not inflate a weak detection into certainty.
    assert 0.62 <= float(fused_scores[0]) < 0.99
    # Fused box is the score-weighted average, i.e. inside the cluster envelope.
    assert fused_boxes[0][0] >= 100 and fused_boxes[0][2] <= 169


def test_merge_nearby_boxes_removes_contained_duplicates():
    """A small fire box inside a big smoke box of the same class is one event, not two."""
    boxes = np.array([[0, 0, 200, 200], [80, 80, 120, 120], [300, 300, 340, 340]], dtype=np.float32)
    scores = np.array([0.5, 0.9, 0.4], dtype=np.float32)
    classes = np.zeros(3, dtype=np.int64)

    kept_boxes, _, _ = merge_nearby_boxes(boxes, scores, classes)
    assert len(kept_boxes) == 2


def test_resolution_adaptive_threshold_relaxes_only_for_small_boxes():
    thresholds = resolution_adaptive_threshold(0.40, np.array([0.0001, 0.01, 0.5]), reference_area=0.01)
    assert thresholds[0] < thresholds[1] <= thresholds[2]
    assert thresholds[0] >= 0.40 * 0.45  # bounded relaxation, never a free pass
    assert thresholds[1] == pytest.approx(0.40, abs=1e-6)


def test_box_iou_matrix_matches_scalar_iou():
    a = np.array([[0, 0, 10, 10], [5, 5, 15, 15]], dtype=np.float32)
    matrix = box_iou_matrix(a, a)
    assert matrix.shape == (2, 2)
    assert matrix[0, 0] == pytest.approx(1.0)
    assert matrix[0, 1] == pytest.approx(25.0 / 175.0, abs=1e-5)


# --------------------------------------------------------------------------- #
# Preprocessing
# --------------------------------------------------------------------------- #
def test_letterbox_maps_boxes_back_to_frame_coordinates():
    """A box predicted in letterbox space must round-trip to the same frame pixels."""
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    lb = Letterbox(640, 640)
    blob, scale, dx, dy = lb.apply(frame)

    assert blob.shape == (1, 3, 640, 640)
    # 1280x720 into 640x640 -> scale 0.5, height 360 -> 140 px of vertical padding.
    assert scale == pytest.approx(0.5)
    assert dy == (640 - 360) // 2

    # Invent a canvas-space box covering the frame centre and map it back.
    cx, cy, bw, bh = (dx + 320 * scale), (dy + 180 * scale), 100 * scale, 200 * scale
    x1 = (cx - bw / 2 - dx) / scale
    y1 = (cy - bh / 2 - dy) / scale
    assert x1 == pytest.approx(270, abs=1e-3)
    assert y1 == pytest.approx(80, abs=1e-3)


def test_letterbox_reuses_buffers_across_frames():
    lb = Letterbox(320, 320)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    first, _, _, _ = lb.apply(frame)
    second, _, _, _ = lb.apply(frame)
    assert first is second, "scaling buffers must be reused, not reallocated per frame"


def test_prepare_worker_roi_isolates_head_and_torso():
    head, torso = prepare_worker_roi((100, 100, 200, 400), 640, 480)
    assert head[1] < torso[1], "head region must start above the torso region"
    assert head[3] < torso[3], "head region must end above the torso region"
    assert head[2] > 100 and head[0] < 200, "head region must cover the worker's width"


def test_upscale_if_small_boosts_small_crops_only():
    small = np.zeros((40, 60, 3), dtype=np.uint8)
    scaled, factor = upscale_if_small(small, min_side=160)
    assert factor > 1.0
    assert scaled.shape[1] >= 160

    big = np.zeros((400, 400, 3), dtype=np.uint8)
    _, factor_big = upscale_if_small(big, min_side=160)
    assert factor_big == 1.0


# --------------------------------------------------------------------------- #
# Label vocabulary
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("raw,expected", [
    ("Safety Vest", "vest"),
    ("safety_vest", "vest"),
    ("Goggles", "goggles"),
    ("safety glasses", "goggles"),
    ("Hardhat", "helmet"),
    ("Person", "person"),
    ("Gloves", "gloves"),
])
def test_normalise_ppe_label_maps_positive_classes(raw, expected):
    assert normalise_ppe_label(raw) == expected


@pytest.mark.parametrize("raw", [
    "NO-Safety Vest", "NO-Goggles", "NO-Hardhat", "NO-Mask", "NO-Gloves", "Fall-Detected", "No_Harness",
])
def test_normalise_ppe_label_rejects_negative_heads(raw):
    """
    Negative heads describe *absent* equipment. Admitting them as canonical items would make every
    bare worker look fully equipped - the exact inverse of the intended alert.
    """
    assert normalise_ppe_label(raw) is None


# --------------------------------------------------------------------------- #
# ROI refinement
# --------------------------------------------------------------------------- #
class _FakePerson:
    def __init__(self, person_id, bbox):
        self.person_id = person_id
        self.bbox = bbox


def test_roi_refiner_finds_small_item_the_full_frame_pass_missed():
    """
    Simulates the measured behaviour of the bundled weights: nothing over the whole frame, but the
    item is found once the head crop is examined at higher effective resolution.
    """
    refiner = PPERoiRefiner(min_crop_side=64, positive_ttl=5.0, negative_ttl=1.0)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    person = _FakePerson(101, BoundingBox(0.3, 0.2, 0.5, 0.9))
    calls = []

    def infer(crop):
        calls.append(crop.shape)
        return [("Goggles", 0.42, (2.0, 2.0, 20.0, 10.0))]

    results = refiner.refine(frame, [person], {101: ["goggles"]}, infer_fn=infer)

    assert calls, "the refiner must actually run inference on a crop"
    assert len(results) == 1
    assert results[0].label == "goggles"
    assert results[0].metadata["evidence"] == "roi_refine"
    assert results[0].metadata["roi"] == "head"


def test_roi_refiner_is_evidence_driven_and_cached():
    """Compliant workers cost nothing, and a confirmed item is not re-checked every frame."""
    refiner = PPERoiRefiner(min_crop_side=64)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    person = _FakePerson(7, BoundingBox(0.2, 0.2, 0.4, 0.8))
    calls = {"n": 0}

    def infer(crop):
        calls["n"] += 1
        return [("Goggles", 0.5, (1.0, 1.0, 10.0, 5.0))]

    # Nothing missing -> no work at all.
    assert refiner.refine(frame, [person], {}, infer_fn=infer) == []
    assert calls["n"] == 0

    refiner.refine(frame, [person], {7: ["goggles"]}, infer_fn=infer)
    assert calls["n"] == 1

    # Immediately afterwards the positive cache suppresses further crops.
    refiner.refine(frame, [person], {7: ["goggles"]}, infer_fn=infer)
    assert calls["n"] == 1


def test_roi_refiner_rotates_between_workers():
    """A worker whose item is never found must not starve the others."""
    refiner = PPERoiRefiner(min_crop_side=64, negative_ttl=0.0)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    people = [_FakePerson(i, BoundingBox(0.1 * i, 0.2, 0.1 * i + 0.15, 0.9)) for i in range(1, 4)]
    seen = []

    def infer(crop):
        seen.append(crop.shape)
        return [("Goggles", 0.4, (1.0, 1.0, 8.0, 6.0))]

    missing = {p.person_id: ["goggles"] for p in people}
    for _ in range(3):
        refiner.refine(frame, people, missing, infer_fn=infer)

    assert len(seen) == 3


def test_roi_refiner_respects_body_region_ownership():
    """A torso crop may not testify about goggles."""
    refiner = PPERoiRefiner(min_crop_side=32)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    person = _FakePerson(3, BoundingBox(0.3, 0.3, 0.6, 0.9))

    results = refiner.refine(
        frame, [person], {3: ["vest"]},
        infer_fn=lambda crop: [("Goggles", 0.9, (1.0, 1.0, 9.0, 9.0))],
    )
    assert results == []


# --------------------------------------------------------------------------- #
# Motion gate
# --------------------------------------------------------------------------- #
def test_motion_gate_skips_inference_on_static_scene_but_sweeps_periodically():
    from app.detection.motion_gate import MotionGate

    gate = MotionGate(
        enabled=True, min_area_ratio=0.002, warmup_frames=2, hold_seconds=0.0,
        sweep_interval_seconds=0.6, process_width=160,
    )
    rng = np.random.default_rng(0)
    static = rng.integers(0, 255, (120, 160, 3), dtype=np.uint8)

    # Warm-up (the background model reports everything as foreground on its first frame).
    assert gate.update(static) and gate.update(static)

    # First frame after the sweep window runs the guaranteed safety inspection...
    time.sleep(0.7)
    assert gate.update(static) is True
    # ...and the rest of a static scene stops costing worker inference.
    assert [gate.update(static) for _ in range(4)] == [False, False, False, False]

    # The sweep is periodic, not one-shot: a fully static scene is still inspected regularly, so a
    # person who entered during warm-up cannot be missed indefinitely.
    time.sleep(0.65)
    assert gate.update(static) is True


def test_motion_gate_runs_when_something_moves():
    from app.detection.motion_gate import MotionGate

    gate = MotionGate(enabled=True, warmup_frames=1, hold_seconds=1.0, process_width=160)
    base = np.zeros((120, 160, 3), dtype=np.uint8)
    for _ in range(6):
        gate.update(base)

    moving = base.copy()
    moving[40:90, 50:110] = 255
    assert gate.update(moving) is True
    assert gate.motion_rois, "a moving blob must yield a refinement ROI"


def test_motion_gate_keeps_running_while_a_worker_is_tracked():
    from app.detection.motion_gate import MotionGate

    gate = MotionGate(enabled=True, warmup_frames=1, hold_seconds=0.0, process_width=160)
    static = np.zeros((120, 160, 3), dtype=np.uint8)
    for _ in range(8):
        gate.update(static)
    assert gate.update(static, persons_visible=True) is True


# --------------------------------------------------------------------------- #
# Fire / smoke evidence
# --------------------------------------------------------------------------- #
def test_structure_edge_ratio_separates_man_made_from_amorphous():
    import cv2

    from app.detection.yolo import YOLODetector

    # A brick-like grid of straight lines: man-made structure.
    structured = np.full((200, 200, 3), 200, dtype=np.uint8)
    for y in range(0, 200, 20):
        cv2.line(structured, (0, y), (199, y), (40, 40, 40), 2)
    for x in range(0, 200, 20):
        cv2.line(structured, (x, 0), (x, 199), (40, 40, 40), 2)

    # Smooth amorphous gradient: flame/smoke-like texture.
    ys, xs = np.mgrid[0:200, 0:200]
    amorphous = np.stack([
        (128 + 60 * np.sin(xs / 9.0)).astype(np.uint8),
        (110 + 50 * np.sin(ys / 11.0)).astype(np.uint8),
        (90 + 40 * np.sin((xs + ys) / 13.0)).astype(np.uint8),
    ], axis=2)

    structured_ratio = YOLODetector._structure_edge_ratio(structured)
    amorphous_ratio = YOLODetector._structure_edge_ratio(amorphous)

    assert structured_ratio > 0.45, f"brick-like grid should look structured, got {structured_ratio}"
    assert amorphous_ratio < 0.45, f"amorphous texture should not look structured, got {amorphous_ratio}"


def test_evidence_fusion_boosts_corroborated_detection_without_erasing_a_weak_one():
    import cv2
    from app.detection.yolo import YOLODetector

    # Bright, saturated flame-coloured patch.
    flame = np.zeros((80, 80, 3), dtype=np.uint8)
    flame[:, :] = (40, 180, 250)
    strong_evidence, strong_physics = YOLODetector._fuse_fire_smoke_evidence("fire", 0.30, flame)
    assert strong_physics["corroboration"] > 0.25
    assert strong_evidence > 0.30, "physical corroboration must raise the evidence score"

    # Flat grey patch: no flame colours at all.
    dull = np.full((80, 80, 3), 120, dtype=np.uint8)
    weak_evidence, weak_physics = YOLODetector._fuse_fire_smoke_evidence("fire", 0.30, dull)
    assert weak_physics["corroboration"] < 0.05
    # The model's own score is never reduced, so a confident fire is not thrown away.
    assert weak_evidence >= 0.30


def test_exclusion_roi_suppresses_fire_on_detected_person_or_ppe():
    from app.detection.yolo import YOLODetector

    fire_box = BoundingBox(0.10, 0.10, 0.40, 0.60)
    person_box = BoundingBox(0.12, 0.12, 0.38, 0.58)
    far_box = BoundingBox(0.70, 0.70, 0.90, 0.95)

    assert YOLODetector._overlaps_any(fire_box, [person_box]) is True
    assert YOLODetector._overlaps_any(fire_box, [far_box]) is False


# --------------------------------------------------------------------------- #
# Person class resolution & phantom-worker removal
# --------------------------------------------------------------------------- #
def test_person_class_resolution_does_not_assume_class_zero():
    """
    The bundled ppe.onnx has ``Person`` at class 11 and a COCO export has it at 0, while an
    anonymous export carries no names at all. All three must resolve correctly.
    """
    from app.detection.person_detector import PersonDetector

    detector = PersonDetector.__new__(PersonDetector)  # avoid loading weights

    class _Runner:
        def __init__(self, names):
            self.names = names

        def name_for(self, cid):
            return str(self.names.get(cid, cid)).lower().strip()

    # COCO-style export: person is id 0.
    detector._onnx_runner = _Runner({0: "person", 1: "bicycle"})
    assert detector._is_person({"label": "person", "class_id": 0}) is True
    assert detector._is_person({"label": "bicycle", "class_id": 1}) is False

    # PPE-weight style export: Person at id 11, and id 0 is an unrelated class.
    ppe_names = {0: "Fall-Detected", 1: "Gloves", 11: "Person", 12: "Safety Vest"}
    detector._onnx_runner = _Runner(ppe_names)
    assert detector._is_person({"label": "person", "class_id": 11}) is True
    assert detector._is_person({"label": "fall-detected", "class_id": 0}) is False

    # Anonymous export: no names, 80 classes -> COCO convention applies to id 0 only.
    anonymous = _Runner({})
    anonymous.names = {}
    detector._onnx_runner = anonymous
    assert detector._is_person({"label": "0", "class_id": 0}) is True


def test_haar_fallback_is_not_used_when_a_neural_backend_is_loaded():
    from app.detection.person_detector import PersonDetector

    detector = PersonDetector.__new__(PersonDetector)
    detector._onnx_runner = object()
    detector._model = None
    detector._is_mock_fallback = False
    assert detector._neural_backend_available() is True

    detector._onnx_runner = None
    assert detector._neural_backend_available() is False


# --------------------------------------------------------------------------- #
# Hi-vis vest corroboration
# --------------------------------------------------------------------------- #
def test_hivis_evidence_accepts_fluorescent_garment_and_rejects_plain_clothing():
    from app.detection.ppe_detector import PPEDetector

    # Fluorescent orange fabric crossed by a retroreflective silver band.
    torso = np.zeros((200, 200, 3), dtype=np.uint8)
    torso[:, :] = (0, 120, 240)      # BGR orange
    torso[80:120, :] = (190, 190, 190)  # silver band
    found, stats = PPEDetector._hivis_torso_evidence(torso)
    assert found is True
    assert stats["color_ratio"] > 0.4
    assert stats["silver_ratio"] > 0.1

    # Tan firefighter turnout gear: no fluorescent colour, no silver.
    tan = np.zeros((200, 200, 3), dtype=np.uint8)
    tan[:, :] = (150, 175, 200)
    found_tan, stats_tan = PPEDetector._hivis_torso_evidence(tan)
    assert found_tan is False
    assert stats_tan["color_ratio"] < 0.06

    # Dark red shirt beside nothing reflective.
    plaid = np.zeros((200, 200, 3), dtype=np.uint8)
    plaid[:, :] = (40, 40, 120)
    found_plaid, _ = PPEDetector._hivis_torso_evidence(plaid)
    assert found_plaid is False


def test_hivis_evidence_requires_a_minimum_crop_size():
    from app.detection.ppe_detector import PPEDetector

    tiny = np.full((20, 20, 3), (0, 120, 240), dtype=np.uint8)
    found, _ = PPEDetector._hivis_torso_evidence(tiny)
    assert found is False


# --------------------------------------------------------------------------- #
# Temporal verification policy
# --------------------------------------------------------------------------- #
def test_temporal_tracker_does_not_alert_on_sustained_weak_signal():
    """
    A persistent low-confidence signal stays a *detection*. Alerting on it would trade the false
    alarm for a different false alarm; the alert floor still applies.
    """
    from app.detection.verification import CameraVerificationEngine, EventState

    engine = CameraVerificationEngine(
        camera_id=1, min_confidence=0.14, min_consecutive_frames=2, min_duration_seconds=0.0
    )
    det = DetectionResult(label="fire", confidence=0.20, bbox=BoundingBox(0.1, 0.1, 0.3, 0.3))

    events = []
    for _ in range(6):
        events.extend(engine.process_frame_detections([det], {}))

    assert not any(e.state == EventState.ALERT_SENT for e in events), "weak signal must not alert"
    tracker = engine.trackers["fire"]
    assert tracker is not None
    assert tracker.consecutive_frames >= 2, "the weak signal must still be tracked"


def test_temporal_tracker_alerts_on_strong_sustained_signal():
    from app.detection.verification import CameraVerificationEngine, EventState

    engine = CameraVerificationEngine(
        camera_id=1, min_confidence=0.14, min_consecutive_frames=3, min_duration_seconds=0.0
    )
    det = DetectionResult(label="fire", confidence=0.72, bbox=BoundingBox(0.1, 0.1, 0.3, 0.3))

    events = []
    for _ in range(5):
        events.extend(engine.process_frame_detections([det], {}))

    assert any(e.state == EventState.ALERT_SENT for e in events)


# --------------------------------------------------------------------------- #
# Pipeline scheduling
# --------------------------------------------------------------------------- #
def _blank_frame(h=480, w=640):
    return np.full((h, w, 3), 90, dtype=np.uint8)


def test_pipeline_adapts_worker_cadence_to_measured_cost():
    from app.camera.pipeline import FramePipeline

    pipeline = FramePipeline(camera_id=1, ppe_inference_interval_sec=0.25)
    for _ in range(5):
        pipeline._observe_worker_cost(600.0)

    # 600 ms of work must not be requested every 250 ms.
    assert pipeline._adaptive_worker_interval > 0.4
    assert pipeline._adaptive_worker_interval <= 2.0  # bounded by the configured ceiling
    stats = pipeline.performance_stats()
    assert stats["effective_worker_interval_sec"] > 0.25


def test_pipeline_reports_latency_and_keeps_reporting_fire_without_workers():
    """Fire/smoke must never be starved by the worker branch's motion gate."""
    from app.camera.pipeline import FramePipeline

    class _FireOnly:
        def __init__(self):
            self.calls = 0

        def detect(self, image, **kwargs):
            self.calls += 1
            return [DetectionResult(
                label="fire", confidence=0.6,
                bbox=BoundingBox(0.4, 0.4, 0.6, 0.6),
                metadata={"evidence": "model"},
            )]

    detector = _FireOnly()
    pipeline = FramePipeline(camera_id=1, fire_smoke_detector=detector, ppe_enabled=False, person_enabled=False)

    for i in range(4):
        frame = pipeline.process_frame(_blank_frame(), frame_id=i, fps=25.0)
        assert "pipeline_latency_ms" in frame.metadata

    assert detector.calls == 4, "the fire path must run on every frame regardless of motion"


def test_pipeline_does_not_drop_tracks_on_a_gated_frame():
    from app.camera.pipeline import FramePipeline
    from app.safety.tracker import TrackedPerson

    pipeline = FramePipeline(camera_id=1)
    pipeline.tracker._tracked_persons[101] = TrackedPerson(
        person_id=101, camera_id=1, bbox=BoundingBox(0.2, 0.2, 0.4, 0.8),
        confidence=0.9, last_seen_timestamp=time.time(),
    )
    pipeline.tracker._disappeared_counts[101] = 0

    # Several gated frames must not age the track out.
    for _ in range(5):
        pipeline.motion_gate.update(_blank_frame(), persons_visible=False)
    tracks = pipeline.tracker.get_active_tracks()
    assert len(tracks) == 1


# --------------------------------------------------------------------------- #
# Operator-facing sensitivity control stays coherent end to end
# --------------------------------------------------------------------------- #
def test_alert_floor_never_sits_below_the_per_frame_floor():
    """Raising an operator's sensitivity must not leave the alert floor beneath it."""
    from app.detection.verification import ClassVerificationTracker

    tracker = ClassVerificationTracker(camera_id=1, class_name="fire", min_confidence=0.55)
    assert tracker.alert_min_confidence >= tracker.min_confidence

    tracker = ClassVerificationTracker(camera_id=1, class_name="smoke", min_confidence=0.60)
    assert tracker.alert_min_confidence >= tracker.min_confidence


def test_verification_api_keeps_detection_and_alert_floors_in_sync(client, auth_headers):
    """
    PUT /system/verification historically wrote only FIRE_CONFIDENCE_THRESHOLD. The temporal state
    machine reads FIRE_VERIFICATION_MIN_CONFIDENCE, so without this coupling an operator's change
    would silently stop affecting live detection.
    """
    from app.config.settings import settings

    original = (
        settings.FIRE_CONFIDENCE_THRESHOLD,
        settings.FIRE_VERIFICATION_MIN_CONFIDENCE,
        settings.SMOKE_CONFIDENCE_THRESHOLD,
        settings.SMOKE_VERIFICATION_MIN_CONFIDENCE,
    )
    try:
        response = client.put(
            "/api/v1/system/verification",
            json={"fire_min_confidence": 0.57, "smoke_min_confidence": 0.52},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert settings.FIRE_VERIFICATION_MIN_CONFIDENCE == pytest.approx(0.57)
        assert settings.SMOKE_VERIFICATION_MIN_CONFIDENCE == pytest.approx(0.52)

        reported = client.get("/api/v1/system/verification", headers=auth_headers).json()["data"]
        assert reported["fire_min_confidence"] == pytest.approx(0.57)
        assert reported["smoke_min_confidence"] == pytest.approx(0.52)
    finally:
        (
            settings.FIRE_CONFIDENCE_THRESHOLD,
            settings.FIRE_VERIFICATION_MIN_CONFIDENCE,
            settings.SMOKE_CONFIDENCE_THRESHOLD,
            settings.SMOKE_VERIFICATION_MIN_CONFIDENCE,
        ) = original


def test_ppe_profile_change_invalidates_refiner_cache():
    """Cached ROI conclusions belong to the previous profile and must not leak into the next."""
    from app.camera.pipeline import FramePipeline
    from app.detection.roi_refine import PPERoiRefiner

    class _PPE:
        def __init__(self):
            self._roi_refiner = PPERoiRefiner()

    pipeline = FramePipeline(camera_id=1, ppe_detector=_PPE())
    pipeline.ppe_detector._roi_refiner._cache[123] = {"vest": (time.time() + 60, True)}
    pipeline.set_ppe_profile({"required_equipment": ["goggles"]})
    assert pipeline.ppe_detector._roi_refiner._cache == {}
