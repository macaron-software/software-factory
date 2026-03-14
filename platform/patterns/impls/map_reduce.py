"""Map-Reduce pattern: fan-out to workers, then aggregate results.

Phase 1 (Map): Each worker processes the task independently in parallel.
Phase 2 (Reduce): A designated reducer agent synthesizes all worker outputs.
"""
# Ref: feat-patterns

from __future__ import annotations

import asyncio


async def run_map_reduce(engine, run, task: str):
    """Map-Reduce: parallel map → single reduce."""
    nodes = list(run.nodes.keys())
    if not nodes:
        return

    if len(nodes) < 2:
        await engine._execute_node(run, nodes[0], task)
        return

    # Last node is reducer, others are mappers
    mappers = nodes[:-1]
    reducer = nodes[-1]

    # Map phase: fan-out
    await asyncio.gather(
        *(engine._execute_node(run, nid, task) for nid in mappers)
    )

    # Collect mapper outputs
    outputs = []
    for nid in mappers:
        out = run.nodes[nid].output or ""
        if out:
            outputs.append(f"[{nid}]: {out}")

    # Reduce phase: synthesize
    reduce_task = (
        f"Synthesize the following worker outputs into a coherent result:\n\n"
        + "\n\n".join(outputs)
    )
    await engine._execute_node(run, reducer, reduce_task)
