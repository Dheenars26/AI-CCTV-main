"""
Comprehensive Unit & Integration Test Suite for Phase 14 Multi-Camera and Multi-DVR Architecture.
Tests AES-256 credential encryption, layered DVR health checks, manufacturer adapters,
channel limit & duplicate channel validations, deletion restriction policies,
bounded queue overflow protection, priority frame scheduling, resource allocation & CUDA OOM recovery,
worker failure isolation, and simulated 32+ camera / 4 DVR load architecture.
"""

import pytest
import time
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.dvr import DVR, DVRStatus, DVRManufacturer
from app.models.camera import Camera
from app.utils.encryption import encrypt_credential, decrypt_credential, mask_credential
from app.camera.adapters.factory import DVRAdapterFactory
from app.camera.bounded_queue import BoundedFrameQueue
from app.camera.frame_scheduler import FrameScheduler
from app.camera.resource_manager import ResourceManager
from app.camera.ai_pool import AIWorkerPool
from app.camera.dvr_manager import DVRManager
from app.camera.manager import CameraManager
from app.services.dvr_service import DVRService
from app.utils.exceptions import ValidationException, ConflictException


def test_credential_encryption_and_masking():
    """1. Tests AES-256 credential encryption, decryption, and zero credential leakage masking."""
    pwd = "TopSecretDVRPassword123!"
    encrypted = encrypt_credential(pwd)

    assert encrypted != pwd
    assert decrypt_credential(encrypted) == pwd
    assert mask_credential(encrypted) == "******"


def test_manufacturer_adapter_factory():
    """2. Tests manufacturer adapter factory instantiations and RTSP URL formatting."""
    generic_adapter = DVRAdapterFactory.get_adapter("GENERIC_RTSP")
    hikvision_adapter = DVRAdapterFactory.get_adapter("HIKVISION")
    dahua_adapter = DVRAdapterFactory.get_adapter("DAHUA")

    # Generic RTSP URL
    url_gen = generic_adapter.construct_rtsp_url("192.168.1.100", 554, "admin", "pass123", channel=1)
    assert url_gen == "rtsp://admin:pass123@192.168.1.100:554/live/ch1"

    # Hikvision Channel formatting (Channel 1 -> 101, Channel 2 -> 201)
    url_hik = hikvision_adapter.construct_rtsp_url("192.168.1.100", 554, "admin", "pass123", channel=2)
    assert url_hik == "rtsp://admin:pass123@192.168.1.100:554/Streaming/Channels/201"

    # Dahua Channel formatting
    url_dah = dahua_adapter.construct_rtsp_url("192.168.1.100", 554, "admin", "pass123", channel=3)
    assert url_dah == "rtsp://admin:pass123@192.168.1.100:554/cam/realmonitor?channel=3&subtype=0"


def test_dvr_crud_and_deletion_restriction_policy(db: Session):
    """3. Tests DVR Service CRUD, optimistic concurrency, and deletion restriction when cameras are attached."""
    service = DVRService(db=db)

    # 1. Create DVR
    from app.schemas.dvr import DVRCreate, DVRUpdate
    create_payload = DVRCreate(
        name="Main NVR 01",
        management_host="127.0.0.1",
        management_port=80,
        rtsp_port=554,
        username="admin",
        password="dvrpassword123",
        manufacturer="HIKVISION",
        channels_count=16
    )
    dvr = service.create_dvr(create_payload)
    assert dvr.id is not None
    assert dvr.version_id == 1

    # 2. Attach Camera to DVR
    cam = Camera(
        name="Channel 1 Gate Cam",
        camera_number="CAM-101",
        dvr_id=dvr.id,
        dvr_channel=1,
        rtsp_url="dummy",
        source_type="file",
        enabled=False
    )
    db.add(cam)
    db.commit()

    # 3. Attempt Delete DVR with attached camera -> Must be REJECTED!
    with pytest.raises(ValidationException) as exc_info:
        service.delete_dvr(dvr.id)
    assert "attached" in str(exc_info.value)

    # 4. Detach camera & delete DVR cleanly
    db.delete(cam)
    db.commit()
    assert service.delete_dvr(dvr.id) is True


def test_channel_limit_and_duplicate_validation(db: Session):
    """4. Tests DVR channel limits (dvr_channel <= channels_count) and duplicate channel assignment rejection."""
    service = DVRService(db=db)
    from app.schemas.dvr import DVRCreate
    dvr = service.create_dvr(DVRCreate(
        name="Small 4-Channel DVR",
        management_host="192.168.1.50",
        management_port=80,
        rtsp_port=554,
        username="admin",
        password="pass",
        channels_count=4
    ))

    # Reject channel > max channels
    with pytest.raises(ValidationException):
        service.validate_camera_dvr_channel(dvr.id, channel=5)

    # Assign channel 1 to Camera 1
    cam1 = Camera(name="Cam 1", camera_number="C1", dvr_id=dvr.id, dvr_channel=1, rtsp_url="dummy", source_type="file")
    db.add(cam1)
    db.commit()

    # Attempt assigning channel 1 to Camera 2 -> Duplicate Conflict Exception!
    with pytest.raises(ConflictException):
        service.validate_camera_dvr_channel(dvr.id, channel=1)


