"""
Physical DVR/NVR Device Manager Subsystem (DVRManager).
Monitors physical DVR hardware health via 3-layer checks (Network -> Port -> Authenticated Check),
handles staggered DVR recovery (OFFLINE -> RECOVERING -> ONLINE), and prevents connection storms.
"""

import time
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable, Any

from app.models.dvr import DVR, DVRStatus
from app.camera.adapters.factory import DVRAdapterFactory
from app.utils.encryption import decrypt_credential
from app.utils.logger import logger


class DVRManager:
    """
    Manages physical DVR hardware device lifecycle, background health checks, and recovery loops.
    """

    def __init__(self, event_callback: Optional[Callable[[str, Dict[str, Any]], Any]] = None):
        self._dvrs: Dict[int, DVR] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None
        self.event_callback = event_callback
        self.check_interval_seconds: int = 15

    def set_event_callback(self, callback: Callable[[str, Dict[str, Any]], Any]) -> None:
        self.event_callback = callback

    def register_dvr(self, dvr: DVR) -> None:
        with self._lock:
            self._dvrs[dvr.id] = dvr
            logger.info(f"DVRManager: Registered DVR ID {dvr.id} ('{dvr.name}') at {dvr.management_host}:{dvr.management_port}")

    def unregister_dvr(self, dvr_id: int) -> None:
        with self._lock:
            self._dvrs.pop(dvr_id, None)
            logger.info(f"DVRManager: Unregistered DVR ID {dvr_id}")

    def get_dvr(self, dvr_id: int) -> Optional[DVR]:
        with self._lock:
            return self._dvrs.get(dvr_id)

    def start_health_monitor(self) -> None:
        from app.config.settings import settings
        if settings.APP_ENV == "testing":
            return
        with self._lock:
            if self._monitor_thread and self._monitor_thread.is_alive():
                return
            self._stop_event.clear()
            self._monitor_thread = threading.Thread(
                target=self._health_check_loop,
                name="DVRHealthMonitorThread",
                daemon=True
            )
            self._monitor_thread.start()
            logger.info("DVRManager: Started background DVR health monitor thread.")

    def stop_health_monitor(self) -> None:
        self._stop_event.set()
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=0.2)
        logger.info("DVRManager: Stopped DVR health monitor thread.")

    def check_dvr_health_now(self, dvr_id: int) -> Dict[str, Any]:
        dvr = self.get_dvr(dvr_id)
        if not dvr:
            return {"success": False, "error": f"DVR ID {dvr_id} not registered."}

        adapter = DVRAdapterFactory.get_adapter(dvr.manufacturer)
        password = decrypt_credential(dvr.credential_reference)

        net_ok, mgmt_ok, rtsp_ok, auth_ok, latency_ms, error_msg = adapter.perform_layered_health_check(
            host=dvr.management_host,
            management_port=dvr.management_port,
            rtsp_port=dvr.rtsp_port,
            username=dvr.username,
            password=password
        )

        now = datetime.now(timezone.utc)
        dvr.last_health_check_at = now
        old_status = dvr.status

        if net_ok and mgmt_ok:
            dvr.last_successful_health_check_at = now
            dvr.health_check_error = None
            if old_status in (DVRStatus.OFFLINE.value, DVRStatus.UNREACHABLE.value):
                new_status = DVRStatus.RECOVERING.value
            else:
                new_status = DVRStatus.ONLINE.value
        else:
            dvr.health_check_error = error_msg or "Layered network/port check failed"
            new_status = DVRStatus.OFFLINE.value

        dvr.status = new_status

        # Dispatch WebSocket Event on status transition
        if old_status != new_status and self.event_callback:
            try:
                self.event_callback("dvr_status_changed", {
                    "dvr_id": dvr.id,
                    "dvr_name": dvr.name,
                    "old_status": old_status,
                    "new_status": new_status,
                    "timestamp": now.isoformat()
                })
            except Exception as e:
                logger.warning(f"DVRManager: WebSocket event dispatch error: {str(e)}")

        return {
            "dvr_id": dvr.id,
            "name": dvr.name,
            "status": new_status,
            "network_reachable": net_ok,
            "management_port_reachable": mgmt_ok,
            "rtsp_port_reachable": rtsp_ok,
            "authenticated_check": auth_ok,
            "latency_ms": latency_ms,
            "error_details": dvr.health_check_error
        }

    def _health_check_loop(self) -> None:
        while not self._stop_event.is_set():
            with self._lock:
                dvr_ids = list(self._dvrs.keys())

            for dvr_id in dvr_ids:
                try:
                    self.check_dvr_health_now(dvr_id)
                except Exception as e:
                    logger.error(f"DVRManager: Error running health check on DVR ID {dvr_id}: {str(e)}")

            self._stop_event.wait(timeout=self.check_interval_seconds)
