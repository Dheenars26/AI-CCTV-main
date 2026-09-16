"""
Physical DVR Service Layer (DVRService).
Handles DVR device registration, channel validation, credential encryption,
optimistic concurrency control (version_id), and deletion restriction policies.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.dvr import DVR, DVRStatus, DVRManufacturer
from app.models.camera import Camera
from app.schemas.dvr import DVRCreate, DVRUpdate
from app.utils.encryption import encrypt_credential, mask_credential
from app.services.audit_service import AuditService
from app.utils.exceptions import (
    ResourceNotFoundException,
    ValidationException,
    ConflictException
)


class DVRService:
    """
    Service managing DVR ORM operations with validation and audit logging.
    """

    def __init__(self, db: Session, dvr_manager: Optional[Any] = None):
        self.db = db
        self.dvr_manager = dvr_manager

    def list_dvrs(self) -> List[DVR]:
        return self.db.query(DVR).order_by(DVR.id.asc()).all()

    def get_dvr(self, dvr_id: int) -> DVR:
        dvr = self.db.query(DVR).filter(DVR.id == dvr_id).first()
        if not dvr:
            raise ResourceNotFoundException(f"DVR with ID {dvr_id} not found.")
        return dvr

    def create_dvr(self, payload: DVRCreate, username: str = "system") -> DVR:
        # Check duplicate name
        existing = self.db.query(DVR).filter(DVR.name == payload.name).first()
        if existing:
            raise ConflictException(f"DVR with name '{payload.name}' already exists.")

        encrypted_pass = encrypt_credential(payload.password)

        dvr = DVR(
            name=payload.name,
            management_host=payload.management_host,
            management_port=payload.management_port,
            rtsp_port=payload.rtsp_port,
            username=payload.username,
            credential_reference=encrypted_pass,
            manufacturer=payload.manufacturer,
            channels_count=payload.channels_count,
            enabled=payload.enabled,
            status=DVRStatus.UNKNOWN.value
        )
        self.db.add(dvr)
        self.db.flush()
        self.db.commit()

        if self.dvr_manager:
            self.dvr_manager.register_dvr(dvr)

        # Audit Event Log (Zero credential leak)
        AuditService.log_event(
            db=self.db,
            event_type="DVR_CREATED",
            username=username,
            details=f"Created DVR '{dvr.name}' (ID: {dvr.id}) at {dvr.management_host}:{dvr.management_port}"
        )

        return dvr

    def update_dvr(self, dvr_id: int, payload: DVRUpdate, username: str = "system") -> DVR:
        dvr = self.get_dvr(dvr_id)

        # Optimistic concurrency version check
        if payload.version_id is not None and payload.version_id != dvr.version_id:
            raise ConflictException("DVR configuration was updated by another administrator. Please refresh.")

        if payload.name and payload.name != dvr.name:
            existing = self.db.query(DVR).filter(DVR.name == payload.name).first()
            if existing:
                raise ConflictException(f"DVR name '{payload.name}' already in use.")
            dvr.name = payload.name

        if payload.management_host is not None:
            dvr.management_host = payload.management_host
        if payload.management_port is not None:
            dvr.management_port = payload.management_port
        if payload.rtsp_port is not None:
            dvr.rtsp_port = payload.rtsp_port
        if payload.username is not None:
            dvr.username = payload.username
        if payload.password is not None:
            dvr.credential_reference = encrypt_credential(payload.password)
            AuditService.log_event(self.db, "DVR_CREDENTIALS_CHANGED", username, f"DVR '{dvr.name}' password updated.")
        if payload.manufacturer is not None:
            dvr.manufacturer = payload.manufacturer
        if payload.channels_count is not None:
            dvr.channels_count = payload.channels_count
        if payload.enabled is not None:
            dvr.enabled = payload.enabled

        dvr.version_id += 1
        self.db.flush()
        self.db.commit()

        if self.dvr_manager:
            self.dvr_manager.register_dvr(dvr)

        AuditService.log_event(self.db, "DVR_UPDATED", username, f"Updated DVR '{dvr.name}' (v{dvr.version_id})")
        return dvr

    def delete_dvr(self, dvr_id: int, username: str = "system") -> bool:
        dvr = self.get_dvr(dvr_id)

        # Deletion Policy: Reject deletion if cameras are attached!
        attached_cameras = self.db.query(Camera).filter(Camera.dvr_id == dvr_id).count()
        if attached_cameras > 0:
            raise ValidationException(
                f"Cannot delete DVR '{dvr.name}'. {attached_cameras} camera(s) are attached to this DVR. Please detach cameras first."
            )

        if self.dvr_manager:
            self.dvr_manager.unregister_dvr(dvr_id)

        dvr_name = dvr.name
        self.db.delete(dvr)
        self.db.commit()

        AuditService.log_event(self.db, "DVR_DELETED", username, f"Deleted DVR '{dvr_name}' (ID: {dvr_id})")
        return True

    def validate_camera_dvr_channel(self, dvr_id: int, channel: int, current_camera_id: Optional[int] = None) -> None:
        """
        Validates camera-to-DVR channel relationship rules:
        1. Channel <= dvr.channels_count
        2. Rejects duplicate channel assignments on same DVR.
        """
        dvr = self.get_dvr(dvr_id)
        if channel < 1 or channel > dvr.channels_count:
            raise ValidationException(
                f"Invalid channel {channel} for DVR '{dvr.name}'. Max channels: {dvr.channels_count}."
            )

        query = self.db.query(Camera).filter(Camera.dvr_id == dvr_id, Camera.dvr_channel == channel)
        if current_camera_id:
            query = query.filter(Camera.id != current_camera_id)

        duplicate = query.first()
        if duplicate:
            raise ConflictException(
                f"Channel {channel} on DVR '{dvr.name}' is already assigned to camera '{duplicate.name}'."
            )
