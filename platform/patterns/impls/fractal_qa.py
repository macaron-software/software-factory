"""Fractal QA pattern — recursive decomposition into atomic BDD/Gherkin scenarios.

Source: TinyAGI/fractals (MIT) — fractal vertical applied to QA/behavior layer.
Decision: decompose acceptance criteria into atomic Given/When/Then scenarios.
Each leaf scenario is runnable via playwright MCP or a test executor.
Backprop-merge aggregates scenario results into a QA report.

Fractal vertical position (deepest layer):
  Vision → Epic → Story (fractal-stories)
               → Test Suite → Test Case (fractal-tests)
               → QA Scenario (fractal-qa)  ← this pattern
"""
# Ref: feat-patterns

from __future__ import annotations
import asyncio
import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

MAX_DEPTH = 3
MAX_CHILDREN = 5


def _classify_prompt_qa(item: str, depth: int) -> str:
    return (
        f"[FRACTAL QA — CLASSIFY]\n"
        f"Item: {item}\n\n"
        f"Is this an atomic Gherkin scenario (single Given/When/Then) "
        f"or does it cover multiple behaviors that should be separate scenarios?\n\n"
        f"Reply with exactly one word: ATOMIC or COMPOSITE."
    )


def _decompose_prompt_qa(item: str, max_children: int) -> str:
    return (
        f"[FRACTAL QA — DECOMPOSE]\n"
        f"Behavior: {item}\n\n"
        f"Break this into at most {max_children} atomic Gherkin scenarios.\n"
        f"Each scenario must:\n"
        f"  - Have exactly one Given, one When, one Then\n"
        f"  - Test exactly one observable behavior\n"
        f"  - Be independently executable\n\n"
        f"Format: one scenario per line, prefixed with a dash.\n"
        f"Example: '- Given logged in user, When they upload file >10MB, Then error message shown'\n"
        f"No explanations — just the scenario list."
    )


def _scenario_prompt(scenario: str, lineage: list[str]) -> str:
    lineage_chain = " → ".join(lineage) if lineage else ""
    return (
        f"[FRACTAL QA — EXECUTE SCENARIO]\n"
        f"Scenario: {scenario}\n"
        f"Lineage: {lineage_chain}\n\n"
        f"Write and execute a Gherkin-style validation for this scenario.\n"
        f"Format your response as:\n"
        f"SCENARIO: <title>\n"
        f"GIVEN: <precondition>\n"
        f"WHEN: <action>\n"
        f"THEN: <expected result>\n"
        f"RESULT: PASS|FAIL|PENDING\n"
        f"NOTES: <any observations>"
    )


def _parse_scenarios(text: str) -> list[str]:
    items = []
    for line in text.split("\n"):
        line = line.strip()
        m = re.match(r'^[-*•]\s+(.+)', line) or re.match(r'^\d+[.)]\s+(.+)', line)
        if m:
            items.append(m.group(1).strip())
        elif line and line[0] not in ('#', '[', '-', '*') and len(line) > 15:
            items.append(line)
    return items[:MAX_CHILDREN]


@dataclass
class QANode:
    item: str
    depth: int
    node_type: str = "pending"
    children: list["QANode"] = field(default_factory=list)
    result: str = ""
    passed: bool | None = None
    lineage: list[str] = field(default_factory=list)


async def _build_qa_tree(engine, run, planner_id: str, item: str, depth: int, parent_lineage: list[str]) -> QANode:
    lineage = parent_lineage + [f"Scenario: {item[:80]}"]
    node = QANode(item=item, depth=depth, lineage=lineage)

    if depth >= MAX_DEPTH:
        node.node_type = "atomic"
        return node

    classify_out = await engine._execute_node(run, planner_id, _classify_prompt_qa(item, depth))
    is_atomic = "ATOMIC" in classify_out.upper() or "COMPOSITE" not in classify_out.upper()

    if is_atomic:
        node.node_type = "atomic"
        return node

    node.node_type = "composite"
    decompose_out = await engine._execute_node(run, planner_id, _decompose_prompt_qa(item, MAX_CHILDREN))
    scenario_items = _parse_scenarios(decompose_out)
    if not scenario_items:
        node.node_type = "atomic"
        return node

    child_tasks = [_build_qa_tree(engine, run, planner_id, si, depth+1, parent_lineage) for si in scenario_items]
    node.children = await asyncio.gather(*child_tasks)
    return node


def _collect_qa_leaves(node: QANode) -> list[QANode]:
    if node.node_type == "atomic":
        return [node]
    leaves = []
    for child in node.children:
        leaves.extend(_collect_qa_leaves(child))
    return leaves


async def run_fractal_qa(engine, run, task: str) -> None:
    """Fractal QA pattern — decomposes acceptance criteria into atomic BDD scenarios.

    Each scenario is executed by a QA agent and results are aggregated.
    PASS/FAIL tracked per scenario with full lineage traceability.

    Use for: acceptance testing, regression QA, behavior validation.
    """
    from ..engine import _sse

    nodes = engine._ordered_nodes(run.pattern)
    if not nodes:
        return

    planner_id = nodes[0]
    worker_ids = nodes[1:] if len(nodes) > 1 else [planner_id]
    parent_lineage = list(run.lineage) if run.lineage else []

    await _sse(run, {"type": "message", "content": "🔍 **Fractal QA PLAN**: decomposing into atomic BDD scenarios..."})
    root = await _build_qa_tree(engine, run, planner_id, task, depth=0, parent_lineage=parent_lineage)

    leaves = _collect_qa_leaves(root)
    logger.info("fractal_qa: %d QA scenarios", len(leaves))
    await _sse(run, {"type": "message", "content": f"🔍 **{len(leaves)} scenarios** to validate..."})

    async def execute_scenario(i: int, leaf: QANode) -> None:
        worker_id = worker_ids[i % len(worker_ids)]
        original_lineage = run.lineage
        run.lineage = leaf.lineage
        try:
            leaf.result = await engine._execute_node(run, worker_id, _scenario_prompt(leaf.item, leaf.lineage))
            leaf.passed = "RESULT: PASS" in leaf.result.upper()
            try:
                from ...traceability.store import log_artifact
                status = "PASS" if leaf.passed else "FAIL"
                log_artifact(run.session_id, "qa", leaf.item[:120], leaf.lineage,
                             f"QA scenario {status}: {leaf.item}")
            except Exception:
                pass
        finally:
            run.lineage = original_lineage

    await asyncio.gather(*[execute_scenario(i, leaf) for i, leaf in enumerate(leaves)], return_exceptions=True)

    passed = sum(1 for l in leaves if l.passed is True)
    failed = sum(1 for l in leaves if l.passed is False)
    pending = len(leaves) - passed - failed

    report = "\n".join(
        f"{'✅' if l.passed else '❌' if l.passed is False else '⏳'} {l.item[:70]}"
        for l in leaves
    )
    await _sse(run, {
        "type": "message",
        "content": f"📊 **QA Report**: {passed} PASS / {failed} FAIL / {pending} PENDING\n\n{report}"
    })
