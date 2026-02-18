"""Memory Seeder — auto-populate memory from project files + platform knowledge.

Called at startup to ensure the memory wiki is never empty.
Seeds both project-level and global-level memories.
"""
from __future__ import annotations

import logging
from pathlib import Path

from .manager import get_memory_manager
from .project_files import load_project_memory, MEMORY_FILES

logger = logging.getLogger(__name__)

# Platform-wide knowledge to seed into global memory
_GLOBAL_SEEDS = [
    # Architecture
    ("architecture", "stack", "FastAPI + HTMX + SSE + SQLite (WAL) + Jinja2 templates", 0.9),
    ("architecture", "patterns", "8 workflow patterns: Parallel, Sequential, Loop, Router, Aggregator, Hierarchical, Network, Human-in-loop", 0.9),
    ("architecture", "llm-providers", "Multi-provider: Azure OpenAI → MiniMax M2.5 → GLM-4.7 (fallback chain)", 0.9),
    ("architecture", "a2a-protocol", "11 message types: REQUEST, RESPONSE, DELEGATE, VETO, APPROVE, INFORM, NEGOTIATE, ESCALATE, ASK, DECIDE, STATUS", 0.9),
    ("architecture", "memory-layers", "4 layers: Session (ephemeral) → Pattern (workflow) → Project (persistent) → Global (cross-project)", 0.9),
    # Process
    ("process", "safe-hierarchy", "Portfolio → ART (Agile Release Train) → Team. 5 hierarchy ranks: 0=CEO, 10=Director, 20=Lead, 30=Senior, 40=Mid, 50=Junior", 0.85),
    ("process", "veto-system", "3 niveaux: ABSOLUTE (security, compliance — no override), STRONG (architecture — escalation possible), ADVISORY (suggestion — can be overridden)", 0.85),
    ("process", "dora-metrics", "4 DORA metrics tracked: Deployment Frequency, Lead Time for Changes, Change Failure Rate, MTTR", 0.85),
    ("process", "wsjf-formula", "WSJF = Cost of Delay / Job Duration. CoD = Business Value + Time Criticality + Risk Reduction. Higher WSJF = higher priority", 0.9),
    ("process", "brain-phases", "Phase 1: Features (vision) → Phase 2: Fixes (bugs/security) → Phase 3: Refactor (clean code). No refactor until fixes deployed.", 0.85),
    # Team
    ("team", "agent-count", "45+ agents across 5 SAFe levels: Strategic (DSI, CTO, CPO), Portfolio (managers), Program (RTE, SM), Team (dev, QA, DevOps, Security)", 0.8),
    ("team", "adversarial-review", "Multi-vendor cognitive diversity: Code critic (MiniMax), Security critic (GLM), Architecture critic (Opus). Same LLM cannot evaluate its own output.", 0.9),
    # Vision
    ("vision", "platform-purpose", "Macaron Agent Platform: emulate a full DSI (Direction des Systèmes d'Information) with autonomous AI agents collaborating on real software projects", 0.95),
    ("vision", "differentiation", "Real agentic orchestration ≠ workflow automation. Agents debate, veto, negotiate, delegate — not just if/then boxes with LLM wrappers", 0.9),
    # Conventions
    ("convention", "zero-skip", "NEVER skip tests, checks, or quality gates. FIX > SKIP. Always.", 0.95),
    ("convention", "tdd-first", "Red-Green-Refactor. Tests before code. Coverage 80%+. Complexity < 15 cyclomatic.", 0.9),
    ("convention", "fractal-decomposition", "L1: Split into 3 concerns (FEATURE → GUARDS → FAILURES). L2: KISS atomic (IMPL → TEST → VERIFY)", 0.85),
    ("convention", "lean-values", "Quality > Speed, Feedback rapide, Éliminer waste, Respect des personnes, Amélioration continue, Flux continu", 0.9),
]


def seed_project_memories():
    """Seed project-level memories from project files (VISION.md, SPECS.md, etc.)."""
    from ..projects.manager import get_project_store

    mem = get_memory_manager()
    store = get_project_store()
    projects = store.list_all()
    seeded = 0

    for proj in projects:
        if not proj.path or not Path(proj.path).is_dir():
            continue

        # Check if already seeded (skip if project already has memories)
        existing = mem.project_get(proj.id, limit=1)
        if existing:
            continue

        # Load project files
        pm = load_project_memory(proj.id, proj.path)
        for pf in pm.files:
            # Determine category from filename
            category = _file_to_category(pf.path)
            # Store truncated content as memory
            value = pf.content[:2000] if len(pf.content) > 2000 else pf.content
            mem.project_store(
                project_id=proj.id,
                key=pf.label,
                value=value,
                category=category,
                source="auto-seed",
                confidence=0.7,
            )
            seeded += 1

        # Also store vision if available
        if proj.vision and not any(pf.path.lower().startswith("vision") for pf in pm.files):
            mem.project_store(
                project_id=proj.id,
                key="Project Vision",
                value=proj.vision[:2000],
                category="vision",
                source="auto-seed",
                confidence=0.8,
            )
            seeded += 1

        logger.info("[MemSeed] Seeded %d memories for project %s", len(pm.files), proj.id)

    return seeded


def seed_global_memories():
    """Seed global platform knowledge into memory_global."""
    mem = get_memory_manager()

    # Check if already seeded
    existing = mem.global_get(limit=1)
    if existing:
        return 0

    seeded = 0
    for category, key, value, confidence in _GLOBAL_SEEDS:
        mem.global_store(
            key=key,
            value=value,
            category=category,
            confidence=confidence,
        )
        seeded += 1

    logger.info("[MemSeed] Seeded %d global memories", seeded)
    return seeded


def seed_all():
    """Run all memory seeding. Safe to call multiple times (idempotent)."""
    g = seed_global_memories()
    p = seed_project_memories()
    total = g + p
    if total:
        logger.info("[MemSeed] Total seeded: %d (global=%d, project=%d)", total, g, p)
    return total


def _file_to_category(path: str) -> str:
    """Map filename to memory category."""
    p = path.lower()
    if "vision" in p:
        return "vision"
    if "spec" in p:
        return "architecture"
    if "readme" in p:
        return "architecture"
    if "claude" in p or "copilot" in p or "cursor" in p or "convention" in p:
        return "convention"
    return "context"
