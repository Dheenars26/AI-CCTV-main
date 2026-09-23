"""
High-Performance ONNX Runtime YOLOv8 Inference Engine.
Provides sub-15ms object detection inference on CPU/GPU without dependency on PyTorch.
Features aspect-ratio preserving letterboxing, multi-class NMS, and singleton model caching.
"""

import os
import ast
import json
import time
import threading
from typing import List, Dict, Tuple, Optional, Any
import numpy as np
import cv2

from app.detection.base import BoundingBox, DetectionResult
from app.utils.logger import logger

# Standard 80 COCO Classes used by YOLOv8 models
STANDARD_COCO_CLASSES: Dict[int, str] = {
    0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 4: "airplane", 5: "bus", 6: "train", 7: "truck", 8: "boat",
    9: "traffic light", 10: "fire hydrant", 11: "stop sign", 12: "parking meter", 13: "bench", 14: "bird", 15: "cat",
    16: "dog", 17: "horse", 18: "sheep", 19: "cow", 20: "elephant", 21: "bear", 22: "zebra", 23: "giraffe",
    24: "backpack", 25: "umbrella", 26: "handbag", 27: "tie", 28: "suitcase", 29: "frisbee", 30: "skis", 31: "snowboard",
    32: "sports ball", 33: "kite", 34: "baseball bat", 35: "baseball glove", 36: "skateboard", 37: "surfboard",
    38: "tennis racket", 39: "bottle", 40: "wine glass", 41: "cup", 42: "fork", 43: "knife", 44: "spoon", 45: "bowl",
    46: "banana", 47: "apple", 48: "sandwich", 49: "orange", 50: "broccoli", 51: "carrot", 52: "hot dog", 53: "pizza",
    54: "donut", 55: "cake", 56: "chair", 57: "couch", 58: "potted plant", 59: "bed", 60: "dining table", 61: "toilet",
    62: "tv", 63: "laptop", 64: "mouse", 65: "remote", 66: "keyboard", 67: "cell phone", 68: "microwave", 69: "oven",
    70: "toaster", 71: "sink", 72: "refrigerator", 73: "book", 74: "clock", 75: "vase", 76: "scissors", 77: "teddy bear",
    78: "hair drier", 79: "toothbrush"
}

_GLOBAL_ONNX_CACHE: Dict[str, "ONNXYOLORunner"] = {}
_ONNX_CACHE_LOCK = threading.Lock()


