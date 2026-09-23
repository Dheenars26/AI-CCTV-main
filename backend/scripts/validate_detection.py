#!/usr/bin/env python3
"""
Detection accuracy + speed validation harness.

Run this against *your own* CCTV footage before and after tuning thresholds. It reports exactly the
two things that matter operationally: how often the system is wrong (false positives / misses) and
how much each camera actually costs.

Usage
-----
Validate against labelled images::

    python scripts/validate_detection.py --images ./samples --labels ./samples/labels.json

Labels file format (class names are normalised, so "safety vest" == "vest")::

    {
      "frame_0001.jpg": {"fire": [[x1, y1, x2, y2]], "smoke": [[...]], "person": [[...]]},
      "empty_warehouse.jpg": {},
      "worker_no_vest.jpg": {"person": [[300, 40, 560, 520]], "vest_absent": true}
    }

An image with an empty label object is treated as a **negative**: any fire/smoke/PPE detection on it
is counted as a false positive, which is the measurement that matters for false-alarm rate.

Benchmark throughput instead of accuracy::

    python scripts/validate_detection.py --benchmark

Notes
-----
* Images only (frames from your own recordings are ideal). Label 20-50 frames per scene to get
  meaningful numbers.
* Annotated copies are written to ``--out`` so you can see exactly what the model saw.
"""

import argparse
import json
import os
import statistics
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config.settings import settings  # noqa: E402
from app.detection.roi_refine import normalise_ppe_label  # noqa: E402


IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".webp")


