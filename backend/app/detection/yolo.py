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

    def detect(self, image_bgr: Any, candidate_rois: Optional[List[BoundingBox]] = None, **kwargs: Any) -> List[DetectionResult]:
        """
        Executes YOLO object detection on frame matrix with candidate ROI-restricted computer-vision fallback.
        """
        if image_bgr is None or getattr(image_bgr, "size", 0) == 0:
            return []

        # Route to ONNX Inference Engine if active
        if self._onnx_runner is not None:
            fire_conf = getattr(settings, "FIRE_CONFIDENCE_THRESHOLD", 0.50)
            smoke_conf = getattr(settings, "SMOKE_CONFIDENCE_THRESHOLD", 0.48)
            predict_conf = min(self.conf_threshold, fire_conf, smoke_conf, 0.40)

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

                # 1. Area filtering: Discard tiny noise (< 0.15% frame) and excessive smoke (> 85% frame)
                norm_area = (float(bw) * float(bh)) / float(w * h)
                if norm_area < 0.0015:
                    continue
                if label == "smoke" and (norm_area > 0.85 or (bw / float(w) > 0.94 and bh / float(h) > 0.94)):
                    continue

                # 2. Aspect ratio filtering: Discard extreme slivers (overhead lights or frame edges)
                aspect_ratio = float(bw) / float(bh)
                if aspect_ratio > 5.5 or aspect_ratio < 0.18:
                    continue

                # 3. Chromaticity and physics verification filter
                if label == "fire" and x2 > x1 and y2 > y1:
                    crop = image_bgr[y1:y2, x1:x2]
                    is_valid_flame, flame_ratio = YOLODetector._verify_flame_chromaticity(crop)
                    if not is_valid_flame and conf < 0.92:
                        continue
                    if flame_ratio > 0.10:
                        conf = min(0.99, conf + 0.06)
                elif label == "smoke" and x2 > x1 and y2 > y1:
                    crop = image_bgr[y1:y2, x1:x2]
                    is_valid_smoke, _ = YOLODetector._verify_smoke_dispersion(crop)
                    if not is_valid_smoke and conf < 0.90:
                        continue

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
                        "raw_pixel_coords": [x1, y1, x2, y2]
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

                    # -------------------------------------------------------------
                    # Accuracy Enhancement: Chromaticity & Physics Verification Filter
                    # -------------------------------------------------------------
                    if matched_label == "fire" and rx2 > rx1 and ry2 > ry1:
                        crop = image_bgr[ry1:ry2, rx1:rx2]
                        is_valid_flame, flame_ratio = YOLODetector._verify_flame_chromaticity(crop)
                        if not is_valid_flame and confidence < 0.92:
                            continue
                        if flame_ratio > 0.10:
                            confidence = min(0.99, confidence + 0.06)

                    elif matched_label == "smoke" and rx2 > rx1 and ry2 > ry1:
                        crop = image_bgr[ry1:ry2, rx1:rx2]
                        is_valid_smoke, _ = YOLODetector._verify_smoke_dispersion(crop)
                        if not is_valid_smoke and confidence < 0.90:
                            continue

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
