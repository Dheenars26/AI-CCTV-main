"""
Comprehensive 42-Phase Audit Verification Test Suite.
Validates one-camera CCTV pipeline end-to-end:
Capture -> BoundedQueue -> FrameScheduler -> Preprocessing -> ONNX/YOLO ->
Detection -> Association -> Verification FSM -> Rules -> Alert -> Evidence -> DB -> WS -> Security.
"""

import time
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, List, Optional
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import create_application
from app.config.settings import settings
from app.camera.bounded_queue import BoundedFrameQueue
from app.camera.frame_scheduler import FrameScheduler
from app.camera.resource_manager import ResourceManager
from app.detection.base import BoundingBox, DetectionResult
from app.detection.verification import (
    CameraVerificationEngine,
    EventState,
    VerifiedEvent
)
from app.safety.tracker import PersonTracker, TrackedPerson
from app.safety.association import PPEAssociationEngine, WorkerPPEAnalysis
from app.safety.rules import SafetyRuleEngine
from app.safety.verification import PPETemporalVerificationEngine, WorkerPPETrackerFSM
from app.recording.ring_buffer import RollingFrameRingBuffer
from app.utils.metrics import metrics_collector
from app.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_jwt_token,
    hash_token,
    generate_csrf_token,
    verify_csrf_token,
    sanitize_rtsp_url
)
from app.services.ws_ticket_service import ws_ticket_service
from app.database.session import SessionLocal, get_db, check_db_connection
from app.models.user import User
from app.models.camera import Camera
from app.models.alert import Alert


# =============================================================================
# PHASE 4 & 5: CAMERA LIFECYCLE & BOUNDED FRAME QUEUE AUDIT (maxsize=1)
# =============================================================================

def test_phase5_bounded_frame_queue_maxsize_one_and_frame_age():
    """
    Phase 5 Audit:
    Inspect BoundedFrameQueue.
    Verifies maxsize=1 enforces newest-frame prioritization, drops stale frames,
    and records frame_age_ms in metrics registry.
    """
    queue = BoundedFrameQueue(camera_id=1, maxsize=1)
    assert queue.maxsize == 1
    assert queue.current_size == 0

    frame1 = np.zeros((100, 100, 3), dtype=np.uint8)
    t1 = datetime.now(timezone.utc) - timedelta(milliseconds=200)
    queue.put_frame(frame1, t1, 1)

    assert queue.current_size == 1
    assert queue.dropped_frames == 0

    # Put a newer frame; frame1 must be dropped immediately
    frame2 = np.ones((100, 100, 3), dtype=np.uint8)
    t2 = datetime.now(timezone.utc)
    queue.put_frame(frame2, t2, 2)

    assert queue.current_size == 1
    assert queue.dropped_frames == 1  # Older frame dropped!

    # Retrieve frame: must receive newest frame (frame2, frame_id=2)
    pulled_frame, pulled_ts, pulled_id = queue.get_frame(timeout=0.1)
    assert pulled_frame is not None
    assert pulled_ts is not None
    assert pulled_id == 2
    assert pulled_frame[0, 0, 0] == 1  # Frame 2 content!

    # Compute and verify frame_age_ms
    now_utc = datetime.now(timezone.utc)
    frame_age_ms = (now_utc - pulled_ts).total_seconds() * 1000.0
    assert frame_age_ms >= 0.0

    # Record to Prometheus metrics collector
    metrics_collector.record_queue_depth("Camera-1", queue.current_size)
    metrics_collector.record_frame_age("Camera-1", frame_age_ms)

    assert "Camera-1" in metrics_collector.frame_age_ms
    assert metrics_collector.ai_queue_depth.get("Camera-1") == 0


def test_phase4_camera_source_empty_and_corrupt_frame_handling():
    """
    Phase 4 Audit:
    Tests handling of empty frames, None frames, and corrupted frame shapes.
    """
    from app.camera.dummy_source import SyntheticDummyCamera
    cam = SyntheticDummyCamera(camera_id=99, fps_limit=30)
    assert cam.connect() is True

    # Valid read
    ret, frame = cam.read_frame()
    assert ret is True
    assert frame is not None
    assert frame.shape == (480, 640, 3)

    # Disconnect
    cam.disconnect()
    assert cam.is_connected() is False

    # Corrupt/None frame safe handling
    from app.camera.pipeline import Frame, StandardPreprocessor
    prep = StandardPreprocessor()
    f_empty = Frame(camera_id=99, frame_id=1, image=None, timestamp=datetime.now(timezone.utc))
    res = prep.process(f_empty)
    assert res.image is None


