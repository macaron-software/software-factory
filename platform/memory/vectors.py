"""Vector Memory — embedding-based semantic search for memory layers.

Uses OpenAI-compatible embedding endpoint (Azure, etc.) to generate
embeddings. Stores them in SQLite as JSON arrays. Computes cosine
similarity in Python/numpy for search.

Falls back to FTS5 keyword search if no embedding provider is available.

Usage:
    from platform.memory.vectors import get_vector_store
    vs = get_vector_store()
    await vs.store("project-1", "architecture", "Uses microservices with gRPC")
    results = await vs.search("project-1", "what communication protocol?", limit=5)
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Optional

import numpy as np

from ..db.migrations import get_db

logger = logging.getLogger(__name__)

# Embedding config — uses Azure OpenAI text-embedding-3-small
# NOTE: castudioia* endpoints are VNet-only (unusable from Docker) — use ascii-ui-openai
_EMBEDDING_ENDPOINT = os.environ.get(
    "EMBEDDING_ENDPOINT",
    os.environ.get("AZURE_OPENAI_ENDPOINT", "https://ascii-ui-openai.openai.azure.com").rstrip("/")
    + "/openai/deployments/text-embedding-3-small/embeddings?api-version=2024-10-21"
)
_EMBEDDING_KEY_ENV = os.environ.get("EMBEDDING_KEY_ENV", "AZURE_OPENAI_API_KEY")
_EMBEDDING_DIM = 1536  # text-embedding-3-small dimension


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


class VectorStore:
    """Embedding-based semantic search backed by SQLite."""

    def __init__(self):
        self._ensure_table()
        self._http = None

    def _ensure_table(self):
        conn = get_db()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_vectors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scope TEXT NOT NULL,
                scope_id TEXT NOT NULL,
                category TEXT DEFAULT 'context',
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                embedding TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(scope_id, category, key)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_mv_scope
            ON memory_vectors(scope_id)
        """)
        conn.commit()
        conn.close()

    async def _get_http(self):
        if self._http is None:
            import httpx
            self._http = httpx.AsyncClient(timeout=30.0)
        return self._http

    async def embed(self, text: str) -> Optional[list[float]]:
        """Generate embedding vector for text using OpenAI-compatible API."""
        key = os.environ.get(_EMBEDDING_KEY_ENV, "")
        if not key:
            logger.debug("No embedding API key (%s), skipping", _EMBEDDING_KEY_ENV)
            return None

        try:
            http = await self._get_http()
            resp = await http.post(
                _EMBEDDING_ENDPOINT,
                json={"input": text[:8000], "model": "text-embedding-3-small"},
                headers={"api-key": key, "Content-Type": "application/json"},
            )
            if resp.status_code != 200:
                logger.warning("Embedding API error %d: %s", resp.status_code, resp.text[:200])
                return None
            data = resp.json()
            return data["data"][0]["embedding"]
        except Exception as exc:
            logger.warning("Embedding failed: %s", exc)
            return None

    async def store(
        self,
        scope_id: str,
        key: str,
        value: str,
        category: str = "context",
        scope: str = "project",
    ) -> int:
        """Store a memory entry with its embedding vector."""
        embedding = await self.embed(f"{key}: {value}")
        emb_json = json.dumps(embedding) if embedding else None

        conn = get_db()
        existing = conn.execute(
            "SELECT id FROM memory_vectors WHERE scope_id=? AND category=? AND key=?",
            (scope_id, category, key)
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE memory_vectors SET value=?, embedding=?, created_at=CURRENT_TIMESTAMP WHERE id=?",
                (value, emb_json, existing["id"])
            )
            conn.commit()
            rid = existing["id"]
        else:
            cur = conn.execute(
                "INSERT INTO memory_vectors (scope, scope_id, category, key, value, embedding) VALUES (?,?,?,?,?,?)",
                (scope, scope_id, category, key, value, emb_json)
            )
            conn.commit()
            rid = cur.lastrowid
        conn.close()
        return rid

    async def search(
        self,
        scope_id: str,
        query: str,
        limit: int = 10,
        min_similarity: float = 0.3,
    ) -> list[dict]:
        """Semantic search using cosine similarity. Falls back to LIKE search."""
        query_embedding = await self.embed(query)

        conn = get_db()
        if query_embedding is not None:
            # Vector search: load all entries for scope, compute similarity
            rows = conn.execute(
                "SELECT id, category, key, value, embedding FROM memory_vectors WHERE scope_id=? AND embedding IS NOT NULL",
                (scope_id,)
            ).fetchall()
            conn.close()

            query_vec = np.array(query_embedding, dtype=np.float32)
            scored = []
            for row in rows:
                try:
                    emb = np.array(json.loads(row["embedding"]), dtype=np.float32)
                    sim = _cosine_similarity(query_vec, emb)
                    if sim >= min_similarity:
                        scored.append({
                            "id": row["id"],
                            "category": row["category"],
                            "key": row["key"],
                            "value": row["value"],
                            "similarity": round(sim, 4),
                        })
                except (json.JSONDecodeError, ValueError):
                    continue

            scored.sort(key=lambda x: x["similarity"], reverse=True)
            return scored[:limit]
        else:
            # Fallback: keyword search
            rows = conn.execute(
                "SELECT id, category, key, value FROM memory_vectors WHERE scope_id=? AND (key LIKE ? OR value LIKE ?) LIMIT ?",
                (scope_id, f"%{query}%", f"%{query}%", limit)
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]

    def count(self, scope_id: str = "") -> dict:
        """Count entries, optionally filtered by scope."""
        conn = get_db()
        if scope_id:
            row = conn.execute(
                "SELECT COUNT(*) as total, SUM(CASE WHEN embedding IS NOT NULL THEN 1 ELSE 0 END) as with_embedding FROM memory_vectors WHERE scope_id=?",
                (scope_id,)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) as total, SUM(CASE WHEN embedding IS NOT NULL THEN 1 ELSE 0 END) as with_embedding FROM memory_vectors"
            ).fetchone()
        conn.close()
        return {"total": row["total"], "with_embedding": row["with_embedding"] or 0}

    async def close(self):
        if self._http and not self._http.is_closed:
            await self._http.aclose()


# Singleton
_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store
