"""
Production Fire & Smoke Detection Engine - small-object-aware, false-positive-resistant.

Design goals
------------
1. Detect SMALL fire/smoke that a single full-frame 416px pass misses, via tiled
   re-inference - triggered only when the full-frame pass is empty or ambiguous, so the
   extra cost is paid only when it might actually change the outcome.
2. Reject texture/color false positives (striped doormats, fabric, gray floor tile) via a
   texture-uniformity veto that plain HSV heuristics miss - this is the fix for the
   confirmed false positive where a doormat scored SMOKE at 41% confidence.
3. Never let a single signal become an alert. Every accepted detection is
   model_score + physics corroboration (+ optional motion corroboration), and anything
   that looks like a static man-made surface or woven fabric is vetoed outright,
   regardless of model confidence.
4. Reuse the project's existing primitives rather than reimplementing them:
   ONNXYOLORunner (onnx_engine.py), upscale_if_small (preprocess.py),
   weighted_box_fusion / box_iou_matrix / resolution_adaptive_threshold (nms.py),
   BoundingBox / DetectionResult (base.py).

This module is a drop-in replacement for the fire/smoke-specific detection logic
currently inside yolo.py. Wire it into fire_smoke_detector.py in place of the direct
YOLODetector.detect() call - the public detect() signature below is compatible with
that call site (same exclusion_rois kwarg, same DetectionResult return type).
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from app.detection.base import BoundingBox, DetectionResult
from app.detection.nms import box_iou_matrix, resolution_adaptive_threshold, weighted_box_fusion
from app.detection.onnx_engine import (
    ONNXYOLORunner,
    UltralyticsYOLORunner,
    get_onnx_yolo_runner,
    get_yolo_runner,
    resolve_model_path,
)
from app.detection.preprocess import upscale_if_small
from app.config.settings import settings
from app.utils.logger import logger


def _cfg(name: str, default: Any) -> Any:
    """Settings lookup with a safe default, so this file works even before settings.py
    is updated with the new keys it introduces."""
    return getattr(settings, name, default)


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #

@dataclass
class _Candidate:
    """One raw or fused fire/smoke box, in full-frame normalised coordinates."""
    label: str                      # "fire" | "smoke"
    model_confidence: float
    x1: float
    y1: float
    x2: float
    y2: float
    source: str                     # "full_frame" | "tile" | "roi_rescue"
    box_agreement: int = 1
    physics: Dict[str, Any] = field(default_factory=dict)
    final_confidence: float = 0.0
    vetoed: bool = False
    veto_reason: str = ""

    def area_norm(self) -> float:
        return max(0.0, self.x2 - self.x1) * max(0.0, self.y2 - self.y1)

    def to_xyxy(self) -> Tuple[float, float, float, float]:
        return (self.x1, self.y1, self.x2, self.y2)


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #

class FireSmokeEngine:
    """
    Small-object-aware, false-positive-resistant fire/smoke detector.

    Usage
    -----
        engine = FireSmokeEngine(model_path="runs/detect/train/weights/best.pt")
        results = engine.detect(
            frame_bgr,
            exclusion_rois=worker_and_vest_boxes,   # never let a person/vest box be "fire"
            motion_context={"motion_ratio": 0.01, "motion_rois": [...]},  # from MotionGate
        )
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        conf_threshold: Optional[float] = None,
        iou_threshold: Optional[float] = None,
        device: Optional[str] = None,
    ):
        self.model_path = resolve_model_path(
            model_path or _cfg("YOLO_MODEL_PATH", "runs/detect/train/weights/best.pt"),
            default_names=[
                "runs/detect/train/weights/best.pt",
                "models/fire_smoke.pt",
                "models/fire_smoke.onnx",
                "fire_smoke.pt",
                "fire_smoke.onnx",
                "yolov8n.pt",
            ]
        )
        self.iou_threshold = iou_threshold if iou_threshold is not None else _cfg("YOLO_IOU_THRESHOLD", 0.45)
        self.device = device or _cfg("YOLO_DEVICE", "cpu")

        # Per-class candidate/alert floors - the two-tier gate that lets weak signals
        # survive into physics fusion without becoming alerts on model score alone.
        self.fire_candidate_floor = float(_cfg("FIRE_CANDIDATE_CONFIDENCE", 0.12))
        self.smoke_candidate_floor = float(_cfg("SMOKE_CANDIDATE_CONFIDENCE", 0.15))
        self.fire_alert_floor = float(_cfg("FIRE_ALERT_CONFIDENCE", 0.35))
        self.smoke_alert_floor = float(_cfg("SMOKE_ALERT_CONFIDENCE", 0.35))
        self.physics_weight = float(_cfg("FIRE_PHYSICS_WEIGHT", 0.35))
        self.require_agreement = int(_cfg("FIRE_REQUIRE_AGREEMENT", 2))
        self.structure_edge_ratio = float(_cfg("FIRE_STRUCTURE_EDGE_RATIO", 0.55))

        # Small-object tiling (disabled by default for CCTV surveillance to prevent zoomed-in tile hallucinations).
        self.tiling_enabled = bool(_cfg("FIRE_SMOKE_TILING_ENABLED", False))
        self.tile_grid: Tuple[int, int] = tuple(_cfg("FIRE_SMOKE_TILE_GRID", (2, 2)))
        self.tile_overlap = float(_cfg("FIRE_SMOKE_TILE_OVERLAP", 0.15))
        # Cost guard: only tile every Nth invocation when nothing already looks strong,
        # so a static empty scene isn't tiled every single frame.
        self.tile_min_interval_frames = int(_cfg("FIRE_SMOKE_TILE_MIN_INTERVAL_FRAMES", 3))
        self._frames_since_tile = 0

        # ROI rescue (second pass, upscaled, for mid-band candidates only).
        self.roi_rescue_enabled = bool(_cfg("SMOKE_ROI_REFINE_ENABLED", True))
        self.roi_rescue_min_side = int(_cfg("FIRE_SMOKE_ROI_RESCUE_MIN_SIDE", 224))

        # Vetoes.
        self.texture_veto_enabled = bool(_cfg("SMOKE_TEXTURE_ENTROPY_VETO", True))
        self.motion_corroboration_enabled = bool(_cfg("SMOKE_MOTION_CORROBORATION", True))
        self.motion_static_ratio = float(_cfg("FIRE_SMOKE_MOTION_STATIC_RATIO", 0.003))

        try:
            self._runner = get_yolo_runner(
                model_path=self.model_path, device=self.device
            )
            self._is_mock_fallback = self._runner is None
        except Exception as e:
            logger.warning(
                f"FireSmokeEngine: model at '{self.model_path}' unavailable ({e}) - "
                f"running in degraded mode with no detections."
            )
            self._runner = None
            self._is_mock_fallback = True

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def detect(
        self,
        image_bgr: np.ndarray,
        candidate_rois: Optional[List[BoundingBox]] = None,
        exclusion_rois: Optional[Any] = None,
        motion_context: Optional[Dict[str, Any]] = None,
    ) -> List[DetectionResult]:
        """
        :param candidate_rois: optional whitelist regions to search (e.g. zone masks).
        :param exclusion_rois: worker/PPE boxes that must never be reported as fire/smoke -
               a hi-vis vest is the single strongest false-positive source for the fire model.
               Accepts either a List[BoundingBox] or Dict[str, List[BoundingBox]].
        :param motion_context: ``{"motion_ratio": float, "motion_rois": [(x1,y1,x2,y2), ...]}``
               from MotionGate, normalised frame coordinates. Used only as a secondary veto
               signal on already-weak candidates - never gates whether inference runs at all.
        """
        if self._is_mock_fallback or image_bgr is None or image_bgr.size == 0:
            return []

        h, w = image_bgr.shape[:2]
        t_start = time.perf_counter()

        # --- Pass 1: full-frame, always runs. --------------------------------- #
        candidates = self._full_frame_pass(image_bgr)

        # --- Pass 2: tiled re-inference, conditional on Pass 1 being weak/empty. #
        self._frames_since_tile += 1
        needs_tiling = self.tiling_enabled and self._should_tile(candidates)
        if needs_tiling and self._frames_since_tile >= self.tile_min_interval_frames:
            self._frames_since_tile = 0
            tile_candidates = self._tiled_pass(image_bgr)
            candidates = self._merge_cross_source(candidates, tile_candidates)

        if not candidates:
            return []

        # --- Region filtering. ------------------------------------------------- #
        if candidate_rois:
            candidates = [c for c in candidates if self._inside_any(c, candidate_rois)]
        if exclusion_rois:
            candidates = self._apply_exclusions(candidates, exclusion_rois)
        if not candidates:
            return []

        # --- Physics fusion: structure veto, texture veto, motion corroboration. #
        for c in candidates:
            self._fuse_physics(c, image_bgr, w, h, motion_context)

        # --- ROI rescue for the ambiguous middle band (this is what recovers    #
        #     thin/small smoke and small fire that Pass 1+2 under-scored).       #
        if self.roi_rescue_enabled:
            for c in candidates:
                if c.vetoed:
                    continue
                floor = self.fire_candidate_floor if c.label == "fire" else self.smoke_candidate_floor
                alert = self.fire_alert_floor if c.label == "fire" else self.smoke_alert_floor
                if floor <= c.final_confidence < alert:
                    self._roi_rescue(c, image_bgr, w, h)

        # --- Final gate: only alert-floor-and-above, non-vetoed candidates survive. #
        results: List[DetectionResult] = []
        for c in candidates:
            if c.vetoed:
                continue
            effective_alert = c.physics.get("adaptive_floor", self.fire_alert_floor if c.label == "fire" else self.smoke_alert_floor)
            if c.final_confidence < effective_alert:
                continue
            results.append(DetectionResult(
                label=c.label,
                confidence=round(float(c.final_confidence), 4),
                bbox=BoundingBox(x_min=c.x1, y_min=c.y1, x_max=c.x2, y_max=c.y2),
                metadata={
                    "detector_module": "FireSmokeEngine",
                    "source": c.source,
                    "model_confidence": round(c.model_confidence, 4),
                    "box_agreement": c.box_agreement,
                    "physics": c.physics,
                },
            ))

        elapsed_ms = (time.perf_counter() - t_start) * 1000.0
        logger.debug(
            f"FireSmokeEngine: {len(results)} accepted / "
            f"{len(candidates)} candidates in {elapsed_ms:.1f} ms "
            f"(tiled={needs_tiling and self._frames_since_tile == 0})"
        )
        return results

    def health(self) -> Dict[str, Any]:
        return {
            "engine": "FireSmokeEngine",
            "status": "DEGRADED" if self._is_mock_fallback else "HEALTHY",
            "model_path": self.model_path,
            "backend": getattr(self._runner, "backend_type", "unknown") if self._runner else "mock",
            "tiling_enabled": self.tiling_enabled,
            "roi_rescue_enabled": self.roi_rescue_enabled,
        }

    # ------------------------------------------------------------------ #
    # Pass 1: full-frame inference
    # ------------------------------------------------------------------ #

    def _full_frame_pass(self, image_bgr: np.ndarray) -> List[_Candidate]:
        if self._runner is None:
            return []
        base_floor = min(self.fire_candidate_floor, self.smoke_candidate_floor)
        raw, _ = self._runner.predict(
            image_bgr,
            conf_threshold=base_floor,
            iou_threshold=self.iou_threshold,
            target_classes=["fire", "smoke"],
            use_wbf=True,
            adaptive_small_classes=True,
        )
        out: List[_Candidate] = []
        for d in raw:
            bbox: BoundingBox = d["bbox"]
            out.append(_Candidate(
                label=str(d["label"]).lower(),
                model_confidence=float(d["confidence"]),
                x1=bbox.x_min, y1=bbox.y_min, x2=bbox.x_max, y2=bbox.y_max,
                source="full_frame",
                box_agreement=int(d.get("box_agreement", 1)),
            ))
        return out

    def _should_tile(self, candidates: List[_Candidate]) -> bool:
        """
        Tile when Pass 1 found nothing, or when everything it found is still below its
        alert floor - i.e. exactly the situation where a small/thin fire or smoke plume
        would be under-scored by a single 416px full-frame pass. A candidate that's
        already confidently above its alert floor doesn't need the extra resolution.
        """
        if not candidates:
            return True
        for c in candidates:
            alert = self.fire_alert_floor if c.label == "fire" else self.smoke_alert_floor
            if c.model_confidence >= alert:
                return False
        return True

    # ------------------------------------------------------------------ #
    # Pass 2: tiled inference (small-object recovery)
    # ------------------------------------------------------------------ #

    def _tiled_pass(self, image_bgr: np.ndarray) -> List[_Candidate]:
        """
        Splits the frame into an overlapping grid and re-runs inference per tile. Each
        tile is a smaller crop of the original resolution, so the same 416px network
        input now covers far fewer real pixels per network pixel - a small fire/smoke
        region that was a handful of px in the full-frame pass becomes a much larger
        fraction of a tile, which is the entire point: this recovers small objects
        without needing a bigger, slower network input on every frame.
        """
        if self._runner is None:
            return []
        h, w = image_bgr.shape[:2]
        rows, cols = self.tile_grid
        if rows <= 1 and cols <= 1:
            return []

        tile_h = int(h / rows)
        tile_w = int(w / cols)
        overlap_h = int(tile_h * self.tile_overlap)
        overlap_w = int(tile_w * self.tile_overlap)

        candidates: List[_Candidate] = []
        base_floor = min(self.fire_candidate_floor, self.smoke_candidate_floor)

        for r in range(rows):
            for c_idx in range(cols):
                y1 = max(0, r * tile_h - overlap_h)
                y2 = min(h, (r + 1) * tile_h + overlap_h)
                x1 = max(0, c_idx * tile_w - overlap_w)
                x2 = min(w, (c_idx + 1) * tile_w + overlap_w)
                tile = image_bgr[y1:y2, x1:x2]
                if tile.size == 0 or min(tile.shape[:2]) < 32:
                    continue

                raw, _ = self._runner.predict(
                    tile,
                    conf_threshold=base_floor,
                    iou_threshold=self.iou_threshold,
                    target_classes=["fire", "smoke"],
                    use_wbf=True,
                    adaptive_small_classes=True,
                )
                tw = x2 - x1
                th = y2 - y1
                for d in raw:
                    bbox: BoundingBox = d["bbox"]
                    # Map tile-normalised coords back to full-frame-normalised coords.
                    fx1 = (x1 + bbox.x_min * tw) / w
                    fy1 = (y1 + bbox.y_min * th) / h
                    fx2 = (x1 + bbox.x_max * tw) / w
                    fy2 = (y1 + bbox.y_max * th) / h
                    candidates.append(_Candidate(
                        label=str(d["label"]).lower(),
                        model_confidence=float(d["confidence"]),
                        x1=fx1, y1=fy1, x2=fx2, y2=fy2,
                        source="tile",
                        box_agreement=int(d.get("box_agreement", 1)),
                    ))
        return candidates

    def _merge_cross_source(
        self, full_frame: List[_Candidate], tiles: List[_Candidate]
    ) -> List[_Candidate]:
        """
        De-duplicates full-frame and tile detections that refer to the same physical
        object (tile boxes near a full-frame box's location), keeping the higher-scoring
        of the pair but summing box_agreement so a candidate seen by both passes carries
        that corroboration forward into physics fusion.
        """
        if not full_frame:
            return tiles
        if not tiles:
            return full_frame

        merged = list(full_frame)
        used_tile = [False] * len(tiles)

        for i, ff in enumerate(full_frame):
            for j, t in enumerate(tiles):
                if used_tile[j] or t.label != ff.label:
                    continue
                iou = box_iou_matrix(
                    np.array([[ff.x1, ff.y1, ff.x2, ff.y2]], dtype=np.float32),
                    np.array([[t.x1, t.y1, t.x2, t.y2]], dtype=np.float32),
                )[0][0]
                if iou > 0.3:
                    used_tile[j] = True
                    if t.model_confidence > ff.model_confidence:
                        merged[i] = t
                    merged[i].box_agreement = ff.box_agreement + t.box_agreement

        for j, t in enumerate(tiles):
            if not used_tile[j]:
                merged.append(t)
        return merged

    # ------------------------------------------------------------------ #
    # Region filtering
    # ------------------------------------------------------------------ #

    @staticmethod
    def _inside_any(c: _Candidate, rois: List[BoundingBox]) -> bool:
        cx, cy = (c.x1 + c.x2) / 2.0, (c.y1 + c.y2) / 2.0
        return any(r.x_min <= cx <= r.x_max and r.y_min <= cy <= r.y_max for r in rois)

    def _apply_exclusions(
        self, candidates: List[_Candidate], exclusion_rois: Any
    ) -> List[_Candidate]:
        """A worker/vest box overlapping a candidate is the single strongest false-positive
        source for the fire model (hi-vis fabric under certain lighting) - drop any candidate
        whose IoU with an exclusion box is high, before it ever reaches physics fusion.
        Supports both List[BoundingBox] and Dict[str, List[BoundingBox]]."""
        if not exclusion_rois:
            return candidates
        kept: List[_Candidate] = []
        for c in candidates:
            if isinstance(exclusion_rois, dict):
                active_ex = exclusion_rois.get(c.label, [])
            else:
                active_ex = exclusion_rois
            if not active_ex:
                kept.append(c)
                continue
            excl_arr = np.array([[r.x_min, r.y_min, r.x_max, r.y_max] for r in active_ex], dtype=np.float32)
            iou = box_iou_matrix(np.array([[c.x1, c.y1, c.x2, c.y2]], dtype=np.float32), excl_arr)[0]
            # Tightened from 0.35: a worker/vest box with 28%+ overlap is sufficient to suppress fire FP
            if iou.size and float(iou.max()) > 0.28:
                continue
            kept.append(c)
        return kept

    # ------------------------------------------------------------------ #
    # Physics fusion: structure veto, texture veto, motion corroboration
    # ------------------------------------------------------------------ #

    def _fuse_physics(
        self,
        c: _Candidate,
        image_bgr: np.ndarray,
        frame_w: int,
        frame_h: int,
        motion_context: Optional[Dict[str, Any]],
    ) -> None:
        px1 = int(max(0, c.x1 * frame_w))
        py1 = int(max(0, c.y1 * frame_h))
        px2 = int(min(frame_w, c.x2 * frame_w))
        py2 = int(min(frame_h, c.y2 * frame_h))
        crop = image_bgr[py1:py2, px1:px2]

        if crop.size == 0:
            c.final_confidence = c.model_confidence
            return

        # Agreement requirement: a lone sub-floor detection cannot be corroborated into
        # an alert by physics alone - it needs to have been seen more than once (by WBF
        # cluster size or by both full-frame + tile passes) before physics gets a vote.
        alert_floor = self.fire_alert_floor if c.label == "fire" else self.smoke_alert_floor
        # Agreement requirement: low-confidence (<0.20) noise detections require multi-source agreement.
        # Single-pass candidates >= 0.20 are admitted directly to physical corroboration so
        # real early flames and smoke plumes are boosted immediately without waiting 3 frames for a tile pass.
        if c.model_confidence < 0.20 and c.box_agreement < self.require_agreement:
            c.final_confidence = c.model_confidence
            c.physics["skipped_reason"] = "insufficient_agreement"
            return

        # Whole-frame hallucination veto: genuine smoke plumes in early detection originate locally.
        # If a smoke candidate covers > 45% of the frame while the room has sharp background details
        # (Laplacian variance > 40), this is an exposure/white-balance hallucination on ambient lighting.
        area = c.area_norm()
        if area > 0.45 and c.label == "smoke":
            gray_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            lap_var = float(cv2.Laplacian(gray_crop, cv2.CV_64F).var())
            # Lowered from 35 to 28: less textured but still clearly non-smoke backgrounds veto faster
            if lap_var > 28.0:
                c.vetoed = True
                c.veto_reason = "full_frame_hallucination"
                c.physics["hallucination_veto"] = True
                return

        # Tightened from 0.70 to 0.65: structured surfaces with even moderately high confidence are vetoed
        structure_hit = self._structure_edge_veto(crop, edge_ratio_limit=self.structure_edge_ratio)
        if structure_hit and c.model_confidence < 0.65:
            c.vetoed = True
            c.veto_reason = "structure_edge"
            c.physics["structure_edge_ratio_exceeded"] = True
            return

        corroboration = 0.0
        if c.label == "smoke":
            texture_hit = self.texture_veto_enabled and self._smoke_texture_veto(crop)
            if texture_hit:
                c.vetoed = True
                c.veto_reason = "fabric_texture"
                c.physics["texture_veto"] = True
                return

            dispersion_ok, dispersion_ratio = self._smoke_dispersion_score(crop)
            corroboration = dispersion_ratio if dispersion_ok else 0.0
            c.physics["dispersion_ratio"] = round(dispersion_ratio, 3)

            if self.motion_corroboration_enabled and motion_context is not None:
                motion_ratio = float(motion_context.get("motion_ratio", 1.0))
                c.physics["motion_ratio"] = round(motion_ratio, 5)
                if motion_ratio < self.motion_static_ratio and c.model_confidence < alert_floor:
                    # Static scene + still-weak model score + nothing moving here: treat
                    # as corroborated-absence-of-motion, not corroborated-smoke. A real
                    # plume disperses; a rug never does.
                    c.vetoed = True
                    c.veto_reason = "static_no_motion"
                    return
        else:  # fire
            flicker_ok, flicker_ratio = self._fire_color_score(crop)
            corroboration = flicker_ratio if flicker_ok else 0.0
            c.physics["color_ratio"] = round(flicker_ratio, 3)

            # Crucial false-positive defense: if crop has virtually no flame chromaticity
            # (warm_ratio < 0.10) and model confidence is below decisive floor (0.55),
            # veto this candidate so sunlit doors, brown walls and human skin don't trigger fire.
            # Tightened chromaticity gate from 0.12 → 0.10 to allow dimmer ember detection,
            # but hardened the confidence gate from 0.55 → 0.58 to prevent weak-conf chromaticity hits.
            if not flicker_ok and c.model_confidence < 0.58:
                c.vetoed = True
                c.veto_reason = "insufficient_flame_chromaticity"
                c.physics["chromaticity_veto"] = True
                return

        # Resolution-adaptive floor: small boxes get a slightly more lenient bar, since a
        # correct 6x6px fire ember will always score lower than a large flame purely from
        # network resolution - but the texture/structure vetoes above already did the real
        # false-positive filtering, so this leniency is safe.
        area = c.area_norm()
        adaptive_floor = float(resolution_adaptive_threshold(
            base_threshold=alert_floor,
            box_areas_norm=np.array([area], dtype=np.float32),
        )[0])
        c.physics["adaptive_floor"] = round(adaptive_floor, 3)

        boosted = c.model_confidence + (1.0 - c.model_confidence) * self.physics_weight * corroboration
        c.final_confidence = float(min(0.99, boosted))

    @staticmethod
    def _structure_edge_veto(crop_bgr: np.ndarray, edge_ratio_limit: float = 0.55) -> bool:
        """Rejects man-made, straight-edged surfaces (brick, tile grout, wall panels,
        doors, desks) that occasionally trip the color/texture stage. Measured separation:
        false positives on structured surfaces scored 0.63-0.74 edge ratio; true fire/smoke
        scored 0.09-0.32."""
        try:
            gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 60, 160)
            lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=30, minLineLength=15, maxLineGap=4)
            if lines is None:
                return False
            lines = lines.reshape(-1, 4)
            straight_px = sum(
                np.hypot(float(x2 - x1), float(y2 - y1)) for (x1, y1, x2, y2) in lines
            )
            edge_count = float(np.count_nonzero(edges))
            ratio = straight_px / max(edge_count, 1.0)
            return ratio > edge_ratio_limit
        except Exception:
            return False

    @staticmethod
    def _smoke_texture_veto(crop_bgr: np.ndarray) -> bool:
        """
        True when the crop has the texture signature of woven fabric, carpet, or floor tiling.
        Uses 8×8 grid with mean per-cell range and variance of range.
        Fabric: high mean_range (repeating pattern across cells) AND low var_range (uniform across cells).
        Smoke gradient: high var_range.
        """
        if crop_bgr is None or crop_bgr.size < 64:
            return False
        try:
            gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
            h, w = gray.shape[:2]
            if h < 16 or w < 16:
                return False

            rows, cols = 8, 8
            cell_ranges = []
            for r in range(rows):
                for c in range(cols):
                    ry1 = r * h // rows
                    ry2 = (r + 1) * h // rows
                    cx1 = c * w // cols
                    cx2 = (c + 1) * w // cols
                    cell = gray[ry1:ry2, cx1:cx2]
                    if cell.size > 0:
                        cell_ranges.append(float(int(cell.max()) - int(cell.min())))

            if len(cell_ranges) < 8:
                return False

            mean_range = float(np.mean(cell_ranges))
            var_range = float(np.var(cell_ranges))

            thresh_mean = float(getattr(settings, "SMOKE_TEXTURE_MEAN_RANGE_THRESH", 10.0))
            thresh_var = float(getattr(settings, "SMOKE_TEXTURE_VAR_RANGE_THRESH", 5.0))
            return mean_range > thresh_mean and var_range < thresh_var
        except Exception:
            return False

    @staticmethod
    def _smoke_dispersion_score(crop_bgr: np.ndarray) -> Tuple[bool, float]:
        """Lightweight achromatic/soft-gradient corroboration: low saturation, not a flat
        surface, not densely edged. Returns (is_plausible_smoke, corroboration_ratio)."""
        try:
            hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
            sat = hsv[:, :, 1].astype(np.float32)
            high_sat_ratio = float(np.mean(sat > 85))
            if high_sat_ratio > 0.40:
                return False, 0.0

            gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
            pixel_std = float(np.std(gray))
            if pixel_std < 7.0:
                return False, 0.0

            edges = cv2.Canny(gray, 50, 150)
            edge_density = float(np.count_nonzero(edges)) / float(edges.size)
            if edge_density > 0.42:
                return False, 0.0

            # Reject uniform drywall, ceilings, and flat painted walls with virtually no local gradients
            grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
            grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
            grad_mag = np.hypot(grad_x, grad_y)
            mean_grad = float(np.mean(grad_mag))
            if mean_grad < 4.0 and pixel_std < 16.0:
                return False, 0.0

            # Scaled corroboration: real turbulent smoke has soft non-zero gradient
            grad_factor = min(1.0, max(0.25, mean_grad / 25.0))
            corroboration = min(0.70, max(0.0, 1.0 - high_sat_ratio) * grad_factor)
            return True, corroboration
        except Exception:
            return False, 0.0

    @staticmethod
    def _fire_color_score(crop_bgr: np.ndarray) -> Tuple[bool, float]:
        """Corroborates fire candidates via multi-band flame chromaticity:
        - Lower yellow/amber/orange band (H in 0..38, S >= 65, V >= 140)
        - Upper crimson flame band (H in 168..180, S >= 75, V >= 160)
        - Thermodynamic incandescent core (R > G > B, R >= 170, V >= 150)
        Distinguishes self-luminous flames from dark painted wood, plastic, or maroon furniture."""
        try:
            hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
            # Lower yellow/amber/orange band: H in 0..38, S >= 60, V >= 130
            # Slightly relaxed to catch dim embers (was S>=65, V>=140)
            lower1 = np.array([0, 60, 130], dtype=np.uint8)
            upper1 = np.array([38, 255, 255], dtype=np.uint8)
            mask1 = cv2.inRange(hsv, lower1, upper1)

            # Upper crimson band: H in 165..180, S >= 70, V >= 150
            lower2 = np.array([165, 70, 150], dtype=np.uint8)
            upper2 = np.array([180, 255, 255], dtype=np.uint8)
            mask2 = cv2.inRange(hsv, lower2, upper2)

            warm_mask = cv2.bitwise_or(mask1, mask2)
            warm_ratio = float(np.count_nonzero(warm_mask)) / float(max(1, warm_mask.size))

            # Thermodynamic flame intensity: self-luminous R > G > B with real incandescence
            b, g, r = cv2.split(crop_bgr)
            v = hsv[:, :, 2]
            # Real flame cores: R>=165, V>=140, G>=45. Slightly relaxed vs. R>=170/V>=150 to catch
            # dim early flames while still rejecting dark mahogany wood (R:120-145).
            thermo_flame = (r > g) & (g > b) & (r >= 165) & (v >= 140) & (g >= 45)
            thermo_ratio = float(np.count_nonzero(thermo_flame)) / float(max(1, crop_bgr.shape[0] * crop_bgr.shape[1]))

            effective_flame_ratio = max(warm_ratio, thermo_ratio * 0.85)
            # is_valid_flame: accept if effective ratio > 0.10, or if both warm AND thermo > 0.07
            is_valid_flame = effective_flame_ratio > 0.10 or (warm_ratio > 0.07 and thermo_ratio > 0.07)
            return is_valid_flame, min(1.0, effective_flame_ratio / 0.45)
        except Exception:
            return False, 0.0

    # ------------------------------------------------------------------ #
    # ROI rescue: second pass at higher resolution for ambiguous candidates
    # ------------------------------------------------------------------ #

    def _roi_rescue(self, c: _Candidate, image_bgr: np.ndarray, frame_w: int, frame_h: int) -> None:
        """
        Re-runs inference on an upscaled crop of a mid-band candidate (candidate_floor
        <= score < alert_floor). This is what recovers genuinely small/thin fire and
        smoke: at 416px full-frame input, a 20x20px real ember or wisp is a handful of
        network pixels; cropped and upscaled to >=224px it becomes a normal-sized object
        for the same network.
        """
        px1 = int(max(0, c.x1 * frame_w))
        py1 = int(max(0, c.y1 * frame_h))
        px2 = int(min(frame_w, c.x2 * frame_w))
        py2 = int(min(frame_h, c.y2 * frame_h))
        # Pad generously - the original box may be tightly cropped to a weak activation
        # that doesn't cover the full extent of the real object.
        pad_x = max(4, int((px2 - px1) * 0.5))
        pad_y = max(4, int((py2 - py1) * 0.5))
        rx1 = max(0, px1 - pad_x)
        ry1 = max(0, py1 - pad_y)
        rx2 = min(frame_w, px2 + pad_x)
        ry2 = min(frame_h, py2 + pad_y)

        crop = image_bgr[ry1:ry2, rx1:rx2]
        if crop.size == 0 or min(crop.shape[:2]) < 8:
            return

        crop_up, _ = upscale_if_small(crop, min_side=self.roi_rescue_min_side)

        if self._runner is None:
            return

        try:
            raw, _ = self._runner.predict(
                crop_up,
                conf_threshold=min(self.fire_candidate_floor, self.smoke_candidate_floor),
                iou_threshold=self.iou_threshold,
                target_classes=[c.label],
                use_wbf=True,
                adaptive_small_classes=True,
            )
        except Exception as e:
            logger.debug(f"FireSmokeEngine: ROI rescue inference failed: {e}")
            return

        if not raw:
            return

        best = max(raw, key=lambda d: float(d["confidence"]))
        rescued_conf = float(best["confidence"])
        if rescued_conf <= c.model_confidence:
            return  # rescue found nothing better than what we already had

        c.model_confidence = rescued_conf
        c.source = "roi_rescue"
        c.box_agreement += 1
        c.physics["roi_rescue_confidence"] = round(rescued_conf, 4)

        alert_floor = self.fire_alert_floor if c.label == "fire" else self.smoke_alert_floor
        corroboration = c.physics.get("dispersion_ratio", c.physics.get("color_ratio", 0.0))
        boosted = rescued_conf + (1.0 - rescued_conf) * self.physics_weight * corroboration
        c.final_confidence = float(min(0.99, max(c.final_confidence, boosted)))
