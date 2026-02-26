"""
Thompson Sampling for LLM provider selection.

Uses Beta(accepted+1, rejected+1) sampling — same algorithm as agent selection.
"accepted" = successful call with quality_score >= threshold
"rejected"  = failed call OR quality_score below threshold

Usage:
    from .llm_thompson import llm_thompson_select, llm_thompson_record
    best_provider = llm_thompson_select(candidates)
    llm_thompson_record(provider, success=True, quality=0.8)

Table: llm_provider_scores (provider, accepted, rejected, total_calls, avg_quality, last_used)
"""
from __future__ import annotations

import logging
import math
import random
import time

log = logging.getLogger(__name__)

_DB_READY = False
QUALITY_THRESHOLD = 0.6   # min quality to count as "accepted"
MIN_VISITS = 5             # min calls before trusting Thompson over uniform


def _ensure_table() -> None:
    global _DB_READY
    if _DB_READY:
        return
    try:
        from ..db.migrations import get_db
        db = get_db()
        db.execute("""
            CREATE TABLE IF NOT EXISTS llm_provider_scores (
                provider TEXT PRIMARY KEY,
                accepted INTEGER DEFAULT 0,
                rejected INTEGER DEFAULT 0,
                total_calls INTEGER DEFAULT 0,
                avg_quality REAL DEFAULT 0.0,
                last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.commit()
        db.close()
        _DB_READY = True
    except Exception as e:
        log.debug(f"llm_thompson _ensure_table: {e}")


def _get_scores(providers: list[str]) -> dict[str, dict]:
    """Load Beta distribution params for given providers."""
    _ensure_table()
    try:
        from ..db.migrations import get_db
        db = get_db()
        rows = db.execute(
            "SELECT * FROM llm_provider_scores WHERE provider IN (%s)"
            % ",".join("?" * len(providers)),
            providers,
        ).fetchall()
        db.close()
        return {r["provider"]: dict(r) for r in rows}
    except Exception:
        return {}


def llm_thompson_select(candidates: list[str]) -> str:
    """
    Select the best provider using Thompson Sampling (Beta distributions).
    Returns provider name. Falls back to first candidate if insufficient data.
    """
    if not candidates:
        return ""
    if len(candidates) == 1:
        return candidates[0]

    scores = _get_scores(candidates)

    # Check if we have enough data to trust Thompson
    all_have_data = all(
        scores.get(p, {}).get("total_calls", 0) >= MIN_VISITS
        for p in candidates
    )
    if not all_have_data:
        # Exploration: return default order (first candidate)
        return candidates[0]

    # Sample from Beta distributions
    best_provider = candidates[0]
    best_sample = -1.0

    for p in candidates:
        s = scores.get(p, {})
        alpha = s.get("accepted", 0) + 1
        beta = s.get("rejected", 0) + 1
        # Sample via Gamma trick
        try:
            g1 = random.gammavariate(alpha, 1.0)
            g2 = random.gammavariate(beta, 1.0)
            sample = g1 / (g1 + g2) if (g1 + g2) > 0 else 0.5
        except Exception:
            sample = 0.5
        if sample > best_sample:
            best_sample = sample
            best_provider = p

    if best_provider != candidates[0]:
        log.info(f"LLM Thompson: selected {best_provider!r} (sample={best_sample:.3f}) over {candidates[0]!r}")
    return best_provider


def llm_thompson_record(provider: str, success: bool, quality: float = 0.0) -> None:
    """
    Record outcome for a provider call.
    success=True + quality >= QUALITY_THRESHOLD → accepted
    otherwise → rejected
    """
    _ensure_table()
    accepted = 1 if (success and quality >= QUALITY_THRESHOLD) else 0
    rejected = 0 if accepted else 1
    try:
        from ..db.migrations import get_db
        db = get_db()
        row = db.execute(
            "SELECT accepted, rejected, total_calls, avg_quality FROM llm_provider_scores WHERE provider=?",
            (provider,)
        ).fetchone()
        if row:
            new_total = row["total_calls"] + 1
            new_avg = (row["avg_quality"] * row["total_calls"] + quality) / new_total
            db.execute(
                "UPDATE llm_provider_scores SET accepted=accepted+?, rejected=rejected+?, "
                "total_calls=total_calls+1, avg_quality=?, last_used=CURRENT_TIMESTAMP "
                "WHERE provider=?",
                (accepted, rejected, round(new_avg, 4), provider)
            )
        else:
            db.execute(
                "INSERT INTO llm_provider_scores (provider, accepted, rejected, total_calls, avg_quality) "
                "VALUES (?, ?, ?, 1, ?)",
                (provider, accepted, rejected, quality)
            )
        db.commit()
        db.close()
    except Exception as e:
        log.debug(f"llm_thompson_record: {e}")


def llm_thompson_stats() -> list[dict]:
    """Return stats for all known providers."""
    _ensure_table()
    try:
        from ..db.migrations import get_db
        db = get_db()
        rows = db.execute(
            "SELECT * FROM llm_provider_scores ORDER BY avg_quality DESC"
        ).fetchall()
        db.close()
        result = []
        for r in rows:
            d = dict(r)
            total = d["total_calls"] or 1
            d["success_rate"] = round(d["accepted"] / total, 3)
            d["rejection_rate"] = round(d["rejected"] / total, 3)
            result.append(d)
        return result
    except Exception:
        return []
