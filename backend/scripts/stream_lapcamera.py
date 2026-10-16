"""
Local Laptop Webcam HTTP Streamer for AI CCTV.
Bridges your Windows laptop webcam into Docker containers.

Run this script in PowerShell on your Windows host:
    python backend/scripts/stream_lapcamera.py

Then in the AI CCTV Dashboard:
- Add or Edit Camera
- Source Type: "RTSP IP Camera Stream" (or keep source as URL)
- Stream URL: http://host.docker.internal:8085/video
"""

import sys
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import cv2

# Global frame buffer and lock
frame_lock = threading.Lock()
latest_jpg = None
running = True


def capture_loop(device_index: int = 0, fps_target: int = 25):
    global latest_jpg, running

    # Try DirectShow on Windows first for fast startup
    cap = cv2.VideoCapture(device_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(device_index)

    if not cap.isOpened():
        print(f"[ERROR] Could not open webcam at device index {device_index}!")
        print("Please check that no other application (Zoom, Teams, Camera app) is using the webcam.")
        running = False
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, fps_target)

    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"[SUCCESS] Webcam connected: {actual_w}x{actual_h} @ {fps_target}fps")
    print(f"[READY] Streaming live webcam at:")
    print(f"        Local Host:    http://localhost:8085/video")
    print(f"        Inside Docker: http://host.docker.internal:8085/video\n")

    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), 75]
    frame_interval = 1.0 / fps_target

    while running:
        t0 = time.time()
        ret, frame = cap.read()
        if ret and frame is not None:
            _, buffer = cv2.imencode(".jpg", frame, encode_params)
            with frame_lock:
                latest_jpg = buffer.tobytes()

        elapsed = time.time() - t0
        sleep_time = max(0.001, frame_interval - elapsed)
        time.sleep(sleep_time)

    cap.release()


class MJPEGHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/video", "/stream"):
            self.send_response(200)
            self.send_header("Age", "0")
            self.send_header("Cache-Control", "no-cache, private")
            self.send_header("Pragma", "no-cache")
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=FRAME")
            self.end_headers()

            try:
                while running:
                    with frame_lock:
                        jpg_bytes = latest_jpg

                    if jpg_bytes:
                        self.wfile.write(b"--FRAME\r\n")
                        self.send_header("Content-Type", "image/jpeg")
                        self.send_header("Content-Length", str(len(jpg_bytes)))
                        self.end_headers()
                        self.wfile.write(jpg_bytes)
                        self.wfile.write(b"\r\n")
                    time.sleep(0.04)  # ~25 fps
            except (ConnectionResetError, BrokenPipeError):
                pass
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Silence verbose HTTP access logs
        return


def main():
    device_idx = 0
    port = 8085
    if len(sys.argv) > 1:
        try:
            device_idx = int(sys.argv[1])
        except ValueError:
            pass

    t = threading.Thread(target=capture_loop, args=(device_idx, 25), daemon=True)
    t.start()

    # Wait briefly for capture to start
    time.sleep(1.0)
    if not running:
        return

    server = HTTPServer(("0.0.0.0", port), MJPEGHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping webcam stream...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
