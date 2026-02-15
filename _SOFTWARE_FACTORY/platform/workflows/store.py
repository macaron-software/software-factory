"""Workflow store and engine — chains patterns into multi-phase pipelines.

A Workflow is a sequence of phases. Each phase runs a pattern.
Phases can have gates (conditions to proceed) and shared context.
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
from ..patterns.engine import run_pattern
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
                description="Migration ISO 100% Angular 16.2→17.3. CDP orchestre, Lead décompose, Devs codemods, QA golden files (0% diff), Security audit.",
                icon="rocket", is_builtin=True,
                phases=[
                    WorkflowPhase(id="p1-deps", pattern_id="sequential",
                                  name="Phase 1: Dependencies & Audit",
                                  description="Update Angular deps, npm audit, Security CVE check.",
                                  gate="no_veto",
                                  config={"agents": ["chef_projet", "lead_dev", "securite"]}),
                    WorkflowPhase(id="p2-pilot", pattern_id="hierarchical",
                                  name="Phase 2: Pilot (ai12-reporting)",
                                  description="Migrate small app (10 modules). Lead→Dev→QA golden.",
                                  gate="no_veto",
                                  config={"agents": ["lead_dev", "dev_frontend", "qa_lead"]}),
                    WorkflowPhase(id="p3-main", pattern_id="hierarchical",
                                  name="Phase 3: Main App (ai08-admin)",
                                  description="Migrate large app (38 modules). Multi-dev, QA validates.",
                                  gate="no_veto",
                                  config={"agents": ["lead_dev", "dev_frontend", "dev_fullstack", "qa_lead"]}),
                    WorkflowPhase(id="p4-deploy", pattern_id="sequential",
                                  name="Phase 4: Deploy Canary",
                                  description="Staging→E2E→canary 1%→100%. Rollback si régression.",
                                  gate="all_approved",
                                  config={"agents": ["chef_projet", "qa_lead", "securite", "devops"]}),
                ],
                config={
                    "graph": {
                        "pattern": "hierarchical",
                        "nodes": [
                            {"id": "n1", "agent_id": "chef_projet", "x": 400, "y": 50, "label": "Chef de Projet Migration"},
                            {"id": "n2", "agent_id": "lead_dev", "x": 200, "y": 200, "label": "Lead Dev Angular"},
                            {"id": "n3", "agent_id": "securite", "x": 600, "y": 200, "label": "Security Audit"},
                            {"id": "n4", "agent_id": "qa_lead", "x": 400, "y": 200, "label": "QA Migration (ISO 100%)"},
                            {"id": "n5", "agent_id": "dev_frontend", "x": 100, "y": 380, "label": "Dev Frontend (Pilot)"},
                            {"id": "n6", "agent_id": "dev_fullstack", "x": 300, "y": 380, "label": "Dev Frontend (Main)"},
                            {"id": "n7", "agent_id": "devops", "x": 500, "y": 380, "label": "DevOps Deploy"},
                        ],
                        "edges": [
                            {"from": "n1", "to": "n2", "label": "decompose"},
                            {"from": "n1", "to": "n3", "label": "audit"},
                            {"from": "n1", "to": "n4", "label": "validate"},
                            {"from": "n2", "to": "n5", "label": "pilot"},
                            {"from": "n2", "to": "n6", "label": "main"},
                            {"from": "n5", "to": "n4", "label": "golden"},
                            {"from": "n6", "to": "n4", "label": "golden"},
                            {"from": "n4", "to": "n1", "label": "GO/NOGO"},
                            {"from": "n3", "to": "n1", "label": "report"},
                            {"from": "n1", "to": "n7", "label": "deploy"},
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


# ── Workflow Engine ──────────────────────────────────────────────

async def run_workflow(
    workflow: WorkflowDef,
    session_id: str,
    initial_task: str,
    project_id: str = "",
) -> WorkflowRun:
    """Execute a workflow — run each phase's pattern sequentially."""
    run = WorkflowRun(
        workflow=workflow,
        session_id=session_id,
        project_id=project_id,
    )

    store = get_session_store()
    pattern_store = get_pattern_store()

    store.add_message(MessageDef(
        session_id=session_id,
        from_agent="system",
        message_type="system",
        content=f"🔄 Workflow **{workflow.name}** started — {len(workflow.phases)} phases",
    ))

    task = initial_task
    for i, phase in enumerate(workflow.phases):
        run.current_phase = i

        store.add_message(MessageDef(
            session_id=session_id,
            from_agent="system",
            message_type="system",
            content=f"📌 Phase {i+1}/{len(workflow.phases)}: **{phase.name}** — {phase.description}",
        ))

        pattern = pattern_store.get(phase.pattern_id)
        if not pattern:
            store.add_message(MessageDef(
                session_id=session_id,
                from_agent="system",
                message_type="system",
                content=f"⚠️ Pattern '{phase.pattern_id}' not found, skipping phase.",
            ))
            continue

        try:
            result = await run_pattern(pattern, session_id, task, project_id)
            run.phase_results.append({
                "phase": phase.name,
                "success": result.success,
                "error": result.error,
            })

            # Check gate
            if phase.gate == "no_veto" and not result.success:
                run.status = "gated"
                store.add_message(MessageDef(
                    session_id=session_id,
                    from_agent="system",
                    message_type="system",
                    content=f"🚫 Workflow gated at phase '{phase.name}' — pattern had vetoes/failures.",
                ))
                break

            # Use last agent output as context for next phase
            last_msgs = store.get_messages(session_id, limit=3)
            for m in reversed(last_msgs):
                if m.from_agent not in ("system", "user"):
                    task = f"[Previous phase output from {m.from_agent}]:\n{m.content[:2000]}\n\n[Original task]:\n{initial_task}"
                    break

        except Exception as e:
            run.status = "failed"
            run.error = str(e)
            logger.error("Workflow phase %s failed: %s", phase.name, e)
            store.add_message(MessageDef(
                session_id=session_id,
                from_agent="system",
                message_type="system",
                content=f"❌ Phase '{phase.name}' error: {e}",
            ))
            break

    if run.status == "running":
        run.status = "completed"

    status_emoji = {"completed": "✅", "failed": "❌", "gated": "🚫"}.get(run.status, "⏹")
    store.add_message(MessageDef(
        session_id=session_id,
        from_agent="system",
        message_type="system",
        content=f"{status_emoji} Workflow **{workflow.name}** {run.status}",
    ))

    return run
