"""
REST API v1 Endpoints for Incidents and Correlated Safety Events.
"""

import math
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import User
from app.api.v1.dependencies import get_current_user, require_role
from app.services.incident_service import IncidentService
from app.schemas.incident import (
    IncidentResponse,
    IncidentStatusUpdate,
    IncidentPaginatedResponse
)

router = APIRouter(prefix="/incidents", tags=["Safety Incidents"])


@router.get("", response_model=IncidentPaginatedResponse)
def list_incidents(
    camera_id: Optional[int] = Query(None, description="Filter by Camera ID"),
    zone_id: Optional[int] = Query(None, description="Filter by Zone ID"),
    incident_type: Optional[str] = Query(None, description="Filter by Incident Type (FIRE, SMOKE, PPE_VIOLATION, ZONE_VIOLATION, SAFETY_INCIDENT)"),
    severity: Optional[str] = Query(None, description="Filter by Severity (CRITICAL, HIGH, MEDIUM, LOW)"),
    status: Optional[str] = Query(None, description="Filter by Status (ACTIVE, ACKNOWLEDGED, RESOLVED)"),
    date_from: Optional[datetime] = Query(None, description="Filter start date"),
    date_to: Optional[datetime] = Query(None, description="Filter end date"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = IncidentService(db)
    items, total = service.get_incidents(
        camera_id=camera_id,
        zone_id=zone_id,
        incident_type=incident_type,
        severity=severity,
        status=status,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size
    )
    pages = math.ceil(total / page_size) if total > 0 else 1
    return IncidentPaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages
    )


@router.get("/{id}", response_model=IncidentResponse)
def get_incident(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = IncidentService(db)
    inc = service.get_incident(id)
    if not inc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return inc


@router.patch("/{id}", response_model=IncidentResponse)
def update_incident_status(
    id: str,
    payload: IncidentStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "MANAGER", "OPERATOR"]))
):
    service = IncidentService(db)
    updated = service.update_incident_status(
        incident_id=id,
        status=payload.status,
        user_id=current_user.id
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return updated


# Dedicated Events Router (/api/v1/events)
events_router = APIRouter(prefix="/events", tags=["Safety Events & Incidents"])

@events_router.get("", response_model=IncidentPaginatedResponse)
def list_events(
    camera_id: Optional[int] = Query(None),
    incident_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return list_incidents(camera_id=camera_id, zone_id=None, incident_type=incident_type, severity=severity, status=status, date_from=None, date_to=None, page=page, page_size=page_size, db=db, current_user=current_user)


@events_router.get("/{event_id}", response_model=IncidentResponse)
def get_event(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return get_incident(id=event_id, db=db, current_user=current_user)
