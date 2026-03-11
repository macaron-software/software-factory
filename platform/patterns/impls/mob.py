"""Mob pattern: mob programming — rotate driver/navigators.

One 'driver' agent writes code while others 'navigate' (review/suggest).
After each round, driver role rotates. All agents see evolving code.
Builds shared understanding and catches issues early.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def run_mob(engine, run, task: str):
    """Mob: rotate driver/navigators, all see same code."""
    nodes = list(run.nodes.keys())
    if not nodes:
        return

    if len(nodes) == 1:
        await engine._execute_node(run, nodes[0], task)
        return

    max_rounds = run.pattern.config.get("max_rounds", len(nodes))
    code_state = ""

    for round_num in range(max_rounds):
        driver_idx = round_num % len(nodes)
        driver = nodes[driver_idx]
        navigators = [n for i, n in enumerate(nodes) if i != driver_idx]

        # Navigators suggest
        nav_suggestions = []
        for nid in navigators:
            nav_task = (
                f"[MOB — NAVIGATOR round {round_num + 1}]\n"
                f"Task: {task}\n"
                f"Current code state:\n{code_state or '(empty — first round)'}\n\n"
                f"Suggest what the driver should implement next. Be specific."
            )
            await engine._execute_node(run, nid, nav_task)
            out = run.nodes[nid].output or ""
            if out:
                nav_suggestions.append(f"[{nid}]: {out}")

        # Driver implements
        driver_task = (
            f"[MOB — DRIVER round {round_num + 1}]\n"
            f"Task: {task}\n"
            f"Current code state:\n{code_state or '(empty — first round)'}\n\n"
            f"Navigator suggestions:\n" + "\n\n".join(nav_suggestions)
            + "\n\nImplement the next piece. Use code_write/code_edit tools."
        )
        await engine._execute_node(run, driver, driver_task)
        output = run.nodes[driver].output or ""
        if output:
            code_state = output

    logger.info("MOB: completed %d rounds with %d agents", max_rounds, len(nodes))
