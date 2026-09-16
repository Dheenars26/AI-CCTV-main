"""
SQLAlchemy ORM Model for Camera Configuration.
Stores persistent camera settings (RTSP stream details, location, status flags).
"""

from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, Boolean, Integer, Float, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.dvr import DVR
    from app.models.detection import Detection
    from app.models.alert import Alert


class Camera(Base):
    """
    Camera Configuration Table definition.
    Stores metadata and persistent settings for CCTV/DVR/NVR streams.
    """
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    camera_number: Mapped[str] = mapped_column(String(50), nullable=False, default="CAM-01")
    
    # Optional Physical DVR/NVR Association
    dvr_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("dvrs.id", ondelete="RESTRICT"), nullable=True)
    dvr_channel: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    channel_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    dvr_address: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    rtsp_url: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, default="rtsp")  # rtsp, file, webcam
    location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=13.0827)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=80.2707)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # AI Module Toggles & Per-Camera Scheduling
    fire_smoke_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ppe_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    person_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    zone_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ppe_inference_interval_sec: Mapped[float] = mapped_column(Float, default=0.05, nullable=False)

    # Performance, Priority & Scheduling Configuration
    priority: Mapped[str] = mapped_column(String(20), default="HIGH", nullable=False)  # HIGH, MEDIUM, LOW
    capture_fps: Mapped[int] = mapped_column(Integer, default=25, nullable=False)
    target_ai_fps: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    frame_skip: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    gpu_device_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 0, 1, -1 for CPU
    
    fps_limit: Mapped[int] = mapped_column(Integer, default=25, nullable=False)
    connection_timeout: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    reconnect_interval: Mapped[int] = mapped_column(Integer, default=5, nullable=False)

    # Timestamps
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
    dvr: Mapped[Optional["DVR"]] = relationship("DVR", back_populates="cameras")

    detections: Mapped[List["Detection"]] = relationship(
        "Detection",
        back_populates="camera",
        cascade="all, delete-orphan"
    )
    alerts: Mapped[List["Alert"]] = relationship(
        "Alert",
        back_populates="camera",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_camera_dvr_id", "dvr_id"),
        Index("idx_camera_priority", "priority"),
        Index("idx_camera_dvr_channel", "dvr_id", "dvr_channel"),
    )

    def __repr__(self) -> str:
        return f"<Camera(id={self.id}, name='{self.name}', dvr_id={self.dvr_id}, priority='{self.priority}')>"
