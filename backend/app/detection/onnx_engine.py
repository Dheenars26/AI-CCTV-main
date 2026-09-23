"""
High-Performance ONNX Runtime YOLOv8 Inference Engine.

Design goals (in order of measured impact):

1. **Correct class-aware decoding.** The previous decoder routed every prediction through
   ``cv2.dnn.NMSBoxes``, which is class agnostic - it deleted a ``Person`` box because a
   ``Safety Vest`` box covered the same torso. Decoding is now vectorised and per-class.
2. **Duplicate fusion (WBF).** A low candidate threshold makes YOLO emit 5-15 near-duplicate boxes
   per object (measured: 12 of the top-12 PPE candidates were one hard hat). Weighted Box Fusion
   merges those clusters into a single, better-localised box, and the resulting coordinates are
   stable frame-to-frame, which is exactly what the temporal verification FSM needs to confirm fast
   without admitting noise.
3. **Allocation-free preprocessing.** Letterbox canvases and NCHW blobs are pooled per thread.
4. **Per-class + size-adaptive thresholds.** A global 0.35 floor cannot serve both a 400-pixel
   smoke plume and 4-pixel safety glasses.

The public contract (``get_onnx_yolo_runner`` and ``predict``'s return shape) is unchanged so all
existing detectors and tests keep working.
"""

import os
import ast
import json
import time
import threading
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
import cv2

from app.config.settings import settings
from app.detection.base import BoundingBox
from app.detection.nms import (
    apply_class_thresholds,
    merge_nearby_boxes,
    nms,
    resolution_adaptive_threshold,
    weighted_box_fusion,
)
from app.detection.preprocess import Letterbox
from app.utils.logger import logger

_GLOBAL_ONNX_CACHE: Dict[str, "ONNXYOLORunner"] = {}
_ONNX_CACHE_LOCK = threading.Lock()

# Classes whose boxes are physically small in surveillance footage. Their candidate floor is
# relaxed relative to the model-wide threshold; the temporal FSM downstream is what confirms them.
_SMALL_OBJECT_CLASSES = {
    "goggles", "glasses", "safety_glasses", "safety_glass", "safety goggles", "eyewear",
    "eye_protection", "spectacles", "gloves", "glove", "mask", "face_mask", "n95", "respirator",
}


