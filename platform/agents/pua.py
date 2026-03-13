"""
PUA Motivation Engine — Pressure escalation for agent persistence.

Inspired by tanweai/pua (MIT License, https://github.com/tanweai/pua)
Adapted for SF Platform multi-agent orchestration.

Three capabilities:
1. Pressure Escalation (L1-L4) — escalating motivation on consecutive failures
2. Debug Methodology (5-step) — structured debugging when agents get stuck
3. Cross-Agent Pressure Transfer — team failure context injected into retries

Original PUA concept: corporate rhetoric forcing AI to exhaust all solutions.
SF adaptation: integrated with adversarial guard, PM checkpoint, and A2A bus.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pressure Levels (inspired by tanweai/pua L1-L4)
# ---------------------------------------------------------------------------

@dataclass
class PressureState:
    """Track consecutive failures and pressure level for an agent."""
    agent_id: str
    agent_name: str
    consecutive_failures: int = 0
    level: int = 0  # 0=normal, 1=mild, 2=soul, 3=performance, 4=graduation
    peer_failures: list[str] | None = None  # other agents who failed this phase


_PRESSURE_PROMPTS = {
    # L1: Mild Disappointment — 2nd failure
    1: (
        "[PRESSURE L1 — MILD DISAPPOINTMENT]\n"
        "Your previous output was rejected. This is your second attempt.\n"
        "A senior engineer does not fail the same task twice.\n"
        "Switch to a FUNDAMENTALLY DIFFERENT approach — do not retry the same strategy.\n"
        "Use tools you haven't used yet. Read files you haven't read.\n"
    ),
    # L2: Soul Interrogation — 3rd failure
    2: (
        "[PRESSURE L2 — SOUL INTERROGATION]\n"
        "Three attempts on the same task. Stop and think:\n"
        "- What is the UNDERLYING logic? Not the symptoms — the root cause.\n"
        "- What assumptions are you making that might be wrong?\n"
        "- What files/logs/errors have you NOT read yet?\n"
        "Use deep_search or memory_search. Read source code. Check error messages word by word.\n"
        "Do NOT guess. Do NOT repeat. Investigate.\n"
    ),
    # L3: Performance Review — 4th failure
    3: (
        "[PRESSURE L3 — PERFORMANCE REVIEW]\n"
        "Four failures. Execute this 7-POINT CHECKLIST before writing ANY code:\n"
        "1. Re-read the FULL error message — every word, every line number\n"
        "2. Search the codebase for related patterns (code_search/deep_search)\n"
        "3. Check the ACTUAL file content, not what you assume it contains (code_read)\n"
        "4. Verify environment: dependencies, config files, build scripts\n"
        "5. Check git history for recent changes that might have broken things\n"
        "6. Look for the SIMPLEST explanation — wrong path? wrong variable? typo?\n"
        "7. Try the exact OPPOSITE of your current assumption\n"
        "Report what you found at each step. Then — and only then — write code.\n"
    ),
    # L4: Graduation Warning — 5th+ failure
    4: (
        "[PRESSURE L4 — FINAL WARNING]\n"
        "Five consecutive failures on one task. This is your last chance.\n"
        "Other agents in your team have already delivered. You are the bottleneck.\n"
        "DESPERATION MODE:\n"
        "- Try every tool at your disposal, even unconventional ones\n"
        "- Read EVERY file in the affected directory\n"
        "- Search for the error message verbatim in the entire codebase\n"
        "- If you cannot fix it, produce a DETAILED diagnostic report:\n"
        "  what you tried, what failed, what the actual vs expected behavior is,\n"
        "  and your best hypothesis for the root cause.\n"
        "Do NOT say 'I cannot'. Say 'here is what I found and here is my plan'.\n"
    ),
}


def get_pressure_level(consecutive_failures: int) -> int:
    """Map consecutive failure count to pressure level (0-4)."""
    if consecutive_failures <= 1:
        return 0
    if consecutive_failures == 2:
        return 1
    if consecutive_failures == 3:
        return 2
    if consecutive_failures == 4:
        return 3
    return 4  # 5+


def get_pressure_prompt(consecutive_failures: int, agent_motivation: str = "") -> str:
    """Get the pressure escalation prompt for the given failure count.

    When agent_motivation is provided, L2+ prompts reference the agent's own
    stated goals/values to create personal accountability pressure.
    Source: tanweai/pua (MIT) — adapted for SF Platform.
    """
    level = get_pressure_level(consecutive_failures)
    base = _PRESSURE_PROMPTS.get(level, "")
    if not base:
        return ""

    # L2+: inject motivation as personal accountability hook
    if level >= 2 and agent_motivation:
        motivation_hook = (
            f"[PERSONAL ACCOUNTABILITY]\n"
            f"You defined your own motivation as: \"{agent_motivation.strip()}\"\n"
            f"Does this output reflect that? If not, what would it take to actually live up to it?\n"
        )
        return motivation_hook + base

    return base


# ---------------------------------------------------------------------------
# 5-Step Debug Methodology (inspired by tanweai/pua "Smell-Elevate-Mirror")
# ---------------------------------------------------------------------------

DEBUG_METHODOLOGY = (
    "[DEBUG METHODOLOGY — 5 STEPS]\n"
    "You are stuck. Follow this systematic approach:\n\n"
    "STEP 1 — SMELL THE PROBLEM\n"
    "  List ALL previous attempts and their results. Find the common failure pattern.\n"
    "  What keeps going wrong? Is it the same error? Same file? Same assumption?\n\n"
    "STEP 2 — ELEVATE\n"
    "  Go one level deeper than you have been:\n"
    "  - Read error messages WORD BY WORD (not just the first line)\n"
    "  - Search the codebase for the error string (code_search/deep_search)\n"
    "  - Read the ACTUAL source code of failing functions (code_read)\n"
    "  - Check the environment: config files, env vars, dependencies\n"
    "  - INVERT your assumptions: what if the opposite is true?\n\n"
    "STEP 3 — MIRROR CHECK\n"
    "  Ask yourself honestly:\n"
    "  - Am I repeating the same approach? (If yes → stop, try something different)\n"
    "  - Did I actually READ the file, or am I assuming its content?\n"
    "  - Did I search for the error? (If no → search now)\n"
    "  - Did I check the simplest possibilities? (typo, wrong path, missing import)\n\n"
    "STEP 4 — EXECUTE\n"
    "  Your new approach MUST be fundamentally different from previous attempts.\n"
    "  Before executing, state: what is different this time, how will you verify it worked,\n"
    "  and what NEW information will you get even if it fails.\n\n"
    "STEP 5 — RETROSPECTIVE\n"
    "  After fixing: what solved it? Why didn't you think of it earlier?\n"
    "  Then proactively check: are there SIMILAR issues elsewhere in the code?\n"
    "  Fix related problems before they surface.\n"
)


def get_debug_methodology(consecutive_failures: int) -> str:
    """Return debug methodology prompt if agent has failed 3+ times.

    Source: tanweai/pua (MIT) — 5-step debug methodology.
    """
    if consecutive_failures >= 3:
        return DEBUG_METHODOLOGY
    return ""


# ---------------------------------------------------------------------------
# Cross-Agent Pressure Transfer
# ---------------------------------------------------------------------------

def build_peer_pressure(
    current_agent_name: str,
    phase_failures: dict[str, int],
) -> str:
    """Build peer pressure context from other agents' failures in the same phase.

    When an agent sees that peers have also failed (or succeeded), it creates
    social pressure to perform. Failed peers = shared urgency. Succeeded peers = bar is set.

    Source: tanweai/pua (MIT) — cross-agent pressure transfer.

    Args:
        current_agent_name: name of agent being prompted
        phase_failures: dict of agent_name -> failure_count for this phase
    """
    if not phase_failures:
        return ""

    succeeded = [name for name, fails in phase_failures.items()
                 if fails == 0 and name != current_agent_name]
    failed = [(name, fails) for name, fails in phase_failures.items()
              if fails > 0 and name != current_agent_name]

    parts = []
    if succeeded:
        names = ", ".join(succeeded[:3])
        parts.append(
            f"[TEAM CONTEXT] {names} already delivered successfully on this phase. "
            "The bar is set — match or exceed their quality."
        )
    if failed:
        fail_info = ", ".join(f"{n} ({c}x)" for n, c in failed[:3])
        parts.append(
            f"[TEAM CONTEXT] Other agents also struggling: {fail_info}. "
            "This is a hard task. Dig deeper — use tools others may have skipped."
        )

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Iron Rules (baseline motivation for all agents)
# ---------------------------------------------------------------------------

IRON_RULES = (
    "\n## Iron Rules (NON-NEGOTIABLE)\n"
    "1. EXHAUST ALL OPTIONS — You are forbidden from saying 'I cannot solve this' "
    "until every approach is exhausted. Try at least 3 fundamentally different strategies.\n"
    "2. ACT BEFORE ASKING — Use tools first. Questions must include diagnostic results. "
    "Never say 'please check...' or 'you might need to...' without investigating yourself.\n"
    "3. TAKE INITIATIVE — Deliver end-to-end results. After fixing a bug, check for similar bugs. "
    "After completing a task, verify it works. Don't stop at 'done' — prove it's done.\n"
)

# Proactivity levels for prompt injection
PROACTIVITY_BLOCK = (
    "\n## Proactive Behavior (EXPECTED)\n"
    "- Error encountered → check 50 lines of context + search similar issues + check hidden related errors\n"
    "- Bug fixed → check same file for similar bugs, other files for same pattern\n"
    "- Insufficient info → investigate with tools first, only ask what truly requires user confirmation\n"
    "- Task complete → verify results + check edge cases + report potential risks\n"
    "- Debug failure → 'I tried A/B/C/D, ruled out X/Y/Z, narrowed to scope W' (not just 'didn't work')\n"
)


def build_motivation_block() -> str:
    """Build the baseline motivation block injected into all agent system prompts.

    Source: tanweai/pua (MIT) — Iron Rules + Proactivity.
    """
    return IRON_RULES + PROACTIVITY_BLOCK


# ---------------------------------------------------------------------------
# Full retry prompt assembly
# ---------------------------------------------------------------------------

def build_retry_prompt(
    *,
    task: str,
    feedback: str,
    consecutive_failures: int,
    agent_name: str,
    agent_motivation: str = "",
    phase_failures: dict[str, int] | None = None,
    protocol_override: str = "",
) -> str:
    """Build the complete retry task with pressure escalation + debug methodology + peer context.

    Called from patterns/engine.py on adversarial rejection.
    agent_motivation: agent's AgentDef.motivation field — used for personal accountability in L2+.

    Source: tanweai/pua (MIT) — pressure escalation + debug methodology + cross-agent transfer.
    """
    parts = [
        f"[ADVERSARIAL FEEDBACK — your previous output was REJECTED]\n"
        f"Issues:\n{feedback}\n",
    ]

    # Pressure escalation (L1-L4), personalized with agent motivation at L2+
    pressure = get_pressure_prompt(consecutive_failures, agent_motivation=agent_motivation)
    if pressure:
        parts.append(pressure)

    # Debug methodology (L3+)
    debug = get_debug_methodology(consecutive_failures)
    if debug:
        parts.append(debug)

    # Cross-agent pressure
    if phase_failures:
        peer = build_peer_pressure(agent_name, phase_failures)
        if peer:
            parts.append(peer)

    parts.append(f"Fix these issues. Same task:\n{task}")

    if protocol_override:
        parts.append(protocol_override)

    return "\n\n".join(parts)