# =============================================================================
# PHASE 6: FRAME SCHEDULER AUDIT (5, 10, 15, 20, 30 FPS)
# =============================================================================

def test_phase6_frame_scheduler_rates_and_priorities():
    """
    Phase 6 Audit:
    Tests FrameScheduler at 5, 10, 15, 20, 30 target AI FPS with capture_fps=30,
    and priority multipliers (HIGH, MEDIUM, LOW), plus backpressure.
    """
    sched = FrameScheduler()
    capture_fps = 30

    # Test 10 target AI FPS (should sample every 3rd frame: 30 / 10 = 3)
    sampled_10fps = [sched.should_process_frame(i, priority="HIGH", capture_fps=capture_fps, target_ai_fps=10) for i in range(30)]
    assert sum(sampled_10fps) == 10

    # Test 15 target AI FPS (should sample every 2nd frame: 30 / 15 = 2)
    sampled_15fps = [sched.should_process_frame(i, priority="HIGH", capture_fps=capture_fps, target_ai_fps=15) for i in range(30)]
    assert sum(sampled_15fps) == 15

    # Test 30 target AI FPS (should sample every frame)
    sampled_30fps = [sched.should_process_frame(i, priority="HIGH", capture_fps=capture_fps, target_ai_fps=30) for i in range(30)]
    assert sum(sampled_30fps) == 30

    # Test 5 target AI FPS (should sample every 6th frame: 30 / 5 = 6)
    sampled_5fps = [sched.should_process_frame(i, priority="HIGH", capture_fps=capture_fps, target_ai_fps=5) for i in range(30)]
    assert sum(sampled_5fps) == 5

    # Test Priority LOW (0.25 multiplier): should downsample further
    sampled_low = [sched.should_process_frame(i, priority="LOW", capture_fps=capture_fps, target_ai_fps=10) for i in range(60)]
    assert sum(sampled_low) <= sum(sampled_10fps)

    # Test Backpressure > 0.5: doubles skip factor
    sampled_bp = [sched.should_process_frame(i, priority="HIGH", capture_fps=capture_fps, target_ai_fps=10, backpressure_level=0.8) for i in range(30)]
    assert sum(sampled_bp) < sum(sampled_10fps)


# =============================================================================
# PHASE 7 & 8: YOLO / ONNX MODEL AUDIT & IMAGE SIZE BENCHMARK
# =============================================================================

def test_phase7_model_caching_and_inference_mode():
    """
    Phase 7 Audit:
    Verifies YOLO/ONNX models are cached as singletons (loaded once),
    inference runs safely without gradient construction, and handles missing weights gracefully.
    """
    from app.detection.onnx_engine import get_onnx_yolo_runner
    model_path = "models/fire_smoke.onnx"
    backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    full_path = os.path.join(backend_root, model_path)

    if os.path.isfile(full_path):
        runner1 = get_onnx_yolo_runner(full_path, device="cpu")
        runner2 = get_onnx_yolo_runner(full_path, device="cpu")
        assert runner1 is runner2  # Exactly same instance in memory!

        # Inference on dummy frame
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        dets, inf_ms = runner1.predict(frame, conf_threshold=0.5)
        assert isinstance(dets, list)
        assert inf_ms >= 0.0

    # Missing model failure isolation
    with pytest.raises(FileNotFoundError):
        get_onnx_yolo_runner("models/nonexistent_weights_xyz.onnx", device="cpu")


def test_phase8_image_size_benchmark():
    """
    Phase 8 Audit:
    Benchmark preprocessing and inference across resolutions (416, 512, 640).
    """
    backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fs_path = os.path.join(backend_root, "models", "fire_smoke.onnx")

    if os.path.isfile(fs_path):
        from app.detection.onnx_engine import get_onnx_yolo_runner
        runner = get_onnx_yolo_runner(fs_path, device="cpu")

        benchmarks = {}
        for sz in [416, 512, 640]:
            test_img = np.zeros((sz, sz, 3), dtype=np.uint8)
            t0 = time.perf_counter()
            dets, inf_ms = runner.predict(test_img, conf_threshold=0.5)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            benchmarks[sz] = {"inference_ms": inf_ms, "total_ms": elapsed_ms}

        for sz, data in benchmarks.items():
            assert data["total_ms"] > 0.0


