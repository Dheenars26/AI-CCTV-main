"""
Temporal Verification & False-Alarm Reduction Subsystem.
Implements a state machine (NORMAL -> POSSIBLE -> CONFIRMED -> ALERT_SENT -> ACTIVE -> CLEARED)
to eliminate single-frame transient false alarms and suppress duplicate alerts.
Independent per camera and per target class ('fire', 'smoke').
"""

import uuid
import time
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any, Callable

from app.config.settings import settings
from app.detection.base import BoundingBox, DetectionResult
from app.utils.logger import logger


class EventState(str, Enum):
    """
    Finite State Machine states for Temporal Alert Verification.
    """
    NORMAL = "NORMAL"         # No detection present
    POSSIBLE = "POSSIBLE"     # Spurious/Transient detection (1 to N-1 frames)
    CONFIRMED = "CONFIRMED"   # Verified consecutive threshold reached
    ALERT_SENT = "ALERT_SENT" # Initial alert payload generated & sent
    ACTIVE = "ACTIVE"         # Continuous ongoing active event
    CLEARED = "CLEARED"       # Event ended and returned to normal


@dataclass
class VerifiedEvent:
    """
    Structured Verified Event Output Object.
    Consumed by WebSocket broadcaster, Database logger, Evidence recorder, and Email notification systems.
    """
    event_id: str
    camera_id: int
    class_name: str  # "fire", "smoke"
    state: EventState
    consecutive_frames: int
    duration_seconds: float
    max_confidence: float
    latest_confidence: float
    start_time: datetime
    updated_time: datetime
    bounding_box: Optional[BoundingBox] = None
    frame_info: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.event_id,
            "alert_id": self.event_id,
            "event_id": self.event_id,
            "camera_id": self.camera_id,
            "class_name": self.class_name,
            "state": self.state.value,
            "consecutive_frames": self.consecutive_frames,
            "duration_seconds": round(self.duration_seconds, 2),
            "max_confidence": round(self.max_confidence, 4),
            "latest_confidence": round(self.latest_confidence, 4),
            "start_time": self.start_time.isoformat(),
            "updated_time": self.updated_time.isoformat(),
            "bounding_box": self.bounding_box.to_dict() if self.bounding_box else None,
            "frame_info": self.frame_info,
            "metadata": self.metadata
        }


