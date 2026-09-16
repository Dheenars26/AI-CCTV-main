"""
AI Detection Subsystem Base Interfaces & Models.
Defines clean abstractions for object detection engines (YOLO, ONNX, OpenCV, TensorRT).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class BoundingBox:
    """
    Normalized or Absolute Bounding Box coordinates.
    Values normalized to [0.0, 1.0] relative to frame dimensions.
    """
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "x_min": round(self.x_min, 4),
            "y_min": round(self.y_min, 4),
            "x_max": round(self.x_max, 4),
            "y_max": round(self.y_max, 4)
        }

    def to_pixel_coords(self, width: int, height: int) -> tuple[int, int, int, int]:
        """
        Converts normalized coordinates to integer pixel bounding box (xmin, ymin, xmax, ymax).
        """
        return (
            int(self.x_min * width),
            int(self.y_min * height),
            int(self.x_max * width),
            int(self.y_max * height)
        )

    def iou(self, other: "BoundingBox") -> float:
        """Computes Intersection over Union (IoU) with another bounding box."""
        inter_x1 = max(self.x_min, other.x_min)
        inter_y1 = max(self.y_min, other.y_min)
        inter_x2 = min(self.x_max, other.x_max)
        inter_y2 = min(self.y_max, other.y_max)
        inter_w = max(0.0, inter_x2 - inter_x1)
        inter_h = max(0.0, inter_y2 - inter_y1)
        inter_area = inter_w * inter_h
        area1 = max(0.0, self.x_max - self.x_min) * max(0.0, self.y_max - self.y_min)
        area2 = max(0.0, other.x_max - other.x_min) * max(0.0, other.y_max - other.y_min)
        union_area = area1 + area2 - inter_area
        return (inter_area / union_area) if union_area > 0 else 0.0


@dataclass
class DetectionResult:
    """
    Single object detection prediction output (e.g. Fire, Smoke, Person).
    """
    label: str
    confidence: float
    bbox: BoundingBox
    camera_id: Optional[int] = None
    timestamp: Optional[str] = None
    frame_info: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def class_name(self) -> str:
        """Alias property for label matching domain naming conventions."""
        return self.label

    def to_dict(self) -> Dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "class_name": self.class_name,
            "label": self.label,
            "confidence": round(self.confidence, 4),
            "bbox": self.bbox.to_dict(),
            "timestamp": self.timestamp,
            "frame_info": self.frame_info,
            "metadata": self.metadata
        }


from enum import Enum


class DetectorStatus(str, Enum):
    """
    Status of an AI Detection Module.
    """
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"


class BaseDetector(ABC):
    """
    Abstract Base Class for AI Detection Models.
    Allows swapping detection backends (YOLOv8, ONNX Runtime, TensorRT, Dummy)
    without modifying the video processing pipeline.
    """

    @abstractmethod
    def initialize(self) -> bool:
        """
        Initializes AI model weights and compute backend.
        Returns True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def detect(self, image_bgr: Any, candidate_rois: Optional[List[BoundingBox]] = None, **kwargs: Any) -> List[DetectionResult]:
        """
        Executes AI inference on a BGR image array.
        Returns a list of DetectionResult objects.
        """
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """
        Returns model descriptor name and framework version.
        """
        pass

    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """
        Returns metadata such as model_name, model_version, model_path, model_hash, loaded_at.
        Internal security details like raw absolute disk credentials are omitted or sanitized for API output.
        """
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """
        Returns health status dict containing status (HEALTHY, DEGRADED, UNAVAILABLE, ERROR),
        device, and error metrics.
        """
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """
        Releases GPU memory and shuts down inference engine cleanly.
        """
        pass


class DummyDetector(BaseDetector):
    """
    Passthrough / Mock Detector for pipeline development and mock testing.
    Can optionally simulate mock detections for integration testing.
    """

    def __init__(self, simulate_detection: bool = False):
        self.simulate_detection = simulate_detection
        self.status = DetectorStatus.HEALTHY

    def initialize(self) -> bool:
        self.status = DetectorStatus.HEALTHY
        return True

    def detect(self, image_bgr: Any, candidate_rois: Optional[List[BoundingBox]] = None, **kwargs: Any) -> List[DetectionResult]:
        if not self.simulate_detection:
            return []

        # Return simulated test detection if flag enabled
        return [
            DetectionResult(
                label="fire_simulated",
                confidence=0.92,
                bbox=BoundingBox(x_min=0.2, y_min=0.2, x_max=0.5, y_max=0.5),
                metadata={"simulation": True}
            )
        ]

    def get_model_name(self) -> str:
        return "DummyDetector-v1.0"

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "model_name": "DummyDetector",
            "model_version": "1.0.0",
            "model_path": "internal://dummy",
            "model_hash": "dummy_hash_0000",
            "loaded_at": "2026-08-26T00:00:00Z"
        }

    def health_check(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "device": "cpu",
            "model": self.get_model_name()
        }

    def shutdown(self) -> None:
        self.status = DetectorStatus.UNAVAILABLE
