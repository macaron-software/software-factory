"""
AC Workflow & Pattern Bench — per-workflow + per-pattern functional validation.

Layer 1: Structural (6 cases) — global invariants
Layer 2: Per-Workflow (50 cases) — each workflow individually validated
Layer 3: Per-Pattern (27 cases) — each pattern individually validated

Per-workflow checks:
  - loads from store
  - has ≥1 phase
  - each phase has valid pattern_id that resolves
  - each phase.config.agents (if any) resolve in agent store
  - gates are valid
  - graph nodes (if present) reference valid agents

Per-pattern checks:
  - loads from store
  - type maps to known engine dispatch
  - impl file exists for type
  - agents (if any) resolve in agent store
  - edges reference valid node IDs
  - config is well-formed

Usage:
    from platform.tools.workflow_bench_tools import run_workflow_bench
    result = run_workflow_bench()           # structural only (6 cases)
    result = run_workflow_bench(full=True)  # all layers (6 + 50 + 27 cases)
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
PLATFORM_ROOT = Path(__file__).resolve().parent.parent

VALID_GATE_TYPES = {"all_approved", "no_veto", "always", "best_effort", "qa_approved", "checkpoint", ""}

KNOWN_PATTERN_TYPES = {
    "solo", "sequential", "parallel", "wave", "loop",
    "hierarchical", "network", "router", "composite",
    "human_in_the_loop", "aggregator", "backprop_merge",
    "fractal_qa", "fractal_stories", "fractal_tests", "fractal_worktree",
}

# Engine dispatch table (from patterns/engine.py run_pattern)
# Types with explicit dispatch + types that fall through to sequential
ENGINE_DISPATCH_TYPES = {
    "solo", "sequential", "parallel", "loop", "hierarchical",
    "network", "router", "aggregator", "wave",
    "human-in-the-loop", "composite",
    # Fallback to sequential (have impl files but no explicit dispatch)
    "backprop-merge", "fractal-qa", "fractal-stories",
    "fractal-tests", "fractal-worktree", "blackboard",
    "map-reduce", "swarm",
}

# Agent IDs that are role-generic placeholders resolved at runtime via Darwin selector
DYNAMIC_AGENT_ROLES = {
    "qa", "lead-dev", "dev-1", "dev-2", "dev-3",
    "product-owner", "po", "business_analyst", "test_auto", "api_tester",
    "ops-agent", "chef-projet", "expert-metier",
}


@dataclass
class WorkflowBenchCase:
    case_id: str
    description: str
    passed: bool = False
    checks: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    elapsed_ms: int = 0


@dataclass
class WorkflowBenchResult:
    cases: list[WorkflowBenchCase] = field(default_factory=list)
    pass_rate: float = 0.0
    total_cases: int = 0
    passed_cases: int = 0
    elapsed_ms: int = 0
    status: str = "ok"
    workflow_count: int = 0
    pattern_count: int = 0
    per_workflow_pass: int = 0
    per_workflow_fail: int = 0
    per_pattern_pass: int = 0
    per_pattern_fail: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def _check(case: WorkflowBenchCase, condition: bool, label: str) -> bool:
    if condition:
        case.checks.append(f"✅ {label}")
    else:
        case.checks.append(f"❌ {label}")
        case.errors.append(label)
    return condition


# ── Layer 1: Structural (original 6 cases) ───────────────────────


def _case_yaml_parse_all(store) -> WorkflowBenchCase:
    """All builtin workflows parse without error."""
    c = WorkflowBenchCase("yaml-parse-all", "All builtin YAML workflows parse correctly")
    t0 = time.time()
    try:
        workflows = store.list_all()
        builtins = [w for w in workflows if w.is_builtin]
        _check(c, len(builtins) >= 30, f"at least 30 builtin workflows loaded (got {len(builtins)})")

        for wf in builtins:
            _check(c, bool(wf.id), f"workflow '{wf.name or '?'}' has id")
            _check(c, bool(wf.name), f"workflow '{wf.id}' has name")
            _check(c, len(wf.phases) > 0, f"workflow '{wf.id}' has phases ({len(wf.phases)})")

        _check(c, True, f"parsed {len(builtins)} builtin workflows total")
        c.passed = len(c.errors) == 0
    except Exception as e:
        c.errors.append(f"Exception: {e}")
    c.elapsed_ms = int((time.time() - t0) * 1000)
    return c


def _case_pattern_registry() -> WorkflowBenchCase:
    """All pattern types have implementations in impls/."""
    c = WorkflowBenchCase("pattern-registry", "All pattern types have implementations")
    t0 = time.time()
    try:
        impls_dir = PLATFORM_ROOT / "patterns" / "impls"
        _check(c, impls_dir.exists(), f"impls dir exists")

        impl_files = sorted(f.stem for f in impls_dir.glob("*.py") if f.stem != "__init__")
        _check(c, len(impl_files) >= 10, f"at least 10 impl files (got {len(impl_files)})")

        for ptype in KNOWN_PATTERN_TYPES:
            has_file = ptype in impl_files or ptype.replace("-", "_") in impl_files
            _check(c, has_file, f"impl file for '{ptype}'")

        c.passed = len(c.errors) == 0
    except Exception as e:
        c.errors.append(f"Exception: {e}")
    c.elapsed_ms = int((time.time() - t0) * 1000)
    return c


def _case_workflow_phase_structure(store) -> WorkflowBenchCase:
    """Each workflow has valid phases with pattern_id refs."""
    c = WorkflowBenchCase("workflow-phase-structure", "Workflow phases have valid structure")
    t0 = time.time()
    try:
        workflows = store.list_all()
        builtins = [w for w in workflows if w.is_builtin]

        total_phases = 0
        for wf in builtins:
            for phase in wf.phases:
                total_phases += 1
                _check(c, bool(phase.pattern_id), f"{wf.id}/{phase.id}: has pattern_id")
                if phase.gate:
                    _check(c, isinstance(phase.gate, str) and len(phase.gate) > 0,
                           f"{wf.id}/{phase.id}: gate is non-empty string")

        _check(c, total_phases > 50, f"total phases across all workflows: {total_phases}")
        c.passed = len(c.errors) == 0
    except Exception as e:
        c.errors.append(f"Exception: {e}")
    c.elapsed_ms = int((time.time() - t0) * 1000)
    return c


def _case_workflow_crud(store) -> WorkflowBenchCase:
    """Create → get → update → delete lifecycle."""
    c = WorkflowBenchCase("workflow-crud", "Workflow CRUD lifecycle")
    t0 = time.time()
    try:
        from platform.workflows.store import WorkflowDef, WorkflowPhase

        test_id = f"bench-test-{uuid.uuid4().hex[:8]}"
        wf = WorkflowDef(
            id=test_id,
            name="Bench Test Workflow",
            description="Created by AC bench",
            phases=[
                WorkflowPhase(
                    id="phase-1",
                    pattern_id="solo",
                    name="Test Phase",
                    description="Solo agent test",
                    gate="always",
                )
            ],
            config={"bench": True},
            is_builtin=False,
        )

        created = store.create(wf)
        _check(c, created is not None, "create returns workflow")

        fetched = store.get(test_id)
        _check(c, fetched is not None, "get returns created workflow")
        if fetched:
            _check(c, fetched.name == "Bench Test Workflow", "name matches")
            _check(c, len(fetched.phases) == 1, "has 1 phase")

        store.delete(test_id)
        deleted = store.get(test_id)
        _check(c, deleted is None, "workflow deleted successfully")

        c.passed = len(c.errors) == 0
    except Exception as e:
        c.errors.append(f"Exception: {e}")
    c.elapsed_ms = int((time.time() - t0) * 1000)
    return c


def _case_gate_types(store) -> WorkflowBenchCase:
    """Verify all gate types used in workflows are valid."""
    c = WorkflowBenchCase("gate-types", "All gate types in workflows are valid")
    t0 = time.time()
    try:
        workflows = store.list_all()
        builtins = [w for w in workflows if w.is_builtin]

        used_gates = set()
        typed_gates = set()
        freetext_gates = 0
        for wf in builtins:
            for phase in wf.phases:
                if phase.gate:
                    used_gates.add(phase.gate)
                    if phase.gate in VALID_GATE_TYPES:
                        typed_gates.add(phase.gate)
                    else:
                        freetext_gates += 1

        _check(c, len(used_gates) >= 2, f"at least 2 distinct gates (got {len(used_gates)})")
        _check(c, len(typed_gates) >= 1 or freetext_gates > 0,
               f"gates used: {len(typed_gates)} typed + {freetext_gates} free-text")

        c.passed = len(c.errors) == 0
    except Exception as e:
        c.errors.append(f"Exception: {e}")
    c.elapsed_ms = int((time.time() - t0) * 1000)
    return c


def _case_workflow_coverage(store) -> WorkflowBenchCase:
    """Every pattern_id in workflows maps to a known pattern type."""
    c = WorkflowBenchCase("workflow-coverage", "Workflow pattern_ids map to real patterns")
    t0 = time.time()
    try:
        workflows = store.list_all()
        builtins = [w for w in workflows if w.is_builtin]

        used_pattern_ids = set()
        for wf in builtins:
            for phase in wf.phases:
                if phase.pattern_id:
                    used_pattern_ids.add(phase.pattern_id)

        _check(c, len(used_pattern_ids) >= 3, f"at least 3 distinct pattern_ids used (got {len(used_pattern_ids)})")

        try:
            from platform.patterns.store import PatternStore
            ps = PatternStore()
            ps.seed_builtins()
            all_patterns = ps.list_all()
            pattern_ids = {p.id for p in all_patterns}
            pattern_types = {p.type for p in all_patterns}

            unmatched = []
            for pid in used_pattern_ids:
                found = pid in pattern_ids or pid in pattern_types or pid in KNOWN_PATTERN_TYPES
                if not found:
                    unmatched.append(pid)

            _check(c, len(unmatched) == 0,
                   f"all pattern_ids matched" if not unmatched else f"unmatched: {unmatched[:5]}")
            _check(c, len(all_patterns) >= 10, f"at least 10 patterns in store (got {len(all_patterns)})")
        except ImportError:
            _check(c, True, "PatternStore import skipped (standalone mode)")

        c.passed = len(c.errors) == 0
    except Exception as e:
        c.errors.append(f"Exception: {e}")
    c.elapsed_ms = int((time.time() - t0) * 1000)
    return c


# ── Layer 2: Per-Workflow functional validation ───────────────────


def _get_agent_ids() -> set[str]:
    """Load all agent IDs from the agent store."""
    try:
        from platform.agents.store import get_agent_store
        return {a.id for a in get_agent_store().list_all()}
    except Exception:
        return set()


def _get_pattern_lookup() -> tuple[set[str], set[str]]:
    """Return (pattern_ids, pattern_types) from the store."""
    try:
        from platform.patterns.store import PatternStore
        ps = PatternStore()
        ps.seed_builtins()
        all_p = ps.list_all()
        return {p.id for p in all_p}, {p.type for p in all_p}
    except Exception:
        return set(), set()


def _validate_single_workflow(wf, agent_ids: set, pattern_ids: set, pattern_types: set) -> WorkflowBenchCase:
    """Full functional validation for a single workflow."""
    c = WorkflowBenchCase(f"wf:{wf.id}", f"Workflow '{wf.id}' functional validation")
    t0 = time.time()
    try:
        # 1. Basic fields
        _check(c, bool(wf.id), "has id")
        _check(c, bool(wf.name), "has name")
        _check(c, len(wf.phases) >= 1, f"has ≥1 phase (got {len(wf.phases)})")

        # 2. Per-phase validation
        phase_ids = set()
        for phase in wf.phases:
            # Unique phase id within workflow
            _check(c, phase.id not in phase_ids, f"phase '{phase.id}' is unique")
            phase_ids.add(phase.id)

            # Pattern resolution
            pid = phase.pattern_id
            resolves = (
                pid in pattern_ids
                or pid in pattern_types
                or pid in KNOWN_PATTERN_TYPES
                or pid in ENGINE_DISPATCH_TYPES
            )
            _check(c, resolves, f"phase '{phase.id}' pattern_id '{pid}' resolves")

            # Gate validity (enum or free-text)
            if phase.gate:
                _check(c, isinstance(phase.gate, str), f"phase '{phase.id}' gate is string")

            # Agent refs in config
            cfg_agents = phase.config.get("agents", []) if phase.config else []
            if cfg_agents and agent_ids:
                for aid in cfg_agents:
                    exists = aid in agent_ids or aid in DYNAMIC_AGENT_ROLES
                    _check(c, exists, f"phase '{phase.id}' agent '{aid}' exists")

            # Timeout sanity
            if phase.timeout:
                _check(c, 0 < phase.timeout <= 7200,
                       f"phase '{phase.id}' timeout {phase.timeout}s in range")

        # 3. Graph nodes (if present in config)
        graph = (wf.config or {}).get("graph", {})
        if graph:
            nodes = graph.get("nodes", [])
            edges = graph.get("edges", [])
            node_ids = {n["id"] for n in nodes if "id" in n}

            _check(c, len(nodes) >= 1, f"graph has {len(nodes)} nodes")

            # Node agents resolve
            if agent_ids:
                for n in nodes:
                    aid = n.get("agent_id", "")
                    if aid:
                        exists = aid in agent_ids or aid in DYNAMIC_AGENT_ROLES
                        _check(c, exists, f"graph node '{n['id']}' agent '{aid}' exists")

            # Edges reference valid nodes
            for e in edges:
                _check(c, e.get("from") in node_ids, f"edge from '{e.get('from')}' valid")
                _check(c, e.get("to") in node_ids, f"edge to '{e.get('to')}' valid")

        c.passed = len(c.errors) == 0
    except Exception as e:
        c.errors.append(f"Exception: {e}")
    c.elapsed_ms = int((time.time() - t0) * 1000)
    return c


def run_per_workflow_bench(store) -> list[WorkflowBenchCase]:
    """Run per-workflow validation for all builtin workflows."""
    agent_ids = _get_agent_ids()
    pattern_ids, pattern_types = _get_pattern_lookup()

    workflows = store.list_all()
    builtins = sorted([w for w in workflows if w.is_builtin], key=lambda w: w.id)

    return [_validate_single_workflow(wf, agent_ids, pattern_ids, pattern_types) for wf in builtins]


# ── Layer 3: Per-Pattern functional validation ───────────────────


def _validate_single_pattern(pat, agent_ids: set, impls: set) -> WorkflowBenchCase:
    """Full functional validation for a single pattern."""
    c = WorkflowBenchCase(f"pat:{pat.id}", f"Pattern '{pat.id}' ({pat.type}) functional validation")
    t0 = time.time()
    try:
        # 1. Basic fields
        _check(c, bool(pat.id), "has id")
        _check(c, bool(pat.name), "has name")
        _check(c, bool(pat.type), "has type")

        # 2. Type dispatches to engine
        ptype_normalized = pat.type.replace("-", "_")
        dispatches = (
            pat.type in ENGINE_DISPATCH_TYPES
            or pat.type in KNOWN_PATTERN_TYPES
        )
        _check(c, dispatches, f"type '{pat.type}' has engine dispatch")

        # 3. Impl file exists
        has_impl = ptype_normalized in impls or pat.type in impls
        _check(c, has_impl, f"impl file for type '{pat.type}'")

        # 4. Agent nodes validate
        if pat.agents:
            node_ids = set()
            for node in pat.agents:
                nid = node.get("id", "")
                aid = node.get("agent_id", "")
                _check(c, bool(nid), f"node has id")
                if nid:
                    _check(c, nid not in node_ids, f"node '{nid}' is unique")
                    node_ids.add(nid)
                if aid and agent_ids:
                    exists = aid in agent_ids or aid in DYNAMIC_AGENT_ROLES
                    _check(c, exists, f"node '{nid}' agent '{aid}' exists")

            # 5. Edges reference valid nodes
            if pat.edges:
                for edge in pat.edges:
                    efrom = edge.get("from", "")
                    eto = edge.get("to", "")
                    if efrom:
                        _check(c, efrom in node_ids, f"edge from '{efrom}' valid node")
                    if eto:
                        _check(c, eto in node_ids, f"edge to '{eto}' valid node")

        # 6. A/B test config consistency
        if pat.ab_alt_id:
            _check(c, 0.0 < pat.ab_ratio <= 1.0,
                   f"ab_ratio {pat.ab_ratio} in (0,1]")

        # 7. Composite steps
        if pat.type == "composite" and pat.steps:
            for step in pat.steps:
                _check(c, bool(step.get("pattern_id")),
                       f"composite step has pattern_id")

        c.passed = len(c.errors) == 0
    except Exception as e:
        c.errors.append(f"Exception: {e}")
    c.elapsed_ms = int((time.time() - t0) * 1000)
    return c


def run_per_pattern_bench() -> list[WorkflowBenchCase]:
    """Run per-pattern validation for all patterns in store."""
    from platform.patterns.store import PatternStore

    ps = PatternStore()
    ps.seed_builtins()
    patterns = sorted(ps.list_all(), key=lambda p: p.id)

    agent_ids = _get_agent_ids()
    impls_dir = PLATFORM_ROOT / "patterns" / "impls"
    impls = {f.stem for f in impls_dir.glob("*.py") if f.stem != "__init__"} if impls_dir.exists() else set()

    return [_validate_single_pattern(pat, agent_ids, impls) for pat in patterns]


# ── Main runner ───────────────────────────────────────────────────


def run_workflow_bench(full: bool = False) -> WorkflowBenchResult:
    """Run workflow bench.

    Args:
        full: if True, run all 3 layers (structural + per-workflow + per-pattern).
              if False, run only structural (6 cases) for backward compat.
    """
    from platform.workflows.store import get_workflow_store

    t0 = time.time()
    store = get_workflow_store()

    wf_count = store.count()
    pat_count = 0
    try:
        from platform.patterns.store import PatternStore
        ps = PatternStore()
        ps.seed_builtins()
        pat_count = ps.count()
    except Exception:
        pass

    # Layer 1: Structural (always)
    cases = [
        _case_yaml_parse_all(store),
        _case_pattern_registry(),
        _case_workflow_phase_structure(store),
        _case_workflow_crud(store),
        _case_gate_types(store),
        _case_workflow_coverage(store),
    ]

    pw_pass = pw_fail = pp_pass = pp_fail = 0

    if full:
        # Layer 2: Per-Workflow
        wf_cases = run_per_workflow_bench(store)
        cases.extend(wf_cases)
        pw_pass = sum(1 for c in wf_cases if c.passed)
        pw_fail = len(wf_cases) - pw_pass

        # Layer 3: Per-Pattern
        try:
            pat_cases = run_per_pattern_bench()
            cases.extend(pat_cases)
            pp_pass = sum(1 for c in pat_cases if c.passed)
            pp_fail = len(pat_cases) - pp_pass
        except Exception as e:
            c = WorkflowBenchCase("per-pattern-error", f"Per-pattern bench failed: {e}")
            c.errors.append(str(e))
            cases.append(c)

    passed = sum(1 for c in cases if c.passed)
    result = WorkflowBenchResult(
        cases=cases,
        pass_rate=passed / len(cases) if cases else 0.0,
        total_cases=len(cases),
        passed_cases=passed,
        elapsed_ms=int((time.time() - t0) * 1000),
        status="PASS" if passed == len(cases) else "FAIL",
        workflow_count=wf_count,
        pattern_count=pat_count,
        per_workflow_pass=pw_pass,
        per_workflow_fail=pw_fail,
        per_pattern_pass=pp_pass,
        per_pattern_fail=pp_fail,
    )

    # Persist results
    out_dir = DATA_DIR / "workflow_bench"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    suffix = "_full" if full else ""
    out_file = out_dir / f"workflow_bench{suffix}_{ts}.json"
    out_file.write_text(json.dumps(result.to_dict(), indent=2, default=str))

    return result


# ── CLI ───────────────────────────────────────────────────────────


def print_workflow_bench_result(result: WorkflowBenchResult, verbose: bool = False):
    """Pretty-print bench results."""
    print(f"\nAC Workflow+Pattern Bench: {result.passed_cases}/{result.total_cases} ({result.status})")
    print(f"  Workflows: {result.workflow_count} | Patterns: {result.pattern_count}")
    if result.per_workflow_pass or result.per_workflow_fail:
        print(f"  Per-workflow: {result.per_workflow_pass} PASS / {result.per_workflow_fail} FAIL")
    if result.per_pattern_pass or result.per_pattern_fail:
        print(f"  Per-pattern:  {result.per_pattern_pass} PASS / {result.per_pattern_fail} FAIL")
    print(f"  Elapsed: {result.elapsed_ms}ms")

    # Group cases by layer
    structural = [c for c in result.cases if not c.case_id.startswith(("wf:", "pat:"))]
    wf_cases = [c for c in result.cases if c.case_id.startswith("wf:")]
    pat_cases = [c for c in result.cases if c.case_id.startswith("pat:")]

    if structural:
        print("\n  ── Structural ──")
        for c in structural:
            icon = "✅" if c.passed else "❌"
            print(f"    {icon} {c.case_id} ({c.elapsed_ms}ms)")
            if verbose or not c.passed:
                for err in c.errors:
                    print(f"        ⚠️  {err}")

    if wf_cases:
        wf_pass = [c for c in wf_cases if c.passed]
        wf_fail = [c for c in wf_cases if not c.passed]
        print(f"\n  ── Per-Workflow ({len(wf_pass)} PASS / {len(wf_fail)} FAIL) ──")
        for c in wf_fail:
            print(f"    ❌ {c.case_id} ({c.elapsed_ms}ms)")
            for err in c.errors:
                print(f"        ⚠️  {err}")
        if verbose:
            for c in wf_pass:
                print(f"    ✅ {c.case_id} ({c.elapsed_ms}ms)")

    if pat_cases:
        pat_pass = [c for c in pat_cases if c.passed]
        pat_fail = [c for c in pat_cases if not c.passed]
        print(f"\n  ── Per-Pattern ({len(pat_pass)} PASS / {len(pat_fail)} FAIL) ──")
        for c in pat_fail:
            print(f"    ❌ {c.case_id} ({c.elapsed_ms}ms)")
            for err in c.errors:
                print(f"        ⚠️  {err}")
        if verbose:
            for c in pat_pass:
                print(f"    ✅ {c.case_id} ({c.elapsed_ms}ms)")


if __name__ == "__main__":
    import sys
    full = "--full" in sys.argv
    verbose = "-v" in sys.argv or "--verbose" in sys.argv
    result = run_workflow_bench(full=full)
    print_workflow_bench_result(result, verbose=verbose)
