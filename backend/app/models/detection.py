"""
SQLAlchemy ORM Model for Raw AI Detections.
Stores high-volume frame prediction history with indexes for performance auditing.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.camera import Camera


class Detection(Base):
    """
    Detection Table storing raw AI frame predictions (fire, smoke).
    """
    __tablename__ = "detections"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    camera_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("cameras.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )
    module: Mapped[str] = mapped_column(String(50), default="FIRE_SMOKE", index=True, nullable=False) # "FIRE_SMOKE", "SAFETY_ANALYSIS"
    class_name: Mapped[str] = mapped_column(String(50), index=True, nullable=False)  # "fire", "smoke"

    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    bounding_box: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)  # {x_min, y_min, x_max, y_max}
    frame_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fps: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
        nullable=False
    )

    # Relationships
    camera: Mapped["Camera"] = relationship("Camera", back_populates="detections")

    # Compound Indexes for high-frequency queries
    __table_args__ = (
        Index("idx_detections_camera_time", "camera_id", "timestamp"),
        Index("idx_detections_class_conf", "class_name", "confidence"),
    )

    def __repr__(self) -> str:
        return (
            f"<Detection(id='{self.id}', camera_id={self.camera_id}, "
            f"class='{self.class_name}', conf={round(self.confidence, 2)})>"
        )
