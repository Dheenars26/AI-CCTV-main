"""
High-Level Alert Manager Orchestrator Subsystem.
Submits verified alert events to an asynchronous background worker pool for non-blocking email delivery.
"""

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Any

from app.detection.verification import VerifiedEvent
from app.alerts.notification_manager import NotificationManager, NotificationLog
from app.utils.logger import logger


class AlertManager:
    """
    Orchestrates alert handling across NotificationManager and background worker pools.
    Guarantees non-blocking execution so stream ingestion and frame processing are never delayed.
    """

    def __init__(
        self,
        notification_manager: Optional[NotificationManager] = None,
        max_workers: int = 4
    ):
        self.notification_manager = notification_manager or NotificationManager()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="AlertWorker")

    def process_verified_event_async(
        self,
        event: VerifiedEvent,
        snapshot_path: Optional[str] = None,
        camera_name: str = "CCTV Camera",
        location: str = "Unspecified Location",
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        recipients: Optional[List[str]] = None
    ) -> None:
        """
        Submits email notification task to non-blocking background thread pool.
        Returns immediately to caller.
        """
        if event.state != "ALERT_SENT" and getattr(event.state, "value", str(event.state)) != "ALERT_SENT":
            return

        self._executor.submit(
            self._dispatch_task,
            event,
            snapshot_path,
            camera_name,
            location,
            latitude,
            longitude,
            recipients
        )

    def _dispatch_task(
        self,
        event: VerifiedEvent,
        snapshot_path: Optional[str],
        camera_name: str,
        location: str,
        latitude: Optional[float],
        longitude: Optional[float],
        recipients: Optional[List[str]]
    ) -> None:
        """
        Executes background email delivery task inside worker thread pool.
        Catches and logs any exceptions cleanly.
        """
        try:
            log_entry = self.notification_manager.dispatch_alert_notification(
                event=event,
                snapshot_path=snapshot_path,
                camera_name=camera_name,
                location=location,
                latitude=latitude,
                longitude=longitude,
                recipients=recipients
            )
            logger.info(
                f"AlertManager: Background notification worker completed. Status: {log_entry.status} "
                f"for Camera {event.camera_id} [{event.class_name}]"
            )
        except Exception as e:
            logger.error(f"AlertManager: Exception in background notification worker: {str(e)}")

    def shutdown(self) -> None:
        """
        Shuts down background worker pool cleanly on server exit.
        """
        logger.info("AlertManager: Shutting down background alert worker pool...")
        try:
            self._executor.shutdown(wait=True, cancel_futures=True)
        except TypeError:
            try:
                self._executor.shutdown(wait=True)
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"AlertManager: Exception during shutdown: {str(e)}")
