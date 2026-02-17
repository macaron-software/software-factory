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
from ..patterns.store import get_pattern_store, PatternDef
from ..patterns.engine import run_pattern, _push_sse
from ..sessions.store import get_session_store, SessionDef, MessageDef

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
        self._ensure_table()
        conn = get_db()
        rows = conn.execute("SELECT * FROM workflows ORDER BY created_at").fetchall()
        conn.close()
        return [self._row_to_wf(r) for r in rows]

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
            (wf.id, wf.name, wf.description,
             json.dumps([{"id": p.id, "pattern_id": p.pattern_id, "name": p.name,
                          "description": p.description, "gate": p.gate, "config": p.config}
                         for p in wf.phases]),
             json.dumps(wf.config), wf.icon, int(wf.is_builtin)),
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
        """Seed pre-built workflow templates."""
        if self.count() > 0:
            return
        builtins = [
            WorkflowDef(
                id="sf-pipeline", name="Software Factory Pipeline",
                description="Full SF cycle: Brain analysis → TDD development → Adversarial review → Deploy.",
                icon="rocket", is_builtin=True,
                phases=[
                    WorkflowPhase(id="p1", pattern_id="hierarchical", name="Analysis",
                                  description="Brain decomposes the task into subtasks",
                                  gate="always"),
                    WorkflowPhase(id="p2", pattern_id="adversarial-pair", name="TDD Development",
                                  description="Writer implements with TDD, reviewer validates",
                                  gate="always"),
                    WorkflowPhase(id="p3", pattern_id="adversarial-cascade", name="Quality Gate",
                                  description="4-layer adversarial review cascade",
                                  gate="no_veto"),
                ],
            ),
            WorkflowDef(
                id="review-cycle", name="Code Review Cycle",
                description="Sequential review: code → security → architecture.",
                icon="eye", is_builtin=True,
                phases=[
                    WorkflowPhase(id="p1", pattern_id="sequential", name="Multi-Layer Review",
                                  description="Analyst → Developer → Reviewer pipeline",
                                  gate="always"),
                    WorkflowPhase(id="p2", pattern_id="adversarial-pair", name="Fix Issues",
                                  description="Fix any issues found in review",
                                  gate="no_veto"),
                ],
            ),
            WorkflowDef(
                id="debate-decide", name="Debate & Decide",
                description="Agents debate, then a judge decides, then implement the decision.",
                icon="briefcase", is_builtin=True,
                phases=[
                    WorkflowPhase(id="p1", pattern_id="debate", name="Debate",
                                  description="Agents argue for/against different approaches",
                                  gate="always"),
                    WorkflowPhase(id="p2", pattern_id="hierarchical", name="Implementation",
                                  description="Execute the decided approach",
                                  gate="always"),
                ],
            ),
            WorkflowDef(
                id="migration-sharelook",
                name="Migration Sharelook Angular 16→17",
                description="Migration ISO 100% Angular 16.2→17.3 — SAFe PI: Planning→Sprint→Review→Retro→Release.",
                icon="rocket", is_builtin=True,
                phases=[
                    # ── PI Planning: Vision, scope, risques ──
                    WorkflowPhase(id="pi-planning", pattern_id="sequential",
                                  name="PI Planning",
                                  description="CP présente vision migration. Lead+QA+Sécu définissent scope, risques, acceptance criteria.",
                                  gate="always",
                                  config={"agents": ["chef_projet", "lead_dev", "qa_lead", "securite"]}),
                    # ── Sprint Planning: Lead décompose en stories pour les devs ──
                    WorkflowPhase(id="sprint-planning", pattern_id="hierarchical",
                                  name="Sprint Planning",
                                  description="Lead décompose migration en user stories. Assigne aux devs selon expertise (pilot vs main app).",
                                  gate="always",
                                  config={"agents": ["lead_dev", "dev_frontend", "dev_fullstack"]}),
                    # ── Dev Sprint: Devs codent, Lead review complétude ──
                    WorkflowPhase(id="dev-sprint", pattern_id="hierarchical",
                                  name="Dev Sprint",
                                  description="Devs exécutent migration en //. Lead vérifie complétude. Inner loop jusqu'à COMPLETE.",
                                  gate="always",
                                  config={"agents": ["lead_dev", "dev_frontend", "dev_fullstack", "qa_lead"]}),
                    # ── Sprint Review: QA valide, Sécu audite, CP GO/NOGO ──
                    WorkflowPhase(id="sprint-review", pattern_id="sequential",
                                  name="Sprint Review",
                                  description="Lead présente travail. QA valide ISO 100% (golden files). Sécu audit CVE. CP décide GO/NOGO.",
                                  gate="no_veto",
                                  config={"agents": ["lead_dev", "qa_lead", "securite", "chef_projet"]}),
                    # ── Retrospective: Tous débattent améliorations ──
                    WorkflowPhase(id="retrospective", pattern_id="network",
                                  name="Retrospective",
                                  description="Équipe entière débat: ce qui a marché, ce qui a échoué, améliorations process.",
                                  gate="always",
                                  config={"agents": ["lead_dev", "dev_frontend", "dev_fullstack", "qa_lead", "chef_projet"]}),
                    # ── Release: DevOps deploy, QA smoke, CP valide ──
                    WorkflowPhase(id="release", pattern_id="sequential",
                                  name="Release",
                                  description="DevOps deploy staging→canary. QA smoke test. CP valide mise en prod.",
                                  gate="all_approved",
                                  config={"agents": ["devops", "qa_lead", "chef_projet"]}),
                ],
                config={
                    "graph": {
                        "pattern": "hierarchical",
                        "nodes": [
                            {"id": "n1", "agent_id": "chef_projet", "x": 400, "y": 30, "label": "Chef de Projet"},
                            {"id": "n2", "agent_id": "lead_dev", "x": 250, "y": 170, "label": "Lead Dev Angular"},
                            {"id": "n3", "agent_id": "securite", "x": 550, "y": 170, "label": "Security Audit"},
                            {"id": "n4", "agent_id": "qa_lead", "x": 400, "y": 170, "label": "QA Lead (ISO 100%)"},
                            {"id": "n5", "agent_id": "dev_frontend", "x": 150, "y": 340, "label": "Dev Frontend"},
                            {"id": "n6", "agent_id": "dev_fullstack", "x": 350, "y": 340, "label": "Dev Fullstack"},
                            {"id": "n7", "agent_id": "devops", "x": 550, "y": 340, "label": "DevOps"},
                        ],
                        "edges": [
                            # PI Planning: CP briefs everyone
                            {"from": "n1", "to": "n2", "label": "brief", "type": "sequential", "color": "#3b82f6"},
                            {"from": "n1", "to": "n4", "label": "criteria", "type": "sequential", "color": "#3b82f6"},
                            {"from": "n1", "to": "n3", "label": "audit", "type": "sequential", "color": "#3b82f6"},
                            # Sprint: Lead delegates to devs
                            {"from": "n2", "to": "n5", "label": "stories", "type": "parallel", "color": "#f59e0b"},
                            {"from": "n2", "to": "n6", "label": "stories", "type": "parallel", "color": "#f59e0b"},
                            # Review: Devs report to QA
                            {"from": "n5", "to": "n4", "label": "validate", "type": "sequential", "color": "#10b981"},
                            {"from": "n6", "to": "n4", "label": "validate", "type": "sequential", "color": "#10b981"},
                            # Feedback: QA reports to CP
                            {"from": "n4", "to": "n1", "label": "GO/NOGO", "type": "report", "color": "#ef4444"},
                            {"from": "n3", "to": "n1", "label": "report", "type": "report", "color": "#ef4444"},
                            # Release: CP triggers deploy
                            {"from": "n1", "to": "n7", "label": "deploy", "type": "sequential", "color": "#8b5cf6"},
                        ],
                    },
                    "project_ref": "sharelook",
                    "migration": {"framework": "angular", "from": "16.2.12", "to": "17.3.0"},
                    "agents_permissions": {
                        "qa_lead": {"can_veto": True, "veto_level": "ABSOLUTE"},
                        "securite": {"can_veto": True, "veto_level": "ABSOLUTE"},
                        "lead_dev": {"can_veto": True, "veto_level": "STRONG", "can_delegate": True},
                        "chef_projet": {"can_delegate": True},
                    },
                },
            ),
        ]
        for w in builtins:
            self.create(w)

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
        store.add_message(MessageDef(
            session_id=session_id,
            from_agent="system", to_agent=to_agent or "all",
            message_type="system", content=prompt,
        ))
        return prompt

    # Push thinking status
    await _push_sse(session_id, {
        "type": "agent_status",
        "agent_id": rte.id,
        "status": "thinking",
    })

    ctx = ExecutionContext(
        agent=rte,
        session_id=session_id,
        project_id=project_id,
        tools_enabled=False,  # RTE doesn't need tools, just speaks
    )

    executor = get_executor()
    result = await executor.run(ctx, prompt)

    msg = MessageDef(
        session_id=session_id,
        from_agent=rte.id,
        to_agent=to_agent or "all",
        message_type="text",
        content=result.content,
        metadata={
            "model": result.model,
            "provider": result.provider,
            "tokens_in": result.tokens_in,
            "tokens_out": result.tokens_out,
            "duration_ms": result.duration_ms,
            "role": "rte_facilitation",
        },
    )
    store.add_message(msg)
    await _push_sse(session_id, {
        "type": "message",
        "from_agent": rte.id,
        "to_agent": to_agent or "all",
        "content": result.content,
        "message_type": "text",
    })
    await _push_sse(session_id, {
        "type": "agent_status",
        "agent_id": rte.id,
        "status": "idle",
    })

    return result.content


