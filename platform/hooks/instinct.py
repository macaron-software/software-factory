"""Instinct Observer — automatic pattern extraction from agent sessions → skills.

SOURCE: ECC continuous-learning-v2 (https://github.com/affaan-m/everything-claude-code/tree/main/skills/continuous-learning-v2)
WHY: ECC's instinct system is the most valuable concept: instead of manually curating skills,
     agents automatically learn atomic behaviors ("instincts") from observed tool call patterns.
     Each instinct has: trigger, action, confidence score (0.3–0.9), domain tag, project scope.
     Instincts can later be "evolved" into formal skill YAML definitions.

ADAPTATION: ECC uses CLI-level hooks (PreToolUse/PostToolUse JSON stdin/stdout). We adapted it
     for server-side: observations flow through our HookContext.all_tool_calls at SESSION_END.
     Project scoping uses ctx.project_id. Confidence is incremented on repeated observations.

CONFIDENCE TIERS (from ECC):
    0.3 = tentative (seen once or single evidence)
    0.5 = developing (2-3 observations)
    0.7 = established (4-5 observations, pattern clear)
    0.9 = near-certain (6+ observations, no counter-evidence)

PATTERN TYPES DETECTED:
    1. Repeated tool sequences — e.g., always code_read before code_write
    2. Error corrections — tool call followed by a retry with different args
    3. Workflow clusters — same 3+ tools appearing together in same session
"""
# Ref: feat-memory

from __future__ import annotations

import json
import logging
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Path where evolved skill YAMLs are written to disk
# Resolved relative to this file: platform/hooks/ → platform/ → skills/definitions/
_SKILLS_DIR = Path(__file__).parent.parent / "skills" / "definitions"

# Minimum number of tool calls in a session before we bother analyzing
_MIN_TOOL_CALLS = 6

# Minimum repeat count for a pair/sequence to become an instinct
_MIN_PATTERN_REPEAT = 2

# Domain assignment heuristics — tool name → domain
_TOOL_DOMAINS = {
    "code_write": "coding",
    "code_edit": "coding",
    "code_read": "coding",
    "list_files": "navigation",
    "code_search": "navigation",
    "git_commit": "git",
    "git_diff": "git",
    "git_log": "git",
    "git_status": "git",
    "build": "build",
    "test": "testing",
    "lint": "testing",
    "docker_build": "devops",
    "docker_deploy": "devops",
    "memory_write": "memory",
    "memory_read": "memory",
    "browser_screenshot": "ui",
    "playwright_test": "testing",
}


@dataclass
class ObservedPattern:
    trigger: str  # "when X tool is called"
    action: str  # "always Y before/after"
    domain: str
    confidence: float
    evidence: list[dict] = field(default_factory=list)


def analyze_session(
    all_tool_calls: list[dict],
    agent_id: str,
    project_id: str,
    session_id: str,
) -> list[ObservedPattern]:
    """Analyze a session's tool calls and extract recurring patterns.

    Returns a list of ObservedPattern candidates. The caller persists them to DB.
    """
    if len(all_tool_calls) < _MIN_TOOL_CALLS:
        return []

    patterns: list[ObservedPattern] = []
    names = [t.get("name", "") for t in all_tool_calls]

    # Pattern 1: Bigram sequences (tool A followed by tool B)
    bigrams: Counter = Counter()
    for i in range(len(names) - 1):
        bigrams[(names[i], names[i + 1])] += 1
    for (a, b), count in bigrams.items():
        if count >= _MIN_PATTERN_REPEAT and a != b:
            domain = _TOOL_DOMAINS.get(a, _TOOL_DOMAINS.get(b, "workflow"))
            patterns.append(
                ObservedPattern(
                    trigger=f"when using {a}",
                    action=f"follow with {b} (seen {count}× this session)",
                    domain=domain,
                    confidence=_confidence(count),
                    evidence=[
                        {"session": session_id[:8], "count": count, "pair": f"{a}→{b}"}
                    ],
                )
            )

    # Pattern 2: Most-used tool (dominant workflow)
    counts = Counter(names)
    top_name, top_count = counts.most_common(1)[0]
    if top_count >= 4 and top_count >= len(names) * 0.3:
        domain = _TOOL_DOMAINS.get(top_name, "workflow")
        patterns.append(
            ObservedPattern(
                trigger=f"in {domain} sessions",
                action=f"rely heavily on {top_name} ({top_count}/{len(names)} calls)",
                domain=domain,
                confidence=_confidence(top_count),
                evidence=[
                    {
                        "session": session_id[:8],
                        "dominant": top_name,
                        "count": top_count,
                    }
                ],
            )
        )

    # Pattern 3: Read-before-write (common best practice detection)
    reads = {"code_read", "list_files", "code_search", "file_search"}
    writes = {"code_write", "code_edit", "write_file"}
    rw_pairs = 0
    for i, tc in enumerate(all_tool_calls):
        if tc.get("name") in writes and i > 0:
            window = [t.get("name") for t in all_tool_calls[max(0, i - 3) : i]]
            if any(r in window for r in reads):
                rw_pairs += 1
    if rw_pairs >= 2:
        patterns.append(
            ObservedPattern(
                trigger="before editing code",
                action=f"read/search first ({rw_pairs}× read-before-write pattern in session)",
                domain="coding",
                confidence=_confidence(rw_pairs + 1),
                evidence=[{"session": session_id[:8], "rw_pairs": rw_pairs}],
            )
        )

    return patterns[:5]  # cap at 5 patterns per session


