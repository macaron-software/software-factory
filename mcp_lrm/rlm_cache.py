"""
RLM Cache — PostgreSQL cache for Confluence/Jira content.
Falls back to SQLite if DATABASE_URL is not set or psycopg unavailable.
Uses pg tsvector/GIN for full-text search.
"""

import os
import time
from pathlib import Path
from typing import Optional

_STALE_SECONDS = 3600  # 1 hour

# ── Backend detection ──────────────────────────────────────────────────────────

def _load_env() -> str:
    """Load DATABASE_URL from env or .env file next to this package."""
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        for env_file in [
            Path(__file__).resolve().parents[1] / ".env",
            Path(__file__).resolve().parents[2] / ".env",
        ]:
            if env_file.exists():
                for line in env_file.read_text().splitlines():
                    line = line.strip()
                    if line.startswith("DATABASE_URL=") and not line.startswith("#"):
                        url = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
            if url:
                break
    return url


_PG_URL = _load_env()
_USE_PG = bool(_PG_URL and _PG_URL.startswith("postgresql"))

# SQLite fallback path
_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "rlm_cache.db"


# ── PostgreSQL helpers ─────────────────────────────────────────────────────────

def _pg_conn():
    import psycopg
    return psycopg.connect(_PG_URL)


def _pg_init(conn) -> None:
    """Create tables and GIN indexes in PG if they don't exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rlm_confluence_pages (
                page_id     TEXT PRIMARY KEY,
                space_key   TEXT NOT NULL DEFAULT '',
                title       TEXT NOT NULL DEFAULT '',
                body        TEXT NOT NULL DEFAULT '',
                url         TEXT DEFAULT '',
                ancestors   TEXT DEFAULT '',
                updated_at  DOUBLE PRECISION NOT NULL DEFAULT 0,
                fetched_at  DOUBLE PRECISION NOT NULL DEFAULT 0,
                fts         TSVECTOR GENERATED ALWAYS AS (
                    to_tsvector('simple', coalesce(title,'') || ' ' || coalesce(body,''))
                ) STORED
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS rlm_confluence_fts_idx
            ON rlm_confluence_pages USING GIN(fts)
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rlm_jira_issues (
                issue_key   TEXT PRIMARY KEY,
                project     TEXT NOT NULL DEFAULT '',
                summary     TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                status      TEXT DEFAULT '',
                assignee    TEXT DEFAULT '',
                priority    TEXT DEFAULT '',
                issue_type  TEXT DEFAULT '',
                labels      TEXT DEFAULT '',
                created_at  TEXT DEFAULT '',
                updated_at  DOUBLE PRECISION NOT NULL DEFAULT 0,
                fetched_at  DOUBLE PRECISION NOT NULL DEFAULT 0,
                fts         TSVECTOR GENERATED ALWAYS AS (
                    to_tsvector('simple', coalesce(summary,'') || ' ' || coalesce(description,''))
                ) STORED
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS rlm_jira_fts_idx
            ON rlm_jira_issues USING GIN(fts)
        """)
    conn.commit()


# ── SQLite fallback ────────────────────────────────────────────────────────────

