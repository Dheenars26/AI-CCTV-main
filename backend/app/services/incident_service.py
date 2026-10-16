"""
Incident & Safety Statistics Service (IncidentService).
Manages workplace safety incidents, correlation records, status workflows, and reporting metrics.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple, Dict, Any, Union
from sqlalchemy.orm import Session
from sqlalchemy import select, func, desc

from app.models.incident import Incident
from app.models.ppe import PPEViolation, PersonDetection
from app.models.alert import Alert
from app.models.camera import Camera
from app.services.audit_service import AuditService


class IncidentService:
    def __init__(self, db: Session):
        self.db = db

    def create_incident(
        self,
        camera_id: int,
        incident_type: str,
        events: List[str],
        severity: str = "HIGH",
        status: str = "ACTIVE",
        zone_id: Optional[int] = None,
        person_id: Optional[int] = None,
        evidence_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        site_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        metadata_json: Optional[Dict[str, Any]] = None
    ) -> Incident:
        # If organization_id is not explicitly passed, attempt to inherit from the camera
        if not organization_id and camera_id:
            cam = self.db.get(Camera, camera_id)
            if cam:
                organization_id = cam.organization_id
                if not site_id:
                    site_id = cam.site_id

        inc = Incident(
            camera_id=camera_id,
            zone_id=zone_id,
            incident_type=incident_type,
            events=events,
            severity=severity,
            status=status,
            person_id=person_id,
            evidence_id=evidence_id,
            organization_id=organization_id,
            site_id=site_id,
            start_time=start_time or datetime.now(timezone.utc),
            metadata_json=metadata_json or {}
        )
        self.db.add(inc)
        self.db.commit()
        self.db.refresh(inc)
        return inc

    def get_incident(self, incident_id: str, organization_id: Optional[str] = None) -> Optional[Incident]:
        inc = self.db.get(Incident, incident_id)
        if not inc:
            return None
        if organization_id is not None and inc.organization_id is not None:
            if inc.organization_id != organization_id:
                return None
        return inc

    def get_incidents(
        self,
        camera_id: Optional[int] = None,
        zone_id: Optional[int] = None,
        incident_type: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        organization_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[Incident], int]:
        stmt = select(Incident)

        if organization_id is not None:
            stmt = stmt.where(Incident.organization_id == organization_id)
        if camera_id is not None:
            stmt = stmt.where(Incident.camera_id == camera_id)
        if zone_id is not None:
            stmt = stmt.where(Incident.zone_id == zone_id)
        if incident_type:
            stmt = stmt.where(Incident.incident_type == incident_type)
        if severity:
            stmt = stmt.where(Incident.severity == severity)
        if status:
            stmt = stmt.where(Incident.status == status)
        if date_from:
            stmt = stmt.where(Incident.start_time >= date_from)
        if date_to:
            stmt = stmt.where(Incident.start_time <= date_to)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.scalar(count_stmt) or 0

        stmt = stmt.order_by(desc(Incident.start_time)).offset((page - 1) * page_size).limit(page_size)
        items = self.db.scalars(stmt).all()

        return list(items), total

    def update_incident_status(
        self,
        incident_id: str,
        status: str,
        user_id: Optional[Union[int, str]] = None,
        organization_id: Optional[str] = None
    ) -> Optional[Incident]:
        inc = self.get_incident(incident_id, organization_id=organization_id)
        if not inc:
            return None

        inc.status = status.upper()
        if inc.status in ["RESOLVED", "CLEARED"]:
            inc.cleared_time = datetime.now(timezone.utc)
        inc.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(inc)

        AuditService.log_event(
            self.db,
            event_type="PPE_VIOLATION_RESOLVED" if "PPE" in inc.incident_type else "INCIDENT_STATUS_UPDATED",
            actor_id=str(user_id) if user_id else None,
            details={"incident_id": inc.id, "status": inc.status, "incident_type": inc.incident_type}
        )

        return inc

    def get_safety_statistics(self, organization_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculates platform-wide or organization-scoped workplace safety statistics for dashboard KPIs.
        """
        now = datetime.now(timezone.utc)
        day_ago = now - timedelta(days=1)

        cam_stmt = select(func.count(Camera.id))
        enabled_cam_stmt = select(func.count(Camera.id)).where(Camera.enabled == True)
        if organization_id is not None:
            cam_stmt = cam_stmt.where(Camera.organization_id == organization_id)
            enabled_cam_stmt = enabled_cam_stmt.where(Camera.organization_id == organization_id)

        total_cameras = self.db.scalar(cam_stmt) or 0
        enabled_cameras = self.db.scalar(enabled_cam_stmt) or 0
        
        fire_stmt = select(func.count(Alert.id)).where(Alert.class_name == "fire", Alert.state != "CLEARED")
        smoke_stmt = select(func.count(Alert.id)).where(Alert.class_name == "smoke", Alert.state != "CLEARED")
        if organization_id is not None:
            fire_stmt = fire_stmt.where(Alert.organization_id == organization_id)
            smoke_stmt = smoke_stmt.where(Alert.organization_id == organization_id)

        active_fire_alerts = self.db.scalar(fire_stmt) or 0
        active_smoke_alerts = self.db.scalar(smoke_stmt) or 0

        total_ppe_violations_24h = self.db.scalar(
            select(func.count(PPEViolation.id)).where(
                PPEViolation.timestamp >= day_ago,
                PPEViolation.status == "VIOLATION"
            )
        ) or 0

        zone_stmt = select(func.count(Incident.id)).where(Incident.incident_type == "ZONE_VIOLATION", Incident.start_time >= day_ago)
        crit_stmt = select(func.count(Incident.id)).where(Incident.severity == "CRITICAL", Incident.status == "ACTIVE")
        if organization_id is not None:
            zone_stmt = zone_stmt.where(Incident.organization_id == organization_id)
            crit_stmt = crit_stmt.where(Incident.organization_id == organization_id)

        total_zone_violations_24h = self.db.scalar(zone_stmt) or 0
        critical_incidents_active = self.db.scalar(crit_stmt) or 0

        workers_detected_24h = self.db.scalar(
            select(func.count(func.distinct(PersonDetection.person_id))).where(PersonDetection.timestamp >= day_ago)
        ) or 0

        # Compliance rate calculation
        total_evaluations = self.db.scalar(
            select(func.count(PPEViolation.id)).where(PPEViolation.timestamp >= day_ago)
        ) or 0
        pass_evaluations = self.db.scalar(
            select(func.count(PPEViolation.id)).where(PPEViolation.timestamp >= day_ago, PPEViolation.status == "PASS")
        ) or 0
        
        compliance_pct = 100.0 if total_evaluations == 0 else round((pass_evaluations / total_evaluations) * 100.0, 1)

        return {
            "total_cameras": total_cameras,
            "online_cameras": enabled_cameras,
            "offline_cameras": max(0, total_cameras - enabled_cameras),
            "active_fire_alerts": active_fire_alerts,
            "active_smoke_alerts": active_smoke_alerts,
            "ppe_violations_24h": total_ppe_violations_24h,
            "workers_detected_24h": workers_detected_24h,
            "zone_violations_24h": total_zone_violations_24h,
            "critical_incidents_active": critical_incidents_active,
            "daily_compliance_percentage": compliance_pct,
            "calculated_at": now.isoformat()
        }
