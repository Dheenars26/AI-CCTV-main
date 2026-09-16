"""
Pydantic Schemas for Incident Evidence Metadata (EvidenceResponse).
Never exposes raw operating system file paths.
"""

from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    evidence_id: str = Field(..., description="Secure evidence token ID (e.g. ev_9f8e7d6c5b4a)")
    alert_id: str = Field(..., description="Associated Alert Event ID")
    camera_id: int = Field(..., description="Camera ID")
    snapshot_url: str = Field(..., description="Secure public JPEG snapshot URL")
    video_url: Optional[str] = Field(default=None, description="Secure public MP4 video clip URL")
    file_size_bytes: int = Field(default=0, description="Snapshot file size in bytes")
    metadata_envelope: Optional[Dict[str, Any]] = Field(default=None, description="JSON metadata envelope details")
    retention_until: Optional[datetime] = Field(default=None, description="Expiration date based on retention policy")
    created_at: datetime

