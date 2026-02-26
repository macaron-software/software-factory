"""
RL Policy — Q-learning for mid-mission pattern adaptation.

Offline batch training on rl_experience table.
Called by engine.py at phase start to recommend pattern changes.

Usage:
    from platform.agents.rl_policy import RLPolicy, get_rl_policy
    policy = get_rl_policy()
    rec = policy.recommend(mission_id, phase_id, state_dict)
    # rec = {"action": "keep" | "switch_parallel" | ..., "confidence": 0.0-1.0, "q_value": float}
"""
from __future__ import annotations

import json
import math
import random
import logging
from typing import Any
from pathlib import Path

log = logging.getLogger(__name__)

# ── Action space ─────────────────────────────────────────────────────────────
ACTIONS = [
    "keep",
    "switch_parallel",
    "switch_sequential",
    "switch_hierarchical",
    "switch_debate",
    "add_agent",
    "remove_agent",
]

# ── Hyperparameters ───────────────────────────────────────────────────────────
LEARNING_RATE = 0.1
DISCOUNT_FACTOR = 0.9
EPSILON = 0.1          # exploration rate
CONFIDENCE_THRESHOLD = 0.70  # min confidence to fire recommendation
MIN_VISITS = 3         # min state visits before trusting Q-values


def _bucket(value: float, buckets: int = 5) -> int:
    """Discretize a [0,1] float into `buckets` bins."""
    return min(buckets - 1, int(value * buckets))


def _encode_state(
    wf_id: str,
    phase_idx: int,
    rejection_pct: float,
    quality_score: float,
    phase_count: int = 5,
) -> str:
    """Encode mission state as a hashable string key."""
    # Normalize phase position to [0,1]
    phase_pos = phase_idx / max(1, phase_count - 1)
    rej_bucket = _bucket(min(1.0, rejection_pct / 100.0))
    qual_bucket = _bucket(quality_score)
    phase_bucket = _bucket(phase_pos)
    # Hash wf_id to reduce cardinality
    wf_hash = abs(hash(wf_id)) % 100
    return f"{wf_hash}:{phase_bucket}:{rej_bucket}:{qual_bucket}"


