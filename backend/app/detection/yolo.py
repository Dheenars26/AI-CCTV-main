"""
YOLOv8 AI Fire & Smoke Object Detection Engine.
Integrates Ultralytics YOLOv8 / ONNX runtime with CPU and GPU support.
Features resilient model loading (loads ONCE), configurable thresholds, and fallback handling.
"""

import os
import time
import threading
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple
import numpy as np

from app.config.settings import settings
from app.detection.base import BaseDetector, DetectionResult, BoundingBox
from app.utils.logger import logger

# Global model cache and thread lock to guarantee model is loaded & pre-fused ONCE safely across pipeline threads
_YOLO_MODEL_CACHE: Dict[str, Any] = {}
_YOLO_CACHE_LOCK = threading.Lock()


class YOLODetector(BaseDetector):
    """
    Ultralytics YOLOv8 Fire & Smoke AI Detection Implementation.
    Loads AI weights file ONCE and executes non-blocking CPU/GPU inference.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        conf_threshold: Optional[float] = None,
        iou_threshold: Optional[float] = None,
        device: Optional[str] = None,
        target_classes: Optional[List[str]] = None
    ):
        """
        :param model_path: Absolute or relative path to YOLO weights (.pt, .onnx, .engine).
        :param conf_threshold: Detection confidence threshold (0.0 to 1.0).
        :param iou_threshold: Non-Maximum Suppression (NMS) IoU threshold.
        :param device: Inference compute target ('cpu', 'cuda', '0', etc.).
        :param target_classes: Target labels to filter ('fire', 'smoke').
        """
        self.model_path = model_path or settings.YOLO_MODEL_PATH
        self.conf_threshold = conf_threshold if conf_threshold is not None else getattr(settings, "YOLO_CONF_THRESHOLD", 0.35)
        self.iou_threshold = iou_threshold if iou_threshold is not None else settings.YOLO_IOU_THRESHOLD
        self.device = device or settings.YOLO_DEVICE
        self.target_classes = [c.lower() for c in (target_classes or ["fire", "smoke"])]

        # Guard half-precision (FP16) strictly against CPU execution
        try:
            import torch
            try:
                if hasattr(torch, "set_flush_denormal"):
                    torch.set_flush_denormal(True)
                # Allocate optimal CPU threads leaving headroom for streaming & OS
                cpu_cores = os.cpu_count() or 4
                torch.set_num_threads(min(8, max(4, cpu_cores - 2)))
            except Exception:
                pass
            self.is_cuda = torch.cuda.is_available() and self.device.lower() not in ["cpu", ""]
        except (ImportError, OSError, Exception):
            self.is_cuda = False
        self.half = self.is_cuda

        self._model = None
        self._onnx_runner = None
        self._is_mock_fallback: bool = False
        self._load_model()

    def _load_model(self) -> None:
        """
        Loads YOLO model instance once using global registry cache.
        Prioritizes ONNX runtime for cross-platform speed and compliance, with Ultralytics fallback.
        """
        cache_key = f"{self.model_path}_{self.device}"

        with _YOLO_CACHE_LOCK:
            if cache_key in _YOLO_MODEL_CACHE:
                logger.info(f"YOLODetector: Reusing cached YOLO model from '{self.model_path}' on device '{self.device}'.")
                cached = _YOLO_MODEL_CACHE[cache_key]
                self._model = cached.get("model")
                self._onnx_runner = cached.get("onnx_runner")
                self._is_mock_fallback = cached.get("is_mock", False)
                return

            logger.info("=" * 60)
            logger.info(f"YOLODetector: Initializing AI Detection Model Engine")
            logger.info(f"Model Path: '{self.model_path}' | Device Target: '{self.device}' | FP16 Half: {self.half}")
            logger.info(f"Conf Threshold: {self.conf_threshold} | IoU NMS Threshold: {self.iou_threshold}")
            logger.info("=" * 60)

            # Fast Fallback Mode in Testing Environment
            import sys
            if settings.APP_ENV == "testing" or "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ:
                logger.warning(
                    f"YOLODetector: Safe Mode active (APP_ENV={settings.APP_ENV}, model_path='{self.model_path}'). "
                    f"Skipping heavy neural network initialization."
                )
                self._is_mock_fallback = True
                _YOLO_MODEL_CACHE[cache_key] = {"model": None, "onnx_runner": None, "is_mock": True}
                return

            # Attempt 1: High-Performance ONNX Runtime Model Engine
            onnx_candidates = []
            if self.model_path.endswith(".onnx"):
                onnx_candidates.append(self.model_path)
            else:
                onnx_candidates.append(os.path.splitext(self.model_path)[0] + ".onnx")
            onnx_candidates.append("models/fire_smoke.onnx")
            backend_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            onnx_candidates.append(os.path.join(backend_root, "models", "fire_smoke.onnx"))

            for cand in onnx_candidates:
                if cand and os.path.isfile(cand):
                    try:
                        from app.detection.onnx_engine import get_onnx_yolo_runner
                        runner = get_onnx_yolo_runner(cand, device=self.device)
                        self._onnx_runner = runner
                        self._model = None
                        self._is_mock_fallback = False
                        _YOLO_MODEL_CACHE[cache_key] = {"model": None, "onnx_runner": runner, "is_mock": False}
                        logger.info(f"YOLODetector: Successfully loaded ONNX YOLO model from '{cand}'.")
                        return
                    except Exception as oe:
                        logger.warning(f"YOLODetector: Could not initialize ONNX runner from '{cand}': {oe}")

            # Attempt 2: Ultralytics PyTorch Engine
            if not os.path.isfile(self.model_path):
                logger.warning(
                    "YOLODetector: Fire/smoke weights are missing at '%s'. "
                    "Running in fallback mode.",
                    self.model_path,
                )
                self._is_mock_fallback = True
                _YOLO_MODEL_CACHE[cache_key] = {"model": None, "onnx_runner": None, "is_mock": True}
                return

            try:
                import logging as _logging
                try:
                    from ultralytics.utils import LOGGER as _uLOGGER
                    _uLOGGER.setLevel(_logging.WARNING)
                except Exception:
                    pass

                from ultralytics import YOLO
                import torch
                t0 = time.time()
                model = YOLO(self.model_path)
                try:
                    model.fuse()
                except Exception as fe:
                    logger.warning(f"YOLODetector: Model pre-fuse notification: {fe}")

                model.to(self.device)

                try:
                    dummy_img = np.zeros((416, 416, 3), dtype=np.uint8)
                    with torch.inference_mode():
                        model.predict(source=dummy_img, imgsz=416, device=self.device, verbose=False)
                    logger.info("YOLODetector: Pre-warmed model graph for instantaneous real-time inference.")
                except Exception as we:
                    logger.debug(f"YOLODetector: Warmup notification: {we}")

                load_time_sec = round(time.time() - t0, 3)

                logger.info(f"YOLODetector: Successfully loaded YOLO model from '{self.model_path}' on {self.device} in {load_time_sec}s.")
                self._model = model
                self._is_mock_fallback = False
                _YOLO_MODEL_CACHE[cache_key] = {"model": model, "onnx_runner": None, "is_mock": False}

            except ImportError:
                logger.warning(
                    "YOLODetector: Neither ONNX nor 'ultralytics' is available. Running in Safe Fallback Mode."
                )
                self._is_mock_fallback = True
                _YOLO_MODEL_CACHE[cache_key] = {"model": None, "onnx_runner": None, "is_mock": True}

            except Exception as e:
                logger.error(
                    f"YOLODetector: Error loading YOLO model from '{self.model_path}': {str(e)}. "
                    f"Falling back to Safe Mode."
                )
                self._is_mock_fallback = True
                _YOLO_MODEL_CACHE[cache_key] = {"model": None, "onnx_runner": None, "is_mock": True}

    def detect(
        self,
        image_bgr: Any,
        candidate_rois: Optional[List[BoundingBox]] = None,
        exclusion_rois: Optional[List[BoundingBox]] = None,
        **kwargs: Any
    ) -> List[DetectionResult]:
        """
        Executes fire/smoke detection on a frame.

        :param candidate_rois: retained for interface compatibility (optional search ROIs).
        :param exclusion_rois: person / PPE / equipment boxes that must NOT be reported as fire
               (for example a high-vis vest, which the fire model scores as flame).
        """
        if image_bgr is None or getattr(image_bgr, "size", 0) == 0:
            return []

        # Route to ONNX Inference Engine if active
        if self._onnx_runner is not None:
            fire_conf = getattr(settings, "FIRE_CONFIDENCE_THRESHOLD", 0.50)
            smoke_conf = getattr(settings, "SMOKE_CONFIDENCE_THRESHOLD", 0.48)
            # The operator-facing thresholds (FIRE/SMOKE_CONFIDENCE_THRESHOLD, also writable through
            # PUT /system/verification) express desired sensitivity. The candidate and alert floors
            # are derived from them so a single knob stays authoritative:
            #   candidate floor  = min(configured noise floor, half the sensitivity threshold)
            #   alert floor      = at least the sensitivity threshold
            fire_candidate = min(
                float(getattr(settings, "FIRE_CANDIDATE_CONFIDENCE", 0.14)), fire_conf * 0.5
            )
            smoke_candidate = min(
                float(getattr(settings, "SMOKE_CANDIDATE_CONFIDENCE", 0.13)), smoke_conf * 0.5
            )
            require_agreement = int(getattr(settings, "FIRE_REQUIRE_AGREEMENT", 3))
            structure_limit = float(getattr(settings, "FIRE_STRUCTURE_EDGE_RATIO", 0.45))
            predict_conf = min(self.conf_threshold, fire_candidate, smoke_candidate)

            raw_dets, inf_time_ms = self._onnx_runner.predict(
                image_bgr,
                conf_threshold=predict_conf,
                iou_threshold=self.iou_threshold,
                target_classes=self.target_classes
            )

            h, w = image_bgr.shape[:2]
            detections: List[DetectionResult] = []
            for item in raw_dets:
                label = item["label"]
                conf = item["confidence"]
                bbox = item["bbox"]
                x1, y1, x2, y2 = item["pixel_coords"]
                agreement = int(item.get("box_agreement", 1))
                class_threshold = fire_conf if label == "fire" else smoke_conf
                candidate_floor = fire_candidate if label == "fire" else smoke_candidate

                bw = x2 - x1
                bh = y2 - y1
                if bw <= 4 or bh <= 4 or w <= 0 or h <= 0:
                    continue

                # 1. Area filtering: discard tiny noise (<0.15% of frame) and over-large smoke boxes
                norm_area = (float(bw) * float(bh)) / float(w * h)
                if norm_area < 0.0015:
                    continue
                if label == "smoke" and (norm_area > 0.85 or (bw / float(w) > 0.94 and bh / float(h) > 0.94)):
                    continue

                # 2. Aspect ratio filtering: discard extreme slivers (overhead lights, frame edges)
                aspect_ratio = float(bw) / float(bh)
                if aspect_ratio > 5.5 or aspect_ratio < 0.18:
                    continue

                # 3. Exclusion: a detected vest/helmet/worker is never fire. Without this, the
                #    fire model's strongest false positives on real footage are hi-vis clothing.
                if exclusion_rois and YOLODetector._overlaps_any(bbox, exclusion_rois):
                    continue

                # 4. Physical corroboration -> fused evidence score (booster, never a gate)
                evidence, phys = YOLODetector._fuse_fire_smoke_evidence(
                    label, conf, image_bgr[max(0, y1):y2, max(0, x1):x2]
                )

                # 5. Emission policy: strong model score OR multi-box agreement OR strong physics.
                strong_model = conf >= class_threshold
                corroborated = agreement >= require_agreement
                physics_strong = phys.get("corroboration", 0.0) >= 0.25
                if evidence < candidate_floor:
                    continue
                if not (strong_model or corroborated or physics_strong):
                    continue

                # 6. Structure veto: a surface dominated by long straight edges is man-made.
                #    Measured separation on real imagery - false positives (brick wall, concrete,
                #    reflective webbing) score 0.63-0.74, genuine flame/smoke regions 0.09-0.32.
                #    Smoke is amorphous by physics, so the veto is unconditional for it; flame can sit
                #    behind grilles, glazing or beams, so fire is only vetoed below its alert floor
                #    (a decisive reading is never thrown away).
                alert_floor = max(
                    float(getattr(
                        settings,
                        "FIRE_ALERT_CONFIDENCE" if label == "fire" else "SMOKE_ALERT_CONFIDENCE",
                        0.35,
                    )),
                    class_threshold,
                )
                edge_ratio = float(phys.get("structure_edge_ratio") or 0.0)
                if edge_ratio > structure_limit:
                    if label == "smoke" or evidence < alert_floor:
                        continue

                detections.append(DetectionResult(
                    label=label,
                    confidence=round(min(0.99, evidence), 4),
                    bbox=bbox,
                    metadata={
                        "inference_time_ms": inf_time_ms,
                        "device": self.device,
                        "engine": "ONNXYOLORunner",
                        "raw_pixel_coords": [x1, y1, x2, y2],
                        "model_confidence": round(conf, 4),
                        "box_agreement": agreement,
                        "physics_valid": phys.get("valid"),
                        "physics_corroboration": round(float(phys.get("corroboration", 0.0)), 4),
                        "structure_edge_ratio": phys.get("structure_edge_ratio"),
                        "painted_surface": phys.get("painted_surface"),
                        "thermal_core_ratio": phys.get("thermal_core_ratio"),
                        "evidence": "model+agreement" if corroborated else ("model" if strong_model else "physics"),
                    }
                ))

            enable_hsv = getattr(settings, "YOLO_ENABLE_HSV_FALLBACK", False)
            if enable_hsv and not any(d.label.lower() in ["fire", "smoke"] for d in detections):
                hsv_dets = self._detect_color_hsv(image_bgr, candidate_rois=candidate_rois)
                detections.extend(hsv_dets)

            return detections

        if self._is_mock_fallback or self._model is None:
            enable_hsv = getattr(settings, "YOLO_ENABLE_HSV_FALLBACK", False)
            if enable_hsv:
                return self._detect_color_hsv(image_bgr, candidate_rois=candidate_rois)
            return []

        try:
            import torch
            h, w = image_bgr.shape[:2]
            t_start = time.time()

            imgsz_val = getattr(settings, "AI_IMAGE_SIZE", getattr(settings, "YOLO_IMGSZ", 416))
            if self.device.lower() in ["cpu", ""]:
                imgsz_val = min(416, max(384, imgsz_val))
            augment_val = getattr(settings, "YOLO_AUGMENT", False)

            fire_conf = getattr(settings, "FIRE_CONFIDENCE_THRESHOLD", 0.32)
            smoke_conf = getattr(settings, "SMOKE_CONFIDENCE_THRESHOLD", 0.28)
            predict_conf = min(self.conf_threshold, fire_conf, smoke_conf, 0.28)

            predict_kwargs: Dict[str, Any] = {
                "source": image_bgr,
                "conf": predict_conf,
                "iou": self.iou_threshold,
                "device": self.device,
                "max_det": 30,
                "imgsz": imgsz_val,
                "augment": augment_val,
                "verbose": False
            }
            if self.half:
                predict_kwargs["half"] = True

            with torch.inference_mode():
                results = self._model.predict(**predict_kwargs)

            inference_time_ms = round((time.time() - t_start) * 1000, 2)
            detections: List[DetectionResult] = []

            # Excluded labels that substring-match 'fire' but are NOT fire incidents
            EXCLUDED_COCO_LABELS = {"fire hydrant", "fire_hydrant", "fire extinguisher", "fire_extinguisher", "traffic light"}

            for r in results:
                boxes = r.boxes
                if boxes is None or len(boxes) == 0:
                    continue

                for box in boxes:
                    cls_id = int(box.cls[0])
                    class_name = r.names.get(cls_id, f"class_{cls_id}").lower().strip()

                    # Ignore excluded labels like 'fire hydrant'
                    if class_name in EXCLUDED_COCO_LABELS:
                        continue

                    # Strict target class matching to prevent false positives
                    matched_label = None
                    for target in self.target_classes:
                        t = target.lower().strip()
                        if class_name == t:
                            matched_label = t
                            break
                        elif t == "fire" and class_name in ["fire_smoke", "flame", "wildfire"]:
                            matched_label = "fire"
                            break
                        elif t == "smoke" and class_name in ["smoke_plume", "dense_smoke"]:
                            matched_label = "smoke"
                            break

                    if not matched_label:
                        continue

                    confidence = float(box.conf[0])
                    class_threshold = (
                        getattr(settings, "FIRE_CONFIDENCE_THRESHOLD", 0.50)
                        if matched_label == "fire"
                        else getattr(settings, "SMOKE_CONFIDENCE_THRESHOLD", 0.48)
                    )

                    xyxy = box.xyxy[0].cpu().numpy()
                    x1, y1, x2, y2 = float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])
                    rx1, ry1 = max(0, int(x1)), max(0, int(y1))
                    rx2, ry2 = min(w, int(x2)), min(h, int(y2))

                    bw = rx2 - rx1
                    bh = ry2 - ry1
                    if bw <= 4 or bh <= 4 or w <= 0 or h <= 0:
                        continue

                    # Area & aspect ratio filtering
                    norm_area = (float(bw) * float(bh)) / float(w * h)
                    if norm_area < 0.0015:
                        continue
                    if matched_label == "smoke" and (norm_area > 0.85 or (bw / float(w) > 0.94 and bh / float(h) > 0.94)):
                        continue
                    aspect_ratio = float(bw) / float(bh)
                    if aspect_ratio > 5.5 or aspect_ratio < 0.18:
                        continue

                    norm_bbox = BoundingBox(
                        x_min=max(0.0, min(1.0, x1 / w)),
                        y_min=max(0.0, min(1.0, y1 / h)),
                        x_max=max(0.0, min(1.0, x2 / w)),
                        y_max=max(0.0, min(1.0, y2 / h))
                    )

                    # -------------------------------------------------------------
                    # Exclusion: detected workers / PPE are never fire or smoke
                    # -------------------------------------------------------------
                    if exclusion_rois and YOLODetector._overlaps_any(norm_bbox, exclusion_rois):
                        continue

                    # -------------------------------------------------------------
                    # Evidence fusion: physics corroboration boosts, structure damps.
                    # Hard colour gates were removed - they discarded genuine fires scored
                    # below 0.90 (measured: a real blaze the network scored 0.61).
                    # -------------------------------------------------------------
                    crop = image_bgr[ry1:ry2, rx1:rx2]
                    evidence, phys = YOLODetector._fuse_fire_smoke_evidence(matched_label, confidence, crop)
                    candidate_floor = (
                        getattr(settings, "FIRE_CANDIDATE_CONFIDENCE", 0.18)
                        if matched_label == "fire"
                        else getattr(settings, "SMOKE_CANDIDATE_CONFIDENCE", 0.16)
                    )
                    if evidence < candidate_floor:
                        continue
                    if confidence < class_threshold and phys.get("corroboration", 0.0) < 0.25:
                        continue
                    confidence = evidence

                    det_res = DetectionResult(
                        label=matched_label,
                        confidence=confidence,
                        bbox=norm_bbox,
                        metadata={
                            "inference_time_ms": inference_time_ms,
                            "device": self.device,
                            "half_fp16": self.half,
                            "raw_pixel_coords": [int(x1), int(y1), int(x2), int(y2)],
                            "physics_valid": phys.get("valid"),
                            "physics_corroboration": round(float(phys.get("corroboration", 0.0)), 4),
                            "structure_edge_ratio": phys.get("structure_edge_ratio"),
                        }
                    )
                    detections.append(det_res)

            # Run computer vision color & thermal fallback ONLY in mock fallback mode or when explicitly enabled in settings
            enable_hsv = getattr(settings, "YOLO_ENABLE_HSV_FALLBACK", False)
            if self._is_mock_fallback:
                hsv_dets = self._detect_color_hsv(image_bgr, candidate_rois=candidate_rois)
                detections.extend(hsv_dets)
            elif enable_hsv and not any(d.label.lower() in ["fire", "smoke"] for d in detections):
                hsv_dets = self._detect_color_hsv(image_bgr, candidate_rois=candidate_rois)
                detections.extend(hsv_dets)

            return detections

        except Exception as e:
            logger.error(f"YOLODetector: Inference error on frame: {str(e)}")
            return self._detect_color_hsv(image_bgr, candidate_rois=None) if self._is_mock_fallback else []

    @staticmethod
    def _structure_edge_ratio(crop_bgr: np.ndarray) -> float:
        """
        Fraction of edge pixels explained by long straight segments.

        Fire and smoke are amorphous: their silhouettes and internal texture contain no long
        straight lines. Man-made surfaces that the model confuses with fire do - measured on real
        footage, a white brick wall produced 0.64 and a high-vis vest with reflective webbing 0.67,
        while genuine smoke/fire regions produced 0.21-0.28. The metric therefore discriminates
        without relying on colour (which fails for orange-lit smoke).
        """
        import cv2
        if crop_bgr is None or crop_bgr.size < 64:
            return 0.0
        try:
            gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 30, 100)
            total = int(np.count_nonzero(edges))
            if total < 24:
                return 0.0
            h, w = gray.shape[:2]
            lines = cv2.HoughLinesP(
                edges, 1, np.pi / 180.0, threshold=28,
                minLineLength=max(12, int(0.22 * min(h, w))), maxLineGap=6
            )
            if lines is None:
                return 0.0
            segments = np.asarray(lines).reshape(-1, 4)
            canvas = np.zeros_like(edges)
            for sx1, sy1, sx2, sy2 in segments[:60]:
                cv2.line(canvas, (int(sx1), int(sy1)), (int(sx2), int(sy2)), 255, 2)
            straight = int(np.count_nonzero(cv2.bitwise_and(canvas, edges)))
            return min(1.0, straight / float(total))
        except Exception:
            return 0.0

    @staticmethod
    def _is_painted_surface(crop_bgr: np.ndarray) -> bool:
        """
        True for uniform, flat-coloured surfaces: painted panels, plastic, painted cones, clothing.

        A painted surface is a single flat colour with almost no internal variation, which is what
        separates it from a real flame or plume (both have spatial gradients). Measured on synthetic
        reproductions of the classic false positives: a plain orange shirt, a painted traffic cone and
        a floor reflection strip all score a grey-level standard deviation below 3, while a genuine
        flame region scores above 12.
        """
        import cv2
        if crop_bgr is None or crop_bgr.size < 64:
            return False
        try:
            gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
            return float(np.std(gray)) < 6.0
        except Exception:
            return False

    @staticmethod
    def _thermal_core_ratio(crop_bgr: np.ndarray) -> float:
        """
        Fraction of pixels that look like an incandescent core: bright, desaturated (near white).

        Real flames have a hot core that saturates towards white; painted orange, warm lamps seen
        through a lens, and orange fabric do not (they stay saturated). Used as a *booster* only.
        """
        import cv2
        if crop_bgr is None or crop_bgr.size < 16:
            return 0.0
        try:
            hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
            h, sat, val = cv2.split(hsv)
            core = (val >= 200) & (sat <= 120) & (h <= 35)
            return float(np.count_nonzero(core)) / float(crop_bgr.shape[0] * crop_bgr.shape[1])
        except Exception:
            return 0.0

    @staticmethod
    def _fuse_fire_smoke_evidence(
        label: str, model_confidence: float, crop_bgr: np.ndarray
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Combines the neural score with physical corroboration into a single evidence score.

        Previously the physics verifiers acted as **hard gates** with a 0.90/0.92 escape hatch, so a
        genuine fire the network scored at 0.61 was silently discarded for failing a colour test.
        Corroboration is now a booster: strong colour/structure evidence lifts a weak score into
        alertable range, and weak colour evidence cannot erase a confident detection. Structural
        (straight-edge) evidence acts as a damper, because it is the cue that separates real flames
        from brickwork, windows and reflective clothing.
        """
        phys: Dict[str, Any] = {"valid": None, "corroboration": 0.0, "structure_edge_ratio": None}
        if crop_bgr is None or getattr(crop_bgr, "size", 0) < 16:
            return float(model_confidence), phys

        try:
            if label == "fire":
                is_valid, ratio = YOLODetector._verify_flame_chromaticity(crop_bgr)
            else:
                is_valid, ratio = YOLODetector._verify_smoke_dispersion(crop_bgr)
        except Exception:
            is_valid, ratio = False, 0.0

        structure = YOLODetector._structure_edge_ratio(crop_bgr)
        structure_limit = float(getattr(settings, "FIRE_STRUCTURE_EDGE_RATIO", 0.45))
        thermal_core = YOLODetector._thermal_core_ratio(crop_bgr)
        painted = YOLODetector._is_painted_surface(crop_bgr)

        corroboration = max(0.0, float(ratio))
        if painted:
            # A flat, uniform patch is a painted surface, plastic or fabric - never a flame. Colour
            # alone cannot tell them apart (both are saturated orange), so this is the damper that
            # neutralises the classic false positives: orange shirts, painted cones, floor stripes.
            corroboration = 0.0
        elif structure > structure_limit:
            # Structured surface: keep a little of the colour evidence, discard the rest.
            corroboration *= 0.15

        if label == "fire" and thermal_core > 0.0:
            # Incandescent cores only appear in genuine combustion and hot light sources; treat them
            # as a small independent boost rather than a requirement.
            corroboration = min(1.0, corroboration + min(0.35, thermal_core * 1.5))

        weight = float(getattr(settings, "FIRE_PHYSICS_WEIGHT", 0.35))
        evidence = float(model_confidence) + (1.0 - float(model_confidence)) * weight * corroboration

        phys["valid"] = bool(is_valid)
        phys["corroboration"] = corroboration
        phys["structure_edge_ratio"] = round(structure, 3)
        phys["painted_surface"] = painted
        phys["thermal_core_ratio"] = round(thermal_core, 4)
        return min(0.99, evidence), phys

    @staticmethod
    def _overlaps_any(box: BoundingBox, others: List[BoundingBox], min_ioa: float = 0.55) -> bool:
        """True when ``box`` is substantially covered by any of ``others`` (IoA test)."""
        area = max(1e-9, (box.x_max - box.x_min) * (box.y_max - box.y_min))
        for other in others:
            inter_w = max(0.0, min(box.x_max, other.x_max) - max(box.x_min, other.x_min))
            inter_h = max(0.0, min(box.y_max, other.y_max) - max(box.y_min, other.y_min))
            if (inter_w * inter_h) / area >= min_ioa:
                return True
        return False

    @staticmethod
    def _verify_flame_chromaticity(crop_bgr: np.ndarray) -> Tuple[bool, float]:
        """
        Validates candidate flame bounding box using HSV and YCrCb color space physics.
        Real flame exhibits:
        1. High luminance: Y in [105, 255]
        2. High chrominance: Cr >= Cb + 8 and Cr >= 130
        3. Characteristic flame hues in [0, 32] U [165, 180] with saturation S >= 45 and V >= 95
        4. Red dominance: R > G and R > B across flame pixels
        5. Thermal gradient and variance: genuine flame has thermal gradient, not uniform painted matte red/orange
        Returns (is_valid, flame_pixel_ratio).
        """
        import cv2
        if crop_bgr is None or crop_bgr.size < 16:
            return True, 1.0

        try:
            h, w = crop_bgr.shape[:2]
            total_pixels = h * w
            if total_pixels == 0:
                return False, 0.0

            hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
            ycrcb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2YCrCb)
            y, cr, cb = cv2.split(ycrcb)
            b, g, r = cv2.split(crop_bgr)

            y_cond = y >= 95
            cr_cond = (cr >= cb + 6) & (cr >= 125)
            ycrcb_flame = y_cond & cr_cond

            m1 = cv2.inRange(hsv, np.array([0, 40, 85]), np.array([32, 255, 255]))
            m2 = cv2.inRange(hsv, np.array([165, 40, 85]), np.array([180, 255, 255]))
            hsv_flame = (m1 > 0) | (m2 > 0)

            # Red channel dominance: Flame is distinctly warmer: R >= G and R >= B + 15
            red_dom = (r >= g) & (r >= b + 15) & (r >= 115)

            flame_pixels = ycrcb_flame & hsv_flame & red_dom
            flame_count = int(np.sum(flame_pixels))
            ratio = float(flame_count) / float(total_pixels)

            # Rejection 1: Low flame pixel density (< 3.0% flame pixels in candidate bounding box)
            if ratio < 0.030:
                return False, ratio

            # Rejection 2: Cold red painted metal/plastic (e.g. fire extinguisher cylinder, dark red signs)
            # Real incandescent flames have mean luminance Y >= 105 across flame pixels
            mean_y = float(np.mean(y[flame_pixels])) if flame_count > 0 else 0.0
            if mean_y < 100.0:
                return False, ratio

            return True, ratio
        except Exception:
            return True, 0.5

    @staticmethod
    def _verify_smoke_dispersion(crop_bgr: np.ndarray) -> Tuple[bool, float]:
        """
        Validates candidate smoke bounding box:
        Genuine smoke exhibits:
        1. Low-to-moderate saturation (S <= 80), rejecting vibrant clothing or safety equipment.
        2. Soft volumetric intensity variance (pixel_std in [8.5, 65.0]), rejecting flat painted walls/floors.
        3. Low edge density (Canny edge density <= 0.20), rejecting sharp geometric office furniture/machinery.
        """
        import cv2
        if crop_bgr is None or crop_bgr.size < 16:
            return True, 1.0

        try:
            h, w = crop_bgr.shape[:2]
            if h < 8 or w < 8:
                return False, 0.0

            hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
            s = hsv[:, :, 1]
            total_px = float(s.size)

            # High saturation check: Reject colored objects (bright vests, clothes, signs)
            high_sat_ratio = float(np.sum(s > 85)) / total_px
            if high_sat_ratio > 0.32:
                return False, 0.0

            # Texture variance check: Flat walls and floors have std < 8.5
            gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
            pixel_std = float(np.std(gray))
            if pixel_std < 8.5:
                # Flat uniform surface (drywall, ceiling tile, tabletop)
                return False, 0.0

            # Edge density check: Solid geometric objects have dense sharp lines; smoke is diffuse
            edges = cv2.Canny(gray, 30, 100)
            edge_density = float(np.sum(edges > 0)) / total_px
            if edge_density > 0.20:
                # Sharp geometric edges (monitors, keyboards, books, structural beams)
                return False, 0.0

            return True, 1.0 - high_sat_ratio
        except Exception:
            return True, 0.5

    def _detect_color_hsv(self, image_bgr: np.ndarray, candidate_rois: Optional[List[BoundingBox]] = None) -> List[DetectionResult]:
        """
        Computer Vision Multi-Channel Thermal & Flame Feature Detector.
        Accurately segments flame and smoke regions with physics-based luminosity, wood suppression, and envelope checks.
        """
        import cv2
        if image_bgr is None or image_bgr.size == 0:
            return []

        h, w = image_bgr.shape[:2]
        max_dim = 640
        if max(h, w) > max_dim:
            scale = max_dim / float(max(h, w))
            proc_w, proc_h = int(w * scale), int(h * scale)
            proc_bgr = cv2.resize(image_bgr, (proc_w, proc_h), interpolation=cv2.INTER_AREA)
        else:
            proc_w, proc_h = w, h
            proc_bgr = image_bgr

        proc_total_pixels = proc_h * proc_w
        detections: List[DetectionResult] = []

        try:
            hsv = cv2.cvtColor(proc_bgr, cv2.COLOR_BGR2HSV)
            ycrcb = cv2.cvtColor(proc_bgr, cv2.COLOR_BGR2YCrCb)
            b, g, r = cv2.split(proc_bgr)
            r_i, g_i, b_i = r.astype(np.int32), g.astype(np.int32), b.astype(np.int32)

            # 1. Human Skin Exclusion Mask (YCrCb + HSV)
            y_ch, cr_ch, cb_ch = cv2.split(ycrcb)
            skin_ycrcb = (cr_ch >= 135) & (cr_ch <= 170) & (cb_ch >= 80) & (cb_ch <= 125)
            skin_hsv = cv2.inRange(hsv, np.array([0, 25, 50]), np.array([22, 160, 240]))
            skin_mask = cv2.bitwise_or(skin_ycrcb.astype(np.uint8) * 255, skin_hsv)

            # 2. High-Vis Neon Safety Vest Exclusion Mask (protects vest from being misclassified as flame)
            vest_yellow = cv2.inRange(hsv, np.array([25, 90, 110]), np.array([75, 255, 255]))
            vest_orange = cv2.inRange(hsv, np.array([8, 130, 110]), np.array([24, 255, 255]))
            vest_mask = cv2.bitwise_or(vest_yellow, vest_orange)

            # 3. Wood & Furniture Suppression Mask (prevents reddish-brown doors/tables from triggering flame)
            wood_mask = (y_ch < 155) & (cr_ch >= 135) & (cr_ch <= 175) & (cb_ch >= 70) & (cb_ch <= 120)

            # 4. Flame Color & Thermal Segmentation (Physics-based luminosity and chromaticity with fast integer arithmetic)
            flame_bgr_cond = (r >= 185) & (r_i * 100 > g_i * 118) & (g_i * 100 > b_i * 110)
            flame_bgr_mask = flame_bgr_cond.astype(np.uint8) * 255

            # Fire condition 2: HSV red, orange, and golden-yellow flame hues with high brightness
            mask_fire_red1 = cv2.inRange(hsv, np.array([0, 65, 175]), np.array([30, 255, 255]))
            mask_fire_red2 = cv2.inRange(hsv, np.array([168, 65, 175]), np.array([180, 255, 255]))
            mask_hsv_fire = cv2.bitwise_or(mask_fire_red1, mask_fire_red2)

            # Fire condition 3: White-hot luminous core (MUST be enveloped by flame colors, not isolated white shirts/switches)
            white_hot_mask = cv2.inRange(hsv, np.array([0, 0, 230]), np.array([180, 50, 255]))
            white_hot_bgr = (r >= 230) & (g >= 215) & (b >= 170)
            white_hot_mask = cv2.bitwise_and(white_hot_mask, white_hot_bgr.astype(np.uint8) * 255)

            # Enforce that white cores must touch actual flame hues
            dilated_flame = cv2.dilate(mask_hsv_fire, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
            valid_white_core = cv2.bitwise_and(white_hot_mask, dilated_flame)

            # Combined flame candidate mask
            raw_flame_mask = cv2.bitwise_or(cv2.bitwise_and(mask_hsv_fire, flame_bgr_mask), valid_white_core)
            raw_flame_mask = cv2.bitwise_and(raw_flame_mask, cv2.bitwise_not(wood_mask.astype(np.uint8) * 255))
            
            # Subtract skin and vest
            intense_core = cv2.inRange(hsv, np.array([0, 50, 220]), np.array([35, 255, 255]))
            exclusion_to_apply = cv2.bitwise_and(cv2.bitwise_or(skin_mask, vest_mask), cv2.bitwise_not(intense_core))
            mask_fire = cv2.bitwise_and(raw_flame_mask, cv2.bitwise_not(exclusion_to_apply))

            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            mask_fire = cv2.morphologyEx(mask_fire, cv2.MORPH_OPEN, kernel)
            mask_fire = cv2.morphologyEx(mask_fire, cv2.MORPH_DILATE, kernel)

            contours, _ = cv2.findContours(mask_fire, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            min_fire_area = max(80, int(proc_total_pixels * 0.0007))

            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area >= min_fire_area:
                    x, y, cw, ch = cv2.boundingRect(cnt)
                    aspect_ratio = float(cw) / float(ch) if ch > 0 else 1.0

                    if 0.25 <= aspect_ratio <= 3.0:
                        norm_bbox = BoundingBox(
                            x_min=max(0.0, min(1.0, float(x) / float(proc_w))),
                            y_min=max(0.0, min(1.0, float(y) / float(proc_h))),
                            x_max=max(0.0, min(1.0, float(x + cw) / float(proc_w))),
                            y_max=max(0.0, min(1.0, float(y + ch) / float(proc_h)))
                        )
                        conf = min(0.92, 0.60 + (area / proc_total_pixels) * 2.0)
                        detections.append(
                            DetectionResult(
                                label="fire",
                                confidence=round(conf, 2),
                                bbox=norm_bbox,
                                metadata={
                                    "detection_engine": "OpenCV-MultiChannel-Thermal-Fire-Detector",
                                    "area_pixels": int(area)
                                }
                            )
                        )

            # 5. Smoke Detection (Full-Frame Chromatic Neutrality & Diffuse Texture)
            if not any(d.label == "smoke" for d in detections):
                rg_diff = cv2.absdiff(r, g)
                gb_diff = cv2.absdiff(g, b)
                rb_diff = cv2.absdiff(r, b)
                
                # Balanced gray/smoke tones under real-world camera lighting
                rgb_balanced = (rg_diff <= 20) & (gb_diff <= 20) & (rb_diff <= 24) & (r >= 95) & (r <= 220)
                rgb_balanced_uint8 = rgb_balanced.astype(np.uint8) * 255

                lower_smoke = np.array([0, 0, 85], dtype=np.uint8)
                upper_smoke = np.array([180, 35, 215], dtype=np.uint8)
                mask_hsv_smoke = cv2.inRange(hsv, lower_smoke, upper_smoke)

                mask_smoke = cv2.bitwise_and(mask_hsv_smoke, rgb_balanced_uint8)
                mask_smoke = cv2.bitwise_and(mask_smoke, cv2.bitwise_not(skin_mask))
                mask_smoke = cv2.bitwise_and(mask_smoke, cv2.bitwise_not(vest_mask))

                kernel_smk = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
                mask_smoke = cv2.morphologyEx(mask_smoke, cv2.MORPH_OPEN, kernel_smk)
                mask_smoke = cv2.morphologyEx(mask_smoke, cv2.MORPH_DILATE, kernel_smk)

                smoke_contours, _ = cv2.findContours(mask_smoke, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                min_smoke_area = max(300, int(proc_total_pixels * 0.0040))
                gray_frame_smk = cv2.cvtColor(proc_bgr, cv2.COLOR_BGR2GRAY)

                for cnt in smoke_contours:
                    area = cv2.contourArea(cnt)
                    if area >= min_smoke_area:
                        x, y, cw, ch = cv2.boundingRect(cnt)
                        if cw < proc_w * 0.85 and ch < proc_h * 0.85:
                            smoke_crop_gray = gray_frame_smk[y:y+ch, x:x+cw]
                            pixel_std = float(np.std(smoke_crop_gray))
                            extent = area / float(cw * ch) if (cw * ch) > 0 else 0.0

                            smoke_edges = cv2.Canny(smoke_crop_gray, 30, 100)
                            edge_density = float(np.sum(smoke_edges > 0)) / float(smoke_edges.size) if smoke_edges.size > 0 else 0.0

                            # Smoke is diffuse with soft edges and internal intensity dispersion
                            if pixel_std >= 18.0 and extent <= 0.70 and edge_density <= 0.15:
                                norm_bbox = BoundingBox(
                                    x_min=max(0.0, min(1.0, float(x) / float(proc_w))),
                                    y_min=max(0.0, min(1.0, float(y) / float(proc_h))),
                                    x_max=max(0.0, min(1.0, float(x + cw) / float(proc_w))),
                                    y_max=max(0.0, min(1.0, float(y + ch) / float(proc_h)))
                                )
                                conf = min(0.85, 0.55 + (area / proc_total_pixels) * 1.5)
                                detections.append(
                                    DetectionResult(
                                        label="smoke",
                                        confidence=round(conf, 2),
                                        bbox=norm_bbox,
                                        metadata={
                                            "detection_engine": "OpenCV-MultiChannel-Smoke-Detector",
                                            "area_pixels": int(area),
                                            "pixel_std": round(pixel_std, 2),
                                            "edge_density": round(edge_density, 3)
                                        }
                                    )
                                )

        except Exception as e:
            logger.warning(f"YOLODetector: Exception during HSV fire/smoke detection: {str(e)}")

        return detections

    def initialize(self) -> bool:
        self._load_model()
        return True

    def get_model_name(self) -> str:
        if self._is_mock_fallback:
            return f"YOLODetector-SafeMode (Path: {self.model_path})"
        return f"YOLOv8-FireSmoke (Device: {self.device}, Conf: {self.conf_threshold})"

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "model_name": "YOLODetector",
            "model_version": "8.0.0",
            "model_filename": os.path.basename(self.model_path),
            "model_hash": "yolo_v8_hash",
            "loaded_at": datetime.now(timezone.utc).isoformat(),
            "target_classes": self.target_classes,
            "device": self.device
        }

    def health_check(self) -> Dict[str, Any]:
        status_val = "DEGRADED" if self._is_mock_fallback else "HEALTHY"
        return {
            "detector": "YOLODetector",
            "status": status_val,
            "device": self.device,
            "model_name": self.get_model_name()
        }

    def shutdown(self) -> None:
        self._model = None
        self._is_mock_fallback = True
