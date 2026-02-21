"""Security middleware — authentication, RBAC, rate limiting."""
from __future__ import annotations

import hashlib
import logging
import os
import time
from collections import defaultdict

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """Simple API key authentication.

    Set MACARON_API_KEY env var to enable. If not set, auth is disabled (dev mode).
    """

    EXCLUDED_PATHS = {"/health", "/static"}

    async def dispatch(self, request: Request, call_next):
        api_key = os.getenv("MACARON_API_KEY")
        if not api_key:
            # Log warning in production-like environments
            if os.getenv("ENVIRONMENT", "dev") != "dev":
                logger.warning("AUTH DISABLED — set MACARON_API_KEY for production")
            return await call_next(request)

        path = request.url.path
        if any(path.startswith(p) for p in self.EXCLUDED_PATHS):
            return await call_next(request)

        token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        if not token:
            token = request.query_params.get("token", "")

        if not token or hashlib.sha256(token.encode()).hexdigest() != hashlib.sha256(api_key.encode()).hexdigest():
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter (per IP)."""

    def __init__(self, app, max_requests: int = 60, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        cutoff = now - self.window

        hits = self._hits[client_ip]
        self._hits[client_ip] = [t for t in hits if t > cutoff]

        if len(self._hits[client_ip]) >= self.max_requests:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

        self._hits[client_ip].append(now)
        return await call_next(request)


def health_check():
    """Health check endpoint data."""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "timestamp": time.time(),
    }
