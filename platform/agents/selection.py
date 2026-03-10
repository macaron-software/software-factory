"""Thompson Sampling — probabilistic agent selection.

Selects the best agent for a role+domain using Beta(accepted+1, rejected+1) sampling.
Agents with high rejection rates are deprioritised but not excluded (exploration).
"""

from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .store import AgentDef

logger = logging.getLogger(__name__)

# Rejection rate above which we force a better provider (azure-openai)
REJECTION_RATE_THRESHOLD = 0.40
# Minimum iterations before Thompson kicks in (cold start → uniform)
THOMPSON_MIN_ITERATIONS = 5


def _beta_sample(accepted: int, rejected: int) -> float:
    """Sample from Beta(α=accepted+1, β=rejected+1) using the Gamma trick."""
    alpha = max(accepted + 1, 1)
    beta = max(rejected + 1, 1)
    x = random.gammavariate(alpha, 1.0)
    y = random.gammavariate(beta, 1.0)
    return x / (x + y)


def get_agent_scores(agent_id: str, task_domain: str = "") -> dict:
    """Fetch accepted/rejected counts for an agent, optionally filtered by domain."""
    try:
        from ..db.migrations import get_db

        db = get_db()
        if task_domain:
            row = db.execute(
                """SELECT COALESCE(SUM(accepted),0) accepted, COALESCE(SUM(rejected),0) rejected,
                          COALESCE(SUM(iterations),0) iterations
                   FROM agent_scores WHERE agent_id=? AND (epic_id=? OR epic_id='')""",
                (agent_id, task_domain),
            ).fetchone()
        else:
            row = db.execute(
                """SELECT COALESCE(SUM(accepted),0) accepted, COALESCE(SUM(rejected),0) rejected,
                          COALESCE(SUM(iterations),0) iterations
                   FROM agent_scores WHERE agent_id=?""",
                (agent_id,),
            ).fetchone()
        db.close()
        if row:
            return {"accepted": row[0], "rejected": row[1], "iterations": row[2]}
    except Exception:
        pass
    return {"accepted": 0, "rejected": 0, "iterations": 0}


def rejection_rate(agent_id: str, task_domain: str = "") -> float:
    """Return rejection rate [0-1] for an agent. 0 if no data."""
    s = get_agent_scores(agent_id, task_domain)
    total = s["accepted"] + s["rejected"]
    if total == 0:
        return 0.0
    return s["rejected"] / total


def thompson_select(candidates: list["AgentDef"], task_domain: str = "") -> "AgentDef":
    """Select the best candidate agent via Thompson Sampling.

    Each candidate is scored by sampling Beta(accepted+1, rejected+1).
    Agents with insufficient history (< THOMPSON_MIN_ITERATIONS) get a
    uniform warm-up score so they aren't starved.

    Returns the agent with the highest sample.
    """
    if not candidates:
        raise ValueError("thompson_select: empty candidates list")
    if len(candidates) == 1:
        return candidates[0]

    best_agent = candidates[0]
    best_score = -1.0

    for agent in candidates:
        s = get_agent_scores(agent.id, task_domain)
        if s["iterations"] < THOMPSON_MIN_ITERATIONS:
            # Cold start: uniform exploration (0.4–0.6 range)
            score = random.uniform(0.4, 0.6)
        else:
            score = _beta_sample(s["accepted"], s["rejected"])

        logger.debug(
            "Thompson [%s/%s] acc=%d rej=%d score=%.3f",
            agent.id, task_domain, s["accepted"], s["rejected"], score,
        )
        if score > best_score:
            best_score = score
            best_agent = agent

    logger.info(
        "Thompson selected %s (score=%.3f domain=%s) from %d candidates",
        best_agent.id, best_score, task_domain or "*", len(candidates),
    )
    return best_agent


def select_agent_for_role(
    role: str,
    task_domain: str = "",
    project_id: str = "",
) -> "AgentDef | None":
    """Find all agents matching a role, then Thompson-select the best one.

    Falls back to domain similarity if no data for exact domain.
    """
    try:
        from ..agents.store import get_agent_store

        store = get_agent_store()
        all_agents = store.list_all()

        # Match by role (exact or partial)
        role_lower = role.lower().replace("-", "_").replace(" ", "_")
        candidates = [
            a for a in all_agents
            if a.role and (
                a.role.lower().replace("-", "_").replace(" ", "_") == role_lower
                or role_lower in a.id.lower()
            )
        ]

        if not candidates:
            # Direct id lookup
            agent = store.get(role)
            return agent

        if len(candidates) == 1:
            return candidates[0]

        return thompson_select(candidates, task_domain or project_id)

    except Exception as e:
        logger.warning("select_agent_for_role failed: %s", e)
        return None