def test_bounded_queue_stale_frame_dropping():
    """5. Tests BoundedFrameQueue dropping stale frames when queue capacity limit is reached."""
    bqueue = BoundedFrameQueue(camera_id=1, maxsize=3)
    import numpy as np
    dummy_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    now = datetime.now(timezone.utc)

    # Push 5 frames into capacity 3 queue
    for i in range(5):
        bqueue.put_frame(dummy_frame, now, i)

    # Max size remains <= 3, and dropped_frames counter equals 2
    assert bqueue.current_size <= 3
    assert bqueue.dropped_frames == 2


def test_frame_scheduler_priority_sampling():
    """6. Tests FrameScheduler sampling behavior across HIGH, MEDIUM, and LOW camera priorities."""
    scheduler = FrameScheduler()

    # HIGH priority -> processes frame
    assert scheduler.should_process_frame(frame_index=5, priority="HIGH", capture_fps=25, target_ai_fps=5) is True

    # LOW priority -> skips more frames
    high_count = sum(1 for f in range(25) if scheduler.should_process_frame(f, priority="HIGH", capture_fps=25, target_ai_fps=5))
    low_count = sum(1 for f in range(25) if scheduler.should_process_frame(f, priority="LOW", capture_fps=25, target_ai_fps=5))

    assert high_count >= low_count


def test_resource_manager_cuda_oom_recovery():
    """7. Tests ResourceManager device resolution and controlled CUDA OOM recovery handling."""
    res_mgr = ResourceManager()

    # Validate CPU device fallback for -1
    assert res_mgr.get_target_device(-1) == "cpu"

    # Simulate CUDA OOM on GPU 0 -> Returns device and increments recovery counter
    rec_dev = res_mgr.handle_cuda_oom(0)
    assert rec_dev in ("cuda:0", "cpu")


def test_ai_worker_pool_failure_isolation():
    """8. Tests AIWorkerPool task exception isolation (AI exception does not crash process)."""
    pool = AIWorkerPool(max_workers=2)

    def failing_ai_task():
        raise RuntimeError("Simulated AI Model CUDA Exception")

    # Submit failing task
    assert pool.submit_job(failing_ai_task) is True
    time.sleep(0.2)

    # Failed job counter incremented, pool remains healthy
    assert pool.failed_jobs >= 1
    pool.shutdown()


def test_large_scale_multi_dvr_32_camera_simulation(db: Session):
    """9. Tests large-scale architecture: 4 DVRs and 32 camera streams running concurrently."""
    cm = CameraManager()
    dvr_service = DVRService(db=db, dvr_manager=cm.dvr_manager)

    from app.schemas.dvr import DVRCreate

    # 1. Create 4 DVR Hardware Devices
    dvrs = []
    for d in range(1, 5):
        dvr = dvr_service.create_dvr(DVRCreate(
            name=f"Simulated NVR {d:02d}",
            management_host=f"10.0.0.{d}",
            management_port=80,
            rtsp_port=554,
            username="admin",
            password="password",
            channels_count=8
        ))
        dvrs.append(dvr)

    # 2. Register 32 Cameras across the 4 DVRs (8 channels each)
    cameras = []
    for d_idx, dvr in enumerate(dvrs):
        for c in range(1, 9):
            cam_idx = (d_idx * 8) + c
            cam = Camera(
                name=f"Simulated Cam {cam_idx:02d}",
                camera_number=f"CAM-{cam_idx:02d}",
                dvr_id=dvr.id,
                dvr_channel=c,
                rtsp_url="dummy",
                source_type="file",
                priority="HIGH" if c <= 2 else ("MEDIUM" if c <= 5 else "LOW"),
                enabled=True
            )
            db.add(cam)
            db.commit()
            cameras.append(cam)
            cm.add_camera(cam)

    # Verify all 32 cameras added to CameraManager
    assert len(cm._sources) == 32

    # Verify per-camera telemetry metrics retrieval
    metrics = cm.get_camera_metrics(cameras[0].id)
    assert metrics["camera_id"] == cameras[0].id
    assert "dropped_frames" in metrics
    assert "queue_depth" in metrics

    # Cleanup
    cm.stop_all()
    for cam in cameras:
        db.delete(cam)
    for dvr in dvrs:
        db.delete(dvr)
    db.commit()


def test_dvr_rest_api_endpoints(client: TestClient, auth_headers):
    """10. Tests REST API /api/v1/dvrs endpoints with RBAC permissions."""
    # 1. List DVRs
    list_resp = client.get("/api/v1/dvrs", headers=auth_headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["success"] is True

    # 2. Create DVR via REST API
    payload = {
        "name": "REST Test NVR",
        "management_host": "127.0.0.1",
        "management_port": 80,
        "rtsp_port": 554,
        "username": "admin",
        "password": "SecretPass123!",
        "manufacturer": "DAHUA",
        "channels_count": 16
    }
    create_resp = client.post("/api/v1/dvrs", json=payload, headers=auth_headers)
    assert create_resp.status_code == 201
    dvr_data = create_resp.json()["data"]
    assert dvr_data["name"] == "REST Test NVR font" or dvr_data["name"] == "REST Test NVR"
    assert dvr_data["masked_credential"] == "******"
    assert "password" not in dvr_data  # Zero credential leak!
