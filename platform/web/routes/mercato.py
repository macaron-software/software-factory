"""Web routes — Agent Mercato (transfer market)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .helpers import _templates

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Page ─────────────────────────────────────────────────────────


@router.get("/mercato", response_class=HTMLResponse)
async def mercato_page(request: Request):
    from ...agents.store import get_agent_store
    from ...mercato.service import get_mercato_service
    from ...mercato.valuation import compute_market_value
    from ...projects.manager import get_project_store

    svc = get_mercato_service()
    agent_store = get_agent_store()
    project_store = get_project_store()

    projects = project_store.list_all()
    all_agents = agent_store.list_all()
    agent_map = {a.id: a for a in all_agents}
    listings = svc.list_active()

    # Enrich listings with agent info + valuation
    enriched_listings = []
    for ls in listings:
        agent = agent_map.get(ls.agent_id)
        if not agent:
            continue
        enriched_listings.append(
            {
                "listing": ls,
                "agent": agent,
                "market_value": compute_market_value(agent),
            }
        )

    free_agent_ids = svc.get_free_agents()
    free_agents = [agent_map[aid] for aid in free_agent_ids if aid in agent_map]

    # Compute valuations for free agents
    free_with_val = [
        {"agent": a, "market_value": compute_market_value(a)} for a in free_agents[:50]
    ]

    recent_transfers = svc.get_transfers(limit=20)

    return _templates(request).TemplateResponse(
        "mercato.html",
        {
            "request": request,
            "page_title": "Mercato",
            "listings": enriched_listings,
            "free_agents": free_with_val,
            "transfers": recent_transfers,
            "projects": projects,
            "agent_map": agent_map,
        },
    )


# ── API: Listings ────────────────────────────────────────────────


@router.get("/api/mercato/listings")
async def api_list_listings():
    from ...agents.store import get_agent_store
    from ...mercato.service import get_mercato_service
    from ...mercato.valuation import compute_market_value

    svc = get_mercato_service()
    agent_store = get_agent_store()
    agent_map = {a.id: a for a in agent_store.list_all()}
    listings = svc.list_active()
    result = []
    for ls in listings:
        agent = agent_map.get(ls.agent_id)
        result.append(
            {
                "id": ls.id,
                "agent_id": ls.agent_id,
                "agent_name": agent.name if agent else ls.agent_id,
                "seller_project": ls.seller_project,
                "listing_type": ls.listing_type,
                "asking_price": ls.asking_price,
                "loan_weeks": ls.loan_weeks,
                "market_value": compute_market_value(agent) if agent else 0,
                "status": ls.status,
            }
        )
    return result


@router.post("/api/mercato/listings")
async def api_create_listing(request: Request):
    from ...agents.store import get_agent_store
    from ...mercato.service import get_mercato_service
    from ...mercato.valuation import compute_market_value

    data = await request.json()
    agent_id = data.get("agent_id")
    seller = data.get("seller_project")
    ltype = data.get("listing_type", "transfer")
    price = data.get("asking_price")

    if not agent_id or not seller:
        return JSONResponse({"error": "agent_id and seller_project required"}, 400)

    svc = get_mercato_service()
    if price is None:
        agent = get_agent_store().get(agent_id)
        price = compute_market_value(agent) if agent else 500

    try:
        ls = svc.create_listing(
            agent_id,
            seller,
            ltype,
            price,
            data.get("loan_weeks"),
            data.get("buyout_clause"),
        )
        return {"id": ls.id, "asking_price": ls.asking_price, "status": "active"}
    except ValueError as e:
        return JSONResponse({"error": str(e)}, 400)


@router.delete("/api/mercato/listings/{listing_id}")
async def api_cancel_listing(listing_id: str, request: Request):
    from ...mercato.service import get_mercato_service

    data = await request.json() if request.headers.get("content-type") == "application/json" else {}
    project_id = data.get("project_id", "")
    svc = get_mercato_service()
    ok = svc.cancel_listing(listing_id, project_id)
    if ok:
        return {"status": "cancelled"}
    return JSONResponse({"error": "Listing not found or not yours"}, 404)


# ── API: Transfers ───────────────────────────────────────────────


@router.post("/api/mercato/transfers")
async def api_execute_transfer(request: Request):
    from ...mercato.service import get_mercato_service

    data = await request.json()
    listing_id = data.get("listing_id")
    buyer = data.get("buyer_project")
    if not listing_id or not buyer:
        return JSONResponse({"error": "listing_id and buyer_project required"}, 400)
    svc = get_mercato_service()
    try:
        t = svc.execute_transfer(listing_id, buyer)
        return {"id": t.id, "agent_id": t.agent_id, "price": t.price, "type": t.transfer_type}
    except ValueError as e:
        return JSONResponse({"error": str(e)}, 400)


@router.get("/api/mercato/transfers")
async def api_list_transfers(project_id: str | None = None):
    from ...mercato.service import get_mercato_service

    svc = get_mercato_service()
    transfers = svc.get_transfers(project_id)
    return [
        {
            "id": t.id,
            "agent_id": t.agent_id,
            "from": t.from_project,
            "to": t.to_project,
            "type": t.transfer_type,
            "price": t.price,
            "date": t.completed_at,
        }
        for t in transfers
    ]


# ── API: Wallet ──────────────────────────────────────────────────


@router.get("/api/mercato/wallet/{project_id}")
async def api_wallet(project_id: str):
    from ...mercato.service import get_mercato_service

    svc = get_mercato_service()
    w = svc.get_wallet(project_id)
    txs = svc.get_transactions(project_id, limit=20)
    return {
        "project_id": w.project_id,
        "balance": w.balance,
        "total_earned": w.total_earned,
        "total_spent": w.total_spent,
        "recent_transactions": txs,
    }


# ── API: Valuation ───────────────────────────────────────────────


@router.get("/api/mercato/valuation/{agent_id}")
async def api_valuation(agent_id: str):
    from ...agents.store import get_agent_store
    from ...mercato.valuation import valuation_breakdown

    agent = get_agent_store().get(agent_id)
    if not agent:
        return JSONResponse({"error": "Agent not found"}, 404)
    return valuation_breakdown(agent)


# ── API: Free Agents & Draft ─────────────────────────────────────


@router.get("/api/mercato/free-agents")
async def api_free_agents():
    from ...agents.store import get_agent_store
    from ...mercato.service import get_mercato_service
    from ...mercato.valuation import compute_market_value

    svc = get_mercato_service()
    agent_store = get_agent_store()
    agent_map = {a.id: a for a in agent_store.list_all()}
    free_ids = svc.get_free_agents()
    return [
        {
            "id": aid,
            "name": agent_map[aid].name,
            "role": agent_map[aid].role,
            "market_value": compute_market_value(agent_map[aid]),
            "skills": len(agent_map[aid].skills),
            "tools": len(agent_map[aid].tools),
        }
        for aid in free_ids
        if aid in agent_map
    ]


@router.post("/api/mercato/draft/{agent_id}")
async def api_draft(agent_id: str, request: Request):
    from ...mercato.service import get_mercato_service

    data = await request.json()
    project_id = data.get("project_id")
    if not project_id:
        return JSONResponse({"error": "project_id required"}, 400)
    svc = get_mercato_service()
    try:
        a = svc.draft_agent(agent_id, project_id)
        return {"agent_id": a.agent_id, "project_id": a.project_id, "status": "drafted"}
    except ValueError as e:
        return JSONResponse({"error": str(e)}, 400)


# ── HTMX Partials ───────────────────────────────────────────────


@router.get("/api/mercato/project-roster/{project_id}", response_class=HTMLResponse)
async def project_roster_partial(project_id: str, request: Request):
    """Return agent cards for a project (HTMX partial)."""
    from ...agents.store import get_agent_store
    from ...mercato.service import get_mercato_service
    from ...mercato.valuation import compute_market_value

    svc = get_mercato_service()
    agent_store = get_agent_store()
    agent_map = {a.id: a for a in agent_store.list_all()}
    assignments = svc.get_project_agents(project_id)
    agents_data = []
    for a in assignments:
        agent = agent_map.get(a.agent_id)
        if agent:
            agents_data.append(
                {
                    "agent": agent,
                    "assignment": a,
                    "market_value": compute_market_value(agent),
                }
            )

    html_parts = []
    for ad in agents_data:
        ag = ad["agent"]
        asg = ad["assignment"]
        badge = "LOAN" if asg.assignment_type == "loaned" else ""
        html_parts.append(f"""
        <div class="mercato-card">
            <div class="mercato-card__header">
                <img src="/static/avatars/{ag.id}.jpg" onerror="this.src='/static/avatars/default.jpg'" class="mercato-card__avatar">
                <div>
                    <div class="mercato-card__name">{ag.name}</div>
                    <div class="mercato-card__role">{ag.role}</div>
                </div>
                {"<span class='mercato-badge mercato-badge--loan'>LOAN</span>" if badge else ""}
            </div>
            <div class="mercato-card__value">{ad["market_value"]} tokens</div>
        </div>
        """)
    return "\n".join(html_parts) if html_parts else "<p class='empty-state'>No agents assigned</p>"


@router.get("/mercato/roster-partial", response_class=HTMLResponse)
async def mercato_roster_overview(request: Request):
    """Mercato summary for embed in ART/Teams tab (HTMX partial)."""
    from ...agents.store import get_agent_store
    from ...mercato.service import get_mercato_service

    svc = get_mercato_service()
    agent_store = get_agent_store()
    agent_map = {a.id: a for a in agent_store.list_all()}
    listings = svc.list_active()
    free_ids = svc.get_free_agents()
    transfers = svc.get_transfers(limit=5)

    html = '<div style="display:flex;flex-direction:column;gap:1rem">'
    # KPIs
    html += '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:.7rem">'
    html += f'<div class="art-kpi"><div class="num">{len(listings)}</div><div class="lbl">Active Listings</div></div>'
    html += f'<div class="art-kpi"><div class="num">{len(free_ids)}</div><div class="lbl">Free Agents</div></div>'
    html += f'<div class="art-kpi"><div class="num">{len(transfers)}</div><div class="lbl">Recent Transfers</div></div>'
    html += f'<div class="art-kpi"><div class="num">{len(agent_map)}</div><div class="lbl">Total Agents</div></div>'
    html += "</div>"

    # Active listings
    if listings:
        html += '<div style="background:var(--bg-secondary);border:1px solid var(--border);border-radius:var(--radius);padding:.8rem">'
        html += '<h3 style="font-size:.8rem;font-weight:700;margin-bottom:.5rem;color:var(--text-primary)">Active Listings</h3>'
        for ls in listings[:8]:
            agent = agent_map.get(ls.agent_id)
            name = agent.name if agent else ls.agent_id
            html += '<div style="display:flex;justify-content:space-between;align-items:center;padding:.3rem 0;border-bottom:1px solid var(--border)">'
            html += f'<span style="font-size:.75rem;color:var(--text-primary)">{name}</span>'
            html += f'<span style="font-size:.65rem;color:var(--purple-light)">{ls.asking_price} tokens</span>'
            html += "</div>"
        html += "</div>"

    # Recent transfers
    if transfers:
        html += '<div style="background:var(--bg-secondary);border:1px solid var(--border);border-radius:var(--radius);padding:.8rem">'
        html += '<h3 style="font-size:.8rem;font-weight:700;margin-bottom:.5rem;color:var(--text-primary)">Recent Transfers</h3>'
        for tr in transfers[:5]:
            agent = agent_map.get(tr.agent_id)
            name = agent.name if agent else tr.agent_id
            html += '<div style="display:flex;justify-content:space-between;align-items:center;padding:.3rem 0;border-bottom:1px solid var(--border)">'
            html += f'<span style="font-size:.75rem;color:var(--text-primary)">{name}</span>'
            html += f'<span style="font-size:.65rem;color:var(--green)">{tr.price} tokens</span>'
            html += "</div>"
        html += "</div>"

    html += "</div>"
    return html