class ClassVerificationTracker:
    """
    State machine tracking a single detection class ('fire' or 'smoke') for one camera.
    """

    def __init__(
        self,
        camera_id: int,
        class_name: str,
        min_confidence: Optional[float] = None,
        min_consecutive_frames: Optional[int] = None,
        min_duration_seconds: Optional[float] = None,
        cooldown_seconds: Optional[float] = None,
        cleared_miss_tolerance: int = 2
    ):
        self.camera_id = camera_id
        self.class_name = class_name
        cls_lower = class_name.lower()
        # Per-frame floor: a *candidate* floor, not an alert gate. Confirming an alert additionally
        # requires ``alert_min_confidence`` plus the persistence window below, so detection stays
        # sensitive while the alert channel stays trustworthy.
        if cls_lower == "fire":
            self.min_confidence = min_confidence if min_confidence is not None else getattr(
                settings, "FIRE_VERIFICATION_MIN_CONFIDENCE", getattr(settings, "FIRE_CONFIDENCE_THRESHOLD", 0.50)
            )
            self.alert_min_confidence = max(
                self.min_confidence,
                getattr(settings, "FIRE_ALERT_CONFIDENCE", getattr(settings, "FIRE_CONFIDENCE_THRESHOLD", 0.50)),
            )
            self.min_consecutive_frames = min_consecutive_frames if min_consecutive_frames is not None else getattr(settings, "FIRE_MIN_CONSECUTIVE_FRAMES", 6)
            self.min_duration_seconds = min_duration_seconds if min_duration_seconds is not None else getattr(settings, "FIRE_MIN_DURATION_SECONDS", 1.2)
            self.cooldown_seconds = cooldown_seconds if cooldown_seconds is not None else getattr(settings, "VERIFICATION_COOLDOWN_SECONDS", 30.0)
        elif cls_lower == "smoke":
            self.min_confidence = min_confidence if min_confidence is not None else getattr(
                settings, "SMOKE_VERIFICATION_MIN_CONFIDENCE", getattr(settings, "SMOKE_CONFIDENCE_THRESHOLD", 0.48)
            )
            self.alert_min_confidence = max(
                self.min_confidence,
                getattr(settings, "SMOKE_ALERT_CONFIDENCE", getattr(settings, "SMOKE_CONFIDENCE_THRESHOLD", 0.48)),
            )
            self.min_consecutive_frames = min_consecutive_frames if min_consecutive_frames is not None else getattr(settings, "SMOKE_MIN_CONSECUTIVE_FRAMES", 8)
            self.min_duration_seconds = min_duration_seconds if min_duration_seconds is not None else getattr(settings, "SMOKE_MIN_DURATION_SECONDS", 2.0)
            self.cooldown_seconds = cooldown_seconds if cooldown_seconds is not None else getattr(settings, "SMOKE_ALERT_COOLDOWN_SECONDS", 30.0)
        else:
            self.min_confidence = min_confidence if min_confidence is not None else getattr(settings, "VERIFICATION_MIN_CONFIDENCE", 0.45)
            self.alert_min_confidence = min_confidence if min_confidence is not None else getattr(settings, "VERIFICATION_MIN_CONFIDENCE", 0.45)
            self.min_consecutive_frames = min_consecutive_frames if min_consecutive_frames is not None else 7
            self.min_duration_seconds = min_duration_seconds if min_duration_seconds is not None else 1.4
            self.cooldown_seconds = cooldown_seconds if cooldown_seconds is not None else 30.0
        self.cleared_miss_tolerance = max(2, cleared_miss_tolerance)

        # Internal state metrics
        self.state: EventState = EventState.NORMAL
        self.event_id: Optional[str] = None
        self.consecutive_frames: int = 0
        self.missed_frames: int = 0
        self.start_time: Optional[datetime] = None
        self.start_timestamp: float = 0.0
        self.last_alert_timestamp: float = 0.0
        self.max_confidence: float = 0.0
        self.latest_confidence: float = 0.0
        self.latest_bbox: Optional[BoundingBox] = None
        self.latest_frame_info: Dict[str, Any] = {}

    def update(self, detections: List[DetectionResult], frame_info: Dict[str, Any]) -> Optional[VerifiedEvent]:
        """
        Processes new frame detections for this class and updates the state machine.
        Returns a VerifiedEvent payload when a state transition occurs (e.g. CONFIRMED/ALERT_SENT, ACTIVE, CLEARED).
        """
        now_dt = datetime.now().astimezone()
        now_ts = time.time()

        # Find detections matching this class with confidence >= min_confidence
        class_dets = [
            d for d in detections
            if d.class_name.lower() == self.class_name.lower() and d.confidence >= self.min_confidence
        ]

        spatial_iou_threshold = getattr(settings, "SPATIAL_IOU_THRESHOLD", 0.18)
        best_det = None

        if class_dets:
            if self.latest_bbox and self.state in [EventState.POSSIBLE, EventState.ALERT_SENT, EventState.ACTIVE]:
                # Spatial tracking: match boxes that overlap (IoU >= threshold) OR have close centroids (< 0.35 normalized dist)
                matching_dets = []
                for d in class_dets:
                    iou = d.bbox.iou(self.latest_bbox)
                    c_prev_x = (self.latest_bbox.x_min + self.latest_bbox.x_max) / 2.0
                    c_prev_y = (self.latest_bbox.y_min + self.latest_bbox.y_max) / 2.0
                    c_curr_x = (d.bbox.x_min + d.bbox.x_max) / 2.0
                    c_curr_y = (d.bbox.y_min + d.bbox.y_max) / 2.0
                    dist = ((c_prev_x - c_curr_x) ** 2 + (c_prev_y - c_curr_y) ** 2) ** 0.5
                    if iou >= spatial_iou_threshold or dist <= 0.35:
                        matching_dets.append((d, max(iou, 1.0 - dist)))

                if matching_dets:
                    best_det = max(matching_dets, key=lambda x: (x[1], x[0].confidence))[0]
                else:
                    best_det = max(class_dets, key=lambda d: d.confidence)
            else:
                best_det = max(class_dets, key=lambda d: d.confidence)

        # -----------------------------------------------------------------
        # CASE A: Spatially Matched Detection Present in Current Frame
        # -----------------------------------------------------------------
        if best_det:
            self.missed_frames = 0
            self.consecutive_frames += 1
            self.latest_confidence = best_det.confidence
            self.max_confidence = max(self.max_confidence, best_det.confidence)
            self.latest_bbox = best_det.bbox
            self.latest_frame_info = frame_info

            # Transition 1: NORMAL -> POSSIBLE
            if self.state == EventState.NORMAL:
                self.state = EventState.POSSIBLE
                self.event_id = f"evt_{uuid.uuid4().hex[:10]}"
                self.start_time = now_dt
                self.start_timestamp = now_ts
                logger.info(
                    f"TemporalTracker: Camera {self.camera_id} [{self.class_name.upper()}] "
                    f"State NORMAL -> POSSIBLE (Conf: {round(best_det.confidence, 2)})"
                )

            duration = now_ts - self.start_timestamp

            # Transition 2: POSSIBLE -> CONFIRMED -> ALERT_SENT
            if self.state == EventState.POSSIBLE:
                sustained = (self.consecutive_frames >= self.min_consecutive_frames) and (duration >= self.min_duration_seconds)
                if sustained and self.max_confidence < self.alert_min_confidence:
                    # Persistent but weak: keep tracking as a visible detection without raising an
                    # alert. Logged once per streak at debug level to avoid log spam.
                    if self.consecutive_frames == self.min_consecutive_frames:
                        logger.debug(
                            f"TemporalTracker: Camera {self.camera_id} [{self.class_name.upper()}] "
                            f"sustained low-confidence signal (max {round(self.max_confidence, 2)} < "
                            f"alert floor {round(self.alert_min_confidence, 2)}); detection only."
                        )
                elif sustained:
                    self.state = EventState.CONFIRMED
                    logger.warning(
                        f"TemporalTracker: Camera {self.camera_id} [{self.class_name.upper()}] "
                        f"State POSSIBLE -> CONFIRMED! (Frames: {self.consecutive_frames}, Duration: {round(duration, 1)}s)"
                    )
                    # Transition immediately to ALERT_SENT
                    self.state = EventState.ALERT_SENT
                    self.last_alert_timestamp = now_ts
                    evt_id = self.event_id or f"evt_{uuid.uuid4().hex[:10]}"
                    self.event_id = evt_id

                    return VerifiedEvent(
                        event_id=evt_id,
                        camera_id=self.camera_id,
                        class_name=self.class_name,
                        state=EventState.ALERT_SENT,
                        consecutive_frames=self.consecutive_frames,
                        duration_seconds=duration,
                        max_confidence=self.max_confidence,
                        latest_confidence=self.latest_confidence,
                        start_time=self.start_time or now_dt,
                        updated_time=now_dt,
                        bounding_box=self.latest_bbox,
                        frame_info=self.latest_frame_info,
                        metadata={"action": "INITIAL_ALERT"}
                    )

            # Transition 3: ALERT_SENT / ACTIVE -> ACTIVE
            if self.state in [EventState.ALERT_SENT, EventState.ACTIVE]:
                self.state = EventState.ACTIVE
                # Check if cooldown has elapsed to send periodic status update
                if (now_ts - self.last_alert_timestamp) >= self.cooldown_seconds:
                    self.last_alert_timestamp = now_ts
                    evt_id = self.event_id or f"evt_{uuid.uuid4().hex[:10]}"
                    self.event_id = evt_id
                    return VerifiedEvent(
                        event_id=evt_id,
                        camera_id=self.camera_id,
                        class_name=self.class_name,
                        state=EventState.ACTIVE,
                        consecutive_frames=self.consecutive_frames,
                        duration_seconds=duration,
                        max_confidence=self.max_confidence,
                        latest_confidence=self.latest_confidence,
                        start_time=self.start_time or now_dt,
                        updated_time=now_dt,
                        bounding_box=self.latest_bbox,
                        frame_info=self.latest_frame_info,
                        metadata={"action": "ACTIVE_UPDATE", "cooldown_elapsed": True}
                    )

            return None

        # -----------------------------------------------------------------
        # CASE B: Detection Absent in Current Frame
        # -----------------------------------------------------------------
        else:
            # Sub-case B1: False Alarm Recovery (POSSIBLE -> NORMAL)
            if self.state == EventState.POSSIBLE:
                self.missed_frames += 1
                if self.consecutive_frames <= 1 or self.missed_frames >= self.cleared_miss_tolerance:
                    logger.info(
                        f"TemporalTracker: Camera {self.camera_id} [{self.class_name.upper()}] "
                        f"Transient detection cleared before confirmation. Resetting POSSIBLE -> NORMAL."
                    )
                    self.reset()
                return None

            # Sub-case B2: Active Event Clearing (ALERT_SENT / ACTIVE -> CLEARED -> NORMAL)
            if self.state in [EventState.ALERT_SENT, EventState.ACTIVE]:
                self.missed_frames += 1
                if self.missed_frames >= self.cleared_miss_tolerance:
                    duration = now_ts - self.start_timestamp
                    evt_id = self.event_id or f"evt_{uuid.uuid4().hex[:10]}"
                    cleared_event = VerifiedEvent(
                        event_id=evt_id,
                        camera_id=self.camera_id,
                        class_name=self.class_name,
                        state=EventState.CLEARED,
                        consecutive_frames=self.consecutive_frames,
                        duration_seconds=duration,
                        max_confidence=self.max_confidence,
                        latest_confidence=self.latest_confidence,
                        start_time=self.start_time or now_dt,
                        updated_time=now_dt,
                        bounding_box=self.latest_bbox,
                        frame_info=self.latest_frame_info,
                        metadata={"action": "EVENT_CLEARED"}
                    )
                    logger.info(
                        f"TemporalTracker: Camera {self.camera_id} [{self.class_name.upper()}] "
                        f"Event CLEARED after {round(duration, 1)}s. Returning to NORMAL state."
                    )
                    self.reset()
                    return cleared_event

            return None

    def reset(self) -> None:
        """
        Resets tracking state back to NORMAL.
        """
        self.state = EventState.NORMAL
        self.event_id = None
        self.consecutive_frames = 0
        self.missed_frames = 0
        self.start_time = None
        self.start_timestamp = 0.0
        self.last_alert_timestamp = 0.0
        self.max_confidence = 0.0
        self.latest_confidence = 0.0
        self.latest_bbox = None
        self.latest_frame_info = {}


