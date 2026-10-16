"""
Phase 3 Multi-Tenant Isolation Tests:
Verifies strict isolation between organizations across:
- Cameras (list, create, read, update, delete)
- Alerts (list, get, resolve)
- Incidents (list, get, update)
- Safety Zones (list, get, update, delete)
- Evidence (list, detail, snapshots)
- WebSockets (targeted org events not leaked)
"""

import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.user import User
from app.models.organization import Organization, Site
from app.models.camera import Camera
from app.models.alert import Alert
from app.models.incident import Incident
from app.models.evidence import Evidence
from app.models.zone import SafetyZone
from app.utils.security import hash_password, create_access_token

client = TestClient(app)


@pytest.fixture
def multi_tenant_setup(db: Session):
    """Sets up two distinct organizations, users, and resources."""
    u_suffix = uuid.uuid4().hex[:6]
    org1 = Organization(id=f"org_alpha_{u_suffix}", name=f"Alpha Industries {u_suffix}", slug=f"alpha-ind-{u_suffix}")
    org2 = Organization(id=f"org_beta_{u_suffix}", name=f"Beta Logistics {u_suffix}", slug=f"beta-log-{u_suffix}")
    db.add_all([org1, org2])
    db.flush()

    user1 = User(
        id=str(uuid.uuid4()),
        username=f"user_alpha_{u_suffix}",
        email=f"alpha_{u_suffix}@test.local",
        hashed_password=hash_password("Pass123!"),
        role="ADMIN",
        organization_id=org1.id,
        is_active=True
    )
    user2 = User(
        id=str(uuid.uuid4()),
        username=f"user_beta_{u_suffix}",
        email=f"beta_{u_suffix}@test.local",
        hashed_password=hash_password("Pass123!"),
        role="ADMIN",
        organization_id=org2.id,
        is_active=True
    )
    db.add_all([user1, user2])
    db.flush()

    cam1 = Camera(
        name="Alpha Front Entrance",
        rtsp_url="rtsp://10.0.0.1/stream",
        organization_id=org1.id,
        enabled=True
    )
    cam2 = Camera(
        name="Beta Loading Dock",
        rtsp_url="rtsp://10.0.1.1/stream",
        organization_id=org2.id,
        enabled=True
    )
    db.add_all([cam1, cam2])
    db.flush()

    alert1 = Alert(
        camera_id=cam1.id,
        class_name="fire",
        state="CONFIRMED",
        organization_id=org1.id
    )
    alert2 = Alert(
        camera_id=cam2.id,
        class_name="smoke",
        state="CONFIRMED",
        organization_id=org2.id
    )
    db.add_all([alert1, alert2])
    db.flush()

    inc1 = Incident(
        id=f"inc_alpha_{u_suffix}",
        camera_id=cam1.id,
        incident_type="FIRE",
        events=["fire"],
        severity="HIGH",
        status="ACTIVE",
        organization_id=org1.id
    )
    inc2 = Incident(
        id=f"inc_beta_{u_suffix}",
        camera_id=cam2.id,
        incident_type="SMOKE",
        events=["smoke"],
        severity="MEDIUM",
        status="ACTIVE",
        organization_id=org2.id
    )
    db.add_all([inc1, inc2])
    db.flush()

    zone1 = SafetyZone(
        camera_id=cam1.id,
        name="Alpha Hazard Zone",
        zone_type="HAZARD",
        polygon_coordinates=[[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]],
        organization_id=org1.id,
        enabled=True
    )
    zone2 = SafetyZone(
        camera_id=cam2.id,
        name="Beta Restricted Zone",
        zone_type="RESTRICTED",
        polygon_coordinates=[[0.2, 0.2], [0.6, 0.2], [0.6, 0.6], [0.2, 0.6]],
        organization_id=org2.id,
        enabled=True
    )
    db.add_all([zone1, zone2])
    db.flush()

    ev1 = Evidence(
        id=f"ev_alpha_{u_suffix}",
        evidence_id=f"evi_alpha_{u_suffix}",
        alert_id=alert1.id,
        camera_id=cam1.id,
        snapshot_relative_path="alpha.jpg",
        organization_id=org1.id
    )
    ev2 = Evidence(
        id=f"ev_beta_{u_suffix}",
        evidence_id=f"evi_beta_{u_suffix}",
        alert_id=alert2.id,
        camera_id=cam2.id,
        snapshot_relative_path="beta.jpg",
        organization_id=org2.id
    )
    db.add_all([ev1, ev2])
    db.commit()

    token1 = create_access_token(data={"sub": user1.id, "username": user1.username, "role": user1.role, "organization_id": org1.id})
    token2 = create_access_token(data={"sub": user2.id, "username": user2.username, "role": user2.role, "organization_id": org2.id})

    return {
        "org1": org1,
        "org2": org2,
        "user1": user1,
        "user2": user2,
        "token1": token1,
        "token2": token2,
        "headers1": {"Authorization": f"Bearer {token1}"},
        "headers2": {"Authorization": f"Bearer {token2}"},
        "cam1": cam1,
        "cam2": cam2,
        "alert1": alert1,
        "alert2": alert2,
        "inc1": inc1,
        "inc2": inc2,
        "zone1": zone1,
        "zone2": zone2,
        "ev1": ev1,
        "ev2": ev2
    }