class RLPolicy:
    """
    Simple tabular Q-learning policy.
    Q-table: {state_key: {action: q_value}}
    Visit counts: {state_key: {action: count}}
    """

    def __init__(self) -> None:
        self._q: dict[str, dict[str, float]] = {}
        self._visits: dict[str, dict[str, int]] = {}
        self._total_decisions = 0
        self._loaded = False

    # ── Public API ───────────────────────────────────────────────────────────

    def recommend(
        self,
        mission_id: str,
        phase_id: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Recommend an action for the current mission state.
        Returns {"action": str, "confidence": float, "q_value": float, "fired": bool}
        fired=True only if confidence >= CONFIDENCE_THRESHOLD.
        """
        if not self._loaded:
            self._load_or_train()

        wf_id = state_dict.get("workflow_id", "")
        phase_idx = state_dict.get("phase_idx", 0)
        rejection_pct = state_dict.get("rejection_pct", 0.0)
        quality_score = state_dict.get("quality_score", CONFIDENCE_THRESHOLD)
        phase_count = state_dict.get("phase_count", 5)

        state_key = _encode_state(wf_id, phase_idx, rejection_pct, quality_score, phase_count)
        q_row = self._q.get(state_key, {})
        visit_row = self._visits.get(state_key, {})
        total_visits = sum(visit_row.values())

        # Insufficient data → keep
        if total_visits < MIN_VISITS:
            return {"action": "keep", "confidence": 0.0, "q_value": 0.0, "fired": False}

        # Best action by Q-value
        best_action = max(ACTIONS, key=lambda a: q_row.get(a, 0.0))
        best_q = q_row.get(best_action, 0.0)

        # Confidence: sigmoid of Q-value advantage over "keep"
        keep_q = q_row.get("keep", 0.0)
        advantage = best_q - keep_q
        confidence = 1.0 / (1.0 + math.exp(-5 * advantage))

        fired = confidence >= CONFIDENCE_THRESHOLD and best_action != "keep"

        if fired:
            self._total_decisions += 1
            self._log_decision(mission_id, phase_id, state_key, best_action, best_q, confidence)

        return {
            "action": best_action,
            "confidence": round(confidence, 3),
            "q_value": round(best_q, 4),
            "fired": fired,
        }

    def record_experience(
        self,
        mission_id: str,
        state_dict: dict[str, Any],
        action: str,
        reward: float,
        next_state_dict: dict[str, Any],
    ) -> None:
        """Store a transition (s, a, r, s') in the DB for nightly retraining."""
        try:
            from ..db.migrations import get_db
            db = get_db()
            wf_id = state_dict.get("workflow_id", "")
            phase_idx = state_dict.get("phase_idx", 0)
            phase_count = state_dict.get("phase_count", 5)
            state_key = _encode_state(
                wf_id, phase_idx,
                state_dict.get("rejection_pct", 0.0),
                state_dict.get("quality_score", 0.5),
                phase_count,
            )
            next_state_key = _encode_state(
                next_state_dict.get("workflow_id", wf_id),
                next_state_dict.get("phase_idx", phase_idx + 1),
                next_state_dict.get("rejection_pct", 0.0),
                next_state_dict.get("quality_score", 0.5),
                phase_count,
            )
            db.execute("""
                INSERT INTO rl_experience (state_json, action, reward, next_state_json, mission_id)
                VALUES (?, ?, ?, ?, ?)
            """, (state_key, action, reward, next_state_key, mission_id))
            db.commit()
            db.close()
        except Exception as e:
            log.debug(f"RL record_experience: {e}")

    def train(self, max_rows: int = 50_000) -> dict[str, Any]:
        """
        Batch Q-learning update from rl_experience table.
        Returns training stats.
        """
        try:
            from ..db.migrations import get_db
            db = get_db()
            rows = db.execute(
                "SELECT state_json, action, reward, next_state_json FROM rl_experience ORDER BY id DESC LIMIT ?",
                (max_rows,),
            ).fetchall()
            db.close()
        except Exception as e:
            log.warning(f"RL train: DB error {e}")
            return {"error": str(e)}

        updates = 0
        for row in rows:
            state_key = row["state_json"]
            action = row["action"]
            reward = float(row["reward"])
            next_key = row["next_state_json"]

            if state_key not in self._q:
                self._q[state_key] = {a: 0.0 for a in ACTIONS}
                self._visits[state_key] = {a: 0 for a in ACTIONS}

            # Q-learning update
            max_next_q = max(self._q.get(next_key, {a: 0.0 for a in ACTIONS}).values())
            current_q = self._q[state_key].get(action, 0.0)
            new_q = current_q + LEARNING_RATE * (reward + DISCOUNT_FACTOR * max_next_q - current_q)
            self._q[state_key][action] = new_q
            self._visits[state_key][action] = self._visits[state_key].get(action, 0) + 1
            updates += 1

        self._loaded = True
        log.info(f"RL train: {updates} transitions, {len(self._q)} states")
        return {
            "transitions": updates,
            "states": len(self._q),
            "actions": len(ACTIONS),
        }

    def stats(self) -> dict[str, Any]:
        """Return stats for /api/rl/policy/stats endpoint."""
        total_visits = sum(
            sum(v.values()) for v in self._visits.values()
        )
        state_count = len(self._q)
        avg_confidence = 0.0
        if self._q:
            confidences = []
            for q_row in self._q.values():
                best_q = max(q_row.values(), default=0.0)
                keep_q = q_row.get("keep", 0.0)
                adv = best_q - keep_q
                confidences.append(1.0 / (1.0 + math.exp(-5 * adv)))
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        # Action counts across all states
        action_counts: dict[str, int] = {a: 0 for a in ACTIONS}
        avg_rewards: dict[str, float] = {a: 0.0 for a in ACTIONS}
        action_q_sums: dict[str, float] = {a: 0.0 for a in ACTIONS}
        for q_row in self._q.values():
            for a, q in q_row.items():
                action_counts[a] = action_counts.get(a, 0) + 1
                action_q_sums[a] = action_q_sums.get(a, 0.0) + q
        for a in ACTIONS:
            cnt = action_counts.get(a, 0)
            avg_rewards[a] = round(action_q_sums.get(a, 0.0) / max(1, cnt), 4)

        return {
            "decisions": self._total_decisions,
            "experience_count": total_visits,
            "coverage": round(min(1.0, state_count / max(1, state_count + 10)), 3),
            "avg_confidence": round(avg_confidence, 3),
            "state_count": state_count,
            "action_counts": {a: v for a, v in action_counts.items() if v > 0},
            "avg_rewards": avg_rewards,
        }

    # ── Internals ────────────────────────────────────────────────────────────

    def _load_or_train(self) -> None:
        """Load Q-table from DB experience on first use."""
        try:
            result = self.train(max_rows=100_000)
            log.info(f"RL: loaded Q-table — {result}")
        except Exception as e:
            log.debug(f"RL _load_or_train: {e}")
        self._loaded = True

    def _log_decision(
        self,
        mission_id: str,
        phase_id: str,
        state_key: str,
        action: str,
        q_value: float,
        confidence: float,
    ) -> None:
        """Log RL decision for observability."""
        log.info(
            f"RL decision: mission={mission_id} phase={phase_id} "
            f"action={action} conf={confidence:.2f} q={q_value:.4f}"
        )


# ── Singleton ─────────────────────────────────────────────────────────────────
_policy: RLPolicy | None = None


def get_rl_policy() -> RLPolicy:
    global _policy
    if _policy is None:
        _policy = RLPolicy()
    return _policy