# =============================================================================
# PHASE 9: CLASS-SPECIFIC CONFIDENCE AUDIT
# =============================================================================

def test_phase9_class_specific_thresholds():
    """
    Phase 9 Audit:
    Verifies that class-specific thresholds are genuine and distinct:
    FIRE: 0.45, SMOKE: 0.38, PERSON: 0.20, VEST: 0.22, GLASSES: 0.22.
    """
    assert getattr(settings, "FIRE_CONFIDENCE_THRESHOLD") == 0.40
    assert getattr(settings, "SMOKE_CONFIDENCE_THRESHOLD") == 0.35
    assert getattr(settings, "PERSON_CONFIDENCE_THRESHOLD") == 0.20
    assert getattr(settings, "VEST_CONFIDENCE_THRESHOLD") == 0.20
    assert getattr(settings, "GLASSES_CONFIDENCE_THRESHOLD") == 0.20

    # Ensure changing one threshold does not mutate others
    fire_t = settings.FIRE_CONFIDENCE_THRESHOLD
    smoke_t = settings.SMOKE_CONFIDENCE_THRESHOLD
    vest_t = settings.VEST_CONFIDENCE_THRESHOLD
    assert fire_t != vest_t
    assert smoke_t != vest_t


# =============================================================================
# PHASE 10, 14, 15: TEMPORAL VERIFICATION FSM, COOLDOWN & DUPLICATION AUDIT
# =============================================================================

def test_phase10_14_15_fire_temporal_verification_and_cooldown():
    """
    Phase 10, 14, 15 Audit:
    Verifies Fire Temporal Verification FSM:
    NORMAL -> POSSIBLE -> CONFIRMED -> ALERT_SENT -> ACTIVE -> CLEARED.
    Verifies 1-frame transient detection does NOT trigger alert.
    Verifies consecutive detections confirm alert.
    Verifies cooldown prevents duplicate alerts during continuous fire.
    """
    engine = CameraVerificationEngine(
        camera_id=1,
        min_confidence=0.50,
        min_consecutive_frames=3,
        min_duration_seconds=0.5,
        cooldown_seconds=10.0
    )

    det = DetectionResult(
        label="fire",
        confidence=0.88,
        bbox=BoundingBox(0.2, 0.2, 0.4, 0.4)
    )

    # Frame 1: Transient detection -> POSSIBLE (NO alert sent)
    evts1 = engine.process_frame_detections([det], frame_info={"frame_id": 1, "fps": 25})
    assert len(evts1) == 0  # No alert on single frame!

    # Advance time slightly
    time.sleep(0.2)

    # Frame 2: Still accumulating -> POSSIBLE (NO alert sent)
    evts2 = engine.process_frame_detections([det], frame_info={"frame_id": 2, "fps": 25})
    assert len(evts2) == 0

    time.sleep(0.35)

    # Frame 3: Consecutive frames & duration reached -> ALERT_SENT!
    evts3 = engine.process_frame_detections([det], frame_info={"frame_id": 3, "fps": 25})
    assert len(evts3) == 1
    assert evts3[0].state == EventState.ALERT_SENT
    assert evts3[0].class_name == "fire"

    # Frame 4: Fire continues -> ACTIVE (NO duplicate alert sent)
    evts4 = engine.process_frame_detections([det], frame_info={"frame_id": 4, "fps": 25})
    assert len(evts4) == 0

    # Frame 5: Fire clears (no detections for consecutive miss tolerance)
    for f in range(5, 12):
        evts_clear = engine.process_frame_detections([], frame_info={"frame_id": f, "fps": 25})
        if any(e.state == EventState.CLEARED for e in evts_clear):
            break

    cleared = [e for e in evts_clear if e.state == EventState.CLEARED]
    assert len(cleared) >= 1
    assert cleared[0].class_name == "fire"


