"""CTO Chat — Jarvis de la Software Factory.

Onglet "CTO" dans le Portfolio : chat avec Karim Benali (strat-cto),
agent exécutif avec accès aux outils plateforme, web, GitHub et création de ressources.
"""

from __future__ import annotations

import html as html_mod
import json
import logging

import markdown as md_lib
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from starlette.requests import Request

from .helpers import _parse_body, _templates

logger = logging.getLogger(__name__)

router = APIRouter()

_CTO_AGENT_ID = "strat-cto"
_CTO_SESSION_TYPE = "cto_chat"


def _list_cto_sessions(limit: int = 50):
    """Return all CTO chat sessions, newest first."""
    from ...sessions.store import get_session_store

    store = get_session_store()
    all_sessions = store.list_all(limit=200)
    cto = [s for s in all_sessions if (s.config or {}).get("type") == _CTO_SESSION_TYPE]
    return cto[:limit]


def _create_cto_session(title: str = "") -> object:
    """Create a new CTO chat session."""
    from ...sessions.store import get_session_store, SessionDef, MessageDef

    store = get_session_store()
    session = store.create(
        SessionDef(
            name=title or "Nouvelle conversation",
            goal="Pilotage de la Software Factory — analyses, métriques, création de projets/missions.",
            status="active",
            config={"lead_agent": _CTO_AGENT_ID, "type": _CTO_SESSION_TYPE},
        )
    )
    store.add_message(
        MessageDef(
            session_id=session.id,
            from_agent="system",
            message_type="system",
            content="Session CTO initialisée. Karim Benali est disponible.",
        )
    )
    return session


def _get_or_create_latest_cto_session():
    """Return the most recent CTO session, creating one if none exists."""
    sessions = _list_cto_sessions(limit=1)
    return sessions[0] if sessions else _create_cto_session()


def _session_title(session) -> str:
    """Return a display title for a session (first user msg or name)."""
    from ...sessions.store import get_session_store

    store = get_session_store()
    msgs = store.get_messages(session.id, limit=5)
    for m in msgs:
        if m.from_agent == "user" and m.content:
            t = m.content.strip()
            return t[:55] + ("…" if len(t) > 55 else "")
    return session.name or "Conversation"


def _build_history_html(session_id: str) -> str:
    """Build chat messages HTML for a session."""
    from ...sessions.store import get_session_store

    store = get_session_store()
    messages = store.get_messages(session_id, limit=50)
    history_html = ""
    for msg in messages:
        if msg.message_type == "system":
            continue
        if msg.from_agent == "user":
            history_html += (
                f'<div class="chat-msg chat-msg-user">'
                f'<div class="chat-msg-body"><div class="chat-msg-text">{html_mod.escape(msg.content or "")}</div></div>'
                f'<div class="chat-msg-avatar user">S</div>'
                f"</div>"
            )
        else:
            rendered = md_lib.markdown(
                msg.content or "",
                extensions=["fenced_code", "tables", "nl2br"],
            )
            tool_calls = (
                (msg.metadata or {}).get("tool_calls") if msg.metadata else None
            )
            tools_html = ""
            if tool_calls:
                pills = "".join(
                    f'<span class="chat-tool-pill">'
                    f'<svg class="icon icon-xs"><use href="#icon-wrench"/></svg> '
                    f"{html_mod.escape(str(tc.get('name', tc) if isinstance(tc, dict) else tc))}</span>"
                    for tc in tool_calls
                )
                tools_html = f'<div class="chat-msg-tools">{pills}</div>'
            history_html += (
                f'<div class="chat-msg chat-msg-agent">'
                f'<div class="chat-msg-avatar cto-avatar"></div>'
                f'<div class="chat-msg-body">'
                f'<div class="chat-msg-sender">Karim Benali — CTO</div>'
                f'<div class="chat-msg-text md-rendered">{rendered}</div>'
                f"{tools_html}"
                f"</div></div>"
            )
    return history_html


@router.get("/cto", response_class=HTMLResponse)
async def cto_panel(request: Request):
    """Render the CTO chat panel with sidebar (htmx partial)."""
    from ...agents.store import get_agent_store

    agent_store = get_agent_store()
    agent = agent_store.get(_CTO_AGENT_ID)

    session = _get_or_create_latest_cto_session()
    sessions = _list_cto_sessions(limit=30)

    # Build sidebar items
    sidebar_items = []
    for s in sessions:
        sidebar_items.append(
            {
                "id": s.id,
                "title": _session_title(s),
                "ts": str(s.created_at or "")[:10],
                "active": s.id == session.id,
            }
        )

    history_html = _build_history_html(session.id)

    templates = _templates(request)
    return templates.TemplateResponse(
        "cto_panel.html",
        {
            "request": request,
            "session_id": session.id,
            "history_html": history_html,
            "sidebar_items": sidebar_items,
            "agent": agent,
        },
    )


