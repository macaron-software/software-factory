"""
Auth routes — login, register, refresh, logout, user management.

Endpoints:
    POST /api/auth/login      — authenticate, set JWT cookies
    POST /api/auth/register   — create user (admin only, or first user via setup)
    POST /api/auth/refresh    — rotate refresh token
    POST /api/auth/logout     — clear cookies, invalidate session
    GET  /api/auth/me         — current user info
    POST /api/auth/setup      — first-time setup (create admin)

    GET  /api/users           — list users (admin)
    GET  /api/users/{id}      — get user (admin or self)
    PUT  /api/users/{id}      — update user (admin or self)
    DELETE /api/users/{id}    — delete user (admin only)
    PUT  /api/users/{id}/projects/{project_id}/role — set project role (admin)
    DELETE /api/users/{id}/projects/{project_id}/role — remove project role (admin)
"""

import collections
import logging
import os
import time

from fastapi import APIRouter, Depends, Request
from starlette.responses import JSONResponse

from ...auth import service
from ...auth.middleware import require_auth, get_current_user

_log = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# SBD-04: In-memory sliding-window rate limiter for auth endpoints.
# WHY: /api/auth/login and /api/auth/demo have no external rate limiting and
# are publicly reachable → brute-force / credential-stuffing vectors.
# 5 attempts per 60 s per IP; exceeding returns 429 with Retry-After.
# Ref: SecureByDesign v1.1.0 SBD-04 — brute-force protection on auth endpoints
# (https://github.com/Yems221/securebydesign-llmskill/blob/main/SKILL.md)
# ---------------------------------------------------------------------------
_RATE_LIMIT_MAX = 5
_RATE_LIMIT_WINDOW = 60  # seconds
_login_attempts: dict[str, collections.deque] = {}


def _check_rate_limit(ip: str) -> bool:
    """Return True if IP has exceeded the login rate limit."""
    now = time.monotonic()
    bucket = _login_attempts.setdefault(ip, collections.deque())
    while bucket and now - bucket[0] > _RATE_LIMIT_WINDOW:
        bucket.popleft()
    if len(bucket) >= _RATE_LIMIT_MAX:
        return True
    bucket.append(now)
    return False


ACCESS_COOKIE_MAX_AGE = 15 * 60  # 15 minutes
REFRESH_COOKIE_MAX_AGE = 7 * 24 * 60 * 60  # 7 days


def _set_auth_cookies(response: JSONResponse, tokens: dict) -> JSONResponse:
    """Set access + refresh tokens as httponly cookies."""
    response.set_cookie(
        "access_token",
        tokens["access_token"],
        max_age=ACCESS_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        "refresh_token",
        tokens["refresh_token"],
        max_age=REFRESH_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/api/auth",
    )
    return response


def _clear_auth_cookies(response: JSONResponse) -> JSONResponse:
    """Clear auth cookies."""
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/api/auth")
    return response


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------


@router.post("/api/auth/setup")
async def setup(request: Request):
    """First-time setup — create admin user. Only works if 0 users exist."""
    if service.user_count() > 0:
        return JSONResponse({"error": "Setup already completed"}, status_code=400)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    email = body.get("email", "").strip()
    password = body.get("password", "")
    name = body.get("display_name", email.split("@")[0] if email else "Admin")

    if not email or not password:
        return JSONResponse({"error": "Email and password required"}, status_code=400)

    try:
        service.register(email, password, name, role="admin")
        tokens = service.login(
            email,
            password,
            ip=request.client.host if request.client else "",
            ua=request.headers.get("user-agent", ""),
        )
        resp = JSONResponse({"ok": True, "user": tokens["user"]})
        return _set_auth_cookies(resp, tokens)
    except service.AuthError as e:
        return JSONResponse({"error": str(e), "code": e.code}, status_code=400)
    except Exception as e:
        # SBD-13: log full error server-side, return generic message to client.
        _log.error("setup: unexpected error: %s", e, exc_info=True)
        return JSONResponse(
            {"error": "Setup error. Check server logs."}, status_code=500
        )


