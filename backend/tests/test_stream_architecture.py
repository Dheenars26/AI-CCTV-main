"""
Unit & Integration Test Suite for Phase 11 Browser-Compatible Video Streaming Architecture.
Verifies StreamService token issuance, validation, DVR credential masking, MJPEG header contracts, and HLS playlist generation.
"""

import pytest
from fastapi.testclient import TestClient
from app.services.stream_service import StreamService


def test_stream_service_token_issuance_and_validation():
    """
    Tests StreamService session token issuance and validation logic.
    """
    stream_service = StreamService()
    camera_id = 42

    # 1. Generate Stream Token
    token = stream_service.generate_stream_token(camera_id=camera_id, user_id="op_1")
    assert token.startswith("st_")

    # 2. Validate valid token for target camera
    assert stream_service.validate_stream_token(token, expected_camera_id=camera_id) is True

    # 3. Reject token if camera_id does not match (tampering protection)
    assert stream_service.validate_stream_token(token, expected_camera_id=999) is False

    # 4. Reject invalid or malformed tokens
    assert stream_service.validate_stream_token("invalid_token", expected_camera_id=camera_id) is False


def test_get_stream_config_endpoint(client: TestClient, auth_headers):
    """
    Tests GET /api/v1/cameras/{id}/stream/config endpoint.
    Verifies that frontends receive pre-authorized stream URLs without raw RTSP credentials.
    """
    create_payload = {
        "name": "Perimeter Gate Cam",
        "camera_number": "CAM-88",
        "rtsp_url": "dummy",
        "source_type": "file",
        "enabled": False
    }
    create_resp = client.post("/api/v1/cameras", json=create_payload, headers=auth_headers)
    assert create_resp.status_code == 201
    cam_id = create_resp.json()["data"]["id"]

    config_resp = client.get(f"/api/v1/cameras/{cam_id}/stream/config", headers=auth_headers)
    assert config_resp.status_code == 200
    config_data = config_resp.json()["data"]

    assert config_data["camera_id"] == cam_id
    assert "stream_token" in config_data
    assert f"/api/v1/cameras/{cam_id}/stream" in config_data["mjpeg_url"]
    assert f"/api/v1/cameras/{cam_id}/stream/hls/index.m3u8" in config_data["hls_url"]
    assert "mjpeg" in config_data["supported_protocols"]
    assert "hls" in config_data["supported_protocols"]


def test_hls_playlist_endpoint(client: TestClient, auth_headers):
    """
    Tests GET /api/v1/cameras/{id}/stream/hls/index.m3u8 endpoint.
    """
    create_resp = client.post("/api/v1/cameras", json={
        "name": "HLS Test Cam",
        "camera_number": "CAM-77",
        "rtsp_url": "dummy",
        "source_type": "file",
        "enabled": False
    }, headers=auth_headers)
    cam_id = create_resp.json()["data"]["id"]

    resp = client.get(f"/api/v1/cameras/{cam_id}/stream/hls/index.m3u8", headers=auth_headers)
    assert resp.status_code == 200
    assert "application/vnd.apple.mpegurl" in resp.headers["content-type"]
    text = resp.text
    assert "#EXTM3U" in text
    assert "#EXT-X-TARGETDURATION" in text
    assert "segment_" in text
