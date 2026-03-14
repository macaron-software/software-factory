"""Memory layer endpoints."""
# Ref: feat-memory

from __future__ import annotations

import html as html_mod
import json
import logging

from fastapi import Depends,  APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ...schemas import MemoryStats
from .input_models import GlobalMemoryCreate, ProjectMemoryCreate
from ....auth.middleware import require_auth

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
async def project_memory(
    project_id: str, q: str = "", category: str = "", role: str = ""
):
    """Get or search project memory, optionally filtered by agent role."""
    from ....memory.manager import get_memory_manager

    mem = get_memory_manager()
    if q:
        entries = mem.project_search(project_id, q)
    else:
        entries = mem.project_get(
            project_id, category=category or None, agent_role=role
        )
    return JSONResponse(entries)


@router.post("/api/memory/project/{project_id}", dependencies=[Depends(require_auth())])
async def project_memory_store(project_id: str, body: ProjectMemoryCreate):
    """Store a project memory entry (upsert by project_id + category + key)."""
    from ....memory.manager import get_memory_manager

    get_memory_manager().project_store(
        project_id,
        body.key,
        body.value,
        category=body.category,
        source=body.source,
        confidence=body.confidence,
    )
    return JSONResponse({"ok": True})


async def delete_project_memory(project_id: str, category: str = "", role: str = ""):
    """Clear project memory, optionally filtered by category and/or agent role."""
    from ....db.migrations import get_db

    conn = get_db()
    q = "DELETE FROM memory_project WHERE project_id=?"
    params: list = [project_id]
    if category:
        q += " AND category=?"
        params.append(category)
    if role:
        q += " AND agent_role=?"
        params.append(role)
    deleted = conn.execute(q, params).rowcount
    conn.commit()
    conn.close()
    return JSONResponse({"ok": True, "deleted": deleted})


@router.get("/api/memory/global")
async def global_memory(category: str = ""):
    """Get global memory entries."""
    from ....memory.manager import get_memory_manager

    entries = get_memory_manager().global_get(category=category or None)
    return JSONResponse(entries)


