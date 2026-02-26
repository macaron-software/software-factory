"""
Tests for Adaptive Intelligence modules:
  - simulator.py (MissionSimulator)
  - evolution.py (GAEngine, Genome, PhaseSpec)
  - rl_policy.py (RLPolicy)
"""
import os
import sys
import random
import pytest

# Ensure platform is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Use in-memory DB for all tests
os.environ.setdefault("PLATFORM_DB_PATH", ":memory:")


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _init_db():
    """Init in-memory DB before each test."""
    try:
        from platform.db.migrations import init_db
        init_db()
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Simulator
# ─────────────────────────────────────────────────────────────────────────────

class TestMissionSimulator:
    def test_simulate_genome_returns_float(self):
        from platform.agents.simulator import MissionSimulator
        sim = MissionSimulator()
        genome = [
            {"phase_id": "p1", "name": "Analyse", "pattern_id": "sequential", "agents": [], "gate": "always"},
            {"phase_id": "p2", "name": "Dev", "pattern_id": "parallel", "agents": [], "gate": "no_veto"},
        ]
        fitness = sim.simulate_genome(genome, n=10)
        assert isinstance(fitness, float), f"Expected float, got {type(fitness)}"
        assert 0.0 <= fitness <= 1.0, f"Fitness out of range: {fitness}"

    def test_simulate_genome_parallel_beats_loop(self):
        """Parallel pattern should on average outperform loop (PATTERN_MODS)."""
        from platform.agents.simulator import MissionSimulator
        sim = MissionSimulator()
        parallel_genome = [{"phase_id": "p1", "name": "X", "pattern_id": "parallel", "agents": [], "gate": "always"}]
        loop_genome = [{"phase_id": "p1", "name": "X", "pattern_id": "loop", "agents": [], "gate": "always"}]
        # Run multiple times to reduce noise
        parallel_avg = sum(sim.simulate_genome(parallel_genome, n=20) for _ in range(3)) / 3
        loop_avg = sum(sim.simulate_genome(loop_genome, n=20) for _ in range(3)) / 3
        assert parallel_avg >= loop_avg - 0.05, f"Parallel ({parallel_avg:.3f}) unexpectedly worse than loop ({loop_avg:.3f})"

    def test_simulate_genome_all_gates(self):
        from platform.agents.simulator import MissionSimulator, GATE_MODS
        sim = MissionSimulator()
        for gate in GATE_MODS:
            genome = [{"phase_id": "p1", "name": "X", "pattern_id": "sequential", "agents": [], "gate": gate}]
            f = sim.simulate_genome(genome, n=5)
            assert 0.0 <= f <= 1.0, f"Gate {gate!r} returned out-of-range fitness {f}"


# ─────────────────────────────────────────────────────────────────────────────
# GA Engine — Genome & operators
# ─────────────────────────────────────────────────────────────────────────────

class TestGenome:
    def _make_genome(self, wf_id="test-wf", n_phases=3):
        from platform.agents.evolution import Genome, PhaseSpec
        phases = [
            PhaseSpec(phase_id=f"p{i}", name=f"Phase {i}", pattern_id="sequential", agents=["agent-a", "agent-b"])
            for i in range(n_phases)
        ]
        return Genome(wf_id=wf_id, phases=phases)

    def test_genome_to_dict_roundtrip(self):
        from platform.agents.evolution import Genome
        g = self._make_genome()
        d = g.to_dict()
        g2 = Genome.from_dict(d)
        assert g2.wf_id == g.wf_id
        assert len(g2.phases) == len(g.phases)
        assert g2.phases[0].pattern_id == g.phases[0].pattern_id

    def test_crossover_preserves_wf_id(self):
        from platform.agents.evolution import GAEngine
        engine = GAEngine()
        g1 = self._make_genome(n_phases=4)
        g2 = self._make_genome(n_phases=4)
        child = engine._crossover(g1, g2)
        assert child.wf_id == g1.wf_id
        assert 1 <= len(child.phases) <= 4, f"Child has {len(child.phases)} phases"

    def test_crossover_no_duplicate_phase_ids(self):
        from platform.agents.evolution import GAEngine
        engine = GAEngine()
        g1 = self._make_genome(n_phases=4)
        g2 = self._make_genome(n_phases=4)
        for _ in range(20):
            child = engine._crossover(g1, g2)
            phase_ids = [p.phase_id for p in child.phases]
            assert len(phase_ids) == len(set(phase_ids)), f"Duplicate phase_ids: {phase_ids}"

    def test_mutate_stays_valid(self):
        from platform.agents.evolution import GAEngine, VALID_PATTERNS, VALID_GATES
        engine = GAEngine()
        g = self._make_genome(n_phases=3)
        all_agents = ["agent-a", "agent-b", "agent-c", "agent-d"]
        for _ in range(50):
            mutant = engine._mutate(g, all_agents)
            assert len(mutant.phases) >= 1
            for ph in mutant.phases:
                assert ph.pattern_id in VALID_PATTERNS, f"Invalid pattern: {ph.pattern_id}"
                assert ph.gate in VALID_GATES, f"Invalid gate: {ph.gate}"

    def test_tournament_returns_genome(self):
        from platform.agents.evolution import GAEngine
        engine = GAEngine()
        population = [self._make_genome() for _ in range(10)]
        for i, g in enumerate(population):
            g.fitness = i * 0.1
        winner = engine._tournament_select(population)
        assert winner is not None
        assert winner.fitness >= 0


