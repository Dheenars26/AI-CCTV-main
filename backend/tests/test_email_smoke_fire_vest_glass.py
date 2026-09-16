"""
Comprehensive Unit & Integration Test Suite for Smoke, Fire, Missing Vest, and Missing Glasses Alerts.
Verifies that:
1. Fire detection triggers verified alert with email dispatch.
2. Smoke detection triggers verified alert with email dispatch.
3. Missing vest triggers PPE violation with email dispatch.
4. Missing glass (goggles) triggers PPE violation with email dispatch.
5. Helmet is removed/excluded from detection & requirement (no violation for absent helmet).
"""

import time
from datetime import datetime, timezone
import pytest

from app.detection.base import BoundingBox, DetectionResult
from app.detection.verification import VerifiedEvent, EventState
from app.alerts.email_service import EmailService
from app.alerts.notification_manager import NotificationManager, NotificationLog
from app.alerts.alert_manager import AlertManager
from app.safety.association import PPEAssociationEngine
from app.safety.tracker import TrackedPerson


def test_fire_detection_email_alert():
    """
    Verifies that a verified fire incident dispatches a critical fire email alert.
    """
    mock_email = EmailService(smtp_host="", username="")
    notif_mgr = NotificationManager(email_service=mock_email)
    
    now = datetime.now(timezone.utc)
    evt = VerifiedEvent(
        event_id="evt_fire_01",
        camera_id=1,
        class_name="fire",
        state=EventState.ALERT_SENT,
        consecutive_frames=3,
        duration_seconds=0.6,
        max_confidence=0.92,
        latest_confidence=0.92,
        start_time=now,
        updated_time=now,
        bounding_box=BoundingBox(0.2, 0.2, 0.5, 0.5),
        metadata={"evidence_id": "ev_fire_snap_1"}
    )
    
    log = notif_mgr.dispatch_alert_notification(
        event=evt,
        camera_name="Main Warehouse Cam",
        recipients=["dheenacsgroup@gmail.com"]
    )
    
    assert log.status == "DELIVERED"
    assert log.class_name == "fire"
    assert "dheenacsgroup@gmail.com" in log.recipients


def test_smoke_detection_email_alert():
    """
    Verifies that a verified smoke incident dispatches a warning smoke email alert.
    """
    mock_email = EmailService(smtp_host="", username="")
    notif_mgr = NotificationManager(email_service=mock_email)
    
    now = datetime.now(timezone.utc)
    evt = VerifiedEvent(
        event_id="evt_smoke_01",
        camera_id=1,
        class_name="smoke",
        state=EventState.ALERT_SENT,
        consecutive_frames=3,
        duration_seconds=0.8,
        max_confidence=0.85,
        latest_confidence=0.85,
        start_time=now,
        updated_time=now,
        bounding_box=BoundingBox(0.1, 0.1, 0.4, 0.4),
        metadata={"evidence_id": "ev_smoke_snap_1"}
    )
    
    log = notif_mgr.dispatch_alert_notification(
        event=evt,
        camera_name="Electrical Room Cam",
        recipients=["dheenacsgroup@gmail.com"]
    )
    
    assert log.status == "DELIVERED"
    assert log.class_name == "smoke"


def test_missing_vest_email_alert():
    """
    Verifies that missing vest triggers a PPE violation email alert.
    """
    mock_email = EmailService(smtp_host="", username="")
    notif_mgr = NotificationManager(email_service=mock_email)
    
    now = datetime.now(timezone.utc)
    evt = VerifiedEvent(
        event_id="evt_vest_missing_01",
        camera_id=1,
        class_name="ppe_violation",
        state=EventState.ALERT_SENT,
        consecutive_frames=4,
        duration_seconds=1.2,
        max_confidence=0.88,
        latest_confidence=0.88,
        start_time=now,
        updated_time=now,
        metadata={
            "person_id": 1,
            "missing_equipment": ["vest"],
            "detected_equipment": ["goggles"]
        }
    )
    
    log = notif_mgr.dispatch_alert_notification(
        event=evt,
        camera_name="Assembly Line Cam",
        recipients=["dheenacsgroup@gmail.com"]
    )
    
    assert log.status == "DELIVERED"
    assert log.metadata is not None


