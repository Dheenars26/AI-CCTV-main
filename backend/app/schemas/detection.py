"""
Pydantic Schemas for AI Predictions (DetectionResponse).
"""

from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class DetectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique Detection UUID")
    camera_id: int = Field(..., description="Target camera integer ID")
    class_name: str = Field(..., description="Detection class name (fire, smoke)")
    confidence: float = Field(..., description="Model confidence score between 0.0 and 1.0")
    bounding_box: Dict[str, Any] = Field(..., description="Normalized bounding box coordinates {x_min, y_min, x_max, y_max}")
    frame_number: int = Field(default=0, description="Sequential video frame number")
    fps: float = Field(default=0.0, description="Stream processing FPS at detection time")
    timestamp: datetime = Field(..., description="Detection timestamp (UTC)")


class AnalyzeWorkerResult(BaseModel):
    person_id: int = Field(..., description="Tracked or identified worker sequence ID")
    status: str = Field(..., description="Compliance status: PASS or VIOLATION")
    bounding_box: Dict[str, float] = Field(..., description="Normalized worker bbox: {x_min, y_min, x_max, y_max}")
    detected_equipment: list[str] = Field(default_factory=list, description="Verified PPE equipment present on worker")
    missing_equipment: list[str] = Field(default_factory=list, description="Missing mandated PPE items")
    confidence: float = Field(default=1.0, description="Worker detection confidence")


class AnalyzeDetectionItem(BaseModel):
    label: str = Field(..., description="Detection class name (fire, smoke, vest, goggles/glasses, person)")
    confidence: float = Field(..., description="Model confidence score [0.0 - 1.0]")
    bounding_box: Dict[str, float] = Field(..., description="Normalized bounding box: {x_min, y_min, x_max, y_max}")
    category: str = Field(default="general", description="Target category: fire_smoke, ppe, person")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Diagnostic physics and model metadata")


class AnalyzeSummary(BaseModel):
    fire_detected: bool = Field(default=False, description="Whether active flame/combustion was verified")
    smoke_detected: bool = Field(default=False, description="Whether an active smoke plume was verified")
    total_persons: int = Field(default=0, description="Total persons detected in the frame")
    compliant_workers: int = Field(default=0, description="Workers meeting all mandated PPE requirements")
    violations_count: int = Field(default=0, description="Workers missing one or more mandated PPE items")
    total_vests: int = Field(default=0, description="Total high-visibility safety vests identified")
    total_glasses: int = Field(default=0, description="Total safety glasses / eye protection identified")


class AnalyzeImageResponse(BaseModel):
    success: bool = Field(default=True, description="Analysis completion status")
    timestamp: str = Field(..., description="Analysis execution timestamp (ISO 8601 UTC)")
    image_width: int = Field(..., description="Input image width in pixels")
    image_height: int = Field(..., description="Input image height in pixels")
    inference_time_ms: float = Field(..., description="Total pipeline inference & post-processing latency in milliseconds")
    summary: AnalyzeSummary = Field(..., description="Aggregate multi-target safety metrics")
    workers: list[AnalyzeWorkerResult] = Field(default_factory=list, description="Worker-centric PPE compliance breakdowns")
    detections: list[AnalyzeDetectionItem] = Field(default_factory=list, description="All raw verified AI detections")
    annotated_image_base64: Optional[str] = Field(default=None, description="Rendered CCTV HUD image as base64 JPEG data URL")


class AnalyzeImageRequest(BaseModel):
    image_base64: str = Field(..., description="Base64 encoded JPEG or PNG image string (with or without data URL prefix)")
    required_equipment: Optional[list[str]] = Field(default=["vest", "glasses"], description="Mandated PPE requirements for workers")
    return_annotated: bool = Field(default=True, description="Whether to include CCTV HUD annotated image base64")
    min_confidence: Optional[float] = Field(default=None, description="Optional minimum confidence threshold floor")
    camera_id: Optional[int] = Field(default=1, description="Associated camera identifier")


