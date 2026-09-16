"""
Unit and Integration Tests for Webhook Notification Subsystem.
Tests HMAC SHA256 signature generation, payload dispatching, and NotificationManager integration.
"""

import json
import time
from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock, patch

from app.config.settings import settings
from app.alerts.webhook_service import WebhookService
from app.alerts.notification_manager import NotificationManager
from app.detection.verification import VerifiedEvent, EventState, BoundingBox


@pytest.fixture
def mock_verified_event():
    now = datetime.now(timezone.utc)
    return VerifiedEvent(
        event_id="evt_test_webhook_001",
        camera_id=1,
        class_name="fire",
        state=EventState.CONFIRMED,
        consecutive_frames=5,
        duration_seconds=2.5,
        max_confidence=0.92,
        latest_confidence=0.90,
        start_time=now,
        updated_time=now,
        bounding_box=BoundingBox(0.1, 0.1, 0.5, 0.5),
        metadata={"evidence_id": "ev_12345"}
    )


def test_webhook_signature_generation():
    service = WebhookService(secret_key="my-secret-key")
    payload = {"event_id": "evt_001", "class_name": "fire"}
    payload_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    sig = service.generate_signature(payload_bytes)
    
    assert isinstance(sig, str)
    assert len(sig) == 64  # SHA256 hex string is 64 characters


@patch("httpx.Client.post")
def test_webhook_dispatch_success(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_post.return_value = mock_resp

    service = WebhookService(urls=["http://example.com/webhook"], secret_key="secret")
    success = service.dispatch_webhook("http://example.com/webhook", {"alert": "fire"})

    assert success is True
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args.kwargs
    assert "headers" in call_kwargs
    assert "X-CCTV-Signature" in call_kwargs["headers"]
    assert call_kwargs["headers"]["X-CCTV-Signature"].startswith("sha256=")


@patch("httpx.Client.post")
def test_notification_manager_webhook_integration(mock_post, mock_verified_event):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_post.return_value = mock_resp

    # Enable webhooks in settings temporarily
    with patch.object(settings, "WEBHOOK_ALERTS_ENABLED", True), \
         patch.object(settings, "WEBHOOK_URLS", ["http://hooks.example.com/cctv"]), \
         patch.object(settings, "EMAIL_ALERTS_ENABLED", False):

        manager = NotificationManager()
        log = manager.dispatch_alert_notification(
            event=mock_verified_event,
            camera_name="CAM-01 Main",
            location="Building A"
        )

        assert log.status == "DELIVERED"
        assert "webhook_deliveries" in log.metadata
        assert log.metadata["webhook_deliveries"].get("http://hooks.example.com/cctv") is True