def _confidence(count: int) -> float:
    """Convert observation count to ECC-style confidence score."""
    if count <= 1:
        return 0.3
    if count <= 3:
        return 0.5
    if count <= 5:
        return 0.7
    return 0.9


def upsert_instinct(
    pattern: ObservedPattern,
    agent_id: str,
    project_id: str,
    session_id: str,
) -> str:
    """Insert or update an instinct in the DB. Returns instinct ID.

    WHY upsert: same pattern observed across multiple sessions should increase confidence
    (up to 0.9 cap). This mirrors ECC's confidence evolution model.
    """
    try:
        from ..db.migrations import get_db

        with get_db() as db:
            # Check if a matching instinct exists (same agent + trigger + action prefix)
            existing = db.execute(
                """SELECT id, confidence, evidence_json FROM instincts
                   WHERE agent_id = ? AND trigger = ? AND action LIKE ?""",
                (agent_id, pattern.trigger, pattern.action[:30] + "%"),
            ).fetchone()

            if existing:
                # Boost confidence (cap at 0.9)
                new_conf = min(0.9, existing["confidence"] + 0.1)
                old_evidence = json.loads(existing["evidence_json"] or "[]")
                new_evidence = (old_evidence + pattern.evidence)[-10:]  # keep last 10
                db.execute(
                    """UPDATE instincts SET confidence=?, evidence_json=?,
                       updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')
                       WHERE id=?""",
                    (new_conf, json.dumps(new_evidence), existing["id"]),
                )
                return existing["id"]
            else:
                rid = str(uuid.uuid4())
                db.execute(
                    """INSERT INTO instincts
                       (id, agent_id, project_id, trigger, action, confidence, domain, scope,
                        evidence_json, source)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (
                        rid,
                        agent_id,
                        project_id or "",
                        pattern.trigger,
                        pattern.action,
                        pattern.confidence,
                        pattern.domain,
                        "project" if project_id else "global",
                        json.dumps(pattern.evidence),
                        "session-observation",
                    ),
                )
                return rid
    except Exception as exc:
        logger.warning("instinct upsert error: %s", exc)
        return ""


async def observe_session(
    all_tool_calls: list[dict],
    agent_id: str,
    project_id: str,
    session_id: str,
) -> int:
    """Main entry point: analyze session and persist new/updated instincts.

    Returns number of instincts created/updated.
    """
    if not all_tool_calls or len(all_tool_calls) < _MIN_TOOL_CALLS:
        return 0

    # Log raw observation for audit trail
    _log_observation(all_tool_calls, agent_id, project_id, session_id)

    patterns = analyze_session(all_tool_calls, agent_id, project_id, session_id)
    count = 0
    for p in patterns:
        rid = upsert_instinct(p, agent_id, project_id, session_id)
        if rid:
            count += 1
            logger.debug(
                "instinct %s: [%s] trigger=%r conf=%.1f",
                rid[:8],
                p.domain,
                p.trigger,
                p.confidence,
            )

    # After accumulating instincts, check if any project-scoped ones can be promoted
    # SOURCE: ECC instinct promotion — fire asynchronously so it doesn't block the session
    if count > 0:
        try:
            promoted = promote_global_instincts()
            if promoted:
                logger.info(
                    "observe_session: promoted %d instincts to global scope", promoted
                )
        except Exception:
            pass

    return count


def _log_observation(
    all_tool_calls: list[dict], agent_id: str, project_id: str, session_id: str
) -> None:
    """Persist a raw observation row for future reanalysis."""
    try:
        from ..db.migrations import get_db

        summary = Counter(t.get("name", "") for t in all_tool_calls)
        with get_db() as db:
            db.execute(
                """INSERT OR IGNORE INTO instinct_observations
                   (id, agent_id, session_id, project_id, tool_name, args_json, outcome)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    str(uuid.uuid4()),
                    agent_id,
                    session_id or "",
                    project_id or "",
                    "session_summary",
                    json.dumps(dict(summary.most_common(10))),
                    f"{len(all_tool_calls)} tool calls",
                ),
            )
    except Exception:
        pass


