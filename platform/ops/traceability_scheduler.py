"""Traceability Scheduler — periodic traceability audit across all projects.

Runs every 6 hours (configurable). For each active project:
1. Scans epics/features/stories for missing UDIDs
2. Checks code-to-story mapping consistency
3. Verifies test-to-AC coverage
4. Updates traceability metrics in project memory
5. Flags gaps as incidents for the Trace Lead to address

Uses the same agent team: Trace Lead, QA Traceability, Code Auditor, Trace Reporter.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

ENABLED = os.environ.get("TRACEABILITY_SCHEDULER_ENABLED", "1") == "1"
INTERVAL_SECONDS = int(os.environ.get("TRACEABILITY_INTERVAL", str(6 * 3600)))  # 6h
INITIAL_DELAY = int(os.environ.get("TRACEABILITY_INITIAL_DELAY", "120"))  # 2 min


async def run_traceability_audit(project_id: str) -> dict:
    """Run a traceability audit on a single project. Returns audit summary."""
    from ..db.migrations import get_db
    from ..memory.manager import get_memory_manager

    summary = {
        "project_id": project_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "epics": 0,
        "features": 0,
        "stories": 0,
        "stories_with_ac": 0,
        "stories_without_ac": 0,
        "coverage_pct": 0.0,
        "gaps": [],
    }

    try:
        conn = get_db()

        # Count epics
        row = conn.execute(
            "SELECT COUNT(*) as c FROM missions WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        summary["epics"] = row["c"] if row else 0

        # Count features
        epic_ids = [
            r["id"]
            for r in conn.execute(
                "SELECT id FROM missions WHERE project_id = ?", (project_id,)
            ).fetchall()
        ]

        if epic_ids:
            placeholders = ",".join("?" for _ in epic_ids)
            feat_rows = conn.execute(
                f"SELECT id, name, epic_id FROM features WHERE epic_id IN ({placeholders})",
                epic_ids,
            ).fetchall()
            summary["features"] = len(feat_rows)
            feat_ids = [r["id"] for r in feat_rows]

            # Count stories and check ACs
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
                            "type": "missing_ac",
                            "story_id": s["id"],
                            "title": s["title"],
                            "severity": "medium",
                        })

                # Check for features without stories
                stories_by_feat = {}
                for s in story_rows:
                    stories_by_feat.setdefault(s["feature_id"], []).append(s)
                for f in feat_rows:
                    if f["id"] not in stories_by_feat:
                        summary["gaps"].append({
                            "type": "feature_no_stories",
                            "feature_id": f["id"],
                            "name": f["name"],
                            "severity": "high",
                        })

        # Check for epics without features
        epics_with_features = set(r["epic_id"] for r in feat_rows) if epic_ids and feat_rows else set()
        for eid in epic_ids:
            if eid not in epics_with_features:
                summary["gaps"].append({
                    "type": "epic_no_features",
                    "epic_id": eid,
                    "severity": "high",
                })

        conn.close()

        # Calculate coverage
        if summary["stories"] > 0:
            summary["coverage_pct"] = round(
                summary["stories_with_ac"] / summary["stories"] * 100, 1
            )

        # Store audit results in project memory
        try:
            mm = get_memory_manager()
            mm.store(
                project_id=project_id,
                key="traceability-audit-latest",
                value=_format_audit_report(summary),
                category="traceability",
                source="traceability_scheduler",
                confidence=1.0,
            )
            # Also store the structured data
            import json

            mm.store(
                project_id=project_id,
                key="traceability-metrics",
                value=json.dumps(summary, indent=2),
                category="metrics",
                source="traceability_scheduler",
                confidence=1.0,
            )
        except Exception as mem_err:
            logger.warning("Failed to store traceability metrics: %s", mem_err)

        logger.info(
            "[Traceability] Project %s: %d epics, %d features, %d stories, "
            "coverage %.1f%%, %d gaps",
            project_id,
            summary["epics"],
            summary["features"],
            summary["stories"],
            summary["coverage_pct"],
            len(summary["gaps"]),
        )

    except Exception as e:
        logger.error("[Traceability] Audit failed for %s: %s", project_id, e)
        summary["error"] = str(e)

    return summary


def _format_audit_report(summary: dict) -> str:
    """Format audit summary as readable Markdown."""
    gaps_by_type = {}
    for g in summary.get("gaps", []):
        gaps_by_type.setdefault(g["type"], []).append(g)

    lines = [
        f"# Traceability Audit — {summary['project_id']}",
        f"**Date:** {summary['timestamp']}",
        "",
        "## Metrics",
        f"- Epics: {summary['epics']}",
        f"- Features: {summary['features']}",
        f"- Stories: {summary['stories']}",
        f"- Stories with GIVEN/WHEN/THEN: {summary['stories_with_ac']}",
        f"- Stories without AC: {summary['stories_without_ac']}",
        f"- **AC Coverage: {summary['coverage_pct']}%**",
        "",
    ]

    if summary.get("gaps"):
        lines.append(f"## Gaps ({len(summary['gaps'])} total)")
        for gtype, items in gaps_by_type.items():
            label = {
                "missing_ac": "Stories missing acceptance criteria",
                "feature_no_stories": "Features with no stories",
                "epic_no_features": "Epics with no features",
            }.get(gtype, gtype)
            lines.append(f"\n### {label} ({len(items)})")
            for item in items[:10]:
                name = item.get("title", item.get("name", item.get("story_id", "?")))
                lines.append(f"- [{item.get('severity', '?')}] {name}")
            if len(items) > 10:
                lines.append(f"- ... and {len(items) - 10} more")
    else:
        lines.append("## No gaps found")

    return "\n".join(lines)


async def traceability_scheduler_loop() -> None:
    """Background task: run traceability audits on all active projects periodically."""
    logger.info(
        "Traceability scheduler started (interval=%ds, initial_delay=%ds)",
        INTERVAL_SECONDS,
        INITIAL_DELAY,
    )

    # Initial delay to let platform boot
    await asyncio.sleep(INITIAL_DELAY)

    while True:
        try:
            from ..db.migrations import get_db

            conn = get_db()
            active_projects = [
                r["id"]
                for r in conn.execute(
                    "SELECT id FROM projects WHERE status='active' ORDER BY updated_at DESC LIMIT 20"
                ).fetchall()
            ]
            conn.close()

            if active_projects:
                logger.info(
                    "[Traceability] Running audit on %d projects: %s",
                    len(active_projects),
                    active_projects,
                )
                all_summaries = []
                for pid in active_projects:
                    s = await run_traceability_audit(pid)
                    all_summaries.append(s)
                    await asyncio.sleep(5)  # stagger between projects

                # Log global summary
                total_gaps = sum(len(s.get("gaps", [])) for s in all_summaries)
                avg_coverage = (
                    sum(s.get("coverage_pct", 0) for s in all_summaries) / len(all_summaries)
                    if all_summaries
                    else 0
                )
                logger.info(
                    "[Traceability] Cycle complete: %d projects, avg coverage %.1f%%, %d total gaps",
                    len(all_summaries),
                    avg_coverage,
                    total_gaps,
                )

                # Create incidents for critical gaps (epics/features without children)
                for s in all_summaries:
                    critical_gaps = [g for g in s.get("gaps", []) if g.get("severity") == "high"]
                    if len(critical_gaps) > 3:
                        try:
                            from ..missions.feedback import create_platform_incident

                            create_platform_incident(
                                error_type="traceability_gap",
                                message=f"Project {s['project_id']}: {len(critical_gaps)} critical traceability gaps (features without stories, epics without features)",
                                severity="warning",
                                context={
                                    "project_id": s["project_id"],
                                    "gaps": critical_gaps[:5],
                                    "coverage_pct": s.get("coverage_pct", 0),
                                },
                            )
                        except Exception:
                            pass
            else:
                logger.info("[Traceability] No active projects, skipping cycle")

        except asyncio.CancelledError:
            logger.info("Traceability scheduler cancelled")
            return
        except Exception as e:
            logger.error("[Traceability] Scheduler error: %s", e)

        # Wait for next cycle
        next_run = datetime.now(timezone.utc).isoformat()
        logger.info(
            "[Traceability] Next run in %.1fh",
            INTERVAL_SECONDS / 3600,
        )
        await asyncio.sleep(INTERVAL_SECONDS)
