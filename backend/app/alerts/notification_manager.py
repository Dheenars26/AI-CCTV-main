"""
Notification Manager Subsystem.
Manages recipient rules, template rendering, email cooldown control, and audit logging.
"""

import uuid
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any

from app.config.settings import settings
from app.detection.verification import VerifiedEvent
from app.alerts.email_service import EmailService
from app.alerts.webhook_service import WebhookService
from app.utils.logger import logger


@dataclass
class NotificationLog:
    """
    Notification delivery log entry.
    """
    notification_id: str
    event_id: str
    camera_id: int
    class_name: str
    recipients: List[str]
    status: str  # PENDING, DELIVERED, FAILED, SUPPRESSED_COOLDOWN
    timestamp: datetime
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "notification_id": self.notification_id,
            "event_id": self.event_id,
            "camera_id": self.camera_id,
            "class_name": self.class_name,
            "recipients": self.recipients,
            "status": self.status,
            "timestamp": self.timestamp.isoformat(),
            "error_message": self.error_message,
            "metadata": self.metadata
        }


class NotificationManager:
    """
    Manages alert notification rules, duplicate alert suppression, and delivery audit trails across Email and Webhooks.
    """

    def __init__(
        self,
        email_service: Optional[EmailService] = None,
        webhook_service: Optional[WebhookService] = None
    ):
        self.email_service = email_service or EmailService()
        self.webhook_service = webhook_service or WebhookService()
        self._cooldown_seconds = settings.EMAIL_COOLDOWN_SECONDS
        self._email_cooldowns: Dict[Tuple[int, str], float] = {}
        self._logs: List[NotificationLog] = []
        self._lock = threading.Lock()

    def is_in_cooldown(self, camera_id: int, class_name: str) -> bool:
        """
        Returns True if (camera_id, class_name) is within the alert cooldown period.
        """
        key = (camera_id, class_name.lower())
        now = time.time()
        with self._lock:
            last_time = self._email_cooldowns.get(key, 0.0)
            return (now - last_time) < self._cooldown_seconds

    def update_cooldown(self, camera_id: int, class_name: str) -> None:
        """
        Updates last notification timestamp for (camera_id, class_name).
        """
        key = (camera_id, class_name.lower())
        with self._lock:
            self._email_cooldowns[key] = time.time()

    def dispatch_alert_notification(
        self,
        event: VerifiedEvent,
        snapshot_path: Optional[str] = None,
        camera_name: str = "CCTV Camera",
        location: str = "Unspecified Location",
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        recipients: Optional[List[str]] = None
    ) -> NotificationLog:
        """
        Processes and dispatches email and webhook alert notifications for a verified incident.
        Applies cooldown rules and logs delivery status.
        """
        target_recipients = recipients or settings.ALERT_RECIPIENT_EMAILS
        if isinstance(target_recipients, str):
            target_recipients = [r.strip() for r in target_recipients.split(",") if r.strip()]

        # Auto-fallback to active admin user emails in DB if recipient list is unconfigured/empty
        if not target_recipients:
            try:
                from app.database.session import SessionLocal
                from app.models.user import User
                db = SessionLocal()
                try:
                    users = db.query(User.email).filter(User.is_active == True).all()
                    if users:
                        target_recipients = [u[0] for u in users if u[0]]
                finally:
                    db.close()
            except Exception:
                pass
            if not target_recipients:
                target_recipients = [getattr(settings, "SMTP_SENDER_EMAIL", None) or "admin@aicctv.local"]

        notif_id = f"notif_{uuid.uuid4().hex[:10]}"
        now_dt = datetime.now(timezone.utc)

        # Check if email/alert notifications are globally enabled
        if not settings.EMAIL_ALERTS_ENABLED and not settings.WEBHOOK_ALERTS_ENABLED:
            logger.info("NotificationManager: Alert notifications are globally disabled in settings.")
            log_entry = NotificationLog(
                notification_id=notif_id,
                event_id=event.event_id,
                camera_id=event.camera_id,
                class_name=event.class_name,
                recipients=target_recipients,
                status="DISABLED",
                timestamp=now_dt
            )
            self._add_log(log_entry)
            return log_entry

        # Check Cooldown
        if self.is_in_cooldown(event.camera_id, event.class_name):
            logger.info(
                f"NotificationManager: Suppressed duplicate notification for Camera {event.camera_id} "
                f"[{event.class_name.upper()}] (Active cooldown period)."
            )
            log_entry = NotificationLog(
                notification_id=notif_id,
                event_id=event.event_id,
                camera_id=event.camera_id,
                class_name=event.class_name,
                recipients=target_recipients,
                status="SUPPRESSED_COOLDOWN",
                timestamp=now_dt
            )
            self._add_log(log_entry)
            return log_entry

        lat = latitude if latitude is not None else getattr(settings, "DEFAULT_LATITUDE", 13.0827)
        lon = longitude if longitude is not None else getattr(settings, "DEFAULT_LONGITUDE", 80.2707)
        maps_link = f"https://www.google.com/maps?q={lat},{lon}"

        # Extract missing equipment and worker metadata if available
        evt_meta = event.metadata or {}
        raw_missing = evt_meta.get("missing_equipment") or evt_meta.get("missing_items") or []
        if isinstance(raw_missing, str):
            raw_missing = [raw_missing]

        # Filter out helmet from missing items
        clean_missing = [m for m in raw_missing if m.lower() not in ["helmet", "cap", "hard_hat", "headgear"]]
        display_map = {
            "vest": "VEST",
            "safety_vest": "VEST",
            "jacket": "VEST",
            "goggles": "GLASSES",
            "glass": "GLASSES",
            "glasses": "GLASSES",
            "safety_glasses": "GLASSES",
            "safety_glass": "GLASSES"
        }
        clean_display_missing = [display_map.get(m.lower(), m.upper()) for m in clean_missing]
        person_id = evt_meta.get("person_id")

        # Construct descriptive subject line
        cls_lower = event.class_name.lower()
        if "fire" in cls_lower:
            subj_tag = "CRITICAL FIRE"
        elif "smoke" in cls_lower:
            subj_tag = "WARNING SMOKE"
        elif clean_display_missing:
            missing_fmt = " & ".join([f"NO {item}" for item in clean_display_missing])
            subj_tag = f"PPE VIOLATION ({missing_fmt})"
        elif "ppe" in cls_lower:
            subj_tag = "PPE VIOLATION (NO VEST & NO GLASSES)"
        else:
            subj_tag = event.class_name.upper()

        subject = f"[{subj_tag} ALERT] Camera CAM-{event.camera_id:02d} ({camera_name}) Verified!"

        alert_data = {
            "event_id": event.event_id,
            "evidence_id": evt_meta.get("evidence_id", "N/A"),
            "camera_id": event.camera_id,
            "camera_name": camera_name,
            "location": location,
            "latitude": lat,
            "longitude": lon,
            "google_maps_link": maps_link,
            "class_name": event.class_name,
            "missing_items": clean_display_missing if clean_display_missing else clean_missing,
            "person_id": person_id,
            "confidence": event.max_confidence,
            "timestamp": event.start_time.isoformat()
        }

        # 1. Send Email Notification
        email_success = True
        if settings.EMAIL_ALERTS_ENABLED:
            if target_recipients:
                email_success = self.email_service.send_email(
                    recipients=target_recipients,
                    subject=subject,
                    alert_data=alert_data,
                    snapshot_path=snapshot_path
                )
            else:
                logger.info(
                    f"NotificationManager: No email recipients configured for Camera {event.camera_id} "
                    f"[{event.class_name.upper()}]. Skipping email dispatch."
                )

        # 2. Dispatch Webhook Notification
        webhook_results = {}
        if settings.WEBHOOK_ALERTS_ENABLED and settings.WEBHOOK_URLS:
            webhook_results = self.webhook_service.dispatch_all(alert_data)

        overall_success = email_success and (not webhook_results or any(webhook_results.values()))
        status_str = "DELIVERED" if overall_success else "FAILED"
        if overall_success:
            self.update_cooldown(event.camera_id, event.class_name)

        log_entry = NotificationLog(
            notification_id=notif_id,
            event_id=event.event_id,
            camera_id=event.camera_id,
            class_name=event.class_name,
            recipients=target_recipients,
            status=status_str,
            timestamp=now_dt,
            error_message=None if overall_success else (self.email_service.last_error or "One or more notification channels failed"),
            metadata={"webhook_deliveries": webhook_results}
        )
        self._add_log(log_entry)

        # Persist delivery attempt records to SQL Database for UI audit trail
        try:
            from app.database.session import SessionLocal, db_write_lock
            from app.models.notification import Notification
            with db_write_lock:
                db_notif = SessionLocal()
                try:
                    for r_email in target_recipients:
                        err_msg = self.email_service.last_error if not email_success else None
                        n_rec = Notification(
                            id=f"notif_{uuid.uuid4().hex[:12]}",
                            alert_id=event.event_id,
                            channel="email",
                            recipient=r_email,
                            status="DELIVERED" if email_success else "FAILED",
                            error_message=err_msg,
                            sent_at=now_dt
                        )
                        db_notif.add(n_rec)
                    db_notif.commit()
                finally:
                    db_notif.close()
        except Exception as db_err:
            logger.warning(f"NotificationManager: Failed to persist notification audit records to DB: {str(db_err)}")

        return log_entry

    def _add_log(self, log_entry: NotificationLog) -> None:
        with self._lock:
            self._logs.append(log_entry)

    def get_notification_logs(self, camera_id: Optional[int] = None) -> List[NotificationLog]:
        with self._lock:
            if camera_id is not None:
                return [l for l in self._logs if l.camera_id == camera_id]
            return list(self._logs)

    def send_test_email_notification(self, recipient_email: Optional[str] = None) -> Dict[str, Any]:
        """
        Dispatches a test alert email with an attached sample evidence snapshot image.
        """
        import os
        import cv2
        import numpy as np

        target_recipient = recipient_email.strip() if recipient_email else None
        if not target_recipient:
            recipients = settings.ALERT_RECIPIENT_EMAILS
            if isinstance(recipients, str):
                recipients = [r.strip() for r in recipients.split(",") if r.strip()]
            target_recipient = recipients[0] if recipients else settings.SMTP_SENDER_EMAIL

        os.makedirs(settings.EVIDENCE_STORAGE_DIR, exist_ok=True)
        
        # 1. Prefer latest real camera evidence snapshot if available
        candidate_snapshots = []
        for root, _, files in os.walk(settings.EVIDENCE_STORAGE_DIR):
            for file in files:
                if file.lower().endswith(".jpg") and not file.startswith("test_evidence"):
                    fpath = os.path.join(root, file)
                    try:
                        candidate_snapshots.append((os.path.getmtime(fpath), fpath))
                    except Exception:
                        pass

        if candidate_snapshots:
            candidate_snapshots.sort(key=lambda x: x[0], reverse=True)
            test_snapshot_path = candidate_snapshots[0][1]
        else:
            test_snapshot_path = os.path.join(settings.EVIDENCE_STORAGE_DIR, "test_evidence_snapshot.jpg")
            if not os.path.exists(test_snapshot_path):
                img = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(img, "AI CCTV TEST EVIDENCE SNAPSHOT", (40, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                cv2.putText(img, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"), (40, 250), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
                cv2.rectangle(img, (150, 280), (490, 420), (0, 0, 255), 2)
                cv2.putText(img, "CRITICAL DETECTED THREAT", (160, 310), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                cv2.imwrite(test_snapshot_path, img)

        alert_data = {
            "event_id": f"evt_test_{uuid.uuid4().hex[:8]}",
            "evidence_id": "ev_test_snapshot_01",
            "camera_id": 1,
            "camera_name": "Test CCTV Camera 01",
            "location": "Main Entrance Zone",
            "latitude": getattr(settings, "DEFAULT_LATITUDE", 13.0827),
            "longitude": getattr(settings, "DEFAULT_LONGITUDE", 80.2707),
            "google_maps_link": f"https://www.google.com/maps?q={getattr(settings, 'DEFAULT_LATITUDE', 13.0827)},{getattr(settings, 'DEFAULT_LONGITUDE', 80.2707)}",
            "class_name": "fire",
            "missing_items": ["vest", "goggles"],
            "person_id": 101,
            "confidence": 0.965,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        subject = "[TEST ALERT] AI CCTV System Email & Evidence Verification"
        success = self.email_service.send_email(
            recipients=[target_recipient],
            subject=subject,
            alert_data=alert_data,
            snapshot_path=test_snapshot_path
        )

        return {
            "success": success,
            "recipient": target_recipient,
            "snapshot_attached": os.path.exists(test_snapshot_path),
            "error_message": self.email_service.last_error if not success else None,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