def _sqlite_conn():
    import sqlite3
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(_DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    db.execute("""
        CREATE TABLE IF NOT EXISTS confluence_pages (
            page_id TEXT PRIMARY KEY, space_key TEXT NOT NULL,
            title TEXT NOT NULL, body TEXT NOT NULL DEFAULT '',
            url TEXT DEFAULT '', ancestors TEXT DEFAULT '',
            updated_at REAL NOT NULL, fetched_at REAL NOT NULL
        )
    """)
    try:
        db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS confluence_fts USING fts5(title, body, page_id UNINDEXED)")
    except Exception:
        pass
    db.execute("""
        CREATE TABLE IF NOT EXISTS jira_issues (
            issue_key TEXT PRIMARY KEY, project TEXT NOT NULL,
            summary TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
            status TEXT DEFAULT '', assignee TEXT DEFAULT '',
            priority TEXT DEFAULT '', issue_type TEXT DEFAULT '',
            labels TEXT DEFAULT '', created_at TEXT DEFAULT '',
            updated_at REAL NOT NULL, fetched_at REAL NOT NULL
        )
    """)
    try:
        db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS jira_fts USING fts5(summary, description, issue_key UNINDEXED)")
    except Exception:
        pass
    db.commit()
    return db


# ── Cache class ────────────────────────────────────────────────────────────────

class RLMCache:
    """Cache manager for Confluence/Jira content — PostgreSQL or SQLite."""

    def __init__(self):
        if _USE_PG:
            try:
                self._pg = _pg_conn()
                _pg_init(self._pg)
                self._backend = "pg"
            except Exception as e:
                import warnings
                warnings.warn(f"RLMCache: PG unavailable ({e}), falling back to SQLite")
                self._pg = None
                self._backend = "sqlite"
                self.db = _sqlite_conn()
        else:
            self._pg = None
            self._backend = "sqlite"
            self.db = _sqlite_conn()

    # ── Confluence ──────────────────────────────────────────────────────────────

    def upsert_confluence_page(
        self,
        page_id: str,
        space_key: str,
        title: str,
        body: str,
        url: str = "",
        ancestors: str = "",
    ):
        now = time.time()
        if self._backend == "pg":
            with self._pg.cursor() as cur:
                cur.execute("""
                    INSERT INTO rlm_confluence_pages
                        (page_id, space_key, title, body, url, ancestors, updated_at, fetched_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT(page_id) DO UPDATE SET
                        title=EXCLUDED.title, body=EXCLUDED.body, url=EXCLUDED.url,
                        ancestors=EXCLUDED.ancestors,
                        updated_at=EXCLUDED.updated_at, fetched_at=EXCLUDED.fetched_at
                """, (page_id, space_key, title, body, url, ancestors, now, now))
            self._pg.commit()
        else:
            self.db.execute("""
                INSERT INTO confluence_pages (page_id,space_key,title,body,url,ancestors,updated_at,fetched_at)
                VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(page_id) DO UPDATE SET
                    title=excluded.title, body=excluded.body, url=excluded.url,
                    ancestors=excluded.ancestors, updated_at=excluded.updated_at, fetched_at=excluded.fetched_at
            """, (page_id, space_key, title, body, url, ancestors, now, now))
            self.db.execute("DELETE FROM confluence_fts WHERE page_id=?", (page_id,))
            self.db.execute("INSERT INTO confluence_fts (title, body, page_id) VALUES (?,?,?)", (title, body, page_id))
            self.db.commit()

    def search_confluence(self, query: str, limit: int = 10) -> list[dict]:
        clean = self._sanitize_query(query)
        if not clean:
            return []
        if self._backend == "pg":
            try:
                with self._pg.cursor() as cur:
                    cur.execute("""
                        SELECT page_id, space_key, title, url, ancestors,
                               ts_headline('simple', body, plainto_tsquery('simple',%s),
                                           'StartSel=<b>,StopSel=</b>,MaxWords=30,MinWords=10') AS excerpt
                        FROM rlm_confluence_pages
                        WHERE fts @@ plainto_tsquery('simple', %s)
                        ORDER BY ts_rank(fts, plainto_tsquery('simple', %s)) DESC
                        LIMIT %s
                    """, (clean, clean, clean, limit))
                    rows = cur.fetchall()
            except Exception:
                rows = []
            return [{"page_id": r[0], "space_key": r[1], "title": r[2],
                     "url": r[3], "ancestors": r[4], "excerpt": r[5] or ""} for r in rows]
        else:
            try:
                rows = self.db.execute("""
                    SELECT p.page_id, p.space_key, p.title, p.url, p.ancestors,
                           snippet(confluence_fts,1,'<b>','</b>','...',40) as excerpt
                    FROM confluence_fts f JOIN confluence_pages p ON f.page_id=p.page_id
                    WHERE confluence_fts MATCH ? ORDER BY rank LIMIT ?
                """, (clean, limit)).fetchall()
            except Exception:
                rows = []
            return [{"page_id": r[0], "space_key": r[1], "title": r[2],
                     "url": r[3], "ancestors": r[4], "excerpt": r[5] or ""} for r in rows]

    def get_confluence_page(self, page_id: str) -> Optional[dict]:
        if self._backend == "pg":
            with self._pg.cursor() as cur:
                cur.execute("SELECT page_id,space_key,title,body,url,ancestors,fetched_at FROM rlm_confluence_pages WHERE page_id=%s", (page_id,))
                row = cur.fetchone()
        else:
            row = self.db.execute("SELECT page_id,space_key,title,body,url,ancestors,fetched_at FROM confluence_pages WHERE page_id=?", (page_id,)).fetchone()
        if not row:
            return None
        return {"page_id": row[0], "space_key": row[1], "title": row[2],
                "body": row[3], "url": row[4], "ancestors": row[5],
                "stale": (time.time() - row[6]) > _STALE_SECONDS}

    def list_confluence_pages(self, space_key: str = "") -> list[dict]:
        if self._backend == "pg":
            with self._pg.cursor() as cur:
                if space_key:
                    cur.execute("SELECT page_id,title,url,fetched_at FROM rlm_confluence_pages WHERE space_key=%s ORDER BY title", (space_key,))
                else:
                    cur.execute("SELECT page_id,title,url,fetched_at FROM rlm_confluence_pages ORDER BY title")
                rows = cur.fetchall()
        else:
            if space_key:
                rows = self.db.execute("SELECT page_id,title,url,fetched_at FROM confluence_pages WHERE space_key=? ORDER BY title", (space_key,)).fetchall()
            else:
                rows = self.db.execute("SELECT page_id,title,url,fetched_at FROM confluence_pages ORDER BY title").fetchall()
        return [{"page_id": r[0], "title": r[1], "url": r[2], "stale": (time.time()-r[3])>_STALE_SECONDS} for r in rows]

    # ── Jira ────────────────────────────────────────────────────────────────────

    def upsert_jira_issue(self, issue_key, project, summary, description="",
                          status="", assignee="", priority="", issue_type="",
                          labels="", created_at=""):
        now = time.time()
        if self._backend == "pg":
            with self._pg.cursor() as cur:
                cur.execute("""
                    INSERT INTO rlm_jira_issues
                        (issue_key,project,summary,description,status,assignee,priority,issue_type,labels,created_at,updated_at,fetched_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT(issue_key) DO UPDATE SET
                        summary=EXCLUDED.summary, description=EXCLUDED.description,
                        status=EXCLUDED.status, assignee=EXCLUDED.assignee,
                        priority=EXCLUDED.priority, issue_type=EXCLUDED.issue_type,
                        labels=EXCLUDED.labels, updated_at=EXCLUDED.updated_at,
                        fetched_at=EXCLUDED.fetched_at
                """, (issue_key, project, summary, description, status, assignee,
                      priority, issue_type, labels, created_at, now, now))
            self._pg.commit()
        else:
            self.db.execute("""
                INSERT INTO jira_issues (issue_key,project,summary,description,status,assignee,priority,issue_type,labels,created_at,updated_at,fetched_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(issue_key) DO UPDATE SET
                    summary=excluded.summary, description=excluded.description, status=excluded.status,
                    assignee=excluded.assignee, priority=excluded.priority, issue_type=excluded.issue_type,
                    labels=excluded.labels, updated_at=excluded.updated_at, fetched_at=excluded.fetched_at
            """, (issue_key, project, summary, description, status, assignee,
                  priority, issue_type, labels, created_at, now, now))
            self.db.execute("DELETE FROM jira_fts WHERE issue_key=?", (issue_key,))
            self.db.execute("INSERT INTO jira_fts (summary,description,issue_key) VALUES (?,?,?)", (summary, description, issue_key))
            self.db.commit()

    @staticmethod
    def _sanitize_query(query: str) -> str:
        """Strip JQL operators so the query is safe for FTS (FTS5 MATCH or plainto_tsquery)."""
        import re as _re
        q = _re.sub(r'\b(project|status|assignee|priority|issuetype|labels)\s*[=!<>]+\s*', ' ', query, flags=_re.IGNORECASE)
        q = _re.sub(r'\b(AND|OR|NOT|ORDER\s+BY|updated\s+DESC|created\s+DESC)\b', ' ', q, flags=_re.IGNORECASE)
        q = _re.sub(r'["\'\(\)\[\]{}=<>!,;:]', ' ', q)
        return ' '.join(q.split()).strip()

    def search_jira(self, query: str, limit: int = 20) -> list[dict]:
        clean = self._sanitize_query(query)
        if not clean:
            return []
        if self._backend == "pg":
            try:
                with self._pg.cursor() as cur:
                    cur.execute("""
                        SELECT issue_key, project, summary, status, priority, assignee, issue_type,
                               ts_headline('simple', summary || ' ' || description,
                                           plainto_tsquery('simple',%s),
                                           'StartSel=<b>,StopSel=</b>,MaxWords=20,MinWords=5') AS excerpt
                        FROM rlm_jira_issues
                        WHERE fts @@ plainto_tsquery('simple', %s)
                        ORDER BY ts_rank(fts, plainto_tsquery('simple', %s)) DESC
                        LIMIT %s
                    """, (clean, clean, clean, limit))
                    rows = cur.fetchall()
            except Exception:
                rows = []
            return [{"issue_key": r[0], "project": r[1], "summary": r[2],
                     "status": r[3], "priority": r[4], "assignee": r[5],
                     "issue_type": r[6], "excerpt": r[7] or ""} for r in rows]
        else:
            try:
                rows = self.db.execute("""
                    SELECT i.issue_key,i.project,i.summary,i.status,i.priority,i.assignee,i.issue_type,
                           snippet(jira_fts,1,'<b>','</b>','...',40) as excerpt
                    FROM jira_fts f JOIN jira_issues i ON f.issue_key=i.issue_key
                    WHERE jira_fts MATCH ? ORDER BY rank LIMIT ?
                """, (clean, limit)).fetchall()
            except Exception:
                rows = []
            return [{"issue_key": r[0], "project": r[1], "summary": r[2],
                     "status": r[3], "priority": r[4], "assignee": r[5],
                     "issue_type": r[6], "excerpt": r[7] or ""} for r in rows]

    def get_jira_issue(self, issue_key: str) -> Optional[dict]:
        if self._backend == "pg":
            with self._pg.cursor() as cur:
                cur.execute("SELECT issue_key,project,summary,description,status,assignee,priority,issue_type,labels,created_at,updated_at,fetched_at FROM rlm_jira_issues WHERE issue_key=%s", (issue_key,))
                row = cur.fetchone()
        else:
            row = self.db.execute("SELECT * FROM jira_issues WHERE issue_key=?", (issue_key,)).fetchone()
        if not row:
            return None
        cols = ["issue_key","project","summary","description","status","assignee","priority","issue_type","labels","created_at","updated_at","fetched_at"]
        d = dict(zip(cols, row))
        d["stale"] = (time.time() - d["fetched_at"]) > _STALE_SECONDS
        return d

    def stats(self) -> dict:
        if self._backend == "pg":
            with self._pg.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM rlm_confluence_pages")
                c = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM rlm_jira_issues")
                j = cur.fetchone()[0]
        else:
            c = self.db.execute("SELECT COUNT(*) FROM confluence_pages").fetchone()[0]
            j = self.db.execute("SELECT COUNT(*) FROM jira_issues").fetchone()[0]
        return {"confluence_pages": c, "jira_issues": j,
                "backend": self._backend,
                "db": _PG_URL.split("@")[-1] if self._backend == "pg" else str(_DB_PATH)}


_cache: Optional[RLMCache] = None


def get_rlm_cache() -> RLMCache:
    """Get or create the RLM cache singleton."""
    global _cache
    if _cache is None:
        _cache = RLMCache()
    return _cache
