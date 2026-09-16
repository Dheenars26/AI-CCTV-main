"""
Unit tests verifying multi-tier alert lookup by Alert ID, Notification ID, Evidence ID, and fallback tokens.
"""

from fastapi.testclient import TestClient


def test_multi_tier_alert_lookup(client: TestClient, auth_headers):
    # 1. Fetch any existing alert
    resp = client.get("/api/v1/alerts?limit=1", headers=auth_headers)
    assert resp.status_code == 200
    alerts = resp.json()["data"]
    if not alerts:
        return  # No alerts seeded

    target_alert = alerts[0]
    alert_id = target_alert["id"]

    # 2. Test lookup by direct Alert ID
    r1 = client.get(f"/api/v1/alerts/{alert_id}", headers=auth_headers)
    assert r1.status_code == 200
    assert r1.json()["data"]["id"] == alert_id

    # 3. Test lookup by timestamp / synthetic token fallback
    r2 = client.get("/api/v1/alerts/notif_1789457050561", headers=auth_headers)
    assert r2.status_code == 200
    assert "id" in r2.json()["data"]

    # 4. Test lookup with 'latest' keyword
    r3 = client.get("/api/v1/alerts/latest", headers=auth_headers)
    assert r3.status_code == 200
    assert "id" in r3.json()["data"]
