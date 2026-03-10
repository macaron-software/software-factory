#!/usr/bin/env python3
"""
MCP Confluence Server — anonymized Confluence access for SF agents
=================================================================
Wraps Confluence REST API and strips PII before returning to LLM (RGPD Art. 25).

Tools:
  confluence_get_page     Get page content by ID or title
  confluence_search       Full-text search across a space
  confluence_get_space    List pages in a space
  confluence_get_children List child pages

Config (env):
  CONFLUENCE_URL    e.g. https://CONFLUENCE_HOST/confluence
  CONFLUENCE_TOKEN  Personal Access Token (same as Jira PAT usually)
  CONFLUENCE_SPACE  Default space key (e.g. MYPROJECT)

Usage:
  CONFLUENCE_URL=... CONFLUENCE_TOKEN=... python -m mcp_confluence.server
"""

import asyncio
import json
import os
import re
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
    tok = os.environ.get("CONFLUENCE_TOKEN", "")
    if not tok:
        # Try confluence.key first, then jira.key (same PAT at the client)
        for fname in ("confluence.key", "jira.key"):
            key_file = Path.home() / f".config/factory/{fname}"
            if key_file.exists():
                tok = key_file.read_text().strip()
                break
    return tok


def _get_config() -> Dict[str, str]:
    return {
        "url": os.environ.get(
            "CONFLUENCE_URL", "https://CONFLUENCE_HOST/confluence"
        ).rstrip("/"),
        "token": _load_token(),
        "space": os.environ.get("CONFLUENCE_SPACE", ""),
    }


# ── HTTP helpers ──────────────────────────────────────────────────


def _cf_get(path: str, params: Dict = None) -> Any:
    cfg = _get_config()
    url = f"{cfg['url']}/rest/api/{path.lstrip('/')}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {cfg['token']}")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}


# ── HTML → text + anonymize ───────────────────────────────────────

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s{3,}")


def _strip_html(html: str) -> str:
    text = _TAG_RE.sub(" ", html or "")
    text = _WS_RE.sub("\n", text)
    return text.strip()


def _clean_page(body: str, max_chars: int = 4000) -> str:
    text = _strip_html(body)
    text = _anon.anonymize(text)
    return text[:max_chars]


def _anon_user(user: Any) -> str:
    if not user:
        return "—"
    if isinstance(user, str):
        return _anon.anonymize(user)
    # Prefer email (anonymizable) over display name
    email = user.get("username") or user.get("email") or ""
    if email and "@" in email:
        return _anon.anonymize(email)
    display = user.get("displayName") or "?"
    # Mask display name: "Violaine RIESSER" → "V. R."
    parts = display.split()
    if len(parts) >= 2:
        return " ".join(p[0] + "." for p in parts)
    return _anon.anonymize(display)


# ── Tool implementations ──────────────────────────────────────────


def tool_confluence_get_page(
    page_id: str = "", title: str = "", space: str = ""
) -> str:
    cfg = _get_config()
    sp = space or cfg["space"]

    if not page_id and title:
        # Search by title
        params = {"title": title, "expand": "body.storage,version,ancestors"}
        if sp:
            params["spaceKey"] = sp
        data = _cf_get("content", params)
        if "error" in data:
            return f"Erreur: {data['error']}"
        results = data.get("results", [])
        if not results:
            return f"Page '{title}' introuvable"
        page_id = results[0]["id"]

    if not page_id:
        return "Erreur: page_id ou title requis"

    data = _cf_get(
        f"content/{page_id}", {"expand": "body.storage,version,ancestors,children.page"}
    )
    if "error" in data:
        return f"Erreur: {data['error']}"

    title_out = _anon.anonymize(data.get("title", ""))
    body = _clean_page((data.get("body") or {}).get("storage", {}).get("value", ""))
    version = (data.get("version") or {}).get("number", "?")
    author = _anon_user((data.get("version") or {}).get("by"))
    ancestors = " > ".join(a.get("title", "") for a in (data.get("ancestors") or []))
    children = [
        c.get("title", "")
        for c in (data.get("children") or {}).get("page", {}).get("results", [])
    ]

    out = [
        f"# {title_out}",
        f"ID: {page_id} | Version: {version} | Auteur: {author}",
    ]
    if ancestors:
        out.append(f"Chemin: {ancestors}")
    if children:
        out.append(f"Sous-pages: {', '.join(children[:10])}")
    out += ["", body]
    return "\n".join(out)


