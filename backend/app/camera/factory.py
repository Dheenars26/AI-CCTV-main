"""
Camera Source Factory Pattern.
Instantiates concrete CameraSource drivers based on configured SourceType.
"""

import os
from typing import Union
from app.models.camera import Camera
from app.schemas.camera import SourceType, CameraCreate
from app.camera.base import CameraSource
from app.camera.rtsp import RTSPCamera
from app.camera.file_source import VideoFileCamera
from app.camera.webcam import WebcamCamera
from app.config.settings import settings
from app.utils.logger import logger


class CameraFactory:
    """
    Factory creating appropriate CameraSource instance.
    """

    @staticmethod
    def create_source(camera: Union[Camera, CameraCreate], camera_id: int = 0) -> CameraSource:
        """
        Creates and returns a concrete CameraSource instance.
        """
        cid = camera.id if hasattr(camera, "id") and camera.id is not None else camera_id
        source_type_val = camera.source_type
        if isinstance(source_type_val, SourceType):
            source_type_str = source_type_val.value
        else:
            source_type_str = str(source_type_val).lower()

        raw_fps = getattr(camera, "fps_limit", 25)
        fps = int(raw_fps) if raw_fps is not None else 25
        raw_timeout = getattr(camera, "connection_timeout", 10)
        timeout = int(raw_timeout) if raw_timeout is not None else 10
        url = camera.rtsp_url

        url_str = str(url).strip().lower() if url else "dummy"
        is_webcam = (source_type_str == SourceType.WEBCAM.value) or url_str.isdigit()
        is_rtsp = url_str.startswith("rtsp://") or url_str.startswith("http://") or url_str.startswith("https://")

        if is_webcam:
            logger.info(f"CameraFactory: Instantiating WebcamCamera for Camera ID {cid}")
            return WebcamCamera(
                camera_id=cid,
                rtsp_url=url if url else "0",
                fps_limit=fps,
                timeout_seconds=timeout
            )
        elif source_type_str == SourceType.FILE.value:
            if not os.path.exists(str(url)) or settings.APP_ENV == "testing":
                from app.camera.dummy_source import SyntheticDummyCamera
                logger.info(f"CameraFactory: File not found or test mode. Instantiating SyntheticDummyCamera for Camera ID {cid}")
                return SyntheticDummyCamera(
                    camera_id=cid,
                    rtsp_url=url or "dummy",
                    fps_limit=fps,
                    timeout_seconds=timeout
                )
            logger.info(f"CameraFactory: Instantiating VideoFileCamera for Camera ID {cid}")
            return VideoFileCamera(
                camera_id=cid,
                rtsp_url=url,
                fps_limit=fps,
                timeout_seconds=timeout,
                loop=True
            )
        elif is_rtsp or source_type_str == SourceType.RTSP.value:
            logger.info(f"CameraFactory: Instantiating RTSPCamera for Camera ID {cid}")
            return RTSPCamera(
                camera_id=cid,
                rtsp_url=url,
                fps_limit=fps,
                timeout_seconds=timeout
            )
        else:
            from app.camera.dummy_source import SyntheticDummyCamera
            logger.info(f"CameraFactory: Instantiating SyntheticDummyCamera for Camera ID {cid}")
            return SyntheticDummyCamera(
                camera_id=cid,
                rtsp_url=url or "dummy",
                fps_limit=fps,
                timeout_seconds=timeout
            )

