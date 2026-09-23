"""
PPE Violation Temporal Verification Subsystem (PPETemporalVerificationEngine).
Applies finite state machine verification to PPE violations to eliminate single-frame transient false positives.
FSM States: NORMAL -> POSSIBLE -> CONFIRMED -> ALERT_SENT -> ACTIVE -> CLEARED.
"""

import uuid
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from app.detection.verification import EventState, VerifiedEvent, BoundingBox
from app.safety.association import WorkerPPEAnalysis
from app.utils.logger import logger


class WorkerPPETrackerFSM:
    """
    FSM tracking PPE compliance for a single worker (by person_id) on a camera stream.
    """

    def __init__(
        self,
        camera_id: int,
        person_id: int,
        min_consecutive_frames: int = 5,
        min_duration_seconds: float = 2.0,
        cleared_miss_tolerance: int = 3
    ):
        self.camera_id = camera_id
        self.person_id = person_id
        self.min_consecutive_frames = min_consecutive_frames
        self.min_duration_seconds = min_duration_seconds
        self.cleared_miss_tolerance = cleared_miss_tolerance

        self.state: EventState = EventState.NORMAL
        self.event_id: Optional[str] = None
        self.consecutive_frames: int = 0
        self.missed_frames: int = 0
        self.start_time: Optional[datetime] = None
        self.start_timestamp: float = 0.0
        self.last_alert_timestamp: float = 0.0
        self.latest_analysis: Optional[WorkerPPEAnalysis] = None

    def update(self, analysis: Optional[WorkerPPEAnalysis]) -> Optional[VerifiedEvent]:
        """
        Updates worker PPE state machine and returns a VerifiedEvent payload on state transition.
        """
        now_dt = datetime.now(timezone.utc)
        now_ts = time.time()

        is_violation = (analysis is not None and analysis.status == "VIOLATION")

        # -----------------------------------------------------------------
        # CASE A: Violation present in current frame
        # -----------------------------------------------------------------
        if is_violation and analysis:
            self.missed_frames = 0
            self.consecutive_frames += 1
            self.latest_analysis = analysis

            if self.state == EventState.NORMAL:
                self.state = EventState.POSSIBLE
                self.event_id = f"ppe_evt_{uuid.uuid4().hex[:10]}"
                self.start_time = now_dt
                self.start_timestamp = now_ts
                logger.info(f"PPETrackerFSM: Cam {self.camera_id} Person #{self.person_id} NORMAL -> POSSIBLE violation.")

            duration = now_ts - self.start_timestamp

            if self.state == EventState.POSSIBLE:
                if (self.consecutive_frames >= self.min_consecutive_frames) and (duration >= self.min_duration_seconds):
                    self.state = EventState.ALERT_SENT
                    self.last_alert_timestamp = now_ts
                    logger.warning(f"PPETrackerFSM: Cam {self.camera_id} Person #{self.person_id} VERIFIED PPE VIOLATION!")

                    return VerifiedEvent(
                        event_id=self.event_id or f"ppe_evt_{uuid.uuid4().hex[:10]}",
                        camera_id=self.camera_id,
                        class_name="ppe_violation",
                        state=EventState.ALERT_SENT,
                        consecutive_frames=self.consecutive_frames,
                        duration_seconds=duration,
                        max_confidence=analysis.confidence,
                        latest_confidence=analysis.confidence,
                        start_time=self.start_time or now_dt,
                        updated_time=now_dt,
                        bounding_box=analysis.bounding_box,
                        metadata={
                            "person_id": self.person_id,
                            "missing_equipment": analysis.missing_equipment,
                            "detected_equipment": analysis.detected_equipment
                        }
                    )

            if self.state in [EventState.ALERT_SENT, EventState.ACTIVE]:
                self.state = EventState.ACTIVE
                return None

            return None

        # -----------------------------------------------------------------
        # CASE B: Violation absent / PASS in current frame
        # -----------------------------------------------------------------
        else:
            if self.state == EventState.POSSIBLE:
                self.missed_frames += 1
                if self.missed_frames >= self.cleared_miss_tolerance:
                    logger.info(f"PPETrackerFSM: Cam {self.camera_id} Person #{self.person_id} Transient violation cleared. Resetting to NORMAL.")
                    self.reset()
                return None

            if self.state in [EventState.ALERT_SENT, EventState.ACTIVE]:
                self.missed_frames += 1
                if self.missed_frames >= self.cleared_miss_tolerance:
                    duration = now_ts - self.start_timestamp
                    cleared_evt = VerifiedEvent(
                        event_id=self.event_id or f"ppe_evt_{uuid.uuid4().hex[:10]}",
                        camera_id=self.camera_id,
                        class_name="ppe_violation",
                        state=EventState.CLEARED,
                        consecutive_frames=self.consecutive_frames,
                        duration_seconds=duration,
                        max_confidence=self.latest_analysis.confidence if self.latest_analysis else 0.9,
                        latest_confidence=0.0,
                        start_time=self.start_time or now_dt,
                        updated_time=now_dt,
                        bounding_box=self.latest_analysis.bounding_box if self.latest_analysis else None,
                        metadata={"person_id": self.person_id, "action": "PPE_VIOLATION_CLEARED"}
                    )
                    logger.info(f"PPETrackerFSM: Cam {self.camera_id} Person #{self.person_id} PPE violation CLEARED after {round(duration, 1)}s.")
                    self.reset()
                    return cleared_evt

            return None

    def reset(self) -> None:
        self.state = EventState.NORMAL
        self.event_id = None
        self.consecutive_frames = 0
        self.missed_frames = 0
        self.start_time = None
        self.start_timestamp = 0.0
        self.last_alert_timestamp = 0.0
        self.latest_analysis = None


class PPETemporalVerificationEngine:
    """
    Manages per-worker PPE FSM trackers per camera stream.
    """

    def __init__(
        self,
        camera_id: int,
        min_consecutive_frames: int = 5,
        min_duration_seconds: float = 2.0
    ):
        self.camera_id = camera_id
        self.min_consecutive_frames = min_consecutive_frames
        self.min_duration_seconds = min_duration_seconds
        self._trackers: Dict[int, WorkerPPETrackerFSM] = {}

    def process_worker_analyses(self, analyses: List[WorkerPPEAnalysis]) -> List[VerifiedEvent]:
        verified_events: List[VerifiedEvent] = []
        active_pids = {a.person_id for a in analyses}

        # Update active worker FSMs
        for analysis in analyses:
            pid = analysis.person_id
            if pid not in self._trackers:
                self._trackers[pid] = WorkerPPETrackerFSM(
                    camera_id=self.camera_id,
                    person_id=pid,
                    min_consecutive_frames=self.min_consecutive_frames,
                    min_duration_seconds=self.min_duration_seconds
                )
            fsm = self._trackers[pid]
            evt = fsm.update(analysis)
            if evt:
                verified_events.append(evt)

        # Update workers not present in current frame
        for pid in list(self._trackers.keys()):
            if pid not in active_pids:
                fsm = self._trackers[pid]
                evt = fsm.update(None)
                if evt:
                    verified_events.append(evt)
                if fsm.state == EventState.NORMAL and fsm.missed_frames >= 10:
                    self._trackers.pop(pid, None)

        return verified_events

    def reset(self) -> None:
        for fsm in self._trackers.values():
            fsm.reset()
        self._trackers.clear()
