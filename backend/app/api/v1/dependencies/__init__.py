"""
API v1 Dependencies Initialization.
Exports get_current_user and RequirePermission.
"""

from fastapi import Depends
from app.api.v1.dependencies.permissions import get_current_user, RequirePermission, ROLE_PERMISSIONS

# Alias require_role to RequirePermission or helper function
def require_role(roles: list[str]):
    """
    Helper dependency restricting access to specified roles.
    """
    def _role_checker(user = Depends(get_current_user)):
        user_role = (user.role or "VIEWER").upper()
        if "*" in roles or user_role in [r.upper() for r in roles] or user_role == "ADMIN":
            return user
        from app.utils.exceptions import AppException
        from fastapi import status
        raise AppException(
            message=f"Access denied. Requires one of roles: {roles}",
            code="FORBIDDEN",
            status_code=status.HTTP_403_FORBIDDEN
        )
    return _role_checker

__all__ = ["get_current_user", "RequirePermission", "require_role", "ROLE_PERMISSIONS"]
