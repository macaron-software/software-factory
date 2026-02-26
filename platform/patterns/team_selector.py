"""
TeamSelector — Darwin fitness-based agent selection for patterns.

Selects the best agent for a (pattern, technology, phase_type) context using
Thompson Sampling over Beta(wins+1, losses+1) distributions. Supports:
  - Warmup: random selection while runs < WARMUP_MIN
  - Similarity fallback: angular_16 data re-used for angular_17 cold start
  - Soft retirement: fitness < RETIRE_THRESHOLD after RETIRE_MIN_RUNS → weight × 0.1
  - A/B shadow test detection (callers can query should_ab_test())
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger(__name__)

WARMUP_MIN = 5
RETIRE_THRESHOLD = 20.0
RETIRE_MIN_RUNS = 10
AB_TEST_DELTA = 10.0  # trigger A/B when fitness scores within this delta
AB_TEST_PROBABILITY = 0.10  # 10% random shadow tests
RECENCY_WEIGHT = 1.5  # recent missions weight multiplier (last 20% of runs)


def _import_db():
    from ..db.migrations import get_db
    return get_db()


# ---------------------------------------------------------------------------
# Fitness helpers
# ---------------------------------------------------------------------------

def compute_fitness(
    wins: int,
    losses: int,
    runs: int,
    avg_iterations: float,
    weight_multiplier: float = 1.0,
) -> float:
    """Multi-dimensional fitness score (0–100)."""
    if runs == 0:
        return 0.0

    acceptance_rate = wins / runs * 100 if runs > 0 else 0.0
    iteration_penalty = max(0, (avg_iterations - 1.0) * 5.0)
    production_score = max(0, acceptance_rate - iteration_penalty)

    collaboration_bonus = min(10.0, runs * 0.5)
    coherence_score = acceptance_rate * 0.8

    raw = (
        production_score * 0.35
        + coherence_score * 0.25
        + collaboration_bonus * 0.25
        + max(0, 100 - iteration_penalty * 2) * 0.15
    )

    return min(100.0, raw * weight_multiplier)


def _tech_family(technology: str) -> str:
    """Return technology family prefix for similarity fallback.
    E.g. 'angular_19' → 'angular', 'python_fastapi' → 'python'.
    """
    if "_" in technology:
        return technology.split("_")[0]
    return technology


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _get_candidates(db, skill: str, pattern_id: str, technology: str, phase_type: str) -> list[dict]:
    """Return all non-retired agent rows matching skill + pattern + tech + phase."""
    rows = db.execute("""
        SELECT tf.*, a.id as aid
        FROM team_fitness tf
        JOIN agents a ON a.id = tf.agent_id
        WHERE tf.pattern_id = ?
          AND tf.technology = ?
          AND tf.phase_type = ?
          AND tf.retired = 0
        ORDER BY tf.fitness_score DESC
    """, (pattern_id, technology, phase_type)).fetchall()

    # Filter by skill: agent must have the skill in their skills_json or role
    result = []
    for row in rows:
        a_skills = db.execute(
            "SELECT skills_json, role FROM agents WHERE id = ?", (row["agent_id"],)
        ).fetchone()
        if a_skills:
            import json
            skills = json.loads(a_skills["skills_json"] or "[]")
            role = (a_skills["role"] or "").lower()
            if skill in skills or skill in role:
                result.append(dict(row))
    return result


def _get_agents_with_skill(db, skill: str) -> list[str]:
    """All agent IDs that have a given skill."""
    import json
    rows = db.execute("SELECT id, skills_json, role FROM agents WHERE is_builtin = 1 OR id IS NOT NULL").fetchall()
    result = []
    for row in rows:
        skills = json.loads(row["skills_json"] or "[]")
        role = (row["role"] or "").lower()
        if skill in skills or skill in role:
            result.append(row["id"])
    return result


def _upsert_team_fitness(db, agent_id: str, pattern_id: str, technology: str, phase_type: str):
    """Ensure a team_fitness row exists (warmup state)."""
    db.execute("""
        INSERT OR IGNORE INTO team_fitness
            (agent_id, pattern_id, technology, phase_type, fitness_score, runs, wins, losses)
        VALUES (?, ?, ?, ?, 0.0, 0, 0, 0)
    """, (agent_id, pattern_id, technology, phase_type))


def record_selection(
    db,
    mission_id: Optional[str],
    workflow_id: Optional[str],
    agent_id: str,
    pattern_id: str,
    technology: str,
    phase_type: str,
    mode: str,
    thompson_score: Optional[float],
):
    db.execute("""
        INSERT INTO team_selections
            (mission_id, workflow_id, agent_id, pattern_id, technology, phase_type,
             selection_mode, thompson_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (mission_id, workflow_id, agent_id, pattern_id, technology, phase_type,
          mode, thompson_score))
    db.commit()


