"""
Pydantic Schemas for PPE Profiles, Requirements, and PPE Violations.
Sanitizes public API outputs to prevent exposing model file paths or internal disk paths.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class PPERequirementSchema(BaseModel):
    equipment_type: str
    is_required: bool = True
    severity: str = "HIGH"


class PPEProfileCreate(BaseModel):
    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    required_equipment: List[str] = Field(default_factory=list)
    optional_equipment: List[str] = Field(default_factory=list)


class PPEProfileUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    required_equipment: Optional[List[str]] = None
    optional_equipment: Optional[List[str]] = None


class PPEProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    required_equipment: List[str]
    optional_equipment: List[str]
    created_at: datetime
    updated_at: datetime


class PPEViolationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    camera_id: int
    zone_id: Optional[int] = None
    person_id: int
    profile_id: Optional[int] = None
    status: str
    severity: str
    missing_items: List[str]
    detected_items: List[str]
    required_items: List[str]
    confidence: float
    timestamp: datetime
    evidence_id: Optional[str] = None
    created_at: datetime


class PPEViolationPaginatedResponse(BaseModel):
    items: List[PPEViolationResponse]
    total: int
    page: int
    page_size: int
    pages: int
