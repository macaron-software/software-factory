"""
Mission Simulator — synthetic training data generator for GA + RL cold start.

Generates N simulated workflow runs with plausible phase outcomes based on
domain knowledge priors (pattern effectiveness, gate strictness, agent seniority).
Priors are auto-calibrated from real phase_outcomes when sufficient data exists.

Usage:
    from platform.agents.simulator import MissionSimulator
    sim = MissionSimulator()
    sim.run_all(n_runs_per_workflow=200)   # seed all workflows
    sim.run_workflow("tma-maintenance", n=300)
"""

from __future__ import annotations

import random
import math
import logging
from typing import Any

log = logging.getLogger(__name__)

# ── Priors (complexity-scaled; overridden by calibrate_pattern_mods()) ────────

# Pattern modifier: how much each pattern improves P(phase_success) over base.
# These are DEFAULT priors — calibrate_pattern_mods() overrides them with real data.
# Note: complex workflows amplify these; trivial workflows suppress them entirely.
PATTERN_MODS: dict[str, float] = {
    "parallel": 0.15,
    "hierarchical": 0.10,
    "sequential": 0.0,
    "network": 0.05,
    "router": 0.03,
    "debate": 0.08,
    "loop": -0.05,  # loop risks infinite retries
    "mapreduce": 0.07,
    "pipeline": 0.04,
    "scatter_gather": 0.06,
    "blackboard": 0.02,
    "swarm": 0.0,
}

# Whether PATTERN_MODS have been calibrated from real data this session
_CALIBRATED = False

# Gate modifier: gate strictness improves quality but costs duration
GATE_MODS: dict[str, tuple[float, float]] = {
    # (quality_bonus, duration_penalty)
    "all_approved": (0.08, 0.20),
    "majority": (0.05, 0.10),
    "no_veto": (0.05, 0.05),
    "always": (0.0, 0.0),
    "any_approved": (0.02, 0.05),
}

BASE_SUCCESS_RATE = 0.60  # baseline P(phase_success)
NOISE_SIGMA = 0.10  # gaussian noise std
QUALITY_BASE = 0.55  # baseline quality score
QUALITY_SIGMA = 0.12

# Complexity scaling: how much pattern bonuses apply per tier
_COMPLEXITY_SCALE = {
    "trivial": 0.0,  # 1-2 phase workflows: patterns irrelevant
    "simple": 0.4,  # tma, cicd, sast
    "medium": 0.7,  # feature, quality-improvement
    "complex": 1.0,  # product-lifecycle, ideation-to-prod
}