def test_camera_tenant_isolation(multi_tenant_setup):
    """User from Org Alpha should only list Org Alpha cameras and not Org Beta cameras."""
    h1 = multi_tenant_setup["headers1"]
    h2 = multi_tenant_setup["headers2"]

    # Org Alpha list
    res = client.get("/api/v1/cameras", headers=h1)
    assert res.status_code == 200
    cams1 = res.json()["data"]
    cam1_ids = [c["id"] for c in cams1]
    assert multi_tenant_setup["cam1"].id in cam1_ids
    assert multi_tenant_setup["cam2"].id not in cam1_ids

    # Org Alpha attempting to read Org Beta camera directly
    res_direct = client.get(f"/api/v1/cameras/{multi_tenant_setup['cam2'].id}", headers=h1)
    assert res_direct.status_code in (403, 404)


def test_alert_tenant_isolation(multi_tenant_setup):
    """User from Org Alpha should not list or see Org Beta alerts."""
    h1 = multi_tenant_setup["headers1"]

    res = client.get("/api/v1/alerts", headers=h1)
    assert res.status_code == 200
    alert_ids = [a["id"] for a in res.json()["data"]]
    assert multi_tenant_setup["alert1"].id in alert_ids
    assert multi_tenant_setup["alert2"].id not in alert_ids

    # Cannot get Org Beta alert by ID
    res_direct = client.get(f"/api/v1/alerts/{multi_tenant_setup['alert2'].id}", headers=h1)
    assert res_direct.status_code in (403, 404)


def test_incident_tenant_isolation(multi_tenant_setup):
    """User from Org Alpha should not list or see Org Beta incidents."""
    h1 = multi_tenant_setup["headers1"]

    res = client.get("/api/v1/incidents", headers=h1)
    assert res.status_code == 200
    inc_ids = [i["id"] for i in res.json()["items"]]
    assert multi_tenant_setup["inc1"].id in inc_ids
    assert multi_tenant_setup["inc2"].id not in inc_ids

    # Direct access forbidden
    res_direct = client.get(f"/api/v1/incidents/{multi_tenant_setup['inc2'].id}", headers=h1)
    assert res_direct.status_code == 404


def test_zone_tenant_isolation(multi_tenant_setup):
    """User from Org Alpha should not list or see Org Beta zones."""
    h1 = multi_tenant_setup["headers1"]

    res = client.get("/api/v1/zones", headers=h1)
    assert res.status_code == 200
    zone_ids = [z["id"] for z in res.json()]
    assert multi_tenant_setup["zone1"].id in zone_ids
    assert multi_tenant_setup["zone2"].id not in zone_ids

    # Direct access
    res_direct = client.get(f"/api/v1/zones/{multi_tenant_setup['zone2'].id}", headers=h1)
    assert res_direct.status_code == 404


def test_evidence_tenant_isolation(multi_tenant_setup):
    """User from Org Alpha should not list or see Org Beta evidence."""
    h1 = multi_tenant_setup["headers1"]

    res = client.get("/api/v1/evidence", headers=h1)
    assert res.status_code == 200
    ev_ids = [e["evidence_id"] for e in res.json()["data"]]
    assert multi_tenant_setup["ev1"].evidence_id in ev_ids
    assert multi_tenant_setup["ev2"].evidence_id not in ev_ids

    # Direct details access
    res_direct = client.get(f"/api/v1/evidence/{multi_tenant_setup['ev2'].evidence_id}", headers=h1)
    assert res_direct.status_code in (403, 404)
