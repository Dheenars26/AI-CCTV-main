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
import cv2

from app.config.settings import settings
from app.detection.base import BaseDetector, DetectionResult, BoundingBox
from app.utils.logger import logger

# Global model cache and thread lock to guarantee model is loaded & pre-fused ONCE safely across pipeline threads
_YOLO_MODEL_CACHE: Dict[str, Any] = {}
_YOLO_CACHE_LOCK = threading.Lock()

# Flame contour history for temporal flicker analysis
_FLAME_CONTOUR_HISTORY: Dict[str, List[float]] = {}
_FLAME_CONTOUR_LOCK = threading.Lock()


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

    def detect(self, image_bgr: Any, candidate_rois: Optional[List[BoundingBox]] = None, **kwargs: Any) -> List[DetectionResult]:
        """
        Executes YOLO object detection on frame matrix with candidate ROI-restricted computer-vision fallback.
        """
        if image_bgr is None or getattr(image_bgr, "size", 0) == 0:
            return []

        # Route to ONNX Inference Engine if active
        if self._onnx_runner is not None:
            fire_conf = getattr(settings, "FIRE_CONFIDENCE_THRESHOLD", 0.40)
            smoke_conf = getattr(settings, "SMOKE_CONFIDENCE_THRESHOLD", 0.35)
            # Restore baseline threshold to filter out low-confidence background noise (e.g., floor mats at 0.068)
            predict_conf = max(0.22, float(self.conf_threshold))

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
                class_threshold = fire_conf if label == "fire" else smoke_conf

                bw = x2 - x1
                bh = y2 - y1
                if bw <= 4 or bh <= 4 or w <= 0 or h <= 0:
                    continue

                # 1. Area filtering: Discard tiny noise and excessive smoke (> 40% frame area is rejected as model boundary noise)
                norm_area = (float(bw) * float(bh)) / float(w * h)
                min_area = 0.00008 if label == "fire" else 0.00020
                if norm_area < min_area:
                    continue
                if label == "smoke" and (norm_area > 0.40 or (bw / float(w) > 0.65 and bh / float(h) > 0.65)):
                    continue

                # 2. Aspect ratio filtering: Discard extreme slivers (overhead lights or frame edges)
                aspect_ratio = float(bw) / float(bh)
                if aspect_ratio > 5.5 or aspect_ratio < 0.18:
                    continue
                # Spreading fire line guard: Discard extreme horizontal bars (> 4.2)
                if label == "fire" and aspect_ratio > 4.2:
                    continue

                # 3. Chromaticity, thermal core and physics verification filter
                is_on_person = False
                if candidate_rois:
                    cx_norm = (float(x1) + float(x2)) / (2.0 * float(w))
                    cy_norm = (float(y1) + float(y2)) / (2.0 * float(h))
                    for roi in candidate_rois:
                        if roi.x_min <= cx_norm <= roi.x_max and (roi.y_min + (roi.y_max - roi.y_min) * 0.12) <= cy_norm <= roi.y_max:
                            is_on_person = True
                            break

                spatial_key = f"{round(float(x1) / float(w), 1)}_{round(float(y1) / float(h), 1)}"
                has_thermal_core = False
                smoke_metric_val = 0.0
                is_valid_smoke_val = False

                if label == "fire" and x2 > x1 and y2 > y1:
                    crop = image_bgr[y1:y2, x1:x2]
                    is_valid_flame, flame_ratio = YOLODetector._verify_flame_chromaticity(
                        crop,
                        is_person_torso=is_on_person,
                        spatial_key=spatial_key,
                        aspect_ratio=aspect_ratio
                    )
                    if not is_valid_flame and conf < 0.78:
                        continue
                    if is_valid_flame:
                        has_thermal_core = True
                        conf = min(0.98, round(conf + 0.25, 3))
                        class_threshold = max(0.22, class_threshold - 0.15)

                elif label == "smoke" and x2 > x1 and y2 > y1:
                    if is_on_person and conf < 0.90:
                        # Worker clothing suppression: white shirts, jackets, or hardhats on workers are not smoke plumes
                        continue
                    # Floor mat / carpet suppression: wide horizontal rectangle on or near bottom floor
                    is_floor_plane = (float(y2) / float(h)) >= 0.90 and (float(bw) / float(max(1, bh))) > 1.2
                    if not is_floor_plane and (float(y2) / float(h)) >= 0.92:
                        crop_g = cv2.cvtColor(image_bgr[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
                        if float(np.std(crop_g)) < 22.0:
                            is_floor_plane = True
                    if is_floor_plane:
                        continue
                    crop = image_bgr[y1:y2, x1:x2]
                    is_valid_smoke, smoke_metric = YOLODetector._verify_smoke_dispersion(crop)
                    if not is_valid_smoke and conf < 0.72:
                        continue
                    if is_valid_smoke:
                        is_valid_smoke_val = True
                        smoke_metric_val = smoke_metric
                        conf = max(min(0.96, round(conf + 0.45, 3)), 0.75)
                        class_threshold = max(0.20, class_threshold - 0.10)

                if conf < class_threshold:
                    continue

                detections.append(DetectionResult(
                    label=label,
                    confidence=conf,
                    bbox=bbox,
                    metadata={
                        "inference_time_ms": inf_time_ms,
                        "device": self.device,
                        "engine": "ONNXYOLORunner",
                        "raw_pixel_coords": [x1, y1, x2, y2],
                        "has_thermal_core": has_thermal_core,
                        "smoke_metric": smoke_metric_val,
                        "is_valid_smoke": is_valid_smoke_val
                    }
                ))

            enable_hsv = getattr(settings, "YOLO_ENABLE_HSV_FALLBACK", True)
            if enable_hsv:
                hsv_dets = self._detect_color_hsv(image_bgr, candidate_rois=candidate_rois)
                detections = YOLODetector._fuse_detections(detections, hsv_dets, fire_conf, smoke_conf)

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
            predict_conf = max(0.22, float(self.conf_threshold))

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

                    # Area & aspect ratio filtering (> 40% frame area is rejected as model boundary noise)
                    norm_area = (float(bw) * float(bh)) / float(w * h)
                    min_area = 0.00008 if matched_label == "fire" else 0.00020
                    if norm_area < min_area:
                        continue
                    if matched_label == "smoke" and (norm_area > 0.40 or (bw / float(w) > 0.65 and bh / float(h) > 0.65)):
                        continue
                    aspect_ratio = float(bw) / float(bh)
                    if aspect_ratio > 5.5 or aspect_ratio < 0.18:
                        continue
                    # Spreading fire line guard: Discard extreme horizontal bars (> 4.2)
                    if matched_label == "fire" and aspect_ratio > 4.2:
                        continue

                    # -------------------------------------------------------------
                    # Accuracy Enhancement: Chromaticity & Physics Verification Filter
                    # -------------------------------------------------------------
                    is_on_person = False
                    if candidate_rois:
                        cx_norm = (float(x1) + float(x2)) / (2.0 * float(w))
                        cy_norm = (float(y1) + float(y2)) / (2.0 * float(h))
                        for roi in candidate_rois:
                            if roi.x_min <= cx_norm <= roi.x_max and (roi.y_min + (roi.y_max - roi.y_min) * 0.12) <= cy_norm <= roi.y_max:
                                is_on_person = True
                                break

                    spatial_key = f"{round(float(x1) / float(w), 1)}_{round(float(y1) / float(h), 1)}"
                    has_thermal_core = False
                    smoke_metric_val = 0.0
                    is_valid_smoke_val = False

                    if matched_label == "fire" and rx2 > rx1 and ry2 > ry1:
                        crop = image_bgr[ry1:ry2, rx1:rx2]
                        is_valid_flame, flame_ratio = YOLODetector._verify_flame_chromaticity(
                            crop,
                            is_person_torso=is_on_person,
                            spatial_key=spatial_key,
                            aspect_ratio=aspect_ratio
                        )
                        if not is_valid_flame and confidence < 0.78:
                            continue
                        if is_valid_flame:
                            has_thermal_core = True
                            confidence = min(0.98, round(confidence + 0.25, 3))
                            class_threshold = max(0.22, class_threshold - 0.15)

                    elif matched_label == "smoke" and rx2 > rx1 and ry2 > ry1:
                        if is_on_person and confidence < 0.90:
                            continue
                        # Floor mat / carpet suppression: wide horizontal rectangle on or near bottom floor
                        is_floor_plane = (float(ry2) / float(h)) >= 0.90 and (float(bw) / float(max(1, bh))) > 1.2
                        if not is_floor_plane and (float(ry2) / float(h)) >= 0.92:
                            crop_g = cv2.cvtColor(image_bgr[ry1:ry2, rx1:rx2], cv2.COLOR_BGR2GRAY)
                            if float(np.std(crop_g)) < 22.0:
                                is_floor_plane = True
                        if is_floor_plane:
                            continue
                        crop = image_bgr[ry1:ry2, rx1:rx2]
                        is_valid_smoke, smoke_metric = YOLODetector._verify_smoke_dispersion(crop)
                        if not is_valid_smoke and confidence < 0.72:
                            continue
                        if is_valid_smoke:
                            is_valid_smoke_val = True
                            smoke_metric_val = smoke_metric
                            confidence = max(min(0.96, round(confidence + 0.45, 3)), 0.75)
                            class_threshold = max(0.20, class_threshold - 0.10)

                    if confidence < class_threshold:
                        continue

                    norm_bbox = BoundingBox(
                        x_min=max(0.0, min(1.0, x1 / w)),
                        y_min=max(0.0, min(1.0, y1 / h)),
                        x_max=max(0.0, min(1.0, x2 / w)),
                        y_max=max(0.0, min(1.0, y2 / h))
                    )

                    det_res = DetectionResult(
                        label=matched_label,
                        confidence=confidence,
                        bbox=norm_bbox,
                        metadata={
                            "inference_time_ms": inference_time_ms,
                            "device": self.device,
                            "half_fp16": self.half,
                            "raw_pixel_coords": [int(x1), int(y1), int(x2), int(y2)]
                        }
                    )
                    detections.append(det_res)

            # Run computer vision color & thermal fallback ONLY in mock fallback mode or when explicitly enabled in settings
            enable_hsv = getattr(settings, "YOLO_ENABLE_HSV_FALLBACK", True)
            if self._is_mock_fallback:
                hsv_dets = self._detect_color_hsv(image_bgr, candidate_rois=candidate_rois)
                detections.extend(hsv_dets)
            elif enable_hsv:
                hsv_dets = self._detect_color_hsv(image_bgr, candidate_rois=candidate_rois)
                detections = YOLODetector._fuse_detections(detections, hsv_dets, fire_conf, smoke_conf)

            return detections

        except Exception as e:
            logger.error(f"YOLODetector: Inference error on frame: {str(e)}")
            return self._detect_color_hsv(image_bgr, candidate_rois=None) if self._is_mock_fallback else []

    @staticmethod
    def _verify_flame_chromaticity(
        crop_bgr: np.ndarray,
        is_person_torso: bool = False,
        spatial_key: Optional[str] = None,
        aspect_ratio: float = 1.0
    ) -> Tuple[bool, float]:
        """
        Validates flame candidates using HSV chromaticity, desaturated thermal cores, 
        and explicit cold red pigment suppression.
        """
        import cv2
        if crop_bgr is None or crop_bgr.size < 16:
            return False, 0.0

        try:
            h, w = crop_bgr.shape[:2]
            total_pixels = h * w
            if total_pixels < 16:
                return False, 0.0

            hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
            b, g, r = cv2.split(crop_bgr)
            h_ch, s, v = cv2.split(hsv)

            # 1. Broad Flame Color Mask (Red/Orange/Yellow hues)
            mask_red1 = cv2.inRange(hsv, np.array([0, 70, 85]), np.array([10, 255, 255]))
            mask_red2 = cv2.inRange(hsv, np.array([170, 70, 85]), np.array([180, 255, 255]))
            mask_orange = cv2.inRange(hsv, np.array([11, 55, 95]), np.array([38, 255, 255]))

            flame_mask = cv2.bitwise_or(cv2.bitwise_or(mask_red1, mask_red2), mask_orange)
            flame_pixel_count = cv2.countNonZero(flame_mask)
            ratio = float(flame_pixel_count) / float(total_pixels)

            # 2. Cold Red Pigment Filtering (Red dustbins, red cones, red doors, books, folders)
            # Detect cold red plastic (S > 115, B < 105, R < 180). Reject if cold ratio > 0.40.
            cold_plastic_mask = (s > 115) & (b < 105) & (r < 180)
            cold_pixel_count = np.count_nonzero(cold_plastic_mask & (flame_mask > 0))
            cold_ratio = float(cold_pixel_count) / float(max(1, flame_pixel_count))
            if cold_ratio > 0.40:
                return False, 0.0

            # 3. Constrained Thermal Emission Core Check (Genuine Blackbody Emission)
            # Require genuine blackbody emission: R >= 220, G >= 180, B >= 135, V >= 180
            thermal_core_mask = (r >= 220) & (g >= 180) & (b >= 135) & (v >= 180)
            # Use a tight 2x2 morphological opening kernel on core mask to prevent mask bleed into adjacent white desks
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            contained_core = cv2.morphologyEx(thermal_core_mask.astype(np.uint8), cv2.MORPH_OPEN, kernel)
            dilated_flame = cv2.dilate(flame_mask, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
            valid_core = cv2.bitwise_and(contained_core, dilated_flame)
            core_pixel_count = cv2.countNonZero(valid_core)
            core_ratio = core_pixel_count / float(max(1, flame_pixel_count))
            has_core = (core_pixel_count >= 2) and (core_ratio >= 0.005)

            # Rejection 1: Min flame ratio (early/small distant flames allow 0.002 if incandescent core present)
            min_ratio = 0.002 if has_core else 0.008
            if ratio < min_ratio:
                return False, ratio

            # Cold red pigments reflect red but absorb green (G/R < 0.25). Combustion blackbody radiation emits substantial green
            if flame_pixel_count > 0:
                mean_r_fl = float(np.mean(r[flame_mask > 0]))
                mean_g_fl = float(np.mean(g[flame_mask > 0]))
                if mean_r_fl > 100.0 and (mean_g_fl / max(1.0, mean_r_fl)) < 0.25 and not has_core:
                    return False, 0.0

            # Rejections for worker torso clothing and flat reflection strips
            if is_person_torso and not has_core:
                return False, 0.0

            ycrcb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2YCrCb)
            y_ch, cr, cb = cv2.split(ycrcb)
            std_y = float(np.std(y_ch[flame_mask > 0])) if flame_pixel_count > 5 else 0.0
            std_cr = float(np.std(cr[flame_mask > 0])) if flame_pixel_count > 5 else 0.0

            # Static painted orange/red object rejection (t-shirts, traffic cones, flat painted wood)
            if not has_core and (std_y < 7.0 or std_cr < 4.5):
                return False, 0.0

            if aspect_ratio > 2.8 and (not has_core or std_y < 7.0):
                return False, 0.0

            # Rejection of cool white/blue vehicular headlights and electric lightbulbs with no thermal turbulence
            if flame_pixel_count > 0:
                mean_cr = float(np.mean(cr[flame_mask > 0]))
                mean_cb = float(np.mean(cb[flame_mask > 0]))
                mean_b_all = float(np.mean(b[flame_mask > 0]))
                if (mean_b_all >= 165.0) and (abs(mean_cr - mean_cb) < 7.0 or std_y < 8.0):
                    return False, 0.0

            # Temporal flicker tracking for static traffic cones / signs
            if spatial_key:
                with _FLAME_CONTOUR_LOCK:
                    history = _FLAME_CONTOUR_HISTORY.setdefault(spatial_key, [])
                    history.append(float(flame_pixel_count))
                    if len(history) > 6:
                        history.pop(0)
                    if len(history) >= 4:
                        mean_hist = float(np.mean(history))
                        if mean_hist > 0:
                            flicker_var = (max(history) - min(history)) / mean_hist
                            if flicker_var < 0.015 and not has_core:
                                return False, 0.0

            # 4. Confidence Score Weighting
            chroma_score = min(1.0, ratio * 2.5)
            if has_core:
                return True, max(ratio, min(1.0, chroma_score + 0.25))
            elif chroma_score > 0.40 and std_y >= 7.0 and std_cr >= 4.5:
                return True, max(ratio, chroma_score * 0.70)

            return False, ratio
        except Exception:
            return False, 0.0

    @staticmethod
    def _verify_smoke_dispersion(crop_bgr: np.ndarray) -> Tuple[bool, float]:
        """
        Validates candidate smoke bounding box:
        Genuine smoke exhibits:
        1. Low-to-moderate saturation (S <= 75), rejecting vibrant clothing or safety equipment.
        2. Soft volumetric intensity variance (pixel_std in [10.0, 75.0]), rejecting flat painted walls/floors.
        3. Dual-band luminance: White/gray smoke (Y in [85, 245]) and dark/black smoke (Y in [18, 85]).
        4. Achromatic balance: Smoke scatters light neutrally: |R-G| <= 18, |G-B| <= 18, |R-B| <= 22.
        5. Edge softness vs architectural geometry: Diffuse dispersion vs sharp rigid door/window lines.
        """
        import cv2
        if crop_bgr is None or crop_bgr.size < 16:
            return True, 1.0

        try:
            h, w = crop_bgr.shape[:2]
            if h < 8 or w < 8:
                return False, 0.0

            # Resize if large for fast analysis
            if max(h, w) > 256:
                scale = 256.0 / float(max(h, w))
                crop_eval = cv2.resize(crop_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
            else:
                crop_eval = crop_bgr

            hsv = cv2.cvtColor(crop_eval, cv2.COLOR_BGR2HSV)
            s = hsv[:, :, 1]
            total_px = float(s.size)

            # High saturation check: Reject crops dominated by highly vibrant objects (bright orange cones, signs, high-vis vests)
            high_sat_ratio = float(np.sum(s > 85)) / total_px
            if high_sat_ratio > 0.65:
                return False, 0.0

            # Texture variance check: Flat walls and floors have low std (< 10.0 in daylight, < 5.0 in dark scenes)
            # Dense black hydrocarbon smoke absorbs light uniformly (allow min_std down to 3.5 for dark smoke)
            gray = cv2.cvtColor(crop_eval, cv2.COLOR_BGR2GRAY)
            pixel_std = float(np.std(gray))
            mean_gray = float(np.mean(gray))
            min_std = 2.5 if mean_gray < 50.0 else (2.8 if mean_gray < 75.0 else 3.0)
            if pixel_std < min_std:
                # Flat uniform surface (drywall, ceiling tile, tabletop)
                return False, 0.0

            # Achromatic neutrality check: Works for both white/gray smoke and dark/black smoke
            # Evaluated specifically on candidate low/moderate-saturation smoke pixels to ignore background furniture/clothing
            smoke_eval_mask = (s <= 85)
            if np.sum(smoke_eval_mask) < 16:
                return False, 0.0
            mean_b = float(np.mean(crop_eval[:, :, 0][smoke_eval_mask]))
            mean_g = float(np.mean(crop_eval[:, :, 1][smoke_eval_mask]))
            mean_r = float(np.mean(crop_eval[:, :, 2][smoke_eval_mask]))
            # Allow warm ambient lighting (incandescent / sodium / sunset) with tolerance up to 42/48
            if abs(mean_r - mean_g) > 42.0 or abs(mean_g - mean_b) > 42.0 or abs(mean_r - mean_b) > 48.0:
                # Strongly tinted surface (colored wall, wood, foliage)
                return False, 0.0

            # Brown/Amber Dust Cloud Rejection (sweeping, forklift dust, construction sand)
            # Dust has warm amber hue (H in [15..35], S > 35) and Cr > 138
            mean_hue = float(np.mean(hsv[:, :, 0]))
            mean_sat = float(np.mean(s))
            ycrcb_eval = cv2.cvtColor(crop_eval, cv2.COLOR_BGR2YCrCb)
            mean_cr_val = float(np.mean(ycrcb_eval[:, :, 1]))
            if (15.0 <= mean_hue <= 35.0) and mean_sat > 35.0 and mean_cr_val > 138.0:
                return False, 0.0

            # Rejection: Moving Shadows on Floor (Shadows darken surface but preserve sharp floor lines/cracks)
            # Turbid smoke diffuses and blurs high frequencies
            if 35.0 <= mean_gray <= 115.0:
                laplacian = cv2.Laplacian(gray, cv2.CV_64F)
                lap_var = float(laplacian.var())
                sharp_edges = cv2.Canny(gray, 50, 150)
                sharp_edge_density = float(np.sum(sharp_edges > 0)) / total_px
                if sharp_edge_density > 0.070 and lap_var > 130.0:
                    # Sharp floor texture is preserved unattenuated -> Surface shadow, not smoke!
                    return False, 0.0

            # Edge density check: Solid geometric objects have dense sharp lines; smoke is diffuse
            edges = cv2.Canny(gray, 30, 100)
            edge_density = float(np.sum(edges > 0)) / total_px
            if edge_density > 0.32:
                return False, 0.0

            # Architectural straight-line rejection (doors, windows, desk boundaries)
            min_line_len = max(16, int(min(crop_eval.shape[:2]) * 0.40))
            lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=30, minLineLength=min_line_len, maxLineGap=4)
            if lines is not None and len(lines) >= 2:
                # Prominent collinear architectural lines on flat surface (door frame, window, desk)
                return False, 0.0

            # Rejection: Flat bright white surfaces (paper, whiteboard, plastic cups, white drywall):
            # Pure white objects have high luminance (mean_gray > 205) and low-to-moderate variance (< 18.0)
            if mean_gray > 205.0 and pixel_std < 18.0:
                return False, 0.0

            # Rejection: Sharp perimeter contrast (solid rectangular cutouts like paper, books, whiteboards)
            # Smoke has diffuse feathering boundaries; paper and solid objects have sharp step edges at borders
            h_crop, w_crop = crop_eval.shape[:2]
            if min(h_crop, w_crop) >= 24:
                b_width = max(2, int(min(h_crop, w_crop) * 0.08))
                border_mask = np.zeros((h_crop, w_crop), dtype=bool)
                border_mask[:b_width, :] = True
                border_mask[-b_width:, :] = True
                border_mask[:, :b_width] = True
                border_mask[:, -b_width:] = True

                sobelx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
                sobely = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
                grad_mag = np.sqrt(sobelx**2 + sobely**2)
                border_grad = float(np.mean(grad_mag[border_mask])) if np.any(border_mask) else 0.0
                inner_grad = float(np.mean(grad_mag[~border_mask])) if np.any(~border_mask) else 0.0
                if border_grad > 40.0 and (border_grad / max(1.0, inner_grad)) > 2.0:
                    return False, 0.0

            return True, 1.0 - (float(np.sum(s > 75)) / total_px)
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
            flame_bgr_cond = (r >= 140) & ((r_i + 10) >= g_i) & ((r_i > b_i + 12) | ((r >= 170) & (g >= 140)))
            flame_bgr_mask = flame_bgr_cond.astype(np.uint8) * 255

            # Fire condition 2: HSV red, orange, and golden-yellow flame hues with high brightness
            mask_fire_red1 = cv2.inRange(hsv, np.array([0, 35, 110]), np.array([38, 255, 255]))
            mask_fire_red2 = cv2.inRange(hsv, np.array([165, 35, 110]), np.array([180, 255, 255]))
            mask_hsv_fire = cv2.bitwise_or(mask_fire_red1, mask_fire_red2)

            # Fire condition 3: White-hot luminous core (MUST be enveloped by flame colors, not isolated white shirts/switches)
            white_hot_mask = cv2.inRange(hsv, np.array([0, 0, 175]), np.array([180, 65, 255]))
            white_hot_bgr = (r >= 180) & (g >= 155) & (b >= 120)
            white_hot_mask = cv2.bitwise_and(white_hot_mask, white_hot_bgr.astype(np.uint8) * 255)

            # Enforce that white cores must touch actual flame hues
            dilated_flame = cv2.dilate(mask_hsv_fire, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
            valid_white_core = cv2.bitwise_and(white_hot_mask, dilated_flame)

            # Combined flame candidate mask
            raw_flame_mask = cv2.bitwise_or(cv2.bitwise_and(mask_hsv_fire, flame_bgr_mask), valid_white_core)
            raw_flame_mask = cv2.bitwise_and(raw_flame_mask, cv2.bitwise_not(wood_mask.astype(np.uint8) * 255))
            
            # Subtract skin and vest
            intense_core = cv2.inRange(hsv, np.array([0, 45, 205]), np.array([35, 255, 255]))
            exclusion_to_apply = cv2.bitwise_and(cv2.bitwise_or(skin_mask, vest_mask), cv2.bitwise_not(intense_core))
            mask_fire = cv2.bitwise_and(raw_flame_mask, cv2.bitwise_not(exclusion_to_apply))

            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            mask_fire = cv2.morphologyEx(mask_fire, cv2.MORPH_OPEN, kernel)
            mask_fire = cv2.morphologyEx(mask_fire, cv2.MORPH_DILATE, kernel)

            contours, _ = cv2.findContours(mask_fire, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            min_fire_area = max(10, int(proc_total_pixels * 0.00007))

            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area >= min_fire_area:
                    x, y, cw, ch = cv2.boundingRect(cnt)
                    aspect_ratio = float(cw) / float(ch) if ch > 0 else 1.0

                    # Reject frame edge noise slivers
                    if (float(x) / proc_w < 0.015 or float(x + cw) / proc_w > 0.985 or float(y) / proc_h < 0.015 or float(y + ch) / proc_h > 0.985) and area < 80:
                        continue

                    if 0.18 <= aspect_ratio <= 4.2:
                        crop = proc_bgr[y:y+ch, x:x+cw]
                        cx_norm = (float(x) + float(cw) / 2.0) / float(proc_w)
                        cy_norm = (float(y) + float(ch) / 2.0) / float(proc_h)
                        is_torso = False
                        if candidate_rois:
                            for roi in candidate_rois:
                                if roi.x_min <= cx_norm <= roi.x_max and (roi.y_min + (roi.y_max - roi.y_min) * 0.12) <= cy_norm <= roi.y_max:
                                    is_torso = True
                                    break

                        spatial_key = f"{round(cx_norm, 1)}_{round(cy_norm, 1)}"
                        is_valid_flame, flame_ratio = YOLODetector._verify_flame_chromaticity(
                            crop,
                            is_person_torso=is_torso,
                            spatial_key=spatial_key,
                            aspect_ratio=aspect_ratio
                        )
                        if not is_valid_flame:
                            continue

                        norm_bbox = BoundingBox(
                            x_min=max(0.0, min(1.0, float(x) / float(proc_w))),
                            y_min=max(0.0, min(1.0, float(y) / float(proc_h))),
                            x_max=max(0.0, min(1.0, float(x + cw) / float(proc_w))),
                            y_max=max(0.0, min(1.0, float(y + ch) / float(proc_h)))
                        )
                        b_cr, g_cr, r_cr = cv2.split(crop)
                        hsv_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
                        v_crop, s_crop = hsv_crop[:, :, 2], hsv_crop[:, :, 1]
                        real_core = (v_crop >= 225) & (b_cr >= 140) & (g_cr >= 160) & (s_crop <= 75)
                        core_cnt = int(np.sum(real_core))

                        conf = min(0.95, 0.74 + min(0.20, (area / proc_total_pixels) * 2.5))
                        detections.append(
                            DetectionResult(
                                label="fire",
                                confidence=round(conf, 2),
                                bbox=norm_bbox,
                                metadata={
                                    "detection_engine": "OpenCV-MultiChannel-Thermal-Fire-Detector",
                                    "area_pixels": int(area),
                                    "flame_ratio": round(flame_ratio, 3),
                                    "has_thermal_core": True,
                                    "core_pixels": core_cnt
                                }
                            )
                        )

            # 5. Smoke Detection (Dual-Mode: White/Gray Smoke & Dark/Black Hydrocarbon Smoke)
            rg_diff = cv2.absdiff(r, g)
            gb_diff = cv2.absdiff(g, b)
            rb_diff = cv2.absdiff(r, b)

            # Dark / Black Hydrocarbon Smoke (Electrical/Rubber/Fuel Burning)
            rgb_balanced_dark = (rg_diff <= 18) & (gb_diff <= 18) & (rb_diff <= 24) & (r >= 12) & (r < 90)
            mask_hsv_dark = cv2.inRange(hsv, np.array([0, 0, 12], dtype=np.uint8), np.array([180, 60, 90], dtype=np.uint8))
            mask_dark_smoke = cv2.bitwise_and(mask_hsv_dark, rgb_balanced_dark.astype(np.uint8) * 255)

            # White / Light Gray Smoke (with warm lighting tolerance)
            rgb_balanced_white = (rg_diff <= 22) & (gb_diff <= 22) & (rb_diff <= 28) & (r >= 70) & (r <= 245)
            mask_hsv_white = cv2.inRange(hsv, np.array([0, 0, 70], dtype=np.uint8), np.array([180, 60, 245], dtype=np.uint8))
            raw_white_smoke = cv2.bitwise_and(mask_hsv_white, rgb_balanced_white.astype(np.uint8) * 255)

            raw_white_ratio = float(np.sum(raw_white_smoke > 0)) / float(proc_total_pixels)
            if raw_white_ratio > 0.35:
                # White/neutral background room: exclude flat walls, isolate regions with diffuse plume texture
                gray_proc = cv2.cvtColor(proc_bgr, cv2.COLOR_BGR2GRAY)
                blur_mean = cv2.blur(gray_proc.astype(np.float32), (15, 15))
                blur_sqr = cv2.blur(gray_proc.astype(np.float32) ** 2, (15, 15))
                loc_std = np.sqrt(np.maximum(0, blur_sqr - blur_mean ** 2))
                smoke_tex = (loc_std >= 5.0) & (loc_std <= 40.0)
                mask_white_smoke = cv2.bitwise_and(raw_white_smoke, smoke_tex.astype(np.uint8) * 255)
            else:
                mask_white_smoke = raw_white_smoke

            mask_smoke = cv2.bitwise_or(mask_white_smoke, mask_dark_smoke)
            mask_smoke = cv2.bitwise_and(mask_smoke, cv2.bitwise_not(skin_mask))
            mask_smoke = cv2.bitwise_and(mask_smoke, cv2.bitwise_not(vest_mask))

            kernel_smk = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            mask_smoke = cv2.morphologyEx(mask_smoke, cv2.MORPH_OPEN, kernel_smk)
            mask_smoke = cv2.morphologyEx(mask_smoke, cv2.MORPH_DILATE, kernel_smk)

            smoke_contours, _ = cv2.findContours(mask_smoke, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            min_smoke_area = max(50, int(proc_total_pixels * 0.00035))

            for cnt in smoke_contours:
                area = cv2.contourArea(cnt)
                if area >= min_smoke_area:
                    x, y, cw, ch = cv2.boundingRect(cnt)
                    aspect_ratio = float(cw) / float(ch) if ch > 0 else 1.0
                    norm_smoke_area = (float(cw) * float(ch)) / float(proc_w * proc_h)
                    if norm_smoke_area > 0.40 or (area / float(proc_total_pixels)) > 0.40:
                        continue
                    if cw < proc_w * 0.85 and ch < proc_h * 0.85 and 0.22 <= aspect_ratio <= 3.2:
                        smoke_crop = proc_bgr[y:y+ch, x:x+cw]
                        is_valid_smoke, smoke_metric = YOLODetector._verify_smoke_dispersion(smoke_crop)
                        if not is_valid_smoke:
                            continue

                        norm_bbox = BoundingBox(
                            x_min=max(0.0, min(1.0, float(x) / float(proc_w))),
                            y_min=max(0.0, min(1.0, float(y) / float(proc_h))),
                            x_max=max(0.0, min(1.0, float(x + cw) / float(proc_w))),
                            y_max=max(0.0, min(1.0, float(y + ch) / float(proc_h)))
                        )
                        conf = min(0.92, 0.70 + min(0.22, (area / proc_total_pixels) * 2.0))
                        detections.append(
                            DetectionResult(
                                label="smoke",
                                confidence=round(conf, 2),
                                bbox=norm_bbox,
                                metadata={
                                    "detection_engine": "OpenCV-MultiChannel-Smoke-Detector",
                                    "area_pixels": int(area),
                                    "smoke_metric": round(smoke_metric, 3),
                                    "is_valid_smoke": True
                                }
                            )
                        )

        except Exception as e:
            logger.warning(f"YOLODetector: Exception during HSV fire/smoke detection: {str(e)}")

        return detections

    @staticmethod
    def _fuse_detections(
        yolo_detections: List[DetectionResult],
        hsv_detections: List[DetectionResult],
        fire_threshold: float,
        smoke_threshold: float
    ) -> List[DetectionResult]:
        """
        Fuses deep learning YOLO detections with multi-spectral computer vision detections.
        Strict Consensus Only: HSV chromaticity candidates must ONLY be used to boost or
        validate existing YOLO model bounding boxes (IoU > 0.20).
        Standalone HSV candidate injection is completely prohibited.
        """
        fused: List[DetectionResult] = list(yolo_detections)
        for h_det in hsv_detections:
            matched_idx = -1
            for idx, y_det in enumerate(yolo_detections):
                if y_det.label.lower() == h_det.label.lower():
                    iou = y_det.bbox.iou(h_det.bbox)
                    # Strict consensus: only boost existing YOLO box if IoU > 0.20
                    if iou > 0.20:
                        matched_idx = idx
                        break

            if matched_idx >= 0:
                target = fused[matched_idx]
                target.confidence = min(0.99, round(max(target.confidence, h_det.confidence) + 0.12, 4))
                target.metadata["fused_engines"] = ["YOLOv8", h_det.metadata.get("detection_engine", "OpenCV-CV")]
                target.metadata["consensus_boost"] = 0.12
                target.metadata["hsv_validated"] = True
            # Standalone HSV candidate injection completely stripped out to prevent sunlight gaps from creating false fire boxes

        return fused

    @staticmethod
    def calculate_ppe_status_anchor(
        person_bbox: Tuple[int, int, int, int],
        frame_dimensions: Tuple[int, int],
        text_size: Tuple[int, int],
        padding: Tuple[int, int] = (12, 6)
    ) -> Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int]]:
        """
        Dynamically calculates anchor coordinates for PPE status text overlays
        (e.g., 'Worker #101 | MISSING: GLASSES') attaching to the upper boundary of
        the detected person bounding box without clipping outside the image ROI.

        :param person_bbox: (x1, y1, x2, y2) in pixel coordinates.
        :param frame_dimensions: (width, height) of the camera frame.
        :param text_size: (tw, th) rendered text width and height.
        :param padding: (pad_x, pad_y) badge internal padding.
        :return: ((badge_x1, badge_y1), (badge_x2, badge_y2), (text_x, text_y))
        """
        x1, y1, x2, y2 = person_bbox
        w, h = frame_dimensions
        tw, th = text_size
        pad_x, pad_y = padding
        badge_w = tw + pad_x * 2
        badge_h = th + pad_y * 2 + 2

        # Dynamically attach to upper boundary of detected person bounding box.
        # If sufficient headroom above person box, anchor right above top boundary;
        # otherwise clamp cleanly inside the upper ROI boundary to avoid clipping.
        if y1 >= badge_h + 8:
            badge_y1 = y1 - badge_h - 4
            badge_y2 = y1 - 4
        else:
            badge_y1 = max(4, y1 + 4)
            badge_y2 = min(h - 4, badge_y1 + badge_h)

        badge_x1 = max(4, min(x1, w - badge_w - 4))
        badge_x2 = min(w - 4, badge_x1 + badge_w)
        text_pos = (badge_x1 + pad_x, badge_y1 + pad_y + th)
        return (badge_x1, badge_y1), (badge_x2, badge_y2), text_pos

    @staticmethod
    def validate_person_ppe_roi(
        item_label: str,
        item_bbox: BoundingBox,
        person_bbox: BoundingBox
    ) -> bool:
        """
        Maintains glass and vest state consistency by keeping safety vest and safety glasses
        detection checks localized strictly to the upper-torso and facial regions of the cropped person bounding box.

        :param item_label: Detected PPE label ('vest', 'goggles', 'glasses', etc.).
        :param item_bbox: Normalized BoundingBox of detected equipment item.
        :param person_bbox: Normalized BoundingBox of parent detected person.
        :return: True if equipment is within expected anatomical region, False otherwise.
        """
        item_l = item_label.lower().strip()
        p_h = max(1e-4, person_bbox.y_max - person_bbox.y_min)
        item_cy = (item_bbox.y_min + item_bbox.y_max) / 2.0
        rel_y = (item_cy - person_bbox.y_min) / p_h

        # Safety glasses / goggles: strictly localized to facial region (top 38% of person bounding box)
        if any(g in item_l for g in ["goggles", "glasses", "spectacles", "eyewear"]):
            return -0.05 <= rel_y <= 0.38

        # Safety vest: strictly localized to upper-torso region (between 12% and 82% of person bounding box)
        if any(v in item_l for v in ["vest", "jacket", "hivis"]):
            return 0.12 <= rel_y <= 0.82

        return True

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