class MissionSimulator:
    """Generates synthetic training data for GA fitness + RL experience buffer."""

    def __init__(self) -> None:
        self._wf_store = None
        self._agent_store = None

    def _get_stores(self):
        if self._wf_store is None:
            from ..workflows.store import get_workflow_store
            from ..agents.store import get_agent_store

            self._wf_store = get_workflow_store()
            self._agent_store = get_agent_store()

    # ── Public API ──────────────────────────────────────────────────────────

    def calibrate_pattern_mods(self, min_rows: int = 30) -> dict[str, float]:
        """
        Override PATTERN_MODS with empirical averages from real phase_outcomes.
        Only updates patterns with enough data (min_rows per pattern).
        Returns the updated dict (patterns not yet calibrated keep prior values).
        """
        global PATTERN_MODS, _CALIBRATED
        try:
            from ..db.migrations import get_db

            db = get_db()
            rows = db.execute(
                """
                SELECT pattern_id,
                       AVG(success) as avg_success,
                       AVG(quality_score) as avg_quality,
                       COUNT(*) as n
                FROM phase_outcomes
                GROUP BY pattern_id
                HAVING COUNT(*) >= ?
            """,
                (min_rows,),
            ).fetchall()
            db.close()

            if not rows:
                log.debug(
                    "Simulator: no phase_outcomes for calibration yet, using priors"
                )
                return PATTERN_MODS

            # Compute global baseline from all data
            db2 = db  # already closed, re-fetch
            try:
                from ..db.migrations import get_db as _gdb

                db2 = _gdb()
                baseline_row = db2.execute(
                    "SELECT AVG(success), AVG(quality_score) FROM phase_outcomes"
                ).fetchone()
                db2.close()
                global_success = float(baseline_row[0] or BASE_SUCCESS_RATE)
            except Exception:
                global_success = BASE_SUCCESS_RATE

            calibrated = 0
            for r in rows:
                pat = r["pattern_id"] if hasattr(r, "__getitem__") else r[0]
                avg_s = float(r["avg_success"] if hasattr(r, "__getitem__") else r[1])
                n = int(r["n"] if hasattr(r, "__getitem__") else r[3])
                # Real modifier = empirical success delta vs global baseline
                real_mod = avg_s - global_success
                old = PATTERN_MODS.get(pat, 0.0)
                # Weighted blend: more data → trust empirical more
                weight = min(0.9, n / 500.0)  # 500+ rows = 90% empirical
                PATTERN_MODS[pat] = round((1 - weight) * old + weight * real_mod, 4)
                calibrated += 1

            _CALIBRATED = True
            log.info(
                f"Simulator: calibrated {calibrated} pattern mods from real data. "
                f"parallel={PATTERN_MODS.get('parallel', 0):.3f} "
                f"sequential={PATTERN_MODS.get('sequential', 0):.3f}"
            )
            return PATTERN_MODS
        except Exception as e:
            log.debug(f"Simulator calibrate_pattern_mods: {e}")
            return PATTERN_MODS

    def run_all(self, n_runs_per_workflow: int = 200) -> dict[str, int]:
        """Simulate n_runs_per_workflow for every known workflow. Returns {wf_id: rows_inserted}."""
        self._get_stores()
        workflows = self._wf_store.list_all()
        results: dict[str, int] = {}
        for wf in workflows:
            try:
                count = self.run_workflow(wf.id, n=n_runs_per_workflow)
                results[wf.id] = count
            except Exception as e:
                log.warning(f"Simulator: skip {wf.id} — {e}")
        log.info(
            f"Simulator: seeded {sum(results.values())} rows across {len(results)} workflows"
        )
        return results

    def run_workflow(self, wf_id: str, n: int = 200) -> int:
        """Simulate n runs for a single workflow, writing to agent_scores."""
        self._get_stores()
        wf = self._wf_store.get(wf_id)
        if not wf:
            raise ValueError(f"Workflow {wf_id!r} not found")

        all_agents = {a.id: a for a in self._agent_store.list_all()}
        rows_written = 0

        for run_idx in range(n):
            sim_epic_id = f"sim-{wf_id}-{run_idx:04d}"
            for phase in wf.phases:
                phase_result = self._simulate_phase(phase, all_agents, sim_epic_id)
                rows_written += self._write_phase_result(phase_result, sim_epic_id)

        return rows_written

    def simulate_mission_fast(self, mission_id: str) -> dict[str, str]:
        """Force all phases of a simulated mission to 'done'.

        Sets every phase status to 'done' directly in the mission store,
        bypassing actual agent execution.  Useful for testing pipelines
        and seeding progress data without running real LLM calls.

        Returns a dict mapping phase_id → new status.
        """
        try:
            from ..missions.store import PhaseStatus, get_mission_store
        except ImportError as exc:
            raise RuntimeError("Mission store not available") from exc

        ms = get_mission_store()
        mission = ms.get(mission_id)
        if not mission:
            raise ValueError(f"Mission {mission_id!r} not found")

        updated: dict[str, str] = {}
        for phase in mission.phases:
            phase.status = PhaseStatus.DONE
            updated[phase.phase_id] = "done"

        mission.status = "done"  # type: ignore[assignment]
        ms.update(mission)
        log.info(
            "simulate_mission_fast: mission %s — %d phases forced to done",
            mission_id,
            len(updated),
        )
        return updated

    def simulate_genome(
        self, genome: list[dict[str, Any]], n: int = 50, complexity: str = "simple"
    ) -> float:
        """
        Simulate n runs of a GA genome (list of PhaseSpec dicts) and return
        estimated fitness = avg(success_rate × quality_score).
        Called by GA engine for evolved offspring without real data.
        Pattern bonuses are scaled by complexity tier.
        """
        if not genome:
            return 0.0

        self._get_stores()
        all_agents = {a.id: a for a in self._agent_store.list_all()}
        fitnesses: list[float] = []

        for _ in range(n):
            phase_successes: list[float] = []
            phase_qualities: list[float] = []
            for phase_spec in genome:
                success, quality = self._simulate_phase_spec(
                    phase_spec, all_agents, complexity
                )
                phase_successes.append(success)
                phase_qualities.append(quality)
            # Fitness: geometric mean of phase successes × avg quality
            if phase_successes:
                run_success = math.prod(phase_successes) ** (1.0 / len(phase_successes))
                run_quality = sum(phase_qualities) / len(phase_qualities)
                fitnesses.append(run_success * run_quality)

        return sum(fitnesses) / len(fitnesses) if fitnesses else 0.0

    # ── Internals ──────────────────────────────────────────────────────────

    def _simulate_phase(self, phase, all_agents: dict, epic_id: str) -> dict:
        """Simulate one phase execution, return {agent_id: {accepted, rejected, quality}}."""
        cfg = phase.config or {}
        agents = cfg.get("agent_ids", cfg.get("agents", []))
        pattern_id = phase.pattern_id or "sequential"
        gate = getattr(phase, "gate", "always") or "always"

        results = {}
        for agent_id in agents:
            agent = all_agents.get(agent_id)
            seniority = self._agent_seniority(agent)
            p_success, quality = self._compute_outcome(
                pattern_id, gate, seniority, "simple"
            )
            accepted = 1 if random.random() < p_success else 0
            rejected = 1 - accepted
            results[agent_id] = {
                "accepted": accepted,
                "rejected": rejected,
                "quality_score": quality if accepted else quality * 0.6,
            }
        return results

    def _simulate_phase_spec(
        self, phase_spec: dict, all_agents: dict, complexity: str = "simple"
    ) -> tuple[float, float]:
        """Return (success_prob, quality) for a GA genome phase spec."""
        pattern_id = phase_spec.get("pattern_id", "sequential")
        gate = phase_spec.get("gate", "always")
        agents = phase_spec.get("agents", [])
        if not agents:
            return BASE_SUCCESS_RATE, QUALITY_BASE
        seniority = sum(self._agent_seniority(all_agents.get(a)) for a in agents) / len(
            agents
        )
        return self._compute_outcome(pattern_id, gate, seniority, complexity)

    def _compute_outcome(
        self, pattern_id: str, gate: str, seniority: float, complexity: str = "simple"
    ) -> tuple[float, float]:
        """Compute (p_success, quality_score) given priors + gaussian noise.
        Pattern mods are scaled by complexity tier — trivial workflows get 0 bonus.
        """
        scale = _COMPLEXITY_SCALE.get(complexity, 0.7)
        p_mod = PATTERN_MODS.get(pattern_id, 0.0) * scale
        g_qual, _g_dur = GATE_MODS.get(gate, (0.0, 0.0))
        # Seniority: rank 10=top → 1.0 bonus, rank 50=mid → 0, rank 90=low → -0.2
        seniority_bonus = max(-0.20, min(0.25, (50 - seniority) / 200.0))
        p_success = BASE_SUCCESS_RATE + p_mod + g_qual * 0.5 + seniority_bonus
        p_success = max(0.1, min(0.97, p_success + random.gauss(0, NOISE_SIGMA)))
        quality = QUALITY_BASE + g_qual + seniority_bonus * 1.5
        quality = max(0.05, min(0.99, quality + random.gauss(0, QUALITY_SIGMA)))
        return p_success, quality

    def _agent_seniority(self, agent) -> float:
        """Return hierarchy_rank (lower = more senior). Default 50 if unknown."""
        if agent is None:
            return 50.0
        return float(getattr(agent, "hierarchy_rank", 50) or 50)

    def _write_phase_result(self, phase_result: dict, epic_id: str) -> int:
        """Write simulated agent outcomes to agent_scores table."""
        try:
            from ..db.migrations import get_db

            db = get_db()
            count = 0
            for agent_id, r in phase_result.items():
                db.execute(
                    """
                    INSERT INTO agent_scores (agent_id, epic_id, accepted, rejected, iterations, quality_score)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(agent_id, epic_id) DO UPDATE SET
                        accepted = agent_scores.accepted + excluded.accepted,
                        rejected = agent_scores.rejected + excluded.rejected,
                        iterations = agent_scores.iterations + 1,
                        quality_score = (agent_scores.quality_score + excluded.quality_score) / 2.0
                """,
                    (
                        agent_id,
                        epic_id,
                        r["accepted"],
                        r["rejected"],
                        1,
                        r["quality_score"],
                    ),
                )
                count += 1
            db.commit()
            db.close()
            return count
        except Exception as e:
            log.warning(f"Simulator write error: {e}")
            return 0