class CameraVerificationEngine:
    """
    Manages temporal verification trackers per target class ('fire', 'smoke') for a single camera.
    """

    def __init__(
        self,
        camera_id: int,
        target_classes: Optional[List[str]] = None,
        min_confidence: Optional[float] = None,
        min_consecutive_frames: Optional[int] = None,
        min_duration_seconds: Optional[float] = None,
        cooldown_seconds: Optional[float] = None
    ):
        self.camera_id = camera_id
        target_classes = target_classes or ["fire", "smoke"]
        self.trackers: Dict[str, ClassVerificationTracker] = {
            cls_name.lower(): ClassVerificationTracker(
                camera_id=camera_id,
                class_name=cls_name.lower(),
                min_confidence=min_confidence,
                min_consecutive_frames=min_consecutive_frames,
                min_duration_seconds=min_duration_seconds,
                cooldown_seconds=cooldown_seconds
            )
            for cls_name in target_classes
        }

    def process_frame_detections(
        self,
        detections: List[DetectionResult],
        frame_info: Dict[str, Any]
    ) -> List[VerifiedEvent]:
        """
        Evaluates frame detections across all class trackers.
        Returns a list of state transition VerifiedEvents.
        """
        events: List[VerifiedEvent] = []
        for cls_name, tracker in self.trackers.items():
            verified_evt = tracker.update(detections, frame_info)
            if verified_evt:
                events.append(verified_evt)
        return events

    def reset_all(self) -> None:
        """
        Resets all class trackers (e.g. on camera stream disconnect).
        """
        for tracker in self.trackers.values():
            tracker.reset()
