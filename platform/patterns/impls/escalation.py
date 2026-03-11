"""Escalation pattern: tiered agents, try cheapest/simplest first.

Agents are ordered by expertise level. The first agent attempts the task;
if the result is insufficient (no tools used, empty output, or vetoed),
escalate to the next tier. Stops at first successful tier.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def run_escalation(engine, run, task: str):
    """Escalation: tiered retry, stop at first success."""
    from ..engine import NodeStatus

    nodes = list(run.nodes.keys())
    if not nodes:
        return

    for i, nid in enumerate(nodes):
        tier = i + 1
        tier_task = (
            f"[Tier {tier}/{len(nodes)}] {task}\n\n"
            f"You are tier-{tier} agent. Solve this task completely. "
            f"If you cannot, the task will be escalated to a higher-tier agent."
        )
        await engine._execute_node(run, nid, tier_task)

        node = run.nodes[nid]
        has_output = bool(node.output and len(node.output.strip()) > 50)
        has_tools = bool(node.result and node.result.tool_calls)
        not_vetoed = node.status != NodeStatus.VETOED

        if has_output and has_tools and not_vetoed:
            logger.info("ESCALATION: tier %d/%d (%s) succeeded", tier, len(nodes), nid)
            break
        else:
            logger.warning("ESCALATION: tier %d/%d (%s) insufficient — escalating", tier, len(nodes), nid)
    else:
        logger.warning("ESCALATION: all %d tiers exhausted", len(nodes))
