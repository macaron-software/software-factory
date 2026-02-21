"""Auto-Heal Engine — incident → epic → TMA workflow pipeline.

Scans platform_incidents for unresolved errors, groups them into epics,
and launches the TMA (Tierce Maintenance Applicative) workflow to auto-fix.

Architecture:
  1. Periodic scan (every 60s) for open incidents without mission_id
  2. Group by error_type + source → create 1 epic per error family
  3. Launch TMA workflow (diagnose → fix → verify → close)
  4. Track resolution: mission completed → incident resolved

Can run as:
  - In-process asyncio task (server lifespan)
  - Standalone cron: python3 -m platform.ops.auto_heal --once
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────

SCAN_INTERVAL = int(os.environ.get("AUTOHEAL_INTERVAL", "60"))  # seconds
SEVERITY_THRESHOLD = os.environ.get("AUTOHEAL_SEVERITY", "P3")  # P0,P1,P2,P3
MAX_CONCURRENT_HEALS = int(os.environ.get("AUTOHEAL_MAX_CONCURRENT", "3"))
ENABLED = os.environ.get("AUTOHEAL_ENABLED", "1") == "1"

# Severity ordering for filtering
_SEV_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}

# Workflow ID for TMA missions
TMA_WORKFLOW_ID = "tma-autoheal"
TMA_PROJECT_ID = "macaron-platform"


@dataclass
class IncidentGroup:
    """A group of related incidents to heal as one epic."""
    error_type: str
    error_detail_sample: str
    incident_ids: list[str]
    count: int
    severity: str
    source: str


def _get_db():
    """Get DB connection (works both in-process and standalone)."""
    try:
        from ..db.migrations import get_db
        return get_db()
    except (ImportError, ValueError):
        # Standalone mode — direct SQLite
        import sqlite3
        from pathlib import Path
        db_path = Path(__file__).parent.parent.parent / "data" / "platform.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn


def scan_open_incidents() -> list[IncidentGroup]:
    """Find open incidents not yet linked to a mission, grouped by error family."""
    db = _get_db()
    try:
        sev_cutoff = _SEV_ORDER.get(SEVERITY_THRESHOLD, 3)
        rows = db.execute(
            """SELECT id, error_type, error_detail, severity, source
               FROM platform_incidents
               WHERE status = 'open'
                 AND (mission_id IS NULL OR mission_id = '')
               ORDER BY created_at DESC
               LIMIT 100""",
        ).fetchall()

        # Group by error_type (e.g., "500", "timeout", "llm_failure")
        groups: dict[str, IncidentGroup] = {}
        for r in rows:
            sev = r["severity"] or "P3"
            if _SEV_ORDER.get(sev, 3) > sev_cutoff:
                continue
            key = r["error_type"] or "unknown"
            if key not in groups:
                groups[key] = IncidentGroup(
                    error_type=key,
                    error_detail_sample=(r["error_detail"] or "")[:200],
                    incident_ids=[],
                    count=0,
                    severity=sev,
                    source=r["source"] or "auto",
                )
            groups[key].incident_ids.append(r["id"])
            groups[key].count += 1
            # Escalate to highest severity in group
            if _SEV_ORDER.get(sev, 3) < _SEV_ORDER.get(groups[key].severity, 3):
                groups[key].severity = sev

        return list(groups.values())
    finally:
        db.close()


def create_heal_epic(group: IncidentGroup) -> str:
    """Create a mission (epic) for an incident group. Returns mission_id."""
    from ..missions.store import get_mission_store, MissionDef

    mission_store = get_mission_store()

    # Check if there's already an active TMA mission for this error type
    db = _get_db()
    try:
        existing = db.execute(
            """SELECT id FROM missions
               WHERE type = 'bug' AND status IN ('planning', 'active')
                 AND name LIKE ?
               LIMIT 1""",
            (f"[TMA] {group.error_type}%",),
        ).fetchone()
        if existing:
            mission_id = existing["id"]
            # Link new incidents to existing mission
            _link_incidents_to_mission(db, group.incident_ids, mission_id)
            logger.info("Auto-heal: linked %d incidents to existing mission %s",
                       group.count, mission_id)
            return mission_id
    finally:
        db.close()

    # Create new TMA epic
    mission = MissionDef(
        project_id=TMA_PROJECT_ID,
        name=f"[TMA] {group.error_type} — {group.count} incidents",
        description=(
            f"Auto-generated TMA epic for {group.count} incidents.\n"
            f"Error type: {group.error_type}\n"
            f"Sample: {group.error_detail_sample}\n"
            f"Severity: {group.severity}\n"
            f"Incident IDs: {', '.join(group.incident_ids[:10])}"
        ),
        goal=(
            f"Diagnose and fix error '{group.error_type}'. "
            f"Sample error: {group.error_detail_sample}. "
            f"Validate fix does not introduce regressions."
        ),
        status="active",
        type="bug",
        workflow_id=TMA_WORKFLOW_ID,
        wsjf_score=_sev_to_wsjf(group.severity),
        created_by="auto-heal",
        kanban_status="implementing",
        config={
            "autoheal": True,
            "error_type": group.error_type,
            "incident_count": group.count,
            "incident_ids": group.incident_ids[:20],
        },
    )
    mission = mission_store.create_mission(mission)

    # Link incidents to the new mission
    db = _get_db()
    try:
        _link_incidents_to_mission(db, group.incident_ids, mission.id)
    finally:
        db.close()

    logger.warning("Auto-heal: created TMA epic %s for %d incidents (%s)",
                  mission.id, group.count, group.error_type)
    return mission.id


def _link_incidents_to_mission(db, incident_ids: list[str], mission_id: str):
    """Link incidents to a mission by setting mission_id."""
    for iid in incident_ids:
        db.execute(
            "UPDATE platform_incidents SET mission_id = ?, status = 'investigating' WHERE id = ?",
            (mission_id, iid),
        )
    db.commit()


def _sev_to_wsjf(sev: str) -> float:
    """Convert severity to WSJF score for prioritization."""
    return {"P0": 100.0, "P1": 50.0, "P2": 20.0, "P3": 5.0}.get(sev, 5.0)


async def launch_tma_workflow(mission_id: str) -> Optional[str]:
    """Launch the TMA workflow for a mission. Returns session_id."""
    from ..missions.store import get_mission_store
    from ..workflows.store import get_workflow_store
    from ..sessions.store import get_session_store, SessionDef

    mission_store = get_mission_store()
    wf_store = get_workflow_store()
    session_store = get_session_store()

    mission = mission_store.get_mission(mission_id)
    if not mission:
        logger.error("Auto-heal: mission %s not found", mission_id)
        return None

    # Skip if there's already an active/planning session for this mission
    db = _get_db()
    try:
        existing = db.execute(
            """SELECT id FROM sessions
               WHERE name LIKE ? AND status IN ('planning', 'active')
               LIMIT 1""",
            (f"%{mission_id[:8]}%",),
        ).fetchone()
        if not existing:
            # Check by config_json containing mission_id
            existing = db.execute(
                """SELECT id FROM sessions
                   WHERE config_json LIKE ? AND status IN ('planning', 'active')
                   LIMIT 1""",
                (f"%{mission_id}%",),
            ).fetchone()
        if existing:
            logger.info("Auto-heal: session %s already active for mission %s, skipping",
                       existing["id"], mission_id)
            return existing["id"]
    finally:
        db.close()

    wf = wf_store.get(TMA_WORKFLOW_ID)
    if not wf:
        logger.warning("Auto-heal: TMA workflow '%s' not found, using sf-pipeline fallback",
                      TMA_WORKFLOW_ID)
        wf = wf_store.get("sf-pipeline")
        if not wf:
            logger.error("Auto-heal: no workflow available for TMA")
            return None

    # Create session for the workflow
    session = SessionDef(
        name=f"[Auto-Heal] {mission.name}",
        goal=mission.goal,
        project_id=mission.project_id,
        config={"workflow_id": wf.id, "mission_id": mission_id, "autoheal": True},
    )
    session = session_store.create(session)

    # Launch workflow in background
    from ..web.routes.workflows import _run_workflow_background
    asyncio.create_task(_run_workflow_background(
        wf, session.id, mission.goal, mission.project_id or "",
    ))

    logger.warning("Auto-heal: launched TMA workflow session=%s for mission=%s",
                  session.id, mission_id)
    return session.id


async def resolve_completed_missions():
    """Check for completed TMA missions and resolve their incidents."""
    db = _get_db()
    try:
        # Find completed TMA missions
        rows = db.execute(
            """SELECT m.id as mission_id, m.status
               FROM missions m
               WHERE m.type = 'bug' AND m.created_by = 'auto-heal'
                 AND m.status IN ('completed', 'failed')
                 AND EXISTS (
                     SELECT 1 FROM platform_incidents i
                     WHERE i.mission_id = m.id AND i.status = 'investigating'
                 )""",
        ).fetchall()

        for r in rows:
            new_status = "resolved" if r["status"] == "completed" else "open"
            resolution = "Auto-healed by TMA workflow" if new_status == "resolved" else ""
            db.execute(
                """UPDATE platform_incidents
                   SET status = ?, resolution = ?, resolved_at = ?
                   WHERE mission_id = ? AND status = 'investigating'""",
                (new_status, resolution, datetime.now(timezone.utc).isoformat(),
                 r["mission_id"]),
            )
        if rows:
            db.commit()
            logger.info("Auto-heal: resolved incidents for %d completed missions", len(rows))
    finally:
        db.close()


# ── Active heal tracking ─────────────────────────────────────────────

_active_heals: set[str] = set()  # mission_ids currently running


async def heal_cycle():
    """One scan-create-launch cycle."""
    global _active_heals

    # 1. Resolve completed missions first
    await resolve_completed_missions()

    # 2. Rebuild active heals from DB (survives restart)
    db = _get_db()
    try:
        rows = db.execute(
            "SELECT id FROM missions WHERE created_by='auto-heal' AND status='active'"
        ).fetchall()
        _active_heals = {r["id"] for r in rows}
    finally:
        db.close()

    # 3. Scan for new incidents
    groups = scan_open_incidents()
    if not groups:
        return

    logger.info("Auto-heal: found %d incident groups (%d active heals)",
               len(groups), len(_active_heals))

    # 4. Create epics and launch workflows (respect concurrency limit)
    for group in sorted(groups, key=lambda g: _SEV_ORDER.get(g.severity, 3)):
        if len(_active_heals) >= MAX_CONCURRENT_HEALS:
            logger.info("Auto-heal: max concurrent heals reached (%d), deferring",
                       MAX_CONCURRENT_HEALS)
            break

        mission_id = create_heal_epic(group)

        if mission_id not in _active_heals:
            session_id = await launch_tma_workflow(mission_id)
            if session_id:
                _active_heals.add(mission_id)


async def auto_heal_loop():
    """Background loop: scan incidents → create epics → launch TMA workflows."""
    logger.info("Auto-heal loop started (interval=%ds, severity≥%s, max_concurrent=%d)",
               SCAN_INTERVAL, SEVERITY_THRESHOLD, MAX_CONCURRENT_HEALS)
    while True:
        await asyncio.sleep(SCAN_INTERVAL)
        if not ENABLED:
            continue
        try:
            await heal_cycle()
        except Exception as e:
            logger.error("Auto-heal cycle error: %s", e, exc_info=True)


# ── Stats ─────────────────────────────────────────────────────────────

def get_autoheal_stats() -> dict:
    """Return auto-heal statistics."""
    db = _get_db()
    try:
        total = db.execute(
            "SELECT COUNT(*) as n FROM missions WHERE created_by='auto-heal'"
        ).fetchone()["n"]
        active = db.execute(
            "SELECT COUNT(*) as n FROM missions WHERE created_by='auto-heal' AND status='active'"
        ).fetchone()["n"]
        completed = db.execute(
            "SELECT COUNT(*) as n FROM missions WHERE created_by='auto-heal' AND status='completed'"
        ).fetchone()["n"]
        failed = db.execute(
            "SELECT COUNT(*) as n FROM missions WHERE created_by='auto-heal' AND status='failed'"
        ).fetchone()["n"]
        open_incidents = db.execute(
            "SELECT COUNT(*) as n FROM platform_incidents WHERE status='open'"
        ).fetchone()["n"]
        investigating = db.execute(
            "SELECT COUNT(*) as n FROM platform_incidents WHERE status='investigating'"
        ).fetchone()["n"]
        resolved = db.execute(
            "SELECT COUNT(*) as n FROM platform_incidents WHERE status='resolved'"
        ).fetchone()["n"]
        return {
            "enabled": ENABLED,
            "interval_s": SCAN_INTERVAL,
            "severity_threshold": SEVERITY_THRESHOLD,
            "max_concurrent": MAX_CONCURRENT_HEALS,
            "missions": {"total": total, "active": active, "completed": completed, "failed": failed},
            "incidents": {"open": open_incidents, "investigating": investigating, "resolved": resolved},
            "active_heals": len(_active_heals),
        }
    finally:
        db.close()


# ── CLI entry point ──────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent.parent))

    parser = argparse.ArgumentParser(description="Auto-Heal Engine")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--stats", action="store_true", help="Show stats and exit")
    args = parser.parse_args()

    if args.stats:
        import pprint
        pprint.pprint(get_autoheal_stats())
    elif args.once:
        asyncio.run(heal_cycle())
        print("✅ Auto-heal cycle completed")
    else:
        print(f"Auto-heal loop (interval={SCAN_INTERVAL}s)")
        asyncio.run(auto_heal_loop())
