"""
api/middleware/logging.py
Structured request/response logging and global exception handler.
"""
from __future__ import annotations

import time
import uuid

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

log = structlog.get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with timing, status code, and a request ID."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())[:8]
        start = time.perf_counter()

        # Bind request context to all log calls within this request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        try:
            response = await call_next(request)
        except Exception as exc:
            log.exception("unhandled_exception", error=str(exc))
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error", "request_id": request_id},
            )

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        log.info(
            "request",
            status=response.status_code,
            duration_ms=elapsed_ms,
        )

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{elapsed_ms}ms"
        return response