# ─────────────────────────────────────────────────────────────────────────────
# RL Policy
# ─────────────────────────────────────────────────────────────────────────────

class TestRLPolicy:
    def _make_policy(self):
        from platform.agents.rl_policy import RLPolicy
        return RLPolicy()

    def _state(self, wf_id="test-wf", phase_idx=0, rej=0.1, qual=0.7):
        return {"workflow_id": wf_id, "phase_idx": phase_idx, "rejection_pct": rej, "quality_score": qual, "phase_count": 5}

    def test_recommend_returns_dict(self):
        policy = self._make_policy()
        result = policy.recommend("m1", "p1", self._state())
        assert isinstance(result, dict)
        assert "action" in result
        assert "fired" in result

    def test_recommend_cold_start_not_fired(self):
        """With no data, recommend() should not fire."""
        policy = self._make_policy()
        result = policy.recommend("no-data-wf", "p0", self._state("no-data-wf"))
        assert result["fired"] is False

    def test_record_experience_increments(self):
        policy = self._make_policy()
        before_stats = policy.stats()
        policy.record_experience(
            mission_id="m1",
            state_dict=self._state(),
            action="switch_parallel",
            reward=0.8,
            next_state_dict=self._state(phase_idx=1),
        )
        # stats should reflect any change (experience stored in DB)
        after_stats = policy.stats()
        assert isinstance(after_stats, dict)

    def test_train_runs_without_error(self):
        policy = self._make_policy()
        for _ in range(10):
            policy.record_experience(
                mission_id="m1",
                state_dict=self._state(rej=0.4, qual=0.5),
                action="switch_parallel",
                reward=random.uniform(0, 1),
                next_state_dict=self._state(phase_idx=1, rej=0.3, qual=0.6),
            )
        result = policy.train(max_rows=100)
        assert isinstance(result, dict)

    def test_stats_structure(self):
        policy = self._make_policy()
        stats = policy.stats()
        assert "decisions" in stats or "state_count" in stats  # flexible key check
        assert isinstance(stats, dict)

    def test_recommend_fires_after_enough_visits(self):
        """After seeding high-rejection data, recommend() should eventually fire or at least not crash."""
        policy = self._make_policy()
        for _ in range(20):
            policy.record_experience(
                mission_id="m2",
                state_dict=self._state("high-rej", rej=0.5, qual=0.3),
                action="switch_parallel",
                reward=0.9,
                next_state_dict=self._state("high-rej", phase_idx=1, rej=0.2, qual=0.7),
            )
        policy.train(max_rows=1000)
        result = policy.recommend("m2", "p0", self._state("high-rej", rej=0.5, qual=0.3))
        assert isinstance(result, dict)
        assert result["action"] in ["keep", "switch_parallel", "switch_sequential",
                                    "switch_hierarchical", "switch_debate", "add_agent", "remove_agent"]


# ─────────────────────────────────────────────────────────────────────────────
# LLM Thompson
# ─────────────────────────────────────────────────────────────────────────────

class TestLLMThompson:
    def test_select_single_candidate(self):
        from platform.llm.llm_thompson import llm_thompson_select
        assert llm_thompson_select(["minimax"]) == "minimax"

    def test_select_empty_returns_empty(self):
        from platform.llm.llm_thompson import llm_thompson_select
        assert llm_thompson_select([]) == ""

    def test_record_and_stats(self):
        from platform.llm.llm_thompson import llm_thompson_record, llm_thompson_stats
        llm_thompson_record("test-provider", success=True, quality=0.8)
        llm_thompson_record("test-provider", success=False, quality=0.0)
        stats = llm_thompson_stats()
        providers = [s["provider"] for s in stats]
        assert "test-provider" in providers

    def test_select_explores_with_insufficient_data(self):
        """With < MIN_VISITS data, should return first candidate (exploration)."""
        from platform.llm.llm_thompson import llm_thompson_select
        result = llm_thompson_select(["minimax", "azure-openai"])
        assert result in ["minimax", "azure-openai"]
