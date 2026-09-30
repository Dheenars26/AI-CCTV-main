#!/usr/bin/env python3
"""
AI CCTV Custom Model Training, Fine-Tuning & Deployment Pipeline.
Supports training and upgrading models for:
  - PPE Detection ('helmet', 'vest', 'goggles', 'gloves', 'mask', 'safety_shoe')
  - Fire & Smoke Detection ('fire', 'smoke')
  - Person / Worker Detection ('person')

Usage Examples:
---------------
1. Scaffold a new training dataset template:
   python scripts/train.py --task ppe --init-dataset

2. Train upgraded YOLOv8s (Small) on your dataset and auto-deploy to ONNX:
   python scripts/train.py --task ppe --model yolov8s.pt --data datasets/ppe/dataset.yaml --epochs 50 --deploy

3. Fine-tune Fire & Smoke detection using GPU (or CPU):
   python scripts/train.py --task fire_smoke --model yolov8s.pt --data datasets/fire_smoke/dataset.yaml --epochs 60 --deploy

4. Export an existing PyTorch checkpoint directly to ONNX:
   python scripts/train.py --export-only --checkpoint runs/detect/train/weights/best.pt --task ppe --deploy
"""

import os
import sys
import argparse
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

# Ensure backend root is in PYTHONPATH
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.config.settings import settings
from app.utils.logger import logger


TASK_SPECS = {
    "ppe": {
        "name": "Personal Protective Equipment (PPE)",
        "classes": [
            "helmet", "gloves", "vest", "boots", "goggles", "none",
            "Person", "no_helmet", "no_goggle", "no_gloves", "no_boots"
        ],
        "default_target_onnx": "models/ppe.onnx",
        "default_target_pt": "models/ppe.pt",
        "default_base_model": "yolov8s.pt",
        "recommended_imgsz": 640,
    },
    "fire_smoke": {
        "name": "Fire & Smoke",
        "classes": ["fire", "smoke"],
        "default_target_onnx": "models/fire_smoke.onnx",
        "default_target_pt": "models/fire_smoke.pt",
        "default_base_model": "yolov8s.pt",
        "recommended_imgsz": 640,
    },
    "person": {
        "name": "Person / Worker",
        "classes": ["person"],
        "default_target_onnx": "models/yolov8s.onnx",
        "default_target_pt": "models/yolov8s.pt",
        "default_base_model": "yolov8s.pt",
        "recommended_imgsz": 640,
    },
}

DATASET_DOWNLOAD_SOURCES = {
    "ppe": {
        "url": "https://github.com/ultralytics/assets/releases/download/v0.0.0/construction-ppe.zip",
        "description": "Ultralytics Construction PPE Dataset (1,416 annotated images, 11 classes: helmet, vest, boots, goggles, gloves, etc.)",
        "filename": "construction-ppe.zip",
    }
}


def download_dataset(task: str, custom_url: Optional[str] = None, output_dir: Optional[str] = None) -> str:
    """
    Downloads and extracts an official/public annotated training dataset.
    """
    spec = TASK_SPECS.get(task, TASK_SPECS["ppe"])
    base_dir = output_dir or os.path.join(BACKEND_ROOT, "datasets", task)
    os.makedirs(base_dir, exist_ok=True)

    source = DATASET_DOWNLOAD_SOURCES.get(task, {})
    url = custom_url or source.get("url")
    if not url:
        print(f"[-] No default download URL configured for task '{task}'. Please specify --url <zip_url>.")
        return ""

    zip_name = source.get("filename", f"{task}_dataset.zip")
    zip_dest = os.path.join(base_dir, zip_name)

    print("=" * 60)
    print(f"[*] Downloading {spec['name']} dataset...")
    print(f"    URL: {url}")
    print(f"    Target: {zip_dest}")
    print("=" * 60)

    import urllib.request
    import zipfile

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req) as resp, open(zip_dest, "wb") as out_file:
        total_size = int(resp.headers.get("content-length", 0))
        block_size = 1024 * 1024  # 1MB
        downloaded = 0
        while True:
            chunk = resp.read(block_size)
            if not chunk:
                break
            out_file.write(chunk)
            downloaded += len(chunk)
            if total_size > 0:
                pct = int(downloaded * 100 / total_size)
                mb_down = downloaded / (1024 * 1024)
                mb_tot = total_size / (1024 * 1024)
                sys.stdout.write(f"\r    Downloading: {pct}% [{mb_down:.1f}/{mb_tot:.1f} MB]")
            else:
                mb_down = downloaded / (1024 * 1024)
                sys.stdout.write(f"\r    Downloading: {mb_down:.1f} MB")
            sys.stdout.flush()
    print("\n[+] Download complete!")

    print(f"[*] Extracting archive to '{base_dir}'...")
    with zipfile.ZipFile(zip_dest, "r") as zf:
        zf.extractall(base_dir)
    print("[+] Extraction finished.")

    # Locate dataset.yaml or scaffold one
    yaml_candidates = list(Path(base_dir).rglob("*.yaml")) + list(Path(base_dir).rglob("*.yml"))
    if yaml_candidates:
        primary_yaml = str(yaml_candidates[0])
        print(f"[+] Found dataset configuration: {primary_yaml}")
        return primary_yaml

    return scaffold_dataset_template(task, output_dir=base_dir)