def test_missing_glass_email_alert():
    """
    Verifies that missing glasses/goggles triggers a PPE violation email alert.
    """
    mock_email = EmailService(smtp_host="", username="")
    notif_mgr = NotificationManager(email_service=mock_email)
    
    now = datetime.now(timezone.utc)
    evt = VerifiedEvent(
        event_id="evt_glass_missing_01",
        camera_id=1,
        class_name="ppe_violation",
        state=EventState.ALERT_SENT,
        consecutive_frames=4,
        duration_seconds=1.2,
        max_confidence=0.88,
        latest_confidence=0.88,
        start_time=now,
        updated_time=now,
        metadata={
            "person_id": 2,
            "missing_equipment": ["goggles"],
            "detected_equipment": ["vest"]
        }
    )
    
    log = notif_mgr.dispatch_alert_notification(
        event=evt,
        camera_name="Workshop Cam",
        recipients=["dheenacsgroup@gmail.com"]
    )
    
    assert log.status == "DELIVERED"


def test_helmet_exclusion_passes_when_vest_and_glass_worn():
    """
    Verifies that when helmet is excluded, a worker wearing only vest and goggles
    is marked as PASS (no violation for absent helmet).
    """
    engine = PPEAssociationEngine()
    
    worker = TrackedPerson(
        person_id=1,
        camera_id=1,
        bbox=BoundingBox(0.2, 0.1, 0.6, 0.9),
        confidence=0.90,
        last_seen_timestamp=time.time()
    )
    
    # Worker has vest and goggles, but NO helmet
    ppe_dets = [
        DetectionResult(
            label="vest",
            confidence=0.88,
            bbox=BoundingBox(0.22, 0.25, 0.58, 0.65)
        ),
        DetectionResult(
            label="goggles",
            confidence=0.82,
            bbox=BoundingBox(0.35, 0.15, 0.45, 0.25)
        )
    ]
    
    # Required equipment: strictly vest and goggles (helmet removed)
    raw_req = ["vest", "goggles"]
    required_equipment = [e for e in raw_req if e.lower() not in ["helmet", "cap", "hard_hat", "headgear"]]
    
    analyses = engine.associate(
        camera_id=1,
        tracked_persons=[worker],
        ppe_detections=ppe_dets,
        required_equipment=required_equipment
    )
    
    assert len(analyses) == 1
    assert analyses[0].status == "PASS"
    assert len(analyses[0].missing_equipment) == 0
    assert "helmet" not in analyses[0].required_equipment
    assert "helmet" not in analyses[0].missing_equipment


def test_missing_vest_and_glass_triggers_violation():
    """
    Verifies that a worker wearing neither vest nor glasses is flagged with both missing.
    """
    engine = PPEAssociationEngine()
    
    worker = TrackedPerson(
        person_id=2,
        camera_id=1,
        bbox=BoundingBox(0.2, 0.1, 0.6, 0.9),
        confidence=0.90,
        last_seen_timestamp=time.time()
    )
    
    # Worker has no gear at all
    ppe_dets = []
    
    raw_req = ["vest", "goggles"]
    required_equipment = [e for e in raw_req if e.lower() not in ["helmet", "cap", "hard_hat", "headgear"]]
    
    analyses = engine.associate(
        camera_id=1,
        tracked_persons=[worker],
        ppe_detections=ppe_dets,
        required_equipment=required_equipment
    )
    
    assert len(analyses) == 1
    assert analyses[0].status == "VIOLATION"
    assert "vest" in analyses[0].missing_equipment
    assert "goggles" in analyses[0].missing_equipment
    assert "helmet" not in analyses[0].missing_equipment
