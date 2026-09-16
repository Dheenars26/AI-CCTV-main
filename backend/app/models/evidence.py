"""
SQLAlchemy ORM Model for Incident Evidence Metadata & Secure References.
Stores file metadata, secure token URLs, and retention policies. Does NOT store raw binaries in DB.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, TYPE_CHECKING
from sqlalchemy import String, Integer, DateTime, ForeignKey, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.alert import Alert
    from app.models.camera import Camera


class Evidence(Base):
    """
    Evidence Table storing secure token references and metadata for JPEG snapshots & MP4 clips.
    """
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    evidence_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False
    )
    alert_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("alerts.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )
    camera_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("cameras.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )
    snapshot_relative_path: Mapped[str] = mapped_column(String(500), nullable=False)
    video_relative_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    metadata_relative_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metadata_envelope: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    retention_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    alert: Mapped["Alert"] = relationship("Alert", back_populates="evidence")
    camera: Mapped["Camera"] = relationship("Camera")

    # Compound Index
    __table_args__ = (
        Index("idx_evidence_camera_retention", "camera_id", "retention_until"),
    )

    def __repr__(self) -> str:
        return (
            f"<Evidence(id='{self.id}', evidence_id='{self.evidence_id}', "
            f"alert_id='{self.alert_id}', camera_id={self.camera_id})>"
        )
