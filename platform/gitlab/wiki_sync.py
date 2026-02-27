"""
GitLab Wiki Sync — push SF platform wiki pages to GitLab project wiki.

Usage:
    python -m platform.gitlab.wiki_sync [--dry-run] [--force]

Reads wiki_pages from local SQLite, upserts to GitLab via REST API.
Creates a home page (README) with table of contents + individual pages.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Optional

import httpx

log = logging.getLogger(__name__)

GITLAB_URL = os.getenv("GITLAB_LAPOSTE_URL", "https://gitlab.azure.innovation-laposte.io")
GITLAB_TOKEN = os.getenv("GITLAB_LAPOSTE_TOKEN", "")
GITLAB_PROJECT = os.getenv("GITLAB_LAPOSTE_PROJECT", "udd-ia-native/software-factory")

# URL-encode the project path for API calls
GITLAB_PROJECT_ID = GITLAB_PROJECT.replace("/", "%2F")


def _api(path: str) -> str:
    return f"{GITLAB_URL}/api/v4/projects/{GITLAB_PROJECT_ID}/wikis{path}"


def _headers() -> dict:
    return {"PRIVATE-TOKEN": GITLAB_TOKEN, "Content-Type": "application/json"}


def list_pages() -> list[dict]:
    """List all existing wiki pages on GitLab."""
    r = httpx.get(_api("?with_content=0"), headers=_headers(), timeout=15, verify=False)
    r.raise_for_status()
    return r.json()


def upsert_page(slug: str, title: str, content: str) -> dict:
    """Create or update a GitLab wiki page."""
    existing = {p["slug"]: p for p in list_pages()}
    payload = {"title": title, "content": content, "format": "markdown"}
    if slug in existing:
        r = httpx.put(_api(f"/{slug}"), headers=_headers(), json=payload, timeout=15, verify=False)
    else:
        r = httpx.post(_api(""), headers=_headers(), json=payload, timeout=15, verify=False)
    r.raise_for_status()
    return r.json()


def build_home_page(pages: list[dict]) -> str:
    """Build a table-of-contents home page."""
    from collections import defaultdict
    by_cat: dict[str, list] = defaultdict(list)
    for p in pages:
        cat = p["category"].strip()
        by_cat[cat].append(p)

    lines = [
        "# Plateforme Agents — Documentation",
        "",
        "> Documentation de la **Plateforme Agents La Poste** — architecture multi-agents pour l'ingénierie logicielle.",
        "",
        "## Table des matières",
        "",
    ]
    for cat, items in sorted(by_cat.items(), key=lambda x: x[0]):
        # strip emoji prefix for cleaner header
        cat_clean = cat.split(" ", 1)[-1] if cat[0].isdigit() or not cat[0].isalpha() else cat
        lines.append(f"### {cat_clean}")
        lines.append("")
        for p in sorted(items, key=lambda x: x.get("sort_order", 99)):
            lines.append(f"- [{p['title']}]({p['slug']})")
        lines.append("")

    lines += [
        "---",
        "",
        "*Synchronisé automatiquement depuis la [Software Factory](https://sf.macaron-software.com)*",
    ]
    return "\n".join(lines)


def sync(dry_run: bool = False, force: bool = False) -> dict:
    """Sync all SF wiki pages to GitLab wiki."""
    from ..db.migrations import get_db

    db = get_db()
    pages = db.execute(
        "SELECT slug, title, category, content, sort_order FROM wiki_pages ORDER BY category, sort_order, title"
    ).fetchall()

    if not pages:
        return {"status": "error", "message": "No wiki pages found in DB"}

    # Fetch existing GitLab pages (for upsert logic)
    try:
        existing = {p["slug"]: p for p in list_pages()}
    except Exception as e:
        return {"status": "error", "message": f"GitLab API error: {e}"}

    results = {"created": [], "updated": [], "skipped": [], "errors": []}

    # Push individual pages
    for row in pages:
        slug = row["slug"]
        title = row["title"]
        content = row["content"] or ""

        if not force and slug in existing:
            results["skipped"].append(slug)
            log.debug("skip %s (exists, use --force to overwrite)", slug)
            continue

        action = "update" if slug in existing else "create"
        log.info("%s %s — %s", action, slug, title)

        if dry_run:
            results["created" if action == "create" else "updated"].append(slug)
            continue

        try:
            payload = {"title": title, "content": content, "format": "markdown"}
            if action == "update":
                r = httpx.put(_api(f"/{slug}"), headers=_headers(), json=payload, timeout=15, verify=False)
            else:
                r = httpx.post(_api(""), headers=_headers(), json=payload, timeout=15, verify=False)
            r.raise_for_status()
            results["created" if action == "create" else "updated"].append(slug)
        except Exception as e:
            log.error("error pushing %s: %s", slug, e)
            results["errors"].append({"slug": slug, "error": str(e)})

    # Build and push home page
    page_dicts = [dict(p) for p in pages]
    home_content = build_home_page(page_dicts)
    home_slug = "home"

    if not dry_run:
        try:
            payload = {"title": "Home", "content": home_content, "format": "markdown"}
            if home_slug in existing:
                r = httpx.put(_api(f"/{home_slug}"), headers=_headers(), json=payload, timeout=15, verify=False)
            else:
                r = httpx.post(_api(""), headers=_headers(), json=payload, timeout=15, verify=False)
            r.raise_for_status()
            results["created" if home_slug not in existing else "updated"].append(home_slug)
        except Exception as e:
            results["errors"].append({"slug": home_slug, "error": str(e)})

    results["status"] = "ok" if not results["errors"] else "partial"
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    dry = "--dry-run" in sys.argv
    force = "--force" in sys.argv

    if not GITLAB_TOKEN:
        print("ERROR: GITLAB_LAPOSTE_TOKEN not set")
        sys.exit(1)

    print(f"Syncing SF wiki → {GITLAB_URL}/{GITLAB_PROJECT} wiki {'(DRY RUN)' if dry else ''}")
    result = sync(dry_run=dry, force=force)
    print(f"\nResult: {result['status']}")
    if result.get("created"):
        print(f"  Created: {result['created']}")
    if result.get("updated"):
        print(f"  Updated: {result['updated']}")
    if result.get("skipped"):
        print(f"  Skipped (use --force): {len(result['skipped'])} pages")
    if result.get("errors"):
        print(f"  Errors: {result['errors']}")
