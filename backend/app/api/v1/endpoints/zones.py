"""
REST API v1 Endpoints for Polygon Safety Zones.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import User
from app.api.v1.dependencies import get_current_user, require_role
from app.services.zone_service import ZoneService
from app.schemas.zone import SafetyZoneCreate, SafetyZoneUpdate, SafetyZoneResponse

router = APIRouter(prefix="/zones", tags=["Safety Zones"])


def _sync_zones_to_manager(request: Request, camera_id: int, db: Session) -> None:
    """Safely synchronizes active safety zones to running camera pipeline without opening new DB sessions."""
    try:
        camera_manager = getattr(request.app.state, "camera_manager", None)
        if camera_manager and hasattr(camera_manager, "update_camera_safety_zones"):
            service = ZoneService(db)
            active_zones = service.get_zones(camera_id=camera_id)
            zone_dicts = [
                {
                    "id": z.id,
                    "name": z.name,
                    "zone_type": z.zone_type,
                    "polygon_coordinates": z.polygon_coordinates,
                    "ppe_profile_id": z.ppe_profile_id,
                    "enabled": z.enabled
                }
                for z in active_zones if z.enabled
            ]
            camera_manager.update_camera_safety_zones(camera_id, zone_dicts)
    except Exception:
        pass


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
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"]))
):
    service = ZoneService(db)
    zone = service.create_zone(
        camera_id=payload.camera_id,
        name=payload.name,
        polygon_coordinates=payload.polygon_coordinates,
        zone_type=payload.zone_type,
        ppe_profile_id=payload.ppe_profile_id,
        enabled=payload.enabled,
        user_id=current_user.id
    )

    # Hot-reload safety zone in real-time camera pipeline
    _sync_zones_to_manager(request, payload.camera_id, db)

    return zone


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
@router.put("/{id}", response_model=SafetyZoneResponse)
def update_safety_zone(
    id: int,
    payload: SafetyZoneUpdate,
    request: Request,
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

    # Hot-reload safety zone in real-time camera pipeline
    _sync_zones_to_manager(request, updated.camera_id, db)

    return updated


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_safety_zone(
    id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"]))
):
    service = ZoneService(db)
    zone = service.get_zone(id)
    cam_id = zone.camera_id if zone else None

    success = service.delete_zone(id, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Safety Zone not found")

    # Hot-reload safety zone in real-time camera pipeline
    if cam_id:
        _sync_zones_to_manager(request, cam_id, db)
