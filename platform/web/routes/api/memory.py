"""Memory layer endpoints."""

from __future__ import annotations

import html as html_mod
import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ...schemas import MemoryStats

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/memory/vector/search")
async def vector_search(scope_id: str, q: str, limit: int = 10):
    """Semantic vector search in memory."""
    from ....memory.manager import get_memory_manager

    mem = get_memory_manager()
    results = await mem.semantic_search(scope_id, q, limit=limit)
    return JSONResponse(results)


@router.get("/api/memory/vector/stats")
async def vector_stats(scope_id: str = ""):
    """Vector store statistics."""
    from ....memory.vectors import get_vector_store

    return JSONResponse(get_vector_store().count(scope_id))


@router.get("/api/memory/project/{project_id}")
async def project_memory(project_id: str, q: str = "", category: str = ""):
    """Get or search project memory."""
    from ....memory.manager import get_memory_manager

    mem = get_memory_manager()
    if q:
        entries = mem.project_search(project_id, q)
    else:
        entries = mem.project_get(project_id, category=category or None)
    return JSONResponse(entries)


@router.get("/api/memory/global")
async def global_memory(category: str = ""):
    """Get global memory entries."""
    from ....memory.manager import get_memory_manager

    entries = get_memory_manager().global_get(category=category or None)
    return JSONResponse(entries)


@router.post("/api/memory/global")
async def global_memory_store(request: Request):
    """Store a global memory entry."""
    from ....memory.manager import get_memory_manager

    data = await request.json()
    cat = data.get("category", "general")
    key = data.get("key", "")
    val = data.get("value", "")
    if not key or not val:
        return JSONResponse({"error": "key and value required"}, status_code=400)
    get_memory_manager().global_store(
        key, val, category=cat, confidence=data.get("confidence", 0.8)
    )
    return JSONResponse({"ok": True})


@router.get("/api/memory/search")
async def memory_search(q: str = ""):
    """Search across all memory layers."""
    from ....memory.manager import get_memory_manager

    if not q:
        return HTMLResponse(
            '<div style="color:var(--text-muted);font-size:0.75rem;padding:0.5rem">Tapez une requête…</div>'
        )
    mem = get_memory_manager()
    results = mem.global_search(q, limit=20)
    if not results:
        return HTMLResponse(
            f'<div style="color:var(--text-muted);font-size:0.75rem;padding:0.5rem">No results for "{html_mod.escape(q)}"</div>'
        )
    html = ""
    for r in results:
        cat = r.get("category", "")
        conf = r.get("confidence", 0)
        html += f"""<div class="mem-entry">
            <div><span class="mem-badge {cat}">{cat}</span> <span class="mem-key">{r.get("key", "")}</span></div>
            <div class="mem-val">{str(r.get("value", ""))[:300]}</div>
            <div class="mem-meta"><span>{int(conf * 100)}% confidence</span></div>
        </div>"""
    return HTMLResponse(html)


@router.get("/api/memory/stats", responses={200: {"model": MemoryStats}})
async def memory_stats():
    """Memory layer statistics."""
    from ....memory.manager import get_memory_manager

    return JSONResponse(get_memory_manager().stats())
