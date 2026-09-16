"""
PPE Service Subsystem (PPEService).
Handles database operations for PPE Profiles, PPE Requirements, and PPE Violations with filtering and pagination.
"""

from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any, Union, cast
from sqlalchemy.orm import Session
from sqlalchemy import select, func, desc

from app.models.ppe import PPEProfile, PPERequirement, PPEViolation, PersonDetection
from app.services.audit_service import AuditService
from app.utils.logger import logger


class PPEService:
    def __init__(self, db: Session):
        self.db = db

    # -------------------------------------------------------------------------
    # PPE Profiles
    # -------------------------------------------------------------------------
    def get_profiles(self) -> List[PPEProfile]:
        return list(self.db.scalars(select(PPEProfile).order_by(PPEProfile.id)).all())

    def get_profile(self, profile_id: int) -> Optional[PPEProfile]:
        return self.db.get(PPEProfile, profile_id)

    def get_profile_by_name(self, name: str) -> Optional[PPEProfile]:
        return self.db.scalar(select(PPEProfile).where(PPEProfile.name == name))

    def create_profile(
        self,
        name: str,
        required_equipment: List[str],
        optional_equipment: Optional[List[str]] = None,
        description: Optional[str] = None,
        user_id: Optional[Union[int, str]] = None,
        commit: bool = True
    ) -> PPEProfile:
        profile = PPEProfile(
            name=name,
            description=description,
            required_equipment=required_equipment,
            optional_equipment=optional_equipment or []
        )
        self.db.add(profile)
        self.db.flush()
        if commit:
            self.db.commit()

        # Audit Log
        AuditService.log_event(
            self.db,
            event_type="PPE_PROFILE_CREATED",
            actor_id=str(user_id) if user_id else None,
            details={"profile_id": profile.id, "name": name, "required_equipment": required_equipment}
        )

        return profile

    def update_profile(
        self,
        profile_id: int,
        name: Optional[str] = None,
        required_equipment: Optional[List[str]] = None,
        optional_equipment: Optional[List[str]] = None,
        description: Optional[str] = None,
        user_id: Optional[Union[int, str]] = None
    ) -> Optional[PPEProfile]:
        profile = self.get_profile(profile_id)
        if not profile:
            return None

        if name is not None:
            profile.name = name
        if required_equipment is not None:
            profile.required_equipment = required_equipment
        if optional_equipment is not None:
            profile.optional_equipment = optional_equipment
        if description is not None:
            profile.description = description

        profile.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        self.db.commit()

        AuditService.log_event(
            self.db,
            event_type="PPE_PROFILE_UPDATED",
            actor_id=str(user_id) if user_id else None,
            details={"profile_id": profile.id, "name": profile.name, "updated_at": profile.updated_at.isoformat()}
        )

        return profile

    def delete_profile(self, profile_id: int, user_id: Optional[Union[int, str]] = None) -> bool:
        profile = self.get_profile(profile_id)
        if not profile:
            return False

        name = profile.name
        from app.models.ppe import PPERequirement, PPEViolation
        from app.models.zone import SafetyZone

        self.db.query(SafetyZone).filter(SafetyZone.ppe_profile_id == profile_id).update({"ppe_profile_id": None}, synchronize_session=False)
        self.db.query(PPEViolation).filter(PPEViolation.profile_id == profile_id).update({"profile_id": None}, synchronize_session=False)
        self.db.query(PPERequirement).filter(PPERequirement.profile_id == profile_id).delete(synchronize_session=False)
        self.db.delete(profile)
        self.db.commit()
        
        AuditService.log_event(
            self.db,
            event_type="PPE_PROFILE_DELETED",
            actor_id=str(user_id) if user_id else None,
            details={"profile_id": profile_id, "name": name}
        )
        return True

    def init_default_profiles_if_empty(self) -> None:
        """
        Populates standard industrial default PPE profiles if empty.
        """
        if len(self.get_profiles()) > 0:
            return

        defaults = [
            {
                "name": "Factory Floor",
                "description": "General manufacturing floor requiring helmet and safety vest",
                "required": ["helmet", "vest"],
                "optional": ["gloves", "mask"]
            },
            {
                "name": "Welding Area",
                "description": "High hazard welding area requiring head, body, face, and hand protection",
                "required": ["helmet", "vest", "goggles", "gloves"],
                "optional": ["mask", "safety_shoes"]
            },
            {
                "name": "Chemical Area",
                "description": "Chemical storage and processing area requiring respiratory and full skin protection",
                "required": ["helmet", "mask", "gloves", "goggles"],
                "optional": ["vest", "safety_shoes"]
            }
        ]

        for d in defaults:
            self.create_profile(
                name=str(d["name"]),
                description=str(d["description"]),
                required_equipment=cast(List[str], d["required"]),
                optional_equipment=cast(List[str], d["optional"]),
                commit=False
            )
        self.db.commit()
        logger.info("PPEService: Initialized default industrial PPE profiles.")

    # -------------------------------------------------------------------------
    # PPE Violations
    # -------------------------------------------------------------------------
    def create_violation(
        self,
        camera_id: int,
        person_id: int,
        status: str,
        severity: str,
        missing_items: List[str],
        detected_items: List[str],
        required_items: List[str],
        confidence: float,
        zone_id: Optional[int] = None,
        profile_id: Optional[int] = None,
        evidence_id: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> PPEViolation:
        viol = PPEViolation(
            camera_id=camera_id,
            zone_id=zone_id,
            person_id=person_id,
            profile_id=profile_id,
            status=status,
            severity=severity,
            missing_items=missing_items,
            detected_items=detected_items,
            required_items=required_items,
            confidence=confidence,
            evidence_id=evidence_id,
            timestamp=timestamp or datetime.now(timezone.utc)
        )
        self.db.add(viol)
        self.db.commit()
        self.db.refresh(viol)
        return viol

    def get_violations(
        self,
        camera_id: Optional[int] = None,
        zone_id: Optional[int] = None,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[PPEViolation], int]:
        stmt = select(PPEViolation)

        if camera_id is not None:
            stmt = stmt.where(PPEViolation.camera_id == camera_id)
        if zone_id is not None:
            stmt = stmt.where(PPEViolation.zone_id == zone_id)
        if status:
            stmt = stmt.where(PPEViolation.status == status)
        if severity:
            stmt = stmt.where(PPEViolation.severity == severity)
        if date_from:
            stmt = stmt.where(PPEViolation.timestamp >= date_from)
        if date_to:
            stmt = stmt.where(PPEViolation.timestamp <= date_to)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.scalar(count_stmt) or 0

        stmt = stmt.order_by(desc(PPEViolation.timestamp)).offset((page - 1) * page_size).limit(page_size)
        items = self.db.scalars(stmt).all()

        return list(items), total

    def get_violation(self, violation_id: str) -> Optional[PPEViolation]:
        return self.db.get(PPEViolation, violation_id)
