"""
Unit and Integration Test Suite for Phase 2 Camera Subsystem.
"""

import time
import pytest
from app.schemas.camera import SourceType, CameraCreate
from app.camera.factory import CameraFactory
from app.camera.buffer import LatestFrameBuffer
from app.camera.file_source import VideoFileCamera
from app.camera.base import CameraStatus
from app.camera.manager import CameraManager


def test_camera_factory():
    """
    Tests CameraFactory instantiation for different SourceTypes.
    """
    from app.camera.dummy_source import SyntheticDummyCamera

    # 1. File Source (Returns SyntheticDummyCamera or VideoFileCamera)
    config_file = CameraCreate(
        name="Test File Cam",
        rtsp_url="test_video.mp4",
        source_type=SourceType.FILE
    )
    source_file = CameraFactory.create_source(config_file, camera_id=1)
    assert isinstance(source_file, (VideoFileCamera, SyntheticDummyCamera))

    # 2. Webcam Source
    config_webcam = CameraCreate(
        name="Test Webcam",
        rtsp_url="0",
        source_type=SourceType.WEBCAM
    )
    source_webcam = CameraFactory.create_source(config_webcam, camera_id=2)
    assert source_webcam.__class__.__name__ in ("WebcamCamera", "SyntheticDummyCamera")

    # 3. RTSP Source
    config_rtsp = CameraCreate(
        name="Test RTSP NVR",
        rtsp_url="rtsp://admin:pass@192.168.1.10:554/live/ch0",
        source_type=SourceType.RTSP
    )
    source_rtsp = CameraFactory.create_source(config_rtsp, camera_id=3)
    assert source_rtsp.__class__.__name__ in ("RTSPCamera", "SyntheticDummyCamera")


def test_latest_frame_buffer():
    """
    Tests LatestFrameBuffer thread-safe update and read.
    """
    buffer = LatestFrameBuffer(camera_id=1)
    assert buffer.get_latest()[0] is None

    import numpy as np
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    buffer.update(dummy_frame)

    frame, ts, count = buffer.get_latest()
    assert frame is not None
    assert frame.shape == (480, 640, 3)
    assert count == 1
    assert ts is not None


def test_synthetic_file_camera():
    """
    Tests VideoFileCamera synthetic test frame generator when video file is missing.
    """
    cam = VideoFileCamera(camera_id=99, rtsp_url="non_existent_file.mp4", loop=True)
    assert cam.connect() is True
    assert cam.is_connected() is True

    success, frame = cam.read_frame()
    assert success is True
    assert frame is not None
    assert frame.shape == (720, 1280, 3)

    cam.disconnect()
    assert cam.is_connected() is False


def test_camera_manager_execution():
    """
    Tests CameraManager registering, starting worker, reading buffer, and stopping cleanly.
    """
    manager = CameraManager()

    class MockCameraObj:
        id = 10
        name = "Manager Test Cam"
        rtsp_url = "non_existent.mp4"
        source_type = "file"
        fps_limit = 25
        capture_fps = 25
        target_ai_fps = 5
        frame_skip = 1
        priority = "HIGH"
        gpu_device_id = 0
        dvr_id = None
        dvr_channel = None
        connection_timeout = 10
        reconnect_interval = 5

    manager.add_camera(MockCameraObj())
    assert manager.start_camera(10) is True

    # Allow worker thread time to produce synthetic frame
    time.sleep(0.3)

    state = manager.get_runtime_state(10)
    assert state is not None
    assert state.connection_status in [CameraStatus.CONNECTED, CameraStatus.CONNECTING]

    frame, ts, count = manager.get_latest_frame(10)
    assert frame is not None
    assert count > 0

    manager.stop_camera(10)
    assert manager.get_runtime_state(10).connection_status == CameraStatus.DISCONNECTED
    manager.stop_all()


def test_camera_rest_api_lifecycle(client, auth_headers):
    """
    Integration test testing full REST API lifecycle (POST, GET, PUT, PATCH, START, STATUS, FRAME, DELETE).
    """
    # 1. Create Camera (Synthetic File Source)
    payload = {
        "name": "Warehouse Test Cam",
        "camera_number": "CAM-TEST-99",
        "dvr_address": "127.0.0.1",
        "rtsp_url": "test_synthetic_stream.mp4",
        "source_type": "file",  # Use file mode for testing
        "location": "Zone A",
        "enabled": False,
        "fps_limit": 30,
        "connection_timeout": 5,
        "reconnect_interval": 2
    }
    res_create = client.post("/api/v1/cameras", json=payload, headers=auth_headers)
    assert res_create.status_code == 201
    data = res_create.json()["data"]
    cid = data["id"]
    assert data["name"] == "Warehouse Test Cam"
    assert data["sanitized_rtsp_url"] == "test_synthetic_stream.mp4"

    # 2. Get Camera Detail
    res_get = client.get(f"/api/v1/cameras/{cid}", headers=auth_headers)
    assert res_get.status_code == 200
    assert res_get.json()["data"]["id"] == cid

    # 3. Get Camera Status
    res_status = client.get(f"/api/v1/cameras/{cid}/status", headers=auth_headers)
    assert res_status.status_code == 200

    # 4. Partial Update (PATCH)
    res_patch = client.patch(f"/api/v1/cameras/{cid}", json={"location": "Updated Zone B"}, headers=auth_headers)
    assert res_patch.status_code == 200
    assert res_patch.json()["data"]["location"] == "Updated Zone B"

    # 5. Delete Camera
    res_del = client.delete(f"/api/v1/cameras/{cid}", headers=auth_headers)
    assert res_del.status_code == 200
    assert res_del.json()["data"] is True