class ONNXYOLORunner:
    """
    Optimised YOLOv8 ONNX runner using ONNX Runtime, with an OpenCV-DNN fallback for environments
    where onnxruntime is unavailable.
    """

    def __init__(
        self,
        model_path: str,
        device: str = "cpu",
        threads: Optional[int] = None,
        enable_wbf: bool = True,
    ):
        self.model_path = model_path
        self.device = str(device).lower()
        self.session: Optional[Any] = None
        self.net_cv: Optional[Any] = None
        self.input_name: str = "images"
        self.output_name: str = "output0"
        self.in_h: int = 640
        self.in_w: int = 640
        self.names: Dict[int, str] = {}
        self.backend_type: str = "none"
        self.enable_wbf = bool(enable_wbf)
        self.threads = threads

        # Per-thread scratch buffers so the runner stays safe to share across camera workers
        # without a global lock serialising inference.
        self._tls = threading.local()

        self._load()

    # ------------------------------------------------------------------ #
    # Loading
    # ------------------------------------------------------------------ #
    def _resolve_thread_count(self) -> int:
        """
        Chooses the ONNX intra-op thread count.

        Two threads per session is the sweet spot for the single-camera case (measured 27 ms vs 40 ms
        for the fire model on a 2-vCPU host), while the cap of four stops a multi-camera deployment
        from oversubscribing the CPU across its three sessions per camera - which measurably *reduces*
        aggregate throughput.
        """
        if self.threads is not None:
            return max(1, int(self.threads))
        cores = os.cpu_count() or 2
        if cores <= 1:
            return 1
        return max(2, min(4, cores // 2))

    def _load(self) -> None:
        if not os.path.isfile(self.model_path):
            raise FileNotFoundError(f"ONNX model file not found: {self.model_path}")

        # Attempt 1: onnxruntime
        try:
            import onnxruntime as ort

            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            intra = self._resolve_thread_count()
            sess_options.intra_op_num_threads = intra
            sess_options.inter_op_num_threads = 1
            sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            sess_options.enable_cpu_mem_arena = True
            sess_options.enable_mem_pattern = True

            providers = ["CPUExecutionProvider"]
            available = ort.get_available_providers()
            if self.device in ["cuda", "gpu", "0"] and "CUDAExecutionProvider" in available:
                providers.insert(0, "CUDAExecutionProvider")

            self.session = ort.InferenceSession(self.model_path, sess_options=sess_options, providers=providers)
            in_meta = self.session.get_inputs()[0]
            self.input_name = in_meta.name
            shape = in_meta.shape

            self.in_h = shape[2] if (len(shape) > 2 and isinstance(shape[2], int)) else 640
            self.in_w = shape[3] if (len(shape) > 3 and isinstance(shape[3], int)) else 640

            out_meta = self.session.get_outputs()[0]
            self.output_name = out_meta.name

            meta = self.session.get_modelmeta().custom_metadata_map
            raw_names = meta.get("names", "")
            if raw_names:
                try:
                    self.names = ast.literal_eval(raw_names)
                except Exception:
                    try:
                        self.names = json.loads(raw_names.replace("'", '"'))
                    except Exception:
                        pass

            self.backend_type = "onnxruntime"
            logger.info(
                f"ONNXYOLORunner: Loaded '{self.model_path}' via onnxruntime ({providers[0]}). "
                f"Input: {self.in_w}x{self.in_h}, Classes: {len(self.names)}, intra-op threads: {intra}"
            )
            self._warmup()
            return
        except Exception as e:
            logger.warning(f"ONNXYOLORunner: onnxruntime failed to load '{self.model_path}': {e}. Trying cv2.dnn...")

        # Attempt 2: cv2.dnn fallback
        try:
            net = cv2.dnn.readNetFromONNX(self.model_path)
            net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            self.net_cv = net
            self.backend_type = "cv2_dnn"
            logger.info(f"ONNXYOLORunner: Loaded '{self.model_path}' via cv2.dnn.")
            self._warmup()
            return
        except Exception as e:
            logger.error(f"ONNXYOLORunner: Both onnxruntime and cv2.dnn failed for '{self.model_path}': {e}")
            raise RuntimeError(f"Cannot load ONNX model '{self.model_path}' with any available backend.")

    def _warmup(self, passes: int = 2) -> None:
        """
        Primes the ORT memory arena and CPU caches.

        Without this the first real frame pays a 100-400 ms allocation penalty, which is long enough
        to make a fire alert late and to trip the pipeline's back-pressure logic on startup.
        """
        try:
            dummy = np.zeros((self.in_h, self.in_w, 3), dtype=np.uint8)
            for _ in range(max(1, passes)):
                self.predict(dummy, conf_threshold=0.5, iou_threshold=0.45, target_classes=None)
            logger.debug(f"ONNXYOLORunner: Warmup complete for '{os.path.basename(self.model_path)}'.")
        except Exception as e:
            logger.debug(f"ONNXYOLORunner: Warmup skipped: {e}")

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _letterbox(self) -> Letterbox:
        """Returns the calling thread's reusable letterbox buffer."""
        lb = getattr(self._tls, "letterbox", None)
        if lb is None or lb.in_w != self.in_w or lb.in_h != self.in_h:
            lb = Letterbox(self.in_w, self.in_h)
            self._tls.letterbox = lb
        return lb

    @property
    def class_names(self) -> List[str]:
        """Lower-cased class names in id order."""
        if not self.names:
            return []
        size = max(int(k) for k in self.names.keys()) + 1
        return [str(self.names.get(i, str(i))).lower().strip() for i in range(size)]

    def name_for(self, class_id: int) -> str:
        """Robust class-id to label lookup (metadata dicts may use int or str keys)."""
        if class_id in self.names:
            return str(self.names[class_id]).lower().strip()
        str_key = str(class_id)
        if str_key in self.names:  # type: ignore[operator]
            return str(self.names[str_key]).lower().strip()  # type: ignore[index]
        names = self.class_names
        if 0 <= class_id < len(names):
            return names[class_id]
        return str(class_id)

    def _class_threshold_array(self, class_thresholds: Optional[Dict[Any, float]], num_classes: int, default: float) -> Optional[np.ndarray]:
        """
        Converts a ``{class_id|class_name: threshold}`` mapping into a per-class array.

        Both integer ids and label names are accepted, so callers can pass whatever is read from
        configuration without knowing the model's class ordering.
        """
        if not class_thresholds:
            return None
        arr = np.full(num_classes, float(default), dtype=np.float32)
        for key, thr in class_thresholds.items():
            if isinstance(key, int) or (isinstance(key, str) and key.isdigit()):
                idx = int(key)
                if 0 <= idx < num_classes:
                    arr[idx] = float(thr)
                continue
            target = str(key).lower().strip()
            for cid in range(num_classes):
                if self.name_for(cid) == target:
                    arr[cid] = float(thr)
        return arr

    # ------------------------------------------------------------------ #
    # Inference
    # ------------------------------------------------------------------ #
    def predict(
        self,
        image_bgr: np.ndarray,
        conf_threshold: float = 0.35,
        iou_threshold: float = 0.45,
        target_classes: Optional[List[str]] = None,
        class_thresholds: Optional[Dict[Any, float]] = None,
        use_wbf: Optional[bool] = None,
        adaptive_small_classes: bool = True,
        max_det: int = 100,
    ) -> Tuple[List[Dict[str, Any]], float]:
        """
        Executes YOLOv8 forward inference with letterbox preprocessing, class-aware decoding and
        duplicate fusion.

        :param conf_threshold: base candidate floor applied to all classes.
        :param iou_threshold: IoU used by the fusion/NMS stage.
        :param target_classes: optional whitelist of labels to return (case-insensitive).
        :param class_thresholds: optional per-class overrides, keyed by class name or id.
        :param use_wbf: override duplicate handling (``True`` fuses, ``False`` uses plain NMS).
        :param adaptive_small_classes: relax the floor for tiny safety classes (goggles, gloves...).
        :returns: ``(detections, inference_time_ms)`` where each detection dict carries
                  ``label``, ``confidence``, ``bbox`` (BoundingBox), ``class_id``, ``pixel_coords``
                  and ``box_agreement`` (number of raw boxes fused into it).
        """
        if image_bgr is None or image_bgr.size == 0:
            return [], 0.0

        h, w = image_bgr.shape[:2]
        t_pre = time.perf_counter()
        blob, scale, dx, dy = self._letterbox().apply(image_bgr)
        preprocess_ms = (time.perf_counter() - t_pre) * 1000.0

        t0 = time.perf_counter()
        if self.backend_type == "onnxruntime" and self.session is not None:
            raw_out = self.session.run([self.output_name], {self.input_name: blob})[0]
        elif self.net_cv is not None:
            self.net_cv.setInput(blob)
            raw_out = self.net_cv.forward()
        else:
            return [], 0.0
        inf_time_ms = (time.perf_counter() - t0) * 1000.0

        results = self._decode(
            raw_out=raw_out,
            frame_w=w,
            frame_h=h,
            scale=scale,
            dx=dx,
            dy=dy,
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold,
            target_classes=target_classes,
            class_thresholds=class_thresholds,
            use_wbf=self.enable_wbf if use_wbf is None else use_wbf,
            adaptive_small_classes=adaptive_small_classes,
            max_det=max_det,
        )

        self._tls.last_timings = {
            "preprocess_ms": round(preprocess_ms, 2),
            "inference_ms": round(inf_time_ms, 2),
            "detections": len(results),
        }
        return results, round(inf_time_ms, 2)

    def get_last_timings(self) -> Dict[str, Any]:
        """Returns the timing breakdown of the most recent ``predict`` call on this thread."""
        return getattr(self._tls, "last_timings", {})

    def _decode(
        self,
        raw_out: np.ndarray,
        frame_w: int,
        frame_h: int,
        scale: float,
        dx: int,
        dy: int,
        conf_threshold: float,
        iou_threshold: float,
        target_classes: Optional[List[str]],
        class_thresholds: Optional[Dict[Any, float]],
        use_wbf: bool,
        adaptive_small_classes: bool,
        max_det: int,
    ) -> List[Dict[str, Any]]:
        """
        Vectorised decode of a YOLOv8 head ``(1, 4 + nc, anchors)`` (or transposed) tensor.
        """
        preds = np.squeeze(raw_out, axis=0)
        if preds.ndim != 2:
            return []
        # YOLOv8 exports as (4+nc, anchors); some exporters transpose it.
        if preds.shape[0] < preds.shape[1]:
            preds = preds.T

        num_attrs = preds.shape[1]
        num_classes = max(1, num_attrs - 4)

        boxes_xywh = preds[:, :4]
        scores = preds[:, 4:4 + num_classes]

        max_scores = scores.max(axis=1)
        class_ids = scores.argmax(axis=1)

        # --- Stage 1: cheap candidate gate at the loosest class floor ---
        candidate_floor = float(conf_threshold)
        if class_thresholds:
            candidate_floor = min(candidate_floor, min(float(v) for v in class_thresholds.values()))
        if adaptive_small_classes and self.names:
            if any(self.name_for(cid) in _SMALL_OBJECT_CLASSES for cid in range(num_classes)):
                candidate_floor = min(candidate_floor, float(conf_threshold) * 0.5)
        # Never scan below the noise floor: sub-0.05 outputs are pure background texture.
        candidate_floor = max(candidate_floor, 0.05)

        keep = max_scores >= candidate_floor
        if not np.any(keep):
            return []

        boxes_xywh = boxes_xywh[keep]
        scores_kept = max_scores[keep]
        class_ids = class_ids[keep]

        # --- Stage 2: per-class thresholds ---
        per_class = self._class_threshold_array(class_thresholds, num_classes, conf_threshold)
        if per_class is None:
            thresholds = np.full(scores_kept.shape, float(conf_threshold), dtype=np.float32)
            if adaptive_small_classes and self.names:
                for cid in range(num_classes):
                    if self.name_for(cid) in _SMALL_OBJECT_CLASSES:
                        thresholds[class_ids == cid] = float(conf_threshold) * 0.5
            keep_mask = scores_kept >= thresholds
        else:
            if adaptive_small_classes and self.names:
                for cid in range(num_classes):
                    if self.name_for(cid) in _SMALL_OBJECT_CLASSES:
                        per_class[cid] = min(per_class[cid], float(conf_threshold) * 0.5)
            keep_mask = apply_class_thresholds(scores_kept, class_ids, {i: float(v) for i, v in enumerate(per_class)}, conf_threshold)

        boxes_xywh = boxes_xywh[keep_mask]
        scores_kept = scores_kept[keep_mask]
        class_ids = class_ids[keep_mask]
        if boxes_xywh.shape[0] == 0:
            return []

        # --- Stage 3: letterbox -> frame coordinates ---
        inv = 1.0 / (scale if scale > 0 else 1.0)
        cx, cy, bw, bh = boxes_xywh[:, 0], boxes_xywh[:, 1], boxes_xywh[:, 2], boxes_xywh[:, 3]
        xyxy = np.stack([
            (cx - bw / 2.0 - dx) * inv,
            (cy - bh / 2.0 - dy) * inv,
            (cx + bw / 2.0 - dx) * inv,
            (cy + bh / 2.0 - dy) * inv,
        ], axis=1).astype(np.float32)
        xyxy[:, [0, 2]] = np.clip(xyxy[:, [0, 2]], 0, frame_w)
        xyxy[:, [1, 3]] = np.clip(xyxy[:, [1, 3]], 0, frame_h)

        # --- Stage 4: size-adaptive floor (small classes only) ---
        if adaptive_small_classes and self.names:
            areas_norm = ((xyxy[:, 2] - xyxy[:, 0]) * (xyxy[:, 3] - xyxy[:, 1])) / float(max(1, frame_w * frame_h))
            alive_mask = np.ones(len(xyxy), dtype=bool)
            for cid in np.unique(class_ids):
                if self.name_for(int(cid)) not in _SMALL_OBJECT_CLASSES:
                    continue
                members = np.where(class_ids == cid)[0]
                relaxed = resolution_adaptive_threshold(
                    float(conf_threshold) * 0.5, areas_norm[members], reference_area=0.004, min_ratio=0.7
                )
                alive_mask[members] = scores_kept[members] >= relaxed
            xyxy, scores_kept, class_ids = xyxy[alive_mask], scores_kept[alive_mask], class_ids[alive_mask]
            if xyxy.shape[0] == 0:
                return []

        # --- Stage 5: duplicate handling ---
        # Fusion/NMS run in Python; bound the candidate count per class so a pathological frame
        # (very low floor + cluttered scene) cannot turn post-processing into the bottleneck.
        max_candidates = int(getattr(settings, "AI_MAX_CANDIDATES_PER_CLASS", 120))
        if len(xyxy) > max_candidates:
            order = np.argsort(-scores_kept, kind="stable")[:max_candidates]
            xyxy, scores_kept, class_ids = xyxy[order], scores_kept[order], class_ids[order]

        agreement = np.ones(len(xyxy), dtype=np.int32)
        if len(xyxy) > 1:
            if use_wbf:
                xyxy, scores_kept, class_ids, agreement = weighted_box_fusion(
                    xyxy, scores_kept, class_ids, iou_threshold=iou_threshold
                )
            else:
                idx = nms(xyxy, scores_kept, iou_threshold, class_ids, class_aware=True, max_det=max_det)
                xyxy, scores_kept, class_ids = xyxy[idx], scores_kept[idx], class_ids[idx]
            xyxy, scores_kept, class_ids = merge_nearby_boxes(xyxy, scores_kept, class_ids)
            agreement = agreement[:len(xyxy)] if len(agreement) >= len(xyxy) else np.ones(len(xyxy), dtype=np.int32)

        # --- Stage 6: filter to requested classes and package ---
        target_lower = [t.lower().strip() for t in target_classes] if target_classes else None

        order = np.argsort(-scores_kept)
        results: List[Dict[str, Any]] = []
        for idx in order:
            if len(results) >= max_det:
                break
            cid = int(class_ids[idx])
            label = self.name_for(cid)
            if target_lower and label not in target_lower:
                continue

            x1, y1, x2, y2 = xyxy[idx]
            if x2 - x1 < 1 or y2 - y1 < 1:
                continue

            norm_bbox = BoundingBox(
                x_min=max(0.0, min(1.0, float(x1) / float(frame_w))),
                y_min=max(0.0, min(1.0, float(y1) / float(frame_h))),
                x_max=max(0.0, min(1.0, float(x2) / float(frame_w))),
                y_max=max(0.0, min(1.0, float(y2) / float(frame_h))),
            )

            results.append({
                "label": label,
                "confidence": float(scores_kept[idx]),
                "bbox": norm_bbox,
                "class_id": cid,
                "pixel_coords": [int(x1), int(y1), int(x2), int(y2)],
                "box_agreement": int(agreement[idx]) if idx < len(agreement) else 1,
            })

        return results

    # ------------------------------------------------------------------ #
    # Diagnostics
    # ------------------------------------------------------------------ #
    def health(self) -> Dict[str, Any]:
        return {
            "model": os.path.basename(self.model_path),
            "backend": self.backend_type,
            "device": self.device,
            "input_size": [self.in_w, self.in_h],
            "classes": len(self.names),
        }


def get_onnx_yolo_runner(
    model_path: str,
    device: str = "cpu",
    threads: Optional[int] = None,
    enable_wbf: bool = True,
) -> ONNXYOLORunner:
    """
    Returns a cached :class:`ONNXYOLORunner` for the given weights path and device.

    Caching is essential: several detectors (fire/smoke, PPE, person) resolve to the same ONNX file
    in some deployments, and each instantiation costs tens of megabytes of session memory.
    """
    key = f"{os.path.abspath(model_path)}_{device}_{threads}_{int(enable_wbf)}"
    with _ONNX_CACHE_LOCK:
        if key not in _GLOBAL_ONNX_CACHE:
            _GLOBAL_ONNX_CACHE[key] = ONNXYOLORunner(
                model_path, device=device, threads=threads, enable_wbf=enable_wbf
            )
        return _GLOBAL_ONNX_CACHE[key]
