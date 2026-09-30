import base64
import math
import threading
import time
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, Request, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
import cv2
import numpy as np

from app.database.session import get_db
from app.models.detection import Detection
from app.schemas.common import PaginatedResponseModel, PaginationMeta
from app.schemas.detection import (
    DetectionResponse,
    AnalyzeImageRequest,
    AnalyzeImageResponse,
    AnalyzeSummary,
    AnalyzeWorkerResult,
    AnalyzeDetectionItem,
)

from app.api.v1.dependencies.permissions import RequirePermission
from app.models.user import User
from app.camera.pipeline import FramePipeline

router = APIRouter(prefix="/detections", tags=["Detections & AI History"])

_ANALYZE_PIPELINE: Optional[FramePipeline] = None
_ANALYZE_LOCK = threading.Lock()



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
    summary="Query Alert Events from MongoDB",
    description="Lists alert event documents stored in MongoDB with filtering and pagination."
)
async def list_mongo_detections(
    camera_id: Optional[int] = Query(None, description="Filter by Camera ID"),
    alert_type: Optional[str] = Query(None, description="Filter by alert type (fire, smoke, ppe_violation, etc.)"),
    date_from: Optional[datetime] = Query(None, description="Filter start date ISO 8601"),
    date_to: Optional[datetime] = Query(None, description="Filter end date ISO 8601"),
    limit: int = Query(50, ge=1, le=1000, description="Items per page"),
    skip: int = Query(0, ge=0, description="Pagination skip offset"),
    current_user: User = Depends(RequirePermission("detections:read"))
):
    from app.services.mongo_service import mongo_alert_service
    from app.schemas.mongo_docs import AlertEventQueryFilter
    from app.schemas.common import ResponseModel

    filter_params = AlertEventQueryFilter(
        camera_id=camera_id,
        alert_type=alert_type,
        start_time=date_from,
        end_time=date_to,
        limit=limit,
        skip=skip
    )
    result = await mongo_alert_service.query_alert_events(filter_params)
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


