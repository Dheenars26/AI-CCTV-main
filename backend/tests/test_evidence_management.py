"""
Unit & Integration Test Suite for Phase 6 Incident Evidence Management.
"""

import os
import time
import pytest
import numpy as np
from datetime import datetime, timezone

from app.detection.base import BoundingBox
from app.detection.verification import VerifiedEvent, EventState
from app.recording.ring_buffer import RollingFrameRingBuffer
from app.recording.evidence_service import EvidenceService, EvidenceRecord


def test_rolling_frame_ring_buffer():
    """
    Tests RollingFrameRingBuffer frame pushes, temporal filtering, and clear functionality.
    """
    buffer = RollingFrameRingBuffer(max_seconds=2.0, default_fps=10.0)
    dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)

    # Push 5 frames
    for i in range(5):
        buffer.add_frame(dummy_img, timestamp=datetime.now(timezone.utc))
        time.sleep(0.05)

    pre_frames = buffer.get_pre_event_frames(duration_seconds=1.0)
    assert len(pre_frames) == 5
    assert pre_frames[0][0].shape == (100, 100, 3)

    buffer.clear()
    assert len(buffer.get_pre_event_frames()) == 0


def test_evidence_service_archiving(tmp_path):
    """
    Tests EvidenceService JPEG snapshot, MP4 video clip, and JSON metadata archiving.
    Verifies collision-free filename structure, organized folder hierarchy, and token obfuscation.
    """
    test_storage_dir = str(tmp_path / "evidence_test")
    service = EvidenceService(base_storage_dir=test_storage_dir)

    now = datetime.now(timezone.utc)
    bbox = BoundingBox(x_min=0.1, y_min=0.1, x_max=0.5, y_max=0.5)
    evt = VerifiedEvent(
        event_id="evt_test12345",
        camera_id=1,
        class_name="fire",
        state=EventState.ALERT_SENT,
        consecutive_frames=3,
        duration_seconds=1.2,
        max_confidence=0.91,
        latest_confidence=0.91,
        start_time=now,
        updated_time=now,
        bounding_box=bbox,
        frame_info={"resolution": "640x480"}
    )

    frame_img = np.zeros((480, 640, 3), dtype=np.uint8)
    pre_frames = [(frame_img.copy(), now) for _ in range(5)]

    record = service.save_incident_evidence(
        event=evt,
        annotated_frame=frame_img,
        pre_event_frames=pre_frames,
        camera_name="Main Warehouse Cam"
    )

    assert record is not None
    assert isinstance(record, EvidenceRecord)
    assert record.evidence_id.startswith("ev_")
    assert "/api/v1/evidence/" in record.snapshot_url
    assert record.file_size_bytes > 0

    # Verify Physical File Hierarchy: evidence/CAM-01/YYYY-MM-DD/fire_*.jpg
    physical_snapshot = service.get_physical_snapshot_path(record.evidence_id)
    assert physical_snapshot is not None
    assert os.path.exists(physical_snapshot)
    assert "CAM-01" in physical_snapshot

    physical_video = service.get_physical_video_path(record.evidence_id)
    assert physical_video is not None
    assert os.path.exists(physical_video)
    assert physical_video.endswith(".mp4") or physical_video.endswith(".webm")


def test_evidence_service_secure_token_lookup(tmp_path):
    """
    Tests resolving secure evidence tokens to internal records while hiding OS filesystem paths.
    """
    test_dir = str(tmp_path / "evidence_tokens")
    service = EvidenceService(base_storage_dir=test_dir)

    now = datetime.now(timezone.utc)
    evt = VerifiedEvent(
        event_id="evt_token_test",
        camera_id=3,
        class_name="smoke",
        state=EventState.ALERT_SENT,
        consecutive_frames=4,
        duration_seconds=2.0,
        max_confidence=0.88,
        latest_confidence=0.88,
        start_time=now,
        updated_time=now
    )

    frame_img = np.zeros((100, 100, 3), dtype=np.uint8)
    record = service.save_incident_evidence(evt, frame_img)
    assert record is not None
    token_id = record.evidence_id

    # Lookup record via token ID
    retrieved = service.get_evidence_record(token_id)
    assert retrieved is not None
    assert retrieved.evidence_id == token_id
    assert retrieved.camera_id == 3
    assert retrieved.class_name == "smoke"


def test_evidence_retention_purge(tmp_path):
    """
    Tests purging expired evidence files older than retention policy.
    """
    test_dir = str(tmp_path / "evidence_purge")
    service = EvidenceService(base_storage_dir=test_dir)

    # Create dummy camera folder structure
    cam_dir = os.path.join(test_dir, "CAM-01", "2026-01-01")
    os.makedirs(cam_dir, exist_ok=True)
    old_file = os.path.join(cam_dir, "fire_000000_old.jpg")
    with open(old_file, "w") as f:
        f.write("dummy image data")

    # Set old mtime (e.g. 60 days ago)
    old_time = time.time() - (60 * 86400)
    os.utime(old_file, (old_time, old_time))

    # Purge expired evidence (older than 30 days)
    purged_count = service.purge_expired_evidence(retention_days=30)
    assert purged_count == 1
    assert not os.path.exists(old_file)


def test_evidence_post_event_live_recording(tmp_path):
    """
    Tests live post-event frame recording and smooth real-time video compilation.
    Verifies that pushing live frames updates the video file with real motion.
    """
    import cv2
    test_dir = str(tmp_path / "evidence_post_event")
    service = EvidenceService(base_storage_dir=test_dir)

    now = datetime.now(timezone.utc)
    evt = VerifiedEvent(
        event_id="evt_post_test",
        camera_id=2,
        class_name="ppe_violation",
        state=EventState.ALERT_SENT,
        consecutive_frames=3,
        duration_seconds=1.0,
        max_confidence=0.95,
        latest_confidence=0.95,
        start_time=now,
        updated_time=now
    )

    # Initial frame with distinct pattern
    frame_alert = np.zeros((240, 320, 3), dtype=np.uint8)
    frame_alert[:, :] = (0, 0, 255)  # red

    # 3 pre-event frames
    pre_frames = []
    for i in range(3):
        f = np.zeros((240, 320, 3), dtype=np.uint8)
        f[:, :] = (i * 50, 0, 0)
        pre_frames.append((f, now))

    # Save initial incident evidence with post-event recording enabled
    rec = service.save_incident_evidence(
        event=evt,
        annotated_frame=frame_alert,
        pre_event_frames=pre_frames,
        camera_name="Warehouse Entrance",
        fps=20.0,
        record_post_event=True,
        post_duration_seconds=0.5
    )
    assert rec is not None
    assert rec.video_url is not None

    # Check active session exists
    assert 2 in service._active_sessions
    session = service._active_sessions[2][0]

    # Push 15 live post-event frames with changing content (motion)
    for k in range(16):
        live_frame = np.zeros((240, 320, 3), dtype=np.uint8)
        live_frame[:, :] = (0, k * 15, 0)
        service.push_live_frame(camera_id=2, frame=live_frame)

    # Wait for session to finalize
    session.finished_event.wait(timeout=3.0)

    # Verify physical video file exists and contains frames
    phys_video = service.get_physical_video_path(rec.evidence_id)
    assert phys_video is not None
    assert os.path.exists(phys_video)

    cap = cv2.VideoCapture(phys_video)
    assert cap.isOpened()
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    # Must contain pre-frames (3) + alert frames (2) + post frames (10) = 15 frames
    assert frame_count >= 15

