"""
Unit & Integration Tests for POST /api/v1/detections/analyze Endpoint.
Verifies multi-target analysis (fire, smoke, vest, glasses) via multipart and base64 payloads.
"""

import base64
import io
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient


def create_dummy_jpeg(color=(128, 128, 128), width=320, height=240) -> bytes:
    img = np.full((height, width, 3), color, dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return buf.tobytes()


def test_analyze_multipart_upload(client: TestClient, auth_headers: dict):
    jpeg_bytes = create_dummy_jpeg()
    files = {"file": ("test_frame.jpg", io.BytesIO(jpeg_bytes), "image/jpeg")}

    res = client.post(
        "/api/v1/detections/analyze?required_equipment=vest,glasses&return_annotated=true",
        files=files,
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["success"] is True
    assert "summary" in data
    assert "workers" in data
    assert "detections" in data
    assert "inference_time_ms" in data
    assert data["image_width"] == 320
    assert data["image_height"] == 240
    assert data["annotated_image_base64"] is not None
    assert data["annotated_image_base64"].startswith("data:image/jpeg;base64,")


def test_analyze_base64_payload(client: TestClient, auth_headers: dict):
    jpeg_bytes = create_dummy_jpeg(color=(40, 40, 200), width=400, height=300)
    b64 = "data:image/jpeg;base64," + base64.b64encode(jpeg_bytes).decode("utf-8")

    payload = {
        "image_base64": b64,
        "required_equipment": ["vest", "glasses"],
        "return_annotated": True,
        "camera_id": 2,
    }

    res = client.post(
        "/api/v1/detections/analyze",
        json=payload,
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["success"] is True
    assert data["image_width"] == 400
    assert data["image_height"] == 300
    assert "summary" in data
    assert "fire_detected" in data["summary"]
    assert "smoke_detected" in data["summary"]
    assert "total_vests" in data["summary"]
    assert "total_glasses" in data["summary"]


def test_analyze_invalid_payload_error(client: TestClient, auth_headers: dict):
    # Missing both file and base64
    res = client.post("/api/v1/detections/analyze", json={}, headers=auth_headers)
    assert res.status_code == 400
    assert "No image provided" in str(res.json())

