"""
Person AI Detection Module Implementation.
Fulfills BaseDetector interface specifically for worker/person bounding box detection.
"""

import os
import time
import hashlib
import threading
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import numpy as np
import cv2
import cv2.data

from app.config.settings import settings
from app.detection.base import BaseDetector, DetectionResult, BoundingBox, DetectorStatus
from app.detection.nms import nms as _nms
from app.detection.preprocess import upscale_if_small
from app.utils.logger import logger

_PERSON_MODEL_CACHE: Dict[str, Any] = {}
_PERSON_CACHE_LOCK = threading.Lock()


class PersonDetector(BaseDetector):
    """
    Person Detector Module for identifying human workers in surveillance frames.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        conf_threshold: Optional[float] = None,
        device: Optional[str] = None
    ):
        self.model_path = model_path or getattr(settings, "PERSON_MODEL_PATH", "yolov8n.pt")
        self.conf_threshold = conf_threshold if conf_threshold is not None else getattr(settings, "PERSON_CONFIDENCE_THRESHOLD", 0.25)
        self.device = device or getattr(settings, "YOLO_DEVICE", "cpu")
        
        try:
            import torch
            try:
                cpu_cores = os.cpu_count() or 4
                torch.set_num_threads(min(8, max(4, cpu_cores - 2)))
            except Exception:
                pass
            self.is_cuda = torch.cuda.is_available() and self.device.lower() not in ["cpu", ""]
        except (ImportError, OSError, Exception):
            self.is_cuda = False
        self.half = self.is_cuda

        self.status = DetectorStatus.UNAVAILABLE
        self.loaded_at: Optional[str] = None
        self.model_hash: str = "unknown"
        self._model: Any = None
        self._onnx_runner: Any = None
        self._is_mock_fallback: bool = False
        self._last_full_frame_detections: List[DetectionResult] = []

        self.initialize()

    def initialize(self) -> bool:
        cache_key = f"person_{self.model_path}_{self.device}"
        if os.path.exists(self.model_path):
            try:
                with open(self.model_path, "rb") as f:
                    self.model_hash = hashlib.md5(f.read(8192)).hexdigest()
            except Exception:
                self.model_hash = "hash_error"
        else:
            self.model_hash = "mock_mode_no_weights"

        with _PERSON_CACHE_LOCK:
            if cache_key in _PERSON_MODEL_CACHE:
                cached = _PERSON_MODEL_CACHE[cache_key]
                self._model = cached.get("model")
                self._onnx_runner = cached.get("onnx_runner")
                self._is_mock_fallback = cached.get("is_mock", True)
                self.status = DetectorStatus.DEGRADED if self._is_mock_fallback else DetectorStatus.HEALTHY
                self.loaded_at = cached.get("loaded_at", datetime.now(timezone.utc).isoformat())
                return True

            import sys
            if settings.APP_ENV == "testing" or "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ:
                self._is_mock_fallback = True
                self.status = DetectorStatus.DEGRADED
                self.loaded_at = datetime.now(timezone.utc).isoformat()
                _PERSON_MODEL_CACHE[cache_key] = {"model": None, "onnx_runner": None, "is_mock": True, "loaded_at": self.loaded_at}
                return True

            # Attempt 1: High-Performance ONNX Runtime Model Engine
            onnx_candidates = []
            if self.model_path.endswith(".onnx"):
                onnx_candidates.append(self.model_path)
            else:
                onnx_candidates.append(os.path.splitext(self.model_path)[0] + ".onnx")
            onnx_candidates.append("models/yolov8n.onnx")
            onnx_candidates.append("models/ppe.onnx")
            backend_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            onnx_candidates.append(os.path.join(backend_root, "models", "yolov8n.onnx"))
            onnx_candidates.append(os.path.join(backend_root, "models", "ppe.onnx"))

            for cand in onnx_candidates:
                if cand and os.path.isfile(cand):
                    try:
                        from app.detection.onnx_engine import get_onnx_yolo_runner
                        runner = get_onnx_yolo_runner(cand, device=self.device)
                        self._onnx_runner = runner
                        self._model = None
                        self._is_mock_fallback = False
                        self.status = DetectorStatus.HEALTHY
                        self.loaded_at = datetime.now(timezone.utc).isoformat()
                        _PERSON_MODEL_CACHE[cache_key] = {"model": None, "onnx_runner": runner, "is_mock": False, "loaded_at": self.loaded_at}
                        logger.info(f"PersonDetector: Successfully initialized ONNX model from '{cand}'.")
                        return True
                    except Exception as oe:
                        logger.warning(f"PersonDetector: Could not initialize ONNX runner from '{cand}': {oe}")

            # Attempt 2: Ultralytics PyTorch Engine
            try:
                import logging as _logging
                try:
                    from ultralytics.utils import LOGGER as _uLOGGER
                    _uLOGGER.setLevel(_logging.WARNING)
                except Exception:
                    pass

                from ultralytics import YOLO
                weights_path = self.model_path if os.path.exists(self.model_path) else "yolov8n.pt"
                model = YOLO(weights_path)
                try:
                    model.fuse()
                except Exception as fe:
                    logger.warning(f"PersonDetector: Model fuse notice: {fe}")
                model.to(self.device)

                # Pre-warm model graph with a dummy pass
                try:
                    dummy_img = np.zeros((416, 416, 3), dtype=np.uint8)
                    import torch
                    with torch.inference_mode():
                        model.predict(source=dummy_img, imgsz=416, device=self.device, classes=[0], verbose=False)
                    logger.info("PersonDetector: Pre-warmed person detection model graph.")
                except Exception as we:
                    logger.debug(f"PersonDetector: Warmup notice: {we}")

                self._model = model
                self._is_mock_fallback = False
                self.status = DetectorStatus.HEALTHY
                self.loaded_at = datetime.now(timezone.utc).isoformat()
                _PERSON_MODEL_CACHE[cache_key] = {"model": model, "onnx_runner": None, "is_mock": False, "loaded_at": self.loaded_at}
                return True

            except Exception as e:
                logger.warning(f"PersonDetector: Model load error: {str(e)}. Fallback mode enabled.")
                self._is_mock_fallback = True
                self.status = DetectorStatus.DEGRADED
                self.loaded_at = datetime.now(timezone.utc).isoformat()
                _PERSON_MODEL_CACHE[cache_key] = {"model": None, "onnx_runner": None, "is_mock": True, "loaded_at": self.loaded_at}
                return True

    def detect(
        self,
        image_bgr: Any,
        candidate_rois: Optional[List[BoundingBox]] = None,
        motion_rois: Optional[List[Any]] = None,
        **kwargs: Any
    ) -> List[DetectionResult]:
        """
        Detects workers in a frame.

        :param motion_rois: optional normalised ``(x_min, y_min, x_max, y_max)`` boxes from the
               motion gate. Each is re-examined at higher effective resolution, which recovers
               distant workers the full-frame pass misses for a fraction of a second pass.
        """
        if not getattr(settings, "AI_PERSON_ENABLED", True) or image_bgr is None or getattr(image_bgr, "size", 0) == 0:
            return []

        h, w = image_bgr.shape[:2]
        detections: List[DetectionResult] = []
        self._last_full_frame_detections: List[DetectionResult] = []

        # High-Performance ONNX Runner
        if self._onnx_runner is not None:
            try:
                raw_dets, inf_time_ms = self._onnx_runner.predict(
                    image_bgr,
                    conf_threshold=self.conf_threshold,
                    iou_threshold=0.45,
                    target_classes=None
                )
                for d in raw_dets:
                    if not self._is_person(d):
                        continue
                    detections.append(DetectionResult(
                        label="person",
                        confidence=float(d["confidence"]),
                        bbox=d["bbox"],
                        metadata={
                            "detector_module": "PersonDetector",
                            "engine": "ONNXYOLORunner",
                            "device": self.device,
                            "inference_time_ms": inf_time_ms,
                            "raw_class": d["label"],
                            "box_agreement": d.get("box_agreement", 1),
                        }
                    ))

                self._last_full_frame_detections = list(detections)

                # Refine on motion regions before giving up: a worker 40 m away may be a 20-pixel
                # blob in a 1080p frame, well under the 640-px network's reliable size.
                if motion_rois and getattr(settings, "ENABLE_PERSON_ROI_REFINE", True):
                    detections.extend(self._refine_on_motion_rois(image_bgr, motion_rois, h, w))

                # Only fall back to the classical detector when no neural backend exists at all.
                # Previously this ran whenever the network returned zero persons, which is precisely
                # what happens on an empty scene - the Haar/skin path then fabricated workers at a
                # fixed 0.86-0.88 confidence and every one of them became a phantom PPE violation.
                if not detections and not self._neural_backend_available():
                    detections.extend(self._detect_opencv_person_fallback(image_bgr))

                return self._dedupe(detections)
            except Exception as oe:
                logger.error(f"PersonDetector: Error during ONNX inference: {oe}")

        if not self._is_mock_fallback and self._model is not None:
            try:
                import torch
                imgsz_val = getattr(settings, "AI_IMAGE_SIZE", getattr(settings, "YOLO_IMGSZ", 416))
                if self.device.lower() in ["cpu", ""]:
                    imgsz_val = min(416, max(384, imgsz_val))
                predict_kwargs = {
                    "source": image_bgr,
                    "conf": self.conf_threshold,
                    "device": self.device,
                    "classes": [0],  # COCO class 0 is 'person'
                    "max_det": 30,
                    "imgsz": imgsz_val,
                    "verbose": False
                }
                if self.half:
                    predict_kwargs["half"] = True
                with torch.inference_mode():
                    results = self._model.predict(**predict_kwargs)
                for r in results:
                    boxes = r.boxes
                    if boxes is None:
                        continue
                    for box in boxes:
                        conf = float(box.conf[0])
                        xyxy = box.xyxy[0].cpu().numpy()
                        x1, y1, x2, y2 = float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])
                        norm_bbox = BoundingBox(
                            x_min=max(0.0, min(1.0, x1 / w)),
                            y_min=max(0.0, min(1.0, y1 / h)),
                            x_max=max(0.0, min(1.0, x2 / w)),
                            y_max=max(0.0, min(1.0, y2 / h))
                        )
                        detections.append(DetectionResult(
                            label="person",
                            confidence=conf,
                            bbox=norm_bbox,
                            metadata={"detector_module": "PersonDetector", "device": self.device}
                        ))
            except Exception as e:
                logger.error(f"PersonDetector: Error during YOLO detection: {str(e)}")

        # If neural network detector produced no detections and fallback is allowed, run OpenCV cascade
        if not detections and (self._is_mock_fallback or (self._model is None and self._onnx_runner is None)):
            cv_persons = self._detect_opencv_person_fallback(image_bgr)
            detections.extend(cv_persons)

        return detections

    _face_cascade_obj = None
    _profile_cascade_obj = None
    _upperbody_cascade_obj = None

    @classmethod
    def _detect_opencv_person_fallback_static(cls, image_bgr: np.ndarray) -> List[DetectionResult]:
        """
        Static entry point for multi-stage OpenCV person anchor detection.
        Eliminates PyTorch model instantiation overhead when calling fallbacks.
        """
        return cls._detect_opencv_person_fallback_impl(image_bgr)

    def _detect_opencv_person_fallback(self, image_bgr: np.ndarray) -> List[DetectionResult]:
        return self._detect_opencv_person_fallback_impl(image_bgr)

    @classmethod
    def _detect_opencv_person_fallback_impl(cls, image_bgr: np.ndarray) -> List[DetectionResult]:
        """
        Multi-Stage OpenCV Person Anchor Detector (Haar face/body + skin/torso contour).
        """
        if image_bgr is None or image_bgr.size == 0:
            return []

        h, w = image_bgr.shape[:2]
        results: List[DetectionResult] = []

        try:
            # 1. Downscale large frames to 480p max dimension for sub-millisecond processing
            if w > 480:
                scale_ratio = 480.0 / float(w)
                proc_w = 480
                proc_h = int(h * scale_ratio)
                proc_bgr = cv2.resize(image_bgr, (proc_w, proc_h), interpolation=cv2.INTER_NEAREST)
            else:
                proc_w, proc_h = w, h
                proc_bgr = image_bgr

            # 2. Lazy-load Cascades
            cascade_cls = getattr(cv2, "CascadeClassifier", None)
            if PersonDetector._face_cascade_obj is None and cascade_cls is not None:
                f_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                if os.path.exists(f_path):
                    PersonDetector._face_cascade_obj = cascade_cls(f_path)

            if PersonDetector._profile_cascade_obj is None and cascade_cls is not None:
                p_path = cv2.data.haarcascades + "haarcascade_profileface.xml"
                if os.path.exists(p_path):
                    PersonDetector._profile_cascade_obj = cascade_cls(p_path)

            if PersonDetector._upperbody_cascade_obj is None and cascade_cls is not None:
                u_path = cv2.data.haarcascades + "haarcascade_upperbody.xml"
                if os.path.exists(u_path):
                    PersonDetector._upperbody_cascade_obj = cascade_cls(u_path)

            gray = cv2.cvtColor(proc_bgr, cv2.COLOR_BGR2GRAY)

            # Stage 1: Frontal Face Cascade (fast multi-scale)
            if PersonDetector._face_cascade_obj is not None:
                faces = PersonDetector._face_cascade_obj.detectMultiScale(gray, scaleFactor=1.12, minNeighbors=4, minSize=(20, 20))
                for (fx, fy, fw_c, fh_c) in faces:
                    px1 = max(0, fx - int(fw_c * 0.65))
                    py1 = max(0, fy - int(fh_c * 0.45))
                    px2 = min(proc_w, fx + fw_c + int(fw_c * 0.65))
                    py2 = min(proc_h, fy + fh_c + int(fh_c * 3.4))

                    norm_box = BoundingBox(
                        x_min=max(0.0, min(1.0, px1 / proc_w)),
                        y_min=max(0.0, min(1.0, py1 / proc_h)),
                        x_max=max(0.0, min(1.0, px2 / proc_w)),
                        y_max=max(0.0, min(1.0, py2 / proc_h))
                    )
                    results.append(DetectionResult(
                        label="person",
                        confidence=0.94,
                        bbox=norm_box,
                        metadata={"detector_module": "OpenCV-FrontalFace-PersonDetector", "face_box": [fx, fy, fw_c, fh_c]}
                    ))

            # Stage 2: Profile Face Cascade (if frontal face missed)
            if not results and PersonDetector._profile_cascade_obj is not None:
                p_faces = PersonDetector._profile_cascade_obj.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=3, minSize=(25, 25))
                for (fx, fy, fw, fh) in p_faces:
                    px1 = max(0, fx - int(fw * 0.65))
                    py1 = max(0, fy - int(fh * 0.45))
                    px2 = min(w, fx + fw + int(fw * 0.65))
                    py2 = min(h, fy + fh + int(fh * 3.4))

                    norm_box = BoundingBox(
                        x_min=max(0.0, min(1.0, px1 / w)),
                        y_min=max(0.0, min(1.0, py1 / h)),
                        x_max=max(0.0, min(1.0, px2 / w)),
                        y_max=max(0.0, min(1.0, py2 / h))
                    )
                    results.append(DetectionResult(
                        label="person",
                        confidence=0.91,
                        bbox=norm_box,
                        metadata={"detector_module": "OpenCV-ProfileFace-PersonDetector"}
                    ))

            # Stage 3: Upperbody Cascade (if faces missed)
            if not results and PersonDetector._upperbody_cascade_obj is not None:
                bodies = PersonDetector._upperbody_cascade_obj.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=3, minSize=(40, 40))
                for (bx, by, bw_c, bh_c) in bodies:
                    norm_box = BoundingBox(
                        x_min=max(0.0, min(1.0, bx / w)),
                        y_min=max(0.0, min(1.0, by / h)),
                        x_max=max(0.0, min(1.0, (bx + bw_c) / w)),
                        y_max=max(0.0, min(1.0, (by + bh_c) / h))
                    )
                    results.append(DetectionResult(
                        label="person",
                        confidence=0.88,
                        bbox=norm_box,
                        metadata={"detector_module": "OpenCV-UpperBody-PersonDetector"}
                    ))

            # Stage 4: Human Skin & Torso Contour Anchor Fallback (HSV + YCrCb Dual Mask)
            if not results:
                hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
                ycrcb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2YCrCb)

                mask_hsv_skin = cv2.inRange(hsv, np.array([0, 20, 50]), np.array([28, 180, 255]))
                mask_ycrcb_skin = cv2.inRange(ycrcb, np.array([0, 133, 80]), np.array([255, 173, 125]))
                skin_mask = cv2.bitwise_and(mask_hsv_skin, mask_ycrcb_skin)

                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
                skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_CLOSE, kernel)
                contours, _ = cv2.findContours(skin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                for cnt in contours:
                    area = cv2.contourArea(cnt)
                    if area > (h * w * 0.020):  # At least 2.0% of camera frame
                        cx, cy, cw_c, ch_c = cv2.boundingRect(cnt)
                        aspect_ratio = float(cw_c) / float(ch_c) if ch_c > 0 else 1.0
                        if 0.20 <= aspect_ratio <= 1.8:
                            # Expand skin area to full person box
                            px1 = max(0, cx - int(cw_c * 0.4))
                            py1 = max(0, cy - int(ch_c * 0.3))
                            px2 = min(w, cx + cw_c + int(cw_c * 0.4))
                            py2 = min(h, cy + ch_c + int(ch_c * 2.5))

                            norm_box = BoundingBox(
                                x_min=max(0.0, min(1.0, px1 / w)),
                                y_min=max(0.0, min(1.0, py1 / h)),
                                x_max=max(0.0, min(1.0, px2 / w)),
                                y_max=max(0.0, min(1.0, py2 / h))
                            )
                            results.append(DetectionResult(
                                label="person",
                                confidence=0.86,
                            bbox=norm_box,
                            metadata={"detector_module": "OpenCV-SkinContour-PersonDetector"}
                        ))
                        break  # Found main human subject

        except Exception as e:
            logger.warning(f"PersonDetector: Multi-stage cascade exception: {str(e)}")

        return results

    def _neural_backend_available(self) -> bool:
        """True when weights are loaded and inference is trustworthy enough to skip CV fallbacks."""
        if getattr(self, "_onnx_runner", None) is not None:
            return True
        return self._model is not None and not self._is_mock_fallback

    def _is_person(self, detection: Dict[str, Any]) -> bool:
        """
        Decides whether a raw detection is a worker.

        The previous implementation accepted ``class_id == 0`` as "person". That is only true for
        COCO-ordered weights; the bundled ``yolov8n.onnx`` export carries no class-name metadata, so
        the id-0 shortcut was the sole test and the model's *label names* were ignored entirely.
        Resolution order is now: model metadata name -> COCO fallback for a genuine 80-class model ->
        explicit name list.
        """
        label = str(detection.get("label", "")).lower().strip()
        if label in ("person", "worker", "human", "people"):
            return True
        cid = int(detection.get("class_id", -1))
        name_from_model = ""
        runner = getattr(self, "_onnx_runner", None)
        if runner is not None:
            try:
                name_from_model = runner.name_for(cid)
            except Exception:
                name_from_model = ""
        if name_from_model in ("person", "worker", "human", "people"):
            return True
        if not name_from_model or name_from_model.isdigit():
            # Anonymous export: a standard COCO model has exactly 80 classes and person is index 0.
            num_classes = getattr(runner, "names", {}) or {}
            if cid == 0 and len(num_classes) in (0, 80):
                return True
        return False

    def _refine_on_motion_rois(
        self,
        image_bgr: np.ndarray,
        motion_rois: List[Any],
        h: int,
        w: int,
    ) -> List[DetectionResult]:
        """
        Second-pass worker search on upscaled motion crops.

        The pass costs one extra inference, so it is spent only where it can pay off: a region that
        is small in the frame (a distant worker, where upscaling genuinely adds pixels) and that no
        existing detection already covers.
        """
        extra: List[DetectionResult] = []
        max_rois = int(getattr(settings, "PERSON_ROI_REFINE_MAX_ROIS", 1))
        max_roi_fraction = float(getattr(settings, "PERSON_ROI_REFINE_MAX_AREA", 0.35))
        for roi in list(motion_rois)[:max_rois]:
            try:
                x_min, y_min, x_max, y_max = [float(v) for v in roi]
            except Exception:
                continue
            x1 = max(0, int(x_min * w))
            y1 = max(0, int(y_min * h))
            x2 = min(w, int(x_max * w))
            y2 = min(h, int(y_max * h))
            if x2 - x1 < 32 or y2 - y1 < 32:
                continue
            # Large regions are already well sampled at full-frame resolution - upscaling them
            # cannot reveal anything new.
            if ((x2 - x1) * (y2 - y1)) / float(max(1, w * h)) > max_roi_fraction:
                continue
            # Already covered by a full-frame detection: nothing to recover.
            if any(
                d.bbox.x_max > x_min and d.bbox.x_min < x_max and d.bbox.y_max > y_min and d.bbox.y_min < y_max
                for d in self._last_full_frame_detections
            ):
                continue
            crop = image_bgr[y1:y2, x1:x2]
            if crop.size == 0:
                continue
            prepared, upscale = upscale_if_small(crop, min_side=480)
            try:
                roi_dets, _ = self._onnx_runner.predict(
                    prepared,
                    conf_threshold=max(0.25, self.conf_threshold * 0.75),
                    iou_threshold=0.45,
                    target_classes=None,
                )
            except Exception:
                continue
            back = 1.0 / (upscale if upscale > 0 else 1.0)
            for d in roi_dets:
                if not self._is_person(d):
                    continue
                bx1, by1, bx2, by2 = d["pixel_coords"]
                gx1 = max(0.0, x1 + bx1 * back)
                gy1 = max(0.0, y1 + by1 * back)
                gx2 = min(float(w), x1 + bx2 * back)
                gy2 = min(float(h), y1 + by2 * back)
                if gx2 - gx1 < 2 or gy2 - gy1 < 2:
                    continue
                extra.append(DetectionResult(
                    label="person",
                    confidence=float(d["confidence"]),
                    bbox=BoundingBox(x_min=gx1 / w, y_min=gy1 / h, x_max=gx2 / w, y_max=gy2 / h),
                    metadata={
                        "detector_module": "PersonDetector",
                        "engine": "ONNXYOLORunner-MotionROI",
                        "roi_upscale": round(upscale, 2),
                        "evidence": "motion_roi",
                    },
                ))
        return extra

    @staticmethod
    def _dedupe(detections: List[DetectionResult], iou_threshold: float = 0.55) -> List[DetectionResult]:
        """Suppresses duplicate person boxes (full-frame and ROI passes can both fire)."""
        if len(detections) <= 1:
            return detections
        import numpy as np

        boxes = np.array([
            [d.bbox.x_min, d.bbox.y_min, d.bbox.x_max, d.bbox.y_max] for d in detections
        ], dtype=np.float32)
        scores = np.array([d.confidence for d in detections], dtype=np.float32)
        classes = np.zeros(len(detections), dtype=np.int64)
        keep = _nms(boxes, scores, iou_threshold, classes, class_aware=True)
        return [detections[i] for i in keep]

    def get_model_name(self) -> str:
        return f"PersonDetector (Device: {self.device})"

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "model_name": "PersonDetector",
            "model_version": "1.0.0",
            "model_filename": os.path.basename(self.model_path),
            "model_hash": self.model_hash,
            "loaded_at": self.loaded_at,
            "target_classes": ["person"],
            "device": self.device
        }

    def health_check(self) -> Dict[str, Any]:
        return {
            "detector": "PersonDetector",
            "status": self.status.value,
            "device": self.device,
            "model_name": self.get_model_name(),
            "enabled": getattr(settings, "AI_PERSON_ENABLED", True)
        }

    def shutdown(self) -> None:
        self._model = None
        self.status = DetectorStatus.UNAVAILABLE
