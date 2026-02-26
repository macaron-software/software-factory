"""CTO Chat — Jarvis de la Software Factory.

Onglet "CTO" dans le Portfolio : chat avec Karim Benali (strat-cto),
agent exécutif avec accès aux outils plateforme, web, GitHub et création de ressources.
"""

from __future__ import annotations

import html as html_mod
import logging

import markdown as md_lib
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.requests import Request

from .helpers import _parse_body, _templates

logger = logging.getLogger(__name__)

router = APIRouter()

_CTO_AGENT_ID = "strat-cto"
_CTO_SESSION_NAME = "cto-global"


def _get_or_create_cto_session():
    """Return the singleton CTO session, creating it if needed."""
    from ...sessions.store import get_session_store, SessionDef, MessageDef

    store = get_session_store()
    sessions = [
        s
        for s in store.list_all()
        if s.name == _CTO_SESSION_NAME and s.status == "active"
    ]
    if sessions:
        return sessions[0]

    session = store.create(
        SessionDef(
            name=_CTO_SESSION_NAME,
            goal="Pilotage de la Software Factory — analyses, métriques, création de projets/missions.",
            status="active",
            config={"lead_agent": _CTO_AGENT_ID, "type": "cto_chat"},
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


@router.get("/cto", response_class=HTMLResponse)
async def cto_panel(request: Request):
    """Render the CTO chat panel (htmx partial)."""
    from ...agents.store import get_agent_store
    from ...sessions.store import get_session_store

    agent_store = get_agent_store()
    agent = agent_store.get(_CTO_AGENT_ID)

    session = _get_or_create_cto_session()
    store = get_session_store()
    messages = store.get_messages(session.id, limit=50)

    # Build chat history HTML
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

    templates = _templates(request)
    return templates.TemplateResponse(
        "cto_panel.html",
        {
            "request": request,
            "session_id": session.id,
            "history_html": history_html,
            "agent": agent,
        },
    )


@router.get("/api/cto/session")
async def cto_session():
    """Get or create the CTO session, return its id."""
    session = _get_or_create_cto_session()
    return JSONResponse({"session_id": session.id, "status": session.status})


@router.post("/api/cto/message", response_class=HTMLResponse)
async def cto_message(request: Request):
    """Send a message to the CTO agent, return chat bubbles HTML."""
    from ...sessions.store import get_session_store, MessageDef
    from ...sessions.runner import handle_user_message

    data = await _parse_body(request)
    content = str(data.get("content", "")).strip()
    if not content:
        return HTMLResponse("")

    session = _get_or_create_cto_session()
    store = get_session_store()

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
        f'<div class="chat-msg-body"><div class="chat-msg-text">{html_mod.escape(content)}</div></div>'
        f'<div class="chat-msg-avatar user">S</div>'
        f"</div>"
    )

    agent_msg = await handle_user_message(session.id, content, _CTO_AGENT_ID)

    if agent_msg:
        agent_content = (
            agent_msg.get("content", "")
            if isinstance(agent_msg, dict)
            else getattr(agent_msg, "content", str(agent_msg))
        )
        tool_calls = None
        if isinstance(agent_msg, dict):
            tool_calls = (agent_msg.get("metadata") or {}).get("tool_calls")
        elif hasattr(agent_msg, "metadata") and agent_msg.metadata:
            tool_calls = agent_msg.metadata.get("tool_calls")

        tools_html = ""
        if tool_calls:
            pills = "".join(
                f'<span class="chat-tool-pill">'
                f'<svg class="icon icon-xs"><use href="#icon-wrench"/></svg> '
                f"{html_mod.escape(str(tc.get('name', tc) if isinstance(tc, dict) else tc))}</span>"
                for tc in tool_calls
            )
            tools_html = f'<div class="chat-msg-tools">{pills}</div>'

        rendered = md_lib.markdown(
            str(agent_content),
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
        return HTMLResponse(user_html + agent_html)

    return HTMLResponse(user_html)
