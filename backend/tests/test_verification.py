"""
Unit & Integration Test Suite for Phase 5 Temporal Verification & False-Alarm Reduction.
Covers:
1. One-frame false detection (transient noise recovery)
2. Consecutive detection (state transitions NORMAL -> POSSIBLE -> CONFIRMED -> ALERT_SENT)
3. Detection disappearing (ACTIVE -> CLEARED -> NORMAL)
4. Repeated detection (new incident after clearing)
5. Cooldown (duplicate alert suppression during active period)
6. Camera disconnection (safe state machine reset)
"""

import time
import pytest
from datetime import datetime, timezone

from app.detection.base import DetectionResult, BoundingBox
from app.detection.verification import (
    EventState,
    VerifiedEvent,
    ClassVerificationTracker,
    CameraVerificationEngine
)


def make_detection(label: str = "smoke", confidence: float = 0.85, camera_id: int = 1) -> DetectionResult:
    """Helper to generate a test DetectionResult."""
    return DetectionResult(
        label=label,
        confidence=confidence,
        bbox=BoundingBox(x_min=0.1, y_min=0.1, x_max=0.4, y_max=0.4),
        camera_id=camera_id,
        timestamp=datetime.now(timezone.utc).isoformat()
    )


def test_one_frame_false_detection():
    """
    Test 1: One-frame spurious false detection should transition NORMAL -> POSSIBLE,
    and then return to NORMAL on frame 2 without generating an alert payload.
    """
    tracker = ClassVerificationTracker(
        camera_id=1,
        class_name="smoke",
        min_confidence=0.50,
        min_consecutive_frames=3,
        min_duration_seconds=0.5,
        cooldown_seconds=10.0
    )

    frame_info = {"frame_id": 1, "fps": 25.0}

    # Frame 1: Spurious detection occurs
    evt1 = tracker.update([make_detection(label="smoke", confidence=0.80)], frame_info)
    assert evt1 is None  # No alert generated yet
    assert tracker.state == EventState.POSSIBLE
    assert tracker.consecutive_frames == 1

    # Frame 2: Detection disappears immediately (false alarm)
    evt2 = tracker.update([], frame_info)
    assert evt2 is None
    assert tracker.state == EventState.NORMAL
    assert tracker.consecutive_frames == 0


def test_consecutive_detection_confirmation():
    """
    Test 2: Valid consecutive detections exceeding min_consecutive_frames & duration
    should transition POSSIBLE -> CONFIRMED -> ALERT_SENT and return a VerifiedEvent.
    """
    tracker = ClassVerificationTracker(
        camera_id=1,
        class_name="fire",
        min_confidence=0.50,
        min_consecutive_frames=3,
        min_duration_seconds=0.1,  # Short duration for test speed
        cooldown_seconds=10.0
    )

    det = make_detection(label="fire", confidence=0.90)

    # Frame 1: NORMAL -> POSSIBLE
    evt1 = tracker.update([det], {"frame_id": 1})
    assert evt1 is None
    assert tracker.state == EventState.POSSIBLE

    # Frame 2: Consecutive detection
    time.sleep(0.05)
    evt2 = tracker.update([det], {"frame_id": 2})
    assert evt2 is None
    assert tracker.state == EventState.POSSIBLE

    # Frame 3: Reaches min_consecutive_frames (3) and min_duration
    time.sleep(0.06)
    evt3 = tracker.update([det], {"frame_id": 3})
    assert evt3 is not None
    assert isinstance(evt3, VerifiedEvent)
    assert evt3.class_name == "fire"
    assert evt3.state == EventState.ALERT_SENT
    assert evt3.consecutive_frames == 3
    assert evt3.event_id is not None


def test_detection_disappearing_cleared_transition():
    """
    Test 3: Active event clears when detection disappears for cleared_miss_tolerance frames.
    """
    tracker = ClassVerificationTracker(
        camera_id=1,
        class_name="smoke",
        min_confidence=0.50,
        min_consecutive_frames=2,
        min_duration_seconds=0.05,
        cleared_miss_tolerance=2
    )

    det = make_detection(label="smoke", confidence=0.88)

    # Frame 1 & 2: Confirm event
    tracker.update([det], {"frame_id": 1})
    time.sleep(0.06)
    evt_confirm = tracker.update([det], {"frame_id": 2})
    assert evt_confirm is not None
    assert evt_confirm.state == EventState.ALERT_SENT

    # Frame 3: Detection missing (missed_frames = 1)
    evt_miss1 = tracker.update([], {"frame_id": 3})
    assert evt_miss1 is None
    assert tracker.state in [EventState.ALERT_SENT, EventState.ACTIVE]

    # Frame 4: Detection missing (missed_frames = 2 -> cleared threshold)
    evt_cleared = tracker.update([], {"frame_id": 4})
    assert evt_cleared is not None
    assert evt_cleared.state == EventState.CLEARED
    assert tracker.state == EventState.NORMAL