def scaffold_dataset_template(task: str, output_dir: Optional[str] = None) -> str:
    """
    Creates an empty YOLO dataset directory layout with a configured dataset.yaml file.
    """
    spec = TASK_SPECS.get(task, TASK_SPECS["ppe"])
    base_dir = output_dir or os.path.join(BACKEND_ROOT, "datasets", task)
    base_dir = os.path.abspath(base_dir)

    train_img_dir = os.path.join(base_dir, "images", "train")
    val_img_dir = os.path.join(base_dir, "images", "val")
    train_lbl_dir = os.path.join(base_dir, "labels", "train")
    val_lbl_dir = os.path.join(base_dir, "labels", "val")

    os.makedirs(train_img_dir, exist_ok=True)
    os.makedirs(val_img_dir, exist_ok=True)
    os.makedirs(train_lbl_dir, exist_ok=True)
    os.makedirs(val_lbl_dir, exist_ok=True)

    yaml_path = os.path.join(base_dir, "dataset.yaml")
    classes_list = spec["classes"]
    names_dict = {i: c for i, c in enumerate(classes_list)}

    yaml_content = f"""# AI CCTV {spec['name']} Detection Dataset Configuration
# Auto-generated by backend/scripts/train.py

path: {base_dir.replace('\\\\', '/')}
train: images/train
val: images/val

# Class definitions (matches detector pipeline vocabulary)
names:
"""
    for idx, cname in names_dict.items():
        yaml_content += f"  {idx}: {cname}\n"

    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(yaml_content)

    readme_path = os.path.join(base_dir, "README.md")
    readme_content = f"""# {spec['name']} Dataset Guide

### Directory Structure:
- `images/train/`: Training images (`.jpg`, `.png`, `.webp`)
- `images/val/`: Validation images for accuracy metrics
- `labels/train/`: YOLO-format label text files (`.txt`), one per image with matching basename
- `labels/val/`: Validation label text files (`.txt`)

### Annotation Format (Normalized 0.0 - 1.0):
`<class_id> <x_center> <y_center> <width> <height>`

### Class ID Map:
"""
    for idx, cname in names_dict.items():
        readme_content += f"- **{idx}**: `{cname}`\n"

    readme_content += f"""
### Training Command:
```bash
python scripts/train.py --task {task} --data "{yaml_path}" --model {spec['default_base_model']} --epochs 50 --deploy
```
"""
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme_content)

    print("=" * 60)
    print(f"[*] Scaffolded dataset template for '{task}' at:")
    print(f"    {base_dir}")
    print(f"    Configuration: {yaml_path}")
    print("=" * 60)
    return yaml_path


