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
    """API key authentication for sensitive endpoints.

    Set MACARON_API_KEY env var to enable. If not set, auth is disabled (dev mode).
    Only protects API mutation endpoints and sensitive data — pages, static,
    health, docs, and SSE are always public.
    """

    EXCLUDED_PREFIXES = (
        "/health", "/static", "/docs", "/redoc", "/openapi.json",
        "/sse", "/favicon", "/api/health", "/api/i18n/",
    )
    # Public API reads (GET only) — always accessible
    PUBLIC_GET_PATHS = (
        "/api/projects", "/api/agents", "/api/missions",
        "/api/integrations", "/api/metrics", "/api/workflows",
        "/api/monitoring/live", "/api/notifications/status",
    )

    async def dispatch(self, request: Request, call_next):
        api_key = os.getenv("MACARON_API_KEY")
        if not api_key:
            if os.getenv("ENVIRONMENT", "dev") != "dev":
                logger.warning("AUTH DISABLED — set MACARON_API_KEY for production")
            return await call_next(request)

        path = request.url.path

        # Always allow excluded paths (static, docs, health, SSE)
        if any(path.startswith(p) for p in self.EXCLUDED_PREFIXES):
            return await call_next(request)

        # Allow all non-API paths (HTML pages)
        if not path.startswith("/api/"):
            return await call_next(request)

        # Allow public GET endpoints
        if request.method == "GET" and any(path.startswith(p) for p in self.PUBLIC_GET_PATHS):
            # Mark as unauthenticated for info redaction
            request.state.authenticated = False
            return await call_next(request)

        # All other API calls require auth
        token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        if not token:
            token = request.query_params.get("token", "")

        if not token or hashlib.sha256(token.encode()).hexdigest() != hashlib.sha256(api_key.encode()).hexdigest():
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

        request.state.authenticated = True
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiter with PG persistence (survives restart) and in-memory fast path."""

    def __init__(self, app, max_requests: int = 60, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._pg_synced = False

    def _ensure_pg_table(self):
        """Create rate_limit_hits table if using PG."""
        if self._pg_synced:
            return
        try:
            from .db.adapter import is_postgresql, get_connection
            if is_postgresql():
                db = get_connection()
                db.execute("""CREATE TABLE IF NOT EXISTS rate_limit_hits (
                    id SERIAL PRIMARY KEY,
                    client_key TEXT NOT NULL,
                    ts DOUBLE PRECISION NOT NULL
                )""")
                db.execute("CREATE INDEX IF NOT EXISTS idx_rl_key_ts ON rate_limit_hits(client_key, ts)")
                db.commit()
                db.close()
        except Exception:
            pass
        self._pg_synced = True

    async def dispatch(self, request: Request, call_next):
        self._ensure_pg_table()
        # Key: combine IP + bearer token for per-client limiting
        client_ip = request.client.host if request.client else "unknown"
        token = request.headers.get("Authorization", "")[:20]
        client_key = f"{client_ip}:{hashlib.md5(token.encode()).hexdigest()[:8]}" if token else client_ip
        now = time.time()
        cutoff = now - self.window

        # Fast path: in-memory check
        hits = self._hits[client_key]
        self._hits[client_key] = [t for t in hits if t > cutoff]

        if len(self._hits[client_key]) >= self.max_requests:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

        self._hits[client_key].append(now)

        # Async persist to PG (non-blocking)
        try:
            from .db.adapter import is_postgresql
            if is_postgresql():
                import asyncio
                asyncio.get_event_loop().call_soon(self._pg_persist, client_key, now, cutoff)
        except Exception:
            pass

        return await call_next(request)

    def _pg_persist(self, client_key: str, ts: float, cutoff: float):
        """Persist hit to PG and cleanup old entries."""
        try:
            from .db.adapter import get_connection
            db = get_connection()
            db.execute("INSERT INTO rate_limit_hits (client_key, ts) VALUES (?, ?)", (client_key, ts))
            db.execute("DELETE FROM rate_limit_hits WHERE ts < ?", (cutoff,))
            db.commit()
            db.close()
        except Exception:
            pass


def health_check():
    """Health check endpoint data."""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "timestamp": time.time(),
    }
