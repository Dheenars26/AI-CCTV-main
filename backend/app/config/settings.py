"""
Centralized Application Settings Management using Pydantic Settings.
Loads configuration from environment variables or .env file.
"""

import sys
import os
from typing import List, Union, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import json


class Settings(BaseSettings):
    """
    Application settings model with environment variable fallback and validation.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # General App Config
    APP_NAME: str = "SynterionX AI Surveillance Platform"
    APP_ENV: str = "testing" if ("pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ) else "development"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    VERSION: str = "1.0.0"

    # Security & CORS
    CORS_ORIGINS: Union[List[str], str] = ["*"]
    SECRET_KEY: str = "development-secret-key-change-in-production"

    # Database Settings
    DATABASE_URL: str = "sqlite:///./cctv.db"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # Logging Config
    LOG_LEVEL: str = "INFO"
    LOG_FILE_PATH: str = "logs/app.log"

    # Camera & RTSP Defaults
    DEFAULT_RTSP_TIMEOUT_SECONDS: int = 10
    MAX_RECONNECT_ATTEMPTS: int = 5
    DEFAULT_LATITUDE: float = 13.0827
    DEFAULT_LONGITUDE: float = 80.2707

    # AI Model & Compute Engine Configuration
    AI_DEVICE: str = "cpu"
    AI_HALF_PRECISION: bool = True
    AI_IMAGE_SIZE: int = 320
    AI_TARGET_FPS: int = 10
    ENABLE_PERSON_TRACKING: bool = True
    ENABLE_PPE_ROI: bool = False  # Disabled by default; enable only if ROI benchmarking justifies extra cost

    # Class-Specific Confidence Thresholds (Tuned for High Precision & Zero False Alarms)
    FIRE_CONFIDENCE_THRESHOLD: float = 0.50
    SMOKE_CONFIDENCE_THRESHOLD: float = 0.48
    PERSON_CONFIDENCE_THRESHOLD: float = 0.40
    VEST_CONFIDENCE_THRESHOLD: float = 0.35
    GLASSES_CONFIDENCE_THRESHOLD: float = 0.30
    ENABLE_CV_VEST_DETECTION: bool = True
    ENABLE_CV_HELMET_DETECTION: bool = False
    ENABLE_CV_GLASSES_DETECTION: bool = True

    # YOLO Model File Paths & Backward Compatibility Aliases
    YOLO_MODEL_PATH: str = "models/fire_smoke.onnx"
    YOLO_CONF_THRESHOLD: float = 0.48
    YOLO_IOU_THRESHOLD: float = 0.45
    YOLO_IMGSZ: int = 416
    YOLO_AUGMENT: bool = False
    YOLO_DEVICE: str = "cpu"
    YOLO_ENABLE_HSV_FALLBACK: bool = False
    AI_DETECTION_ENABLED: bool = True
    AI_FIRE_SMOKE_ENABLED: bool = True

    # PPE & Workplace Safety AI Model Configuration
    AI_PPE_ENABLED: bool = True
    AI_PERSON_ENABLED: bool = True
    AI_ZONE_ENABLED: bool = True
    PPE_MODEL_PATH: str = "models/ppe.onnx"
    PPE_CONFIDENCE_THRESHOLD: float = 0.38
    PPE_IOU_THRESHOLD: float = 0.45
    PPE_DEVICE: str = "cpu"
    PPE_VERIFICATION_FRAMES: int = 6
    PPE_VERIFICATION_DURATION_SECONDS: float = 1.2
    PPE_INFERENCE_INTERVAL_SEC: float = 0.25
    PPE_ALERT_COOLDOWN_SECONDS: float = 60.0
    PERSON_MODEL_PATH: str = "models/yolov8n.onnx"

    # Fire & Smoke Temporal Verification (Requires persistent spatial detection before confirming)
    FIRE_MIN_CONSECUTIVE_FRAMES: int = 7
    FIRE_MIN_DURATION_SECONDS: float = 1.4
    SMOKE_MIN_CONSECUTIVE_FRAMES: int = 9
    SMOKE_MIN_DURATION_SECONDS: float = 2.2
    SMOKE_ALERT_COOLDOWN_SECONDS: float = 30.0

    # Feature Toggles for Safety Engine
    ZONE_MONITORING_ENABLED: bool = True
    PERSON_DETECTION_ENABLED: bool = True
    SAFETY_INCIDENT_ENABLED: bool = True
    PPE_EVIDENCE_ENABLED: bool = True
    PPE_EMAIL_ALERT_ENABLED: bool = True
    PPE_WEBHOOK_ALERT_ENABLED: bool = False

    # Temporal Verification & False Alarm Reduction Settings
    VERIFICATION_MIN_CONFIDENCE: float = 0.45
    VERIFICATION_MIN_CONSECUTIVE_FRAMES: int = 7
    VERIFICATION_MIN_DURATION_SECONDS: float = 1.4
    VERIFICATION_COOLDOWN_SECONDS: float = 30.0
    SPATIAL_IOU_THRESHOLD: float = 0.18

    # Incident Evidence Management & Video Archiving Settings
    EVIDENCE_STORAGE_DIR: str = "evidence"
    PRE_EVENT_BUFFER_SECONDS: float = 5.0
    POST_EVENT_BUFFER_SECONDS: float = 10.0
    EVIDENCE_RETENTION_DAYS: int = 1
    EVIDENCE_JPEG_QUALITY: int = 90

    # Email Alert System & SMTP Configuration
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    SMTP_SENDER_EMAIL: str = "alerts@aicctv.local"
    SMTP_SENDER_NAME: str = "AI CCTV Fire & Smoke Monitoring"
    ALERT_RECIPIENT_EMAILS: Union[List[str], str] = []
    EMAIL_ALERTS_ENABLED: bool = True
    EMAIL_RETRY_ATTEMPTS: int = 3
    EMAIL_COOLDOWN_SECONDS: float = 60.0

    # Webhook Alert Dispatch Configuration
    WEBHOOK_ALERTS_ENABLED: bool = True
    WEBHOOK_URLS: Union[List[str], str] = []
    WEBHOOK_SECRET_KEY: str = "cctv-webhook-secret-key"
    WEBHOOK_TIMEOUT_SECONDS: float = 5.0

    @field_validator("DEBUG", mode="before")
    @classmethod
    def normalize_debug(cls, value: object) -> bool:
        """Accept common deployment labels while keeping a strict boolean internally."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on", "debug", "development", "dev"}:
                return True
            if normalized in {"0", "false", "no", "off", "release", "production", "prod"}:
                return False
        return bool(value)

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, v: Optional[str]) -> str:
        """
        Ensures SQLite database path is always anchored as an absolute path in backend directory,
        normalizes postgres:// to postgresql://, and falls back to SQLite if empty.
        """
        if not v or not v.strip():
            backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_path = os.path.join(backend_dir, "cctv.db")
            return f"sqlite:///{db_path}"
        
        v_str = v.strip()
        if "localhost:5432" in v_str or "127.0.0.1:5432" in v_str:
            backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_path = os.path.join(backend_dir, "cctv.db")
            return f"sqlite:///{db_path}"

        if v_str.startswith("postgres://"):
            return v_str.replace("postgres://", "postgresql://", 1)

        if "sqlite:///./" in v_str or v_str == "sqlite:///cctv.db":
            backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_path = os.path.join(backend_dir, "cctv.db")
            return f"sqlite:///{db_path}"
        return v_str

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """
        Parses CORS_ORIGINS from string or JSON array into a List of string URLs.
        """
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["*"]

    @field_validator("ALERT_RECIPIENT_EMAILS", mode="before")
    @classmethod
    def assemble_recipient_emails(cls, v: Union[str, List[str]]) -> List[str]:
        """
        Parses ALERT_RECIPIENT_EMAILS from string or JSON array into a List of email strings.
        """
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return []

    @field_validator("WEBHOOK_URLS", mode="before")
    @classmethod
    def assemble_webhook_urls(cls, v: Union[str, List[str]]) -> List[str]:
        """
        Parses WEBHOOK_URLS from string or JSON array into a List of webhook URL strings.
        """
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return []


settings = Settings()
