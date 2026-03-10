"""Backpropagation Merge pattern — bottom-up merge after parallel leaf execution.

Source: TinyAGI/fractals roadmap "Backpropagation (merge agent)" section (MIT)
  https://github.com/TinyAGI/fractals#roadmap
Decision: implement the merge-agent concept as a standalone SF pattern.
  In fractals: merge agent runs per composite node after its children complete,
  propagating bottom-up to root. We generalize this as a post-execution aggregator
  that can be chained after fractal-worktree OR used standalone after any parallel pattern.

Use case in SF: coding missions where N agents each produce a module/file,
  and a senior agent must integrate them into a coherent codebase.
"""

from __future__ import annotations

import asyncio
import logging

from .fractal_worktree import (
    FractalNode,
    MAX_DEPTH,
    _build_tree,
    _collect_leaves,
    _execute_leaf,
)

logger = logging.getLogger(__name__)


def _merge_prompt(task: str, children_outputs: list[tuple[str, str]]) -> str:
    """Prompt for the merge agent at a composite node.

    Ref: TinyAGI/fractals roadmap — 'combines worktree branches into one coherent result'.
    SF adaptation: merge agent synthesizes agent outputs (text) rather than git branches.
    """
    children_section = "\n\n".join(
        f"### Subtask {i+1}: {subtask}\n{output[:800]}"
        for i, (subtask, output) in enumerate(children_outputs)
        if output
    )
    return (
        f"[BACKPROPAGATION MERGE]\n"
        f"Parent task: {task}\n\n"
        f"The following subtasks have been completed by your team:\n\n"
        f"{children_section}\n\n"
        f"Synthesize these results into a single coherent response for the parent task.\n"
        f"Resolve any conflicts or overlaps. Ensure completeness.\n"
        f"Be concise — output the integrated result, not a summary of summaries."
    )


async def _backprop_node(engine, run, merger_id: str, node: FractalNode) -> str:
    """Recursively execute and merge a FractalNode tree bottom-up.

    For each composite node:
      1. Execute (or retrieve) all children results
      2. Run merge agent with all children outputs
      3. Propagate merged result up

    For leaf nodes: execute directly.
    """
    if node.node_type == "atomic":
        if not node.result:
            # Execute if not already done (standalone backprop-merge usage)
            node.result = await engine._execute_node(run, merger_id, node.task)
        return node.result

    # Recurse: execute all children in parallel
    child_coros = [_backprop_node(engine, run, merger_id, child) for child in node.children]
    child_results = await asyncio.gather(*child_coros, return_exceptions=True)

    # Pair children tasks with their results
    children_outputs = []
    for child, result in zip(node.children, child_results):
        r = result if isinstance(result, str) else str(result)
        children_outputs.append((child.task, r))

    # Merge agent synthesizes all children for this composite node
    merged = await engine._execute_node(
        run, merger_id, _merge_prompt(node.task, children_outputs)
    )
    node.result = merged
    return merged


async def run_backprop_merge(engine, run, task: str) -> None:
    """Backpropagation Merge pattern execution.

    Builds a fractal decomposition tree (same as fractal-worktree Phase 1),
    then executes leaf tasks and merges bottom-up:

      leaf1 ─┐
      leaf2 ─┤→ merge(composite1) ─┐
      leaf3 ─┘                     │→ merge(root)
      leaf4 ─┐                     │
      leaf5 ─┤→ merge(composite2) ─┘

    The merge agent at each composite receives all its children's results
    and synthesizes a coherent output. Root merge = final answer.

    Agents in the pattern:
      - First node: planner agent (builds the tree via classify/decompose)
      - Last node: merger agent (runs merge at each composite level)
      - If only one node: same agent does both roles.

    Source: TinyAGI/fractals roadmap — "Backpropagation (merge agent)" (MIT).
    """
    from ..engine import _sse

    nodes = engine._ordered_nodes(run.pattern)
    if not nodes:
        return

    planner_id = nodes[0]
    # Merger is the last agent (or planner if only one node)
    merger_id = nodes[-1] if len(nodes) > 1 else planner_id

    repo_path = run.project_path or ""
    session_id = run.session_id

    # ── Phase 1: Build decomposition tree ──
    await _sse(run, {"type": "message", "content": "🌿 **Backprop PLAN phase**: building decomposition tree..."})
    root = await _build_tree(engine, run, planner_id, task, depth=0)

    leaves = _collect_leaves(root)
    logger.info("backprop_merge: %d leaves to execute + merge up", len(leaves))
    await _sse(run, {
        "type": "message",
        "content": f"🌳 **Tree ready**: {len(leaves)} leaves — executing then merging bottom-up",
    })

    # ── Phase 2: Execute leaves (with worktrees if available) ──
    worker_ids = nodes[1:-1] if len(nodes) > 2 else [planner_id]
    leaf_list = _collect_leaves(root)
    leaf_coros = [
        _execute_leaf(engine, run, worker_ids[i % len(worker_ids)], leaf, repo_path, session_id)
        for i, leaf in enumerate(leaf_list)
    ]
    await _sse(run, {"type": "message", "content": "⚡ **Execute phase**: running leaves in parallel..."})
    await asyncio.gather(*leaf_coros, return_exceptions=True)

    # ── Phase 3: Backpropagation merge ──
    await _sse(run, {"type": "message", "content": "🔀 **Merge phase**: backpropagating results bottom-up..."})
    final_result = await _backprop_node(engine, run, merger_id, root)

    await _sse(run, {
        "type": "message",
        "content": f"✅ **Backprop complete** — integrated result:\n\n{final_result[:600]}",
    })
