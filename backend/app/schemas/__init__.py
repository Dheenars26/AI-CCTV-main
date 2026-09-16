"""
Pydantic Schemas Package Initialization.
Defines data models, request/response contracts, and validation rules.
"""

from app.schemas.common import ResponseModel, PaginatedResponseModel, PaginationMeta, ErrorDetail, ErrorResponse
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse, UserCreate
from app.schemas.camera import CameraCreate, CameraUpdate, CameraResponse, CameraRuntimeStateResponse
from app.schemas.detection import DetectionResponse
from app.schemas.alert import AlertResponse, AlertUpdate
from app.schemas.evidence import EvidenceResponse
from app.schemas.notification import NotificationResponse
from app.schemas.system import SystemStatusResponse, SystemStatsResponse
from app.schemas.websocket import (
    WSEventEnvelope,
    FireDetectedPayload,
    SmokeDetectedPayload,
    AlertStatePayload,
    CameraStatusPayload,
    SystemStatusPayload
)
from app.schemas.stream import StreamConfigResponse, StreamSessionTokenPayload
from app.schemas.dvr import DVRCreate, DVRUpdate, DVRResponse, DVRHealthResponse
from app.schemas.ppe import (
    PPEProfileCreate,
    PPEProfileUpdate,
    PPEProfileResponse,
    PPEViolationResponse,
    PPEViolationPaginatedResponse,
    PPERequirementSchema,
)
from app.schemas.zone import SafetyZoneCreate, SafetyZoneUpdate, SafetyZoneResponse
from app.schemas.incident import (
    IncidentStatusUpdate,
    IncidentResponse,
    IncidentPaginatedResponse,
    SafetyStatisticsResponse,
)

__all__ = [
    "ResponseModel",
    "PaginatedResponseModel",
    "PaginationMeta",
    "ErrorDetail",
    "ErrorResponse",
    "LoginRequest",
    "TokenResponse",
    "UserResponse",
    "UserCreate",
    "CameraCreate",
    "CameraUpdate",
    "CameraResponse",
    "CameraRuntimeStateResponse",
    "DetectionResponse",
    "AlertResponse",
    "AlertUpdate",
    "EvidenceResponse",
    "NotificationResponse",
    "SystemStatusResponse",
    "SystemStatsResponse",
    "WSEventEnvelope",
    "FireDetectedPayload",
    "SmokeDetectedPayload",
    "AlertStatePayload",
    "CameraStatusPayload",
    "SystemStatusPayload",
    "StreamConfigResponse",
    "StreamSessionTokenPayload",
    "DVRCreate",
    "DVRUpdate",
    "DVRResponse",
    "DVRHealthResponse",
    "PPEProfileCreate",
    "PPEProfileUpdate",
    "PPEProfileResponse",
    "PPEViolationResponse",
    "PPEViolationPaginatedResponse",
    "PPERequirementSchema",
    "SafetyZoneCreate",
    "SafetyZoneUpdate",
    "SafetyZoneResponse",
    "IncidentStatusUpdate",
    "IncidentResponse",
    "IncidentPaginatedResponse",
    "SafetyStatisticsResponse",
]
