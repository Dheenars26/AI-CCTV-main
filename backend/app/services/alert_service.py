"""
Alert & Incident Business Service Layer (AlertService).
Manages persistent ORM transactions for Alerts, Detections, Evidence metadata, Notifications, and SystemLogs.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc, select, and_

from app.models.alert import Alert
from app.models.detection import Detection
from app.models.evidence import Evidence
from app.models.notification import Notification
from app.models.system_log import SystemLog
from app.services.mongo_service import schedule_mongo_detection_log, schedule_mongo_detections_batch
from app.utils.logger import logger


class AlertService:
    """
    Business logic layer for Incident Alerts, Evidence metadata, and Audit logs.
    Handles atomic database transactions.
    """

    def __init__(self, db: Session):
        self.db = db

    def create_alert(
        self,
        alert_id: str,
        camera_id: int,
        class_name: str,
        state: str,
        consecutive_frames: int,
        duration_seconds: float,
        max_confidence: float,
        latest_confidence: float,
        start_time: datetime
    ) -> Alert:
        """
        Persists a new verified alert record in the database.
        """
        alert = Alert(
            id=alert_id,
            camera_id=camera_id,
            class_name=class_name.lower(),
            state=state.upper(),
            consecutive_frames=consecutive_frames,
            duration_seconds=duration_seconds,
            max_confidence=max_confidence,
            latest_confidence=latest_confidence,
            start_time=start_time
        )
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)
        logger.info(f"AlertService: Persisted Alert '{alert.id}' for Camera {camera_id} [{class_name}] state={state}")
        return alert

    def update_alert_state(
        self,
        alert_id: str,
        state: str,
        duration_seconds: Optional[float] = None,
        max_confidence: Optional[float] = None,
        cleared_time: Optional[datetime] = None
    ) -> Optional[Alert]:
        """
        Updates an existing alert record's state and metrics.
        """
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            return None

        alert.state = state.upper()
        if duration_seconds is not None:
            alert.duration_seconds = duration_seconds
        if max_confidence is not None:
            alert.max_confidence = max(alert.max_confidence, max_confidence)
        if cleared_time is not None:
            alert.cleared_time = cleared_time
        alert.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(alert)
        return alert

    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """
        Retrieves single alert record by ID.
        """
        return self.db.query(Alert).filter(Alert.id == alert_id).first()

    def list_alerts(
        self,
        camera_id: Optional[int] = None,
        class_name: Optional[str] = None,
        state: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Alert]:
        """
        Lists alert records matching optional search filters.
        """
        query = self.db.query(Alert)

        if camera_id is not None:
            query = query.filter(Alert.camera_id == camera_id)
        if class_name:
            query = query.filter(Alert.class_name == class_name.lower())
        if state:
            query = query.filter(Alert.state == state.upper())
        if start_date:
            query = query.filter(Alert.start_time >= start_date)
        if end_date:
            query = query.filter(Alert.start_time <= end_date)

        return query.order_by(desc(Alert.start_time)).offset(offset).limit(limit).all()

    def create_detection(
        self,
        camera_id: int,
        class_name: str,
        confidence: float,
        bounding_box: Dict[str, Any],
        frame_number: int = 0,
        fps: float = 0.0,
        timestamp: Optional[datetime] = None
    ) -> Detection:
        """
        Persists a raw frame AI detection record.
        """
        ts = timestamp or datetime.now(timezone.utc)
        det = Detection(
            camera_id=camera_id,
            class_name=class_name.lower(),
            confidence=confidence,
            bounding_box=bounding_box,
            frame_number=frame_number,
            fps=fps,
            timestamp=ts
        )
        self.db.add(det)
        self.db.commit()

        # Non-blocking async forward to MongoDB (Hybrid telemetry store)
        try:
            schedule_mongo_detection_log(
                camera_id=camera_id,
                camera_name=f"Camera #{camera_id}",
                class_name=class_name,
                confidence=confidence,
                bounding_box=bounding_box,
                frame_number=frame_number,
                fps=fps,
                timestamp=ts
            )
        except Exception:
            pass

        return det

    def create_detections_batch(
        self,
        camera_id: int,
        detections: List[Any],
        frame_number: int = 0,
        fps: float = 0.0,
        timestamp: Optional[datetime] = None
    ) -> List[Detection]:
        """
        Persists a batch of AI detections in a single atomic database transaction.
        Also pushes telemetry records to MongoDB detection_logs if connected.
        """
        if not detections:
            return []

        ts = timestamp or datetime.now(timezone.utc)
        records = []
        mongo_docs = []
        for det in detections:
            bbox_dict = det.bbox.to_dict() if hasattr(det, "bbox") else det.get("bbox", {})
            lbl = det.label if hasattr(det, "label") else det.get("label", "unknown")
            conf = det.confidence if hasattr(det, "confidence") else det.get("confidence", 0.0)
            records.append(
                Detection(
                    camera_id=camera_id,
                    class_name=str(lbl).lower(),
                    confidence=float(conf),
                    bounding_box=bbox_dict,
                    frame_number=frame_number,
                    fps=fps,
                    timestamp=ts
                )
            )
            mongo_docs.append({
                "class_name": str(lbl),
                "confidence": float(conf),
                "bounding_box": bbox_dict
            })

        self.db.add_all(records)
        self.db.commit()

        # Non-blocking async forward to MongoDB
        try:
            schedule_mongo_detections_batch(
                camera_id=camera_id,
                camera_name=f"Camera #{camera_id}",
                detections=mongo_docs,
                frame_number=frame_number,
                fps=fps,
                timestamp=ts
            )
        except Exception:
            pass

        return records

    def create_evidence_record(
        self,
        evidence_id: str,
        alert_id: str,
        camera_id: int,
        snapshot_relative_path: str,
        video_relative_path: Optional[str] = None,
        metadata_relative_path: Optional[str] = None,
        file_size_bytes: int = 0,
        metadata_envelope: Optional[Dict[str, Any]] = None,
        retention_days: int = 30
    ) -> Evidence:
        """
        Persists evidence file metadata and secure token reference in DB.
        """
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        retention_until = now + timedelta(days=retention_days)
        
        evidence = Evidence(
            evidence_id=evidence_id,
            alert_id=alert_id,
            camera_id=camera_id,
            snapshot_relative_path=snapshot_relative_path,
            video_relative_path=video_relative_path,
            metadata_relative_path=metadata_relative_path,
            file_size_bytes=file_size_bytes,
            metadata_envelope=metadata_envelope
        )
        self.db.add(evidence)
        self.db.commit()
        self.db.refresh(evidence)
        return evidence

    def get_evidence_by_token(self, evidence_id: str) -> Optional[Evidence]:
        """
        Retrieves evidence record by secure token ID.
        """
        return self.db.query(Evidence).filter(Evidence.evidence_id == evidence_id).first()

    def log_notification(self, alert_id: str, recipient: str, status: str, channel: str = "email", error_message: Optional[str] = None) -> Notification:
        """
        Persists notification delivery audit log entry.
        """
        notif = Notification(
            alert_id=alert_id,
            channel=channel,
            recipient=recipient,
            status=status.upper(),
            error_message=error_message,
            sent_at=datetime.now(timezone.utc)
        )
        self.db.add(notif)
        self.db.commit()
        self.db.refresh(notif)
        return notif

    def log_system_event(self, level: str, module: str, message: str, correlation_id: Optional[str] = None, camera_id: Optional[int] = None) -> SystemLog:
        """
        Persists operational system log entry.
        """
        sys_log = SystemLog(
            level=level.upper(),
            module=module,
            message=message,
            correlation_id=correlation_id,
            camera_id=camera_id,
            created_at=datetime.now(timezone.utc)
        )
        self.db.add(sys_log)
        self.db.commit()
        self.db.refresh(sys_log)
        return sys_log
