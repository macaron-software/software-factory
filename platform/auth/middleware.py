"""
Auth middleware — FastAPI dependencies for authentication & authorization.

Usage in routes:
    from platform.auth.middleware import require_auth, require_project_role

    @router.get("/api/projects")
    async def list_projects(user: User = Depends(require_auth())):
        ...

    @router.post("/api/missions")
    async def create_mission(user: User = Depends(require_auth("project_manager"))):
        ...

    @router.put("/api/projects/{project_id}/settings")
    async def update_project(user: User = Depends(require_project_role("project_id", "project_manager"))):
        ...
"""

import hashlib
import os

from starlette.requests import Request
from starlette.responses import RedirectResponse

from .service import User, get_project_role, user_count, verify_access_token

# Role hierarchy (higher index = more privileges)
ROLE_HIERARCHY = {"viewer": 0, "developer": 1, "project_manager": 2, "admin": 3}

# Legacy API key support
_API_KEY = os.environ.get("MACARON_API_KEY", "")


def _extract_token(request: Request) -> str | None:
    """Extract JWT from cookie or Authorization header."""
    # 1. Cookie (preferred for web UI)
    token = request.cookies.get("access_token")
    if token:
        return token

    # 2. Authorization: Bearer <token>
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer ") and len(auth) > 40:
        return auth[7:]

    return None


def _check_api_key(request: Request) -> bool:
    """Check legacy API key auth (backward compatible)."""
    if not _API_KEY:
        return False
    auth = request.headers.get("authorization", "")
    token = (
        auth[7:]
        if auth.startswith("Bearer ")
        else request.query_params.get("token", "")
    )
    if not token:
        return False
    return (
        hashlib.sha256(token.encode()).hexdigest()
        == hashlib.sha256(_API_KEY.encode()).hexdigest()
    )


async def get_current_user(request: Request) -> User | None:
    """Get authenticated user from request. Returns None if not authenticated."""
    token = _extract_token(request)
    if token:
        user = verify_access_token(token)
        if user:
            return user

    # Fallback: API key → treat as admin
    if _check_api_key(request):
        return User(
            id="api-key-user",
            email="api@system",
            display_name="API Key User",
            role="admin",
            auth_provider="api_key",
        )

    return None


def require_auth(min_role: str = "viewer"):
    """FastAPI dependency — require authenticated user with minimum role.

    Usage: user: User = Depends(require_auth("developer"))
    """

    async def _dependency(request: Request) -> User:
        user = await get_current_user(request)
        if user is None:
            # Check if this is an API call or page request
            if request.url.path.startswith("/api/"):
                from starlette.exceptions import HTTPException

                raise HTTPException(status_code=401, detail="Authentication required")
            # Redirect to login page for HTML requests
            return RedirectResponse(
                url=f"/login?next={request.url.path}", status_code=302
            )

        min_level = ROLE_HIERARCHY.get(min_role, 0)
        user_level = ROLE_HIERARCHY.get(user.role, 0)
        if user_level < min_level:
            if request.url.path.startswith("/api/"):
                from starlette.exceptions import HTTPException

                raise HTTPException(
                    status_code=403,
                    detail=f"Requires role '{min_role}' or higher",
                )
            return RedirectResponse(url="/unauthorized", status_code=302)

        # Attach user to request state for downstream use
        request.state.user = user
        return user

    return _dependency


def require_project_role(project_id_param: str, min_role: str = "viewer"):
    """FastAPI dependency — require user has minimum role ON A SPECIFIC PROJECT.

    The project_id is extracted from the path parameter named `project_id_param`.
    Falls back to user's global role if no project-specific role is set.

    Usage: user: User = Depends(require_project_role("project_id", "project_manager"))
    """

    async def _dependency(request: Request) -> User:
        user = await get_current_user(request)
        if user is None:
            if request.url.path.startswith("/api/"):
                from starlette.exceptions import HTTPException

                raise HTTPException(status_code=401, detail="Authentication required")
            return RedirectResponse(
                url=f"/login?next={request.url.path}", status_code=302
            )

        # Admin bypasses project-level checks
        if user.role == "admin":
            request.state.user = user
            return user

        # Get project_id from path params
        project_id = request.path_params.get(project_id_param, "")
        if not project_id:
            # Try query params
            project_id = request.query_params.get("project_id", "")

        if project_id:
            effective_role = get_project_role(user.id, project_id)
        else:
            effective_role = user.role

        min_level = ROLE_HIERARCHY.get(min_role, 0)
        effective_level = ROLE_HIERARCHY.get(effective_role, 0)

        if effective_level < min_level:
            if request.url.path.startswith("/api/"):
                from starlette.exceptions import HTTPException

                raise HTTPException(
                    status_code=403,
                    detail=f"Requires role '{min_role}' on project '{project_id}'",
                )
            return RedirectResponse(url="/unauthorized", status_code=302)

        request.state.user = user
        return user

    return _dependency


def is_setup_needed() -> bool:
    """Check if setup wizard is needed (no users in DB)."""
    return user_count() == 0


# Public paths that don't require auth
PUBLIC_PATHS = {
    "/api/health",
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/refresh",
    "/api/auth/setup",
    "/api/auth/logout",
    "/api/auth/demo",
    "/api/set-lang",
    "/api/i18n",
    "/api/webhooks",
    "/api/autoheal/heartbeat",
    "/api/notifications/badge",
    "/login",
    "/setup",
    "/static",
    "/favicon.ico",
    "/health",
    "/docs",
    "/openapi.json",
    "/js-error",
    "/api/analytics",
}


def is_public_path(path: str) -> bool:
    """Check if a path is public (no auth required)."""
    for pp in PUBLIC_PATHS:
        if path == pp or path.startswith(pp + "/"):
            return True
    return False
