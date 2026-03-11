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
from ..patterns.engine import (
    run_pattern,
    _push_sse,
    WorkflowPaused,
    AdversarialEscalation,
)
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
    # Scale-adaptive planning (BMAD-inspired): phase only runs at or above this complexity.
    # Values: "simple" | "standard" | "enterprise" | "" (empty = always run).
    # Example: set min_complexity="enterprise" on heavyweight planning phases.
    min_complexity: str = ""


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
    category: str = ""
    graph: dict = field(default_factory=dict)


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
                        (
                            {
                                "id": p.id,
                                "pattern_id": p.pattern_id,
                                "name": p.name,
                                "description": p.description,
                                "gate": p.gate,
                                "config": p.config,
                                "retry_count": p.retry_count,
                                "skip_on_failure": p.skip_on_failure,
                                "timeout": p.timeout,
                                "min_complexity": p.min_complexity,
                            }
                            if isinstance(p, WorkflowPhase)
                            else p  # already a dict (from compose_workflow)
                        )
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
        # Known WorkflowPhase fields
        _PHASE_FIELDS = {f.name for f in WorkflowPhase.__dataclass_fields__.values()}
        cleaned_phases = []
        for p in phases_data:
            # Normalize: move top-level 'agents' into config.agents
            if "agents" in p and "agents" not in p.get("config", {}):
                p.setdefault("config", {})["agents"] = p.pop("agents")
            elif "agents" in p:
                p.pop("agents")
            # Map common aliases to dataclass field names
            if "pattern" in p and "pattern_id" not in p:
                p["pattern_id"] = p.pop("pattern")
            # Strip unknown keys to avoid __init__ crash
            cleaned = {k: v for k, v in p.items() if k in _PHASE_FIELDS}
            cleaned_phases.append(WorkflowPhase(**cleaned))
        return WorkflowDef(
            id=row["id"],
            name=row["name"],
            description=row["description"] or "",
            phases=cleaned_phases,
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
            "SELECT id, phases_json FROM epic_runs WHERE session_id=? AND phases_json LIKE '%\"running\"%'",
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
                    "UPDATE epic_runs SET phases_json=? WHERE id=?",
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
            "SELECT workspace_path FROM epic_runs WHERE session_id=? LIMIT 1",
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
            # No build system detected — report as inconclusive, not "passed"
            import os
            src_files = [f for f in os.listdir(workspace)
                        if f.endswith(('.swift', '.rs', '.go', '.java', '.ts', '.tsx', '.py'))]
            if src_files or os.path.isdir(os.path.join(workspace, "src")):
                return False, "No build system detected (missing Package.swift / Cargo.toml / package.json / etc.) — cannot validate compilation"
            return True, ""  # No source files = nothing to build

        proc = await asyncio.create_subprocess_exec(
            *build_cmd,
            cwd=workspace,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=1800)
        except asyncio.TimeoutError:
            proc.kill()
            return False, "Build timed out after 1800s"

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

    if os.path.isfile(os.path.join(workspace, "Package.swift")):
        # Use full path to Apple Swift (avoid OpenStack swift CLI)
        swift_bin = "/usr/bin/swift" if os.path.isfile("/usr/bin/swift") else "swift"
        return [swift_bin, "build"]
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
    if os.path.isfile(os.path.join(workspace, "build.gradle")) or os.path.isfile(
        os.path.join(workspace, "build.gradle.kts")
    ):
        return ["gradle", "compileJava"]
    if os.path.isfile(os.path.join(workspace, "go.mod")):
        return ["go", "build", "./..."]
    if os.path.isfile(os.path.join(workspace, "Makefile")):
        return ["make", "-n"]  # dry-run to check Makefile syntax
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


# ── PM v2 Orchestrator (Lego-brick phases) ──────────────────────

_PATTERN_CATALOG = {
    "solo": "Single agent works alone. Use for: inception, simple writes, single-skill tasks",
    "sequential": "Agents pipeline A→B→C. Use for: design→review, build→test→deploy",
    "parallel": "Dispatcher fans out to N workers, aggregator merges. Use for: multi-file coding, parallel tests, independent sub-tasks",
    "loop": "Writer-reviewer iterate until gate passes (max N). Use for: TDD red-green-refactor, code-review cycles, fix-verify loops",
    "hierarchical": "Manager delegates to devs, QA validates. Use for: dev sprints, feature implementation with oversight",
    "network": "N debaters argue, judge LLM decides winner. Use for: architecture decisions, design trade-offs, adversarial review",
    "router": "Analyze task → route to best specialist agent. Use for: bug triage, multi-domain tasks, skill-based dispatch",
    "aggregator": "Workers run in parallel, results consolidated. Use for: specs from multiple perspectives, parallel analysis",
    "wave": "Dependency DAG: execute in waves respecting deps. Use for: multi-module builds, ordered migrations",
    "human-in-the-loop": "Agent proposes, human validates at checkpoints. Use for: critical deploys, security reviews",
    "map_reduce": "Map task to N workers, reduce results into synthesis. Use for: large codebase analysis, multi-file refactoring",
    "blackboard": "Agents read/write shared knowledge board iteratively. Use for: complex design convergence, multi-agent brainstorming",
    "composite": "Chain of sub-patterns executed sequentially. Use for: complex workflows needing mixed patterns",
}

_FEEDBACK_TYPES = {
    "adversarial": "Adversarial guard reviews output quality/security",
    "tools": "Require build/test tool execution before validation",
    "judge": "Network debate with judge LLM for decision",
    "human": "Human-in-the-loop checkpoint for manual review",
}

_GATE_TYPES = {
    "all_approved": "All reviewers must approve",
    "no_veto": "Proceed unless someone vetoes",
    "always": "Always proceed regardless",
    "best_effort": "Continue despite partial failures",
}

_PHASE_TEMPLATES = [
    {"id": "inception", "name": "Inception & Stories", "pattern": "solo",
     "team_roles": ["product"], "gate": "no_veto"},
    {"id": "design", "name": "Architecture Design", "pattern": "sequential",
     "team_roles": ["architect", "tech-lead"], "gate": "no_veto"},
    {"id": "design-debate", "name": "Architecture Debate", "pattern": "network",
     "team_roles": ["architect", "tech-lead", "critic"], "gate": "no_veto"},
    {"id": "dev-sprint", "name": "Development Sprint", "pattern": "hierarchical",
     "team_roles": ["tech-lead", "developer", "qa"], "gate": "no_veto"},
    {"id": "parallel-dev", "name": "Parallel Development", "pattern": "parallel",
     "team_roles": ["developer", "developer", "developer"], "gate": "best_effort"},
    {"id": "tdd-sprint", "name": "TDD Sprint", "pattern": "loop",
     "team_roles": ["developer", "qa"], "gate": "all_approved"},
    {"id": "code-review", "name": "Code Review", "pattern": "loop",
     "team_roles": ["reviewer", "developer"], "gate": "all_approved"},
    {"id": "qa-acceptance", "name": "QA & Acceptance", "pattern": "loop",
     "team_roles": ["qa", "critic"], "gate": "all_approved",
     "feedback": ["adversarial", "tools"]},
    {"id": "multi-file-refactor", "name": "Multi-File Refactoring", "pattern": "map_reduce",
     "team_roles": ["developer", "developer", "architect"], "gate": "no_veto"},
    {"id": "design-convergence", "name": "Design Convergence", "pattern": "blackboard",
     "team_roles": ["architect", "product", "tech-lead"], "gate": "no_veto"},
    {"id": "deploy", "name": "Deploy & Verify", "pattern": "sequential",
     "team_roles": ["infra", "qa"], "gate": "always"},
    {"id": "rework", "name": "Rework Sprint", "pattern": "hierarchical",
     "team_roles": ["tech-lead", "developer"], "gate": "no_veto"},
    {"id": "bug-triage", "name": "Bug Triage & Routing", "pattern": "router",
     "team_roles": ["lead", "developer", "sre"], "gate": "no_veto"},
]


def _build_agent_catalog() -> str:
    """Build compact agent catalog grouped by role for PM prompt."""
    try:
        from ..agents.store import get_agent_store
        agents = get_agent_store().list_all()
    except Exception:
        return "  (agent catalog unavailable)"
    by_role: dict[str, list] = {}
    for ag in agents:
        role = ag.role or "worker"
        by_role.setdefault(role, []).append(ag)
    lines = []
    for role in sorted(by_role):
        ags = by_role[role]
        ids = []
        for a in ags[:8]:
            label = a.id
            if a.skills:
                label += f"({','.join(a.skills[:3])})"
            ids.append(label)
        lines.append(f"  [{role}] {', '.join(ids)}")
    return "\n".join(lines) or "  (no agents)"


def _format_catalog_section(d: dict) -> str:
    return "\n".join(f"  {k}: {v}" for k, v in d.items())


def _format_templates_section() -> str:
    lines = []
    for t in _PHASE_TEMPLATES:
        fb = f", feedback={t['feedback']}" if t.get("feedback") else ""
        lines.append(
            f"  {t['id']}: pattern={t['pattern']}, "
            f"roles={t['team_roles']}, gate={t['gate']}{fb}"
        )
    return "\n".join(lines)


_PM_DECISION_PROMPT_V2 = """\
Project: {project_id}
Phase completed: "{phase_name}"
Loop: {loop_count}/{loop_limit}

## Evidence
{phase_evidence}

## History (last 10)
{history}

## Workflow Phases
{catalog}

## Goal
{goal}

## Patterns: {patterns}
## Agents: {agents}
## Templates: {templates}
## Feedback: {feedback_types}
## Gates: {gate_types}

─── DECISION ───
Return ONE JSON object. Pick the BEST option:

1. ADVANCE to next phase (phase succeeded):
{{"decision": "next", "reason": "..."}}

2. RE-RUN same phase (minor fix needed, max 2 loops):
{{"decision": "loop", "phase_id": "<phase>", "reason": "...", "findings": "..."}}

3. SKIP to a later phase:
{{"decision": "skip", "phase_id": "<phase>", "reason": "...", "findings": "..."}}

4. DONE (all AC met + build OK + tests pass):
{{"decision": "done", "reason": "...", "findings": "..."}}

5. COMPOSE a new dynamic phase — PICK THE RIGHT PATTERN for the situation:
{{"decision": "phase", "phase": {{"name": "<name>", "pattern": "<pattern>", "team": ["<agent_id>", ...], "gate": "<gate>", "feedback": ["<type>", ...], "max_iterations": <int>, "task": "<instructions>"}}, "reason": "..."}}

─── PATTERN SELECTION GUIDE ───
Pick the pattern that matches the situation:
- Fix a bug or iterate code→review: "loop" (writer + reviewer)
- Run build then test then deploy: "sequential" (pipeline)
- Multiple independent files/tasks: "parallel" (fan-out workers)
- Need manager oversight over devs: "hierarchical" (manager delegates)
- Architecture trade-off or debate: "network" (debaters + judge)
- Route to best specialist: "router" (triage + dispatch)
- Large refactoring across files: "map_reduce" (workers + synthesizer)
- Complex design needing convergence: "blackboard" (shared knowledge iterations)
- Simple single-agent task: "solo" (one agent)

─── PROGRESSION RULES ───
- After 2 loops of SAME phase → MUST use "next", "skip", or "phase"
- NEVER loop same phase 3+ times — decompose the problem instead
- Vary patterns: don't always use loop/sequential — match the problem shape
- Multiple files to fix → parallel or map_reduce (not sequential)
- Need debate/decision → network (not loop)
- After dev phase: compose "qa-acceptance" with feedback=["adversarial","tools"]

─── NEVER "done" IF ───
- Build never ran or failed
- Tests not executed or failed
- Source files < 3 (non-trivial project)
- Adversarial guard rejected (score >= 7)
"""


def _build_dynamic_phase(pm_block: dict) -> tuple:
    """Build (WorkflowPhase, PatternDef) from PM phase block."""
    import uuid
    from ..patterns.store import PatternDef

    spec = pm_block.get("phase", {})
    phase_id = spec.get("id") or f"pm-{uuid.uuid4().hex[:8]}"
    pattern_type = spec.get("pattern", "sequential")
    team = spec.get("team", [])
    gate = spec.get("gate", "no_veto")
    feedback = spec.get("feedback", [])
    max_iter = spec.get("max_iterations", 5)
    task = spec.get("task", "")
    timeout = spec.get("timeout", 0)

    if pattern_type not in _PATTERN_CATALOG:
        logger.warning("PM_PHASE: unknown pattern %s → sequential", pattern_type)
        pattern_type = "sequential"

    config: dict = {"max_iterations": max_iter}
    if "adversarial" in feedback:
        config["adversarial_guard"] = True
    if "tools" in feedback:
        config["require_tool_validation"] = True

    agents = [{"id": f"n{j}", "agent_id": aid} for j, aid in enumerate(team)]
    if not agents:
        agents = [{"id": "n0", "agent_id": "dev_fullstack"}]

    pat_id = f"pm-pat-{phase_id}"
    phase_name = spec.get("name", phase_id)

    pattern_def = PatternDef(
        id=pat_id,
        name=phase_name,
        description=task or phase_name,
        type=pattern_type,
        agents=agents,
        edges=[],
        config=config,
    )

    workflow_phase = WorkflowPhase(
        id=phase_id,
        pattern_id=pat_id,
        name=phase_name,
        description=task,
        gate=gate,
        config={"agents": team, **config},
        timeout=timeout,
    )

    return workflow_phase, pattern_def


def _build_evidence(phase_result: str, tool_calls: list | None) -> str:
    """Build phase evidence string from result + tool calls."""
    lines = [f"Result: {phase_result}"]
    if tool_calls:
        src, builds, tests = [], [], []
        for tc in tool_calls:
            tn = tc.get("name", "")
            if tn in ("code_write", "code_edit"):
                fp = str(tc.get("args", {}).get("path", "") or tc.get("args", {}).get("file_path", ""))
                if fp:
                    src.append(fp.rsplit("/", 1)[-1])
            elif tn in ("build", "docker_build", "docker_build_verify", "cicd_runner"):
                r = str(tc.get("result", ""))[:200]
                c = str(tc.get("args", {}).get("command", ""))[:80]
                builds.append(f"{tn}({c}): {r}")
            elif tn in ("test", "playwright_test", "android_test"):
                r = str(tc.get("result", ""))[:200]
                c = str(tc.get("args", {}).get("command", ""))[:80]
                tests.append(f"{tn}({c}): {r}")
        lines.append(f"Files created ({len(src)}): {', '.join(src[:10])}" if src else "Files: NONE")
        lines.append(f"Build: {'; '.join(builds[:3])}" if builds else "Build: NOT EXECUTED")
        lines.append(f"Tests: {'; '.join(tests[:3])}" if tests else "Tests: NOT EXECUTED")
    return "\n".join(lines)


async def _pm_checkpoint(
    store,
    session_id: str,
    project_id: str,
    phase_name: str,
    phase_result: str,
    history: list[str],
    catalog: list[str],
    goal: str,
    phase_tool_calls: list | None = None,
    loop_count: int = 0,
    loop_limit: int = 20,
) -> dict:
    """Ask PM agent to decide next workflow phase (v2: supports dynamic phases)."""
    import json as _json

    phase_evidence = _build_evidence(phase_result, phase_tool_calls)

    # Find PM agent
    from ..agents.store import get_agent_store
    _agent_store = get_agent_store()
    _pm_agent_id = None
    for candidate in ("product", "ai-product-manager"):
        try:
            if _agent_store.get(candidate):
                _pm_agent_id = candidate
                break
        except Exception:
            continue

    if not _pm_agent_id:
        logger.warning("PM_CHECKPOINT: no PM agent — continuing linearly")
        return {"decision": "next", "phase_id": "", "reason": "no PM agent", "findings": ""}

    prompt = _PM_DECISION_PROMPT_V2.format(
        project_id=project_id,
        phase_name=phase_name,
        phase_evidence=phase_evidence,
        history="\n".join(f"  - {h}" for h in history[-10:]),
        catalog="\n".join(f"  - {c}" for c in catalog),
        goal=goal[:500],
        patterns=_format_catalog_section(_PATTERN_CATALOG),
        agents=_build_agent_catalog(),
        templates=_format_templates_section(),
        feedback_types=_format_catalog_section(_FEEDBACK_TYPES),
        gate_types=_format_catalog_section(_GATE_TYPES),
        loop_count=loop_count,
        loop_limit=loop_limit,
    )

    try:
        from ..llm.client import get_llm_client, LLMMessage
        llm = get_llm_client()
        _sys = (
            "You are a Product Manager orchestrating an agile software project. "
            "You decide workflow progression: advance, loop, compose new phases, or finish. "
            "Respond with a SINGLE JSON object, no markdown, no explanation. "
            "Prefer composing new dynamic phases ('phase' decision) over looping the same phase repeatedly."
        )
        msgs = [
            LLMMessage(role="system", content=_sys),
            LLMMessage(role="user", content=prompt),
        ]
        result = await llm.chat(msgs)
        raw = result.content.strip()

        if "```" in raw:
            import re
            m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
            if m:
                raw = m.group(1).strip()

        decision = _json.loads(raw)
        dec_type = decision.get("decision", "?")
        logger.warning(
            "PM_CHECKPOINT phase=%s decision=%s target=%s reason=%s",
            phase_name, dec_type,
            decision.get("phase_id", "") or decision.get("phase", {}).get("name", ""),
            decision.get("reason", "")[:100],
        )
        return decision
    except Exception as e:
        logger.warning("PM_CHECKPOINT error: %s — defaulting to next", e)
        return {"decision": "next", "phase_id": "", "reason": f"error: {e}", "findings": ""}


# ── Workflow Engine ──────────────────────────────────────────────


PHASE_TIMEOUT_SECONDS = 172800  # 48h — industrial pipeline, never stop
WORKFLOW_TIMEOUT_SECONDS = (
    3600  # 1h total workflow timeout — 30min too tight with rate-limit contention
)


async def run_workflow(
    workflow: WorkflowDef,
    session_id: str,
    initial_task: str,
    project_id: str = "",
    resume_from: int = 0,
    complexity: str = "standard",
) -> WorkflowRun:
    """Execute a workflow — RTE facilitates each phase transition.

    Args:
        resume_from: phase index to resume from (skip completed phases).
        complexity: scale-adaptive level — "simple" | "standard" | "enterprise".
            Phases with min_complexity higher than this level are skipped.
            Inspired by BMAD scale-domain-adaptive planning.
    """
    run = WorkflowRun(
        workflow=workflow,
        session_id=session_id,
        project_id=project_id,
    )

    # Resolve project_path from project store (needed by file tools for workspace aliasing)
    _project_path = ""
    if project_id:
        try:
            from ..projects.manager import get_project_store as _gps

            _proj = _gps().get(project_id)
            if _proj and _proj.path:
                _project_path = _proj.path
        except Exception:
            pass
        # Fallback: auto-discover workspace directory if DB lookup failed
        if not _project_path:
            import os as _os

            _base = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
            for _candidate in [
                _os.path.join(_base, "workspace", project_id),
                _os.path.join(_base, "data", "workspaces", project_id),
            ]:
                if _os.path.isdir(_candidate):
                    _project_path = _candidate
                    logger.info("run_workflow: fallback project_path=%s", _project_path)
                    break
        if not _project_path:
            logger.warning(
                "run_workflow: no project_path for project_id=%s — agents will have NO tools",
                project_id,
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

    # Complexity levels for scale-adaptive planning (BMAD-inspired)
    _COMPLEXITY_ORDER = {"simple": 0, "standard": 1, "enterprise": 2}
    _run_complexity_level = _COMPLEXITY_ORDER.get(complexity, 1)

    accumulated_context = []
    import time as _time

    _workflow_start = _time.monotonic()

    # PM-driven workflow: mutable phase queue instead of fixed iteration
    _pm_driven = workflow.config.get("pm_driven", False)
    _phase_queue = list(workflow.phases)
    _phase_catalog = {p.id: p for p in workflow.phases}
    _pm_loop_count = 0
    _pm_loop_limit = 20
    _pm_skip_to = None
    _pm_done = False
    _pm_consecutive_loops: dict[str, int] = {}  # track consecutive loops per phase
    _dynamic_patterns: dict = {}  # PM-created patterns (phase_id → PatternDef)

    for i, phase in enumerate(_phase_queue):
        # Skip already-completed phases on resume
        if i < resume_from:
            run.phase_results.append(
                {"phase": phase.name, "success": True, "skipped": True}
            )
            continue

        # PM skip-to: skip phases until we reach the target
        if _pm_skip_to and phase.id != _pm_skip_to:
            run.phase_results.append(
                {"phase": phase.name, "success": True, "skipped": True, "reason": "pm_skip"}
            )
            continue
        _pm_skip_to = None  # reset once we reach the target

        # Scale-adaptive: skip phases requiring higher complexity than requested
        if phase.min_complexity:
            _phase_level = _COMPLEXITY_ORDER.get(phase.min_complexity, 1)
            if _phase_level > _run_complexity_level:
                run.phase_results.append(
                    {
                        "phase": phase.name,
                        "success": True,
                        "skipped": True,
                        "reason": f"min_complexity={phase.min_complexity} > run complexity={complexity}",
                    }
                )
                continue

        run.current_phase = i

        # Workflow-level timeout — prevents zombie sessions
        _elapsed = _time.monotonic() - _workflow_start
        if _elapsed > WORKFLOW_TIMEOUT_SECONDS:
            logger.warning(
                "WORKFLOW TIMEOUT after %.0fs (limit=%ds) — stopping at phase %d/%d",
                _elapsed,
                WORKFLOW_TIMEOUT_SECONDS,
                i + 1,
                len(workflow.phases),
            )
            run.status = "completed_with_gaps"
            run.phase_results.append(
                {
                    "phase": phase.name,
                    "success": False,
                    "skipped": True,
                    "reason": f"workflow_timeout ({_elapsed:.0f}s > {WORKFLOW_TIMEOUT_SECONDS}s)",
                }
            )
            break

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

        pattern = _dynamic_patterns.get(phase.id) or pattern_store.get(phase.pattern_id)
        if not pattern:
            await _rte_facilitate(
                session_id,
                f"Le pattern '{phase.pattern_id}' n'existe pas. On passe à la phase suivante.",
                to_agent=phase_leader,
                project_id=project_id,
            )
            continue

        # Override pattern agents with the phase's workflow agents
        # FIX: merge YAML phase.config into pattern.config (YAML > pattern store defaults)
        _merged_config = {**pattern.config}
        if phase.config:
            for k, v in phase.config.items():
                if k != "agents":  # agents handled separately
                    _merged_config[k] = v

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
                config=_merged_config,
                icon=pattern.icon,
            )
        else:
            pattern.config = _merged_config

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

        # Phase-level logging for diagnostics (pipeline completion tracking)
        logger.warning(
            "WORKFLOW phase_start wf=%s phase=%s (%d/%d) pattern=%s agents=%s gate=%s timeout=%d",
            workflow.id,
            phase.id,
            i + 1,
            len(workflow.phases),
            phase.pattern_id,
            phase_agents[:3],
            phase.gate,
            phase_timeout,
        )

        # Collect tool_calls from phase for PM evidence
        _phase_tool_calls: list[dict] = []

        # Build lineage for traceability: agents know WHY they exist in this workflow phase
        _lineage = []
        if run.workflow:
            _lineage.append(f"Workflow: {run.workflow.name or workflow.id}")
        if phase.name:
            _lineage.append(f"Phase: {phase.name}")
        if initial_task and len(initial_task) < 120:
            _lineage.append(f"Goal: {initial_task[:120]}")

        try:
            result = await asyncio.wait_for(
                run_pattern(
                    pattern,
                    session_id,
                    phase_task,
                    project_id,
                    project_path=_project_path,
                    lineage=_lineage,
                ),
                timeout=phase_timeout,
            )

            # Collect tool_calls from all nodes for PM evidence
            _phase_tool_calls = list(result.all_tool_calls or [])

            # Record phase result — success path
            run.phase_results.append(
                {
                    "phase": phase.name,
                    "success": result.success,
                    "error": result.error or None,
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
                # Inject build result into tool_calls for PM evidence
                _phase_tool_calls.append({
                    "name": "build",
                    "args": {"command": "auto_build_validation"},
                    "result": "[OK] Build passed" if build_ok else f"[FAIL] {build_error[:300]}",
                })
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

        except WorkflowPaused:
            # Human-in-the-loop requested a pause — save checkpoint at current phase
            _save_checkpoint(
                store, session_id, i
            )  # i not i+1: re-run this phase on resume
            run.status = "paused"
            run.phase_results.append(
                {
                    "phase": phase.name,
                    "success": False,
                    "paused": True,
                    "error": "Awaiting human validation",
                }
            )
            logger.info("Workflow paused at phase %s (%d)", phase.name, i)
            break

        except AdversarialEscalation as ae:
            # Agent exhausted retries — escalate to RTE/higher team, abort current phase
            logger.warning(
                "ADVERSARIAL ESCALATE phase=%s agent=%s score=%d — escalating to team lead",
                phase.name,
                ae.agent_name,
                ae.score,
            )
            run.phase_results.append(
                {
                    "phase": phase.name,
                    "success": False,
                    "escalated": True,
                    "error": str(ae),
                }
            )
            escalation_msg = (
                f"⚠️ **ESCALADE ADVERSARIALE** — Phase **{phase.name}**\n\n"
                f"L'agent **{ae.agent_name}** a épuisé ses tentatives (score {ae.score}/10) "
                f"sans passer le contrôle qualité :\n"
                + "\n".join(f"- {i}" for i in ae.issues[:5])
                + "\n\n"
                "**Action requise** : analyser les problèmes, corriger l'agent ou la tâche, "
                "et relancer le cycle."
            )
            await _rte_facilitate(
                session_id,
                escalation_msg,
                to_agent=leader,
                project_id=project_id,
            )
            _save_checkpoint(store, session_id, i)  # re-run this phase on next cycle
            # gate=always/best_effort/no_veto → continue despite escalation (QA still runs)
            if phase.skip_on_failure or phase.gate in ("always", "best_effort", "no_veto"):
                accumulated_context.append(
                    f"[{phase.name}] ESCALATED: {ae.agent_name} failed adversarial (score={ae.score})"
                )
                continue
            run.status = "escalated"
            break

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
                continue
            # Critical phase timeout — always continue (industrial pipeline, never stop)
            await _rte_facilitate(
                session_id,
                f"La phase **{phase.name}** a dépassé le timeout ({phase_timeout}s). "
                f"On continue malgré tout (pipeline industriel).\n{_last_summary}",
                to_agent=leader,
                project_id=project_id,
            )
            _save_checkpoint(store, session_id, i + 1)
            continue

        except Exception as e:
            if isinstance(e, AdversarialEscalation):
                raise  # already handled above — should not reach here
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
                            run_pattern(
                                pattern,
                                session_id,
                                retry_task,
                                project_id,
                                project_path=_project_path,
                                lineage=_lineage,
                            ),
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
            if phase.skip_on_failure or phase.gate in ("always", "best_effort", "no_veto"):
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

        except (asyncio.CancelledError, KeyboardInterrupt):
            # CancelledError is BaseException — must be caught explicitly
            # Without this, the entire workflow dies silently
            logger.error(
                "WORKFLOW phase %s CANCELLED (CancelledError) — saving checkpoint and continuing. wf=%s session=%s",
                phase.name,
                workflow.id,
                session_id,
            )
            run.phase_results.append(
                {
                    "phase": phase.name,
                    "success": False,
                    "error": "CancelledError",
                    "cancelled": True,
                }
            )
            _save_checkpoint(store, session_id, i + 1)
            accumulated_context.append(
                f"[{phase.name}] CANCELLED — task was interrupted"
            )
            # Continue to next phase instead of dying silently
            continue

        finally:
            logger.warning(
                "WORKFLOW phase_end wf=%s phase=%s (%d/%d) results=%d",
                workflow.id,
                phase.id,
                i + 1,
                len(_phase_queue),
                len(run.phase_results),
            )

            # PM checkpoint: let PM decide what comes next
            if _pm_driven and run.status == "running" and _pm_loop_count < _pm_loop_limit:
                try:
                    _last_result = run.phase_results[-1] if run.phase_results else {}
                    _pm_decision = await _pm_checkpoint(
                        store,
                        session_id,
                        project_id or "",
                        phase.name,
                        f"success={_last_result.get('success', '?')}",
                        accumulated_context,
                        [p.id for p in workflow.phases],
                        initial_task or "",
                        phase_tool_calls=_phase_tool_calls,
                        loop_count=_pm_loop_count,
                        loop_limit=_pm_loop_limit,
                    )
                    _pm_dec = _pm_decision.get("decision", "next")
                    _pm_target = _pm_decision.get("phase_id", "")
                    _pm_findings = _pm_decision.get("findings", "")
                    _pm_reason = _pm_decision.get("reason", "")

                    if _pm_findings:
                        accumulated_context.append(f"[PM] {_pm_findings}")

                    if _pm_dec == "done":
                        logger.warning("PM_DECISION: done — reason=%s", _pm_reason[:100])
                        accumulated_context.append(f"[PM] DONE: {_pm_reason}")
                        _pm_done = True
                        _pm_consecutive_loops.clear()

                    elif _pm_dec == "phase":
                        # v2: PM composed a dynamic phase
                        _pm_loop_count += 1
                        _pm_consecutive_loops.clear()  # phase composition resets loop counter
                        try:
                            _dyn_phase, _dyn_pattern = _build_dynamic_phase(_pm_decision)
                            _dynamic_patterns[_dyn_phase.id] = _dyn_pattern
                            _phase_catalog[_dyn_phase.id] = _dyn_phase
                            _phase_queue.insert(i + 1, _dyn_phase)
                            logger.warning(
                                "PM_DECISION: phase → %s pattern=%s team=%s (dyn %d/%d)",
                                _dyn_phase.name, _dyn_pattern.type,
                                [a["agent_id"] for a in _dyn_pattern.agents],
                                _pm_loop_count, _pm_loop_limit,
                            )
                            accumulated_context.append(
                                f"[PM] PHASE → {_dyn_phase.name} "
                                f"(pattern={_dyn_pattern.type}): {_pm_reason}"
                            )
                        except Exception as _dyn_err:
                            logger.error("PM dynamic phase build failed: %s", _dyn_err)

                    elif _pm_dec == "loop" and _pm_target:
                        _pm_loop_count += 1
                        # Track consecutive loops per phase — force advance after 3
                        _pm_consecutive_loops[_pm_target] = _pm_consecutive_loops.get(_pm_target, 0) + 1
                        _consec = _pm_consecutive_loops[_pm_target]
                        if _consec >= 3:
                            logger.warning(
                                "PM_DECISION: loop BREAKER → %s looped %d times, forcing next",
                                _pm_target, _consec,
                            )
                            accumulated_context.append(
                                f"[PM] LOOP BREAKER: {_pm_target} looped {_consec}x — advancing"
                            )
                            # Reset counter and advance linearly
                            _pm_consecutive_loops[_pm_target] = 0
                        else:
                            logger.warning(
                                "PM_DECISION: loop → %s (loop %d/%d, consec %d/3) — reason=%s",
                                _pm_target, _pm_loop_count, _pm_loop_limit, _consec, _pm_reason[:100],
                            )
                            if _pm_target in _phase_catalog:
                                _phase_queue.insert(i + 1, _phase_catalog[_pm_target])
                                accumulated_context.append(
                                    f"[PM] LOOP → {_pm_target} ({_consec}/3): {_pm_reason}"
                                )

                    elif _pm_dec == "skip" and _pm_target:
                        logger.warning(
                            "PM_DECISION: skip → %s — reason=%s",
                            _pm_target, _pm_reason[:100],
                        )
                        _pm_skip_to = _pm_target
                        _pm_consecutive_loops.clear()
                        accumulated_context.append(
                            f"[PM] SKIP → {_pm_target}: {_pm_reason}"
                        )
                    else:
                        # "next" — continue linearly (default)
                        _pm_consecutive_loops.clear()

                    # Store PM decision as a message for traceability
                    store.add_message(
                        MessageDef(
                            session_id=session_id,
                            from_agent=_pm_decision.get("_agent", "product"),
                            to_agent="all",
                            content=f"```json\n{__import__('json').dumps(_pm_decision, ensure_ascii=False)}\n```",
                            message_type="text",
                        )
                    )
                except Exception as _pm_err:
                    logger.error("PM checkpoint error: %s — continuing linearly", _pm_err, exc_info=True)

        # PM decided to stop the workflow — break OUTSIDE the finally block
        if _pm_done:
            break

    # Pipeline DoD check — verify deliverables after all phases
    if _project_path and run.status in ("completed", "running"):
        import os

        _deliverables = {
            "INCEPTION.md": os.path.exists(os.path.join(_project_path, "INCEPTION.md")),
            "Dockerfile": os.path.exists(os.path.join(_project_path, "Dockerfile")),
            "source_code": any(
                f.endswith(
                    (".vue", ".js", ".ts", ".rs", ".py", ".go", ".html", ".jsx", ".tsx")
                )
                for root, _, files in os.walk(_project_path)
                for f in files
                if ".git" not in root and "node_modules" not in root
            ),
            "tests": any(
                "test" in f.lower() or "spec" in f.lower()
                for root, _, files in os.walk(_project_path)
                for f in files
                if ".git" not in root and "node_modules" not in root
            ),
        }
        _present = [k for k, v in _deliverables.items() if v]
        _missing = [k for k, v in _deliverables.items() if not v]
        logger.warning(
            "WORKFLOW pipeline_dod wf=%s present=%s missing=%s",
            workflow.id,
            _present,
            _missing,
        )
        if _missing:
            run.status = "completed_with_gaps"

    if run.status == "running":
        run.status = "completed"

    # Update session status to match workflow outcome
    session_status = {
        "completed": "completed",
        "completed_with_gaps": "completed",
        "failed": "failed",
        "gated": "interrupted",
        "paused": "interrupted",
        "escalated": "interrupted",
    }.get(run.status, "completed")
    try:
        store.update_status(session_id, session_status)
    except Exception:
        pass

    # RTE closes the workflow (skip closing message when paused — workflow isn't done)
    if run.status in ("paused", "escalated"):
        return run

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
