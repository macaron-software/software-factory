"""Agent market valuation — compute market_value from agent stats."""

from __future__ import annotations

from ..agents.store import AgentDef


def compute_market_value(agent: AgentDef, success_rate: float = 0.5) -> int:
    """Return market value in tokens based on agent capabilities."""
    base = (100 - min(agent.hierarchy_rank, 100)) * 10
    skill_bonus = len(agent.skills) * 50
    tool_bonus = len(agent.tools) * 30
    perf_bonus = int(success_rate * 500)
    veto_premium = 200 if agent.permissions.get("can_veto") else 0
    return base + skill_bonus + tool_bonus + perf_bonus + veto_premium


def valuation_breakdown(agent: AgentDef, success_rate: float = 0.5) -> dict:
    """Return detailed breakdown for UI display."""
    base = (100 - min(agent.hierarchy_rank, 100)) * 10
    skill_bonus = len(agent.skills) * 50
    tool_bonus = len(agent.tools) * 30
    perf_bonus = int(success_rate * 500)
    veto_premium = 200 if agent.permissions.get("can_veto") else 0
    return {
        "base_value": base,
        "skill_bonus": skill_bonus,
        "tool_bonus": tool_bonus,
        "perf_bonus": perf_bonus,
        "veto_premium": veto_premium,
        "total": base + skill_bonus + tool_bonus + perf_bonus + veto_premium,
    }
