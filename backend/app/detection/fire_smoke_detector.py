"""
Fire & Smoke AI Detection Implementation.
Modular wrapper fulfilling BaseDetector interface for Fire & Smoke detection
using YOLOv8 (PyTorch or ONNX) with physics-based false-positive suppression.
"""

import os
import time
import hashlib
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import numpy as np

from app.config.settings import settings
from app.detection.base import BaseDetector, DetectionResult, BoundingBox, DetectorStatus
from app.detection.fire_smoke_engine import FireSmokeEngine
from app.detection.onnx_engine import resolve_model_path
from app.detection.yolo import YOLODetector
from app.utils.logger import logger


class FireSmokeDetector(BaseDetector):
    """
    Fire & Smoke Detection Module.
    Wraps FireSmokeEngine (small-object aware, false-positive resistant) behind the standard BaseDetector interface.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        conf_threshold: Optional[float] = None,
        iou_threshold: Optional[float] = None,
        device: Optional[str] = None
    ):
        self.model_path = resolve_model_path(
            model_path or settings.YOLO_MODEL_PATH,
            default_names=[
                "runs/detect/train/weights/best.pt",
                "models/fire_smoke.pt",
                "models/fire_smoke.onnx",
                "yolov8n.pt",
            ]
        )
        self.conf_threshold = conf_threshold if conf_threshold is not None else settings.YOLO_CONF_THRESHOLD
        self.iou_threshold = iou_threshold if iou_threshold is not None else settings.YOLO_IOU_THRESHOLD
        self.device = device or settings.YOLO_DEVICE
        
        self.status = DetectorStatus.UNAVAILABLE
        self.loaded_at: Optional[str] = None
        self.model_hash: str = "unknown"
        self._engine: Optional[FireSmokeEngine] = None
        self._yolo: Optional[YOLODetector] = None
        self.initialize()

    def initialize(self) -> bool:
        """
        Initializes the underlying FireSmokeEngine and records model metadata.
        """
        try:
            if os.path.exists(self.model_path):
                try:
                    with open(self.model_path, "rb") as f:
                        self.model_hash = hashlib.md5(f.read(8192)).hexdigest()
                except Exception:
                    self.model_hash = "hash_error"
            else:
                self.model_hash = "mock_mode_no_weights"

            self._engine = FireSmokeEngine(
                model_path=self.model_path,
                conf_threshold=self.conf_threshold,
                iou_threshold=self.iou_threshold,
                device=self.device,
            )
            self._yolo = YOLODetector(
                model_path=self.model_path,
                conf_threshold=self.conf_threshold,
                iou_threshold=self.iou_threshold,
                device=self.device,
                target_classes=["fire", "smoke"]
            )
            self.loaded_at = datetime.now(timezone.utc).isoformat()
            
            if self._engine._is_mock_fallback:
                self.status = DetectorStatus.DEGRADED
            else:
                self.status = DetectorStatus.HEALTHY
            return True

        except Exception as e:
            logger.error(f"FireSmokeDetector: Failed to initialize: {str(e)}")
            self.status = DetectorStatus.ERROR
            return False

    def detect(
        self,
        image_bgr: Any,
        candidate_rois: Optional[List[BoundingBox]] = None,
        exclusion_rois: Optional[Any] = None,
        motion_context: Optional[Dict[str, Any]] = None,
        **kwargs: Any
    ) -> List[DetectionResult]:
        """
        :param exclusion_rois: worker/PPE boxes that must never be reported as fire (a hi-vis vest
               is the single strongest false-positive source for the fire model).
        :param motion_context: motion metadata from MotionGate.
        """
        if not settings.AI_FIRE_SMOKE_ENABLED or self.status == DetectorStatus.ERROR or not self._engine:
            return []

        try:
            results = self._engine.detect(
                image_bgr,
                candidate_rois=candidate_rois,
                exclusion_rois=exclusion_rois,
                motion_context=motion_context,
            )
            for res in results:
                res.metadata["detector_module"] = "FireSmokeDetector"
            return results
        except Exception as e:
            logger.error(f"FireSmokeDetector: Detection execution failed: {str(e)}")
            self.status = DetectorStatus.DEGRADED
            # Attempt HSV fallback
            return self._yolo._detect_color_hsv(image_bgr, candidate_rois=candidate_rois) if self._yolo else []

    def get_model_name(self) -> str:
        return "FireSmokeDetector-YOLOv8"

    def get_model_info(self) -> Dict[str, Any]:
        # Return public-safe metadata without exposing internal filesystem secrets
        return {
            "model_name": "FireSmokeDetector-YOLOv8",
            "model_version": "8.0.0",
            "model_filename": os.path.basename(self.model_path),
            "model_hash": self.model_hash,
            "loaded_at": self.loaded_at,
            "target_classes": ["fire", "smoke"],
            "device": self.device
        }

    def health_check(self) -> Dict[str, Any]:
        return {
            "detector": "FireSmokeDetector",
            "status": self.status.value,
            "device": self.device,
            "model_name": self.get_model_name(),
            "enabled": settings.AI_FIRE_SMOKE_ENABLED
        }

    def shutdown(self) -> None:
        self._engine = None
        self._yolo = None
        self.status = DetectorStatus.UNAVAILABLE
