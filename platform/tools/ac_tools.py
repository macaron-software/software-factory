"""
AC Tools — Amélioration Continue tool implementations.
=======================================================
Tools for AC cycle recording, project state, and experiment tracking.
These replace the http_post calls described in AC skill files.
"""
# Ref: feat-quality

from __future__ import annotations

import json
import logging
import time

from ..models import AgentInstance
from .registry import BaseTool

logger = logging.getLogger(__name__)


def _ac_conn():
    """Get DB connection (SQLite or PG via adapter)."""
    from ..db.migrations import get_db

    return get_db()


def _is_pg(conn) -> bool:
    try:
        from ..db.adapter import is_postgresql

        return is_postgresql()
    except Exception:
        return False


def _ensure_ac_tables(conn) -> None:
    """Idempotent: create AC tables if not present."""
    pg = _is_pg(conn)
    serial = "SERIAL" if pg else "INTEGER"
    auto = "" if pg else "AUTOINCREMENT"

    stmts = [
        f"""CREATE TABLE IF NOT EXISTS ac_cycles (
            id {serial} PRIMARY KEY {auto}, project_id TEXT NOT NULL, cycle_num INTEGER NOT NULL,
            git_sha TEXT, platform_run_id TEXT, status TEXT DEFAULT 'pending',
            phase_scores TEXT DEFAULT '{{}}', total_score INTEGER DEFAULT 0,
            defect_count INTEGER DEFAULT 0, fix_commit TEXT, fix_summary TEXT,
            adversarial_scores TEXT DEFAULT '{{}}', traceability_score INTEGER DEFAULT 0,
            veto_count INTEGER DEFAULT 0, rl_reward REAL DEFAULT 0,
            rolled_back INTEGER DEFAULT 0, screenshot_path TEXT,
            started_at TEXT, completed_at TEXT, UNIQUE(project_id, cycle_num))""",
        """CREATE TABLE IF NOT EXISTS ac_project_state (
            project_id TEXT PRIMARY KEY, current_cycle INTEGER DEFAULT 0,
            status TEXT DEFAULT 'idle', current_run_id TEXT,
            total_score_avg REAL DEFAULT 0, last_git_sha TEXT,
            ci_status TEXT DEFAULT 'unknown', convergence_status TEXT DEFAULT 'cold_start',
            next_cycle_hint TEXT, started_at TEXT, updated_at TEXT)""",
    ]
    for stmt in stmts:
        try:
            conn.execute(stmt)
        except Exception:
            pass
    # Idempotent ALTER TABLEs
    alters = [
        "ALTER TABLE ac_cycles ADD COLUMN veto_count INTEGER DEFAULT 0",
        "ALTER TABLE ac_cycles ADD COLUMN rl_reward REAL DEFAULT 0",
        "ALTER TABLE ac_cycles ADD COLUMN rolled_back INTEGER DEFAULT 0",
        "ALTER TABLE ac_cycles ADD COLUMN screenshot_path TEXT",
        "ALTER TABLE ac_project_state ADD COLUMN next_cycle_hint TEXT",
        "ALTER TABLE ac_project_state ADD COLUMN convergence_status TEXT DEFAULT 'cold_start'",
        "ALTER TABLE ac_project_state ADD COLUMN current_run_id TEXT",
    ]
    for stmt in alters:
        try:
            conn.execute(stmt)
        except Exception:
            pass
    try:
        conn.commit()
    except Exception:
        pass