@router.post("/api/memory/global", dependencies=[Depends(require_auth())])
async def global_memory_store(body: GlobalMemoryCreate):
    """Store a global memory entry."""
    from ....memory.manager import get_memory_manager

    get_memory_manager().global_store(
        body.key, body.value, category=body.category, confidence=body.confidence
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


@router.get("/api/memory/health")
async def memory_health():
    """Full health snapshot of all memory layers (counts, quality, role breakdown)."""
    from ....memory.compactor import get_memory_health

    return JSONResponse(get_memory_health())


@router.post("/api/memory/ingest", dependencies=[Depends(require_auth())])
async def memory_ingest(request: Request):
    """Ingest raw text into platform memory (memory_global, category='inbox').

    SOURCE: GoogleCloudPlatform/generative-ai always-on-memory-agent (IngestAgent)
            https://github.com/GoogleCloudPlatform/generative-ai/tree/main/gemini/agents/always-on-memory-agent
    WHY: Always-on-memory-agent's IngestAgent extracts summary+entities+topics+importance
         from any text and stores it as structured memory. We expose the same flow via HTTP
         so agents and the CLI can push artifacts without dropping files in inbox/.

    Body: {"text": "...", "source"?: "...", "filename"?: "..."}
    Returns: {id, summary, entities, topics, importance, stored}
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    text = body.get("text", "").strip()
    if not text:
        return JSONResponse({"error": "text is required"}, status_code=400)

    from ....memory.inbox import ingest_text

    result = await ingest_text(
        content=text,
        source=body.get("source", "api"),
        filename=body.get("filename", "input.txt"),
    )
    return JSONResponse(result)


@router.get("/api/memory/query")
async def memory_query(q: str = "", limit_memory: int = 30, limit_instincts: int = 20):
    """LLM-synthesized answer over all platform memory + instincts + insights.

    SOURCE: GoogleCloudPlatform/generative-ai always-on-memory-agent (QueryAgent)
            https://github.com/GoogleCloudPlatform/generative-ai/tree/main/gemini/agents/always-on-memory-agent
    WHY: Their QueryAgent reads ALL memories + consolidation insights and synthesizes
         a natural language answer with source citations. We had no such cross-layer
         synthesis endpoint — only per-layer keyword search. This adds LLM reasoning
         over the accumulated platform knowledge base.

    Reads: memory_global + instincts (top by confidence) + instinct_insights
    Returns: {answer, sources: [{type, id, excerpt}]}
    """
    if not q:
        return JSONResponse({"error": "q parameter is required"}, status_code=400)

    # 1. Load memory_global
    memories: list[dict] = []
    try:
        from ....memory.manager import get_memory_manager

        mm = get_memory_manager()
        memories = mm.global_search(q, limit=limit_memory) or mm.global_get(
            limit=limit_memory
        )
    except Exception as e:
        logger.warning("memory_query: global_get error: %s", e)

    # 2. Load instincts
    instincts: list[dict] = []
    try:
        from ....db.migrations import get_db

        with get_db() as db:
            rows = db.execute(
                """SELECT id, agent_id, trigger, action, domain, confidence
                   FROM instincts ORDER BY confidence DESC LIMIT ?""",
                (limit_instincts,),
            ).fetchall()
            instincts = [
                {
                    "id": r[0],
                    "agent_id": r[1],
                    "trigger": r[2],
                    "action": r[3],
                    "domain": r[4],
                    "confidence": r[5],
                }
                for r in rows
            ]
    except Exception as e:
        logger.warning("memory_query: instincts error: %s", e)

    # 3. Load instinct_insights
    insights: list[dict] = []
    try:
        with get_db() as db:
            rows = db.execute(
                """SELECT id, type, summary, domains, confidence
                   FROM instinct_insights ORDER BY confidence DESC LIMIT 20"""
            ).fetchall()
            insights = [
                {
                    "id": r[0],
                    "type": r[1],
                    "summary": r[2],
                    "domains": r[3],
                    "confidence": r[4],
                }
                for r in rows
            ]
    except Exception as e:
        logger.warning("memory_query: insights error: %s", e)

    if not memories and not instincts and not insights:
        return JSONResponse({"answer": "No platform memory found yet.", "sources": []})

    # 4. Build context for LLM
    sections = []

    if memories:
        mem_lines = []
        for i, m in enumerate(memories[:20]):
            val = m.get("value", "") or m.get("content", "")
            try:
                parsed = json.loads(val) if val.startswith("{") else {}
                val = parsed.get("summary", val)
            except Exception:
                pass
            mem_lines.append(f"[MEM-{i}] {m.get('key', '?')}: {str(val)[:200]}")
        sections.append("PLATFORM MEMORY:\n" + "\n".join(mem_lines))

    if instincts:
        inst_lines = [
            f"[INST-{i}] agent={v['agent_id']} domain={v['domain']} "
            f"conf={v['confidence']:.1f}: {v['trigger']} → {v['action'][:80]}"
            for i, v in enumerate(instincts[:15])
        ]
        sections.append(
            "AGENT INSTINCTS (learned behaviors):\n" + "\n".join(inst_lines)
        )

    if insights:
        ins_lines = [
            f"[INSIGHT-{i}] [{v['type']}] conf={v['confidence']:.1f}: {v['summary']}"
            for i, v in enumerate(insights[:10])
        ]
        sections.append("CROSS-AGENT INSIGHTS:\n" + "\n".join(ins_lines))

    context = "\n\n".join(sections)
    prompt = f"""You are a platform knowledge assistant. Answer the question using ONLY the provided context.
Cite your sources using [MEM-N], [INST-N], or [INSIGHT-N] references.

{context}

QUESTION: {q}

Answer concisely with citations. If the context doesn't contain relevant info, say so."""

    # 5. LLM synthesis
    answer = "Unable to synthesize answer."
    sources = []
    try:
        from ....llm.client import LLMClient, LLMMessage

        client = LLMClient()
        resp = await client.chat(
            messages=[LLMMessage(role="user", content=prompt)],
            temperature=0.3,
            max_tokens=1024,
        )
        answer = resp.content.strip()

        # Build sources list from cited references in answer
        import re

        cited_mems = {int(m) for m in re.findall(r"\[MEM-(\d+)\]", answer)}
        cited_inst = {int(m) for m in re.findall(r"\[INST-(\d+)\]", answer)}
        cited_ins = {int(m) for m in re.findall(r"\[INSIGHT-(\d+)\]", answer)}

        for i in sorted(cited_mems):
            if i < len(memories):
                m = memories[i]
                sources.append(
                    {
                        "type": "memory",
                        "id": m.get("key", ""),
                        "excerpt": str(m.get("value", ""))[:150],
                    }
                )
        for i in sorted(cited_inst):
            if i < len(instincts):
                v = instincts[i]
                sources.append(
                    {
                        "type": "instinct",
                        "id": v["id"][:8],
                        "excerpt": f"{v['trigger']} → {v['action'][:80]}",
                    }
                )
        for i in sorted(cited_ins):
            if i < len(insights):
                v = insights[i]
                sources.append(
                    {
                        "type": "insight",
                        "id": v["id"][:8],
                        "excerpt": v["summary"][:150],
                    }
                )

    except Exception as e:
        logger.error("memory_query: LLM call failed: %s", e)
        answer = f"LLM synthesis failed: {e}"

    return JSONResponse({"answer": answer, "sources": sources})


@router.post("/api/memory/compact", dependencies=[Depends(require_auth())])
async def memory_compact():
    """Trigger on-demand memory compaction (dedup, prune, compress, re-score)."""
    import asyncio
    from ....memory.compactor import run_compaction

    loop = asyncio.get_event_loop()
    stats = await loop.run_in_executor(None, run_compaction)
    return JSONResponse(
        {
            "ok": True,
            "pattern_pruned": stats.pattern_pruned,
            "project_pruned": stats.project_pruned,
            "project_compressed": stats.project_compressed,
            "global_deduped": stats.global_deduped,
            "global_rescored": stats.global_rescored,
            "errors": stats.errors,
            "ran_at": stats.ran_at,
        }
    )
