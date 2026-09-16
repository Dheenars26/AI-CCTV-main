"""
Comprehensive Integration & Security Test Suite for Phase 12.
Tests Argon2id, HttpOnly Cookies, Token Rotation, Reuse Detection, RBAC Permissions,
Single-Use WS Tickets, Account Lockouts, Security Headers, and Audit Logging.
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.models.audit_log import AuditLog
from app.utils.security import hash_password, verify_password, decode_jwt_token, hash_token
from app.services.ws_ticket_service import ws_ticket_service


@pytest.fixture
def create_test_users(db: Session):
    """
    Creates isolated test users for each RBAC role: ADMIN, MANAGER, OPERATOR, VIEWER.
    """
    users = {}
    roles = ["ADMIN", "MANAGER", "OPERATOR", "VIEWER"]

    for r in roles:
        u = db.query(User).filter(User.username == f"user_{r.lower()}").first()
        if not u:
            u = User(
                username=f"user_{r.lower()}",
                email=f"user_{r.lower()}@aicctv.local",
                hashed_password=hash_password("Password123!"),
                full_name=f"Test {r} User",
                role=r,
                is_active=True
            )
            db.add(u)
            db.commit()
            db.refresh(u)
        users[r] = u

    return users


def test_argon2id_password_hashing():
    """1. Tests Argon2id password hashing and verification."""
    pwd = "SecureMasterPassword123!"
    hashed = hash_password(pwd)

    assert hashed is not None
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_login_httponly_cookies_and_csrf(client: TestClient, create_test_users):
    """2. Tests user login returning JWT access token, CSRF token, and HttpOnly refresh token cookie."""
    resp = client.post("/api/v1/auth/login", json={"username": "user_operator", "password": "Password123!"})
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert "access_token" in data
    assert "csrf_token" in data
    assert data["user"]["username"] == "user_operator"
    assert data["user"]["role"] == "OPERATOR"

    # Verify HttpOnly refreshToken Cookie
    assert "refreshToken" in client.cookies
    assert "csrf_token" in client.cookies


def test_refresh_token_rotation_and_reuse_detection(client: TestClient, create_test_users, db: Session):
    """3. Tests Refresh Token Rotation and Token Family Reuse Theft Detection."""
    # Step A: Login to get initial refresh token
    login_resp = client.post("/api/v1/auth/login", json={"username": "user_manager", "password": "Password123!"})
    assert login_resp.status_code == 200
    token1 = client.cookies.get("refreshToken")
    csrf1 = login_resp.json()["data"]["csrf_token"]
    assert token1 is not None

    # Step B: Call refresh -> returns NEW refresh token (Token 2) and revokes Token 1
    ref_resp1 = client.post(
        "/api/v1/auth/refresh",
        cookies={"refreshToken": token1, "csrf_token": csrf1},
        headers={"X-CSRF-Token": csrf1}
    )
    assert ref_resp1.status_code == 200
    token2 = client.cookies.get("refreshToken")
    csrf2 = ref_resp1.json()["data"]["csrf_token"]
    assert token2 != token1

    # Verify Token 1 is revoked in DB
    h1 = hash_token(token1)
    db_token1 = db.query(RefreshToken).filter(RefreshToken.token_hash == h1).first()
    assert db_token1.is_revoked is True

    # Step C: REUSE DETECTION ATTACK SCENARIO
    # Attacker attempts to reuse revoked Token 1 -> System detects theft & revokes ENTIRE token family!
    reuse_resp = client.post(
        "/api/v1/auth/refresh",
        cookies={"refreshToken": token1, "csrf_token": csrf1},
        headers={"X-CSRF-Token": csrf1}
    )
    assert reuse_resp.status_code == 401
    assert "THEFT" in reuse_resp.json()["error"]["code"]

    # Verify Token 2 in family was ALSO revoked automatically
    h2 = hash_token(token2)
    db_token2 = db.query(RefreshToken).filter(RefreshToken.token_hash == h2).first()
    assert db_token2.is_revoked is True


def test_permission_based_rbac_enforcement(client: TestClient, create_test_users):
    """4. Tests RBAC permissions across roles (ADMIN, MANAGER, OPERATOR, VIEWER)."""
    # A. VIEWER Login
    v_login = client.post("/api/v1/auth/login", json={"username": "user_viewer", "password": "Password123!"}).json()["data"]
    v_headers = {"Authorization": f"Bearer {v_login['access_token']}"}

    # VIEWER can read system status
    status_resp = client.get("/api/v1/system/status", headers=v_headers)
    assert status_resp.status_code == 200

    # VIEWER is FORBIDDEN (403) from creating cameras
    create_cam_payload = {"name": "Unauthorized Cam", "camera_number": "CAM-ERR", "rtsp_url": "dummy", "source_type": "file"}
    cam_err_resp = client.post("/api/v1/cameras", json=create_cam_payload, headers=v_headers)
    assert cam_err_resp.status_code == 403

    # B. ADMIN Login
    a_login = client.post("/api/v1/auth/login", json={"username": "user_admin", "password": "Password123!"}).json()["data"]
    a_headers = {"Authorization": f"Bearer {a_login['access_token']}"}

    # ADMIN can create cameras
    admin_cam_resp = client.post("/api/v1/cameras", json=create_cam_payload, headers=a_headers)
    assert admin_cam_resp.status_code == 201


def test_single_use_websocket_ticket_handshake(client: TestClient, create_test_users):
    """5. Tests WebSocket single-use ticket issuance and consumption."""
    # Login to get access token
    op_login = client.post("/api/v1/auth/login", json={"username": "user_operator", "password": "Password123!"}).json()["data"]
    op_headers = {"Authorization": f"Bearer {op_login['access_token']}"}

    # Request single-use WS ticket
    ticket_resp = client.post("/api/v1/auth/ws-ticket", headers=op_headers)
    assert ticket_resp.status_code == 200
    ticket = ticket_resp.json()["data"]["ticket"]
    assert ticket.startswith("wst_")

    # Consume ticket via service
    consumed_payload = ws_ticket_service.consume_ticket(ticket)
    assert consumed_payload is not None
    assert consumed_payload["username"] == "user_operator"

    # Attempt second consume (Re-use) -> must fail!
    second_consume = ws_ticket_service.consume_ticket(ticket)
    assert second_consume is None


def test_account_lockout_on_failed_logins(client: TestClient, create_test_users, db: Session):
    """6. Tests account lockout after 5 consecutive failed login attempts."""
    target_user = "user_operator"

    # Attempt 5 incorrect password logins
    for i in range(5):
        client.post("/api/v1/auth/login", json={"username": target_user, "password": "WrongPassword!"})

    # 6th attempt with CORRECT password -> blocked due to account lock (403)
    locked_resp = client.post("/api/v1/auth/login", json={"username": target_user, "password": "Password123!"})
    assert locked_resp.status_code == 403
    assert "LOCKED" in locked_resp.json()["error"]["code"]

    # Unlock user in DB for remaining tests
    u = db.query(User).filter(User.username == target_user).first()
    u.failed_login_attempts = 0
    u.locked_until = None
    db.commit()


def test_security_headers(client: TestClient):
    """7. Tests security response headers (nosniff, DENY/SAMEORIGIN, CSP)."""
    resp = client.get("/api/v1/system/status")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") in ("DENY", "SAMEORIGIN")
    assert "Content-Security-Policy" in resp.headers
    assert "X-XSS-Protection" not in resp.headers  # Deprecated header removed


def test_security_audit_logging(client: TestClient, create_test_users, db: Session):
    """8. Tests dedicated security audit events written to audit_logs table."""
    client.post("/api/v1/auth/login", json={"username": "user_admin", "password": "Password123!"})

    db.expire_all()
    audit_entry = db.query(AuditLog).filter(AuditLog.event_type == "LOGIN_SUCCESS", AuditLog.username == "user_admin").first()
    assert audit_entry is not None
    assert audit_entry.status == "SUCCESS"
    assert "Password" not in (audit_entry.details or "")  # Zero credential leak
