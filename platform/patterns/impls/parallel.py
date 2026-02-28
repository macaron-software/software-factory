"""Parallel pattern: dispatcher fans out to workers with role-specific subtasks."""

from __future__ import annotations

import asyncio
import json
import re


def _extract_worker_subtasks(
    dispatcher_output: str, worker_roles: list[str]
) -> dict[int, str]:
    """Extract per-worker subtasks from dispatcher output.

    The dispatcher is asked to produce a JSON block with role-specific focus areas.
    Falls back to sending the full dispatcher output to all workers if parsing fails.
    """
    # Try to parse a JSON block like: {"workers": ["task A", "task B", ...]}
    match = re.search(
        r'\{[^{}]*"workers"\s*:\s*\[([^\]]+)\][^{}]*\}', dispatcher_output, re.DOTALL
    )
    if match:
        try:
            inner = json.loads('{"workers": [' + match.group(1) + "]}")
            tasks = inner.get("workers", [])
            if len(tasks) == len(worker_roles):
                return {i: t for i, t in enumerate(tasks)}
        except Exception:
            pass
    return {}


async def run_parallel(engine, run, task: str):
    """Find dispatcher, fan out to workers with role-specific subtasks, then aggregate."""
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

    # Build worker role list for decomposition hint
    worker_roles = []
    for nid in parallel_targets:
        ns = run.nodes.get(nid)
        if ns and ns.agent:
            worker_roles.append(f"{ns.agent.name} ({ns.agent.role})")
        else:
            worker_roles.append(f"worker-{nid}")

    # Inject decomposition directive into dispatcher task
    decompose_hint = ""
    if len(parallel_targets) > 1 and worker_roles:
        roles_list = "\n".join(f"  - {r}" for r in worker_roles)
        decompose_hint = (
            f"\n\n[TEAM DISPATCH]: You are the dispatcher. Your team:\n{roles_list}\n"
            f"After your analysis, produce a JSON block at the end with role-specific focus for each worker:\n"
            f'```json\n{{"workers": ["<task for {worker_roles[0]}>", '
            + ", ".join(f'"<task for {r}>"' for r in worker_roles[1:])
            + "]}}\n```\nBe concise and specific per role."
        )

    # Dispatcher sends to workers
    first_worker = (
        engine._node_agent_id(run, parallel_targets[0]) if parallel_targets else "all"
    )
    dispatcher_output = await engine._execute_node(
        run,
        dispatcher_id,
        task + decompose_hint,
        to_agent_id=first_worker,
    )

    # Extract per-worker subtasks from dispatcher output
    subtasks = (
        _extract_worker_subtasks(dispatcher_output, worker_roles)
        if parallel_targets
        else {}
    )

    # Fan out — each worker gets its role-specific subtask (or dispatcher output as fallback)
    agg_agent = engine._node_agent_id(run, agg_node) if agg_node else dispatcher_agent
    if parallel_targets:
        worker_tasks = []
        for i, nid in enumerate(parallel_targets):
            # Use decomposed subtask if available, else full task
            worker_task = subtasks.get(i, task)
            worker_tasks.append(
                engine._execute_node(
                    run,
                    nid,
                    worker_task,
                    context_from=dispatcher_output,
                    to_agent_id=agg_agent,
                )
            )
        results = await asyncio.gather(*worker_tasks, return_exceptions=True)

        # Aggregate — aggregator receives all worker outputs labeled by agent
        if agg_node:
            combined_parts = []
            for i, (nid, r) in enumerate(zip(parallel_targets, results)):
                ns = run.nodes.get(nid)
                label = ns.agent.name if ns and ns.agent else nid
                subtask_label = (
                    f" [focus: {subtasks[i][:60]}...]" if i in subtasks else ""
                )
                combined_parts.append(
                    f"[{label}{subtask_label}]:\n{r if isinstance(r, str) else str(r)}"
                )
            combined = "\n\n---\n".join(combined_parts)
            await engine._execute_node(
                run,
                agg_node,
                task,
                context_from=combined,
                to_agent_id=dispatcher_agent,
            )
