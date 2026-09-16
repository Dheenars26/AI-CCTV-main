"""
Pydantic Schemas for Authentication, Tokens, CSRF, and User Management.
Never exposes password hashes or raw secrets.
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator


class LoginRequest(BaseModel):
    username: str = Field(..., json_schema_extra={"example": "admin"}, description="Account username or email")
    password: str = Field(..., json_schema_extra={"example": "secretpassword"}, description="Account plain text password")


class RefreshTokenRequest(BaseModel):
    refresh_token: Optional[str] = Field(default=None, description="Optional refresh token in body if cookies not used")


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique User UUID")
    username: str = Field(..., description="Username identifier")
    email: str = Field(..., description="Account email address")
    full_name: Optional[str] = Field(default=None, description="Full display name")
    role: str = Field(..., description="User role (ADMIN, MANAGER, OPERATOR, VIEWER)")
    is_active: bool = Field(..., description="Account active status flag")
    is_superuser: bool = Field(..., description="Superuser privileges flag")
    created_at: datetime
    updated_at: datetime

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, v: str) -> str:
        return v.upper() if isinstance(v, str) else v


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT Bearer access token")
    token_type: str = Field(default="bearer", description="Token authentication type")
    expires_in: int = Field(default=1800, description="Access token expiration in seconds (30 minutes)")
    csrf_token: str = Field(..., description="CSRF Double-Submit Token")
    user: UserResponse = Field(..., description="Authenticated user profile")


class WSTicketResponse(BaseModel):
    ticket: str = Field(..., description="Single-use WebSocket handshake ticket (10s TTL)")
    expires_in: int = Field(default=10, description="Ticket validity in seconds")


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    email: str = Field(..., description="Account email address")
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = None
    role: str = Field(default="OPERATOR", pattern="^(ADMIN|MANAGER|OPERATOR|VIEWER|admin|manager|operator|viewer)$")


class UserProfileUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
