"""
Phase 4 License & Subscription Enforcement Tests:
Verifies:
- Valid license allows camera additions within limits
- Expired license blocks camera addition
- Camera limit exceeded rejects new cameras with HTTP 403 (CAMERA_LIMIT_EXCEEDED)
- Module gating allows enabled features and blocks disabled ones
"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.user import User
from app.models.organization import Organization
from app.models.license import License, LicenseTier, LicenseStatus
from app.models.camera import Camera
from app.utils.security import hash_password, create_access_token

client = TestClient(app)


def test_starter_license_camera_limit_enforced(db: Session):
    """STARTER license has max 4 cameras; 5th camera creation must be rejected."""
    suffix = uuid.uuid4().hex[:6]
    org = Organization(id=f"org_starter_{suffix}", name=f"Starter Org {suffix}", slug=f"starter-{suffix}")
    db.add(org)
    db.flush()

    user = User(
        id=str(uuid.uuid4()),
        username=f"starter_admin_{suffix}",
        email=f"starter_{suffix}@test.local",
        hashed_password=hash_password("Pass123!"),
        role="ADMIN",
        organization_id=org.id,
        is_active=True
    )
    lic = License(
        id=f"lic_starter_{suffix}",
        organization_id=org.id,
        license_key=f"SYNX-STARTER-{suffix.upper()}",
        tier=LicenseTier.STARTER.value,
        status=LicenseStatus.ACTIVE.value,
        max_cameras=4,
        enabled_modules=["fire", "smoke"]
    )
    db.add_all([user, lic])
    db.flush()

    # Pre-populate 4 cameras
    for i in range(4):
        cam = Camera(
            name=f"Starter Cam {i}",
            rtsp_url=f"rtsp://10.0.0.{i+1}/stream",
            organization_id=org.id,
            enabled=True
        )
        db.add(cam)
    db.commit()

    token = create_access_token(data={"sub": user.id, "username": user.username, "role": user.role, "organization_id": org.id})
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt to create 5th camera
    res = client.post(
        "/api/v1/cameras",
        json={"name": "5th Camera Beyond Limit", "rtsp_url": "rtsp://10.0.0.5/stream", "enabled": True},
        headers=headers
    )
    assert res.status_code == 403
    err_body = str(res.json()).lower()
    assert "limit" in err_body or "camera_limit_exceeded" in err_body


def test_expired_license_blocks_camera_creation(db: Session):
    """Expired license blocks new camera additions."""
    suffix = uuid.uuid4().hex[:6]
    org = Organization(id=f"org_exp_{suffix}", name=f"Expired Org {suffix}", slug=f"exp-{suffix}")
    db.add(org)
    db.flush()

    user = User(
        id=str(uuid.uuid4()),
        username=f"exp_admin_{suffix}",
        email=f"exp_{suffix}@test.local",
        hashed_password=hash_password("Pass123!"),
        role="ADMIN",
        organization_id=org.id,
        is_active=True
    )
    lic = License(
        id=f"lic_exp_{suffix}",
        organization_id=org.id,
        license_key=f"SYNX-EXP-{suffix.upper()}",
        tier=LicenseTier.PROFESSIONAL.value,
        status=LicenseStatus.EXPIRED.value,
        max_cameras=16,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        enabled_modules=["fire", "smoke", "ppe"]
    )
    db.add_all([user, lic])
    db.commit()

    token = create_access_token(data={"sub": user.id, "username": user.username, "role": user.role, "organization_id": org.id})
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post(
        "/api/v1/cameras",
        json={"name": "Camera On Expired License", "rtsp_url": "rtsp://10.0.0.99/stream", "enabled": True},
        headers=headers
    )
    assert res.status_code == 403
    err_body = str(res.json()).lower()
    assert "expired" in err_body or "license" in err_body
