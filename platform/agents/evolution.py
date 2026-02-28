"""
Genetic Algorithm engine — evolves workflow templates using historical mission data.

Nightly runner: reads agent_scores + mission outcomes, evolves workflow genomes,
saves top-3 proposals to evolution_proposals table for human review.

Usage:
    from platform.agents.evolution import GAEngine
    engine = GAEngine()
    best = engine.evolve("tma-maintenance", generations=30)

    from platform.agents.evolution_scheduler import start_evolution_scheduler
    await start_evolution_scheduler()   # call once at app startup
"""
from __future__ import annotations

import copy
import json
import math
import random
import logging
import asyncio
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

# ── GA Hyperparameters ────────────────────────────────────────────────────────
POPULATION_SIZE = 40
MAX_GENERATIONS = 30
MUTATION_RATE = 0.15
TOURNAMENT_K = 3
ELITE_COUNT = 2            # top genomes carried unchanged to next gen
MIN_FITNESS_DELTA = 0.001  # stop if no improvement for 5 generations

VALID_PATTERNS = [
    "sequential", "hierarchical", "parallel", "network",
    "debate", "loop", "mapreduce", "pipeline",
    "scatter_gather", "blackboard", "router",
]
VALID_GATES = ["always", "no_veto", "majority", "all_approved", "any_approved"]


# ── Genome ────────────────────────────────────────────────────────────────────

