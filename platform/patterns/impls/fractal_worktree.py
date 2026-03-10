"""Fractal Worktree pattern — recursive task decomposition + git worktrees per leaf.

Source: TinyAGI/fractals (MIT) — https://github.com/TinyAGI/fractals
Decision: port the two key innovations to SF's Python/FastAPI stack:
  1. LLM-driven classify gate (atomic vs composite) before decomposing
  2. git worktrees per leaf agent for conflict-free parallel code execution
We do NOT spawn Claude/Codex CLI — SF's own AgentExecutor handles execution.
The net result is the same: each code-writing agent works in isolation.

ADR: fractal-worktree pattern enables deterministic, reviewable decomposition
     before any code is written — addresses the "agent goes rogue" problem in
     unstructured parallel execution.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Hard limit to prevent runaway recursion (TinyAGI default: 4)
MAX_DEPTH = 3
# Max subtasks per decompose call (keeps plans tractable)
MAX_CHILDREN = 5


@dataclass
class FractalNode:
    """A node in the decomposition tree."""

    task: str
    depth: int
    node_type: str = "pending"   # "atomic" | "composite"
    children: list[FractalNode] = field(default_factory=list)
    result: str = ""
    worktree_path: str = ""
    branch: str = ""


# ── Git worktree helpers ────────────────────────────────────────────────────

def _is_git_repo(path: str) -> bool:
    """Check if path is inside a git repo."""
    try:
        r = subprocess.run(
            ["git", "-C", path, "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, timeout=5
        )
        return r.returncode == 0
    except Exception:
        return False


def _create_worktree(repo_path: str, branch: str, worktree_path: str) -> bool:
    """Create a git worktree for isolated agent execution."""
    try:
        r = subprocess.run(
            ["git", "-C", repo_path, "worktree", "add", worktree_path, "-b", branch],
            capture_output=True, text=True, timeout=15
        )
        return r.returncode == 0
    except Exception:
        return False


def _remove_worktree(repo_path: str, worktree_path: str) -> None:
    """Clean up worktree after execution."""
    try:
        subprocess.run(
            ["git", "-C", repo_path, "worktree", "remove", "--force", worktree_path],
            capture_output=True, timeout=10
        )
    except Exception:
        pass


# ── LLM classify / decompose ────────────────────────────────────────────────

def _classify_prompt(task: str) -> str:
    """Prompt to classify a task as atomic or composite.

    Inspired by TinyAGI/fractals llm.ts::classify() structured output.
    SF adaptation: text response instead of JSON schema (minimax compatibility).
    """
    return (
        f"[FRACTAL CLASSIFY]\n"
        f"Task: {task}\n\n"
        f"Is this task ATOMIC (self-contained, can be done by one agent in one step) "
        f"or COMPOSITE (requires multiple distinct sub-tasks)?\n\n"
        f"Reply with exactly one word: ATOMIC or COMPOSITE.\n"
        f"If the task is already very specific and actionable, answer ATOMIC."
    )


def _decompose_prompt(task: str, max_children: int) -> str:
    """Prompt to decompose a composite task into subtasks.

    Inspired by TinyAGI/fractals llm.ts::decompose() structured output.
    """
    return (
        f"[FRACTAL DECOMPOSE]\n"
        f"Task: {task}\n\n"
        f"Break this into at most {max_children} concrete, non-overlapping subtasks.\n"
        f"Each subtask must be self-contained and actionable by a single agent.\n"
        f"Format: one subtask per line, prefixed with a dash.\n"
        f"Do NOT include explanations, just the subtask list."
    )


def _parse_subtasks(text: str) -> list[str]:
    """Extract subtask lines from decompose response."""
    subtasks = []
    for line in text.split("\n"):
        line = line.strip()
        # Accept: "- task", "* task", "• task", "1. task", "1) task"
        m = re.match(r'^[-*•]\s+(.+)', line) or re.match(r'^\d+[.)]\s+(.+)', line)
        if m:
            subtasks.append(m.group(1).strip())
        elif line and line[0] not in ('#', '[', '-', '*') and len(line) > 10:
            # Fallback: bare non-empty non-bullet line
            subtasks.append(line)
    return subtasks[:MAX_CHILDREN]


# ── Core recursive decomposition ────────────────────────────────────────────

async def _build_tree(engine, run, planner_id: str, task: str, depth: int) -> FractalNode:
    """Recursively classify and decompose a task into a FractalNode tree.

    Phase 1 of the fractal-worktree pattern (PLAN phase in TinyAGI/fractals).
    """
    node = FractalNode(task=task, depth=depth)

    if depth >= MAX_DEPTH:
        # Force atomic at max depth — prevents infinite recursion
        node.node_type = "atomic"
        return node

    # Classify: is this task atomic or composite?
    classify_output = await engine._execute_node(
        run, planner_id, _classify_prompt(task)
    )
    is_atomic = "ATOMIC" in classify_output.upper() or "COMPOSITE" not in classify_output.upper()

    if is_atomic:
        node.node_type = "atomic"
        return node

    # Decompose into subtasks
    node.node_type = "composite"
    decompose_output = await engine._execute_node(
        run, planner_id, _decompose_prompt(task, MAX_CHILDREN)
    )
    subtasks = _parse_subtasks(decompose_output)

    if not subtasks:
        # Parse failed — treat as atomic
        node.node_type = "atomic"
        return node

    # Recurse on each child
    child_tasks = [
        _build_tree(engine, run, planner_id, subtask, depth + 1)
        for subtask in subtasks
    ]
    node.children = await asyncio.gather(*child_tasks)
    return node


def _collect_leaves(node: FractalNode) -> list[FractalNode]:
    """Collect all atomic leaf nodes."""
    if node.node_type == "atomic":
        return [node]
    leaves = []
    for child in node.children:
        leaves.extend(_collect_leaves(child))
    return leaves


# ── Phase 2: Execute leaves ──────────────────────────────────────────────────

async def _execute_leaf(engine, run, worker_id: str, leaf: FractalNode,
                        repo_path: str, session_id: str) -> None:
    """Execute a single leaf task, optionally in an isolated git worktree."""
    use_worktree = bool(repo_path) and _is_git_repo(repo_path)

    if use_worktree:
        # Create isolated branch + worktree per leaf
        # Ref: TinyAGI/fractals executor.ts — git worktree per task
        slug = re.sub(r'[^a-z0-9]+', '-', leaf.task.lower())[:40].strip('-')
        branch = f"fractal/{session_id[:8]}/{slug}"
        wt_path = os.path.join(repo_path, ".git", "fractal-worktrees", slug)
        os.makedirs(os.path.dirname(wt_path), exist_ok=True)

        if _create_worktree(repo_path, branch, wt_path):
            leaf.worktree_path = wt_path
            leaf.branch = branch
            # Override project_path for this leaf's execution context
            original_path = run.project_path
            run.project_path = wt_path
            try:
                leaf.result = await engine._execute_node(run, worker_id, leaf.task)
            finally:
                run.project_path = original_path
                _remove_worktree(repo_path, wt_path)
            return

    # No worktree — plain execution (graceful degradation)
    leaf.result = await engine._execute_node(run, worker_id, leaf.task)


# ── Main entry point ─────────────────────────────────────────────────────────

async def run_fractal_worktree(engine, run, task: str) -> None:
    """Fractal Worktree pattern execution.

    Phase 1 — PLAN: recursively classify + decompose the task into an atomic leaf tree.
    Phase 2 — EXECUTE: run leaf tasks in parallel, each in an isolated git worktree.
    Phase 3 — MERGE (optional, if backprop-merge pattern is chained): handled separately.

    Agents in the pattern:
      - First node: planner/classifier agent (brain-class)
      - Remaining nodes (round-robin): worker agents for leaf execution

    Source: TinyAGI/fractals (MIT) — adapted for SF AgentExecutor stack.
    """
    from ..engine import _sse

    nodes = engine._ordered_nodes(run.pattern)
    if not nodes:
        return

    planner_id = nodes[0]
    # Workers are the remaining agents; fallback to planner if only one node
    worker_ids = nodes[1:] if len(nodes) > 1 else [planner_id]

    repo_path = run.project_path or ""
    session_id = run.session_id

    # ── Phase 1: Build decomposition tree ──
    await _sse(run, {"type": "message", "content": "🌿 **Fractal PLAN phase**: classifying and decomposing task tree..."})
    root = await _build_tree(engine, run, planner_id, task, depth=0)

    leaves = _collect_leaves(root)
    logger.info("fractal_worktree: %d leaves at depth ≤%d", len(leaves), MAX_DEPTH)
    await _sse(run, {
        "type": "message",
        "content": f"🌳 **Tree built**: {len(leaves)} atomic leaf task(s) to execute"
                   + (" with git worktrees" if repo_path and _is_git_repo(repo_path) else ""),
    })

    # ── Phase 2: Execute leaves in parallel (round-robin worker assignment) ──
    await _sse(run, {"type": "message", "content": "⚡ **Fractal EXECUTE phase**: running leaves in parallel..."})

    leaf_coros = []
    for i, leaf in enumerate(leaves):
        worker_id = worker_ids[i % len(worker_ids)]
        leaf_coros.append(_execute_leaf(engine, run, worker_id, leaf, repo_path, session_id))

    await asyncio.gather(*leaf_coros, return_exceptions=True)

    # ── Summary ──
    results_summary = "\n".join(
        f"- **{leaf.task[:60]}**: {leaf.result[:120]}..."
        for leaf in leaves if leaf.result
    )
    await _sse(run, {
        "type": "message",
        "content": f"✅ **Fractal complete** — {len(leaves)} tasks executed\n\n{results_summary}",
    })
