"""Security package — prompt injection, command validation, path hardening, auth."""
from __future__ import annotations

import hashlib
import logging
import os

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

from .sanitize import sanitize_user_input, sanitize_agent_output, sanitize_command
from .prompt_guard import PromptInjectionGuard, get_prompt_guard

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """API key authentication for sensitive endpoints.

    Set MACARON_API_KEY env var to enable. If not set, auth is disabled (dev mode).
    Only protects API mutation endpoints and sensitive data — pages, static,
    health, docs, and SSE are always public.
    """

    EXCLUDED_PREFIXES = (
        "/health", "/static", "/docs", "/redoc", "/openapi.json",
        "/sse", "/favicon", "/api/health", "/api/i18n/", "/api/auth",
    )
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

        if any(path.startswith(p) for p in self.EXCLUDED_PREFIXES):
            return await call_next(request)

        if not path.startswith("/api/"):
            return await call_next(request)

        # Skip API key check if JWT auth already authenticated user
        if hasattr(request.state, "user") and request.state.user is not None:
            request.state.authenticated = True
            return await call_next(request)

        if request.method == "GET" and any(path.startswith(p) for p in self.PUBLIC_GET_PATHS):
            request.state.authenticated = False
            return await call_next(request)

        token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        if not token:
            token = request.query_params.get("token", "")

        if not token or hashlib.sha256(token.encode()).hexdigest() != hashlib.sha256(api_key.encode()).hexdigest():
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

        request.state.authenticated = True
        return await call_next(request)


__all__ = [
    "sanitize_user_input",
    "sanitize_agent_output",
    "sanitize_command",
    "PromptInjectionGuard",
    "get_prompt_guard",
    "AuthMiddleware",
]
