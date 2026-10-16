"""
SQLAlchemy ORM Models for Multi-Tenant Hierarchy.
Defines Organization, Site, and OrganizationUser entities.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.camera import Camera
    from app.models.license import License


class Organization(Base):
    """
    Customer Organization Table.
    Top-level multi-tenant tenant boundary isolating all sites, cameras, and events.
    """
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: f"org_{uuid.uuid4().hex[:12]}"
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

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
    sites: Mapped[List["Site"]] = relationship("Site", back_populates="organization", cascade="all, delete-orphan")
    license: Mapped[Optional["License"]] = relationship("License", back_populates="organization", uselist=False, cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Organization(id='{self.id}', name='{self.name}', slug='{self.slug}')>"


class Site(Base):
    """
    Physical Customer Site / Facility Table.
    Belongs to an Organization, groups physical camera and zone deployments.
    """
    __tablename__ = "sites"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: f"site_{uuid.uuid4().hex[:12]}"
    )
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

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
    organization: Mapped["Organization"] = relationship("Organization", back_populates="sites")

    def __repr__(self) -> str:
        return f"<Site(id='{self.id}', name='{self.name}', organization_id='{self.organization_id}')>"


class OrganizationUser(Base):
    """
    Join Table associating Users with Organizations and tenant roles.
    """
    __tablename__ = "organization_users"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )
    role: Mapped[str] = mapped_column(String(50), default="MEMBER", nullable=False)  # ORG_ADMIN, MEMBER

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    __table_args__ = (
        Index("idx_org_user_unique", "organization_id", "user_id", unique=True),
    )
