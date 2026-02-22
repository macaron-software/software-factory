"""Wave pattern: parallel within waves, sequential across waves."""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


async def run_wave(engine, run, task: str):
    """Wave execution: parallel within waves, sequential across waves.

    Analyzes the dependency graph and groups independent nodes into waves.
    Agents within a wave run in parallel (asyncio.gather).
    Each wave waits for the previous wave to complete.
    Context from previous waves is compressed to prevent context rot.
    """
    from ..engine import _sse

    waves = engine._compute_waves(run.pattern)
    if not waves:
        return

    accumulated = []  # compressed outputs from all previous waves

    for wave_idx, wave_nodes in enumerate(waves):
        wave_label = f"Wave {wave_idx + 1}/{len(waves)}"
        logger.info("Wave execution: %s — %d agents in parallel", wave_label, len(wave_nodes))

        # Announce wave
        await _sse(run, {
            "type": "message",
            "content": f"{wave_label} — {len(wave_nodes)} agent(s) en parallele",
            "from_agent": "system",
        })

        # Build compressed context from previous waves
        context = engine._build_compressed_context(accumulated) if accumulated else ""

        if len(wave_nodes) == 1:
            # Single node — run directly
            nid = wave_nodes[0]
            to = "all"
            output = await engine._execute_node(run, nid, task, context_from=context, to_agent_id=to)
            ns = run.nodes.get(nid)
            label = ns.agent.name if ns and ns.agent else nid
            accumulated.append(f"[{label}]:\n{output}")
        else:
            # Multiple nodes — run in parallel
            coros = [
                engine._execute_node(run, nid, task, context_from=context, to_agent_id="all")
                for nid in wave_nodes
            ]
            results = await asyncio.gather(*coros, return_exceptions=True)

            for nid, result in zip(wave_nodes, results):
                ns = run.nodes.get(nid)
                label = ns.agent.name if ns and ns.agent else nid
                output = result if isinstance(result, str) else str(result)
                accumulated.append(f"[{label}]:\n{output}")