@router.get("/api/cto/session")
async def cto_session():
    """Get or create the latest CTO session, return its id."""
    session = _get_or_create_latest_cto_session()
    return JSONResponse({"session_id": session.id, "status": session.status})


@router.post("/api/cto/sessions/new", response_class=JSONResponse)
async def cto_new_session():
    """Create a new CTO chat session."""
    session = _create_cto_session()
    return JSONResponse({"session_id": session.id})


@router.get("/api/cto/sessions/{session_id}/messages", response_class=HTMLResponse)
async def cto_load_session(session_id: str, request: Request):
    """Load messages for a CTO session (for sidebar switching)."""
    history_html = _build_history_html(session_id)
    return HTMLResponse(history_html or "")


def _resolve_mentions(content: str) -> str:
    """Replace @ProjectName mentions with rich project context for the LLM."""
    import re

    mentions = re.findall(r"@([\w\-]+)", content)
    if not mentions:
        return content
    try:
        from ...projects.manager import get_project_store
        from ...missions.store import get_mission_store

        ps = get_project_store()
        ms = get_mission_store()
        all_projects = ps.list_all()
        injected = []
        for mention in mentions:
            mention_lower = mention.lower().replace("-", " ").replace("_", " ")
            # Find project by name (fuzzy: starts with or contains)
            match = None
            for p in all_projects:
                pname = p.name.lower().replace("-", " ").replace("_", " ")
                if (
                    pname == mention_lower
                    or pname.startswith(mention_lower)
                    or mention_lower in pname
                ):
                    match = p
                    break
            if not match:
                continue
            # Gather missions for this project
            missions = ms.list(project_id=match.id, limit=10)
            m_lines = (
                "\n".join(
                    f"  - [{m.status}] {m.name} (workflow: {m.workflow_id or '?'})"
                    for m in missions
                )
                or "  - Aucune mission"
            )
            workspace = match.path or ""
            ctx_block = (
                f"\n\n--- Contexte projet @{mention} ---\n"
                f"Nom: {match.name}\n"
                f"ID: {match.id}\n"
                f"Description: {match.description or '(non renseignée)'}\n"
                f"Type: {match.factory_type or '?'} | Statut: {match.status or '?'}\n"
                f"Domaines: {', '.join(match.domains) if match.domains else '?'}\n"
                f"Git URL: {match.git_url or '(non configuré)'}\n"
                f"Workspace (cwd pour outils git/code): {workspace or '(non configuré — utilise create_project pour en créer un)'}\n"
                f"Vision: {match.vision[:300] + '...' if match.vision and len(match.vision) > 300 else (match.vision or '(non définie)')}\n"
                f"Missions:\n{m_lines}\n"
                f"IMPORTANT: Pour toute opération git/code sur ce projet, utilise cwd='{workspace}' (pas '.')\n"
                f"---\n"
            )
            injected.append(ctx_block)
        return content + "".join(injected)
    except Exception as e:
        logger.warning("_resolve_mentions failed: %s", e)
        return content


