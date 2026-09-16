"""
Camera Management REST API Endpoints.
Full CRUD, Start/Stop stream controls, live status probes, and JPEG verification snapshots.
"""

import asyncio
import time
import cv2
import numpy as np
from typing import List, Optional
from fastapi import APIRouter, Depends, Response, status, Request, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.camera import (
    CameraCreate,
    CameraUpdate,
    CameraResponse,
    CameraRuntimeStateResponse
)
from app.schemas.common import ResponseModel
from app.services.camera_service import CameraService
from app.camera.manager import CameraManager
from app.api.v1.dependencies.permissions import RequirePermission
from app.models.user import User
from app.utils.exceptions import AppException
from app.utils.logger import logger

router = APIRouter(prefix="/cameras", tags=["Cameras Management"])


def get_camera_service(request: Request, db: Session = Depends(get_db)) -> CameraService:
    """
    FastAPI dependency injecting CameraService with request-scoped DB session
    and application-scoped CameraManager instance.
    """
    camera_manager = getattr(request.app.state, "camera_manager", None)
    if camera_manager is None:
        from app.camera.manager import CameraManager
        camera_manager = CameraManager()
        request.app.state.camera_manager = camera_manager

    return CameraService(db=db, camera_manager=camera_manager)


from app.utils.security import sanitize_rtsp_url
from app.models.camera import Camera


def _build_camera_response(c: Camera) -> CameraResponse:
    return CameraResponse(
        id=c.id,
        name=c.name,
        camera_number=c.camera_number,
        dvr_id=getattr(c, "dvr_id", None),
        dvr_channel=getattr(c, "dvr_channel", None),
        dvr_address=c.dvr_address,
        sanitized_rtsp_url=sanitize_rtsp_url(c.rtsp_url),
        source_type=c.source_type,
        location=c.location,
        latitude=getattr(c, "latitude", 13.0827),
        longitude=getattr(c, "longitude", 80.2707),
        enabled=c.enabled,
        fire_smoke_enabled=getattr(c, "fire_smoke_enabled", True),
        ppe_enabled=getattr(c, "ppe_enabled", True),
        person_enabled=getattr(c, "person_enabled", True),
        zone_enabled=getattr(c, "zone_enabled", True),
        ppe_inference_interval_sec=getattr(c, "ppe_inference_interval_sec", 0.5),
        priority=getattr(c, "priority", "HIGH"),
        capture_fps=getattr(c, "capture_fps", 25),
        target_ai_fps=getattr(c, "target_ai_fps", 5),
        gpu_device_id=getattr(c, "gpu_device_id", 0),
        fps_limit=c.fps_limit,
        connection_timeout=c.connection_timeout,
        reconnect_interval=c.reconnect_interval,
        created_at=c.created_at if getattr(c, "created_at", None) is not None else datetime.now(timezone.utc),
        updated_at=c.updated_at if getattr(c, "updated_at", None) is not None else datetime.now(timezone.utc)
    )


@router.get(
    "",
    response_model=ResponseModel[List[CameraResponse]],
    summary="List CCTV Cameras",
    description="Retrieves all registered CCTV / NVR camera configurations. RTSP passwords are strictly masked."
)
async def list_cameras(
    current_user: User = Depends(RequirePermission("cameras:read")),
    service: CameraService = Depends(get_camera_service)
):
    cameras = service.list_cameras()
    response_data = [_build_camera_response(c) for c in cameras]
    return ResponseModel(data=response_data)


