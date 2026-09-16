"""
SQLAlchemy ORM Models for PPE Profiles, PPE Requirements, Person Detections, and PPE Violations.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.camera import Camera


class PPEProfile(Base):
    """
    Configurable PPE Profile (e.g., Factory Floor, Welding Area, Chemical Area).
    Stores required equipment rules per environment.
    """
    __tablename__ = "ppe_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    required_equipment: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)  # ["helmet", "vest", ...]
    optional_equipment: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)  # ["mask", ...]
    
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

    requirements: Mapped[List["PPERequirement"]] = relationship(
        "PPERequirement",
        back_populates="profile",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<PPEProfile(id={self.id}, name='{self.name}')>"


class PPERequirement(Base):
    """
    Individual equipment requirement mapping to a PPE profile.
    """
    __tablename__ = "ppe_requirements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ppe_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    equipment_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "helmet", "vest", "mask", "goggles", "gloves", "safety_shoes"
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="HIGH", nullable=False)  # HIGH, MEDIUM, LOW, CRITICAL
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    profile: Mapped["PPEProfile"] = relationship("PPEProfile", back_populates="requirements")

    __table_args__ = (
        Index("idx_ppe_req_profile_equip", "profile_id", "equipment_type"),
    )


class PersonDetection(Base):
    """
    Session-based worker/person detection history with temporary tracking IDs.
    Does NOT store facial identity or biometric data.
    """
    __tablename__ = "person_detections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    camera_id: Mapped[int] = mapped_column(Integer, ForeignKey("cameras.id", ondelete="CASCADE"), index=True, nullable=False)
    person_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)  # Temporary tracking ID per camera session
    bounding_box: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True, nullable=False)

    __table_args__ = (
        Index("idx_person_dets_cam_time", "camera_id", "timestamp"),
        Index("idx_person_dets_cam_person", "camera_id", "person_id"),
    )


class PPEViolation(Base):
    """
    Recorded worker PPE compliance violation.
    Indexed for fast query filtering by camera, zone, status, and severity.
    """
    __tablename__ = "ppe_violations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: f"violation_{uuid.uuid4().hex[:12]}")
    camera_id: Mapped[int] = mapped_column(Integer, ForeignKey("cameras.id", ondelete="CASCADE"), index=True, nullable=False)
    zone_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("safety_zones.id", ondelete="SET NULL"), index=True, nullable=True)
    person_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    profile_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("ppe_profiles.id", ondelete="SET NULL"), nullable=True)
    
    status: Mapped[str] = mapped_column(String(20), index=True, nullable=False, default="VIOLATION")  # PASS, VIOLATION, UNKNOWN
    severity: Mapped[str] = mapped_column(String(20), index=True, nullable=False, default="HIGH")  # CRITICAL, HIGH, MEDIUM, LOW
    missing_items: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    detected_items: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    required_items: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True, nullable=False)
    
    evidence_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    camera: Mapped["Camera"] = relationship("Camera")
    
    __table_args__ = (
        Index("idx_ppe_viol_cam_time", "camera_id", "timestamp"),
        Index("idx_ppe_viol_status_sev", "status", "severity"),
    )

    def __repr__(self) -> str:
        return f"<PPEViolation(id='{self.id}', camera={self.camera_id}, person={self.person_id}, status='{self.status}')>"
