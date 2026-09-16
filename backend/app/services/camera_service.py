"""
Camera Business Service Layer (CameraService).
Orchestrates persistent database operations (SQLAlchemy) and runtime stream execution (CameraManager).
"""

import cv2
from typing import List, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy.orm import Session
import numpy as np

from app.models.camera import Camera
from app.schemas.camera import CameraCreate, CameraUpdate, CameraRuntimeStateResponse
from app.camera.manager import CameraManager
from app.utils.exceptions import AppException, CameraException
from app.utils.logger import logger


class CameraService:
    """
    Business logic layer for CCTV / NVR Camera management.
    """

    def __init__(self, db: Session, camera_manager: CameraManager):
        self.db = db
        self.camera_manager = camera_manager

    def create_camera(self, payload: CameraCreate) -> Camera:
        """
        Creates a new camera configuration in DB and registers it with CameraManager.
        """
        source_type_str = payload.source_type.value if hasattr(payload.source_type, "value") else str(payload.source_type)
        camera = Camera(
            name=payload.name,
            camera_number=payload.camera_number,
            dvr_id=payload.dvr_id,
            dvr_channel=payload.dvr_channel,
            channel_name=payload.channel_name,
            dvr_address=payload.dvr_address,
            rtsp_url=payload.rtsp_url,
            source_type=source_type_str,
            location=payload.location,
            latitude=payload.latitude if payload.latitude is not None else 13.0827,
            longitude=payload.longitude if payload.longitude is not None else 80.2707,
            enabled=payload.enabled,
            fire_smoke_enabled=payload.fire_smoke_enabled,
            ppe_enabled=payload.ppe_enabled,
            person_enabled=payload.person_enabled,
            zone_enabled=payload.zone_enabled,
            ppe_inference_interval_sec=payload.ppe_inference_interval_sec,
            priority=getattr(payload, "priority", "HIGH") or "HIGH",
            capture_fps=getattr(payload, "capture_fps", 25) or 25,
            target_ai_fps=getattr(payload, "target_ai_fps", 15) or 15,
            frame_skip=getattr(payload, "frame_skip", 1) or 1,
            gpu_device_id=getattr(payload, "gpu_device_id", 0) or 0,
            fps_limit=payload.fps_limit,
            connection_timeout=payload.connection_timeout,
            reconnect_interval=payload.reconnect_interval
        )
        self.db.add(camera)
        self.db.flush()

        # Register with CameraManager in safe block so stream worker issues don't abort DB commit
        try:
            self.camera_manager.add_camera(camera)
            if camera.enabled:
                self.camera_manager.start_camera(camera.id)
        except Exception as e:
            logger.error(f"CameraService: Runtime ingestion registration warning for Camera ID {camera.id}: {str(e)}", exc_info=True)

        self.db.commit()
        self.db.refresh(camera)
        logger.info(f"CameraService: Registered Camera ID {camera.id} ('{camera.name}')")
        return camera

    def get_camera(self, camera_id: int) -> Camera:
        """
        Retrieves camera configuration by ID from DB.
        """
        camera = self.db.query(Camera).filter(Camera.id == camera_id).first()
        if not camera:
            raise AppException(
                message=f"Camera with ID {camera_id} not found",
                code="CAMERA_NOT_FOUND",
                status_code=404
            )
        return camera

    def list_cameras(self) -> List[Camera]:
        """
        Lists all registered camera configurations from DB.
        """
        return self.db.query(Camera).all()

    def update_camera(self, camera_id: int, payload: CameraUpdate) -> Camera:
        """
        Updates camera configuration in DB and reloads runtime state in CameraManager.
        """
        camera = self.get_camera(camera_id)

        # Stop existing worker before updating configuration
        self.camera_manager.stop_camera(camera_id)

        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if key == "source_type" and value is not None:
                setattr(camera, key, value.value)
            elif value is not None:
                setattr(camera, key, value)

        camera.updated_at = datetime.now(timezone.utc)
        self.db.flush()

        # Re-register updated config with CameraManager
        self.camera_manager.add_camera(camera)
        if camera.enabled:
            self.camera_manager.start_camera(camera.id)

        self.db.commit()

        logger.info(f"CameraService: Updated Camera ID {camera_id}")
        return camera

    def delete_camera(self, camera_id: int) -> bool:
        """
        Stops runtime worker and removes camera configuration from DB.
        """
        camera = self.get_camera(camera_id)
        self.camera_manager.remove_camera(camera_id)

        self.db.delete(camera)
        self.db.commit()
        logger.info(f"CameraService: Deleted Camera ID {camera_id}")
        return True

    def delete_all_cameras(self) -> int:
        """
        Stops runtime workers for all cameras and deletes all camera configurations from DB.
        Returns the count of deleted cameras.
        """
        cameras = self.db.query(Camera).all()
        count = len(cameras)
        for c in cameras:
            try:
                self.camera_manager.remove_camera(c.id)
            except Exception as e:
                logger.warning(f"Error removing camera {c.id} from manager: {e}")
            self.db.delete(c)
        self.db.commit()
        logger.info(f"CameraService: Bulk deleted all {count} cameras from system")
        return count


    def start_camera(self, camera_id: int) -> CameraRuntimeStateResponse:
        """
        Manually triggers starting camera stream worker.
        """
        camera = self.get_camera(camera_id)
        if not camera.enabled:
            camera.enabled = True
            self.db.commit()

        # Ensure registered in manager
        if camera_id not in self.camera_manager._sources:
            self.camera_manager.add_camera(camera)

        self.camera_manager.start_camera(camera_id)
        return self.get_camera_status(camera_id)

    def stop_camera(self, camera_id: int) -> CameraRuntimeStateResponse:
        """
        Manually triggers stopping camera stream worker.
        """
        camera = self.get_camera(camera_id)
        if camera.enabled:
            camera.enabled = False
            self.db.commit()

        self.camera_manager.stop_camera(camera_id)
        return self.get_camera_status(camera_id)

    def get_camera_status(self, camera_id: int) -> CameraRuntimeStateResponse:
        """
        Retrieves dynamic runtime connection metrics for specified camera.
        """
        # Ensure camera exists in DB
        self.get_camera(camera_id)
        state = self.camera_manager.get_runtime_state(camera_id)

        if not state:
            return CameraRuntimeStateResponse(
                camera_id=camera_id,
                connection_status="DISCONNECTED",
                reconnect_attempts=0
            )

        return CameraRuntimeStateResponse(
            camera_id=camera_id,
            connection_status=state.connection_status.value,
            last_frame_timestamp=state.last_frame_timestamp.isoformat() if state.last_frame_timestamp else None,
            current_fps=state.current_fps,
            resolution=f"{state.resolution[0]}x{state.resolution[1]}" if state.resolution else None,
            reconnect_attempts=state.reconnect_attempts,
            error_message=state.error_message
        )

    def get_camera_jpeg_snapshot(self, camera_id: int) -> bytes:
        """
        Generates a single JPEG snapshot image byte payload for verification testing.
        """
        # Ensure camera exists
        self.get_camera(camera_id)

        frame, timestamp, frame_count = self.camera_manager.get_latest_frame(camera_id)
        if frame is None:
            buf = self.camera_manager._buffers.get(camera_id)
            if buf:
                jpeg_bytes, _, _ = buf.get_latest_jpeg()
                if jpeg_bytes:
                    return jpeg_bytes

            # If camera stream is initializing or warming up, generate a valid placeholder snapshot
            placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(placeholder, f"Camera #{camera_id} Initializing...", (120, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 215, 255), 2, cv2.LINE_AA)
            cv2.putText(placeholder, "Please wait, warming up video ingestion stream...", (110, 270), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (170, 170, 170), 1, cv2.LINE_AA)
            success, encoded_placeholder = cv2.imencode(".jpg", placeholder, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if success:
                return encoded_placeholder.tobytes()

            raise CameraException(
                message=f"No active frame available for Camera ID {camera_id}. Ensure stream is started and connected.",
                details={"camera_id": camera_id}
            )

        success, encoded_image = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not success:
            raise CameraException(message="Failed to encode frame into JPEG format.")

        return encoded_image.tobytes()
