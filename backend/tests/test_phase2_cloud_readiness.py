"""
Phase 2 Cloud Deployment Readiness Tests:
Tests endpoints /healthz, /readyz, /metrics, REST API (/api/v1/), and WebSocket ticket handshake.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_healthz_endpoint():
    """Verify top-level /healthz liveness probe."""
    res = client.get("/healthz")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("healthy", "ok", "HEALTHY")
    assert data.get("service") == "ai-cctv-monitor"


def test_readyz_endpoint():
    """Verify top-level /readyz readiness probe."""
    res = client.get("/readyz")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("READY", "DEGRADED", "NOT_READY")
    assert "database_connected" in data
    assert data["database_connected"] is True


def test_metrics_endpoint():
    """Verify Prometheus metrics exposition at /metrics."""
    res = client.get("/metrics")
    assert res.status_code == 200
    assert "text/plain" in res.headers.get("content-type", "")
    content = res.text
    assert "cctv_" in content or "HELP" in content


def test_rest_api_prefix_root(auth_headers):
    """Verify REST API root /api/v1/ prefix."""
    res = client.get("/api/v1/cameras", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "data" in data or isinstance(data, list)
