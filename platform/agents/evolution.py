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
import random
import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

# ── GA Hyperparameters ────────────────────────────────────────────────────────
POPULATION_SIZE = 40
MAX_GENERATIONS = 30
MUTATION_RATE = 0.15
TOURNAMENT_K = 3
ELITE_COUNT = 2  # top genomes carried unchanged to next gen
MIN_FITNESS_DELTA = 0.001  # stop if no improvement for 5 generations

VALID_PATTERNS = [
    "sequential",
    "hierarchical",
    "parallel",
    "network",
    "debate",
    "loop",
    "mapreduce",
    "pipeline",
    "scatter_gather",
    "blackboard",
    "router",
]
VALID_GATES = ["always", "no_veto", "majority", "all_approved", "any_approved"]

# ── Workflow complexity tiers ─────────────────────────────────────────────────
# Determines max agents per phase and how much pattern bonuses are worth
COMPLEXITY_TIERS = {
    "trivial": {
        "max_phases": 2,
        "max_agents": 1,
        "pattern_scale": 0.0,
    },  # pr-review, single-fix
    "simple": {
        "max_phases": 4,
        "max_agents": 2,
        "pattern_scale": 0.4,
    },  # tma, cicd, sast
    "medium": {
        "max_phases": 7,
        "max_agents": 3,
        "pattern_scale": 0.7,
    },  # feature, quality
    "complex": {
        "max_phases": 99,
        "max_agents": 5,
        "pattern_scale": 1.0,
    },  # product-lifecycle, ideation-to-prod
}

# Agent domain categories (derived from role keywords)
_DOMAIN_KEYWORDS = {
    "tech": [
        "developer",
        "engineer",
        "architect",
        "backend",
        "frontend",
        "fullstack",
        "devops",
        "platform",
        "api",
    ],
    "product": ["product", "po", "cpo", "owner", "business", "analyst", "ba"],
    "ux": ["ux", "ui", "designer", "design", "accessibility", "user"],
    "security": ["security", "ciso", "sast", "pentest", "compliance", "audit"],
    "qa": ["qa", "test", "tester", "quality", "validator"],
    "strategy": ["cto", "ceo", "strategy", "strategic", "executive", "director"],
    "data": ["data", "ml", "ai", "analytics", "scientist", "pipeline"],
    "ops": ["ops", "sre", "deploy", "infra", "cloud", "monitoring", "incident"],
}


def _agent_domain(agent) -> str:
    """Infer the domain of an agent from its role string."""
    if agent is None:
        return "unknown"
    role = (getattr(agent, "role", "") or "").lower()
    name = (getattr(agent, "name", "") or "").lower()
    combined = role + " " + name
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            return domain
    return "generic"


def _workflow_complexity(wf) -> str:
    """Classify a workflow into a complexity tier based on structural signals.

    Signals used:
    - phase_count: primary driver
    - domain_diversity: number of distinct phase types
    - has_strategic_phase: ideation/committee/architecture → bumps up
    """
    if wf is None:
        return "simple"
    phases = getattr(wf, "phases", []) or []
    n = len(phases)

    # Phase count → base tier
    if n <= 2:
        tier = "trivial"
    elif n <= 4:
        tier = "simple"
    elif n <= 7:
        tier = "medium"
    else:
        tier = "complex"

    # Boost tier if workflow contains strategic/multi-domain phases
    phase_names = " ".join((p.name or "").lower() for p in phases)
    strategic_signals = [
        "idéation",
        "ideation",
        "architecture",
        "committee",
        "comité",
        "stratégique",
        "strategic",
        "design system",
        "pi planning",
        "product design",
        "constitution",
    ]
    if any(sig in phase_names for sig in strategic_signals):
        # Bump up one tier
        tiers = ["trivial", "simple", "medium", "complex"]
        idx = tiers.index(tier)
        tier = tiers[min(idx + 1, 3)]

    return tier


