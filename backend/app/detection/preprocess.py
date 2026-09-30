"""
High-performance, allocation-aware preprocessing primitives for YOLO inference.

This module isolates the *pure* image->tensor math used by every detector so that it can be
unit-tested and reused. The key performance property is that :class:`Letterbox` owns reusable
buffers: a camera running at 10 FPS performs ~864k letterbox operations per day, and the naive
implementation (``cv2.resize`` -> ``transpose`` -> ``astype`` -> ``/255.0``) allocates two full
tensors per call. Reusing the canvas + blob and scaling in-place removes that allocator churn.
"""

from typing import Optional, Tuple
import numpy as np
import cv2


# Standard YOLO letterbox fill value (grey 114) used at export time by Ultralytics.
DEFAULT_PAD_VALUE = 114


class Letterbox:
    """
    Aspect-ratio preserving resize + pad to a fixed network input size.

    The instance keeps a ``uint8`` canvas and a ``float32`` NCHW blob between calls. Buffers are
    re-created only when the incoming frame size changes, so steady-state inference is
    allocation-free on the preprocessing side.
    """

    __slots__ = ("in_w", "in_h", "_canvas", "_blob", "_cached_hw", "pad_value")

    def __init__(self, in_w: int, in_h: int, pad_value: int = DEFAULT_PAD_VALUE):
        self.in_w = in_w
        self.in_h = in_h
        self.pad_value = pad_value
        self._canvas: Optional[np.ndarray] = None
        self._blob: Optional[np.ndarray] = None
        self._cached_hw: Optional[Tuple[int, int]] = None

    def _ensure_buffers(self) -> None:
        if self._canvas is None or self._canvas.shape[:2] != (self.in_h, self.in_w):
            self._canvas = np.full((self.in_h, self.in_w, 3), self.pad_value, dtype=np.uint8)
            self._blob = np.empty((1, 3, self.in_h, self.in_w), dtype=np.float32)

    def apply(self, image_bgr: np.ndarray) -> Tuple[np.ndarray, float, int, int]:
        """
        Letterboxes ``image_bgr`` into the reusable blob.

        :returns: ``(blob, scale, dx, dy)`` where ``scale`` is the resize factor applied to the
                  original frame and ``(dx, dy)`` is the top-left padding offset inside the canvas.
                  Box coordinates predicted in canvas space can be mapped back with
                  :func:`scale_boxes`.
        """
        h, w = image_bgr.shape[:2]
        if h == 0 or w == 0:
            raise ValueError("Cannot letterbox an empty frame")

        self._ensure_buffers()
        canvas = self._canvas
        blob = self._blob
        assert canvas is not None and blob is not None  # for type checkers

        scale = min(self.in_w / float(w), self.in_h / float(h))
        nw, nh = int(round(w * scale)), int(round(h * scale))
        nw = max(1, min(self.in_w, nw))
        nh = max(1, min(self.in_h, nh))

        if (h, w) != self._cached_hw or (nw, nh) != (canvas.shape[1], canvas.shape[0]):
            canvas[:] = self.pad_value

        resized = cv2.resize(image_bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)

        dx = (self.in_w - nw) // 2
        dy = (self.in_h - nh) // 2

        # Clear only the bands that can hold previous content, then paste the resized frame.
        if self._cached_hw is not None:
            canvas[:] = self.pad_value
        canvas[dy:dy + nh, dx:dx + nw] = resized
        self._cached_hw = (h, w)

        # HWC(uint8) -> NCHW(float32 in [0,1]) with a single read pass and one in-place scaling.
        np.copyto(blob[0], canvas.transpose(2, 0, 1))
        blob *= np.float32(1.0 / 255.0)
        return blob, scale, dx, dy

    @staticmethod
    def plain_blob(image_bgr: np.ndarray) -> np.ndarray:
        """Converts a *pre-sized* BGR image straight to an NCHW float32 blob (no letterbox)."""
        blob = np.empty((1, 3) + image_bgr.shape[:2], dtype=np.float32)
        np.copyto(blob[0], image_bgr.transpose(2, 0, 1))
        blob *= np.float32(1.0 / 255.0)
        return blob


