"""
Unit & Integration Test Suite for Phase 7 Email Alert System.
"""

import os
import time
import pytest
from datetime import datetime, timezone

from app.detection.base import BoundingBox
from app.detection.verification import VerifiedEvent, EventState
from app.alerts.email_service import EmailService
from app.alerts.notification_manager import NotificationManager, NotificationLog
from app.alerts.alert_manager import AlertManager


def test_email_service_template_building():
    """
    Tests HTML and Plain-Text template rendering with dynamic alert parameters.
    """
    service = EmailService()

    alert_data = {
        "event_id": "evt_test999",
        "evidence_id": "ev_test_token_123",
        "camera_id": 1,
        "camera_name": "Main Entrance Cam",
        "location": "Building A - Ground Floor",
        "class_name": "fire",
        "confidence": 0.942,
        "timestamp": "2026-08-18T09:50:00Z"
    }

    html = service._build_html_template(alert_data)
    assert "CRITICAL FIRE ALERT DETECTED" in html
    assert "#dc2626" in html  # Red banner
    assert "Main Entrance Cam" in html
    assert "Building A - Ground Floor" in html
    assert "94.2%" in html
    assert "ev_test_token_123" in html

    # Test Smoke alert amber banner
    alert_smoke = dict(alert_data, class_name="smoke")
    html_smoke = service._build_html_template(alert_smoke)
    assert "#d97706" in html_smoke  # Amber banner

    # Test No Helmet & No Vest PPE violation alert
    alert_ppe = dict(alert_data, class_name="ppe_violation", missing_items=["helmet", "vest"], person_id=3)
    html_ppe = service._build_html_template(alert_ppe)
    assert "SAFETY VIOLATION DETECTED: NO HELMET, NO VEST" in html_ppe
    assert "#e11d48" in html_ppe
    assert "Worker #3" in html_ppe
    assert "NO HELMET, NO VEST" in html_ppe


def test_email_service_dry_run_send():
    """
    Tests EmailService dry-run execution when SMTP credentials are not configured.
    """
    service = EmailService(smtp_host="", username="")
    alert_data = {
        "event_id": "evt_dryrun",
        "camera_id": 2,
        "class_name": "smoke",
        "confidence": 0.88,
        "timestamp": "2026-08-18T09:50:00Z"
    }

    success = service.send_email(
        recipients=["test@security.com"],
        subject="[SMOKE ALERT] Test",
        alert_data=alert_data
    )
    assert success is True


def test_notification_manager_cooldown_suppression():
    """
    Tests NotificationManager enforcing email cooldown to suppress duplicate alerts.
    """
    mock_service = EmailService(smtp_host="", username="")
    notif_mgr = NotificationManager(email_service=mock_service)

    now = datetime.now(timezone.utc)
    evt = VerifiedEvent(
        event_id="evt_cooldown_1",
        camera_id=5,
        class_name="fire",
        state=EventState.ALERT_SENT,
        consecutive_frames=3,
        duration_seconds=1.2,
        max_confidence=0.91,
        latest_confidence=0.91,
        start_time=now,
        updated_time=now
    )

    # First Alert -> DELIVERED
    log1 = notif_mgr.dispatch_alert_notification(evt, camera_name="Server Room Cam", recipients=["test@security.com"])
    assert log1.status == "DELIVERED"
    assert notif_mgr.is_in_cooldown(5, "fire") is True

    # Immediate Second Alert -> SUPPRESSED_COOLDOWN
    evt2 = dict(evt.__dict__)
    evt2_obj = VerifiedEvent(**evt2)
    evt2_obj.event_id = "evt_cooldown_2"

    log2 = notif_mgr.dispatch_alert_notification(evt2_obj, camera_name="Server Room Cam", recipients=["test@security.com"])
    assert log2.status == "SUPPRESSED_COOLDOWN"


def test_alert_manager_async_dispatch():
    """
    Tests AlertManager submitting non-blocking email alert dispatch tasks to thread pool.
    """
    mock_service = EmailService(smtp_host="", username="")
    notif_mgr = NotificationManager(email_service=mock_service)
    alert_mgr = AlertManager(notification_manager=notif_mgr)

    now = datetime.now(timezone.utc)
    evt = VerifiedEvent(
        event_id="evt_async_test",
        camera_id=9,
        class_name="fire",
        state=EventState.ALERT_SENT,
        consecutive_frames=3,
        duration_seconds=1.5,
        max_confidence=0.95,
        latest_confidence=0.95,
        start_time=now,
        updated_time=now
    )

    # Submit task asynchronously - returns immediately
    t0 = time.time()
    alert_mgr.process_verified_event_async(evt, camera_name="Async Cam Test", recipients=["test@security.com"])
    elapsed_call_ms = (time.time() - t0) * 1000

    # Non-blocking call returns in under 200 milliseconds
    assert elapsed_call_ms < 200.0

    # Wait briefly for background thread pool execution
    time.sleep(0.2)

    logs = notif_mgr.get_notification_logs(camera_id=9)
    assert len(logs) == 1
    assert logs[0].status == "DELIVERED"

    alert_mgr.shutdown()


def test_notification_settings_api(client, auth_headers):
    """
    Tests GET and PUT endpoints for alert email notification settings.
    """
    # GET settings
    res = client.get("/api/v1/notifications/settings", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert "recipient_emails" in data
    assert "email_alerts_enabled" in data
    assert "cooldown_seconds" in data

    # PUT update settings
    payload = {
        "recipient_emails": ["ops-team@company.com", "alerts-admin@company.com"],
        "email_alerts_enabled": True,
        "cooldown_seconds": 120.0
    }
    update_res = client.put("/api/v1/notifications/settings", json=payload, headers=auth_headers)
    assert update_res.status_code == 200
    updated_data = update_res.json()["data"]
    assert updated_data["recipient_emails"] == ["ops-team@company.com", "alerts-admin@company.com"]
    assert updated_data["cooldown_seconds"] == 120.0

