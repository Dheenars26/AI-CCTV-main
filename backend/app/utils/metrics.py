"""
Prometheus Metrics Telemetry Engine (metrics.py).
Defines non-cardinal Prometheus metrics for operational observability.
High-cardinality labels (RTSP URLs, passwords, usernames, IP addresses, filenames, user IDs) are strictly excluded.
"""

import os
import time
import threading
from typing import Dict, Any, List, Optional
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


class MetricsRegistry:
    """
    In-memory Prometheus metrics collector producing standard Prometheus format exposition output.
    """

    def __init__(self):
        self._lock = threading.Lock()
        
        # Gauges
        self.camera_fps: Dict[str, float] = {}  # key: camera_name
        self.camera_connection_status: Dict[str, int] = {}  # key: camera_name (1=CONNECTED, 0=DISCONNECTED)
        self.dvr_connection_status: Dict[str, int] = {}  # key: dvr_name (1=ONLINE, 0=OFFLINE)
        self.ai_queue_depth: Dict[str, int] = {}  # key: camera_name
        self.websocket_connected_clients: int = 0
        self.evidence_storage_bytes: int = 0

        # Counters
        self.frame_dropped_total: Dict[str, int] = {}  # key: camera_name
        self.camera_reconnect_total: Dict[str, int] = {}  # key: camera_name
        self.ai_inference_total: int = 0
        self.detection_total: Dict[str, int] = {}  # key: detection_class (e.g. fire, smoke)
        self.alert_total: Dict[str, int] = {}  # key: severity (CRITICAL, WARNING)
        self.evidence_deleted_total: int = 0
        self.email_dispatch_total: Dict[str, int] = {}  # key: status (SUCCESS, FAILED)
        self.api_requests_total: Dict[str, int] = {}  # key: method_endpoint

        # PPE & Workplace Safety Metrics
        self.ppe_detection_total: Dict[str, int] = {}  # key: equipment_type
        self.ppe_violation_total: Dict[str, int] = {}  # key: camera_id
        self.ppe_compliance_total: Dict[str, int] = {}  # key: status (PASS, VIOLATION)
        self.zone_violation_total: Dict[str, int] = {}  # key: zone_type
        self.person_detection_total: Dict[str, int] = {}  # key: camera_id
        self.safety_incident_total: Dict[str, int] = {}  # key: incident_type

        # Histograms / Durations
        self.ai_inference_latency_sum: float = 0.0
        self.ai_inference_latency_count: int = 0
        self.api_request_duration_sum: float = 0.0
        self.api_request_duration_count: int = 0

    def record_camera_fps(self, camera_name: str, fps: float) -> None:
        with self._lock:
            self.camera_fps[camera_name] = round(fps, 2)

    def record_camera_status(self, camera_name: str, connected: bool) -> None:
        with self._lock:
            self.camera_connection_status[camera_name] = 1 if connected else 0

    def record_dvr_status(self, dvr_name: str, online: bool) -> None:
        with self._lock:
            self.dvr_connection_status[dvr_name] = 1 if online else 0

    def record_queue_depth(self, camera_name: str, depth: int) -> None:
        with self._lock:
            self.ai_queue_depth[camera_name] = depth

    def record_frame_dropped(self, camera_name: str) -> None:
        with self._lock:
            self.frame_dropped_total[camera_name] = self.frame_dropped_total.get(camera_name, 0) + 1

    def record_camera_reconnect(self, camera_name: str) -> None:
        with self._lock:
            self.camera_reconnect_total[camera_name] = self.camera_reconnect_total.get(camera_name, 0) + 1

    def record_ai_inference(self, latency_seconds: float) -> None:
        with self._lock:
            self.ai_inference_total += 1
            self.ai_inference_latency_sum += latency_seconds
            self.ai_inference_latency_count += 1

    def record_detection(self, label: str) -> None:
        with self._lock:
            l = label.lower()
            self.detection_total[l] = self.detection_total.get(l, 0) + 1

    def record_alert(self, severity: str) -> None:
        with self._lock:
            s = severity.upper()
            self.alert_total[s] = self.alert_total.get(s, 0) + 1

    def record_email_dispatch(self, success: bool) -> None:
        with self._lock:
            status_key = "SUCCESS" if success else "FAILED"
            self.email_dispatch_total[status_key] = self.email_dispatch_total.get(status_key, 0) + 1

    def update_websocket_clients(self, count: int) -> None:
        with self._lock:
            self.websocket_connected_clients = max(0, count)

    def record_evidence_deleted(self, count: int = 1) -> None:
        with self._lock:
            self.evidence_deleted_total += count

    def record_ppe_detection(self, equipment_type: str) -> None:
        with self._lock:
            eq = equipment_type.lower()
            self.ppe_detection_total[eq] = self.ppe_detection_total.get(eq, 0) + 1

    def record_ppe_violation(self, camera_id: int) -> None:
        with self._lock:
            cid_str = str(camera_id)
            self.ppe_violation_total[cid_str] = self.ppe_violation_total.get(cid_str, 0) + 1

    def record_ppe_compliance(self, status: str) -> None:
        with self._lock:
            s = status.upper()
            self.ppe_compliance_total[s] = self.ppe_compliance_total.get(s, 0) + 1

    def record_zone_violation(self, zone_type: str) -> None:
        with self._lock:
            zt = zone_type.upper()
            self.zone_violation_total[zt] = self.zone_violation_total.get(zt, 0) + 1

    def record_person_detection(self, camera_id: int) -> None:
        with self._lock:
            cid_str = str(camera_id)
            self.person_detection_total[cid_str] = self.person_detection_total.get(cid_str, 0) + 1

    def record_safety_incident(self, incident_type: str) -> None:
        with self._lock:
            it = incident_type.upper()
            self.safety_incident_total[it] = self.safety_incident_total.get(it, 0) + 1

    def generate_prometheus_output(self) -> str:
        """
        Formats metrics into standard Prometheus exposition format.
        """
        lines: List[str] = []

        # System Metrics
        cpu_pct = psutil.cpu_percent() if PSUTIL_AVAILABLE else 0.0
        ram_bytes = psutil.virtual_memory().used if PSUTIL_AVAILABLE else 0
        lines.append("# HELP cctv_cpu_usage_percent CPU utilization percentage")
        lines.append("# TYPE cctv_cpu_usage_percent gauge")
        lines.append(f"cctv_cpu_usage_percent {cpu_pct:.2f}")

        lines.append("# HELP cctv_memory_usage_bytes System memory usage in bytes")
        lines.append("# TYPE cctv_memory_usage_bytes gauge")
        lines.append(f"cctv_memory_usage_bytes {ram_bytes}")

        # GPU Metrics if available
        if TORCH_AVAILABLE and torch.cuda.is_available():
            for dev_id in range(torch.cuda.device_count()):
                try:
                    alloc_mem = torch.cuda.memory_allocated(dev_id)
                    lines.append(f'cctv_gpu_memory_allocated_bytes{{gpu="{dev_id}"}} {alloc_mem}')
                except Exception:
                    pass

        # Camera Gauges & Counters
        with self._lock:
            lines.append("# HELP cctv_camera_fps Current capture frame rate")
            lines.append("# TYPE cctv_camera_fps gauge")
            for cam, fps in self.camera_fps.items():
                safe_cam = cam.replace('"', '\\"')
                lines.append(f'cctv_camera_fps{{camera="{safe_cam}"}} {fps}')

            lines.append("# HELP cctv_camera_connection_status Connection status (1=connected, 0=disconnected)")
            lines.append("# TYPE cctv_camera_connection_status gauge")
            for cam, stat in self.camera_connection_status.items():
                safe_cam = cam.replace('"', '\\"')
                lines.append(f'cctv_camera_connection_status{{camera="{safe_cam}"}} {stat}')

            lines.append("# HELP cctv_dvr_connection_status DVR status (1=online, 0=offline)")
            lines.append("# TYPE cctv_dvr_connection_status gauge")
            for dvr, stat in self.dvr_connection_status.items():
                safe_dvr = dvr.replace('"', '\\"')
                lines.append(f'cctv_dvr_connection_status{{dvr="{safe_dvr}"}} {stat}')

            lines.append("# HELP cctv_ai_queue_depth Ingestion frame queue depth")
            lines.append("# TYPE cctv_ai_queue_depth gauge")
            for cam, depth in self.ai_queue_depth.items():
                safe_cam = cam.replace('"', '\\"')
                lines.append(f'cctv_ai_queue_depth{{camera="{safe_cam}"}} {depth}')

            lines.append("# HELP cctv_frame_dropped_total Total dropped frames")
            lines.append("# TYPE cctv_frame_dropped_total counter")
            for cam, cnt in self.frame_dropped_total.items():
                safe_cam = cam.replace('"', '\\"')
                lines.append(f'cctv_frame_dropped_total{{camera="{safe_cam}"}} {cnt}')

            lines.append("# HELP cctv_camera_reconnect_total Total camera reconnection attempts")
            lines.append("# TYPE cctv_camera_reconnect_total counter")
            for cam, cnt in self.camera_reconnect_total.items():
                safe_cam = cam.replace('"', '\\"')
                lines.append(f'cctv_camera_reconnect_total{{camera="{safe_cam}"}} {cnt}')

            lines.append("# HELP cctv_ai_inference_total Total AI inference executions")
            lines.append("# TYPE cctv_ai_inference_total counter")
            lines.append(f"cctv_ai_inference_total {self.ai_inference_total}")

            lines.append("# HELP cctv_detection_total Total object detections by label")
            lines.append("# TYPE cctv_detection_total counter")
            for label, cnt in self.detection_total.items():
                lines.append(f'cctv_detection_total{{detection_class="{label}"}} {cnt}')

            lines.append("# HELP cctv_alert_total Total alerts triggered by severity")
            lines.append("# TYPE cctv_alert_total counter")
            for sev, cnt in self.alert_total.items():
                lines.append(f'cctv_alert_total{{severity="{sev}"}} {cnt}')

            lines.append("# HELP cctv_email_dispatch_total Total email notifications dispatched")
            lines.append("# TYPE cctv_email_dispatch_total counter")
            for status_key, cnt in self.email_dispatch_total.items():
                lines.append(f'cctv_email_dispatch_total{{status="{status_key}"}} {cnt}')

            lines.append("# HELP cctv_websocket_connected_clients Active WebSocket client connections")
            lines.append("# TYPE cctv_websocket_connected_clients gauge")
            lines.append(f"cctv_websocket_connected_clients {self.websocket_connected_clients}")

            lines.append("# HELP cctv_evidence_deleted_total Total evidence items purged by retention cleaner")
            lines.append("# TYPE cctv_evidence_deleted_total counter")
            lines.append(f"cctv_evidence_deleted_total {self.evidence_deleted_total}")

            # PPE & Safety Exposition Metrics
            lines.append("# HELP cctv_ppe_detection_total Total PPE equipment detections")
            lines.append("# TYPE cctv_ppe_detection_total counter")
            for eq, cnt in self.ppe_detection_total.items():
                lines.append(f'cctv_ppe_detection_total{{equipment_type="{eq}"}} {cnt}')

            lines.append("# HELP cctv_ppe_violation_total Total PPE violations by camera ID")
            lines.append("# TYPE cctv_ppe_violation_total counter")
            for cid_str, cnt in self.ppe_violation_total.items():
                lines.append(f'cctv_ppe_violation_total{{camera_id="{cid_str}"}} {cnt}')

            lines.append("# HELP cctv_ppe_compliance_total Total PPE worker evaluations by status")
            lines.append("# TYPE cctv_ppe_compliance_total counter")
            for st, cnt in self.ppe_compliance_total.items():
                lines.append(f'cctv_ppe_compliance_total{{status="{st}"}} {cnt}')

            lines.append("# HELP cctv_zone_violation_total Total safety zone violations by zone type")
            lines.append("# TYPE cctv_zone_violation_total counter")
            for zt, cnt in self.zone_violation_total.items():
                lines.append(f'cctv_zone_violation_total{{zone_type="{zt}"}} {cnt}')

            lines.append("# HELP cctv_person_detection_total Total worker detections by camera ID")
            lines.append("# TYPE cctv_person_detection_total counter")
            for cid_str, cnt in self.person_detection_total.items():
                lines.append(f'cctv_person_detection_total{{camera_id="{cid_str}"}} {cnt}')

            lines.append("# HELP cctv_safety_incident_total Total workplace safety incidents by incident type")
            lines.append("# TYPE cctv_safety_incident_total counter")
            for it, cnt in self.safety_incident_total.items():
                lines.append(f'cctv_safety_incident_total{{incident_type="{it}"}} {cnt}')

        return "\n".join(lines) + "\n"


# Global Metrics Collector Singleton
metrics_collector = MetricsRegistry()
