"""
Enterprise Multi-Camera & Multi-DVR Orchestration Subsystem (CameraManager).
Implements the 9-stage processing architecture:
DVR/NVR -> DVR Adapter -> DVR Manager -> Camera Manager -> Camera Workers (Ingestion) -> Bounded Queues -> Frame Scheduler -> AI Worker Pool -> Resource Manager.
"""

import time
import threading
from datetime import datetime, timezone
from typing import Dict, Optional, Callable, Tuple, Any, List
import numpy as np

from app.models.camera import Camera
from app.models.dvr import DVR, DVRStatus
from app.camera.base import CameraSource, CameraStatus, CameraRuntimeState
from app.camera.factory import CameraFactory
from app.camera.buffer import LatestFrameBuffer
from app.camera.bounded_queue import BoundedFrameQueue
from app.camera.frame_scheduler import FrameScheduler
from app.camera.resource_manager import ResourceManager
from app.camera.ai_pool import AIWorkerPool
from app.camera.dvr_manager import DVRManager
from app.utils.logger import logger

from app.config.settings import settings
from app.camera.pipeline import FramePipeline, StandardEventManager, StandardPostprocessor
from app.detection import YOLODetector, DummyDetector, FireSmokeDetector, PPEDetector, PersonDetector
from app.recording import RollingFrameRingBuffer, EvidenceService
from app.alerts import AlertManager


