"""
PPE label normalisation and worker-crop (ROI) refinement.

Two problems are solved here.

**1. Small objects.** Safety glasses and gloves occupy a handful of pixels in a 640-px network
input. Measured on a real worker photo, the bundled PPE model scores ``Goggles`` at 0.116 over the
whole frame, but 0.25-0.31 when the same network is re-run on the worker's head crop - a factor
>2x in confidence purely from resolution. :class:`PPERoiRefiner` performs that second pass.

**2. Cost.** A second pass costs a full inference (~90 ms on CPU). Re-running it for every worker on
every frame would halve the camera's frame rate. The refiner is therefore *evidence driven*: it
only examines body regions whose item is currently **missing** (i.e. a potential violation), it
looks at one region per call (round-robin across pending workers), and it caches conclusions with a
short TTL so a confirmed item is not re-checked for several seconds. Compliant workers cost nothing.
"""

import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
import numpy as np

from app.detection.base import BoundingBox, DetectionResult
from app.detection.preprocess import clip_roi, prepare_worker_roi, upscale_if_small


# Canonical label vocabulary shared by the detector and the association engine.
_CANONICAL_ALIASES: Dict[str, Tuple[str, ...]] = {
    "person": ("person", "worker", "human", "people"),
    "helmet": ("helmet", "hard hat", "hardhat", "hard-hat", "cap", "headgear", "safety helmet"),
    "vest": ("vest", "safety vest", "safety_vest", "jacket", "hivis", "hi vis", "high vis",
             "high_vis_vest", "waistcoat", "reflective vest", "reflective_vest"),
    "mask": ("mask", "face mask", "face_mask", "n95", "respirator"),
    "goggles": ("goggles", "glasses", "safety glasses", "safety_glasses", "safety glass",
                "safety_glass", "eyewear", "eye protection", "eye_protection", "spectacles",
                "specs", "spec", "protective glasses", "protective_glasses", "safety goggles",
                "safety_goggles"),
    "gloves": ("gloves", "glove", "hand protection", "hand_protection"),
    "safety_shoes": ("safety shoes", "safety_shoes", "safety shoe", "safety_shoe", "shoes", "shoe",
                     "boots", "boot", "steel toe"),
}

# Classes that describe a *missing* item rather than a present one (ppe.onnx ships these heads).
NEGATIVE_CLASS_PREFIXES = ("no-", "no_", "no ", "fall-detected", "fall_detected")

_LABEL_LOOKUP: Dict[str, str] = {
    alias: canonical for canonical, aliases in _CANONICAL_ALIASES.items() for alias in aliases
}

# Which body region should be searched for a missing item, and the region's crop selector.
_BODY_REGION_FOR_ITEM: Dict[str, str] = {
    "goggles": "head",
    "mask": "head",
    "helmet": "head",
    "vest": "torso",
    "gloves": "torso",
    "safety_shoes": "full",
}


def normalise_ppe_label(raw_label: str) -> Optional[str]:
    """
    Maps a model class name onto the canonical vocabulary.

    Returns ``None`` for negative heads such as ``NO-Safety Vest`` (they are explicit
    non-compliance heads whose boxes overlap the worker, and mixing them into the positive
    vocabulary would both double-count detections and mislabel equipment as present).
    """
    if raw_label is None:
        return None
    label = raw_label.lower().strip().replace("_", " ").replace("-", " ")
    label = " ".join(label.split())

    if any(label.startswith(prefix.replace("-", " ").replace("_", " ")) for prefix in NEGATIVE_CLASS_PREFIXES):
        return None
    if label.startswith("no ") or label.startswith("fall detected"):
        return None

    if label in _LABEL_LOOKUP:
        return _LABEL_LOOKUP[label]
    # Substring fallback for exotic class spellings (e.g. "workers_with_vest").
    for alias, canonical in _LABEL_LOOKUP.items():
        if canonical == "person":
            continue
        if alias in label:
            return canonical
    if "person" in label or "worker" in label:
        return "person"
    return None