# ── Genome ────────────────────────────────────────────────────────────────────


@dataclass
class PhaseSpec:
    phase_id: str
    name: str
    pattern_id: str
    agents: list[str]
    gate: str = "always"
    task_hints: dict[str, str] = field(default_factory=dict)  # {agent_id: focus_area}

    def to_dict(self) -> dict:
        return {
            "phase_id": self.phase_id,
            "name": self.name,
            "pattern_id": self.pattern_id,
            "agents": self.agents,
            "gate": self.gate,
            "task_hints": self.task_hints,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PhaseSpec":
        return cls(
            phase_id=d["phase_id"],
            name=d.get("name", d["phase_id"]),
            pattern_id=d.get("pattern_id", "sequential"),
            agents=d.get("agents", []),
            gate=d.get("gate", "always"),
            task_hints=d.get("task_hints", {}),
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
        self._agent_cache: dict[str, Any] = {}  # id → agent object

    def _get_deps(self):
        if self._wf_store is None:
            from ..workflows.store import get_workflow_store
            from ..agents.store import get_agent_store
            from ..agents.simulator import MissionSimulator

            self._wf_store = get_workflow_store()
            self._agent_store = get_agent_store()
            self._simulator = MissionSimulator()
            # Cache all agents for domain lookups
            for a in self._agent_store.list_all():
                self._agent_cache[a.id] = a

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

        # Calibrate simulator priors from real data before evolving
        try:
            self._simulator.calibrate_pattern_mods()
        except Exception as e:
            log.debug(f"GA calibrate_pattern_mods: {e}")

        complexity = _workflow_complexity(wf)
        all_agent_ids = [a.id for a in self._agent_store.list_all()]
        population = self._init_population(wf, all_agent_ids, complexity)

        best_fitness = 0.0
        stagnation = 0
        fitness_history: list[dict] = []

        for gen in range(generations):
            # Evaluate fitness
            for genome in population:
                if genome.fitness == 0.0:
                    genome.fitness = self._fitness(genome, complexity)

            population.sort(key=lambda g: g.fitness, reverse=True)
            gen_best = population[0].fitness
            gen_avg = sum(g.fitness for g in population) / len(population)
            fitness_history.append(
                {
                    "gen": gen,
                    "max_fitness": round(gen_best, 4),
                    "avg_fitness": round(gen_avg, 4),
                }
            )

            log.debug(
                f"GA [{wf_id}] gen={gen} best={gen_best:.4f} avg={gen_avg:.4f} tier={complexity}"
            )

            if gen_best - best_fitness < MIN_FITNESS_DELTA:
                stagnation += 1
                if stagnation >= 5:
                    log.info(f"GA [{wf_id}] converged at gen={gen} tier={complexity}")
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
                child = self._mutate(child, all_agent_ids, complexity)
                child.fitness = 0.0  # reset for re-evaluation
                next_gen.append(child)
            population = next_gen

        # Final evaluation
        for genome in population:
            if genome.fitness == 0.0:
                genome.fitness = self._fitness(genome, complexity)
        population.sort(key=lambda g: g.fitness, reverse=True)

        # Save top-3 proposals
        top3 = population[:3]
        run_id = self._save_run(
            wf_id, generations, population[0].fitness, fitness_history
        )
        for rank, genome in enumerate(top3):
            self._save_proposal(genome, wf_id, generations, run_id)

        log.info(
            f"GA [{wf_id}] done: best_fitness={population[0].fitness:.4f} tier={complexity}"
        )
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

    def _fitness(self, genome: Genome, complexity: str = "simple") -> float:
        """
        Fitness = success_rate × avg_quality × diversity_bonus − redundancy_penalty − budget_penalty.
        Priority: real phase_outcomes > historical agent_scores > simulator.
        All measures are scoped to the same complexity tier to avoid TMA/PR data
        polluting complex workflow optimization.
        """
        historical = self._historical_fitness(genome, complexity)
        if historical is not None:
            return historical
        # cold start: simulate with complexity-aware scaling
        raw = self._simulator.simulate_genome(
            [p.to_dict() for p in genome.phases], n=30, complexity=complexity
        )
        return raw

    def _historical_fitness(
        self, genome: Genome, complexity: str = "simple"
    ) -> float | None:
        """
        Query real phase_outcomes (preferred) then agent_scores as fallback.
        Scoped to complexity tier so trivial workflows don't pollute complex ones.
        Applies: redundancy penalty, diversity bonus, phase budget penalty.
        """
        try:
            from ..db.migrations import get_db

            db = get_db()

            # ── 1. Try real phase_outcomes scoped to this workflow + complexity tier ──
            po_rows = db.execute(
                """SELECT pattern_id, team_size, success, quality_score, rejection_count
                   FROM phase_outcomes
                   WHERE workflow_id = ? AND complexity_tier = ?
                   ORDER BY created_at DESC LIMIT 200""",
                (genome.wf_id, complexity),
            ).fetchall()

            if po_rows and len(po_rows) >= 5:
                total = len(po_rows)
                successes = sum(r["success"] for r in po_rows)
                success_rate = successes / total
                avg_quality = sum(r["quality_score"] for r in po_rows) / total
                base_fitness = success_rate * avg_quality
                return self._apply_team_modifiers(base_fitness, genome, complexity, db)

            # ── 2. Fallback: agent_scores (not scoped to complexity) ──
            all_agents = set()
            for phase in genome.phases:
                all_agents.update(phase.agents)
            if not all_agents:
                db.close()
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
            # Apply pattern + gate modifiers (complexity-scaled)
            pattern_bonus = self._pattern_bonus(genome, complexity)
            base_fitness = min(0.99, (success_rate + pattern_bonus * 0.5) * avg_quality)
            return self._apply_team_modifiers(base_fitness, genome, complexity)
        except Exception as e:
            log.debug(f"GA historical_fitness: {e}")
            return None

    def _pattern_bonus(self, genome: Genome, complexity: str) -> float:
        """Compute complexity-scaled pattern+gate bonus."""
        from ..agents.simulator import PATTERN_MODS, GATE_MODS

        scale = COMPLEXITY_TIERS.get(complexity, {}).get("pattern_scale", 0.7)
        bonus = 0.0
        for phase in genome.phases:
            bonus += PATTERN_MODS.get(phase.pattern_id, 0.0) * scale
            g_qual, _ = GATE_MODS.get(phase.gate, (0.0, 0.0))
            bonus += g_qual * 0.3
        return bonus / max(1, len(genome.phases))

    def _apply_team_modifiers(
        self, base_fitness: float, genome: Genome, complexity: str, db=None
    ) -> float:
        """Apply redundancy penalty, diversity bonus, budget penalty, chemistry bonus."""
        max_agents = COMPLEXITY_TIERS.get(complexity, {}).get("max_agents", 3)
        score = base_fitness

        # Collect all agents across phases
        all_agents_in_genome = []
        for phase in genome.phases:
            all_agents_in_genome.extend(phase.agents)

        # ── Diversity bonus: reward teams that cover distinct domains ──
        domains = [
            _agent_domain(self._agent_cache.get(a)) for a in all_agents_in_genome
        ]
        unique_domains = {d for d in domains if d not in ("unknown", "generic")}
        diversity_bonus = min(0.12, len(unique_domains) * 0.03)

        # ── Redundancy penalty: punish duplicate roles in same phase ──
        redundancy_penalty = 0.0
        for phase in genome.phases:
            phase_domains = [
                _agent_domain(self._agent_cache.get(a)) for a in phase.agents
            ]
            dupes = len(phase_domains) - len(set(phase_domains))
            redundancy_penalty += dupes * 0.06

        # ── Budget penalty: penalize teams exceeding complexity tier's max ──
        budget_penalty = 0.0
        for phase in genome.phases:
            excess = max(0, len(phase.agents) - max_agents)
            budget_penalty += excess * 0.10

        # ── Chemistry bonus from agent_pair_scores ──
        chemistry_bonus = 0.0
        if db is not None:
            try:
                for phase in genome.phases:
                    agents = phase.agents
                    for i in range(len(agents)):
                        for j in range(i + 1, len(agents)):
                            a, b = sorted([agents[i], agents[j]])
                            row = db.execute(
                                """SELECT joint_successes, co_appearances FROM agent_pair_scores
                                   WHERE agent_a=? AND agent_b=?""",
                                (a, b),
                            ).fetchone()
                            if row and row["co_appearances"] >= 3:
                                pair_rate = (
                                    row["joint_successes"] / row["co_appearances"]
                                )
                                chemistry_bonus += (
                                    pair_rate - 0.6
                                ) * 0.04  # baseline 60%
            except Exception:
                pass

        score = (
            score
            + diversity_bonus
            - redundancy_penalty
            - budget_penalty
            + chemistry_bonus
        )
        return max(0.01, min(0.99, score))

    # ── Genetic operators ────────────────────────────────────────────────────

    def _init_population(
        self, wf, all_agent_ids: list[str], complexity: str = "simple"
    ) -> list[Genome]:
        """Initialize population: 1 clone of base + POPULATION_SIZE-1 mutations."""
        base = self._wf_to_genome(wf)
        population = [copy.deepcopy(base)]
        for _ in range(POPULATION_SIZE - 1):
            mutant = copy.deepcopy(base)
            # Apply multiple mutations for initial diversity
            for _ in range(random.randint(1, 3)):
                mutant = self._mutate(mutant, all_agent_ids, complexity)
            population.append(mutant)
        return population

    def _wf_to_genome(self, wf) -> Genome:
        """Convert workflow object to Genome."""
        phases = []
        for phase in wf.phases:
            cfg = phase.config or {}
            agents = cfg.get("agent_ids", cfg.get("agents", []))
            phases.append(
                PhaseSpec(
                    phase_id=phase.id,
                    name=phase.name,
                    pattern_id=phase.pattern_id or "sequential",
                    agents=list(agents),
                    gate=getattr(phase, "gate", "always") or "always",
                    task_hints={},
                )
            )
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

    def _mutate(
        self, genome: Genome, all_agent_ids: list[str], complexity: str = "simple"
    ) -> Genome:
        """Apply random mutations to genome phases, respecting complexity tier budget."""
        genome = copy.deepcopy(genome)
        max_agents = COMPLEXITY_TIERS.get(complexity, {}).get("max_agents", 3)

        # Domain-indexed agent lookup for smarter agent swaps
        domain_agents: dict[str, list[str]] = {}
        for aid in all_agent_ids:
            d = _agent_domain(self._agent_cache.get(aid))
            domain_agents.setdefault(d, []).append(aid)

        for phase in genome.phases:
            if not genome.phases:
                break
            r = random.random()
            if r < MUTATION_RATE:
                # Swap pattern_id — for trivial/simple, avoid expensive patterns
                if complexity in ("trivial", "simple"):
                    simple_patterns = ["sequential", "hierarchical", "loop"]
                    phase.pattern_id = random.choice(simple_patterns)
                else:
                    phase.pattern_id = random.choice(VALID_PATTERNS)
            if r < MUTATION_RATE * 0.7:
                # Swap gate
                phase.gate = random.choice(VALID_GATES)
            if r < MUTATION_RATE * 0.5 and phase.agents:
                # Smart agent swap: replace with agent from same or complementary domain
                idx = random.randrange(len(phase.agents))
                current_domains = {
                    _agent_domain(self._agent_cache.get(a)) for a in phase.agents
                }
                # Prefer agent from an underrepresented domain
                missing_domains = [
                    d for d in _DOMAIN_KEYWORDS if d not in current_domains
                ]
                if (
                    missing_domains
                    and complexity in ("medium", "complex")
                    and random.random() < 0.4
                ):
                    target_domain = random.choice(missing_domains)
                    candidates = domain_agents.get(target_domain, all_agent_ids)
                    phase.agents[idx] = (
                        random.choice(candidates)
                        if candidates
                        else random.choice(all_agent_ids)
                    )
                else:
                    phase.agents[idx] = random.choice(all_agent_ids)
            if r < MUTATION_RATE * 0.2 and len(phase.agents) > 1:
                # Remove agent — prefer removing duplicate domains
                agent_domains = [
                    _agent_domain(self._agent_cache.get(a)) for a in phase.agents
                ]
                dupes = [
                    i for i, d in enumerate(agent_domains) if agent_domains.count(d) > 1
                ]
                if dupes:
                    phase.agents.pop(random.choice(dupes))
                else:
                    phase.agents.pop(random.randrange(len(phase.agents)))
            if (
                r < MUTATION_RATE * 0.1
                and all_agent_ids
                and len(phase.agents) < max_agents
            ):
                # Add agent (respects complexity budget)
                candidate = random.choice(all_agent_ids)
                if candidate not in phase.agents:
                    phase.agents.append(candidate)
            # Mutate task hints (small chance)
            if r < MUTATION_RATE * 0.05 and phase.agents:
                agent = random.choice(phase.agents)
                domain = _agent_domain(self._agent_cache.get(agent))
                if domain not in ("unknown", "generic"):
                    phase.task_hints[agent] = (
                        f"Focus on {domain} aspects relevant to this phase"
                    )
        return genome

    # ── DB persistence ───────────────────────────────────────────────────────

    def _save_run(
        self, wf_id: str, generations: int, best_fitness: float, history: list
    ) -> str:
        """Save GA run metadata to evolution_runs table."""
        import uuid

        run_id = str(uuid.uuid4())[:8]
        try:
            from ..db.migrations import get_db

            db = get_db()
            db.execute(
                """
                INSERT INTO evolution_runs (id, wf_id, generations, best_fitness, fitness_history_json)
                VALUES (?, ?, ?, ?, ?)
            """,
                (run_id, wf_id, generations, best_fitness, json.dumps(history)),
            )
            db.commit()
            db.close()
        except Exception as e:
            log.warning(f"GA save_run: {e}")
        return run_id

    def _save_proposal(
        self, genome: Genome, base_wf_id: str, generation: int, run_id: str
    ) -> None:
        """Save evolved genome as evolution proposal. Auto-approves if fitness delta > threshold."""
        import uuid
        import os

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

            db.execute(
                """
                INSERT INTO evolution_proposals
                    (id, base_wf_id, genome_json, fitness, generation, run_id, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    proposal_id,
                    base_wf_id,
                    json.dumps(genome.to_dict()),
                    genome.fitness,
                    generation,
                    run_id,
                    status,
                ),
            )
            db.commit()
            db.close()
            if auto_approve:
                log.info(
                    f"GA proposal {proposal_id} AUTO-APPROVED fitness={genome.fitness:.4f} (base={base_fitness:.4f} +{delta_threshold * 100:.0f}%)"
                )
            else:
                log.info(
                    f"GA proposal saved: {proposal_id} fitness={genome.fitness:.4f} status={status}"
                )
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
                (wf_id,),
            ).fetchone()
            if row and row[0] is not None:
                return float(row[0])
            # Fall back to simulator baseline
            if self._simulator and self._wf_store.get(wf_id):
                try:
                    return self._simulator.simulate_genome(
                        [
                            p.to_dict()
                            for p in self._wf_to_genome(
                                self._wf_store.get(wf_id)
                            ).phases
                        ],
                        n=10,
                    )
                except Exception:
                    pass
            # Bootstrap mode: no history, no simulator → approve anything fitness > 0
            return 0.0
        except Exception:
            return 0.0
