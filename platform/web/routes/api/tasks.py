"""Copilot→SF task brief delegation endpoint.

Allows GitHub Copilot (or any orchestrator) to submit structured task briefs
that the SF turns into TMA missions executed by agents with git access.

POST /api/tasks/copilot-brief
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()
logger = logging.getLogger(__name__)

# Task brief schema (validated manually — no pydantic to keep it lightweight)
_REQUIRED_FIELDS = {"title", "description"}
_VALID_TYPES = {"bug_fix", "feature", "refactor", "docs", "test", "chore"}


@router.post("/api/tasks/copilot-brief")
async def submit_copilot_brief(request: Request) -> JSONResponse:
    """Submit a structured task brief from Copilot (or any orchestrator).

    Creates a TMA mission and assigns an agent with git access.

    Body (JSON):
    {
      "type": "bug_fix | feature | refactor | docs | test | chore",
      "title": "Fix /sessions/{id} 500 error",
      "description": "The route crashes because...",
      "files": ["platform/web/routes/sessions.py:1050"],   // optional
      "expected": "Should return 200 with session data",   // optional
      "context": "Stack trace / relevant code snippet",    // optional
      "test_cmd": "pytest tests/test_sessions.py -k ...", // optional
      "repo_url": "https://github.com/...",               // optional, defaults to SF repo
      "branch": "main",                                    // optional
      "project_id": "software-factory"                    // optional
    }

    Returns:
    {
      "mission_id": "...",
      "session_url": "/sessions/...",
      "status": "created"
    }
    """
    from ....db.migrations import get_db
    from ..helpers import _parse_body

    body = await _parse_body(request)

    # Validate required fields
    missing = _REQUIRED_FIELDS - set(body.keys())
    if missing:
        return JSONResponse(
            {"error": f"Missing required fields: {missing}"}, status_code=400
        )

    brief_type = body.get("type", "chore")
    if brief_type not in _VALID_TYPES:
        brief_type = "chore"

    title = body["title"]
    description = body["description"]
    files = body.get("files", [])
    expected = body.get("expected", "")
    context = body.get("context", "")
    test_cmd = body.get("test_cmd", "")
    repo_url = body.get(
        "repo_url", "https://github.com/macaron-software/software-factory.git"
    )
    branch = body.get("branch", "main")
    project_id = body.get("project_id", "software-factory")

    # Build structured goal for the TMA agent
    goal_parts = [
        f"## Task Brief ({brief_type})\n",
        f"**Title**: {title}\n",
        f"**Description**: {description}\n",
    ]
    if files:
        goal_parts.append(f"**Files**: {', '.join(files)}\n")
    if expected:
        goal_parts.append(f"**Expected behavior**: {expected}\n")
    if context:
        goal_parts.append(f"**Context**:\n```\n{context[:2000]}\n```\n")
    goal_parts.extend(
        [
            f"**Repo**: {repo_url} (branch: {branch})\n",
            "---\n",
            "## Instructions for agent\n",
            f"1. Clone or update the repo: `{repo_url}`\n",
            "2. Read the files listed above and understand the issue\n",
            "3. Implement the fix / feature with minimal, surgical changes\n",
            "4. Commit with a clear message referencing this task\n",
            "5. Push to a feature branch and create a PR\n",
        ]
    )
    if test_cmd:
        goal_parts.insert(-1, f"4b. Run tests: `{test_cmd}` — all must pass\n")

    goal = "".join(goal_parts)

    # Create mission in DB
    mission_id = f"tma-copilot-{uuid.uuid4().hex[:8]}"
    now = datetime.utcnow().isoformat()

    db = get_db()
    try:
        db.execute(
            """INSERT INTO missions
               (id, project_id, name, status, type, goal, wsjf_score, created_at)
               VALUES (?, ?, ?, 'planning', 'program', ?, 5.0, ?)""",
            (mission_id, project_id, f"[Copilot] {title}", goal, now),
        )
        db.commit()
    except Exception as e:
        logger.error("Failed to create copilot brief mission: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        db.close()

    logger.info("Copilot brief created: mission=%s title=%s", mission_id, title)

    return JSONResponse(
        {
            "mission_id": mission_id,
            "session_url": f"/missions/{mission_id}",
            "status": "created",
            "note": "Mission created in 'planning' state. Use sf missions start {id} or the UI to launch.",
        },
        status_code=201,
    )


@router.get("/api/tasks/copilot-brief/{mission_id}")
async def get_copilot_brief_status(mission_id: str) -> JSONResponse:
    """Get status of a copilot-brief mission."""
    from ....db.migrations import get_db

    db = get_db()
    try:
        row = db.execute(
            "SELECT id, name, status, goal, created_at FROM missions WHERE id=?",
            (mission_id,),
        ).fetchone()
    finally:
        db.close()

    if not row:
        return JSONResponse({"error": "mission not found"}, status_code=404)

    return JSONResponse(
        {
            "mission_id": row["id"],
            "title": row["name"],
            "status": row["status"],
            "created_at": row["created_at"],
        }
    )