class ONNXYOLORunner:
    """
    Optimized YOLOv8 ONNX model runner using ONNX Runtime with OpenCV DNN fallback.
    """

    def __init__(self, model_path: str, device: str = "cpu"):
        self.model_path = model_path
        self.device = device.lower()
        self.session: Optional[Any] = None
        self.net_cv: Optional[Any] = None
        self.input_name: str = "images"
        self.output_name: str = "output0"
        self.in_h: int = 640
        self.in_w: int = 640
        self.names: Dict[int, str] = {}
        self.backend_type: str = "none"

        self._load()
        if not self.names:
            self.names = dict(STANDARD_COCO_CLASSES)
        self._canvas: np.ndarray = np.full((self.in_h, self.in_w, 3), 114, dtype=np.uint8)
        self._neg_pairs: Dict[int, int] = {}
        self._init_negative_pairs()

    def _load(self) -> None:
        """Loads ONNX model into onnxruntime with automatic fallback to OpenCV DNN."""
        if not os.path.isfile(self.model_path):
            raise FileNotFoundError(f"ONNX model file not found: {self.model_path}")

        # Attempt 1: onnxruntime
        try:
            import onnxruntime as ort
            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

            if self.device.lower() in ["cpu", ""]:
                sess_options.intra_op_num_threads = 4
                sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
                try:
                    sess_options.add_session_config_entry("session.intra_op.allow_spinning", "1")
                except Exception:
                    pass

            providers = ["CPUExecutionProvider"]
            if self.device in ["cuda", "gpu"] and "CUDAExecutionProvider" in ort.get_available_providers():
                providers.insert(0, "CUDAExecutionProvider")

            self.session = ort.InferenceSession(self.model_path, sess_options=sess_options, providers=providers)
            in_meta = self.session.get_inputs()[0]
            self.input_name = in_meta.name
            shape = in_meta.shape

            self.in_h = shape[2] if (len(shape) > 2 and isinstance(shape[2], int)) else 640
            self.in_w = shape[3] if (len(shape) > 3 and isinstance(shape[3], int)) else 640

            out_meta = self.session.get_outputs()[0]
            self.output_name = out_meta.name

            # Read custom metadata for class names
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

            if not self.names:
                self.names = dict(STANDARD_COCO_CLASSES)

            self.backend_type = "onnxruntime"
            logger.info(
                f"ONNXYOLORunner: Loaded '{self.model_path}' via onnxruntime ({providers[0]}). "
                f"Input: {self.in_w}x{self.in_h}, Classes: {len(self.names)}"
            )
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
            if not self.names:
                self.names = dict(STANDARD_COCO_CLASSES)
            logger.info(f"ONNXYOLORunner: Loaded '{self.model_path}' via cv2.dnn.")
        except Exception as e:
            logger.error(f"ONNXYOLORunner: Both onnxruntime and cv2.dnn failed for '{self.model_path}': {e}")
            raise RuntimeError(f"Cannot load ONNX model '{self.model_path}' with any available backend.")

    def _init_negative_pairs(self) -> None:
        """Find matching positive-negative class pairs (e.g. Safety Vest <-> NO-Safety Vest)."""
        name_to_id = {v.lower().strip(): k for k, v in self.names.items()}
        for name, cid in name_to_id.items():
            if name.startswith("no-") or name.startswith("no_"):
                pos_candidate = name[3:].strip()
                if pos_candidate in name_to_id:
                    self._neg_pairs[name_to_id[pos_candidate]] = cid
                elif pos_candidate.replace(" ", "_") in name_to_id:
                    self._neg_pairs[name_to_id[pos_candidate.replace(" ", "_")]] = cid

    def predict(
        self,
        image_bgr: np.ndarray,
        conf_threshold: float = 0.35,
        iou_threshold: float = 0.45,
        target_classes: Optional[List[str]] = None
    ) -> Tuple[List[Dict[str, Any]], float]:
        """
        Executes YOLOv8 forward inference with letterbox preprocessing and multi-class NMS.
        Returns: (detections, inference_time_ms)
        Each detection is a dict with: 'label', 'confidence', 'bbox' (BoundingBox), 'class_id'.
        """
        if image_bgr is None or image_bgr.size == 0:
            return [], 0.0

        h, w = image_bgr.shape[:2]

        # 1. High-speed Letterbox resizing (preserves aspect ratio without distortion)
        scale = min(self.in_w / float(w), self.in_h / float(h))
        nw, nh = int(round(w * scale)), int(round(h * scale))
        resized = cv2.resize(image_bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)

        canvas = self._canvas.copy()
        dx = (self.in_w - nw) // 2
        dy = (self.in_h - nh) // 2
        canvas[dy:dy + nh, dx:dx + nw] = resized

        # Optimized C++ blob conversion to [0.0, 1.0] and NCHW format
        blob = cv2.dnn.blobFromImage(canvas, 1.0 / 255.0, (self.in_w, self.in_h), swapRB=True, crop=False)

        # 2. Forward inference
        t0 = time.time()
        if self.backend_type == "onnxruntime" and self.session is not None:
            raw_out = self.session.run(None, {self.input_name: blob})[0]
        elif self.net_cv is not None:
            self.net_cv.setInput(blob)
            raw_out = self.net_cv.forward()
        else:
            return [], 0.0

        inf_time_ms = round((time.time() - t0) * 1000, 2)

        # YOLOv8 output tensor: (1, 4 + num_classes, num_boxes) -> transpose to (num_boxes, 4 + num_classes)
        preds = np.squeeze(raw_out, axis=0)
        if preds.shape[0] < preds.shape[1]:
            preds = preds.T

        boxes = preds[:, :4]
        raw_scores_matrix = preds[:, 4:]
        max_scores = np.max(raw_scores_matrix, axis=1)
        class_ids = np.argmax(raw_scores_matrix, axis=1)

        keep = max_scores >= conf_threshold
        if not np.any(keep):
            return [], inf_time_ms

        boxes = boxes[keep]
        scores = max_scores[keep]
        class_ids = class_ids[keep]
        filtered_scores_matrix = raw_scores_matrix[keep]

        # 3. Vectorized scaling candidate boxes back from letterbox canvas to original frame dimensions
        cx, cy, bw, bh = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
        x1 = np.clip((cx - bw / 2.0 - dx) / scale, 0, w)
        y1 = np.clip((cy - bh / 2.0 - dy) / scale, 0, h)
        x2 = np.clip((cx + bw / 2.0 - dx) / scale, 0, w)
        y2 = np.clip((cy + bh / 2.0 - dy) / scale, 0, h)

        # 4. Multi-class Non-Maximum Suppression (NMS) with strict geometry validation
        valid_nms: List[List[int]] = []
        valid_scores: List[float] = []
        valid_idx_map: List[int] = []

        for i in range(len(scores)):
            bx = int(x1[i])
            by = int(y1[i])
            bw_b = int(x2[i] - x1[i])
            bh_b = int(y2[i] - y1[i])
            sc = float(scores[i])
            if bw_b > 1 and bh_b > 1 and np.isfinite(sc) and sc >= conf_threshold:
                valid_nms.append([bx, by, bw_b, bh_b])
                valid_scores.append(sc)
                valid_idx_map.append(i)

        if not valid_nms:
            return [], inf_time_ms

        flat_indices: List[int] = []
        try:
            indices = cv2.dnn.NMSBoxes(valid_nms, valid_scores, float(conf_threshold), float(iou_threshold))
            if indices is not None and len(indices) > 0:
                if hasattr(indices, "flatten"):
                    flat_indices = [valid_idx_map[int(idx)] for idx in indices.flatten()]
                elif isinstance(indices, (list, tuple)):
                    flat_indices = [valid_idx_map[int(idx[0] if isinstance(idx, (list, tuple, np.ndarray)) else idx)] for idx in indices]
        except Exception as nms_err:
            logger.warning(f"ONNXYOLORunner: NMSBoxes notice: {nms_err}. Using top candidate.")
            flat_indices = [valid_idx_map[0]]

        results: List[Dict[str, Any]] = []
        target_lower = [t.lower().strip() for t in target_classes] if target_classes else None

        for idx in flat_indices:
            cid = int(class_ids[idx])
            conf = float(scores[idx])
            label = self.names.get(cid, str(cid)).lower().strip()

            if target_lower and label not in target_lower:
                continue

            neg_cid = self._neg_pairs.get(cid)
            neg_score = float(filtered_scores_matrix[idx, neg_cid]) if neg_cid is not None else 0.0

            norm_bbox = BoundingBox(
                x_min=max(0.0, min(1.0, float(x1[idx]) / float(w))),
                y_min=max(0.0, min(1.0, float(y1[idx]) / float(h))),
                x_max=max(0.0, min(1.0, float(x2[idx]) / float(w))),
                y_max=max(0.0, min(1.0, float(y2[idx]) / float(h)))
            )

            results.append({
                "label": label,
                "confidence": conf,
                "bbox": norm_bbox,
                "class_id": cid,
                "negative_class_score": neg_score,
                "class_margin": round(conf - neg_score, 4),
                "pixel_coords": [int(x1[idx]), int(y1[idx]), int(x2[idx]), int(y2[idx])]
            })

        return results, inf_time_ms