@dataclass
class PhaseSpec:
    phase_id: str
    name: str
    pattern_id: str
    agents: list[str]
    gate: str = "always"

    def to_dict(self) -> dict:
        return {
            "phase_id": self.phase_id,
            "name": self.name,
            "pattern_id": self.pattern_id,
            "agents": self.agents,
            "gate": self.gate,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PhaseSpec":
        return cls(
            phase_id=d["phase_id"],
            name=d.get("name", d["phase_id"]),
            pattern_id=d.get("pattern_id", "sequential"),
            agents=d.get("agents", []),
            gate=d.get("gate", "always"),
        )


@dataclass
class Genome:
    wf_id: str
    phases: list[PhaseSpec]
    fitness: float = 0.0

    def to_dict(self) -> dict:
        return {
            "wf_id": self.wf_id,
            "phases": [p.to_dict() for p in self.phases],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Genome":
        return cls(
            wf_id=d["wf_id"],
            phases=[PhaseSpec.from_dict(p) for p in d["phases"]],
        )


# ── GA Engine ─────────────────────────────────────────────────────────────────

class GAEngine:
    """Genetic algorithm to evolve workflow templates."""

    def __init__(self) -> None:
        self._wf_store = None
        self._agent_store = None
        self._simulator = None

    def _get_deps(self):
        if self._wf_store is None:
            from ..workflows.store import get_workflow_store
            from ..agents.store import get_agent_store
            from ..agents.simulator import MissionSimulator
            self._wf_store = get_workflow_store()
            self._agent_store = get_agent_store()
            self._simulator = MissionSimulator()

    # ── Public ────────────────────────────────────────────────────────────────

    def evolve(self, wf_id: str, generations: int = MAX_GENERATIONS) -> Genome:
        """
        Evolve workflow wf_id for `generations` generations.
        Saves top-3 proposals to DB and returns the best genome.
        """
        self._get_deps()
        wf = self._wf_store.get(wf_id)
        if not wf:
            raise ValueError(f"Workflow {wf_id!r} not found")

        all_agent_ids = [a.id for a in self._agent_store.list_all()]
        population = self._init_population(wf, all_agent_ids)

        best_fitness = 0.0
        stagnation = 0
        fitness_history: list[dict] = []

        for gen in range(generations):
            # Evaluate fitness
            for genome in population:
                if genome.fitness == 0.0:
                    genome.fitness = self._fitness(genome)

            population.sort(key=lambda g: g.fitness, reverse=True)
            gen_best = population[0].fitness
            gen_avg = sum(g.fitness for g in population) / len(population)
            fitness_history.append({"gen": gen, "max_fitness": round(gen_best, 4), "avg_fitness": round(gen_avg, 4)})

            log.debug(f"GA [{wf_id}] gen={gen} best={gen_best:.4f} avg={gen_avg:.4f}")

            if gen_best - best_fitness < MIN_FITNESS_DELTA:
                stagnation += 1
                if stagnation >= 5:
                    log.info(f"GA [{wf_id}] converged at gen={gen}")
                    break
            else:
                best_fitness = gen_best
                stagnation = 0

            # Next generation
            next_gen = population[:ELITE_COUNT]  # elitism
            while len(next_gen) < POPULATION_SIZE:
                parent_a = self._tournament_select(population)
                parent_b = self._tournament_select(population)
                child = self._crossover(parent_a, parent_b)
                child = self._mutate(child, all_agent_ids)
                child.fitness = 0.0  # reset for re-evaluation
                next_gen.append(child)
            population = next_gen

        # Final evaluation
        for genome in population:
            if genome.fitness == 0.0:
                genome.fitness = self._fitness(genome)
        population.sort(key=lambda g: g.fitness, reverse=True)

        # Save top-3 proposals
        top3 = population[:3]
        run_id = self._save_run(wf_id, generations, population[0].fitness, fitness_history)
        for rank, genome in enumerate(top3):
            self._save_proposal(genome, wf_id, generations, run_id)

        log.info(f"GA [{wf_id}] done: best_fitness={population[0].fitness:.4f}")
        return population[0]

    def evolve_all(self, generations: int = MAX_GENERATIONS) -> dict[str, float]:
        """Evolve all workflows. Returns {wf_id: best_fitness}."""
        self._get_deps()
        results: dict[str, float] = {}
        for wf in self._wf_store.list_all():
            try:
                best = self.evolve(wf.id, generations)
                results[wf.id] = best.fitness
            except Exception as e:
                log.warning(f"GA evolve_all: skip {wf.id} — {e}")
        return results

    # ── Fitness ───────────────────────────────────────────────────────────────

    def _fitness(self, genome: Genome) -> float:
        """
        Fitness = success_rate × avg_quality_score.
        First tries historical agent_scores data, falls back to simulator.
        """
        historical = self._historical_fitness(genome)
        if historical is not None:
            return historical
        # cold start: simulate
        return self._simulator.simulate_genome(
            [p.to_dict() for p in genome.phases], n=30
        )

    def _historical_fitness(self, genome: Genome) -> float | None:
        """Query agent_scores for agents in genome. Returns None if too little data."""
        try:
            from ..db.migrations import get_db
            db = get_db()
            all_agents = set()
            for phase in genome.phases:
                all_agents.update(phase.agents)
            if not all_agents:
                return None
            placeholders = ",".join("?" * len(all_agents))
            rows = db.execute(
                f"SELECT agent_id, accepted, rejected, iterations, quality_score "
                f"FROM agent_scores WHERE agent_id IN ({placeholders}) AND iterations >= 3",
                list(all_agents),
            ).fetchall()
            db.close()
            if not rows:
                return None
            total_accepted = sum(r["accepted"] for r in rows)
            total_iterations = sum(r["iterations"] for r in rows)
            if total_iterations < 5:
                return None
            success_rate = total_accepted / max(1, total_iterations)
            avg_quality = sum(r["quality_score"] for r in rows) / len(rows)
            # Apply pattern + gate modifiers on top of historical baseline
            pattern_bonus = 0.0
            for phase in genome.phases:
                from ..agents.simulator import PATTERN_MODS, GATE_MODS
                pattern_bonus += PATTERN_MODS.get(phase.pattern_id, 0.0)
                g_qual, _ = GATE_MODS.get(phase.gate, (0.0, 0.0))
                pattern_bonus += g_qual * 0.3
            pattern_bonus /= max(1, len(genome.phases))
            return min(0.99, (success_rate + pattern_bonus * 0.5) * avg_quality)
        except Exception as e:
            log.debug(f"GA historical_fitness: {e}")
            return None

    # ── Genetic operators ────────────────────────────────────────────────────

    def _init_population(self, wf, all_agent_ids: list[str]) -> list[Genome]:
        """Initialize population: 1 clone of base + POPULATION_SIZE-1 mutations."""
        base = self._wf_to_genome(wf)
        population = [copy.deepcopy(base)]
        for _ in range(POPULATION_SIZE - 1):
            mutant = copy.deepcopy(base)
            # Apply multiple mutations for initial diversity
            for _ in range(random.randint(1, 3)):
                mutant = self._mutate(mutant, all_agent_ids)
            population.append(mutant)
        return population

    def _wf_to_genome(self, wf) -> Genome:
        """Convert workflow object to Genome."""
        phases = []
        for phase in wf.phases:
            cfg = phase.config or {}
            agents = cfg.get("agent_ids", cfg.get("agents", []))
            phases.append(PhaseSpec(
                phase_id=phase.id,
                name=phase.name,
                pattern_id=phase.pattern_id or "sequential",
                agents=list(agents),
                gate=getattr(phase, "gate", "always") or "always",
            ))
        return Genome(wf_id=wf.id, phases=phases)

    def _tournament_select(self, population: list[Genome]) -> Genome:
        """Tournament selection: pick k random candidates, return best."""
        candidates = random.sample(population, min(TOURNAMENT_K, len(population)))
        return max(candidates, key=lambda g: g.fitness)

    def _crossover(self, a: Genome, b: Genome) -> Genome:
        """1-point crossover on phase list."""
        if len(a.phases) < 2 or len(b.phases) < 2:
            return copy.deepcopy(a)
        cut = random.randint(1, min(len(a.phases), len(b.phases)) - 1)
        new_phases = copy.deepcopy(a.phases[:cut]) + copy.deepcopy(b.phases[cut:])
        # Deduplicate phase_ids (keep first occurrence)
        seen: set[str] = set()
        deduped: list[PhaseSpec] = []
        for p in new_phases:
            if p.phase_id not in seen:
                deduped.append(p)
                seen.add(p.phase_id)
        if not deduped:
            return copy.deepcopy(a)
        return Genome(wf_id=a.wf_id, phases=deduped)

    def _mutate(self, genome: Genome, all_agent_ids: list[str]) -> Genome:
        """Apply random mutations to genome phases."""
        genome = copy.deepcopy(genome)
        for phase in genome.phases:
            if not genome.phases:
                break
            r = random.random()
            if r < MUTATION_RATE:
                # Swap pattern_id
                phase.pattern_id = random.choice(VALID_PATTERNS)
            if r < MUTATION_RATE * 0.7:
                # Swap gate
                phase.gate = random.choice(VALID_GATES)
            if r < MUTATION_RATE * 0.5 and phase.agents:
                # Swap one agent
                idx = random.randrange(len(phase.agents))
                phase.agents[idx] = random.choice(all_agent_ids)
            if r < MUTATION_RATE * 0.2 and len(phase.agents) > 1:
                # Remove one agent
                phase.agents.pop(random.randrange(len(phase.agents)))
            if r < MUTATION_RATE * 0.1 and all_agent_ids:
                # Add one agent
                candidate = random.choice(all_agent_ids)
                if candidate not in phase.agents:
                    phase.agents.append(candidate)
        return genome

    # ── DB persistence ───────────────────────────────────────────────────────

    def _save_run(self, wf_id: str, generations: int, best_fitness: float, history: list) -> str:
        """Save GA run metadata to evolution_runs table."""
        import uuid
        run_id = str(uuid.uuid4())[:8]
        try:
            from ..db.migrations import get_db
            db = get_db()
            db.execute("""
                INSERT INTO evolution_runs (id, wf_id, generations, best_fitness, fitness_history_json)
                VALUES (?, ?, ?, ?, ?)
            """, (run_id, wf_id, generations, best_fitness, json.dumps(history)))
            db.commit()
            db.close()
        except Exception as e:
            log.warning(f"GA save_run: {e}")
        return run_id

    def _save_proposal(self, genome: Genome, base_wf_id: str, generation: int, run_id: str) -> None:
        """Save evolved genome as evolution proposal. Auto-approves if fitness delta > threshold."""
        import uuid, os
        proposal_id = str(uuid.uuid4())[:8]
        try:
            from ..db.migrations import get_db
            db = get_db()

            # Auto-approve if fitness exceeds base by GA_AUTO_APPROVE_DELTA (default 10%)
            delta_threshold = float(os.environ.get("GA_AUTO_APPROVE_DELTA", "0.10"))
            base_fitness = self._get_base_fitness(base_wf_id, db)
            auto_approve = (
                base_fitness is not None
                and genome.fitness >= base_fitness * (1 + delta_threshold)
                and genome.fitness > 0.5
            )
            status = "approved" if auto_approve else "pending"

            db.execute("""
                INSERT INTO evolution_proposals
                    (id, base_wf_id, genome_json, fitness, generation, run_id, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (proposal_id, base_wf_id, json.dumps(genome.to_dict()), genome.fitness, generation, run_id, status))
            db.commit()
            db.close()
            if auto_approve:
                log.info(f"GA proposal {proposal_id} AUTO-APPROVED fitness={genome.fitness:.4f} (base={base_fitness:.4f} +{delta_threshold*100:.0f}%)")
            else:
                log.info(f"GA proposal saved: {proposal_id} fitness={genome.fitness:.4f} status={status}")
        except Exception as e:
            log.warning(f"GA save_proposal: {e}")

    def _get_base_fitness(self, wf_id: str, db) -> float | None:
        """Get best historical fitness for a workflow (from previous approved proposals).

        Returns None only if truly unknown. On first run (no approved proposals),
        falls back to simulator; if simulator unavailable, returns 0.0 so any
        positive-fitness genome can be auto-approved (bootstrap mode).
        """
        try:
            row = db.execute(
                "SELECT MAX(fitness) FROM evolution_proposals WHERE base_wf_id=? AND status='approved'",
                (wf_id,)
            ).fetchone()
            if row and row[0] is not None:
                return float(row[0])
            # Fall back to simulator baseline
            if self._simulator and self._wf_store.get(wf_id):
                try:
                    return self._simulator.simulate_genome(
                        [p.to_dict() for p in self._wf_to_genome(self._wf_store.get(wf_id)).phases],
                        n=10
                    )
                except Exception:
                    pass
            # Bootstrap mode: no history, no simulator → approve anything fitness > 0
            return 0.0
        except Exception:
            return 0.0
