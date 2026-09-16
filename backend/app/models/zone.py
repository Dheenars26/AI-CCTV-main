"""
SQLAlchemy ORM Model for Safety Zones.
Stores camera-bound polygon safety zone definitions and PPE requirements.
"""

from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.camera import Camera
    from app.models.ppe import PPEProfile


class SafetyZone(Base):
    """
    Safety Zone Table definition.
    Stores camera polygon boundaries (normalized coordinates [[x,y],...]) and zone type rules.
    """
    __tablename__ = "safety_zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("cameras.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    zone_type: Mapped[str] = mapped_column(String(30), default="HAZARD", index=True, nullable=False)  # HAZARD, RESTRICTED, GENERAL
    
    # Polygon coordinates stored as normalized [[x1, y1], [x2, y2], [x3, y3], ...] (0.0 to 1.0)
    polygon_coordinates: Mapped[List[List[float]]] = mapped_column(JSON, nullable=False)
    
    ppe_profile_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("ppe_profiles.id", ondelete="SET NULL"),
        nullable=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

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
    camera: Mapped["Camera"] = relationship("Camera")
    ppe_profile: Mapped[Optional["PPEProfile"]] = relationship("PPEProfile")

    __table_args__ = (
        Index("idx_safety_zone_cam_type", "camera_id", "zone_type"),
    )

    def __repr__(self) -> str:
        return f"<SafetyZone(id={self.id}, camera_id={self.camera_id}, name='{self.name}', type='{self.zone_type}')>"
