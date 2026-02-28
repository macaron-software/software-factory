"""Workflow store and engine — chains patterns into multi-phase pipelines.

A Workflow is a sequence of phases. Each phase runs a pattern.
Phases can have gates (conditions to proceed) and shared context.
The RTE (Release Train Engineer) agent facilitates transitions via LLM.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Optional

from ..db.migrations import get_db
from ..patterns.store import get_pattern_store
from ..patterns.engine import run_pattern, _push_sse
from ..sessions.store import get_session_store, MessageDef

logger = logging.getLogger(__name__)


@dataclass
class WorkflowPhase:
    """A single phase in a workflow."""

    id: str = ""
    pattern_id: str = ""
    name: str = ""
    description: str = ""
    gate: str = ""  # "all_approved", "no_veto", "always", "best_effort"
    config: dict = field(default_factory=dict)
    retry_count: int = 1  # max retries on failure (0 = no retry)
    skip_on_failure: bool = False  # skip phase after all retries exhausted
    timeout: int = 0  # per-phase timeout override (0 = use global default)


@dataclass
class WorkflowDef:
    """A workflow definition — ordered list of phases."""

    id: str = ""
    name: str = ""
    description: str = ""
    phases: list[WorkflowPhase] = field(default_factory=list)
    config: dict = field(default_factory=dict)
    icon: str = "workflow"
    is_builtin: bool = False
    created_at: str = ""


@dataclass
class WorkflowRun:
    """Runtime state of a workflow execution."""

    workflow: WorkflowDef
    session_id: str
    project_id: str = ""
    current_phase: int = 0
    phase_results: list[dict] = field(default_factory=list)
    status: str = "running"  # running, completed, failed, gated
    error: str = ""


class WorkflowStore:
    """CRUD for workflow definitions."""

    def _ensure_table(self):
        conn = get_db()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS workflows (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                phases_json TEXT DEFAULT '[]',
                config_json TEXT DEFAULT '{}',
                icon TEXT DEFAULT 'workflow',
                is_builtin INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()
        conn.close()

    def list_all(self) -> list[WorkflowDef]:
        from ..cache import get as cache_get, put as cache_put

        cached = cache_get("workflows:all")
        if cached is not None:
            return cached
        self._ensure_table()
        conn = get_db()
        rows = conn.execute("SELECT * FROM workflows ORDER BY created_at").fetchall()
        conn.close()
        result = [self._row_to_wf(r) for r in rows]
        cache_put("workflows:all", result, ttl=120)
        return result

    def get(self, wf_id: str) -> Optional[WorkflowDef]:
        self._ensure_table()
        conn = get_db()
        row = conn.execute("SELECT * FROM workflows WHERE id=?", (wf_id,)).fetchone()
        conn.close()
        return self._row_to_wf(row) if row else None

    def create(self, wf: WorkflowDef) -> WorkflowDef:
        self._ensure_table()
        if not wf.id:
            wf.id = uuid.uuid4().hex[:8]
        conn = get_db()
        conn.execute(
            "INSERT OR REPLACE INTO workflows (id, name, description, phases_json, config_json, icon, is_builtin) VALUES (?,?,?,?,?,?,?)",
            (
                wf.id,
                wf.name,
                wf.description,
                json.dumps(
                    [
                        {
                            "id": p.id,
                            "pattern_id": p.pattern_id,
                            "name": p.name,
                            "description": p.description,
                            "gate": p.gate,
                            "config": p.config,
                        }
                        for p in wf.phases
                    ]
                ),
                json.dumps(wf.config),
                wf.icon,
                int(wf.is_builtin),
            ),
        )
        conn.commit()
        conn.close()
        return wf

    def delete(self, wf_id: str):
        conn = get_db()
        conn.execute("DELETE FROM workflows WHERE id=?", (wf_id,))
        conn.commit()
        conn.close()

    def count(self) -> int:
        self._ensure_table()
        conn = get_db()
        c = conn.execute("SELECT COUNT(*) FROM workflows").fetchone()[0]
        conn.close()
        return c

    def seed_builtins(self):
        """Seed pre-built workflow templates (upserts all builtins)."""
        from .builtins import get_builtin_workflows

        builtins = get_builtin_workflows()
        for w in builtins:
            self.create(w)  # INSERT OR REPLACE

    def _row_to_wf(self, row) -> WorkflowDef:
        phases_data = json.loads(row["phases_json"] or "[]")
        return WorkflowDef(
            id=row["id"],
            name=row["name"],
            description=row["description"] or "",
            phases=[WorkflowPhase(**p) for p in phases_data],
            config=json.loads(row["config_json"] or "{}"),
            icon=row["icon"] or "workflow",
            is_builtin=bool(row["is_builtin"]),
            created_at=row["created_at"] or "",
        )


_store: Optional[WorkflowStore] = None


def get_workflow_store() -> WorkflowStore:
    global _store
    if _store is None:
        _store = WorkflowStore()
        _store.seed_builtins()
    return _store


# ── RTE Facilitator ──────────────────────────────────────────────

_RTE_AGENT_ID = "release_train_engineer"


async def _rte_facilitate(
    session_id: str,
    prompt: str,
    to_agent: str = "",
    project_id: str = "",
) -> str:
    """Call the RTE agent via LLM to facilitate a workflow transition.
    Returns the RTE's message content."""
    from ..agents.store import get_agent_store
    from ..agents.executor import get_executor, ExecutionContext

    store = get_session_store()
    agent_store = get_agent_store()
    rte = agent_store.get(_RTE_AGENT_ID)
    if not rte:
        # Fallback to system message if RTE agent not found
        store.add_message(
            MessageDef(
                session_id=session_id,
                from_agent="system",
                to_agent=to_agent or "all",
                message_type="system",
                content=prompt,
            )
        )
        return prompt

    # Push thinking status
    await _push_sse(
        session_id,
        {
            "type": "agent_status",
            "agent_id": rte.id,
            "status": "thinking",
        },
    )

    ctx = ExecutionContext(
        agent=rte,
        session_id=session_id,
        project_id=project_id,
        tools_enabled=False,  # RTE doesn't need tools, just speaks
    )

    # Stream the RTE response via SSE
    await _push_sse(
        session_id,
        {
            "type": "stream_start",
            "agent_id": rte.id,
            "agent_name": rte.name,
            "node_id": rte.id,
            "pattern_type": "workflow",
            "to_agent": to_agent or "all",
            "flow_step": "Facilitation",
            "iteration": 0,
        },
    )

    executor = get_executor()
    accumulated = ""
    try:
        async for kind, value in executor.run_streaming(ctx, prompt):
            if kind == "delta" and value:
                accumulated += value
                await _push_sse(
                    session_id,
                    {
                        "type": "stream_delta",
                        "agent_id": rte.id,
                        "delta": value,
                    },
                )
            elif kind == "result":
                accumulated = value.content or accumulated
    except Exception as e:
        logger.error("RTE streaming failed: %s", e)
        # Fallback to non-streaming
        result = await executor.run(ctx, prompt)
        accumulated = result.content

    await _push_sse(
        session_id,
        {
            "type": "stream_end",
            "agent_id": rte.id,
            "content": accumulated,
            "message_type": "text",
            "to_agent": to_agent or "all",
        },
    )

    msg = MessageDef(
        session_id=session_id,
        from_agent=rte.id,
        to_agent=to_agent or "all",
        message_type="text",
        content=accumulated,
    )
    store.add_message(msg)
    await _push_sse(
        session_id,
        {
            "type": "agent_status",
            "agent_id": rte.id,
            "status": "idle",
        },
    )

    return accumulated


