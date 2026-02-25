"""Shared helpers for all route modules."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import Request
from fastapi.responses import JSONResponse, FileResponse

logger = logging.getLogger(__name__)


async def _parse_body(request: Request) -> dict:
    """Parse request body as JSON or form data, whichever the client sends."""
    ct = request.headers.get("content-type", "")
    if "application/json" in ct:
        return await request.json()
    return dict(await request.form())


def _is_json_request(request: Request) -> bool:
    """Return True if the client sent JSON (for choosing JSON vs redirect response)."""
    return "application/json" in request.headers.get("content-type", "")

# Track which mission_ids have an active asyncio task running
_active_mission_tasks: dict[str, asyncio.Task] = {}

# Limit concurrent mission execution (10 allows Quality/Retro/Skill missions to get slots)
_mission_semaphore = asyncio.Semaphore(10)

_AVATAR_DIR = Path(__file__).parent.parent / "static" / "avatars"


def _templates(request: Request):
    return request.app.state.templates


def _avatar_url(agent_id: str) -> str:
    """Get avatar photo URL for an agent, or empty string."""
    jpg = _AVATAR_DIR / f"{agent_id}.jpg"
    if jpg.exists():
        return f"/static/avatars/{agent_id}.jpg"
    svg = _AVATAR_DIR / f"{agent_id}.svg"
    if svg.exists():
        return f"/static/avatars/{agent_id}.svg"
    return ""


def _agent_map_for_template(agents) -> dict:
    """Build agent_map dict suitable for msg_unified.html, including avatar_url."""
    m = {}
    for a in agents:
        if hasattr(a, 'id'):  # AgentDef dataclass
            m[a.id] = {
                "id": a.id,
                "name": a.name, "icon": a.icon or "bot",
                "color": a.color or "#8b949e", "role": a.role or "",
                "avatar": getattr(a, "avatar", "") or "bot",
                "avatar_url": _avatar_url(a.id),
                "hierarchy_rank": getattr(a, "hierarchy_rank", 50),
                "tagline": getattr(a, "tagline", "") or "",
                "skills": getattr(a, "skills", []) or [],
                "tools": getattr(a, "tools", []) or [],
                "persona": getattr(a, "persona", "") or "",
                "motivation": getattr(a, "motivation", "") or "",
            }
        elif isinstance(a, dict):  # already a dict
            aid = a.get("id", "")
            m[aid] = {
                "id": aid,
                "name": a.get("name", ""), "icon": a.get("icon", "bot"),
                "color": a.get("color", "#8b949e"), "role": a.get("role", ""),
                "avatar": a.get("avatar", "bot"),
                "avatar_url": a.get("avatar_url", "") or _avatar_url(aid),
                "hierarchy_rank": a.get("hierarchy_rank", 50),
                "tagline": a.get("tagline", ""),
                "skills": a.get("skills", []),
                "tools": a.get("tools", []),
                "persona": a.get("persona", ""),
                "motivation": a.get("motivation", ""),
            }
    return m


async def serve_workspace_file(path: str):
    """Serve files from project workspaces (screenshots, artifacts)."""
    from ...config import FACTORY_ROOT
    workspaces = FACTORY_ROOT / "data" / "workspaces"
    for base in [workspaces, FACTORY_ROOT.parent]:
        full_path = base / path
        if full_path.exists() and full_path.is_file():
            import mimetypes
            media = mimetypes.guess_type(str(full_path))[0] or "application/octet-stream"
            return FileResponse(str(full_path), media_type=media)
    if workspaces.exists():
        for ws_dir in workspaces.iterdir():
            if ws_dir.is_dir():
                full_path = ws_dir / path
                if full_path.exists() and full_path.is_file():
                    import mimetypes
                    media = mimetypes.guess_type(str(full_path))[0] or "application/octet-stream"
                    return FileResponse(str(full_path), media_type=media)
    return JSONResponse({"error": "Not found"}, status_code=404)
