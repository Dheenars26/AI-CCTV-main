"""
OpenCV Video Frame Processing Pipeline Subsystem.
Implements a modular, multi-stage processing pipeline:
Frame -> Preprocessor -> FreezeDetector -> AI Detector -> Postprocessor -> EventManager.
Fully frontend-independent and thread-isolated.
"""

import time
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple, Callable
import cv2
import numpy as np

from app.detection.base import BaseDetector, DummyDetector, DetectionResult
from app.detection.verification import CameraVerificationEngine, VerifiedEvent
from app.detection.fire_smoke_detector import FireSmokeDetector
from app.detection.ppe_detector import PPEDetector
from app.detection.person_detector import PersonDetector
from app.safety.tracker import PersonTracker
from app.safety.association import PPEAssociationEngine
from app.zones.engine import ZoneEngine
from app.safety.rules import SafetyRuleEngine
from app.safety.verification import PPETemporalVerificationEngine
from app.config.settings import settings
from app.utils.logger import logger


@dataclass
class Frame:
    """
    Unified Data Structure representing a single video frame moving through the processing pipeline.
    Contains image matrix, temporal metadata, frame index, freeze status, and detection payloads.
    """
    camera_id: int
    frame_id: int
    image: Optional[np.ndarray]
    timestamp: datetime
    fps: float = 0.0
    is_frozen: bool = False
    detections: List[DetectionResult] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def release(self) -> None:
        """
        Safely clears internal matrix references to facilitate prompt garbage collection.
        """
        self.image = None
        self.detections.clear()
        self.metadata.clear()


class BasePreprocessor(ABC):
    """
    Abstract Base Class for Frame Preprocessing.
    """
    @abstractmethod
    def process(self, frame: Frame) -> Frame:
        pass


class StandardPreprocessor(BasePreprocessor):
    """
    Standard OpenCV Preprocessor.
    Handles frame dimension standardization, matrix validation, and optional ROI cropping.
    """

    def __init__(self, target_size: Optional[Tuple[int, int]] = None, roi_crop: Optional[Tuple[float, float, float, float]] = None):
        """
        :param target_size: Optional (width, height) to resize frame.
        :param roi_crop: Optional (ymin, xmin, ymax, xmax) normalized coordinates [0.0 - 1.0].
        """
        self.target_size = target_size
        self.roi_crop = roi_crop

    def process(self, frame: Frame) -> Frame:
        if frame.image is None or frame.image.size == 0:
            logger.warning(f"Preprocessor: Received empty or invalid frame for Camera {frame.camera_id}")
            return frame

        # 1. Apply ROI cropping if defined
        if self.roi_crop:
            h, w = frame.image.shape[:2]
            ymin, xmin, ymax, xmax = self.roi_crop
            y1, x1 = int(ymin * h), int(xmin * w)
            y2, x2 = int(ymax * h), int(xmax * w)
            if y2 > y1 and x2 > x1:
                frame.image = frame.image[y1:y2, x1:x2].copy()
                frame.metadata["roi_applied"] = True

        # 2. Resize frame if target size specified
        if self.target_size:
            tw, th = self.target_size
            curr_h, curr_w = frame.image.shape[:2]
            if (curr_w, curr_h) != (tw, th):
                frame.image = cv2.resize(frame.image, (tw, th), interpolation=cv2.INTER_LINEAR)
                frame.metadata["resized"] = f"{tw}x{th}"

        return frame


class FreezeDetector:
    """
    Detects static, frozen, or stuck camera streams (e.g. NVR stream hang/freeze).
    Uses downsampled grayscale frame matrix difference (Mean Absolute Difference).
    """

    def __init__(
        self,
        difference_threshold: float = 1.5,
        freeze_threshold_seconds: float = 10.0,
        sample_resolution: Tuple[int, int] = (64, 64)
    ):
        """
        :param difference_threshold: Mean absolute pixel diff threshold below which frames are considered identical.
        :param freeze_threshold_seconds: Continuous duration (seconds) of static frames required to flag a freeze.
        :param sample_resolution: Resolution to downsample frames for lightweight comparison.
        """
        self.difference_threshold = difference_threshold
        self.freeze_threshold_seconds = freeze_threshold_seconds
        self.sample_resolution = sample_resolution

        self._previous_gray: Optional[np.ndarray] = None
        self._freeze_start_time: Optional[float] = None
        self._is_frozen_active: bool = False

    def evaluate(self, frame: Frame) -> bool:
        """
        Evaluates frame for freeze state. Returns True if frame is frozen, False otherwise.
        """
        if frame.image is None or frame.image.size == 0:
            return False

        # 1. Downsample and convert to grayscale for lightweight computation
        small = cv2.resize(frame.image, self.sample_resolution, interpolation=cv2.INTER_NEAREST)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        now = time.time()
        if self._previous_gray is None:
            self._previous_gray = gray
            self._freeze_start_time = now
            return False

        # 2. Compute Mean Absolute Difference (MAD)
        diff = cv2.absdiff(gray, self._previous_gray)
        mad = float(np.mean(diff))
        self._previous_gray = gray

        now = time.time()
        frame.metadata["frame_diff_mad"] = round(mad, 3)

        # 3. Check difference threshold
        if mad < self.difference_threshold:
            if self._freeze_start_time is None:
                self._freeze_start_time = now
            
            elapsed_freeze = now - self._freeze_start_time
            if elapsed_freeze >= self.freeze_threshold_seconds:
                if not self._is_frozen_active:
                    self._is_frozen_active = True
                    logger.warning(
                        f"FreezeDetector: Camera {frame.camera_id} stream FROZEN! "
                        f"(No motion detected for {round(elapsed_freeze, 1)}s, MAD={round(mad, 3)})"
                    )
                frame.is_frozen = True
                frame.metadata["freeze_duration_sec"] = round(elapsed_freeze, 1)
                return True
        else:
            if self._is_frozen_active:
                logger.info(f"FreezeDetector: Camera {frame.camera_id} stream motion RESUMED.")
                self._is_frozen_active = False
            self._freeze_start_time = None
            frame.is_frozen = False

        return False

    def reset(self) -> None:
        """
        Resets freeze detector state.
        """
        self._previous_gray = None
        self._freeze_start_time = None
        self._is_frozen_active = False


