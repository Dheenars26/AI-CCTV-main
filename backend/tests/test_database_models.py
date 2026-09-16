"""
Unit & Integration Test Suite for Phase 8 PostgreSQL / SQLAlchemy ORM Database Models & AlertService Transactions.
"""

import pytest
import numpy as np
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.database.session import SessionLocal, engine
from app.database.base import Base
from app.models.user import User
from app.models.camera import Camera
from app.models.detection import Detection
from app.models.alert import Alert
from app.models.evidence import Evidence
from app.models.notification import Notification
from app.models.system_log import SystemLog
from app.services.alert_service import AlertService


@pytest.fixture(autouse=True)
def setup_test_tables():
    """Ensure all SQLAlchemy metadata tables exist before each test."""
    Base.metadata.create_all(bind=engine)
    yield


def test_user_model_creation(db: Session):
    """
    Tests User ORM model creation, role assignment, and attributes.
    """
    user = User(
        username="admin_test_unit",
        email="admin_unit_test@aicctv.local",
        hashed_password="secret_hashed_password",
        full_name="Admin Security Officer",
        role="admin",
        is_active=True,
        is_superuser=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    assert user.id is not None
    assert len(user.id) == 36  # UUID v4 string
    assert user.username == "admin_test_unit"
    assert user.role == "admin"


def test_camera_and_detection_relationship(db: Session):
    """
    Tests Camera and Detection ORM relationships and cascade deletion.
    """
    cam = Camera(
        name="Lobby Camera",
        camera_number="CAM-02",
        rtsp_url="rtsp://192.168.1.50/live",
        source_type="rtsp",
        location="Building A Lobby"
    )
    db.add(cam)
    db.commit()
    db.refresh(cam)

    det = Detection(
        camera_id=cam.id,
        class_name="fire",
        confidence=0.95,
        bounding_box={"x_min": 0.1, "y_min": 0.2, "x_max": 0.4, "y_max": 0.5},
        frame_number=150,
        fps=25.0,
        timestamp=datetime.now(timezone.utc)
    )
    db.add(det)
    db.commit()

    # Query back camera detections
    fetched_cam = db.query(Camera).filter(Camera.id == cam.id).first()
    assert len(fetched_cam.detections) == 1
    assert fetched_cam.detections[0].class_name == "fire"
    assert fetched_cam.detections[0].confidence == 0.95


def test_alert_evidence_notification_relationship(db: Session):
    """
    Tests Alert -> Evidence -> Notification cascade relationship hierarchy.
    """
    cam = Camera(
        name="Server Room Cam",
        camera_number="CAM-03",
        rtsp_url="rtsp://192.168.1.60/live"
    )
    db.add(cam)
    db.commit()

    now = datetime.now(timezone.utc)
    alert = Alert(
        id="evt_test_alert_1",
        camera_id=cam.id,
        class_name="fire",
        state="ALERT_SENT",
        consecutive_frames=3,
        duration_seconds=1.5,
        max_confidence=0.92,
        latest_confidence=0.92,
        start_time=now
    )
    db.add(alert)
    db.commit()

    evidence = Evidence(
        evidence_id="ev_token_test_123",
        alert_id=alert.id,
        camera_id=cam.id,
        snapshot_relative_path="evidence/CAM-03/2026-08-18/fire_001.jpg",
        video_relative_path="evidence/CAM-03/2026-08-18/fire_001.mp4",
        file_size_bytes=102400
    )
    notif = Notification(
        alert_id=alert.id,
        channel="email",
        recipient="security@company.com",
        status="DELIVERED",
        sent_at=now
    )
    db.add(evidence)
    db.add(notif)
    db.commit()

    fetched_alert = db.query(Alert).filter(Alert.id == alert.id).first()
    assert fetched_alert is not None
    assert fetched_alert.evidence.evidence_id == "ev_token_test_123"
    assert len(fetched_alert.notifications) == 1
    assert fetched_alert.notifications[0].status == "DELIVERED"


def test_alert_service_transactions(db: Session):
    """
    Tests AlertService high-level business methods and database transactions.
    """
    cam = Camera(
        name="Warehouse Cam",
        camera_number="CAM-04",
        rtsp_url="rtsp://192.168.1.70/live"
    )
    db.add(cam)
    db.commit()

    service = AlertService(db=db)
    now = datetime.now(timezone.utc)

    # 1. Create Alert
    alert = service.create_alert(
        alert_id="evt_svc_001",
        camera_id=cam.id,
        class_name="smoke",
        state="ALERT_SENT",
        consecutive_frames=4,
        duration_seconds=2.0,
        max_confidence=0.88,
        latest_confidence=0.88,
        start_time=now
    )
    assert alert.id == "evt_svc_001"

    # 2. Update Alert State
    updated = service.update_alert_state(
        alert_id="evt_svc_001",
        state="CLEARED",
        cleared_time=now
    )
    assert updated.state == "CLEARED"

    # 3. Log System Event
    sys_log = service.log_system_event(
        level="WARNING",
        module="VerificationEngine",
        message="Stream freeze cleared",
        camera_id=cam.id
    )
    assert sys_log.id is not None
    assert sys_log.level == "WARNING"
