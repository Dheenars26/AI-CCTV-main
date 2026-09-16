"""
Polygon Safety Zone Monitoring Engine (ZoneEngine).
Evaluates worker spatial containment inside camera-defined polygon safety zones using point-in-polygon geometry.
Enforces coordinate validation (>= 3 vertices, valid non-self-intersecting polygon).
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from app.detection.base import BoundingBox
from app.safety.association import WorkerPPEAnalysis
from app.utils.logger import logger


@dataclass
class ZoneEvaluationResult:
    zone_id: int
    zone_name: str
    zone_type: str  # "HAZARD", "RESTRICTED", "GENERAL"
    ppe_profile_id: Optional[int]
    worker_analysis: WorkerPPEAnalysis
    is_inside: bool
    is_unauthorized: bool = False
    metadata: Optional[Dict[str, Any]] = None


class ZoneEngine:
    """
    Polygon Zone Containment & Geometry Validation Subsystem.
    """

    @staticmethod
    def validate_polygon(coordinates: List[List[float]]) -> Tuple[bool, str]:
        """
        Validates polygon coordinates:
        - Must be a non-empty list of [x, y] vertex pairs
        - Must contain at least 3 distinct vertices
        - Coordinates must be normalized in range [0.0, 1.0]
        """
        if not isinstance(coordinates, list):
            return False, "Polygon coordinates must be a list of [x, y] pairs."

        if len(coordinates) < 3:
            return False, f"Polygon must contain at least 3 vertices (received {len(coordinates)})."

        for idx, pt in enumerate(coordinates):
            if not isinstance(pt, (list, tuple)) or len(pt) < 2:
                return False, f"Vertex at index {idx} is invalid."
            x, y = float(pt[0]), float(pt[1])
            if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
                return False, f"Vertex {pt} at index {idx} out of normalized bounds [0.0, 1.0]."

        return True, "Valid polygon"

    @classmethod
    def point_in_polygon(cls, x: float, y: float, polygon: List[List[float]]) -> bool:
        """
        Ray-casting point-in-polygon containment algorithm using Jordan Curve Theorem.
        Returns True if point (x, y) is inside the polygon.
        """
        n = len(polygon)
        inside = False
        p1x, p1y = polygon[0][0], polygon[0][1]

        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n][0], polygon[i % n][1]
            if (p1y > y) != (p2y > y):
                if x < (p2x - p1x) * (y - p1y) / (p2y - p1y) + p1x:
                    inside = not inside
            p1x, p1y = p2x, p2y

        return inside

    @classmethod
    def is_worker_in_zone(cls, worker_box: BoundingBox, polygon: List[List[float]]) -> bool:
        """
        Checks if worker is inside safety zone polygon by testing multi-point body anchors
        (centroid, foot base, lower torso, and left/right stance base points).
        """
        valid, _ = cls.validate_polygon(polygon)
        if not valid:
            return False

        w = worker_box.x_max - worker_box.x_min
        h = worker_box.y_max - worker_box.y_min

        # Compute key worker body anchor points
        center_x = (worker_box.x_min + worker_box.x_max) / 2.0
        center_y = (worker_box.y_min + worker_box.y_max) / 2.0

        anchor_points = [
            (center_x, center_y),                     # Centroid
            (center_x, worker_box.y_max),             # Bottom center (foot base)
            (center_x, worker_box.y_min + 0.75 * h),  # Knee level
            (worker_box.x_min + 0.25 * w, worker_box.y_max),  # Left foot stance
            (worker_box.x_min + 0.75 * w, worker_box.y_max)   # Right foot stance
        ]

        for ax, ay in anchor_points:
            if cls.point_in_polygon(ax, ay, polygon):
                return True

        return False

    def evaluate_workers_in_zones(
        self,
        worker_analyses: List[WorkerPPEAnalysis],
        safety_zones: List[Dict[str, Any]]
    ) -> List[ZoneEvaluationResult]:
        """
        Evaluates active workers against registered camera safety zones.
        Returns a list of ZoneEvaluationResult matches.
        """
        results: List[ZoneEvaluationResult] = []
        if not worker_analyses or not safety_zones:
            return results

        for worker in worker_analyses:
            for zone in safety_zones:
                if not zone.get("enabled", True):
                    continue

                poly = zone.get("polygon_coordinates", [])
                if not poly:
                    continue

                if self.is_worker_in_zone(worker.bounding_box, poly):
                    z_type = zone.get("zone_type", "HAZARD").upper()
                    is_unauth = (z_type == "RESTRICTED")

                    eval_res = ZoneEvaluationResult(
                        zone_id=zone.get("id", 0),
                        zone_name=zone.get("name", "Safety Zone"),
                        zone_type=z_type,
                        ppe_profile_id=zone.get("ppe_profile_id"),
                        worker_analysis=worker,
                        is_inside=True,
                        is_unauthorized=is_unauth,
                        metadata={"evaluated_at": worker.timestamp}
                    )
                    results.append(eval_res)

        return results