class PPERoiRefiner:
    """
    Evidence-driven worker-crop refinement for PPE items that are currently missing.

    Usage::

        refiner = PPERoiRefiner()
        extra = refiner.refine(image, persons, missing_by_person, infer_fn=runner_fn)
    """

    def __init__(
        self,
        enabled: bool = True,
        max_persons: int = 4,
        positive_ttl: float = 4.0,
        negative_ttl: float = 1.0,
        min_crop_side: int = 220,
        confidence_floor: float = 0.085,
    ):
        self.enabled = enabled
        self.max_persons = max_persons
        self.positive_ttl = positive_ttl
        self.negative_ttl = negative_ttl
        self.min_crop_side = min_crop_side
        self.confidence_floor = confidence_floor

        # person_id -> item -> (expiry_timestamp, found, det_info)
        self._cache: Dict[int, Dict[str, Tuple[float, bool, Optional[Dict[str, Any]]]]] = {}
        self._round_robin: int = 0
        self.last_report: Dict[str, object] = {}

    # ------------------------------------------------------------------ #
    def _cached(self, person_id: int, item: str) -> Optional[bool]:
        entry = self._cache.get(person_id, {}).get(item)
        if not entry:
            return None
        expiry = entry[0]
        found = entry[1]
        if time.time() > expiry:
            return None
        return found

    def _cached_entry(self, person_id: int, item: str) -> Optional[Tuple[bool, Optional[Dict[str, Any]]]]:
        entry = self._cache.get(person_id, {}).get(item)
        if not entry:
            return None
        expiry = entry[0]
        found = entry[1]
        det_info = entry[2] if len(entry) > 2 else None
        if time.time() > expiry:
            return None
        return found, det_info

    def _remember(
        self,
        person_id: int,
        item: str,
        found: bool,
        confidence: float = 0.0,
        det_info: Optional[Dict[str, Any]] = None,
    ) -> None:
        ttl = self.positive_ttl if found else self.negative_ttl
        # A high-confidence finding is trusted for longer than a marginal one.
        if found and confidence >= 0.55:
            ttl *= 1.5
        self._cache.setdefault(person_id, {})[item] = (time.time() + ttl, found, det_info)

    def forget(self, person_id: Optional[int] = None) -> None:
        """Drops cached conclusions (all workers, or one) after a config/profile change."""
        if person_id is None:
            self._cache.clear()
        else:
            self._cache.pop(person_id, None)

    # ------------------------------------------------------------------ #
    def refine(
        self,
        image_bgr: np.ndarray,
        persons: Sequence[Any],
        missing_by_person: Dict[int, List[str]],
        infer_fn: Callable[[np.ndarray], List[Tuple[str, float, Tuple[float, float, float, float]]]],
    ) -> List[DetectionResult]:
        """
        Runs at most one ROI inference and returns any newly found PPE as detections.

        :param image_bgr: full BGR frame.
        :param persons: tracked workers (objects exposing ``person_id`` and ``bbox``).
        :param missing_by_person: ``{person_id: [canonical item, ...]}`` currently believed missing.
        :param infer_fn: callable taking a crop and returning ``(raw_label, confidence, xyxy)`` in
                         *crop* pixel coordinates.
        :returns: detections in full-frame normalised coordinates, tagged with the ROI used.
        """
        self.last_report = {"candidates": 0, "attempted": 0, "hit": False, "roi": None}
        if not self.enabled or image_bgr is None or not missing_by_person:
            return []

        h, w = image_bgr.shape[:2]

        # Build the pending work list, collecting any valid cached positive detections.
        cached_results: List[DetectionResult] = []
        pending: List[Tuple[int, Any, str, str]] = []
        for index, person in enumerate(persons[: self.max_persons]):
            pid = person_key(person, index)
            for item in missing_by_person.get(pid, []):
                item_l = item.lower()
                cached_entry = self._cached_entry(pid, item_l)
                if cached_entry is not None:
                    found, det_info = cached_entry
                    if found and det_info is not None:
                        # Re-emit cached detection adjusted to person's current bbox
                        p_bbox = person.bbox
                        p_w = max(1e-4, p_bbox.x_max - p_bbox.x_min)
                        p_h = max(1e-4, p_bbox.y_max - p_bbox.y_min)
                        rx1, ry1, rx2, ry2 = det_info["rel_bbox"]
                        cached_results.append(DetectionResult(
                            label=det_info["label"],
                            confidence=det_info["confidence"],
                            bbox=BoundingBox(
                                x_min=max(0.0, min(1.0, p_bbox.x_min + rx1 * p_w)),
                                y_min=max(0.0, min(1.0, p_bbox.y_min + ry1 * p_h)),
                                x_max=max(0.0, min(1.0, p_bbox.x_min + rx2 * p_w)),
                                y_max=max(0.0, min(1.0, p_bbox.y_min + ry2 * p_h)),
                            ),
                            metadata={
                                "detector_module": "PPEDetector-WorkerROI",
                                "roi": det_info.get("region", "head"),
                                "evidence": "roi_refine_cached",
                                "person_id": pid,
                            }
                        ))
                    continue  # already corroborated recently - nothing to re-infer
                pending.append((pid, person, item_l, _BODY_REGION_FOR_ITEM.get(item_l, "torso")))

        self.last_report["candidates"] = len(pending)
        if not pending:
            return cached_results

        # Round-robin so a worker who never gets the item cannot starve other workers.
        picked = pending[self._round_robin % len(pending)]
        self._round_robin += 1
        pid, person, item, region = picked

        bbox = person.bbox
        person_xyxy = (
            bbox.x_min * w, bbox.y_min * h, bbox.x_max * w, bbox.y_max * h,
        )
        head_roi, torso_roi = prepare_worker_roi(person_xyxy, w, h)
        roi = head_roi if region == "head" else torso_roi if region == "torso" else clip_roi(
            (0, 0, w, h), w, h
        )
        x1, y1, x2, y2 = clip_roi(roi, w, h)
        crop = image_bgr[y1:y2, x1:x2]
        if crop.size == 0 or (x2 - x1) < 16 or (y2 - y1) < 16:
            return cached_results

        crop_prepared, upscale = upscale_if_small(crop, min_side=self.min_crop_side)
        self.last_report["attempted"] = 1
        self.last_report["roi"] = region
        self.last_report["person_id"] = pid

        try:
            raw_items = infer_fn(crop_prepared)
        except Exception:
            return cached_results

        results: List[DetectionResult] = []
        found_items: List[str] = []
        for raw_label, confidence, xyxy in raw_items:
            canonical = normalise_ppe_label(raw_label)
            if canonical is None or canonical == "person":
                continue
            min_conf = self.confidence_floor
            if canonical == "vest":
                from app.config.settings import settings
                min_conf = float(getattr(settings, "VEST_CROP_CONFIDENCE_FLOOR", 0.15))
            elif canonical == "gloves":
                min_conf = max(0.20, self.confidence_floor)

            if confidence < min_conf:
                continue
            # A body-region crop can only testify about the equipment that lives there.
            if region == "head" and canonical not in ("goggles", "mask", "helmet"):
                continue
            if region == "torso" and canonical not in ("vest", "gloves"):
                continue

            # Geometry sanity check for glasses (prevent "head" being classified as "glasses")
            lx1, ly1, lx2, ly2 = xyxy
            if canonical == "goggles":
                crop_area = (x2 - x1) * (y2 - y1)
                box_area = (lx2 - lx1) * (ly2 - ly1)
                if box_area > 0.40 * crop_area:  # Glasses shouldn't cover >40% of the head
                    continue

            lx1, ly1, lx2, ly2 = xyxy
            scale_back = 1.0 / (upscale if upscale > 0 else 1.0)
            fx1 = max(0.0, x1 + lx1 * scale_back)
            fy1 = max(0.0, y1 + ly1 * scale_back)
            fx2 = min(float(w), x1 + lx2 * scale_back)
            fy2 = min(float(h), y1 + ly2 * scale_back)
            if fx2 - fx1 < 1 or fy2 - fy1 < 1:
                continue

            results.append(DetectionResult(
                label=canonical,
                confidence=float(confidence),
                bbox=BoundingBox(
                    x_min=fx1 / w, y_min=fy1 / h, x_max=fx2 / w, y_max=fy2 / h
                ),
                metadata={
                    "detector_module": "PPEDetector-WorkerROI",
                    "roi": region,
                    "roi_upscale": round(upscale, 2),
                    "person_id": pid,
                    "evidence": "roi_refine",
                },
            ))
            found_items.append(canonical)

        p_w = max(1e-4, bbox.x_max - bbox.x_min)
        p_h = max(1e-4, bbox.y_max - bbox.y_min)
        for det in results:
            det_info = {
                "label": det.label,
                "confidence": det.confidence,
                "rel_bbox": (
                    (det.bbox.x_min - bbox.x_min) / p_w,
                    (det.bbox.y_min - bbox.y_min) / p_h,
                    (det.bbox.x_max - bbox.x_min) / p_w,
                    (det.bbox.y_max - bbox.y_min) / p_h,
                ),
                "region": region,
            }
            self._remember(pid, det.label, found=True, confidence=det.confidence, det_info=det_info)

        if item not in found_items:
            self._remember(pid, item, found=False, confidence=0.0, det_info=None)

        self.last_report["hit"] = bool(results)
        self.last_report["found"] = found_items
        return cached_results + results


def person_key(person: Any, index: int = 0) -> int:
    """
    Stable cache key for a worker.

    Tracked workers expose ``person_id``. Raw detections do not, so a *spatial* key is derived from
    the quantised box centre: a worker who stays in place keeps their cached conclusions between
    frames even though the detector has no identity for them. Using the list index alone would make
    the cache shuffle every time two workers swap detection order.
    """
    pid = getattr(person, "person_id", None)
    if pid is not None:
        try:
            return int(pid)
        except (TypeError, ValueError):
            pass
    bbox = getattr(person, "bbox", None)
    if bbox is not None:
        cx = (float(bbox.x_min) + float(bbox.x_max)) / 2.0
        cy = (float(bbox.y_min) + float(bbox.y_max)) / 2.0
        # 10x10 grid cells over the frame - coarse enough to be stable, fine enough to separate
        # two workers standing side by side.
        return 100000 + round(cx * 10) * 100 + round(cy * 10)
    return 100000 + index


def _items_for_region(region: str) -> Tuple[str, ...]:
    if region == "head":
        return ("goggles", "mask", "helmet")
    if region == "torso":
        return ("vest", "gloves", "mask")
    return ("vest", "goggles", "gloves", "helmet", "mask", "safety_shoes")
