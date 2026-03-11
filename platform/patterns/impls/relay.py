"""Relay pattern: baton passing with incremental enrichment.

Each agent receives the accumulated work product and adds their contribution.
Unlike sequential (independent tasks), relay explicitly builds on previous
output. Like a relay race — each runner carries the baton further.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def run_relay(engine, run, task: str):
    """Relay: each agent enriches the previous agent's output."""
    nodes = list(run.nodes.keys())
    if not nodes:
        return

    baton = task
    for i, nid in enumerate(nodes):
        relay_task = (
            f"[Relay leg {i + 1}/{len(nodes)}]\n"
            f"Original task: {task}\n\n"
            f"Previous work product to build upon:\n{baton}\n\n"
            f"Add your contribution. Build on what exists, don't restart from scratch."
        )
        await engine._execute_node(run, nid, relay_task)
        output = run.nodes[nid].output or ""
        if output:
            baton = output

    logger.info("RELAY: completed %d legs", len(nodes))
