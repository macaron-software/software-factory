"""
platform/ac/reward.py — Unified reward function for AC improvement cycles.

R ∈ [-1.0, +1.0] combining:
  - quality       40%  total_score/100
  - adversarial   30%  weighted average of 14 dimensions (critical x2)
  - traceability  15%  traceability_score/100
  - efficiency    10%  penalty for veto count and TDD iterations
  - regression     5%  penalty if score dropped vs previous cycle

Hard constraint: if ANY critical dimension < 60 → R = -1.0 (absolute veto)

Adversarial dimensions (14 total):
  Critical (weight=2.0, veto < 60): security, honesty, no_slop, no_mock_data,
    no_hardcode, test_quality, traceability, secure_by_design
  Warning (weight=1.0): architecture, fallback, over_engineering,
    observability, resilience, refactoring
"""
# Ref: feat-quality

from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger(__name__)

# ── Dimension weights ──────────────────────────────────────────────────────────
# Critical (weight=2.0) — absolute veto if score < CRITICAL_THRESHOLD
_CRITICAL_DIMS = {
    "security",
    "honesty",
    "no_slop",
    "no_mock_data",
    "no_hardcode",
    "test_quality",
    "traceability",
    "secure_by_design",  # SecureByDesign 25-control audit (securebydesign.saccessa.com)
}
CRITICAL_THRESHOLD = 60  # below this → R = -1.0

# Warning (weight=1.0)
_WARNING_DIMS = {
    "architecture",
    "fallback",
    "over_engineering",
    "observability",
    "resilience",
    "refactoring",  # AC Refactor phase — code smells, tech debt, performance
}

# Total weight denominator for normalization
_TOTAL_WEIGHT = len(_CRITICAL_DIMS) * 2.0 + len(_WARNING_DIMS) * 1.0


def _weighted_adversarial(scores: dict[str, int]) -> float:
    """
    Return weighted average of adversarial scores ∈ [0.0, 1.0].
    Critical dimensions count double. Missing dimensions default to 50 (warn).
    """
    if not scores:
        return 0.5  # no data → neutral

    total = 0.0
    weight_sum = 0.0
    for dim, weight in {
        **{d: 2.0 for d in _CRITICAL_DIMS},
        **{d: 1.0 for d in _WARNING_DIMS},
    }.items():
        score = scores.get(dim, 50)  # default 50 if not measured
        total += (score / 100.0) * weight
        weight_sum += weight

    return total / weight_sum if weight_sum > 0 else 0.5


def _has_critical_failure(scores: dict[str, int]) -> bool:
    """True if any critical dimension is below CRITICAL_THRESHOLD."""
    for dim in _CRITICAL_DIMS:
        if scores.get(dim, 100) < CRITICAL_THRESHOLD:
            return True
    return False


def ac_reward(
    total_score: int,
    adversarial_scores: dict[str, int],
    traceability_score: int,
    defect_count: int = 0,
    veto_count: int = 0,
    prev_score: Optional[int] = None,
) -> float:
    """
    Compute normalized reward R ∈ [-1.0, +1.0] for an AC cycle.

    Args:
        total_score: Overall quality score 0-100
        adversarial_scores: {dimension: score} for the 12 adversarial checks
        traceability_score: Traceability score 0-100
        defect_count: Number of defects detected
        veto_count: Number of VETO signals during the cycle
        prev_score: Score from previous cycle (for regression detection)

    Returns:
        float ∈ [-1.0, +1.0]
    """
    # Hard constraint — critical failure → absolute veto
    if _has_critical_failure(adversarial_scores):
        log.info(
            "ac_reward: critical adversarial failure → R=-1.0 (scores=%s)",
            {k: v for k, v in adversarial_scores.items() if k in _CRITICAL_DIMS},
        )
        return -1.0

    # 1. Quality (40%)
    quality_signal = (total_score / 100.0) * 0.40

    # 2. Adversarial (30%)
    adv_signal = _weighted_adversarial(adversarial_scores) * 0.30

    # 3. Traceability (15%)
    trace_signal = (traceability_score / 100.0) * 0.15

    # 4. Efficiency (10%) — penalize excess vetos and defects
    # veto_count: 0=perfect, 5+=max penalty
    efficiency_ratio = max(0.0, 1.0 - (veto_count / 5.0))
    # Extra penalty for defects: > 10 defects → 50% efficiency penalty
    defect_penalty = max(0.0, 1.0 - (defect_count / 20.0))
    efficiency_signal = (efficiency_ratio * 0.6 + defect_penalty * 0.4) * 0.10

    # 5. Regression (5%) — penalize if score dropped
    regression_signal = 0.05
    if prev_score is not None and total_score < prev_score:
        drop_pct = (prev_score - total_score) / max(1, prev_score)
        regression_signal = (
            1.0 - drop_pct
        ) * 0.05  # partial penalty proportional to drop

    raw = (
        quality_signal
        + adv_signal
        + trace_signal
        + efficiency_signal
        + regression_signal
    )

    # Normalize from [0, 1] range to [-1, +1]
    # R=0.5 maps to 0.0 (neutral), R=1.0 maps to +1.0, R=0.0 maps to -1.0
    normalized = (raw - 0.5) * 2.0
    result = max(-1.0, min(1.0, normalized))

    log.debug(
        "ac_reward: quality=%.2f adv=%.2f trace=%.2f eff=%.2f reg=%.2f → raw=%.3f R=%.3f",
        quality_signal,
        adv_signal,
        trace_signal,
        efficiency_signal,
        regression_signal,
        raw,
        result,
    )
    return round(result, 4)


def ac_reward_from_cycle(cycle: dict, prev_cycle: Optional[dict] = None) -> float:
    """
    Convenience wrapper accepting a cycle dict (from DB row or inject-cycle payload).
    """
    import json

    adv_raw = cycle.get("adversarial_scores", {})
    if isinstance(adv_raw, str):
        try:
            adv_raw = json.loads(adv_raw)
        except Exception:
            adv_raw = {}

    return ac_reward(
        total_score=int(cycle.get("total_score", 0)),
        adversarial_scores=adv_raw if isinstance(adv_raw, dict) else {},
        traceability_score=int(cycle.get("traceability_score", 0)),
        defect_count=int(cycle.get("defect_count", 0)),
        veto_count=int(cycle.get("veto_count", 0)),
        prev_score=int(prev_cycle["total_score"]) if prev_cycle else None,
    )


def ac_rl_state(
    project_id: str,
    cycle_num: int,
    total_score: int,
    defect_count: int,
    tier: str = "simple",
) -> dict:
    """
    Build RL state dict for record_experience() / recommend().
    Maps AC project state to the RL policy's expected state format.
    """
    _tier_complexity = {
        "simple": "simple",
        "simple-compile": "simple",
        "medium": "medium",
        "complex": "complex",
        "enterprise": "complex",
    }
    return {
        "workflow_id": "ac-improvement-cycle",
        "phase_idx": min(cycle_num, 19),  # cap at 19 for RL state encoding
        "quality_score": total_score / 100.0,
        "rejection_pct": min(1.0, defect_count / 20.0),
        "phase_count": 5,  # ac-improvement-cycle has 5 phases
        "team_size": 5,  # AC team = 5 agents
        "complexity": _tier_complexity.get(tier, "simple"),
    }
