"""Fractal Stories pattern — LLM-driven story decomposition for product planning.

Source: TinyAGI/fractals (MIT) — fractal vertical applied to product layer.
Decision: replace SF's static mission→phase→task hierarchy with a classify gate:
  "Is this deliverable in 1 sprint by 1 team, or does it need decomposition?"
This produces more accurate, context-aware story breakdowns than fixed templates.

Lineage propagated at each level: Vision → Epic → Feature → Story → Task
Each leaf = a story/task atomic enough for 1 agent in 1 session.
"""

from __future__ import annotations
import asyncio
import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

MAX_DEPTH = 3   # Vision(0) → Epic(1) → Feature(2) → Story(3)
MAX_CHILDREN = 6


LEVEL_NAMES = ["Vision", "Epic", "Feature", "Story", "Task"]


def _classify_prompt_stories(item: str, depth: int) -> str:
    level = LEVEL_NAMES[min(depth, len(LEVEL_NAMES)-1)]
    next_level = LEVEL_NAMES[min(depth+1, len(LEVEL_NAMES)-1)]
    return (
        f"[FRACTAL STORIES — CLASSIFY]\n"
        f"Current level: {level}\n"
        f"Item: {item}\n\n"
        f"Can this be delivered by a single team in a single sprint (1-2 weeks)? "
        f"Is it specific enough to estimate and assign?\n\n"
        f"Reply with exactly one word: ATOMIC (yes, one sprint) or COMPOSITE (needs decomposition into {next_level}s)."
    )


def _decompose_prompt_stories(item: str, depth: int, max_children: int) -> str:
    level = LEVEL_NAMES[min(depth, len(LEVEL_NAMES)-1)]
    next_level = LEVEL_NAMES[min(depth+1, len(LEVEL_NAMES)-1)]
    return (
        f"[FRACTAL STORIES — DECOMPOSE]\n"
        f"Current {level}: {item}\n\n"
        f"Break this into at most {max_children} concrete {next_level}s.\n"
        f"Each {next_level} must be:\n"
        f"  - Independent and deliverable\n"
        f"  - Written from the user's perspective (As a... I want... So that...)\n"
        f"  - Estimable (has clear acceptance criteria)\n\n"
        f"Format: one {next_level} per line, prefixed with a dash.\n"
        f"No explanations — just the list."
    )


def _parse_items(text: str) -> list[str]:
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
class StoryNode:
    item: str
    depth: int
    level: str = "pending"
    node_type: str = "pending"   # "atomic" | "composite"
    children: list["StoryNode"] = field(default_factory=list)
    result: str = ""
    lineage: list[str] = field(default_factory=list)


async def _build_story_tree(engine, run, planner_id: str, item: str, depth: int, parent_lineage: list[str]) -> StoryNode:
    level_name = LEVEL_NAMES[min(depth, len(LEVEL_NAMES)-1)]
    lineage = parent_lineage + [f"{level_name}: {item[:80]}"]
    node = StoryNode(item=item, depth=depth, level=level_name, lineage=lineage)

    if depth >= MAX_DEPTH:
        node.node_type = "atomic"
        return node

    classify_out = await engine._execute_node(run, planner_id, _classify_prompt_stories(item, depth))
    is_atomic = "ATOMIC" in classify_out.upper() or "COMPOSITE" not in classify_out.upper()

    if is_atomic:
        node.node_type = "atomic"
        return node

    node.node_type = "composite"
    decompose_out = await engine._execute_node(run, planner_id, _decompose_prompt_stories(item, depth, MAX_CHILDREN))
    children_items = _parse_items(decompose_out)
    if not children_items:
        node.node_type = "atomic"
        return node

    child_tasks = [_build_story_tree(engine, run, planner_id, child_item, depth+1, lineage) for child_item in children_items]
    node.children = await asyncio.gather(*child_tasks)
    return node


def _collect_story_leaves(node: StoryNode) -> list[StoryNode]:
    if node.node_type == "atomic":
        return [node]
    leaves = []
    for child in node.children:
        leaves.extend(_collect_story_leaves(child))
    return leaves


async def run_fractal_stories(engine, run, task: str) -> None:
    """Fractal Stories pattern — decomposes a product vision/epic into atomic stories.

    Phase 1 PLAN: classify gate (sprint-deliverable?) → decompose recursively
    Phase 2 EXECUTE: leaf stories assigned to worker agents in parallel
    Lineage propagated: each leaf knows its full product ancestry

    Use this pattern for: product planning, backlog refinement, epic decomposition.
    """
    from ..engine import _sse

    nodes = engine._ordered_nodes(run.pattern)
    if not nodes:
        return

    planner_id = nodes[0]
    worker_ids = nodes[1:] if len(nodes) > 1 else [planner_id]

    parent_lineage = list(run.lineage) if run.lineage else []

    await _sse(run, {"type": "message", "content": "📋 **Fractal Stories PLAN**: decomposing into atomic stories..."})
    root = await _build_story_tree(engine, run, planner_id, task, depth=0, parent_lineage=parent_lineage)

    leaves = _collect_story_leaves(root)
    logger.info("fractal_stories: %d atomic stories", len(leaves))
    await _sse(run, {"type": "message", "content": f"📚 **{len(leaves)} atomic stories** identified — executing..."})

    async def execute_story(i: int, leaf: StoryNode) -> None:
        worker_id = worker_ids[i % len(worker_ids)]
        # Temporarily enrich run lineage with leaf's full ancestry
        original_lineage = run.lineage
        run.lineage = leaf.lineage
        try:
            leaf.result = await engine._execute_node(run, worker_id, leaf.item)
        finally:
            run.lineage = original_lineage

    await asyncio.gather(*[execute_story(i, leaf) for i, leaf in enumerate(leaves)], return_exceptions=True)

    summary = "\n".join(f"- [{leaf.level}] {leaf.item[:60]}: {leaf.result[:80]}..." for leaf in leaves if leaf.result)
    await _sse(run, {"type": "message", "content": f"✅ **Stories complete**\n\n{summary}"})
