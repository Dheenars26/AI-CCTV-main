"""
SQLAlchemy ORM Model for Physical DVR/NVR Devices (DVR).
Stores metadata, management host/port specs, encrypted credentials, channel limits, and health status.
"""

from enum import Enum as PyEnum
from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, Boolean, Integer, DateTime, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.camera import Camera


class DVRStatus(str, PyEnum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    UNREACHABLE = "UNREACHABLE"
    DEGRADED = "DEGRADED"
    UNKNOWN = "UNKNOWN"
    RECOVERING = "RECOVERING"


class DVRManufacturer(str, PyEnum):
    GENERIC_RTSP = "GENERIC_RTSP"
    HIKVISION = "HIKVISION"
    DAHUA = "DAHUA"
    CPPLUS = "CPPLUS"


class DVR(Base):
    """
    Physical DVR/NVR Device Table Definition.
    Manages multi-channel video recorder hardware connections.
    """
    __tablename__ = "dvrs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    
    # Network Management Endpoint Specs
    management_host: Mapped[str] = mapped_column(String(100), nullable=False)
    management_port: Mapped[int] = mapped_column(Integer, default=80, nullable=False)
    rtsp_port: Mapped[int] = mapped_column(Integer, default=554, nullable=False)

    # Encrypted Credential Reference (AES-256)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    credential_reference: Mapped[str] = mapped_column(Text, nullable=False)

    # Hardware Specs
    manufacturer: Mapped[str] = mapped_column(String(50), nullable=False, default=DVRManufacturer.GENERIC_RTSP.value)
    channels_count: Mapped[int] = mapped_column(Integer, default=16, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Health Check Telemetry
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=DVRStatus.UNKNOWN.value)
    last_health_check_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_successful_health_check_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    health_check_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Optimistic Concurrency Protection
    version_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

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

    # Relational Camera Mapping (Restricts deletion if cameras are attached)
    cameras: Mapped[List["Camera"]] = relationship(
        "Camera",
        back_populates="dvr",
        cascade="save-update",
        passive_deletes=False
    )

    __table_args__ = (
        Index("idx_dvr_status", "status"),
        Index("idx_dvr_mgmt_host", "management_host"),
    )

    def __repr__(self) -> str:
        return f"<DVR(id={self.id}, name='{self.name}', host='{self.management_host}', status='{self.status}')>"
