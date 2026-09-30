"""
Train a YOLOv8-nano fire & smoke detection model.

Usage:
    python train.py

Prerequisites:
    1. pip install ultralytics
    2. Prepare a dataset with 'data.yaml' in the project root pointing
       to your train/val image folders and class names (fire, smoke).

Output:
    Best weights are saved to  runs/detect/train/weights/best.pt
    which is automatically picked up by the live inference pipeline.
"""

from ultralytics import YOLO


def train_fire_smoke_model():
    # Load a pre-trained YOLO nano model (yolov8n.pt or yolov11n.pt)
    # Nano models are ideal for real-time edge deployment
    model = YOLO("yolov8n.pt")

    # Train the model
    results = model.train(
        data="data.yaml",      # Path to dataset config file
        epochs=50,             # Number of training epochs
        imgsz=640,             # Training image size
        batch=16,              # Adjust based on GPU VRAM
        device=0               # Use 'cpu' if you don't have a CUDA-enabled GPU
    )
    print("Training complete! Best weights saved to 'runs/detect/train/weights/best.pt'")


if __name__ == "__main__":
    train_fire_smoke_model()