class CameraManager:
    """
    Orchestrates ingestion workers, bounded queues, frame scheduling, AI pool, and resource allocation.
    """

    def __init__(self, event_callback: Optional[Callable[[str, Dict[str, Any]], Any]] = None):
        self._sources: Dict[int, CameraSource] = {}
        self._buffers: Dict[int, LatestFrameBuffer] = {}
        self._bounded_queues: Dict[int, BoundedFrameQueue] = {}
        self._pipelines: Dict[int, FramePipeline] = {}
        self._ring_buffers: Dict[int, RollingFrameRingBuffer] = {}
        self._threads: Dict[int, threading.Thread] = {}
        self._stop_events: Dict[int, threading.Event] = {}
        self._reconnect_intervals: Dict[int, int] = {}
        self._camera_priorities: Dict[int, str] = {}
        self._camera_dvrs: Dict[int, Optional[int]] = {}
        self._camera_enabled: Dict[int, bool] = {}
        self._ai_jobs_in_progress: Dict[int, bool] = {}
        
        self._lock = threading.RLock()
        self.event_callback = event_callback

        # Stage Subsystem Components
        self.dvr_manager = DVRManager(event_callback=event_callback)
        self.frame_scheduler = FrameScheduler()
        self.resource_manager = ResourceManager()
        # Scale AI pool to prevent CPU saturation (max 2 workers on CPU fallback)
        default_ai_workers = getattr(settings, "MAX_CONCURRENT_AI_JOBS", 8)
        ai_workers = min(2, default_ai_workers) if not self.resource_manager.cuda_available else default_ai_workers
        self.ai_pool = AIWorkerPool(max_workers=ai_workers)
        self.evidence_service = EvidenceService()
        self.alert_manager = AlertManager()

        # Telemetry metrics counters
        self._ai_fps_window_start: Dict[int, float] = {}
        self._ai_frame_count: Dict[int, int] = {}
        self._current_ai_fps: Dict[int, float] = {}
        self._last_detection_db_save: Dict[int, float] = {}

    def set_event_callback(self, callback: Callable[[str, Dict[str, Any]], Any]) -> None:
        self.event_callback = callback
        self.dvr_manager.set_event_callback(callback)

    def _notify_lifecycle_event(self, event_type: str, camera_id: int, status: CameraStatus, details: str = "") -> None:
        if self.event_callback:
            payload = {
                "camera_id": camera_id,
                "status": status.value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "details": details
            }
            try:
                self.event_callback(event_type, payload)
            except Exception as e:
                logger.warning(f"Error executing camera lifecycle callback: {str(e)}")

    def add_camera(self, camera: Camera, zones: Optional[List[Dict[str, Any]]] = None) -> None:
        """
        Registers camera configuration, bounded ingestion queue, and pipeline.
        """
        with self._lock:
            try:
                cid = camera.id
                c_fps = int(getattr(camera, "capture_fps", 25) or 25)
                gpu_id = int(getattr(camera, "gpu_device_id", 0) or 0)
                fs_enabled = bool(getattr(camera, "fire_smoke_enabled", True))
                ppe_enabled = bool(getattr(camera, "ppe_enabled", True))
                person_enabled = bool(getattr(camera, "person_enabled", True))
                zone_enabled = bool(getattr(camera, "zone_enabled", True))
                ppe_interval = float(getattr(camera, "ppe_inference_interval_sec", 0.1) or 0.1)
            except Exception:
                cid = getattr(camera, "id", 1)
                c_fps = 25
                gpu_id = 0
                fs_enabled = True
                ppe_enabled = True
                person_enabled = True
                zone_enabled = True
                ppe_interval = 0.1

            if cid in self._sources:
                self.stop_camera(cid)

            source = CameraFactory.create_source(camera, camera_id=cid)
            self._sources[cid] = source
            self._buffers[cid] = LatestFrameBuffer(camera_id=cid)
            self._bounded_queues[cid] = BoundedFrameQueue(camera_id=cid, maxsize=1)
            self._ring_buffers[cid] = RollingFrameRingBuffer(
                max_seconds=getattr(settings, "PRE_EVENT_BUFFER_SECONDS", 5.0),
                default_fps=c_fps
            )

            # Device selection via ResourceManager
            target_device = self.resource_manager.get_target_device(gpu_id)
            
            try:
                fs_detector = FireSmokeDetector(device=target_device)
            except Exception as fe:
                logger.warning(f"CameraManager: FireSmokeDetector initialization warning for Camera ID {cid}: {fe}")
                fs_detector = None

            try:
                ppe_detector = PPEDetector(device=target_device)
            except Exception as pe:
                logger.warning(f"CameraManager: PPEDetector initialization warning for Camera ID {cid}: {pe}")
                ppe_detector = None

            try:
                person_detector = PersonDetector(device=target_device)
            except Exception as pde:
                logger.warning(f"CameraManager: PersonDetector initialization warning for Camera ID {cid}: {pde}")
                person_detector = None

            self._pipelines[cid] = FramePipeline(
                camera_id=cid,
                fire_smoke_detector=fs_detector,
                ppe_detector=ppe_detector,
                person_detector=person_detector,
                postprocessor=StandardPostprocessor(debug_overlay=settings.DEBUG),
                event_manager=StandardEventManager(event_callback=self.event_callback),
                fire_smoke_enabled=fs_enabled,
                ppe_enabled=ppe_enabled,
                person_enabled=person_enabled,
                zone_enabled=zone_enabled,
                ppe_inference_interval_sec=ppe_interval
            )
            logger.info(f"CameraManager: Configured pipeline & detectors for Camera ID {cid} on device '{target_device}'")

            # Apply any provided safety zones
            if zones:
                self._pipelines[cid].set_safety_zones(zones)

            self._reconnect_intervals[cid] = getattr(camera, "reconnect_interval", 5)
            self._camera_priorities[cid] = getattr(camera, "priority", "HIGH")
            self._camera_dvrs[cid] = getattr(camera, "dvr_id", None)
            self._camera_enabled[cid] = bool(getattr(camera, "enabled", True))
            self._ai_fps_window_start[cid] = time.time()
            self._ai_frame_count[cid] = 0
            self._current_ai_fps[cid] = 0.0

            logger.info(f"CameraManager: Added Camera ID {cid} ('{camera.name}') with device '{target_device}' & priority '{camera.priority}'.")

    def update_camera_safety_zones(self, camera_id: int, zones: Optional[List[Dict[str, Any]]] = None) -> None:
        """
        Hot-reloads safety zones for an active camera pipeline in real time.
        """
        with self._lock:
            pipeline = self._pipelines.get(camera_id)
            if not pipeline:
                return

            active_zones = zones if zones is not None else []
            pipeline.set_safety_zones(active_zones)
            logger.info(f"CameraManager: Hot-reloaded {len(active_zones)} safety zones for Camera ID {camera_id}")

    def is_camera_enabled(self, camera_id: int) -> bool:
        """
        Fast in-memory verification of camera-enabled state.
        Zero DB lock contention for high-frequency stream loops.
        """
        with self._lock:
            return self._camera_enabled.get(camera_id, False)

    def set_camera_enabled(self, camera_id: int, enabled: bool) -> None:
        """
        Updates in-memory camera-enabled state.
        """
        with self._lock:
            self._camera_enabled[camera_id] = enabled

    def start_camera(self, camera_id: int) -> bool:
        with self._lock:
            if camera_id not in self._sources:
                logger.error(f"CameraManager: Cannot start unknown Camera ID {camera_id}")
                return False

            existing_thread = self._threads.get(camera_id)
            existing_stop_event = self._stop_events.get(camera_id)

            if existing_thread and existing_thread.is_alive():
                if existing_stop_event and existing_stop_event.is_set():
                    logger.info(f"CameraManager: Waiting for terminating worker thread for Camera ID {camera_id}...")
                    existing_thread.join(timeout=2.0)
                else:
                    logger.info(f"CameraManager: Ingestion worker thread already active for Camera ID {camera_id}")
                    return True

            stop_event = threading.Event()
            self._stop_events[camera_id] = stop_event
            self._camera_enabled[camera_id] = True

            worker_thread = threading.Thread(
                target=self._camera_ingestion_worker_loop,
                args=(camera_id, stop_event),
                name=f"CameraIngestionWorker-{camera_id}",
                daemon=True
            )
            self._threads[camera_id] = worker_thread
            worker_thread.start()
            logger.info(f"CameraManager: Started ingestion worker thread for Camera ID {camera_id}")
            return True

    def is_running(self, camera_id: int) -> bool:
        """
        Verifies if background ingestion worker thread is active for camera_id.
        """
        with self._lock:
            thread = self._threads.get(camera_id)
            stop_evt = self._stop_events.get(camera_id)
            if stop_evt and stop_evt.is_set():
                return False
            return thread is not None and thread.is_alive()

    def start_all_enabled(self) -> None:
        """
        Starts background ingestion worker threads for all registered cameras.
        """
        with self._lock:
            camera_ids = list(self._sources.keys())
        for cid in camera_ids:
            self.start_camera(cid)



    def stop_camera(self, camera_id: int) -> None:
        with self._lock:
            stop_event = self._stop_events.get(camera_id)
            thread = self._threads.get(camera_id)
            source = self._sources.get(camera_id)
            buffer = self._buffers.get(camera_id)
            bqueue = self._bounded_queues.get(camera_id)

            if buffer:
                buffer.clear()
            if bqueue:
                bqueue.clear()

        if stop_event:
            stop_event.set()

        if source:
            try:
                source.disconnect()
            except Exception as e:
                logger.warning(f"CameraManager: Exception during source disconnect for Camera ID {camera_id}: {str(e)}")

        if thread and thread.is_alive():
            thread.join(timeout=0.1)

        with self._lock:
            self._threads.pop(camera_id, None)
            self._stop_events.pop(camera_id, None)
            self._camera_enabled[camera_id] = False
            self._ai_jobs_in_progress.pop(camera_id, None)
            self._notify_lifecycle_event("CAMERA_STOPPED", camera_id, CameraStatus.DISCONNECTED)
            logger.info(f"CameraManager: Fast-stopped Camera ID {camera_id}")

    def remove_camera(self, camera_id: int) -> None:
        self.stop_camera(camera_id)
        with self._lock:
            self._sources.pop(camera_id, None)
            self._buffers.pop(camera_id, None)
            self._bounded_queues.pop(camera_id, None)
            self._pipelines.pop(camera_id, None)
            ring_buf = self._ring_buffers.pop(camera_id, None)
            if ring_buf:
                ring_buf.clear()
            self._reconnect_intervals.pop(camera_id, None)
            self._camera_priorities.pop(camera_id, None)
            self._camera_dvrs.pop(camera_id, None)
            self._camera_enabled.pop(camera_id, None)
            self._ai_jobs_in_progress.pop(camera_id, None)
            logger.info(f"CameraManager: Removed Camera ID {camera_id}")

    def stop_all(self) -> None:
        logger.info("CameraManager: Stopping all camera workers and AI pool...")
        camera_ids = list(self._sources.keys())
        for cid in camera_ids:
            self.stop_camera(cid)
        self.dvr_manager.stop_health_monitor()
        self.ai_pool.shutdown()
        logger.info("CameraManager: All camera workers & AI pool stopped.")

    def get_runtime_state(self, camera_id: int) -> Optional[CameraRuntimeState]:
        source = self._sources.get(camera_id)
        return source.get_state() if source else None

    def get_latest_frame(self, camera_id: int) -> Tuple[Optional[np.ndarray], Optional[datetime], int]:
        buffer = self._buffers.get(camera_id)
        return buffer.get_latest() if buffer else (None, None, 0)

    def get_camera_metrics(self, camera_id: int) -> Dict[str, Any]:
        """
        Returns rich per-camera telemetry metrics (capture FPS, AI FPS, dropped frames, queue depth).
        """
        source = self._sources.get(camera_id)
        bqueue = self._bounded_queues.get(camera_id)
        state = source.get_state() if source else None

        pipeline = self._pipelines.get(camera_id)
        active_dets = list(pipeline._latest_detections) if pipeline else []
        active_workers = list(pipeline._latest_worker_analyses) if pipeline else []

        fire_cnt = sum(1 for d in active_dets if "fire" in d.label.lower())
        smoke_cnt = sum(1 for d in active_dets if "smoke" in d.label.lower())
        person_cnt = sum(1 for d in active_dets if d.label.lower() in ["person", "worker"])
        ppe_viol_cnt = sum(1 for w in active_workers if w.get("status") == "VIOLATION")

        return {
            "camera_id": camera_id,
            "status": state.connection_status.value if state else "DISCONNECTED",
            "capture_fps": state.current_fps if state else 0.0,
            "camera_capture_fps": state.current_fps if state else 0.0,
            "ai_fps": self._current_ai_fps.get(camera_id, 0.0),
            "ai_processing_fps": self._current_ai_fps.get(camera_id, 0.0),
            "dropped_frames": bqueue.dropped_frames if bqueue else 0,
            "queue_depth": bqueue.current_size if bqueue else 0,
            "reconnect_count": state.reconnect_attempts if state else 0,
            "fire_detection_count": fire_cnt,
            "smoke_detection_count": smoke_cnt,
            "person_detection_count": person_cnt,
            "ppe_violation_count": ppe_viol_cnt,
            "last_frame_timestamp": state.last_frame_timestamp.isoformat() if (state and state.last_frame_timestamp) else None
        }

    def _camera_ingestion_worker_loop(self, camera_id: int, stop_event: threading.Event) -> None:
        """
        Ingestion Worker Loop (Failure Isolated):
        Reads raw frames from source into BoundedFrameQueue and triggers scheduled AI processing.
        Ingestion failures or frame corrupted stream drops do NOT stop other camera workers.
        """
        source = self._sources.get(camera_id)
        buffer = self._buffers.get(camera_id)
        bqueue = self._bounded_queues.get(camera_id)
        pipeline = self._pipelines.get(camera_id)
        reconnect_interval = self._reconnect_intervals.get(camera_id, 5)

        if not source or not buffer or not bqueue:
            logger.error(f"CameraIngestionWorker-{camera_id}: Required components missing.")
            return

        raw_fps = getattr(source, "fps_limit", 25)
        fps_limit = max(1, int(raw_fps) if raw_fps is not None else 25)
        target_frame_time = 1.0 / fps_limit
        frame_counter: int = 0
        fps_window_start = time.time()
        window_frame_count: int = 0

        # Ensure active safety zones are loaded from DB if not already populated
        if pipeline and not pipeline.active_safety_zones:
            try:
                from app.database.session import SessionLocal as _SL
                from app.models.zone import SafetyZone as _SZ
                with _SL() as _db:
                    db_zones = _db.query(_SZ).filter(_SZ.camera_id == camera_id, _SZ.enabled == True).all()
                    if db_zones:
                        z_dicts = [
                            {
                                "id": z.id,
                                "name": z.name,
                                "zone_type": z.zone_type,
                                "polygon_coordinates": z.polygon_coordinates,
                                "ppe_profile_id": z.ppe_profile_id,
                                "enabled": z.enabled
                            }
                            for z in db_zones
                        ]
                        pipeline.set_safety_zones(z_dicts)
                        logger.info(f"CameraIngestionWorker-{camera_id}: Auto-loaded {len(z_dicts)} safety zones from DB.")
            except Exception as ze:
                logger.warning(f"CameraIngestionWorker-{camera_id}: Could not auto-load safety zones from DB: {ze}")

        while not stop_event.is_set():
            try:
                # Check DVR status if attached to physical DVR
                dvr_id = self._camera_dvrs.get(camera_id)
                if dvr_id:
                    dvr_obj = self.dvr_manager.get_dvr(dvr_id)
                    if dvr_obj and dvr_obj.status in (DVRStatus.OFFLINE.value, DVRStatus.UNREACHABLE.value):
                        source.state.connection_status = CameraStatus.DISCONNECTED
                        self._notify_lifecycle_event("CAMERA_DISCONNECTED", camera_id, CameraStatus.DISCONNECTED, "Attached DVR is OFFLINE")
                        stop_event.wait(timeout=reconnect_interval)
                        continue

                # Reconnect loop
                if not source.is_connected():
                    if stop_event.is_set():
                        break

                    source.state.connection_status = CameraStatus.CONNECTING
                    source.state.reconnect_attempts += 1
                    self._notify_lifecycle_event("CAMERA_CONNECTING", camera_id, CameraStatus.CONNECTING)

                    connected = source.connect()
                    if connected and not stop_event.is_set():
                        self._notify_lifecycle_event("CAMERA_CONNECTED", camera_id, CameraStatus.CONNECTED)
                    else:
                        if stop_event.is_set():
                            break
                        backoff = 1.0 if source.state.reconnect_attempts <= 2 else min(10, reconnect_interval * (2 ** (min(3, source.state.reconnect_attempts - 2))))
                        source.state.connection_status = CameraStatus.RECONNECTING
                        self._notify_lifecycle_event("CAMERA_RECONNECTING", camera_id, CameraStatus.RECONNECTING)
                        stop_event.wait(timeout=backoff)
                        continue

                # Ingest raw frame
                loop_start = time.time()
                success, raw_frame = source.read_frame()

                if success and raw_frame is not None:
                    now = datetime.now(timezone.utc)
                    source.state.last_frame_timestamp = now
                    frame_counter += 1
                    window_frame_count += 1

                    # Update Moving Capture FPS
                    elapsed_window = time.time() - fps_window_start
                    if elapsed_window >= 1.0:
                        source.state.current_fps = round(window_frame_count / elapsed_window, 2)
                        fps_window_start = time.time()
                        window_frame_count = 0

                    # Update latest display buffer with smooth cached overlays for zero-flicker MJPEG streaming
                    display_frame = pipeline.draw_display_overlay(raw_frame, frame_counter, source.state.current_fps, now) if pipeline else raw_frame
                    buffer.update(display_frame)

                    # Push to pre-event ring buffer
                    ring_buf = self._ring_buffers.get(camera_id)
                    if ring_buf:
                        ring_buf.update_fps(source.state.current_fps)
                        ring_buf.add_frame(raw_frame, now)

                    # Feed active incident post-event video recorders
                    if getattr(self, "evidence_service", None):
                        self.evidence_service.push_live_frame(camera_id, raw_frame, now)

                    # Push frame into Bounded Queue
                    bqueue.put_frame(raw_frame, now, frame_counter)

                    # Frame Scheduler check for AI inference dispatch
                    priority = self._camera_priorities.get(camera_id, "HIGH")
                    raw_target_ai_fps = getattr(source, "target_ai_fps", 6)
                    # When on CPU, clamp target_ai_fps to at most 6 (safe real-time throughput with 384px SIMD inference)
                    target_ai_fps = min(6, raw_target_ai_fps) if not self.resource_manager.cuda_available else raw_target_ai_fps

                    if self.frame_scheduler.should_process_frame(frame_counter, priority, fps_limit, target_ai_fps):
                        # Concurrency Gating: Skip submitting if AI inference is already in progress for this camera
                        with self._lock:
                            is_ai_busy = self._ai_jobs_in_progress.get(camera_id, False)

                        if not is_ai_busy:
                            with self._lock:
                                self._ai_jobs_in_progress[camera_id] = True
                            # Dispatch to AI Worker Pool (Isolated submission)
                            submitted = self.ai_pool.submit_job(self._execute_ai_pipeline_task, camera_id, frame_counter, now)
                            if not submitted:
                                with self._lock:
                                    self._ai_jobs_in_progress[camera_id] = False

                else:
                    source.disconnect()
                    self._notify_lifecycle_event("CAMERA_DISCONNECTED", camera_id, CameraStatus.DISCONNECTED)
                    stop_event.wait(timeout=reconnect_interval)
                    continue

                # Frame rate throttling:
                # Live hardware webcams and RTSP streams are already paced by physical hardware/network sockets.
                # Only apply sleep throttling to non-clocked synthetic matrixes or local video file playback
                # to prevent buffer accumulation and video latency lag.
                if getattr(source, "requires_throttling", True):
                    elapsed = time.time() - loop_start
                    sleep_time = target_frame_time - elapsed
                    if sleep_time > 0:
                        stop_event.wait(timeout=sleep_time)

            except Exception as e:
                logger.error(f"CameraIngestionWorker-{camera_id}: Exception caught and isolated: {str(e)}", exc_info=True)
                stop_event.wait(timeout=1.0)

    def _execute_ai_pipeline_task(self, camera_id: int, frame_id: int, timestamp: datetime) -> None:
        """
        Isolated AI Pipeline Task:
        Pulls latest frame from BoundedFrameQueue and executes YOLO AI detection & verification.
        Controlled CUDA OOM Recovery handling included.
        """
        source: Optional[CameraSource] = self._sources.get(camera_id)
        pipeline: Optional[FramePipeline] = self._pipelines.get(camera_id)
        bqueue: Optional[BoundedFrameQueue] = self._bounded_queues.get(camera_id)

        if not bqueue or not pipeline or not source:
            with self._lock:
                self._ai_jobs_in_progress[camera_id] = False
            return

        try:
            raw_frame, ts, fid = bqueue.get_frame(timeout=0.1)
            if raw_frame is None:
                return

            cam_name = getattr(source, "name", f"Camera-{camera_id}")
            try:
                from app.utils.metrics import metrics_collector
                metrics_collector.record_queue_depth(cam_name, bqueue.current_size)
                if ts:
                    frame_age = (datetime.now(timezone.utc) - ts).total_seconds() * 1000.0
                    metrics_collector.record_frame_age(cam_name, frame_age)
            except Exception:
                pass

            current_fps = source.state.current_fps or 15.0
            processed_frame = pipeline.process_frame(
                raw_image=raw_frame,
                frame_id=fid,
                fps=current_fps,
                timestamp=timestamp
            )


            # Update AI FPS Telemetry
            with self._lock:
                self._ai_frame_count[camera_id] = self._ai_frame_count.get(camera_id, 0) + 1
                elapsed = time.time() - self._ai_fps_window_start.get(camera_id, time.time())
                if elapsed >= 1.0:
                    self._current_ai_fps[camera_id] = round(self._ai_frame_count[camera_id] / elapsed, 2)
                    self._ai_fps_window_start[camera_id] = time.time()
                    self._ai_frame_count[camera_id] = 0

            # Persist raw AI detections to database asynchronously via background thread pool (throttled to at most once per 2s per camera to prevent SQLite lock starvation)
            now_epoch = time.time()
            if processed_frame.detections and (now_epoch - self._last_detection_db_save.get(camera_id, 0.0)) >= 2.0:
                self._last_detection_db_save[camera_id] = now_epoch
                def _async_save_detections(dets=list(processed_frame.detections), cid=camera_id, f_num=fid, fps_val=current_fps, ts_val=timestamp):
                    try:
                        from app.database.session import SessionLocal, db_write_lock
                        from app.services.alert_service import AlertService
                        with db_write_lock:
                            db_det = SessionLocal()
                            try:
                                det_svc = AlertService(db_det)
                                det_svc.create_detections_batch(
                                    camera_id=cid,
                                    detections=dets,
                                    frame_number=f_num,
                                    fps=fps_val,
                                    timestamp=ts_val
                                )
                            finally:
                                try:
                                    db_det.close()
                                except Exception:
                                    pass
                    except Exception as det_db_err:
                        logger.warning(f"CameraManager: Async detection DB persistence error: {str(det_db_err)}")

                if not getattr(self.ai_pool, "_shutdown", False):
                    try:
                        self.ai_pool._executor.submit(_async_save_detections)
                    except Exception:
                        pass

            # Check for verified ALERT_SENT event (Dispatched asynchronously to background worker to guarantee 0 inference latency)
            verified_events_data = processed_frame.metadata.get("verified_events", [])
            for evt_dict in verified_events_data:
                if evt_dict.get("state") == "ALERT_SENT":
                    ring_buf = self._ring_buffers.get(camera_id)
                    pre_frames = ring_buf.get_pre_event_frames() if ring_buf else []
                    cam_name = getattr(source, "name", f"Camera-{camera_id}")
                    cam_loc = getattr(source, "location", "Surveillance Zone")
                    lat = getattr(source, "latitude", getattr(settings, "DEFAULT_LATITUDE", 13.0827))
                    lon = getattr(source, "longitude", getattr(settings, "DEFAULT_LONGITUDE", 80.2707))
                    measured_stream_fps = source.state.current_fps or 25.0
                    frame_img_copy = processed_frame.image.copy() if processed_frame.image is not None else None

                    def _async_process_verified_alert(evt_data=evt_dict, cid=camera_id, c_name=cam_name, c_loc=cam_loc, c_lat=lat, c_lon=lon, p_frames=pre_frames, img=frame_img_copy, ts_val=timestamp, cam_fps=measured_stream_fps):
                        try:
                            from app.detection.verification import VerifiedEvent, EventState, BoundingBox
                            bbox_data = evt_data.get("bounding_box")
                            bbox_obj = BoundingBox(**bbox_data) if bbox_data else None
                            evt_obj = VerifiedEvent(
                                event_id=evt_data.get("event_id", ""),
                                camera_id=cid,
                                class_name=evt_data.get("class_name", "alert"),
                                state=EventState.ALERT_SENT,
                                consecutive_frames=evt_data.get("consecutive_frames", 0),
                                duration_seconds=evt_data.get("duration_seconds", 0.0),
                                max_confidence=evt_data.get("max_confidence", 0.0),
                                latest_confidence=evt_data.get("latest_confidence", 0.0),
                                start_time=ts_val,
                                updated_time=ts_val,
                                bounding_box=bbox_obj,
                                frame_info=evt_data.get("frame_info", {}),
                                metadata=dict(evt_data.get("metadata", {}))
                            )

                            # Persist verified alert to database so REST API & Dashboard reflect incidents
                            from app.database.session import SessionLocal, db_write_lock
                            from app.services.alert_service import AlertService
                            with db_write_lock:
                                db = SessionLocal()
                                try:
                                    alert_svc = AlertService(db)
                                    alert_svc.create_alert(
                                        alert_id=evt_obj.event_id,
                                        camera_id=cid,
                                        class_name=evt_obj.class_name,
                                        state="ALERT_SENT",
                                        consecutive_frames=evt_obj.consecutive_frames,
                                        duration_seconds=evt_obj.duration_seconds,
                                        max_confidence=evt_obj.max_confidence,
                                        latest_confidence=evt_obj.latest_confidence,
                                        start_time=evt_obj.start_time
                                    )
                                    if evt_obj.class_name == "ppe_violation":
                                        try:
                                            from app.services.ppe_service import PPEService
                                            ppe_svc = PPEService(db)
                                            meta_evt = evt_data.get("metadata", {})
                                            raw_missing = meta_evt.get("missing_equipment", ["vest"])
                                            clean_missing = [m for m in raw_missing if m.lower() not in ["helmet", "cap", "hard_hat", "headgear"]]
                                            ppe_svc.create_violation(
                                                camera_id=cid,
                                                person_id=meta_evt.get("person_id", 1),
                                                status="VIOLATION",
                                                severity="HIGH",
                                                missing_items=clean_missing or ["vest"],
                                                detected_items=meta_evt.get("detected_equipment", []),
                                                required_items=["vest", "goggles"],
                                                confidence=evt_obj.max_confidence,
                                                timestamp=evt_obj.start_time
                                            )
                                        except Exception as ppe_db_err:
                                            logger.warning(f"CameraManager: PPE DB persistence error: {str(ppe_db_err)}")
                                    elif evt_obj.class_name == "zone_violation":
                                        try:
                                            from app.models.incident import Incident
                                            meta_evt = evt_data.get("metadata", {})
                                            inc = Incident(
                                                camera_id=cid,
                                                zone_id=meta_evt.get("zone_id"),
                                                incident_type="ZONE_VIOLATION",
                                                events=meta_evt.get("events", ["UNAUTHORIZED_AREA_ENTRY"]),
                                                severity=meta_evt.get("severity", "HIGH"),
                                                status="ACTIVE",
                                                person_id=meta_evt.get("person_id"),
                                                start_time=evt_obj.start_time
                                            )
                                            db.add(inc)
                                            db.commit()
                                        except Exception as z_db_err:
                                            logger.warning(f"CameraManager: Zone violation incident persistence error: {str(z_db_err)}")
                                finally:
                                    try:
                                        db.close()
                                    except Exception:
                                        pass

                            # Save incident evidence files (snapshot + video clip)
                            rec = None
                            if img is not None:
                                rec = self.evidence_service.save_incident_evidence(
                                    event=evt_obj,
                                    annotated_frame=img,
                                    pre_event_frames=p_frames,
                                    camera_name=c_name,
                                    fps=cam_fps,
                                    record_post_event=True
                                )
                            if rec:
                                evt_obj.metadata["evidence_id"] = rec.evidence_id
                                try:
                                    db_ev = SessionLocal()
                                    try:
                                        ev_svc = AlertService(db_ev)
                                        ev_svc.create_evidence_record(
                                            evidence_id=rec.evidence_id,
                                            alert_id=evt_obj.event_id,
                                            camera_id=cid,
                                            snapshot_relative_path=rec.snapshot_relative_path,
                                            video_relative_path=rec.video_relative_path,
                                            metadata_relative_path=rec.metadata_relative_path,
                                            file_size_bytes=rec.file_size_bytes,
                                            metadata_envelope=rec.metadata
                                        )
                                    finally:
                                        try:
                                            db_ev.close()
                                        except Exception:
                                            pass
                                except Exception as db_ev_err:
                                    logger.warning(f"CameraManager: Failed to persist evidence DB record: {str(db_ev_err)}")

                            # Dispatch email and notification alerts asynchronously
                            snap_path = self.evidence_service.get_physical_snapshot_path(rec.evidence_id) if rec else None
                            self.alert_manager.process_verified_event_async(
                                event=evt_obj,
                                snapshot_path=snap_path,
                                camera_name=c_name,
                                location=c_loc,
                                latitude=c_lat,
                                longitude=c_lon
                            )

                            # Broadcast live WebSocket event to connected frontend clients
                            if self.event_callback:
                                try:
                                    event_name = f"VERIFIED_{evt_obj.class_name.upper()}"
                                    self.event_callback(event_name, evt_obj.to_dict())
                                except Exception as cb_err:
                                    logger.warning(f"CameraManager: Failed to execute event callback: {str(cb_err)}")

                        except Exception as async_alert_err:
                            logger.error(f"CameraManager: Exception in async alert worker: {str(async_alert_err)}")

                    if not getattr(self.ai_pool, "_shutdown", False):
                        try:
                            self.ai_pool._executor.submit(_async_process_verified_alert)
                        except Exception:
                            _async_process_verified_alert()
        except RuntimeError as cuda_err:
            if "out of memory" in str(cuda_err).lower():
                target_gpu = getattr(source, "gpu_device_id", 0) if source else 0
                new_device = self.resource_manager.handle_cuda_oom(target_gpu)
                logger.warning(f"Camera-{camera_id}: Controlled CUDA OOM recovery triggered. Switched device to '{new_device}'.")
                if pipeline:
                    pipeline.detector = YOLODetector(device=new_device)
            else:
                logger.error(f"Camera-{camera_id}: AI task error: {str(cuda_err)}")
        except Exception as e:
            logger.error(f"Camera-{camera_id}: AI task exception isolated: {str(e)}")
        finally:
            with self._lock:
                self._ai_jobs_in_progress[camera_id] = False