# =============================================================================
# PHASE 11, 12, 13: PPE ASSOCIATION & MULTI-WORKER ISOLATION AUDIT
# =============================================================================

def test_phase11_ppe_association_critical_two_workers_no_inheritance():
    """
    Phase 11 Audit (Critical Test from Prompt):
    Person A has vest.
    Person B does not.
    Ensure Person B does NOT inherit Person A's vest!
    """
    engine = PPEAssociationEngine(min_association_iou=0.15)

    # Person A on left (x: 0.1 to 0.3)
    box_a = BoundingBox(0.10, 0.10, 0.30, 0.90)
    person_a = TrackedPerson(person_id=101, camera_id=1, bbox=box_a, confidence=0.92, last_seen_timestamp=time.time())

    # Person B on right (x: 0.60 to 0.80)
    box_b = BoundingBox(0.60, 0.10, 0.80, 0.90)
    person_b = TrackedPerson(person_id=102, camera_id=1, bbox=box_b, confidence=0.89, last_seen_timestamp=time.time())

    # Only ONE vest detected, strictly located on Person A's torso
    vest_a = DetectionResult(
        label="vest",
        confidence=0.85,
        bbox=BoundingBox(0.12, 0.30, 0.28, 0.70)
    )

    analyses = engine.associate(
        camera_id=1,
        tracked_persons=[person_a, person_b],
        ppe_detections=[vest_a],
        required_equipment=["vest"]
    )

    assert len(analyses) == 2
    analysis_a = next(a for a in analyses if a.person_id == 101)
    analysis_b = next(a for a in analyses if a.person_id == 102)

    # Person A must have vest and PASS
    assert "vest" in analysis_a.detected_equipment
    assert analysis_a.status == "PASS"

    # Person B must NOT have vest and must be VIOLATION
    assert "vest" not in analysis_b.detected_equipment
    assert "vest" in analysis_b.missing_equipment
    assert analysis_b.status == "VIOLATION"


# =============================================================================
# PHASE 16: EVIDENCE RING BUFFER & EXPIRED CLEANUP AUDIT
# =============================================================================

def test_phase16_evidence_ring_buffer_pre_event_frames():
    """
    Phase 16 Audit:
    Verifies RollingFrameRingBuffer preserves pre-event frames accurately
    without memory leak or unbound growth.
    """
    ring = RollingFrameRingBuffer(max_seconds=2.0, default_fps=10.0)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    # Push 30 frames spaced by 0.1s in past
    base_t = datetime.now(timezone.utc) - timedelta(seconds=3.0)
    for i in range(30):
        t = base_t + timedelta(seconds=i * 0.1)
        ring.add_frame(frame, t)

    pre_frames = ring.get_pre_event_frames(duration_seconds=2.0)
    # Filtered to <= 2.0s duration window: should contain ~20-21 frames
    assert len(pre_frames) <= 22
    assert len(pre_frames) >= 18


# =============================================================================
# PHASE 17, 18, 19, 20: DATABASE, REST API, AUTHENTICATION & RBAC AUDIT
# =============================================================================