def check_dataset_stats(yaml_path: str) -> bool:
    """Checks whether images and annotations exist in the configured dataset."""
    import yaml  # type: ignore[import-untyped]
    if not os.path.isfile(yaml_path):
        print(f"[-] Dataset config not found: {yaml_path}")
        return False

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    root = data.get("path", os.path.dirname(yaml_path))
    train_rel = data.get("train", "images/train")
    val_rel = data.get("val", "images/val")

    train_path = os.path.join(root, train_rel) if not os.path.isabs(train_rel) else train_rel
    val_path = os.path.join(root, val_rel) if not os.path.isabs(val_rel) else val_rel

    train_count = len([f for f in os.listdir(train_path) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.webp'))]) if os.path.isdir(train_path) else 0
    val_count = len([f for f in os.listdir(val_path) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.webp'))]) if os.path.isdir(val_path) else 0

    print(f"[*] Dataset '{yaml_path}':")
    print(f"    Train images: {train_count}")
    print(f"    Val images  : {val_count}")

    if train_count == 0:
        print(f"[-] Warning: No training images found in '{train_path}'.")
        print(f"    Please place annotated images and labels in the dataset folders before training:")
        print(f"      - Images: {train_path}")
        labels_path = train_path.replace("images", "labels")
        print(f"      - Labels: {labels_path}")
        print(f"\n    Available Options:")
        print(f"    1. Download a ready-to-use YOLO dataset (e.g. Roboflow Universe 'fire and smoke', DFireDataset, Kaggle).")
        print(f"    2. If you already have a pre-trained PyTorch checkpoint (e.g. models/{os.path.basename(os.path.dirname(yaml_path))}.pt):")
        print(f"       Run with --export-only to deploy it immediately to ONNX at 640x640:")
        task_name = os.path.basename(os.path.dirname(yaml_path))
        print(f"       python scripts/train.py --export-only --checkpoint models/{task_name}.pt --task {task_name} --imgsz 640 --deploy")
        return False
    return True


def export_model_to_onnx(
    pt_path: str,
    imgsz: int = 640,
    opset: int = 17,
    simplify: bool = True
) -> str:
    """Exports trained YOLO PyTorch weights to optimized ONNX format."""
    from ultralytics import YOLO
    print(f"[*] Exporting '{pt_path}' to ONNX format (imgsz={imgsz}, opset={opset})...")
    model = YOLO(pt_path)
    exported_path = model.export(
        format="onnx",
        imgsz=imgsz,
        dynamic=False,
        opset=opset,
        simplify=simplify
    )
    print(f"[+] Successfully exported to ONNX: {exported_path}")
    return exported_path


def deploy_trained_model(
    exported_onnx_path: str,
    best_pt_path: Optional[str],
    task: str
) -> bool:
    """
    Backs up the current active model in backend/models and copies the new trained weights into place.
    """
    spec = TASK_SPECS.get(task, TASK_SPECS["ppe"])
    target_onnx_rel = spec["default_target_onnx"]
    target_pt_rel = spec["default_target_pt"]

    models_dir = os.path.join(BACKEND_ROOT, "models")
    os.makedirs(models_dir, exist_ok=True)

    dest_onnx = os.path.join(BACKEND_ROOT, target_onnx_rel)
    dest_pt = os.path.join(BACKEND_ROOT, target_pt_rel)

    # 1. Backup existing ONNX if present and different from exported path
    if os.path.exists(dest_onnx) and os.path.abspath(exported_onnx_path) != os.path.abspath(dest_onnx):
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        stem, ext = os.path.splitext(dest_onnx)
        backup_path = f"{stem}_backup_{timestamp}{ext}"
        try:
            shutil.copy2(dest_onnx, backup_path)
            print(f"[*] Backed up existing model to '{os.path.basename(backup_path)}'.")
        except Exception as e:
            print(f"[-] Warning: Could not create backup: {e}")

    # 2. Copy new ONNX weights
    try:
        if os.path.abspath(exported_onnx_path) != os.path.abspath(dest_onnx):
            shutil.copy2(exported_onnx_path, dest_onnx)
            print(f"[+] Deployed new ONNX model -> '{dest_onnx}'")
        else:
            print(f"[+] ONNX model is already at target path -> '{dest_onnx}'")
    except Exception as e:
        print(f"[-] Failed to deploy ONNX model: {e}")
        return False

    # 3. Copy new PT weights if available
    if best_pt_path and os.path.exists(best_pt_path):
        try:
            if os.path.abspath(best_pt_path) != os.path.abspath(dest_pt):
                shutil.copy2(best_pt_path, dest_pt)
                print(f"[+] Deployed new PyTorch checkpoint -> '{dest_pt}'")
            else:
                print(f"[+] PyTorch checkpoint is already at target path -> '{dest_pt}'")
        except Exception as e:
            print(f"[-] Could not copy PT checkpoint: {e}")

    # 4. Verify new ONNX file with ONNX Runtime
    try:
        import onnxruntime as ort
        sess = ort.InferenceSession(dest_onnx, providers=["CPUExecutionProvider"])
        meta = sess.get_modelmeta().custom_metadata_map
        classes = meta.get("names", "Unknown")
        print(f"[SUCCESS] ONNX Runtime verified '{os.path.basename(dest_onnx)}' cleanly.")
        print(f"          Input shape: {[i.shape for i in sess.get_inputs()]}")
        print(f"          Classes    : {classes[:120]}...")
        return True
    except Exception as e:
        print(f"[-] Verification warning for deployed ONNX: {e}")
        return False


def run_training(args):
    """Executes the Ultralytics training pipeline with surveillance-optimized hyperparameters."""
    from ultralytics import YOLO

    task = args.task
    spec = TASK_SPECS.get(task, TASK_SPECS["ppe"])
    data_yaml = args.data

    if not data_yaml:
        default_yaml = os.path.join(BACKEND_ROOT, "datasets", task, "dataset.yaml")
        if os.path.isfile(default_yaml):
            data_yaml = default_yaml
        else:
            print(f"[!] No --data provided. Creating dataset template at '{default_yaml}'...")
            data_yaml = scaffold_dataset_template(task)
            print("[!] Please add your training images and labels to the dataset directory before re-running.")
            return

    # Check dataset readiness
    if not check_dataset_stats(data_yaml) and not args.force:
        print("[-] Training aborted: Dataset contains no images. Use --force to proceed anyway.")
        return

    base_model = args.model or spec["default_base_model"]
    imgsz = args.imgsz or spec["recommended_imgsz"]
    epochs = args.epochs
    batch = args.batch
    device = args.device

    print("=" * 60)
    print("       AI CCTV SURVEILLANCE MODEL TRAINING PIPELINE")
    print("=" * 60)
    print(f"Task             : {spec['name']} ({task})")
    print(f"Base Model       : {base_model}")
    print(f"Dataset YAML     : {data_yaml}")
    print(f"Target Classes   : {spec['classes']}")
    print(f"Image Size       : {imgsz}x{imgsz}")
    print(f"Epochs           : {epochs}")
    print(f"Batch Size       : {batch}")
    print(f"Device Target    : {device}")
    print("=" * 60)

    # Load base YOLO architecture (e.g. yolov8s.pt)
    model = YOLO(base_model)

    # Surveillance-tuned augmentations:
    # Slightly reduced shear/rotation to preserve overhead perspective consistency,
    # while retaining strong scale and mosaic augmentation for small objects.
    train_args = {
        "data": data_yaml,
        "epochs": epochs,
        "imgsz": imgsz,
        "batch": batch,
        "device": device,
        "patience": args.patience,
        "workers": args.workers,
        "optimizer": "auto",
        "seed": 42,
        "exist_ok": True,
        "project": "runs/train",
        "name": f"{task}_{Path(base_model).stem}",
        "verbose": True,
    }

    if args.augment:
        train_args.update({
            "mosaic": 1.0,
            "scale": 0.5,
            "degrees": 10.0,
            "fliplr": 0.5,
            "hsv_h": 0.015,
            "hsv_s": 0.7,
            "hsv_v": 0.4,
        })

    print(f"[*] Starting training loop for {epochs} epochs...")
    results = model.train(**train_args)

    # Locate best checkpoint
    save_dir = getattr(model.trainer, "save_dir", "runs/train")
    best_pt = os.path.join(save_dir, "weights", "best.pt")

    if not os.path.exists(best_pt):
        last_pt = os.path.join(save_dir, "weights", "last.pt")
        best_pt = last_pt if os.path.exists(last_pt) else None

    print("=" * 60)
    print("[+] Training completed!")
    if best_pt and os.path.exists(best_pt):
        print(f"    Best weights checkpoint: {best_pt}")

        # Run validation metrics
        print("[*] Running final validation pass...")
        val_results = model.val(data=data_yaml, imgsz=imgsz)
        print(f"    Validation mAP50    : {getattr(val_results.box, 'map50', 'N/A')}")
        print(f"    Validation mAP50-95 : {getattr(val_results.box, 'map', 'N/A')}")

        if args.deploy:
            onnx_path = export_model_to_onnx(best_pt, imgsz=imgsz)
            deploy_trained_model(onnx_path, best_pt, task)
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="AI CCTV Model Training, Fine-Tuning & Export System")
    parser.add_argument("--task", type=str, default="ppe", choices=["ppe", "fire_smoke", "person"],
                        help="Target detection task: ppe, fire_smoke, or person")
    parser.add_argument("--model", type=str, default=None,
                        help="Base model weights (e.g. yolov8s.pt, yolov8m.pt, yolov8n.pt)")
    parser.add_argument("--data", type=str, default=None,
                        help="Path to dataset.yaml configuration file")
    parser.add_argument("--data-dir", type=str, default=None,
                        help="Base directory for dataset if scaffolded")
    parser.add_argument("--epochs", type=int, default=50,
                        help="Number of training epochs (default: 50)")
    parser.add_argument("--batch", type=int, default=16,
                        help="Batch size (default: 16, use -1 for auto)")
    parser.add_argument("--imgsz", type=int, default=640,
                        help="Inference & training image resolution (default: 640)")
    parser.add_argument("--device", type=str, default="cpu",
                        help="Compute target device (e.g. '0', 'cpu', 'cuda')")
    parser.add_argument("--workers", type=int, default=4,
                        help="DataLoader worker threads (default: 4)")
    parser.add_argument("--patience", type=int, default=15,
                        help="Early stopping patience epochs (default: 15)")
    parser.add_argument("--augment", action="store_true", default=True,
                        help="Enable surveillance data augmentations")
    parser.add_argument("--deploy", action="store_true",
                        help="Automatically export best weights to ONNX and deploy to backend/models/")
    parser.add_argument("--download-dataset", action="store_true",
                        help="Download and extract official/benchmark dataset for the chosen task")
    parser.add_argument("--url", type=str, default=None,
                        help="Custom URL for dataset zip download")
    parser.add_argument("--init-dataset", action="store_true",
                        help="Scaffold empty dataset folder structure and dataset.yaml template")
    parser.add_argument("--export-only", action="store_true",
                        help="Export existing checkpoint directly to ONNX without training")
    parser.add_argument("--checkpoint", type=str, default=None,
                        help="Checkpoint path for --export-only")
    parser.add_argument("--force", action="store_true",
                        help="Force training even if dataset validation warns of low image count")

    args = parser.parse_args()

    # Auto-detect CUDA if not explicitly set to cpu
    if args.device == "cpu":
        try:
            import torch
            if torch.cuda.is_available():
                args.device = "0"
                print("[*] NVIDIA CUDA GPU detected! Training on device: 0")
        except Exception:
            pass

    if args.download_dataset:
        yaml_path = download_dataset(args.task, custom_url=args.url, output_dir=args.data_dir)
        if not args.data and yaml_path:
            args.data = yaml_path
        print(f"[+] Dataset is ready for training at: {yaml_path}")
        # If user only specified --download-dataset without running training, stop here
        if not args.model and "--epochs" not in sys.argv:
            return

    if args.init_dataset:
        scaffold_dataset_template(args.task, args.data_dir)
        return

    if args.export_only:
        ckpt = args.checkpoint
        # If user passed placeholder like "path/to/best.pt" or file not found, search runs/ and models/
        if not ckpt or ckpt == "path/to/best.pt" or not os.path.exists(ckpt):
            import glob
            search_patterns = [
                os.path.join(BACKEND_ROOT, "models", f"{args.task}.pt"),
                os.path.join(BACKEND_ROOT, "runs", "**", "weights", "best.pt"),
                os.path.join(os.path.dirname(BACKEND_ROOT), "runs", "**", "weights", "best.pt"),
                os.path.join("runs", "**", "weights", "best.pt"),
            ]
            candidates = []
            for pattern in search_patterns:
                candidates.extend(glob.glob(pattern, recursive=True))

            existing = [os.path.abspath(c) for c in candidates if os.path.isfile(c)]
            # Sort by modification time (newest first)
            existing.sort(key=lambda p: os.path.getmtime(p), reverse=True)

            if existing:
                ckpt = existing[0]
                print(f"[*] Auto-detected latest trained checkpoint: {ckpt}")
            else:
                print(f"[-] Checkpoint file not found: {args.checkpoint or f'{args.task}.pt'}")
                print("    Please specify an existing checkpoint path via --checkpoint <path/to/weights.pt>.")
                sys.exit(1)

        onnx_path = export_model_to_onnx(ckpt, imgsz=args.imgsz)
        if args.deploy:
            deploy_trained_model(onnx_path, ckpt, args.task)
        return

    run_training(args)


if __name__ == "__main__":
    main()
