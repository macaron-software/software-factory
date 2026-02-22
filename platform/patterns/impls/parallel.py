"""Parallel pattern: dispatcher fans out to workers, then aggregates."""
from __future__ import annotations

import asyncio


async def run_parallel(engine, run, task: str):
    """Find dispatcher, fan out to workers, then aggregate."""
    order = engine._ordered_nodes(run.pattern)
    if not order:
        return

    dispatcher_id = order[0]
    dispatcher_agent = engine._node_agent_id(run, dispatcher_id)

    # Find parallel targets and aggregator
    parallel_targets = []
    agg_node = None
    for edge in run.pattern.edges:
        if edge["from"] == dispatcher_id and edge.get("type") == "parallel":
            parallel_targets.append(edge["to"])
    for node in run.pattern.agents:
        nid = node["id"]
        if nid != dispatcher_id and nid not in parallel_targets:
            agg_node = nid

    # Dispatcher sends to workers (first worker as target for display)
    first_worker = engine._node_agent_id(run, parallel_targets[0]) if parallel_targets else "all"
    dispatcher_output = await engine._execute_node(
        run, dispatcher_id, task, to_agent_id=first_worker,
    )

    # Fan out — each worker reports to aggregator (or dispatcher)
    agg_agent = engine._node_agent_id(run, agg_node) if agg_node else dispatcher_agent
    if parallel_targets:
        tasks = [
            engine._execute_node(run, nid, task, context_from=dispatcher_output, to_agent_id=agg_agent)
            for nid in parallel_targets
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate — aggregator reports to dispatcher
        if agg_node:
            combined = "\n\n".join(
                f"[Worker {parallel_targets[i]}]: {r if isinstance(r, str) else str(r)}"
                for i, r in enumerate(results)
            )
            await engine._execute_node(
                run, agg_node, task, context_from=combined, to_agent_id=dispatcher_agent,
            )