class AcInjectCycleTool(BaseTool):
    """
    Record a completed AC cycle in the database.

    Called by ac-cicd-agent at the end of each AC cycle.
    Replaces the http_post to /api/improvement/inject-cycle.

    Required params:
      project_id    — e.g. "ac-hello-html"
      cycle_num     — cycle number (integer)
      total_score   — overall score 0-100
      status        — "completed" | "failed"

    Optional params:
      git_sha               — git commit SHA of the workspace
      phase_scores          — dict {inception:X, tdd-sprint:X, adversarial:X, qa-sprint:X, cicd:X}
      defect_count          — number of defects found
      veto_count            — number of adversarial VETOs
      fix_summary           — short description of fixes
      adversarial_scores    — dict of adversarial dimension scores
      traceability_score    — traceability score 0-100
      screenshot_path       — relative path to screenshot in workspace
      platform_run_id       — mission/session ID for traceability
    """

    name = "ac_inject_cycle"
    description = (
        "Record a completed AC improvement cycle in the database. "
        "Call this at the end of the CI/CD phase with all cycle scores."
    )
    category = "ac"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        project_id = str(params.get("project_id", "")).strip()
        cycle_num = params.get("cycle_num")
        if not project_id or cycle_num is None:
            return json.dumps({"error": "project_id and cycle_num are required"})

        try:
            cycle_num = int(cycle_num)
        except (TypeError, ValueError):
            return json.dumps({"error": f"cycle_num must be integer, got: {cycle_num}"})

        total_score = int(params.get("total_score", 0))
        status = str(params.get("status", "completed"))
        git_sha = str(params.get("git_sha", ""))
        platform_run_id = str(
            params.get("platform_run_id", f"ac-{project_id}-{cycle_num}")
        )
        defect_count = int(params.get("defect_count", 0))
        veto_count = int(params.get("veto_count", 0))
        fix_summary = str(params.get("fix_summary", ""))
        screenshot_path = str(params.get("screenshot_path", ""))
        traceability_score = int(params.get("traceability_score", 0))

        phase_scores = params.get("phase_scores", {})
        if isinstance(phase_scores, str):
            try:
                phase_scores = json.loads(phase_scores)
            except Exception:
                phase_scores = {}

        adversarial_scores = params.get("adversarial_scores", {})
        if isinstance(adversarial_scores, str):
            try:
                adversarial_scores = json.loads(adversarial_scores)
            except Exception:
                adversarial_scores = {}

        now = time.strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            conn = _ac_conn()
            _ensure_ac_tables(conn)
            pg = _is_pg(conn)

            if pg:
                conn.execute(
                    """INSERT INTO ac_cycles
                       (project_id, cycle_num, git_sha, platform_run_id, status,
                        phase_scores, total_score, defect_count, veto_count, fix_summary,
                        adversarial_scores, traceability_score, screenshot_path,
                        started_at, completed_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT(project_id, cycle_num) DO UPDATE SET
                         git_sha=EXCLUDED.git_sha, status=EXCLUDED.status,
                         phase_scores=EXCLUDED.phase_scores,
                         total_score=EXCLUDED.total_score,
                         defect_count=EXCLUDED.defect_count,
                         veto_count=EXCLUDED.veto_count,
                         fix_summary=EXCLUDED.fix_summary,
                         adversarial_scores=EXCLUDED.adversarial_scores,
                         traceability_score=EXCLUDED.traceability_score,
                         screenshot_path=COALESCE(NULLIF(EXCLUDED.screenshot_path,''), ac_cycles.screenshot_path),
                         completed_at=EXCLUDED.completed_at""",
                    (
                        project_id,
                        cycle_num,
                        git_sha,
                        platform_run_id,
                        status,
                        json.dumps(phase_scores),
                        total_score,
                        defect_count,
                        veto_count,
                        fix_summary,
                        json.dumps(adversarial_scores),
                        traceability_score,
                        screenshot_path,
                        now,
                        now,
                    ),
                )
            else:
                conn.execute(
                    """INSERT INTO ac_cycles
                       (project_id, cycle_num, git_sha, platform_run_id, status,
                        phase_scores, total_score, defect_count, veto_count, fix_summary,
                        adversarial_scores, traceability_score, screenshot_path,
                        started_at, completed_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(project_id, cycle_num) DO UPDATE SET
                         git_sha=excluded.git_sha, status=excluded.status,
                         phase_scores=excluded.phase_scores,
                         total_score=excluded.total_score,
                         defect_count=excluded.defect_count,
                         veto_count=excluded.veto_count,
                         fix_summary=excluded.fix_summary,
                         adversarial_scores=excluded.adversarial_scores,
                         traceability_score=excluded.traceability_score,
                         screenshot_path=COALESCE(NULLIF(excluded.screenshot_path,''), ac_cycles.screenshot_path),
                         completed_at=excluded.completed_at""",
                    (
                        project_id,
                        cycle_num,
                        git_sha,
                        platform_run_id,
                        status,
                        json.dumps(phase_scores),
                        total_score,
                        defect_count,
                        veto_count,
                        fix_summary,
                        json.dumps(adversarial_scores),
                        traceability_score,
                        screenshot_path,
                        now,
                        now,
                    ),
                )
            conn.commit()

            # Update project state
            try:
                if pg:
                    conn.execute(
                        """INSERT INTO ac_project_state
                           (project_id, current_cycle, status, last_git_sha, ci_status,
                            total_score_avg, updated_at)
                           VALUES (%s,%s,%s,%s,%s,%s,%s)
                           ON CONFLICT(project_id) DO UPDATE SET
                             current_cycle=GREATEST(ac_project_state.current_cycle, EXCLUDED.current_cycle),
                             last_git_sha=EXCLUDED.last_git_sha,
                             ci_status=EXCLUDED.ci_status,
                             total_score_avg=EXCLUDED.total_score_avg,
                             updated_at=EXCLUDED.updated_at""",
                        (
                            project_id,
                            cycle_num,
                            "idle",
                            git_sha,
                            "green" if status == "completed" else "red",
                            float(total_score),
                            now,
                        ),
                    )
                else:
                    conn.execute(
                        """INSERT INTO ac_project_state
                           (project_id, current_cycle, status, last_git_sha, ci_status,
                            total_score_avg, updated_at)
                           VALUES (?,?,?,?,?,?,?)
                           ON CONFLICT(project_id) DO UPDATE SET
                             current_cycle=MAX(current_cycle, excluded.current_cycle),
                             last_git_sha=excluded.last_git_sha,
                             ci_status=excluded.ci_status,
                             total_score_avg=excluded.total_score_avg,
                             updated_at=excluded.updated_at""",
                        (
                            project_id,
                            cycle_num,
                            "idle",
                            git_sha,
                            "green" if status == "completed" else "red",
                            float(total_score),
                            now,
                        ),
                    )
                conn.commit()
            except Exception as e:
                logger.warning("ac_project_state update failed: %s", e)

            logger.info(
                "ac_inject_cycle: project=%s cycle=%d score=%d status=%s",
                project_id,
                cycle_num,
                total_score,
                status,
            )
            return json.dumps(
                {
                    "ok": True,
                    "project_id": project_id,
                    "cycle_num": cycle_num,
                    "total_score": total_score,
                    "status": status,
                    "recorded_at": now,
                }
            )
        except Exception as e:
            logger.error("ac_inject_cycle error: %s", e)
            return json.dumps(
                {"error": str(e), "project_id": project_id, "cycle_num": cycle_num}
            )


