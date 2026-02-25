"""LLM response cache — deterministic deduplication of identical prompts.

Caches LLM responses keyed by hash(model + messages + temperature).
Saves tokens and latency on repeated/retried prompts.

Env vars:
  LLM_CACHE_ENABLED=true   (default: true)
  LLM_CACHE_TTL=86400      (default: 24h, 0 = infinite)
  LLM_CACHE_MAX_SIZE=10000  (max cached entries)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "platform.db"
_ENABLED = os.environ.get("LLM_CACHE_ENABLED", "true").lower() in ("true", "1", "yes")
_TTL = int(os.environ.get("LLM_CACHE_TTL", "86400"))
_MAX_SIZE = int(os.environ.get("LLM_CACHE_MAX_SIZE", "10000"))


def _cache_key(
    model: str,
    messages: list[dict],
    temperature: float,
    tools: list[dict] | None = None,
) -> str:
    """Deterministic hash of the request parameters."""
    payload = json.dumps(
        {"model": model, "messages": messages, "temperature": temperature, "tools": tools or []},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _ensure_table(db: sqlite3.Connection) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS llm_cache (
            cache_key   TEXT PRIMARY KEY,
            model       TEXT NOT NULL,
            temperature REAL NOT NULL,
            response    TEXT NOT NULL,
            tokens_in   INTEGER DEFAULT 0,
            tokens_out  INTEGER DEFAULT 0,
            created_at  REAL NOT NULL,
            hit_count   INTEGER DEFAULT 0
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_llm_cache_created ON llm_cache(created_at)")


class LLMCache:
    """SQLite-backed LLM response cache."""

    def __init__(self, db_path: Path | str | None = None):
        self._db_path = Path(db_path) if db_path else _DB_PATH
        self._stats = {"hits": 0, "misses": 0, "evictions": 0, "tokens_saved": 0}
        self._initialized = False

    def _db(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self._db_path))
        db.row_factory = sqlite3.Row
        if not self._initialized:
            _ensure_table(db)
            self._initialized = True
        return db

    def get(
        self,
        model: str,
        messages: list[dict],
        temperature: float,
        tools: list[dict] | None = None,
    ) -> dict | None:
        """Lookup cached response. Returns dict with content/tokens or None."""
        if not _ENABLED:
            return None

        key = _cache_key(model, messages, temperature, tools)
        db = self._db()
        try:
            row = db.execute("SELECT * FROM llm_cache WHERE cache_key = ?", (key,)).fetchone()
            if row is None:
                self._stats["misses"] += 1
                return None

            # Check TTL
            if _TTL > 0 and (time.time() - row["created_at"]) > _TTL:
                db.execute("DELETE FROM llm_cache WHERE cache_key = ?", (key,))
                db.commit()
                self._stats["misses"] += 1
                return None

            # Cache hit
            db.execute(
                "UPDATE llm_cache SET hit_count = hit_count + 1 WHERE cache_key = ?", (key,)
            )
            db.commit()
            self._stats["hits"] += 1
            self._stats["tokens_saved"] += row["tokens_in"] + row["tokens_out"]

            return {
                "content": row["response"],
                "tokens_in": row["tokens_in"],
                "tokens_out": row["tokens_out"],
                "cached": True,
            }
        finally:
            db.close()

    def put(
        self,
        model: str,
        messages: list[dict],
        temperature: float,
        content: str,
        tokens_in: int = 0,
        tokens_out: int = 0,
        tools: list[dict] | None = None,
    ) -> None:
        """Store a response in cache."""
        if not _ENABLED:
            return

        key = _cache_key(model, messages, temperature, tools)
        db = self._db()
        try:
            # Evict oldest if at capacity
            count = db.execute("SELECT COUNT(*) FROM llm_cache").fetchone()[0]
            if count >= _MAX_SIZE:
                evict_n = max(1, _MAX_SIZE // 10)
                db.execute(
                    "DELETE FROM llm_cache WHERE cache_key IN "
                    "(SELECT cache_key FROM llm_cache ORDER BY created_at ASC LIMIT ?)",
                    (evict_n,),
                )
                self._stats["evictions"] += evict_n

            db.execute(
                """INSERT OR REPLACE INTO llm_cache
                   (cache_key, model, temperature, response, tokens_in, tokens_out, created_at, hit_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0)""",
                (key, model, temperature, content, tokens_in, tokens_out, time.time()),
            )
            db.commit()
        finally:
            db.close()

    def invalidate(self, model: str | None = None) -> int:
        """Invalidate cache entries. If model specified, only that model."""
        db = self._db()
        try:
            if model:
                cur = db.execute("DELETE FROM llm_cache WHERE model = ?", (model,))
            else:
                cur = db.execute("DELETE FROM llm_cache")
            db.commit()
            return cur.rowcount
        finally:
            db.close()

    def stats(self) -> dict:
        """Return cache statistics."""
        db = self._db()
        try:
            row = db.execute(
                "SELECT COUNT(*) as entries, SUM(tokens_in + tokens_out) as total_tokens, "
                "SUM(hit_count) as total_hits FROM llm_cache"
            ).fetchone()
            return {
                **self._stats,
                "entries": row["entries"] or 0,
                "total_cached_tokens": row["total_tokens"] or 0,
                "total_db_hits": row["total_hits"] or 0,
                "enabled": _ENABLED,
                "ttl": _TTL,
                "max_size": _MAX_SIZE,
            }
        finally:
            db.close()


# Singleton instance
_cache = LLMCache()


def get_cache() -> LLMCache:
    """Return the global LLM cache instance."""
    return _cache
