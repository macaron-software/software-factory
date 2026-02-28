"""Guidelines API — manage domain architecture guidelines."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse

router = APIRouter()
logger = logging.getLogger(__name__)

_GL_DB_PATH = (
    Path(__file__).parent.parent.parent.parent.parent / "data" / "guidelines.db"
)


def _get_gl_db():
    import sqlite3

    if not _GL_DB_PATH.exists():
        return None
    conn = sqlite3.connect(str(_GL_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


@router.get("/api/guidelines/domains")
async def list_domains():
    """List all domains with guidelines + item counts."""
    conn = _get_gl_db()
    if not conn:
        return JSONResponse({"domains": [], "error": "Guidelines DB not found"})
    try:
        rows = conn.execute("""
            SELECT project,
                   COUNT(DISTINCT p.id) as pages,
                   COUNT(i.id) as items,
                   MAX(p.scraped_at) as last_sync
            FROM guideline_pages p
            LEFT JOIN guideline_items i ON i.source_page_id = p.id
            GROUP BY project ORDER BY project
        """).fetchall()
    except Exception as e:
        conn.close()
        return JSONResponse({"domains": [], "error": str(e)})
    conn.close()
    return JSONResponse({"domains": [dict(r) for r in rows]})


@router.get("/api/guidelines/domain/{domain}")
async def get_domain_guidelines(domain: str, role: str = "dev"):
    """Get guidelines summary for a domain."""
    project = f"domain:{domain}" if not domain.startswith("domain:") else domain
    conn = _get_gl_db()
    if not conn:
        return JSONResponse({"error": "Guidelines DB not found"}, status_code=404)
    pages = conn.execute(
        "SELECT id, title, category, url, summary FROM guideline_pages WHERE project=? ORDER BY category, title",
        (project,),
    ).fetchall()
    items = conn.execute(
        "SELECT category, topic, constraint_text FROM guideline_items WHERE project=? ORDER BY category, topic",
        (project,),
    ).fetchall()
    conn.close()
    by_cat: dict = {}
    for item in items:
        by_cat.setdefault(item["category"], []).append(
            {
                "topic": item["topic"],
                "constraint": item["constraint_text"],
            }
        )
    return JSONResponse(
        {
            "domain": domain,
            "project": project,
            "pages": [dict(p) for p in pages],
            "items_by_category": by_cat,
            "total_items": len(items),
        }
    )


@router.delete("/api/guidelines/domain/{domain}")
async def clear_domain_guidelines(domain: str):
    """Clear all guidelines for a domain (to re-import)."""
    project = f"domain:{domain}" if not domain.startswith("domain:") else domain
    conn = _get_gl_db()
    if not conn:
        return JSONResponse({"error": "Guidelines DB not found"}, status_code=404)
    pages_del = conn.execute(
        "DELETE FROM guideline_pages WHERE project=?", (project,)
    ).rowcount
    items_del = conn.execute(
        "DELETE FROM guideline_items WHERE project=?", (project,)
    ).rowcount
    conn.commit()
    conn.close()
    return JSONResponse(
        {"ok": True, "pages_deleted": pages_del, "items_deleted": items_del}
    )


@router.post("/api/guidelines/sync")
async def sync_guidelines(
    body: "GuidelineSyncRequest", background_tasks: BackgroundTasks
):
    """Trigger a guidelines sync from Confluence or manual seed."""
    from .input_models import GuidelineSyncRequest as _M  # noqa: F401

    data = body
    source = data.source
    domain = data.domain
    if not domain:
        return JSONResponse({"error": "domain is required"}, status_code=400)

    project = f"domain:{domain}" if not domain.startswith("domain:") else domain

    if source == "confluence":
        url = (data.url or "").strip()
        token = (data.token or "").strip()
        space = (data.space or "").strip()
        if not url or not token or not space:
            return JSONResponse(
                {"error": "url, token and space are required for Confluence sync"},
                status_code=400,
            )

        def _run_scraper():
            cmd = [
                sys.executable,
                "-m",
                "mcp_lrm.guidelines_scraper",
                "--source",
                "confluence",
                "--url",
                url,
                "--token",
                token,
                "--space",
                space,
                "--project",
                project,
            ]
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=120
                )
                if result.returncode != 0:
                    logger.error("Guidelines scraper failed: %s", result.stderr[:500])
                else:
                    logger.info("Guidelines scraper done: %s", result.stdout[:200])
            except Exception as e:
                logger.error("Guidelines scraper error: %s", e)

        background_tasks.add_task(_run_scraper)
        return JSONResponse({"ok": True, "status": "sync_started", "project": project})

    # Manual items seed
    items = data.items or []
    if not items:
        return JSONResponse(
            {"error": "items required for manual source"}, status_code=400
        )

    conn = _get_gl_db()
    if not conn:
        # Create DB
        import sqlite3

        _GL_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(_GL_DB_PATH))
        conn.row_factory = sqlite3.Row
        conn.execute("""CREATE TABLE IF NOT EXISTS guideline_pages (
            id TEXT PRIMARY KEY, project TEXT, title TEXT, category TEXT,
            url TEXT DEFAULT '', content TEXT DEFAULT '', summary TEXT DEFAULT '',
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS guideline_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT, source_page_id TEXT, project TEXT,
            category TEXT, topic TEXT, constraint_text TEXT
        )""")
        conn.commit()

    page_id = f"manual:{project}:{domain}"
    conn.execute(
        "INSERT OR REPLACE INTO guideline_pages (id, project, title, category, summary) VALUES (?,?,?,?,?)",
        (
            page_id,
            project,
            f"Manual guidelines for {domain}",
            "manual",
            f"Manually added guidelines for domain {domain}",
        ),
    )
    for item in items:
        conn.execute(
            "INSERT INTO guideline_items (source_page_id, project, category, topic, constraint_text) VALUES (?,?,?,?,?)",
            (
                page_id,
                project,
                item.category,
                item.topic,
                item.constraint,
            ),
        )
    conn.commit()
    conn.close()
    return JSONResponse(
        {"ok": True, "status": "seeded", "count": len(items), "project": project}
    )
