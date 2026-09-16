"""
Integration tests for PPE Profiles, Safety Zones, Incidents, and Safety Reports REST APIs.
"""

import pytest
from fastapi.testclient import TestClient


def test_ppe_profiles_crud(client: TestClient, auth_headers: dict):
    # 1. List profiles
    res = client.get("/api/v1/ppe/profiles", headers=auth_headers)
    assert res.status_code == 200
    profiles = res.json()
    assert isinstance(profiles, list)

    # 2. Create profile
    payload = {
        "name": "Test Welding Zone Profile",
        "description": "Profile for test welding area",
        "required_equipment": ["helmet", "vest", "goggles", "gloves"],
        "optional_equipment": ["mask"]
    }
    res = client.post("/api/v1/ppe/profiles", json=payload, headers=auth_headers)
    assert res.status_code == 201
    created = res.json()
    assert created["name"] == payload["name"]
    prof_id = created["id"]

    # 3. Get single profile
    res = client.get(f"/api/v1/ppe/profiles/{prof_id}", headers=auth_headers)
    assert res.status_code == 200

    # 4. Delete profile
    res = client.delete(f"/api/v1/ppe/profiles/{prof_id}", headers=auth_headers)
    assert res.status_code in [200, 204]


def test_safety_zones_crud(client: TestClient, auth_headers: dict):
    # 1. Create Safety Zone
    payload = {
        "camera_id": 1,
        "name": "Chemical Hazard Zone",
        "zone_type": "HAZARD",
        "polygon_coordinates": [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]],
        "enabled": True
    }
    res = client.post("/api/v1/zones", json=payload, headers=auth_headers)
    assert res.status_code == 201
    created = res.json()
    assert created["name"] == payload["name"]
    zone_id = created["id"]

    # 2. List Safety Zones by camera
    res = client.get("/api/v1/zones?camera_id=1", headers=auth_headers)
    assert res.status_code == 200
    zones = res.json()
    assert any(z["id"] == zone_id for z in zones)

    # 3. Delete Safety Zone
    res = client.delete(f"/api/v1/zones/{zone_id}", headers=auth_headers)
    assert res.status_code in [200, 204]


def test_safety_statistics_and_reports(client: TestClient, auth_headers: dict):
    # 1. Safety statistics KPI endpoint
    res = client.get("/api/v1/safety/statistics", headers=auth_headers)
    assert res.status_code == 200
    stats = res.json()
    assert "total_cameras" in stats
    assert "daily_compliance_percentage" in stats

    # 2. Daily report endpoint
    res = client.get("/api/v1/reports/ppe/daily", headers=auth_headers)
    assert res.status_code == 200

    # 3. Incident report endpoint
    res = client.get("/api/v1/reports/incidents", headers=auth_headers)
    assert res.status_code == 200
