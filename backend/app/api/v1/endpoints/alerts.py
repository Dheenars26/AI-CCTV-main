"""
Alert Incident REST API Endpoints (/api/v1/alerts).
Provides paginated query filters, single incident retrieval, and state acknowledgements.
"""

import math
from typing import Optional, List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.database.session import get_db
from app.models.alert import Alert
from app.models.notification import Notification
from app.models.evidence import Evidence
from app.schemas.common import ResponseModel, PaginatedResponseModel, PaginationMeta
from app.schemas.alert import AlertResponse, AlertUpdate
from app.utils.exceptions import AppException
from app.utils.logger import logger

from app.api.v1.dependencies.permissions import RequirePermission
from app.models.user import User

router = APIRouter(prefix="/alerts", tags=["Alerts & Incident Management"])


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _format_alert_response(alert: Alert) -> AlertResponse:
    evidence_token = alert.evidence.evidence_id if alert.evidence else None
    snapshot_url = f"/api/v1/evidence/{evidence_token}/snapshot" if evidence_token else None
    video_url = f"/api/v1/evidence/{evidence_token}/video" if (alert.evidence and alert.evidence.video_relative_path) else None

    cam_name = alert.camera.name if alert.camera else f"Camera #{alert.camera_id}"
    cam_location = alert.camera.location if (alert.camera and alert.camera.location) else "Unassigned"

    return AlertResponse(
        id=alert.id,
        camera_id=alert.camera_id,
        camera_name=cam_name,
        camera_location=cam_location,
        location=cam_location,
        class_name=alert.class_name,
        state=alert.state,
        consecutive_frames=alert.consecutive_frames,
        duration_seconds=alert.duration_seconds,
        max_confidence=alert.max_confidence,
        latest_confidence=alert.latest_confidence,
        evidence_id=evidence_token,
        snapshot_url=snapshot_url,
        video_url=video_url,
        start_time=_ensure_utc(alert.start_time) or datetime.now(timezone.utc),
        cleared_time=_ensure_utc(alert.cleared_time),
        remedial_action=alert.remedial_action,
        remedy_notes=alert.remedy_notes,
        resolved_by=alert.resolved_by,
        created_at=_ensure_utc(alert.created_at) or datetime.now(timezone.utc),
        updated_at=_ensure_utc(alert.updated_at) or datetime.now(timezone.utc)
    )


