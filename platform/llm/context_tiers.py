"""
Context Tiers — L0 / L1 / L2 tiered context loading for agent prompts.
======================================================================

Inspired by OpenViking's tiered context approach.
Instead of always injecting full skill/memory content (expensive, noisy),
we select a tier based on agent role, hierarchy, and token budget:

  L0 (Abstract)  — name + 1-line summary per skill.  ~20 tok/skill.
                    Used for: routing, skill catalog, delegation decisions.
  L1 (Overview)  — key points, truncated content.     ~150 tok/skill.
                    Used for: standard execution by junior/mid agents.
  L2 (Detail)    — full content (current behavior).   ~500 tok/skill.
                    Used for: organizer agents, deep-expertise tasks.

Token savings: L0 = 90%, L1 = 60-70% vs L2 baseline.
"""
from __future__ import annotations

import enum
import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ── Tier budgets (chars per skill / per memory fact) ─────────────

_SKILL_BUDGET = {
    "L0": 120,     # ~30 tokens — name + one-liner
    "L1": 600,     # ~150 tokens — key paragraphs
    "L2": 1500,    # ~400 tokens — full content (current behavior)
}

_MEMORY_BUDGET = {
    "L0": 0,       # no memory injection
    "L1": 800,     # condensed project memory
    "L2": 4000,    # full project memory
}

_SKILLS_MAX = {
    "L0": 10,      # more skills at lower fidelity
    "L1": 5,       # standard count
    "L2": 5,       # full count
}

_GUIDELINES_BUDGET = {
    "L0": 0,
    "L1": 400,
    "L2": 2000,
}


class ContextTier(str, enum.Enum):
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"


@dataclass(frozen=True)
class TierBudget:
    """Token/char budgets for a given tier."""
    tier: ContextTier
    skill_chars: int
    skill_max: int
    memory_chars: int
    guidelines_chars: int

    @classmethod
    def for_tier(cls, tier: ContextTier) -> "TierBudget":
        t = tier.value
        return cls(
            tier=tier,
            skill_chars=_SKILL_BUDGET[t],
            skill_max=_SKILLS_MAX[t],
            memory_chars=_MEMORY_BUDGET[t],
            guidelines_chars=_GUIDELINES_BUDGET[t],
        )


# ── Tier selection ───────────────────────────────────────────────

def select_tier(
    hierarchy_rank: int = 50,
    capability_grade: str = "executor",
    task_type: str = "execute",
    token_budget: int | None = None,
) -> ContextTier:
    """
    Select context tier based on agent profile and task.

    Args:
        hierarchy_rank: 0=CEO → 50=junior (from agent definition)
        capability_grade: "organizer" or "executor"
        task_type: "route" | "plan" | "execute" | "review"
        token_budget: optional hard limit on total context tokens
    """
    # Routing/catalog → always L0 (minimal context, fast)
    if task_type == "route":
        return ContextTier.L0

    # Tight token budget → downgrade
    if token_budget is not None and token_budget < 2000:
        return ContextTier.L0

    # Organizers (rank < 30) or review tasks → L2 (full context)
    if capability_grade == "organizer" or hierarchy_rank < 30:
        return ContextTier.L2

    # Review tasks need full detail
    if task_type == "review":
        return ContextTier.L2

    # Standard execution → L1
    return ContextTier.L1


# ── L0 summary extraction ───────────────────────────────────────

_SENTENCE_RE = re.compile(r"[.!?]\s+|\n", re.MULTILINE)


def extract_l0_summary(content: str, name: str = "") -> str:
    """
    Extract a one-line L0 summary from skill content.

    Strategy: first sentence of content, capped at 100 chars.
    Pure text extraction — no LLM needed.
    """
    if not content:
        return name or "—"

    # Strip markdown headers and leading whitespace
    text = content.strip()
    text = re.sub(r"^#+\s+", "", text, count=1)

    # Take first sentence
    parts = _SENTENCE_RE.split(text, maxsplit=1)
    summary = parts[0].strip() if parts else text[:100]

    # Cap length
    if len(summary) > 100:
        summary = summary[:97] + "..."
    return summary


