"""
Incident Evidence Management & Video Archiving Subsystem.
Preserves JPEG snapshot evidence, MP4 video clips, and JSON metadata envelopes upon verified alert events.
Implements secure evidence token abstraction hiding physical OS paths from API clients.
"""

import os
import glob
import json
import uuid
import time
import shutil
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
import cv2
import numpy as np

from app.config.settings import settings
from app.detection.base import BoundingBox
from app.detection.verification import VerifiedEvent
from app.utils.logger import logger


@dataclass
class EvidenceRecord:
    """
    Structured Evidence Record object.
    Exposes secure evidence token URLs instead of raw OS filesystem paths.
    """
    evidence_id: str
    event_id: str
    camera_id: int
    camera_name: str
    class_name: str  # "fire", "smoke"
    confidence: float
    timestamp: datetime
    snapshot_relative_path: str
    video_relative_path: Optional[str] = None
    metadata_relative_path: Optional[str] = None
    snapshot_url: str = ""
    video_url: Optional[str] = None
    file_size_bytes: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "event_id": self.event_id,
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "class_name": self.class_name,
            "confidence": round(self.confidence, 4),
            "timestamp": self.timestamp.isoformat(),
            "snapshot_url": self.snapshot_url,
            "video_url": self.video_url,
            "file_size_bytes": self.file_size_bytes,
            "metadata": self.metadata
        }


class IncidentRecordingSession:
    """
    Asynchronous incident recording session that collects live post-event frames from camera ingestion
    and updates the evidence video file into a complete pre-event + detection + post-event clip.
    """
    def __init__(
        self,
        evidence_id: str,
        camera_id: int,
        video_path: str,
        pre_event_frames: List[Tuple[np.ndarray, datetime]],
        annotated_frame: np.ndarray,
        fps: float = 25.0,
        post_duration_seconds: float = 10.0,
        on_complete: Optional[Any] = None
    ):
        self.evidence_id = evidence_id
        self.camera_id = camera_id
        self.video_path = video_path
        self.pre_event_frames = pre_event_frames
        self.annotated_frame = annotated_frame
        self.fps = min(30.0, max(10.0, float(fps) if fps and fps > 0 else 25.0))
        self.post_duration_seconds = post_duration_seconds
        self.target_post_frames = max(1, int(self.post_duration_seconds * self.fps))
        self.on_complete = on_complete

        self._post_frames: List[np.ndarray] = []
        self._lock = threading.Lock()
        self._start_time = time.time()
        self._is_completed = False
        self.watchdog: Optional[threading.Timer] = None
        self.finished_event = threading.Event()

    def push_frame(self, frame: np.ndarray) -> bool:
        """Pushes a live frame. Returns True if session is still collecting, False if finished."""
        if self._is_completed:
            return False

        with self._lock:
            if self._is_completed:
                return False
            self._post_frames.append(frame.copy())
            if len(self._post_frames) >= self.target_post_frames or (time.time() - self._start_time) >= (self.post_duration_seconds + 1.5):
                self._is_completed = True
                return False
            return True

    def finalize(self, service: "EvidenceService") -> bool:
        """Compiles and writes the final complete video clip."""
        if self.watchdog:
            try:
                self.watchdog.cancel()
            except Exception:
                pass

        with self._lock:
            self._is_completed = True
            post_snapshot = list(self._post_frames)

        try:
            success = service._write_video_clip(
                video_path=self.video_path,
                pre_event_frames=self.pre_event_frames,
                current_frame=self.annotated_frame,
                fps=self.fps,
                post_event_frames=post_snapshot
            )
        finally:
            self.finished_event.set()

        if self.on_complete:
            try:
                self.on_complete(self.evidence_id, self.video_path, success)
            except Exception as cb_err:
                logger.warning(f"IncidentRecordingSession callback error: {cb_err}")
        return success