@router.post("/api/auth/demo")
async def demo_login(request: Request):
    """Skip login — create or reuse demo admin and auto-login. Available on all environments."""

    ip = request.client.host if request.client else ""
    if _check_rate_limit(ip):
        return JSONResponse(
            {"error": "Too many attempts. Try again later.", "code": "rate_limited"},
            status_code=429,
            headers={"Retry-After": str(_RATE_LIMIT_WINDOW)},
        )

    import asyncio

    demo_email = os.environ.get("SF_DEMO_EMAIL", "admin@demo.local")
    demo_pass = os.environ.get("SF_DEMO_PASSWORD", "")
    if not demo_pass:
        return JSONResponse({"error": "Demo login not configured"}, status_code=503)
    demo_name = "Demo Admin"

    loop = asyncio.get_event_loop()

    # Ensure migrations are up to date (user_sessions table may be missing on older deploys)
    try:
        from ...db.migrations import init_db

        await loop.run_in_executor(None, init_db)
    except Exception as _e:
        _log.warning("demo_login: migration check failed: %s", _e)

    # Create demo user if doesn't exist (run bcrypt in thread pool)
    try:
        await loop.run_in_executor(
            None,
            lambda: service.register(demo_email, demo_pass, demo_name, role="admin"),
        )
    except service.AuthError:
        # Already exists — force-reset password in case the stored hash is stale
        # (e.g. created with a different password in a prior session / env change)
        try:
            await loop.run_in_executor(
                None,
                lambda: service.force_reset_password(demo_email, demo_pass),
            )
        except Exception as _pe:
            _log.warning("demo_login: password reset failed: %s", _pe)
    except Exception as _e:
        _log.error("demo_login: register failed: %s", _e)

    try:
        tokens = await loop.run_in_executor(
            None,
            lambda: service.login(
                demo_email,
                demo_pass,
                ip=request.client.host if request.client else "",
                ua=request.headers.get("user-agent", ""),
            ),
        )
        resp = JSONResponse({"ok": True, "user": tokens["user"], "demo": True})
        return _set_auth_cookies(resp, tokens)
    except service.AuthError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        # SBD-13: log internally, return generic message.
        _log.error("demo_login: login failed: %s", e, exc_info=True)
        return JSONResponse({"error": "Demo login error"}, status_code=500)


@router.post("/api/auth/login")
async def login(request: Request):
    """Authenticate user with email/password. Returns JWT cookies."""
    ip = request.client.host if request.client else ""
    if _check_rate_limit(ip):
        return JSONResponse(
            {"error": "Too many attempts. Try again later.", "code": "rate_limited"},
            status_code=429,
            headers={"Retry-After": str(_RATE_LIMIT_WINDOW)},
        )

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    email = body.get("email", "")
    password = body.get("password", "")

    try:
        tokens = service.login(
            email,
            password,
            ip=request.client.host if request.client else "",
            ua=request.headers.get("user-agent", ""),
        )
        resp = JSONResponse({"ok": True, "user": tokens["user"]})
        return _set_auth_cookies(resp, tokens)
    except service.AuthError as e:
        return JSONResponse({"error": str(e), "code": e.code}, status_code=401)


