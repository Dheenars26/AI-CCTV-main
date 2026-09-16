"""
SQLAlchemy ORM Model for Confirmed Alert Incidents.
Stores alert lifecycle states (POSSIBLE, CONFIRMED, ALERT_SENT, ACTIVE, CLEARED).
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.camera import Camera
    from app.models.evidence import Evidence
    from app.models.notification import Notification


class Alert(Base):
    """
    Alert Table tracking verified fire & smoke incident lifecycles.
    """
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: f"evt_{uuid.uuid4().hex[:12]}"
    )
    camera_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("cameras.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )
    module: Mapped[str] = mapped_column(String(50), default="FIRE_SMOKE", index=True, nullable=False) # "FIRE_SMOKE", "SAFETY_ANALYSIS"
    class_name: Mapped[str] = mapped_column(String(50), index=True, nullable=False)  # "fire", "smoke", "cap_found", "mask_not_found", etc.

    state: Mapped[str] = mapped_column(String(30), index=True, nullable=False)  # POSSIBLE, CONFIRMED, ALERT_SENT, ACTIVE, CLEARED
    consecutive_frames: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    max_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    latest_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    
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
    remedial_action: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    remedy_notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
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

    # Relationships
    camera: Mapped["Camera"] = relationship("Camera", back_populates="alerts")
    evidence: Mapped[Optional["Evidence"]] = relationship(
        "Evidence",
        back_populates="alert",
        uselist=False,
        cascade="all, delete-orphan"
    )
    notifications: Mapped[List["Notification"]] = relationship(
        "Notification",
        back_populates="alert",
        cascade="all, delete-orphan"
    )

    # Compound Indexes
    __table_args__ = (
        Index("idx_alerts_camera_state", "camera_id", "state"),
        Index("idx_alerts_class_start", "class_name", "start_time"),
    )

    def __repr__(self) -> str:
        return (
            f"<Alert(id='{self.id}', camera_id={self.camera_id}, "
            f"class='{self.class_name}', state='{self.state}', max_conf={round(self.max_confidence, 2)})>"
        )
