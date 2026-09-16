"""
SQLAlchemy ORM Model for Security Audit Logs.
Dedicated table recording security events, authentication outcomes, RBAC access decisions, and entity mutations.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, DateTime, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class AuditLog(Base):
    """
    AuditLog Table capturing security, authentication, and access control audit events.
    """
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    event_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(String(36), index=True, nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), index=True, default="SUCCESS", nullable=False)  # SUCCESS, FAILED, DENIED
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
        nullable=False
    )

    __table_args__ = (
        Index("idx_audit_logs_event_time", "event_type", "created_at"),
        Index("idx_audit_logs_actor_time", "actor_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog(id='{self.id}', event_type='{self.event_type}', actor='{self.username}', status='{self.status}')>"