@router.post("/api/cto/message")
async def cto_message(request: Request):
    """Send a message to the CTO agent, return SSE stream."""
    from ...sessions.store import get_session_store, MessageDef
    from ...agents.executor import get_executor

    data = await _parse_body(request)
    content = str(data.get("content") or data.get("message", "")).strip()
    display = str(data.get("display") or content).strip()
    session_id = str(data.get("session_id", "")).strip()
    if not content:
        return HTMLResponse("")

    # Resolve @Project mentions → inject project context for the LLM
    content_with_ctx = _resolve_mentions(content)

    # Resolve session
    store = get_session_store()
    if session_id:
        session = store.get(session_id) or _get_or_create_latest_cto_session()
    else:
        session = _get_or_create_latest_cto_session()

    store.add_message(
        MessageDef(
            session_id=session.id,
            from_agent="user",
            message_type="text",
            content=content,
        )
    )

    user_html = (
        f'<div class="chat-msg chat-msg-user">'
        f'<div class="chat-msg-body"><div class="chat-msg-text">{html_mod.escape(display)}</div></div>'
        f'<div class="chat-msg-avatar user">S</div>'
        f"</div>"
    )

    def sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    async def event_generator():
        yield sse("user_html", {"html": user_html, "session_id": session.id})

        try:
            from ...agents.store import get_agent_store

            agent_store = get_agent_store()
            agent = agent_store.get(_CTO_AGENT_ID)
            if not agent:
                yield sse("error", {"message": "CTO agent not found"})
                return

            from ...sessions.runner import _build_context

            ctx = await _build_context(agent, session)

            executor = get_executor()
            result = None

            async for event_type_s, data_s in executor.run_streaming(
                ctx, content_with_ctx
            ):
                if event_type_s == "delta":
                    yield sse("chunk", {"text": data_s})
                elif event_type_s == "result":
                    result = data_s

            if not result:
                yield sse("error", {"message": "No response from agent"})
                return

            store.add_message(
                MessageDef(
                    session_id=session.id,
                    from_agent=_CTO_AGENT_ID,
                    to_agent="user",
                    message_type="text",
                    content=result.content,
                    metadata={
                        "model": result.model,
                        "provider": result.provider,
                        "tokens_in": result.tokens_in,
                        "tokens_out": result.tokens_out,
                        "duration_ms": result.duration_ms,
                        "tool_calls": result.tool_calls if result.tool_calls else None,
                    },
                )
            )

            tool_calls = result.tool_calls or []
            tools_html = ""
            if tool_calls:
                pills = "".join(
                    f'<span class="chat-tool-pill">'
                    f"{html_mod.escape(str(tc.get('name', tc) if isinstance(tc, dict) else tc))}</span>"
                    for tc in tool_calls
                )
                tools_html = f'<div class="chat-msg-tools">{pills}</div>'

            rendered = md_lib.markdown(
                str(result.content),
                extensions=["fenced_code", "tables", "nl2br"],
            )
            agent_html = (
                f'<div class="chat-msg chat-msg-agent">'
                f'<div class="chat-msg-avatar cto-avatar"></div>'
                f'<div class="chat-msg-body">'
                f'<div class="chat-msg-sender">Karim Benali — CTO</div>'
                f'<div class="chat-msg-text md-rendered">{rendered}</div>'
                f"{tools_html}"
                f"</div></div>"
            )
            title_hint = html_mod.escape(display[:55])
            yield sse(
                "done",
                {
                    "html": agent_html,
                    "session_id": session.id,
                    "title_hint": title_hint,
                },
            )

        except Exception as exc:
            logger.exception("CTO streaming error")
            yield sse("error", {"message": str(exc)[:200]})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── File upload ──────────────────────────────────────────────────────────────

_TEXT_EXTS = {
    ".txt",
    ".md",
    ".rst",
    ".csv",
    ".json",
    ".yaml",
    ".yml",
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".html",
    ".css",
    ".scss",
    ".java",
    ".kt",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".sh",
    ".xml",
    ".sql",
    ".toml",
    ".ini",
    ".cfg",
    ".env",
}
_MAX_CHARS = 40_000  # clip to avoid exploding the context window


@router.post("/api/cto/upload")
async def cto_upload(file: UploadFile = File(...)):
    """Extract text from an uploaded file and return it for injection into chat."""
    import io
    import os

    name = file.filename or "document"
    ext = os.path.splitext(name)[1].lower()
    data = await file.read()

    text = ""
    error = ""

    try:
        if ext in _TEXT_EXTS:
            text = data.decode("utf-8", errors="replace")
        elif ext == ".pdf":
            try:
                import pypdf  # type: ignore

                reader = pypdf.PdfReader(io.BytesIO(data))
                parts = []
                for page in reader.pages:
                    t = page.extract_text() or ""
                    if t.strip():
                        parts.append(t)
                text = "\n\n".join(parts)
            except Exception as exc:
                error = f"PDF parsing failed: {exc}"
        elif ext in (".docx", ".doc"):
            try:
                import docx  # type: ignore

                doc = docx.Document(io.BytesIO(data))
                text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            except Exception as exc:
                error = f"DOCX parsing failed: {exc}"
        else:
            # Try UTF-8 decode as last resort
            try:
                text = data.decode("utf-8", errors="replace")
            except Exception:
                error = f"Format non supporté : {ext}"
    except Exception as exc:
        error = str(exc)

    if error and not text:
        return JSONResponse({"ok": False, "error": error, "name": name})

    truncated = len(text) > _MAX_CHARS
    text = text[:_MAX_CHARS]

    return JSONResponse(
        {
            "ok": True,
            "name": name,
            "ext": ext,
            "size": len(data),
            "chars": len(text),
            "truncated": truncated,
            "text": text,
        }
    )
