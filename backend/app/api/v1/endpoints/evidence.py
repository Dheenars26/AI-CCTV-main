"""
Incident Evidence Media & Metadata REST API Endpoints (/api/v1/evidence).
Serves JPEG snapshot images and MP4 video clips via secure token URLs without exposing raw OS filesystem paths.
"""

import os
import math
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database.session import get_db
from app.models.evidence import Evidence
from app.schemas.common import ResponseModel, PaginatedResponseModel, PaginationMeta
from app.schemas.evidence import EvidenceResponse
from app.recording.evidence_service import EvidenceService
from app.utils.exceptions import AppException
from app.utils.logger import logger

from app.api.v1.dependencies.permissions import RequirePermission
from app.models.user import User

router = APIRouter(prefix="/evidence", tags=["Evidence & Video Archiving"])
evidence_service = EvidenceService()


def _format_evidence_response(ev: Evidence) -> EvidenceResponse:
    snap_url = f"/api/v1/evidence/{ev.evidence_id}/snapshot"
    vid_url = f"/api/v1/evidence/{ev.evidence_id}/video" if ev.video_relative_path else None

    return EvidenceResponse(
        evidence_id=ev.evidence_id,
        alert_id=ev.alert_id,
        camera_id=ev.camera_id,
        snapshot_url=snap_url,
        video_url=vid_url,
        file_size_bytes=ev.file_size_bytes,
        metadata_envelope=ev.metadata_envelope,
        retention_until=ev.retention_until,
        created_at=ev.created_at
    )