def _save_checkpoint(store, session_id: str, completed_phase: int):
    """Save workflow progress to session config for resume."""
    try:
        sess = store.get(session_id)
        if sess:
            config = sess.config or {}
            config["workflow_checkpoint"] = completed_phase
            store.update_config(session_id, config)
    except Exception as e:
        logger.debug("Checkpoint save failed for %s: %s", session_id, e)


def _sync_phase_done_to_mission_run(session_id: str, phase_index: int):
    """Mark phase at phase_index as 'done' in mission_runs.phases_json for this session.

    Keeps phases_json in sync with the workflow engine's session-checkpoint so that
    the orchestrator resume path can skip completed phases correctly.
    """
    try:
        import json as _json

        from ..db.migrations import get_db as _get_db

        _db = _get_db()
        try:
            row = _db.execute(
                "SELECT id, phases_json FROM mission_runs WHERE session_id=? ORDER BY created_at DESC LIMIT 1",
                (session_id,),
            ).fetchone()
            if not row:
                return
            phases = _json.loads(row[1] or "[]")
            if phase_index < len(phases):
                ph = phases[phase_index]
                if ph.get("status") not in ("done", "done_with_issues", "skipped"):
                    ph["status"] = "done"
                    _db.execute(
                        "UPDATE mission_runs SET phases_json=? WHERE id=?",
                        (_json.dumps(phases, default=str), row[0]),
                    )
                    _db.commit()
        finally:
            _db.close()
    except Exception as e:
        logger.debug(
            "_sync_phase_done_to_mission_run failed for session %s idx %d: %s",
            session_id,
            phase_index,
            e,
        )


