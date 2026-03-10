"""Cross-instinct consolidation — timer-based memory consolidation.

SOURCE: GoogleCloudPlatform/generative-ai — always-on-memory-agent (ConsolidateAgent)
        https://github.com/GoogleCloudPlatform/generative-ai/tree/main/gemini/agents/always-on-memory-agent

WHY: That project's ConsolidateAgent runs every 30 min, reads all memories, finds
     cross-cutting connections (Memory#1 <-> Memory#3 shared topic), and generates
     meta-insights — exactly like a brain consolidating memories during sleep.
     Our instinct system (platform/hooks/instinct.py) extracts patterns per-session
     but NEVER cross-references instincts against each other. If agent A learned
     "always read before write" and agent B learned the same, that cross-agent
     convergence is invisible. This module adds that consolidation layer.

ADAPTATION vs always-on-memory-agent:
- No vector DB, no embeddings — LLM reads all instincts directly (same philosophy)
- Stores cross-instinct insights in instinct_insights table (not a separate file)
- Timer period: 30 min (CONSOLIDATION_INTERVAL env var) — same as original
- Uses platform LLMClient (provider-agnostic: minimax/azure/gpt — not Gemini-specific)
- Groups: by domain pair, by agent convergence, by confidence cluster

INSIGHT TYPES:
  connection  — two instincts share a pattern across different agents/projects
  insight     — meta observation from clustering (e.g., "3 agents avoid X")
  convergence — same trigger/action in 2+ agents → global candidate
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# How often to consolidate (seconds). Default: 30 min (same as always-on-memory-agent)
CONSOLIDATION_INTERVAL = int(os.environ.get("CONSOLIDATION_INTERVAL", 1800))

# Max instincts to pass to LLM in one consolidation batch (token budget)
_MAX_INSTINCTS_PER_BATCH = int(os.environ.get("CONSOLIDATION_BATCH_SIZE", 60))

# Minimum confidence for instincts considered for cross-reference
_MIN_CONFIDENCE = 0.3


@dataclass
class InstinctInsight:
    """A cross-instinct connection or meta-insight derived by the LLM."""

    type: str  # connection | insight | convergence
    instinct_ids: list[str]
    summary: str
    domains: list[str]
    confidence: float = 0.5
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


# ─────────────────────────────────────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────────────────────────────────────


def _load_instincts(limit: int = _MAX_INSTINCTS_PER_BATCH) -> list[dict]:
    """Load recent high-confidence instincts from DB."""
    try:
        from ..db.migrations import get_db

        with get_db() as db:
            rows = db.execute(
                """SELECT id, agent_id, project_id, trigger, action, confidence, domain, scope
                   FROM instincts
                   WHERE confidence >= ?
                   ORDER BY confidence DESC, updated_at DESC
                   LIMIT ?""",
                (_MIN_CONFIDENCE, limit),
            ).fetchall()
            cols = [
                "id",
                "agent_id",
                "project_id",
                "trigger",
                "action",
                "confidence",
                "domain",
                "scope",
            ]
            return [dict(zip(cols, r)) for r in rows]
    except Exception as e:
        logger.error("consolidate._load_instincts: %s", e)
        return []


def _already_consolidated(instinct_ids: list[str]) -> bool:
    """Check if a pair/group of instinct IDs was already consolidated."""
    if len(instinct_ids) < 2:
        return False
    try:
        from ..db.migrations import get_db

        # Check if all IDs appear together in an existing insight
        with get_db() as db:
            rows = db.execute(
                "SELECT instinct_ids FROM instinct_insights ORDER BY created_at DESC LIMIT 200"
            ).fetchall()
            key = frozenset(instinct_ids)
            for r in rows:
                try:
                    ids = frozenset(json.loads(r[0]))
                    if key <= ids:  # subset check
                        return True
                except Exception:
                    pass
        return False
    except Exception:
        return False


def _save_insight(insight: InstinctInsight) -> str:
    """Persist an InstinctInsight to DB. Returns id."""
    try:
        from ..db.migrations import get_db

        with get_db() as db:
            db.execute(
                """INSERT OR IGNORE INTO instinct_insights
                   (id, type, instinct_ids, summary, domains, confidence, created_at, updated_at)
                   VALUES (?,?,?,?,?,?, strftime('%Y-%m-%dT%H:%M:%SZ','now'), strftime('%Y-%m-%dT%H:%M:%SZ','now'))""",
                (
                    insight.id,
                    insight.type,
                    json.dumps(insight.instinct_ids),
                    insight.summary,
                    json.dumps(insight.domains),
                    insight.confidence,
                ),
            )
        return insight.id
    except Exception as e:
        logger.error("consolidate._save_insight: %s", e)
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# LLM consolidation
# ─────────────────────────────────────────────────────────────────────────────


def _build_consolidation_prompt(instincts: list[dict]) -> str:
    """Build the prompt for the LLM to find connections between instincts.

    SOURCE: always-on-memory-agent ConsolidateAgent prompt strategy —
    "find connections, generate cross-cutting insights, compress related info".
    """
    lines = []
    for i, inst in enumerate(instincts):
        lines.append(
            f"[{i}] id={inst['id'][:8]} agent={inst.get('agent_id', '?')} "
            f"domain={inst['domain']} conf={inst['confidence']:.1f} "
            f"trigger='{inst['trigger']}' action='{inst['action']}'"
        )

    instinct_list = "\n".join(lines)

    return f"""You are analyzing {len(instincts)} learned agent behaviors (instincts) to find cross-cutting patterns.

