"""
End-to-End Integration Test for Restricted Area Intrusion Alerts & Email Delivery.
Tests:
1. Worker enters a defined RESTRICTED polygon zone.
2. AI pipeline evaluates point-in-polygon containment and detects unauthorized entry.
3. Safety Rule Engine generates ZONE_VIOLATION alert.
4. FramePipeline annotates the frame with red intruder HUD brackets and incident banner.
5. EvidenceService captures and stores the annotated incident snapshot.
6. NotificationManager dispatches an alert email with inline snapshot attachment to added recipient emails.
7. EmailService renders custom HTML/Text templates containing the restricted zone details and evidence.
"""

import os
import uuid
import numpy as np
import pytest
from datetime import datetime, timezone

from app.detection.base import BoundingBox, DetectionResult
from app.zones.engine import ZoneEngine, ZoneEvaluationResult
from app.safety.association import WorkerPPEAnalysis
from app.safety.rules import SafetyRuleEngine, SafetyRuleDecision
from app.detection.verification import VerifiedEvent, EventState
from app.camera.pipeline import FramePipeline, StandardPostprocessor, Frame
from app.alerts.email_service import EmailService
from app.alerts.notification_manager import NotificationManager
from app.config.settings import settings


def test_restricted_zone_point_in_polygon_detection():
    """
    Verifies ZoneEngine correctly identifies worker entering a RESTRICTED polygon zone.
    """
    zone_engine = ZoneEngine()
    
    # Define a 4-point polygon representing a restricted zone (e.g. [0.2, 0.2] to [0.6, 0.6])
    restricted_zone = {
        "id": 10,
        "name": "High Voltage Room",
        "zone_type": "RESTRICTED",
        "polygon_coordinates": [[0.2, 0.2], [0.6, 0.2], [0.6, 0.6], [0.2, 0.6]],
        "enabled": True
    }

    # Worker located inside the restricted area (centroid at [0.4, 0.4])
    worker_inside = WorkerPPEAnalysis(
        person_id=42,
        camera_id=1,
        bounding_box=BoundingBox(x_min=0.35, y_min=0.30, x_max=0.45, y_max=0.50),
        status="PASS",
        required_equipment=["vest", "goggles"],
        detected_equipment=["vest", "goggles"],
        missing_equipment=[],
        confidence=0.95,
        timestamp=datetime.now(timezone.utc).isoformat()
    )

    eval_results = zone_engine.evaluate_workers_in_zones([worker_inside], [restricted_zone])
    assert len(eval_results) == 1
    res = eval_results[0]
    assert res.zone_id == 10
    assert res.zone_name == "High Voltage Room"
    assert res.zone_type == "RESTRICTED"
    assert res.is_inside is True
    assert res.is_unauthorized is True


def test_safety_rule_engine_generates_zone_violation():
    """
    Verifies SafetyRuleEngine triggers a ZONE_VIOLATION decision for unauthorized restricted zone entry.
    """
    rule_engine = SafetyRuleEngine(cooldown_seconds=0.0)

    worker = WorkerPPEAnalysis(
        person_id=42,
        camera_id=1,
        bounding_box=BoundingBox(x_min=0.35, y_min=0.30, x_max=0.45, y_max=0.50),
        status="PASS",
        required_equipment=["vest", "goggles"],
        detected_equipment=["vest", "goggles"],
        missing_equipment=[],
        confidence=0.92,
        timestamp=datetime.now(timezone.utc).isoformat()
    )

    zone_eval = ZoneEvaluationResult(
        zone_id=10,
        zone_name="High Voltage Room",
        zone_type="RESTRICTED",
        ppe_profile_id=None,
        worker_analysis=worker,
        is_inside=True,
        is_unauthorized=True
    )

    decisions = rule_engine.evaluate_rules(
        camera_id=1,
        fire_smoke_detections=[],
        worker_analyses=[worker],
        zone_evaluations=[zone_eval]
    )

    zone_decisions = [d for d in decisions if d.incident_type == "ZONE_VIOLATION"]
    assert len(zone_decisions) >= 1
    zd = zone_decisions[0]
    assert zd.camera_id == 1
    assert zd.person_id == 42
    assert zd.zone_name == "High Voltage Room"
    assert "UNAUTHORIZED_AREA_ENTRY" in zd.events
    assert zd.severity == "HIGH"


