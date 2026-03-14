"""
Agent Reward Tools — composite reward scoring for SF agent runs.
================================================================
Implements the reward function pattern inspired by ART (OpenPipe, Apache-2.0):
  https://github.com/OpenPipe/ART

PURPOSE: Give every agent run an explicit reward signal (0.0 – 1.0) based on
observable task outcomes, not vibes. This serves two goals:
  1. NOW  — quality monitoring: track which agent roles degrade over time
  2. LATER — ART readiness: when SF runs local Qwen weights, these trajectories
             + reward scores become direct GRPO training data

DESIGN CHOICES vs full ART integration:
  - We don't train yet (no GPU, we use API LLMs)
  - But we collect the same data ART would need: (trajectory, reward)
  - reward_export_art() outputs JSONL in ART's expected trajectory format
    so migration later is a config change, not a code rewrite

REWARD COMPONENTS (all 0.0 – 1.0, None = not measured):
  quality    — spec-driven-quality gate pass rate (if module enabled)
  slop       — anti-slop cleanliness score (1=clean, 0=hallucinations/fillers)
  tools      — tool call efficiency: success_rate × (1 − retry_overhead)
  latency    — normalised response time (1=fast, 0=slow, threshold 30s)
  outcome    — explicit outcome flag: 1=success, 0.5=partial, 0=failed

COMPOSITE: weighted average of available components (ignores None values)
  Default weights: outcome×0.40, quality×0.25, slop×0.20, tools×0.10, latency×0.05

SOURCE: Reward function design from ART (OpenPipe, Apache-2.0) — we port the
  *concept* (explicit per-run reward signal + trajectory storage) without the
  GPU training loop. The data format is ART-compatible for future migration.
"""
# Ref: feat-mercato

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from ..models import AgentInstance
from .registry import BaseTool

logger = logging.getLogger(__name__)

_DEFAULT_WEIGHTS = {
    "outcome": 0.40,
    "quality": 0.25,
    "slop": 0.20,
    "tools": 0.10,
    "latency": 0.05,
}

_LATENCY_THRESHOLD_S = 30.0  # above this → latency_score = 0


