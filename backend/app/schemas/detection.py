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