@router.get(
    "",
    response_model=PaginatedResponseModel[EvidenceResponse],
    summary="List Archived Evidence Envelopes",
    description="Lists evidence metadata records with pagination and filtering by camera_id or alert_id."
)
async def list_evidence(
    camera_id: Optional[int] = Query(None, description="Filter by Camera ID"),
    alert_id: Optional[str] = Query(None, description="Filter by Alert Event ID"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Item pagination offset index"),
    current_user: User = Depends(RequirePermission("evidence:read")),
    db: Session = Depends(get_db)
):
    query = db.query(Evidence)
    if camera_id is not None:
        query = query.filter(Evidence.camera_id == camera_id)
    if alert_id:
        query = query.filter(Evidence.alert_id == alert_id)

    total = query.count()
    items = query.order_by(desc(Evidence.created_at)).offset(offset).limit(limit).all()

    page = (offset // limit) + 1 if limit > 0 else 1
    pages = math.ceil(total / limit) if limit > 0 else 1

    formatted = [_format_evidence_response(e) for e in items]
    meta = PaginationMeta(total=total, limit=limit, offset=offset, page=page, pages=pages)

    return PaginatedResponseModel(data=formatted, pagination=meta)


@router.get(
    "/{evidence_id}",
    response_model=ResponseModel[EvidenceResponse],
    summary="Get Evidence Metadata",
    description="Retrieves evidence record details by secure token ID."
)
async def get_evidence_details(
    evidence_id: str,
    current_user: User = Depends(RequirePermission("evidence:read")),
    db: Session = Depends(get_db)
):
    ev = db.query(Evidence).filter(Evidence.evidence_id == evidence_id).first()
    if not ev:
        raise AppException(
            message=f"Evidence record with token '{evidence_id}' not found",
            code="EVIDENCE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND
        )
    return ResponseModel(data=_format_evidence_response(ev))


@router.get(
    "/{evidence_id}/snapshot",
    summary="Download JPEG Incident Snapshot",
    description="Serves high-resolution JPEG evidence snapshot image bytes securely.",
    responses={
        200: {
            "content": {"image/jpeg": {}},
            "description": "JPEG snapshot image payload"
        }
    }
)
async def get_evidence_snapshot(
    evidence_id: str,
    db: Session = Depends(get_db)
):
    # 1. Try registry lookup
    physical_path = evidence_service.get_physical_snapshot_path(evidence_id)
    
    # 2. Try DB fallback
    if not physical_path or not os.path.exists(physical_path):
        ev = db.query(Evidence).filter(Evidence.evidence_id == evidence_id).first()
        if ev:
            full_path = os.path.join(evidence_service.base_storage_dir, ev.snapshot_relative_path)
            if os.path.exists(full_path):
                physical_path = full_path

    if not physical_path or not os.path.exists(physical_path):
        raise AppException(
            message=f"Evidence snapshot file for token '{evidence_id}' not found on storage",
            code="SNAPSHOT_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND
        )

    return FileResponse(path=physical_path, media_type="image/jpeg", filename=f"{evidence_id}.jpg")


@router.get(
    "/{evidence_id}/video",
    summary="Stream Video Clip",
    description="Streams archived incident video clip with HTTP byte-range support for HTML5 video playback.",
    responses={
        200: {
            "content": {"video/mp4": {}, "video/webm": {}},
            "description": "Video clip stream payload"
        },
        206: {
            "content": {"video/mp4": {}, "video/webm": {}},
            "description": "Partial Content byte-range video stream"
        }
    }
)
async def get_evidence_video(
    evidence_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    physical_path = evidence_service.get_physical_video_path(evidence_id)

    if not physical_path or not os.path.exists(physical_path):
        ev = db.query(Evidence).filter(Evidence.evidence_id == evidence_id).first()
        if ev and ev.video_relative_path:
            full_path = os.path.join(evidence_service.base_storage_dir, ev.video_relative_path)
            if os.path.exists(full_path):
                physical_path = full_path

    if not physical_path or not os.path.exists(physical_path):
        raise AppException(
            message=f"Evidence video clip file for token '{evidence_id}' not found on storage",
            code="VIDEO_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND
        )

    ext = os.path.splitext(physical_path)[1].lower()
    media_type = "video/webm" if ext == ".webm" else "video/mp4"

    # Support HTTP 206 Byte-Range requests required by Chrome, Edge, and Safari HTML5 video players
    file_size = os.path.getsize(physical_path)
    range_header = request.headers.get("range")

    if range_header:
        try:
            bytes_type, byte_range = range_header.split("=")
            if bytes_type.strip() == "bytes":
                start_str, end_str = byte_range.split("-")
                start = int(start_str) if start_str else 0
                end = int(end_str) if end_str else file_size - 1
                end = min(end, file_size - 1)

                if start <= end and start < file_size:
                    chunk_size = (end - start) + 1
                    with open(physical_path, "rb") as f:
                        f.seek(start)
                        data = f.read(chunk_size)

                    headers = {
                        "Content-Range": f"bytes {start}-{end}/{file_size}",
                        "Accept-Ranges": "bytes",
                        "Content-Length": str(chunk_size),
                        "Content-Type": media_type,
                    }
                    return Response(content=data, status_code=206, headers=headers)
        except Exception as range_err:
            logger.warning(f"Evidence API: Byte-range streaming notice: {str(range_err)}")

    return FileResponse(
        path=physical_path,
        media_type=media_type,
        filename=f"{evidence_id}{ext}",
        headers={"Accept-Ranges": "bytes"}
    )


@router.delete(
    "",
    response_model=ResponseModel[dict],
    summary="Bulk Delete/Purge All Evidence (MANAGER/ADMIN Only)",
    description="Purges ALL evidence records, snapshot images, and video clips from disk storage and DB."
)
async def purge_all_evidence(
    current_user: User = Depends(RequirePermission("evidence:purge")),
    db: Session = Depends(get_db)
):
    count = evidence_service.purge_all_evidence(db=db)
    return ResponseModel(data={"message": f"Successfully purged all evidence gallery records and files ({count} file(s) removed)."})


@router.delete(
    "/{evidence_id}",
    response_model=ResponseModel[dict],
    summary="Purge Evidence File (MANAGER/ADMIN Only)",
    description="Purges evidence record and files from disk storage. Requires evidence:purge permission."
)
async def purge_evidence(
    evidence_id: str,
    current_user: User = Depends(RequirePermission("evidence:purge")),
    db: Session = Depends(get_db)
):
    ev = db.query(Evidence).filter(Evidence.evidence_id == evidence_id).first()
    if not ev:
        raise AppException(
            message=f"Evidence record with token '{evidence_id}' not found",
            code="EVIDENCE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND
        )

    evidence_service.purge_evidence_item(evidence_id, db=db)
    return ResponseModel(data={"message": f"Evidence '{evidence_id}' purged successfully."})
