"""Voting pattern: N agents independently evaluate, majority wins.

Each agent evaluates the task independently and produces a vote.
Results aggregated by majority. Unlike network (debate), agents don't
see each other's positions — pure independent judgment.
"""

from __future__ import annotations

import asyncio
import logging
import re

logger = logging.getLogger(__name__)


async def run_voting(engine, run, task: str):
    """Voting: independent evaluation, majority wins."""
    nodes = list(run.nodes.keys())
    if not nodes:
        return

    vote_task = (
        f"{task}\n\n"
        f"After your analysis, end your response with a JSON vote block:\n"
        f'{{"vote": "approve" or "reject", "confidence": 0-100, "reason": "one sentence"}}'
    )
    await asyncio.gather(
        *(engine._execute_node(run, nid, vote_task) for nid in nodes)
    )

    # Tally votes
    approves = 0
    rejects = 0
    for nid in nodes:
        out = run.nodes[nid].output or ""
        vote_match = re.search(r'"vote"\s*:\s*"(approve|reject)"', out, re.IGNORECASE)
        if vote_match:
            if vote_match.group(1).lower() == "approve":
                approves += 1
            else:
                rejects += 1
        else:
            if len(out.strip()) > 100:
                approves += 1
            else:
                rejects += 1

    total = approves + rejects
    result = "APPROVED" if approves > rejects else "REJECTED"
    logger.info("VOTING: %s (%d/%d approve, %d/%d reject)", result, approves, total, rejects, total)
    run.pattern.config["_vote_result"] = {
        "decision": result, "approves": approves, "rejects": rejects, "total": total,
    }
