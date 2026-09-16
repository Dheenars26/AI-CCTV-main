"""
SQLAlchemy ORM Model for Operational System & Audit Logs.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, DateTime, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class SystemLog(Base):
    """
    SystemLog Table storing operational logs and audit events.
    """
    __tablename__ = "system_logs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    level: Mapped[str] = mapped_column(String(20), index=True, default="INFO", nullable=False)  # INFO, WARNING, ERROR, CRITICAL
    module: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    camera_id: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
        nullable=False
    )

    # Compound Index
    __table_args__ = (
        Index("idx_logs_level_time", "level", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<SystemLog(id='{self.id}', level='{self.level}', module='{self.module}', camera_id={self.camera_id})>"
