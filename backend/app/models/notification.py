"""
SQLAlchemy ORM Model for Alert Notification Audit Logs.
Stores email/webhook delivery logs and status tracking.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.alert import Alert


class Notification(Base):
    """
    Notification Table storing delivery attempts (DELIVERED, FAILED, SUPPRESSED_COOLDOWN).
    """
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: f"notif_{uuid.uuid4().hex[:12]}"
    )
    alert_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("alerts.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )
    channel: Mapped[str] = mapped_column(String(30), default="email", nullable=False)  # email, websocket, webhook
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)  # recipient email address
    status: Mapped[str] = mapped_column(String(30), index=True, default="PENDING", nullable=False)  # DELIVERED, FAILED, SUPPRESSED_COOLDOWN
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
        nullable=False
    )

    # Relationships
    alert: Mapped["Alert"] = relationship("Alert", back_populates="notifications")

    # Compound Index
    __table_args__ = (
        Index("idx_notifications_status_time", "status", "sent_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Notification(id='{self.id}', alert_id='{self.alert_id}', "
            f"recipient='{self.recipient}', status='{self.status}')>"
        )
