"""Red-Blue pattern: structured adversarial attack/defense.

Red team finds bugs, security holes, edge cases. Blue team fixes.
Iterates until red team finds no more issues or max_rounds reached.
More structured than network debate — explicit attack/defend roles.
"""
# Ref: feat-patterns

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def run_red_blue(engine, run, task: str):
    """Red-Blue: iterative attack/defend adversarial."""
    nodes = list(run.nodes.keys())
    if len(nodes) < 2:
        if nodes:
            await engine._execute_node(run, nodes[0], task)
        return

    # First half = blue team (builders/defenders), rest = red team (attackers)
    mid = max(1, len(nodes) // 2)
    blue_team = nodes[:mid]
    red_team = nodes[mid:]
    max_rounds = run.pattern.config.get("max_rounds", 3)

    # Initial build by blue team
    blue_context = task
    for nid in blue_team:
        await engine._execute_node(run, nid, f"[BLUE TEAM — BUILD/DEFEND]\n{blue_context}")
        blue_context += f"\n\n{run.nodes[nid].output or ''}"

    for round_num in range(1, max_rounds + 1):
        # Red team attacks
        red_findings = []
        for nid in red_team:
            attack_task = (
                f"[RED TEAM — ATTACK round {round_num}/{max_rounds}]\n"
                f"Find bugs, security holes, edge cases, logic errors in:\n\n"
                f"{blue_context}\n\n"
                f"Be specific. List concrete issues with file/line references."
            )
            await engine._execute_node(run, nid, attack_task)
            out = run.nodes[nid].output or ""
            if out:
                red_findings.append(out)

        if not any(f.strip() for f in red_findings):
            logger.info("RED-BLUE: red team found no issues at round %d", round_num)
            break

        # Blue team defends/fixes
        defense_task = (
            f"[BLUE TEAM — DEFEND/FIX round {round_num}/{max_rounds}]\n"
            f"Red team found these issues:\n\n"
            + "\n\n---\n".join(red_findings)
            + "\n\nFix all issues. Use code_write/code_edit tools."
        )
        blue_context = defense_task
        for nid in blue_team:
            await engine._execute_node(run, nid, blue_context)
            blue_context += f"\n\n{run.nodes[nid].output or ''}"

    logger.info("RED-BLUE: completed %d rounds", round_num)
