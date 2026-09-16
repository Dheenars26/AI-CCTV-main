"""
AI Detection Subsystem Package Initialization.
"""

from app.detection.base import BaseDetector, DummyDetector, DetectionResult, BoundingBox, DetectorStatus
from app.detection.yolo import YOLODetector
from app.detection.fire_smoke_detector import FireSmokeDetector
from app.detection.ppe_detector import PPEDetector
from app.detection.person_detector import PersonDetector
from app.detection.verification import (
    EventState,
    VerifiedEvent,
    ClassVerificationTracker,
    CameraVerificationEngine
)

__all__ = [
    "BaseDetector",
    "DummyDetector",
    "YOLODetector",
    "FireSmokeDetector",
    "PPEDetector",
    "PersonDetector",
    "DetectorStatus",
    "DetectionResult",
    "BoundingBox",
    "EventState",
    "VerifiedEvent",
    "ClassVerificationTracker",
    "CameraVerificationEngine"
]


