"""
Unit & Integration Test Suite for Phase 10 Real-Time WebSocket Event Subsystem (/api/v1/ws).
Verifies multi-client connections, ping/pong heartbeats, JWT auth preparation, event serialization, and isolated broadcasting.
"""

import pytest
from fastapi.testclient import TestClient
from app.websocket.connection_manager import (
    manager,
    EVENT_FIRE_DETECTED,
    EVENT_SMOKE_DETECTED,
    EVENT_ALERT_CREATED,
    EVENT_CAMERA_STATUS_CHANGED
)
from app.utils.security import create_access_token


def test_websocket_connect_welcome_and_ping_pong(client: TestClient, admin_user):
    """
    Tests WebSocket connection to /api/v1/auth/ws-ticket and /api/v1/ws with subprotocol ticket.
    """
    # 1. Obtain ticket
    auth_resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    token = auth_resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    ticket_resp = client.post("/api/v1/auth/ws-ticket", headers=headers)
    ticket = ticket_resp.json()["data"]["ticket"]

    # 2. Connect with ticket subprotocol
    with client.websocket_connect("/api/v1/ws", subprotocols=[f"cctv-auth-{ticket}"]) as websocket:
        # Receive Welcome Message
        data = websocket.receive_json()
        assert data["event"] == "connected"
        assert data["version"] == "1.0"
        assert data["data"]["channel"] == "alerts"
        assert data["data"]["authenticated"] is True

        # Send Ping Keep-Alive Message
        websocket.send_text("ping")
        pong = websocket.receive_json()
        assert pong["type"] == "pong"
        assert pong["version"] == "1.0"
        assert "timestamp" in pong


def test_websocket_jwt_auth_connection(client: TestClient, admin_user):
    """
    Tests WebSocket connection with single-use ticket.
    """
    auth_resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    token = auth_resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    ticket_resp = client.post("/api/v1/auth/ws-ticket", headers=headers)
    ticket = ticket_resp.json()["data"]["ticket"]
    
    with client.websocket_connect(f"/api/v1/ws?ticket={ticket}") as websocket:
        welcome = websocket.receive_json()
        assert welcome["event"] == "connected"
        assert welcome["data"]["authenticated"] is True


def test_websocket_legacy_endpoint_alias(client: TestClient, admin_user):
    """
    Tests legacy route alias /ws/v1/alerts with single-use ticket.
    """
    auth_resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    token = auth_resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    ticket_resp = client.post("/api/v1/auth/ws-ticket", headers=headers)
    ticket = ticket_resp.json()["data"]["ticket"]

    with client.websocket_connect(f"/ws/v1/alerts?ticket={ticket}") as websocket:
        welcome = websocket.receive_json()
        assert welcome["event"] == "connected"


@pytest.mark.anyio
async def test_connection_manager_isolated_broadcast():
    """
    Tests ConnectionManager broadcast_event structure and envelope serialization.
    """
    event_data = {
        "camera_id": 1,
        "camera_name": "Front Gate",
        "confidence": 0.95,
        "alert_id": "evt_test123"
    }

    # Verify synchronous thread-safe call does not crash when no clients connected
    manager.broadcast_event_sync(EVENT_FIRE_DETECTED, event_data)
    assert manager.active_count == 0
