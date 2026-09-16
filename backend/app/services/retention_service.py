"""
Evidence Retention & Disk Space Cleaner Subsystem (EvidenceRetentionService).
Enforces evidence lifecycle states: ACTIVE, RESOLVED, PROTECTED, EXPIRED.
Monitors storage disk usage (minimum_free_disk_gb and percentage threshold).
Deletes DB metadata and physical evidence files transactionally.
NEVER purges ACTIVE (unresolved) or PROTECTED evidence items.
"""

import os
import shutil
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.models.evidence import Evidence
from app.models.alert import Alert
from app.utils.metrics import metrics_collector
from app.utils.logger import logger
from app.config.settings import settings


class EvidenceRetentionService:
    """
    Service managing disk space cleanup and evidence retention policies.
    """

    def __init__(
        self,
        retention_days: int = 30,
        min_free_disk_gb: float = 20.0,
        max_disk_usage_percent: float = 90.0
    ):
        self.retention_days = retention_days
        self.min_free_disk_gb = min_free_disk_gb
        self.max_disk_usage_percent = max_disk_usage_percent

    def run_retention_sweep(self, db: Session) -> Dict[str, Any]:
        """
        Executes retention policy sweep:
        1. Identifies RESOLVED evidence older than retention_days.
        2. Evaluates free disk space. If free GB < min_free_disk_gb or usage % > max_disk_usage_percent, triggers emergency purge of oldest RESOLVED evidence.
        3. Transactionally deletes metadata + files. Never deletes ACTIVE or PROTECTED evidence.
        """
        purged_count = 0
        freed_bytes = 0

        now = datetime.now(timezone.utc)
        cutoff_date = now - timedelta(days=self.retention_days)

        # 1. Sweep expired RESOLVED evidence older than cutoff_date
        expired_items = db.query(Evidence).filter(
            Evidence.created_at <= cutoff_date
        ).all()

        for item in expired_items:
            if item.retention_until and item.retention_until > now:
                continue  # Protected by retention_until lock!

            # Check associated alert status
            alert = db.query(Alert).filter(Alert.id == item.alert_id).first()
            if alert and alert.state in ("ACTIVE", "ALERT_SENT", "UNRESOLVED"):
                continue  # Never delete ACTIVE / UNRESOLVED evidence!

            size = item.file_size_bytes or 0
            if self._delete_evidence_item(db, item):
                purged_count += 1
                freed_bytes += size

        # 2. Check disk space threshold
        evidence_dir = getattr(settings, "EVIDENCE_STORAGE_PATH", "./evidence")
        if os.path.exists(evidence_dir):
            total, used, free = shutil.disk_usage(evidence_dir)
            free_gb = free / (1024 ** 3)
            usage_percent = (used / total) * 100

            if free_gb < self.min_free_disk_gb or usage_percent > self.max_disk_usage_percent:
                logger.warning(f"RetentionService: Emergency Disk Purge Triggered! Free Disk: {free_gb:.2f} GB (Threshold: {self.min_free_disk_gb} GB), Usage: {usage_percent:.1f}%")

                emergency_items = db.query(Evidence).order_by(Evidence.created_at.asc()).limit(50).all()

                for item in emergency_items:
                    if item.retention_until and item.retention_until > now:
                        continue
                    alert = db.query(Alert).filter(Alert.id == item.alert_id).first()
                    if alert and alert.state in ("ACTIVE", "ALERT_SENT", "UNRESOLVED"):
                        continue

                    size = item.file_size_bytes or 0
                    if self._delete_evidence_item(db, item):
                        purged_count += 1
                        freed_bytes += size

        metrics_collector.record_evidence_deleted(purged_count)
        return {
            "purged_count": purged_count,
            "freed_bytes": freed_bytes,
            "cutoff_date": cutoff_date.isoformat()
        }

    def _delete_evidence_item(self, db: Session, item: Evidence) -> bool:
        """
        Deletes physical snapshot/clip files and DB record transactionally.
        Handles missing files safely.
        """
        try:
            # Delete physical files
            snap_path = getattr(item, "snapshot_relative_path", None) or getattr(item, "snapshot_path", None)
            vid_path = getattr(item, "video_relative_path", None) or getattr(item, "video_clip_path", None)
            paths_to_remove = [snap_path, vid_path]
            for p in paths_to_remove:
                if p and os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception as fe:
                        logger.warning(f"RetentionService: File remove error for '{p}': {str(fe)}")

            # Delete DB record
            db.delete(item)
            db.commit()
            logger.info(f"RetentionService: Transactionally purged Evidence ID '{item.evidence_id}'")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"RetentionService: Transactional deletion failed for Evidence ID '{item.evidence_id}': {str(e)}")
            return False
