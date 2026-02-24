"""
RLM Cache — SQLite FTS5 cache for Confluence/Jira content.
Provides fast full-text search without re-fetching from APIs.
"""

import sqlite3
import time
from pathlib import Path
from typing import Optional

_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "rlm_cache.db"
_STALE_SECONDS = 3600  # 1 hour


def _get_db() -> sqlite3.Connection:
    """Get or create the RLM cache database."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(_DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")

    # Confluence pages cache
    db.execute("""
        CREATE TABLE IF NOT EXISTS confluence_pages (
            page_id TEXT PRIMARY KEY,
            space_key TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL DEFAULT '',
            url TEXT DEFAULT '',
            ancestors TEXT DEFAULT '',
            updated_at REAL NOT NULL,
            fetched_at REAL NOT NULL
        )
    """)

    # FTS5 index for Confluence (standalone — no content sync)
    try:
        db.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS confluence_fts
            USING fts5(title, body, page_id UNINDEXED)
        """)
    except sqlite3.OperationalError:
        pass

    # Jira issues cache
    db.execute("""
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
            updated_at REAL NOT NULL,
            fetched_at REAL NOT NULL
        )
    """)

    # FTS5 index for Jira (standalone — no content sync)
    try:
        db.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS jira_fts
            USING fts5(summary, description, issue_key UNINDEXED)
        """)
    except sqlite3.OperationalError:
        pass

    db.commit()
    return db


class RLMCache:
    """Cache manager for Confluence/Jira content."""

    def __init__(self):
        self.db = _get_db()

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
        self.db.execute(
            """
            INSERT INTO confluence_pages (page_id, space_key, title, body, url, ancestors, updated_at, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(page_id) DO UPDATE SET
                title=excluded.title, body=excluded.body, url=excluded.url,
                ancestors=excluded.ancestors, updated_at=excluded.updated_at, fetched_at=excluded.fetched_at
        """,
            (page_id, space_key, title, body, url, ancestors, now, now),
        )
        # Update FTS
        self.db.execute("DELETE FROM confluence_fts WHERE page_id=?", (page_id,))
        self.db.execute(
            "INSERT INTO confluence_fts (title, body, page_id) VALUES (?, ?, ?)",
            (title, body, page_id),
        )
        self.db.commit()

    def search_confluence(self, query: str, limit: int = 10) -> list[dict]:
        """Full-text search in cached Confluence pages."""
        rows = self.db.execute(
            """
            SELECT p.page_id, p.space_key, p.title, p.url, p.ancestors,
                   snippet(confluence_fts, 1, '<b>', '</b>', '...', 40) as excerpt
            FROM confluence_fts f
            JOIN confluence_pages p ON f.page_id = p.page_id
            WHERE confluence_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """,
            (query, limit),
        ).fetchall()
        return [
            {
                "page_id": r[0],
                "space_key": r[1],
                "title": r[2],
                "url": r[3],
                "ancestors": r[4],
                "excerpt": r[5],
            }
            for r in rows
        ]

    def get_confluence_page(self, page_id: str) -> Optional[dict]:
        """Get a cached Confluence page."""
        row = self.db.execute(
            "SELECT page_id, space_key, title, body, url, ancestors, fetched_at FROM confluence_pages WHERE page_id=?",
            (page_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "page_id": row[0],
            "space_key": row[1],
            "title": row[2],
            "body": row[3],
            "url": row[4],
            "ancestors": row[5],
            "stale": (time.time() - row[6]) > _STALE_SECONDS,
        }

    def list_confluence_pages(self, space_key: str = "") -> list[dict]:
        """List cached Confluence pages."""
        if space_key:
            rows = self.db.execute(
                "SELECT page_id, title, url, fetched_at FROM confluence_pages WHERE space_key=? ORDER BY title",
                (space_key,),
            ).fetchall()
        else:
            rows = self.db.execute(
                "SELECT page_id, title, url, fetched_at FROM confluence_pages ORDER BY title"
            ).fetchall()
        return [
            {
                "page_id": r[0],
                "title": r[1],
                "url": r[2],
                "stale": (time.time() - r[3]) > _STALE_SECONDS,
            }
            for r in rows
        ]

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
        self.db.execute(
            """
            INSERT INTO jira_issues (issue_key, project, summary, description, status, assignee, priority, issue_type, labels, created_at, updated_at, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(issue_key) DO UPDATE SET
                summary=excluded.summary, description=excluded.description, status=excluded.status,
                assignee=excluded.assignee, priority=excluded.priority, issue_type=excluded.issue_type,
                labels=excluded.labels, updated_at=excluded.updated_at, fetched_at=excluded.fetched_at
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
        # Update FTS
        self.db.execute("DELETE FROM jira_fts WHERE issue_key=?", (issue_key,))
        self.db.execute(
            "INSERT INTO jira_fts (summary, description, issue_key) VALUES (?, ?, ?)",
            (summary, description, issue_key),
        )
        self.db.commit()

    def search_jira(self, query: str, limit: int = 20) -> list[dict]:
        """Full-text search in cached Jira issues."""
        rows = self.db.execute(
            """
            SELECT i.issue_key, i.project, i.summary, i.status, i.priority, i.assignee, i.issue_type,
                   snippet(jira_fts, 1, '<b>', '</b>', '...', 40) as excerpt
            FROM jira_fts f
            JOIN jira_issues i ON f.issue_key = i.issue_key
            WHERE jira_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """,
            (query, limit),
        ).fetchall()
        return [
            {
                "issue_key": r[0],
                "project": r[1],
                "summary": r[2],
                "status": r[3],
                "priority": r[4],
                "assignee": r[5],
                "issue_type": r[6],
                "excerpt": r[7],
            }
            for r in rows
        ]

    def get_jira_issue(self, issue_key: str) -> Optional[dict]:
        """Get a cached Jira issue."""
        row = self.db.execute(
            "SELECT * FROM jira_issues WHERE issue_key=?", (issue_key,)
        ).fetchone()
        if not row:
            return None
        cols = [
            "issue_key",
            "project",
            "summary",
            "description",
            "status",
            "assignee",
            "priority",
            "issue_type",
            "labels",
            "created_at",
            "updated_at",
            "fetched_at",
        ]
        d = dict(zip(cols, row))
        d["stale"] = (time.time() - d["fetched_at"]) > _STALE_SECONDS
        return d

    def stats(self) -> dict:
        """Cache statistics."""
        c_count = self.db.execute("SELECT COUNT(*) FROM confluence_pages").fetchone()[0]
        j_count = self.db.execute("SELECT COUNT(*) FROM jira_issues").fetchone()[0]
        return {
            "confluence_pages": c_count,
            "jira_issues": j_count,
            "db_path": str(_DB_PATH),
        }


_cache: Optional[RLMCache] = None


def get_rlm_cache() -> RLMCache:
    """Get or create the RLM cache singleton."""
    global _cache
    if _cache is None:
        _cache = RLMCache()
    return _cache
