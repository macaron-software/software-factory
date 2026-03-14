"""
platform/ac/skill_thompson.py — Thompson Sampling for AC skill variant selection.

Each AC agent skill can have multiple prompt variants (v1, v2, ...).
Thompson Sampling (Beta distribution) picks the best-performing variant
for each new cycle, based on historical cycle scores.

Also supports cross-project (tier-level) learning as fallback when a
project has insufficient data for reliable selection.

Table: ac_skill_scores
  skill_id   TEXT    -- e.g. "ac-codex"
  variant    TEXT    -- e.g. "v1", "v2"
  project_id TEXT    -- or "__tier_simple" for shared pool
  wins       INTEGER -- cycles where cycle score improved after using this variant
  losses     INTEGER -- cycles where cycle score degraded or plateaued
  avg_score  REAL    -- running average cycle score when this variant was used
  updated_at TEXT
  PRIMARY KEY (skill_id, variant, project_id)
"""
# Ref: feat-quality

from __future__ import annotations

import logging
import random
import time
from typing import Optional

log = logging.getLogger(__name__)

MIN_VISITS_FOR_THOMPSON = 3  # minimum cycles before trusting Thompson over uniform
_TIER_SHARED_PREFIX = "__tier_"


def _get_db():
    try:
        from ..db.migrations import get_db

        return get_db()
    except Exception as e:
        log.warning("ac_skill_thompson: cannot get DB: %s", e)
        return None


def _ensure_table(conn) -> None:
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ac_skill_scores (
                skill_id   TEXT NOT NULL,
                variant    TEXT NOT NULL,
                project_id TEXT NOT NULL,
                wins       INTEGER DEFAULT 0,
                losses     INTEGER DEFAULT 0,
                avg_score  REAL DEFAULT 0.0,
                updated_at TEXT,
                PRIMARY KEY (skill_id, variant, project_id)
            )
        """)
    except Exception as e:
        log.debug("ac_skill_thompson ensure_table: %s", e)


def ac_skill_select_variant(
    skill_id: str,
    variants: list[str],
    project_id: str,
    tier: Optional[str] = None,
) -> str:
    """
    Select the best skill variant using Thompson Sampling.

    Falls back to tier-level shared pool if insufficient project-specific data.
    Falls back to random uniform if no data at all.

    Args:
        skill_id:   e.g. "ac-codex"
        variants:   e.g. ["v1", "v2"]
        project_id: e.g. "ac-hello-html"
        tier:       e.g. "simple" (for cross-project fallback)

    Returns:
        Selected variant string.
    """
    if not variants:
        return "v1"
    if len(variants) == 1:
        return variants[0]

    conn = _get_db()
    if conn is None:
        return random.choice(variants)

    _ensure_table(conn)

    def _load_scores(pool_id: str) -> dict[str, tuple[int, int]]:
        """Returns {variant: (wins, losses)}."""
        try:
            rows = conn.execute(
                "SELECT variant, wins, losses FROM ac_skill_scores WHERE skill_id=? AND project_id=?",
                (skill_id, pool_id),
            ).fetchall()
            return {r["variant"]: (r["wins"], r["losses"]) for r in rows}
        except Exception:
            return {}

    # Try project-specific data first
    scores = _load_scores(project_id)
    total_visits = sum(w + lo for w, lo in scores.values())

    # Fallback to tier-level pool if insufficient data
    if total_visits < MIN_VISITS_FOR_THOMPSON and tier:
        tier_pool = f"{_TIER_SHARED_PREFIX}{tier}"
        tier_scores = _load_scores(tier_pool)
        tier_visits = sum(w + lo for w, lo in tier_scores.values())
        if tier_visits >= MIN_VISITS_FOR_THOMPSON:
            scores = tier_scores
            log.debug(
                "ac_skill_thompson: using tier pool %s for %s/%s (project only %d visits)",
                tier_pool,
                skill_id,
                project_id,
                total_visits,
            )

    conn.close()

    # Thompson Sampling: draw Beta(wins+1, losses+1) for each variant
    best_variant = None
    best_sample = -1.0
    for v in variants:
        wins, losses = scores.get(v, (0, 0))
        # Beta distribution: alpha=wins+1, beta=losses+1
        sample = random.betavariate(wins + 1, losses + 1)
        if sample > best_sample:
            best_sample = sample
            best_variant = v

    selected = best_variant or random.choice(variants)
    log.debug(
        "ac_skill_thompson: selected %s=%s (sample=%.3f, scores=%s)",
        skill_id,
        selected,
        best_sample,
        scores,
    )
    return selected


def ac_skill_record(
    skill_id: str,
    variant: str,
    project_id: str,
    cycle_score: int,
    prev_cycle_score: Optional[int],
    tier: Optional[str] = None,
) -> None:
    """
    Record the outcome of using a skill variant in a cycle.

    A "win" is when the cycle score improved vs the previous cycle.
    A "loss" is when the score stayed the same or decreased.

    Also updates the tier-level shared pool for cross-project learning.
    """
    if prev_cycle_score is None:
        return  # can't judge without comparison

    improved = cycle_score > prev_cycle_score
    conn = _get_db()
    if conn is None:
        return

    _ensure_table(conn)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ")

    def _upsert(pool_id: str) -> None:
        try:
            conn.execute(
                """INSERT INTO ac_skill_scores (skill_id, variant, project_id, wins, losses, avg_score, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(skill_id, variant, project_id) DO UPDATE SET
                     wins = wins + ?,
                     losses = losses + ?,
                     avg_score = (avg_score * (wins + losses) + ?) / (wins + losses + 1),
                     updated_at = ?""",
                (
                    skill_id,
                    variant,
                    pool_id,
                    1 if improved else 0,
                    0 if improved else 1,
                    cycle_score,
                    now,
                    1 if improved else 0,
                    0 if improved else 1,
                    cycle_score,
                    now,
                ),
            )
        except Exception as e:
            log.debug("ac_skill_record upsert %s: %s", pool_id, e)

    _upsert(project_id)
    if tier:
        _upsert(f"{_TIER_SHARED_PREFIX}{tier}")

    try:
        conn.commit()
    except Exception:
        pass
    conn.close()

    log.debug(
        "ac_skill_record: %s/%s project=%s score=%d prev=%d → %s",
        skill_id,
        variant,
        project_id,
        cycle_score,
        prev_cycle_score,
        "win" if improved else "loss",
    )


def ac_skill_stats(skill_id: str, project_id: Optional[str] = None) -> list[dict]:
    """Return stats for a skill (all variants, optionally filtered by project)."""
    conn = _get_db()
    if conn is None:
        return []
    _ensure_table(conn)
    try:
        if project_id:
            rows = conn.execute(
                "SELECT * FROM ac_skill_scores WHERE skill_id=? AND project_id=? ORDER BY wins DESC",
                (skill_id, project_id),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM ac_skill_scores WHERE skill_id=? ORDER BY avg_score DESC",
                (skill_id,),
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        log.debug("ac_skill_stats: %s", e)
        return []
    finally:
        conn.close()
