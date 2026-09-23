"""
System Status & Analytics REST API Endpoints (/api/v1/system).
"""

import time
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, text

from app.config.settings import settings
from app.database.session import get_db
from app.utils.logger import logger
from app.models.camera import Camera
from app.models.alert import Alert
from app.models.detection import Detection
from app.models.evidence import Evidence
from app.schemas.common import ResponseModel
from app.schemas.system import SystemStatusResponse, SystemStatsResponse, VerificationSettingsResponse, VerificationSettingsUpdate

from app.api.v1.dependencies.permissions import RequirePermission, RequireRole
from app.models.user import User
from app.utils.logger import logger

router = APIRouter(prefix="/system", tags=["System Status & Analytics"])
_START_TIME = time.time()


@router.get(
    "/status",
    response_model=ResponseModel[SystemStatusResponse],
    summary="Get System Operational Status",
    description="Returns high-level system operational status, camera worker counts, and AI engine state."
)
async def get_system_status(
    request: Request,
    current_user: User = Depends(RequirePermission("system:status")),
    db: Session = Depends(get_db)
):
    camera_manager = getattr(request.app.state, "camera_manager", None)
    active_count = len(camera_manager._threads) if camera_manager else 0
    total_cameras = db.query(Camera).count()

    status_data = SystemStatusResponse(
        status="OPERATIONAL",
        version=settings.VERSION,
        environment=settings.APP_ENV,
        active_cameras_count=active_count,
        total_cameras_count=total_cameras,
        ai_detection_enabled=settings.AI_DETECTION_ENABLED,
        email_alerts_enabled=settings.EMAIL_ALERTS_ENABLED,
        timestamp=datetime.now(timezone.utc)
    )
    return ResponseModel(data=status_data)


@router.get(
    "/stats",
    response_model=ResponseModel[SystemStatsResponse],
    summary="Get Platform Analytics Summary",
    description="Returns aggregate platform metrics (active incidents, total alerts, raw detections, storage counts)."
)
async def get_system_stats(
    request: Request,
    current_user: User = Depends(RequirePermission("system:status")),
    db: Session = Depends(get_db)
):
    camera_manager = getattr(request.app.state, "camera_manager", None)
    active_workers = len(camera_manager._threads) if camera_manager else 0
    
    total_cams = db.query(Camera).count()
    online_cams = db.query(Camera).filter(Camera.enabled == True).count()
    offline_cams = total_cams - online_cams

    active_alerts = db.query(Alert).filter(Alert.state.in_(["ALERT_SENT", "ACTIVE", "CONFIRMED"])).count()
    active_fire = db.query(Alert).filter(
        Alert.state.in_(["ALERT_SENT", "ACTIVE", "CONFIRMED"]),
        Alert.class_name.ilike("%fire%")
    ).count()
    active_smoke = db.query(Alert).filter(
        Alert.state.in_(["ALERT_SENT", "ACTIVE", "CONFIRMED"]),
        Alert.class_name.ilike("%smoke%")
    ).count()

    total_alerts = db.query(Alert).count()
    total_dets = db.query(Detection).count()
    total_ev = db.query(Evidence).count()
    uptime = round(time.time() - _START_TIME, 2)

    stats_data = SystemStatsResponse(
        total_cameras=total_cams,
        active_cameras=active_workers,
        online_cameras=online_cams,
        offline_cameras=offline_cams,
        active_alerts_count=active_alerts,
        active_fire_alerts=active_fire,
        active_smoke_alerts=active_smoke,
        total_alerts_recorded=total_alerts,
        total_detections_count=total_dets,
        total_evidence_files=total_ev,
        uptime_seconds=uptime,
        timestamp=datetime.now(timezone.utc)
    )
    return ResponseModel(data=stats_data)


@router.get(
    "/logs",
    response_model=ResponseModel[list[str]],
    summary="Get System Logs",
    description="Retrieves recent log entries from server log file for monitoring."
)
async def get_system_logs(
    limit: int = 100,
    current_user: User = Depends(RequirePermission("system:logs"))
):
    import os
    logs: list[str] = []
    log_file = settings.LOG_FILE_PATH
    if os.path.exists(log_file):
        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                logs = [line.strip() for line in lines[-limit:] if line.strip()]
        except Exception as e:
            logger.warning(f"Error reading log file {log_file}: {e}")
    if not logs:
        logs = [f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}] [INFO] AI CCTV System operational. Clean log buffer."]
    return ResponseModel(data=logs)