@router.get(
    "",
    response_model=PaginatedResponseModel[AlertResponse],
    summary="Query Verified Incidents",
    description="Lists verified fire and smoke alert incidents with pagination, filtering by camera, class_name, state, and date range."
)
async def list_alerts(
    camera_id: Optional[int] = Query(None, description="Filter by Camera ID"),
    class_name: Optional[str] = Query(None, description="Filter by class label (e.g. fire, smoke, ppe_violation)"),
    state: Optional[str] = Query(None, description="Filter by state (POSSIBLE, CONFIRMED, ALERT_SENT, ACTIVE, CLEARED, RESOLVED, ACKNOWLEDGED, NEW)"),
    status: Optional[str] = Query(None, description="Filter by status (alias for state)"),
    date_from: Optional[datetime] = Query(None, description="Filter start date ISO 8601"),
    date_to: Optional[datetime] = Query(None, description="Filter end date ISO 8601"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Item pagination offset index"),
    current_user: User = Depends(RequirePermission("alerts:read")),
    db: Session = Depends(get_db)
):
    query = db.query(Alert)

    if camera_id is not None:
        query = query.filter(Alert.camera_id == camera_id)
    if class_name:
        query = query.filter(Alert.class_name == class_name.lower())

    filter_state = state or status
    if filter_state:
        st_upper = filter_state.strip().upper()
        if st_upper == "NEW":
            query = query.filter(Alert.state.in_(["ALERT_SENT", "ACTIVE", "CONFIRMED", "POSSIBLE", "NEW"]))
        elif st_upper in ("RESOLVED", "CLEARED"):
            query = query.filter(Alert.state.in_(["RESOLVED", "CLEARED"]))
        elif st_upper == "ACKNOWLEDGED":
            query = query.filter(Alert.state == "ACKNOWLEDGED")
        else:
            query = query.filter(Alert.state == st_upper)

    if date_from:
        query = query.filter(Alert.start_time >= date_from)
    if date_to:
        query = query.filter(Alert.start_time <= date_to)

    total = query.count()
    alerts = query.order_by(desc(func.datetime(Alert.start_time))).offset(offset).limit(limit).all()

    page = (offset // limit) + 1 if limit > 0 else 1
    pages = math.ceil(total / limit) if limit > 0 else 1

    formatted_data = [_format_alert_response(a) for a in alerts]
    meta = PaginationMeta(total=total, limit=limit, offset=offset, page=page, pages=pages)

    return PaginatedResponseModel(data=formatted_data, pagination=meta)


@router.post(
    "/resolve-all",
    response_model=ResponseModel[dict],
    summary="Resolve All Active Alerts",
    description="Marks all active/unresolved fire and smoke alerts as RESOLVED immediately."
)
@router.patch(
    "/resolve-all",
    response_model=ResponseModel[dict],
    summary="Resolve All Active Alerts (Patch)",
    description="Marks all active/unresolved fire and smoke alerts as RESOLVED immediately."
)
async def resolve_all_alerts(
    current_user: User = Depends(RequirePermission("alerts:write")),
    db: Session = Depends(get_db)
):
    now = datetime.now(timezone.utc)
    from app.database.session import db_write_lock
    with db_write_lock:
        count = db.query(Alert).filter(
            ~Alert.state.in_(["RESOLVED", "CLEARED"])
        ).update(
            {
                Alert.state: "RESOLVED",
                Alert.cleared_time: now,
                Alert.updated_at: now,
                Alert.remedial_action: "All Incident Notifications Cleared",
                Alert.resolved_by: current_user.username
            },
            synchronize_session=False
        )
        db.commit()

    # Broadcast WebSocket notification so all frontend subscribers update instantly
    from app.websocket.connection_manager import manager as ws_manager
    await ws_manager.broadcast_event("alert_resolved", {"resolved_count": count, "state": "RESOLVED"})

    logger.info(f"Alerts API: User '{current_user.username}' resolved all {count} active alerts.")
    return ResponseModel(data={"resolved_count": count, "status": "RESOLVED"})


def _find_alert_by_id_or_alias(db: Session, alert_id: str) -> Optional[Alert]:
    """
    Resolves an Alert incident using multiple key formats:
    1. Exact match on Alert.id (e.g. ppe_evt_..., evt_...)
    2. Notification delivery audit ID (e.g. notif_...)
    3. Evidence token or Evidence UUID (e.g. ev_...)
    4. Fallback for client-side synthetic timestamp IDs (e.g. notif_17894...) or 'latest'
    """
    clean_id = alert_id.strip() if alert_id else ""
    if not clean_id:
        return None

    # 1. Direct match on Alert primary key
    alert = db.query(Alert).filter(Alert.id == clean_id).first()
    if alert:
        return alert

    # 2. Match by Notification delivery audit ID (e.g. notif_...)
    if clean_id.startswith("notif_"):
        notif = db.query(Notification).filter(Notification.id == clean_id).first()
        if notif and notif.alert_id:
            alert = db.query(Alert).filter(Alert.id == notif.alert_id).first()
            if alert:
                return alert

    # 3. Match by Evidence ID / Evidence token (e.g. ev_... or UUID)
    ev = db.query(Evidence).filter(
        (Evidence.evidence_id == clean_id) | (Evidence.id == clean_id)
    ).first()
    if ev and ev.alert_id:
        alert = db.query(Alert).filter(Alert.id == ev.alert_id).first()
        if alert:
            return alert

    # 4. Fallback for client-side synthetic timestamp IDs (e.g. notif_1789457050561) or "latest"
    if clean_id.startswith("notif_") or clean_id == "latest":
        active_alert = db.query(Alert).filter(
            ~Alert.state.in_(["RESOLVED", "CLEARED"])
        ).order_by(desc(Alert.start_time)).first()
        if active_alert:
            return active_alert
        latest_alert = db.query(Alert).order_by(desc(Alert.start_time)).first()
        if latest_alert:
            return latest_alert

    return None


@router.get(
    "/{alert_id}",
    response_model=ResponseModel[AlertResponse],
    summary="Get Alert Details",
    description="Retrieves a single verified alert incident by ID with secure evidence token links."
)
async def get_alert(
    alert_id: str,
    current_user: User = Depends(RequirePermission("alerts:read")),
    db: Session = Depends(get_db)
):
    alert = _find_alert_by_id_or_alias(db, alert_id)
    if not alert:
        raise AppException(
            message=f"Alert incident with ID '{alert_id}' not found",
            code="ALERT_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND
        )
    return ResponseModel(data=_format_alert_response(alert))


@router.patch(
    "/{alert_id}",
    response_model=ResponseModel[AlertResponse],
    summary="Update / Resolve Alert",
    description="Updates state of an active alert incident (e.g. set state to RESOLVED or CLEARED)."
)
@router.patch(
    "/{alert_id}/acknowledge",
    response_model=ResponseModel[AlertResponse],
    summary="Acknowledge / Clear Alert",
    description="Updates state of an active alert incident (e.g. set state to CLEARED)."
)
@router.post(
    "/{alert_id}/resolve",
    response_model=ResponseModel[AlertResponse],
    summary="Resolve Alert Direct",
    description="Marks a specific alert incident as RESOLVED."
)
async def acknowledge_alert(
    alert_id: str,
    payload: Optional[AlertUpdate] = None,
    current_user: User = Depends(RequirePermission("alerts:write")),
    db: Session = Depends(get_db)
):
    alert = _find_alert_by_id_or_alias(db, alert_id)
    if not alert:
        raise AppException(
            message=f"Alert incident with ID '{alert_id}' not found",
            code="ALERT_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND
        )

    target_state = payload.state.upper() if (payload and payload.state) else "RESOLVED"
    alert.state = target_state
    if target_state in ("CLEARED", "RESOLVED"):
        alert.cleared_time = datetime.now(timezone.utc)
        if payload and payload.remedial_action:
            alert.remedial_action = payload.remedial_action
        if payload and payload.remedy_notes:
            alert.remedy_notes = payload.remedy_notes
        alert.resolved_by = (payload.resolved_by if (payload and payload.resolved_by) else current_user.username)

    alert.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(alert)

    # Broadcast WebSocket notification for single alert resolution
    from app.websocket.connection_manager import manager as ws_manager
    await ws_manager.broadcast_event("alert_resolved", {"alert_id": alert.id, "state": target_state})

    return ResponseModel(data=_format_alert_response(alert))
