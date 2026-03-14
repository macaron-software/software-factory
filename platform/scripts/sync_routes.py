"""Discover all FastAPI routes and sync missing pages to project_screens.

Run:
    python3 -m platform.scripts.sync_routes [--project _sf] [--dry-run]

For each HTML route (non-API, non-static) not yet in project_screens:
- Creates a screen row with auto-matched feature_id (longest prefix match)
- Leaves rbac_roles empty (to be filled by retro_sf_safe.py)
"""
# Ref: feat-quality

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Allow running both as module and direct script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def _get_db():
    try:
        from platform.db.migrations import get_db
    except ImportError:
        from macaron_platform.db.migrations import get_db
    return get_db()


def _slug(url: str) -> str:
    return url.replace("/", "-").lstrip("-") or "home"


# Routes to skip (dynamic / non-page routes)
SKIP_PATTERNS = re.compile(
    r"^(/api/|/static|/ws/|/auth/|/docs|/openapi|/health|/favicon|"
    r"/manifest|/robots|/oauth|/callback|/redoc|/sw\.js|/sse/|"
    r".*/partial$|.*-partial$|.*\.js$|.*\.json$)"
)

# Param patterns like /{id} — we keep the template form for slug
PARAM_RE = re.compile(r"\{[^}]+\}")


def discover_routes() -> list[str]:
    """Return sorted list of unique page paths from the FastAPI app."""
    try:
        from platform.server import app
    except ImportError:
        from macaron_platform.server import app

    seen: set[str] = set()
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", None) or {"GET"}
        if "GET" not in methods:
            continue
        if SKIP_PATTERNS.match(path):
            continue
        if not path or path == "/":
            seen.add("/")
            continue
        # Keep only non-parameterized routes (static pages)
        if PARAM_RE.search(path):
            continue
        seen.add(path)

    return sorted(seen)


def _best_feature(url: str, db) -> str | None:
    """Find the feature whose pages best match the given URL (longest prefix)."""
    row = db.execute(
        "SELECT feature_id FROM project_screens WHERE feature_id IS NOT NULL "
        "ORDER BY LENGTH(page_url) DESC LIMIT 1"
    ).fetchone()
    if not row:
        return None

    # Try prefix match on known screens
    slug = _slug(url)
    # e.g. /metrics/tab/analytics -> try metrics-tab, metrics, etc.
    parts = slug.split("-")
    for length in range(len(parts), 0, -1):
        prefix = "-".join(parts[:length])
        match = db.execute(
            "SELECT feature_id FROM project_screens WHERE id LIKE ? LIMIT 1",
            [f"{prefix}%"],
        ).fetchone()
        if match:
            return match[0]
    return None


def sync(project_id: str = "_sf", dry_run: bool = False):
    db = _get_db()
    routes = discover_routes()
    print(f"Discovered {len(routes)} page routes")

    # Existing screens
    existing = {
        r[0]
        for r in db.execute(
            "SELECT page_url FROM project_screens WHERE project_id = ?",
            [project_id],
        ).fetchall()
    }
    print(f"Already in project_screens: {len(existing)}")

    new_routes = [r for r in routes if r not in existing]
    print(f"New routes to add: {len(new_routes)}")

    if not new_routes:
        print("Nothing to sync.")
        return

    for url in new_routes:
        screen_id = _slug(url)
        name = url.strip("/").replace("-", " ").replace("/", " - ").title() or "Home"
        feature_id = _best_feature(url, db)
        rbac = json.dumps(["admin", "project_manager", "developer", "viewer"])
        print(
            f"  {'[dry]' if dry_run else '[add]'} {url!s:40s} -> feature={feature_id}"
        )
        if not dry_run:
            db.execute(
                "INSERT OR IGNORE INTO project_screens "
                "(id, project_id, name, page_url, feature_id, rbac_roles) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [screen_id, project_id, name, url, feature_id, rbac],
            )

    if not dry_run:
        db.commit()
        print(f"Synced {len(new_routes)} new routes into project_screens.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Sync FastAPI routes to project_screens"
    )
    parser.add_argument("--project", default="_sf", help="Project ID (default: _sf)")
    parser.add_argument(
        "--dry-run", action="store_true", help="Print without inserting"
    )
    args = parser.parse_args()
    sync(project_id=args.project, dry_run=args.dry_run)
