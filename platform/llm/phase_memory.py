"""Compact phase memory — telegraphic summaries between mission phases.

After each phase completes, generates a compressed summary and stores it
as a special `phase_summary` message. Subsequent phases load ALL prior
summaries as pre-context, giving agents a compact view of the full mission
history without the token cost of replaying thousands of messages.

Format: telegraphic, abbreviated, no noise. ~100-200 tokens per phase.
"""
# Ref: feat-hybrid-token-opt

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Message type used to tag phase summaries (filterable)
PHASE_SUMMARY_TYPE = "phase_summary"


@dataclass
class PhaseDigest:
    """Compact representation of one completed phase."""
    phase_id: str
    phase_name: str
    pattern: str
    status: str            # done | failed | done_with_issues
    agents: list[str]
    quality: int           # 0-100
    decisions: list[str]   # key decisions extracted
    artifacts: list[str]   # files created/modified
    tools_used: list[str]  # significant tool calls
    duration_s: float


def _extract_decisions(messages: list, max_decisions: int = 5) -> list[str]:
    """Extract key decisions from agent messages (rule-based, no LLM)."""
    decisions = []
    _DECISION_MARKERS = (
        "decision:", "decided:", "conclusion:", "we chose", "selected:",
        "approach:", "strategy:", "architecture:", "design:", "stack:",
        "GO", "NOGO", "approved", "rejected", "veto",
        "créé", "created", "generated", "implemented",
    )
    for msg in reversed(messages):
        content = (getattr(msg, "content", "") or "").strip()
        if not content or len(content) < 30:
            continue
        agent = getattr(msg, "from_agent", "") or ""
        if agent in ("system", "user"):
            continue
        # Check for decision markers
        content_lower = content.lower()
        for marker in _DECISION_MARKERS:
            if marker.lower() in content_lower:
                # Extract the sentence containing the marker
                for line in content.split("\n"):
                    if marker.lower() in line.lower() and len(line.strip()) > 10:
                        clean = line.strip()[:200]
                        if clean not in decisions:
                            decisions.append(clean)
                        break
                break
        if len(decisions) >= max_decisions:
            break
    return decisions


def _extract_artifacts(messages: list) -> list[str]:
    """Extract file paths from tool calls in messages."""
    artifacts = set()
    _FILE_PATTERN = re.compile(r'(?:path|file|filename)["\s:=]+([^\s"\']+\.\w{1,6})')
    _TOOL_PATTERN = re.compile(r'(?:code_write|code_edit|create_file|write_file)\s*\(.*?["\']([^"\']+)["\']')
    for msg in messages:
        content = (getattr(msg, "content", "") or "")
        meta = getattr(msg, "metadata", {}) or {}
        # From tool calls in metadata
        tool_calls = meta.get("tool_calls", [])
        if isinstance(tool_calls, list):
            for tc in tool_calls:
                if isinstance(tc, dict):
                    args = tc.get("arguments", {})
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except Exception:
                            args = {}
                    for key in ("path", "file_path", "filename"):
                        if key in args:
                            artifacts.add(args[key])
        # From content patterns
        for match in _FILE_PATTERN.findall(content):
            if "/" in match or "." in match:
                artifacts.add(match)
        for match in _TOOL_PATTERN.findall(content):
            artifacts.add(match)
    return sorted(artifacts)[:15]  # cap


def _extract_tools(messages: list) -> list[str]:
    """Extract significant tool names used during the phase."""
    tools = set()
    for msg in messages:
        meta = getattr(msg, "metadata", {}) or {}
        tool_calls = meta.get("tool_calls", [])
        if isinstance(tool_calls, list):
            for tc in tool_calls:
                if isinstance(tc, dict):
                    name = tc.get("name", tc.get("function", ""))
                    if name:
                        tools.add(name)
    return sorted(tools)[:10]


def build_phase_digest(
    phase_id: str,
    phase_name: str,
    pattern: str,
    status: str,
    agents: list[str],
    quality: int,
    messages: list,
    duration_s: float = 0.0,
) -> PhaseDigest:
    """Build a compact digest from a completed phase's messages."""
    return PhaseDigest(
        phase_id=phase_id,
        phase_name=phase_name,
        pattern=pattern,
        status=status,
        agents=agents,
        quality=quality,
        decisions=_extract_decisions(messages),
        artifacts=_extract_artifacts(messages),
        tools_used=_extract_tools(messages),
        duration_s=duration_s,
    )


def format_digest_telegraphic(digest: PhaseDigest) -> str:
    """Format a phase digest as a compact telegraphic string.

    Target: ~100-200 tokens. No fluff, abbreviations, pipe-separated.
    """
    parts = [
        f"## P:{digest.phase_id} ({digest.phase_name})",
        f"pattern={digest.pattern} status={digest.status} q={digest.quality}%",
        f"team=[{','.join(digest.agents[:6])}]",
    ]
    if digest.duration_s > 0:
        parts.append(f"dur={digest.duration_s:.0f}s")
    if digest.decisions:
        parts.append("DECISIONS:")
        for d in digest.decisions[:4]:
            parts.append(f"  - {d}")
    if digest.artifacts:
        parts.append(f"FILES: {' | '.join(digest.artifacts[:8])}")
    if digest.tools_used:
        parts.append(f"TOOLS: {','.join(digest.tools_used[:8])}")
    return "\n".join(parts)


