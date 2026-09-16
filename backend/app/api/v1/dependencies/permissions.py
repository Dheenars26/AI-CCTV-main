"""
Permission-Based Role-Based Access Control (RBAC) & Authentication Dependencies.
Maps roles (ADMIN, MANAGER, OPERATOR, VIEWER) to explicit permission strings.
Supports Bearer tokens in headers or cookies (never URL query parameters).
"""

from typing import List, Set, Optional, Callable, Dict
from fastapi import Depends, Header, Cookie, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import User
from app.utils.security import decode_jwt_token
from app.utils.exceptions import AppException
from app.services.audit_service import AuditService
from app.utils.logger import logger


# Explicit Permission Hierarchy Mapping per Role
ROLE_PERMISSIONS: Dict[str, Set[str]] = {
    "ADMIN": {"*"},  # Full administrative access
    "MANAGER": {
        "cameras:read",
        "cameras:write",
        "dvr:read",
        "dvr:create",
        "dvr:update",
        "dvr:delete",
        "dvr:health_read",
        "alerts:read",
        "alerts:write",
        "evidence:read",
        "evidence:purge",
        "reports:read",
        "system:status",
        "system:logs",
        "notifications:read",
        "notifications:write"
    },
    "OPERATOR": {
        "cameras:read",
        "cameras:status",
        "dvr:read",
        "dvr:health_read",
        "alerts:read",
        "alerts:write",
        "detections:read",
        "evidence:read",
        "notifications:read",
        "notifications:write"
    },
    "VIEWER": {
        "cameras:read",
        "cameras:status",
        "dvr:read",
        "detections:read",
        "system:status",
        "notifications:read"
    }
}


from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)
security_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    oauth_token: Optional[str] = Depends(oauth2_scheme),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    access_token_cookie: Optional[str] = Cookie(None, alias="access_token"),
    db: Session = Depends(get_db)
) -> User:
    """
    FastAPI dependency resolving the current authenticated user.
    Reads JWT token from OAuth2 Bearer, HTTPBearer header, or HttpOnly cookie.
    Query string tokens are strictly rejected for REST endpoints.
    """
    token = None

    auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
    if oauth_token:
        token = oauth_token.strip()
    elif credentials and credentials.credentials:
        token = credentials.credentials.strip()
    elif auth_header and auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "").strip()
    # 2. Extract from Cookie
    elif access_token_cookie:
        token = access_token_cookie

    if not token:
        raise AppException(
            message="Authentication credentials required. Missing Bearer Authorization header or cookie.",
            code="UNAUTHORIZED",
            status_code=status.HTTP_401_UNAUTHORIZED
        )

    # Decode and validate access token
    payload = decode_jwt_token(token, expected_type="access")
    if not payload or "sub" not in payload:
        raise AppException(
            message="Invalid, tampered, or expired access token.",
            code="INVALID_TOKEN",
            status_code=status.HTTP_401_UNAUTHORIZED
        )

    user_id = payload["sub"]
    user = db.query(User).filter(User.id == user_id).first()

    if not user or not user.is_active:
        raise AppException(
            message="User account disabled or not found.",
            code="ACCOUNT_DISABLED",
            status_code=status.HTTP_401_UNAUTHORIZED
        )

    if user.is_locked:
        raise AppException(
            message="User account is temporarily locked due to failed login attempts.",
            code="ACCOUNT_LOCKED",
            status_code=status.HTTP_403_FORBIDDEN
        )

    request.state.current_user = user
    return user


class RequirePermission:
    """
    FastAPI Dependency enforcement for specific permission strings.
    """

    def __init__(self, permission: str):
        self.permission = permission

    def __call__(self, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        user_role = (current_user.role or "VIEWER").upper()
        allowed_permissions = ROLE_PERMISSIONS.get(user_role, set())

        # Wildcard '*' grants all permissions (ADMIN)
        if "*" in allowed_permissions or self.permission in allowed_permissions:
            return current_user

        # Access Denied -> Record Audit Log
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("User-Agent")
        AuditService.log_event(
            db=db,
            event_type="PERMISSION_DENIED",
            actor_id=current_user.id,
            username=current_user.username,
            ip_address=client_ip,
            user_agent=user_agent,
            status="DENIED",
            details={
                "required_permission": self.permission,
                "user_role": user_role,
                "endpoint": request.url.path
            }
        )

        raise AppException(
            message=f"Access forbidden. Role '{user_role}' lacks required permission '{self.permission}'.",
            code="FORBIDDEN_PERMISSION",
            status_code=status.HTTP_403_FORBIDDEN
        )


class RequireRole:
    """
    FastAPI Dependency enforcement for specified role names.
    """

    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = [r.upper() for r in allowed_roles]

    def __call__(self, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        user_role = (current_user.role or "VIEWER").upper()
        if user_role in self.allowed_roles:
            return current_user

        client_ip = request.client.host if request.client else "unknown"
        AuditService.log_event(
            db=db,
            event_type="ROLE_ACCESS_DENIED",
            actor_id=current_user.id,
            username=current_user.username,
            ip_address=client_ip,
            status="DENIED",
            details={"user_role": user_role, "allowed_roles": self.allowed_roles, "endpoint": request.url.path}
        )

        raise AppException(
            message=f"Access forbidden. Requires one of roles: {self.allowed_roles}.",
            code="FORBIDDEN_ROLE",
            status_code=status.HTTP_403_FORBIDDEN
        )