def tool_confluence_search(query: str, space: str = "", max_results: int = 10) -> str:
    cfg = _get_config()
    sp = space or cfg["space"]
    cql = f'text ~ "{query}" AND type = page'
    if sp:
        cql += f' AND space = "{sp}"'
    data = _cf_get(
        "content/search",
        {
            "cql": cql,
            "limit": max_results,
            "expand": "version",
        },
    )
    if "error" in data:
        return f"Erreur: {data['error']}"
    results = data.get("results", [])
    total = data.get("totalSize", len(results))
    lines = [f"Résultats: {len(results)}/{total} pages pour '{query}'\n"]
    for r in results:
        title = _anon.anonymize(r.get("title", ""))
        pid = r.get("id", "")
        sp_key = (r.get("space") or {}).get("key", "")
        lines.append(f"  [{sp_key}] **{title}** (id:{pid})")
    return "\n".join(lines)


def tool_confluence_get_space(space: str = "", max_results: int = 30) -> str:
    cfg = _get_config()
    sp = space or cfg["space"]
    if not sp:
        return "Erreur: CONFLUENCE_SPACE non configuré"
    data = _cf_get(
        "content",
        {
            "spaceKey": sp,
            "type": "page",
            "limit": max_results,
            "expand": "version,ancestors",
        },
    )
    if "error" in data:
        return f"Erreur: {data['error']}"
    results = data.get("results", [])
    lines = [f"Pages dans l'espace {sp} ({len(results)} résultats):"]
    for r in results:
        title = _anon.anonymize(r.get("title", ""))
        pid = r.get("id", "")
        depth = len(r.get("ancestors", []))
        indent = "  " * depth
        lines.append(f"{indent}• {title} (id:{pid})")
    return "\n".join(lines)


def tool_confluence_get_children(page_id: str) -> str:
    data = _cf_get(f"content/{page_id}/child/page", {"limit": 50, "expand": "version"})
    if "error" in data:
        return f"Erreur: {data['error']}"
    results = data.get("results", [])
    lines = [f"Sous-pages de {page_id} ({len(results)}):"]
    for r in results:
        title = _anon.anonymize(r.get("title", ""))
        pid = r.get("id", "")
        lines.append(f"  • {title} (id:{pid})")
    return "\n".join(lines)


# ── MCP Protocol ──────────────────────────────────────────────────

TOOLS = [
    {
        "name": "confluence_get_page",
        "description": "Récupère le contenu d'une page Confluence par ID ou titre. Anonymisé (RGPD).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "page_id": {
                    "type": "string",
                    "description": "ID numérique de la page (ex: 1151407255)",
                },
                "title": {
                    "type": "string",
                    "description": "Titre exact de la page (alternatif à page_id)",
                },
                "space": {
                    "type": "string",
                    "description": "Clé espace (ex: MYPROJECT). Optionnel si CONFLUENCE_SPACE set.",
                },
            },
        },
    },
    {
        "name": "confluence_search",
        "description": "Recherche full-text dans Confluence (CQL). Résultats anonymisés.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Texte à rechercher"},
                "space": {
                    "type": "string",
                    "description": "Clé espace pour filtrer (ex: MYPROJECT)",
                },
                "max_results": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "confluence_get_space",
        "description": "Liste les pages d'un espace Confluence. Anonymisé.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "space": {
                    "type": "string",
                    "description": "Clé espace. Optionnel si CONFLUENCE_SPACE set.",
                },
                "max_results": {"type": "integer", "default": 30},
            },
        },
    },
    {
        "name": "confluence_get_children",
        "description": "Liste les sous-pages d'une page Confluence.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "page_id": {"type": "string", "description": "ID de la page parente"},
            },
            "required": ["page_id"],
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


class MCPConfluenceServer:
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
                    "serverInfo": {"name": "mcp-confluence", "version": "1.0.0"},
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
            return None

        return {
            "jsonrpc": "2.0",
            "id": mid,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }

    def _dispatch(self, name: str, args: Dict) -> str:
        if name == "confluence_get_page":
            return tool_confluence_get_page(
                args.get("page_id", ""), args.get("title", ""), args.get("space", "")
            )
        if name == "confluence_search":
            return tool_confluence_search(
                args["query"], args.get("space", ""), args.get("max_results", 10)
            )
        if name == "confluence_get_space":
            return tool_confluence_get_space(
                args.get("space", ""), args.get("max_results", 30)
            )
        if name == "confluence_get_children":
            return tool_confluence_get_children(args["page_id"])
        return f"Outil inconnu: {name}"


async def main():
    server = MCPConfluenceServer()
    while True:
        msg = await read_message()
        if msg is None:
            break
        resp = server.handle(msg)
        if resp is not None:
            write_message(resp)


if __name__ == "__main__":
    asyncio.run(main())
