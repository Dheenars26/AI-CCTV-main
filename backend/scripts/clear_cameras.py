"""
Clear All Cameras CLI Utility (clear_cameras.py).
Stops all stream worker threads and purges all camera records from the database.
Usage:
    python scripts/clear_cameras.py
"""

import os
import sys

# Ensure working directory is backend folder so .env is loaded correctly
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(backend_dir)
sys.path.insert(0, backend_dir)

from app.database.session import SessionLocal
from app.camera.manager import CameraManager
from app.services.camera_service import CameraService


def main():
    db = SessionLocal()
    try:
        manager = CameraManager()
        service = CameraService(db=db, camera_manager=manager)
        count = service.delete_all_cameras()
        print(f"[SUCCESS] Successfully removed all {count} cameras from system.")
        sys.exit(0)
    except Exception as e:
        print(f"[ERROR] Failed to clear cameras: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
