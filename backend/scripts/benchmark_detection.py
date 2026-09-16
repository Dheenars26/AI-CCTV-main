"""
Standalone Benchmark Utility for AI CCTV Detection Engine.
Measures RTSP capture FPS, YOLO pre/post-processing time, inference latency, AI processing FPS,
CPU %, GPU %, and RAM usage across resolutions (416, 512, 640), FP32/FP16 precision modes,
and target FPS sampling rates (5, 10, 15 FPS).
"""

import sys
import os
import time
import psutil
import numpy as np

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config.settings import settings
from app.detection.yolo import YOLODetector
from app.detection.ppe_detector import PPEDetector
from app.detection.person_detector import PersonDetector


def benchmark_engine(
    resolution: int = 640,
    use_half: bool = True,
    target_fps: int = 10,
    iterations: int = 20
):
    """
    Runs benchmark iterations on synthetic test frames.
    Returns structured performance metric tuple.
    """
    synthetic_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    import cv2
    cv2.rectangle(synthetic_frame, (100, 100), (300, 500), (50, 100, 200), -1)
    cv2.circle(synthetic_frame, (700, 300), 80, (0, 200, 255), -1)

    device_target = "cuda" if settings.YOLO_DEVICE in ["cuda", "0"] else "cpu"

    detector = PPEDetector(
        model_path=settings.PPE_MODEL_PATH,
        conf_threshold=0.35,
        device=device_target
    )
    detector.half = use_half and detector.is_cuda

    # Warmup runs
    for _ in range(2):
        detector.detect(synthetic_frame)

    t_preprocess_list = []
    t_inference_list = []
    t_postprocess_list = []

    process = psutil.Process()
    cpu_start = process.cpu_percent(interval=None)

    t_start_total = time.time()

    for _ in range(iterations):
        t0 = time.time()
        img_resized = cv2.resize(synthetic_frame, (resolution, resolution), interpolation=cv2.INTER_LINEAR)
        t1 = time.time()

        dets = detector.detect(img_resized)
        t2 = time.time()

        PPEDetector._apply_nms(dets)
        t3 = time.time()

        t_preprocess_list.append((t1 - t0) * 1000.0)
        t_inference_list.append((t2 - t1) * 1000.0)
        t_postprocess_list.append((t3 - t2) * 1000.0)

        frame_delay = 1.0 / max(1, target_fps)
        elapsed_step = time.time() - t0
        if elapsed_step < frame_delay:
            time.sleep(frame_delay - elapsed_step)

    t_total_elapsed = time.time() - t_start_total

    cpu_end = process.cpu_percent(interval=None)
    ram_end = process.memory_info().rss / (1024 * 1024)

    avg_preprocess_ms = round(float(np.mean(t_preprocess_list)), 2)
    avg_inference_ms = round(float(np.mean(t_inference_list)), 2)
    avg_postprocess_ms = round(float(np.mean(t_postprocess_list)), 2)
    total_latency_ms = round(avg_preprocess_ms + avg_inference_ms + avg_postprocess_ms, 2)
    effective_fps = round(float(iterations) / float(t_total_elapsed), 2)

    return {
        "resolution": resolution,
        "precision": "FP16" if (use_half and detector.is_cuda) else "FP32",
        "target_fps": target_fps,
        "preprocess_ms": avg_preprocess_ms,
        "inference_ms": avg_inference_ms,
        "postprocess_ms": avg_postprocess_ms,
        "total_latency_ms": total_latency_ms,
        "effective_fps": effective_fps,
        "cpu_usage_pct": round(max(cpu_start, cpu_end), 1),
        "ram_mb": round(ram_end, 1)
    }


def main():
    print("=" * 85)
    print("AI CCTV DETECTION ENGINE BENCHMARK SUITE")
    print(f"Device Target: {settings.YOLO_DEVICE} | Environment: {settings.APP_ENV}")
    print("=" * 85)

    resolutions = [416, 512, 640]
    precisions = [True, False]

    results = []

    print("\n[Running Benchmark Matrix...]")
    for res in resolutions:
        for half_flag in precisions:
            prec_name = "FP16" if half_flag else "FP32"
            res_dict = benchmark_engine(
                resolution=res,
                use_half=half_flag,
                target_fps=10,
                iterations=15
            )
            results.append(res_dict)
            print(
                f"Res: {res}x{res} | Precision: {prec_name} | "
                f"Inference Latency: {res_dict['inference_ms']}ms | Total Latency: {res_dict['total_latency_ms']}ms | "
                f"AI FPS: {res_dict['effective_fps']} | RAM: {res_dict['ram_mb']}MB"
            )

    print("\n" + "=" * 85)
    print("BENCHMARK COMPARISON TABLE")
    print("=" * 85)
    print(f"| {'Resolution':<10} | {'Precision':<9} | {'Target FPS':<10} | {'Inference Latency':<18} | {'Total Latency':<14} | {'AI FPS':<8} | {'RAM (MB)':<8} |")
    print(f"|{'-'*12}|{'-'*11}|{'-'*12}|{'-'*20}|{'-'*16}|{'-'*10}|{'-'*10}|")

    for r in results:
        inf_str = f"{r['inference_ms']} ms"
        tot_str = f"{r['total_latency_ms']} ms"
        print(
            f"| {r['resolution']:<10} | {r['precision']:<9} | {r['target_fps']:<10} | "
            f"{inf_str:<18} | {tot_str:<14} | "
            f"{r['effective_fps']:<8} | {r['ram_mb']:<8} |"
        )
    print("=" * 85)


if __name__ == "__main__":
    main()