# ── Workflow Engine ──────────────────────────────────────────────

async def run_workflow(
    workflow: WorkflowDef,
    session_id: str,
    initial_task: str,
    project_id: str = "",
) -> WorkflowRun:
    """Execute a workflow — RTE facilitates each phase transition."""
    run = WorkflowRun(
        workflow=workflow,
        session_id=session_id,
        project_id=project_id,
    )

    store = get_session_store()
    pattern_store = get_pattern_store()

    # Workflow leader = first agent of first phase (typically CP)
    leader = ""
    if workflow.phases:
        first_agents = workflow.phases[0].config.get("agents", [])
        if first_agents:
            leader = first_agents[0]

    # RTE kicks off the sprint
    ceremony_names = [p.name for p in workflow.phases]
    await _rte_facilitate(
        session_id,
        f"Tu lances le sprint **{workflow.name}** — {len(workflow.phases)} cérémonies: {', '.join(ceremony_names)}.\n"
        f"Objectif du sprint: {initial_task}\n\n"
        f"Annonce le démarrage à l'équipe. Le Scrum Master facilite, le CP priorise, l'équipe s'organise.",
        to_agent=leader,
        project_id=project_id,
    )

    task = initial_task
    accumulated_context = []
    for i, phase in enumerate(workflow.phases):
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
                agents=[{"id": f"n{j}", "agent_id": aid} for j, aid in enumerate(phase_agents)],
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
            run.phase_results.append({
                "phase": phase.name,
                "success": result.success,
                "error": result.error,
            })

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
                    accumulated_context.append(f"[{phase.name}] {m.from_agent}: {summary}")
                    break

        except Exception as e:
            run.status = "failed"
            run.error = str(e)
            logger.error("Workflow phase %s failed: %s", phase.name, e)
            await _rte_facilitate(
                session_id,
                f"Erreur technique sur la phase **{phase.name}**: {e}\n"
                f"Annonce l'erreur à l'équipe et propose un plan de recovery.",
                to_agent=leader,
                project_id=project_id,
            )
            break

    if run.status == "running":
        run.status = "completed"

    # RTE closes the workflow
    status_emoji = {"completed": "[OK]", "failed": "[FAIL]", "gated": "[BLOCKED]"}.get(run.status, "[DONE]")
    phase_summary = "\n".join(
        f"- {r['phase']}: {'[OK]' if r['success'] else '[FAIL]'}" for r in run.phase_results
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
