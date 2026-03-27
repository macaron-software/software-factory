"""Memory Manager — 4-layer memory system with FTS5 search.

Layer 1: Session (ephemeral, in conversation)
Layer 2: Pattern (shared during workflow run)
Layer 3: Project (persistent per-project knowledge)
Layer 4: Global (cross-project learnings)

Uses existing DB tables: memory_pattern, memory_project, memory_global.
"""
# Ref: feat-memory

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from ..db.migrations import get_db

logger = logging.getLogger(__name__)


def _compute_relevance(
    confidence: float, updated_at_str: str, access_count: int = 0
) -> float:
    """Relevance = confidence × recency_factor × access_boost."""
    try:
        if updated_at_str:
            updated = datetime.fromisoformat(str(updated_at_str)[:19])
            age_days = (datetime.utcnow() - updated).total_seconds() / 86400
        else:
            age_days = 0
    except Exception:
        age_days = 0

    if age_days < 7:
        recency = 1.0
    elif age_days < 30:
        recency = 0.7
    elif age_days < 90:
        recency = 0.4
    else:
        recency = 0.1

    try:
        access_num = int(access_count or 0)
    except Exception:
        access_num = 0
    access_boost = min(1.5, 1.0 + access_num * 0.05)
    return round(min(1.0, confidence * recency * access_boost), 4)


@dataclass
class MemoryEntry:
    id: int = 0
    key: str = ""
    value: str = ""
    category: str = "context"
    source: str = ""  # agent_id or "system"
    confidence: float = 0.5
    scope_id: str = ""  # session_id, project_id, or "global"
    layer: str = "project"  # session | pattern | project | global
    created_at: str = ""


_MEMORY_COMPRESS_THRESHOLD = int(__import__("os").environ.get("MEMORY_COMPRESS_THRESHOLD", "50"))
_MEMORY_COMPRESS_KEEP = 20  # Keep the N most recent after compression
_KO_DENSITY_SWITCH = int(os.environ.get("KO_DENSITY_SWITCH", "200"))
_HARD_CONSTRAINT_CATEGORIES = {
    "constraint",
    "security",
    "rbac",
    "acceptance",
    "ko-constraint",
    "ko-security",
    "ko-rbac",
    "ko-acceptance",
}