def _iou(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _match_counts(
    predictions: List[Tuple[str, float, Tuple[float, float, float, float]]],
    ground_truth: Dict[str, List[List[float]]],
    iou_threshold: float = 0.35,
) -> Tuple[int, int, int]:
    """Returns (true_positives, false_positives, false_negatives) for one image."""
    gt_pool = []
    for raw_label, boxes in ground_truth.items():
        canonical = normalise_ppe_label(raw_label) or raw_label.lower()
        for box in boxes:
            gt_pool.append([canonical, tuple(float(v) for v in box), False])

    tp = fp = 0
    for label, _conf, box in predictions:
        best_idx, best_iou = -1, 0.0
        for idx, (gt_label, gt_box, taken) in enumerate(gt_pool):
            if taken or gt_label != label:
                continue
            score = _iou(box, gt_box)  # type: ignore[arg-type]
            if score > best_iou:
                best_iou, best_idx = score, idx
        if best_idx >= 0 and best_iou >= iou_threshold:
            gt_pool[best_idx][2] = True
            tp += 1
        else:
            fp += 1
    fn = sum(1 for _l, _b, taken in gt_pool if not taken)
    return tp, fp, fn


def _collect_predictions(frame) -> List[Tuple[str, float, Tuple[float, float, float, float]]]:
    out: List[Tuple[str, float, Tuple[float, float, float, float]]] = []
    h, w = frame.image.shape[:2]
    for det in frame.detections:
        canonical = normalise_ppe_label(det.label) or det.label.lower()
        x1, y1, x2, y2 = det.bbox.to_pixel_coords(w, h)
        out.append((canonical, float(det.confidence), (float(x1), float(y1), float(x2), float(y2))))
    return out


def _annotate(image: np.ndarray, frame, min_conf: float = 0.25) -> np.ndarray:
    canvas = image.copy()
    h, w = image.shape[:2]
    palette = {
        "fire": (0, 0, 255), "smoke": (0, 165, 255), "person": (255, 200, 0),
        "vest": (0, 200, 0), "goggles": (255, 0, 255), "helmet": (0, 255, 255),
    }
    for det in frame.detections:
        if det.confidence < min_conf and det.label not in ("fire", "smoke"):
            continue
        x1, y1, x2, y2 = det.bbox.to_pixel_coords(w, h)
        colour = palette.get(normalise_ppe_label(det.label) or det.label, (200, 200, 200))
        cv2.rectangle(canvas, (x1, y1), (x2, y2), colour, 2)
        evidence = det.metadata.get("evidence", "")
        text = f"{det.label} {det.confidence:.2f}" + (f" [{evidence}]" if evidence else "")
        cv2.putText(canvas, text, (x1, max(14, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, colour, 2, cv2.LINE_AA)
    return canvas


def run_validation(images_dir: str, labels_path: Optional[str], out_dir: Optional[str], max_frames: int) -> int:
    from app.camera.pipeline import FramePipeline

    paths = sorted(
        os.path.join(images_dir, f) for f in os.listdir(images_dir)
        if f.lower().endswith(IMAGE_EXTENSIONS)
    )[:max_frames]
    if not paths:
        print(f"No images found in {images_dir}")
        return 1

    labels: Dict[str, Any] = {}
    if labels_path and os.path.isfile(labels_path):
        with open(labels_path, "r", encoding="utf-8") as handle:
            labels = json.load(handle)

    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # Validation measures *detector* quality, so the scheduler's cost-based gating is disabled:
    # every frame is fully processed and nothing is skipped for timing reasons.
    _previous_cadence = getattr(settings, "PPE_ADAPTIVE_CADENCE", True)
    _previous_refine_every = getattr(settings, "PPE_ROI_REFINE_EVERY_N", 2)
    settings.PPE_ADAPTIVE_CADENCE = False
    settings.PPE_ROI_REFINE_EVERY_N = 1  # per-frame quality is what is being measured here
    pipeline = FramePipeline(camera_id=1)
    pipeline.motion_gate.enabled = False
    pipeline.ppe_inference_interval_sec = 0.0

    latencies: List[float] = []
    totals = {"tp": 0, "fp": 0, "fn": 0}
    class_stats: Dict[str, Dict[str, int]] = {}
    negative_frames = 0
    negative_frames_clean = 0
    per_frame_rows: List[str] = []

    for idx, path in enumerate(paths):
        image = cv2.imread(path)
        if image is None:
            continue
        name = os.path.basename(path)
        pipeline.reset()

        t0 = time.perf_counter()
        frame = pipeline.process_frame(image, frame_id=idx, fps=25.0)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(latency_ms)

        predictions = _collect_predictions(frame)
        per_class = ", ".join(f"{lbl}:{conf:.2f}" for lbl, conf, _ in predictions) or "-"
        row = f"{name:44s} {latency_ms:7.1f}ms  {per_class}"
        per_frame_rows.append(row)

        for label, _conf, _box in predictions:
            class_stats.setdefault(label, {"pred": 0, "tp": 0, "fp": 0})
            class_stats[label]["pred"] += 1

        ground_truth = labels.get(name)
        if ground_truth is not None:
            if not ground_truth:
                negative_frames += 1
                if not predictions:
                    negative_frames_clean += 1
            tp, fp, fn = _match_counts(predictions, ground_truth)
            totals["tp"] += tp
            totals["fp"] += fp
            totals["fn"] += fn
            for label, _conf, _box in predictions:
                class_stats.setdefault(label, {"pred": 0, "tp": 0, "fp": 0})
            per_frame_rows[-1] += f"   | tp={tp} fp={fp} fn={fn}"

        if out_dir:
            cv2.imwrite(os.path.join(out_dir, name), _annotate(image, frame))

    print("\n".join(per_frame_rows))
    print("\n" + "=" * 78)
    if latencies:
        latencies_sorted = sorted(latencies)
        p95 = latencies_sorted[min(len(latencies_sorted) - 1, int(0.95 * len(latencies_sorted)))]
        print(f"Frames            : {len(latencies)}")
        print(f"Latency mean/p95  : {statistics.mean(latencies):.1f} ms / {p95:.1f} ms")
        print(f"Throughput        : {1000.0 / statistics.mean(latencies):.2f} FPS per camera (single process)")
    print(f"Detections by class: { {k: v['pred'] for k, v in class_stats.items()} }")
    if labels:
        tp, fp, fn = totals["tp"], totals["fp"], totals["fn"]
        precision = tp / (tp + fp) if (tp + fp) else float("nan")
        recall = tp / (tp + fn) if (tp + fn) else float("nan")
        print(f"Matched vs labels : TP={tp} FP={fp} FN={fn}  precision={precision:.3f} recall={recall:.3f}")
        if negative_frames:
            print(
                f"Negative frames   : {negative_frames}, clean (zero detections) = "
                f"{negative_frames_clean} ({100.0 * negative_frames_clean / negative_frames:.0f}%)"
            )
    else:
        print("No labels supplied: precision/recall not computed. See --labels format in this file's docstring.")
    print("=" * 78)
    settings.PPE_ADAPTIVE_CADENCE = _previous_cadence
    settings.PPE_ROI_REFINE_EVERY_N = _previous_refine_every
    return 0


def run_benchmark(iterations: int = 8) -> int:
    """
    Measures the pipeline on a synthetic scene at two intensities: an idle scene (nothing moving)
    and an occupied scene (a worker walking). This is what shows where the CPU actually goes.
    """
    from app.camera.pipeline import FramePipeline

    rng = np.random.default_rng(7)
    background = np.full((720, 1280, 3), 70, dtype=np.uint8)
    background[:] = rng.integers(50, 90, (720, 1280, 3), dtype=np.uint8)
    cv2.rectangle(background, (0, 520), (1280, 720), (95, 95, 95), -1)  # floor

    def empty_frame() -> np.ndarray:
        return background.copy()

    def worker_frame(offset: int) -> np.ndarray:
        frame = background.copy()
        x = 300 + offset * 12
        cv2.rectangle(frame, (x, 200), (x + 90, 470), (180, 120, 60), -1)      # body
        cv2.circle(frame, (x + 45, 180), 28, (140, 175, 225), -1)              # head
        cv2.rectangle(frame, (x, 240), (x + 90, 350), (40, 190, 250), -1)      # hi-vis vest
        cv2.line(frame, (x + 10, 185), (x + 80, 185), (30, 30, 30), 4)         # glasses brow bar
        return frame

    report: Dict[str, Any] = {}
    for label, factory, motion in (("idle scene (no motion)", empty_frame, False),
                                   ("occupied scene (worker)", worker_frame, True)):
        pipeline = FramePipeline(camera_id=1)
        timings: List[float] = []
        for i in range(iterations + 3):  # warm-up
            image = factory(i) if motion else factory()
            t0 = time.perf_counter()
            pipeline.process_frame(image, frame_id=i, fps=25.0)
            cost = (time.perf_counter() - t0) * 1000.0
            if i >= 3:
                timings.append(cost)
        report[label] = {
            "mean_ms": round(statistics.mean(timings), 1),
            "min_ms": round(min(timings), 1),
            "fps": round(1000.0 / statistics.mean(timings), 2),
        }

    print(json.dumps(report, indent=2))
    print(
        "\nReading: the idle scene only pays for the fire/smoke network; the worker detectors are\n"
        "gated off until something moves. The occupied scene pays for the full worker branch."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate detection accuracy and speed.")
    parser.add_argument("--images", help="Directory of test frames (jpg/png).")
    parser.add_argument("--labels", help="Optional JSON file with ground-truth boxes.")
    parser.add_argument("--out", help="Optional directory for annotated output frames.")
    parser.add_argument("--max-frames", type=int, default=200, help="Cap the number of frames used.")
    parser.add_argument("--benchmark", action="store_true", help="Run the speed benchmark instead.")
    args = parser.parse_args()

    if args.benchmark:
        return run_benchmark()
    if not args.images:
        parser.print_help()
        return 1
    return run_validation(args.images, args.labels, args.out, args.max_frames)


if __name__ == "__main__":
    raise SystemExit(main())
