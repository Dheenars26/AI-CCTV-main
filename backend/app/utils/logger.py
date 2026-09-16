"""
Structured Logging Configuration.
Configures console and file logger handlers with context-aware Request Correlation ID.
"""

import sys
import os
import logging
from logging.handlers import RotatingFileHandler
from app.config.settings import settings
from app.middleware.request_id import get_request_id


class RequestIDLogFilter(logging.Filter):
    """
    Log filter that injects the active request_id from contextvars into log records.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


class SafeRotatingFileHandler(RotatingFileHandler):
    """
    Windows-safe RotatingFileHandler that silently handles file lock conflicts during rotation.
    """
    def doRollover(self):
        try:
            super().doRollover()
        except (PermissionError, OSError):
            pass


def setup_logger() -> logging.Logger:
    """
    Initializes and configures the application logger.
    Configures console output and rotating file log output.
    """
    logger_instance = logging.getLogger("ai_cctv_monitor")

    # Set base level
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger_instance.setLevel(log_level)

    # Avoid duplicate handlers if setup_logger called multiple times
    if logger_instance.hasHandlers():
        return logger_instance

    # Create log format with request_id
    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [req_id:%(request_id)s] [%(name)s:%(filename)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    request_filter = RequestIDLogFilter()

    # 1. Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(request_filter)
    logger_instance.addHandler(console_handler)

    # 2. File Handler
    log_dir = os.path.dirname(settings.LOG_FILE_PATH)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    file_handler = SafeRotatingFileHandler(
        settings.LOG_FILE_PATH,
        maxBytes=10 * 1024 * 1024,  # 10 MB per file
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(request_filter)
    logger_instance.addHandler(file_handler)

    logger_instance.propagate = False
    return logger_instance


logger = setup_logger()
