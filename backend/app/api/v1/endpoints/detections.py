"""
Raw AI Detections REST API Endpoints (/api/v1/detections).
Provides high-frequency prediction frame history queries with pagination and filters.
"""

import math
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database.session import get_db
from app.models.detection import Detection
from app.schemas.common import PaginatedResponseModel, PaginationMeta
from app.schemas.detection import DetectionResponse

from app.api.v1.dependencies.permissions import RequirePermission
from app.models.user import User

router = APIRouter(prefix="/detections", tags=["Detections & AI History"])


@router.get(
    "",
    response_model=PaginatedResponseModel[DetectionResponse],
    summary="Query Raw AI Prediction History",
    description="Lists raw frame AI predictions (fire, smoke) with pagination, filtering by camera, class, minimum confidence, and date range."
)
async def list_detections(
    camera_id: Optional[int] = Query(None, description="Filter by Camera ID"),
    class_name: Optional[str] = Query(None, pattern="^(fire|smoke)$", description="Filter by class (fire, smoke)"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum confidence threshold"),
    date_from: Optional[datetime] = Query(None, description="Filter start date ISO 8601"),
    date_to: Optional[datetime] = Query(None, description="Filter end date ISO 8601"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Item pagination offset index"),
    current_user: User = Depends(RequirePermission("detections:read")),
    db: Session = Depends(get_db)
):
    query = db.query(Detection)

    if camera_id is not None:
        query = query.filter(Detection.camera_id == camera_id)
    if class_name:
        query = query.filter(Detection.class_name == class_name.lower())
    if min_confidence is not None:
        query = query.filter(Detection.confidence >= min_confidence)
    if date_from:
        query = query.filter(Detection.timestamp >= date_from)
    if date_to:
        query = query.filter(Detection.timestamp <= date_to)

    total = query.count()
    items = query.order_by(desc(Detection.timestamp)).offset(offset).limit(limit).all()

    page = (offset // limit) + 1 if limit > 0 else 1
    pages = math.ceil(total / limit) if limit > 0 else 1

    formatted = [DetectionResponse.model_validate(d) for d in items]
    meta = PaginationMeta(total=total, limit=limit, offset=offset, page=page, pages=pages)

    return PaginatedResponseModel(data=formatted, pagination=meta)


@router.get(
    "/mongo",
    summary="Query High-Volume Detection Logs from MongoDB",
    description="Lists indexed detection event documents stored in MongoDB with filtering and pagination."
)
async def list_mongo_detections(
    camera_id: Optional[int] = Query(None, description="Filter by Camera ID"),
    class_name: Optional[str] = Query(None, description="Filter by class (fire, smoke, person, etc.)"),
    module: Optional[str] = Query(None, description="Filter by module (FIRE_SMOKE, PPE, RESTRICTED_ZONE)"),
    date_from: Optional[datetime] = Query(None, description="Filter start date ISO 8601"),
    date_to: Optional[datetime] = Query(None, description="Filter end date ISO 8601"),
    limit: int = Query(50, ge=1, le=1000, description="Items per page"),
    skip: int = Query(0, ge=0, description="Pagination skip offset"),
    current_user: User = Depends(RequirePermission("detections:read"))
):
    from app.services.mongo_service import mongo_detection_service
    from app.schemas.mongo_docs import MongoQueryFilter
    from app.schemas.common import ResponseModel

    filter_params = MongoQueryFilter(
        camera_id=camera_id,
        class_name=class_name,
        module=module,
        start_time=date_from,
        end_time=date_to,
        limit=limit,
        skip=skip
    )
    result = await mongo_detection_service.query_detection_history(filter_params)
    return ResponseModel(data=result)


@router.get(
    "/{id}",
    response_model=DetectionResponse,
    summary="Get Single Detection Frame Prediction",
    description="Retrieves a single raw AI detection prediction record by ID."
)
async def get_detection_by_id(
    id: str,
    current_user: User = Depends(RequirePermission("detections:read")),
    db: Session = Depends(get_db)
):
    from fastapi import HTTPException, status
    det = db.query(Detection).filter(Detection.id == id).first()
    if not det:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detection record not found")
    return DetectionResponse.model_validate(det)