def evolve_instincts(
    agent_id: str, project_id: str = "", min_confidence: float = 0.6
) -> dict:
    """Cluster high-confidence instincts into a skill definition.

    SOURCE: ECC /evolve command
    WHY: High-confidence instincts (≥0.6) that share a domain are clustered
         into a formal skill YAML that can be loaded by the agent at runtime.

    Returns: {"skill_id": ..., "yaml": ..., "instinct_ids": [...]}
    """
    try:
        from ..db.migrations import get_db

        with get_db() as db:
            rows = db.execute(
                """SELECT id, trigger, action, domain, confidence FROM instincts
                   WHERE agent_id = ? AND confidence >= ? AND evolved_into IS NULL
                   ORDER BY confidence DESC LIMIT 20""",
                (agent_id, min_confidence),
            ).fetchall()

        if not rows:
            return {"error": "No instincts meeting confidence threshold"}

        # Group by domain
        by_domain: dict[str, list] = defaultdict(list)
        for r in rows:
            by_domain[r["domain"]].append(r)

        # Pick the richest domain
        best_domain = max(by_domain, key=lambda d: len(by_domain[d]))
        cluster = by_domain[best_domain]

        skill_id = f"evolved-{best_domain}-{agent_id[:8]}"
        behaviors = "\n".join(
            f"- **{r['trigger']}**: {r['action']} (confidence: {r['confidence']:.1f})"
            for r in cluster
        )
        skill_yaml = f"""name: {skill_id}
description: "Auto-evolved from {len(cluster)} instincts in domain '{best_domain}' for agent {agent_id}. Source: instinct-observer (ECC-inspired)."
origin: instinct-observer
confidence: {sum(r["confidence"] for r in cluster) / len(cluster):.2f}
domain: {best_domain}
agent_id: {agent_id}
project_id: {project_id or "global"}

behaviors:
{behaviors}

# Evolved from instincts: {", ".join(r["id"][:8] for r in cluster)}
# SOURCE: platform/hooks/instinct.py (ECC continuous-learning-v2 adaptation)
"""
        # Mark instincts as evolved
        try:
            from ..db.migrations import get_db

            with get_db() as db:
                for r in cluster:
                    db.execute(
                        "UPDATE instincts SET evolved_into=? WHERE id=?",
                        (skill_id, r["id"]),
                    )
        except Exception:
            pass

        # Write YAML to disk so it can be loaded by the agent at runtime
        # SOURCE: ECC /evolve — persists skills to skills/ directory
        yaml_path: Path | None = None
        try:
            _SKILLS_DIR.mkdir(parents=True, exist_ok=True)
            yaml_path = _SKILLS_DIR / f"{skill_id}.yaml"
            yaml_path.write_text(skill_yaml, encoding="utf-8")
            logger.info("evolve_instincts: wrote %s", yaml_path)
        except Exception as write_err:
            logger.warning("evolve_instincts: could not write YAML: %s", write_err)

        return {
            "skill_id": skill_id,
            "domain": best_domain,
            "yaml": skill_yaml,
            "yaml_path": str(yaml_path) if yaml_path else None,
            "instinct_count": len(cluster),
            "instinct_ids": [r["id"] for r in cluster],
        }
    except Exception as exc:
        logger.error("evolve_instincts error: %s", exc)
        return {"error": str(exc)}


def promote_global_instincts(min_projects: int = 2, min_confidence: float = 0.7) -> int:
    """Promote project-scoped instincts to global when seen in multiple projects.

    SOURCE: ECC instinct promotion logic
    WHY: If the same trigger→action pattern appears across 2+ distinct projects
         with high confidence, it's a universal agent behavior worth globalising.

    Returns: count of instincts promoted.
    """
    try:
        from ..db.migrations import get_db

        with get_db() as db:
            # Find trigger→action pairs that appear in 2+ distinct projects
            candidates = db.execute(
                """SELECT trigger, action, domain, agent_id,
                          COUNT(DISTINCT project_id) as project_count,
                          AVG(confidence) as avg_conf
                   FROM instincts
                   WHERE scope = 'project' AND confidence >= ? AND project_id IS NOT NULL AND project_id != ''
                   GROUP BY trigger, action, agent_id
                   HAVING project_count >= ?""",
                (min_confidence, min_projects),
            ).fetchall()

            if not candidates:
                return 0

            promoted = 0
            for row in candidates:
                # Upsert a global-scope instinct (one per agent + trigger)
                global_id = f"global-{row['agent_id'] or 'any'}-{uuid.uuid4().hex[:8]}"
                existing = db.execute(
                    "SELECT id FROM instincts WHERE trigger=? AND agent_id=? AND scope='global'",
                    (row["trigger"], row["agent_id"]),
                ).fetchone()
                if existing:
                    db.execute(
                        "UPDATE instincts SET confidence=MIN(0.9, confidence+0.05), "
                        "updated_at=NOW() WHERE id=?",
                        (existing["id"],),
                    )
                else:
                    db.execute(
                        """INSERT INTO instincts
                           (id, agent_id, project_id, trigger, action, confidence, domain, scope, source)
                           VALUES (?,?,NULL,?,?,?,?,'global','promotion')""",
                        (
                            global_id,
                            row["agent_id"],
                            row["trigger"],
                            row["action"],
                            min(0.9, float(row["avg_conf"]) + 0.05),
                            row["domain"],
                        ),
                    )
                    promoted += 1
            db.commit()
            if promoted:
                logger.info("promote_global_instincts: promoted %d instincts", promoted)
            return promoted
    except Exception as exc:
        logger.error("promote_global_instincts error: %s", exc)
        return 0
