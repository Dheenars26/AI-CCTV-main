"""
Safety Zone Service Subsystem (ZoneService).
Handles database operations and polygon coordinate validation for camera SafetyZones.
"""

from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any, Union
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.zone import SafetyZone
from app.services.audit_service import AuditService
from app.zones.engine import ZoneEngine
from app.utils.exceptions import ValidationException


class ZoneService:
    def __init__(self, db: Session):
        self.db = db

    def get_zones(self, camera_id: Optional[int] = None) -> List[SafetyZone]:
        stmt = select(SafetyZone)
        if camera_id is not None:
            stmt = stmt.where(SafetyZone.camera_id == camera_id)
        return list(self.db.scalars(stmt.order_by(SafetyZone.id)).all())

    def get_zone(self, zone_id: int) -> Optional[SafetyZone]:
        return self.db.get(SafetyZone, zone_id)

    def create_zone(
        self,
        camera_id: int,
        name: str,
        polygon_coordinates: List[List[float]],
        zone_type: str = "HAZARD",
        ppe_profile_id: Optional[int] = None,
        enabled: bool = True,
        user_id: Optional[Union[int, str]] = None
    ) -> SafetyZone:
        # Validate polygon coordinates
        valid, msg = ZoneEngine.validate_polygon(polygon_coordinates)
        if not valid:
            raise ValidationException(f"Invalid safety zone polygon: {msg}")

        zone = SafetyZone(
            camera_id=camera_id,
            name=name,
            zone_type=zone_type.upper(),
            polygon_coordinates=polygon_coordinates,
            ppe_profile_id=ppe_profile_id,
            enabled=enabled
        )
        self.db.add(zone)
        self.db.flush()
        self.db.commit()

        AuditService.log_event(
            self.db,
            event_type="SAFETY_ZONE_CREATED",
            actor_id=str(user_id) if user_id else None,
            details={"zone_id": zone.id, "camera_id": camera_id, "name": name, "zone_type": zone_type}
        )

        return zone

    def update_zone(
        self,
        zone_id: int,
        name: Optional[str] = None,
        zone_type: Optional[str] = None,
        polygon_coordinates: Optional[List[List[float]]] = None,
        ppe_profile_id: Optional[int] = None,
        enabled: Optional[bool] = None,
        user_id: Optional[Union[int, str]] = None
    ) -> Optional[SafetyZone]:
        zone = self.get_zone(zone_id)
        if not zone:
            return None

        if polygon_coordinates is not None:
            valid, msg = ZoneEngine.validate_polygon(polygon_coordinates)
            if not valid:
                raise ValidationException(f"Invalid safety zone polygon: {msg}")
            zone.polygon_coordinates = polygon_coordinates

        if name is not None:
            zone.name = name
        if zone_type is not None:
            zone.zone_type = zone_type.upper()
        if ppe_profile_id is not None:
            zone.ppe_profile_id = ppe_profile_id
        if enabled is not None:
            zone.enabled = enabled

        zone.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        self.db.commit()

        AuditService.log_event(
            self.db,
            event_type="SAFETY_ZONE_UPDATED",
            actor_id=str(user_id) if user_id else None,
            details={"zone_id": zone.id, "name": zone.name, "updated_at": zone.updated_at.isoformat()}
        )

        return zone

    def delete_zone(self, zone_id: int, user_id: Optional[Union[int, str]] = None) -> bool:
        zone = self.get_zone(zone_id)
        if not zone:
            return False

        name = zone.name
        self.db.delete(zone)
        self.db.commit()

        AuditService.log_event(
            self.db,
            event_type="SAFETY_ZONE_DELETED",
            actor_id=str(user_id) if user_id else None,
            details={"zone_id": zone_id, "name": name}
        )
        return True
