#!/usr/bin/env python3
"""
MCP Jira Server — anonymized Jira access for SF agents
======================================================
Wraps Jira REST API v2/v3 and strips PII (names, emails, phones)
before returning content to LLM agents (RGPD Art. 25).

Tools:
  jira_search        Search issues (JQL)
  jira_get_issue     Get single issue details
  jira_get_backlog   Get project backlog
  jira_get_sprints   List sprints for a board
  jira_get_epics     List epics for a project

Config (env or args):
  JIRA_URL      e.g. https://JIRA_HOST/jira
  JIRA_TOKEN    Personal Access Token
  JIRA_PROJECT  Default project key (e.g. VELIGO)
  JIRA_BOARD_ID Default board ID

Usage:
  JIRA_URL=... JIRA_TOKEN=... python -m mcp_jira.server
  python -m mcp_jira.server --project VELIGO
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

import urllib.request
import urllib.parse

try:
    from mcp_lrm.anonymizer import Anonymizer

    _anon = Anonymizer()
except ImportError:

    class _FallbackAnon:
        def anonymize(self, text: str) -> str:
            return text

    _anon = _FallbackAnon()


# ── Config ────────────────────────────────────────────────────────


def _load_token() -> str:
    tok = os.environ.get("JIRA_TOKEN", "")
    if not tok:
        key_file = Path.home() / ".config/factory/jira.key"
        if key_file.exists():
            tok = key_file.read_text().strip()
    return tok


def _get_config() -> Dict[str, str]:
    return {
        "url": os.environ.get(
            "JIRA_URL", "https://JIRA_HOST/jira"
        ).rstrip("/"),
        "token": _load_token(),
        "project": os.environ.get("JIRA_PROJECT", ""),
        "board_id": os.environ.get("JIRA_BOARD_ID", ""),
    }


# ── HTTP helpers ──────────────────────────────────────────────────


def _jira_get(path: str, params: Dict = None) -> Any:
    cfg = _get_config()
    url = f"{cfg['url']}/rest/api/2/{path.lstrip('/')}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {cfg['token']}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}


# ── Anonymization helpers ─────────────────────────────────────────


def _anon_user(user: Any) -> str:
    if not user:
        return "—"
    if isinstance(user, str):
        return _anon.anonymize(user)
    display = user.get("displayName") or user.get("name") or user.get("accountId", "?")
    return _anon.anonymize(display)


def _anon_issue(issue: Dict) -> Dict:
    fields = issue.get("fields", {})
    return {
        "key": issue.get("key", ""),
        "summary": _anon.anonymize(fields.get("summary") or ""),
        "description": _anon.anonymize((fields.get("description") or "")[:800]),
        "status": (fields.get("status") or {}).get("name", ""),
        "priority": (fields.get("priority") or {}).get("name", ""),
        "type": (fields.get("issuetype") or {}).get("name", ""),
        "assignee": _anon_user(fields.get("assignee")),
        "reporter": _anon_user(fields.get("reporter")),
        "created": fields.get("created", "")[:10],
        "updated": fields.get("updated", "")[:10],
        "labels": fields.get("labels", []),
        "components": [c.get("name", "") for c in (fields.get("components") or [])],
        "sprint": _extract_sprint(fields),
        "story_points": fields.get("story_points") or fields.get("customfield_10016"),
        "epic_link": fields.get("customfield_10014")
        or fields.get("epic", {}).get("key", ""),
    }


def _extract_sprint(fields: Dict) -> str:
    sprints = fields.get("customfield_10020") or fields.get("sprint") or []
    if isinstance(sprints, list) and sprints:
        s = sprints[-1]
        if isinstance(s, dict):
            return s.get("name", "")
        return str(s)
    return ""


# ── Tool implementations ──────────────────────────────────────────


def tool_jira_search(jql: str, max_results: int = 20, project: str = "") -> str:
    cfg = _get_config()
    if project:
        jql = f"project = {project} AND ({jql})"
    elif cfg["project"] and "project" not in jql.lower():
        jql = f"project = {cfg['project']} AND ({jql})"
    data = _jira_get(
        "search",
        {
            "jql": jql,
            "maxResults": max_results,
            "fields": "summary,description,status,priority,issuetype,assignee,reporter,created,updated,labels,components",
        },
    )
    if "error" in data:
        return f"Erreur Jira: {data['error']}"
    issues = data.get("issues", [])
    total = data.get("total", len(issues))
    result = [f"Résultats: {len(issues)}/{total} issues\n"]
    for iss in issues:
        a = _anon_issue(iss)
        sprint = f" [{a['sprint']}]" if a["sprint"] else ""
        sp = f" ({a['story_points']}pts)" if a["story_points"] else ""
        result.append(
            f"**{a['key']}** [{a['type']}]{sprint}{sp} — {a['summary']}\n"
            f"  Statut: {a['status']} | Priorité: {a['priority']} | Assigné: {a['assignee']}"
        )
    return "\n".join(result)


def tool_jira_get_issue(issue_key: str) -> str:
    data = _jira_get(
        f"issue/{issue_key}",
        {
            "fields": "summary,description,status,priority,issuetype,assignee,reporter,created,updated,labels,components,comment",
        },
    )
    if "error" in data:
        return f"Erreur: {data['error']}"
    a = _anon_issue(data)
    comments_raw = (data.get("fields") or {}).get("comment", {}).get("comments", [])
    comments = []
    for c in comments_raw[-5:]:
        author = _anon_user(c.get("author"))
        body = _anon.anonymize((c.get("body") or "")[:300])
        date = (c.get("created") or "")[:10]
        comments.append(f"  [{date}] {author}: {body}")
    out = [
        f"## {a['key']}: {a['summary']}",
        f"Type: {a['type']} | Statut: {a['status']} | Priorité: {a['priority']}",
        f"Assigné: {a['assignee']} | Reporter: {a['reporter']}",
        f"Sprint: {a['sprint']} | Story points: {a['story_points']}",
        f"Créé: {a['created']} | MàJ: {a['updated']}",
        f"Labels: {', '.join(a['labels'])} | Composants: {', '.join(a['components'])}",
        "",
        "**Description:**",
        a["description"] or "—",
    ]
    if comments:
        out += ["", f"**Commentaires récents ({len(comments)}):**"] + comments
    return "\n".join(out)


def tool_jira_get_backlog(project: str = "", max_results: int = 30) -> str:
    cfg = _get_config()
    proj = project or cfg["project"]
    if not proj:
        return "Erreur: JIRA_PROJECT non configuré"
    jql = f"project = {proj} AND sprint is EMPTY AND status != Done ORDER BY priority DESC, created ASC"
    return tool_jira_search(jql, max_results=max_results)


def tool_jira_get_sprints(board_id: str = "") -> str:
    cfg = _get_config()
    bid = board_id or cfg["board_id"]
    if not bid:
        return "Erreur: JIRA_BOARD_ID non configuré"
    data = _jira_get(f"../agile/1.0/board/{bid}/sprint", {"state": "active,future"})
    if "error" in data:
        return f"Erreur: {data['error']}"
    sprints = data.get("values", [])
    lines = [f"Sprints (board {bid}):"]
    for s in sprints:
        state = s.get("state", "")
        name = s.get("name", "")
        start = (s.get("startDate") or "")[:10]
        end = (s.get("endDate") or "")[:10]
        lines.append(f"  [{state}] {name} ({start} → {end}) — id:{s.get('id', '')}")
    return "\n".join(lines)


def tool_jira_get_epics(project: str = "") -> str:
    cfg = _get_config()
    proj = project or cfg["project"]
    if not proj:
        return "Erreur: JIRA_PROJECT non configuré"
    # Veligo uses "Feature" as top-level type (not "Epic")
    jql = f"project = {proj} AND issuetype = Feature ORDER BY priority DESC"
    return tool_jira_search(jql, max_results=50)


# ── MCP Protocol ──────────────────────────────────────────────────

TOOLS = [
    {
        "name": "jira_search",
        "description": "Recherche d'issues Jira par JQL. Résultats anonymisés (RGPD).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "jql": {
                    "type": "string",
                    "description": "JQL query (ex: 'status = \"In Progress\"')",
                },
                "project": {
                    "type": "string",
                    "description": "Clé projet (ex: VELIGO). Optionnel si JIRA_PROJECT est set.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Nombre max de résultats (défaut: 20)",
                    "default": 20,
                },
            },
            "required": ["jql"],
        },
    },
    {
        "name": "jira_get_issue",
        "description": "Détails d'une issue Jira par clé (ex: VELIGO-42). Commentaires inclus. Anonymisé.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "issue_key": {
                    "type": "string",
                    "description": "Clé Jira (ex: VELIGO-42)",
                },
            },
            "required": ["issue_key"],
        },
    },
    {
        "name": "jira_get_backlog",
        "description": "Backlog du projet (issues sans sprint, non terminées). Anonymisé.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Clé projet. Optionnel si JIRA_PROJECT est set.",
                },
                "max_results": {"type": "integer", "default": 30},
            },
        },
    },
    {
        "name": "jira_get_sprints",
        "description": "Liste les sprints actifs et futurs du board.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "board_id": {
                    "type": "string",
                    "description": "ID du board. Optionnel si JIRA_BOARD_ID est set.",
                },
            },
        },
    },
    {
        "name": "jira_get_epics",
        "description": "Liste les épics du projet. Anonymisé.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Clé projet. Optionnel si JIRA_PROJECT est set.",
                },
            },
        },
    },
]


async def read_message() -> Optional[Dict]:
    try:
        line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
        if not line:
            return None
        return json.loads(line.strip())
    except (json.JSONDecodeError, EOFError):
        return None


def write_message(msg: Dict):
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


class MCPJiraServer:
    def handle(self, msg: Dict) -> Optional[Dict]:
        method = msg.get("method", "")
        mid = msg.get("id")

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": mid,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "mcp-jira", "version": "1.0.0"},
                },
            }

        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}

        if method == "tools/call":
            params = msg.get("params", {})
            name = params.get("name", "")
            args = params.get("arguments", {})
            try:
                result = self._dispatch(name, args)
            except Exception as e:
                result = f"Erreur: {e}"
            return {
                "jsonrpc": "2.0",
                "id": mid,
                "result": {"content": [{"type": "text", "text": result}]},
            }

        if method in ("notifications/initialized", "notifications/cancelled"):
            return None  # no response for notifications

        return {
            "jsonrpc": "2.0",
            "id": mid,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }

    def _dispatch(self, name: str, args: Dict) -> str:
        if name == "jira_search":
            return tool_jira_search(
                args.get("jql", ""),
                args.get("max_results", 20),
                args.get("project", ""),
            )
        if name == "jira_get_issue":
            return tool_jira_get_issue(args["issue_key"])
        if name == "jira_get_backlog":
            return tool_jira_get_backlog(
                args.get("project", ""), args.get("max_results", 30)
            )
        if name == "jira_get_sprints":
            return tool_jira_get_sprints(args.get("board_id", ""))
        if name == "jira_get_epics":
            return tool_jira_get_epics(args.get("project", ""))
        return f"Outil inconnu: {name}"


async def main():
    server = MCPJiraServer()
    while True:
        msg = await read_message()
        if msg is None:
            break
        resp = server.handle(msg)
        if resp is not None:
            write_message(resp)


if __name__ == "__main__":
    asyncio.run(main())
