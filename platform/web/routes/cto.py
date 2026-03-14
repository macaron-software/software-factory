"""CTO Chat — Jarvis de la Software Factory.

Onglet "CTO" dans le Portfolio : chat avec Karim Benali (strat-cto),
agent exécutif avec accès aux outils plateforme, web, GitHub et création de ressources.
"""
# Ref: feat-cto

from __future__ import annotations

import html as html_mod
import json
import logging

import markdown as md_lib
from fastapi import Depends,  APIRouter, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from starlette.requests import Request

from .helpers import _parse_body, _templates, _avatar_url
from .sse_utils import sse
from ...auth.middleware import require_auth

logger = logging.getLogger(__name__)

router = APIRouter()

_CTO_AGENT_ID = "strat-cto"
_CTO_SESSION_TYPE = "cto_chat"


def _list_cto_sessions(limit: int = 50):
    """Return all CTO chat sessions, newest first."""
    from ...sessions.store import get_session_store

    store = get_session_store()
    # Use list_by_config_type to avoid the list_all(limit=200) cap that could
    # miss CTO sessions when many agent sessions exist.
    return store.list_by_config_type(_CTO_SESSION_TYPE, limit=limit)


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
    from ...agents.store import get_agent_store

    store = get_session_store()
    agent_store = get_agent_store()
    messages = [
        m
        for m in store.get_messages(session_id, limit=200)
        if m.message_type != "system"
    ]
    history_html = ""
    for msg in messages:
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
                extensions=["fenced_code", "tables"],
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

            if msg.from_agent == _CTO_AGENT_ID:
                history_html += (
                    f'<div class="chat-msg chat-msg-agent">'
                    f'<div class="chat-msg-avatar cto-avatar"></div>'
                    f'<div class="chat-msg-body">'
                    f'<div class="chat-msg-sender">Karim Benali — CTO</div>'
                    f'<div class="chat-msg-text md-rendered">{rendered}</div>'
                    f"{tools_html}"
                    f"</div></div>"
                )
            else:
                # Invited agent — look up their name/avatar
                inv = agent_store.get(msg.from_agent)
                inv_name = inv.name if inv else (msg.from_agent or "Agent")
                inv_role = (inv.role or "") if inv else ""
                av_url = _avatar_url(msg.from_agent)
                initials = "".join(w[0].upper() for w in inv_name.split()[:2])
                av_html = (
                    f'<img class="invited-avatar-img" src="{html_mod.escape(av_url)}" alt="{html_mod.escape(inv_name)}">'
                    if av_url
                    else f'<div class="invited-avatar invited-avatar-initials">{initials}</div>'
                )
                history_html += (
                    f'<div class="chat-msg chat-msg-invited">'
                    f"{av_html}"
                    f'<div class="chat-msg-body">'
                    f'<div class="chat-msg-sender">{html_mod.escape(inv_name)}'
                    + (f" — {html_mod.escape(inv_role)}" if inv_role else "")
                    + f"</div>"
                    f'<div class="chat-msg-text md-rendered">{rendered}</div>'
                    f"{tools_html}"
                    f"</div></div>"
                )

    # Detect interrupted: last message is from user → show retry bar
    if messages and messages[-1].from_agent == "user":
        last_content = messages[-1].content or ""
        short = last_content[:60] + "…" if len(last_content) > 60 else last_content
        safe_content = html_mod.escape(last_content).replace('"', "&#34;")
        safe_short = html_mod.escape(short)
        history_html += (
            f'<div class="cto-retry-bar" data-msg="{safe_content}">'
            f'<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
            f'<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>'
            f'<span class="retry-msg" title="Conversation interrompue">Conversation interrompue — «{safe_short}»</span>'
            f'<button class="cto-retry-btn edit" onclick="ctoRetryEdit()">Modifier</button>'
            f'<button class="cto-retry-btn" onclick="ctoRetryResend()">Relancer</button>'
            f"</div>"
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


@router.post("/api/cto/sessions/new", response_class=JSONResponse, dependencies=[Depends(require_auth())])
async def cto_new_session():
    """Create a new CTO chat session."""
    session = _create_cto_session()
    return JSONResponse({"session_id": session.id})


@router.get("/api/cto/sessions/{session_id}/messages", response_class=HTMLResponse)
async def cto_load_session(session_id: str, request: Request):
    """Load messages for a CTO session (for sidebar switching)."""
    history_html = _build_history_html(session_id)
    return HTMLResponse(history_html or "")


# ── Key agents invitable in CTO chat ────────────────────────────────────────
_INVITABLE_ROLES = {
    "Program Manager",
    "Project Manager",
    "Lean Portfolio Manager",
    "Chief Technology Officer",
    "Solution Architect",
    "Architect",
    "Product Manager",
    "Mobile Architect",
    "Release Manager",
    "Test Manager",
    "Change Manager",
    "Solution Manager",
}
_INVITABLE_PREFIXES = (
    "strat-",
    "chef_de_programme",
    "chef_projet",
    "architecte",
    "lean_portfolio",
    "product-manager-art",
    "test_manager",
    "change_manager",
    "solution_manager",
)


def _get_invitable_agents():
    """Return agents that can be invited into the CTO chat."""
    from ...agents.store import get_agent_store

    store = get_agent_store()
    agents = store.list_all()
    result = []
    for a in agents:
        if a.id == _CTO_AGENT_ID:
            continue
        role = a.role or ""
        is_key = (
            role in _INVITABLE_ROLES
            or any(a.id.startswith(p) for p in _INVITABLE_PREFIXES)
            or role
            in (
                "chef_de_programme",
                "chef_projet",
                "lean_portfolio_manager",
                "architecte",
                "product-manager-art",
                "test_manager",
                "change_manager",
                "solution_manager",
            )
        )
        if is_key:
            result.append(a)
    return result[:30]


@router.get("/api/cto/mention-list", response_class=JSONResponse)
async def cto_mention_list(type: str = "all"):
    """Return projects (type=project), agents (type=agent), or both (type=all)."""
    from ...projects.manager import get_project_store

    items = []
    if type in ("project", "all"):
        try:
            ps = get_project_store()
            for p in ps.list_all():  # no limit — frontend already slices to 12
                has_content = bool(p.description or p.vision)
                if has_content:
                    sub = (p.description or p.vision or "")[:50].replace("\n", " ")
                else:
                    sub = "⚠ aucun contenu"
                items.append(
                    {
                        "type": "project",
                        "id": p.id,
                        "name": p.name,
                        "sub": sub,
                        "empty": not has_content,
                    }
                )
        except Exception:
            pass
    if type in ("agent", "all"):
        try:
            for a in _get_invitable_agents():
                items.append(
                    {"type": "agent", "id": a.id, "name": a.name, "sub": a.role or ""}
                )
        except Exception:
            pass
    return JSONResponse(items)


@router.get("/api/cto/search", response_class=JSONResponse)
async def cto_search(q: str = ""):
    """Search CTO conversations by title and message content. Returns matching sessions."""
    if not q or len(q.strip()) < 2:
        return JSONResponse([])
    from ...sessions.store import get_session_store

    store = get_session_store()
    q_lower = q.strip().lower()
    results = []
    try:
        sessions = _list_cto_sessions(limit=200)
        for s in sessions:
            title = _session_title(s).lower()
            score = 0
            snippet = ""
            if q_lower in title:
                score += 10
            # Search message content
            try:
                msgs = store.get_messages(s.id, limit=100)
                for msg in msgs:
                    content = (msg.content or "").lower()
                    if q_lower in content:
                        score += 5
                        # Extract a snippet around the match
                        idx = content.find(q_lower)
                        start = max(0, idx - 40)
                        end = min(len(msg.content), idx + len(q_lower) + 60)
                        raw = msg.content[start:end].replace("\n", " ").strip()
                        if start > 0:
                            raw = "…" + raw
                        if end < len(msg.content):
                            raw += "…"
                        snippet = raw
                        break
            except Exception:
                pass
            if score > 0:
                results.append(
                    {
                        "id": s.id,
                        "title": _session_title(s),
                        "ts": str(s.created_at or "")[:10],
                        "snippet": snippet,
                        "score": score,
                    }
                )
    except Exception as e:
        logger.warning("cto_search failed: %s", e)
    results.sort(key=lambda x: x["score"], reverse=True)
    return JSONResponse(results[:20])


@router.get("/api/cto/chips", response_class=JSONResponse)
async def cto_chips():
    """Return dynamic contextual chips based on active missions and platform state."""
    from ...epics.store import get_epic_store
    from ...projects.manager import get_project_store

    chips = []
    try:
        ms = get_epic_store()
        ps = get_project_store()
        # Active missions → chips to dive in
        running = ms.list_missions(status="running", limit=5)
        for m in running:
            project = None
            try:
                project = ps.get(m.project_id) if m.project_id else None
            except Exception:
                pass
            chips.append(
                {
                    "label": f"⚡ {m.name[:28]}",
                    "prompt": f"Donne-moi le statut détaillé de la mission « {m.name} »{' du projet ' + project.name if project else ''} : avancement, blocages, prochaine étape.",
                    "cls": "cto-chip-project",
                    "type": "mission",
                }
            )
        # Recent failed missions → investigate
        failed = ms.list_missions(status="failed", limit=3)
        for m in failed:
            chips.append(
                {
                    "label": f"🔴 {m.name[:28]}",
                    "prompt": f"La mission « {m.name} » a échoué. Analyse les causes et propose un plan de reprise.",
                    "cls": "cto-chip-debt",
                    "type": "alert",
                }
            )
        # Projects without workspace → suggest setup
        all_projects = ps.list_all(limit=5)
        no_ws = [p for p in all_projects if not (p.workspace_path or p.git_url)][:2]
        for p in no_ws:
            chips.append(
                {
                    "label": f"🔧 Setup {p.name[:20]}",
                    "prompt": f"Configure le workspace, le git local et le docker pour le projet @{p.name}.",
                    "cls": "cto-chip-project",
                    "type": "setup",
                }
            )
    except Exception as e:
        logger.warning("cto_chips failed: %s", e)
    return JSONResponse(chips[:6])


def _find_agent_mentions(content: str):
    """Return list of (mention_text, agent) for #AgentName mentions."""
    import re

    mentions = re.findall(
        r"#([\w\-][\w\-\s]*?)(?=\s*(?:—|--|,|:|\?|$|\set\s|\spour\s|\sou\s))", content
    )
    if not mentions:
        mentions = re.findall(r"#([\w\-]+)", content)
    if not mentions:
        return []
    all_agents = _get_invitable_agents()
    found = []
    seen = set()
    for mention in mentions:
        m_lower = mention.lower().strip()
        for a in all_agents:
            aname = a.name.lower()
            aid = a.id.lower()
            if a.id not in seen and (
                m_lower == aname
                or m_lower in aname
                or aname.startswith(m_lower)
                or m_lower in aid
            ):
                found.append((mention, a))
                seen.add(a.id)
                break
    return found


# Keywords → auto-invited role when a project is @mentioned
_PROJECT_KEYWORDS_TO_ROLE = {
    "Program Manager": (
        "pilotage",
        "avancement",
        "en est",
        "statut",
        "status",
        "planning",
        "délai",
        "retard",
        "sprint",
        "livraison",
    ),
    "Architect": (
        "architecture",
        "technique",
        "stack",
        "dette technique",
        "migration",
        "conception",
        "design",
        "scalab",
    ),
    "Lean Portfolio Manager": (
        "budget",
        "coût",
        "invest",
        "portfolio",
        "capacit",
        "priorisation",
        "roadmap",
    ),
    "Test Manager": (
        "qualité",
        "quality",
        "test",
        "bug",
        "régression",
        "recette",
        "e2e",
        "couverture",
    ),
}


def _auto_invite_for_project_mention(content: str, explicit_agent_ids: set) -> list:
    """Auto-invite relevant colleague(s) when a project is @mentioned.
    Returns list of agents not already explicitly @mentioned.
    """
    import re
    from ...projects.manager import get_project_store

    # Check if any @mention resolves to a PROJECT (not an agent)
    mentions = re.findall(r"@([\w\-][\w\-\s]*?)(?=\s*(?:—|--|,|:|\?|$))", content)
    if not mentions:
        mentions = re.findall(r"@([\w\-]+)", content)
    if not mentions:
        return []

    try:
        ps = get_project_store()
        all_projects = ps.list_all()
    except Exception:
        return []

    has_project_mention = False
    for mention in mentions:
        m_lower = mention.lower().replace("-", " ").replace("_", " ")
        for p in all_projects:
            pname = p.name.lower().replace("-", " ").replace("_", " ")
            if pname == m_lower or pname.startswith(m_lower) or m_lower in pname:
                has_project_mention = True
                break
        if has_project_mention:
            break

    if not has_project_mention:
        return []

    # Determine which role to invite based on content keywords
    content_lower = content.lower()
    target_role = "Program Manager"  # default
    for role, kws in _PROJECT_KEYWORDS_TO_ROLE.items():
        if any(kw in content_lower for kw in kws):
            target_role = role
            break

    # Find the agent matching that role
    all_agents = _get_invitable_agents()
    for a in all_agents:
        if a.id in explicit_agent_ids:
            continue
        if (
            a.role == target_role
            or target_role.lower() in (a.role or "").lower()
            or target_role.lower() in a.id.lower()
        ):
            return [a]

    # Fallback: invite chef_de_programme (Alexandre Moreau)
    for a in all_agents:
        if a.id in explicit_agent_ids:
            continue
        if a.id == "chef_de_programme" or "programme" in a.id:
            return [a]
    return []


def _resolve_mentions(content: str) -> tuple[str, str]:
    """Resolve @ProjectName mentions.

    Returns (clean_content, project_context_block) where:
    - clean_content = original content unchanged (@ mention stays as-is)
    - project_context_block = rich project info to inject into ExecutionContext.project_context
    """
    import re

    # Capture full project name including em-dash/en-dash until a verb/sentence-break
    _STOP = (
        r"parle|dis|où|que|comment|quoi|quel|donne|fait|lance|crée|analyse"
        r"|explique|résume|liste|montre|deploie|pour |et |c'est|c'est|ça |ca "
    )
    mentions = re.findall(
        rf"@((?:[\w][\w\-\s—–]*?)(?=\s+(?:{_STOP})|\s*$|\s*\?|\s*:))",
        content,
        re.IGNORECASE,
    )
    if not mentions:
        mentions = re.findall(r"@([\w][\w\-\s—–]{0,79}?)(?=\s*[\?:!\n]|$)", content)
    if not mentions:
        mentions = re.findall(r"@([\w\-]+)", content)
    # Strip trailing spaces/dashes from each mention
    mentions = [m.strip(" \t—–-") for m in mentions if m.strip()]
    if not mentions:
        return content, ""
    try:
        from ...projects.manager import get_project_store
        from ...epics.store import get_epic_store

        ps = get_project_store()
        ms = get_epic_store()
        all_projects = ps.list_all()
        blocks = []
        for mention in mentions:

            def _norm(s: str) -> str:
                """Normalize project name for fuzzy matching."""
                import unicodedata

                s = unicodedata.normalize("NFD", s)
                s = "".join(c for c in s if unicodedata.category(c) != "Mn")
                return (
                    s.lower()
                    .replace("-", " ")
                    .replace("_", " ")
                    .replace("—", " ")
                    .replace("–", " ")
                    .strip()
                )

            from difflib import SequenceMatcher

            m_norm = _norm(mention)
            # Score each project: exact=10, startswith=7, fuzzy similarity≥0.6→score*5
            # Also check first word match and words-in-common
            best, best_score = None, 0.0
            for p in all_projects:
                p_norm = _norm(p.name)
                # Exact match
                if p_norm == m_norm:
                    score = 10.0
                # Mention is fully contained in project name or vice versa
                elif m_norm in p_norm or p_norm.startswith(m_norm):
                    score = 7.0
                else:
                    # Fuzzy ratio on full name
                    ratio = SequenceMatcher(None, m_norm, p_norm).ratio()
                    # Also try first word of project vs mention (handles "Maison Léa" → "maison lea")
                    first_words = " ".join(p_norm.split()[:2])
                    ratio2 = SequenceMatcher(None, m_norm, first_words).ratio()
                    score = max(ratio, ratio2) * 5.0
                    # Bonus: significant word overlap
                    m_words = set(m_norm.split())
                    p_words = set(p_norm.split())
                    overlap = len(m_words & p_words) / max(len(m_words), 1)
                    score += overlap * 3.0
                if score > 0 and (p.factory_type or "STANDALONE") != "STANDALONE":
                    score += 0.5
                if score > best_score:
                    best, best_score = p, score
            # Require minimum confidence to avoid false positives
            match = best if best_score >= 2.5 else None
            if not match:
                continue
            missions = ms.list_missions(project_id=match.id, limit=5)
            m_lines = (
                "\n".join(f"  - [{m.status}] {m.name}" for m in missions)
                if missions
                else "  (aucune mission active)"
            )
            # Load domain context if project has an arch_domain
            domain_block = ""
            try:
                if getattr(match, "arch_domain", None):
                    from ...projects.domains import load_domain as _ld_cto

                    _dom_cto = _ld_cto(match.arch_domain)
                    if _dom_cto:
                        domain_block = f"Domaine technique: {_dom_cto.name}\n{_dom_cto.to_context_string()}\n"
            except Exception:
                pass
            blocks.append(
                f"## Projet mentionné : {match.name}\n"
                f"ID: {match.id}\n"
                f"Type: {match.factory_type or 'STANDALONE'} | Statut: {match.status or 'actif'}\n"
                f"Stack: {', '.join(match.domains) if match.domains else '?'}\n"
                f"Description: {match.description or '(non renseignée)'}\n"
                f"Vision: {match.vision[:500] + '...' if match.vision and len(match.vision) > 500 else (match.vision or '(non définie)')}\n"
                f"Git: {match.git_url or '(non configuré)'}\n"
                + (domain_block)
                + f"Missions:\n{m_lines}\n"
            )
        ctx_block = (
            (
                "# CONTEXTE PROJET RÉSOLU (injecté automatiquement)\n"
                "Tu as accès aux informations complètes de ce projet. "
                "Utilise-les pour répondre directement et précisément. "
                "N'appelle PAS d'outils pour chercher ce projet — tout est déjà ici.\n\n"
                + "\n".join(blocks)
            )
            if blocks
            else ""
        )
        return content, ctx_block
    except Exception as e:
        logger.warning("_resolve_mentions failed: %s", e)
        return content, ""


def _badge_mentions(text: str) -> str:
    """Convert @Project and #Agent mentions to colored badge HTML for display."""
    import re

    parts = []
    last = 0
    # Match @ProjectName or #AgentName — greedy up to logical stop
    pattern = re.compile(
        r"([@#])([\w\-][^@#\n]*?)(?=\s{2,}|\s+(?:ou|en|et|pour|qu|qui|dit|de|du|la|le|les)\s|[?!,;]|\s*$)",
        re.IGNORECASE,
    )
    for m in pattern.finditer(text):
        trigger = m.group(1)
        name = m.group(2).strip()
        cls = "mention-badge-project" if trigger == "@" else "mention-badge-agent"
        parts.append(html_mod.escape(text[last : m.start()]))
        parts.append(f'<span class="{cls}">{trigger}{html_mod.escape(name)}</span>')
        last = m.start() + len(trigger) + len(m.group(2))
    parts.append(html_mod.escape(text[last:]))
    return "".join(parts)


@router.post("/api/cto/message", dependencies=[Depends(require_auth())])
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
    content, mention_ctx = _resolve_mentions(content)

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
        f'<div class="chat-msg-body"><div class="chat-msg-text">{_badge_mentions(display)}</div></div>'
        f'<div class="chat-msg-avatar user">S</div>'
        f"</div>"
    )


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

            # Inject resolved @mention project context into system prompt (not user msg)
            if mention_ctx:
                ctx.project_context = mention_ctx + (
                    ("\n\n" + ctx.project_context) if ctx.project_context else ""
                )

            executor = get_executor()
            result = None

            async for event_type_s, data_s in executor.run_streaming(ctx, content):
                if event_type_s == "delta":
                    yield sse("chunk", {"text": data_s})
                elif event_type_s == "tool":
                    # Keepalive: forward tool name so nginx doesn't timeout (60s)
                    yield sse("tool_ping", {"name": data_s})
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
            creation_cards_html = ""
            if tool_calls:
                pills = "".join(
                    f'<span class="chat-tool-pill">'
                    f"{html_mod.escape(str(tc.get('name', tc) if isinstance(tc, dict) else tc))}</span>"
                    for tc in tool_calls
                )
                tools_html = f'<div class="chat-msg-tools">{pills}</div>'

                # Render creation cards for create_project / create_mission / create_team
                for tc in tool_calls:
                    if not isinstance(tc, dict):
                        continue
                    tc_name = tc.get("name", "")
                    try:
                        tc_res = json.loads(tc.get("result", "{}"))
                    except Exception:
                        tc_res = {}
                    if not tc_res.get("ok"):
                        continue
                    if tc_name == "create_project":
                        pid = tc_res.get("project_id", "")
                        pname = html_mod.escape(tc_res.get("name", ""))
                        scaffold = tc_res.get("scaffold", [])
                        missions = tc_res.get("epics", [])
                        scaffold_text = (
                            ", ".join(scaffold) if scaffold else "workspace prêt"
                        )
                        missions_html = ""
                        for m in missions:
                            if m.get("error"):
                                continue
                            m_id = html_mod.escape(m.get("mission_id", ""))
                            m_name = html_mod.escape(m.get("name", ""))
                            wf = m.get("workflow", "")
                            icon = (
                                "🔧"
                                if "tma" in wf
                                else ("🛡️" if "security" in wf else "🧹")
                            )
                            missions_html += (
                                f'<a class="cto-mission-chip" href="/missions/{m_id}" target="_blank">'
                                f"{icon} {m_name}</a>"
                            )
                        creation_cards_html += (
                            f'<div class="cto-creation-card cto-creation-project">'
                            f'<span class="cto-creation-icon">📁</span>'
                            f'<div class="cto-creation-info">'
                            f'<div class="cto-creation-title">{pname}</div>'
                            f'<div class="cto-creation-sub">{html_mod.escape(scaffold_text)}</div>'
                            f"{f'<div class=cto-creation-missions>{missions_html}</div>' if missions_html else ''}"
                            f"</div>"
                            f'<a class="cto-creation-link" href="/projects/{html_mod.escape(pid)}" target="_blank">Ouvrir →</a>'
                            f"</div>"
                        )
                    elif tc_name == "create_mission":
                        mid = tc_res.get("mission_id", "")
                        mname = html_mod.escape(tc_res.get("name", ""))
                        run_id = tc_res.get("epic_run_id", "")
                        run_badge = (
                            '<span class="cto-creation-badge">🚀 lancée</span>'
                            if run_id
                            else ""
                        )
                        creation_cards_html += (
                            f'<div class="cto-creation-card">'
                            f'<span class="cto-creation-icon">🎯</span>'
                            f'<div class="cto-creation-info">'
                            f'<div class="cto-creation-title">{mname}{run_badge}</div>'
                            f'<div class="cto-creation-sub">Mission créée · ID {html_mod.escape(mid)}</div>'
                            f"</div>"
                            f'<a class="cto-creation-link" href="/missions/{html_mod.escape(mid)}" target="_blank">Suivre →</a>'
                            f"</div>"
                        )
                    elif tc_name == "create_team":
                        tname = html_mod.escape(tc_res.get("team_name", "équipe"))
                        count = tc_res.get("count", 0)
                        creation_cards_html += (
                            f'<div class="cto-creation-card">'
                            f'<span class="cto-creation-icon">👥</span>'
                            f'<div class="cto-creation-info">'
                            f'<div class="cto-creation-title">Équipe {tname}</div>'
                            f'<div class="cto-creation-sub">{count} agent(s) créé(s)</div>'
                            f"</div>"
                            f"</div>"
                        )
                    elif tc_name == "create_domain":
                        did = tc_res.get("domain_id", "")
                        dname = html_mod.escape(tc_res.get("name", ""))
                        missions = tc_res.get("epics", [])
                        sub_projects = tc_res.get("sub_projects", [])
                        missions_html = "".join(
                            f'<a class="cto-mission-chip" href="/missions/{html_mod.escape(m.get("mission_id", ""))}" target="_blank">'
                            f"🔧 {html_mod.escape(m.get('name', ''))}</a>"
                            for m in missions
                            if not m.get("error")
                        )
                        sub_html = ""
                        if sub_projects:
                            sub_html = (
                                '<div class="cto-creation-sub">'
                                + ", ".join(
                                    html_mod.escape(s.get("name", ""))
                                    for s in sub_projects
                                )
                                + "</div>"
                            )
                        creation_cards_html += (
                            f'<div class="cto-creation-card cto-creation-project">'
                            f'<span class="cto-creation-icon">🏛️</span>'
                            f'<div class="cto-creation-info">'
                            f'<div class="cto-creation-title">Domaine {dname}</div>'
                            f"{sub_html}"
                            f"{f'<div class=cto-creation-missions>{missions_html}</div>' if missions_html else ''}"
                            f"</div>"
                            f'<a class="cto-creation-link" href="/projects/{html_mod.escape(did)}" target="_blank">Ouvrir →</a>'
                            f"</div>"
                        )
                    elif tc_name == "platform_tma":
                        summary = tc_res.get("summary", {})
                        n_inc = summary.get("open_incidents", 0)
                        n_tkt = summary.get("open_tickets", 0)
                        n_tma = summary.get("tma_missions", 0)
                        status_icon = "🔴" if (n_inc + n_tkt) > 0 else "✅"
                        creation_cards_html += (
                            f'<div class="cto-creation-card">'
                            f'<span class="cto-creation-icon">{status_icon}</span>'
                            f'<div class="cto-creation-info">'
                            f'<div class="cto-creation-title">TMA / Incidents</div>'
                            f'<div class="cto-creation-sub">'
                            f"{n_inc} incident(s) · {n_tkt} ticket(s) · {n_tma} mission(s) TMA"
                            f"</div></div>"
                            f'<a class="cto-creation-link" href="/tma" target="_blank">Voir TMA →</a>'
                            f"</div>"
                        )

            rendered = md_lib.markdown(
                str(result.content),
                extensions=["fenced_code", "tables"],
            )
            agent_html = (
                f'<div class="chat-msg chat-msg-agent">'
                f'<div class="chat-msg-avatar cto-avatar"></div>'
                f'<div class="chat-msg-body">'
                f'<div class="chat-msg-sender">Karim Benali — CTO</div>'
                f'<div class="chat-msg-text md-rendered">{rendered}</div>'
                f"{tools_html}"
                f"{creation_cards_html}"
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

            # ── Invited agents (@mention → another agent responds) ────────
            invited = _find_agent_mentions(content)
            explicit_ids = {a.id for _, a in invited}
            # Auto-invite relevant colleague when a project is @mentioned
            auto = _auto_invite_for_project_mention(content, explicit_ids)
            all_invited = invited + [(None, a) for a in auto]
            for _mention_text, inv_agent in all_invited:
                try:
                    inv_ctx = await _build_context(inv_agent, session)
                    # Build a contextual prompt for the invited agent
                    inv_prompt = (
                        f"Tu es invité dans une conversation par le CTO Karim Benali.\n"
                        f"Question de l'utilisateur : {content}\n\n"
                        f"Réponse du CTO :\n{result.content[:1000]}\n\n"
                        f"En tant que {inv_agent.name} ({inv_agent.role}), "
                        f"donne ta perspective, complète ou nuance si nécessaire. "
                        f"Sois direct et concis.\n"
                        f"IMPORTANT : Ne commence PAS ta réponse par ton nom ni ton rôle "
                        f"(ex: '{inv_agent.name} —'), l'en-tête est déjà affiché dans l'interface."
                    )
                    yield sse(
                        "agent_thinking",
                        {
                            "agent_id": inv_agent.id,
                            "agent_name": inv_agent.name,
                            "agent_role": inv_agent.role or "",
                            "avatar_url": _avatar_url(inv_agent.id),
                        },
                    )
                    inv_result = None
                    async for ev_t, ev_d in executor.run_streaming(inv_ctx, inv_prompt):
                        if ev_t == "delta":
                            yield sse(
                                "agent_chunk",
                                {
                                    "text": ev_d,
                                    "agent_id": inv_agent.id,
                                    "agent_name": inv_agent.name,
                                },
                            )
                        elif ev_t == "tool":
                            yield sse(
                                "tool_ping", {"name": ev_d, "agent_id": inv_agent.id}
                            )
                        elif ev_t == "result":
                            inv_result = ev_d
                    if inv_result:
                        store.add_message(
                            MessageDef(
                                session_id=session.id,
                                from_agent=inv_agent.id,
                                to_agent="user",
                                message_type="text",
                                content=inv_result.content,
                            )
                        )
                        inv_rendered = md_lib.markdown(
                            str(inv_result.content),
                            extensions=["fenced_code", "tables"],
                        )
                        initials = "".join(
                            w[0].upper() for w in inv_agent.name.split()[:2]
                        )
                        av_url = _avatar_url(inv_agent.id)
                        av_html = (
                            f'<img class="invited-avatar-img" src="{html_mod.escape(av_url)}" '
                            f'alt="{html_mod.escape(inv_agent.name)}">'
                            if av_url
                            else f'<div class="invited-avatar invited-avatar-initials">{initials}</div>'
                        )
                        inv_html = (
                            f'<div class="invited-divider">{html_mod.escape(inv_agent.name)} a rejoint</div>'
                            f'<div class="chat-msg chat-msg-invited">'
                            f"{av_html}"
                            f'<div class="chat-msg-body">'
                            f'<div class="chat-msg-sender">{html_mod.escape(inv_agent.name)} — '
                            f"{html_mod.escape(inv_agent.role or '')}</div>"
                            f'<div class="chat-msg-text md-rendered">{inv_rendered}</div>'
                            f"</div></div>"
                        )
                        yield sse(
                            "agent_done",
                            {
                                "html": inv_html,
                                "agent_id": inv_agent.id,
                                "agent_name": inv_agent.name,
                            },
                        )
                except Exception as inv_exc:
                    logger.warning("Invited agent %s error: %s", inv_agent.id, inv_exc)

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


@router.post("/api/cto/upload", dependencies=[Depends(require_auth())])
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
