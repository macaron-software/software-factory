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
import os
import re
import time
import urllib.request
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

BASE_URL = "https://component.gallery"
DB_PATH = Path(__file__).parent.parent / "data" / "component_gallery.db"
USER_AGENT = "Mozilla/5.0 (compatible; SoftwareFactoryBot/1.0)"


def _get_pg_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        for candidate in [
            Path(__file__).resolve().parents[1] / ".env",
            Path.home() / ".sf" / ".env",
        ]:
            if candidate.exists():
                for line in candidate.read_text().splitlines():
                    if line.startswith("DATABASE_URL="):
                        url = line.split("=", 1)[1].strip()
                        break
            if url:
                break
    if not url:
        raise RuntimeError("DATABASE_URL not set")
    return url


# ---------------------------------------------------------------------------
# DB setup
# ---------------------------------------------------------------------------


def _ensure_schema(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS components (
            slug        TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            description TEXT DEFAULT '',
            aliases     TEXT DEFAULT '',
            scraped_at  TEXT DEFAULT '',
            tsv         TSVECTOR GENERATED ALWAYS AS (
                to_tsvector('simple',
                    coalesce(slug,'') || ' ' || coalesce(name,'') || ' ' ||
                    coalesce(description,'') || ' ' || coalesce(aliases,''))
            ) STORED
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS implementations (
            id              BIGSERIAL PRIMARY KEY,
            component_slug  TEXT NOT NULL REFERENCES components(slug),
            component_name  TEXT NOT NULL,
            ds_name         TEXT NOT NULL,
            url             TEXT NOT NULL,
            tech            TEXT DEFAULT '',
            features        TEXT DEFAULT ''
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_impl_slug ON implementations(component_slug)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_impl_ds ON implementations(ds_name)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_components_tsv ON components USING GIN(tsv)"
    )


def get_db(path: Path = DB_PATH):
    conn = psycopg.connect(_get_pg_url(), row_factory=dict_row)
    conn.autocommit = True
    _ensure_schema(conn)
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
        except Exception:
            if attempt < retries - 1:
                time.sleep(2**attempt)
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
        html,
        re.DOTALL,
    )
    if prose_match:
        raw = re.sub(r"<[^>]+>", " ", prose_match.group(1))
        description = re.sub(r"\s+", " ", raw).strip()[:1000]
    else:
        # Fallback: find paragraphs near component name
        paras = re.findall(r"<p[^>]*>([^<]{80,})</p>", html)
        for p in paras:
            clean = re.sub(r"<[^>]+>", "", p).strip()
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
        html,
    ):
        impls.append(
            {
                "component_name": m.group(1),
                "url": m.group(2),
                "ds_name": m.group(3),
                "tech": m.group(4) or "",
                "features": m.group(5) or "",
            }
        )

    # Aliases: distinct names used across design systems
    names_used = sorted(set(i["component_name"] for i in impls))
    slug_title = slug.replace("-", " ").title()

    # Component canonical name from <title>
    title_m = re.search(r"<title>([^|<]+)", html)
    canonical_name = title_m.group(1).strip() if title_m else slug_title

    return {
        "slug": slug,
        "name": canonical_name,
        "description": description,
        "aliases": ", ".join(
            n for n in names_used if n.lower() != canonical_name.lower()
        ),
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
        existing = {r["slug"] for r in conn.execute("SELECT slug FROM components")}
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
                "INSERT INTO components(slug, name, description, aliases, scraped_at) "
                "VALUES (%s, %s, %s, %s, NOW()::TEXT) "
                "ON CONFLICT (slug) DO UPDATE SET name=EXCLUDED.name, "
                "description=EXCLUDED.description, aliases=EXCLUDED.aliases, "
                "scraped_at=EXCLUDED.scraped_at",
                (data["slug"], data["name"], data["description"], data["aliases"]),
            )
            conn.execute(
                "DELETE FROM implementations WHERE component_slug = %s", (slug,)
            )
            for impl in data["implementations"]:
                conn.execute(
                    "INSERT INTO implementations(component_slug, component_name, ds_name, url, tech, features) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (
                        slug,
                        impl["component_name"],
                        impl["ds_name"],
                        impl["url"],
                        impl["tech"],
                        impl["features"],
                    ),
                )

            if verbose:
                print(f"{len(data['implementations'])} impls", flush=True)
            time.sleep(0.3)  # polite delay

        except Exception as e:
            if verbose:
                print(f"ERROR: {e}", flush=True)
            continue

    if verbose:
        total_impls = conn.execute("SELECT COUNT(*) FROM implementations").fetchone()[
            "count"
        ]
        total_comps = conn.execute("SELECT COUNT(*) FROM components").fetchone()[
            "count"
        ]
        print(
            f"\n✅ Done: {total_comps} components, {total_impls} total implementations",
            flush=True,
        )

    conn.close()


def print_stats():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM components").fetchone()["count"]
    impls = conn.execute("SELECT COUNT(*) FROM implementations").fetchone()["count"]
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
    parser.add_argument(
        "--update", action="store_true", help="Only fetch missing components"
    )
    parser.add_argument("--stats", action="store_true", help="Show DB stats")
    args = parser.parse_args()

    if args.stats:
        print_stats()
    else:
        scrape(update_only=args.update)
