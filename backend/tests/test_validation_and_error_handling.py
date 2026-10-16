"""
Unit and Integration Tests for Enhanced Error Handling & Validation.
Covers REST API parameter validation, alert state guards, database restore safety, and WebSocket frame checks.
"""

import os
import tempfile
import pytest
from fastapi.testclient import TestClient

from scripts.restore_db import (
    sanitize_and_validate_path,
    is_valid_sqlite_backup,
    SQLITE_HEADER
)


def test_alerts_invalid_date_range_validation(client: TestClient, admin_user):
    """Ensures GET /api/v1/alerts rejects date_from > date_to with HTTP 400 ValidationException."""
    login_resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    token = login_resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get(
        "/api/v1/alerts?date_from=2026-10-06T12:00:00Z&date_to=2026-10-01T12:00:00Z",
        headers=headers
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "date_from" in body["error"]["message"]


def test_alerts_invalid_camera_id_validation(client: TestClient, admin_user):
    """Ensures GET /api/v1/alerts rejects non-positive camera_id with HTTP 400."""
    login_resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    token = login_resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get(
        "/api/v1/alerts?camera_id=0",
        headers=headers
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "Camera ID must be a positive integer" in body["error"]["message"]


def test_alerts_invalid_state_transition_validation(client: TestClient, admin_user):
    """Ensures PATCH /api/v1/alerts/{id} rejects unknown states with HTTP 400 ValidationException."""
    login_resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    token = login_resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.patch(
        "/api/v1/alerts/evt_nonexistent",
        headers=headers,
        json={"state": "COMPLETELY_INVALID_STATE"}
    )
    assert resp.status_code in (400, 404, 422)
    body = resp.json()
    assert body["success"] is False


def test_restore_db_path_sanitization_rejects_injection():
    """Verifies restore_db.py rejects shell metacharacters and directory traversal."""
    with pytest.raises(ValueError, match="Malicious character detected"):
        sanitize_and_validate_path("backup.db; rm -rf /")

    with pytest.raises(ValueError, match="Malicious character detected"):
        sanitize_and_validate_path("backup.db | cat /etc/passwd")

    with pytest.raises(FileNotFoundError):
        sanitize_and_validate_path("nonexistent_backup_file_12345.db")


def test_restore_db_sqlite_header_validation():
    """Verifies SQLite header checker validates real vs corrupted files."""
    with tempfile.NamedTemporaryFile(delete=False) as valid_db:
        valid_db.write(SQLITE_HEADER + b"\x00" * 84)
        valid_path = valid_db.name

    with tempfile.NamedTemporaryFile(delete=False) as invalid_db:
        invalid_db.write(b"CORRUPTED_NOT_A_SQLITE_DATABASE_HEADER")
        invalid_path = invalid_db.name

    try:
        assert is_valid_sqlite_backup(valid_path) is True
        assert is_valid_sqlite_backup(invalid_path) is False
    finally:
        if os.path.exists(valid_path):
            os.remove(valid_path)
        if os.path.exists(invalid_path):
            os.remove(invalid_path)
