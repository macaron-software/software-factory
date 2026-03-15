# Ref: feat-gossipsub
"""GossipSub — Cross-project mutation broadcasting.

Broadcasts winning mutations (skill variants, instincts, GA genomes) across
projects so that a typography fix that scored well on a portfolio project can
be adopted by a dashboard project without either discovering it independently.

Architecture:
  - Producers: skill_thompson (on win), instinct (on promote), evolution (on approve)
  - Transport: A2A bus broadcast (Redis pub/sub + PG NOTIFY fallback)
  - Consumers: each project's AC layer cherry-picks compatible mutations
  - Storage: gossip_ledger table for analytics + replay

Inspired by libp2p GossipSub protocol — eager push to mesh peers,
lazy pull via ledger for offline nodes.
"""
import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional

log = logging.getLogger(__name__)


# ── Types ────────────────────────────────────────────────────────────────────

class GossipType(str, Enum):
    SKILL_VARIANT = "skill_variant"
    INSTINCT = "instinct"
    GENOME = "genome"
    META_INSIGHT = "meta_insight"


@dataclass
class GossipMessage:
    """A mutation broadcast across the gossip network."""
    gossip_type: GossipType
    source_project: str
    payload: dict
    tier: str = ""              # complexity tier (simple/medium/complex)
    score_delta: float = 0.0    # improvement magnitude
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    ts: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ"))


# ── Ledger (DB persistence) ─────────────────────────────────────────────────

_TABLE_CREATED = False


