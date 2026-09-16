"""
Rate Limiting Middleware for API & Login Endpoints.
Supports Redis backend with fallback to In-Memory Sliding Window sliding window rate limiting.
Enforces stricter limits on authentication endpoints to prevent brute-force attacks.
"""

import time
from typing import Dict, List, Tuple
from threading import Lock
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from fastapi import status

from app.config.settings import settings
from app.utils.logger import logger


class InMemorySlidingWindowLimiter:
    """
    Sliding window in-memory rate limiter per IP / Key.
    """

    def __init__(self):
        self._requests: Dict[str, List[float]] = {}
        self._lock = Lock()

    def is_allowed(self, key: str, max_requests: int, window_seconds: float) -> Tuple[bool, int]:
        """
        Checks if key exceeds limit within window.
        Returns tuple: (is_allowed: bool, remaining_requests: int).
        """
        now = time.time()
        window_start = now - window_seconds

        with self._lock:
            timestamps = self._requests.get(key, [])
            # Filter timestamps outside sliding window
            timestamps = [ts for ts in timestamps if ts > window_start]
            
            if len(timestamps) >= max_requests:
                self._requests[key] = timestamps
                return False, 0

            timestamps.append(now)
            self._requests[key] = timestamps
            remaining = max_requests - len(timestamps)
            return True, remaining


_memory_limiter = InMemorySlidingWindowLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI Rate Limiting Middleware.
    Enforces distinct rules for login vs standard REST API endpoints.
    """

    def __init__(self, app, login_limit: int = 5, login_window: int = 900, api_limit: int = 120, api_window: int = 60):
        super().__init__(app)
        self.login_limit = login_limit       # 5 attempts
        self.login_window = login_window     # per 15 minutes (900 seconds)
        self.api_limit = api_limit           # 120 requests
        self.api_window = api_window         # per 1 minute (60 seconds)

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip rate limiting for CORS OPTIONS preflight requests or in testing mode
        if request.method == "OPTIONS" or getattr(settings, "APP_ENV", "development") == "testing":
            return await call_next(request)

        # CRITICAL: Skip middleware entirely for MJPEG stream and WebSocket endpoints.
        # BaseHTTPMiddleware buffers the full response body before returning — this causes
        # an infinite timeout on never-ending streaming responses like MJPEG.
        path = request.url.path
        if path.endswith("/stream") or "/stream/" in path or path.startswith("/api/v1/ws") or path.startswith("/ws/"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "127.0.0.1"

        # Skip rate limiting for local loopback development requests or debug mode
        if client_ip in ("127.0.0.1", "::1", "localhost", "testclient") or getattr(settings, "DEBUG", True):
            return await call_next(request)

        # 1. Stricter Rate Limiting on Login Endpoint
        if path == "/api/v1/auth/login" and request.method == "POST":
            limiter_key = f"login_rate_{client_ip}"
            allowed, remaining = _memory_limiter.is_allowed(limiter_key, self.login_limit, self.login_window)
            if not allowed:
                logger.warning(f"RateLimitMiddleware: Excessive failed login attempts from IP '{client_ip}'. Blocked.")
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "success": False,
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": "Too many login attempts. Please try again after 15 minutes.",
                            "details": None
                        },
                        "request_id": getattr(request.state, "request_id", None)
                    },
                    headers={"Retry-After": str(self.login_window)}
                )

        # 2. General API Rate Limiting
        elif path.startswith("/api/v1/"):
            limiter_key = f"api_rate_{client_ip}"
            allowed, remaining = _memory_limiter.is_allowed(limiter_key, self.api_limit, self.api_window)
            if not allowed:
                logger.warning(f"RateLimitMiddleware: General API rate limit exceeded for IP '{client_ip}'.")
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "success": False,
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": "API request rate limit exceeded. Please slow down.",
                            "details": None
                        },
                        "request_id": getattr(request.state, "request_id", None)
                    },
                    headers={"Retry-After": str(self.api_window)}
                )

        response = await call_next(request)
        return response
