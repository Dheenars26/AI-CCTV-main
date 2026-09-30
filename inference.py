"""
Live fire & smoke inference using a trained YOLOv8 model.

Usage:
    python inference.py              # webcam (source=0)
    python inference.py video.mp4    # video file
    python inference.py rtsp://...   # RTSP stream

The script loads the best weights from training output and runs real-time
detection with bounding-box overlays + confidence labels.
Press 'q' to quit.
"""

import sys
import cv2
from ultralytics import YOLO


def run_inference(source_path=0):
    """
    Run live fire/smoke detection on a video source.

    Args:
        source_path: 0 for webcam, or a path/URL to a video file or RTSP stream.
    """
    # Load your custom-trained weights
    model = YOLO("runs/detect/train/weights/best.pt")

    cap = cv2.VideoCapture(source_path)
    if not cap.isOpened():
        print(f"Error: Cannot open video source: {source_path}")
        return

    print(f"Running inference on source: {source_path}")
    print("Press 'q' to quit")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("End of stream or cannot read frame.")
            break

        # Run YOLO inference on the frame
        results = model(frame, conf=0.5)

        # Draw detections on the frame
        annotated_frame = results[0].plot()

        cv2.imshow("Fire & Smoke Detection", annotated_frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("Inference stopped.")


if __name__ == "__main__":
    source = sys.argv[1] if len(sys.argv) > 1 else 0
    run_inference(source)
