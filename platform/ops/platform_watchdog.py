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
    from ..db.migrations import get_db

    return get_db()


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


def _launch_quality_improvement(
    db, run_id: str, issues: list[str], skill_hints: Optional[list[str]] = None
) -> Optional[str]:
    """Insert a quality-improvement epic_run on the software-factory project."""
    try:
        new_id = uuid.uuid4().hex[:8]
        issues_text = "\n".join(f"- {i}" for i in issues)
        hints_text = ""
        if skill_hints:
            hints_text = (
                "\n## Fichiers SF à corriger (hints)\n"
                + "\n".join(f"- {h}" for h in skill_hints)
                + "\n"
            )
        brief = (
            f"# Platform Quality Issue Detected\n\n"
            f"Source run: {run_id}\n"
            f"Detected at: {datetime.now(timezone.utc).isoformat()}\n\n"
            f"## Issues Found\n{issues_text}\n"
            f"{hints_text}\n"
            f"## Task pour les agents AC (ac-architect + lead_dev)\n"
            f"Analyser et corriger les problèmes détectés dans la SF elle-même:\n"
            f"1. Lire les fichiers concernés: code_read('/app/platform/...') ou deploy/Dockerfile\n"
            f"2. Modifier la SF: code_edit() ou code_write() sur /app/platform/ ou /app/deploy/\n"
            f"3. Valider la correction et commiter\n\n"
            f"⚠️ Ne pas modifier les fichiers projets/workspaces — modifier la plateforme SF.\n"
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
                phases_json, brief, created_at, updated_at, cdp_agent_id)
               VALUES (?, ?, ?, ?, 'paused', 'quality-scan', ?, ?, ?, ?, ?)""",
            (
                new_id,
                QI_WORKFLOW_ID,
                "Platform Quality Loop — Recursive Self-Improvement",
                SF_PROJECT_ID,
                wf_row[0],
                brief,
                now,
                now,
                "plat-cto",  # GPT-5.2-Codex CTO as lead orchestrator
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


def scan_ac_issues() -> list[dict]:
    """Scan active AC cycles for structural issues and report them for quality-improvement.

    Detects problems that require SF-level fixes (missing tools, wrong agents, etc.)
    and returns them so watchdog_cycle() can trigger quality-improvement on the SF.
    """
    db = _get_db()
    issues_found = []
    try:
        rows = db.execute(
            "SELECT project_id, current_run_id, current_cycle FROM ac_project_state WHERE status='running'"
        ).fetchall()
    except Exception as e:
        logger.warning("platform_watchdog: scan_ac_issues failed: %s", e)
        return []

    for row in rows:
        project_id, run_id, cycle = row[0], row[1], row[2]
        if not run_id:
            continue
        issues = []

        # Check workspace for .ts file containing HTML (agent confusion)
        try:
            import glob as _glob

            ts_files = _glob.glob("/app/data/workspaces/*/src/*.ts")
            for ts_path in ts_files:
                try:
                    content = open(ts_path).read(500)
                    if "<!DOCTYPE html" in content or "<html" in content:
                        issues.append(
                            f"AC cycle {project_id} cycle {cycle}: fichier .ts contient du HTML "
                            f"— confusion d'extension dans les agents ac-codex/ac-architect. "
                            f"Fix: renforcer les instructions d'extension dans skills/ac-codex.md."
                        )
                        break
                except Exception:
                    pass
        except Exception:
            pass

        if issues:
            # Use run_id as dedup key so we don't re-trigger for same cycle
            issues_found.append(
                {"run_id": f"ac-{run_id}", "project_id": project_id, "issues": issues}
            )

    return issues_found


# Mapping: escalation reason pattern → (skill file to fix, description)
_ESCALATION_SKILL_MAP = [
    (
        [
            "mentions of calls",
            "No code_write evidence",
            "no code_write",
            "only read files",
        ],
        "/app/skills/ac-codex.md",
        "ac-codex ne produit pas de code_write réel — écrit le texte '[code_write]' au lieu d'appeler l'outil. "
        "Fix: renforcer dans ac-codex.md la règle 'SÉQUENCE OBLIGATOIRE code_write' et ajouter un exemple concret.",
    ),
    (
        ["XXX marker", "placeholder", "XXX"],
        "/app/skills/ac-codex.md",
        "ac-codex produit des marqueurs XXX dans le code. "
        "Fix: ajouter dans ac-codex.md règle 'INTERDIT: XXX, TODO, placeholder dans le code livré'.",
    ),
    (
        ["TOO_SHORT", "26 chars", "25 chars"],
        "/app/skills/ac-architect.md",
        "ac-architect produit une réponse trop courte (< 80 chars) sans écrire INCEPTION.md. "
        "Fix: renforcer dans ac-architect.md la séquence OBLIGATOIRE code_write.",
    ),
    (
        ["No tests written", "test-first", "RED→GREEN→REFACTOR"],
        "/app/skills/ac-codex.md",
        "ac-codex ne suit pas TDD (pas de tests écrits). "
        "Fix: renforcer dans ac-codex.md la séquence obligatoire tests AVANT implémentation.",
    ),
    (
        ["HALLUCINATION", "Claims TDD sprint but no"],
        "/app/skills/ac-codex.md",
        "ac-codex hallucine des tool calls (dit avoir fait TDD sans preuves). "
        "Fix: ajouter dans ac-codex.md 'PREUVE OBLIGATOIRE: code_read après chaque code_write pour afficher le contenu dans l'evidence'.",
    ),
]


def scan_escalated_ac_runs() -> list[dict]:
    """Scan recently escalated AC runs to detect recurring SF skill bugs.

    Maps escalation reasons to specific skill files that need fixing and triggers
    quality-improvement with targeted briefs. Only scans runs escalated in last 2h.
    """
    try:
        from ..web.routes.pages import _ac_get_db, _ac_ensure_tables

        conn = _ac_get_db()
        _ac_ensure_tables(conn)
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        try:
            rows = conn.execute(
                """SELECT project_id, last_escalation_at, current_cycle, last_escalation_reason
                   FROM ac_project_state
                   WHERE status='idle'
                   AND last_escalation_at > ?
                   AND last_escalation_reason IS NOT NULL""",
                (cutoff,),
            ).fetchall()
        except Exception:
            rows = []
        finally:
            conn.close()

        issues_found = []
        seen_skills: set = set()  # deduplicate by skill file per watchdog cycle

        for row in rows:
            project_id = row[0]
            escalation_at = row[1]
            cycle = row[2]
            reason = row[3]

            # Use project_id+escalation_at as dedup key (current_run_id is NULL after escalation)
            run_id = f"{project_id}-{escalation_at}"

            for patterns, skill_file, description in _ESCALATION_SKILL_MAP:
                if any(p.lower() in reason.lower() for p in patterns):
                    if skill_file in seen_skills:
                        continue
                    seen_skills.add(skill_file)
                    issues_found.append(
                        {
                            "run_id": f"escalated-{run_id}",
                            "project_id": project_id,
                            "issues": [
                                f"AC cycle {project_id} cycle {cycle} escaladé: {reason[:200]}",
                                description,
                            ],
                            "skill_hints": [
                                f"code_read('{skill_file}') puis corriger le skill",
                                f"code_write('{skill_file}', contenu_corrigé)",
                            ],
                        }
                    )
                    break  # one issue per run

        if issues_found:
            logger.warning(
                "platform_watchdog: scan_escalated_ac_runs found %d SF skill bug(s)",
                len(issues_found),
            )
        return issues_found

    except Exception as e:
        logger.warning("platform_watchdog: scan_escalated_ac_runs failed: %s", e)
        return []


async def watchdog_cycle():
    """One watchdog cycle: scan → detect → trigger quality-improvement if needed."""
    db = _get_db()
    false_positives = (
        scan_false_completions() + scan_ac_issues() + scan_escalated_ac_runs()
    )

    if not false_positives:
        return

    logger.warning(
        "platform_watchdog: %d false positive(s) detected", len(false_positives)
    )

    for fp in false_positives:
        run_id = fp["run_id"]
        issues = fp["issues"]
        skill_hints = fp.get("skill_hints")

        if _is_already_triggered(db, run_id):
            logger.warning(
                "platform_watchdog: quality-improvement already triggered for %s, skipping",
                run_id,
            )
            continue

        new_run_id = _launch_quality_improvement(
            db, run_id, issues, skill_hints=skill_hints
        )
        if new_run_id:
            logger.warning(
                "platform_watchdog: → quality-improvement %s triggered for run %s",
                new_run_id,
                run_id,
            )


async def resume_stuck_ac_cycles() -> int:
    """Resume AC cycles whose state is 'running' but workflow task is dead (e.g. after restart).

    Called once at startup and periodically by the watchdog loop.
    Returns the number of cycles resumed.
    """
    resumed = 0
    try:
        from ..web.routes.pages import _ac_get_db, _ac_ensure_tables

        def _find_stuck():
            conn = _ac_get_db()
            _ac_ensure_tables(conn)
            try:
                rows = conn.execute(
                    "SELECT project_id, current_run_id, current_cycle, status "
                    "FROM ac_project_state WHERE status='running' AND current_run_id IS NOT NULL"
                ).fetchall()
                # valid_ids = all project_ids that exist in ac_project_state (DB-driven)
                valid = {
                    r["project_id"] if hasattr(r, "__getitem__") else r[0] for r in rows
                }
            except Exception:
                rows = []
                valid = set()
            finally:
                conn.close()
            return rows, valid

        stuck, valid_ids = await asyncio.to_thread(_find_stuck)

        for row in stuck:
            project_id = row["project_id"] if hasattr(row, "__getitem__") else row[0]
            run_id = row["current_run_id"] if hasattr(row, "__getitem__") else row[1]

            if project_id not in valid_ids:
                continue

            # Check if an asyncio task is already running for this session
            from ..web.routes.epics.execution import _active_mission_tasks

            # _active_mission_tasks is keyed by session_id; run_id is the mission/epic id.
            # Check both to avoid duplicate tasks.
            if run_id in _active_mission_tasks:
                continue  # already running

            logger.warning(
                "watchdog: AC cycle stuck — project=%s run=%s → relaunching",
                project_id,
                run_id,
            )

            try:
                from ..missions.store import get_mission_store
                from ..workflows.store import get_workflow_store
                from ..web.routes.epics.execution import (
                    get_mission_semaphore,
                    _active_mission_tasks as _tasks,
                )

                mission = await asyncio.to_thread(
                    get_mission_store().get_mission, run_id
                )
                if not mission or mission.status not in (
                    "active",
                    "running",
                    "planning",
                ):
                    logger.warning(
                        "watchdog: AC run %s has status=%s, skipping resume",
                        run_id,
                        getattr(mission, "status", "?"),
                    )
                    continue

                wf = get_workflow_store().get(
                    mission.workflow_id or "ac-improvement-cycle"
                )
                if not wf:
                    logger.warning("watchdog: workflow not found for run %s", run_id)
                    continue

                # Find existing session_id for this run (config_json has mission_id=run_id)
                session_id = None
                try:
                    from ..db.migrations import get_db as _get_db_wd

                    def _find_session():
                        conn = _get_db_wd()
                        try:
                            row = conn.execute(
                                "SELECT id FROM sessions WHERE config_json LIKE ?"
                                " ORDER BY created_at DESC LIMIT 1",
                                (f'%"mission_id": "{run_id}"%',),
                            ).fetchone()
                            return row["id"] if row else None
                        finally:
                            conn.close()

                    session_id = await asyncio.to_thread(_find_session)
                except Exception:
                    pass

                # If session not found or already in tasks, relaunch via execution path
                if session_id and session_id in _tasks:
                    logger.warning(
                        "watchdog: session %s already running for AC run %s",
                        session_id,
                        run_id,
                    )
                    continue

                if not session_id:
                    # No session exists — replicate launch_mission_workflow logic
                    logger.warning(
                        "watchdog: no session found for AC run %s — launching fresh",
                        run_id,
                    )
                    try:
                        from ..sessions.store import SessionDef, get_session_store
                        from ..epics.store import get_epic_run_store
                        from ..models import EpicRun, EpicStatus, PhaseRun, PhaseStatus
                        from ..config import DATA_DIR
                        import subprocess as _sp

                        task_desc = mission.goal or mission.description or mission.name
                        _sess_store = get_session_store()
                        new_sess = _sess_store.create(
                            SessionDef(
                                name=mission.name,
                                goal=mission.goal or "",
                                project_id=project_id,
                                status="active",
                                config={"workflow_id": wf.id, "mission_id": run_id},
                            )
                        )
                        ws_path = DATA_DIR / "workspaces" / new_sess.id
                        ws_path.mkdir(parents=True, exist_ok=True)
                        _sp.run(["git", "init"], cwd=str(ws_path), capture_output=True)
                        phases = [
                            PhaseRun(
                                phase_id=p.id,
                                phase_name=p.name,
                                pattern_id=p.pattern_id,
                                status=PhaseStatus.PENDING,
                            )
                            for p in wf.phases
                        ]
                        epic_run = EpicRun(
                            id=new_sess.id,
                            workflow_id=wf.id,
                            workflow_name=wf.name,
                            brief=task_desc,
                            status=EpicStatus.PENDING,
                            phases=phases,
                            project_id=project_id,
                            session_id=new_sess.id,
                            parent_epic_id=run_id,
                            workspace_path=str(ws_path),
                        )
                        try:
                            get_epic_run_store().create(epic_run)
                        except Exception:
                            pass

                        async def _guarded_fresh(
                            wf=wf,
                            sid=new_sess.id,
                            desc=task_desc,
                            pid=project_id,
                        ):
                            async with get_mission_semaphore():
                                from ..web.routes.workflows import (
                                    _run_workflow_background,
                                )

                                await _run_workflow_background(wf, sid, desc, pid)

                        ftask = asyncio.create_task(_guarded_fresh())
                        _tasks[new_sess.id] = ftask
                        ftask.add_done_callback(lambda t: _tasks.pop(new_sess.id, None))
                        resumed += 1
                        logger.warning(
                            "watchdog: AC cycle fresh-launched — project=%s new_session=%s run=%s",
                            project_id,
                            new_sess.id,
                            run_id,
                        )
                    except Exception as exc:
                        logger.error(
                            "watchdog: failed to launch AC run %s: %s", run_id, exc
                        )
                    continue

                task_desc = mission.goal or mission.description or mission.name

                async def _guarded(
                    wf=wf, sid=session_id, desc=task_desc, pid=project_id
                ):
                    async with get_mission_semaphore():
                        from ..web.routes.workflows import _run_workflow_background

                        await _run_workflow_background(wf, sid, desc, pid)

                task = asyncio.create_task(_guarded())
                _tasks[session_id] = task
                task.add_done_callback(lambda t: _tasks.pop(session_id, None))
                resumed += 1
                logger.warning(
                    "watchdog: AC cycle resumed — project=%s session=%s run=%s",
                    project_id,
                    session_id,
                    run_id,
                )
                # Stagger concurrent cycles to avoid LLM rate-limit collisions
                await asyncio.sleep(60)
            except Exception as exc:
                logger.error("watchdog: failed to resume AC run %s: %s", run_id, exc)

    except Exception as exc:
        logger.error("watchdog: resume_stuck_ac_cycles failed: %s", exc)

    return resumed


async def platform_watchdog_loop():
    """Background loop: every WATCHDOG_INTERVAL seconds, scan for false completions + resume stuck AC."""
    logger.warning(
        "Platform watchdog loop started (interval=%ds, project=%s, workflow=%s)",
        WATCHDOG_INTERVAL,
        SF_PROJECT_ID,
        QI_WORKFLOW_ID,
    )
    # Wait for server startup hook to register interrupted sessions in _active_mission_tasks
    # before we check — avoids double-resume race condition (startup hook + watchdog both fire).
    await asyncio.sleep(15)
    n = await resume_stuck_ac_cycles()
    if n:
        logger.warning("watchdog: resumed %d stuck AC cycle(s) at startup", n)

    while True:
        await asyncio.sleep(WATCHDOG_INTERVAL)
        try:
            await watchdog_cycle()
        except Exception as e:
            logger.error("platform_watchdog: cycle error: %s", e)
        try:
            await resume_stuck_ac_cycles()
        except Exception as e:
            logger.error("platform_watchdog: ac resume error: %s", e)
