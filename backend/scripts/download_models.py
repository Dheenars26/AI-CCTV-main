"""
AI CCTV Model Management & Model Downloader Utility.
Inspects local model files, downloads official Ultralytics YOLO models or specialized weights,
and reports performance/class configuration.
"""

import os
import sys
import argparse
import hashlib
from typing import Dict, Any

# Ensure backend root is in PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config.settings import settings
from app.utils.logger import logger


def get_file_md5(filepath: str, max_bytes: int = 8192) -> str:
    if not os.path.exists(filepath):
        return "missing"
    try:
        with open(filepath, "rb") as f:
            return hashlib.md5(f.read(max_bytes)).hexdigest()
    except Exception as e:
        return f"error: {str(e)}"


def inspect_models() -> Dict[str, Any]:
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    models_dir = os.path.join(backend_dir, "models")
    os.makedirs(models_dir, exist_ok=True)

    fire_smoke_path = os.path.join(backend_dir, settings.YOLO_MODEL_PATH)
    ppe_path = os.path.join(backend_dir, settings.PPE_MODEL_PATH)
    yolov8n_path = os.path.join(backend_dir, "yolov8n.pt")

    status = {
        "fire_smoke_model": {
            "path": fire_smoke_path,
            "exists": os.path.exists(fire_smoke_path),
            "size_bytes": os.path.getsize(fire_smoke_path) if os.path.exists(fire_smoke_path) else 0,
            "hash": get_file_md5(fire_smoke_path)
        },
        "ppe_model": {
            "path": ppe_path,
            "exists": os.path.exists(ppe_path),
            "size_bytes": os.path.getsize(ppe_path) if os.path.exists(ppe_path) else 0,
            "hash": get_file_md5(ppe_path)
        },
        "base_yolo_model": {
            "path": yolov8n_path,
            "exists": os.path.exists(yolov8n_path),
            "size_bytes": os.path.getsize(yolov8n_path) if os.path.exists(yolov8n_path) else 0,
            "hash": get_file_md5(yolov8n_path)
        }
    }
    return status


def download_base_yolo(variant: str = "s") -> bool:
    """
    Downloads base YOLO weights (yolov8n.pt, yolov8s.pt, yolov8m.pt, yolov8l.pt, yolov8x.pt)
    via Ultralytics package.
    """
    model_name = f"yolov8{variant.lower()}.pt"
    print(f"[*] Downloading Ultralytics YOLO model: {model_name}...")
    try:
        from ultralytics import YOLO
        model = YOLO(model_name)
        print(f"[+] Successfully loaded/downloaded {model_name}.")
        return True
    except Exception as e:
        print(f"[-] Download failed for {model_name}: {str(e)}")
        return False


def main():
    parser = argparse.ArgumentParser(description="AI CCTV Model Management & Optimization Tool")
    parser.add_argument("--inspect", action="store_true", help="Inspect local AI model status")
    parser.add_argument("--variant", type=str, default="s", choices=["n", "s", "m", "l", "x"], help="YOLO model variant (n=nano, s=small, m=medium, l=large, x=extra-large)")
    parser.add_argument("--download", action="store_true", help="Download base YOLO model weights")
    args = parser.parse_args()

    status = inspect_models()
    print("=" * 60)
    print("       AI CCTV MONITORING MODEL SYSTEM STATUS")
    print("=" * 60)
    for k, v in status.items():
        print(f"[{k.upper()}]")
        print(f"  Path      : {v['path']}")
        print(f"  Exists    : {v['exists']}")
        print(f"  Size (MB) : {round(v['size_bytes'] / (1024 * 1024), 2)} MB")
        print(f"  MD5 Hash  : {v['hash']}")
        print("-" * 60)

    if args.download:
        download_base_yolo(args.variant)


if __name__ == "__main__":
    main()
