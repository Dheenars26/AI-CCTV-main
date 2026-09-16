"""
Exception handling module.
Defines custom exception classes and global FastAPI exception handlers
that produce standardized JSON error responses with correlation IDs.
"""

from typing import Any, Optional
from datetime import datetime, date
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException
from app.utils.logger import logger
from app.middleware.request_id import get_request_id


class AppException(Exception):
    """
    Base application exception for domain errors.
    """
    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_SERVER_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Any] = None
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details


class DatabaseException(AppException):
    """
    Exception raised during database operations.
    """
    def __init__(self, message: str = "Database transaction failed", details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="DATABASE_ERROR",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=details
        )


class CameraException(AppException):
    """
    Exception raised during camera or RTSP stream operations.
    """
    def __init__(self, message: str = "Camera operation failed", details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="CAMERA_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details
        )


class ResourceNotFoundException(AppException):
    def __init__(self, message: str = "Resource not found", details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details=details
        )


class ValidationException(AppException):
    def __init__(self, message: str = "Validation failed", details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details
        )


class ConflictException(AppException):
    def __init__(self, message: str = "Conflict detected", details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="CONFLICT",
            status_code=status.HTTP_409_CONFLICT,
            details=details
        )


def _make_json_serializable(obj: Any) -> Any:
    """
    Recursively converts non-JSON-serializable objects (like bytes, datetime, custom objects) into serializable representations.
    """
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(k): _make_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_make_json_serializable(v) for v in obj]
    if hasattr(obj, "model_dump"):
        return _make_json_serializable(obj.model_dump())
    if hasattr(obj, "dict") and callable(getattr(obj, "dict")):
        return _make_json_serializable(obj.dict())
    return str(obj)


def build_error_response(
    code: str,
    message: str,
    status_code: int,
    details: Optional[Any] = None,
    request: Optional[Request] = None
) -> JSONResponse:
    """
    Helper to construct standard JSON error envelope with guaranteed CORS headers.
    """
    req_id = get_request_id()
    sanitized_details = _make_json_serializable(details) if details is not None else None
    
    headers: dict[str, str] = {}
    if request:
        origin = request.headers.get("origin")
        if origin:
            headers["Access-Control-Allow-Origin"] = origin
            headers["Access-Control-Allow-Credentials"] = "true"
            headers["Access-Control-Allow-Headers"] = "*"
            headers["Access-Control-Allow-Methods"] = "*"
            headers["Vary"] = "Origin"

    return JSONResponse(
        status_code=status_code,
        headers=headers,
        content={
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "details": sanitized_details
            },
            "request_id": req_id
        }
    )


def register_exception_handlers(app: FastAPI) -> None:
    """
    Registers custom exception handlers on the FastAPI application instance.
    """

    @app.exception_handler(AppException)
    async def custom_app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        logger.error(f"Application Exception [{exc.code}]: {exc.message} - Details: {exc.details}")
        return build_error_response(
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
            request=request
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        logger.warning(f"HTTP Exception [{exc.status_code}]: {exc.detail}")
        code_str = "HTTP_ERROR"
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            code_str = "NOT_FOUND"
        elif exc.status_code == status.HTTP_401_UNAUTHORIZED:
            code_str = "UNAUTHORIZED"
        elif exc.status_code == status.HTTP_403_FORBIDDEN:
            code_str = "FORBIDDEN"

        return build_error_response(
            code=code_str,
            message=str(exc.detail),
            status_code=exc.status_code,
            request=request
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        logger.warning(f"Request Validation Error: {exc.errors()}")
        return build_error_response(
            code="VALIDATION_ERROR",
            message="Invalid request input payload or parameters",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=exc.errors(),
            request=request
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.critical(f"Unhandled Internal Server Exception: {str(exc)}", exc_info=True)
        return build_error_response(
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected internal server error occurred",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            request=request
        )
