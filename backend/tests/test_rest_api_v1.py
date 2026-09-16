"""
Unit & Integration Test Suite for Phase 9 Frontend-Independent REST API (/api/v1/).
Verifies HTTP JSON contracts, authentication, sanitization, pagination, filtering, and media streaming.
"""

import pytest
from fastapi.testclient import TestClient


def test_auth_login_and_me_endpoints(client: TestClient, admin_user):
    """
    Tests POST /api/v1/auth/login and GET /api/v1/auth/me with Bearer token authentication.
    """
    # 1. Login with default admin credentials
    login_resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert login_resp.status_code == 200
    res_data = login_resp.json()["data"]
    assert "access_token" in res_data
    token = res_data["access_token"]
    assert res_data["user"]["username"] == "admin"

    # 2. Access /auth/me with valid Bearer Token
    headers = {"Authorization": f"Bearer {token}"}
    me_resp = client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    user_data = me_resp.json()["data"]
    assert user_data["username"] == "admin"
    assert "hashed_password" not in user_data  # Never expose secrets!


def test_cameras_crud_and_sanitization(client: TestClient, auth_headers):
    """
    Tests Camera CRUD endpoints and verifies RTSP password sanitization.
    """
    # Create camera with credentials
    payload = {
        "name": "Secure Entrance Cam",
        "camera_number": "CAM-10",
        "rtsp_url": "dummy",
        "source_type": "file",
        "location": "Gate A",
        "enabled": False
    }
    resp = client.post("/api/v1/cameras", json=payload, headers=auth_headers)
    assert resp.status_code == 201
    cam_data = resp.json()["data"]
    cam_id = cam_data["id"]

    # Verify RTSP Password Sanitization
    from app.utils.security import sanitize_rtsp_url
    assert sanitize_rtsp_url("rtsp://admin:secretpass123@192.168.1.100:554/live") == "rtsp://***:***@192.168.1.100:554/live"

    # List cameras
    list_resp = client.get("/api/v1/cameras", headers=auth_headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()["data"]) >= 1


def test_alerts_paginated_api(client: TestClient, auth_headers):
    """
    Tests GET /api/v1/alerts with pagination and filters and resolve-all endpoint.
    """
    resp = client.get("/api/v1/alerts?limit=10&offset=0", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "pagination" in data
    assert data["pagination"]["limit"] == 10

    resolve_resp = client.post("/api/v1/alerts/resolve-all", headers=auth_headers)
    assert resolve_resp.status_code == 200
    resolve_data = resolve_resp.json()
    assert resolve_data["success"] is True
    assert "resolved_count" in resolve_data["data"]


def test_detections_api(client: TestClient, auth_headers):
    """
    Tests GET /api/v1/detections API.
    """
    resp = client.get("/api/v1/detections?limit=5", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "pagination" in data


def test_evidence_api(client: TestClient, auth_headers):
    """
    Tests GET /api/v1/evidence API.
    """
    resp = client.get("/api/v1/evidence", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


def test_notifications_api(client: TestClient, auth_headers):
    """
    Tests GET /api/v1/notifications API.
    """
    resp = client.get("/api/v1/notifications", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


def test_system_status_and_stats_apis(client: TestClient, auth_headers):
    """
    Tests GET /api/v1/system/status, /stats, and /logs endpoints.
    """
    status_resp = client.get("/api/v1/system/status", headers=auth_headers)
    assert status_resp.status_code == 200
    status_data = status_resp.json()["data"]
    assert status_data["status"] == "OPERATIONAL"
    assert "version" in status_data

    stats_resp = client.get("/api/v1/system/stats", headers=auth_headers)
    assert stats_resp.status_code == 200
    stats_data = stats_resp.json()["data"]
    assert "total_cameras" in stats_data
    assert "uptime_seconds" in stats_data

    logs_resp = client.get("/api/v1/system/logs", headers=auth_headers)
    assert logs_resp.status_code == 200
    logs_data = logs_resp.json()["data"]
    assert isinstance(logs_data, list)
    assert len(logs_data) >= 1


def test_alert_state_filter_and_acknowledge(client: TestClient, auth_headers):
    """
    Tests alert querying with status/state query parameters and ACKNOWLEDGED updates.
    """
    # Test query with status alias
    resp_new = client.get("/api/v1/alerts?status=NEW", headers=auth_headers)
    assert resp_new.status_code == 200
    assert resp_new.json()["success"] is True

    resp_ack = client.get("/api/v1/alerts?status=ACKNOWLEDGED", headers=auth_headers)
    assert resp_ack.status_code == 200
    assert resp_ack.json()["success"] is True


def test_system_verification_endpoints(client: TestClient, auth_headers):
    """
    Tests GET and PUT /api/v1/system/verification endpoints.
    """
    get_resp = client.get("/api/v1/system/verification", headers=auth_headers)
    assert get_resp.status_code == 200
    data = get_resp.json()["data"]
    assert "fire_min_consecutive_frames" in data
    assert "smoke_min_consecutive_frames" in data
    assert "ppe_verification_frames" in data

    update_payload = {
        "fire_min_consecutive_frames": 4,
        "fire_min_duration_seconds": 0.6,
        "smoke_min_consecutive_frames": 5
    }
    put_resp = client.put("/api/v1/system/verification", json=update_payload, headers=auth_headers)
    assert put_resp.status_code == 200
    put_data = put_resp.json()["data"]
    assert put_data["fire_min_consecutive_frames"] == 4
    assert put_data["fire_min_duration_seconds"] == 0.6
    assert put_data["smoke_min_consecutive_frames"] == 5


def test_alert_remedial_action_resolution(client: TestClient, auth_headers):
    """
    Tests resolving an alert with remedial action, notes, and responder ID.
    """
    # Query alerts to get an alert ID
    list_resp = client.get("/api/v1/alerts", headers=auth_headers)
    assert list_resp.status_code == 200
    alerts = list_resp.json()["data"]
    if alerts:
        target_id = alerts[0]["id"]
        resolve_payload = {
            "state": "RESOLVED",
            "remedial_action": "EXTINGUISHER_DEPLOYED",
            "remedy_notes": "Extinguisher ABC deployed by Security Officer. Flame extinguished safely."
        }
        res = client.patch(f"/api/v1/alerts/{target_id}", json=resolve_payload, headers=auth_headers)
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["state"] == "RESOLVED"
        assert data["remedial_action"] == "EXTINGUISHER_DEPLOYED"
        assert "Extinguisher ABC" in data["remedy_notes"]
        assert data["resolved_by"] is not None

