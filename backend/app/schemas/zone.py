"""
Pydantic Schemas for Safety Zones and Polygon Boundaries.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class SafetyZoneCreate(BaseModel):
    camera_id: int
    name: str = Field(..., max_length=100)
    zone_type: str = Field(default="HAZARD")  # HAZARD, RESTRICTED, GENERAL
    polygon_coordinates: List[List[float]] = Field(..., description="Normalized [[x1,y1],[x2,y2],...]")
    ppe_profile_id: Optional[int] = None
    enabled: bool = True


class SafetyZoneUpdate(BaseModel):
    name: Optional[str] = None
    zone_type: Optional[str] = None
    polygon_coordinates: Optional[List[List[float]]] = None
    ppe_profile_id: Optional[int] = None
    enabled: Optional[bool] = None


class SafetyZoneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    camera_id: int
    name: str
    zone_type: str
    polygon_coordinates: List[List[float]]
    ppe_profile_id: Optional[int] = None
    enabled: bool
    created_at: datetime
    updated_at: datetime