@router.post(
    "",
    response_model=ResponseModel[CameraResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register Camera",
    description="Registers a new CCTV / NVR RTSP camera or test stream source."
)
async def create_camera(
    payload: CameraCreate,
    current_user: User = Depends(RequirePermission("cameras:write")),
    service: CameraService = Depends(get_camera_service)
):
    c = service.create_camera(payload)
    return ResponseModel(data=_build_camera_response(c))


@router.get(
    "/{camera_id}",
    response_model=ResponseModel[CameraResponse],
    summary="Get Camera Configuration",
    description="Retrieves single camera configuration by ID."
)
async def get_camera(
    camera_id: int,
    current_user: User = Depends(RequirePermission("cameras:read")),
    service: CameraService = Depends(get_camera_service)
):
    c = service.get_camera(camera_id)
    return ResponseModel(data=_build_camera_response(c))


@router.put(
    "/{camera_id}",
    response_model=ResponseModel[CameraResponse],
    summary="Update Camera (Full)",
    description="Replaces camera configuration."
)
async def update_camera_full(
    camera_id: int,
    payload: CameraCreate,
    current_user: User = Depends(RequirePermission("cameras:write")),
    service: CameraService = Depends(get_camera_service)
):
    update_payload = CameraUpdate(**payload.model_dump())
    c = service.update_camera(camera_id, update_payload)
    return ResponseModel(data=_build_camera_response(c))


@router.patch(
    "/{camera_id}",
    response_model=ResponseModel[CameraResponse],
    summary="Update Camera (Partial)",
    description="Partially updates camera configuration fields."
)
async def update_camera_partial(
    camera_id: int,
    payload: CameraUpdate,
    current_user: User = Depends(RequirePermission("cameras:write")),
    service: CameraService = Depends(get_camera_service)
):
    c = service.update_camera(camera_id, payload)
    return ResponseModel(data=_build_camera_response(c))


@router.delete(
    "/{camera_id}",
    response_model=ResponseModel[bool],
    summary="Delete Camera",
    description="Stops stream ingestion worker and removes camera configuration from system."
)
async def delete_camera(
    camera_id: int,
    current_user: User = Depends(RequirePermission("cameras:write")),
    service: CameraService = Depends(get_camera_service)
):
    success = service.delete_camera(camera_id)
    return ResponseModel(data=success)


@router.delete(
    "",
    response_model=ResponseModel[int],
    summary="Bulk Delete All Cameras",
    description="Stops stream ingestion workers for all registered cameras and purges configurations from system."
)
async def delete_all_cameras(
    current_user: User = Depends(RequirePermission("cameras:write")),
    service: CameraService = Depends(get_camera_service)
):
    count = service.delete_all_cameras()
    return ResponseModel(data=count)



@router.get(
    "/{camera_id}/status",
    response_model=ResponseModel[CameraRuntimeStateResponse],
    summary="Get Camera Stream Status",
    description="Retrieves live runtime metrics (FPS, resolution, connection state, reconnect attempts)."
)
async def get_camera_status(
    camera_id: int,
    current_user: User = Depends(RequirePermission("cameras:read")),
    service: CameraService = Depends(get_camera_service)
):
    status_data = service.get_camera_status(camera_id)
    return ResponseModel(data=status_data)


@router.post(
    "/{camera_id}/start",
    response_model=ResponseModel[CameraRuntimeStateResponse],
    summary="Start Camera Stream",
    description="Starts background ingestion worker thread for camera."
)
async def start_camera(
    camera_id: int,
    current_user: User = Depends(RequirePermission("cameras:write")),
    service: CameraService = Depends(get_camera_service)
):
    status_data = service.start_camera(camera_id)
    return ResponseModel(data=status_data)


@router.post(
    "/{camera_id}/stop",
    response_model=ResponseModel[CameraRuntimeStateResponse],
    summary="Stop Camera Stream",
    description="Stops background ingestion worker thread and releases stream capture resources."
)
async def stop_camera(
    camera_id: int,
    current_user: User = Depends(RequirePermission("cameras:write")),
    service: CameraService = Depends(get_camera_service)
):
    status_data = service.stop_camera(camera_id)
    return ResponseModel(data=status_data)


@router.get(
    "/{camera_id}/frame",
    summary="JPEG Snapshot Verification Endpoint",
    description="Returns a single JPEG image frame from the latest buffer for verification testing.",
    responses={
        200: {
            "content": {"image/jpeg": {}},
            "description": "Returns raw JPEG image frame bytes."
        }
    }
)
async def get_camera_frame(
    camera_id: int,
    current_user: User = Depends(RequirePermission("cameras:read")),
    service: CameraService = Depends(get_camera_service)
):
    jpeg_bytes = service.get_camera_jpeg_snapshot(camera_id)
    return Response(content=jpeg_bytes, media_type="image/jpeg")


from app.schemas.stream import StreamConfigResponse
from app.services.stream_service import StreamService


@router.get(
    "/{camera_id}/stream/config",
    response_model=ResponseModel[StreamConfigResponse],
    summary="Get Authorized Stream Configuration",
    description="Returns authorized browser-compatible streaming protocol URLs (MJPEG, HLS, WebRTC) without leaking DVR credentials."
)
def get_stream_config(
    camera_id: int,
    request: Request,
    current_user: User = Depends(RequirePermission("cameras:read")),
    service: CameraService = Depends(get_camera_service)
):
    camera = service.get_camera(camera_id)
    camera_manager = getattr(request.app.state, "camera_manager", None)
    stream_service = StreamService(camera_manager=camera_manager)
    config = stream_service.get_stream_config(camera=camera)
    return ResponseModel(data=config)


def _generate_placeholder_jpeg(text: str = "Connecting Camera Stream...") -> bytes:
    """Generates a lightweight fallback JPEG image matrix for video stream warm-up."""
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(img, text, (90, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 215, 255), 2, cv2.LINE_AA)
    cv2.putText(img, "Please wait, initializing stream worker...", (130, 270), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (170, 170, 170), 1, cv2.LINE_AA)
    _, encoded = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return encoded.tobytes()


def _is_camera_enabled_in_db(camera_id: int) -> bool:
    """Helper to query camera-enabled status."""
    return True


async def mjpeg_frame_generator(
    camera_id: int,
    camera_manager: Optional[CameraManager],
    service: Optional[CameraService] = None,
    request: Optional[Request] = None
):
    """
    Generates continuous multipart MJPEG frame stream for direct browser rendering.
    Handles buffer warm-up, auto-start, zero CPU blocking streaming, and instant disconnect cleanup.
    """
    if not camera_manager:
        placeholder = _generate_placeholder_jpeg("Camera Service Initializing...")
        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + placeholder + b"\r\n"
        return

    # In-memory camera enabled check (zero SQLite queries on event loop)
    is_enabled = camera_manager.is_camera_enabled(camera_id) if hasattr(camera_manager, "is_camera_enabled") else True

    # Ensure camera is registered in CameraManager
    if service and camera_id not in camera_manager._sources:
        try:
            cam_obj = service.get_camera(camera_id)
            camera_manager.add_camera(cam_obj)
        except Exception as err:
            logger.warning(f"mjpeg_frame_generator: Failed to auto-register camera {camera_id}: {str(err)}")

    if is_enabled and not camera_manager.is_running(camera_id):
        camera_manager.start_camera(camera_id)

    # Yield first real frame from buffer if already available (instant start)
    buf = camera_manager._buffers.get(camera_id)
    if is_enabled and buf:
        jpeg_bytes, _, _ = buf.get_latest_jpeg()
        if jpeg_bytes:
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n"
        else:
            placeholder = _generate_placeholder_jpeg("Connecting to Camera Stream...")
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + placeholder + b"\r\n"
    else:
        placeholder = _generate_placeholder_jpeg("Camera Stream is Off" if not is_enabled else "Connecting to Camera Stream...")
        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + placeholder + b"\r\n"
        if not is_enabled:
            return

    last_sent_count = -1
    last_real_frame_time = time.time()
    last_placeholder_sent_time = 0.0
    last_sent_time = 0.0

    try:
        while True:
            # 1. Instant client disconnect detection to eliminate zombie stream workers
            if request and await request.is_disconnected():
                logger.debug(f"mjpeg_frame_generator: Client disconnected for camera {camera_id}")
                break

            # 2. Fast in-memory camera enabled check
            if camera_manager and hasattr(camera_manager, "is_camera_enabled"):
                is_enabled = camera_manager.is_camera_enabled(camera_id)

            if not is_enabled:
                if camera_manager.is_running(camera_id):
                    camera_manager.stop_camera(camera_id)
                placeholder = _generate_placeholder_jpeg("Camera Stream is Off")
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + placeholder + b"\r\n"
                break

            # Ensure background ingestion worker is running ONLY when enabled
            if is_enabled and not camera_manager.is_running(camera_id):
                camera_manager.start_camera(camera_id)

            buf = camera_manager._buffers.get(camera_id)
            if buf and buf._frame_count != last_sent_count:
                jpeg_bytes, ts, count = buf.get_latest_jpeg()
                if jpeg_bytes is not None and count != last_sent_count:
                    last_sent_count = count
                    now_t = time.time()
                    last_real_frame_time = now_t
                    last_sent_time = now_t
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n"
                    )

            # Only yield reconnecting placeholder if NO real frame has been received for over 4.0 continuous seconds
            now_t = time.time()
            if (now_t - last_real_frame_time) > 4.0:
                if (now_t - last_placeholder_sent_time) >= 2.0:
                    last_placeholder_sent_time = now_t
                    placeholder_frame = _generate_placeholder_jpeg("Camera Stream Connecting...")
                    yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + placeholder_frame + b"\r\n"

            # Low-latency adaptive pacing:
            # Pace stream at up to ~30 FPS without accumulating latency.
            # If waiting for a new camera frame, sleep 10ms to deliver next frame smoothly.
            elapsed_since_sent = time.time() - last_sent_time
            if elapsed_since_sent < 0.033:  # ~30 FPS ceiling
                sleep_duration = max(0.010, 0.033 - elapsed_since_sent)
                await asyncio.sleep(sleep_duration)
            else:
                await asyncio.sleep(0.010)
    except (asyncio.CancelledError, GeneratorExit, ConnectionResetError, BrokenPipeError):
        pass
    except Exception as err:
        logger.warning(f"mjpeg_frame_generator: Stream exception for camera {camera_id}: {str(err)}")
        try:
            placeholder = _generate_placeholder_jpeg("Stream Reconnecting...")
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + placeholder + b"\r\n"
        except Exception:
            pass


