#!/usr/bin/env python3
"""
Architecture Guidelines Scraper
================================
Scrapes org/project wiki (Confluence, GitLab Wiki, or Markdown directory)
into a structured SQLite database, then exposed via MCP tools.

The goal: agents automatically respect DSI/org architectural guidelines
by having them injected into their system prompt.

Sources supported:
  - Confluence (REST API)
  - GitLab Wiki (API or local clone)
  - Markdown directory (local .md files)
  - URL list (raw HTML fetch)

Database: data/guidelines.db
  • guideline_pages  — raw scraped pages (id, space, title, url, category, content, summary)
  • guideline_items  — extracted constraints (must_use, forbidden, standard, pattern, decision)
  • guideline_fts    — FTS5 virtual table

Usage:
    python -m mcp_lrm.guidelines_scraper --source confluence --space EXAMPLE --project myproject
    python -m mcp_lrm.guidelines_scraper --source markdown --path /path/to/wiki --project myproject
    python -m mcp_lrm.guidelines_scraper --stats --project myproject
    python -m mcp_lrm.guidelines_scraper --summary --project myproject
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

DB_PATH = Path(__file__).parent.parent / "data" / "guidelines.db"


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


# ── Keywords for auto-categorization ─────────────────────────────────────────

_CAT_KEYWORDS: dict[str, list[str]] = {
    "tech_stack": [
        "stack",
        "technologies",
        "socle",
        "technologique",
        "framework",
        "version",
        "runtime",
        "langage",
        "language",
        "bibliothèque",
        "library",
        "dependency",
        "dépendance",
        "java",
        "python",
        "react",
        "vue",
        "angular",
        "spring",
        "node",
        "dotnet",
        ".net",
    ],
    "forbidden": [
        "interdit",
        "prohib",
        "forbidden",
        "ne pas",
        "ne jamais",
        "banned",
        "déprécié",
        "deprecated",
        "éviter",
        "avoid",
        "proscrit",
        "not allowed",
        "not permitted",
    ],
    "pattern": [
        "pattern",
        "architecture",
        "design",
        "principe",
        "principle",
        "clean archi",
        "ddd",
        "cqrs",
        "event",
        "microservice",
        "hexagonal",
        "couche",
        "layer",
        "structure",
    ],
    "standard": [
        "standard",
        "norme",
        "convention",
        "règle",
        "rule",
        "naming",
        "format",
        "api",
        "rest",
        "openapi",
        "swagger",
        "logging",
        "log",
        "monitoring",
        "observabilité",
    ],
    "adr": [
        "adr",
        "décision",
        "decision",
        "record",
        "choix",
        "choice",
        "rationale",
        "why",
        "pourquoi",
    ],
}

# ── Constraint extraction patterns ───────────────────────────────────────────
# Simple heuristics to extract concrete constraints from text

_CONSTRAINT_PATTERNS = [
    # "Utiliser Spring Boot 3.x"
    (r"(?:utiliser?|use|employ|adopter?)\s+([^\n.]{5,80})", "must_use"),
    # "Ne pas utiliser jQuery"
    (
        r"(?:ne pas|ne jamais|interdit|forbidden|banned|avoid|éviter)\s+(?:utiliser?\s+)?([^\n.]{3,80})",
        "forbidden",
    ),
    # "Version minimale : Java 17"
    (r"version\s+(?:minimale?|minimum|requise?)[\s:]+([^\n.]{3,60})", "standard"),
    # "Standard : OAuth2 / OIDC"
    (r"standard\s*[:–-]\s*([^\n.]{5,80})", "standard"),
    # "Pattern : Clean Architecture"
    (r"(?:pattern|architecture)\s*[:–-]\s*([^\n.]{5,80})", "pattern"),
    # Bullet lines starting with ✓ or ✅
    (r"[✓✅]\s+([^\n]{5,100})", "must_use"),
    # Bullet lines starting with ✗ or ❌ or ⛔
    (r"[✗❌⛔🚫]\s+([^\n]{5,100})", "forbidden"),
]


# ── DB helpers ────────────────────────────────────────────────────────────────


def get_db(project: str = "default"):
    conn = psycopg.connect(_get_pg_url(), row_factory=dict_row)
    conn.autocommit = True
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS guideline_pages (
            id          TEXT PRIMARY KEY,
            project     TEXT NOT NULL DEFAULT 'default',
            space       TEXT,
            title       TEXT,
            url         TEXT,
            category    TEXT DEFAULT 'other',
            content     TEXT,
            summary     TEXT,
            tags        TEXT,
            updated_at  TEXT,
            tsv         TSVECTOR GENERATED ALWAYS AS (
                to_tsvector('simple',
                    coalesce(title,'') || ' ' || coalesce(content,'') || ' ' || coalesce(summary,''))
            ) STORED
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS guideline_items (
            id              BIGSERIAL PRIMARY KEY,
            project         TEXT NOT NULL DEFAULT 'default',
            category        TEXT,
            topic           TEXT,
            constraint_text TEXT,
            source_page_id  TEXT,
            source_title    TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS guideline_meta (
            project     TEXT PRIMARY KEY,
            source      TEXT,
            space       TEXT,
            last_sync   TEXT,
            page_count  INTEGER DEFAULT 0,
            item_count  INTEGER DEFAULT 0,
            config_json TEXT
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_guideline_pages_tsv ON guideline_pages USING GIN(tsv)"
    )


def _upsert_page(
    conn,
    page_id: str,
    project: str,
    space: str,
    title: str,
    url: str,
    content: str,
    category: str,
    summary: str,
    tags: str = "",
    updated_at: str = "",
) -> None:
    conn.execute(
        """INSERT INTO guideline_pages
           (id, project, space, title, url, category, content, summary, tags, updated_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (id) DO UPDATE SET
               project=EXCLUDED.project, space=EXCLUDED.space, title=EXCLUDED.title,
               url=EXCLUDED.url, category=EXCLUDED.category, content=EXCLUDED.content,
               summary=EXCLUDED.summary, tags=EXCLUDED.tags, updated_at=EXCLUDED.updated_at""",
        (
            page_id,
            project,
            space,
            title,
            url,
            category,
            content,
            summary,
            tags,
            updated_at,
        ),
    )


def _insert_items(
    conn,
    project: str,
    page_id: str,
    page_title: str,
    items: list[tuple],
) -> None:
    """items: list of (category, topic, constraint_text)"""
    conn.execute("DELETE FROM guideline_items WHERE source_page_id = %s", (page_id,))
    conn.executemany(
        "INSERT INTO guideline_items (project, category, topic, constraint_text, source_page_id, source_title) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        [
            (project, cat, topic, text, page_id, page_title)
            for cat, topic, text in items
        ],
    )


# ── Categorization ────────────────────────────────────────────────────────────


def _categorize(title: str, content: str) -> str:
    combined = (title + " " + content[:500]).lower()
    scores: dict[str, int] = {cat: 0 for cat in _CAT_KEYWORDS}
    for cat, kws in _CAT_KEYWORDS.items():
        for kw in kws:
            if kw in combined:
                scores[cat] += 1
    best = max(scores, key=lambda c: scores[c])
    return best if scores[best] > 0 else "other"


def _make_summary(title: str, content: str) -> str:
    """Extract a 200-char summary from content."""
    # Remove markdown headers, links, code blocks
    text = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
    text = re.sub(r"`[^`]+`", "", text)
    text = re.sub(r"#+ ", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:200]


def _extract_items(
    page_id: str, title: str, content: str, category: str
) -> list[tuple]:
    """Extract (category, topic, constraint_text) triples from page content."""
    items: list[tuple] = []
    seen: set[str] = set()

    for pattern, cat in _CONSTRAINT_PATTERNS:
        for m in re.finditer(pattern, content, re.IGNORECASE):
            text = m.group(1).strip().rstrip(".,;")
            if len(text) < 5 or text in seen:
                continue
            seen.add(text)
            # Guess topic from title + match
            topic = _guess_topic(title + " " + text)
            items.append((cat, topic, text))

    return items[:50]  # cap per page


def _guess_topic(text: str) -> str:
    text_lower = text.lower()
    topics = {
        "backend": [
            "java",
            "spring",
            "python",
            "node",
            "api",
            "rest",
            "microservice",
            "back",
        ],
        "frontend": [
            "react",
            "vue",
            "angular",
            "typescript",
            "javascript",
            "css",
            "front",
            "ui",
        ],
        "database": [
            "sql",
            "postgres",
            "mysql",
            "mongodb",
            "redis",
            "elasticsearch",
            "bdd",
            "database",
            "base de données",
        ],
        "auth": ["oauth", "oidc", "jwt", "sso", "auth", "keycloak", "ldap", "identity"],
        "infra": [
            "docker",
            "kubernetes",
            "k8s",
            "helm",
            "aws",
            "azure",
            "cloud",
            "infra",
            "ci/cd",
            "pipeline",
        ],
        "security": [
            "sécurité",
            "security",
            "tls",
            "ssl",
            "https",
            "cert",
            "scan",
            "sast",
            "dast",
            "owasp",
        ],
        "quality": [
            "test",
            "sonar",
            "coverage",
            "qualité",
            "quality",
            "revue",
            "review",
            "lint",
        ],
        "logging": [
            "log",
            "trace",
            "monitoring",
            "observ",
            "metrics",
            "kibana",
            "grafana",
        ],
    }
    for topic, kws in topics.items():
        if any(kw in text_lower for kw in kws):
            return topic
    return "general"


# ── Scrapers ─────────────────────────────────────────────────────────────────


def scrape_confluence(
    project: str,
    space: str,
    confluence_url: str,
    token: str,
    limit: int = 200,
    verbose: bool = False,
) -> int:
    """Scrape a Confluence space via REST API → DB."""
    import urllib.request

    conn = get_db(project)
    conn.execute("DELETE FROM guideline_pages WHERE project = %s", (project,))
    conn.execute("DELETE FROM guideline_items WHERE project = %s", (project,))

    start = 0
    total = 0
    base = confluence_url.rstrip("/")
    auth_header = f"Bearer {token}"

    while True:
        url = (
            f"{base}/rest/api/content"
            f"?spaceKey={space}&limit=50&start={start}"
            f"&expand=body.storage,version"
        )
        req = urllib.request.Request(url)
        req.add_header("Authorization", auth_header)
        req.add_header("Accept", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
        except Exception as e:
            print(f"  ⚠ Confluence error at start={start}: {e}")
            break

        results = data.get("results", [])
        if not results:
            break

        for page in results:
            page_id = page["id"]
            title = page["title"]
            body = page.get("body", {}).get("storage", {}).get("value", "")
            # Strip HTML tags
            content = re.sub(r"<[^>]+>", " ", body)
            content = re.sub(r"&\w+;", " ", content)
            content = re.sub(r"\s+", " ", content).strip()

            page_url = f"{base}/pages/{page_id}"
            category = _categorize(title, content)
            summary = _make_summary(title, content)
            updated = page.get("version", {}).get("when", "")

            _upsert_page(
                conn,
                page_id,
                project,
                space,
                title,
                page_url,
                content,
                category,
                summary,
                updated_at=updated,
            )
            items = _extract_items(page_id, title, content, category)
            if items:
                _insert_items(conn, project, page_id, title, items)
            total += 1
            if verbose:
                print(f"  ✓ [{category:10}] {title[:60]}")

            if total >= limit:
                break

        if total >= limit or len(results) < 50:
            break
        start += 50
        time.sleep(0.2)  # be nice to Confluence

    item_count = conn.execute(
        "SELECT COUNT(*) FROM guideline_items WHERE project = %s", (project,)
    ).fetchone()["count"]
    conn.execute(
        "INSERT INTO guideline_meta (project, source, space, last_sync, page_count, item_count) "
        "VALUES (%s, 'confluence', %s, NOW(), %s, %s) "
        "ON CONFLICT (project) DO UPDATE SET source=EXCLUDED.source, space=EXCLUDED.space, "
        "last_sync=EXCLUDED.last_sync, page_count=EXCLUDED.page_count, item_count=EXCLUDED.item_count",
        (project, space, total, item_count),
    )
    conn.close()
    return total


def scrape_markdown_dir(
    project: str,
    path: str,
    space: str = "local",
    verbose: bool = False,
) -> int:
    """Scrape a directory of .md files → DB."""
    root = Path(path)
    if not root.exists():
        print(f"⚠ Path not found: {path}")
        return 0

    conn = get_db(project)
    conn.execute("DELETE FROM guideline_pages WHERE project = %s", (project,))
    conn.execute("DELETE FROM guideline_items WHERE project = %s", (project,))

    total = 0
    for md_file in sorted(root.rglob("*.md")):
        rel = str(md_file.relative_to(root))
        page_id = rel.replace("/", "_").replace("\\", "_")
        title = md_file.stem.replace("-", " ").replace("_", " ").title()
        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception:
            continue

        category = _categorize(title, content)
        summary = _make_summary(title, content)
        updated = str(md_file.stat().st_mtime)

        _upsert_page(
            conn,
            page_id,
            project,
            space,
            title,
            str(md_file),
            content,
            category,
            summary,
            updated_at=updated,
        )
        items = _extract_items(page_id, title, content, category)
        if items:
            _insert_items(conn, project, page_id, title, items)
        total += 1
        if verbose:
            print(f"  ✓ [{category:10}] {title[:60]}")

    item_count = conn.execute(
        "SELECT COUNT(*) FROM guideline_items WHERE project = %s", (project,)
    ).fetchone()["count"]
    conn.execute(
        "INSERT INTO guideline_meta (project, source, space, last_sync, page_count, item_count) "
        "VALUES (%s, 'markdown', %s, NOW(), %s, %s) "
        "ON CONFLICT (project) DO UPDATE SET source=EXCLUDED.source, space=EXCLUDED.space, "
        "last_sync=EXCLUDED.last_sync, page_count=EXCLUDED.page_count, item_count=EXCLUDED.item_count",
        (project, space, total, item_count),
    )
    conn.close()
    return total


def scrape_gitlab_wiki(
    project: str,
    gitlab_url: str,
    gitlab_project_id: str,
    token: str,
    verbose: bool = False,
) -> int:
    """Scrape a GitLab project wiki via API → DB."""
    import urllib.request

    conn = get_db(project)
    conn.execute("DELETE FROM guideline_pages WHERE project = %s", (project,))
    conn.execute("DELETE FROM guideline_items WHERE project = %s", (project,))

    base = gitlab_url.rstrip("/")
    url = (
        f"{base}/api/v4/projects/{gitlab_project_id}/wikis?with_content=1&per_page=100"
    )
    req = urllib.request.Request(url)
    req.add_header("PRIVATE-TOKEN", token)

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            pages = json.loads(resp.read())
    except Exception as e:
        print(f"⚠ GitLab Wiki error: {e}")
        conn.close()
        return 0

    total = 0
    for page in pages:
        page_id = page.get("slug", str(total))
        title = page.get("title", "")
        content = page.get("content", "")
        page_url = f"{base}/wikis/{page_id}"
        category = _categorize(title, content)
        summary = _make_summary(title, content)

        _upsert_page(
            conn,
            page_id,
            project,
            "gitlab-wiki",
            title,
            page_url,
            content,
            category,
            summary,
        )
        items = _extract_items(page_id, title, content, category)
        if items:
            _insert_items(conn, project, page_id, title, items)
        total += 1
        if verbose:
            print(f"  ✓ [{category:10}] {title[:60]}")

    item_count = conn.execute(
        "SELECT COUNT(*) FROM guideline_items WHERE project = %s", (project,)
    ).fetchone()["count"]
    conn.execute(
        "INSERT INTO guideline_meta (project, source, space, last_sync, page_count, item_count) "
        "VALUES (%s, 'gitlab', %s, NOW(), %s, %s) "
        "ON CONFLICT (project) DO UPDATE SET source=EXCLUDED.source, space=EXCLUDED.space, "
        "last_sync=EXCLUDED.last_sync, page_count=EXCLUDED.page_count, item_count=EXCLUDED.item_count",
        (project, "gitlab-wiki", total, item_count),
    )
    conn.close()
    return total


# ── Summary builder ───────────────────────────────────────────────────────────


def build_guidelines_summary(
    project: str, role: str = "dev", max_chars: int = 800
) -> str:
    """Build a compact guidelines summary for prompt injection.

    Returns a string like:
        ## Tech Stack
        - Backend: Java 17, Spring Boot 3.2
        - Frontend: React 18, TypeScript 5
        ## Forbidden
        - Ne pas utiliser jQuery
        - MongoDB sans validation archi interdite
        ## Standards
        - Auth: OAuth2/OIDC via Keycloak
    """
    if not DB_PATH.exists():
        return ""

    try:
        conn = get_db()
    except Exception:
        return ""

    meta = conn.execute(
        "SELECT page_count FROM guideline_meta WHERE project = %s", (project,)
    ).fetchone()
    if not meta or meta["page_count"] == 0:
        conn.close()
        return ""

    sections: list[str] = []

    # Tech stack items
    must_use = conn.execute(
        "SELECT topic, constraint_text FROM guideline_items "
        "WHERE project = %s AND category = 'must_use' ORDER BY topic LIMIT 20",
        (project,),
    ).fetchall()
    if must_use:
        lines = [f"- {r['topic'].title()}: {r['constraint_text']}" for r in must_use]
        sections.append("**Tech Stack requis**\n" + "\n".join(lines))

    # Forbidden items
    forbidden = conn.execute(
        "SELECT constraint_text FROM guideline_items "
        "WHERE project = %s AND category = 'forbidden' ORDER BY topic LIMIT 15",
        (project,),
    ).fetchall()
    if forbidden:
        lines = [f"- {r['constraint_text']}" for r in forbidden]
        sections.append("**Interdit / Proscrit**\n" + "\n".join(lines))

    # Standards
    standards = conn.execute(
        "SELECT topic, constraint_text FROM guideline_items "
        "WHERE project = %s AND category IN ('standard', 'pattern') ORDER BY topic LIMIT 15",
        (project,),
    ).fetchall()
    if standards:
        lines = [f"- {r['topic'].title()}: {r['constraint_text']}" for r in standards]
        sections.append("**Standards & Patterns**\n" + "\n".join(lines))

    conn.close()

    if not sections:
        return ""

    result = "\n\n".join(sections)
    if len(result) > max_chars:
        result = result[:max_chars] + "..."
    return result


# ── CLI ───────────────────────────────────────────────────────────────────────


def _print_stats(project: str) -> None:
    try:
        conn = get_db()
    except Exception:
        print("DB not found")
        return
    meta = conn.execute(
        "SELECT * FROM guideline_meta WHERE project = %s", (project,)
    ).fetchone()
    if not meta:
        print(f"No data for project '{project}'")
        conn.close()
        return
    print(f"Project:    {project}")
    print(f"Source:     {meta['source']} / {meta['space']}")
    print(f"Last sync:  {meta['last_sync']}")
    print(f"Pages:      {meta['page_count']}")
    print(f"Items:      {meta['item_count']}")
    cats = conn.execute(
        "SELECT category, COUNT(*) as n FROM guideline_pages WHERE project=%s GROUP BY category ORDER BY n DESC",
        (project,),
    ).fetchall()
    print("\nPages by category:")
    for r in cats:
        print(f"  {r['category']:15} {r['n']}")
    cat_items = conn.execute(
        "SELECT category, COUNT(*) as n FROM guideline_items WHERE project=%s GROUP BY category ORDER BY n DESC",
        (project,),
    ).fetchall()
    print("\nItems by category:")
    for r in cat_items:
        print(f"  {r['category']:15} {r['n']}")
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Architecture Guidelines Scraper")
    parser.add_argument("--project", default="default", help="Project ID")
    parser.add_argument(
        "--source", choices=["confluence", "markdown", "gitlab"], help="Source type"
    )
    parser.add_argument("--space", default="", help="Confluence space key or label")
    parser.add_argument("--url", default="", help="Confluence/GitLab base URL")
    parser.add_argument(
        "--token",
        default="",
        help="API token (or use CONFLUENCE_TOKEN / GITLAB_TOKEN env)",
    )
    parser.add_argument("--path", default="", help="Local directory (markdown source)")
    parser.add_argument("--gitlab-project-id", default="", help="GitLab project ID")
    parser.add_argument("--limit", type=int, default=200, help="Max pages to scrape")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--stats", action="store_true", help="Show DB stats")
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Show guidelines summary for prompt injection",
    )
    parser.add_argument(
        "--list-projects", action="store_true", help="List all projects in DB"
    )
    args = parser.parse_args()

    if args.stats:
        _print_stats(args.project)
        return

    if args.summary:
        summary = build_guidelines_summary(args.project)
        if summary:
            print(summary)
        else:
            print(f"No guidelines found for project '{args.project}'")
        return

    if args.list_projects:
        try:
            conn = get_db()
        except Exception:
            print("DB not found")
            return
        rows = conn.execute(
            "SELECT project, source, space, last_sync, page_count, item_count FROM guideline_meta ORDER BY project"
        ).fetchall()
        print(
            f"{'Project':20} {'Source':12} {'Space':15} {'Last sync':20} {'Pages':6} {'Items':6}"
        )
        for r in rows:
            print(
                f"{r['project']:20} {r['source']:12} {r['space']:15} {r['last_sync']:20} {r['page_count']:6} {r['item_count']:6}"
            )
        conn.close()
        return

    if not args.source:
        parser.print_help()
        return

    if args.source == "confluence":
        url = args.url or os.environ.get("CONFLUENCE_URL", "")
        token = args.token or os.environ.get("CONFLUENCE_TOKEN", "")
        if not url or not token:
            print(
                "⚠ Need --url and --token (or CONFLUENCE_URL / CONFLUENCE_TOKEN env vars)"
            )
            sys.exit(1)
        print(f"Scraping Confluence space '{args.space}' → project '{args.project}'...")
        n = scrape_confluence(
            args.project, args.space, url, token, limit=args.limit, verbose=args.verbose
        )
        print(f"✓ {n} pages scraped")
        _print_stats(args.project)

    elif args.source == "markdown":
        if not args.path:
            print("⚠ Need --path for markdown source")
            sys.exit(1)
        print(f"Scraping Markdown dir '{args.path}' → project '{args.project}'...")
        n = scrape_markdown_dir(
            args.project, args.path, space=args.space or "local", verbose=args.verbose
        )
        print(f"✓ {n} files scraped")
        _print_stats(args.project)

    elif args.source == "gitlab":
        url = args.url or os.environ.get("GITLAB_URL", "")
        token = args.token or os.environ.get("GITLAB_TOKEN", "")
        gid = args.gitlab_project_id or os.environ.get("GITLAB_PROJECT_ID", "")
        if not url or not token or not gid:
            print("⚠ Need --url, --token, --gitlab-project-id (or env vars)")
            sys.exit(1)
        print(f"Scraping GitLab Wiki (project {gid}) → project '{args.project}'...")
        n = scrape_gitlab_wiki(args.project, url, gid, token, verbose=args.verbose)
        print(f"✓ {n} pages scraped")
        _print_stats(args.project)


if __name__ == "__main__":
    main()
