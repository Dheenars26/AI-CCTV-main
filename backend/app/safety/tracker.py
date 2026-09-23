"""
Session-Based Multi-Object Worker Tracker (PersonTracker).
Tracks workers across video frames using IoU & centroid distance matching without facial biometrics or identity tracking.
Assigns temporary numeric person_id values per camera stream session.
"""

import time
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from app.detection.base import BoundingBox, DetectionResult


@dataclass
class TrackedPerson:
    person_id: int
    camera_id: int
    bbox: BoundingBox
    confidence: float
    last_seen_timestamp: float
    hits: int = 1
    age: int = 1


class PersonTracker:
    """
    IoU & Centroid Distance Multi-Object Tracker for Surveillance Workers.
    Guarantees stable temporal tracking IDs across frames without facial recognition.
    """

    def __init__(
        self,
        camera_id: int,
        iou_threshold: float = 0.3,
        max_disappeared_frames: int = 20,
        alpha: float = 0.70
    ):
        self.camera_id = camera_id
        self.iou_threshold = iou_threshold
        self.max_disappeared_frames = max_disappeared_frames
        self.alpha = alpha
        
        self._next_person_id: int = 101
        self._tracked_persons: Dict[int, TrackedPerson] = {}
        self._disappeared_counts: Dict[int, int] = {}

    def update(self, person_detections: List[DetectionResult]) -> List[TrackedPerson]:
        """
        Updates tracking FSM with new frame person detections.
        Applies Exponential Moving Average (EMA, alpha=0.70) bounding box smoothing.
        Resets EMA directly to current detection box if track reappears after occlusion (disappeared >= 1 frame).
        """
        now = time.time()
        
        # Filter weak/small pseudo-person detections with robust surveillance recall
        person_detections = [
            d for d in person_detections
            if d.confidence >= 0.28 and (d.bbox.y_max - d.bbox.y_min) >= 0.08
        ]

        # If no active detections, increment disappeared counts
        if not person_detections:
            for pid in list(self._tracked_persons.keys()):
                self._disappeared_counts[pid] = self._disappeared_counts.get(pid, 0) + 1
                if self._disappeared_counts[pid] > self.max_disappeared_frames:
                    self._tracked_persons.pop(pid, None)
                    self._disappeared_counts.pop(pid, None)
            return self.get_active_tracks()

        # Match incoming detections with existing tracks
        unmatched_dets = list(range(len(person_detections)))
        existing_pids = list(self._tracked_persons.keys())

        if existing_pids:
            # Match using IoU + Centroid Distance
            for pid in existing_pids:
                tracked = self._tracked_persons[pid]
                best_match_idx = -1
                best_score = 0.12

                t_cx = (tracked.bbox.x_min + tracked.bbox.x_max) / 2.0
                t_cy = (tracked.bbox.y_min + tracked.bbox.y_max) / 2.0

                for idx in unmatched_dets:
                    det = person_detections[idx]
                    iou_val = tracked.bbox.iou(det.bbox)
                    d_cx = (det.bbox.x_min + det.bbox.x_max) / 2.0
                    d_cy = (det.bbox.y_min + det.bbox.y_max) / 2.0
                    dist = ((t_cx - d_cx)**2 + (t_cy - d_cy)**2)**0.5

                    # Combined match score
                    score = iou_val + max(0.0, 0.35 - dist) if (iou_val >= 0.12 or dist <= 0.22) else 0.0
                    if score > best_score:
                        best_score = score
                        best_match_idx = idx

                if best_match_idx != -1:
                    matched_det = person_detections[best_match_idx]
                    disappeared_frames = self._disappeared_counts.get(pid, 0)

                    # Resets EMA state directly on track reappearance after occlusion to prevent stale interpolation
                    if disappeared_frames >= 1:
                        tracked.bbox = matched_det.bbox
                    else:
                        tracked.bbox = self._smooth_bbox(tracked.bbox, matched_det.bbox, self.alpha)

                    tracked.confidence = round(0.3 * tracked.confidence + 0.7 * matched_det.confidence, 4)
                    tracked.last_seen_timestamp = now
                    tracked.hits += 1
                    tracked.age += 1
                    self._disappeared_counts[pid] = 0
                    unmatched_dets.remove(best_match_idx)
                else:
                    self._disappeared_counts[pid] = self._disappeared_counts.get(pid, 0) + 1

        # Register new detections as new tracking IDs
        for idx in unmatched_dets:
            det = person_detections[idx]
            pid = self._next_person_id
            self._next_person_id += 1

            new_track = TrackedPerson(
                person_id=pid,
                camera_id=self.camera_id,
                bbox=det.bbox,
                confidence=det.confidence,
                last_seen_timestamp=now
            )
            self._tracked_persons[pid] = new_track
            self._disappeared_counts[pid] = 0

        # Remove stale tracks
        for pid in list(self._tracked_persons.keys()):
            if self._disappeared_counts.get(pid, 0) > self.max_disappeared_frames:
                self._tracked_persons.pop(pid, None)
                self._disappeared_counts.pop(pid, None)

        # Purge duplicate overlapping tracks tracking the same person
        self._purge_duplicate_tracks()

        return self.get_active_tracks()

    def has_recent_tracks(self) -> bool:
        """
        True while any track is still within its occlusion grace window.

        Distinct from :meth:`get_active_tracks` (which requires a detection in the *current* frame).
        Scheduling decisions must use this: a worker who stood still for one frame, or a detector that
        missed one frame, must not be treated as "the scene is empty".
        """
        return bool(self._tracked_persons)

    def get_active_tracks(self) -> List[TrackedPerson]:
        """
        Returns only currently active, non-disappeared tracked persons.
        Filters out ghost tracks (disappeared_counts > 0).
        """
        return [
            t for pid, t in self._tracked_persons.items()
            if self._disappeared_counts.get(pid, 0) == 0
        ]

    def _purge_duplicate_tracks(self) -> None:
        """
        Suppresses and purges duplicate tracks tracking the same physical person.
        If two tracks in _tracked_persons overlap with IoU >= 0.30 or centroid distance <= 0.18,
        keeps the track with higher hits / active status and deletes the duplicate.
        """
        active_pids = list(self._tracked_persons.keys())
        if len(active_pids) < 2:
            return

        def track_priority(pid: int):
            t = self._tracked_persons[pid]
            is_active = 1 if self._disappeared_counts.get(pid, 0) == 0 else 0
            return (is_active, t.hits, t.confidence, pid)

        sorted_pids = sorted(active_pids, key=track_priority, reverse=True)
        kept_pids: List[int] = []

        for pid in sorted_pids:
            if pid not in self._tracked_persons:
                continue
            t_box = self._tracked_persons[pid].bbox
            t_cx = (t_box.x_min + t_box.x_max) / 2.0
            t_cy = (t_box.y_min + t_box.y_max) / 2.0

            is_duplicate = False
            for k_pid in kept_pids:
                if k_pid not in self._tracked_persons:
                    continue
                k_box = self._tracked_persons[k_pid].bbox
                k_cx = (k_box.x_min + k_box.x_max) / 2.0
                k_cy = (k_box.y_min + k_box.y_max) / 2.0

                iou_val = t_box.iou(k_box)
                dist = ((t_cx - k_cx)**2 + (t_cy - k_cy)**2)**0.5

                if iou_val >= 0.30 or dist <= 0.18:
                    is_duplicate = True
                    break

            if is_duplicate:
                self._tracked_persons.pop(pid, None)
                self._disappeared_counts.pop(pid, None)
            else:
                kept_pids.append(pid)

    @staticmethod
    def _smooth_bbox(prev: BoundingBox, curr: BoundingBox, alpha: float = 0.70) -> BoundingBox:
        """
        Calculates Exponential Moving Average (EMA, alpha=0.70) for bounding box coordinates.
        """
        return BoundingBox(
            x_min=max(0.0, min(1.0, alpha * curr.x_min + (1.0 - alpha) * prev.x_min)),
            y_min=max(0.0, min(1.0, alpha * curr.y_min + (1.0 - alpha) * prev.y_min)),
            x_max=max(0.0, min(1.0, alpha * curr.x_max + (1.0 - alpha) * prev.x_max)),
            y_max=max(0.0, min(1.0, alpha * curr.y_max + (1.0 - alpha) * prev.y_max))
        )

    @staticmethod
    def _compute_iou(boxA: BoundingBox, boxB: BoundingBox) -> float:
        """
        Computes Intersection over Union (IoU) between two bounding boxes.
        """
        xA = max(boxA.x_min, boxB.x_min)
        yA = max(boxA.y_min, boxB.y_min)
        xB = min(boxA.x_max, boxB.x_max)
        yB = min(boxA.y_max, boxB.y_max)

        interWidth = max(0.0, xB - xA)
        interHeight = max(0.0, yB - yA)
        interArea = interWidth * interHeight

        boxAArea = (boxA.x_max - boxA.x_min) * (boxA.y_max - boxA.y_min)
        boxBArea = (boxB.x_max - boxB.x_min) * (boxB.y_max - boxB.y_min)
        unionArea = boxAArea + boxBArea - interArea

        if unionArea <= 0:
            return 0.0
        return interArea / unionArea

    def reset(self) -> None:
        self._tracked_persons.clear()
        self._disappeared_counts.clear()
        self._next_person_id = 101