@router.get(
    "/{camera_id}/stream",
    summary="Live MJPEG Stream",
    description="Streams continuous processed video frames in MJPEG multipart format directly to web browsers.",
    responses={
        200: {
            "content": {"multipart/x-mixed-replace": {}},
            "description": "Returns continuous MJPEG video stream."
        }
    }
)
async def stream_camera_video(
    camera_id: int,
    request: Request,
    stream_token: Optional[str] = Query(None, description="Optional stream authorization token"),
    service: CameraService = Depends(get_camera_service)
):
    camera_manager = getattr(request.app.state, "camera_manager", None)
    if not (camera_manager and camera_id in getattr(camera_manager, "_sources", {})):
        service.get_camera(camera_id)  # Verifies camera exists in DB if not in memory

    # Optional Stream Token Validation
    if stream_token:
        stream_service = StreamService()
        if not stream_service.validate_stream_token(stream_token, camera_id):
            raise AppException(
                message="Invalid or expired stream authorization token",
                code="INVALID_STREAM_TOKEN",
                status_code=status.HTTP_403_FORBIDDEN
            )

    return StreamingResponse(
        mjpeg_frame_generator(camera_id, camera_manager, service, request),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Accel-Buffering": "no",  # Disable nginx/proxy buffering
        }
    )


