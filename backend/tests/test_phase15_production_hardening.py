"""
Unit & Integration Test Suite for Phase 15 Production Hardening.
Verifies 100% backend frontend-independence, Prometheus metrics exposition,
health/readiness probes (/healthz & /readyz), evidence disk retention cleaner,
and database backup archive SHA-256 integrity generation.
"""

import os
import glob
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.utils.metrics import metrics_collector
from app.services.retention_service import EvidenceRetentionService
from scripts.backup_db import execute_database_backup


def test_backend_frontend_decoupling_audit():
    """1. Audits backend codebase ensuring ZERO imports or dependencies on React/frontend code."""
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app"))
    py_files = glob.glob(os.path.join(backend_dir, "**", "*.py"), recursive=True)

    forbidden_tokens = ["react", "vite", "tailwind", "jsx", "tsx", "src/pages"]

    for file_path in py_files:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read().lower()
            for token in forbidden_tokens:
                assert token not in content, f"Frontend dependency '{token}' found in backend file: {file_path}"


def test_prometheus_metrics_generation():
    """2. Tests Prometheus Metrics Engine formatting and safe label validation."""
    metrics_collector.record_camera_fps("CAM-01", 24.5)
    metrics_collector.record_camera_status("CAM-01", connected=True)
    metrics_collector.record_dvr_status("DVR-01", online=True)
    metrics_collector.record_detection("fire")
    metrics_collector.record_alert("CRITICAL")

    output = metrics_collector.generate_prometheus_output()

    assert "cctv_camera_fps" in output
    assert "cctv_camera_connection_status" in output
    assert "cctv_dvr_connection_status" in output
    assert 'detection_class="fire"' in output
    assert 'severity="CRITICAL"' in output

    # High-cardinality leak checks: Verify passwords, RTSP URLs, or IPs are NOT present!
    assert "rtsp://" not in output
    assert "password" not in output.lower()


def test_healthz_and_readyz_probes(client: TestClient):
    """3. Tests /healthz liveness probe and /readyz readiness probe endpoints."""
    # 1. Liveness probe
    h_resp = client.get("/api/v1/system/healthz")
    assert h_resp.status_code == 200
    assert h_resp.json()["status"] == "HEALTHY"

    # 2. Readiness probe
    r_resp = client.get("/api/v1/system/readyz")
    assert r_resp.status_code == 200
    data = r_resp.json()
    assert data["status"] in ("READY", "DEGRADED", "NOT_READY")
    assert data["database_connected"] is True


def test_evidence_retention_sweep(db: Session):
    """4. Tests EvidenceRetentionService retention sweep and emergency disk cleaner."""
    ret_service = EvidenceRetentionService(
        retention_days=30,
        min_free_disk_gb=1.0,
        max_disk_usage_percent=99.0
    )

    res = ret_service.run_retention_sweep(db)
    assert "purged_count" in res
    assert "freed_bytes" in res


def test_database_backup_script(tmp_path):
    """5. Tests backup_db.py database archive generation and SHA-256 hash file creation."""
    out_dir = str(tmp_path / "backups")
    backup_path = execute_database_backup(output_dir=out_dir, retention_count=5)

    assert os.path.exists(backup_path)
    assert os.path.exists(backup_path + ".sha256")
