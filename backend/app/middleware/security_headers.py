"""
Security Headers Middleware.
Applies modern HTTP security headers and dynamic HSTS (HTTP Strict Transport Security)
when requests arrive over secure HTTPS connections.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware attaching modern security response headers.
    Does NOT use deprecated X-XSS-Protection header.
    Emits HSTS only when HTTPS is active.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # 1. Prevent MIME-type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # 2. Frame Options (allow SAMEORIGIN for camera dashboard embeds)
        response.headers["X-Frame-Options"] = "SAMEORIGIN"

        # 3. Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # 4. Content Security Policy (allows cross-origin frontend image/video/connect access)
        response.headers["Content-Security-Policy"] = (
            "default-src * 'unsafe-inline' 'unsafe-eval' data: blob:; "
            "img-src * data: blob:; "
            "media-src * data: blob:; "
            "connect-src * ws: wss:;"
        )

        # 5. Conditional HSTS (Strict-Transport-Security) only when HTTPS is active
        is_https = request.url.scheme == "https" or request.headers.get("X-Forwarded-Proto") == "https"
        if is_https:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        return response
