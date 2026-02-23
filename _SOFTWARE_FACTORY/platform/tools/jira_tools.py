"""Jira integration tools — Jira Server (API v2) with Bearer token auth.

Provides: jira_search, jira_create, jira_update, jira_transition,
           jira_board_issues, jira_sync_from_platform, jira_sync_to_platform.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


# ── Config ───────────────────────────────────────────────────────────


def _get_jira_config() -> tuple[str, str]:
    """Return (base_url, token). Raises ValueError if not configured."""
    url = os.environ.get("JIRA_URL") or os.environ.get("ATLASSIAN_URL", "")
    token = os.environ.get("JIRA_TOKEN") or os.environ.get("ATLASSIAN_TOKEN", "")
    if not token:
        key_path = Path.home() / ".config" / "factory" / "jira.key"
        if key_path.exists():
            token = key_path.read_text().strip()
    if not url or not token:
        raise ValueError(
            "Jira not configured. Set JIRA_URL + JIRA_TOKEN env vars "
            "or place token in ~/.config/factory/jira.key"
        )
    return url.rstrip("/"), token


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ── Low-level API helpers ────────────────────────────────────────────


async def _jira_get(path: str, params: dict | None = None) -> dict:
    import aiohttp

    url, token = _get_jira_config()
    async with (
        aiohttp.ClientSession(headers=_headers(token)) as s,
        s.get(f"{url}{path}", params=params, timeout=aiohttp.ClientTimeout(total=30)) as r,
    ):
        r.raise_for_status()
        return await r.json()


async def _jira_post(path: str, payload: dict) -> dict:
    import aiohttp

    url, token = _get_jira_config()
    async with (
        aiohttp.ClientSession(headers=_headers(token)) as s,
        s.post(f"{url}{path}", json=payload, timeout=aiohttp.ClientTimeout(total=30)) as r,
    ):
        r.raise_for_status()
        if r.status == 204 or r.content_length == 0:
            return {}
        try:
            return await r.json()
        except Exception:
            return {}


async def _jira_put(path: str, payload: dict) -> int:
    import aiohttp

    url, token = _get_jira_config()
    async with (
        aiohttp.ClientSession(headers=_headers(token)) as s,
        s.put(f"{url}{path}", json=payload, timeout=aiohttp.ClientTimeout(total=30)) as r,
    ):
        r.raise_for_status()
        return r.status


# ── Tool implementations ────────────────────────────────────────────


async def jira_search(jql: str, max_results: int = 20) -> str:
    """Search issues via JQL."""
    try:
        data = await _jira_get(
            "/rest/api/2/search",
            {
                "jql": jql,
                "maxResults": max_results,
                "fields": "summary,status,issuetype,assignee,priority,created,updated",
            },
        )
        issues = data.get("issues", [])
        if not issues:
            return "No issues found."
        lines = []
        for i in issues:
            f = i["fields"]
            assignee = (f.get("assignee") or {}).get("displayName", "unassigned")
            status = f.get("status", {}).get("name", "?")
            itype = f.get("issuetype", {}).get("name", "?")
            lines.append(f"[{i['key']}] {f.get('summary', '')} | {itype} | {status} | {assignee}")
        return f"Found {data.get('total', len(issues))} issues:\n" + "\n".join(lines)
    except Exception as e:
        return f"Jira search error: {e}"


async def jira_create(
    project: str,
    summary: str,
    issue_type: str = "User Story",
    description: str = "",
    priority: str = "",
    labels: list[str] | None = None,
) -> str:
    """Create a Jira issue."""
    try:
        fields: dict = {
            "project": {"key": project},
            "summary": summary,
            "issuetype": {"name": issue_type},
        }
        if description:
            fields["description"] = description
        if priority:
            fields["priority"] = {"name": priority}
        if labels:
            fields["labels"] = labels
        # Feature/Epic type requires Epic Name on Jira Server
        if issue_type.lower() in ("feature", "epic"):
            fields["customfield_12951"] = summary
        data = await _jira_post("/rest/api/2/issue", {"fields": fields})
        key = data.get("key", "?")
        url, _ = _get_jira_config()
        return f"Created {key} — {url}/browse/{key}"
    except Exception as e:
        return f"Jira create error: {e}"


async def jira_update(issue_key: str, fields: dict) -> str:
    """Update fields on an existing issue (summary, description, priority, labels, assignee)."""
    try:
        update_fields = {}
        if "summary" in fields:
            update_fields["summary"] = fields["summary"]
        if "description" in fields:
            update_fields["description"] = fields["description"]
        if "priority" in fields:
            update_fields["priority"] = {"name": fields["priority"]}
        if "labels" in fields:
            update_fields["labels"] = fields["labels"]
        if "assignee" in fields:
            update_fields["assignee"] = {"name": fields["assignee"]}
        status = await _jira_put(f"/rest/api/2/issue/{issue_key}", {"fields": update_fields})
        return f"Updated {issue_key} (HTTP {status})"
    except Exception as e:
        return f"Jira update error: {e}"


async def jira_transition(issue_key: str, transition_name: str) -> str:
    """Move issue to a new status via transition name (e.g. 'En Cours', 'Terminé')."""
    try:
        data = await _jira_get(f"/rest/api/2/issue/{issue_key}/transitions")
        transitions = data.get("transitions", [])
        match = None
        for t in transitions:
            if t["name"].lower() == transition_name.lower():
                match = t
                break
        if not match:
            # Fuzzy match
            for t in transitions:
                if transition_name.lower() in t["name"].lower():
                    match = t
                    break
        if not match:
            avail = ", ".join(f"{t['name']} (id={t['id']})" for t in transitions)
            return f"Transition '{transition_name}' not found. Available: {avail}"
        await _jira_post(
            f"/rest/api/2/issue/{issue_key}/transitions", {"transition": {"id": match["id"]}}
        )
        return f"Transitioned {issue_key} → {match['name']}"
    except Exception as e:
        return f"Jira transition error: {e}"


async def jira_board_issues(board_id: int = 8680, max_results: int = 50) -> str:
    """Get all issues from a Jira Agile board."""
    try:
        data = await _jira_get(
            f"/rest/agile/1.0/board/{board_id}/issue",
            {"maxResults": max_results, "fields": "summary,status,issuetype,assignee,priority"},
        )
        issues = data.get("issues", [])
        if not issues:
            return f"Board {board_id} has no issues."
        lines = []
        for i in issues:
            f = i["fields"]
            status = f.get("status", {}).get("name", "?")
            assignee = (f.get("assignee") or {}).get("displayName", "unassigned")
            lines.append(f"[{i['key']}] {f.get('summary', '')} | {status} | {assignee}")
        return f"Board {board_id} — {data.get('total', len(issues))} issues:\n" + "\n".join(lines)
    except Exception as e:
        return f"Jira board error: {e}"


async def jira_add_comment(issue_key: str, comment: str) -> str:
    """Add a comment to an issue."""
    try:
        data = await _jira_post(f"/rest/api/2/issue/{issue_key}/comment", {"body": comment})
        return f"Comment added to {issue_key} (id={data.get('id', '?')})"
    except Exception as e:
        return f"Jira comment error: {e}"


# ── Sync: Platform tasks → Jira ─────────────────────────────────────


async def jira_sync_from_platform(mission_id: str, board_id: int = 8680) -> str:
    """Push platform tasks/stories to Jira board as issues.

    Maps: TaskDef → Sous-Tâche, UserStoryDef → User Story, FeatureDef → Feature.
    Skips items that already have a jira_key stored.
    """
    from ..db.migrations import get_db

    try:
        db = get_db()
        url, _ = _get_jira_config()

        # Get mission info
        mission = db.execute("SELECT * FROM missions WHERE id=?", (mission_id,)).fetchone()
        if not mission:
            return f"Mission {mission_id} not found."

        project_key = os.environ.get("JIRA_PROJECT", "LPDATA")
        created = []

        # Sync features
        features = db.execute("SELECT * FROM features WHERE mission_id=?", (mission_id,)).fetchall()
        for feat in features:
            if feat["jira_key"] if "jira_key" in feat.keys() else None:
                continue
            result = await jira_create(
                project=project_key,
                summary=feat["title"],
                issue_type="Feature",
                description=feat.get("description", ""),
                labels=["macaron-sync", f"mission-{mission_id[:8]}"],
            )
            if "Created" in result:
                jira_key = result.split(" ")[1]
                try:
                    db.execute("UPDATE features SET jira_key=? WHERE id=?", (jira_key, feat["id"]))
                    db.commit()
                except Exception:
                    pass
                created.append(f"Feature {feat['title']} → {jira_key}")

        # Sync user stories
        stories = db.execute(
            "SELECT us.* FROM user_stories us JOIN features f ON us.feature_id=f.id WHERE f.mission_id=?",
            (mission_id,),
        ).fetchall()
        for story in stories:
            if story["jira_key"] if "jira_key" in story.keys() else None:
                continue
            result = await jira_create(
                project=project_key,
                summary=story["title"],
                issue_type="User Story",
                description=story.get("acceptance_criteria", ""),
                labels=["macaron-sync"],
            )
            if "Created" in result:
                jira_key = result.split(" ")[1]
                try:
                    db.execute(
                        "UPDATE user_stories SET jira_key=? WHERE id=?", (jira_key, story["id"])
                    )
                    db.commit()
                except Exception:
                    pass
                created.append(f"Story {story['title']} → {jira_key}")

        # Sync tasks
        tasks = db.execute("SELECT * FROM tasks WHERE mission_id=?", (mission_id,)).fetchall()
        for task in tasks:
            if task["jira_key"] if "jira_key" in task.keys() else None:
                continue
            result = await jira_create(
                project=project_key,
                summary=task["title"],
                issue_type="User Story",
                description=task.get("description", ""),
                labels=["macaron-sync"],
            )
            if "Created" in result:
                jira_key = result.split(" ")[1]
                try:
                    db.execute("UPDATE tasks SET jira_key=? WHERE id=?", (jira_key, task["id"]))
                    db.commit()
                except Exception:
                    pass
                created.append(f"Task {task['title']} → {jira_key}")

        db.close()
        if not created:
            return f"Nothing to sync for mission {mission_id[:8]}."
        return f"Synced {len(created)} items to Jira:\n" + "\n".join(created)
    except Exception as e:
        return f"Sync error: {e}"


async def jira_sync_to_platform(board_id: int = 8680) -> str:
    """Pull Jira board issues into platform as notifications / TMA tickets."""
    from ..services.notifications import emit_notification

    try:
        data = await _jira_get(
            f"/rest/agile/1.0/board/{board_id}/issue",
            {"maxResults": 50, "fields": "summary,status,issuetype,assignee,priority,updated"},
        )
        issues = data.get("issues", [])
        if not issues:
            return "No issues on board to import."

        imported = 0
        for i in issues:
            f = i["fields"]
            emit_notification(
                title=f"Jira: {i['key']}",
                message=f"{f.get('summary', '')} ({f.get('status', {}).get('name', '')})",
                type="jira_sync",
                severity="info",
            )
            imported += 1
        return f"Imported {imported} issues from board {board_id} as notifications."
    except Exception as e:
        return f"Sync error: {e}"


# ── Kanban sync: Platform ↔ Jira ────────────────────────────────────

# Platform kanban_status → Jira transition name
_PLATFORM_TO_JIRA = {
    "funnel": None,              # Créée (initial state, no transition needed)
    "analyzing": "Prêt",         # → Prête
    "backlog": "Prêt",           # → Prête
    "implementing": "Prêt",      # → Prête (Feature type has no "En Cours")
    "done": "Fermer",            # → Fermée
}
    "done": "Réaliser",  # → Réalisée
}

# Jira status name → Platform kanban_status
_JIRA_TO_PLATFORM = {
    "Créée": "funnel",
    "Prête": "backlog",
    "En Cours": "implementing",
    "Réalisée": "done",
    "Fermée": "done",
    "Annulée": "done",
}


async def jira_kanban_sync(direction: str = "both") -> str:
    """Sync kanban statuses between Platform missions and Jira board.

    direction: 'to_jira' | 'from_jira' | 'both'
    Matches missions to Jira issues via the jira_key field on missions.
    """
    from ..db.migrations import get_db
    from ..services.notifications import emit_notification

    results = []
    try:
        db = get_db()
        url, _ = _get_jira_config()
        board_id = int(os.environ.get("JIRA_BOARD_ID", "8680"))
        project_key = os.environ.get("JIRA_PROJECT", "IAN")

        # Get all missions with jira_key
        missions = db.execute(
            "SELECT id, name, kanban_status, status, jira_key FROM missions WHERE jira_key IS NOT NULL AND jira_key != ''"
        ).fetchall()

        # Get Jira board issues
        jira_issues = {}
        try:
            data = await _jira_get(
                f"/rest/agile/1.0/board/{board_id}/issue",
                {"maxResults": 100, "fields": "summary,status,issuetype,labels"},
            )
            for i in data.get("issues", []):
                jira_issues[i["key"]] = i
        except Exception:
            pass

        # ── Platform → Jira ──
        if direction in ("to_jira", "both"):
            for m in missions:
                jira_key = m["jira_key"]
                if jira_key not in jira_issues:
                    continue
                jira_status = jira_issues[jira_key]["fields"]["status"]["name"]
                expected_kanban = _JIRA_TO_PLATFORM.get(jira_status, "funnel")
                platform_kanban = m["kanban_status"] or "funnel"

                if platform_kanban != expected_kanban:
                    target_transition = _PLATFORM_TO_JIRA.get(platform_kanban)
                    if target_transition:
                        result = await jira_transition(jira_key, target_transition)
                        results.append(
                            f"→ Jira: {jira_key} {jira_status} → {target_transition} ({result})"
                        )

        # ── Jira → Platform ──
        if direction in ("from_jira", "both"):
            # Also check issues with macaron-sync label not yet linked
            for key, issue in jira_issues.items():
                jira_status = issue["fields"]["status"]["name"]
                new_kanban = _JIRA_TO_PLATFORM.get(jira_status, "funnel")

                # Find matching mission
                linked = db.execute(
                    "SELECT id, name, kanban_status FROM missions WHERE jira_key=?", (key,)
                ).fetchone()
                if linked:
                    old_kanban = linked["kanban_status"] or "funnel"
                    if old_kanban != new_kanban:
                        db.execute(
                            "UPDATE missions SET kanban_status=? WHERE id=?",
                            (new_kanban, linked["id"]),
                        )
                        db.commit()
                        results.append(
                            f"← Platform: {linked['name'][:30]} {old_kanban} → {new_kanban} (from {key})"
                        )
                        emit_notification(
                            title=f"Kanban sync: {key}",
                            message=f"{linked['name']} moved to {new_kanban}",
                            type="jira_sync",
                            severity="info",
                        )

        # ── Auto-link: create Jira issues for unlinked missions ──
        if direction in ("to_jira", "both"):
            unlinked = db.execute(
                "SELECT id, name, kanban_status, status FROM missions WHERE (jira_key IS NULL OR jira_key = '') AND status != 'archived' AND name NOT LIKE '[TMA]%' LIMIT 10"
            ).fetchall()
            for m in unlinked:
                result = await jira_create(
                    project=project_key,
                    summary=f"[SF] {m['name'][:80]}",
                    issue_type="Feature",
                    description=f"Auto-synced from Macaron Software Factory.\nMission ID: {m['id']}\nStatus: {m['status']}\nKanban: {m['kanban_status'] or 'funnel'}",
                )
                if "Created" in result:
                    jira_key = result.split(" ")[1]
                    db.execute("UPDATE missions SET jira_key=? WHERE id=?", (jira_key, m["id"]))
                    db.commit()
                    # Set the right Jira status
                    target = _PLATFORM_TO_JIRA.get(m["kanban_status"] or "funnel")
                    if target:
                        await jira_transition(jira_key, target)
                    results.append(
                        f"+ Created {jira_key} for '{m['name'][:30]}' ({m['kanban_status'] or 'funnel'})"
                    )

        db.close()
        if not results:
            return "Kanban sync: everything is already in sync."
        return f"Kanban sync completed ({len(results)} changes):\n" + "\n".join(results)
    except Exception as e:
        return f"Kanban sync error: {e}"


# ── Tool dispatch (called from tool_runner.py) ──────────────────────

JIRA_TOOLS = {
    "jira_search",
    "jira_create",
    "jira_update",
    "jira_transition",
    "jira_board_issues",
    "jira_add_comment",
    "jira_sync_from_platform",
    "jira_sync_to_platform",
    "jira_kanban_sync",
}


async def run_jira_tool(name: str, args: dict) -> str:
    """Dispatch a jira_* tool call."""
    if name == "jira_search":
        return await jira_search(args.get("jql", ""), args.get("max_results", 20))
    if name == "jira_create":
        return await jira_create(
            project=args.get("project", os.environ.get("JIRA_PROJECT", "LPDATA")),
            summary=args["summary"],
            issue_type=args.get("type", "User Story"),
            description=args.get("description", ""),
            priority=args.get("priority", ""),
            labels=args.get("labels"),
        )
    if name == "jira_update":
        return await jira_update(args["issue_key"], args.get("fields", {}))
    if name == "jira_transition":
        return await jira_transition(args["issue_key"], args["transition"])
    if name == "jira_board_issues":
        return await jira_board_issues(args.get("board_id", 8680), args.get("max_results", 50))
    if name == "jira_add_comment":
        return await jira_add_comment(args["issue_key"], args["comment"])
    if name == "jira_sync_from_platform":
        return await jira_sync_from_platform(args["mission_id"], args.get("board_id", 8680))
    if name == "jira_sync_to_platform":
        return await jira_sync_to_platform(args.get("board_id", 8680))
    if name == "jira_kanban_sync":
        return await jira_kanban_sync(args.get("direction", "both"))
    return f"Unknown Jira tool: {name}"
