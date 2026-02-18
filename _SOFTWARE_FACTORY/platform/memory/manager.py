"""Memory Manager — 4-layer memory system with FTS5 search.

Layer 1: Session (ephemeral, in conversation)
Layer 2: Pattern (shared during workflow run)
Layer 3: Project (persistent per-project knowledge)
Layer 4: Global (cross-project learnings)

Uses existing DB tables: memory_pattern, memory_project, memory_global.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Optional

from ..db.migrations import get_db

logger = logging.getLogger(__name__)


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


class MemoryManager:
    """Unified interface for all memory layers."""

    # ── Pattern Memory (Layer 2) ────────────────────────────────

    def pattern_store(self, session_id: str, key: str, value: str,
                      category: str = "context", author: str = "system") -> int:
        conn = get_db()
        cur = conn.execute(
            "INSERT INTO memory_pattern (session_id, key, value, type, author_agent) VALUES (?,?,?,?,?)",
            (session_id, key, value, category, author))
        conn.commit()
        rid = cur.lastrowid
        conn.close()
        return rid

    def pattern_get(self, session_id: str, category: Optional[str] = None,
                    author: Optional[str] = None, limit: int = 50) -> list[dict]:
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

    # ── Project Memory (Layer 3) ────────────────────────────────

    def project_store(self, project_id: str, key: str, value: str,
                      category: str = "context", source: str = "system",
                      confidence: float = 0.5) -> int:
        conn = get_db()
        # Upsert: update if same project+category+key exists
        existing = conn.execute(
            "SELECT id FROM memory_project WHERE project_id=? AND category=? AND key=?",
            (project_id, category, key)).fetchone()
        if existing:
            conn.execute(
                "UPDATE memory_project SET value=?, confidence=?, source=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (value, confidence, source, existing["id"]))
            conn.commit()
            rid = existing["id"]
        else:
            cur = conn.execute(
                "INSERT INTO memory_project (project_id, category, key, value, confidence, source) VALUES (?,?,?,?,?,?)",
                (project_id, category, key, value, confidence, source))
            conn.commit()
            rid = cur.lastrowid
        conn.close()
        return rid

    def project_get(self, project_id: str, category: Optional[str] = None,
                    limit: int = 50) -> list[dict]:
        conn = get_db()
        q = "SELECT * FROM memory_project WHERE project_id=?"
        params: list = [project_id]
        if category:
            q += " AND category=?"
            params.append(category)
        q += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(q, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def project_search(self, project_id: str, query: str, limit: int = 20) -> list[dict]:
        """FTS5 search in project memory."""
        conn = get_db()
        try:
            rows = conn.execute("""
                SELECT mp.*, rank FROM memory_project mp
                JOIN memory_project_fts fts ON mp.id = fts.rowid
                WHERE memory_project_fts MATCH ? AND mp.project_id = ?
                ORDER BY rank LIMIT ?
            """, (query, project_id, limit)).fetchall()
        except Exception:
            rows = conn.execute(
                "SELECT * FROM memory_project WHERE project_id=? AND (key LIKE ? OR value LIKE ?) LIMIT ?",
                (project_id, f"%{query}%", f"%{query}%", limit)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ── Global Memory (Layer 4) ──────────────────────────────────

    def global_store(self, key: str, value: str, category: str = "pattern",
                     project_id: str = "", confidence: float = 0.5) -> int:
        conn = get_db()
        existing = conn.execute(
            "SELECT id, occurrences, projects_json FROM memory_global WHERE category=? AND key=?",
            (category, key)).fetchone()
        if existing:
            projects = json.loads(existing["projects_json"] or "[]")
            if project_id and project_id not in projects:
                projects.append(project_id)
            occ = existing["occurrences"] + 1
            new_conf = min(1.0, confidence + 0.05 * occ)
            conn.execute(
                "UPDATE memory_global SET value=?, confidence=?, occurrences=?, projects_json=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (value, new_conf, occ, json.dumps(projects), existing["id"]))
            conn.commit()
            rid = existing["id"]
        else:
            projects = [project_id] if project_id else []
            cur = conn.execute(
                "INSERT INTO memory_global (category, key, value, confidence, occurrences, projects_json) VALUES (?,?,?,?,?,?)",
                (category, key, value, confidence, 1, json.dumps(projects)))
            conn.commit()
            rid = cur.lastrowid
        conn.close()
        return rid

    def global_get(self, category: Optional[str] = None, limit: int = 50) -> list[dict]:
        conn = get_db()
        if category:
            rows = conn.execute(
                "SELECT * FROM memory_global WHERE category=? ORDER BY updated_at DESC LIMIT ?",
                (category, limit)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM memory_global ORDER BY updated_at DESC LIMIT ?",
                (limit,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def global_search(self, query: str, limit: int = 20) -> list[dict]:
        conn = get_db()
        try:
            rows = conn.execute("""
                SELECT mg.*, rank FROM memory_global mg
                JOIN memory_global_fts fts ON mg.id = fts.rowid
                WHERE memory_global_fts MATCH ?
                ORDER BY rank LIMIT ?
            """, (query, limit)).fetchall()
        except Exception:
            rows = conn.execute(
                "SELECT * FROM memory_global WHERE key LIKE ? OR value LIKE ? LIMIT ?",
                (f"%{query}%", f"%{query}%", limit)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ── Stats ────────────────────────────────────────────────────

    def stats(self) -> dict:
        conn = get_db()
        result = {}
        for table, label in [("memory_pattern", "pattern"), ("memory_project", "project"), ("memory_global", "global")]:
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
        conn.close()
        return result


# Singleton
_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    global _manager
    if _manager is None:
        _manager = MemoryManager()
    return _manager
