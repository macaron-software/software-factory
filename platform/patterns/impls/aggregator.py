"""Aggregator pattern: workers in parallel, one aggregator consolidates."""
from __future__ import annotations

import asyncio


async def run_aggregator(engine, run, task: str):
    """Aggregator: multiple agents work in parallel, one aggregator consolidates.

    Unlike parallel (dispatcher → workers → aggregator), aggregator has NO dispatcher.
    Workers start independently, then the aggregator synthesizes all results.
    """
    nodes = engine._ordered_nodes(run.pattern)
    if len(nodes) < 2:
        from .sequential import run_sequential
        return await run_sequential(engine, run, task)

    # Find aggregator (node that receives "aggregate" edges)
    agg_id = None
    worker_ids = []
    agg_targets = set()
    for edge in run.pattern.edges:
        if edge.get("type") == "aggregate":
            agg_targets.add(edge["to"])
    if agg_targets:
        agg_id = list(agg_targets)[0]
        worker_ids = [n for n in nodes if n != agg_id]
    else:
        agg_id = nodes[-1]
        worker_ids = nodes[:-1]

    agg_agent = engine._node_agent_id(run, agg_id)

    # Workers execute in parallel
    run.flow_step = "Analyse parallèle"
    worker_tasks = [
        engine._execute_node(run, wid, task, to_agent_id=agg_agent)
        for wid in worker_ids
    ]
    results = await asyncio.gather(*worker_tasks, return_exceptions=True)

    # Build consolidated input
    combined_parts = []
    for i, r in enumerate(results):
        ns = run.nodes.get(worker_ids[i])
        name = ns.agent.name if ns and ns.agent else worker_ids[i]
        combined_parts.append(f"[{name}]:\n{r if isinstance(r, str) else str(r)}")
    combined = "\n\n---\n\n".join(combined_parts)

    # Aggregator synthesizes
    run.flow_step = "Consolidation"
    await engine._execute_node(
        run, agg_id,
        f"Consolide les analyses de tous les experts en une synthèse actionable.\n\n"
        f"1. Résume les contributions clés de chaque expert\n"
        f"2. Identifie les points de convergence et de divergence\n"
        f"3. Propose un plan d'action consolidé avec priorités\n\n"
        f"Contributions :\n{combined}",
        context_from=combined, to_agent_id="all",
    )