def test_repeated_detection_new_event():
    """
    Test 4: Detection appearing after an event has cleared starts a new event lifecycle.
    """
    engine = CameraVerificationEngine(
        camera_id=2,
        target_classes=["fire"],
        min_consecutive_frames=2,
        min_duration_seconds=0.05,
        cooldown_seconds=5.0
    )

    det = make_detection(label="fire", confidence=0.92, camera_id=2)

    # Event 1 Confirmation
    engine.process_frame_detections([det], {"frame_id": 1})
    time.sleep(0.06)
    evts1 = engine.process_frame_detections([det], {"frame_id": 2})
    assert len(evts1) == 1
    first_event_id = evts1[0].event_id

    # Event 1 Clearing
    engine.process_frame_detections([], {"frame_id": 3})
    evts_cleared = engine.process_frame_detections([], {"frame_id": 4})
    assert len(evts_cleared) == 1
    assert evts_cleared[0].state == EventState.CLEARED

    # Event 2 Confirmation (New incident)
    engine.process_frame_detections([det], {"frame_id": 5})
    time.sleep(0.06)
    evts2 = engine.process_frame_detections([det], {"frame_id": 6})
    assert len(evts2) == 1
    assert evts2[0].event_id != first_event_id  # Unique new event ID


def test_cooldown_suppresses_duplicate_alerts():
    """
    Test 5: During active monitoring within cooldown period, duplicate alerts are suppressed.
    """
    tracker = ClassVerificationTracker(
        camera_id=1,
        class_name="fire",
        min_consecutive_frames=2,
        min_duration_seconds=0.05,
        cooldown_seconds=10.0  # 10 second cooldown
    )

    det = make_detection(label="fire", confidence=0.95)

    # Confirm initial alert
    tracker.update([det], {"frame_id": 1})
    time.sleep(0.06)
    evt_initial = tracker.update([det], {"frame_id": 2})
    assert evt_initial is not None
    assert evt_initial.state == EventState.ALERT_SENT

    # Frame 3, 4, 5: Ongoing detections within 10s cooldown should NOT trigger duplicate alert events
    evt3 = tracker.update([det], {"frame_id": 3})
    evt4 = tracker.update([det], {"frame_id": 4})
    assert evt3 is None
    assert evt4 is None
    assert tracker.state == EventState.ACTIVE


def test_camera_disconnection_resets_state():
    """
    Test 6: Camera disconnection cleanly resets state machine without stale locks.
    """
    engine = CameraVerificationEngine(
        camera_id=5,
        target_classes=["fire", "smoke"],
        min_consecutive_frames=2
    )

    det = make_detection(label="smoke", confidence=0.85, camera_id=5)
    engine.process_frame_detections([det], {"frame_id": 1})
    assert engine.trackers["smoke"].state == EventState.POSSIBLE

    # Stream disconnect event occurs
    engine.reset_all()
    assert engine.trackers["smoke"].state == EventState.NORMAL
    assert engine.trackers["fire"].state == EventState.NORMAL


def test_flame_flicker_single_frame_dip_does_not_abort_verification():
    """
    Test 7: A genuine flickering flame that has a 1-frame confidence drop or missing detection
    does NOT reset to NORMAL if multi-frame credit has been accumulated, successfully confirming
    when the detection resumes.
    """
    tracker = ClassVerificationTracker(
        camera_id=1,
        class_name="fire",
        min_confidence=0.50,
        min_consecutive_frames=3,
        min_duration_seconds=0.1,
        cooldown_seconds=10.0
    )

    det = make_detection(label="fire", confidence=0.88)

    # Frame 1: Detection -> POSSIBLE (credit=1.0)
    tracker.update([det], {"frame_id": 1})
    assert tracker.state == EventState.POSSIBLE

    # Frame 2: Detection -> POSSIBLE (credit=2.0)
    time.sleep(0.04)
    tracker.update([det], {"frame_id": 2})
    assert tracker.state == EventState.POSSIBLE

    # Frame 3: Flame flickers down or packet dropped -> missed 1 frame (credit=1.4)
    # The tracker should STAY in POSSIBLE rather than immediately clearing!
    time.sleep(0.04)
    evt_dip = tracker.update([], {"frame_id": 3})
    assert evt_dip is None
    assert tracker.state == EventState.POSSIBLE
    assert tracker.missed_frames == 1

    # Frame 4: Flame flares back up -> reaches threshold and confirms!
    time.sleep(0.05)
    evt_confirm = tracker.update([det], {"frame_id": 4})
    assert evt_confirm is not None
    assert evt_confirm.state == EventState.ALERT_SENT
    assert tracker.state in [EventState.ALERT_SENT, EventState.ACTIVE]

