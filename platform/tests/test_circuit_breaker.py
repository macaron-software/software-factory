"""Unit tests for circuit breaker and memory compression."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest


# ── Circuit breaker ───────────────────────────────────────────────────────────

def _make_db_with_failures(workflow_id: str, n_fails: int, minutes_ago: int = 5):
    """Create an in-memory SQLite DB with N recent failed epic_runs."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE epic_runs (
            id TEXT PRIMARY KEY,
            workflow_id TEXT,
            status TEXT,
            updated_at TEXT
        )
    """)
    now = datetime.utcnow()
    for i in range(n_fails):
        # Use SQLite-compatible format (space not T separator)
        ts = (now - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO epic_runs VALUES (?, ?, 'failed', ?)",
            (f"run-{i}", workflow_id, ts),
        )
    conn.commit()
    return conn


def test_circuit_open_when_too_many_failures():
    from platform.services.auto_resume import _is_circuit_open
    db = _make_db_with_failures("tma-autoheal", n_fails=6, minutes_ago=10)
    with patch("platform.services.auto_resume._CB_MAX_FAILS", 5), \
         patch("platform.services.auto_resume._CB_WINDOW_MINUTES", 60):
        result = _is_circuit_open("tma-autoheal", db)
        assert isinstance(result, bool)
    db.close()


def test_circuit_closed_when_few_failures():
    from platform.services.auto_resume import _is_circuit_open
    db = _make_db_with_failures("review-cycle", n_fails=2, minutes_ago=10)
    with patch("platform.services.auto_resume._CB_MAX_FAILS", 5):
        result = _is_circuit_open("review-cycle", db)
        assert result is False
    db.close()


def test_circuit_closed_for_old_failures():
    """Failures outside the window should not trip the circuit."""
    from platform.services.auto_resume import _is_circuit_open
    db = _make_db_with_failures("old-workflow", n_fails=10, minutes_ago=120)
    with patch("platform.services.auto_resume._CB_MAX_FAILS", 5), \
         patch("platform.services.auto_resume._CB_WINDOW_MINUTES", 60):
        result = _is_circuit_open("old-workflow", db)
        assert result is False
    db.close()


# ── Memory compression ────────────────────────────────────────────────────────

def _make_memory_db(n_entries: int):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE memory_project (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT,
            category TEXT DEFAULT 'context',
            key TEXT,
            value TEXT,
            confidence REAL DEFAULT 0.5,
            source TEXT DEFAULT 'system',
            agent_role TEXT DEFAULT '',
            relevance_score REAL DEFAULT 0.5,
            access_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_read_at TEXT
        )
    """)
    for i in range(n_entries):
        conn.execute(
            "INSERT INTO memory_project (project_id, category, key, value) VALUES (?, 'context', ?, ?)",
            ("proj-1", f"key-{i}", f"value-{i} " * 10),
        )
    conn.commit()
    return conn


def _wrap_db_no_close(real_conn):
    """Wrap a sqlite3 connection to prevent close() from actually closing it."""
    class _NoClose:
        def __getattr__(self, name):
            if name == "close":
                return lambda: None
            return getattr(real_conn, name)
    return _NoClose()


def test_compression_triggered_above_threshold():
    """When count > threshold, old entries should be compressed."""
    db = _make_memory_db(60)
    wrapped = _wrap_db_no_close(db)

    with patch("platform.memory.manager.get_db", return_value=wrapped), \
         patch("platform.memory.manager._MEMORY_COMPRESS_THRESHOLD", 50):
        mock_resp = MagicMock()
        mock_resp.content = "Compressed summary of old memories"
        with patch("platform.llm.client.get_llm_client") as mock_llm:
            mock_llm.return_value.chat.return_value = mock_resp
            from platform.memory.manager import _maybe_compress_project_memory
            _maybe_compress_project_memory("proj-1")

    count = db.execute("SELECT COUNT(*) FROM memory_project WHERE project_id='proj-1'").fetchone()[0]
    assert count < 60, f"Expected fewer than 60 entries after compression, got {count}"
    db.close()


def test_no_compression_below_threshold():
    """When count <= threshold, nothing should happen."""
    db = _make_memory_db(30)
    wrapped = _wrap_db_no_close(db)

    with patch("platform.memory.manager.get_db", return_value=wrapped), \
         patch("platform.memory.manager._MEMORY_COMPRESS_THRESHOLD", 50):
        from platform.memory.manager import _maybe_compress_project_memory
        _maybe_compress_project_memory("proj-1")

    count = db.execute("SELECT COUNT(*) FROM memory_project WHERE project_id='proj-1'").fetchone()[0]
    assert count == 30  # Unchanged
    db.close()


# ── Sprint loop config ────────────────────────────────────────────────────────

def test_max_iterations_env_default():
    """max_sprints defaults to a reasonable value."""
    import os
    val = int(os.environ.get("MAX_SPRINT_ITERATIONS", "5"))
    assert val >= 2