def update_team_fitness(
    db,
    agent_id: str,
    pattern_id: str,
    technology: str,
    phase_type: str,
    won: bool,
    iterations: int = 1,
):
    """Update fitness after a mission completes."""
    _upsert_team_fitness(db, agent_id, pattern_id, technology, phase_type)
    row = db.execute("""
        SELECT runs, wins, losses, avg_iterations, weight_multiplier
        FROM team_fitness
        WHERE agent_id = ? AND pattern_id = ? AND technology = ? AND phase_type = ?
    """, (agent_id, pattern_id, technology, phase_type)).fetchone()

    if not row:
        return

    runs = row["runs"] + 1
    wins = row["wins"] + (1 if won else 0)
    losses = row["losses"] + (0 if won else 1)
    avg_iter = (row["avg_iterations"] * row["runs"] + iterations) / runs
    weight = row["weight_multiplier"]

    fitness = compute_fitness(wins, losses, runs, avg_iter, weight)

    # Auto soft-retire check
    retired = 0
    retired_at = None
    if fitness < RETIRE_THRESHOLD and runs >= RETIRE_MIN_RUNS and weight >= 1.0:
        weight = 0.1
        log.info("TeamSelector: soft-retiring %s+%s (%s/%s) — fitness %.1f",
                 agent_id, pattern_id, technology, phase_type, fitness)

    db.execute("""
        UPDATE team_fitness
        SET runs = ?, wins = ?, losses = ?, avg_iterations = ?,
            fitness_score = ?, weight_multiplier = ?, last_updated = ?
        WHERE agent_id = ? AND pattern_id = ? AND technology = ? AND phase_type = ?
    """, (runs, wins, losses, avg_iter, fitness, weight,
          datetime.now(timezone.utc).isoformat(),
          agent_id, pattern_id, technology, phase_type))
    db.commit()

    # Daily history snapshot (idempotent)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    db.execute("""
        INSERT OR REPLACE INTO team_fitness_history
            (agent_id, pattern_id, technology, phase_type, snapshot_date, fitness_score, runs)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (agent_id, pattern_id, technology, phase_type, today, fitness, runs))
    db.commit()


# ---------------------------------------------------------------------------
# Thompson Sampling
# ---------------------------------------------------------------------------

def _thompson_sample(candidates: list[dict]) -> tuple[dict, float]:
    """Pick best candidate using Thompson Sampling (Beta distribution)."""
    import random
    best = None
    best_score = -1.0

    for c in candidates:
        wins = max(0, c.get("wins", 0))
        losses = max(0, c.get("losses", 0))
        weight = c.get("weight_multiplier", 1.0)

        # Beta(wins+1, losses+1) — +1 is the Bayesian prior (uniform)
        sample = random.betavariate(wins + 1, losses + 1) * weight * 100

        if sample > best_score:
            best_score = sample
            best = c

    return best, best_score


# ---------------------------------------------------------------------------
# Main selector
# ---------------------------------------------------------------------------

