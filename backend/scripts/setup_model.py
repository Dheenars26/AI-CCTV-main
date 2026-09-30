"""
AI Model Setup & Dependency Inspection Script for AI CCTV Fire & Smoke Platform.
Verifies ONNX Runtime, PyTorch, Ultralytics YOLOv8, and OpenCV computer vision engine readiness.
"""

import sys
import os

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config.settings import settings
from app.utils.logger import logger


def inspect_ai_environment():
    """
    Checks hardware acceleration targets, libraries, and AI model weight files.
    """
    logger.info("=" * 60)
    logger.info("AI CCTV: Model Engine & Computer Vision Environment Diagnostic")
    logger.info("=" * 60)

    # 1. Inspect OpenCV
    try:
        import cv2
        logger.info(f"[SUCCESS] OpenCV installed: Version {cv2.__version__}")
    except ImportError:
        logger.error("[ERROR] OpenCV (cv2) is NOT installed. Required for video stream ingestion.")

    # 2. Inspect ONNX Runtime
    try:
        import onnxruntime as ort
        providers = ort.get_available_providers()
        logger.info(f"[SUCCESS] ONNX Runtime installed: Version {ort.__version__} | Execution Providers: {providers}")
    except ImportError:
        logger.warning("[WARNING] 'onnxruntime' is not installed. Install for high-performance ONNX inference.")

    # 3. Inspect PyTorch & CUDA
    try:
        import torch
        cuda_available = torch.cuda.is_available()
        device_name = torch.cuda.get_device_name(0) if cuda_available else "N/A (CPU Mode)"
        logger.info(f"[SUCCESS] PyTorch installed: Version {torch.__version__} | CUDA Available: {cuda_available} ({device_name})")
    except ImportError:
        logger.warning("[WARNING] 'torch' (PyTorch) is not installed.")

    # 4. Inspect Ultralytics YOLO
    try:
        import ultralytics
        logger.info(f"[SUCCESS] Ultralytics YOLO installed: Version {ultralytics.__version__}")
    except ImportError:
        logger.warning("[WARNING] 'ultralytics' library is not installed. (System falls back to OpenCV HSV Fire/Smoke Engine).")

    # 5. Check Model Weight Files
    backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    models_to_check = [
        ("Fire & Smoke Model", settings.YOLO_MODEL_PATH),
        ("PPE Detection Model", settings.PPE_MODEL_PATH),
        ("Person Detection Model", settings.PERSON_MODEL_PATH),
    ]

    for label, rel_path in models_to_check:
        candidates = [
            rel_path,
            os.path.join(backend_root, rel_path),
            os.path.join(backend_root, "models", os.path.basename(rel_path)),
            os.path.join("backend", rel_path)
        ]
        found_path = None
        for cand in candidates:
            if cand and os.path.exists(cand):
                found_path = os.path.abspath(cand)
                break

        if found_path:
            size_mb = round(os.path.getsize(found_path) / (1024 * 1024), 2)
            logger.info(f"[SUCCESS] {label} exists: '{found_path}' ({size_mb} MB)")
        else:
            expected_abs = os.path.join(backend_root, rel_path)
            logger.warning(f"[NOTICE] {label} '{rel_path}' not found at '{expected_abs}'.")

    logger.info("=" * 60)
    logger.info("AI Model Setup Diagnostic Completed.")
    logger.info("=" * 60)


if __name__ == "__main__":
    inspect_ai_environment()