@router.post(
    "/analyze",
    response_model=AnalyzeImageResponse,
    summary="Unified Multi-Target Frame Analysis (Fire, Smoke, Safety Vest, Glasses)",
    description="Analyzes an uploaded image or base64 frame for Fire, Smoke, Person, Safety Vest, and Glasses with CCTV HUD overlays and PPE compliance."
)
async def analyze_frame(
    request: Request,
    required_equipment: Optional[str] = Query(None, description="Comma-separated required PPE equipment (e.g. 'vest,glasses')"),
    return_annotated: bool = Query(True, description="Whether to include CCTV HUD annotated JPEG preview as base64"),
    camera_id: int = Query(1, description="Camera ID context"),
    current_user: User = Depends(RequirePermission("detections:read"))
):
    image_bytes: Optional[bytes] = None
    effective_req: List[str] = ["vest", "glasses"]
    effective_annotated: bool = return_annotated
    effective_camera_id: int = camera_id

    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        form = await request.form()
        file_field = form.get("file")
        if file_field and hasattr(file_field, "read"):
            image_bytes = await file_field.read()
        req_form = form.get("required_equipment")
        if req_form and isinstance(req_form, str):
            effective_req = [r.strip().lower() for r in req_form.split(",") if r.strip()]
        if form.get("return_annotated") is not None:
            effective_annotated = str(form.get("return_annotated")).lower() in ["true", "1", "yes"]
        cam_id_raw = form.get("camera_id")
        if cam_id_raw is not None:
            try:
                effective_camera_id = int(str(cam_id_raw))
            except ValueError:
                pass
    elif "application/json" in content_type or not content_type:
        try:
            body = await request.json()
        except Exception:
            body = {}
        if isinstance(body, dict):
            b64_str = body.get("image_base64", "")
            if b64_str:
                if "," in b64_str:
                    b64_str = b64_str.split(",", 1)[1]
                try:
                    image_bytes = base64.b64decode(b64_str)
                except Exception:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid base64 image data")
            if body.get("required_equipment"):
                req_val = body.get("required_equipment")
                if isinstance(req_val, list):
                    effective_req = [str(r).strip().lower() for r in req_val if str(r).strip()]
                elif isinstance(req_val, str):
                    effective_req = [r.strip().lower() for r in req_val.split(",") if r.strip()]
            if body.get("return_annotated") is not None:
                effective_annotated = bool(body.get("return_annotated"))
            if body.get("camera_id") is not None:
                try:
                    effective_camera_id = int(body.get("camera_id"))
                except ValueError:
                    pass

    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No image provided. Please upload a file (multipart/form-data) or provide image_base64 in JSON payload."
        )

    np_arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if img is None or img.size == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not decode image from provided payload.")

    h, w = img.shape[:2]

    if required_equipment:
        effective_req = [r.strip().lower() for r in required_equipment.split(",") if r.strip()]

    t0 = time.perf_counter()
    global _ANALYZE_PIPELINE
    with _ANALYZE_LOCK:
        if _ANALYZE_PIPELINE is None:
            _ANALYZE_PIPELINE = FramePipeline(camera_id=effective_camera_id)
            _ANALYZE_PIPELINE.motion_gate.enabled = False
            _ANALYZE_PIPELINE.ppe_inference_interval_sec = 0.0
        pipeline = _ANALYZE_PIPELINE
        pipeline.reset()
        pipeline.set_ppe_profile({"required_equipment": effective_req})
        processed_frame = pipeline.process_frame(img, frame_id=1, fps=30.0)

    latency_ms = (time.perf_counter() - t0) * 1000.0

    dets_out: List[AnalyzeDetectionItem] = []
    fire_count = 0
    smoke_count = 0
    vest_count = 0
    glasses_count = 0

    for d in processed_frame.detections:
        lbl = d.label.lower()
        cat = "general"
        if lbl in ["fire", "smoke"]:
            cat = "fire_smoke"
            if lbl == "fire":
                fire_count += 1
            elif lbl == "smoke":
                smoke_count += 1
        elif lbl in ["vest", "safety_vest", "goggles", "glasses", "safety_glasses", "glass", "gloves", "shoes", "boots"]:
            cat = "ppe"
            if lbl in ["vest", "safety_vest"]:
                vest_count += 1
            elif lbl in ["goggles", "glasses", "safety_glasses", "glass"]:
                glasses_count += 1
        elif lbl in ["person", "worker"]:
            cat = "person"

        dets_out.append(AnalyzeDetectionItem(
            label=d.label,
            confidence=round(float(d.confidence), 4),
            bounding_box=d.bbox.to_dict(),
            category=cat,
            metadata=d.metadata or {}
        ))

    worker_analyses = processed_frame.metadata.get("worker_ppe_analyses", [])
    workers_out: List[AnalyzeWorkerResult] = []
    compliant_workers = 0
    violations_count = 0

    for w_item in worker_analyses:
        st = w_item.get("status", "UNKNOWN")
        if st == "PASS":
            compliant_workers += 1
        else:
            violations_count += 1
        workers_out.append(AnalyzeWorkerResult(
            person_id=w_item.get("person_id", 101),
            status=st,
            bounding_box=w_item.get("bounding_box", {}),
            detected_equipment=w_item.get("detected_equipment", []),
            missing_equipment=w_item.get("missing_equipment", []),
            confidence=float(w_item.get("confidence", 1.0))
        ))

    summary = AnalyzeSummary(
        fire_detected=(fire_count > 0),
        smoke_detected=(smoke_count > 0),
        total_persons=len(workers_out) or sum(1 for d in dets_out if d.category == "person"),
        compliant_workers=compliant_workers,
        violations_count=violations_count,
        total_vests=vest_count,
        total_glasses=glasses_count
    )

    annotated_b64: Optional[str] = None
    if effective_annotated and processed_frame.image is not None:
        ok, buf = cv2.imencode(".jpg", processed_frame.image, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if ok:
            annotated_b64 = "data:image/jpeg;base64," + base64.b64encode(buf).decode("utf-8")

    return AnalyzeImageResponse(
        success=True,
        timestamp=datetime.now(timezone.utc).isoformat(),
        image_width=w,
        image_height=h,
        inference_time_ms=round(latency_ms, 2),
        summary=summary,
        workers=workers_out,
        detections=dets_out,
        annotated_image_base64=annotated_b64
    )

