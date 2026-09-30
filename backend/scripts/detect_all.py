#!/usr/bin/env python3
"""
Unified Multi-Target Detection & Verification CLI Tool (Fire, Smoke, Safety Vest, Glasses).

Production-grade pipeline runner supporting:
- Single image files (.jpg, .png, .webp, .bmp)
- Image directories
- Recorded video files (.mp4, .avi, .mkv, .mov)
- Live RTSP / HTTP network surveillance streams
- USB Webcams (device index 0, 1, ...)

Features:
- Simultaneous 4-target AI detection: Fire, Smoke, Safety Vest, and Glasses / Goggles (+ Person tracking)
- Strict false-positive vetoing (thermodynamics, hi-vis retroreflective edge verification, ocular lens reflection)
- Real-time CCTV HUD overlays with rounded pill badges and corner-bracket tracking
- Automated PPE compliance evaluation (PASS / VIOLATION)
- Live interactive visualization window (--view)
- Output video / image export (--out)
- Structured JSON telemetry reports (--save-json)

Usage Examples:
---------------
1. Analyze a single image and save the annotated preview:
   python backend/scripts/detect_all.py --source worker_sample.jpg --out results/

2. Analyze all images in a folder:
   python backend/scripts/detect_all.py --source ./samples/ --out ./annotated/

3. Test live webcam with interactive HUD display:
   python backend/scripts/detect_all.py --source 0 --view

4. Process a video file and export annotated video + JSON telemetry:
   python backend/scripts/detect_all.py --source factory_floor.mp4 --out output.mp4 --save-json audit.json
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

# Ensure backend root is on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.dirname(SCRIPT_DIR)
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.camera.pipeline import FramePipeline, Frame
from app.config.settings import settings
from app.detection.roi_refine import normalise_ppe_label

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
VIDEO_EXTENSIONS = (".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Unified Multi-Target CCTV AI Detector: Fire, Smoke, Safety Vest, Glasses",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--source",
        "-s",
        type=str,
        default="0",
        help="Input source: image path, directory of images, video file, RTSP stream URL, or webcam index (default: 0)",
    )
    parser.add_argument(
        "--out",
        "-o",
        type=str,
        default=None,
        help="Output destination: directory for annotated images, or video path (.mp4) for video output",
    )
    parser.add_argument(
        "--view",
        action="store_true",
        help="Display live interactive visualization window with CCTV HUD overlays",
    )
    parser.add_argument(
        "--required-ppe",
        type=str,
        default="vest,glasses",
        help="Comma-separated required PPE classes to monitor (default: 'vest,glasses')",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=None,
        help="Optional minimum confidence threshold floor override",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Maximum number of frames to process before stopping",
    )
    parser.add_argument(
        "--save-json",
        type=str,
        default=None,
        help="Path to export structured session detection telemetry as JSON",
    )
    parser.add_argument(
        "--motion-gate",
        action="store_true",
        help="Enable foreground motion gating (recommended for continuous streaming video)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-frame console logging",
    )
    return parser.parse_args()


def is_webcam(source_str: str) -> bool:
    return source_str.isdigit() or (source_str.startswith("webcam") and source_str[6:].isdigit())


def print_banner(source: str, required_ppe: List[str], output: Optional[str]) -> None:
    print("=" * 76)
    print("  AI-CCTV MULTI-TARGET AI DETECTOR & VERIFICATION ENGINE")
    print("  Targets: Fire | Smoke | Safety Vest | Safety Glasses / Goggles")
    print("=" * 76)
    print(f"  Source Input     : {source}")
    print(f"  Required PPE     : {', '.join(required_ppe).upper()}")
    print(f"  Output Path      : {output or 'None (Display / Console only)'}")
    print(f"  Engine Device    : {getattr(settings, 'YOLO_DEVICE', 'cpu').upper()}")
    print("=" * 76)


if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass


def format_detection_pill(label: str, conf: float) -> str:
    norm = normalise_ppe_label(label) or label.lower()
    if norm == "fire":
        return f"[FIRE {int(conf * 100)}%]"
    elif norm == "smoke":
        return f"[SMOKE {int(conf * 100)}%]"
    elif norm == "vest":
        return f"[VEST {int(conf * 100)}%]"
    elif norm in ["goggles", "glasses"]:
        return f"[GLASSES {int(conf * 100)}%]"
    elif norm == "person":
        return f"[WORKER {int(conf * 100)}%]"
    return f"[{norm.upper()} {int(conf * 100)}%]"



def process_images_batch(
    image_paths: List[str],
    pipeline: FramePipeline,
    out_dir: Optional[str],
    view: bool,
    quiet: bool,
) -> Dict[str, Any]:
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    session_stats = {
        "frames_processed": 0,
        "total_latency_ms": 0.0,
        "fire_detections": 0,
        "smoke_detections": 0,
        "vest_detections": 0,
        "glasses_detections": 0,
        "total_workers": 0,
        "compliant_workers": 0,
        "violations_count": 0,
        "frames": [],
    }

    if not quiet:
        print(f"\nProcessing {len(image_paths)} image(s)...")
        print(f"{'IMAGE':<32} {'LATENCY':<10} {'WORKERS':<9} {'COMPLIANCE':<12} {'TARGET DETECTIONS'}")
        print("-" * 76)

    for idx, img_path in enumerate(image_paths):
        img = cv2.imread(img_path)
        if img is None:
            if not quiet:
                print(f"{os.path.basename(img_path):<32} FAILED TO READ")
            continue

        filename = os.path.basename(img_path)
        pipeline.reset()

        t0 = time.perf_counter()
        frame = pipeline.process_frame(img, frame_id=idx + 1, fps=30.0)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        session_stats["frames_processed"] += 1
        session_stats["total_latency_ms"] += latency_ms

        # Extract counts
        worker_analyses = frame.metadata.get("worker_ppe_analyses", [])
        worker_count = len(worker_analyses)
        frame_compliant = sum(1 for w in worker_analyses if w.get("status") == "PASS")
        frame_violations = sum(1 for w in worker_analyses if w.get("status") == "VIOLATION")

        session_stats["total_workers"] += worker_count
        session_stats["compliant_workers"] += frame_compliant
        session_stats["violations_count"] += frame_violations

        fire_in_frame = 0
        smoke_in_frame = 0
        vest_in_frame = 0
        glasses_in_frame = 0

        pills = []
        for det in frame.detections:
            canon = normalise_ppe_label(det.label) or det.label.lower()
            if canon == "fire":
                fire_in_frame += 1
                session_stats["fire_detections"] += 1
            elif canon == "smoke":
                smoke_in_frame += 1
                session_stats["smoke_detections"] += 1
            elif canon == "vest":
                vest_in_frame += 1
                session_stats["vest_detections"] += 1
            elif canon in ["goggles", "glasses"]:
                glasses_in_frame += 1
                session_stats["glasses_detections"] += 1

            pills.append(format_detection_pill(det.label, det.confidence))

        comp_str = f"{frame_compliant}/{worker_count} PASS" if worker_count > 0 else "N/A"
        det_str = " ".join(pills) if pills else "None"

        if not quiet:
            print(f"{filename:<32} {latency_ms:6.1f}ms   {worker_count:<9} {comp_str:<12} {det_str}")

        frame_record = {
            "image": filename,
            "latency_ms": round(latency_ms, 2),
            "workers_count": worker_count,
            "compliant_workers": frame_compliant,
            "violations_count": frame_violations,
            "fire_count": fire_in_frame,
            "smoke_count": smoke_in_frame,
            "vest_count": vest_in_frame,
            "glasses_count": glasses_in_frame,
            "detections": [
                {
                    "label": d.label,
                    "confidence": round(float(d.confidence), 4),
                    "bbox": d.bbox.to_dict(),
                }
                for d in frame.detections
            ],
            "worker_analyses": worker_analyses,
        }
        session_stats["frames"].append(frame_record)

        if out_dir and frame.image is not None:
            save_path = os.path.join(out_dir, f"annotated_{filename}")
            cv2.imwrite(save_path, frame.image)

        if view and frame.image is not None:
            cv2.imshow("AI-CCTV Multi-Target Detector", frame.image)
            key = cv2.waitKey(0) & 0xFF
            if key in [ord("q"), 27]:  # 'q' or ESC
                break

    if view:
        cv2.destroyAllWindows()

    return session_stats


def process_video_stream(
    cap: cv2.VideoCapture,
    pipeline: FramePipeline,
    out_video_path: Optional[str],
    view: bool,
    max_frames: Optional[int],
    quiet: bool,
) -> Dict[str, Any]:
    writer = None
    if out_video_path:
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")  # type: ignore[attr-defined]
        writer = cv2.VideoWriter(out_video_path, fourcc, fps, (w, h))

    session_stats = {
        "frames_processed": 0,
        "total_latency_ms": 0.0,
        "fire_detections": 0,
        "smoke_detections": 0,
        "vest_detections": 0,
        "glasses_detections": 0,
        "total_workers": 0,
        "compliant_workers": 0,
        "violations_count": 0,
        "frames": [],
    }

    if not quiet:
        print("\nStreaming pipeline started. Press 'q' or Ctrl+C to terminate.")
        print(f"{'FRAME':<8} {'FPS':<8} {'LATENCY':<10} {'WORKERS':<9} {'COMPLIANCE':<12} {'ALERTS / TARGETS'}")
        print("-" * 76)

    frame_id = 0
    fps_ema = 30.0

    try:
        while cap.isOpened():
            ret, img = cap.read()
            if not ret or img is None:
                break

            frame_id += 1
            if max_frames and frame_id > max_frames:
                break

            t0 = time.perf_counter()
            frame = pipeline.process_frame(img, frame_id=frame_id, fps=fps_ema)
            latency_ms = (time.perf_counter() - t0) * 1000.0

            inst_fps = 1000.0 / max(latency_ms, 1.0)
            fps_ema = 0.2 * inst_fps + 0.8 * fps_ema

            session_stats["frames_processed"] += 1
            session_stats["total_latency_ms"] += latency_ms

            worker_analyses = frame.metadata.get("worker_ppe_analyses", [])
            worker_count = len(worker_analyses)
            frame_compliant = sum(1 for w in worker_analyses if w.get("status") == "PASS")
            frame_violations = sum(1 for w in worker_analyses if w.get("status") == "VIOLATION")

            session_stats["total_workers"] += worker_count
            session_stats["compliant_workers"] += frame_compliant
            session_stats["violations_count"] += frame_violations

            pills = []
            for det in frame.detections:
                canon = normalise_ppe_label(det.label) or det.label.lower()
                if canon == "fire":
                    session_stats["fire_detections"] += 1
                elif canon == "smoke":
                    session_stats["smoke_detections"] += 1
                elif canon == "vest":
                    session_stats["vest_detections"] += 1
                elif canon in ["goggles", "glasses"]:
                    session_stats["glasses_detections"] += 1
                pills.append(format_detection_pill(det.label, det.confidence))

            comp_str = f"{frame_compliant}/{worker_count} PASS" if worker_count > 0 else "N/A"
            det_str = " ".join(pills[:4]) if pills else "All Clear"

            if not quiet and (frame_id % 5 == 0 or len(pills) > 0):
                print(f"#{frame_id:<7} {fps_ema:5.1f}   {latency_ms:6.1f}ms   {worker_count:<9} {comp_str:<12} {det_str}")

            if writer and frame.image is not None:
                writer.write(frame.image)

            if view and frame.image is not None:
                cv2.imshow("AI-CCTV Multi-Target Live Feed (Press 'q' to stop)", frame.image)
                key = cv2.waitKey(1) & 0xFF
                if key in [ord("q"), 27]:
                    break

    except KeyboardInterrupt:
        print("\nStreaming interrupted by user.")
    finally:
        cap.release()
        if writer:
            writer.release()
        if view:
            cv2.destroyAllWindows()

    return session_stats


def print_summary(stats: Dict[str, Any], output_path: Optional[str]) -> None:
    frames = stats.get("frames_processed", 0)
    total_ms = stats.get("total_latency_ms", 0.0)
    avg_latency = (total_ms / max(frames, 1)) if frames > 0 else 0.0
    avg_fps = (1000.0 / avg_latency) if avg_latency > 0 else 0.0

    workers = stats.get("total_workers", 0)
    compliant = stats.get("compliant_workers", 0)
    violations = stats.get("violations_count", 0)
    comp_rate = (compliant / workers * 100.0) if workers > 0 else 100.0

    print("\n" + "=" * 76)
    print("  DETECTION & VERIFICATION PERFORMANCE SUMMARY")
    print("=" * 76)
    print(f"  Frames Processed : {frames}")
    print(f"  Average Latency  : {avg_latency:.1f} ms  ({avg_fps:.1f} FPS)")
    print("  ------------------------------------------------------------------------")
    print(f"  [FIRE]    Fire Detections     : {stats.get('fire_detections', 0)}")
    print(f"  [SMOKE]   Smoke Detections    : {stats.get('smoke_detections', 0)}")
    print(f"  [VEST]    Safety Vests Found  : {stats.get('vest_detections', 0)}")
    print(f"  [GLASSES] Glasses Found       : {stats.get('glasses_detections', 0)}")
    print("  ------------------------------------------------------------------------")
    print(f"  [WORKER]  Tracked Workers     : {workers}")
    print(f"  [PASS]    Compliant Workers   : {compliant}")
    print(f"  [ALERT]   PPE Violations      : {violations}")
    print(f"  [METRIC]  PPE Compliance Rate : {comp_rate:.1f}%")
    if output_path:
        print(f"  [SAVED]   Export Destination  : {output_path}")
    print("=" * 76 + "\n")


def main() -> int:
    args = parse_arguments()
    req_ppe = [r.strip().lower() for r in args.required_ppe.split(",") if r.strip()]

    print_banner(args.source, req_ppe, args.out)

    # Initialize FramePipeline
    pipeline = FramePipeline(camera_id=1)
    pipeline.set_ppe_profile({"required_equipment": req_ppe})

    # If single image or image directory, disable motion gating to inspect all images fully
    source_str = args.source
    is_image_source = (
        os.path.isfile(source_str) and source_str.lower().endswith(IMAGE_EXTENSIONS)
    ) or (os.path.isdir(source_str))

    if is_image_source or not args.motion_gate:
        pipeline.motion_gate.enabled = False
        pipeline.ppe_inference_interval_sec = 0.0
    else:
        pipeline.motion_gate.enabled = True

    # 1. Image Directory or Single Image Mode
    if is_image_source:
        if os.path.isdir(source_str):
            image_paths = sorted(
                os.path.join(source_str, f)
                for f in os.listdir(source_str)
                if f.lower().endswith(IMAGE_EXTENSIONS)
            )
            if args.max_frames:
                image_paths = image_paths[: args.max_frames]
        else:
            image_paths = [source_str]

        if not image_paths:
            print(f"Error: No valid images found in {source_str}")
            return 1

        stats = process_images_batch(
            image_paths=image_paths,
            pipeline=pipeline,
            out_dir=args.out,
            view=args.view,
            quiet=args.quiet,
        )

    # 2. Video / RTSP / Webcam Mode
    else:
        cam_src: Any = int(source_str) if is_webcam(source_str) else source_str
        cap = cv2.VideoCapture(cam_src)
        if not cap.isOpened():
            print(f"Error: Failed to open video stream/device '{source_str}'")
            return 1

        stats = process_video_stream(
            cap=cap,
            pipeline=pipeline,
            out_video_path=args.out if (args.out and args.out.lower().endswith(VIDEO_EXTENSIONS)) else None,
            view=args.view,
            max_frames=args.max_frames,
            quiet=args.quiet,
        )

    print_summary(stats, args.out)

    if args.save_json:
        # Purge numpy objects before serialization
        clean_stats = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": source_str,
            "frames_processed": stats["frames_processed"],
            "total_latency_ms": round(stats["total_latency_ms"], 2),
            "fire_detections": stats["fire_detections"],
            "smoke_detections": stats["smoke_detections"],
            "vest_detections": stats["vest_detections"],
            "glasses_detections": stats["glasses_detections"],
            "total_workers": stats["total_workers"],
            "compliant_workers": stats["compliant_workers"],
            "violations_count": stats["violations_count"],
            "frames": stats.get("frames", []),
        }
        with open(args.save_json, "w", encoding="utf-8") as f:
            json.dump(clean_stats, f, indent=2)
        print(f"Telemetry JSON report saved to: {args.save_json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
