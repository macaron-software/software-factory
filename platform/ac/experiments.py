"""
platform/ac/experiments.py — A/B experiment tracking and rollback decisions for AC cycles.

Each AC cycle can test ONE improvement (isolated variable control):
  - A variant of a skill prompt (e.g. ac-codex-v2 vs v1)
  - A pattern change (parallel vs sequential for TDD)
  - A threshold change (stricter adversarial criteria)

The coach decides at the end of each cycle whether to:
  - KEEP: score improved → record win, strengthen Thompson
  - ROLLBACK: score dropped > threshold → git revert, delete cycle, retry
  - CONTINUE: neutral result → accumulate data, Thompson decides next variant

Table: ac_experiments
  id              TEXT  PRIMARY KEY
  project_id      TEXT
  cycle_num       INTEGER    -- cycle when experiment started
  experiment_key  TEXT       -- what is being tested, e.g. "skill:ac-codex:variant"
  variant_a       TEXT       -- control (previous behavior)
  variant_b       TEXT       -- treatment (what we're testing)
  score_before    INTEGER    -- score of the cycle BEFORE the experiment
  score_a         INTEGER    -- score when using variant_a (baseline)
  score_b         INTEGER    -- score when using variant_b (treatment)
  winner          TEXT       -- "a" | "b" | "none" | NULL (still running)
  rolled_back     INTEGER    -- 1 if we git-reverted this cycle
  strategy_notes  TEXT       -- what the coach decided and why
  created_at      TEXT
  closed_at       TEXT
"""
# Ref: feat-quality

from __future__ import annotations

import logging
import time
import uuid
from typing import Optional

log = logging.getLogger(__name__)

ROLLBACK_THRESHOLD = 10  # score drop > 10pts → rollback


def _get_db():
    try:
        from ..db.migrations import get_db

        return get_db()
    except Exception as e:
        log.warning("ac_experiments: cannot get DB: %s", e)
        return None


def _ensure_table(conn) -> None:
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ac_experiments (
                id             TEXT PRIMARY KEY,
                project_id     TEXT NOT NULL,
                cycle_num      INTEGER NOT NULL,
                experiment_key TEXT NOT NULL,
                variant_a      TEXT,
                variant_b      TEXT,
                score_before   INTEGER DEFAULT 0,
                score_a        INTEGER,
                score_b        INTEGER,
                winner         TEXT,
                rolled_back    INTEGER DEFAULT 0,
                strategy_notes TEXT,
                created_at     TEXT,
                closed_at      TEXT
            )
        """)
        conn.commit()
    except Exception as e:
        log.debug("ac_experiments ensure_table: %s", e)


def record_experiment(
    project_id: str,
    cycle_num: int,
    experiment_key: str,
    variant_a: str,
    variant_b: str,
    score_before: int,
    strategy_notes: str = "",
) -> str:
    """
    Start recording a new A/B experiment for a cycle.
    Returns the experiment ID.
    """
    conn = _get_db()
    if not conn:
        return ""
    _ensure_table(conn)
    exp_id = str(uuid.uuid4())[:8]
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        conn.execute(
            "INSERT OR REPLACE INTO ac_experiments"
            " (id, project_id, cycle_num, experiment_key, variant_a, variant_b,"
            "  score_before, strategy_notes, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (
                exp_id,
                project_id,
                cycle_num,
                experiment_key,
                variant_a,
                variant_b,
                score_before,
                strategy_notes,
                now,
            ),
        )
        conn.commit()
        log.info(
            "ac_experiments: started %s for %s cycle %d (%s: %s→%s)",
            exp_id,
            project_id,
            cycle_num,
            experiment_key,
            variant_a,
            variant_b,
        )
        return exp_id
    except Exception as e:
        log.warning("ac_experiments record_experiment: %s", e)
        return ""


def get_active_experiment(project_id: str) -> Optional[dict]:
    """Return the most recent open experiment (winner=NULL) for a project."""
    conn = _get_db()
    if not conn:
        return None
    _ensure_table(conn)
    try:
        row = conn.execute(
            "SELECT * FROM ac_experiments"
            " WHERE project_id=? AND winner IS NULL"
            " ORDER BY created_at DESC LIMIT 1",
            (project_id,),
        ).fetchone()
        return dict(row) if row else None
    except Exception as e:
        log.warning("ac_experiments get_active: %s", e)
        return None


def close_experiment(
    exp_id: str,
    score_a: Optional[int],
    score_b: Optional[int],
    winner: str,
    strategy_notes: str = "",
    rolled_back: bool = False,
) -> None:
    """
    Close an experiment with its result.
    winner: "a" | "b" | "none"
    """
    conn = _get_db()
    if not conn:
        return
    _ensure_table(conn)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        conn.execute(
            "UPDATE ac_experiments SET"
            " score_a=?, score_b=?, winner=?, rolled_back=?, strategy_notes=?, closed_at=?"
            " WHERE id=?",
            (score_a, score_b, winner, int(rolled_back), strategy_notes, now, exp_id),
        )
        conn.commit()
        log.info(
            "ac_experiments: closed %s winner=%s rolled_back=%s",
            exp_id,
            winner,
            rolled_back,
        )
    except Exception as e:
        log.warning("ac_experiments close_experiment: %s", e)


def should_rollback(score_before: int, score_current: int) -> bool:
    """
    Return True if the score dropped enough to warrant a git revert.
    Threshold: ROLLBACK_THRESHOLD points drop.
    """
    return (score_before - score_current) > ROLLBACK_THRESHOLD


def get_experiment_history(project_id: str, limit: int = 10) -> list[dict]:
    """Return recent closed experiments for a project."""
    conn = _get_db()
    if not conn:
        return []
    _ensure_table(conn)
    try:
        rows = conn.execute(
            "SELECT * FROM ac_experiments WHERE project_id=? ORDER BY cycle_num DESC LIMIT ?",
            (project_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        log.warning("ac_experiments history: %s", e)
        return []