def get_onnx_yolo_runner(model_path: str, device: str = "cpu") -> ONNXYOLORunner:
    """
    Returns cached ONNXYOLORunner instance for the given weights path and device.
    """
    key = f"{os.path.abspath(model_path)}_{device}"
    with _ONNX_CACHE_LOCK:
        if key not in _GLOBAL_ONNX_CACHE:
            _GLOBAL_ONNX_CACHE[key] = ONNXYOLORunner(model_path, device=device)
        return _GLOBAL_ONNX_CACHE[key]


def create_optimized_onnx_session(model_path: str, device: str = "cpu") -> Any:
    """
    Creates an ONNX runtime session optimized for multi-core Windows CPU performance.
    Sets ORT_ENABLE_ALL, intra_op_num_threads=4 (or match core count), ORT_SEQUENTIAL, and allow_spinning=1.
    """
    import onnxruntime as ort
    sess_options = ort.SessionOptions()
    sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    if device.lower() in ["cpu", ""]:
        cpu_cores = os.cpu_count() or 4
        sess_options.intra_op_num_threads = 4 if cpu_cores >= 4 else cpu_cores
        sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        try:
            sess_options.add_session_config_entry("session.intra_op.allow_spinning", "1")
        except Exception:
            pass
    providers = ["CPUExecutionProvider"]
    if device.lower() in ["cuda", "gpu"] and "CUDAExecutionProvider" in ort.get_available_providers():
        providers.insert(0, "CUDAExecutionProvider")
    return ort.InferenceSession(model_path, sess_options=sess_options, providers=providers)