def _ensure_table(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            agent_role TEXT DEFAULT '',
            mission_id TEXT DEFAULT '',
            outcome_score REAL DEFAULT NULL,
            quality_score REAL DEFAULT NULL,
            slop_score REAL DEFAULT NULL,
            tools_score REAL DEFAULT NULL,
            latency_score REAL DEFAULT NULL,
            composite REAL DEFAULT NULL,
            signals_json TEXT DEFAULT '{}',
            notes TEXT DEFAULT '',
            exported_at TEXT DEFAULT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    try:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rewards_run ON agent_rewards(run_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rewards_role ON agent_rewards(agent_role)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rewards_composite ON agent_rewards(composite)"
        )
    except Exception:
        pass
    try:
        conn.commit()
    except Exception:
        pass


def _compute_composite(scores: dict) -> Optional[float]:
    total_w = 0.0
    total_v = 0.0
    for key, weight in _DEFAULT_WEIGHTS.items():
        v = scores.get(key)
        if v is not None:
            total_w += weight
            total_v += v * weight
    if total_w == 0:
        return None
    return round(total_v / total_w, 4)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


class RewardScoreRunTool(BaseTool):
    """
    Store a reward score for a completed agent run.

    Params:
      run_id       — mission_runs.id or any session identifier
      agent_role   — agent role (dev, qa, devops, diagnostic, …)
      mission_id   — optional mission reference
      outcome      — float 0-1 (1=success, 0.5=partial, 0=failed)
      quality      — float 0-1 from spec-driven-quality gate (optional)
      slop         — float 0-1 from anti-slop check (optional)
      tools        — float 0-1 tool call efficiency (optional)
      latency_s    — actual latency in seconds (converted internally)
      notes        — free text (what was the task, any context)
      signals      — dict of raw signal values (stored as JSON)
    """

    name = "reward_score_run"
    description = "Store a reward score (0-1) for a completed agent run. Call at the end of any mission/task to record quality signal."

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        run_id = params.get("run_id", "")
        agent_role = params.get("agent_role", "")
        mission_id = params.get("mission_id", "")

        scores = {
            "outcome": _clamp(params.get("outcome")),
            "quality": _clamp(params.get("quality")),
            "slop": _clamp(params.get("slop")),
            "tools": _clamp(params.get("tools")),
        }

        # Convert raw latency → normalised score
        latency_s = params.get("latency_s")
        if latency_s is not None:
            try:
                ls = float(latency_s)
                scores["latency"] = round(max(0.0, 1.0 - ls / _LATENCY_THRESHOLD_S), 4)
            except (TypeError, ValueError):
                scores["latency"] = None
        else:
            scores["latency"] = None

        composite = _compute_composite(scores)
        signals = params.get("signals", {})

        try:
            from ..db.adapter import get_connection

            conn = get_connection()
            _ensure_table(conn)
            conn.execute(
                """
                INSERT INTO agent_rewards
                    (run_id, agent_role, mission_id,
                     outcome_score, quality_score, slop_score, tools_score, latency_score,
                     composite, signals_json, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    agent_role,
                    mission_id,
                    scores.get("outcome"),
                    scores.get("quality"),
                    scores.get("slop"),
                    scores.get("tools"),
                    scores.get("latency"),
                    composite,
                    json.dumps(signals),
                    params.get("notes", ""),
                ),
            )
        except Exception as e:
            return f"[reward_score_run] DB error: {e}"

        lines = [
            f"✓ Reward stored — run: {run_id or '(none)'} | role: {agent_role}",
        ]
        if composite is not None:
            bar = _bar(composite)
            lines.append(f"  composite: {composite:.3f} {bar}")
        for k, v in scores.items():
            if v is not None:
                lines.append(f"  {k:<9}: {v:.3f}")
        if params.get("notes"):
            lines.append(f"  notes: {params['notes']}")
        return "\n".join(lines)


class RewardGetHistoryTool(BaseTool):
    """
    Get recent reward scores for a given agent role (or all roles).

    Params:
      agent_role  — filter by role (optional, omit for all)
      n           — number of recent runs to return (default 20)
      min_score   — filter to composite >= min_score (optional)
    """

    name = "reward_get_history"
    description = "Get recent reward scores for an agent role. Use to track quality trends over time."

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        agent_role = params.get("agent_role", "")
        n = min(int(params.get("n", 20)), 100)
        min_score = params.get("min_score")

        try:
            from ..db.adapter import get_connection

            conn = get_connection()
            _ensure_table(conn)

            where = []
            args = []
            if agent_role:
                where.append("agent_role = ?")
                args.append(agent_role)
            if min_score is not None:
                where.append("composite >= ?")
                args.append(float(min_score))

            clause = ("WHERE " + " AND ".join(where)) if where else ""
            args.append(n)

            rows = conn.execute(
                f"""
                SELECT run_id, agent_role, mission_id,
                       outcome_score, quality_score, slop_score, tools_score, latency_score,
                       composite, notes, created_at
                FROM agent_rewards
                {clause}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                args,
            ).fetchall()

        except Exception as e:
            return f"[reward_get_history] DB error: {e}"

        if not rows:
            label = f" for role={agent_role}" if agent_role else ""
            return f"No reward scores found{label}."

        lines = [f"=== reward history ({len(rows)} runs) ==="]
        for row in rows:
            composite = row[8]
            bar = _bar(composite) if composite is not None else "   "
            ts = str(row[10])[:16]
            lines.append(
                f"[{ts}] {row[1] or '?':12s} run={row[0][:12]:12s}  "
                f"composite={composite or 'N/A':>5}  {bar}"
            )
            subs = []
            labels = ["out", "qual", "slop", "tool", "lat"]
            for i, lbl in enumerate(labels):
                v = row[3 + i]
                if v is not None:
                    subs.append(f"{lbl}={v:.2f}")
            if subs:
                lines.append(f"           {' | '.join(subs)}")
            if row[9]:
                lines.append(f"           note: {row[9][:80]}")
        return "\n".join(lines)


class RewardSummaryTool(BaseTool):
    """
    Aggregate reward statistics per agent role.
    Shows avg composite, trend, best/worst runs.

    Params:
      days  — lookback window in days (default 30)
    """

    name = "reward_summary"
    description = (
        "Aggregate reward stats per agent role. Identify which roles are degrading."
    )

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        days = int(params.get("days", 30))

        try:
            from ..db.adapter import get_connection

            conn = get_connection()
            _ensure_table(conn)

            rows = conn.execute(
                """
                SELECT agent_role,
                       COUNT(*) as n,
                       ROUND(CAST(AVG(composite) AS NUMERIC), 3) as avg_c,
                       ROUND(CAST(MIN(composite) AS NUMERIC), 3) as min_c,
                       ROUND(CAST(MAX(composite) AS NUMERIC), 3) as max_c,
                       ROUND(CAST(AVG(outcome_score) AS NUMERIC), 3) as avg_out,
                       ROUND(CAST(AVG(quality_score) AS NUMERIC), 3) as avg_qual,
                       ROUND(CAST(AVG(slop_score) AS NUMERIC), 3) as avg_slop
                FROM agent_rewards
                WHERE created_at >= NOW() - (? * INTERVAL '1 day')
                  AND composite IS NOT NULL
                GROUP BY agent_role
                ORDER BY avg_c DESC
                """,
                (days,),
            ).fetchall()

        except Exception as e:
            return f"[reward_summary] DB error: {e}"

        if not rows:
            return f"No reward data in the last {days} days."

        lines = [f"=== reward summary — last {days} days ===", ""]
        lines.append(f"{'role':<15} {'n':>4}  {'avg':>6}  {'min':>6}  {'max':>6}  bar")
        lines.append("-" * 55)
        for row in rows:
            role, n, avg_c, min_c, max_c = row[0], row[1], row[2], row[3], row[4]
            bar = _bar(avg_c) if avg_c is not None else "   "
            lines.append(
                f"{role or '?':<15} {n:>4}  {avg_c or 0:>6.3f}  "
                f"{min_c or 0:>6.3f}  {max_c or 0:>6.3f}  {bar}"
            )
            avg_out, avg_qual, avg_slop = row[5], row[6], row[7]
            subs = []
            if avg_out is not None:
                subs.append(f"outcome={avg_out:.2f}")
            if avg_qual is not None:
                subs.append(f"quality={avg_qual:.2f}")
            if avg_slop is not None:
                subs.append(f"slop={avg_slop:.2f}")
            if subs:
                lines.append(f"               {' | '.join(subs)}")
        return "\n".join(lines)


class RewardExportArtTool(BaseTool):
    """
    Export agent trajectories + rewards as ART-compatible JSONL.

    Generates a file at /tmp/art_trajectories_<timestamp>.jsonl that can be
    fed directly into ART's training loop once SF runs local model weights.

    Params:
      n          — number of trajectories to export (default 100)
      min_score  — only export runs with composite >= min_score (default 0.0)
      max_score  — only export runs with composite <= max_score (optional, useful for hard negatives)
      output     — output path (default /tmp/art_trajectories_<ts>.jsonl)
    """

    name = "reward_export_art"
    description = "Export agent trajectories and reward scores as ART-compatible JSONL for future RL training."

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        n = min(int(params.get("n", 100)), 1000)
        min_score = float(params.get("min_score", 0.0))
        max_score = params.get("max_score")
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        output = params.get("output", f"/tmp/art_trajectories_{ts}.jsonl")

        try:
            from ..db.adapter import get_connection

            conn = get_connection()
            _ensure_table(conn)

            where = ["composite >= ?"]
            args: list = [min_score]
            if max_score is not None:
                where.append("composite <= ?")
                args.append(float(max_score))
            args.append(n)

            rows = conn.execute(
                f"""
                SELECT run_id, agent_role, mission_id,
                       outcome_score, quality_score, slop_score, tools_score, latency_score,
                       composite, signals_json, notes, created_at
                FROM agent_rewards
                WHERE {" AND ".join(where)}
                ORDER BY composite DESC, created_at DESC
                LIMIT ?
                """,
                args,
            ).fetchall()

        except Exception as e:
            return f"[reward_export_art] DB error: {e}"

        if not rows:
            return "No trajectories found matching filters."

        # ART trajectory format:
        # {"messages": [...], "reward": float, "metadata": {...}}
        # Messages come from tool_calls table (best effort — join by run_id)
        count = 0
        try:
            from ..db.adapter import get_connection

            conn = get_connection()
            with open(output, "w") as f:
                for row in rows:
                    run_id = row[0]
                    # Try to reconstruct trajectory from tool_calls
                    tc_rows = []
                    try:
                        tc_rows = conn.execute(
                            """
                            SELECT tool_name, parameters_json, result_json, success, duration_ms, timestamp
                            FROM tool_calls WHERE agent_id = ?
                            ORDER BY timestamp ASC LIMIT 50
                            """,
                            (run_id,),
                        ).fetchall()
                    except Exception:
                        pass

                    messages = []
                    for tc in tc_rows:
                        messages.append(
                            {
                                "role": "assistant",
                                "content": f"[tool_call:{tc[0]}] {tc[1]}",
                            }
                        )
                        messages.append(
                            {
                                "role": "tool",
                                "content": str(tc[2])[:500],
                                "success": bool(tc[3]),
                                "duration_ms": tc[4],
                            }
                        )

                    record = {
                        "messages": messages,
                        "reward": row[8],  # composite
                        "metadata": {
                            "run_id": row[0],
                            "agent_role": row[1],
                            "mission_id": row[2],
                            "scores": {
                                "outcome": row[3],
                                "quality": row[4],
                                "slop": row[5],
                                "tools": row[6],
                                "latency": row[7],
                            },
                            "signals": _safe_json(row[9]),
                            "notes": row[10],
                            "created_at": row[11],
                        },
                    }
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    count += 1

            # Mark as exported
            conn.execute(
                "UPDATE agent_rewards SET exported_at = NOW() WHERE run_id IN ("
                + ",".join("?" * len(rows))
                + ")",
                [r[0] for r in rows],
            )

        except Exception as e:
            return f"[reward_export_art] Export error: {e}"

        return (
            f"✓ Exported {count} trajectories → {output}\n"
            f"  score range: [{min_score:.2f}, {max_score or 1.0:.2f}]\n"
            f"  ART format: {{messages, reward, metadata}}\n"
            f"  Next: feed to ART TrainableModel when running local weights\n"
            f"  Docs: https://art.openpipe.ai"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clamp(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return round(max(0.0, min(1.0, float(v))), 4)
    except (TypeError, ValueError):
        return None


def _bar(v: Optional[float]) -> str:
    if v is None:
        return "░░░░░"
    filled = round(v * 5)
    return "█" * filled + "░" * (5 - filled)


def _safe_json(s) -> dict:
    if not s:
        return {}
    try:
        return json.loads(s)
    except Exception:
        return {"raw": str(s)[:200]}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_reward_tools(reg) -> None:
    """Register all reward tools into the tool registry."""
    for cls in (
        RewardScoreRunTool,
        RewardGetHistoryTool,
        RewardSummaryTool,
        RewardExportArtTool,
    ):
        reg.register(cls())