class EvidenceService:
    """
    Service managing incident evidence storage, pre/post event video clip generation,
    secure token lookup, and automated retention cleanup.
    """

    def __init__(self, base_storage_dir: Optional[str] = None):
        self.base_storage_dir = base_storage_dir or settings.EVIDENCE_STORAGE_DIR
        self._registry: Dict[str, EvidenceRecord] = {}
        self._physical_paths: Dict[str, Dict[str, str]] = {}
        self._active_sessions: Dict[int, List[IncidentRecordingSession]] = {}
        self._lock = threading.Lock()
        
        # Ensure base directory exists
        os.makedirs(self.base_storage_dir, exist_ok=True)

    def _get_organized_directory(self, camera_id: int, date_dt: datetime) -> str:
        """
        Organizes evidence directory by camera and date:
        evidence/CAM-01/2026-08-18/
        """
        cam_str = f"CAM-{camera_id:02d}"
        date_str = date_dt.strftime("%Y-%m-%d")
        full_dir = os.path.join(self.base_storage_dir, cam_str, date_str)
        os.makedirs(full_dir, exist_ok=True)
        return full_dir

    def push_live_frame(self, camera_id: int, frame: np.ndarray, timestamp: Optional[datetime] = None) -> None:
        """
        Feeds live frame into any active incident recording sessions for camera_id.
        """
        if frame is None or frame.size == 0:
            return

        with self._lock:
            sessions = list(self._active_sessions.get(camera_id, []))

        if not sessions:
            return

        to_finalize = []
        for sess in sessions:
            still_active = sess.push_frame(frame)
            if not still_active:
                to_finalize.append(sess)

        if to_finalize:
            with self._lock:
                current_list = self._active_sessions.get(camera_id, [])
                for r in to_finalize:
                    if r in current_list:
                        current_list.remove(r)
                if not current_list:
                    self._active_sessions.pop(camera_id, None)

            for sess in to_finalize:
                threading.Thread(target=sess.finalize, args=[self], daemon=True).start()

    def _finalize_session_safe(self, session: IncidentRecordingSession) -> None:
        """Safety timer callback: finalizes session if still active after timeout."""
        with self._lock:
            sessions = self._active_sessions.get(session.camera_id, [])
            if session in sessions:
                sessions.remove(session)
            if not sessions:
                self._active_sessions.pop(session.camera_id, None)

        if not session._is_completed:
            session.finalize(self)

    def _on_session_complete(self, evidence_id: str, video_path: str, success: bool) -> None:
        """Invoked when a post-event recording session finishes compiling the video."""
        if not success or not os.path.exists(video_path):
            return
        video_size = os.path.getsize(video_path)
        with self._lock:
            record = self._registry.get(evidence_id)
            if record:
                record.video_url = f"/api/v1/evidence/{evidence_id}/video"
                record.file_size_bytes = max(record.file_size_bytes, video_size)
            if evidence_id in self._physical_paths:
                self._physical_paths[evidence_id]["video"] = video_path

        # Update database record asynchronously with db_write_lock
        def _async_db_update():
            try:
                from app.database.session import SessionLocal, db_write_lock
                from app.models.evidence import Evidence
                with db_write_lock:
                    db = SessionLocal()
                    try:
                        ev_db = db.query(Evidence).filter(Evidence.evidence_id == evidence_id).first()
                        if ev_db:
                            ev_db.video_relative_path = os.path.relpath(video_path, self.base_storage_dir)
                            ev_db.file_size_bytes = video_size
                            db.commit()
                    finally:
                        try:
                            db.close()
                        except Exception:
                            pass
            except Exception as db_err:
                logger.warning(f"EvidenceService: Error updating DB video path for {evidence_id}: {db_err}")

        threading.Thread(target=_async_db_update, daemon=True).start()

    def save_incident_evidence(
        self,
        event: VerifiedEvent,
        annotated_frame: np.ndarray,
        pre_event_frames: Optional[List[Tuple[np.ndarray, datetime]]] = None,
        camera_name: str = "CCTV Camera",
        fps: Optional[float] = None,
        record_post_event: bool = False,
        post_duration_seconds: Optional[float] = None
    ) -> Optional[EvidenceRecord]:
        """
        Preserves JPEG snapshot evidence, metadata envelope, and MP4/WebM video clip.
        Returns EvidenceRecord with secure token URLs.
        """
        if annotated_frame is None or annotated_frame.size == 0:
            logger.warning(f"EvidenceService: Cannot save evidence for Camera {event.camera_id}: Empty image.")
            return None

        try:
            now_dt = datetime.now().astimezone()
            date_dir = self._get_organized_directory(event.camera_id, now_dt)

            # Generate collision-free unique filenames
            time_str = now_dt.strftime("%H%M%S")
            uuid_short = uuid.uuid4().hex[:8]
            base_filename = f"{event.class_name.lower()}_{time_str}_{uuid_short}"

            snapshot_path = os.path.join(date_dir, f"{base_filename}.jpg")
            video_path = os.path.join(date_dir, f"{base_filename}.mp4")
            metadata_path = os.path.join(date_dir, f"{base_filename}.json")

            # 1. Save JPEG Snapshot with high quality
            jpeg_quality = [cv2.IMWRITE_JPEG_QUALITY, getattr(settings, "EVIDENCE_JPEG_QUALITY", 90)]
            cv2.imwrite(snapshot_path, annotated_frame, jpeg_quality)
            snapshot_size = os.path.getsize(snapshot_path) if os.path.exists(snapshot_path) else 0

            # Determine real stream frame rate
            clip_fps = float(fps) if fps else float(event.frame_info.get("fps", 25.0) if event.frame_info else 25.0)
            clip_fps = min(30.0, max(10.0, clip_fps))

            # 2. Write initial MP4/WebM Video Clip (Pre-Event + Current Frame) at accurate stream FPS
            has_video = self._write_video_clip(video_path, pre_event_frames or [], annotated_frame, fps=clip_fps)

            # 3. Create Secure Token Identifiers
            evidence_id = f"ev_{uuid.uuid4().hex[:12]}"
            snapshot_url = f"/api/v1/evidence/{evidence_id}/snapshot"
            video_url = f"/api/v1/evidence/{evidence_id}/video" if has_video else None

            # 4. Save JSON Metadata Envelope
            meta_dict = {
                "evidence_id": evidence_id,
                "event_id": event.event_id,
                "camera_id": event.camera_id,
                "camera_name": camera_name,
                "class_name": event.class_name,
                "confidence": event.max_confidence,
                "timestamp": event.start_time.isoformat(),
                "bounding_box": event.bounding_box.to_dict() if event.bounding_box else None,
                "frame_info": event.frame_info,
                "snapshot_file": os.path.basename(snapshot_path),
                "video_file": os.path.basename(video_path) if has_video else None
            }
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(meta_dict, f, indent=2)

            record = EvidenceRecord(
                evidence_id=evidence_id,
                event_id=event.event_id,
                camera_id=event.camera_id,
                camera_name=camera_name,
                class_name=event.class_name,
                confidence=event.max_confidence,
                timestamp=event.start_time,
                snapshot_relative_path=os.path.relpath(snapshot_path, self.base_storage_dir),
                video_relative_path=os.path.relpath(video_path, self.base_storage_dir) if has_video else None,
                metadata_relative_path=os.path.relpath(metadata_path, self.base_storage_dir),
                snapshot_url=snapshot_url,
                video_url=video_url,
                file_size_bytes=snapshot_size,
                metadata=meta_dict
            )

            # Store in token lookup registry
            with self._lock:
                self._registry[evidence_id] = record
                self._physical_paths[evidence_id] = {
                    "snapshot": snapshot_path,
                    "video": video_path if has_video else "",
                    "metadata": metadata_path
                }

            # 5. Launch active post-event recording session if enabled
            if record_post_event and has_video:
                post_dur = post_duration_seconds if post_duration_seconds is not None else getattr(settings, "POST_EVENT_BUFFER_SECONDS", 10.0)
                session = IncidentRecordingSession(
                    evidence_id=evidence_id,
                    camera_id=event.camera_id,
                    video_path=video_path,
                    pre_event_frames=pre_event_frames or [],
                    annotated_frame=annotated_frame,
                    fps=clip_fps,
                    post_duration_seconds=post_dur,
                    on_complete=self._on_session_complete
                )
                with self._lock:
                    if event.camera_id not in self._active_sessions:
                        self._active_sessions[event.camera_id] = []
                    self._active_sessions[event.camera_id].append(session)

                # Safety watchdog timer to finalize video even if camera stops
                watchdog = threading.Timer(post_dur + 3.0, self._finalize_session_safe, args=[session])
                watchdog.daemon = True
                session.watchdog = watchdog
                watchdog.start()

            logger.info(
                f"EvidenceService: Archived Evidence {evidence_id} for Camera {event.camera_id} "
                f"[{event.class_name.upper()} conf={round(event.max_confidence, 2)}] -> Snapshot: '{snapshot_path}'"
            )
            return record

        except Exception as e:
            logger.error(f"EvidenceService: Error saving incident evidence for Camera {event.camera_id}: {str(e)}")
            return None

    def _write_video_clip(
        self,
        video_path: str,
        pre_event_frames: List[Tuple[np.ndarray, datetime]],
        current_frame: np.ndarray,
        fps: float = 25.0,
        post_event_frames: Optional[List[Any]] = None
    ) -> bool:
        """
        Compiles pre-event rolling buffer frames, detection frame, and post-event frames into an HTML5 WebM/MP4 video clip.
        """
        try:
            h, w = current_frame.shape[:2]
            base_dir = os.path.dirname(video_path)
            base_name = os.path.splitext(os.path.basename(video_path))[0]

            clip_fps = float(fps) if fps and fps > 0 else 25.0
            clip_fps = min(30.0, max(10.0, clip_fps))

            webm_path = os.path.join(base_dir, f"{base_name}.webm")
            writer = None
            target_path = webm_path

            # Primary codec: VP80 WebM for 100% native HTML5 browser playback
            try:
                fourcc_vp8 = cv2.VideoWriter.fourcc(*"VP80")
                w_test = cv2.VideoWriter(webm_path, fourcc_vp8, clip_fps, (w, h))
                if w_test.isOpened():
                    writer = w_test
                    target_path = webm_path
            except Exception:
                pass

            if not writer or not writer.isOpened():
                try:
                    fourcc_vp9 = cv2.VideoWriter.fourcc(*"VP90")
                    w_vp9 = cv2.VideoWriter(webm_path, fourcc_vp9, clip_fps, (w, h))
                    if w_vp9.isOpened():
                        writer = w_vp9
                        target_path = webm_path
                except Exception:
                    pass

            if not writer or not writer.isOpened():
                try:
                    fourcc_mp4 = cv2.VideoWriter.fourcc(*"mp4v")
                    w_mp4 = cv2.VideoWriter(video_path, fourcc_mp4, clip_fps, (w, h))
                    if w_mp4.isOpened():
                        writer = w_mp4
                        target_path = video_path
                except Exception:
                    pass

            if not writer or not writer.isOpened():
                return False

            # 1. Write pre-event frames if available
            if pre_event_frames:
                for item in pre_event_frames:
                    img = item[0] if isinstance(item, (tuple, list)) else item
                    if img is not None and img.size > 0:
                        if img.shape[:2] == (h, w):
                            writer.write(img)
                        else:
                            writer.write(cv2.resize(img, (w, h)))

            # 2. Write detection frame (2 frames if post-event video follows, otherwise 1 second)
            annotated_repeats = 2 if post_event_frames else max(1, int(clip_fps * 1.0))
            for _ in range(annotated_repeats):
                writer.write(current_frame)

            # 3. Write live post-event frames if available
            if post_event_frames:
                for item in post_event_frames:
                    img = item[0] if isinstance(item, (tuple, list)) else item
                    if img is not None and img.size > 0:
                        if img.shape[:2] == (h, w):
                            writer.write(img)
                        else:
                            writer.write(cv2.resize(img, (w, h)))

            writer.release()

            # Ensure file exists at requested video_path as well for backwards compatibility
            if target_path != video_path and os.path.exists(target_path):
                try:
                    shutil.copy2(target_path, video_path)
                except Exception:
                    pass

            return os.path.exists(target_path) and os.path.getsize(target_path) > 0

        except Exception as e:
            logger.warning(f"EvidenceService: Failed writing video clip '{video_path}': {str(e)}")
            return False

    def _ensure_webm_clip(self, raw_path: str) -> str:
        """
        Ensures an HTML5-compatible WebM VP8/VP9 video clip exists on disk for browser playback.
        """
        if not raw_path or not os.path.exists(raw_path):
            return raw_path

        ext = os.path.splitext(raw_path)[1].lower()
        if ext == ".webm":
            return raw_path

        base_no_ext = os.path.splitext(raw_path)[0]
        webm_path = base_no_ext + ".webm"

        if os.path.exists(webm_path) and os.path.getsize(webm_path) > 0:
            return webm_path

        try:
            cap = cv2.VideoCapture(raw_path)
            if not cap.isOpened():
                return raw_path

            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS) or 15.0

            if w <= 0 or h <= 0:
                cap.release()
                return raw_path

            fourcc = cv2.VideoWriter.fourcc(*"VP80")
            writer = cv2.VideoWriter(webm_path, fourcc, fps, (w, h))

            if not writer.isOpened():
                cap.release()
                return raw_path

            while cap.isOpened():
                ret, frame = cap.read()
                if not ret or frame is None:
                    break
                writer.write(frame)

            cap.release()
            writer.release()

            if os.path.exists(webm_path) and os.path.getsize(webm_path) > 0:
                logger.info(f"EvidenceService: Auto-converted '{raw_path}' -> '{webm_path}' for HTML5 browser compatibility.")
                return webm_path
        except Exception as err:
            logger.warning(f"EvidenceService: WebM auto-conversion notice for '{raw_path}': {str(err)}")

        return raw_path

    def get_evidence_record(self, evidence_id: str) -> Optional[EvidenceRecord]:
        """
        Retrieves evidence record by secure token ID.
        """
        with self._lock:
            return self._registry.get(evidence_id)

    def get_physical_snapshot_path(self, evidence_id: str) -> Optional[str]:
        """
        Resolves secure evidence token ID to physical snapshot image path.
        """
        with self._lock:
            paths = self._physical_paths.get(evidence_id)
            if paths and os.path.exists(paths.get("snapshot", "")):
                return paths["snapshot"]
            return None

    def get_physical_video_path(self, evidence_id: str) -> Optional[str]:
        """
        Resolves secure evidence token ID to physical HTML5 video clip path.
        """
        with self._lock:
            paths = self._physical_paths.get(evidence_id)
            if paths:
                raw_path = paths.get("video", "")
                if raw_path and os.path.exists(raw_path):
                    return self._ensure_webm_clip(raw_path)
            return None

    def purge_expired_evidence(self, retention_days: Optional[int] = None, db: Optional[Any] = None) -> int:
        """
        Deletes evidence files older than retention policy (default 24 hours / 1 day) from disk and DB.
        Returns total number of purged evidence files.
        """
        days = retention_days if retention_days is not None else getattr(settings, "EVIDENCE_RETENTION_DAYS", 1)
        cutoff_sec = time.time() - (days * 86400)
        purged_count = 0

        logger.debug(f"EvidenceService: Starting retention purge scan (Deleting evidence older than {days} day(s) / 24 hours)...")

        try:
            # Recursively scan all files in base storage directory (bottom-up to allow directory cleanup)
            for root, dirs, files in os.walk(self.base_storage_dir, topdown=False):
                for file_name in files:
                    file_path = os.path.join(root, file_name)
                    try:
                        if os.path.isfile(file_path):
                            mtime = os.path.getmtime(file_path)
                            if mtime < cutoff_sec:
                                os.remove(file_path)
                                purged_count += 1
                    except Exception as e:
                        logger.warning(f"EvidenceService: Could not delete expired file '{file_path}': {str(e)}")

                # Remove empty subdirectories
                if root != self.base_storage_dir:
                    try:
                        if not os.listdir(root):
                            os.rmdir(root)
                    except Exception:
                        pass

            if db:
                try:
                    from app.models.evidence import Evidence
                    from datetime import timedelta
                    cutoff_dt = datetime.now(timezone.utc) - timedelta(days=days)
                    db.query(Evidence).filter(Evidence.created_at < cutoff_dt).delete(synchronize_session=False)
                    db.commit()
                except Exception as db_err:
                    logger.warning(f"EvidenceService: DB retention purge warning: {str(db_err)}")

            if purged_count > 0:
                logger.info(f"EvidenceService: Retention purge scan completed. Purged {purged_count} expired evidence file(s).")
            else:
                logger.debug(f"EvidenceService: Retention purge scan completed. Purged 0 expired evidence file(s).")
            return purged_count

        except Exception as e:
            logger.error(f"EvidenceService: Retention purge failed: {str(e)}")
            return 0

    def purge_all_evidence(self, db: Optional[Any] = None) -> int:
        """
        Purges ALL evidence files, video clips, JPEG snapshots, and metadata JSON files from disk and DB.
        Returns total number of purged evidence files.
        """
        purged_count = 0
        with self._lock:
            self._registry.clear()
            self._physical_paths.clear()

        try:
            if os.path.exists(self.base_storage_dir):
                for root, dirs, files in os.walk(self.base_storage_dir, topdown=False):
                    for file_name in files:
                        file_path = os.path.join(root, file_name)
                        try:
                            if os.path.isfile(file_path):
                                try:
                                    os.remove(file_path)
                                except PermissionError:
                                    import gc
                                    gc.collect()
                                    time.sleep(0.05)
                                    try:
                                        os.remove(file_path)
                                    except Exception:
                                        pass
                                purged_count += 1
                        except Exception as e:
                            logger.warning(f"EvidenceService: Could not delete file '{file_path}': {str(e)}")

                    if root != self.base_storage_dir:
                        try:
                            if not os.listdir(root):
                                os.rmdir(root)
                        except Exception:
                            pass

            if db:
                try:
                    from app.models.evidence import Evidence
                    db.query(Evidence).delete(synchronize_session=False)
                    db.commit()
                except Exception as db_err:
                    logger.warning(f"EvidenceService: DB purge all warning: {str(db_err)}")

            logger.info(f"EvidenceService: Purged ALL evidence gallery ({purged_count} file(s) deleted).")
            return purged_count

        except Exception as e:
            logger.error(f"EvidenceService: Purge all evidence failed: {str(e)}")
            return 0

    def purge_evidence_item(self, evidence_id: str, db: Optional[Any] = None) -> bool:
        """
        Purges a single evidence record and its associated physical snapshot, video,
        and JSON metadata files from disk storage and database.
        """
        with self._lock:
            self._registry.pop(evidence_id, None)
            self._physical_paths.pop(evidence_id, None)

        purged_files = 0
        try:
            if os.path.exists(self.base_storage_dir):
                for root, dirs, files in os.walk(self.base_storage_dir, topdown=False):
                    for f in files:
                        if evidence_id in f:
                            file_path = os.path.join(root, f)
                            try:
                                if os.path.isfile(file_path):
                                    os.remove(file_path)
                                    purged_files += 1
                            except Exception as e:
                                logger.warning(f"EvidenceService: Could not delete evidence file '{file_path}': {str(e)}")

                    if root != self.base_storage_dir:
                        try:
                            if not os.listdir(root):
                                os.rmdir(root)
                        except Exception:
                            pass

            if db:
                from app.models.evidence import Evidence
                ev = db.query(Evidence).filter(Evidence.evidence_id == evidence_id).first()
                if ev:
                    db.delete(ev)
                    db.commit()

            logger.info(f"EvidenceService: Purged evidence '{evidence_id}' ({purged_files} file(s) removed).")
            return True
        except Exception as e:
            logger.error(f"EvidenceService: Error purging evidence '{evidence_id}': {str(e)}")
            return False

    def sync_disk_evidence_to_db(self, db) -> int:
        """
        Scans base storage directory for valid unexpired incident metadata envelopes (.json)
        and syncs any missing evidence records & alert stubs into the database.
        """
        try:
            from app.models.camera import Camera
            from app.models.alert import Alert
            from app.models.evidence import Evidence

            days = getattr(settings, "EVIDENCE_RETENTION_DAYS", 1)
            cutoff_sec = time.time() - (days * 86400)

            existing_cam_ids = {c[0] for c in db.query(Camera.id).all()}
            default_cam_id = next(iter(existing_cam_ids)) if existing_cam_ids else None

            existing_alert_ids = {a[0] for a in db.query(Alert.id).all()}
            existing_ev_ids = {e[0] for e in db.query(Evidence.evidence_id).all()}

            synced_count = 0
            for root, dirs, files in os.walk(self.base_storage_dir):
                for f in files:
                    if f.endswith(".json"):
                        jf_path = os.path.join(root, f)
                        # Skip and remove expired files older than 24 hours
                        if os.path.getmtime(jf_path) < cutoff_sec:
                            try:
                                os.remove(jf_path)
                            except Exception:
                                pass
                            continue

                        try:
                            with open(jf_path, "r", encoding="utf-8") as fp:
                                meta = json.load(fp)
                            ev_id = meta.get("evidence_id")
                            if not ev_id or ev_id in existing_ev_ids:
                                continue

                            event_id = meta.get("event_id") or f"evt_{uuid.uuid4().hex[:8]}"
                            cam_id = meta.get("camera_id", 1)
                            cls_name = meta.get("class_name", "fire")
                            conf = meta.get("confidence", 0.9)
                            mod_type = meta.get("module") or ("SAFETY_ANALYSIS" if any(k in cls_name.lower() for k in ["ppe", "person", "mask", "vest", "helmet", "cap", "goggle", "glove", "boot"]) else "FIRE_SMOKE")

                            ts_str = meta.get("timestamp")
                            try:
                                dt = datetime.fromisoformat(ts_str) if ts_str else datetime.now(timezone.utc)
                            except Exception:
                                dt = datetime.now(timezone.utc)

                            if cam_id not in existing_cam_ids:
                                if default_cam_id is not None:
                                    cam_id = default_cam_id
                                else:
                                    continue

                            if event_id not in existing_alert_ids:
                                existing_alert = db.query(Alert.id).filter(Alert.id == event_id).first()
                                if existing_alert:
                                    existing_alert_ids.add(event_id)
                                else:
                                    try:
                                        with db.begin_nested():
                                            new_alert = Alert(
                                                id=event_id,
                                                camera_id=cam_id,
                                                module=mod_type,
                                                class_name=cls_name,
                                                state="ALERT_SENT",
                                                consecutive_frames=5,
                                                duration_seconds=5.0,
                                                max_confidence=conf,
                                                latest_confidence=conf,
                                                start_time=dt,
                                                created_at=dt,
                                                updated_at=dt
                                            )
                                            db.add(new_alert)
                                            db.flush()
                                        existing_alert_ids.add(event_id)
                                    except Exception as alert_err:
                                        logger.warning(f"EvidenceService: Could not create stub alert '{event_id}': {str(alert_err)}")

                            if event_id in existing_alert_ids:
                                snap_fn = meta.get("snapshot_file")
                                base_fn = os.path.splitext(f)[0]
                                possible_webm = os.path.join(root, base_fn + ".webm")
                                possible_mp4 = os.path.join(root, base_fn + ".mp4")

                                vid_fn = None
                                if os.path.exists(possible_webm):
                                    vid_fn = base_fn + ".webm"
                                elif os.path.exists(possible_mp4):
                                    vid_fn = base_fn + ".mp4"

                                snap_path = os.path.join(root, snap_fn) if snap_fn else ""
                                vid_path = os.path.join(root, vid_fn) if vid_fn else ""

                                snap_rel = os.path.relpath(snap_path, self.base_storage_dir) if os.path.exists(snap_path) else ""
                                vid_rel = os.path.relpath(vid_path, self.base_storage_dir) if os.path.exists(vid_path) else None
                                size = os.path.getsize(snap_path) if os.path.exists(snap_path) else 0

                                existing_ev = db.query(Evidence.id).filter(Evidence.evidence_id == ev_id).first()
                                if not existing_ev:
                                    try:
                                        with db.begin_nested():
                                            new_ev = Evidence(
                                                id=str(uuid.uuid4()),
                                                evidence_id=ev_id,
                                                alert_id=event_id,
                                                camera_id=cam_id,
                                                snapshot_relative_path=snap_rel,
                                                video_relative_path=vid_rel,
                                                file_size_bytes=size,
                                                metadata_envelope=meta,
                                                created_at=dt
                                            )
                                            db.add(new_ev)
                                            db.flush()
                                            synced_count += 1
                                            existing_ev_ids.add(ev_id)
                                    except Exception as e:
                                        logger.warning(f"EvidenceService: Savepoint failed syncing evidence '{ev_id}': {str(e)}")
                                else:
                                    existing_ev_ids.add(ev_id)

                        except Exception as e:
                            logger.warning(f"EvidenceService: Error processing disk envelope '{jf_path}': {str(e)}")

            if synced_count > 0:
                db.commit()
                logger.info(f"EvidenceService: Auto-synced {synced_count} disk evidence envelope(s) into database.")
            return synced_count

        except Exception as e:
            logger.error(f"EvidenceService: Error syncing disk evidence to DB: {str(e)}")
            return 0
