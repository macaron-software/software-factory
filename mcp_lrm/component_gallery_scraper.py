#!/usr/bin/env python3
"""
Component Gallery Scraper
=========================
Scrapes https://component.gallery and stores all component data in SQLite.

Usage:
    python -m mcp_lrm.component_gallery_scraper          # full scrape
    python -m mcp_lrm.component_gallery_scraper --update # only missing components
    python -m mcp_lrm.component_gallery_scraper --stats  # show DB stats
"""

import argparse
import re
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

BASE_URL = "https://component.gallery"
DB_PATH = Path(__file__).parent.parent / "data" / "component_gallery.db"
USER_AGENT = "Mozilla/5.0 (compatible; SoftwareFactoryBot/1.0)"


# ---------------------------------------------------------------------------
# DB setup
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS components (
    slug        TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT DEFAULT '',
    aliases     TEXT DEFAULT '',   -- comma-separated names used in other DSes
    scraped_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS implementations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    component_slug  TEXT NOT NULL REFERENCES components(slug),
    component_name  TEXT NOT NULL,   -- name used by this design system
    ds_name         TEXT NOT NULL,   -- design system name
    url             TEXT NOT NULL,
    tech            TEXT DEFAULT '', -- React, Vue, CSS, etc.
    features        TEXT DEFAULT ''  -- Code examples,Accessibility,Open source,...
);

CREATE INDEX IF NOT EXISTS idx_impl_slug ON implementations(component_slug);
CREATE INDEX IF NOT EXISTS idx_impl_ds   ON implementations(ds_name);

CREATE VIRTUAL TABLE IF NOT EXISTS components_fts USING fts5(
    slug, name, description, aliases,
    content='components', content_rowid='rowid'
);
"""


def get_db(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


# ---------------------------------------------------------------------------
# Fetching helpers
# ---------------------------------------------------------------------------

def fetch(url: str, retries: int = 3) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise


def get_all_slugs() -> list[str]:
    html = fetch(f"{BASE_URL}/components/")
    # Match both with and without trailing slash
    slugs = re.findall(r'href="/components/([^/\"]+)/?\"', html)
    return sorted(set(s for s in slugs if s and s != "components"))


def parse_component_page(slug: str, html: str) -> dict:
    """Extract structured data from a component page."""

    # Description: first substantial paragraph after main content
    description = ""
    prose_match = re.search(
        r'<div[^>]+class="[^"]*(?:prose|description|intro)[^"]*"[^>]*>(.*?)</div>',
        html, re.DOTALL
    )
    if prose_match:
        raw = re.sub(r'<[^>]+>', ' ', prose_match.group(1))
        description = re.sub(r'\s+', ' ', raw).strip()[:1000]
    else:
        # Fallback: find paragraphs near component name
        paras = re.findall(r'<p[^>]*>([^<]{80,})</p>', html)
        for p in paras:
            clean = re.sub(r'<[^>]+>', '', p).strip()
            if len(clean) > 80 and not clean.startswith("©"):
                description = clean[:1000]
                break

    # Implementation cards — <li data-component-name="..." ...>
    impls = []
    for m in re.finditer(
        r'<li[^>]+data-component-name="([^"]*)"'
        r'[^>]+data-component-url="([^"]*)"'
        r'[^>]+data-design-system-name="([^"]*)"'
        r'(?:[^>]+data-tech="([^"]*)")?'
        r'(?:[^>]+data-features="([^"]*)")?',
        html
    ):
        impls.append({
            "component_name": m.group(1),
            "url": m.group(2),
            "ds_name": m.group(3),
            "tech": m.group(4) or "",
            "features": m.group(5) or "",
        })

    # Aliases: distinct names used across design systems
    names_used = sorted(set(i["component_name"] for i in impls))
    slug_title = slug.replace("-", " ").title()

    # Component canonical name from <title>
    title_m = re.search(r'<title>([^|<]+)', html)
    canonical_name = title_m.group(1).strip() if title_m else slug_title

    return {
        "slug": slug,
        "name": canonical_name,
        "description": description,
        "aliases": ", ".join(n for n in names_used if n.lower() != canonical_name.lower()),
        "implementations": impls,
    }


# ---------------------------------------------------------------------------
# Main scrape logic
# ---------------------------------------------------------------------------

def scrape(update_only: bool = False, verbose: bool = True):
    conn = get_db()

    if verbose:
        print("Fetching component list...", flush=True)
    slugs = get_all_slugs()
    if verbose:
        print(f"Found {len(slugs)} components", flush=True)

    if update_only:
        existing = {r[0] for r in conn.execute("SELECT slug FROM components")}
        slugs = [s for s in slugs if s not in existing]
        if verbose:
            print(f"  → {len(slugs)} new components to fetch", flush=True)

    for i, slug in enumerate(slugs, 1):
        if verbose:
            print(f"  [{i:02d}/{len(slugs)}] {slug}...", end=" ", flush=True)
        try:
            html = fetch(f"{BASE_URL}/components/{slug}/")
            data = parse_component_page(slug, html)

            conn.execute(
                "INSERT OR REPLACE INTO components(slug, name, description, aliases, scraped_at) "
                "VALUES (?, ?, ?, ?, datetime('now'))",
                (data["slug"], data["name"], data["description"], data["aliases"])
            )
            conn.execute("DELETE FROM implementations WHERE component_slug = ?", (slug,))
            for impl in data["implementations"]:
                conn.execute(
                    "INSERT INTO implementations(component_slug, component_name, ds_name, url, tech, features) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (slug, impl["component_name"], impl["ds_name"],
                     impl["url"], impl["tech"], impl["features"])
                )
            conn.commit()

            if verbose:
                print(f"{len(data['implementations'])} impls", flush=True)
            time.sleep(0.3)  # polite delay

        except Exception as e:
            if verbose:
                print(f"ERROR: {e}", flush=True)
            continue

    # Rebuild FTS index
    conn.executescript("""
        DELETE FROM components_fts;
        INSERT INTO components_fts(rowid, slug, name, description, aliases)
            SELECT rowid, slug, name, description, aliases FROM components;
    """)
    conn.commit()

    if verbose:
        total_impls = conn.execute("SELECT COUNT(*) FROM implementations").fetchone()[0]
        total_comps = conn.execute("SELECT COUNT(*) FROM components").fetchone()[0]
        print(f"\n✅ Done: {total_comps} components, {total_impls} total implementations", flush=True)

    conn.close()


def print_stats():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM components").fetchone()[0]
    impls = conn.execute("SELECT COUNT(*) FROM implementations").fetchone()[0]
    top_ds = conn.execute(
        "SELECT ds_name, COUNT(*) as n FROM implementations GROUP BY ds_name ORDER BY n DESC LIMIT 10"
    ).fetchall()
    print(f"Components: {total}")
    print(f"Implementations: {impls}")
    print("Top Design Systems:")
    for row in top_ds:
        print(f"  {row['ds_name']:40s} {row['n']:4d} components")
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--update", action="store_true", help="Only fetch missing components")
    parser.add_argument("--stats", action="store_true", help="Show DB stats")
    args = parser.parse_args()

    if args.stats:
        print_stats()
    else:
        scrape(update_only=args.update)
