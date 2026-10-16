"""
Commercial License & Subscription Enforcement Service.
Enforces product tiers (STARTER, PROFESSIONAL, ENTERPRISE), camera limits,
and module gating per customer organization.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, Dict, Any, List
from sqlalchemy.orm import Session

from app.models.license import License, LicenseTier, LicenseStatus, TIER_SPECS
from app.models.camera import Camera
from app.utils.logger import logger
from app.utils.exceptions import AppException


class LicenseService:
    """
    Manages license validation, camera quotas, module authorization, and tier boundaries.
    """

    @staticmethod
    def get_license_for_org(db: Session, organization_id: str) -> Optional[License]:
        """Fetches active license record for an organization."""
        return db.query(License).filter(License.organization_id == organization_id).first()

    @staticmethod
    def create_or_update_license(
        db: Session,
        organization_id: str,
        license_key: str,
        tier: str = LicenseTier.STARTER.value,
        max_cameras: Optional[int] = None,
        enabled_modules: Optional[List[str]] = None,
        status: str = LicenseStatus.ACTIVE.value,
        expires_at: Optional[datetime] = None
    ) -> License:
        """Creates or updates a license with appropriate tier specs."""
        tier_upper = tier.upper()
        if tier_upper not in TIER_SPECS:
            tier_upper = LicenseTier.STARTER.value

        spec = TIER_SPECS[tier_upper]
        effective_max = max_cameras if max_cameras is not None else int(spec["max_cameras"])
        default_modules: list[str] = spec["enabled_modules"] if isinstance(spec["enabled_modules"], list) else ["fire_smoke"]
        effective_modules = enabled_modules if enabled_modules is not None else list(default_modules)

        lic = db.query(License).filter(License.organization_id == organization_id).first()
        if not lic:
            lic = License(
                organization_id=organization_id,
                license_key=license_key,
                tier=tier_upper,
                max_cameras=effective_max,
                enabled_modules=effective_modules,
                status=status,
                expires_at=expires_at
            )
            db.add(lic)
        else:
            lic.license_key = license_key
            lic.tier = tier_upper
            lic.max_cameras = effective_max
            lic.enabled_modules = effective_modules
            lic.status = status
            lic.expires_at = expires_at

        db.commit()
        db.refresh(lic)
        return lic

    @classmethod
    def validate_license(cls, db: Session, organization_id: Optional[str]) -> Tuple[bool, str, Optional[License]]:
        """
        Validates license status for an organization.
        Returns (is_valid, reason, license_object).
        If organization_id is None, allows standalone single-tenant operation.
        """
        if not organization_id:
            # Standalone single-tenant mode without license constraint
            return True, "STANDALONE_VALID", None

        lic = cls.get_license_for_org(db, organization_id)
        if not lic:
            return False, "LICENSE_NOT_FOUND", None

        if lic.status != LicenseStatus.ACTIVE.value:
            return False, f"LICENSE_{lic.status}", lic

        if lic.expires_at is not None:
            exp = lic.expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > exp:
                return False, "LICENSE_EXPIRED", lic

        return True, "LICENSE_ACTIVE", lic

    @classmethod
    def check_camera_limit(cls, db: Session, organization_id: Optional[str]) -> Tuple[bool, str]:
        """
        Validates whether adding a camera would exceed the organization's licensed camera cap.
        Returns (allowed: bool, reason: str).
        """
        if not organization_id:
            return True, "NO_LIMIT"

        valid, reason, lic = cls.validate_license(db, organization_id)
        if not valid:
            return False, reason

        if not lic:
            return True, "NO_LIMIT"

        curr_count = db.query(Camera).filter(Camera.organization_id == organization_id).count()
        if curr_count >= lic.max_cameras:
            return False, f"CAMERA_LIMIT_EXCEEDED (Max: {lic.max_cameras}, Current: {curr_count})"

        return True, "ALLOWED"

    @classmethod
    def check_module_allowed(cls, db: Session, organization_id: Optional[str], module_name: str) -> Tuple[bool, str]:
        """
        Checks if a requested module (e.g. 'ppe', 'fire_smoke', 'zones') is enabled under the license.
        """
        if not organization_id:
            return True, "ALLOWED"

        valid, reason, lic = cls.validate_license(db, organization_id)
        if not valid:
            return False, reason

        if not lic:
            return True, "ALLOWED"

        if lic.tier == LicenseTier.ENTERPRISE.value:
            return True, "ALLOWED"

        if lic.is_module_enabled(module_name):
            return True, "ALLOWED"

        return False, f"MODULE_DISABLED_FOR_TIER_{lic.tier}"
