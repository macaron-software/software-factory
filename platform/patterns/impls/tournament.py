"""Tournament pattern: N agents solve same task, judge picks best output.

Unlike network (debate format), agents work independently without seeing
each other's outputs. A judge agent evaluates all submissions and
selects the winner. Useful for creative tasks where approach diversity matters.
"""
# Ref: feat-patterns

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


async def run_tournament(engine, run, task: str):
    """Tournament: N agents compete independently, judge picks best."""
    nodes = list(run.nodes.keys())
    if not nodes:
        return

    if len(nodes) < 2:
        await engine._execute_node(run, nodes[0], task)
        return

    # Last node is judge, others are competitors
    competitors = nodes[:-1]
    judge = nodes[-1]

    # Phase 1: all competitors solve the task independently (parallel)
    await asyncio.gather(
        *(engine._execute_node(run, nid, task) for nid in competitors)
    )

    # Collect submissions
    submissions = []
    for i, nid in enumerate(competitors, 1):
        out = run.nodes[nid].output or "(no output)"
        submissions.append(f"## Submission {i} (by {nid})\n{out}")

    # Phase 2: judge evaluates and picks winner
    judge_task = (
        f"TOURNAMENT JUDGE — Evaluate these {len(competitors)} independent submissions "
        f"for the task below and pick the BEST one. Explain why.\n\n"
        f"### Original Task\n{task}\n\n"
        + "\n\n---\n\n".join(submissions)
        + "\n\nPick the best submission number and explain your reasoning."
    )
    await engine._execute_node(run, judge, judge_task)
