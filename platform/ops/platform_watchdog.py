"""Platform Quality Watchdog — SF recursive self-improvement loop.

Scans recently completed epic_runs for false positives (completed but broken deliverables).
When detected → launches a quality-improvement run on project software-factory.

This is the "câble" that closes the recursive loop:
  Mission completes → watchdog checks evidence → if broken → SF fixes itself

Decisions:
  [v1 2026-03] Minimal câblage: post-hoc evidence scan + launch quality-improvement.
               Only checks runs completed in last 2h to avoid re-scanning old runs.
               One quality-improvement run at a time (dedup by source_run_id in brief).
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

WATCHDOG_INTERVAL = int(os.environ.get("PLATFORM_WATCHDOG_INTERVAL", "300"))  # 5min
SF_PROJECT_ID = "software-factory"
QI_WORKFLOW_ID = "quality-improvement"
ENABLED = bool(int(os.environ.get("PLATFORM_WATCHDOG_ENABLED", "1")))

# Criteria that indicate a false positive completion
_FALSE_POSITIVE_INDICATORS = [
    # TypeScript project without compiled output
    ("*.ts files exist", lambda ws: _has_ts_but_no_dist(ws)),
    # package.json build is a no-op echo
    ("package.json build is no-op", lambda ws: _build_is_noop(ws)),
]


def _get_db():
    from ..database import get_db

    return next(get_db())


def _has_ts_but_no_dist(workspace: str) -> bool:
    """Returns True if workspace has .ts files but no dist/ directory."""
    if not workspace or not os.path.isdir(workspace):
        return False
    import glob

    ts_files = glob.glob(os.path.join(workspace, "**/*.ts"), recursive=True)
    ts_files = [f for f in ts_files if "node_modules" not in f]
    dist_js = glob.glob(os.path.join(workspace, "dist/**/*.js"), recursive=True)
    return bool(ts_files) and not bool(dist_js)


def _build_is_noop(workspace: str) -> bool:
    """Returns True if package.json build script is an echo/no-op."""
    if not workspace or not os.path.isdir(workspace):
        return False
    pkg = os.path.join(workspace, "package.json")
    if not os.path.exists(pkg):
        return False
    try:
        import json

        data = json.load(open(pkg))
        build_cmd = data.get("scripts", {}).get("build", "")
        return "echo" in build_cmd or build_cmd.strip() == ""
    except Exception:
        return False


def _is_already_triggered(db, source_run_id: str) -> bool:
    """Check if a quality-improvement run is already running for this source run."""
    try:
        rows = db.execute(
            """SELECT id FROM epic_runs
               WHERE project_id = ? AND workflow_id = ?
               AND brief LIKE ? AND status NOT IN ('failed','cancelled')""",
            (SF_PROJECT_ID, QI_WORKFLOW_ID, f"%{source_run_id}%"),
        ).fetchall()
        return len(rows) > 0
    except Exception:
        return False


def _launch_quality_improvement(db, run_id: str, issues: list[str]) -> Optional[str]:
    """Insert a quality-improvement epic_run on the software-factory project."""
    try:
        new_id = uuid.uuid4().hex[:8]
        issues_text = "\n".join(f"- {i}" for i in issues)
        brief = (
            f"# Platform Quality Issue Detected\n\n"
            f"Source run: {run_id}\n"
            f"Detected at: {datetime.now(timezone.utc).isoformat()}\n\n"
            f"## Issues Found\n{issues_text}\n\n"
            f"## Task\n"
            f"1. Analyze the root cause in platform/services/evidence.py and/or epic_orchestrator.py\n"
            f"2. Fix the issue (add missing checks, tighten criteria)\n"
            f"3. Run pytest tests/ to validate\n"
            f"4. git commit + push\n"
            f"5. sudo systemctl restart macaron-platform-blue\n"
            f"6. Verify the fix: check that a re-run of similar missions would now fail correctly\n"
        )

        # Get quality-improvement phases
        wf_row = db.execute(
            "SELECT phases_json FROM workflows WHERE id = ?", (QI_WORKFLOW_ID,)
        ).fetchone()
        if not wf_row:
            logger.warning("platform_watchdog: workflow %s not found", QI_WORKFLOW_ID)
            return None

        now = datetime.now(timezone.utc).isoformat()
        db.execute(
            """INSERT INTO epic_runs
               (id, workflow_id, workflow_name, project_id, status, current_phase,
                phases_json, brief, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'paused', 'quality-scan', ?, ?, ?, ?)""",
            (
                new_id,
                QI_WORKFLOW_ID,
                "Quality Improvement Cycle",
                SF_PROJECT_ID,
                wf_row[0],
                brief,
                now,
                now,
            ),
        )
        db.commit()
        logger.warning(
            "platform_watchdog: launched quality-improvement %s for source run %s (issues: %s)",
            new_id,
            run_id,
            issues,
        )
        return new_id
    except Exception as e:
        logger.error("platform_watchdog: failed to launch quality-improvement: %s", e)
        return None


def scan_false_completions() -> list[dict]:
    """Scan recently completed runs for false positive completions."""
    db = _get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()

    try:
        rows = db.execute(
            """SELECT id, project_id, workflow_id, workspace_path, brief
               FROM epic_runs
               WHERE status = 'completed'
               AND updated_at > ?
               AND workflow_id IN ('game-sprint','feature-sprint','tdd-sprint')""",
            (cutoff,),
        ).fetchall()
    except Exception:
        # workspace_path column might not exist — try without it
        try:
            rows = db.execute(
                """SELECT id, project_id, workflow_id, NULL as workspace_path, brief
                   FROM epic_runs
                   WHERE status = 'completed' AND updated_at > ?
                   AND workflow_id IN ('game-sprint','feature-sprint','tdd-sprint')""",
                (cutoff,),
            ).fetchall()
        except Exception as e:
            logger.warning("platform_watchdog: scan failed: %s", e)
            return []

    found = []
    for row in rows:
        run_id, project_id, workflow_id, workspace, brief = row
        issues = []

        if workspace:
            for label, check in _FALSE_POSITIVE_INDICATORS:
                try:
                    if check(workspace):
                        issues.append(label)
                except Exception:
                    pass

        # Also check brief for known red flags
        if brief and "No build step needed" in brief:
            issues.append("brief contains 'No build step needed' (fake build detected)")

        if issues:
            found.append({"run_id": run_id, "project_id": project_id, "issues": issues})

    return found


async def watchdog_cycle():
    """One watchdog cycle: scan → detect → trigger quality-improvement if needed."""
    db = _get_db()
    false_positives = scan_false_completions()

    if not false_positives:
        return

    logger.warning(
        "platform_watchdog: %d false positive(s) detected", len(false_positives)
    )

    for fp in false_positives:
        run_id = fp["run_id"]
        issues = fp["issues"]

        if _is_already_triggered(db, run_id):
            logger.warning(
                "platform_watchdog: quality-improvement already triggered for %s, skipping",
                run_id,
            )
            continue

        new_run_id = _launch_quality_improvement(db, run_id, issues)
        if new_run_id:
            logger.warning(
                "platform_watchdog: → quality-improvement %s triggered for run %s",
                new_run_id,
                run_id,
            )


async def platform_watchdog_loop():
    """Background loop: every WATCHDOG_INTERVAL seconds, scan for false completions."""
    logger.warning(
        "Platform watchdog loop started (interval=%ds, project=%s, workflow=%s)",
        WATCHDOG_INTERVAL,
        SF_PROJECT_ID,
        QI_WORKFLOW_ID,
    )
    while True:
        await asyncio.sleep(WATCHDOG_INTERVAL)
        try:
            await watchdog_cycle()
        except Exception as e:
            logger.error("platform_watchdog: cycle error: %s", e)
