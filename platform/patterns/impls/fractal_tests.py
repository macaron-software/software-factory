"""Fractal Tests pattern — recursive decomposition of acceptance criteria into test cases.

Source: TinyAGI/fractals (MIT) — fractal vertical applied to test layer.
Decision: generate tests bottom-up from acceptance criteria, not top-down from code.
Each leaf test includes its lineage as a docstring — answers "why does this test exist?"

This is the "test fractal" layer in the fractal vertical stack:
  Story (fractal-stories) → Acceptance Criteria → Test Suite → Test Case → Assertion
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

LEVEL_NAMES = ["Feature", "TestSuite", "TestCase", "Assertion"]


def _classify_prompt_tests(item: str, depth: int) -> str:
    level = LEVEL_NAMES[min(depth, len(LEVEL_NAMES)-1)]
    return (
        f"[FRACTAL TESTS — CLASSIFY]\n"
        f"Level: {level}\n"
        f"Item: {item}\n\n"
        f"Is this a single atomic test case (one assertion, one scenario) "
        f"or does it need to be split into multiple test cases?\n\n"
        f"Reply with exactly one word: ATOMIC or COMPOSITE."
    )


def _decompose_prompt_tests(item: str, depth: int, max_children: int) -> str:
    level = LEVEL_NAMES[min(depth, len(LEVEL_NAMES)-1)]
    next_level = LEVEL_NAMES[min(depth+1, len(LEVEL_NAMES)-1)]
    return (
        f"[FRACTAL TESTS — DECOMPOSE]\n"
        f"Test item ({level}): {item}\n\n"
        f"Break this into at most {max_children} concrete {next_level}s.\n"
        f"Each {next_level} must test exactly ONE behavior or scenario.\n"
        f"Include: happy path, error cases, edge cases, boundary values.\n\n"
        f"Format: one test per line, prefixed with a dash.\n"
        f"Be specific: 'test login with expired token returns 401' not 'test auth'."
    )


def _generate_test_prompt(test_case: str, lineage: list[str]) -> str:
    lineage_chain = " → ".join(lineage) if lineage else "unknown"
    return (
        f"[FRACTAL TESTS — GENERATE]\n"
        f"Write a test for: {test_case}\n\n"
        f"Lineage (why this test exists):\n{lineage_chain}\n\n"
        f"Requirements:\n"
        f"1. Use pytest style (def test_...)\n"
        f"2. Include a docstring with the lineage chain\n"
        f"3. One assertion per test function\n"
        f"4. Include arrange/act/assert comments\n"
        f"5. Mock external dependencies\n\n"
        f"Output ONLY the test function code, no explanations."
    )


def _parse_test_cases(text: str) -> list[str]:
    items = []
    for line in text.split("\n"):
        line = line.strip()
        m = re.match(r'^[-*•]\s+(.+)', line) or re.match(r'^\d+[.)]\s+(.+)', line)
        if m:
            items.append(m.group(1).strip())
        elif line and line[0] not in ('#', '[', '-', '*') and len(line) > 10:
            items.append(line)
    return items[:MAX_CHILDREN]


@dataclass
class TestNode:
    item: str
    depth: int
    node_type: str = "pending"
    children: list["TestNode"] = field(default_factory=list)
    result: str = ""
    lineage: list[str] = field(default_factory=list)


async def _build_test_tree(engine, run, planner_id: str, item: str, depth: int, parent_lineage: list[str]) -> TestNode:
    level_name = LEVEL_NAMES[min(depth, len(LEVEL_NAMES)-1)]
    lineage = parent_lineage + [f"{level_name}: {item[:80]}"]
    node = TestNode(item=item, depth=depth, lineage=lineage)

    if depth >= MAX_DEPTH:
        node.node_type = "atomic"
        return node

    classify_out = await engine._execute_node(run, planner_id, _classify_prompt_tests(item, depth))
    is_atomic = "ATOMIC" in classify_out.upper() or "COMPOSITE" not in classify_out.upper()

    if is_atomic:
        node.node_type = "atomic"
        return node

    node.node_type = "composite"
    decompose_out = await engine._execute_node(run, planner_id, _decompose_prompt_tests(item, depth, MAX_CHILDREN))
    children_items = _parse_test_cases(decompose_out)
    if not children_items:
        node.node_type = "atomic"
        return node

    child_tasks = [_build_test_tree(engine, run, planner_id, ci, depth+1, lineage) for ci in children_items]
    node.children = await asyncio.gather(*child_tasks)
    return node


def _collect_test_leaves(node: TestNode) -> list[TestNode]:
    if node.node_type == "atomic":
        return [node]
    leaves = []
    for child in node.children:
        leaves.extend(_collect_test_leaves(child))
    return leaves


async def run_fractal_tests(engine, run, task: str) -> None:
    """Fractal Tests pattern — decomposes acceptance criteria into atomic test cases.

    Each generated test includes its lineage chain in the docstring:
      Why: Feature[auth] → TestSuite[JWT validation] → TestCase[expired token → 401]

    Use for: TDD test generation, acceptance test suites, regression coverage.
    """
    from ..engine import _sse

    nodes = engine._ordered_nodes(run.pattern)
    if not nodes:
        return

    planner_id = nodes[0]
    worker_ids = nodes[1:] if len(nodes) > 1 else [planner_id]
    parent_lineage = list(run.lineage) if run.lineage else []

    await _sse(run, {"type": "message", "content": "🧪 **Fractal Tests PLAN**: decomposing into atomic test cases..."})
    root = await _build_test_tree(engine, run, planner_id, task, depth=0, parent_lineage=parent_lineage)

    leaves = _collect_test_leaves(root)
    logger.info("fractal_tests: %d atomic test cases", len(leaves))
    await _sse(run, {"type": "message", "content": f"🧪 **{len(leaves)} test cases** to generate..."})

    async def generate_test(i: int, leaf: TestNode) -> None:
        worker_id = worker_ids[i % len(worker_ids)]
        original_lineage = run.lineage
        run.lineage = leaf.lineage
        try:
            test_prompt = _generate_test_prompt(leaf.item, leaf.lineage)
            leaf.result = await engine._execute_node(run, worker_id, test_prompt)
            # Log to traceability store
            try:
                from ...traceability.store import log_artifact
                log_artifact(run.session_id, "test", leaf.item[:120], leaf.lineage,
                             f"Generated test for: {leaf.item}")
            except Exception:
                pass
        finally:
            run.lineage = original_lineage

    await asyncio.gather(*[generate_test(i, leaf) for i, leaf in enumerate(leaves)], return_exceptions=True)

    test_code = "\n\n".join(leaf.result for leaf in leaves if leaf.result)
    await _sse(run, {"type": "message", "content": f"✅ **Tests generated** ({len(leaves)} cases)\n\n```python\n{test_code[:1500]}\n```"})
