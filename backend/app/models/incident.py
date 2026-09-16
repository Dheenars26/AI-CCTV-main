"""
SQLAlchemy ORM Model for Workplace Safety Incidents & Combined Multi-Event Correlated Alerts.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, DateTime, ForeignKey, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.camera import Camera
    from app.models.zone import SafetyZone


class Incident(Base):
    """
    Unified Incident Table tracking workplace safety events and correlated multi-hazard incidents.
    Supports incident deduplication, acknowledgment, and resolution workflows.
    """
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: f"inc_{uuid.uuid4().hex[:12]}"
    )
    camera_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("cameras.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )
    zone_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("safety_zones.id", ondelete="SET NULL"),
        index=True,
        nullable=True
    )
    incident_type: Mapped[str] = mapped_column(
        String(50),
        index=True,
        nullable=False
    )  # "FIRE", "SMOKE", "PPE_VIOLATION", "ZONE_VIOLATION", "SAFETY_INCIDENT"
    
    # List of triggering events: ["FIRE_DETECTED", "PPE_VIOLATION", "UNAUTHORIZED_AREA_ENTRY"]
    events: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    severity: Mapped[str] = mapped_column(String(20), index=True, nullable=False, default="HIGH")  # CRITICAL, HIGH, MEDIUM, LOW
    status: Mapped[str] = mapped_column(String(30), index=True, nullable=False, default="ACTIVE")  # ACTIVE, ACKNOWLEDGED, RESOLVED

    person_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    evidence_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
        nullable=False
    )
    cleared_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    camera: Mapped["Camera"] = relationship("Camera")
    zone: Mapped[Optional["SafetyZone"]] = relationship("SafetyZone")

    __table_args__ = (
        Index("idx_incidents_cam_type_status", "camera_id", "incident_type", "status"),
        Index("idx_incidents_sev_start", "severity", "start_time"),
    )

    def __repr__(self) -> str:
        return f"<Incident(id='{self.id}', type='{self.incident_type}', severity='{self.severity}', status='{self.status}')>"
