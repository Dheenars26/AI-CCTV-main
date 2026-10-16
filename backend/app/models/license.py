"""
SQLAlchemy ORM Model for Commercial Licenses & Subscriptions.
Supports STARTER, PROFESSIONAL, and ENTERPRISE tiers.
"""

import uuid
from enum import Enum
from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.organization import Organization


class LicenseTier(str, Enum):
    STARTER = "STARTER"
    PROFESSIONAL = "PROFESSIONAL"
    ENTERPRISE = "ENTERPRISE"


class LicenseStatus(str, Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    SUSPENDED = "SUSPENDED"


# Tier Default Specifications
TIER_SPECS = {
    LicenseTier.STARTER.value: {
        "max_cameras": 4,
        "enabled_modules": ["fire_smoke"],
        "multi_site": False
    },
    LicenseTier.PROFESSIONAL.value: {
        "max_cameras": 16,
        "enabled_modules": ["fire_smoke", "ppe", "zones", "person_tracking"],
        "multi_site": False
    },
    LicenseTier.ENTERPRISE.value: {
        "max_cameras": 99999,
        "enabled_modules": ["fire_smoke", "ppe", "zones", "person_tracking", "multi_site", "dvr_cluster"],
        "multi_site": True
    }
}


class License(Base):
    """
    Commercial License Table enforcing camera limits, modules, and tiers per organization.
    """
    __tablename__ = "licenses"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: f"lic_{uuid.uuid4().hex[:12]}"
    )
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False
    )
    license_key: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    tier: Mapped[str] = mapped_column(String(30), default=LicenseTier.STARTER.value, nullable=False)
    max_cameras: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    enabled_modules: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=LicenseStatus.ACTIVE.value, nullable=False)

    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

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

    # Relationship
    organization: Mapped["Organization"] = relationship("Organization", back_populates="license")

    def is_valid(self) -> bool:
        """Returns True if the license is ACTIVE and not expired."""
        if self.status != LicenseStatus.ACTIVE.value:
            return False
        if self.expires_at is not None:
            exp = self.expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > exp:
                return False
        return True

    def is_module_enabled(self, module_name: str) -> bool:
        """Checks if a specific functional module is permitted under this license."""
        if not self.is_valid():
            return False
        if self.tier == LicenseTier.ENTERPRISE.value:
            return True
        mods = [m.lower() for m in (self.enabled_modules or [])]
        return module_name.lower() in mods

    def __repr__(self) -> str:
        return f"<License(id='{self.id}', tier='{self.tier}', status='{self.status}', max_cameras={self.max_cameras})>"
