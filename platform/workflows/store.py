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
    gate: str = ""  # condition to proceed: "all_approved", "no_veto", "always"
    config: dict = field(default_factory=dict)


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


# ── Workflow Engine ──────────────────────────────────────────────


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

        try:
            result = await run_pattern(pattern, session_id, phase_task, project_id)
            run.phase_results.append(
                {
                    "phase": phase.name,
                    "success": result.success,
                    "error": result.error,
                }
            )

            # RTE reacts to gate results
            if phase.gate == "all_approved" and not result.success:
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
            elif phase.gate == "no_veto" and not result.success:
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

            # Checkpoint: save completed phase index for resume
            _save_checkpoint(store, session_id, i + 1)

        except Exception as e:
            logger.error("Workflow phase %s failed: %s", phase.name, e)
            error_str = str(e)
            # Retry up to 3 times on transient errors with exponential backoff
            is_transient = any(
                k in error_str.lower()
                for k in (
                    "429",
                    "rate",
                    "timeout",
                    "connection",
                    "temporarily",
                    "overloaded",
                )
            )
            if is_transient:
                import random

                retry_ok = False
                for attempt in range(1, 4):
                    delay = min(15 * (2 ** (attempt - 1)) + random.uniform(0, 10), 120)
                    logger.info(
                        "Retrying phase %s (attempt %d/3) after %.0fs",
                        phase.name,
                        attempt,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    try:
                        result = await run_pattern(
                            pattern, session_id, phase_task, project_id
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
                        logger.error(
                            "Retry %d failed for phase %s: %s", attempt, phase.name, e2
                        )
                if retry_ok:
                    continue

            # Non-critical phases (gate=always) — log error but continue
            if phase.gate == "always":
                run.phase_results.append(
                    {
                        "phase": phase.name,
                        "success": False,
                        "error": error_str,
                    }
                )
                await _rte_facilitate(
                    session_id,
                    f"Erreur technique sur la phase **{phase.name}**: {error_str}\n"
                    f"La phase a gate='always', on continue avec la suite.",
                    to_agent=leader,
                    project_id=project_id,
                )
                continue  # don't break — keep going

            # Critical phases — stop workflow
            run.status = "failed"
            run.error = error_str
            await _rte_facilitate(
                session_id,
                f"Technical error on phase **{phase.name}**: {error_str}\n"
                f"Annonce l'erreur a l'equipe et propose un plan de recovery.",
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
