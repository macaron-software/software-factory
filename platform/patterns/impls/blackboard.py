"""Blackboard pattern: shared knowledge space where agents read/write iteratively.

Agents take turns reading the blackboard state and contributing their expertise.
Each iteration, every agent reads the current state and adds/refines content.
Converges when max_iterations is reached or no agent modifies the blackboard.
"""

from __future__ import annotations


async def run_blackboard(engine, run, task: str):
    """Blackboard: iterative shared-knowledge convergence."""
    nodes = list(run.nodes.keys())
    if not nodes:
        return

    max_iter = run.pattern.config.get("max_iterations", 3)
    context = task

    for iteration in range(max_iter):
        changed = False
        for nid in nodes:
            prev = context
            await engine._execute_node(run, nid, context)
            node_output = run.nodes[nid].output or ""
            if node_output and node_output != prev:
                context = f"{context}\n\n---\n{node_output}"
                changed = True
        if not changed:
            break