@router.post("/api/auth/register")
async def register(request: Request, user=Depends(require_auth("admin"))):
    """Create new user (admin only)."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    email = body.get("email", "")
    password = body.get("password", "")
    name = body.get("display_name", "")
    role = body.get("role", "viewer")

    if role not in ("admin", "project_manager", "developer", "viewer"):
        return JSONResponse({"error": f"Invalid role: {role}"}, status_code=400)

    try:
        new_user = service.register(email, password, name, role=role)
        return JSONResponse(
            {
                "ok": True,
                "user": {
                    "id": new_user.id,
                    "email": new_user.email,
                    "display_name": new_user.display_name,
                    "role": new_user.role,
                },
            }
        )
    except service.AuthError as e:
        return JSONResponse({"error": str(e), "code": e.code}, status_code=400)


@router.post("/api/auth/refresh")
async def refresh(request: Request):
    """Rotate refresh token. Returns new access + refresh tokens."""
    token = request.cookies.get("refresh_token", "")
    if not token:
        # Try body
        try:
            body = await request.json()
            token = body.get("refresh_token", "")
        except Exception:
            pass

    if not token:
        return JSONResponse({"error": "No refresh token"}, status_code=401)

    try:
        tokens = service.refresh_tokens(
            token,
            ip=request.client.host if request.client else "",
            ua=request.headers.get("user-agent", ""),
        )
        resp = JSONResponse({"ok": True, "user": tokens["user"]})
        return _set_auth_cookies(resp, tokens)
    except service.AuthError as e:
        resp = JSONResponse({"error": str(e), "code": e.code}, status_code=401)
        return _clear_auth_cookies(resp)


@router.post("/api/auth/logout")
async def logout(request: Request):
    """Logout — clear cookies and invalidate sessions."""
    user = await get_current_user(request)
    if user and user.id != "api-key-user":
        service.logout(user.id)

    resp = JSONResponse({"ok": True})
    return _clear_auth_cookies(resp)


@router.get("/api/auth/me")
async def me(request: Request, user=Depends(require_auth())):
    """Get current authenticated user info."""
    projects = service.get_user_projects(user.id) if user.id != "api-key-user" else []
    return JSONResponse(
        {
            "user": {
                "id": user.id,
                "email": user.email,
                "display_name": user.display_name,
                "role": user.role,
                "avatar": user.avatar,
                "auth_provider": user.auth_provider,
                "projects": projects,
            },
        }
    )


# ---------------------------------------------------------------------------
# User management (admin)
# ---------------------------------------------------------------------------


@router.get("/api/users")
async def list_users(request: Request, user=Depends(require_auth("admin"))):
    """List all users (admin only)."""
    users = service.list_users()
    return JSONResponse(
        {
            "users": [
                {
                    "id": u.id,
                    "email": u.email,
                    "display_name": u.display_name,
                    "role": u.role,
                    "avatar": u.avatar,
                    "is_active": u.is_active,
                    "auth_provider": u.auth_provider,
                    "last_login": u.last_login,
                    "created_at": u.created_at,
                    "projects": service.get_user_projects(u.id),
                }
                for u in users
            ],
        }
    )


@router.get("/api/users/{user_id}")
async def get_user(user_id: str, request: Request, user=Depends(require_auth())):
    """Get user details (admin or self)."""
    if user.role != "admin" and user.id != user_id:
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    target = service.get_user_by_id(user_id)
    if not target:
        return JSONResponse({"error": "User not found"}, status_code=404)

    return JSONResponse(
        {
            "user": {
                "id": target.id,
                "email": target.email,
                "display_name": target.display_name,
                "role": target.role,
                "avatar": target.avatar,
                "is_active": target.is_active,
                "projects": service.get_user_projects(target.id),
            },
        }
    )


@router.put("/api/users/{user_id}")
async def update_user(user_id: str, request: Request, user=Depends(require_auth())):
    """Update user (admin or self for display_name/avatar only)."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    if user.role != "admin" and user.id != user_id:
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    # Non-admin can only update display_name and avatar
    if user.role != "admin":
        body = {k: v for k, v in body.items() if k in ("display_name", "avatar")}

    updated = service.update_user(user_id, **body)
    if not updated:
        return JSONResponse({"error": "User not found"}, status_code=404)

    return JSONResponse(
        {
            "ok": True,
            "user": {
                "id": updated.id,
                "email": updated.email,
                "display_name": updated.display_name,
                "role": updated.role,
            },
        }
    )


@router.delete("/api/users/{user_id}")
async def delete_user(
    user_id: str, request: Request, user=Depends(require_auth("admin"))
):
    """Delete user (admin only). Cannot delete self."""
    if user.id == user_id:
        return JSONResponse({"error": "Cannot delete yourself"}, status_code=400)

    service.delete_user(user_id)
    return JSONResponse({"ok": True})


# ---------------------------------------------------------------------------
# Project role management (admin)
# ---------------------------------------------------------------------------


@router.put("/api/users/{user_id}/projects/{project_id}/role")
async def set_project_role(
    user_id: str,
    project_id: str,
    request: Request,
    user=Depends(require_auth("admin")),
):
    """Set user role for a project (admin only)."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    role = body.get("role", "viewer")
    if role not in ("admin", "project_manager", "developer", "viewer"):
        return JSONResponse({"error": f"Invalid role: {role}"}, status_code=400)

    service.set_project_role(user_id, project_id, role, granted_by=user.id)
    return JSONResponse({"ok": True, "project_id": project_id, "role": role})


@router.delete("/api/users/{user_id}/projects/{project_id}/role")
async def remove_project_role(
    user_id: str,
    project_id: str,
    request: Request,
    user=Depends(require_auth("admin")),
):
    """Remove project-specific role (falls back to global role)."""
    service.remove_project_role(user_id, project_id)
    return JSONResponse({"ok": True})
