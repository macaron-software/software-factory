"""Wiki — built-in documentation pages with markdown rendering + owner RBAC."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .helpers import _templates

router = APIRouter()
log = logging.getLogger(__name__)


def _wiki_can_write(request: Request, page_row=None) -> bool:
    """Check if current user can write (create/update/delete) a wiki page.

    Rules:
      - visibility='public'  → any authenticated user can edit
      - visibility='owner'   → only the page owner or admin
      - visibility='admin'   → only admin
    """
    user = getattr(request.state, "user", None)
    if not user:
        return False
    role = getattr(user, "role", None) or "viewer"
    if role == "admin":
        return True
    if page_row is None:
        return True  # new page creation — anyone auth'd
    vis = (page_row.get("visibility") if isinstance(page_row, dict)
           else getattr(page_row, "visibility", None)) or "public"
    if vis == "public":
        return True
    if vis == "owner":
        owner = (page_row.get("owner") if isinstance(page_row, dict)
                 else getattr(page_row, "owner", None))
        username = getattr(user, "username", None) or getattr(user, "email", None) or ""
        return owner and owner == username
    return False  # 'admin' visibility — only admin (handled above)
logger = logging.getLogger(__name__)

_GITLAB_ENABLED = bool(os.getenv("GITLAB_TOKEN"))


def _wiki_db():
    from ...db.migrations import get_db

    return get_db()


def _gitlab_sync_page(slug: str, title: str, content: str) -> None:
    """Fire-and-forget: push a single page to GitLab wiki."""
    if not _GITLAB_ENABLED:
        return

    def _push():
        try:
            from ...gitlab.wiki_sync import upsert_page
            upsert_page(slug, title, content)
            logger.debug("gitlab wiki synced: %s", slug)
        except Exception as e:
            logger.warning("gitlab wiki sync failed for %s: %s", slug, e)

    try:
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, _push)
    except RuntimeError:
        import threading
        threading.Thread(target=_push, daemon=True).start()

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


def _resolve_page(db, slug: str, lang: str) -> dict | None:
    """Return wiki page dict, applying translation overlay if available."""
    page = db.execute("SELECT * FROM wiki_pages WHERE slug = ?", (slug,)).fetchone()
    if not page:
        return None
    page = dict(page)
    if lang and lang != "en":
        trans = db.execute(
            "SELECT title, content FROM wiki_translations WHERE slug = ? AND lang = ?",
            (slug, lang),
        ).fetchone()
        if trans:
            page["title"] = trans["title"]
            page["content"] = trans["content"]
    return page


@router.get("/wiki/page/{slug}", response_class=HTMLResponse)
async def wiki_page_content(request: Request, slug: str):
    """Return only the wiki page content (no sidebar) — HTMX target for sidebar links."""
    lang = getattr(request.state, "lang", "en") or "en"
    db = _wiki_db()
    page = _resolve_page(db, slug, lang)
    return _templates(request).TemplateResponse(
        "_partial_wiki_page.html",
        {"request": request, "page": page},
    )


@router.get("/wiki/{slug}", response_class=HTMLResponse)
async def wiki_page(request: Request, slug: str):
    """Return a single wiki page partial (HTMX target)."""
    lang = getattr(request.state, "lang", "en") or "en"
    db = _wiki_db()
    page = _resolve_page(db, slug, lang)
    pages = db.execute(
        "SELECT slug, title, category, icon, sort_order, parent_slug "
        "FROM wiki_pages ORDER BY category, sort_order, title"
    ).fetchall()
    return _templates(request).TemplateResponse(
        "_partial_wiki.html",
        {"request": request, "pages": pages, "page": page},
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
    """API: update wiki page content (RBAC enforced)."""
    db = _wiki_db()
    row = db.execute("SELECT * FROM wiki_pages WHERE slug = ?", (slug,)).fetchone()
    if not row:
        return JSONResponse({"success": False, "error": "not found"}, 404)
    if not _wiki_can_write(request, dict(row)):
        return JSONResponse({"success": False, "error": "forbidden — owner/admin only"}, 403)
    body = await request.json()
    now = datetime.now(timezone.utc).isoformat()
    title = body.get("title", slug)
    content = body.get("content", "")
    db.execute(
        "UPDATE wiki_pages SET content = ?, title = ?, updated_at = ? WHERE slug = ?",
        (content, title, now, slug),
    )
    db.commit()
    _gitlab_sync_page(slug, title, content)
    return {"success": True}


@router.post("/api/wiki", response_class=JSONResponse)
async def api_wiki_create(request: Request):
    """API: create a new wiki page (sets owner from current user)."""
    body = await request.json()
    slug = body.get("slug", "").strip().lower().replace(" ", "-")
    if not slug:
        return JSONResponse({"success": False, "error": "slug required"}, 400)
    db = _wiki_db()
    now = datetime.now(timezone.utc).isoformat()
    user = getattr(request.state, "user", None)
    owner = (getattr(user, "username", None) or getattr(user, "email", None) or "system") if user else "system"
    visibility = body.get("visibility", "public")
    try:
        db.execute(
            "INSERT INTO wiki_pages (slug, title, content, category, icon, sort_order, parent_slug, owner, visibility, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                slug,
                body.get("title", slug),
                body.get("content", ""),
                body.get("category", "general"),
                body.get("icon", ""),
                body.get("sort_order", 100),
                body.get("parent_slug"),
                owner,
                visibility,
                now,
                now,
            ),
        )
        db.commit()
    except Exception as exc:
        return JSONResponse({"success": False, "error": str(exc)}, 409)
    _gitlab_sync_page(slug, body.get("title", slug), body.get("content", ""))
    return {"success": True, "slug": slug}


@router.delete("/api/wiki/{slug}", response_class=JSONResponse)
async def api_wiki_delete(request: Request, slug: str):
    """API: delete a wiki page (RBAC enforced)."""
    db = _wiki_db()
    row = db.execute("SELECT * FROM wiki_pages WHERE slug = ?", (slug,)).fetchone()
    if not row:
        return JSONResponse({"success": False, "error": "not found"}, 404)
    if not _wiki_can_write(request, dict(row)):
        return JSONResponse({"success": False, "error": "forbidden — owner/admin only"}, 403)
    db.execute("DELETE FROM wiki_pages WHERE slug = ?", (slug,))
    db.commit()
    return {"success": True}


@router.post("/api/wiki/seed", response_class=JSONResponse)
async def api_wiki_seed():
    """Seed wiki with built-in documentation pages (INSERT OR IGNORE — keeps existing)."""
    db = _wiki_db()
    now = datetime.now(timezone.utc).isoformat()

    pages, translations = _get_seed_data()
    inserted = 0
    for p in pages:
        try:
            db.execute(
                "INSERT OR IGNORE INTO wiki_pages "
                "(slug, title, content, category, icon, sort_order, parent_slug, owner, visibility, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    p["slug"], p["title"], p["content"], p["category"],
                    p["icon"], p["sort_order"], p.get("parent_slug"),
                    p.get("owner", "system"), p.get("visibility", "public"),
                    now, now,
                ),
            )
            inserted += 1
        except Exception:
            pass
    for t in translations:
        try:
            db.execute(
                "INSERT OR IGNORE INTO wiki_translations (slug, lang, title, content, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (t["slug"], t["lang"], t["title"], t["content"], now, now),
            )
        except Exception:
            pass
    db.commit()
    return {"success": True, "inserted": inserted, "total": len(pages)}


@router.post("/api/wiki/reseed", response_class=JSONResponse)
async def api_wiki_reseed():
    """Force-update wiki pages with latest built-in content (INSERT OR REPLACE — overwrites)."""
    db = _wiki_db()
    now = datetime.now(timezone.utc).isoformat()

    pages, translations = _get_seed_data()
    updated = 0
    for p in pages:
        try:
            db.execute(
                "INSERT OR REPLACE INTO wiki_pages "
                "(slug, title, content, category, icon, sort_order, parent_slug, owner, visibility, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    p["slug"], p["title"], p["content"], p["category"],
                    p["icon"], p["sort_order"], p.get("parent_slug"),
                    p.get("owner", "system"), p.get("visibility", "public"),
                    now, now,
                ),
            )
            updated += 1
        except Exception:
            pass
    for t in translations:
        try:
            db.execute(
                "INSERT OR REPLACE INTO wiki_translations (slug, lang, title, content, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (t["slug"], t["lang"], t["title"], t["content"], now, now),
            )
        except Exception:
            pass
    db.commit()
    return {"success": True, "updated": updated, "total": len(pages), "translations": len(translations)}


def _get_seed_data():
    """Return (pages, translations) from wiki_content module."""
    from .wiki_content import WIKI_PAGES, WIKI_TRANSLATIONS
    return WIKI_PAGES, WIKI_TRANSLATIONS
