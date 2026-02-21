"""LLM Observability — tracks every LLM call in SQLite.

Provides:
- Per-call tracing (provider, model, tokens, cost, duration)
- Per-agent/session/mission aggregation
- Cost estimation per model
- Optional Langfuse REST API forwarding (when keys configured)

Usage:
    from platform.llm.observability import get_tracer
    tracer = get_tracer()
    tracer.trace_call(provider="minimax", model="MiniMax-M2.5", ...)
    stats = tracer.stats()
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass
from typing import Optional

from ..db.migrations import get_db

logger = logging.getLogger(__name__)

# Cost per 1M tokens (USD) — approximate pricing
_COST_PER_1M = {
    "MiniMax-M2.5": {"input": 0.40, "output": 1.20},
    "MiniMax-M2.1": {"input": 0.30, "output": 0.90},
    "gpt-5.2": {"input": 5.00, "output": 15.00},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-5.1": {"input": 3.00, "output": 12.00},
    "gpt-5.1-codex": {"input": 3.00, "output": 12.00},
    "gpt-5.1-codex-mini": {"input": 0.50, "output": 2.00},
    "moonshotai/kimi-k2-instruct": {"input": 1.00, "output": 3.00},
}
_DEFAULT_COST = {"input": 1.00, "output": 3.00}


def _estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    rates = _COST_PER_1M.get(model, _DEFAULT_COST)
    return (tokens_in * rates["input"] + tokens_out * rates["output"]) / 1_000_000


@dataclass
class TraceRecord:
    id: str
    provider: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: int = 0
    cost_usd: float = 0.0
    status: str = "ok"
    error: str = ""
    agent_id: str = ""
    session_id: str = ""
    mission_id: str = ""
    input_preview: str = ""
    output_preview: str = ""


class LLMTracer:
    """Tracks LLM calls in SQLite with cost estimation."""

    def __init__(self):
        self._ensure_table()

    def _ensure_table(self):
        conn = get_db()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS llm_traces (
                id TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                agent_id TEXT DEFAULT '',
                session_id TEXT DEFAULT '',
                mission_id TEXT DEFAULT '',
                tokens_in INTEGER DEFAULT 0,
                tokens_out INTEGER DEFAULT 0,
                duration_ms INTEGER DEFAULT 0,
                cost_usd REAL DEFAULT 0.0,
                status TEXT DEFAULT 'ok',
                error TEXT DEFAULT '',
                input_preview TEXT DEFAULT '',
                output_preview TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_llm_traces_session
            ON llm_traces(session_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_llm_traces_created
            ON llm_traces(created_at)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_llm_traces_agent
            ON llm_traces(agent_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_llm_traces_provider
            ON llm_traces(provider, model)
        """)
        conn.commit()
        conn.close()

    def trace_call(
        self,
        provider: str,
        model: str,
        tokens_in: int = 0,
        tokens_out: int = 0,
        duration_ms: int = 0,
        status: str = "ok",
        error: str = "",
        agent_id: str = "",
        session_id: str = "",
        mission_id: str = "",
        input_preview: str = "",
        output_preview: str = "",
    ) -> str:
        """Record an LLM call. Returns trace ID."""
        trace_id = uuid.uuid4().hex[:12]
        cost = _estimate_cost(model, tokens_in, tokens_out)

        conn = get_db()
        conn.execute("""
            INSERT INTO llm_traces
            (id, provider, model, agent_id, session_id, mission_id,
             tokens_in, tokens_out, duration_ms, cost_usd,
             status, error, input_preview, output_preview)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (trace_id, provider, model, agent_id, session_id, mission_id,
              tokens_in, tokens_out, duration_ms, cost,
              status, error, input_preview[:500], output_preview[:500]))
        conn.commit()
        conn.close()

        logger.info("LLM trace %s: %s/%s %din/%dout $%.4f %dms",
                     trace_id, provider, model, tokens_in, tokens_out, cost, duration_ms)

        # Feed metrics collector
        try:
            from ..metrics.collector import get_collector
            get_collector().track_llm_cost(provider, model, cost, tokens_in, tokens_out)
        except Exception:
            pass

        return trace_id

    def stats(self, session_id: str = "", hours: int = 24) -> dict:
        """Get aggregated stats."""
        conn = get_db()
        where = "WHERE created_at > datetime('now', ?)"
        params: list = [f"-{hours} hours"]
        if session_id:
            where += " AND session_id = ?"
            params.append(session_id)

        row = conn.execute(f"""
            SELECT
                COUNT(*) as total_calls,
                COALESCE(SUM(tokens_in), 0) as total_tokens_in,
                COALESCE(SUM(tokens_out), 0) as total_tokens_out,
                COALESCE(SUM(cost_usd), 0) as total_cost_usd,
                COALESCE(AVG(duration_ms), 0) as avg_duration_ms,
                COALESCE(SUM(CASE WHEN status='error' THEN 1 ELSE 0 END), 0) as error_count
            FROM llm_traces {where}
        """, params).fetchone()

        by_provider = conn.execute(f"""
            SELECT provider, model,
                   COUNT(*) as calls,
                   SUM(tokens_in) as tokens_in,
                   SUM(tokens_out) as tokens_out,
                   SUM(cost_usd) as cost_usd,
                   AVG(duration_ms) as avg_ms
            FROM llm_traces {where}
            GROUP BY provider, model
            ORDER BY calls DESC
        """, params).fetchall()

        by_agent = conn.execute(f"""
            SELECT agent_id,
                   COUNT(*) as calls,
                   SUM(cost_usd) as cost_usd,
                   SUM(tokens_out) as tokens_out
            FROM llm_traces {where}
            AND agent_id != ''
            GROUP BY agent_id
            ORDER BY cost_usd DESC
            LIMIT 20
        """, params).fetchall()

        conn.close()
        return {
            "total_calls": row["total_calls"],
            "total_tokens_in": row["total_tokens_in"],
            "total_tokens_out": row["total_tokens_out"],
            "total_cost_usd": round(row["total_cost_usd"], 4),
            "avg_duration_ms": round(row["avg_duration_ms"]),
            "error_count": row["error_count"],
            "by_provider": [dict(r) for r in by_provider],
            "by_agent": [dict(r) for r in by_agent],
        }

    def recent(self, limit: int = 50, session_id: str = "") -> list[dict]:
        """Get recent traces."""
        conn = get_db()
        if session_id:
            rows = conn.execute(
                "SELECT * FROM llm_traces WHERE session_id=? ORDER BY created_at DESC LIMIT ?",
                (session_id, limit)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM llm_traces ORDER BY created_at DESC LIMIT ?",
                (limit,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]


# Singleton
_tracer: Optional[LLMTracer] = None


def get_tracer() -> LLMTracer:
    global _tracer
    if _tracer is None:
        _tracer = LLMTracer()
    return _tracer
