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

    # Database Settings (SQLAlchemy / Relational)
    # MongoDB Settings (Hybrid Architecture for Detection Logs & Telemetry)
    MONGODB_ENABLED: bool = True
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "cctv_ai_surveillance"
    MONGODB_SERVER_TIMEOUT_MS: int = 2500
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
    # AI_IMAGE_SIZE: raised from 320 to 640 for significantly better small-object accuracy (smoke, glasses)
    AI_IMAGE_SIZE: int = 640
    AI_TARGET_FPS: int = 10
    ENABLE_PERSON_TRACKING: bool = True
    ENABLE_PPE_ROI: bool = True  # Worker-crop refinement: measured to double safety-glasses recall

    # ONNX Runtime & Post-Processing Engine (Accuracy/Speed Tuning)
    AI_ORT_THREADS: int = 0          # 0 = auto (half the cores, capped at 4, never oversubscribed)
    AI_WBF_ENABLED: bool = True      # Weighted Box Fusion: merges duplicate boxes, stabilises boxes
    AI_MAX_CANDIDATES_PER_CLASS: int = 120  # Post-processing cost guard
    AI_MOTION_GATE_ENABLED: bool = True   # Skip worker/PPE inference on frames with no motion
    AI_MOTION_MIN_AREA_RATIO: float = 0.0012
    AI_MOTION_SWEEP_SECONDS: float = 2.5  # Guaranteed full-scene inspection cadence
    ENABLE_PERSON_ROI_REFINE: bool = True   # Second-pass person search on motion regions
    PERSON_ROI_REFINE_MAX_ROIS: int = 1      # Bounded so the extra inference stays predictable
    PERSON_ROI_REFINE_MAX_AREA: float = 0.35 # Only refine regions this small (large ones gain nothing)
    # ENABLE_VEST_HIVIS_CORROBORATION: disabled. HSV color analysis on torso crops falsely
    #   detects regular shirts (grey, white, coloured) as hi-vis vests. The CV method cannot
    #   distinguish fluorescent safety fabric from natural clothing. Neural model is authority.
    ENABLE_VEST_HIVIS_CORROBORATION: bool = False
    VEST_HIVIS_MIN_COLOR_RATIO: float = 0.06  # Fluorescent fabric coverage of the torso box
    VEST_HIVIS_MIN_SILVER_RATIO: float = 0.10 # Retroreflective band coverage of the torso box
    PPE_REQUIRE_PERSON_ASSOCIATION: bool = True  # Unassociated PPE items are never reported
    PPE_CROP_REFINE_MAX_PERSONS: int = 4
    PPE_ROI_REFINE_EVERY_N: int = 1   # Refine missing items on every worker frame for zero latency
    # PPE_ANALYSIS_REUSE_SECONDS: reduced 2.0→1.0. When the worker branch is gated (motion gate,
    #   cadence limiter), the previous PPE conclusions are replayed for this window. 2.0s was long
    #   enough to replay a stale VIOLATION status long after the worker already had their gear on,
    #   producing persistent red badges that contradicted live green "Safety Vest Found" badges.
    PPE_ANALYSIS_REUSE_SECONDS: float = 1.0  # How long previous PPE conclusions stay valid on gated frames

    # ── Class-Specific Confidence Thresholds ────────────────────────────────────────────────────
    # Tuned for accuracy: higher values reduce false alarms; lower values improve recall.
    # FIRE: 0.30 catches real small fires while the physics veto chain eliminates false positives.
    FIRE_CONFIDENCE_THRESHOLD: float = 0.30
    # SMOKE: 0.28 gives a reasonable recall floor; physics/texture veto handles false positives.
    SMOKE_CONFIDENCE_THRESHOLD: float = 0.28
    # PERSON_CONFIDENCE_THRESHOLD: 0.52 — elevated above the default 0.25 for overhead CCTV angles.
    #   Phantom boxes from chair backs, reflective bags, floor objects: 0.30–0.48
    #   Real seated worker torso from overhead: 0.62–0.90
    PERSON_CONFIDENCE_THRESHOLD: float = 0.52
    # Person bounding-box geometry filters. Applied post-inference before box is admitted.
    #   PERSON_MIN_BOX_HEIGHT: 0.07 — floor objects / chair backs top out at ~5% frame height;
    #     a real seated worker is ≥8–10%. Margin of 1–3% is safe.
    #   PERSON_MIN_BOX_AREA: 0.003 — rejects tiny noise boxes smaller than 3% of frame.
    #   PERSON_MAX_ASPECT_RATIO: 1.5 — wider boxes (silver bag AR≈2.4) are firmly rejected.
    PERSON_MIN_BOX_HEIGHT: float = 0.07
    PERSON_MIN_BOX_AREA: float = 0.003          # Minimum normalised area; smaller = noise
    PERSON_MIN_ASPECT_RATIO: float = 0.10        # w/h minimum — reject extremely thin slivers
    PERSON_MAX_ASPECT_RATIO: float = 1.5         # w/h maximum — narrowed from 1.6
    # VEST_CONFIDENCE_THRESHOLD: 0.65 eliminates phantom vests on dark shirts, regular jackets, and olive green shirts.
    #   Real high-visibility vests score 0.70+ on a trained model.
    VEST_CONFIDENCE_THRESHOLD: float = 0.65
    # GLASSES_CONFIDENCE_THRESHOLD: 0.40 — higher than before to eliminate bare-face shadows.
    GLASSES_CONFIDENCE_THRESHOLD: float = 0.40
    ENABLE_CV_VEST_DETECTION: bool = True
    ENABLE_CV_HELMET_DETECTION: bool = False
    ENABLE_CV_GLASSES_DETECTION: bool = True
    ENABLE_CV_GLASSES_FALLBACK_ON_NEURAL_PATH: bool = True
    GLASSES_CV_MIN_PERSON_CONF: float = 0.50     # Only evaluate CV glasses on confirmed-person boxes
    GLASSES_ROI_CONFIDENCE_FLOOR: float = 0.12   # Raised from 0.085 — tighter floor for eyewear search
    VEST_CROP_CONFIDENCE_FLOOR: float = 0.20     # Raised from 0.15 — tighter floor for vest crop search
    PPE_ROI_REFINE_EVERY_N: int = 1              # Refine ROI on every worker frame for rapid response

    # YOLO Model File Paths & Backward Compatibility Aliases
    YOLO_MODEL_PATH: str = "models/fire_smoke.onnx"
    # ENABLE_STANDALONE_VEST_FALLBACK: disabled. Raw HSV scanning of the room produces phantom vest
    # detections on phone screens, orange flame reflections, green desk partitions, and glass railings.
    # Vests must be worn on confirmed worker torsos via neural model or hi-vis corroboration.
    ENABLE_STANDALONE_VEST_FALLBACK: bool = False
    ENABLE_HIGHVIS_WORKER_ANCHOR: bool = False
    # YOLO_CONF_THRESHOLD: 0.20 — low candidate floor for raw inference; per-class gates above
    #   (FIRE_CANDIDATE_CONFIDENCE, SMOKE_CANDIDATE_CONFIDENCE) are the real precision gates.
    YOLO_CONF_THRESHOLD: float = 0.20
    # YOLO_IOU_THRESHOLD: 0.40 — slightly tighter NMS suppression to eliminate duplicate boxes.
    YOLO_IOU_THRESHOLD: float = 0.40
    YOLO_IMGSZ: int = 640  # Raised from 416 for significantly better small-object recall
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
    PPE_CONFIDENCE_THRESHOLD: float = 0.35        # Raised from 0.30 for fewer phantom PPE boxes
    PPE_IOU_THRESHOLD: float = 0.40               # Tighter NMS to eliminate duplicate PPE boxes
    PPE_DEVICE: str = "cpu"
    # PPE temporal verification: require sustained evidence before flagging violation.
    # 6 frames + 2.5 s eliminates transient flickers and single-frame noise.
    PPE_VERIFICATION_FRAMES: int = 6
    PPE_VERIFICATION_DURATION_SECONDS: float = 2.5
    PPE_INFERENCE_INTERVAL_SEC: float = 0.25
    PPE_MAX_INFERENCE_INTERVAL_SEC: float = 2.0
    PPE_ADAPTIVE_CADENCE: bool = True
    PPE_ALERT_COOLDOWN_SECONDS: float = 90.0
    PERSON_MODEL_PATH: str = "models/yolov8s.onnx"

    # ── Fire & Smoke Detection Physics Model ────────────────────────────────────────────────────
    # FIRE_CANDIDATE_CONFIDENCE: 0.12 — low raw candidate floor; real gate is FIRE_ALERT_CONFIDENCE.
    FIRE_CANDIDATE_CONFIDENCE: float = 0.12
    # SMOKE_CANDIDATE_CONFIDENCE: 0.12 — same principle; texture/dispersion veto does heavy lifting.
    SMOKE_CANDIDATE_CONFIDENCE: float = 0.12
    # FIRE_PHYSICS_WEIGHT: 0.40 — allow physics corroboration to contribute more to final confidence.
    FIRE_PHYSICS_WEIGHT: float = 0.40
    # FIRE_STRUCTURE_EDGE_RATIO: 0.45 — surfaces with >45% straight-edge content are man-made.
    FIRE_STRUCTURE_EDGE_RATIO: float = 0.45
    # FIRE_REQUIRE_AGREEMENT: 2 — require multi-pass box agreement for sub-threshold candidates.
    FIRE_REQUIRE_AGREEMENT: int = 2
    # Per-frame minimum confidence accepted by the temporal FSM before accumulating credit.
    FIRE_VERIFICATION_MIN_CONFIDENCE: float = 0.22
    SMOKE_VERIFICATION_MIN_CONFIDENCE: float = 0.22
    VEST_HIVIS_MIN_COLOR_RATIO: float = 0.06

    # ── Fire-Scene PPE Veto ──────────────────────────────────────────────────────────────────────
    FIRE_SCENE_VETO_ENABLED: bool = True
    FIRE_SCENE_THRESHOLD_BOOST: float = 0.28       # Added to person/vest/glasses floors during fire
    FIRE_SCENE_PERSON_IOU_SUPPRESS: float = 0.15
    FIRE_SCENE_TRACK_STALENESS_SECONDS: float = 3.0
    VEST_HIVIS_MIN_SILVER_RATIO: float = 0.035
    VEST_CROP_CONFIDENCE_FLOOR: float = 0.60

    # ── Fire & Smoke Alert Floors ────────────────────────────────────────────────────────────────
    # FIRE_ALERT_CONFIDENCE: 0.42 — combined model+physics score must exceed this to raise an alert.
    FIRE_ALERT_CONFIDENCE: float = 0.42
    # SMOKE_ALERT_CONFIDENCE: 0.50 — lower than fire because smoke appears gradually.
    SMOKE_ALERT_CONFIDENCE: float = 0.50

    # ── Fire & Smoke Temporal Verification ──────────────────────────────────────────────────────
    # FIRE: 4 consecutive frames over ≥1.2 s — catches fast-developing fires without missing slow ones.
    FIRE_MIN_CONSECUTIVE_FRAMES: int = 4
    FIRE_MIN_DURATION_SECONDS: float = 1.2
    # SMOKE: 7 frames over 2.2 s — static textures almost never sustain 7 clean frames over 2.2 s.
    SMOKE_MIN_CONSECUTIVE_FRAMES: int = 7
    SMOKE_MIN_DURATION_SECONDS: float = 2.2
    SMOKE_ALERT_COOLDOWN_SECONDS: float = 45.0

    # ── Tiling for Small Fire/Smoke Recovery ────────────────────────────────────────────────────
    # Enable tiled re-inference when the full-frame pass is empty or weak.
    # Small fires/smoke plumes that are only a few pixels in full-frame view benefit greatly.
    FIRE_SMOKE_TILING_ENABLED: bool = True
    FIRE_SMOKE_TILE_GRID: tuple = (2, 2)           # 2×2 tile grid
    FIRE_SMOKE_TILE_OVERLAP: float = 0.20          # 20% overlap between tiles
    FIRE_SMOKE_TILE_MIN_INTERVAL_FRAMES: int = 2   # Only tile every 2nd frame when weak/empty

    # ── Smoke False-Positive Suppression ─────────────────────────────────────────────────────────
    # These three toggles control the post-structure-veto discriminator chain added for the
    # striped-doormat FP (scored 0.41 SMOKE, survived all previous gates). Each can be disabled
    # independently via env-var / .env for constrained hardware or ablation testing.

    # SMOKE_TEXTURE_ENTROPY_VETO: grid-based local-variance fabric/carpet discriminator.
    #   Divides the candidate crop into a 4×4 grid and measures the std of each cell.
    #   Real smoke has a soft luminance gradient → spatially uniform cell stds (low var-of-stds).
    #   Woven fabric/carpet has high local std in stripe cells and near-uniform in gap cells →
    #   high var-of-stds. Thresholds tuned against the doormat FP case.
    SMOKE_TEXTURE_ENTROPY_VETO: bool = True
    # Thresholds for _smoke_texture_veto (8×8 grid, per-cell max-min range metric).
    # Decision rule: mean_range > THRESH_MEAN AND var_range < THRESH_VAR
    # Calibration (striped doormat FP + smoke positives):
    #   striped_doormat: mean_range=15.7, var_range=0.7  → VETO
    #   diagonal_carpet: mean_range=50.6, var_range=0.5  → VETO
    #   smoke_gradient:  mean_range=32.1, var_range=11.1 → pass (gradient, not pattern)
    #   dense_smoke:     mean_range= 7.2, var_range=178  → pass (low mean_range)
    SMOKE_TEXTURE_MEAN_RANGE_THRESH: float = 10.0   # mean per-cell range below which not patterned
    SMOKE_TEXTURE_VAR_RANGE_THRESH: float = 5.0     # var-of-range above which pattern is non-uniform (gradient)

    # SMOKE_MOTION_CORROBORATION: veto borderline smoke candidates in fully static scenes.
    #   INTENTIONAL EXCEPTION to motion_gate.py's invariant that "the gate never affects the
    #   fire/smoke path". That invariant prohibits SKIPPING inference; this post-hoc vetoes a
    #   below-alert-floor candidate only, so it does not violate the inference-skip rule. Fire
    #   candidates are NEVER subject to this veto. Documented here explicitly so it is not
    #   silently reverted by someone enforcing the old invariant.
    SMOKE_MOTION_CORROBORATION: bool = True
    SMOKE_MOTION_STATIC_THRESHOLD: float = 0.0015  # motion_ratio below this = "essentially static"

    # SMOKE_ROI_REFINE_ENABLED: second-pass zoom re-inference for mid-band smoke candidates
    #   (candidate_floor ≤ evidence < alert_floor). Crops the box, upscales to ≥224 px, re-runs
    #   the ONNX model. Genuine thin plumes score equal or higher at higher resolution; static
    #   textures that were borderline at 320 px typically drop below the candidate floor.
    #   Cost: ~15–40 ms per candidate frame on CPU (only applies to borderline candidates).
    #   Disable on constrained hardware.
    SMOKE_ROI_REFINE_ENABLED: bool = True

    # Feature Toggles for Safety Engine
    ZONE_MONITORING_ENABLED: bool = True
    PERSON_DETECTION_ENABLED: bool = True
    SAFETY_INCIDENT_ENABLED: bool = True
    PPE_EVIDENCE_ENABLED: bool = True
    PPE_EMAIL_ALERT_ENABLED: bool = True
    PPE_WEBHOOK_ALERT_ENABLED: bool = False

    # ── General Temporal Verification (non-fire/smoke classes) ─────────────────────────────────
    VERIFICATION_MIN_CONFIDENCE: float = 0.50
    VERIFICATION_MIN_CONSECUTIVE_FRAMES: int = 7   # Lowered slightly from 8 for faster confirmation
    VERIFICATION_MIN_DURATION_SECONDS: float = 2.0
    VERIFICATION_COOLDOWN_SECONDS: float = 45.0
    # SPATIAL_IOU_THRESHOLD: 0.15 — more lenient spatial matching for moving objects
    # (smoke/fire can shift between frames; a detection 15% IoU away is likely the same object)
    SPATIAL_IOU_THRESHOLD: float = 0.15

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
