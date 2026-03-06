"""
platform/ac/convergence.py — Convergence detection and intervention for AC cycles.

Analyzes score trends across N cycles and triggers:
  - "converging"   → scores improving steadily → no action
  - "plateau"      → variance < 5pts over N cycles → trigger GA evolution
  - "regression"   → score declining trend → trigger adversarial deep-dive
  - "spike_failure"→ sudden VETO after good scores → trigger skill eval
  - "cold_start"   → < 3 cycles → wait
"""

from __future__ import annotations

import logging
import statistics
from typing import Optional

log = logging.getLogger(__name__)

PLATEAU_VARIANCE_THRESHOLD = 5.0  # < 5 points variance over N cycles = plateau
REGRESSION_SLOPE_THRESHOLD = -3.0  # score dropping > 3pts/cycle = regression
SPIKE_THRESHOLD = 15  # sudden drop > 15pts = spike failure
MIN_CYCLES_FOR_DETECTION = 3


def _linear_slope(values: list[float]) -> float:
    """Simple least-squares slope for a list of values."""
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = statistics.mean(values)
    num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    den = sum((i - x_mean) ** 2 for i in range(n))
    return num / den if den > 0 else 0.0


def ac_convergence_check(
    scores: list[int],
    veto_flags: Optional[list[bool]] = None,
) -> dict:
    """
    Analyze a list of cycle scores (chronological order, most recent last).

    Args:
        scores: list of total_score values per cycle
        veto_flags: optional list of booleans (True if cycle had a VETO)

    Returns:
        {
          "status": "converging" | "plateau" | "regression" | "spike_failure" | "cold_start",
          "slope": float,
          "variance": float,
          "confidence": float,   # 0-1, how certain we are
          "recommendation": str,
        }
    """
    n = len(scores)
    if n < MIN_CYCLES_FOR_DETECTION:
        return {
            "status": "cold_start",
            "slope": 0.0,
            "variance": 0.0,
            "confidence": 0.0,
            "recommendation": f"Wait for {MIN_CYCLES_FOR_DETECTION - n} more cycles.",
        }

    recent = [float(s) for s in scores[-5:]]  # last 5 cycles
    slope = _linear_slope(recent)
    variance = statistics.variance(recent) if len(recent) >= 2 else 0.0
    std = statistics.stdev(recent) if len(recent) >= 2 else 0.0
    _ = std  # used for future spike magnitude detection

    # Check for spike failure: sudden large drop in most recent cycle
    if len(scores) >= 2 and (scores[-2] - scores[-1]) >= SPIKE_THRESHOLD:
        return {
            "status": "spike_failure",
            "slope": round(slope, 2),
            "variance": round(variance, 2),
            "confidence": 0.85,
            "recommendation": "Sudden quality drop detected. Trigger skill eval on all AC agents.",
        }

    # Check VETO spike
    if veto_flags and len(veto_flags) >= 2:
        recent_vetos = sum(1 for v in veto_flags[-3:] if v)
        prev_vetos = sum(1 for v in veto_flags[:-3] if v)
        if recent_vetos >= 2 and prev_vetos == 0:
            return {
                "status": "spike_failure",
                "slope": round(slope, 2),
                "variance": round(variance, 2),
                "confidence": 0.9,
                "recommendation": "Repeated VETOs after clean cycles. Trigger skill eval.",
            }

    # Regression: slope < threshold
    if slope <= REGRESSION_SLOPE_THRESHOLD:
        confidence = min(1.0, abs(slope) / 10.0)
        return {
            "status": "regression",
            "slope": round(slope, 2),
            "variance": round(variance, 2),
            "confidence": round(confidence, 2),
            "recommendation": f"Score declining ({slope:+.1f}/cycle). Trigger adversarial deep-dive + RL reset.",
        }

    # Plateau: low variance, low positive slope
    if variance < PLATEAU_VARIANCE_THRESHOLD and 0.0 <= slope < 1.5:
        confidence = min(
            1.0, (PLATEAU_VARIANCE_THRESHOLD - variance) / PLATEAU_VARIANCE_THRESHOLD
        )
        return {
            "status": "plateau",
            "slope": round(slope, 2),
            "variance": round(variance, 2),
            "confidence": round(confidence, 2),
            "recommendation": f"Quality plateau at ~{statistics.mean(recent):.0f}/100. Trigger GA evolution.",
        }

    # Converging: positive slope, reasonable variance
    return {
        "status": "converging",
        "slope": round(slope, 2),
        "variance": round(variance, 2),
        "confidence": round(min(1.0, slope / 5.0), 2),
        "recommendation": "Quality improving. Continue current configuration.",
    }


def ac_check_skill_eval_trigger(
    cycle_num: int, skill_pass_rates: dict[str, float]
) -> list[str]:
    """
    Returns list of skill IDs that should be re-evaluated.

    Triggers:
    - Scheduled: cycles 5, 10, 15 (all skills)
    - Performance: if any skill has pass_rate < 0.7 for 3+ consecutive cycles
    """
    triggers = []

    # Scheduled eval
    if cycle_num in (5, 10, 15, 20):
        triggers = list(skill_pass_rates.keys()) or [
            "ac-architect",
            "ac-codex",
            "ac-adversarial",
            "ac-qa",
            "ac-cicd",
        ]
        log.info(
            "ac_skill_eval_trigger: scheduled eval at cycle %d for %s",
            cycle_num,
            triggers,
        )
        return triggers

    # Performance-based eval
    for skill_id, pass_rate in skill_pass_rates.items():
        if pass_rate < 0.7:
            triggers.append(skill_id)
            log.info(
                "ac_skill_eval_trigger: %s pass_rate=%.2f < 0.7 → trigger eval",
                skill_id,
                pass_rate,
            )

    return triggers


def ac_intervention_plan(convergence_status: str, project_id: str) -> dict:
    """
    Return an intervention plan based on convergence status.
    The plan is executed by ac_cicd_agent or the loop manager.
    """
    plans = {
        "plateau": {
            "action": "ga_evolve",
            "description": "Run GA evolution on ac-improvement-cycle workflow now (don't wait for nightly).",
            "also": ["thompson_boost_exploration"],  # increase exploration in Thompson
            "urgency": "high",
        },
        "regression": {
            "action": "adversarial_deep_dive",
            "description": "Run full adversarial check on all 12 dimensions with increased scrutiny.",
            "also": [
                "rl_reset_project"
            ],  # reset RL Q-values for this project (bad policy)
            "urgency": "critical",
        },
        "spike_failure": {
            "action": "skill_eval_all",
            "description": "Run skill-eval workflow on all 5 AC agent skills.",
            "also": [
                "thompson_reset_variant"
            ],  # reset Thompson to uniform (variant may have degraded)
            "urgency": "critical",
        },
        "converging": {
            "action": "continue",
            "description": "No intervention needed. Continue with RL recommendations.",
            "also": [],
            "urgency": "none",
        },
        "cold_start": {
            "action": "continue",
            "description": "Not enough data. Continue.",
            "also": [],
            "urgency": "none",
        },
    }
    plan = plans.get(convergence_status, plans["converging"])
    return {**plan, "project_id": project_id, "status": convergence_status}
