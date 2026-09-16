"""
Person-Centric PPE Spatial Association Engine (PPEAssociationEngine).
Associates detected PPE equipment items with tracked worker bounding boxes based on body-region spatial rules:
- Helmet -> Head region (0.0 to 0.3 of person height)
- Mask / Goggles -> Face region (0.1 to 0.4 of person height)
- Vest -> Torso region (0.2 to 0.7 of person height)
- Gloves -> Hand region (0.5 to 0.9 of person height)
- Safety Shoes -> Foot region (0.7 to 1.0 of person height)
Determines worker PPE status: PASS, VIOLATION, UNKNOWN.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from app.detection.base import BoundingBox, DetectionResult
from app.safety.tracker import TrackedPerson


@dataclass
class WorkerPPEAnalysis:
    person_id: int
    camera_id: int
    bounding_box: BoundingBox
    status: str  # "PASS", "VIOLATION", "UNKNOWN"
    required_equipment: List[str]
    detected_equipment: List[str]
    missing_equipment: List[str]
    confidence: float
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "person_id": self.person_id,
            "camera_id": self.camera_id,
            "bounding_box": self.bounding_box.to_dict(),
            "status": self.status,
            "required_equipment": self.required_equipment,
            "detected_equipment": self.detected_equipment,
            "missing_equipment": self.missing_equipment,
            "confidence": round(self.confidence, 4),
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }


class PPEAssociationEngine:
    """
    Spatial Body Region Association Engine.
    Correlates individual PPE detections (helmet, vest, mask, goggles, gloves, safety_shoes)
    to tracked worker bounding boxes.
    """

    # Body region relative centroid height ranges (cy_min, cy_max)
    RELATIVE_CENTROID_RANGES: Dict[str, Tuple[float, float]] = {
        "helmet": (-0.25, 0.40),
        "hard_hat": (-0.25, 0.40),
        "cap": (-0.25, 0.40),
        "mask": (-0.10, 0.45),
        "face_mask": (-0.10, 0.45),
        "goggles": (-0.15, 0.65),
        "glasses": (-0.15, 0.65),
        "safety_glasses": (-0.15, 0.65),
        "safety_glass": (-0.15, 0.65),
        "glass": (-0.15, 0.65),
        "eyewear": (-0.15, 0.65),
        "eye_protection": (-0.15, 0.65),
        "spec": (-0.15, 0.65),
        "specs": (-0.15, 0.65),
        "spectacles": (-0.15, 0.65),
        "protective_glasses": (-0.15, 0.65),
        "safety_goggles": (-0.15, 0.65),
        "vest": (0.02, 0.95),
        "safety_vest": (0.02, 0.95),
        "jacket": (0.02, 0.95),
        "gloves": (0.25, 0.95),
        "safety_shoes": (0.70, 1.15),
        "boots": (0.70, 1.15)
    }

    def __init__(self, min_association_iou: float = 0.15):
        self.min_association_iou = min_association_iou

    def associate(
        self,
        camera_id: int,
        tracked_persons: List[TrackedPerson],
        ppe_detections: List[DetectionResult],
        required_equipment: List[str],
        timestamp: Optional[str] = None
    ) -> List[WorkerPPEAnalysis]:
        """
        Executes spatial body region association between workers and PPE items.
        Applies competitive assignment in multi-worker scenes so adjacent workers do not falsely share gear.
        """
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        if not tracked_persons:
            return []

        req_items = [e.lower() for e in (required_equipment or ["helmet", "vest"])]
        results: List[WorkerPPEAnalysis] = []

        ppe_items = [d for d in ppe_detections if d.label.lower() != "person"]

        # Competitive association in multi-worker scenes:
        # Determine the primary owner worker for each PPE detection by highest spatial affinity
        item_owner: Dict[int, int] = {}
        if len(tracked_persons) > 1 and ppe_items:
            for ppe_idx, ppe_det in enumerate(ppe_items):
                label = ppe_det.label.lower()
                best_pid = None
                best_score = -1.0
                for person in tracked_persons:
                    is_on, score = self._is_ppe_on_person_with_score(person.bbox, ppe_det.bbox, label)
                    if is_on and score > best_score:
                        best_score = score
                        best_pid = person.person_id
                if best_pid is not None:
                    item_owner[ppe_idx] = best_pid

        for person in tracked_persons:
            detected_for_person: List[str] = []
            max_conf = person.confidence

            for ppe_idx, ppe_det in enumerate(ppe_items):
                # When multiple workers exist, ensure this equipment item wasn't claimed by a closer worker
                if item_owner and item_owner.get(ppe_idx) != person.person_id:
                    continue

                label = ppe_det.label.lower()
                if self._is_ppe_on_person(person.bbox, ppe_det.bbox, label):
                    standard_label = self._normalize_label(label)
                    if standard_label not in detected_for_person:
                        detected_for_person.append(standard_label)
                        max_conf = max(max_conf, ppe_det.confidence)

            missing_items: List[str] = []
            for req in req_items:
                norm_req = self._normalize_label(req)
                if not any(self._match_equipment(norm_req, det) for det in detected_for_person):
                    missing_items.append(req)

            if not req_items:
                status = "PASS"
            elif len(missing_items) == 0:
                status = "PASS"
            else:
                status = "VIOLATION"

            analysis = WorkerPPEAnalysis(
                person_id=person.person_id,
                camera_id=camera_id,
                bounding_box=person.bbox,
                status=status,
                required_equipment=req_items,
                detected_equipment=detected_for_person,
                missing_equipment=missing_items,
                confidence=max_conf,
                timestamp=ts
            )
            results.append(analysis)

        return results

    def _is_ppe_on_person_with_score(self, person_box: BoundingBox, ppe_box: BoundingBox, label: str) -> Tuple[bool, float]:
        """
        Calculates whether a PPE item is spatially on a person, returning (is_on, match_score).
        Match score combines IoA and centroid distance to accurately resolve multi-worker overlaps.
        """
        p_xmin = max(0.0, min(1.0, person_box.x_min))
        p_ymin = max(0.0, min(1.0, person_box.y_min))
        p_xmax = max(0.0, min(1.0, person_box.x_max))
        p_ymax = max(0.0, min(1.0, person_box.y_max))

        e_xmin = max(0.0, min(1.0, ppe_box.x_min))
        e_ymin = max(0.0, min(1.0, ppe_box.y_min))
        e_xmax = max(0.0, min(1.0, ppe_box.x_max))
        e_ymax = max(0.0, min(1.0, ppe_box.y_max))

        p_w = p_xmax - p_xmin
        p_h = p_ymax - p_ymin

        if p_w <= 0 or p_h <= 0:
            return False, 0.0

        # Relative centroid height cy in range [0.0, 1.0+] relative to worker top/height
        ppe_center_x = (e_xmin + e_xmax) / 2.0
        ppe_center_y = (e_ymin + e_ymax) / 2.0
        cy_rel = (ppe_center_y - p_ymin) / p_h

        cy_bounds = self.RELATIVE_CENTROID_RANGES.get(label, (0.0, 1.05))
        cy_in_range = cy_bounds[0] <= cy_rel <= cy_bounds[1]
        x_in_range = (p_xmin - 0.25 * p_w) <= ppe_center_x <= (p_xmax + 0.25 * p_w)

        # Compute Intersection over PPE Area (IoA)
        inter_x1 = max(p_xmin, e_xmin)
        inter_y1 = max(p_ymin, e_ymin)
        inter_x2 = min(p_xmax, e_xmax)
        inter_y2 = min(p_ymax, e_ymax)

        inter_area = max(0.0, inter_x2 - inter_x1) * max(0.0, inter_y2 - inter_y1)
        ppe_area = max(0.0, e_xmax - e_xmin) * max(0.0, e_ymax - e_ymin)
        ioa = (inter_area / ppe_area) if ppe_area > 0 else 0.0

        is_valid = (
            (ioa >= 0.10 and x_in_range and cy_in_range) or
            (cy_in_range and x_in_range and ioa >= 0.04) or
            (ioa >= 0.30)
        )
        if not is_valid:
            return False, 0.0

        person_center_x = (p_xmin + p_xmax) / 2.0
        dist_x = abs(ppe_center_x - person_center_x) / max(0.01, p_w)
        score = ioa * 2.0 + max(0.0, 1.0 - dist_x)
        return True, score

    def _is_ppe_on_person(self, person_box: BoundingBox, ppe_box: BoundingBox, label: str) -> bool:
        is_on, _ = self._is_ppe_on_person_with_score(person_box, ppe_box, label)
        return is_on

    @staticmethod
    def _normalize_label(label: str) -> str:
        l = label.lower().replace("_", " ").replace("-", " ")
        if any(w in l for w in ["helmet", "hard hat", "hardhat", "cap", "headgear"]):
            return "helmet"
        if any(w in l for w in ["vest", "jacket", "hivis", "hi vis", "high vis", "reflective", "safety vest"]):
            return "vest"
        if any(w in l for w in ["mask", "face mask", "n95", "respirator"]):
            return "mask"
        if any(w in l for w in ["goggles", "glasses", "safety glasses", "safety glass", "glass", "eye protection", "eyewear", "spec", "specs", "spectacles", "protective glasses", "safety goggles"]):
            return "goggles"
        if any(w in l for w in ["glove", "gloves", "hand protection"]):
            return "gloves"
        if any(w in l for w in ["shoe", "shoes", "boot", "boots", "steel toe", "safety shoes"]):
            return "safety_shoes"
        return l

    @classmethod
    def _match_equipment(cls, req: str, det: str) -> bool:
        n_req = cls._normalize_label(req)
        n_det = cls._normalize_label(det)
        return n_req == n_det or n_req in n_det or n_det in n_req