INSTINCTS:
{instinct_list}

Find meaningful connections between these instincts. Look for:
1. CONVERGENCE: same trigger→action pattern in multiple agents (different agent_id, similar trigger/action)
2. CONNECTION: two instincts from different domains that relate to the same underlying principle
3. INSIGHT: a meta-observation about what most/all agents tend to do

Return a JSON array of findings (max 5). Each item:
{{
  "type": "convergence" | "connection" | "insight",
  "instinct_indices": [0, 3, 7],
  "summary": "One sentence describing the connection or insight",
  "domains": ["coding", "git"],
  "confidence": 0.6
}}

Rules:
- Only report genuine connections, not superficial ones
- Each connection needs at least 2 instincts
- confidence 0.3-0.9 based on evidence strength
- Return [] if no meaningful connections found

JSON only, no explanation."""


async def _call_llm(prompt: str) -> list[dict]:
    """Call the platform LLM to get consolidation insights."""
    try:
        from ..llm.client import LLMClient, LLMMessage

        client = LLMClient()
        resp = await client.chat(
            messages=[LLMMessage(role="user", content=prompt)],
            temperature=0.3,
            max_tokens=1024,
        )
        text = resp.content.strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        parsed = json.loads(text)
        return parsed if isinstance(parsed, list) else []
    except Exception as e:
        logger.warning("consolidate._call_llm: %s", e)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Convergence detection (no LLM needed — pure SQL)
# ─────────────────────────────────────────────────────────────────────────────


def _find_convergences(instincts: list[dict]) -> list[InstinctInsight]:
    """Find instincts with similar trigger across different agents (deterministic).

    WHY: Same pattern learned independently by multiple agents = strong signal.
    Source: always-on-memory-agent cross-reference logic — adapted without embeddings
    using exact/prefix string matching (much cheaper, good enough for trigger text).
    """
    from collections import defaultdict

    by_trigger: dict[str, list[dict]] = defaultdict(list)
    for inst in instincts:
        # Normalize trigger key (first 40 chars lowered)
        key = inst["trigger"].lower()[:40].strip()
        by_trigger[key].append(inst)

    insights = []
    for trigger_key, group in by_trigger.items():
        # Only interesting if multiple distinct agents
        agents = {i.get("agent_id", "") for i in group}
        if len(agents) < 2:
            continue

        ids = [i["id"] for i in group]
        if _already_consolidated(ids):
            continue

        avg_conf = sum(i["confidence"] for i in group) / len(group)
        domains = list({i["domain"] for i in group})
        insights.append(
            InstinctInsight(
                type="convergence",
                instinct_ids=ids,
                summary=(
                    f"{len(agents)} agents independently learned: '{group[0]['trigger']}' "
                    f"→ '{group[0]['action'][:60]}' — cross-agent convergence signal"
                ),
                domains=domains,
                confidence=min(0.9, avg_conf + 0.1 * len(agents)),
            )
        )

    return insights


# ─────────────────────────────────────────────────────────────────────────────
# Main consolidation function
# ─────────────────────────────────────────────────────────────────────────────


async def consolidate_once() -> dict:
    """Run one consolidation pass: load instincts, find connections, save insights.

    SOURCE: always-on-memory-agent ConsolidateAgent.consolidate() — adapted.
    Returns: {"llm_insights": N, "convergences": N, "total": N}
    """
    instincts = _load_instincts()
    if len(instincts) < 3:
        logger.debug(
            "consolidate: not enough instincts (%d) — skipping", len(instincts)
        )
        return {"llm_insights": 0, "convergences": 0, "total": 0}

    logger.info("consolidate: running on %d instincts", len(instincts))

    # 1. Deterministic convergence detection (no LLM, cheap)
    convergences = _find_convergences(instincts)
    saved_conv = 0
    for c in convergences:
        if _save_insight(c):
            saved_conv += 1
            logger.debug("consolidate: convergence saved — %s", c.summary[:80])

    # 2. LLM cross-reference (deeper connections + meta-insights)
    prompt = _build_consolidation_prompt(instincts[:_MAX_INSTINCTS_PER_BATCH])
    raw_findings = await _call_llm(prompt)

    saved_llm = 0
    for finding in raw_findings:
        try:
            indices = finding.get("instinct_indices", [])
            ids = [instincts[i]["id"] for i in indices if i < len(instincts)]
            if not ids or _already_consolidated(ids):
                continue
            domains = finding.get("domains", [])
            insight = InstinctInsight(
                type=finding.get("type", "insight"),
                instinct_ids=ids,
                summary=finding.get("summary", ""),
                domains=domains if isinstance(domains, list) else [domains],
                confidence=float(finding.get("confidence", 0.5)),
            )
            if _save_insight(insight):
                saved_llm += 1
                logger.debug(
                    "consolidate: insight saved [%s] %s",
                    insight.type,
                    insight.summary[:80],
                )
        except (IndexError, KeyError, TypeError) as e:
            logger.debug("consolidate: finding parse error: %s", e)

    total = saved_conv + saved_llm
    if total:
        logger.info(
            "consolidate: done — %d convergences + %d LLM insights",
            saved_conv,
            saved_llm,
        )
    return {"llm_insights": saved_llm, "convergences": saved_conv, "total": total}


async def start_consolidation_timer() -> None:
    """Background task: run consolidation every CONSOLIDATION_INTERVAL seconds.

    SOURCE: always-on-memory-agent — runs ConsolidateAgent on a 30-minute timer.
    WHY: Continuous background consolidation surfaces cross-agent patterns that
         session-level observation misses. Like brain consolidation during sleep.
    """
    logger.info(
        "consolidation timer started (interval=%ds = %dmin)",
        CONSOLIDATION_INTERVAL,
        CONSOLIDATION_INTERVAL // 60,
    )
    # Initial delay: wait for DB + agents to be ready
    await asyncio.sleep(120)
    while True:
        try:
            result = await consolidate_once()
            if result["total"] > 0:
                logger.info("consolidation: %s", result)
        except Exception as e:
            logger.error("consolidation timer error: %s", e)
        await asyncio.sleep(CONSOLIDATION_INTERVAL)