def _is_transient_error(error_str: str) -> bool:
    """Check if an error is transient (rate limit, timeout, connection)."""
    return any(
        k in error_str.lower()
        for k in ("429", "rate", "timeout", "connection", "temporarily", "overloaded")
    )


def _reset_stuck_phases(store, session_id: str):
    """Reset phases stuck at 'running' → 'pending' for resumed workflows."""
    try:
        from ..db.migrations import get_db

        db = get_db()
        rows = db.execute(
            "SELECT id, phases_json FROM mission_runs WHERE session_id=? AND phases_json LIKE '%\"running\"%'",
            (session_id,),
        ).fetchall()
        for row in rows:
            import json as _json

            phases = _json.loads(row[1] or "[]")
            fixed = False
            for ph in phases:
                if ph.get("status") == "running":
                    ph["status"] = "pending"
                    ph["summary"] = (
                        ph.get("summary") or ""
                    ) + " [auto-reset on resume]"
                    fixed = True
            if fixed:
                db.execute(
                    "UPDATE mission_runs SET phases_json=? WHERE id=?",
                    (_json.dumps(phases, default=str), row[0]),
                )
        db.commit()
        db.close()
    except Exception as e:
        logger.debug("Reset stuck phases failed for %s: %s", session_id, e)


def _capture_last_agent_summary(store, session_id: str, phase_name: str) -> str:
    """Capture last agent message as error context for failed phases."""
    try:
        last_msgs = store.get_messages(session_id, limit=3)
        for m in reversed(last_msgs):
            if m.from_agent not in ("system", "user", _RTE_AGENT_ID) and m.content:
                snippet = (m.content or "")[:200].replace("\n", " ")
                return f"Dernier message ({m.from_agent}): {snippet}"
    except Exception:
        pass
    return ""


# ── Sandbox Build Validation ─────────────────────────────────────────

_CODE_PHASE_KEYWORDS = (
    "code",
    "develop",
    "implement",
    "feature",
    "tdd",
    "fix",
    "refactor",
    "security fix",
    "hotfix",
    "scaffold",
    "migration",
)


def _is_code_phase(phase_name: str) -> bool:
    """Detect if a phase involves code generation."""
    name_lower = phase_name.lower()
    return any(kw in name_lower for kw in _CODE_PHASE_KEYWORDS)