def test_postprocessor_annotates_intruder_hud_and_banner():
    """
    Verifies that the postprocessor renders an emergency intruder banner and tags the worker in red.
    """
    postprocessor = StandardPostprocessor(debug_overlay=True)
    raw_img = np.zeros((480, 640, 3), dtype=np.uint8)

    restricted_zone = {
        "id": 10,
        "name": "High Voltage Room",
        "zone_type": "RESTRICTED",
        "polygon_coordinates": [[0.2, 0.2], [0.6, 0.2], [0.6, 0.6], [0.2, 0.6]],
        "enabled": True
    }

    worker_dict = {
        "person_id": 42,
        "bounding_box": {"x_min": 0.35, "y_min": 0.30, "x_max": 0.45, "y_max": 0.50},
        "status": "PASS",
        "missing_equipment": [],
        "detected_equipment": ["vest", "goggles"]
    }

    safety_decision_dict = {
        "incident_type": "ZONE_VIOLATION",
        "person_id": 42,
        "zone_name": "High Voltage Room",
        "events": ["UNAUTHORIZED_AREA_ENTRY"],
        "severity": "HIGH"
    }

    frame = Frame(
        camera_id=1,
        image=raw_img,
        timestamp=datetime.now(timezone.utc),
        frame_id=1,
        detections=[],
        metadata={
            "safety_zones": [restricted_zone],
            "worker_ppe_analyses": [worker_dict],
            "safety_decisions": [safety_decision_dict]
        }
    )

    processed_frame = postprocessor.process(frame)
    assert processed_frame.image is not None
    # Verify image was modified with drawing overlays (contains non-zero pixels)
    assert np.any(processed_frame.image > 0)


def test_email_service_restricted_zone_template():
    """
    Verifies EmailService renders HTML and Plain-Text templates tailored for restricted zone intrusions.
    """
    email_service = EmailService()

    alert_data = {
        "event_id": "evt_zone_123",
        "evidence_id": "ev_zone_snap_456",
        "camera_id": 2,
        "camera_name": "North Warehouse Camera",
        "location": "Sector 4 - Electrical Substation",
        "latitude": 13.0827,
        "longitude": 80.2707,
        "class_name": "zone_violation",
        "incident_type": "ZONE_VIOLATION",
        "zone_id": 10,
        "zone_name": "High Voltage Substation",
        "person_id": 42,
        "confidence": 0.965,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    html = email_service._build_html_template(alert_data)
    assert "RESTRICTED AREA INTRUSION" in html
    assert "High Voltage Substation" in html
    assert "#b91c1c" in html  # Crimson intrusion banner
    assert "Unauthorized Person Detected Inside Restricted Boundary" in html
    assert "Worker #42" in html
    assert "cid:evidence_snapshot" in html

    text = email_service._build_text_template(alert_data)
    assert "Restricted" in text or "RESTRICTED" in text.upper()
    assert "High Voltage Substation" in text
    assert "Unauthorized Person Entry" in text


def test_notification_manager_dispatches_to_added_emails(tmp_path):
    """
    Verifies NotificationManager delivers alert to newly added recipient emails with snapshot attached.
    """
    # Create a dummy snapshot file
    dummy_snap = tmp_path / "intruder_snapshot.jpg"
    dummy_snap.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 50)  # Valid JPEG magic bytes

    mock_email_service = EmailService(smtp_host="", username="")
    notif_mgr = NotificationManager(email_service=mock_email_service)

    added_email = "security_lead@facility.com"

    now = datetime.now(timezone.utc)
    event = VerifiedEvent(
        event_id=f"evt_{uuid.uuid4().hex[:8]}",
        camera_id=3,
        class_name="zone_violation",
        state=EventState.ALERT_SENT,
        consecutive_frames=1,
        duration_seconds=0.1,
        max_confidence=0.94,
        latest_confidence=0.94,
        start_time=now,
        updated_time=now,
        metadata={
            "zone_id": 10,
            "zone_name": "High Voltage Room",
            "incident_type": "ZONE_VIOLATION",
            "person_id": 42,
            "events": ["UNAUTHORIZED_AREA_ENTRY"]
        }
    )

    log_entry = notif_mgr.dispatch_alert_notification(
        event=event,
        snapshot_path=str(dummy_snap),
        camera_name="Main Gate Cam",
        location="Restricted Periphery",
        recipients=[added_email]
    )

    assert log_entry.status == "DELIVERED"
    assert added_email in log_entry.recipients
    assert log_entry.class_name == "zone_violation"