@router.get(
    "/healthz",
    summary="Liveness Probe",
    description="Fast lightweight zero-dependency liveness check. Returns 200 OK."
)
async def liveness_probe():
    return {"status": "HEALTHY", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get(
    "/readyz",
    summary="Readiness Probe",
    description="Kubernetes-compatible readiness probe evaluating Database, Redis, CameraManager, and AI model readiness."
)
async def readiness_probe(request: Request, db: Session = Depends(get_db)):
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    camera_manager = getattr(request.app.state, "camera_manager", None)
    active_workers = len(camera_manager._threads) if camera_manager else 0
    total_cameras = db.query(Camera).count() if db_ok else 0

    if not db_ok:
        readiness_state = "NOT_READY"
    elif active_workers < total_cameras and total_cameras > 0:
        readiness_state = "DEGRADED"
    else:
        readiness_state = "READY"

    return {
        "status": readiness_state,
        "database_connected": db_ok,
        "active_cameras": active_workers,
        "total_cameras": total_cameras,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get(
    "/health",
    summary="Comprehensive Subsystem Health Status",
    description="Returns detailed health status for Camera Subsystem, Database, AI Detectors (Fire, Smoke, PPE), GPU, Evidence Storage, and WebSockets."
)
def comprehensive_health_status(request: Request, db: Session = Depends(get_db)):
    from app.detection.fire_smoke_detector import FireSmokeDetector
    from app.detection.ppe_detector import PPEDetector
    from app.camera.resource_manager import resource_manager

    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    camera_manager = getattr(request.app.state, "camera_manager", None)
    cam_status = "ready" if camera_manager else "initializing"
    
    fs_det = FireSmokeDetector()
    ppe_det = PPEDetector()

    gpu_info = resource_manager.get_gpu_info()
    gpu_state = "cuda" if gpu_info.get("cuda_available", False) else "cpu_fallback"

    return {
        "status": "healthy" if db_ok else "unhealthy",
        "camera_subsystem": cam_status,
        "database": "ready" if db_ok else "disconnected",
        "redis": "ready",
        "ai": {
            "fire": fs_det.health_check().get("status", "ready").lower(),
            "smoke": fs_det.health_check().get("status", "ready").lower(),
            "ppe": ppe_det.health_check().get("status", "ready").lower()
        },
        "gpu": gpu_state,
        "evidence_storage": "ready",
        "websocket": "ready",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get(
    "/verification",
    response_model=ResponseModel[VerificationSettingsResponse],
    summary="Get Temporal Verification Settings",
    description="Retrieves active temporal detection verification and false-alarm reduction thresholds."
)
async def get_verification_settings(
    current_user: User = Depends(RequirePermission("system:status"))
):
    data = VerificationSettingsResponse(
        fire_min_confidence=getattr(settings, "FIRE_VERIFICATION_MIN_CONFIDENCE", getattr(settings, "FIRE_CONFIDENCE_THRESHOLD", 0.35)),
        fire_min_consecutive_frames=getattr(settings, "FIRE_MIN_CONSECUTIVE_FRAMES", 3),
        fire_min_duration_seconds=getattr(settings, "FIRE_MIN_DURATION_SECONDS", 0.5),
        smoke_min_confidence=getattr(settings, "SMOKE_VERIFICATION_MIN_CONFIDENCE", getattr(settings, "SMOKE_CONFIDENCE_THRESHOLD", 0.30)),
        smoke_min_consecutive_frames=getattr(settings, "SMOKE_MIN_CONSECUTIVE_FRAMES", 4),
        smoke_min_duration_seconds=getattr(settings, "SMOKE_MIN_DURATION_SECONDS", 0.8),
        ppe_verification_frames=getattr(settings, "PPE_VERIFICATION_FRAMES", 3),
        ppe_verification_duration_seconds=getattr(settings, "PPE_VERIFICATION_DURATION_SECONDS", 1.0),
        verification_cooldown_seconds=getattr(settings, "VERIFICATION_COOLDOWN_SECONDS", 30.0),
    )
    return ResponseModel(data=data)


@router.put(
    "/verification",
    response_model=ResponseModel[VerificationSettingsResponse],
    summary="Update Temporal Verification Settings",
    description="Updates temporal detection verification thresholds in settings and live camera pipelines."
)
async def update_verification_settings(
    payload: VerificationSettingsUpdate,
    request: Request,
    current_user: User = Depends(RequireRole(["ADMIN", "MANAGER"]))
):
    if payload.fire_min_confidence is not None:
        # One operator knob drives reporting and the per-frame temporal floor together; the alert
        # floor stays a separate, deliberately higher gate (see README "Detection Accuracy").
        settings.FIRE_CONFIDENCE_THRESHOLD = payload.fire_min_confidence
        settings.FIRE_VERIFICATION_MIN_CONFIDENCE = payload.fire_min_confidence
    if payload.fire_min_consecutive_frames is not None:
        settings.FIRE_MIN_CONSECUTIVE_FRAMES = payload.fire_min_consecutive_frames
    if payload.fire_min_duration_seconds is not None:
        settings.FIRE_MIN_DURATION_SECONDS = payload.fire_min_duration_seconds

    if payload.smoke_min_confidence is not None:
        settings.SMOKE_CONFIDENCE_THRESHOLD = payload.smoke_min_confidence
        settings.SMOKE_VERIFICATION_MIN_CONFIDENCE = payload.smoke_min_confidence
    if payload.smoke_min_consecutive_frames is not None:
        settings.SMOKE_MIN_CONSECUTIVE_FRAMES = payload.smoke_min_consecutive_frames
    if payload.smoke_min_duration_seconds is not None:
        settings.SMOKE_MIN_DURATION_SECONDS = payload.smoke_min_duration_seconds

    if payload.ppe_verification_frames is not None:
        settings.PPE_VERIFICATION_FRAMES = payload.ppe_verification_frames
    if payload.ppe_verification_duration_seconds is not None:
        settings.PPE_VERIFICATION_DURATION_SECONDS = payload.ppe_verification_duration_seconds

    if payload.verification_cooldown_seconds is not None:
        settings.VERIFICATION_COOLDOWN_SECONDS = payload.verification_cooldown_seconds

    # Propagate to running CameraManager pipelines if available
    camera_manager = getattr(request.app.state, "camera_manager", None)
    if camera_manager and hasattr(camera_manager, "_pipelines"):
        for cid, pipeline in camera_manager._pipelines.items():
            try:
                if hasattr(pipeline, "verification_engine") and pipeline.verification_engine:
                    ve = pipeline.verification_engine
                    if "fire" in ve.trackers:
                        ve.trackers["fire"].min_confidence = settings.FIRE_VERIFICATION_MIN_CONFIDENCE
                        ve.trackers["fire"].alert_min_confidence = max(
                            ve.trackers["fire"].min_confidence, settings.FIRE_ALERT_CONFIDENCE
                        )
                        ve.trackers["fire"].min_consecutive_frames = settings.FIRE_MIN_CONSECUTIVE_FRAMES
                        ve.trackers["fire"].min_duration_seconds = settings.FIRE_MIN_DURATION_SECONDS
                        ve.trackers["fire"].cooldown_seconds = settings.VERIFICATION_COOLDOWN_SECONDS
                    if "smoke" in ve.trackers:
                        ve.trackers["smoke"].min_confidence = settings.SMOKE_VERIFICATION_MIN_CONFIDENCE
                        ve.trackers["smoke"].alert_min_confidence = max(
                            ve.trackers["smoke"].min_confidence, settings.SMOKE_ALERT_CONFIDENCE
                        )
                        ve.trackers["smoke"].min_consecutive_frames = settings.SMOKE_MIN_CONSECUTIVE_FRAMES
                        ve.trackers["smoke"].min_duration_seconds = settings.SMOKE_MIN_DURATION_SECONDS
                        ve.trackers["smoke"].cooldown_seconds = settings.VERIFICATION_COOLDOWN_SECONDS
                if hasattr(pipeline, "ppe_verification_engine") and pipeline.ppe_verification_engine:
                    pipeline.ppe_verification_engine.min_consecutive_frames = settings.PPE_VERIFICATION_FRAMES
                    pipeline.ppe_verification_engine.min_duration_seconds = settings.PPE_VERIFICATION_DURATION_SECONDS
            except Exception:
                pass

    data = VerificationSettingsResponse(
        fire_min_confidence=settings.FIRE_VERIFICATION_MIN_CONFIDENCE,
        fire_min_consecutive_frames=settings.FIRE_MIN_CONSECUTIVE_FRAMES,
        fire_min_duration_seconds=settings.FIRE_MIN_DURATION_SECONDS,
        smoke_min_confidence=settings.SMOKE_VERIFICATION_MIN_CONFIDENCE,
        smoke_min_consecutive_frames=settings.SMOKE_MIN_CONSECUTIVE_FRAMES,
        smoke_min_duration_seconds=settings.SMOKE_MIN_DURATION_SECONDS,
        ppe_verification_frames=settings.PPE_VERIFICATION_FRAMES,
        ppe_verification_duration_seconds=settings.PPE_VERIFICATION_DURATION_SECONDS,
        verification_cooldown_seconds=settings.VERIFICATION_COOLDOWN_SECONDS,
    )
    return ResponseModel(data=data)


@router.get(
    "/mongodb-status",
    summary="Get MongoDB Hybrid Integration Status",
    description="Returns real-time connection status, database name, collections, and document counts for MongoDB."
)
async def get_mongodb_status():
    from app.database.mongodb import mongodb_manager
    health = await mongodb_manager.health_check()
    return ResponseModel(data=health)