class AcGetProjectStateTool(BaseTool):
    """
    Get the current state and score history for an AC project.

    Params:
      project_id — e.g. "ac-hello-html"
      last_n     — number of recent cycles to return (default 5)
    """

    name = "ac_get_project_state"
    description = (
        "Get current state and recent cycle scores for an AC improvement project. "
        "Use to read convergence status, last scores, and RL hints."
    )
    category = "ac"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        project_id = str(params.get("project_id", "")).strip()
        last_n = int(params.get("last_n", 5))
        if not project_id:
            return json.dumps({"error": "project_id required"})

        try:
            conn = _ac_conn()
            _ensure_ac_tables(conn)
            pg = _is_pg(conn)
            ph = "%s" if pg else "?"

            state_row = conn.execute(
                f"SELECT * FROM ac_project_state WHERE project_id={ph}",
                (project_id,),
            ).fetchone()

            cycles = conn.execute(
                f"SELECT cycle_num, total_score, status, git_sha, defect_count, veto_count,"
                f" completed_at FROM ac_cycles"
                f" WHERE project_id={ph} ORDER BY cycle_num DESC LIMIT {ph}",
                (project_id, last_n),
            ).fetchall()

            state = dict(state_row) if state_row else {}
            cycles_list = [dict(r) for r in cycles] if cycles else []

            return json.dumps(
                {
                    "project_id": project_id,
                    "state": state,
                    "recent_cycles": cycles_list,
                },
                default=str,
            )
        except Exception as e:
            logger.error("ac_get_project_state error: %s", e)
            return json.dumps({"error": str(e), "project_id": project_id})


def register_ac_tools(registry) -> None:
    """Register all AC tools into the tool registry."""
    for cls in (AcInjectCycleTool, AcGetProjectStateTool):
        registry.register(cls())
