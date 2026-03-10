"""Sequential pattern: nodes executed in order with context rot mitigation."""
from __future__ import annotations


async def run_sequential(engine, run, task: str):
    """Execute nodes in sequence, with context rot mitigation.

    Each agent sees compressed older outputs + full last output,
    keeping the context window fresh.
    """
    order = engine._ordered_nodes(run.pattern)
    accumulated = []
    first_agent = engine._node_agent_id(run, order[0]) if order else "all"
    for i, nid in enumerate(order):
        if i + 1 < len(order):
            to = engine._node_agent_id(run, order[i + 1])
        else:
            to = first_agent
        # Compressed context: older outputs summarized, last one full
        context = engine._build_compressed_context(accumulated) if accumulated else ""
        output = await engine._execute_node(
            run, nid, task, context_from=context, to_agent_id=to,
        )
        ns = run.nodes.get(nid)
        label = ns.agent.name if ns and ns.agent else nid
        accumulated.append(f"[{label}]:\n{output}")