def _ensure_ko_schema(conn) -> None:
    """Create/upgrade deterministic Knowledge Object storage."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_objects (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            kind TEXT NOT NULL DEFAULT 'constraint',
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            mandatory INTEGER DEFAULT 0,
            confidence REAL DEFAULT 1.0,
            source TEXT DEFAULT 'system',
            access_count INTEGER DEFAULT 0,
            last_read_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    try:
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_ko_unique ON knowledge_objects(project_id, kind, key)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ko_project_mandatory ON knowledge_objects(project_id, mandatory)"
        )
    except Exception:
        pass


def _maybe_compress_project_memory(project_id: str) -> None:
    """If project memory exceeds threshold, LLM-summarize oldest entries into one compressed record."""
    try:
        conn = get_db()
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM memory_project WHERE project_id=?", (project_id,)
            ).fetchone()[0]
            if count <= _MEMORY_COMPRESS_THRESHOLD:
                return
            # Fetch oldest entries (exclude the most recent ones we want to keep)
            old_rows = conn.execute(
                "SELECT id, category, key, value FROM memory_project"
                f" WHERE project_id=? AND COALESCE(category,'') NOT IN ({','.join('?' for _ in _HARD_CONSTRAINT_CATEGORIES)})"
                " ORDER BY COALESCE(updated_at, created_at) ASC"
                f" LIMIT {count - _MEMORY_COMPRESS_KEEP}",
                (project_id, *_HARD_CONSTRAINT_CATEGORIES),
            ).fetchall()
            if not old_rows:
                return
            old_ids = [r["id"] for r in old_rows]
            # Build a summary text from old entries
            snippets = [f"[{r['category']}/{r['key']}] {r['value'][:200]}" for r in old_rows]
            combined_text = "\n".join(snippets)
            # LLM summarization (non-blocking, best-effort)
            try:
                from ..llm.client import LLMMessage, get_llm_client
                client = get_llm_client()
                resp = client.chat(
                    messages=[
                        LLMMessage(role="user", content=(
                            "Résume ces entrées de mémoire projet en un paragraphe dense "
                            "(max 500 chars), conserve les faits clés:\n\n" + combined_text
                        ))
                    ],
                    max_tokens=200,
                )
                summary = resp.content.strip() if resp and resp.content else combined_text[:500]
            except Exception:
                summary = combined_text[:500]
            # Delete old entries and insert compressed summary
            placeholders = ",".join("?" * len(old_ids))
            conn.execute(f"DELETE FROM memory_project WHERE id IN ({placeholders})", old_ids)
            conn.execute(
                "INSERT INTO memory_project (project_id, category, key, value, confidence, source, relevance_score)"
                " VALUES (?, 'context', '_compressed_summary', ?, 0.7, 'system', 0.7)",
                (project_id, summary),
            )
            conn.commit()
            logger.info(
                "memory: compressed %d old entries for project %s → 1 summary",
                len(old_ids), project_id,
            )
        finally:
            conn.close()
    except Exception as e:
        logger.debug("memory: compression skipped: %s", e)


class MemoryManager:
    """Unified interface for all memory layers."""

    # ── Pattern Memory (Layer 2) ────────────────────────────────

    def pattern_store(
        self,
        session_id: str,
        key: str,
        value: str,
        category: str = "context",
        author: str = "system",
    ) -> int:
        conn = get_db()
        cur = conn.execute(
            "INSERT INTO memory_pattern (session_id, key, value, type, author_agent) VALUES (?,?,?,?,?)",
            (session_id, key, value, category, author),
        )
        conn.commit()
        rid = cur.lastrowid
        conn.close()
        return rid

    def pattern_get(
        self,
        session_id: str,
        category: Optional[str] = None,
        author: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        conn = get_db()
        q = "SELECT * FROM memory_pattern WHERE session_id=?"
        params: list = [session_id]
        if category:
            q += " AND type=?"
            params.append(category)
        if author:
            q += " AND author_agent=?"
            params.append(author)
        q += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(q, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def pattern_search(
        self, session_id: str, query: str, limit: int = 20
    ) -> list[dict]:
        """Search pattern memory for a given session (LIKE fallback)."""
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM memory_pattern WHERE session_id=? AND (key LIKE ? OR value LIKE ?) ORDER BY created_at DESC LIMIT ?",
            (session_id, f"%{query}%", f"%{query}%", limit),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ── Project Memory (Layer 3) ────────────────────────────────

    def ko_store(
        self,
        project_id: str,
        key: str,
        value: str,
        kind: str = "constraint",
        mandatory: bool = False,
        source: str = "system",
        confidence: float = 1.0,
    ) -> str:
        """Store deterministic Knowledge Object (hash-addressed by project/kind/key)."""
        conn = get_db()
        _ensure_ko_schema(conn)
        existing = conn.execute(
            "SELECT id FROM knowledge_objects WHERE project_id=? AND kind=? AND key=?",
            (project_id, kind, key),
        ).fetchone()
        if existing:
            ko_id = existing["id"]
            conn.execute(
                "UPDATE knowledge_objects SET value=?, mandatory=?, confidence=?, source=?, "
                "updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (value, 1 if mandatory else 0, confidence, source, ko_id),
            )
        else:
            ko_id = uuid.uuid4().hex[:16]
            conn.execute(
                "INSERT INTO knowledge_objects "
                "(id, project_id, kind, key, value, mandatory, confidence, source) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    ko_id,
                    project_id,
                    kind,
                    key,
                    value,
                    1 if mandatory else 0,
                    confidence,
                    source,
                ),
            )
        conn.commit()
        conn.close()
        return ko_id

    def ko_list_mandatory(self, project_id: str, limit: int = 50) -> list[dict]:
        conn = get_db()
        _ensure_ko_schema(conn)
        rows = conn.execute(
            "SELECT * FROM knowledge_objects WHERE project_id=? AND mandatory=1 "
            "ORDER BY updated_at DESC LIMIT ?",
            (project_id, limit),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def ko_get(self, project_id: str, key: str, kind: str = "") -> dict | None:
        conn = get_db()
        _ensure_ko_schema(conn)
        if kind:
            row = conn.execute(
                "SELECT * FROM knowledge_objects WHERE project_id=? AND kind=? AND key=? LIMIT 1",
                (project_id, kind, key),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM knowledge_objects WHERE project_id=? AND key=? "
                "ORDER BY mandatory DESC, updated_at DESC LIMIT 1",
                (project_id, key),
            ).fetchone()
        if row:
            try:
                conn.execute(
                    "UPDATE knowledge_objects SET access_count=COALESCE(access_count,0)+1, "
                    "last_read_at=CURRENT_TIMESTAMP WHERE id=?",
                    (row["id"],),
                )
                conn.commit()
            except Exception:
                pass
        conn.close()
        return dict(row) if row else None

    def ko_search(
        self,
        project_id: str,
        query: str,
        kind: str = "",
        limit: int = 20,
        mandatory_only: bool = False,
    ) -> list[dict]:
        conn = get_db()
        _ensure_ko_schema(conn)
        where = ["project_id=?"]
        params: list = [project_id]
        if mandatory_only:
            where.append("mandatory=1")
        if kind:
            where.append("kind=?")
            params.append(kind)
        if query:
            where.append("(key LIKE ? OR value LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])
        rows = conn.execute(
            f"SELECT * FROM knowledge_objects WHERE {' AND '.join(where)} "
            "ORDER BY mandatory DESC, updated_at DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
        try:
            ids = [r["id"] for r in rows]
            if ids:
                conn.execute(
                    f"UPDATE knowledge_objects SET access_count=COALESCE(access_count,0)+1, "
                    f"last_read_at=CURRENT_TIMESTAMP WHERE id IN ({','.join('?' * len(ids))})",
                    ids,
                )
                conn.commit()
        except Exception:
            pass
        conn.close()
        return [dict(r) for r in rows]

    def project_retrieve_adaptive(
        self, project_id: str, query: str, limit: int = 12, agent_role: str = ""
    ) -> tuple[str, list[dict]]:
        """Density-adaptive retrieval: deterministic KO first, memory fallback when sparse."""
        conn = get_db()
        _ensure_ko_schema(conn)
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM memory_project WHERE project_id=?",
            (project_id,),
        ).fetchone()
        mem_count = int((row["c"] if row else 0) or 0)
        conn.close()

        mandatory = self.ko_list_mandatory(project_id, limit=8)
        ko_hits = self.ko_search(project_id, query, limit=8) if query else []

        def _to_out(src: dict, source: str) -> dict:
            if source == "ko":
                return {
                    "source": "ko",
                    "kind": src.get("kind", ""),
                    "mandatory": bool(src.get("mandatory", 0)),
                    "key": src.get("key", ""),
                    "value": src.get("value", ""),
                    "category": f"ko:{src.get('kind', '')}",
                }
            return {
                "source": "memory",
                "kind": "",
                "mandatory": False,
                "key": src.get("key", ""),
                "value": src.get("value", ""),
                "category": src.get("category", ""),
            }

        merged: list[dict] = []
        seen: set[str] = set()
        for item in [_to_out(x, "ko") for x in (mandatory + ko_hits)]:
            sig = f"{item.get('source')}::{item.get('key')}::{item.get('kind')}"
            if sig in seen:
                continue
            seen.add(sig)
            merged.append(item)

        if mem_count < _KO_DENSITY_SWITCH:
            for item in self.project_search(project_id, query, limit=max(4, limit // 2)):
                out = _to_out(item, "memory")
                sig = f"{out.get('source')}::{out.get('key')}::{out.get('kind')}"
                if sig in seen:
                    continue
                seen.add(sig)
                merged.append(out)
            mode = "hybrid"
        else:
            mode = "ko-only"

        if not merged:
            mode = "memory-only"
            merged = [
                _to_out(x, "memory")
                for x in self.project_search(project_id, query, limit=limit)
            ]

        return mode, merged[:limit]

    def project_store(
        self,
        project_id: str,
        key: str,
        value: str,
        category: str = "context",
        source: str = "system",
        confidence: float = 0.5,
        agent_role: str = "",
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        relevance = _compute_relevance(confidence, now, 0)
        conn = get_db()
        # Upsert: update if same project+category+key+agent_role exists
        existing = conn.execute(
            "SELECT id, access_count FROM memory_project WHERE project_id=? AND category=? AND key=? AND COALESCE(agent_role,'')=?",
            (project_id, category, key, agent_role),
        ).fetchone()
        if existing:
            ac = existing["access_count"] or 0
            new_rel = _compute_relevance(confidence, now, ac)
            conn.execute(
                "UPDATE memory_project SET value=?, confidence=?, source=?, relevance_score=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (value, confidence, source, new_rel, existing["id"]),
            )
            conn.commit()
            rid = existing["id"]
        else:
            cur = conn.execute(
                "INSERT INTO memory_project (project_id, category, key, value, confidence, source, agent_role, relevance_score) VALUES (?,?,?,?,?,?,?,?)",
                (
                    project_id,
                    category,
                    key,
                    value,
                    confidence,
                    source,
                    agent_role,
                    relevance,
                ),
            )
            conn.commit()
            rid = cur.lastrowid
        conn.close()
        # Compress if project memory is growing too large
        _maybe_compress_project_memory(project_id)
        return rid

    def project_get(
        self,
        project_id: str,
        category: Optional[str] = None,
        limit: int = 50,
        agent_role: str = "",
    ) -> list[dict]:
        conn = get_db()
        _cols = "id, project_id, category, key, value, confidence, source, agent_role, relevance_score, access_count, created_at, updated_at, last_read_at"
        q = f"SELECT {_cols} FROM memory_project WHERE project_id=?"
        params: list = [project_id]
        if category:
            q += " AND category=?"
            params.append(category)
        if agent_role:
            q += " AND (agent_role=? OR agent_role='' OR agent_role IS NULL)"
            params.append(agent_role)
        q += " ORDER BY COALESCE(relevance_score, confidence) DESC, updated_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(q, params).fetchall()
        # Track access
        try:
            ids = [r["id"] for r in rows]
            if ids:
                conn.execute(
                    f"UPDATE memory_project SET access_count = COALESCE(access_count,0) + 1, last_read_at=CURRENT_TIMESTAMP WHERE id IN ({','.join('?' * len(ids))})",
                    ids,
                )
                conn.commit()
        except Exception:
            pass
        conn.close()
        result = []
        for r in rows:
            row = dict(r)
            for k, v in row.items():
                if hasattr(v, "isoformat"):
                    row[k] = v.isoformat()
            result.append(row)
        return result

    def project_search(
        self, project_id: str, query: str, limit: int = 20
    ) -> list[dict]:
        """Full-text search in project memory (FTS5 or tsvector)."""
        from ..db.adapter import is_postgresql

        conn = get_db()
        try:
            if is_postgresql():
                rows = conn.execute(
                    """
                    SELECT mp.*, ts_rank(mp.search_tsv, plainto_tsquery('simple', ?)) as rank
                    FROM memory_project mp
                    WHERE mp.search_tsv @@ plainto_tsquery('simple', ?) AND mp.project_id = ?
                    ORDER BY rank DESC LIMIT ?
                """,
                    (query, query, project_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT mp.*, rank FROM memory_project mp
                    JOIN memory_project_fts fts ON mp.id = fts.rowid
                    WHERE memory_project_fts MATCH ? AND mp.project_id = ?
                    ORDER BY rank LIMIT ?
                """,
                    (query, project_id, limit),
                ).fetchall()
        except Exception:
            rows = conn.execute(
                "SELECT * FROM memory_project WHERE project_id=? AND (key LIKE ? OR value LIKE ?) ORDER BY COALESCE(relevance_score,confidence) DESC LIMIT ?",
                (project_id, f"%{query}%", f"%{query}%", limit),
            ).fetchall()
        # Track access
        try:
            ids = [r["id"] for r in rows]
            if ids:
                conn.execute(
                    f"UPDATE memory_project SET access_count = COALESCE(access_count,0) + 1, last_read_at=CURRENT_TIMESTAMP WHERE id IN ({','.join('?' * len(ids))})",
                    ids,
                )
                conn.commit()
        except Exception:
            pass
        conn.close()
        return [dict(r) for r in rows]

    def project_retrieve(self, project_id: str, key: str) -> dict | None:
        """Retrieve a single memory entry by exact key."""
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM memory_project WHERE project_id=? AND key=? LIMIT 1",
            (project_id, key),
        ).fetchone()
        if row:
            try:
                conn.execute(
                    "UPDATE memory_project SET access_count=COALESCE(access_count,0)+1, "
                    "last_read_at=CURRENT_TIMESTAMP WHERE id=?",
                    (row["id"],),
                )
                conn.commit()
            except Exception:
                pass
        conn.close()
        return dict(row) if row else None

    def project_prune(
        self,
        project_id: str,
        key: str | None = None,
        category: str | None = None,
        older_than_days: int | None = None,
    ) -> int:
        """Delete memory entries. Returns count deleted."""
        conn = get_db()
        conditions = ["project_id=?"]
        params: list = [project_id]
        if key:
            conditions.append("key=?")
            params.append(key)
        if category:
            conditions.append("category=?")
            params.append(category)
        if older_than_days:
            conditions.append(
                "updated_at < datetime('now', ? || ' days')"
            )
            params.append(f"-{older_than_days}")
        if len(conditions) < 2:
            conn.close()
            return 0  # safety: refuse to delete ALL project memory without filter
        where = " AND ".join(conditions)
        cursor = conn.execute(f"DELETE FROM memory_project WHERE {where}", params)
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted

    # ── Global Memory (Layer 4) ──────────────────────────────────

    def global_store(
        self,
        key: str,
        value: str,
        category: str = "pattern",
        project_id: str = "",
        confidence: float = 0.5,
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        conn = get_db()
        existing = conn.execute(
            "SELECT id, occurrences, projects_json, access_count FROM memory_global WHERE category=? AND key=?",
            (category, key),
        ).fetchone()
        if existing:
            projects = json.loads(existing["projects_json"] or "[]")
            if project_id and project_id not in projects:
                projects.append(project_id)
            occ = existing["occurrences"] + 1
            new_conf = min(1.0, confidence + 0.05 * occ)
            new_rel = _compute_relevance(new_conf, now, existing["access_count"] or 0)
            conn.execute(
                "UPDATE memory_global SET value=?, confidence=?, occurrences=?, projects_json=?, relevance_score=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (value, new_conf, occ, json.dumps(projects), new_rel, existing["id"]),
            )
            conn.commit()
            rid = existing["id"]
        else:
            projects = [project_id] if project_id else []
            rel = _compute_relevance(confidence, now, 0)
            cur = conn.execute(
                "INSERT INTO memory_global (category, key, value, confidence, occurrences, projects_json, relevance_score) VALUES (?,?,?,?,?,?,?)",
                (category, key, value, confidence, 1, json.dumps(projects), rel),
            )
            conn.commit()
            rid = cur.lastrowid
        conn.close()
        return rid

    def global_get(self, category: Optional[str] = None, limit: int = 50) -> list[dict]:
        conn = get_db()
        if category:
            rows = conn.execute(
                "SELECT * FROM memory_global WHERE category=? ORDER BY COALESCE(relevance_score,confidence) DESC, updated_at DESC LIMIT ?",
                (category, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM memory_global ORDER BY COALESCE(relevance_score,confidence) DESC, updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def global_search(self, query: str, limit: int = 20) -> list[dict]:
        from ..db.adapter import is_postgresql

        conn = get_db()
        try:
            if is_postgresql():
                rows = conn.execute(
                    """
                    SELECT mg.*, ts_rank(mg.search_tsv, plainto_tsquery('simple', ?)) as rank
                    FROM memory_global mg
                    WHERE mg.search_tsv @@ plainto_tsquery('simple', ?)
                    ORDER BY rank DESC LIMIT ?
                """,
                    (query, query, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT mg.*, rank FROM memory_global mg
                    JOIN memory_global_fts fts ON mg.id = fts.rowid
                    WHERE memory_global_fts MATCH ?
                    ORDER BY rank LIMIT ?
                """,
                    (query, limit),
                ).fetchall()
        except Exception:
            rows = conn.execute(
                "SELECT * FROM memory_global WHERE key LIKE ? OR value LIKE ? ORDER BY COALESCE(relevance_score,confidence) DESC LIMIT ?",
                (f"%{query}%", f"%{query}%", limit),
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ── Vector Search (semantic, embedding-based) ──────────────────

    async def semantic_search(
        self, scope_id: str, query: str, limit: int = 10
    ) -> list[dict]:
        """Semantic search using vector embeddings. Falls back to FTS5."""
        try:
            from .vectors import get_vector_store

            vs = get_vector_store()
            results = await vs.search(scope_id, query, limit=limit)
            if results:
                return results
        except Exception:
            pass
        # Fallback to FTS5
        return self.project_search(scope_id, query, limit=limit)

    async def store_with_embedding(
        self, scope_id: str, key: str, value: str, category: str = "context"
    ) -> int:
        """Store in both project memory (FTS5) and vector store (embeddings)."""
        # Store in project memory (FTS5)
        rid = self.project_store(scope_id, key, value, category=category)
        # Also store in vector store for semantic search
        try:
            from .vectors import get_vector_store

            vs = get_vector_store()
            await vs.store(scope_id, key, value, category=category)
        except Exception as e:
            logger.debug("Vector store failed: %s", e)
        return rid

    # ── Stats ────────────────────────────────────────────────────

    def stats(self) -> dict:
        conn = get_db()
        result = {}
        for table, label in [
            ("memory_pattern", "pattern"),
            ("memory_project", "project"),
            ("memory_global", "global"),
        ]:
            try:
                row = conn.execute(f"SELECT COUNT(*) as c FROM {table}").fetchone()
                result[f"{label}_count"] = row["c"]
            except Exception:
                result[f"{label}_count"] = 0
        # Session archives count (used by template)
        try:
            row = conn.execute("SELECT COUNT(*) as c FROM sessions").fetchone()
            result["session_count"] = row["c"]
        except Exception:
            result["session_count"] = 0
        # Knowledge health stats
        try:
            r = conn.execute(
                "SELECT AVG(COALESCE(relevance_score, confidence)) as avg_rel, "
                "SUM(CASE WHEN COALESCE(relevance_score, confidence) < 0.15 THEN 1 ELSE 0 END) as stale_count "
                "FROM memory_project"
            ).fetchone()
            result["project_avg_relevance"] = round(r["avg_rel"] or 0, 3)
            result["project_stale_count"] = r["stale_count"] or 0
        except Exception:
            result["project_avg_relevance"] = 0
            result["project_stale_count"] = 0
        try:
            r = conn.execute(
                "SELECT AVG(COALESCE(relevance_score, confidence)) as avg_rel FROM memory_global"
            ).fetchone()
            result["global_avg_relevance"] = round(r["avg_rel"] or 0, 3)
        except Exception:
            result["global_avg_relevance"] = 0
        conn.close()
        return result


# Singleton
_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    global _manager
    if _manager is None:
        _manager = MemoryManager()
    return _manager