class BasePostprocessor(ABC):
    """
    Abstract Base Class for Frame Postprocessing.
    """
    @abstractmethod
    def process(self, frame: Frame) -> Frame:
        pass


class StandardPostprocessor(BasePostprocessor):
    """
    Standard OpenCV Postprocessor.
    Enriches frame metadata and adds visual overlays matching high-grade CCTV standards:
    - Item-level green bounding box + '✓ <Item> Found' pill badge for detected PPE
    - Body-region red bounding box + '✕ <Item> Not found' pill badge for missing PPE
    - Clean fire / smoke detection bounding box + 'fire <conf>' label box
    """

    def __init__(self, debug_overlay: bool = True):
        self.debug_overlay = debug_overlay

    def _draw_corner_brackets(self, img: np.ndarray, pt1: Tuple[int, int], pt2: Tuple[int, int], color: Tuple[int, int, int], line_len: int = 14, thickness: int = 2) -> None:
        """Renders modern CCTV HUD corner-bracket bounding boxes."""
        x1, y1 = pt1
        x2, y2 = pt2
        w, h = x2 - x1, y2 - y1
        l = min(line_len, w // 3, h // 3)
        if l < 2:
            cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness, cv2.LINE_AA)
            return

        # Top-Left Corner
        cv2.line(img, (x1, y1), (x1 + l, y1), color, thickness, cv2.LINE_AA)
        cv2.line(img, (x1, y1), (x1, y1 + l), color, thickness, cv2.LINE_AA)
        # Top-Right Corner
        cv2.line(img, (x2, y1), (x2 - l, y1), color, thickness, cv2.LINE_AA)
        cv2.line(img, (x2, y1), (x2, y1 + l), color, thickness, cv2.LINE_AA)
        # Bottom-Left Corner
        cv2.line(img, (x1, y2), (x1 + l, y2), color, thickness, cv2.LINE_AA)
        cv2.line(img, (x1, y2), (x1, y2 - l), color, thickness, cv2.LINE_AA)
        # Bottom-Right Corner
        cv2.line(img, (x2, y2), (x2 - l, y2), color, thickness, cv2.LINE_AA)
        cv2.line(img, (x2, y2), (x2, y2 - l), color, thickness, cv2.LINE_AA)

    def _draw_rounded_rect(self, img: np.ndarray, pt1: Tuple[int, int], pt2: Tuple[int, int], color: Tuple[int, int, int], radius: int = 6, thickness: int = -1) -> None:
        """Helper to draw rounded rectangle in OpenCV."""
        x1, y1 = pt1
        x2, y2 = pt2
        if x2 <= x1 or y2 <= y1:
            return
        r = min(radius, (x2 - x1) // 2, (y2 - y1) // 2)
        if r < 1:
            cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness, cv2.LINE_AA)
            return

        if thickness == -1:
            cv2.rectangle(img, (x1 + r, y1), (x2 - r, y2), color, -1)
            cv2.rectangle(img, (x1, y1 + r), (x2, y2 - r), color, -1)
            cv2.circle(img, (x1 + r, y1 + r), r, color, -1, cv2.LINE_AA)
            cv2.circle(img, (x2 - r, y1 + r), r, color, -1, cv2.LINE_AA)
            cv2.circle(img, (x1 + r, y2 - r), r, color, -1, cv2.LINE_AA)
            cv2.circle(img, (x2 - r, y2 - r), r, color, -1, cv2.LINE_AA)
        else:
            cv2.line(img, (x1 + r, y1), (x2 - r, y1), color, thickness, cv2.LINE_AA)
            cv2.line(img, (x1 + r, y2), (x2 - r, y2), color, thickness, cv2.LINE_AA)
            cv2.line(img, (x1, y1 + r), (x1, y2 - r), color, thickness, cv2.LINE_AA)
            cv2.line(img, (x2, y1 + r), (x2, y2 - r), color, thickness, cv2.LINE_AA)
            cv2.ellipse(img, (x1 + r, y1 + r), (r, r), 180, 0, 90, color, thickness, cv2.LINE_AA)
            cv2.ellipse(img, (x2 - r, y1 + r), (r, r), 270, 0, 90, color, thickness, cv2.LINE_AA)
            cv2.ellipse(img, (x1 + r, y2 - r), (r, r), 90, 0, 90, color, thickness, cv2.LINE_AA)
            cv2.ellipse(img, (x2 - r, y2 - r), (r, r), 0, 0, 90, color, thickness, cv2.LINE_AA)

    def _draw_pill_badge(self, img: np.ndarray, text: str, pos: Tuple[int, int], is_found: bool) -> None:
        """Renders green ('✓') / red ('✕') rounded pill badges matching modern CCTV UI."""
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.48
        thickness = 1
        (tw, th), _ = cv2.getTextSize(text, font, font_scale, thickness)
        x, y = pos
        pad_x, pad_y = 10, 5
        icon_w = 16
        badge_w = icon_w + tw + pad_x * 2 + 4
        badge_h = max(th + pad_y * 2, 26)

        img_h, img_w = img.shape[:2]
        x1 = max(5, min(x, img_w - badge_w - 5))
        y1 = max(5, min(y, img_h - badge_h - 5))
        x2 = x1 + badge_w
        y2 = y1 + badge_h

        bg_color = (0, 185, 75) if is_found else (30, 30, 230)
        border_color = (20, 220, 95) if is_found else (60, 60, 255)

        self._draw_rounded_rect(img, (x1, y1), (x2, y2), bg_color, radius=8, thickness=-1)
        self._draw_rounded_rect(img, (x1, y1), (x2, y2), border_color, radius=8, thickness=1)

        icon_center_y = y1 + badge_h // 2
        if is_found:
            pts = np.array([[x1 + 8, icon_center_y], [x1 + 12, icon_center_y + 4], [x1 + 19, icon_center_y - 4]], np.int32)
            cv2.polylines(img, [pts], False, (255, 255, 255), 2, cv2.LINE_AA)
        else:
            cv2.line(img, (x1 + 9, icon_center_y - 4), (x1 + 17, icon_center_y + 4), (255, 255, 255), 2, cv2.LINE_AA)
            cv2.line(img, (x1 + 17, icon_center_y - 4), (x1 + 9, icon_center_y + 4), (255, 255, 255), 2, cv2.LINE_AA)

        cv2.putText(img, text, (x1 + icon_w + pad_x + 2, y1 + badge_h - pad_y - 1), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

    def process(self, frame: Frame) -> Frame:
        if frame.image is None or frame.image.size == 0:
            return frame

        # Add processing timestamp metadata
        frame.metadata["processed_at"] = datetime.now(timezone.utc).isoformat()
        frame.metadata["detection_count"] = len(frame.detections)

        if self.debug_overlay:
            h, w = frame.image.shape[:2]

            # 1. Stream Freeze Warning Banner
            if frame.is_frozen:
                freeze_text = f"WARNING: STREAM FROZEN ({frame.metadata.get('freeze_duration_sec', 0)}s)"
                cv2.rectangle(frame.image, (int(w * 0.25), 5), (int(w * 0.75), 38), (0, 0, 220), -1)
                cv2.putText(frame.image, freeze_text, (int(w * 0.28), 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)

            # 2. Draw Safety Zone Polygons
            zones = frame.metadata.get("safety_zones", [])
            for zone in zones:
                poly_coords = zone.get("polygon_coordinates", [])
                if len(poly_coords) >= 3:
                    pts = np.array([[int(pt[0] * w), int(pt[1] * h)] for pt in poly_coords], np.int32)
                    pts = pts.reshape((-1, 1, 2))
                    z_type = zone.get("zone_type", "HAZARD").upper()
                    zone_color = (0, 0, 255) if z_type == "RESTRICTED" else (0, 140, 255) if z_type == "HAZARD" else (255, 200, 0)
                    cv2.polylines(frame.image, [pts], True, zone_color, 2, cv2.LINE_AA)
                    z_name = zone.get("name", "Zone")
                    cv2.putText(frame.image, f"ZONE: {z_name} ({z_type})", (pts[0][0][0], max(pts[0][0][1] - 8, 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, zone_color, 2, cv2.LINE_AA)

            # 3. Draw Worker & Item-level PPE Analyses
            worker_analyses = frame.metadata.get("worker_ppe_analyses", [])
            for worker in worker_analyses:
                bbox_data = worker.get("bounding_box", {})
                raw_x1 = int(bbox_data.get("x_min", 0) * w)
                raw_y1 = int(bbox_data.get("y_min", 0) * h)
                raw_x2 = int(bbox_data.get("x_max", 0) * w)
                raw_y2 = int(bbox_data.get("y_max", 0) * h)

                x1 = max(5, min(raw_x1, w - 50))
                y1 = max(5, min(raw_y1, h - 50))
                x2 = min(w - 5, max(x1 + 50, raw_x2))
                y2 = min(h - 5, max(y1 + 50, raw_y2))

                w_box = x2 - x1
                h_box = y2 - y1

                person_id = worker.get("person_id", 101)
                status = worker.get("status", "UNKNOWN")
                missing = [m.lower() for m in worker.get("missing_equipment", [])]
                detected = [d.lower() for d in worker.get("detected_equipment", [])]

                is_pass = (status == "PASS")

                # Worker Box with HUD Corner Brackets
                worker_box_color = (0, 215, 80) if is_pass else (40, 40, 240)
                self._draw_corner_brackets(frame.image, (x1, y1), (x2, y2), worker_box_color, line_len=18, thickness=2)

                # Worker Header ID & Status Tag (High-contrast bright white text on solid status badge)
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.50
                thickness = 1
                if is_pass:
                    worker_tag = f"Worker #{person_id} | PASS"
                    badge_bg_color = (0, 160, 60)       # Solid Emerald Green
                    text_color = (255, 255, 255)       # Crisp Pure White Text
                else:
                    clean_missing = [m for m in missing if m.lower() not in ["helmet", "cap", "hard_hat", "headgear"]]
                    missing_display_map = {
                        "vest": "VEST",
                        "safety_vest": "VEST",
                        "jacket": "VEST",
                        "goggles": "GLASSES",
                        "glass": "GLASSES",
                        "glasses": "GLASSES",
                        "safety_glasses": "GLASSES",
                        "safety_glass": "GLASSES"
                    }
                    missing_str = ", ".join([missing_display_map.get(m.lower(), m.upper()) for m in clean_missing]) if clean_missing else "VEST & GLASSES"
                    worker_tag = f"Worker #{person_id} | MISSING: {missing_str}"
                    badge_bg_color = (30, 30, 210)      # Solid High-Vis Crimson Red
                    text_color = (255, 255, 255)       # Crisp Pure White Text

                (tw, th), _ = cv2.getTextSize(worker_tag, font, font_scale, thickness)
                tag_y = max(th + 10, y1 - 8)
                badge_x2 = min(w - 5, x1 + tw + 16)
                self._draw_rounded_rect(frame.image, (x1, tag_y - th - 8), (badge_x2, tag_y + 4), badge_bg_color, radius=6, thickness=-1)
                self._draw_rounded_rect(frame.image, (x1, tag_y - th - 8), (badge_x2, tag_y + 4), worker_box_color, radius=6, thickness=1)
                cv2.putText(frame.image, worker_tag, (x1 + 8, tag_y - 2), font, font_scale, text_color, thickness, cv2.LINE_AA)

                # Equipment categories to render (ONLY draw badges for DETECTED items; helmet removed per requirements)
                equipment_specs = [
                    (["vest", "jacket", "safety_vest", "safety_jacket"], "Safety Vest Found"),
                    (["gloves", "glove"], "Gloves Found"),
                    (["goggles", "glasses", "safety_glasses", "safety_glass", "glass", "eyewear", "eye_protection", "spectacles", "safety_goggles"], "Safety Glasses Found"),
                    (["safety_shoes", "shoes", "boots"], "Safety Shoes Found"),
                ]

                for keys, found_label in equipment_specs:
                    is_det = any(k in detected for k in keys)
                    if not is_det:
                        continue

                    raw_det_box = None
                    for det in frame.detections:
                        if det.label.lower() in keys:
                            dx1, dy1, dx2, dy2 = det.bbox.to_pixel_coords(w, h)
                            if dx1 < x2 and dx2 > x1 and dy1 < y2 and dy2 > y1:
                                raw_det_box = (max(5, dx1), max(5, dy1), min(w - 5, dx2), min(h - 5, dy2))
                                break

                    if raw_det_box:
                        ix1, iy1, ix2, iy2 = raw_det_box
                    elif found_label == "Safety Glasses Found":
                        # Eye region fallback
                        ix1 = max(5, x1 + int(w_box * 0.15))
                        iy1 = max(5, y1 + int(h_box * 0.14))
                        ix2 = min(w - 5, x2 - int(w_box * 0.15))
                        iy2 = min(h - 5, y1 + int(h_box * 0.38))
                    elif found_label == "Helmet Found":
                        ix1 = max(5, x1)
                        iy1 = max(5, y1)
                        ix2 = min(w - 5, x2)
                        iy2 = min(h - 5, y1 + int(h_box * 0.30))
                    elif found_label == "Safety Vest Found":
                        ix1 = max(5, x1)
                        iy1 = max(5, y1 + int(h_box * 0.20))
                        ix2 = min(w - 5, x2)
                        iy2 = min(h - 5, y1 + int(h_box * 0.75))
                    else:
                        ix1 = max(5, x1)
                        iy1 = max(5, y1)
                        ix2 = min(w - 5, x2)
                        iy2 = min(h - 5, y2)

                    box_color = (0, 215, 80)
                    self._draw_corner_brackets(frame.image, (ix1, iy1), (ix2, iy2), box_color, line_len=10, thickness=2)
                    badge_y = max(5, iy1 - 28) if iy1 >= 32 else iy1 + 4
                    self._draw_pill_badge(frame.image, found_label, (ix1, badge_y), is_found=True)

            # 4. Draw Detections Bounding Boxes (Fire, Smoke, and Standalone PPE Items)
            drawn_worker_boxes = []
            for worker in worker_analyses:
                bbox_data = worker.get("bounding_box", {})
                drawn_worker_boxes.append((
                    int(bbox_data.get("x_min", 0) * w),
                    int(bbox_data.get("y_min", 0) * h),
                    int(bbox_data.get("x_max", 0) * w),
                    int(bbox_data.get("y_max", 0) * h)
                ))

            for det in frame.detections:
                label = det.label.lower()
                if label == "person":
                    continue

                dx1, dy1, dx2, dy2 = det.bbox.to_pixel_coords(w, h)
                x1 = max(5, min(dx1, w - 20))
                y1 = max(5, min(dy1, h - 20))
                x2 = min(w - 5, max(x1 + 20, dx2))
                y2 = min(h - 5, max(y1 + 20, dy2))

                # Handle standalone PPE items (e.g. vest held up to camera, exclude helmet)
                if label in ["helmet", "cap", "hard_hat", "headgear"]:
                    continue

                is_ppe = label in ["vest", "jacket", "mask", "goggles", "gloves", "safety_shoes", "glass"]
                if is_ppe:
                    # Check if already covered by an associated worker's detected equipment
                    already_associated = any(
                        (x1 >= bx1 - 20 and y1 >= by1 - 20 and x2 <= bx2 + 20 and y2 <= by2 + 20)
                        for (bx1, by1, bx2, by2) in drawn_worker_boxes
                    )
                    if already_associated:
                        continue

                    box_color = (0, 215, 80)
                    self._draw_corner_brackets(frame.image, (x1, y1), (x2, y2), box_color, line_len=12, thickness=2)
                    badge_label = "Safety Vest Found" if label in ["vest", "jacket"] else f"{label.title()} Found"
                    badge_y = max(5, y1 - 28) if y1 >= 32 else y1 + 4
                    self._draw_pill_badge(frame.image, badge_label, (x1, badge_y), is_found=True)
                    continue

                # Fire & Smoke detection drawing with responsive confidence threshold
                min_draw_conf = getattr(settings, "FIRE_CONFIDENCE_THRESHOLD", 0.18) if "fire" in label else getattr(settings, "SMOKE_CONFIDENCE_THRESHOLD", 0.18)
                if det.confidence < min_draw_conf:
                    continue

                is_fire = "fire" in label
                box_color = (30, 30, 235) if is_fire else (0, 150, 255)

                self._draw_corner_brackets(frame.image, (x1, y1), (x2, y2), box_color, line_len=14, thickness=2)

                conf_str = f"{label.upper()} ({int(det.confidence * 100)}%)"
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.48
                thickness = 1
                (tw, th), _ = cv2.getTextSize(conf_str, font, font_scale, thickness)

                badge_y1 = max(5, y1 - th - 8) if y1 >= th + 10 else y1
                badge_x2 = min(w - 5, x1 + tw + 12)
                badge_y2 = badge_y1 + th + 6

                self._draw_rounded_rect(frame.image, (x1, badge_y1), (badge_x2, badge_y2), box_color, radius=6, thickness=-1)
                cv2.putText(frame.image, conf_str, (x1 + 6, badge_y2 - 4), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

        return frame


class BaseEventManager(ABC):
    """
    Abstract Base Class for Event Management & Dispatching.
    """
    @abstractmethod
    def dispatch_frame_events(self, frame: Frame) -> None:
        pass


class StandardEventManager(BaseEventManager):
    """
    Standard Event Manager dispatching alerts to callback functions (WebSockets, DB, Logger).
    """

    def __init__(self, event_callback: Optional[Callable[[str, Dict[str, Any]], Any]] = None):
        self.event_callback = event_callback
        self._last_freeze_alert_time: float = 0.0
        self._last_detection_dispatch_time: float = 0.0

    def dispatch_frame_events(self, frame: Frame) -> None:
        if not self.event_callback:
            return

        now = time.time()

        # 1. Dispatch Stream Freeze Alert (throttled to max 1 alert per 10s)
        if frame.is_frozen and (now - self._last_freeze_alert_time) > 10.0:
            self._last_freeze_alert_time = now
            payload = {
                "camera_id": frame.camera_id,
                "event_type": "STREAM_FROZEN",
                "timestamp": frame.timestamp.isoformat(),
                "duration_seconds": frame.metadata.get("freeze_duration_sec", 0)
            }
            try:
                self.event_callback("STREAM_FROZEN", payload)
            except Exception as e:
                logger.warning(f"EventManager: Failed to dispatch freeze alert callback: {str(e)}")

        # 2. Dispatch Verified State Machine Alert Events (ALERT_SENT, ACTIVE, CLEARED) - Instant
        verified_events = frame.metadata.get("verified_events", [])
        for evt_dict in verified_events:
            event_name = f"VERIFIED_{evt_dict.get('state', 'ALERT')}"
            try:
                self.event_callback(event_name, evt_dict)
            except Exception as e:
                logger.warning(f"EventManager: Failed to dispatch verified alert callback: {str(e)}")

        # 3. Dispatch Raw AI Detection Events (Throttled to max 2 per second to prevent WebSocket/frontend flooding)
        if frame.detections and (now - self._last_detection_dispatch_time) >= 0.5:
            self._last_detection_dispatch_time = now
            for det in frame.detections:
                payload = {
                    "camera_id": frame.camera_id,
                    "event_type": "DETECTION_ALERT",
                    "label": det.label,
                    "confidence": det.confidence,
                    "bbox": det.bbox.to_dict(),
                    "timestamp": frame.timestamp.isoformat()
                }
                try:
                    self.event_callback("DETECTION_ALERT", payload)
                except Exception as e:
                    logger.warning(f"EventManager: Failed to dispatch detection alert callback: {str(e)}")


class FramePipeline:
    """
    Unified Frame Processing Pipeline Orchestrator.
    Executes modular AI detectors with per-camera toggles, worker tracking, polygon zone evaluation,
    safety rule correlation, and temporal verification.
    Failure of any individual detector is completely isolated to guarantee resilient system uptime.
    """

    def __init__(
        self,
        camera_id: int,
        preprocessor: Optional[BasePreprocessor] = None,
        freeze_detector: Optional[FreezeDetector] = None,
        detector: Optional[BaseDetector] = None,
        fire_smoke_detector: Optional[BaseDetector] = None,
        ppe_detector: Optional[BaseDetector] = None,
        person_detector: Optional[BaseDetector] = None,
        verification_engine: Optional[CameraVerificationEngine] = None,
        postprocessor: Optional[BasePostprocessor] = None,
        event_manager: Optional[BaseEventManager] = None,
        fire_smoke_enabled: bool = True,
        ppe_enabled: bool = True,
        person_enabled: bool = True,
        zone_enabled: bool = True,
        ppe_inference_interval_sec: float = 0.25
    ):
        self.camera_id = camera_id
        self.preprocessor = preprocessor or StandardPreprocessor()
        # FreezeDetector disabled: synthetic/webcam sources with still scenes should never be flagged
        self.freeze_detector = FreezeDetector(difference_threshold=0.01, freeze_threshold_seconds=9999.0)
        
        # Detector modules
        self.fire_smoke_detector = fire_smoke_detector or detector or FireSmokeDetector()
        # Do not spend CPU on PPE/person models when this camera has those
        # modules disabled.  This keeps fire/smoke response responsive on a
        # single-camera CPU installation.
        self.ppe_detector = (ppe_detector or PPEDetector()) if ppe_enabled else None
        self.person_detector = (person_detector or PersonDetector()) if person_enabled else None
        
        # Detector toggles & scheduling
        self.fire_smoke_enabled = fire_smoke_enabled
        self.ppe_enabled = ppe_enabled
        self.person_enabled = person_enabled
        self.zone_enabled = zone_enabled
        self.ppe_inference_interval_sec = ppe_inference_interval_sec
        self._last_ppe_inference_time: float = 0.0

        # Subsystems
        self.verification_engine = verification_engine or CameraVerificationEngine(
            camera_id=camera_id,
            min_confidence=None,  # Use class-specific thresholds (fire, smoke)
            min_consecutive_frames=None,  # Use class-specific settings (FIRE_MIN_CONSECUTIVE_FRAMES, SMOKE_MIN_CONSECUTIVE_FRAMES)
            min_duration_seconds=None     # Use class-specific settings (FIRE_MIN_DURATION_SECONDS, SMOKE_MIN_DURATION_SECONDS)
        )
        self.tracker = PersonTracker(camera_id=camera_id)
        self.association_engine = PPEAssociationEngine()
        self.zone_engine = ZoneEngine()
        self.rule_engine = SafetyRuleEngine(cooldown_seconds=getattr(settings, "PPE_ALERT_COOLDOWN_SECONDS", 60.0))
        self.ppe_verification_engine = PPETemporalVerificationEngine(
            camera_id=camera_id,
            min_consecutive_frames=getattr(settings, "PPE_VERIFICATION_FRAMES", 3),
            min_duration_seconds=getattr(settings, "PPE_VERIFICATION_DURATION_SECONDS", 1.0)
        )

        self.postprocessor = postprocessor or StandardPostprocessor(debug_overlay=True)
        self.event_manager = event_manager or StandardEventManager()
        
        self.active_safety_zones: List[Dict[str, Any]] = []
        self.active_ppe_profile: Optional[Dict[str, Any]] = None
        
        self._latest_detections: List[DetectionResult] = []
        self._latest_worker_analyses: List[Dict[str, Any]] = []
        self._latest_safety_zones: List[Dict[str, Any]] = []
        self._latest_is_frozen: bool = False
        self._smoothed_detections: Dict[str, Tuple[DetectionResult, float]] = {}
        self._smoothed_workers: Dict[int, Tuple[Dict[str, Any], float]] = {}
        self._worker_compliance_history: Dict[int, Dict[str, float]] = {}
        self._lock = threading.Lock()

    @property
    def detector(self) -> Any:
        return self.fire_smoke_detector

    @detector.setter
    def detector(self, value: Any) -> None:
        self.fire_smoke_detector = value

    def set_safety_zones(self, zones: List[Dict[str, Any]]) -> None:
        with self._lock:
            self.active_safety_zones = zones

    def set_ppe_profile(self, profile: Dict[str, Any]) -> None:
        with self._lock:
            self.active_ppe_profile = profile

    def process_frame(
        self,
        raw_image: np.ndarray,
        frame_id: int,
        fps: float,
        timestamp: Optional[datetime] = None
    ) -> Frame:
        """
        Executes frame processing pipeline sequentially with per-detector failure isolation.
        """
        ts = timestamp or datetime.now(timezone.utc)
        now_ts = time.time()
        
        # 1. Initialize Frame Data Structure
        frame = Frame(
            camera_id=self.camera_id,
            frame_id=frame_id,
            image=raw_image.copy() if raw_image is not None else np.zeros((480, 640, 3), dtype=np.uint8),
            timestamp=ts,
            fps=fps
        )

        # 2. Stage 1: Preprocessor
        frame = self.preprocessor.process(frame)

        # 3. Stage 2: Freeze Detection
        self.freeze_detector.evaluate(frame)

        all_detections: List[DetectionResult] = []
        fire_smoke_dets: List[DetectionResult] = []
        ppe_dets: List[DetectionResult] = []
        person_dets: List[DetectionResult] = []

        frame_info = {
            "frame_id": frame_id,
            "fps": fps,
            "resolution": f"{frame.image.shape[1]}x{frame.image.shape[0]}" if frame.image is not None else "0x0"
        }

        # 4. Stage 3: AI Model Inference (Isolated execution with dynamic delegation)
        if frame.image is None or frame.image.size == 0:
            return frame

        img: np.ndarray = frame.image
        should_run_ppe = (now_ts - self._last_ppe_inference_time) >= self.ppe_inference_interval_sec

        if should_run_ppe:
            self._last_ppe_inference_time = now_ts

            # 4.1 Person Detector Execution (Run FIRST to provide fast YOLO worker bounding boxes)
            if self.person_enabled and self.person_detector:
                try:
                    p_res = self.person_detector.detect(img)
                    person_dets.extend(p_res)
                    all_detections.extend(p_res)
                except Exception as e:
                    logger.error(f"Camera-{self.camera_id} PersonDetector execution error: {str(e)}")

            # 4.2 PPE Detector Execution (Conditionally bypass if no workers/persons are in view to save ~50% CPU)
            has_persons = len(person_dets) > 0 or any(d.label.lower() in ["person", "worker"] for d in all_detections)
            standalone_vest = getattr(settings, "ENABLE_STANDALONE_VEST_FALLBACK", False)
            should_execute_ppe = (not self.person_enabled) or has_persons or standalone_vest

            if self.ppe_enabled and self.ppe_detector and should_execute_ppe:
                try:
                    import inspect
                    sig = inspect.signature(self.ppe_detector.detect)
                    if "person_dets" in sig.parameters:
                        ppe_res = getattr(self.ppe_detector, "detect")(img, person_dets=person_dets)
                    else:
                        ppe_res = self.ppe_detector.detect(img)
                    # Exclude helmet from detections per requirement
                    ppe_res = [d for d in ppe_res if d.label.lower() not in ["helmet", "cap", "hard_hat", "headgear"]]
                    ppe_dets.extend(ppe_res)
                    all_detections.extend(ppe_res)
                    if hasattr(self.ppe_detector, "has_person_class") and self.ppe_detector.has_person_class():
                        # If PPE model also detects persons, merge any unique persons
                        for d in ppe_res:
                            if d.label.lower() in ["person", "worker"] and d not in person_dets:
                                person_dets.append(d)
                except Exception as e:
                    logger.error(f"Camera-{self.camera_id} PPEDetector execution error: {str(e)}")

        # 4.3 Fire / Smoke Detector Execution (passes candidate ROIs from person/gear detections if supported)
        if self.fire_smoke_enabled and self.fire_smoke_detector:
            try:
                candidate_rois = [d.bbox for d in all_detections] if all_detections else None
                import inspect
                sig = inspect.signature(self.fire_smoke_detector.detect)
                if "candidate_rois" in sig.parameters:
                    fs_res = self.fire_smoke_detector.detect(img, candidate_rois=candidate_rois)
                else:
                    fs_res = self.fire_smoke_detector.detect(img)
                fire_smoke_dets.extend(fs_res)
                all_detections.extend(fs_res)
            except Exception as e:
                logger.error(f"Camera-{self.camera_id} FireSmokeDetector execution error: {str(e)}")

        for det in all_detections:
            det.camera_id = self.camera_id
            det.timestamp = ts.isoformat()
            det.frame_info = frame_info
        frame.detections = all_detections

        now_ts = time.time()
        with self._lock:
            # Update smoothed fire/smoke/general detections with 0.75s persistence decay
            for det in all_detections:
                key = f"{det.label}_{round(det.bbox.x_min, 2)}_{round(det.bbox.y_min, 2)}"
                self._smoothed_detections[key] = (det, now_ts + 0.75)

            # Purge expired detections
            self._smoothed_detections = {k: v for k, v in self._smoothed_detections.items() if v[1] > now_ts}
            self._latest_detections = [v[0] for v in self._smoothed_detections.values()]
            self._latest_is_frozen = frame.is_frozen
            current_zones = list(self.active_safety_zones)
            current_profile = dict(self.active_ppe_profile) if self.active_ppe_profile else None

        # 5. Stage 4: Person Tracking & PPE Spatial Association Engine
        tracked_persons = []
        if self.person_enabled:
            # Combine person detections from person_detector and ppe_detector
            raw_person_dets = person_dets + [d for d in ppe_dets if d.label.lower() in ["person", "worker"]]
            
            # Apply NMS deduplication to remove duplicate person boxes for the same worker
            all_person_dets: List[DetectionResult] = []
            for p_det in sorted(raw_person_dets, key=lambda d: d.confidence, reverse=True):
                if not any(p_det.bbox.iou(k.bbox) >= 0.40 for k in all_person_dets):
                    all_person_dets.append(p_det)

            if should_run_ppe or not self.tracker._tracked_persons:
                tracked_persons = self.tracker.update(all_person_dets)
            else:
                tracked_persons = self.tracker.get_active_tracks()

        # Enforce vest & goggles (glasses) requirement; explicitly remove helmet
        raw_req = current_profile.get("required_equipment", ["vest", "goggles"]) if current_profile else ["vest", "goggles"]
        required_equipment = [e for e in raw_req if e.lower() not in ["helmet", "cap", "hard_hat", "headgear"]]
        if not required_equipment:
            required_equipment = ["vest", "goggles"]

        worker_analyses = self.association_engine.associate(
            camera_id=self.camera_id,
            tracked_persons=tracked_persons,
            ppe_detections=ppe_dets,
            required_equipment=required_equipment,
            timestamp=ts.isoformat()
        )
        frame.metadata["worker_ppe_analyses"] = [w.to_dict() for w in worker_analyses]

        # 6. Stage 5: Safety Zone Evaluation Engine
        zone_evaluations = []
        if self.zone_enabled and current_zones:
            frame.metadata["safety_zones"] = current_zones
            zone_evaluations = self.zone_engine.evaluate_workers_in_zones(worker_analyses, current_zones)

        # Cache worker analyses & zones for smooth overlay rendering with temporal hysteresis
        now_ts = time.time()
        with self._lock:
            for w in worker_analyses:
                pid = w.person_id
                w_dict = w.to_dict()

                # Update detected gear history for this worker
                if pid not in self._worker_compliance_history:
                    self._worker_compliance_history[pid] = {}
                worker_gear_times = self._worker_compliance_history[pid]

                for item in w.detected_equipment:
                    worker_gear_times[item.lower()] = now_ts + 1.2

                # If an item is in missing_equipment but was detected recently (within 0.75s),
                # grace it as detected to prevent 1-frame strobe/violation
                missing_items = list(w_dict.get("missing_equipment", []))
                detected_items = list(w_dict.get("detected_equipment", []))

                adjusted_missing = []
                for m in missing_items:
                    if worker_gear_times.get(m.lower(), 0.0) > now_ts:
                        if m not in detected_items:
                            detected_items.append(m)
                    else:
                        adjusted_missing.append(m)

                w_dict["missing_equipment"] = adjusted_missing
                w_dict["detected_equipment"] = detected_items
                if not adjusted_missing:
                    w_dict["status"] = "PASS"

                # Synchronize WorkerPPEAnalysis directly so rules engine & verification FSM receive stabilized state
                w.missing_equipment = adjusted_missing
                w.detected_equipment = detected_items
                if not adjusted_missing:
                    w.status = "PASS"

                self._smoothed_workers[pid] = (w_dict, now_ts + 1.0)

            # Purge expired workers
            self._smoothed_workers = {pid: v for pid, v in self._smoothed_workers.items() if v[1] > now_ts}
            self._latest_worker_analyses = [v[0] for v in self._smoothed_workers.values()]
            self._latest_safety_zones = frame.metadata.get("safety_zones", [])

        # 7. Stage 6: Safety Rules Engine & Correlation
        safety_decisions = self.rule_engine.evaluate_rules(
            camera_id=self.camera_id,
            fire_smoke_detections=fire_smoke_dets,
            worker_analyses=worker_analyses,
            zone_evaluations=zone_evaluations,
            timestamp=ts.isoformat()
        )
        frame.metadata["safety_decisions"] = [s.to_dict() for s in safety_decisions]

        # 8. Stage 7: Temporal Detection & PPE Verification (False-Alarm Reduction State Machines)
        verified_events = self.verification_engine.process_frame_detections(fire_smoke_dets, frame_info)
        verified_ppe_events = self.ppe_verification_engine.process_worker_analyses(worker_analyses)
        all_verified = verified_events + verified_ppe_events
        frame.metadata["verified_events"] = [e.to_dict() for e in all_verified]

        # 9. Stage 8: Postprocessor (Visual Overlay Generation)
        frame = self.postprocessor.process(frame)

        # 10. Stage 9: Event Dispatcher (WebSocket / Notifications)
        self.event_manager.dispatch_frame_events(frame)

        return frame

    def draw_display_overlay(
        self,
        raw_image: np.ndarray,
        frame_id: int,
        fps: float,
        timestamp: Optional[datetime] = None
    ) -> np.ndarray:
        """
        Renders cached active bounding box overlays onto display frame cleanly.
        Prevents live stream flickering across AI inference cycles.
        """
        if raw_image is None or raw_image.size == 0:
            return raw_image

        now_ts = time.time()
        with self._lock:
            # Purge expired smoothed items
            self._smoothed_detections = {k: v for k, v in self._smoothed_detections.items() if v[1] > now_ts}
            self._smoothed_workers = {pid: v for pid, v in self._smoothed_workers.items() if v[1] > now_ts}
            active_dets = [v[0] for v in self._smoothed_detections.values()]
            active_workers = [v[0] for v in self._smoothed_workers.values()]
            active_zones = list(self.active_safety_zones)
            is_frozen = self._latest_is_frozen

            if not active_dets and not active_workers and not active_zones and not is_frozen:
                return raw_image

        display_image = raw_image.copy()
        ts = timestamp or datetime.now(timezone.utc)

        render_frame = Frame(
            camera_id=self.camera_id,
            frame_id=frame_id,
            image=display_image,
            timestamp=ts,
            fps=fps,
            is_frozen=is_frozen,
            detections=active_dets
        )
        render_frame.metadata["worker_ppe_analyses"] = active_workers
        render_frame.metadata["safety_zones"] = active_zones
        self.postprocessor.process(render_frame)
        return render_frame.image if render_frame.image is not None else display_image

    def reset(self) -> None:
        """
        Resets internal pipeline detectors and verification state machine upon stream reconnect.
        """
        with self._lock:
            self._latest_detections.clear()
            self._latest_worker_analyses.clear()
            self._smoothed_detections.clear()
            self._smoothed_workers.clear()
            self._worker_compliance_history.clear()
            self._latest_is_frozen = False
        self.freeze_detector.reset()
        self.verification_engine.reset_all()