class TeamSelector:
    """
    Fitness-based agent selector for patterns using Thompson Sampling.

    Usage:
        agent_id = TeamSelector.select(
            skill="developer",
            pattern_id="tdd-cycle",
            task_domain="code",
            technology="angular_16",
            phase_type="migration",
            mission_id=mission_id,
            workflow_id=workflow_id,
        )
    """

    @staticmethod
    def select(
        skill: str,
        pattern_id: str,
        task_domain: str = "code",
        technology: str = "generic",
        phase_type: str = "generic",
        mission_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
    ) -> Optional[str]:
        """Select best agent for (skill, pattern, technology, phase_type).

        Returns agent_id or None (caller falls back to explicit agent_id or random).
        """
        try:
            db = _import_db()
            try:
                return TeamSelector._select_internal(
                    db, skill, pattern_id, task_domain,
                    technology, phase_type, mission_id, workflow_id,
                )
            finally:
                db.close()
        except Exception as e:
            log.warning("TeamSelector.select error: %s", e)
            return None

    @staticmethod
    def _select_internal(
        db, skill, pattern_id, task_domain,
        technology, phase_type, mission_id, workflow_id,
    ) -> Optional[str]:
        candidates = _get_candidates(db, skill, pattern_id, technology, phase_type)

        # Similarity fallback: try tech family, then domain generic
        if not candidates and technology != "generic":
            family = _tech_family(technology)
            if family != technology:
                candidates = _get_candidates(db, skill, pattern_id, family + "_*", phase_type)
        if not candidates and technology != "generic":
            candidates = _get_candidates(db, skill, pattern_id, "generic", phase_type)
        if not candidates and phase_type != "generic":
            candidates = _get_candidates(db, skill, pattern_id, "generic", "generic")

        # Cold start: no fitness data yet — pick random from skill-qualified agents
        if not candidates:
            agent_ids = _get_agents_with_skill(db, skill)
            if not agent_ids:
                log.debug("TeamSelector: no agents with skill '%s'", skill)
                return None

            # Seed warmup rows for all candidates
            for aid in agent_ids:
                _upsert_team_fitness(db, aid, pattern_id, technology, phase_type)
            db.commit()

            chosen = random.choice(agent_ids)
            record_selection(db, mission_id, workflow_id, chosen, pattern_id,
                             technology, phase_type, "warmup", None)
            log.debug("TeamSelector: warmup random for skill='%s' tech='%s' phase='%s' → %s",
                      skill, technology, phase_type, chosen)
            return chosen

        # Warmup: if any candidate has < WARMUP_MIN runs, force random among them
        warmup_candidates = [c for c in candidates if c["runs"] < WARMUP_MIN]
        if warmup_candidates:
            chosen_row = random.choice(warmup_candidates)
            chosen = chosen_row["agent_id"]
            record_selection(db, mission_id, workflow_id, chosen, pattern_id,
                             technology, phase_type, "warmup", None)
            return chosen

        # Thompson Sampling
        best, score = _thompson_sample(candidates)
        chosen = best["agent_id"]

        record_selection(db, mission_id, workflow_id, chosen, pattern_id,
                         technology, phase_type, "fitness", round(score, 3))
        log.debug("TeamSelector: fitness-based → %s (score=%.2f, tech=%s, phase=%s)",
                  chosen, score, technology, phase_type)
        return chosen

    @staticmethod
    def should_ab_test(
        skill: str,
        pattern_id: str,
        technology: str = "generic",
        phase_type: str = "generic",
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """Returns (should_test, team_a_agent, team_b_agent).

        Triggers A/B if two top teams have fitness delta < AB_TEST_DELTA,
        or probabilistically with AB_TEST_PROBABILITY.
        """
        try:
            db = _import_db()
            try:
                candidates = _get_candidates(db, skill, pattern_id, technology, phase_type)
                if len(candidates) < 2:
                    return False, None, None

                a, b = candidates[0], candidates[1]

                # Probabilistic trigger
                if random.random() < AB_TEST_PROBABILITY:
                    return True, a["agent_id"], b["agent_id"]

                # Close-fitness trigger
                if abs(a["fitness_score"] - b["fitness_score"]) < AB_TEST_DELTA and a["runs"] >= WARMUP_MIN:
                    return True, a["agent_id"], b["agent_id"]

                return False, None, None
            finally:
                db.close()
        except Exception as e:
            log.warning("TeamSelector.should_ab_test error: %s", e)
            return False, None, None

    @staticmethod
    def get_leaderboard(
        technology: str = "generic",
        phase_type: str = "generic",
        limit: int = 20,
    ) -> list[dict]:
        """Return ranked team list for a (technology, phase_type) context."""
        try:
            db = _import_db()
            try:
                rows = db.execute("""
                    SELECT tf.*,
                           a.name as agent_name, a.role as agent_role,
                           CASE
                             WHEN tf.runs >= 5 AND tf.fitness_score >= 80 THEN 'champion'
                             WHEN tf.runs >= 3 AND tf.fitness_score >= 60 THEN 'rising'
                             WHEN tf.retired = 1 THEN 'retired'
                             WHEN tf.runs >= 10 AND tf.fitness_score < 40 THEN 'declining'
                             ELSE 'active'
                           END as badge
                    FROM team_fitness tf
                    JOIN agents a ON a.id = tf.agent_id
                    WHERE tf.technology = ? AND tf.phase_type = ?
                    ORDER BY tf.fitness_score DESC
                    LIMIT ?
                """, (technology, phase_type, limit)).fetchall()
                return [dict(r) for r in rows]
            finally:
                db.close()
        except Exception as e:
            log.warning("TeamSelector.get_leaderboard error: %s", e)
            return []


# ---------------------------------------------------------------------------
# Infer technology + phase_type from workflow/mission context
# ---------------------------------------------------------------------------

_WORKFLOW_TECH_MAP = {
    "full-stack-feature": ("generic", "new_feature"),
    "tdd-cycle": ("generic", "new_feature"),
    "bugfix": ("generic", "bugfix"),
    "bug-fix": ("generic", "bugfix"),
    "refactoring": ("generic", "refactoring"),
    "migration": ("generic", "migration"),
    "security-audit": ("generic", "audit"),
    "architecture-design": ("generic", "design"),
    "api-design": ("generic", "design"),
    "documentation": ("generic", "docs"),
    "code-review": ("generic", "review"),
}

_TECH_KEYWORDS = [
    "angular", "react", "vue", "svelte",
    "python", "fastapi", "django", "flask",
    "java", "spring", "kotlin",
    "typescript", "javascript", "node",
    "go", "rust", "cpp", "dotnet",
    "terraform", "kubernetes", "docker",
    "sql", "postgres", "mongo",
]

_PHASE_KEYWORDS = {
    "migration": "migration",
    "upgrade": "migration",
    "refactor": "refactoring",
    "new feature": "new_feature",
    "feature": "new_feature",
    "bugfix": "bugfix",
    "bug": "bugfix",
    "fix": "bugfix",
    "audit": "audit",
    "security": "audit",
    "design": "design",
    "architecture": "design",
    "documentation": "docs",
    "doc": "docs",
    "test": "testing",
    "review": "review",
}


def infer_context(workflow_id: str = "", title: str = "") -> tuple[str, str]:
    """Infer (technology, phase_type) from workflow_id and/or mission title.

    Returns ('generic', 'generic') if no match found.
    """
    combined = (workflow_id + " " + title).lower()

    # Phase type
    phase = "generic"
    for kw, pt in _PHASE_KEYWORDS.items():
        if kw in combined:
            phase = pt
            break

    # Try workflow map first
    for wf_key, (tech, p) in _WORKFLOW_TECH_MAP.items():
        if wf_key in combined:
            if phase == "generic":
                phase = p
            break

    # Technology
    tech = "generic"
    for kw in _TECH_KEYWORDS:
        if kw in combined:
            # Try to capture version: "angular 16" → "angular_16"
            import re
            m = re.search(rf"{kw}[\s_]?(\d+)", combined)
            if m:
                tech = f"{kw}_{m.group(1)}"
            else:
                tech = kw
            break

    return tech, phase