# ── Tiered skill formatting ─────────────────────────────────────

def format_skill_tiered(
    name: str,
    content: str,
    tier: ContextTier,
    relevance: float = 0.0,
    l0_summary: str | None = None,
) -> str:
    """Format a single skill at the given tier level."""
    budget = _SKILL_BUDGET[tier.value]

    if tier == ContextTier.L0:
        summary = l0_summary or extract_l0_summary(content, name)
        return f"- **{name}**: {summary}"

    if tier == ContextTier.L1:
        truncated = _smart_truncate(content, budget)
        header = f"### {name}"
        if relevance > 0:
            header += f" (relevance: {relevance:.2f})"
        return f"{header}\n{truncated}"

    # L2 — full content (current behavior)
    truncated = content[:budget] + ("..." if len(content) > budget else "")
    header = f"### {name}"
    if relevance > 0:
        header += f" (relevance: {relevance:.2f})"
    return f"{header}\n{truncated}"


def build_tiered_skills(
    skills: list[dict],
    tier: ContextTier,
) -> str:
    """
    Build the full skills prompt section for a given tier.

    Args:
        skills: list of {"name": str, "content": str, "similarity": float, "l0": str?}
        tier: context tier to use
    """
    budget = TierBudget.for_tier(tier)
    limited = skills[:budget.skill_max]

    if not limited:
        return ""

    parts = []
    for skill in limited:
        formatted = format_skill_tiered(
            name=skill.get("name", "Unknown"),
            content=skill.get("content", ""),
            tier=tier,
            relevance=skill.get("similarity", 0.0),
            l0_summary=skill.get("l0"),
        )
        parts.append(formatted)

    if tier == ContextTier.L0:
        return "Available skills:\n" + "\n".join(parts)
    return "\n\n".join(parts)


def apply_tier_to_context(
    tier: ContextTier,
    *,
    project_context: str = "",
    project_memory: str = "",
    guidelines: str = "",
    vision: str = "",
) -> dict[str, str]:
    """
    Apply tier budgets to all context sections.

    Returns dict with truncated strings ready for prompt injection.
    """
    budget = TierBudget.for_tier(tier)
    result = {}

    # Memory
    if budget.memory_chars > 0 and project_memory:
        result["project_memory"] = project_memory[:budget.memory_chars]
    else:
        result["project_memory"] = ""

    # Guidelines
    if budget.guidelines_chars > 0 and guidelines:
        result["guidelines"] = guidelines[:budget.guidelines_chars]
    else:
        result["guidelines"] = ""

    # Vision — only at L2
    if tier == ContextTier.L2 and vision:
        result["vision"] = vision[:3000]
    else:
        result["vision"] = ""

    # Project context — always available (but sized)
    if project_context:
        ctx_budget = budget.memory_chars if budget.memory_chars > 0 else 400
        result["project_context"] = project_context[:ctx_budget]
    else:
        result["project_context"] = ""

    return result


# ── Helpers ──────────────────────────────────────────────────────

def _smart_truncate(text: str, max_chars: int) -> str:
    """Truncate text at a sentence boundary if possible."""
    if len(text) <= max_chars:
        return text

    # Try to cut at last sentence end within budget
    window = text[:max_chars]
    last_period = max(window.rfind(". "), window.rfind(".\n"), window.rfind("\n\n"))
    if last_period > max_chars * 0.5:
        return window[:last_period + 1]
    return window[:max_chars - 3] + "..."


def tier_savings_estimate(
    skills_count: int, tier: ContextTier
) -> dict[str, int]:
    """Estimate token savings for a given tier vs L2 baseline."""
    l2_tokens = skills_count * (_SKILL_BUDGET["L2"] // 4)  # rough: 4 chars/token
    tier_tokens = skills_count * (_SKILL_BUDGET[tier.value] // 4)
    return {
        "baseline_tokens": l2_tokens,
        "tier_tokens": tier_tokens,
        "saved_tokens": l2_tokens - tier_tokens,
        "savings_pct": round((1 - tier_tokens / max(l2_tokens, 1)) * 100),
    }
