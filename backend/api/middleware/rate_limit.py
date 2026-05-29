"""
api/middleware/rate_limit.py
Sliding-window rate limiter backed by Redis.
Limits per IP address (can be extended to per-user JWT).
"""
from __future__ import annotations

import time

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

from config.settings import settings

log = structlog.get_logger(__name__)

# Paths that bypass rate limiting (health checks, docs)
_EXEMPT_PREFIXES = ("/api/health", "/api/docs", "/api/redoc", "/api/openapi", "/static")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding-window rate limiter using Redis sorted sets.
    Default: 100 requests / 60 seconds per IP.
    """

    def __init__(self, app, requests: int = None, window: int = None):
        super().__init__(app)
        self._limit = requests or settings.rate_limit_requests
        self._window = window or settings.rate_limit_window
        self._redis = None

    def _get_redis(self):
        if self._redis is None:
            import redis
            self._redis = redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_timeout=1,
                socket_connect_timeout=1,
            )
        return self._redis

    async def dispatch(self, request: Request, call_next) -> Response:
        # Always let CORS preflight through — rate-limiting OPTIONS breaks cross-origin auth
        if request.method == "OPTIONS":
            return await call_next(request)

        # Skip exempt paths
        for prefix in _EXEMPT_PREFIXES:
            if request.url.path.startswith(prefix):
                return await call_next(request)

        ip = request.client.host if request.client else "unknown"
        key = f"rate:{ip}"
        now = time.time()
        window_start = now - self._window

        try:
            r = self._get_redis()
            pipe = r.pipeline()
            # Remove timestamps outside the window
            pipe.zremrangebyscore(key, "-inf", window_start)
            # Count current requests in window
            pipe.zcard(key)
            # Add this request
            pipe.zadd(key, {str(now): now})
            # Set TTL so Redis auto-cleans
            pipe.expire(key, self._window * 2)
            results = pipe.execute()

            current_count = results[1]

            if current_count >= self._limit:
                retry_after = int(self._window - (now - window_start))
                log.warning("rate_limit_exceeded", ip=ip, count=current_count)
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Too many requests. Please slow down.",
                        "retry_after_seconds": retry_after,
                    },
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(self._limit),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Window": str(self._window),
                    },
                )
        except Exception as exc:
            # Redis down → fail open (don't block requests)
            log.warning("rate_limit_redis_error", error=str(exc))

        response = await call_next(request)
        remaining = max(0, self._limit - (current_count + 1)) if "current_count" in dir() else self._limit
        response.headers["X-RateLimit-Limit"] = str(self._limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
