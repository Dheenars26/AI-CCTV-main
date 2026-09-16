"""
Request Correlation ID Middleware.
Generates or propagates X-Request-ID headers for request tracking across logs and clients.
"""

import uuid
from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

request_id_context_var: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    """
    Returns the current request ID from context storage.
    """
    return request_id_context_var.get()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware that ensures every incoming request gets assigned an X-Request-ID,
    stored in contextvars and attached to HTTP response headers.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        header_request_id = request.headers.get("X-Request-ID")
        req_id = header_request_id if header_request_id else str(uuid.uuid4())

        # Store in context variable for logging & request scope
        token = request_id_context_var.set(req_id)
        request.state.request_id = req_id

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = req_id
            return response
        finally:
            request_id_context_var.reset(token)
