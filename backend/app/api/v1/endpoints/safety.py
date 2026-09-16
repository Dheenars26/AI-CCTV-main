"""
REST API v1 Endpoints for Workplace Safety Statistics & Reports.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func, desc, case

from app.database.session import get_db
from app.models.user import User
from app.models.ppe import PPEViolation, PPEProfile
from app.models.incident import Incident
from app.models.camera import Camera
from app.api.v1.dependencies import get_current_user
from app.services.incident_service import IncidentService
from app.schemas.incident import SafetyStatisticsResponse

router = APIRouter(tags=["Safety Reports & Metrics"])


@router.get("/safety/statistics", response_model=SafetyStatisticsResponse)
def get_safety_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = IncidentService(db)
    return service.get_safety_statistics()


@router.get("/reports/ppe/daily")
def get_daily_ppe_report(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns daily PPE compliance percentage and violation counts per day.
    """
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=days)

    stmt = select(
        func.date(PPEViolation.timestamp).label("day"),
        func.count(PPEViolation.id).label("total_evaluations"),
        func.sum(case((PPEViolation.status == "PASS", 1), else_=0)).label("pass_count"),
        func.sum(case((PPEViolation.status == "VIOLATION", 1), else_=0)).label("violation_count")
    ).where(PPEViolation.timestamp >= start_date).group_by("day").order_by("day")

    rows = db.execute(stmt).all()
    results = []
    for r in rows:
        total = r.total_evaluations or 0
        passes = r.pass_count or 0
        viols = r.violation_count or 0
        rate = round((passes / total) * 100.0, 1) if total > 0 else 100.0
        results.append({
            "date": str(r.day),
            "total_evaluations": total,
            "pass_count": passes,
            "violation_count": viols,
            "compliance_percentage": rate
        })
    return {"period_days": days, "daily_report": results}


@router.get("/reports/ppe/weekly")
def get_weekly_ppe_report(
    weeks: int = Query(4, ge=1, le=52),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns weekly PPE compliance trends.
    """
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(weeks=weeks)

    stmt = select(
        func.strftime("%Y-%W", PPEViolation.timestamp).label("week"),
        func.count(PPEViolation.id).label("total_evaluations"),
        func.sum(case((PPEViolation.status == "VIOLATION", 1), else_=0)).label("violation_count")
    ).where(PPEViolation.timestamp >= start_date).group_by("week").order_by("week")

    rows = db.execute(stmt).all()
    return {"period_weeks": weeks, "weekly_report": [{"week": str(r.week), "total": r.total_evaluations, "violations": r.violation_count} for r in rows]}


@router.get("/reports/incidents")
def get_incidents_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns breakdown of incidents by severity, type, and camera.
    """
    by_type = db.execute(
        select(Incident.incident_type, func.count(Incident.id)).group_by(Incident.incident_type)
    ).all()

    by_severity = db.execute(
        select(Incident.severity, func.count(Incident.id)).group_by(Incident.severity)
    ).all()

    by_camera = db.execute(
        select(Incident.camera_id, func.count(Incident.id)).group_by(Incident.camera_id)
    ).all()

    return {
        "by_incident_type": {r[0]: r[1] for r in by_type},
        "by_severity": {r[0]: r[1] for r in by_severity},
        "by_camera_id": {r[0]: r[1] for r in by_camera}
    }


@router.get("/reports/cameras")
def get_cameras_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns camera breakdown report showing most problematic cameras and active detectors.
    """
    cams = db.scalars(select(Camera)).all()
    cam_reports = []
    for c in cams:
        viols_count = db.scalar(
            select(func.count(PPEViolation.id)).where(PPEViolation.camera_id == c.id)
        ) or 0
        inc_count = db.scalar(
            select(func.count(Incident.id)).where(Incident.camera_id == c.id)
        ) or 0
        cam_reports.append({
            "camera_id": c.id,
            "name": c.name,
            "location": c.location,
            "enabled": c.enabled,
            "fire_smoke_enabled": c.fire_smoke_enabled,
            "ppe_enabled": c.ppe_enabled,
            "person_enabled": c.person_enabled,
            "zone_enabled": c.zone_enabled,
            "total_violations": viols_count,
            "total_incidents": inc_count
        })
    return {"cameras_report": sorted(cam_reports, key=lambda x: x["total_violations"], reverse=True)}
