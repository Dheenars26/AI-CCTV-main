"""
GPU & System Resource Manager (ResourceManager).
Manages multi-GPU allocation, memory monitoring, device selection, and controlled CUDA OOM recovery.
"""

import time
import threading
from typing import Dict, Any, Optional
from app.utils.logger import logger

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


class ResourceManager:
    """
    Tracks GPU device health, allocated memory, utilization, and handles controlled CUDA OOM recovery.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._gpu_status: Dict[int, Dict[str, Any]] = {}
        self._oom_recovery_count: Dict[int, int] = {}
        self._initialize_gpu_devices()

    @property
    def cuda_available(self) -> bool:
        """Returns True if PyTorch CUDA acceleration is active."""
        return TORCH_AVAILABLE and torch.cuda.is_available()

    def _initialize_gpu_devices(self) -> None:
        """
        Discovers installed CUDA devices or registers CPU fallback.
        """
        if TORCH_AVAILABLE and torch.cuda.is_available():
            device_count = torch.cuda.device_count()
            for dev_id in range(device_count):
                props = torch.cuda.get_device_properties(dev_id)
                self._gpu_status[dev_id] = {
                    "device_id": dev_id,
                    "name": props.name,
                    "total_memory_mb": round(props.total_memory / (1024 * 1024), 2),
                    "allocated_memory_mb": 0.0,
                    "utilization_percent": 0.0,
                    "status": "HEALTHY",
                    "is_cpu_fallback": False
                }
                self._oom_recovery_count[dev_id] = 0
            logger.info(f"ResourceManager: Discovered {device_count} CUDA GPU device(s).")
        else:
            logger.info("ResourceManager: No CUDA GPUs detected or PyTorch CPU-only mode. CPU fallback active.")
        
        if TORCH_AVAILABLE:
            try:
                import os
                optimal_threads = min(4, max(1, os.cpu_count() or 4))
                torch.set_num_threads(optimal_threads)
            except Exception:
                pass

        # CPU Fallback Device (-1)
        self._gpu_status[-1] = {
            "device_id": -1,
            "name": "CPU Worker Fallback",
            "total_memory_mb": 0.0,
            "allocated_memory_mb": 0.0,
            "utilization_percent": 0.0,
            "status": "HEALTHY",
            "is_cpu_fallback": True
        }

    def get_target_device(self, requested_gpu_id: int) -> str:
        """
        Validates and returns PyTorch device string (e.g. 'cuda:0' or 'cpu').
        If requested GPU ID does not exist, falls back gracefully to 'cpu'.
        """
        if requested_gpu_id == -1 or not TORCH_AVAILABLE or not torch.cuda.is_available():
            return "cpu"

        if requested_gpu_id in self._gpu_status and self._gpu_status[requested_gpu_id]["status"] == "HEALTHY":
            return f"cuda:{requested_gpu_id}"

        logger.warning(f"ResourceManager: Requested GPU ID {requested_gpu_id} unavailable. Falling back to CPU.")
        return "cpu"

    def handle_cuda_oom(self, gpu_id: int) -> str:
        """
        Controlled CUDA OOM Recovery Procedure:
        1. Log OOM event
        2. Garbage collection (torch.cuda.empty_cache())
        3. Memory cleanup
        4. If recovery count exceeds 3, transition device to DEGRADED and return 'cpu' fallback.
        """
        with self._lock:
            if gpu_id not in self._oom_recovery_count:
                self._oom_recovery_count[gpu_id] = 0
            self._oom_recovery_count[gpu_id] += 1
            rec_count = self._oom_recovery_count[gpu_id]

            logger.error(f"ResourceManager: CUDA OOM Exception caught on GPU {gpu_id} (Recovery attempt #{rec_count}).")

            if TORCH_AVAILABLE and torch.cuda.is_available():
                try:
                    torch.cuda.empty_cache()
                    logger.info(f"ResourceManager: Executed torch.cuda.empty_cache() on GPU {gpu_id}.")
                except Exception as e:
                    logger.warning(f"ResourceManager: empty_cache error: {str(e)}")

            if rec_count >= 3:
                if gpu_id in self._gpu_status:
                    self._gpu_status[gpu_id]["status"] = "DEGRADED"
                logger.warning(f"ResourceManager: GPU {gpu_id} exceeded recovery limit. Falling back to CPU for pipeline stability.")
                return "cpu"

            return f"cuda:{gpu_id}" if (TORCH_AVAILABLE and torch.cuda.is_available()) else "cpu"

    def get_resource_metrics(self) -> Dict[str, Any]:
        """
        Returns telemetry metrics across all GPU devices and CPU.
        """
        with self._lock:
            metrics = {}
            for dev_id, status_dict in self._gpu_status.items():
                if TORCH_AVAILABLE and torch.cuda.is_available() and dev_id >= 0:
                    try:
                        mem_alloc = torch.cuda.memory_allocated(dev_id) / (1024 * 1024)
                        status_dict["allocated_memory_mb"] = round(mem_alloc, 2)
                    except Exception:
                        pass
                metrics[f"gpu_{dev_id}"] = status_dict.copy()
            return metrics

    def get_gpu_info(self) -> Dict[str, Any]:
        """Return the concise GPU capability information used by health endpoints."""
        return {
            "cuda_available": self.cuda_available,
            "devices": self.get_resource_metrics(),
        }


# Process-wide read-only resource view for API health checks.  CameraManager
# still owns its own manager for scheduling and OOM recovery state.
resource_manager = ResourceManager()