def scale_boxes(
    boxes_xywh: np.ndarray,
    scale: float,
    dx: int,
    dy: int,
    frame_w: int,
    frame_h: int,
) -> np.ndarray:
    """
    Maps letterbox-canvas ``cx, cy, w, h`` predictions back to original-frame ``x1, y1, x2, y2``.

    Vectorised over all rows, clipping to the frame bounds.
    """
    if boxes_xywh.size == 0:
        return np.zeros((0, 4), dtype=np.float32)

    cx, cy, bw, bh = boxes_xywh[:, 0], boxes_xywh[:, 1], boxes_xywh[:, 2], boxes_xywh[:, 3]
    inv = 1.0 / (scale if scale > 0 else 1.0)

    x1 = (cx - bw / 2.0 - dx) * inv
    y1 = (cy - bh / 2.0 - dy) * inv
    x2 = (cx + bw / 2.0 - dx) * inv
    y2 = (cy + bh / 2.0 - dy) * inv

    out = np.stack([x1, y1, x2, y2], axis=1)
    out[:, [0, 2]] = np.clip(out[:, [0, 2]], 0, frame_w)
    out[:, [1, 3]] = np.clip(out[:, [1, 3]], 0, frame_h)
    return out


def prepare_worker_roi(
    person_xyxy: Tuple[float, float, float, float],
    frame_w: int,
    frame_h: int,
    head_ratio: float = 0.38,
    head_pad: float = 0.10,
) -> Tuple[Tuple[int, int, int, int], Tuple[int, int, int, int]]:
    """
    Derives clamped ``(head, torso)`` pixel ROIs from a person bounding box.

    Safety glasses and vests occupy 3-15 px in a 1080p frame at typical CCTV distances, which is
    far below what a 640px detector can resolve. Re-running the same network on these ROIs raises
    the effective resolution by 3-8x and is the single largest accuracy lever for goggles/vests.

    :returns: ``(head_roi, torso_roi)`` in ``(x1, y1, x2, y2)`` pixel coordinates.
    """
    x1, y1, x2, y2 = person_xyxy
    px1 = int(max(0, min(frame_w - 1, x1)))
    py1 = int(max(0, min(frame_h - 1, y1)))
    px2 = int(max(px1 + 1, min(frame_w, x2)))
    py2 = int(max(py1 + 1, min(frame_h, y2)))

    pw = px2 - px1
    ph = py2 - py1
    aspect = float(pw) / float(ph) if ph > 0 else 1.0

    # Adapt head ROI vertical coverage and horizontal padding to camera viewpoint
    if aspect > 0.85:
        # Close-up head / bust / seated at desk: head & face occupy up to ~68% of visible height
        eff_head_ratio = 0.68
        eff_pad_x = 0.05
    elif aspect > 0.55:
        # Upper torso / half-body
        eff_head_ratio = 0.52
        eff_pad_x = 0.08
    else:
        # Standing full-body worker
        eff_head_ratio = head_ratio
        eff_pad_x = head_pad

    pad_x = int(pw * eff_pad_x)
    head_x1 = max(0, px1 - pad_x)
    head_x2 = min(frame_w, px2 + pad_x)
    head_y1 = max(0, py1 - int(ph * 0.06))
    head_y2 = min(frame_h, py1 + max(2, int(ph * eff_head_ratio)))

    torso_x1 = max(0, px1 - int(pw * 0.04))
    torso_x2 = min(frame_w, px2 + int(pw * 0.04))
    torso_y1 = max(0, py1 + int(ph * 0.15))
    # If aspect is high (webcam/bust), the person box is only head & shoulders.
    # The torso sits *below* the box, so we must extend y2 further down.
    eff_torso_h = 1.8 if aspect > 0.85 else 0.92
    torso_y2 = min(frame_h, py1 + max(4, int(ph * eff_torso_h)))

    return (head_x1, head_y1, head_x2, head_y2), (torso_x1, torso_y1, torso_x2, torso_y2)


def clip_roi(roi: Tuple[int, int, int, int], frame_w: int, frame_h: int) -> Tuple[int, int, int, int]:
    """Clamps ``(x1, y1, x2, y2)`` into frame bounds guaranteeing a non-empty box."""
    x1, y1, x2, y2 = roi
    x1 = max(0, min(frame_w - 1, x1))
    y1 = max(0, min(frame_h - 1, y1))
    x2 = max(x1 + 1, min(frame_w, x2))
    y2 = max(y1 + 1, min(frame_h, y2))
    return (x1, y1, x2, y2)


def upscale_if_small(crop: np.ndarray, min_side: int = 320) -> Tuple[np.ndarray, float]:
    """
    Upscales a small crop so thin structures (glasses frames, glove seams) survive the network's
    stride-32 downsampling. Returns ``(image, applied_scale)`` where the scale is 1.0 when the
    crop was already large enough.
    """
    h, w = crop.shape[:2]
    if h == 0 or w == 0:
        return crop, 1.0
    shortest = min(h, w)
    if shortest >= min_side:
        return crop, 1.0
    scale = float(min_side) / float(shortest)
    # Cap the resize so a 12 px ROI cannot explode into a multi-megapixel tensor.
    scale = min(scale, 6.0)
    return cv2.resize(crop, (int(round(w * scale)), int(round(h * scale))), interpolation=cv2.INTER_CUBIC), scale
