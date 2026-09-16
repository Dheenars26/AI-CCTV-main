"""
REST API v1 Endpoints for PPE Profiles and PPE Violations.
Requires standard authentication & RBAC authorization.
"""

import math
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import User
from app.api.v1.dependencies import get_current_user, require_role
from app.services.ppe_service import PPEService
from app.schemas.ppe import (
    PPEProfileCreate,
    PPEProfileUpdate,
    PPEProfileResponse,
    PPEViolationResponse,
    PPEViolationPaginatedResponse
)

router = APIRouter(tags=["PPE Compliance"])


@router.get("/ppe/profiles", response_model=List[PPEProfileResponse])
def list_ppe_profiles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = PPEService(db)
    service.init_default_profiles_if_empty()
    return service.get_profiles()


@router.post("/ppe/profiles", response_model=PPEProfileResponse, status_code=status.HTTP_201_CREATED)
def create_ppe_profile(
    payload: PPEProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"]))
):
    service = PPEService(db)
    existing = service.get_profile_by_name(payload.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"PPE Profile with name '{payload.name}' already exists."
        )

    return service.create_profile(
        name=payload.name,
        required_equipment=payload.required_equipment,
        optional_equipment=payload.optional_equipment,
        description=payload.description,
        user_id=current_user.id
    )


@router.get("/ppe/profiles/{id}", response_model=PPEProfileResponse)
def get_ppe_profile(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = PPEService(db)
    profile = service.get_profile(id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PPE Profile not found")
    return profile


@router.patch("/ppe/profiles/{id}", response_model=PPEProfileResponse)
def update_ppe_profile(
    id: int,
    payload: PPEProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"]))
):
    service = PPEService(db)
    updated = service.update_profile(
        profile_id=id,
        name=payload.name,
        required_equipment=payload.required_equipment,
        optional_equipment=payload.optional_equipment,
        description=payload.description,
        user_id=current_user.id
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PPE Profile not found")
    return updated


@router.delete("/ppe/profiles/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ppe_profile(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"]))
):
    service = PPEService(db)
    success = service.delete_profile(id, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PPE Profile not found")


@router.get("/ppe/violations", response_model=PPEViolationPaginatedResponse)
def list_ppe_violations(
    camera_id: Optional[int] = Query(None, description="Filter by Camera ID"),
    zone_id: Optional[int] = Query(None, description="Filter by Zone ID"),
    status: Optional[str] = Query(None, description="Filter by Status (PASS, VIOLATION)"),
    severity: Optional[str] = Query(None, description="Filter by Severity"),
    date_from: Optional[datetime] = Query(None, description="Filter start date"),
    date_to: Optional[datetime] = Query(None, description="Filter end date"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = PPEService(db)
    items, total = service.get_violations(
        camera_id=camera_id,
        zone_id=zone_id,
        status=status,
        severity=severity,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size
    )
    pages = math.ceil(total / page_size) if total > 0 else 1
    return PPEViolationPaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages
    )


@router.get("/ppe/violations/{id}", response_model=PPEViolationResponse)
def get_ppe_violation(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = PPEService(db)
    viol = service.get_violation(id)
    if not viol:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PPE Violation record not found")
    return viol


@router.get("/ppe/events")
def list_ppe_events(
    camera_id: Optional[int] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.models.ppe import PPEViolation
    query = db.query(PPEViolation)
    if camera_id is not None:
        query = query.filter(PPEViolation.camera_id == camera_id)
    items = query.order_by(PPEViolation.timestamp.desc()).limit(limit).all()
    return {"events": [PPEViolationResponse.model_validate(i) for i in items]}


@router.get("/ppe/compliance")
def get_ppe_compliance_summary(
    camera_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.models.ppe import PPEViolation
    from sqlalchemy import func
    query = db.query(PPEViolation)
    if camera_id is not None:
        query = query.filter(PPEViolation.camera_id == camera_id)
    
    total = query.count()
    pass_cnt = query.filter(PPEViolation.status == "PASS").count()
    viol_cnt = query.filter(PPEViolation.status == "VIOLATION").count()
    rate = round((pass_cnt / total) * 100.0, 1) if total > 0 else 100.0

    return {
        "camera_id": camera_id,
        "total_evaluations": total,
        "pass_count": pass_cnt,
        "violation_count": viol_cnt,
        "compliance_percentage": rate
    }


@router.get("/ppe/config")
def get_ppe_configuration(
    current_user: User = Depends(get_current_user)
):
    from app.config.settings import settings
    return {
        "ai_ppe_enabled": settings.AI_PPE_ENABLED,
        "ppe_confidence_threshold": settings.PPE_CONFIDENCE_THRESHOLD,
        "ppe_iou_threshold": settings.PPE_IOU_THRESHOLD,
        "ppe_verification_frames": settings.PPE_VERIFICATION_FRAMES,
        "ppe_verification_duration_seconds": settings.PPE_VERIFICATION_DURATION_SECONDS,
        "ppe_alert_cooldown_seconds": settings.PPE_ALERT_COOLDOWN_SECONDS,
        "ppe_device": settings.PPE_DEVICE
    }


@router.post("/ppe/config")
def update_ppe_configuration(
    payload: dict,
    current_user: User = Depends(require_role(["ADMIN"]))
):
    from app.config.settings import settings
    if "ai_ppe_enabled" in payload:
        settings.AI_PPE_ENABLED = bool(payload["ai_ppe_enabled"])
    if "ppe_confidence_threshold" in payload:
        settings.PPE_CONFIDENCE_THRESHOLD = float(payload["ppe_confidence_threshold"])
    if "ppe_verification_frames" in payload:
        settings.PPE_VERIFICATION_FRAMES = int(payload["ppe_verification_frames"])
    if "ppe_alert_cooldown_seconds" in payload:
        settings.PPE_ALERT_COOLDOWN_SECONDS = float(payload["ppe_alert_cooldown_seconds"])
        
    return {
        "status": "SUCCESS",
        "updated_config": {
            "ai_ppe_enabled": settings.AI_PPE_ENABLED,
            "ppe_confidence_threshold": settings.PPE_CONFIDENCE_THRESHOLD,
            "ppe_verification_frames": settings.PPE_VERIFICATION_FRAMES,
            "ppe_alert_cooldown_seconds": settings.PPE_ALERT_COOLDOWN_SECONDS
        }
    }