def store_phase_summary(
    session_id: str,
    digest: PhaseDigest,
) -> None:
    """Store a compact phase summary as a special message in the session."""
    from ..sessions.store import MessageDef, get_session_store

    summary_text = format_digest_telegraphic(digest)
    msg = MessageDef(
        session_id=session_id,
        from_agent="phase_memory",
        message_type=PHASE_SUMMARY_TYPE,
        content=summary_text,
        metadata={
            "phase_id": digest.phase_id,
            "status": digest.status,
            "quality": digest.quality,
            "agent_count": len(digest.agents),
        },
        priority=10,  # high priority — always loaded
    )
    try:
        get_session_store().add_message(msg)
        logger.warning(
            "PHASE_MEMORY stored phase=%s status=%s q=%d agents=%d tok≈%d",
            digest.phase_id, digest.status, digest.quality,
            len(digest.agents), len(summary_text) // 4,
        )
    except Exception as exc:
        logger.error("PHASE_MEMORY store failed: %s", exc)


def load_phase_summaries(session_id: str) -> list[dict]:
    """Load all phase summaries for a session, ordered chronologically.

    Returns list of dicts compatible with history format:
    [{"from_agent": "phase_memory", "content": "...", "message_type": "phase_summary"}]
    """
    from ..db.migrations import get_db

    db = get_db()
    try:
        rows = db.execute(
            """SELECT from_agent, content, message_type, timestamp
               FROM messages
               WHERE session_id = ? AND message_type = ?
               ORDER BY timestamp ASC""",
            (session_id, PHASE_SUMMARY_TYPE),
        ).fetchall()
        return [
            {
                "from_agent": row[0],
                "content": row[1],
                "message_type": row[2],
            }
            for row in rows
        ]
    except Exception as exc:
        logger.error("PHASE_MEMORY load failed: %s", exc)
        return []
    finally:
        db.close()


def build_compact_context(summaries: list[dict]) -> str:
    """Combine all phase summaries into a single compact context block.

    Injected at the start of agent context so every agent has a
    telegraphic view of all prior phases without replaying full history.
    """
    if not summaries:
        return ""
    header = "# MISSION MEMORY (prior phases — telegraphic)\n"
    body = "\n\n".join(s["content"] for s in summaries)
    return header + body


def backfill_missing_summaries(mission_id: str, session_id: str) -> int:
    """Backfill phase summaries for completed phases that lack one.

    Called on mission resume after server crash — detects phases marked
    'done' in phases_json that have no corresponding phase_summary message.
    Returns count of summaries backfilled.
    """
    from ..db.migrations import get_db

    db = get_db()
    try:
        # Get phases_json for this mission
        row = db.execute(
            "SELECT phases_json FROM epic_runs WHERE id = ?",
            (mission_id,),
        ).fetchone()
        if not row:
            return 0

        phases_json = row[0]
        if isinstance(phases_json, str):
            phases = json.loads(phases_json)
        else:
            phases = phases_json  # already parsed (PG jsonb)

        # Get existing summaries
        existing = set()
        summ_rows = db.execute(
            """SELECT metadata_json FROM messages
               WHERE session_id = ? AND message_type = ?""",
            (session_id, PHASE_SUMMARY_TYPE),
        ).fetchall()
        for sr in summ_rows:
            meta = sr[0]
            if isinstance(meta, str):
                meta = json.loads(meta)
            pid = meta.get("phase_id", "") if isinstance(meta, dict) else ""
            if pid:
                existing.add(pid)

        # Find done phases without summaries
        backfilled = 0
        from ..sessions.store import get_session_store
        ss = get_session_store()
        all_msgs = ss.get_messages(session_id, limit=2000)

        for idx, phase in enumerate(phases):
            status = phase.get("status", "")
            phase_id = phase.get("phase_id", phase.get("id", f"phase-{idx}"))
            if status not in ("done", "done_with_issues"):
                continue
            if phase_id in existing:
                continue

            # Build digest from available data
            agents = phase.get("agents", [])
            if isinstance(agents, str):
                try:
                    agents = json.loads(agents)
                except Exception:
                    agents = []

            digest = build_phase_digest(
                phase_id=phase_id or f"phase-{idx}",
                phase_name=phase.get("phase_name", phase.get("name", phase_id or f"Phase {idx+1}")),
                pattern=phase.get("pattern_id", "unknown"),
                status=status,
                agents=agents if isinstance(agents, list) else [],
                quality=phase.get("quality_score", 0) or 0,
                messages=all_msgs,  # use all messages as fallback
                duration_s=0,
            )
            store_phase_summary(session_id, digest)
            backfilled += 1
            logger.warning(
                "PHASE_MEMORY backfilled phase=%s for mission=%s",
                phase_id, mission_id,
            )

        return backfilled
    except Exception as exc:
        logger.error("PHASE_MEMORY backfill failed: %s", exc)
        return 0
    finally:
        db.close()
