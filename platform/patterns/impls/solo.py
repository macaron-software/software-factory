"""Solo pattern: single agent execution."""
from __future__ import annotations


async def run_solo(engine, run, task: str):
    """Single agent execution."""
    nodes = list(run.nodes.keys())
    if nodes:
        await engine._execute_node(run, nodes[0], task)
