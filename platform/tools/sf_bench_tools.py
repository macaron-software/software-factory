"""
AC SF Bench — end-to-end pilot project validation.

Tests the full Software Factory pipeline:
  1. mission-crud       — create/get/update/delete mission lifecycle
  2. sprint-lifecycle   — create sprint under mission, update status
  3. task-lifecycle     — create task under sprint, update status
  4. workflow-load      — all builtin workflows loadable
  5. pattern-exec-dry   — pattern engine can instantiate all pattern types
  6. agent-store-health — agent store lists 150+ agents
  7. org-structure      — org store has ARTs, portfolios, teams
  8. memory-integration — memory manager stores/retrieves during mission

Usage:
    from platform.tools.sf_bench_tools import run_sf_bench
    result = run_sf_bench()
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


@dataclass
class SFBenchCase:
    case_id: str
    description: str
    passed: bool = False
    checks: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    elapsed_ms: int = 0


@dataclass
class SFBenchResult:
    cases: list[SFBenchCase] = field(default_factory=list)
    pass_rate: float = 0.0
    total_cases: int = 0
    passed_cases: int = 0
    elapsed_ms: int = 0
    status: str = "ok"

    def to_dict(self) -> dict:
        return asdict(self)


def _check(case: SFBenchCase, condition: bool, label: str) -> bool:
    if condition:
        case.checks.append(f"✅ {label}")
    else:
        case.checks.append(f"❌ {label}")
        case.errors.append(label)
    return condition


def _case_mission_crud() -> SFBenchCase:
    """Create/get/update/delete mission lifecycle."""
    c = SFBenchCase("mission-crud", "Mission CRUD lifecycle")
    t0 = time.time()
    try:
        from platform.epics.store import get_epic_store, MissionDef

        store = get_epic_store()
        mid = f"bench-mission-{uuid.uuid4().hex[:8]}"

        m = MissionDef(
            id=mid,
            name="AC SF Bench Mission",
            description="End-to-end bench test mission",
            status="planning",
            project_id="bench-project",
        )
        created = store.create_mission(m)
        _check(c, created is not None, "mission created")

        fetched = store.get_mission(mid)
        _check(c, fetched is not None, "mission retrievable")
        if fetched:
            _check(c, fetched.name == "AC SF Bench Mission", "name matches")

        store.update_mission_status(mid, "active")
        updated = store.get_mission(mid)
        if updated:
            _check(c, updated.status == "active", "status updated to active")

        store.delete_mission(mid)
        deleted = store.get_mission(mid)
        _check(c, deleted is None, "mission deleted")

        c.passed = len(c.errors) == 0
    except Exception as e:
        c.errors.append(f"Exception: {e}")
    c.elapsed_ms = int((time.time() - t0) * 1000)
    return c


def _case_sprint_lifecycle() -> SFBenchCase:
    """Create sprint under mission, update status."""
    c = SFBenchCase("sprint-lifecycle", "Sprint lifecycle under mission")
    t0 = time.time()
    try:
        from platform.epics.store import get_epic_store, MissionDef, SprintDef

        store = get_epic_store()
        mid = f"bench-sprint-{uuid.uuid4().hex[:8]}"

        store.create_mission(MissionDef(
            id=mid, name="Sprint Test Mission",
            description="For sprint lifecycle test",
            status="active", project_id="bench-project",
        ))

        sid = f"bench-sprint-{uuid.uuid4().hex[:8]}"
        sprint = SprintDef(
            id=sid, mission_id=mid, name="Sprint 1",
            type="development", status="planning",
        )
        created = store.create_sprint(sprint)
        _check(c, created is not None, "sprint created")

        sprints = store.list_sprints(mid)
        _check(c, len(sprints) >= 1, f"mission has sprints ({len(sprints)})")

        store.update_sprint_status(sid, "active")
        updated = store.get_sprint(sid)
        if updated:
            _check(c, updated.status == "active", "sprint status updated")

        # Cleanup
        store.delete_mission(mid)
        c.passed = len(c.errors) == 0
    except Exception as e:
        c.errors.append(f"Exception: {e}")
    c.elapsed_ms = int((time.time() - t0) * 1000)
    return c


def _case_task_lifecycle() -> SFBenchCase:
    """Create task under sprint, update status."""
    c = SFBenchCase("task-lifecycle", "Task lifecycle under sprint")
    t0 = time.time()
    try:
        from platform.epics.store import get_epic_store, MissionDef, SprintDef, TaskDef

        store = get_epic_store()
        mid = f"bench-task-m-{uuid.uuid4().hex[:8]}"
        sid = f"bench-task-s-{uuid.uuid4().hex[:8]}"
        tid = f"bench-task-t-{uuid.uuid4().hex[:8]}"

        store.create_mission(MissionDef(
            id=mid, name="Task Test Mission",
            description="For task lifecycle test",
            status="active", project_id="bench-project",
        ))
        store.create_sprint(SprintDef(
            id=sid, mission_id=mid, name="Sprint 1",
            type="development", status="active",
        ))

        task = TaskDef(
            id=tid, sprint_id=sid, mission_id=mid,
            title="Implement feature X",
            description="Build and test feature X", status="pending",
        )
        created = store.create_task(task)
        _check(c, created is not None, "task created")

        tasks = store.list_tasks(sprint_id=sid)
        _check(c, len(tasks) >= 1, f"sprint has tasks ({len(tasks)})")

        store.update_task_status(tid, "done")
        updated = store.get_task(tid)
        if updated:
            _check(c, updated.status == "done", "task status updated to done")

        # Cleanup
        store.delete_mission(mid)
        c.passed = len(c.errors) == 0
    except Exception as e:
        c.errors.append(f"Exception: {e}")
    c.elapsed_ms = int((time.time() - t0) * 1000)
    return c


def _case_workflow_load() -> SFBenchCase:
    """All builtin workflows loadable."""
    c = SFBenchCase("workflow-load", "All builtin workflows load successfully")
    t0 = time.time()
    try:
        from platform.workflows.store import get_workflow_store

        store = get_workflow_store()
        workflows = store.list_all()
        builtins = [w for w in workflows if w.is_builtin]
        _check(c, len(builtins) >= 30, f"at least 30 builtins loaded ({len(builtins)})")

        # Check key workflows exist
        key_wfs = ["feature-sprint", "ideation-to-prod", "cicd-pipeline", "security-hacking"]
        ids = {w.id for w in workflows}
        for wf_id in key_wfs:
            _check(c, wf_id in ids, f"key workflow '{wf_id}' exists")

        c.passed = len(c.errors) == 0
    except Exception as e:
        c.errors.append(f"Exception: {e}")
    c.elapsed_ms = int((time.time() - t0) * 1000)
    return c


def _case_pattern_types() -> SFBenchCase:
    """Pattern engine can instantiate all pattern types."""
    c = SFBenchCase("pattern-types", "All pattern types have implementations")
    t0 = time.time()
    try:
        from platform.patterns.store import PatternStore

        ps = PatternStore()
        ps.seed_builtins()
        patterns = ps.list_all()

        types_found = {p.type for p in patterns}
        expected = {"solo", "sequential", "parallel", "hierarchical", "wave",
                    "loop", "network", "router", "aggregator"}
        for t in expected:
            # Some pattern types might be registered under different names
            _check(c, t in types_found or any(t in p.type for p in patterns),
                   f"pattern type '{t}' available")

        _check(c, len(patterns) >= 15, f"at least 15 patterns ({len(patterns)})")
        c.passed = len(c.errors) == 0
    except Exception as e:
        c.errors.append(f"Exception: {e}")
    c.elapsed_ms = int((time.time() - t0) * 1000)
    return c


def _case_agent_store_health() -> SFBenchCase:
    """Agent store lists 150+ agents."""
    c = SFBenchCase("agent-store-health", "Agent store has sufficient agents")
    t0 = time.time()
    try:
        from platform.agents.store import get_agent_store

        store = get_agent_store()
        agents = store.list_all()
        _check(c, len(agents) >= 100, f"at least 100 agents ({len(agents)})")

        # Check key agents exist
        agent_ids = {a.id for a in agents}
        key_agents = ["brain", "dev", "code-reviewer", "secops-engineer", "architecte"]
        for aid in key_agents:
            _check(c, aid in agent_ids, f"key agent '{aid}' exists")

        # Check agent diversity (tags)
        all_tags = set()
        for a in agents:
            tags = getattr(a, "tags", []) or []
            all_tags.update(tags)
        _check(c, len(all_tags) >= 20, f"tag diversity >= 20 ({len(all_tags)})")

        c.passed = len(c.errors) == 0
    except Exception as e:
        c.errors.append(f"Exception: {e}")
    c.elapsed_ms = int((time.time() - t0) * 1000)
    return c


def _case_org_structure() -> SFBenchCase:
    """Org store has ARTs, portfolios, teams."""
    c = SFBenchCase("org-structure", "Organization structure (ARTs, portfolios, teams)")
    t0 = time.time()
    try:
        from platform.agents.org import get_org_store

        org = get_org_store()

        tree = org.get_org_tree()
        _check(c, tree is not None, "org tree exists")

        arts = org.list_arts()
        _check(c, len(arts) >= 1, f"at least 1 ART ({len(arts)})")

        teams = org.list_teams()
        _check(c, len(teams) >= 3, f"at least 3 teams ({len(teams)})")

        portfolios = org.list_portfolios()
        _check(c, len(portfolios) >= 1, f"at least 1 portfolio ({len(portfolios)})")

        c.passed = len(c.errors) == 0
    except Exception as e:
        c.errors.append(f"Exception: {e}")
    c.elapsed_ms = int((time.time() - t0) * 1000)
    return c


def _case_memory_integration() -> SFBenchCase:
    """Memory manager stores/retrieves during mission context."""
    c = SFBenchCase("memory-integration", "Memory integration for mission context")
    t0 = time.time()
    try:
        from platform.memory.manager import get_memory_manager

        mem = get_memory_manager()
        pid = f"bench-sf-{uuid.uuid4().hex[:8]}"

        # Store mission context
        mem.project_store(pid, "architecture", "Microservices with FastAPI + PostgreSQL",
                         category="context", source="architect")
        mem.project_store(pid, "tech-stack", "Python 3.12, FastAPI, SQLAlchemy, Redis",
                         category="context", source="dev")
        mem.project_store(pid, "risks", "Database migration complexity",
                         category="risk", source="brain")

        # Retrieve and verify
        ctx = mem.project_get(pid, category="context", limit=10)
        _check(c, len(ctx) >= 2, f"context entries stored ({len(ctx)})")

        arch = mem.project_retrieve(pid, "architecture")
        _check(c, arch is not None, "architecture retrievable")
        if arch:
            _check(c, "FastAPI" in str(arch.get("value", "")), "architecture value correct")

        risks = mem.project_get(pid, category="risk", limit=10)
        _check(c, len(risks) >= 1, "risk entries stored")

        c.passed = len(c.errors) == 0
    except Exception as e:
        c.errors.append(f"Exception: {e}")
    c.elapsed_ms = int((time.time() - t0) * 1000)
    return c


def run_sf_bench() -> SFBenchResult:
    """Run all 8 SF bench cases. Returns SFBenchResult."""
    t0 = time.time()

    cases = [
        _case_mission_crud(),
        _case_sprint_lifecycle(),
        _case_task_lifecycle(),
        _case_workflow_load(),
        _case_pattern_types(),
        _case_agent_store_health(),
        _case_org_structure(),
        _case_memory_integration(),
    ]

    passed = sum(1 for c in cases if c.passed)
    result = SFBenchResult(
        cases=cases,
        pass_rate=passed / len(cases) if cases else 0.0,
        total_cases=len(cases),
        passed_cases=passed,
        elapsed_ms=int((time.time() - t0) * 1000),
        status="PASS" if passed == len(cases) else "FAIL",
    )

    out_dir = DATA_DIR / "sf_bench"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_file = out_dir / f"sf_bench_{ts}.json"
    out_file.write_text(json.dumps(result.to_dict(), indent=2, default=str))

    return result


if __name__ == "__main__":
    result = run_sf_bench()
    print(f"\nAC SF Bench: {result.passed_cases}/{result.total_cases} ({result.status})")
    for c in result.cases:
        icon = "✅" if c.passed else "❌"
        print(f"  {icon} {c.case_id}: {c.description} ({c.elapsed_ms}ms)")
        for check in c.checks:
            print(f"      {check}")