async def _sandbox_build_check(project_id: str, session_id: str) -> tuple[bool, str]:
    """Run build/lint in project workspace. Returns (success, error_output)."""
    try:
        from ..db.migrations import get_db as _gdb

        db = _gdb()
        row = db.execute(
            "SELECT workspace_path FROM mission_runs WHERE session_id=? LIMIT 1",
            (session_id,),
        ).fetchone()
        db.close()

        workspace = row[0] if row and row[0] else ""
        if not workspace:
            # Try project workspace
            db = _gdb()
            row = db.execute(
                "SELECT config_json FROM projects WHERE id=? LIMIT 1", (project_id,)
            ).fetchone()
            db.close()
            if row:
                import json as _json

                config = _json.loads(row[0] or "{}")
                workspace = config.get("workspace_path", config.get("path", ""))

        if not workspace:
            return True, ""  # No workspace — skip validation

        import os

        if not os.path.isdir(workspace):
            return True, ""  # Workspace doesn't exist yet

        # Detect build system and run appropriate command
        build_cmd = _detect_build_cmd(workspace)
        if not build_cmd:
            return True, ""

        proc = await asyncio.create_subprocess_exec(
            *build_cmd,
            cwd=workspace,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        except asyncio.TimeoutError:
            proc.kill()
            return False, "Build timed out after 120s"

        if proc.returncode != 0:
            error_output = (stderr or stdout or b"").decode("utf-8", errors="replace")
            return False, error_output[-1000:]  # Last 1000 chars of error

        return True, ""

    except Exception as e:
        logger.debug("Sandbox build check error: %s", e)
        return True, ""  # Don't block on build check errors


def _detect_build_cmd(workspace: str) -> list[str]:
    """Detect the build system from workspace files."""
    import os

    if os.path.isfile(os.path.join(workspace, "package.json")):
        # Check if node_modules exists (deps installed)
        if os.path.isdir(os.path.join(workspace, "node_modules")):
            return ["npm", "run", "build", "--if-present"]
        return ["npm", "install", "--ignore-scripts"]
    if os.path.isfile(os.path.join(workspace, "requirements.txt")):
        return ["python3", "-m", "py_compile", _find_main_py(workspace)]
    if os.path.isfile(os.path.join(workspace, "Cargo.toml")):
        return ["cargo", "check"]
    if os.path.isfile(os.path.join(workspace, "pom.xml")):
        return ["mvn", "-q", "compile", "-DskipTests"]
    if os.path.isfile(os.path.join(workspace, "go.mod")):
        return ["go", "build", "./..."]
    if os.path.isfile(os.path.join(workspace, "Dockerfile")):
        return ["docker", "build", "--check", "."]
    return []


def _find_main_py(workspace: str) -> str:
    """Find main Python file for syntax check."""
    import os

    for f in ("main.py", "app.py", "server.py", "manage.py"):
        if os.path.isfile(os.path.join(workspace, f)):
            return os.path.join(workspace, f)
    # Fallback: first .py file
    for f in os.listdir(workspace):
        if f.endswith(".py"):
            return os.path.join(workspace, f)
    return ""


# ── Workflow Engine ──────────────────────────────────────────────


PHASE_TIMEOUT_SECONDS = 600  # 10 min max per phase


async def run_workflow(
    workflow: WorkflowDef,
    session_id: str,
    initial_task: str,
    project_id: str = "",
    resume_from: int = 0,
) -> WorkflowRun:
    """Execute a workflow — RTE facilitates each phase transition.

    Args:
        resume_from: phase index to resume from (skip completed phases).
    """
    run = WorkflowRun(
        workflow=workflow,
        session_id=session_id,
        project_id=project_id,
    )

    store = get_session_store()
    pattern_store = get_pattern_store()

    # On resume: reset any phases stuck at "running" → "pending"
    if resume_from > 0:
        _reset_stuck_phases(store, session_id)

    # Mark session as running
    try:
        store.update_status(session_id, "active")
    except Exception:
        pass

    # Workflow leader = first agent of first phase (typically CP)
    leader = ""
    if workflow.phases:
        first_agents = workflow.phases[0].config.get("agents", [])
        if first_agents:
            leader = first_agents[0]

    # RTE kicks off the sprint
    ceremony_names = [p.name for p in workflow.phases]
    if resume_from > 0:
        await _rte_facilitate(
            session_id,
            f"Reprise du sprint **{workflow.name}** à la phase {resume_from + 1}/{len(workflow.phases)} "
            f"({workflow.phases[resume_from].name}). Les {resume_from} premières phases sont déjà complétées.",
            to_agent=leader,
            project_id=project_id,
        )
    else:
        await _rte_facilitate(
            session_id,
            f"Tu lances le sprint **{workflow.name}** — {len(workflow.phases)} cérémonies: {', '.join(ceremony_names)}.\n"
            f"Objectif du sprint: {initial_task}\n\n"
            f"Annonce le démarrage à l'équipe. Le Scrum Master facilite, le CP priorise, l'équipe s'organise.",
            to_agent=leader,
            project_id=project_id,
        )

    accumulated_context = []
    for i, phase in enumerate(workflow.phases):
        # Skip already-completed phases on resume
        if i < resume_from:
            run.phase_results.append(
                {"phase": phase.name, "success": True, "skipped": True}
            )
            continue
        run.current_phase = i

        phase_agents = phase.config.get("agents", [])
        phase_leader = phase_agents[0] if phase_agents else leader or "all"

        # RTE facilitates ceremony transition
        prev_summary = ""
        if accumulated_context:
            prev_summary = "\n".join(f"- {c}" for c in accumulated_context[-3:])
        await _rte_facilitate(
            session_id,
            f"**{phase.name}**\n"
            f"{phase.description}\n"
            f"Participants: {', '.join(phase_agents)}\n"
            f"{f'Contexte:{chr(10)}{prev_summary}' if prev_summary else ''}\n\n"
            f"Facilite la cérémonie. Donne la parole à {phase_leader}.",
            to_agent=phase_leader,
            project_id=project_id,
        )

        pattern = pattern_store.get(phase.pattern_id)
        if not pattern:
            await _rte_facilitate(
                session_id,
                f"Le pattern '{phase.pattern_id}' n'existe pas. On passe à la phase suivante.",
                to_agent=phase_leader,
                project_id=project_id,
            )
            continue

        # Override pattern agents with the phase's workflow agents
        if phase_agents:
            from ..patterns.store import PatternDef as PD

            pattern = PD(
                id=f"{workflow.id}-{phase.id}",
                name=f"{phase.name}",
                description=phase.description,
                type=pattern.type,
                agents=[
                    {"id": f"n{j}", "agent_id": aid}
                    for j, aid in enumerate(phase_agents)
                ],
                edges=[],
                config=pattern.config,
                icon=pattern.icon,
            )

        # Build ceremony-specific task with accumulated context
        phase_task = f"## {phase.name}\n{phase.description}\n\n"
        if accumulated_context:
            phase_task += "## Previous phases summary:\n"
            for ctx in accumulated_context[-3:]:
                phase_task += f"- {ctx}\n"
            phase_task += "\n"
        phase_task += f"## Original goal:\n{initial_task}"

        # Phase timeout: per-phase override or global default
        phase_timeout = phase.timeout if phase.timeout > 0 else PHASE_TIMEOUT_SECONDS

        try:
            result = await asyncio.wait_for(
                run_pattern(pattern, session_id, phase_task, project_id),
                timeout=phase_timeout,
            )
            run.phase_results.append(
                {
                    "phase": phase.name,
                    "success": result.success,
                    "error": result.error,
                }
            )

            # RTE reacts to gate results
            if phase.gate == "all_approved" and not result.success:
                if phase.skip_on_failure:
                    await _rte_facilitate(
                        session_id,
                        f"La phase **{phase.name}** n'a pas obtenu l'approbation mais skip_on_failure=True. On continue.",
                        to_agent=leader,
                        project_id=project_id,
                    )
                else:
                    run.status = "gated"
                    await _rte_facilitate(
                        session_id,
                        f"La phase **{phase.name}** n'a pas obtenu l'approbation de tous. "
                        f"Des vetos non résolus subsistent après les boucles de correction. "
                        f"Le workflow est bloqué. Synthétise la situation et propose les prochaines étapes.",
                        to_agent=leader,
                        project_id=project_id,
                    )
                    break
            elif phase.gate in ("no_veto", "best_effort") and not result.success:
                await _rte_facilitate(
                    session_id,
                    f"La phase **{phase.name}** a eu des retours mais on continue. "
                    f"Le feedback a été adressé dans la boucle. On passe à la suite.",
                    to_agent=phase_leader,
                    project_id=project_id,
                )

            # Accumulate context from this phase's output
            last_msgs = store.get_messages(session_id, limit=5)
            for m in reversed(last_msgs):
                if m.from_agent not in ("system", "user", _RTE_AGENT_ID):
                    summary = (m.content or "")[:300].replace("\n", " ")
                    accumulated_context.append(
                        f"[{phase.name}] {m.from_agent}: {summary}"
                    )
                    break

            # Sandbox build validation after code generation phases
            if result.success and _is_code_phase(phase.name) and project_id:
                build_ok, build_error = await _sandbox_build_check(
                    project_id, session_id
                )
                if not build_ok and build_error:
                    accumulated_context.append(
                        f"[BUILD] Erreur de build: {build_error[:200]}"
                    )
                    await _rte_facilitate(
                        session_id,
                        f"⚠️ Build validation failed after **{phase.name}**:\n```\n{build_error[:500]}\n```\n"
                        f"Le code généré ne compile pas. Injecte l'erreur dans le contexte pour correction.",
                        to_agent=phase_leader,
                        project_id=project_id,
                    )

            # Checkpoint: save completed phase index for resume
            _save_checkpoint(store, session_id, i + 1)
            # Also sync phases_json in mission_runs so orchestrator path sees correct state
            _sync_phase_done_to_mission_run(session_id, i)

        except asyncio.TimeoutError:
            logger.error(
                "Workflow phase %s timed out after %ds",
                phase.name,
                phase_timeout,
            )
            error_str = f"Phase timed out after {phase_timeout}s"
            _last_summary = _capture_last_agent_summary(store, session_id, phase.name)
            run.phase_results.append(
                {
                    "phase": phase.name,
                    "success": False,
                    "error": error_str,
                    "timeout": True,
                }
            )
            # Timeouts: continue if gate allows or skip_on_failure
            if (
                phase.gate in ("always", "no_veto", "best_effort")
                or phase.skip_on_failure
            ):
                await _rte_facilitate(
                    session_id,
                    f"La phase **{phase.name}** a dépassé le timeout ({phase_timeout}s). "
                    f"{'skip_on_failure' if phase.skip_on_failure else f'gate={phase.gate}'}, on continue.\n{_last_summary}",
                    to_agent=leader,
                    project_id=project_id,
                )
                _save_checkpoint(store, session_id, i + 1)
                _sync_phase_done_to_mission_run(session_id, i)
                continue
            run.status = "failed"
            run.error = error_str
            await _rte_facilitate(
                session_id,
                f"La phase **{phase.name}** a dépassé le timeout ({phase_timeout}s). "
                f"Le workflow est arrêté.\n{_last_summary}",
                to_agent=leader,
                project_id=project_id,
            )
            break

        except Exception as e:
            logger.error("Workflow phase %s failed: %s", phase.name, e)
            error_str = str(e)
            _last_summary = _capture_last_agent_summary(store, session_id, phase.name)

            # Retry logic: use phase.retry_count (default 1), with error context injection
            max_retries = max(
                phase.retry_count,
                3 if _is_transient_error(error_str) else phase.retry_count,
            )
            retry_ok = False
            if max_retries > 0:
                import random

                for attempt in range(1, max_retries + 1):
                    delay = min(15 * (2 ** (attempt - 1)) + random.uniform(0, 10), 120)
                    logger.warning(
                        "Retrying phase %s (attempt %d/%d) after %.0fs — %s",
                        phase.name,
                        attempt,
                        max_retries,
                        delay,
                        error_str[:100],
                    )
                    await asyncio.sleep(delay)
                    # Inject error context into retry prompt
                    retry_task = (
                        f"{phase_task}\n\n"
                        f"## RETRY (attempt {attempt}/{max_retries})\n"
                        f"Previous attempt failed: {error_str[:500]}\n"
                        f"{_last_summary}\n"
                        f"Fix the issues and try again."
                    )
                    try:
                        result = await asyncio.wait_for(
                            run_pattern(pattern, session_id, retry_task, project_id),
                            timeout=phase_timeout,
                        )
                        run.phase_results.append(
                            {
                                "phase": phase.name,
                                "success": result.success,
                                "error": result.error,
                                "retried": True,
                                "retry_attempt": attempt,
                            }
                        )
                        last_msgs = store.get_messages(session_id, limit=5)
                        for m in reversed(last_msgs):
                            if m.from_agent not in ("system", "user", _RTE_AGENT_ID):
                                summary = (m.content or "")[:300].replace("\n", " ")
                                accumulated_context.append(
                                    f"[{phase.name}] {m.from_agent}: {summary}"
                                )
                                break
                        _save_checkpoint(store, session_id, i + 1)
                        retry_ok = True
                        break
                    except Exception as e2:
                        error_str = str(e2)
                        _last_summary = _capture_last_agent_summary(
                            store, session_id, phase.name
                        )
                        logger.error(
                            "Retry %d failed for phase %s: %s", attempt, phase.name, e2
                        )
            if retry_ok:
                continue

            # All retries exhausted — decide: skip or stop
            if phase.skip_on_failure or phase.gate in ("always", "best_effort"):
                run.phase_results.append(
                    {
                        "phase": phase.name,
                        "success": False,
                        "error": error_str,
                        "context": _last_summary,
                        "skipped_after_failure": True,
                    }
                )
                await _rte_facilitate(
                    session_id,
                    f"La phase **{phase.name}** a échoué après {max_retries} tentatives: {error_str[:200]}\n"
                    f"{_last_summary}\n"
                    f"Phase non-bloquante — on continue avec la suite.",
                    to_agent=leader,
                    project_id=project_id,
                )
                _save_checkpoint(store, session_id, i + 1)
                continue

            # Critical phase — stop workflow
            run.status = "failed"
            run.error = f"{error_str} | {_last_summary}" if _last_summary else error_str
            await _rte_facilitate(
                session_id,
                f"Erreur sur la phase **{phase.name}** après {max_retries} tentatives: {error_str[:200]}\n"
                f"Annonce l'erreur à l'équipe et propose un plan de recovery.",
                to_agent=leader,
                project_id=project_id,
            )
            break

    if run.status == "running":
        run.status = "completed"

    # Update session status to match workflow outcome
    session_status = {
        "completed": "completed",
        "failed": "failed",
        "gated": "interrupted",
    }.get(run.status, "completed")
    try:
        store.update_status(session_id, session_status)
    except Exception:
        pass

    # RTE closes the workflow
    status_emoji = {"completed": "[OK]", "failed": "[FAIL]", "gated": "[BLOCKED]"}.get(
        run.status, "[DONE]"
    )
    phase_summary = "\n".join(
        f"- {r['phase']}: {'[OK]' if r['success'] else '[FAIL]'}"
        for r in run.phase_results
    )
    await _rte_facilitate(
        session_id,
        f"{status_emoji} Le workflow **{workflow.name}** est terminé ({run.status}).\n"
        f"Bilan des phases:\n{phase_summary}\n\n"
        f"Fais la synthèse finale pour l'équipe. Mets en avant les livrables et les prochaines étapes.",
        to_agent=leader,
        project_id=project_id,
    )

    return run
