"""
SQLAlchemy ORM Model for Refresh Token Family Tracking & Revocation.
Enables Refresh Token Rotation and Theft Reuse Detection.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class RefreshToken(Base):
    """
    RefreshToken Table storing active, rotated, and revoked refresh tokens by family ID.
    """
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    family_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    replaced_by_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    __table_args__ = (
        Index("idx_refresh_tokens_user_family", "user_id", "family_id"),
    )

    def __repr__(self) -> str:
        return f"<RefreshToken(id='{self.id}', family_id='{self.family_id}', user_id='{self.user_id}', revoked={self.is_revoked})>"
