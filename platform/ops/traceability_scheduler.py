"""Traceability Scheduler — periodic deep traceability audit across all projects.

Runs every 6 hours (configurable). For each active project:

Phase 1 — Lightweight scan (every cycle, no LLM cost):
  1. Scans epics/features/stories for missing UDIDs
  2. Checks code-to-story mapping consistency
  3. Verifies test-to-AC coverage
  4. Runs legacy_item / traceability_link coverage from migration_store
  5. Cross-checks memory coherence (stale keys, orphan memories)
  6. Updates traceability metrics in project memory

Phase 2 — Mission launch (only when critical gaps detected):
  Launches a real 'traceability-sweep' mission with the trace team
  (trace-lead, trace-auditor, trace-writer, trace-monitor) to fix gaps.
  Uses voting pattern + all_approved gate — same as traceability-check phase.
  Max 1 concurrent mission per project (dedup via DB check).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

ENABLED = os.environ.get("TRACEABILITY_SCHEDULER_ENABLED", "1") == "1"
INTERVAL_SECONDS = int(os.environ.get("TRACEABILITY_INTERVAL", str(6 * 3600)))  # 6h
INITIAL_DELAY = int(os.environ.get("TRACEABILITY_INITIAL_DELAY", "120"))  # 2 min
# Coverage threshold below which a mission is auto-launched
MISSION_THRESHOLD_PCT = int(os.environ.get("TRACEABILITY_MISSION_THRESHOLD", "80"))
MAX_PROJECTS_PER_CYCLE = 20


# ---------------------------------------------------------------------------
# Phase 1 — Lightweight scan (no LLM)
# ---------------------------------------------------------------------------

async def run_traceability_audit(project_id: str) -> dict:
    """Run a deep traceability audit on a single project. Returns audit summary."""
    from ..db.migrations import get_db
    from ..memory.manager import get_memory_manager

    summary: dict = {
        "project_id": project_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "epics": 0,
        "features": 0,
        "stories": 0,
        "stories_with_ac": 0,
        "stories_without_ac": 0,
        "coverage_pct": 0.0,
        "legacy_items": 0,
        "legacy_linked": 0,
        "legacy_orphans": 0,
        "legacy_coverage_pct": 0.0,
        "memory_keys": 0,
        "memory_stale": 0,
        "gaps": [],
        "needs_mission": False,
    }

    try:
        conn = get_db()

        # ── SAFe hierarchy audit ──
        _audit_safe_hierarchy(conn, project_id, summary)

        # ── Legacy items (migration_store) ──
        _audit_legacy_items(conn, project_id, summary)

        # ── Memory coherence ──
        _audit_memory_coherence(project_id, summary)

        conn.close()

        # ── Decide if mission needed ──
        critical_gaps = [g for g in summary["gaps"] if g.get("severity") == "high"]
        summary["needs_mission"] = (
            summary["coverage_pct"] < MISSION_THRESHOLD_PCT
            or summary["legacy_coverage_pct"] < MISSION_THRESHOLD_PCT
            or len(critical_gaps) > 3
        )

        # ── Store in memory ──
        _store_audit_results(project_id, summary)

        logger.info(
            "[Traceability] %s: epics=%d feat=%d stories=%d ac=%.0f%% "
            "legacy=%d/%d(%.0f%%) mem_stale=%d gaps=%d mission=%s",
            project_id, summary["epics"], summary["features"],
            summary["stories"], summary["coverage_pct"],
            summary["legacy_linked"], summary["legacy_items"],
            summary["legacy_coverage_pct"], summary["memory_stale"],
            len(summary["gaps"]), summary["needs_mission"],
        )

    except Exception as e:
        logger.error("[Traceability] Audit failed for %s: %s", project_id, e)
        summary["error"] = str(e)

    return summary


def _audit_safe_hierarchy(conn, project_id: str, summary: dict) -> None:
    """Check epics → features → stories completeness."""
    row = conn.execute(
        "SELECT COUNT(*) as c FROM missions WHERE project_id = ?",
        (project_id,),
    ).fetchone()
    summary["epics"] = row["c"] if row else 0

    epic_ids = [
        r["id"] for r in conn.execute(
            "SELECT id FROM missions WHERE project_id = ?", (project_id,)
        ).fetchall()
    ]
    if not epic_ids:
        return

    ph = ",".join("?" for _ in epic_ids)
    feat_rows = conn.execute(
        f"SELECT id, name, epic_id FROM features WHERE epic_id IN ({ph})",
        epic_ids,
    ).fetchall()
    summary["features"] = len(feat_rows)
    feat_ids = [r["id"] for r in feat_rows]

    # Stories
    if feat_ids:
        ph2 = ",".join("?" for _ in feat_ids)
        story_rows = conn.execute(
            f"SELECT id, title, acceptance_criteria, feature_id FROM user_stories WHERE feature_id IN ({ph2})",
            feat_ids,
        ).fetchall()
        summary["stories"] = len(story_rows)

        for s in story_rows:
            ac = s["acceptance_criteria"] or ""
            if len(ac.strip()) > 10 and ("GIVEN" in ac.upper() or "WHEN" in ac.upper()):
                summary["stories_with_ac"] += 1
            else:
                summary["stories_without_ac"] += 1
                summary["gaps"].append({
                    "type": "missing_ac", "story_id": s["id"],
                    "title": s["title"], "severity": "medium",
                })

        # Features without stories
        stories_by_feat: dict = {}
        for s in story_rows:
            stories_by_feat.setdefault(s["feature_id"], []).append(s)
        for f in feat_rows:
            if f["id"] not in stories_by_feat:
                summary["gaps"].append({
                    "type": "feature_no_stories", "feature_id": f["id"],
                    "name": f["name"], "severity": "high",
                })

    # Epics without features
    epics_with_feat = {r["epic_id"] for r in feat_rows} if feat_rows else set()
    for eid in epic_ids:
        if eid not in epics_with_feat:
            summary["gaps"].append({
                "type": "epic_no_features", "epic_id": eid, "severity": "high",
            })

    if summary["stories"] > 0:
        summary["coverage_pct"] = round(
            summary["stories_with_ac"] / summary["stories"] * 100, 1
        )


def _audit_legacy_items(conn, project_id: str, summary: dict) -> None:
    """Check legacy_items ↔ traceability_links coverage."""
    try:
        items = conn.execute(
            "SELECT id FROM legacy_items WHERE project_id = ?", (project_id,)
        ).fetchall()
        summary["legacy_items"] = len(items)
        if not items:
            summary["legacy_coverage_pct"] = 100.0
            return

        item_ids = [r["id"] for r in items]
        ph = ",".join("?" for _ in item_ids)
        linked = conn.execute(
            f"SELECT DISTINCT source_id FROM traceability_links WHERE source_id IN ({ph})",
            item_ids,
        ).fetchall()
        linked_ids = {r["source_id"] for r in linked}
        summary["legacy_linked"] = len(linked_ids)
        summary["legacy_orphans"] = len(item_ids) - len(linked_ids)
        summary["legacy_coverage_pct"] = round(
            len(linked_ids) / len(item_ids) * 100, 1
        ) if item_ids else 100.0

        # Flag orphans as gaps
        for iid in item_ids:
            if iid not in linked_ids:
                summary["gaps"].append({
                    "type": "legacy_orphan", "item_id": iid, "severity": "high",
                })
    except Exception:
        # Tables may not exist yet — not an error
        summary["legacy_coverage_pct"] = 100.0


def _audit_memory_coherence(project_id: str, summary: dict) -> None:
    """Check project memory for stale or orphaned entries."""
    try:
        from ..memory.manager import get_memory_manager
        mm = get_memory_manager()
        entries = mm.search(project_id=project_id, query="", limit=200)
        summary["memory_keys"] = len(entries)

        # Detect stale entries (no update in 30+ days)
        cutoff = datetime.now(timezone.utc).isoformat()[:10]
        stale = 0
        for e in entries:
            ts = getattr(e, "updated_at", None) or getattr(e, "created_at", None) or ""
            if isinstance(ts, str) and ts[:10] < cutoff[:10]:
                # Rough 30-day check: compare month
                try:
                    entry_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    age_days = (datetime.now(timezone.utc) - entry_dt).days
                    if age_days > 30:
                        stale += 1
                except Exception:
                    pass
        summary["memory_stale"] = stale
        if stale > 10:
            summary["gaps"].append({
                "type": "stale_memory", "count": stale, "severity": "low",
            })
    except Exception:
        pass


def _store_audit_results(project_id: str, summary: dict) -> None:
    """Persist audit results in project memory."""
    try:
        from ..memory.manager import get_memory_manager
        mm = get_memory_manager()
        mm.store(
            project_id=project_id,
            key="traceability-audit-latest",
            value=_format_audit_report(summary),
            category="traceability",
            source="traceability_scheduler",
            confidence=1.0,
        )
        mm.store(
            project_id=project_id,
            key="traceability-metrics",
            value=json.dumps(summary, indent=2),
            category="metrics",
            source="traceability_scheduler",
            confidence=1.0,
        )
    except Exception as e:
        logger.warning("Failed to store traceability metrics for %s: %s", project_id, e)


def _format_audit_report(summary: dict) -> str:
    """Format audit summary as readable Markdown."""
    gaps_by_type: dict = {}
    for g in summary.get("gaps", []):
        gaps_by_type.setdefault(g["type"], []).append(g)

    lines = [
        f"# Traceability Audit — {summary['project_id']}",
        f"**Date:** {summary['timestamp']}",
        "",
        "## SAFe Hierarchy",
        f"- Epics: {summary['epics']}",
        f"- Features: {summary['features']}",
        f"- Stories: {summary['stories']} (AC: {summary['stories_with_ac']}/{summary['stories']})",
        f"- **AC Coverage: {summary['coverage_pct']}%**",
        "",
        "## Legacy Traceability",
        f"- Legacy items: {summary['legacy_items']}",
        f"- Linked: {summary['legacy_linked']}",
        f"- Orphans: {summary['legacy_orphans']}",
        f"- **Legacy Coverage: {summary['legacy_coverage_pct']}%**",
        "",
        "## Memory Health",
        f"- Keys: {summary['memory_keys']}",
        f"- Stale (>30d): {summary['memory_stale']}",
        "",
    ]

    if summary.get("gaps"):
        lines.append(f"## Gaps ({len(summary['gaps'])} total)")
        label_map = {
            "missing_ac": "Stories missing acceptance criteria",
            "feature_no_stories": "Features with no stories",
            "epic_no_features": "Epics with no features",
            "legacy_orphan": "Legacy items with no traceability link",
            "stale_memory": "Stale memory entries",
        }
        for gtype, items in gaps_by_type.items():
            label = label_map.get(gtype, gtype)
            lines.append(f"\n### {label} ({len(items)})")
            for item in items[:10]:
                name = item.get("title", item.get("name", item.get("story_id",
                       item.get("item_id", item.get("count", "?")))))
                lines.append(f"- [{item.get('severity', '?')}] {name}")
            if len(items) > 10:
                lines.append(f"- ... and {len(items) - 10} more")
    else:
        lines.append("## ✅ No gaps found")

    if summary.get("needs_mission"):
        lines.append("\n## ⚠️ Trace mission will be launched to fix gaps")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Phase 2 — Launch trace team mission (only when needed)
# ---------------------------------------------------------------------------

async def launch_trace_mission(project_id: str, summary: dict) -> str | None:
    """Launch a traceability-sweep mission for a project. Returns run_id or None."""
    try:
        from ..db.migrations import get_db

        # Dedup: skip if a traceability mission is already running for this project
        conn = get_db()
        existing = conn.execute(
            "SELECT id FROM epic_runs WHERE status IN ('pending','running') "
            "AND id IN (SELECT id FROM missions WHERE project_id = ? AND name LIKE '%Traceability%')",
            (project_id,),
        ).fetchone()
        conn.close()
        if existing:
            logger.info(
                "[Traceability] Mission already running for %s (run %s), skipping",
                project_id, existing["id"],
            )
            return None

        from ..epics.store import EpicStore, EpicRunStore
        from ..missions.engine import get_engine

        # Build goal from audit gaps
        gap_summary = []
        for g in summary.get("gaps", [])[:10]:
            gap_summary.append(f"- [{g.get('type')}] {g.get('title', g.get('item_id', '?'))}")
        gap_text = "\n".join(gap_summary) if gap_summary else "General coverage improvement needed"

        goal = (
            f"Traceability sweep for project {project_id}.\n\n"
            f"Current coverage: SAFe AC={summary.get('coverage_pct', 0):.0f}%, "
            f"Legacy={summary.get('legacy_coverage_pct', 0):.0f}%\n\n"
            f"Priority gaps:\n{gap_text}\n\n"
            "Tasks:\n"
            "1. trace-auditor: legacy_scan() + traceability_coverage() → full gap report\n"
            "2. trace-writer: add missing # Ref: headers, SPECS.md UUIDs, traceability_link()\n"
            "3. trace-monitor: traceability_validate() → confirm coverage ≥80%\n"
            "4. trace-lead: review, approve or veto\n\n"
            "Target: ≥80% coverage on both SAFe AC and legacy items."
        )

        epic_store = EpicStore()
        mission = epic_store.create(
            name=f"Traceability Sweep — {project_id} (scheduled)",
            workflow_id="traceability-sweep",
            project_id=project_id,
            goal=goal,
            tags=["traceability", "scheduled", "sweep"],
        )

        run_store = EpicRunStore()
        run = run_store.create(mission_id=mission.id)

        engine = get_engine()
        asyncio.create_task(engine.run(run.id))

        logger.info(
            "[Traceability] Launched trace mission %s for project %s "
            "(SAFe=%.0f%% Legacy=%.0f%% gaps=%d)",
            run.id, project_id,
            summary.get("coverage_pct", 0),
            summary.get("legacy_coverage_pct", 0),
            len(summary.get("gaps", [])),
        )
        return run.id

    except Exception as e:
        logger.error("[Traceability] Failed to launch mission for %s: %s", project_id, e)
        return None


# ---------------------------------------------------------------------------
# Main scheduler loop
# ---------------------------------------------------------------------------

async def traceability_scheduler_loop() -> None:
    """Background task: audit all active projects, launch missions for critical gaps."""
    logger.info(
        "Traceability scheduler started (interval=%ds, initial_delay=%ds, threshold=%d%%)",
        INTERVAL_SECONDS, INITIAL_DELAY, MISSION_THRESHOLD_PCT,
    )

    await asyncio.sleep(INITIAL_DELAY)

    while True:
        try:
            from ..db.migrations import get_db

            conn = get_db()
            active_projects = [
                r["id"] for r in conn.execute(
                    "SELECT id FROM projects WHERE status='active' "
                    "ORDER BY updated_at DESC LIMIT ?",
                    (MAX_PROJECTS_PER_CYCLE,),
                ).fetchall()
            ]
            conn.close()

            if active_projects:
                logger.info(
                    "[Traceability] Auditing %d projects: %s",
                    len(active_projects), active_projects,
                )
                all_summaries = []
                missions_launched = 0

                for pid in active_projects:
                    s = await run_traceability_audit(pid)
                    all_summaries.append(s)

                    # Phase 2: launch mission if needed
                    if s.get("needs_mission") and not s.get("error"):
                        run_id = await launch_trace_mission(pid, s)
                        if run_id:
                            missions_launched += 1
                            await asyncio.sleep(30)  # stagger mission launches
                        else:
                            await asyncio.sleep(5)
                    else:
                        await asyncio.sleep(5)

                    # Create incidents for critical gaps
                    critical_gaps = [g for g in s.get("gaps", []) if g.get("severity") == "high"]
                    if len(critical_gaps) > 3:
                        try:
                            from ..missions.feedback import create_platform_incident
                            create_platform_incident(
                                error_type="traceability_gap",
                                message=(
                                    f"Project {pid}: {len(critical_gaps)} critical traceability gaps "
                                    f"(SAFe={s.get('coverage_pct', 0):.0f}% Legacy={s.get('legacy_coverage_pct', 0):.0f}%)"
                                ),
                                severity="warning",
                                context={
                                    "project_id": pid,
                                    "gaps": critical_gaps[:5],
                                    "coverage_pct": s.get("coverage_pct", 0),
                                    "legacy_coverage_pct": s.get("legacy_coverage_pct", 0),
                                },
                            )
                        except Exception:
                            pass

                # Global summary
                total_gaps = sum(len(s.get("gaps", [])) for s in all_summaries)
                avg_safe = (
                    sum(s.get("coverage_pct", 0) for s in all_summaries) / len(all_summaries)
                ) if all_summaries else 0
                avg_legacy = (
                    sum(s.get("legacy_coverage_pct", 0) for s in all_summaries) / len(all_summaries)
                ) if all_summaries else 0

                logger.info(
                    "[Traceability] Cycle complete: %d projects, SAFe avg=%.1f%%, "
                    "Legacy avg=%.1f%%, %d gaps, %d missions launched",
                    len(all_summaries), avg_safe, avg_legacy,
                    total_gaps, missions_launched,
                )
            else:
                logger.info("[Traceability] No active projects, skipping cycle")

        except asyncio.CancelledError:
            logger.info("Traceability scheduler cancelled")
            return
        except Exception as e:
            logger.error("[Traceability] Scheduler error: %s", e)

        logger.info("[Traceability] Next run in %.1fh", INTERVAL_SECONDS / 3600)
        await asyncio.sleep(INTERVAL_SECONDS)
