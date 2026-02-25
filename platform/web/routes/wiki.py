"""Wiki — built-in documentation pages with markdown rendering."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .helpers import _templates

router = APIRouter()
logger = logging.getLogger(__name__)


def _wiki_db():
    from ...db.migrations import get_db

    return get_db()


@router.get("/wiki", response_class=HTMLResponse)
async def wiki_partial(request: Request):
    """Wiki tab content (loaded inside toolbox)."""
    db = _wiki_db()
    pages = db.execute(
        "SELECT slug, title, category, icon, sort_order, parent_slug "
        "FROM wiki_pages ORDER BY category, sort_order, title"
    ).fetchall()
    return _templates(request).TemplateResponse(
        "_partial_wiki.html",
        {"request": request, "pages": pages, "page": None},
    )


@router.get("/wiki/{slug}", response_class=HTMLResponse)
async def wiki_page(request: Request, slug: str):
    """Return a single wiki page partial (HTMX target)."""
    db = _wiki_db()
    page = db.execute("SELECT * FROM wiki_pages WHERE slug = ?", (slug,)).fetchone()
    pages = db.execute(
        "SELECT slug, title, category, icon, sort_order, parent_slug "
        "FROM wiki_pages ORDER BY category, sort_order, title"
    ).fetchall()
    return _templates(request).TemplateResponse(
        "_partial_wiki.html",
        {"request": request, "pages": pages, "page": dict(page) if page else None},
    )


@router.get("/api/wiki/pages", response_class=JSONResponse)
async def api_wiki_list():
    """API: list all wiki pages."""
    db = _wiki_db()
    rows = db.execute(
        "SELECT slug, title, category, icon, sort_order, parent_slug "
        "FROM wiki_pages ORDER BY category, sort_order, title"
    ).fetchall()
    return {"success": True, "pages": [dict(r) for r in rows]}


@router.get("/api/wiki/{slug}", response_class=JSONResponse)
async def api_wiki_get(slug: str):
    """API: get wiki page content."""
    db = _wiki_db()
    row = db.execute("SELECT * FROM wiki_pages WHERE slug = ?", (slug,)).fetchone()
    if not row:
        return JSONResponse({"success": False, "error": "not found"}, 404)
    return {"success": True, "page": dict(row)}


@router.put("/api/wiki/{slug}", response_class=JSONResponse)
async def api_wiki_update(request: Request, slug: str):
    """API: update wiki page content."""
    body = await request.json()
    db = _wiki_db()
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        "UPDATE wiki_pages SET content = ?, title = ?, updated_at = ? WHERE slug = ?",
        (body.get("content", ""), body.get("title", slug), now, slug),
    )
    db.commit()
    return {"success": True}


@router.post("/api/wiki", response_class=JSONResponse)
async def api_wiki_create(request: Request):
    """API: create a new wiki page."""
    body = await request.json()
    slug = body.get("slug", "").strip().lower().replace(" ", "-")
    if not slug:
        return JSONResponse({"success": False, "error": "slug required"}, 400)
    db = _wiki_db()
    now = datetime.now(timezone.utc).isoformat()
    try:
        db.execute(
            "INSERT INTO wiki_pages (slug, title, content, category, icon, sort_order, parent_slug, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                slug,
                body.get("title", slug),
                body.get("content", ""),
                body.get("category", "general"),
                body.get("icon", "📄"),
                body.get("sort_order", 100),
                body.get("parent_slug"),
                now,
                now,
            ),
        )
        db.commit()
    except Exception as exc:
        return JSONResponse({"success": False, "error": str(exc)}, 409)
    return {"success": True, "slug": slug}


@router.delete("/api/wiki/{slug}", response_class=JSONResponse)
async def api_wiki_delete(slug: str):
    """API: delete a wiki page."""
    db = _wiki_db()
    db.execute("DELETE FROM wiki_pages WHERE slug = ?", (slug,))
    db.commit()
    return {"success": True}


@router.post("/api/wiki/seed", response_class=JSONResponse)
async def api_wiki_seed():
    """Seed wiki with built-in documentation pages."""
    db = _wiki_db()
    now = datetime.now(timezone.utc).isoformat()

    pages = _get_seed_pages()
    inserted = 0
    for p in pages:
        try:
            db.execute(
                "INSERT OR IGNORE INTO wiki_pages "
                "(slug, title, content, category, icon, sort_order, parent_slug, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    p["slug"],
                    p["title"],
                    p["content"],
                    p["category"],
                    p["icon"],
                    p["sort_order"],
                    p.get("parent_slug"),
                    now,
                    now,
                ),
            )
            inserted += 1
        except Exception:
            pass
    db.commit()
    return {"success": True, "inserted": inserted, "total": len(pages)}


def _get_seed_pages():
    """Return list of seed wiki pages with markdown content."""
    from .wiki_content import WIKI_PAGES

    return WIKI_PAGES