@router.get(
    "/{camera_id}/stream/hls/index.m3u8",
    summary="HLS M3U8 Master Playlist",
    description="Returns HTTP Live Streaming (HLS) playlist format for HTML5 <video> tag playback.",
    responses={
        200: {
            "content": {"application/vnd.apple.mpegurl": {}},
            "description": "M3U8 HLS Master Playlist"
        }
    }
)
def get_hls_playlist(
    camera_id: int,
    stream_token: Optional[str] = Query(None),
    service: CameraService = Depends(get_camera_service)
):
    camera = service.get_camera(camera_id)
    stream_service = StreamService()
    tok = stream_token or stream_service.generate_stream_token(camera_id)
    playlist = stream_service.generate_hls_playlist(camera_id, tok)
    return Response(content=playlist, media_type="application/vnd.apple.mpegurl")


@router.get(
    "/{camera_id}/detections",
    summary="Get Camera Detection History",
    description="Retrieves raw AI prediction detection history specific to this camera ID."
)
async def get_camera_detections(
    camera_id: int,
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(RequirePermission("cameras:read")),
    db: Session = Depends(get_db)
):
    from app.models.detection import Detection
    from app.schemas.detection import DetectionResponse
    items = db.query(Detection).filter(Detection.camera_id == camera_id).order_by(Detection.timestamp.desc()).limit(limit).all()
    return ResponseModel(data=[DetectionResponse.model_validate(d) for d in items])


@router.get(
    "/{camera_id}/ppe-status",
    summary="Get Camera PPE Compliance Status",
    description="Returns current PPE compliance status, worker count, and recent violations for this camera ID."
)
async def get_camera_ppe_status(
    camera_id: int,
    current_user: User = Depends(RequirePermission("cameras:read")),
    db: Session = Depends(get_db)
):
    from app.models.ppe import PPEViolation, PersonDetection
    from app.services.camera_service import CameraService
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")

    recent_viols = db.query(PPEViolation).filter(PPEViolation.camera_id == camera_id).order_by(PPEViolation.timestamp.desc()).limit(5).all()
    workers_count = db.query(PersonDetection).filter(PersonDetection.camera_id == camera_id).count()

    return ResponseModel(data={
        "camera_id": camera_id,
        "camera_name": cam.name,
        "enabled": cam.enabled,
        "ppe_enabled": cam.ppe_enabled,
        "active_workers_count": workers_count,
        "recent_violations_count": len(recent_viols),
        "status": "VIOLATION" if recent_viols and recent_viols[0].status == "VIOLATION" else "COMPLIANT"
    })