def _ensure_ledger(conn) -> None:
    global _TABLE_CREATED
    if _TABLE_CREATED:
        return
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gossip_ledger (
                id TEXT PRIMARY KEY,
                gossip_type TEXT NOT NULL,
                source_project TEXT NOT NULL,
                tier TEXT DEFAULT '',
                score_delta REAL DEFAULT 0,
                payload_json TEXT NOT NULL,
                broadcast_at TEXT NOT NULL,
                adopted_by TEXT DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_gossip_type_ts
            ON gossip_ledger(gossip_type, broadcast_at DESC)
        """)
        conn.commit()
        _TABLE_CREATED = True
    except Exception as e:
        log.debug("gossip_ledger table create: %s", e)


def _record_broadcast(msg: GossipMessage) -> None:
    """Persist broadcast to ledger for analytics + replay."""
    try:
        from ..db.migrations import get_db
        with get_db() as db:
            _ensure_ledger(db)
            db.execute(
                """INSERT OR IGNORE INTO gossip_ledger
                   (id, gossip_type, source_project, tier, score_delta, payload_json, broadcast_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (msg.id, msg.gossip_type.value, msg.source_project,
                 msg.tier, msg.score_delta, json.dumps(msg.payload), msg.ts),
            )
            db.commit()
    except Exception as e:
        log.debug("gossip ledger write: %s", e)


def record_adoption(gossip_id: str, project_id: str) -> None:
    """Mark that a project adopted a gossip mutation."""
    try:
        from ..db.migrations import get_db
        with get_db() as db:
            _ensure_ledger(db)
            db.execute(
                """UPDATE gossip_ledger
                   SET adopted_by = CASE
                     WHEN adopted_by = '' THEN ?
                     ELSE adopted_by || ',' || ?
                   END
                   WHERE id = ?""",
                (project_id, project_id, gossip_id),
            )
            db.commit()
    except Exception as e:
        log.debug("gossip adoption record: %s", e)


# ── Broadcasting ─────────────────────────────────────────────────────────────

async def _broadcast_via_a2a(msg: GossipMessage) -> None:
    """Push gossip to A2A bus for real-time distribution."""
    try:
        from ..a2a.bus import get_a2a_bus
        from ..models import A2AMessage, MessageType
        bus = get_a2a_bus()
        if not bus:
            return
        a2a_msg = A2AMessage(
            session_id="__gossip__",
            from_agent="gossip-sub",
            to_agent=None,  # broadcast
            message_type=MessageType.INFORM,
            content=f"[GOSSIP:{msg.gossip_type.value}] {msg.source_project} → {msg.tier or 'all'}",
            metadata={
                "channel": "gossip",
                "gossip_type": msg.gossip_type.value,
                "gossip_id": msg.id,
                "source_project": msg.source_project,
                "tier": msg.tier,
                "score_delta": msg.score_delta,
                "payload": msg.payload,
            },
            priority=3,
        )
        await bus.publish(a2a_msg)
    except Exception as e:
        log.debug("gossip a2a broadcast: %s", e)


async def broadcast(msg: GossipMessage) -> None:
    """Broadcast a gossip message: persist to ledger + push to A2A bus."""
    _record_broadcast(msg)
    await _broadcast_via_a2a(msg)
    log.warning(
        "GOSSIP broadcast %s from %s tier=%s delta=%.1f",
        msg.gossip_type.value, msg.source_project, msg.tier, msg.score_delta,
    )


# ── Producers (called by subsystems) ────────────────────────────────────────

async def broadcast_skill_win(
    skill_id: str,
    variant: str,
    project_id: str,
    cycle_score: int,
    prev_score: int,
    tier: str = "",
) -> None:
    """Broadcast when a skill variant wins in a project."""
    delta = cycle_score - prev_score
    if delta <= 0:
        return
    msg = GossipMessage(
        gossip_type=GossipType.SKILL_VARIANT,
        source_project=project_id,
        tier=tier,
        score_delta=float(delta),
        payload={
            "skill_id": skill_id,
            "variant": variant,
            "cycle_score": cycle_score,
            "delta": delta,
        },
    )
    await broadcast(msg)


async def broadcast_instinct_promotion(
    trigger: str,
    action: str,
    agent_id: str,
    confidence: float,
    project_count: int,
) -> None:
    """Broadcast when an instinct is promoted to global scope."""
    msg = GossipMessage(
        gossip_type=GossipType.INSTINCT,
        source_project="__global__",
        score_delta=confidence,
        payload={
            "trigger": trigger,
            "action": action,
            "agent_id": agent_id,
            "confidence": confidence,
            "project_count": project_count,
        },
    )
    await broadcast(msg)


async def broadcast_genome_approval(
    workflow_id: str,
    project_id: str,
    genome: dict,
    fitness: float,
    baseline: float,
) -> None:
    """Broadcast when a GA genome is auto-approved."""
    msg = GossipMessage(
        gossip_type=GossipType.GENOME,
        source_project=project_id,
        score_delta=fitness - baseline,
        payload={
            "workflow_id": workflow_id,
            "fitness": fitness,
            "baseline": baseline,
            "genome_summary": {
                k: v for k, v in genome.items()
                if k in ("pattern", "gate", "agents", "task_hint")
            },
        },
    )
    await broadcast(msg)


async def broadcast_meta_insight(
    insight: str,
    source_projects: list[str],
    confidence: float,
) -> None:
    """Broadcast a cross-instinct consolidation insight."""
    msg = GossipMessage(
        gossip_type=GossipType.META_INSIGHT,
        source_project=",".join(source_projects),
        score_delta=confidence,
        payload={
            "insight": insight[:500],
            "source_projects": source_projects,
            "confidence": confidence,
        },
    )
    await broadcast(msg)


# ── Consumer (cherry-pick from ledger) ───────────────────────────────────────

def get_recent_gossip(
    gossip_type: Optional[GossipType] = None,
    tier: Optional[str] = None,
    limit: int = 20,
    since_hours: int = 24,
) -> list[dict]:
    """Pull recent gossip from ledger for cherry-picking."""
    try:
        from ..db.migrations import get_db
        with get_db() as db:
            _ensure_ledger(db)
            cutoff = time.strftime(
                "%Y-%m-%dT%H:%M:%SZ",
                time.gmtime(time.time() - since_hours * 3600),
            )
            q = "SELECT * FROM gossip_ledger WHERE broadcast_at >= ?"
            params: list = [cutoff]
            if gossip_type:
                q += " AND gossip_type = ?"
                params.append(gossip_type.value)
            if tier:
                q += " AND tier = ?"
                params.append(tier)
            q += " ORDER BY score_delta DESC LIMIT ?"
            params.append(limit)
            rows = db.execute(q, params).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["payload"] = json.loads(d.get("payload_json", "{}"))
                result.append(d)
            return result
    except Exception as e:
        log.debug("get_recent_gossip: %s", e)
        return []


def get_gossip_stats() -> dict:
    """Return gossip network analytics."""
    try:
        from ..db.migrations import get_db
        with get_db() as db:
            _ensure_ledger(db)
            total = db.execute("SELECT COUNT(*) as c FROM gossip_ledger").fetchone()["c"]
            by_type = db.execute(
                "SELECT gossip_type, COUNT(*) as c FROM gossip_ledger GROUP BY gossip_type"
            ).fetchall()
            adopted = db.execute(
                "SELECT COUNT(*) as c FROM gossip_ledger WHERE adopted_by != ''"
            ).fetchone()["c"]
            return {
                "total_broadcasts": total,
                "by_type": {r["gossip_type"]: r["c"] for r in by_type},
                "total_adoptions": adopted,
                "adoption_rate": round(adopted / max(total, 1) * 100, 1),
            }
    except Exception as e:
        log.debug("gossip_stats: %s", e)
        return {"total_broadcasts": 0, "by_type": {}, "total_adoptions": 0, "adoption_rate": 0}