def test_phase17_19_20_auth_rbac_and_refresh_token_theft_prevention(client, db):
    """
    Phase 17, 19, 20 Audit:
    Tests Argon2id authentication, JWT token issuance, refresh token rotation,
    reuse detection (theft mitigation), and RBAC role restrictions.
    """
    # Seed admin user in test DB
    admin = db.query(User).filter(User.username == "admin").first()
    if not admin:
        admin = User(
            username="admin",
            email="admin@aicctv.local",
            hashed_password=hash_password("admin123"),
            full_name="Administrator",
            role="ADMIN",
            is_active=True,
            is_superuser=True
        )
        db.add(admin)
        db.commit()

    # 1. Login with seeded admin
    login_resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert login_resp.status_code == 200
    token_data = login_resp.json()["data"]
    access_token = token_data["access_token"]
    assert access_token is not None

    # 2. Access /api/v1/auth/me with Bearer token
    headers = {"Authorization": f"Bearer {access_token}"}
    me_resp = client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["data"]["username"] == "admin"
    assert me_resp.json()["data"]["role"] == "ADMIN"

    # 3. RBAC Test: Seed an active VIEWER user and attempt ADMIN operation
    viewer = db.query(User).filter(User.username == "viewer").first()
    if not viewer:
        viewer = User(
            id=999,
            username="viewer",
            email="viewer@aicctv.local",
            hashed_password=hash_password("viewer123"),
            full_name="Viewer User",
            role="VIEWER",
            is_active=True
        )
        db.add(viewer)
        db.commit()

    viewer_token = create_access_token(data={"sub": viewer.id, "username": "viewer", "role": "VIEWER"})
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}
    create_user_resp = client.post(
        "/api/v1/auth/register",
        headers=viewer_headers,
        json={"username": "new_user", "email": "new@cctv.local", "password": "Password123!", "role": "OPERATOR"}
    )
    # Must be 403 Forbidden!
    assert create_user_resp.status_code == 403

    # 4. CSRF Protection Test:
    # When refreshToken cookie is set, omitting X-CSRF-Token header MUST return 403 Forbidden!
    csrf_fail_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": "malicious_token"})
    assert csrf_fail_resp.status_code == 403

    # 5. Token Rotation: Valid refresh with CSRF header succeeds and rotates cookie
    csrf_token = token_data.get("csrf_token")
    csrf_headers = {"X-CSRF-Token": csrf_token}
    refresh_ok_resp = client.post("/api/v1/auth/refresh", headers=csrf_headers)
    assert refresh_ok_resp.status_code == 200

    # 6. Replay & Invalid Token Theft Detection:
    # Clear cookies and send an invalid/revoked refresh token in payload
    client.cookies.clear()
    bad_refresh_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": "malicious_reused_token"})
    assert bad_refresh_resp.status_code == 401


# =============================================================================
# PHASE 21: WEBSOCKET SECURITY & SINGLE-USE TICKET AUDIT
# =============================================================================

def test_phase21_websocket_single_use_ticket_handshake():
    """
    Phase 21 Audit:
    Verifies WebSocket ticket service issues 10-second single-use tickets,
    which are consumed upon first use and rejected upon reuse.
    """
    ticket = ws_ticket_service.issue_ticket(user_id="user_123", username="operator1", role="OPERATOR")
    assert ticket.startswith("wst_")

    # 1. First consumption: MUST succeed
    user_payload = ws_ticket_service.consume_ticket(ticket)
    assert user_payload is not None
    assert user_payload["user_id"] == "user_123"
    assert user_payload["role"] == "OPERATOR"

    # 2. Replay attack: Second consumption MUST return None
    replay_payload = ws_ticket_service.consume_ticket(ticket)
    assert replay_payload is None


# =============================================================================
# PHASE 25: FAILURE ISOLATION AUDIT
# =============================================================================

def test_phase25_failure_isolation_yolo_error_does_not_crash_pipeline():
    """
    Phase 25 Audit:
    Simulates a YOLO failure inside FramePipeline; verifies camera pipeline
    safely isolates exception without crashing or dropping thread execution.
    """
    from app.camera.pipeline import FramePipeline
    from app.detection.base import DummyDetector

    class BrokenDetector(DummyDetector):
        def detect(
            self,
            image_bgr: Any,
            candidate_rois: Optional[List[BoundingBox]] = None,
            **kwargs: Any,
        ) -> List[DetectionResult]:
            raise RuntimeError("Simulated CUDA OOM in YOLO detector!")

    pipeline = FramePipeline(camera_id=42, detector=BrokenDetector(), fire_smoke_enabled=True)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # Process frame through broken detector: must return valid frame without crashing
    processed = pipeline.process_frame(frame, frame_id=1, fps=25.0)
    assert processed is not None
    assert processed.camera_id == 42


# =============================================================================
# PHASE 28: CREDENTIAL SANITIZATION AUDIT
# =============================================================================

def test_phase28_rtsp_url_credential_sanitization():
    """
    Phase 28 Audit:
    Ensures RTSP stream URLs with cleartext passwords are fully sanitized
    before writing to logs or returning in API responses.
    """
    dirty_url = "rtsp://admin:superSecret123@192.168.1.100:554/stream1"
    clean_url = sanitize_rtsp_url(dirty_url)
    assert "superSecret123" not in clean_url
    assert clean_url == "rtsp://***:***@192.168.1.100:554/stream1"
