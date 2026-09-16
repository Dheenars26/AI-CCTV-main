"""
REST API v1 Endpoints for Polygon Safety Zones.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import User
from app.api.v1.dependencies import get_current_user, require_role
from app.services.zone_service import ZoneService
from app.schemas.zone import SafetyZoneCreate, SafetyZoneUpdate, SafetyZoneResponse

router = APIRouter(prefix="/zones", tags=["Safety Zones"])


@router.get("", response_model=List[SafetyZoneResponse])
def list_safety_zones(
    camera_id: Optional[int] = Query(None, description="Filter zones by Camera ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ZoneService(db)
    return service.get_zones(camera_id=camera_id)


@router.post("", response_model=SafetyZoneResponse, status_code=status.HTTP_201_CREATED)
def create_safety_zone(
    payload: SafetyZoneCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"]))
):
    service = ZoneService(db)
    return service.create_zone(
        camera_id=payload.camera_id,
        name=payload.name,
        polygon_coordinates=payload.polygon_coordinates,
        zone_type=payload.zone_type,
        ppe_profile_id=payload.ppe_profile_id,
        enabled=payload.enabled,
        user_id=current_user.id
    )


@router.get("/{id}", response_model=SafetyZoneResponse)
def get_safety_zone(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ZoneService(db)
    zone = service.get_zone(id)
    if not zone:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Safety Zone not found")
    return zone


@router.patch("/{id}", response_model=SafetyZoneResponse)
def update_safety_zone(
    id: int,
    payload: SafetyZoneUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"]))
):
    service = ZoneService(db)
    updated = service.update_zone(
        zone_id=id,
        name=payload.name,
        zone_type=payload.zone_type,
        polygon_coordinates=payload.polygon_coordinates,
        ppe_profile_id=payload.ppe_profile_id,
        enabled=payload.enabled,
        user_id=current_user.id
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Safety Zone not found")
    return updated


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_safety_zone(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"]))
):
    service = ZoneService(db)
    success = service.delete_zone(id, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Safety Zone not found")
