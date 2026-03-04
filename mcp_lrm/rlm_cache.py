"""
RLM Cache — PostgreSQL cache for Confluence/Jira content.
Provides fast full-text search without re-fetching from APIs.
"""

import os
import time
from pathlib import Path
from typing import Optional

_STALE_SECONDS = 3600  # 1 hour


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


def _get_db():
    import psycopg
    from psycopg.rows import dict_row

    conn = psycopg.connect(_get_pg_url(), row_factory=dict_row)
    conn.autocommit = True
    return conn


def _ensure_schema(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS confluence_pages (
                page_id TEXT PRIMARY KEY,
                space_key TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL DEFAULT '',
                url TEXT DEFAULT '',
                ancestors TEXT DEFAULT '',
                updated_at DOUBLE PRECISION NOT NULL,
                fetched_at DOUBLE PRECISION NOT NULL,
                tsv TSVECTOR GENERATED ALWAYS AS (
                    to_tsvector('simple', coalesce(title,'') || ' ' || coalesce(body,''))
                ) STORED
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_confluence_fts ON confluence_pages USING GIN(tsv)
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS jira_issues (
                issue_key TEXT PRIMARY KEY,
                project TEXT NOT NULL,
                summary TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                status TEXT DEFAULT '',
                assignee TEXT DEFAULT '',
                priority TEXT DEFAULT '',
                issue_type TEXT DEFAULT '',
                labels TEXT DEFAULT '',
                created_at TEXT DEFAULT '',
                updated_at DOUBLE PRECISION NOT NULL,
                fetched_at DOUBLE PRECISION NOT NULL,
                tsv TSVECTOR GENERATED ALWAYS AS (
                    to_tsvector('simple', coalesce(summary,'') || ' ' || coalesce(description,''))
                ) STORED
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_jira_fts ON jira_issues USING GIN(tsv)
        """)


class RLMCache:
    """Cache manager for Confluence/Jira content."""

    def __init__(self):
        self.db = _get_db()
        _ensure_schema(self.db)

    # ── Confluence ──

    def upsert_confluence_page(
        self,
        page_id: str,
        space_key: str,
        title: str,
        body: str,
        url: str = "",
        ancestors: str = "",
    ):
        """Insert or update a Confluence page in cache."""
        now = time.time()
        with self.db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO confluence_pages (page_id, space_key, title, body, url, ancestors, updated_at, fetched_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(page_id) DO UPDATE SET
                    title=EXCLUDED.title, body=EXCLUDED.body, url=EXCLUDED.url,
                    ancestors=EXCLUDED.ancestors, updated_at=EXCLUDED.updated_at, fetched_at=EXCLUDED.fetched_at
            """,
                (page_id, space_key, title, body, url, ancestors, now, now),
            )

    def search_confluence(self, query: str, limit: int = 10) -> list[dict]:
        """Full-text search in cached Confluence pages."""
        with self.db.cursor() as cur:
            cur.execute(
                """
                SELECT page_id, space_key, title, url, ancestors,
                       ts_headline('simple', body, plainto_tsquery('simple', %s),
                                   'MaxWords=40,MinWords=10,StartSel=<b>,StopSel=</b>') as excerpt
                FROM confluence_pages
                WHERE tsv @@ plainto_tsquery('simple', %s)
                ORDER BY ts_rank(tsv, plainto_tsquery('simple', %s)) DESC
                LIMIT %s
            """,
                (query, query, query, limit),
            )
            return cur.fetchall() or []

    def get_confluence_page(self, page_id: str) -> Optional[dict]:
        """Get a cached Confluence page."""
        with self.db.cursor() as cur:
            cur.execute(
                "SELECT page_id, space_key, title, body, url, ancestors, fetched_at "
                "FROM confluence_pages WHERE page_id=%s",
                (page_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        row["stale"] = (time.time() - row["fetched_at"]) > _STALE_SECONDS
        return row

    def list_confluence_pages(self, space_key: str = "") -> list[dict]:
        """List cached Confluence pages."""
        with self.db.cursor() as cur:
            if space_key:
                cur.execute(
                    "SELECT page_id, title, url, fetched_at FROM confluence_pages "
                    "WHERE space_key=%s ORDER BY title",
                    (space_key,),
                )
            else:
                cur.execute(
                    "SELECT page_id, title, url, fetched_at FROM confluence_pages ORDER BY title"
                )
            rows = cur.fetchall() or []
        for r in rows:
            r["stale"] = (time.time() - r["fetched_at"]) > _STALE_SECONDS
        return rows

    # ── Jira ──

    def upsert_jira_issue(
        self,
        issue_key: str,
        project: str,
        summary: str,
        description: str = "",
        status: str = "",
        assignee: str = "",
        priority: str = "",
        issue_type: str = "",
        labels: str = "",
        created_at: str = "",
    ):
        """Insert or update a Jira issue in cache."""
        now = time.time()
        with self.db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO jira_issues (issue_key, project, summary, description, status, assignee,
                                         priority, issue_type, labels, created_at, updated_at, fetched_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(issue_key) DO UPDATE SET
                    summary=EXCLUDED.summary, description=EXCLUDED.description, status=EXCLUDED.status,
                    assignee=EXCLUDED.assignee, priority=EXCLUDED.priority, issue_type=EXCLUDED.issue_type,
                    labels=EXCLUDED.labels, updated_at=EXCLUDED.updated_at, fetched_at=EXCLUDED.fetched_at
            """,
                (
                    issue_key,
                    project,
                    summary,
                    description,
                    status,
                    assignee,
                    priority,
                    issue_type,
                    labels,
                    created_at,
                    now,
                    now,
                ),
            )

    def search_jira(self, query: str, limit: int = 20) -> list[dict]:
        """Full-text search in cached Jira issues."""
        with self.db.cursor() as cur:
            cur.execute(
                """
                SELECT issue_key, project, summary, status, priority, assignee, issue_type,
                       ts_headline('simple', description, plainto_tsquery('simple', %s),
                                   'MaxWords=40,MinWords=10,StartSel=<b>,StopSel=</b>') as excerpt
                FROM jira_issues
                WHERE tsv @@ plainto_tsquery('simple', %s)
                ORDER BY ts_rank(tsv, plainto_tsquery('simple', %s)) DESC
                LIMIT %s
            """,
                (query, query, query, limit),
            )
            return cur.fetchall() or []

    def get_jira_issue(self, issue_key: str) -> Optional[dict]:
        """Get a cached Jira issue."""
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM jira_issues WHERE issue_key=%s", (issue_key,))
            row = cur.fetchone()
        if not row:
            return None
        row["stale"] = (time.time() - row["fetched_at"]) > _STALE_SECONDS
        return row

    def stats(self) -> dict:
        """Cache statistics."""
        with self.db.cursor() as cur:
            cur.execute("SELECT COUNT(*) as c FROM confluence_pages")
            c_count = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) as c FROM jira_issues")
            j_count = cur.fetchone()["c"]
        return {
            "confluence_pages": c_count,
            "jira_issues": j_count,
            "backend": "postgresql",
        }


_cache: Optional[RLMCache] = None


def get_rlm_cache() -> RLMCache:
    """Get or create the RLM cache singleton."""
    global _cache
    if _cache is None:
        _cache = RLMCache()
    return _cache
