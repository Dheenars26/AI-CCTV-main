"""
Pydantic Schemas for Incidents and Safety Statistics.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class IncidentStatusUpdate(BaseModel):
    status: str = Field(..., description="ACTIVE, ACKNOWLEDGED, RESOLVED")


class IncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    camera_id: int
    zone_id: Optional[int] = None
    incident_type: str
    events: List[str]
    severity: str
    status: str
    person_id: Optional[int] = None
    evidence_id: Optional[str] = None
    start_time: datetime
    cleared_time: Optional[datetime] = None
    metadata_json: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class IncidentPaginatedResponse(BaseModel):
    items: List[IncidentResponse]
    total: int
    page: int
    page_size: int
    pages: int


class SafetyStatisticsResponse(BaseModel):
    total_cameras: int
    online_cameras: int
    offline_cameras: int
    active_fire_alerts: int
    active_smoke_alerts: int
    ppe_violations_24h: int
    workers_detected_24h: int
    zone_violations_24h: int
    critical_incidents_active: int
    daily_compliance_percentage: float
    calculated_at: str
