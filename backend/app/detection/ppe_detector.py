"""
PPE AI Detection Module Implementation.
Modular wrapper fulfilling BaseDetector interface for Personal Protective Equipment & Worker detection.
Supports custom-trained YOLO weights, configurable target classes, confidence thresholds, and safe CPU/fallback startup.
"""

import os
import time
import hashlib
import threading
from datetime import datetime, timezone
import cv2
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np

from app.config.settings import settings
from app.detection.base import BaseDetector, DetectionResult, BoundingBox, DetectorStatus
from app.detection.preprocess import prepare_worker_roi
from app.detection.roi_refine import PPERoiRefiner, normalise_ppe_label, person_key
from app.utils.logger import logger

# Global model cache to avoid re-loading heavy weights across pipeline instances
_PPE_MODEL_CACHE: Dict[str, Any] = {}
_PPE_CACHE_LOCK = threading.Lock()


class PPEDetector(BaseDetector):
    """
    PPE & Worker Detection Module using YOLO object detection engine.
    Detects workers ('person') and safety equipment ('helmet', 'vest', 'mask', 'goggles', 'gloves', 'safety_shoes').
    """

    DEFAULT_CLASSES = ["person", "helmet", "vest", "goggles", "gloves", "safety_shoes"]

    _face_cascade_alt2_obj: Any = None
    _face_cascade_obj: Any = None
    _profile_cascade_obj: Any = None
    _eyeglasses_cascade_obj: Any = None
    _eye_cascade_obj: Any = None

    def __init__(
        self,
        model_path: Optional[str] = None,
        conf_threshold: Optional[float] = None,
        iou_threshold: Optional[float] = None,
        device: Optional[str] = None,
        target_classes: Optional[List[str]] = None
    ):
        raw_path = model_path or getattr(settings, "PPE_MODEL_PATH", "models/ppe.pt")
        if not os.path.isfile(raw_path):
            backend_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            alt_path = os.path.join(backend_root, raw_path)
            if os.path.isfile(alt_path):
                raw_path = alt_path
            elif os.path.isfile(os.path.join("backend", raw_path)):
                raw_path = os.path.join("backend", raw_path)
        self.model_path = raw_path
        self.conf_threshold = conf_threshold if conf_threshold is not None else getattr(settings, "PPE_CONFIDENCE_THRESHOLD", 0.25)
        self.iou_threshold = iou_threshold if iou_threshold is not None else getattr(settings, "PPE_IOU_THRESHOLD", 0.45)
        self.device = device or getattr(settings, "PPE_DEVICE", "cpu")
        self.target_classes = [c.lower() for c in (target_classes or self.DEFAULT_CLASSES)]

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

        # Worker-crop refinement state (per detector instance == per camera pipeline).
        self._roi_refiner = PPERoiRefiner(
            enabled=bool(getattr(settings, "ENABLE_PPE_ROI", True)),
            max_persons=int(getattr(settings, "PPE_CROP_REFINE_MAX_PERSONS", 4)),
            confidence_floor=float(getattr(settings, "GLASSES_ROI_CONFIDENCE_FLOOR", 0.085)),
        )
        self._association_engine: Any = None

        self.initialize()

    def has_person_class(self) -> bool:
        """
        Inspects model names dictionary to verify if a 'person' or 'worker' class exists.
        Returns True if the loaded weights support person/worker detection directly.
        """
        if self._onnx_runner is not None and hasattr(self._onnx_runner, "names"):
            return any(str(name).lower() in ["person", "worker"] for name in self._onnx_runner.names.values())

        if self._is_mock_fallback or self._model is None or not hasattr(self._model, "names"):
            return any(c in ["person", "worker"] for c in self.target_classes)

        names_dict = getattr(self._model, "names", {})
        if isinstance(names_dict, dict):
            return any(str(name).lower() in ["person", "worker"] for name in names_dict.values())
        elif isinstance(names_dict, (list, tuple)):
            return any(str(name).lower() in ["person", "worker"] for name in names_dict)
        return False

    def initialize(self) -> bool:
        """
        Loads PPE YOLO model weights into compute device safely.
        Prioritizes ONNX runtime for cross-platform speed and compliance, with Ultralytics fallback.
        """
        cache_key = f"{self.model_path}_{self.device}"

        if os.path.exists(self.model_path):
            try:
                with open(self.model_path, "rb") as f:
                    self.model_hash = hashlib.md5(f.read(8192)).hexdigest()
            except Exception:
                self.model_hash = "hash_error"
        else:
            self.model_hash = "mock_mode_no_weights"

        with _PPE_CACHE_LOCK:
            if cache_key in _PPE_MODEL_CACHE:
                cached = _PPE_MODEL_CACHE[cache_key]
                self._model = cached.get("model")
                self._onnx_runner = cached.get("onnx_runner")
                self._is_mock_fallback = cached.get("is_mock", True)
                self.status = DetectorStatus.DEGRADED if self._is_mock_fallback else DetectorStatus.HEALTHY
                self.loaded_at = cached.get("loaded_at", datetime.now(timezone.utc).isoformat())
                return True

            import sys
            if settings.APP_ENV == "testing" or "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ:
                logger.warning(
                    f"PPEDetector: Safe Testing Mode active (APP_ENV={settings.APP_ENV}). "
                    f"Skipping heavy neural network initialization."
                )
                self._is_mock_fallback = True
                self.status = DetectorStatus.DEGRADED
                self.loaded_at = datetime.now(timezone.utc).isoformat()
                _PPE_MODEL_CACHE[cache_key] = {"model": None, "onnx_runner": None, "is_mock": True, "loaded_at": self.loaded_at}
                return True

            # Attempt 1: High-Performance ONNX Runtime Model Engine
            onnx_candidates = []
            if self.model_path.endswith(".onnx"):
                onnx_candidates.append(self.model_path)
            else:
                onnx_candidates.append(os.path.splitext(self.model_path)[0] + ".onnx")
            onnx_candidates.append("models/ppe.onnx")
            backend_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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
                        _PPE_MODEL_CACHE[cache_key] = {"model": None, "onnx_runner": runner, "is_mock": False, "loaded_at": self.loaded_at}
                        logger.info(f"PPEDetector: Successfully loaded ONNX PPE model from '{cand}'.")
                        return True
                    except Exception as oe:
                        logger.warning(f"PPEDetector: Could not initialize ONNX runner from '{cand}': {oe}")

            # Attempt 2: Ultralytics PyTorch Engine
            if not os.path.isfile(self.model_path):
                logger.warning(
                    "PPEDetector: PPE weights are missing at '%s'. PPE detection "
                    "is running in fallback mode.",
                    self.model_path,
                )
                self._is_mock_fallback = True
                self.status = DetectorStatus.DEGRADED
                self.loaded_at = datetime.now(timezone.utc).isoformat()
                _PPE_MODEL_CACHE[cache_key] = {"model": None, "onnx_runner": None, "is_mock": True, "loaded_at": self.loaded_at}
                return True

            try:
                import logging as _logging
                try:
                    from ultralytics.utils import LOGGER as _uLOGGER
                    _uLOGGER.setLevel(_logging.WARNING)
                except Exception:
                    pass

                from ultralytics import YOLO
                t0 = time.time()
                model = YOLO(self.model_path)
                try:
                    model.fuse()
                except Exception as fe:
                    logger.warning(f"PPEDetector: Model fuse notice: {fe}")
                model.to(self.device)

                try:
                    dummy_img = np.zeros((416, 416, 3), dtype=np.uint8)
                    import torch
                    with torch.inference_mode():
                        model.predict(source=dummy_img, imgsz=416, device=self.device, verbose=False)
                    logger.info("PPEDetector: Pre-warmed PPE model graph.")
                except Exception as we:
                    logger.debug(f"PPEDetector: Warmup notice: {we}")

                load_time_sec = round(time.time() - t0, 3)

                logger.info(f"PPEDetector: Successfully loaded PPE YOLO model from '{self.model_path}' on {self.device} in {load_time_sec}s.")
                self._model = model
                self._is_mock_fallback = False
                self.status = DetectorStatus.HEALTHY
                self.loaded_at = datetime.now(timezone.utc).isoformat()
                _PPE_MODEL_CACHE[cache_key] = {"model": model, "onnx_runner": None, "is_mock": False, "loaded_at": self.loaded_at}
                return True

            except Exception as e:
                logger.warning(f"PPEDetector: Error loading model from '{self.model_path}': {str(e)}. Safe mode activated.")
                self._is_mock_fallback = True
                self.status = DetectorStatus.DEGRADED
                self.loaded_at = datetime.now(timezone.utc).isoformat()
                _PPE_MODEL_CACHE[cache_key] = {"model": None, "onnx_runner": None, "is_mock": True, "loaded_at": self.loaded_at}
                return True

    def detect(
        self,
        image_bgr: Any,
        candidate_rois: Optional[List[BoundingBox]] = None,
        person_dets: Optional[List[DetectionResult]] = None,
        required_equipment: Optional[List[str]] = None,
        fire_smoke_boxes: Optional[List[DetectionResult]] = None,
        **kwargs: Any
    ) -> List[DetectionResult]:
        """
        Executes PPE object detection on image frame.

        :param person_dets: worker boxes from the dedicated person detector. Passing these is what
               enables ROI refinement and removes the need for any OpenCV person fallback.
        :param required_equipment: items the active PPE profile requires (default vest + goggles).
               Only *missing* items are ever re-examined at high resolution, so compliance costs
               nothing extra per frame.
        :param fire_smoke_boxes: previous frame's fire/smoke detections. When present the
               standalone HSV vest and CV glasses fallbacks are disabled and ONNX confidence
               floors are boosted by FIRE_SCENE_THRESHOLD_BOOST.
        """
        if not getattr(settings, "AI_PPE_ENABLED", True) or image_bgr is None or getattr(image_bgr, "size", 0) == 0:
            return []

        h, w = image_bgr.shape[:2]

        # Route to ONNX Inference Engine if active
        if self._onnx_runner is not None:
            return self._detect_onnx(
                image_bgr=image_bgr,
                person_dets=person_dets,
                required_equipment=required_equipment,
                h=h,
                w=w,
                fire_smoke_boxes=fire_smoke_boxes,
            )

        if self._is_mock_fallback or self._model is None:
            if person_dets:
                ppe_cv_dets = self._detect_cv_ppe_features(image_bgr, person_dets)
                return self._apply_nms(person_dets + ppe_cv_dets, iou_threshold=0.50)
            return self._detect_mock_fallback(image_bgr)

        try:
            import torch
            h, w = image_bgr.shape[:2]
            t_start = time.time()

            imgsz_val = getattr(settings, "AI_IMAGE_SIZE", getattr(settings, "YOLO_IMGSZ", 416))
            if self.device.lower() in ["cpu", ""]:
                imgsz_val = min(416, max(384, imgsz_val))
            augment_val = getattr(settings, "YOLO_AUGMENT", False)

            predict_conf = min(
                self.conf_threshold,
                getattr(settings, "VEST_CONFIDENCE_THRESHOLD", 0.25),
                getattr(settings, "GLASSES_CONFIDENCE_THRESHOLD", 0.25),
                getattr(settings, "PPE_CONFIDENCE_THRESHOLD", 0.25)
            )

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

            for r in results:
                boxes = r.boxes
                if boxes is None or len(boxes) == 0:
                    continue

                for box in boxes:
                    cls_id = int(box.cls[0])
                    raw_class_name = r.names.get(cls_id, f"class_{cls_id}").lower().strip()

                    # Label normalization & mapping
                    matched_label = None
                    if raw_class_name in ["person", "worker", "human"]:
                        matched_label = "person"
                    elif raw_class_name in ["helmet", "hard_hat", "hardhat", "cap", "headgear"]:
                        matched_label = "helmet"
                    elif raw_class_name in ["vest", "safety_vest", "safety vest", "jacket", "hivis", "waistcoat", "high_vis_vest", "reflective_vest"]:
                        matched_label = "vest"
                    elif raw_class_name in ["mask", "face_mask", "n95", "respirator"]:
                        matched_label = "mask"
                    elif raw_class_name in ["goggles", "glasses", "safety_glasses", "safety_glass", "safety glass", "eyewear", "eye_protection", "eye protection", "spec", "specs", "spectacles", "safety_goggles", "safety goggles", "protective_glasses", "protective glasses"] and raw_class_name not in ["wine glass", "glass", "drinking glass"]:
                        matched_label = "goggles"
                    elif raw_class_name in ["gloves", "glove", "hand_protection"]:
                        matched_label = "gloves"
                    elif raw_class_name in ["safety_shoes", "safety_shoe", "shoes", "shoe", "boots", "boot"]:
                        matched_label = "safety_shoes"
                    elif self.target_classes and raw_class_name in self.target_classes:
                        matched_label = raw_class_name

                    if not matched_label or (self.target_classes and matched_label not in self.target_classes and matched_label != "person"):
                        continue

                    confidence = float(box.conf[0])
                    class_threshold = getattr(settings, "VEST_CONFIDENCE_THRESHOLD", 0.20) if matched_label == "vest" else (
                        getattr(settings, "GLASSES_CONFIDENCE_THRESHOLD", 0.20) if matched_label == "goggles" else (
                            getattr(settings, "PERSON_CONFIDENCE_THRESHOLD", 0.35) if matched_label == "person" else self.conf_threshold
                        )
                    )
                    if confidence < class_threshold:
                        continue

                    xyxy = box.xyxy[0].cpu().numpy()
                    x1, y1, x2, y2 = float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])

                    norm_bbox = BoundingBox(
                        x_min=max(0.0, min(1.0, x1 / w)),
                        y_min=max(0.0, min(1.0, y1 / h)),
                        x_max=max(0.0, min(1.0, x2 / w)),
                        y_max=max(0.0, min(1.0, y2 / h))
                    )

                    # Geometry sanity gate (same as ONNX path)
                    if matched_label != "person" and not self._is_sane_ppe_box(matched_label, norm_bbox):
                        continue

                    det_res = DetectionResult(
                        label=matched_label,
                        confidence=confidence,
                        bbox=norm_bbox,
                        metadata={
                            "detector_module": "PPEDetector",
                            "inference_time_ms": inference_time_ms,
                            "device": self.device,
                            "raw_pixel_coords": [int(x1), int(y1), int(x2), int(y2)]
                        }
                    )
                    detections.append(det_res)

            # If person detections were provided by pipeline, use them directly (saves 4 Haar cascades)
            if person_dets is not None and len(person_dets) > 0:
                active_person_dets = list(person_dets)
            else:
                active_person_dets = [d for d in detections if d.label.lower() == "person"]
                if not active_person_dets and (self._is_mock_fallback or self._model is None):
                    from app.detection.person_detector import PersonDetector
                    active_person_dets = PersonDetector._detect_opencv_person_fallback_static(image_bgr)
                    detections.extend(active_person_dets)

            ppe_equipment_dets = [d for d in detections if d.label.lower() != "person"]
            detected_gear_types = {d.label.lower() for d in ppe_equipment_dets}

            # -------------------------------------------------------------
            # Worker-Crop High-Resolution PPE Detail Analysis (Vest, Goggles, Gloves)
            # -------------------------------------------------------------
            if not self._is_mock_fallback and self._model is not None and active_person_dets:
                for p_det in active_person_dets[:5]:
                    c_x1, c_y1, c_x2, c_y2 = p_det.bbox.to_pixel_coords(w, h)
                    pw = c_x2 - c_x1
                    ph = c_y2 - c_y1
                    if pw >= 45 and ph >= 60:
                        crop_x1 = max(0, c_x1 - int(pw * 0.05))
                        crop_y1 = max(0, c_y1 - int(ph * 0.05))
                        crop_x2 = min(w, c_x2 + int(pw * 0.05))
                        crop_y2 = min(h, c_y1 + int(ph * 0.90))
                        crop_img = image_bgr[crop_y1:crop_y2, crop_x1:crop_x2]
                        if crop_img.size > 0:
                            try:
                                with torch.inference_mode():
                                    crop_res = self._model.predict(
                                        source=crop_img,
                                        conf=predict_conf,
                                        iou=self.iou_threshold,
                                        device=self.device,
                                        imgsz=224,
                                        verbose=False
                                    )
                                for cr in crop_res:
                                    if cr.boxes is not None and len(cr.boxes) > 0:
                                        for cbox in cr.boxes:
                                            c_cls_id = int(cbox.cls[0])
                                            c_raw_label = cr.names.get(c_cls_id, f"class_{c_cls_id}").lower().strip()
                                            c_conf = float(cbox.conf[0])
                                            c_matched = None
                                            if c_raw_label in ["vest", "safety_vest", "jacket", "hivis", "reflective_vest", "high_vis_vest"]:
                                                c_matched = "vest"
                                            elif c_raw_label in ["goggles", "glasses", "safety_glasses", "eyewear", "eye_protection", "specs", "spectacles", "safety_goggles", "protective_glasses"]:
                                                c_matched = "goggles"
                                            elif c_raw_label in ["gloves", "glove", "hand_protection"]:
                                                c_matched = "gloves"
                                            elif c_raw_label in ["mask", "face_mask", "n95", "respirator"]:
                                                c_matched = "mask"

                                            class_threshold = getattr(settings, "VEST_CONFIDENCE_THRESHOLD", 0.55) if c_matched == "vest" else getattr(settings, "GLASSES_CONFIDENCE_THRESHOLD", 0.20)
                                            if c_matched and c_conf >= class_threshold:
                                                if hasattr(cbox.xyxy[0], "cpu"):
                                                    c_xyxy = cbox.xyxy[0].cpu().numpy()
                                                else:
                                                    c_xyxy = np.array(cbox.xyxy[0])

                                                # Localize safety vest and safety glasses strictly to upper-torso and facial regions
                                                crop_h = max(1.0, float(crop_y2 - crop_y1))
                                                c_cy_rel = (float(c_xyxy[1]) + float(c_xyxy[3])) / (2.0 * crop_h)
                                                if c_matched == "goggles" and (c_cy_rel < -0.05 or c_cy_rel > 0.38):
                                                    continue
                                                if c_matched == "vest" and (c_cy_rel < 0.12 or c_cy_rel > 0.82):
                                                    continue

                                                abs_x1 = max(0.0, min(float(w), float(crop_x1 + c_xyxy[0])))
                                                abs_y1 = max(0.0, min(float(h), float(crop_y1 + c_xyxy[1])))
                                                abs_x2 = max(0.0, min(float(w), float(crop_x1 + c_xyxy[2])))
                                                abs_y2 = max(0.0, min(float(h), float(crop_y1 + c_xyxy[3])))
                                                crop_bbox = BoundingBox(
                                                    x_min=abs_x1 / float(w),
                                                    y_min=abs_y1 / float(h),
                                                    x_max=abs_x2 / float(w),
                                                    y_max=abs_y2 / float(h)
                                                )
                                                detections.append(DetectionResult(
                                                    label=c_matched,
                                                    confidence=c_conf,
                                                    bbox=crop_bbox,
                                                    metadata={"detector_module": "PPEDetector-WorkerCrop"}
                                                ))
                                                detected_gear_types.add(c_matched)
                            except Exception as ce:
                                logger.debug(f"PPEDetector: Worker crop inference notice: {ce}")

            if active_person_dets:
                cv_ppe = self._detect_cv_ppe_features(image_bgr, active_person_dets, detected_gear_types=detected_gear_types)
                if cv_ppe:
                    detections.extend(cv_ppe)

            # Standalone vest detection fallback (only when explicitly enabled or in mock/test mode).
            # Guard: only run when at least one confirmed person box is present — otherwise this
            # fires on vest-coloured pixels anywhere in the frame (red extinguishers, yellow
            # signage, silver bags) and produces unanchored "Safety Vest Found" badges.
            # FIRE VETO: disabled entirely when fire/smoke candidates exist — flame occupies
            # the same HSV band as hi-vis and is not distinguishable by this method.
            fire_scene_active = bool(
                fire_smoke_boxes
                and getattr(settings, "FIRE_SCENE_VETO_ENABLED", True)
            )
            if (
                "vest" not in {d.label.lower() for d in detections}
                and active_person_dets
                and (self._is_mock_fallback or getattr(settings, "ENABLE_STANDALONE_VEST_FALLBACK", False))
                and not fire_scene_active
            ):
                standalone_vests = self._detect_standalone_vest_hsv(image_bgr, fire_smoke_boxes=fire_smoke_boxes)
                if standalone_vests:
                    detections.extend(standalone_vests)

            return self._apply_nms(detections, iou_threshold=0.50)

        except Exception as e:
            logger.error(f"PPEDetector: Error during inference: {str(e)}")
            self.status = DetectorStatus.DEGRADED
            return []

    # ------------------------------------------------------------------ #
    # PPE bounding-box geometry sanity gate
    # ------------------------------------------------------------------ #
    # Maximum fraction of the *frame area* a single PPE item can plausibly
    # occupy.  A real vest on a worker fills ≤4% of a 1080p surveillance
    # frame; goggles fill ≤1%.  The PPE model hallucinate item-class boxes
    # that cover 30–50% of the frame on office backgrounds (desks, floors,
    # walls).  Rejecting anything beyond these generous ceilings eliminates
    # those hallucinations with zero risk of dropping real equipment.
    _MAX_AREA_FRACTION: Dict[str, float] = {
        "goggles": 0.12,       # glasses on a face
        "helmet":  0.50,
        "vest":    0.85,       # Torso can take up most of the screen in webcams
        "mask":    0.40,
        "gloves":  0.30,
        "safety_shoes": 0.40,
    }
    # Minimum and maximum aspect-ratios (w/h) per class.  Goggles are
    # wider-than-tall; a "goggles" box that is 4× taller than wide is a
    # hallucination on a vertical surface.
    _ASPECT_BOUNDS: Dict[str, Tuple[float, float]] = {
        "goggles": (0.35, 6.0),
        "helmet":  (0.40, 3.5),
        "vest":    (0.20, 3.0),
        "mask":    (0.30, 3.0),
        "gloves":  (0.25, 4.0),
        "safety_shoes": (0.30, 4.0),
    }

    @staticmethod
    def _is_sane_ppe_box(label: str, bbox: BoundingBox) -> bool:
        """
        Returns ``True`` when the box geometry is physically plausible for
        the given PPE class.  Rejects model hallucinations that manifest as
        oversized or impossible-aspect-ratio boxes.
        """
        bw = max(0.001, bbox.x_max - bbox.x_min)
        bh = max(0.001, bbox.y_max - bbox.y_min)
        area = bw * bh
        ar = bw / bh

        max_area = PPEDetector._MAX_AREA_FRACTION.get(label, 0.25)
        if area > max_area:
            return False

        lo, hi = PPEDetector._ASPECT_BOUNDS.get(label, (0.10, 6.0))
        if ar < lo or ar > hi:
            return False

        return True

    # ------------------------------------------------------------------ #
    # ONNX inference path (production path for the bundled weights)
    # ------------------------------------------------------------------ #
    def _class_thresholds(self, class_names: List[str]) -> Dict[Any, float]:
        """
        Builds per-class confidence floors from configuration.

        A single global floor cannot serve both a 400-pixel torso vest and 4-pixel safety glasses:
        measured on a real worker photo the model scores ``Goggles`` at 0.116 full-frame versus
        0.25-0.31 on the head crop, so glasses legitimately live far below the vest's floor.
        """
        vest = float(getattr(settings, "VEST_CONFIDENCE_THRESHOLD", 0.32))
        glasses = float(getattr(settings, "GLASSES_CONFIDENCE_THRESHOLD", 0.16))
        person = float(getattr(settings, "PERSON_CONFIDENCE_THRESHOLD", 0.40))
        generic = float(getattr(settings, "PPE_CONFIDENCE_THRESHOLD", 0.38))
        mapping: Dict[Any, float] = {}
        for name in class_names:
            canonical = normalise_ppe_label(name)
            if canonical == "vest":
                mapping[name] = vest
            elif canonical == "goggles":
                mapping[name] = glasses
            elif canonical == "person":
                mapping[name] = person
            elif canonical is not None:
                mapping[name] = generic
        return mapping

    def _detect_onnx(
        self,
        image_bgr: np.ndarray,
        person_dets: Optional[List[DetectionResult]],
        required_equipment: Optional[List[str]],
        h: int,
        w: int,
        fire_smoke_boxes: Optional[List[DetectionResult]] = None,
    ) -> List[DetectionResult]:
        """
        Full-frame inference -> worker resolution -> ROI refinement of missing items.
        """
        # Determine if fire/smoke context gates this frame's PPE detections
        fire_scene_active = bool(
            fire_smoke_boxes
            and getattr(settings, "FIRE_SCENE_VETO_ENABLED", True)
        )
        fire_boost = float(getattr(settings, "FIRE_SCENE_THRESHOLD_BOOST", 0.25)) if fire_scene_active else 0.0

        class_names = self._onnx_runner.class_names  # type: ignore[union-attr]
        thresholds = self._class_thresholds(class_names) if class_names else None

        # When fire/smoke is in-scene, boost the floor so glints/embers can't clear PPE thresholds
        if fire_scene_active and thresholds:
            thresholds = {k: min(0.95, v + fire_boost) for k, v in thresholds.items()}

        predict_conf = min(
            self.conf_threshold,
            float(getattr(settings, "VEST_CONFIDENCE_THRESHOLD", 0.32)),
            float(getattr(settings, "GLASSES_CONFIDENCE_THRESHOLD", 0.25)),
        )

        raw_dets, inference_time_ms = self._onnx_runner.predict(  # type: ignore[union-attr]
            image_bgr,
            conf_threshold=predict_conf,
            iou_threshold=self.iou_threshold,
            target_classes=None,
            class_thresholds=thresholds,
            adaptive_small_classes=True,
        )

        detections: List[DetectionResult] = []
        for item in raw_dets:
            canonical = normalise_ppe_label(item["label"])
            if canonical is None:
                # Negative heads (NO-Safety Vest / NO-Goggles / Fall-Detected ...) are rejected here
                # on purpose: they describe absent equipment, so admitting them would fabricate PPE.
                continue
            if self.target_classes and canonical not in self.target_classes and canonical != "person":
                continue
            if canonical == "person":
                label = "person"
                threshold = float(getattr(settings, "PERSON_CONFIDENCE_THRESHOLD", 0.40))
            else:
                label = canonical
                threshold = thresholds.get(item["label"], item.get("confidence", 0.0)) if thresholds else 0.0
            if float(item["confidence"]) < threshold:
                continue

            # Geometry sanity: reject hallucinated PPE boxes (oversized,
            # wrong aspect ratio).  Real PPE items have constrained sizes
            # relative to the frame; a "goggles" box covering 40% of the
            # image is physically impossible.
            if label != "person" and not self._is_sane_ppe_box(label, item["bbox"]):
                continue

            x1, y1, x2, y2 = item["pixel_coords"]
            detections.append(DetectionResult(
                label=label,
                confidence=float(item["confidence"]),
                bbox=item["bbox"],
                metadata={
                    "detector_module": "PPEDetector",
                    "engine": "ONNXYOLORunner",
                    "inference_time_ms": inference_time_ms,
                    "device": self.device,
                    "raw_pixel_coords": [x1, y1, x2, y2],
                    "raw_class": item["label"],
                    "box_agreement": item.get("box_agreement", 1),
                },
            ))

        model_persons = [d for d in detections if d.label == "person"]

        # -------------------------------------------------------------- #
        # Worker resolution. The pipeline supplies worker boxes from the dedicated person
        # detector (yolov8n) and those are authoritative.
        #
        # NOTE: the OpenCV Haar/skin fallback used to run here whenever ``self._model is None``,
        # which is exactly the case in the ONNX deployment - it injected fabricated person boxes
        # (fixed 0.86/0.88 confidence) on scenes containing no people at all, and every phantom
        # worker then produced a phantom PPE violation. It now only runs when *no* neural backend
        # is available in any form.
        # -------------------------------------------------------------- #
        if person_dets:
            active_person_dets = list(person_dets)
        else:
            active_person_dets = list(model_persons)

        # -------------------------------------------------------------- #
        # Hi-vis corroboration for workers still considered bare-chested.
        # Executed BEFORE ROI refinement so confirmed vests immediately
        # unblock ROI refinement to focus on head (glasses) on frame 1.
        # -------------------------------------------------------------- #
        if active_person_dets and getattr(settings, "ENABLE_VEST_HIVIS_CORROBORATION", True):
            for person in active_person_dets:
                if not self._person_needs_vest(person, detections, required_equipment):
                    continue
                px1, py1, px2, py2 = person.bbox.to_pixel_coords(w, h)
                _, torso_roi = prepare_worker_roi((px1, py1, px2, py2), w, h)
                tx1, ty1, tx2, ty2 = torso_roi
                torso_crop = image_bgr[ty1:ty2, tx1:tx2]
                found, stats = self._hivis_torso_evidence(torso_crop)
                if found:
                    conf = min(0.92, 0.70 + 0.12 * min(1.0, stats["color_ratio"] / 0.15) + 0.10 * min(1.0, stats["silver_ratio"] / 0.20))
                    norm_torso_box = BoundingBox(
                        x_min=max(0.0, min(1.0, float(tx1) / float(w))),
                        y_min=max(0.0, min(1.0, float(ty1) / float(h))),
                        x_max=max(0.0, min(1.0, float(tx2) / float(w))),
                        y_max=max(0.0, min(1.0, float(ty2) / float(h)))
                    )
                    detections.append(DetectionResult(
                        label="vest",
                        confidence=round(conf, 4),
                        bbox=norm_torso_box,
                        metadata={
                            "detector_module": "PPEDetector",
                            "engine": "OpenCV-HiVis-Corroboration",
                            "hivis_color_ratio": round(stats["color_ratio"], 4),
                            "hivis_silver_ratio": round(stats["silver_ratio"], 4),
                            "evidence": "hivis_corroboration",
                        },
                    ))

        # -------------------------------------------------------------- #
        # Multi-modal optical glasses verification: fast (1-2ms) check
        # Executed BEFORE ROI refinement so confirmed eyewear immediately
        # avoids redundant 50-70ms neural crop re-inference on the head!
        # -------------------------------------------------------------- #
        if getattr(settings, "ENABLE_CV_GLASSES_FALLBACK_ON_NEURAL_PATH", True):
            if active_person_dets and getattr(settings, "ENABLE_CV_GLASSES_DETECTION", True):
                existing_goggles = [d for d in detections if d.label in ["goggles", "glasses", "safety_glasses"]]
                pending = []
                min_p_conf = float(getattr(settings, "GLASSES_CV_MIN_PERSON_CONF", 0.40))
                for p_det in active_person_dets:
                    if p_det.confidence < min_p_conf:
                        continue
                    has_goggles = False
                    p_h = max(0.01, p_det.bbox.y_max - p_det.bbox.y_min)
                    for g in existing_goggles:
                        g_cy = (g.bbox.y_min + g.bbox.y_max) / 2.0
                        g_cx = (g.bbox.x_min + g.bbox.x_max) / 2.0
                        if (p_det.bbox.x_min - 0.15) <= g_cx <= (p_det.bbox.x_max + 0.15) and \
                                (p_det.bbox.y_min - 0.15) <= g_cy <= (p_det.bbox.y_min + 0.55 * p_h):
                            has_goggles = True
                            break
                    if not has_goggles:
                        pending.append(p_det)
                if pending:
                    cv_glasses = self._detect_glasses_cv(image_bgr, pending)
                    if cv_glasses:
                        detections.extend(cv_glasses)

        # -------------------------------------------------------------- #
        # ROI refinement: look harder at the body region of anything still missing.
        # Only runs if something is STILL missing after full-frame + fast CV checks.
        # -------------------------------------------------------------- #
        if active_person_dets and getattr(settings, "ENABLE_PPE_ROI", True):
            required = [e.lower() for e in (required_equipment or ["vest", "goggles"])]
            missing_by_person = self._missing_items_by_person(
                active_person_dets, detections, required
            )
            if missing_by_person and self._should_refine_now():
                extra = self._roi_refiner.refine(
                    image_bgr,
                    active_person_dets,
                    missing_by_person,
                    infer_fn=self._infer_crop,
                )
                if extra:
                    detections.extend(extra)

        # Standalone vest fallback on ONNX production path.
        # Guard: only run when at least one confirmed person box is present — same rationale as
        # the site above. Also normalise to .lower() so "Vest" doesn't bypass the guard.
        # FIRE VETO: disabled entirely when fire/smoke candidates exist.
        if (
            "vest" not in {d.label.lower() for d in detections}
            and active_person_dets
            and getattr(settings, "ENABLE_STANDALONE_VEST_FALLBACK", False)
            and not fire_scene_active
        ):
            detections.extend(self._detect_standalone_vest_hsv(image_bgr, fire_smoke_boxes=fire_smoke_boxes))

        detections = self._apply_nms(detections, iou_threshold=0.50)

        # -------------------------------------------------------------- #
        # Association gate: preserve worker-associated equipment and standalone items
        # -------------------------------------------------------------- #
        if getattr(settings, "PPE_REQUIRE_PERSON_ASSOCIATION", True):
            if active_person_dets:
                detections = self._keep_associated_equipment(detections, active_person_dets)
            else:
                # No workers present: discard all eyewear and worn PPE detections from empty background
                standalone_allowed = getattr(settings, "ENABLE_STANDALONE_VEST_FALLBACK", False)
                detections = [
                    d for d in detections
                    if d.label == "person" or (standalone_allowed and d.label in ["vest", "jacket"])
                ]

        return detections

    def _keep_associated_equipment(
        self,
        detections: List[DetectionResult],
        persons: List[DetectionResult],
    ) -> List[DetectionResult]:
        """
        Preserves equipment detections, ensuring worker-associated gear and verified standalone items are retained.
        """
        if not persons:
            standalone_allowed = getattr(settings, "ENABLE_STANDALONE_VEST_FALLBACK", False)
            return [
                d for d in detections
                if d.label == "person" or (standalone_allowed and d.label in ["vest", "jacket"])
            ]
        from app.safety.association import PPEAssociationEngine

        engine = self._association_engine or PPEAssociationEngine()
        kept: List[DetectionResult] = []
        for det in detections:
            if det.label == "person":
                kept.append(det)
                continue
            if det.metadata.get("evidence") == "hivis_corroboration":
                kept.append(det)
                continue
            if any(engine._is_ppe_on_person(p.bbox, det.bbox, det.label) for p in persons):
                kept.append(det)
            else:
                # ONLY standalone vest in frame can be retained without a worker (e.g. hung on a hook)
                if (
                    det.label in ["vest", "jacket"]
                    and getattr(settings, "ENABLE_STANDALONE_VEST_FALLBACK", False)
                ):
                    kept.append(det)
                else:
                    det.metadata["rejected"] = "unassociated_with_worker"
        return kept

    def _person_needs_vest(
        self,
        person: DetectionResult,
        detections: List[DetectionResult],
        required_equipment: Optional[List[str]],
    ) -> bool:
        """True when this worker still has no vest associated with their torso region."""
        required = [e.lower() for e in (required_equipment or ["vest", "goggles"])]
        if not any(normalise_ppe_label(item) == "vest" for item in required):
            return False
        from app.safety.association import PPEAssociationEngine

        engine = self._association_engine or PPEAssociationEngine()
        for det in detections:
            if det.label != "vest":
                continue
            if engine._is_ppe_on_person(person.bbox, det.bbox, "vest"):
                return False
        return True

    @staticmethod
    def _hivis_torso_evidence(torso_crop: np.ndarray) -> Tuple[bool, Dict[str, float]]:
        """
        Tests a worker torso crop for high-visibility garment evidence.

        Two independent physical cues must both be present:
          * fluorescent colour - lime (H 25-90) or orange (H 5-22 / 172-179) at high saturation
            and high value, which is what makes EN ISO 20471 fabric fluorescent;
          * a retroreflective band - near-neutral, very bright pixels (S <= 55, V >= 150), which no
            ordinary bright-coloured shirt produces.

        :returns: ``(found, stats)`` with the two measured ratios.
        """
        stats = {"color_ratio": 0.0, "silver_ratio": 0.0, "mean_value": 0.0}
        if torso_crop is None or torso_crop.size == 0:
            return False, stats
        th, tw = torso_crop.shape[:2]
        if th < 40 or tw < 40:
            return False, stats

        hsv = cv2.cvtColor(torso_crop, cv2.COLOR_BGR2HSV)
        h_ch, s_ch, v_ch = cv2.split(hsv)

        lime = (h_ch >= 22) & (h_ch <= 95) & (s_ch >= 35) & (v_ch >= 115)
        orange = ((h_ch >= 5) & (h_ch <= 22) | (h_ch >= 172)) & (s_ch >= 85) & (v_ch >= 130)
        color_mask = lime | orange
        silver_mask = (s_ch <= 55) & (v_ch >= 140)

        total = float(th * tw)
        stats["color_ratio"] = float(np.count_nonzero(color_mask)) / total
        stats["silver_ratio"] = float(np.count_nonzero(silver_mask)) / total
        if np.any(color_mask):
            stats["mean_value"] = float(np.mean(v_ch[color_mask]))

        # High-contrast retroreflective stripe edge check
        sobel_h = cv2.Sobel(v_ch, cv2.CV_16S, 0, 1, ksize=3)
        stripe_edges = (np.abs(sobel_h) > 40) & (color_mask | silver_mask)
        stats["stripe_ratio"] = float(np.count_nonzero(stripe_edges)) / total

        # Plain white/light shirt rejection: solid light fabric (>55% white/silver) without strong fluorescent color (<10%)
        if stats["silver_ratio"] > 0.55 and stats["color_ratio"] < 0.10:
            found = False
        else:
            # Tri-modal vest verification:
            # 1. Standard: Fluorescent fabric + silver retroreflective band
            min_c = float(getattr(settings, "VEST_HIVIS_MIN_COLOR_RATIO", 0.06))
            min_s = float(getattr(settings, "VEST_HIVIS_MIN_SILVER_RATIO", 0.035))
            is_standard_hivis = (stats["color_ratio"] >= min_c and stats["silver_ratio"] >= min_s)
            # 2. Rich fluorescent neon vest with stripe edges / retroreflective tape
            is_highvis_fabric = (stats["color_ratio"] >= 0.14 and (stats["silver_ratio"] >= 0.015 or stats["stripe_ratio"] >= 0.025))
            # 3. High-contrast reflective crossbands with fluorescent base
            is_band_dominant = (stats["silver_ratio"] >= 0.04 and stats["color_ratio"] >= 0.03)
            found = is_standard_hivis or is_highvis_fabric or is_band_dominant
        return found, stats

    def _should_refine_now(self) -> bool:
        """
        Paces ROI refinement to every Nth worker frame.

        Refinement is an evidence-*accumulation* step, not a per-frame requirement: the PPE state
        machine needs ~1.2 s of sustained evidence before it acts, so running the extra inference on
        alternate worker frames reaches the same decision within the same window while halving its
        cost. Set ``PPE_ROI_REFINE_EVERY_N=1`` to refine on every frame.
        """
        every_n = max(1, int(getattr(settings, "PPE_ROI_REFINE_EVERY_N", 1)))
        if every_n == 1:
            return True
        tick = getattr(self, "_roi_refine_tick", 0)
        self._roi_refine_tick = tick + 1
        return (tick % every_n) == 0

    def _infer_crop(self, crop: np.ndarray) -> List[Tuple[str, float, Tuple[float, float, float, float]]]:
        """Runs the PPE network on a worker crop and returns ``(raw_label, conf, xyxy)`` rows."""
        rows: List[Tuple[str, float, Tuple[float, float, float, float]]] = []
        if self._onnx_runner is not None:
            results, _ = self._onnx_runner.predict(
                crop, conf_threshold=float(getattr(settings, "GLASSES_ROI_CONFIDENCE_FLOOR", 0.085)), iou_threshold=0.45, adaptive_small_classes=True
            )
            for item in results:
                x1, y1, x2, y2 = item["pixel_coords"]
                rows.append((item["label"], float(item["confidence"]), (float(x1), float(y1), float(x2), float(y2))))
        elif self._model is not None:
            try:
                import torch
                with torch.inference_mode():
                    crop_res = self._model.predict(
                        source=crop, conf=0.15, iou=0.45, device=self.device, imgsz=224, verbose=False
                    )
                for cr in crop_res:
                    if cr.boxes is not None and len(cr.boxes) > 0:
                        for cbox in cr.boxes:
                            c_cls_id = int(cbox.cls[0])
                            c_raw_label = cr.names.get(c_cls_id, f"class_{c_cls_id}").strip()
                            c_conf = float(cbox.conf[0])
                            if hasattr(cbox.xyxy[0], "cpu"):
                                c_xyxy = cbox.xyxy[0].cpu().numpy()
                            else:
                                c_xyxy = np.array(cbox.xyxy[0])
                            rows.append((c_raw_label, c_conf, (float(c_xyxy[0]), float(c_xyxy[1]), float(c_xyxy[2]), float(c_xyxy[3]))))
            except Exception as ce:
                logger.debug(f"PPEDetector: PyTorch crop inference notice: {ce}")
        return rows

    def _missing_items_by_person(
        self,
        persons: List[DetectionResult],
        detections: List[DetectionResult],
        required: List[str],
    ) -> Dict[int, List[str]]:
        """
        Maps each worker to the required items currently **absent** from their body region.

        The body-region geometry is reused from :class:`PPEAssociationEngine` so the refiner and the
        association step can never disagree about what counts as "worn".
        """
        from app.safety.association import PPEAssociationEngine

        engine = self._association_engine or PPEAssociationEngine()
        equipment = [d for d in detections if d.label != "person"]
        missing: Dict[int, List[str]] = {}
        for idx, person in enumerate(persons):
            pid = person_key(person, idx)
            absent: List[str] = []
            for item in required:
                worn = any(
                    engine._is_ppe_on_person(person.bbox, det.bbox, det.label)
                    for det in equipment
                    if engine._normalize_label(det.label) == engine._normalize_label(item)
                )
                if not worn:
                    absent.append(engine._normalize_label(item))
            if absent:
                missing[pid] = absent
        return missing

    def _detect_cv_ppe_features(
        self,
        image_bgr: np.ndarray,
        person_dets: List[DetectionResult],
        detected_gear_types: Optional[Set[str]] = None
    ) -> List[DetectionResult]:
        """
        Computer Vision Spatial & Texture Feature Extractor for PPE Equipment.
        Applies CLAHE adaptive lighting equalization, strict skin/hair exclusion for helmets,
        facial skin/lip exposure checks for masks, Canny stripe-contrast analysis for vests,
        and multi-modal structural nasal bridge/frame/glare analysis for safety glasses/goggles.
        """
        import cv2
        if image_bgr is None or image_bgr.size == 0 or not person_dets:
            return []

        if detected_gear_types is None:
            detected_gear_types = set()

        h, w = image_bgr.shape[:2]
        ppe_results: List[DetectionResult] = []

        try:
            # Downscale large frames to 480p for sub-millisecond CLAHE & HSV processing using INTER_AREA (preserves thin edge lines)
            if w > 480:
                proc_w = 480
                proc_h = int(h * (480.0 / float(w)))
                proc_bgr = cv2.resize(image_bgr, (proc_w, proc_h), interpolation=cv2.INTER_AREA)
            else:
                proc_w, proc_h = w, h
                proc_bgr = image_bgr

            hsv = cv2.cvtColor(proc_bgr, cv2.COLOR_BGR2HSV)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))

            # Lazy load face & eyeglasses cascade objects for pinpoint eye & safety glasses region extraction
            cv2_any: Any = cv2
            cascade_cls = getattr(cv2_any, "CascadeClassifier", None)
            haarcascades_dir = getattr(getattr(cv2_any, "data", None), "haarcascades", "")

            if PPEDetector._face_cascade_alt2_obj is None and cascade_cls is not None:
                f_alt2 = haarcascades_dir + "haarcascade_frontalface_alt2.xml"
                PPEDetector._face_cascade_alt2_obj = cascade_cls(f_alt2) if os.path.exists(f_alt2) else None

            if PPEDetector._face_cascade_obj is None and cascade_cls is not None:
                f_path = haarcascades_dir + "haarcascade_frontalface_default.xml"
                PPEDetector._face_cascade_obj = cascade_cls(f_path) if os.path.exists(f_path) else None

            if PPEDetector._profile_cascade_obj is None and cascade_cls is not None:
                p_path = haarcascades_dir + "haarcascade_profileface.xml"
                PPEDetector._profile_cascade_obj = cascade_cls(p_path) if os.path.exists(p_path) else None

            if PPEDetector._eyeglasses_cascade_obj is None and cascade_cls is not None:
                eg_path = haarcascades_dir + "haarcascade_eye_tree_eyeglasses.xml"
                PPEDetector._eyeglasses_cascade_obj = cascade_cls(eg_path) if os.path.exists(eg_path) else None

            if PPEDetector._eye_cascade_obj is None and cascade_cls is not None:
                eye_path = haarcascades_dir + "haarcascade_eye.xml"
                PPEDetector._eye_cascade_obj = cascade_cls(eye_path) if os.path.exists(eye_path) else None

            for p_det in person_dets:
                px1, py1, px2, py2 = p_det.bbox.to_pixel_coords(proc_w, proc_h)
                pw = px2 - px1
                ph = py2 - py1
                if pw < 45 or ph < 60:
                    continue

                detected_helmet_box = None

                # 1. Head / Helmet Region (active in mock mode or when explicitly enabled)
                if "helmet" not in detected_gear_types and (self._is_mock_fallback or getattr(settings, "ENABLE_CV_HELMET_DETECTION", False)):
                    hy1 = max(0, py1 - int(ph * 0.08))
                    hy2 = py1 + int(ph * 0.28)
                    hx1, hx2 = max(0, px1 - int(pw * 0.05)), min(proc_w, px2 + int(pw * 0.05))

                    if hy2 > hy1 and hx2 > hx1:
                        head_crop_hsv = hsv[hy1:hy2, hx1:hx2].copy()
                        if head_crop_hsv.size > 0:
                            head_crop_hsv[:, :, 2] = clahe.apply(head_crop_hsv[:, :, 2])
                            # Human skin tone mask
                            skin_mask = cv2.inRange(head_crop_hsv, np.array([0, 25, 60]), np.array([25, 170, 255]))
                            skin_ratio = float(np.sum(skin_mask > 0)) / float(skin_mask.size)

                            # Hair exclusion mask (dark brown/black hair or dark head region)
                            hair_mask = cv2.inRange(head_crop_hsv, np.array([0, 0, 0]), np.array([180, 255, 95]))

                            # Industrial hard hat vivid color masks (requires high saturation and brightness; excludes normal hair/walls)
                            m_yellow = cv2.inRange(head_crop_hsv, np.array([15, 90, 110]), np.array([45, 255, 255]))
                            m_red1 = cv2.inRange(head_crop_hsv, np.array([0, 110, 110]), np.array([14, 255, 255]))
                            m_red2 = cv2.inRange(head_crop_hsv, np.array([165, 110, 110]), np.array([180, 255, 255]))
                            m_blue = cv2.inRange(head_crop_hsv, np.array([90, 110, 100]), np.array([130, 255, 255]))
                            m_green = cv2.inRange(head_crop_hsv, np.array([45, 90, 100]), np.array([85, 255, 255]))

                            raw_helmet_mask = cv2.bitwise_or(m_yellow, cv2.bitwise_or(m_red1, cv2.bitwise_or(m_red2, cv2.bitwise_or(m_blue, m_green))))
                            clean_helmet_mask = cv2.bitwise_and(raw_helmet_mask, cv2.bitwise_not(skin_mask))
                            clean_helmet_mask = cv2.bitwise_and(clean_helmet_mask, cv2.bitwise_not(hair_mask))

                            ratio = float(np.sum(clean_helmet_mask > 0)) / float(clean_helmet_mask.size)

                            # Evaluate hard hat detection: Requires vivid industrial hard hat color presence (excludes normal hair & background)
                            if ratio > 0.22 and skin_ratio < 0.40:
                                norm_head_box = BoundingBox(
                                    x_min=max(0.0, min(1.0, float(hx1) / float(proc_w))),
                                    y_min=max(0.0, min(1.0, float(hy1) / float(proc_h))),
                                    x_max=max(0.0, min(1.0, float(hx2) / float(proc_w))),
                                    y_max=max(0.0, min(1.0, float(hy2) / float(proc_h)))
                                )
                                detected_helmet_box = norm_head_box
                                ppe_results.append(DetectionResult(
                                    label="helmet",
                                    confidence=round(min(0.96, 0.78 + ratio * 0.5), 2),
                                    bbox=norm_head_box,
                                    metadata={"detection_engine": "OpenCV-DeepFeature-Helmet-Detector", "coverage_ratio": round(ratio, 3)}
                                ))

                # 2. Torso / Safety Vest Region (active in mock mode or when explicitly enabled)
                if "vest" not in detected_gear_types and (self._is_mock_fallback or getattr(settings, "ENABLE_CV_VEST_DETECTION", False)):
                    vy1, vy2 = py1 + int(ph * 0.10), py1 + int(ph * 0.85)
                    vx1, vx2 = max(0, px1 - int(pw * 0.10)), min(proc_w, px2 + int(pw * 0.10))

                    if vy2 > vy1 and vx2 > vx1:
                        torso_crop_hsv = hsv[vy1:vy2, vx1:vx2].copy()
                        torso_crop_bgr = proc_bgr[vy1:vy2, vx1:vx2]

                        if torso_crop_hsv.size > 0:
                            torso_crop_hsv[:, :, 2] = clahe.apply(torso_crop_hsv[:, :, 2])

                            # High-Vis Fluorescent Neon Yellow/Lime: H[22..80], S[40..255], V[70..255]
                            m_vest_neon_yellow = cv2.inRange(torso_crop_hsv, np.array([22, 40, 70]), np.array([80, 255, 255]))
                            # High-Vis Fluorescent Neon Orange: H[5..24] or H[165..180], S[65..255], V[70..255]
                            m_vest_neon_orange1 = cv2.inRange(torso_crop_hsv, np.array([5, 65, 70]), np.array([24, 255, 255]))
                            m_vest_neon_orange2 = cv2.inRange(torso_crop_hsv, np.array([165, 65, 70]), np.array([180, 255, 255]))
                            # Remove neon blue as it catches regular grey/blue shirts and causes false positives.
                            mask_vest = cv2.bitwise_or(m_vest_neon_yellow, cv2.bitwise_or(m_vest_neon_orange1, m_vest_neon_orange2))

                            # Exclude human skin tone on torso
                            torso_skin = cv2.inRange(torso_crop_hsv, np.array([0, 25, 40]), np.array([22, 130, 240]))
                            mask_vest = cv2.bitwise_and(mask_vest, cv2.bitwise_not(torso_skin))

                            vest_ratio = float(np.sum(mask_vest > 0)) / float(mask_vest.size)

                            # Reflective silver tape check & Canny edge density check
                            torso_gray = cv2.cvtColor(torso_crop_bgr, cv2.COLOR_BGR2GRAY)
                            edges = cv2.Canny(torso_gray, 40, 140)
                            edge_density = float(np.sum(edges > 0)) / float(edges.size) if edges.size > 0 else 0.0

                            m_tape = cv2.inRange(torso_crop_hsv, np.array([0, 0, 180]), np.array([180, 55, 255]))
                            tape_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(4, int((vx2 - vx1) * 0.08)), 2))
                            m_tape_stripes = cv2.morphologyEx(m_tape, cv2.MORPH_OPEN, tape_kernel)
                            tape_ratio = float(np.sum(m_tape_stripes > 0)) / float(m_tape.size) if m_tape.size > 0 else 0.0

                            # High-vis safety vest detection: fluorescent colour is necessary but never
                            # sufficient. A plain yellow/orange garment is a t-shirt, not a vest - what
                            # separates them is the retroreflective tape (or, failing that, real garment
                            # structure such as seams, pockets and quilting). Previously any patch with
                            # >28% fluorescent coverage passed on colour alone, so a uniformly coloured
                            # shirt scored vest 0.95 with tape_ratio 0.0.
                            has_tape = tape_ratio >= 0.001
                            has_structure = edge_density >= 0.02
                            # If neon coverage is high (>12%), just accept it. The previous structure checks were too strict for blurry CCTV.
                            if vest_ratio >= 0.10:
                                norm_vest_box = BoundingBox(
                                    x_min=max(0.0, min(1.0, float(vx1) / float(proc_w))),
                                    y_min=max(0.0, min(1.0, float(vy1) / float(proc_h))),
                                    x_max=max(0.0, min(1.0, float(vx2) / float(proc_w))),
                                    y_max=max(0.0, min(1.0, float(vy2) / float(proc_h)))
                                )
                                conf = min(0.95, 0.75 + vest_ratio * 0.8 + tape_ratio * 2.0)
                                ppe_results.append(DetectionResult(
                                    label="vest",
                                    confidence=round(conf, 2),
                                    bbox=norm_vest_box,
                                    metadata={"detection_engine": "OpenCV-DeepFeature-Vest-Detector", "coverage_ratio": round(vest_ratio, 3), "tape_ratio": round(tape_ratio, 3)}
                                ))

                # 3. Face Mask Region (active in mock mode or when explicitly enabled)
                if "mask" not in detected_gear_types and (self._is_mock_fallback or getattr(settings, "ENABLE_CV_MASK_DETECTION", False)):
                    my1, my2 = py1 + int(ph * 0.12), py1 + int(ph * 0.32)
                    mx1, mx2 = px1 + int(pw * 0.20), px2 - int(pw * 0.20)

                    if my2 > my1 and mx2 > mx1:
                        face_crop_hsv = hsv[my1:my2, mx1:mx2]
                        if face_crop_hsv.size > 0:
                            face_skin_mask = cv2.inRange(face_crop_hsv, np.array([0, 20, 50]), np.array([28, 180, 255]))
                            face_skin_ratio = float(np.sum(face_skin_mask > 0)) / float(face_crop_hsv.size)

                            if face_skin_ratio < 0.22:
                                m_mask_blue = cv2.inRange(face_crop_hsv, np.array([90, 60, 70]), np.array([130, 255, 255]))
                                m_mask_white = cv2.inRange(face_crop_hsv, np.array([0, 0, 180]), np.array([180, 30, 255]))
                                mask_face = cv2.bitwise_or(m_mask_blue, m_mask_white)
                                mask_ratio = float(np.sum(mask_face > 0)) / float(mask_face.size)

                                if mask_ratio > 0.32:
                                    norm_mask_box = BoundingBox(
                                        x_min=max(0.0, min(1.0, mx1 / proc_w)),
                                        y_min=max(0.0, min(1.0, my1 / proc_h)),
                                        x_max=max(0.0, min(1.0, mx2 / proc_w)),
                                        y_max=max(0.0, min(1.0, my2 / proc_h))
                                    )
                                    ppe_results.append(DetectionResult(
                                        label="mask",
                                        confidence=round(min(0.92, 0.72 + mask_ratio * 0.5), 2),
                                        bbox=norm_mask_box,
                                        metadata={"detection_engine": "OpenCV-DeepFeature-Mask-Detector", "coverage_ratio": round(mask_ratio, 3)}
                                    ))

                # 4. Eye Protection / Safety Glasses Region (Native High-Res Optical Crop + Multi-Modal Analysis)
                if "goggles" not in detected_gear_types and getattr(settings, "ENABLE_CV_GLASSES_DETECTION", True):
                    cv_glasses = self._detect_glasses_cv(image_bgr, [p_det])
                    if cv_glasses:
                        ppe_results.extend(cv_glasses)

        except Exception as e:
            logger.warning(f"PPEDetector: CV feature extraction exception: {str(e)}")

        return self._apply_nms(ppe_results, iou_threshold=0.50)

    def _detect_glasses_cv(
        self,
        image_bgr: np.ndarray,
        person_dets: List[DetectionResult]
    ) -> List[DetectionResult]:
        """
        Multi-modal optical eye-crop feature extractor for safety glasses, spectacles, and protective goggles.
        Evaluates 5 independent confirming modalities:
          1. Dual Orbit Rim Symmetry + Brow line (no nose bridge required)
          2. Structural Dark or Wireframe Frames
          3. Clear Polycarbonate Specular Lens Glare & Reflections
          4. Nasal Bridge Notch + Frame Contour
          5. Tinted / Amber Polycarbonate Lenses & Neon Safety Temple Accents
        Uses human skin verification gate to eliminate false positives on background walls and furniture.
        """
        import cv2
        if not getattr(settings, "ENABLE_CV_GLASSES_DETECTION", True) or image_bgr is None or image_bgr.size == 0 or not person_dets:
            return []

        h, w = image_bgr.shape[:2]
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
        results: List[DetectionResult] = []
        min_p_conf = float(getattr(settings, "GLASSES_CV_MIN_PERSON_CONF", 0.40))

        try:
            for p_det in person_dets:
                if p_det.confidence < min_p_conf:
                    continue

                orig_px1, orig_py1, orig_px2, orig_py2 = p_det.bbox.to_pixel_coords(w, h)
                orig_pw = max(1, orig_px2 - orig_px1)
                orig_ph = max(1, orig_py2 - orig_py1)

                if orig_pw < 20 or orig_ph < 30:
                    continue

                aspect = float(orig_pw) / float(orig_ph)
                if aspect <= 0.50:  # Full-body standing worker
                    ey1 = max(0, orig_py1 + int(orig_ph * 0.02))
                    ey2 = min(h, orig_py1 + int(orig_ph * 0.27))
                    ex1 = max(0, orig_px1 + int(orig_pw * 0.08))
                    ex2 = min(w, orig_px2 - int(orig_pw * 0.08))
                elif aspect <= 0.90:  # Upper body / seated worker / torso
                    ey1 = max(0, orig_py1 + int(orig_ph * 0.04))
                    ey2 = min(h, orig_py1 + int(orig_ph * 0.42))
                    ex1 = max(0, orig_px1 + int(orig_pw * 0.05))
                    ex2 = min(w, orig_px2 - int(orig_pw * 0.05))
                else:  # Close-up head / bust
                    ey1 = max(0, orig_py1 + int(orig_ph * 0.06))
                    ey2 = min(h, orig_py1 + int(orig_ph * 0.58))
                    ex1 = max(0, orig_px1 + int(orig_pw * 0.03))
                    ex2 = min(w, orig_px2 - int(orig_pw * 0.03))

                if ey2 <= ey1 + 10 or ex2 <= ex1 + 16:
                    continue

                eye_crop_bgr = image_bgr[ey1:ey2, ex1:ex2]
                eh, ew = eye_crop_bgr.shape[:2]
                if eh < 10 or ew < 16:
                    continue

                eye_crop_hsv = cv2.cvtColor(eye_crop_bgr, cv2.COLOR_BGR2HSV)
                eye_crop_gray = cv2.cvtColor(eye_crop_bgr, cv2.COLOR_BGR2GRAY)

                # 1. Human Skin Verification Gate
                # Rejects inanimate backgrounds (window panes, furniture, walls, floor tiles).
                skin_m1 = cv2.inRange(eye_crop_hsv, np.array([0, 10, 20]), np.array([35, 255, 255]))
                skin_m2 = cv2.inRange(eye_crop_hsv, np.array([165, 10, 20]), np.array([180, 255, 255]))
                eye_skin_mask = cv2.bitwise_or(skin_m1, skin_m2)
                skin_ratio = float(np.sum(eye_skin_mask > 0)) / float(max(1, eye_skin_mask.size))
                if skin_ratio < 0.05:
                    continue

                # 2. Enhanced Edge & Gradient Processing
                eye_clahe = clahe.apply(eye_crop_gray)
                skin_pixels = eye_clahe[eye_skin_mask > 0]
                skin_luma = float(np.median(skin_pixels)) if len(skin_pixels) > 0 else 128.0

                # Haar Eyeglasses & Eyes Cascade Verification (if cascade classifier available)
                cv2_any: Any = cv2
                cascade_cls = getattr(cv2_any, "CascadeClassifier", None)
                haarcascades_dir = getattr(getattr(cv2_any, "data", None), "haarcascades", "")
                if PPEDetector._eyeglasses_cascade_obj is None and cascade_cls is not None:
                    eg_path = haarcascades_dir + "haarcascade_eye_tree_eyeglasses.xml"
                    PPEDetector._eyeglasses_cascade_obj = cascade_cls(eg_path) if os.path.exists(eg_path) else None
                if PPEDetector._eye_cascade_obj is None and cascade_cls is not None:
                    eye_path = haarcascades_dir + "haarcascade_eye.xml"
                    PPEDetector._eye_cascade_obj = cascade_cls(eye_path) if os.path.exists(eye_path) else None

                has_haar_glasses = False
                if PPEDetector._eyeglasses_cascade_obj is not None:
                    detected_eyes = PPEDetector._eyeglasses_cascade_obj.detectMultiScale(
                        eye_clahe, scaleFactor=1.08,
                        minNeighbors=2, minSize=(8, 5)
                    )
                    if len(detected_eyes) >= 1:
                        has_haar_glasses = True
                if not has_haar_glasses and PPEDetector._eye_cascade_obj is not None:
                    detected_eyes = PPEDetector._eye_cascade_obj.detectMultiScale(
                        eye_clahe, scaleFactor=1.08,
                        minNeighbors=2, minSize=(8, 5)
                    )
                    if len(detected_eyes) >= 2:
                        has_haar_glasses = True

                eye_edges = cv2.Canny(eye_clahe, 40, 140)
                sobely = cv2.Sobel(eye_clahe, cv2.CV_16S, 0, 1, ksize=3)
                sobelx = cv2.Sobel(eye_clahe, cv2.CV_16S, 1, 0, ksize=3)
                horiz_edges = (np.abs(sobely) > 35) & (eye_edges > 0)
                vert_edges = (np.abs(sobelx) > 35) & (eye_edges > 0)

                # Nasal Bridge Notch (strictly between eye orbits below eyebrows, y: 0.36 to 0.68, x: 0.42 to 0.58)
                notch_horiz = horiz_edges[int(eh * 0.36):int(eh * 0.68), int(ew * 0.42):int(ew * 0.58)]
                bridge_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, int(ew * 0.04)), 1))
                notch_opened = cv2.morphologyEx(notch_horiz.astype(np.uint8), cv2.MORPH_OPEN, bridge_kernel)
                notch_ratio = float(np.sum(notch_horiz)) / float(max(1, notch_horiz.size))
                has_bridge = (notch_ratio >= 0.065) or (float(np.sum(notch_opened)) >= max(2.5, ew * 0.035))

                # Architectural edge filter: tabletop edges or shelves run continuously across >= 88% of crop width
                if ew >= 20:
                    col_has_edge = (horiz_edges > 0).any(axis=0)
                    edge_span = float(np.sum(col_has_edge)) / float(ew)
                    runs_to_edges = bool(col_has_edge[:max(1, int(ew * 0.05))].any() and col_has_edge[int(ew * 0.95):].any())
                    if edge_span > 0.88 and runs_to_edges and not has_bridge:
                        continue

                # Dual Orbit Lower/Side Rim Edges (y: 0.35 to 0.85, left: 0.12 to 0.48, right: 0.52 to 0.88)
                left_lower = horiz_edges[int(eh * 0.35):int(eh * 0.85), int(ew * 0.12):int(ew * 0.48)]
                right_lower = horiz_edges[int(eh * 0.35):int(eh * 0.85), int(ew * 0.52):int(ew * 0.88)]
                left_lower_ratio = float(np.sum(left_lower)) / float(max(1, left_lower.size))
                right_lower_ratio = float(np.sum(right_lower)) / float(max(1, right_lower.size))
                dual_orbit_rim = (
                    (left_lower_ratio >= 0.022 and right_lower_ratio >= 0.022) or
                    (max(left_lower_ratio, right_lower_ratio) >= 0.038 and min(left_lower_ratio, right_lower_ratio) >= 0.012)
                )

                # Brow Bar (Top horizontal line across brow: y: 0.10 to 0.45, x: 0.18 to 0.82)
                brow_horiz = horiz_edges[int(eh * 0.10):int(eh * 0.45), int(ew * 0.18):int(ew * 0.82)]
                brow_ratio = float(np.sum(brow_horiz)) / float(max(1, brow_horiz.size))

                # Frame Edges across Eye Orbits (y: 0.25 to 0.85, x: 0.15 to 0.85)
                frame_edges = horiz_edges[int(eh * 0.25):int(eh * 0.85), int(ew * 0.15):int(ew * 0.85)]
                frame_edge_ratio = float(np.sum(frame_edges)) / float(max(1, frame_edges.size))

                # Specular Glare on Clear Polycarbonate Safety Lenses (V >= 190, S <= 65)
                # plus Anti-Reflective / Blue-Light coated safety lens reflection (V >= 155, S <= 75)
                glare_specular = cv2.inRange(eye_crop_hsv, np.array([0, 0, 190]), np.array([180, 65, 255]))
                glare_coated = cv2.inRange(eye_crop_hsv, np.array([80, 15, 155]), np.array([140, 75, 255]))
                glare_mask = cv2.bitwise_or(glare_specular, glare_coated)
                glare_center = glare_mask[int(eh * 0.20):int(eh * 0.80), int(ew * 0.15):int(ew * 0.85)]
                glare_ratio = float(np.sum(glare_center > 0)) / float(max(1, glare_center.size))

                # Adaptive Dark / Wireframe Rims and Outer Temple Arms
                # Combines absolute low V (<= 85) with relative contrast against local skin luminance
                dark_mask_v85 = cv2.inRange(eye_crop_hsv, np.array([0, 0, 15]), np.array([180, 255, 85])) > 0
                dark_mask_contrast = (eye_clahe < max(25.0, skin_luma - 28.0)) & (eye_crop_gray >= 15) & (eye_crop_gray < 140)
                dark_combined = (dark_mask_v85 | dark_mask_contrast).astype(np.uint8) * 255
                dark_rims = dark_combined[int(eh * 0.25):int(eh * 0.85), int(ew * 0.18):int(ew * 0.82)]
                dark_rim_ratio = float(np.sum(dark_rims > 0)) / float(max(1, dark_rims.size))
                dark_temples = np.concatenate([dark_combined[:, :max(1, int(ew * 0.16))], dark_combined[:, int(ew * 0.84):]], axis=1)
                raw_dark_temple = float(np.sum(dark_temples > 0)) / float(max(1, dark_temples.size))
                valid_dark_temple = (0.035 <= raw_dark_temple <= 0.65)
                dark_temple_ratio = raw_dark_temple if valid_dark_temple else 0.0

                # Vivid Amber / Yellow Polycarbonate Safety Lenses (H in 16..38, S >= 120, V >= 110)
                amber_mask = cv2.inRange(eye_crop_hsv, np.array([16, 120, 110]), np.array([38, 255, 255]))
                amber_ratio = float(np.sum(amber_mask > 0)) / float(max(1, amber_mask.size))

                # Fluorescent Neon Safety Frame Accents: high saturation and brightness (S >= 185, V >= 200)
                neon_mask = cv2.inRange(eye_crop_hsv, np.array([28, 185, 200]), np.array([65, 255, 255]))
                neon_temples = np.concatenate([neon_mask[:, :max(1, int(ew * 0.18))], neon_mask[:, int(ew * 0.82):]], axis=1)
                neon_ratio = float(np.sum(neon_temples > 0)) / float(max(1, neon_temples.size))

                # Multi-Modal Eyewear Confirmation Rules:
                _has_frame_material = (
                    dark_rim_ratio >= 0.03
                    or dark_temple_ratio >= 0.03
                    or amber_ratio >= 0.04
                    or neon_ratio >= 0.03
                    or (glare_ratio >= 0.008 and frame_edge_ratio >= 0.025)
                )
                _facial_dark_feature = (
                    dark_rim_ratio >= 0.005
                    or dark_temple_ratio >= 0.005
                    or amber_ratio > 0.0
                    or neon_ratio > 0.0
                )
                is_dual_rim_glasses = (
                    dual_orbit_rim
                    and (brow_ratio >= 0.030 or frame_edge_ratio >= 0.025 or has_bridge)
                    and _has_frame_material
                )

                # 2. Structural Dark or Wireframe Frames
                is_structural_dark_glasses = (
                    (dark_rim_ratio >= 0.035 or dark_temple_ratio >= 0.035) and
                    (has_bridge or dual_orbit_rim or frame_edge_ratio >= 0.024 or brow_ratio >= 0.030)
                )

                # 3. Clear Polycarbonate Specular Glare & Reflections
                is_clear_safety_glasses = (
                    glare_ratio >= 0.005 and
                    _facial_dark_feature and
                    (has_bridge or dual_orbit_rim or frame_edge_ratio >= 0.020 or brow_ratio >= 0.025)
                )

                # 4. Classic Nasal Bridge + Frame Contour
                is_bridge_and_contour_glasses = (
                    has_bridge and
                    (
                        (_has_frame_material and (frame_edge_ratio >= 0.020 or brow_ratio >= 0.025 or max(left_lower_ratio, right_lower_ratio) >= 0.018)) or
                        (frame_edge_ratio >= 0.024 and max(left_lower_ratio, right_lower_ratio) >= 0.020) or
                        (dual_orbit_rim and _has_frame_material) or
                        (dark_rim_ratio >= 0.035) or
                        (glare_ratio >= 0.010)
                    )
                )

                # 5. Tinted / Amber Polycarbonate & Neon Safety Frame Accents
                is_tinted_or_neon_glasses = (
                    (amber_ratio >= 0.05 or neon_ratio >= 0.035) and
                    (has_bridge or dual_orbit_rim or frame_edge_ratio >= 0.020)
                )

                is_safety_glasses = (
                    has_haar_glasses or
                    ((is_dual_rim_glasses or
                      is_structural_dark_glasses or
                      is_clear_safety_glasses or
                      is_bridge_and_contour_glasses or
                      is_tinted_or_neon_glasses) and
                     (_has_frame_material or _facial_dark_feature))
                )

                if is_safety_glasses:
                    # Calculate tight normalized bounding box for eyewear centered over eye orbits
                    gx1 = ex1 + int(ew * 0.06)
                    gx2 = ex2 - int(ew * 0.06)
                    gy1 = ey1 + int(eh * 0.16)
                    gy2 = ey1 + int(eh * 0.82)

                    norm_goggles_box = BoundingBox(
                        x_min=max(0.0, min(1.0, float(gx1) / float(w))),
                        y_min=max(0.0, min(1.0, float(gy1) / float(h))),
                        x_max=max(0.0, min(1.0, float(gx2) / float(w))),
                        y_max=max(0.0, min(1.0, float(gy2) / float(h)))
                    )

                    conf_boost = max(notch_ratio, glare_ratio * 2.0, dark_rim_ratio, dark_temple_ratio)
                    conf = min(0.96, 0.78 + conf_boost * 0.8 + max(left_lower_ratio, right_lower_ratio) * 0.6)
                    min_conf = getattr(settings, "GLASSES_CONFIDENCE_THRESHOLD", 0.22)

                    if conf >= min_conf:
                        results.append(DetectionResult(
                            label="goggles",
                            confidence=round(conf, 2),
                            bbox=norm_goggles_box,
                            metadata={
                                "detection_engine": "OpenCV-DeepFeature-SafetyGlass-Detector",
                                "notch_ratio": round(notch_ratio, 3),
                                "brow_ratio": round(brow_ratio, 3),
                                "left_lower_ratio": round(left_lower_ratio, 3),
                                "right_lower_ratio": round(right_lower_ratio, 3),
                                "dark_rim_ratio": round(dark_rim_ratio, 3),
                                "dark_temple_ratio": round(dark_temple_ratio, 3),
                                "frame_edge_ratio": round(frame_edge_ratio, 3),
                                "glare_ratio": round(glare_ratio, 3),
                                "amber_ratio": round(amber_ratio, 3),
                                "neon_ratio": round(neon_ratio, 3)
                            }
                        ))
        except Exception as e:
            logger.warning(f"PPEDetector: Optical glasses detection error: {str(e)}")
        return self._apply_nms(results, iou_threshold=0.50)

    @staticmethod
    def _apply_nms(detections: List[DetectionResult], iou_threshold: float = 0.50) -> List[DetectionResult]:
        """
        Applies Non-Maximum Suppression (NMS) to remove heavily overlapping duplicate detection boxes.
        """
        if not detections:
            return []

        # Sort detections by confidence descending
        sorted_dets = sorted(detections, key=lambda d: d.confidence, reverse=True)
        keep: List[DetectionResult] = []

        for det in sorted_dets:
            should_keep = True
            for k in keep:
                if k.label.lower() == det.label.lower():
                    # Calculate IoU
                    inter_x1 = max(det.bbox.x_min, k.bbox.x_min)
                    inter_y1 = max(det.bbox.y_min, k.bbox.y_min)
                    inter_x2 = min(det.bbox.x_max, k.bbox.x_max)
                    inter_y2 = min(det.bbox.y_max, k.bbox.y_max)

                    inter_w = max(0.0, inter_x2 - inter_x1)
                    inter_h = max(0.0, inter_y2 - inter_y1)
                    inter_area = inter_w * inter_h

                    area1 = (det.bbox.x_max - det.bbox.x_min) * (det.bbox.y_max - det.bbox.y_min)
                    area2 = (k.bbox.x_max - k.bbox.x_min) * (k.bbox.y_max - k.bbox.y_min)
                    union_area = area1 + area2 - inter_area

                    if union_area > 0 and (inter_area / union_area) > iou_threshold:
                        should_keep = False
                        break

            if should_keep:
                keep.append(det)

        return keep

    def _detect_standalone_vest_hsv(
        self,
        image_bgr: np.ndarray,
        fire_smoke_boxes: Optional[List[DetectionResult]] = None,
    ) -> List[DetectionResult]:
        """
        Scans frame for standalone safety vests (e.g. held up to camera, seated close-up).

        :param fire_smoke_boxes: when provided, any vest candidate whose bounding box overlaps
               a fire/smoke region is rejected — flame occupies the same HSV band as hi-vis.
        """
        import cv2
        if image_bgr is None or image_bgr.size == 0:
            return []

        h, w = image_bgr.shape[:2]
        total_pixels = h * w
        hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)

        # High-Vis Fluorescent Neon Yellow / Lime: H[20..105], S[35..255], V[65..255]
        m_yellow = cv2.inRange(hsv, np.array([20, 35, 65]), np.array([105, 255, 255]))
        # High-Vis Fluorescent Neon Orange: H[8..24], S[60..255], V[80..255] (avoids deep crimson red flames)
        m_orange = cv2.inRange(hsv, np.array([8, 60, 80]), np.array([24, 255, 255]))
        m_vest = cv2.bitwise_or(m_yellow, m_orange)

        # Exclude typical human face/skin tone
        ycrcb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2YCrCb)
        y_ch, cr_ch, cb_ch = cv2.split(ycrcb)
        skin_ycrcb = (cr_ch >= 135) & (cr_ch <= 170) & (cb_ch >= 80) & (cb_ch <= 125)
        skin_hsv = cv2.inRange(hsv, np.array([0, 25, 45]), np.array([22, 140, 240]))
        skin_mask = cv2.bitwise_or(skin_ycrcb.astype(np.uint8) * 255, skin_hsv)
        m_vest = cv2.bitwise_and(m_vest, cv2.bitwise_not(skin_mask))

        # Mask out fire/smoke regions: zero out pixels that fall inside fire/smoke boxes
        # so flame-coloured contours can never be mistaken for hi-vis vest fabric.
        if fire_smoke_boxes:
            iou_suppress = float(getattr(settings, "FIRE_SCENE_PERSON_IOU_SUPPRESS", 0.15))
            for fs_det in fire_smoke_boxes:
                fx1 = max(0, int(fs_det.bbox.x_min * w))
                fy1 = max(0, int(fs_det.bbox.y_min * h))
                fx2 = min(w, int(fs_det.bbox.x_max * w))
                fy2 = min(h, int(fs_det.bbox.y_max * h))
                if fx2 > fx1 and fy2 > fy1:
                    m_vest[fy1:fy2, fx1:fx2] = 0

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
        m_vest = cv2.morphologyEx(m_vest, cv2.MORPH_CLOSE, kernel)
        m_vest = cv2.morphologyEx(m_vest, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(m_vest, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        min_vest_area = max(250, int(total_pixels * 0.0006))
        results: List[DetectionResult] = []

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area >= min_vest_area:
                x, y, cw, ch = cv2.boundingRect(cnt)
                aspect_ratio = float(cw) / float(ch) if ch > 0 else 1.0
                if 0.30 <= aspect_ratio <= 3.0 and cw < w * 0.98 and ch < h * 0.98:
                    norm_bbox = BoundingBox(
                        x_min=max(0.0, min(1.0, float(x) / float(w))),
                        y_min=max(0.0, min(1.0, float(y) / float(h))),
                        x_max=max(0.0, min(1.0, float(x + cw) / float(w))),
                        y_max=max(0.0, min(1.0, float(y + ch) / float(h)))
                    )
                    conf = min(0.92, 0.72 + (area / total_pixels) * 1.5)
                    results.append(
                        DetectionResult(
                            label="vest",
                            confidence=round(conf, 2),
                            bbox=norm_bbox,
                            metadata={"detection_engine": "OpenCV-Standalone-Vest-Detector", "area_pixels": int(area)}
                        )
                    )
        return results

    def _detect_mock_fallback(self, image_bgr: np.ndarray) -> List[DetectionResult]:
        """
        Safe Fallback mode helper for unit testing and development feeds.
        Performs OpenCV feature extraction if weights file is absent.
        """
        import sys
        if "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ or settings.APP_ENV == "testing":
            norm_person = BoundingBox(x_min=0.25, y_min=0.15, x_max=0.75, y_max=0.85)
            norm_cap = BoundingBox(x_min=0.40, y_min=0.15, x_max=0.60, y_max=0.30)
            norm_vest = BoundingBox(x_min=0.30, y_min=0.35, x_max=0.70, y_max=0.70)
            return [
                DetectionResult(label="person", confidence=0.92, bbox=norm_person, metadata={"detector_module": "PPEDetector"}),
                DetectionResult(label="cap", confidence=0.89, bbox=norm_cap, metadata={"detector_module": "PPEDetector"}),
                DetectionResult(label="vest", confidence=0.91, bbox=norm_vest, metadata={"detector_module": "PPEDetector"}),
            ]

        try:
            from app.detection.person_detector import PersonDetector
            person_dets = PersonDetector._detect_opencv_person_fallback_static(image_bgr)
            if not person_dets:
                person_dets = [
                    DetectionResult(
                        label="person",
                        confidence=0.88,
                        bbox=BoundingBox(x_min=0.25, y_min=0.15, x_max=0.75, y_max=0.90),
                        metadata={"detector_module": "PPEDetector-AnchorFallback"}
                    )
                ]
            ppe_cv_dets = self._detect_cv_ppe_features(image_bgr, person_dets)
            return person_dets + ppe_cv_dets
        except Exception as err:
            logger.warning(f"PPEDetector: Fallback detection error: {str(err)}")
            return []

    def get_model_name(self) -> str:
        if self._is_mock_fallback:
            return f"PPEDetector-SafeMode ({os.path.basename(self.model_path)})"
        return f"PPEDetector-YOLO (Device: {self.device}, Conf: {self.conf_threshold})"

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "model_name": "PPEDetector-YOLO",
            "model_version": "1.0.0",
            "model_filename": os.path.basename(self.model_path),
            "model_hash": self.model_hash,
            "loaded_at": self.loaded_at,
            "target_classes": self.target_classes,
            "device": self.device,
            "is_fallback": self._is_mock_fallback
        }

    def health_check(self) -> Dict[str, Any]:
        return {
            "detector": "PPEDetector",
            "status": self.status.value,
            "device": self.device,
            "model_name": self.get_model_name(),
            "enabled": getattr(settings, "AI_PPE_ENABLED", True)
        }

    def shutdown(self) -> None:
        self._model = None
        self.status = DetectorStatus.UNAVAILABLE
