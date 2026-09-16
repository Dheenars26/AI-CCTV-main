"""
AI Worker Pool Subsystem (AIWorkerPool).
Executes AI frame processing tasks asynchronously from BoundedFrameQueues.
Complete Failure Isolation: AI exceptions are caught, logged, and isolated from camera ingestion workers.
"""

import time
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Callable, Optional
from app.utils.logger import logger


class AIWorkerPool:
    """
    Manages a pool of worker threads for AI frame processing tasks.
    """

    def __init__(self, max_workers: int = 8):
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="AIWorker")
        self.active_jobs: int = 0
        self.total_processed_jobs: int = 0
        self.failed_jobs: int = 0
        self._lock = threading.Lock()

    def submit_job(self, task_func: Callable[..., Any], *args, **kwargs) -> bool:
        """
        Submits an AI inference job to the worker pool.
        """
        with self._lock:
            if self.active_jobs >= self.max_workers * 2:
                # Pool backpressure: drop job to protect memory
                self.failed_jobs += 1
                return False
            self.active_jobs += 1

        def _wrapped_task():
            try:
                task_func(*args, **kwargs)
                with self._lock:
                    self.total_processed_jobs += 1
            except Exception as e:
                with self._lock:
                    self.failed_jobs += 1
                logger.error(f"AIWorkerPool: Task exception caught and isolated: {str(e)}", exc_info=True)
            finally:
                with self._lock:
                    self.active_jobs = max(0, self.active_jobs - 1)

        try:
            self._executor.submit(_wrapped_task)
            return True
        except Exception as e:
            with self._lock:
                self.active_jobs = max(0, self.active_jobs - 1)
                self.failed_jobs += 1
            if isinstance(e, RuntimeError) and "shutdown" in str(e).lower():
                logger.debug(f"AIWorkerPool: Cannot submit job, worker pool shutting down: {str(e)}")
            else:
                logger.error(f"AIWorkerPool: Failed to submit job: {str(e)}")
            return False

    def shutdown(self) -> None:
        """
        Gracefully shuts down executor pool.
        """
        logger.info("AIWorkerPool: Shutting down AI worker pool...")
        try:
            self._executor.shutdown(wait=True, cancel_futures=True)
        except TypeError:
            try:
                self._executor.shutdown(wait=True)
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"AIWorkerPool: Exception during shutdown: {str(e)}")
        logger.info("AIWorkerPool: Shutdown complete.")
