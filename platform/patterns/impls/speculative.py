"""Speculative pattern: parallel race, first valid result wins.

Multiple agents attempt the task in parallel with different approaches.
The first agent producing valid output (non-empty, with tool calls,
not vetoed) is the winner. Like speculative execution in CPUs.
"""
# Ref: feat-patterns

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


async def run_speculative(engine, run, task: str):
    """Speculative: parallel race, first success wins."""
    from ..engine import NodeStatus

    nodes = list(run.nodes.keys())
    if not nodes:
        return

    if len(nodes) == 1:
        await engine._execute_node(run, nodes[0], task)
        return

    # All agents race in parallel with their own approach framing
    approach_tasks = []
    for i, nid in enumerate(nodes):
        t = (
            f"[Approach {i + 1}/{len(nodes)}] {task}\n\n"
            f"Try your own approach to solve this. Be concrete and use tools."
        )
        approach_tasks.append((nid, t))

    await asyncio.gather(
        *(engine._execute_node(run, nid, t) for nid, t in approach_tasks)
    )

    # Pick first valid result
    winner = None
    for nid in nodes:
        node = run.nodes[nid]
        has_output = bool(node.output and len(node.output.strip()) > 50)
        has_tools = bool(node.result and node.result.tool_calls)
        not_vetoed = node.status != NodeStatus.VETOED
        if has_output and has_tools and not_vetoed:
            winner = nid
            break

    if winner:
        logger.info("SPECULATIVE: winner = %s (first valid result)", winner)
    else:
        winner = max(nodes, key=lambda n: len(run.nodes[n].output or ""))
        logger.warning("SPECULATIVE: no clean winner, using %s (longest output)", winner)
