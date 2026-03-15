# Ref: feat-cognitive-arch
"""
Cognitive Architecture for SF Platform agents.

4-layer composable cognitive profiles inspired by AgentCeption (MIT):
  Layer 0: Atoms — primitive cognitive dimensions (7 axes)
  Layer 1: Archetypes — abstract thinking styles (8 types)
  Layer 2: Figures — historical thinkers extending archetypes (15 curated)
  Layer 3: Pressure adaptation — PUA-driven dynamic atom shifting

Usage:
    profile = resolve_cognitive_arch("pragmatist")           # archetype
    profile = resolve_cognitive_arch("turing,don_norman")     # figure blending
    profile = resolve_cognitive_arch("turing+quality_bar=pragmatic")  # override
    prompt  = render_cognitive_prompt(profile)
    shifted = apply_pressure_shift(profile, pressure_level=3) # PUA adaptation
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ── Layer 0: Atom Definitions ────────────────────────────────────────────────
# Each atom is a cognitive dimension with typed values.
# Values contribute prompt fragments to shape agent reasoning.

ATOMS: dict[str, dict[str, str]] = {
    "epistemic_style": {
        "deductive": "Prove from axioms. Distrust conclusions not derived from first principles.",
        "inductive": "Generalize from patterns. Build confidence by accumulating examples.",
        "abductive": "Seek the simplest explanation that fits observed evidence.",
        "empirical": "Experiment-first. Run the test, then believe the result.",
        "analogical": "Think by metaphor and structural similarity between domains.",
    },
    "cognitive_rhythm": {
        "deep_focus": "Long uninterrupted blocks. Optimal for complex, load-bearing problems.",
        "iterative": "Short cycles. Frequent commits. Comfort with incremental progress.",
        "burst": "Intense, explosive output then synthesis. Full problem in working memory.",
        "exploratory": "Wide scan before narrow execution. Map the territory first.",
    },
    "uncertainty_handling": {
        "probabilistic": "Assign confidence levels. Act on expected value, not certainty.",
        "conservative": "Prefer known-good solutions. Avoid untested territory.",
        "aggressive": "Ship into uncertainty. Learn from breakage.",
        "cautious": "High information requirement before action. Escalate before guessing.",
    },
    "collaboration_posture": {
        "autonomous": "Figure it out alone. Only ask when fully blocked.",
        "consultative": "Poll others before committing to direction.",
        "directive": "Tell others what to do. Comfortable with authority.",
        "collaborative": "Work alongside. High trust in teammates' judgment.",
    },
    "creativity_level": {
        "conservative": "Prefer established patterns. Don't fix what isn't broken.",
        "incremental": "Small improvements to existing approaches.",
        "inventive": "Generate genuinely new approaches. High tolerance for uncertainty.",
        "radical": "Question the problem itself. Invent new paradigms.",
    },
    "quality_bar": {
        "mvp": "Works. Ships fast. Polish later.",
        "pragmatic": "Correct and maintainable. Practical tradeoffs.",
        "craftsperson": "Excellence in implementation, not just correctness.",
        "perfectionist": "Will not ship until it is right. High cost, high output quality.",
    },
    "scope_instinct": {
        "minimal": "Do exactly what was asked. No scope creep.",
        "focused": "Narrow execution. Ignore peripheral concerns.",
        "expansive": "See the broader context and act on it.",
    },
}

ATOM_NAMES = list(ATOMS.keys())


# ── Layer 1: Archetypes ──────────────────────────────────────────────────────
# Abstract thinking styles. Each defines default atom values.

ARCHETYPES: dict[str, dict[str, str]] = {
    "architect": {
        "epistemic_style": "deductive",
        "cognitive_rhythm": "deep_focus",
        "uncertainty_handling": "conservative",
        "collaboration_posture": "autonomous",
        "creativity_level": "incremental",
        "quality_bar": "craftsperson",
        "scope_instinct": "focused",
    },
    "scholar": {
        "epistemic_style": "inductive",
        "cognitive_rhythm": "exploratory",
        "uncertainty_handling": "probabilistic",
        "collaboration_posture": "consultative",
        "creativity_level": "incremental",
        "quality_bar": "perfectionist",
        "scope_instinct": "expansive",
    },
    "pragmatist": {
        "epistemic_style": "empirical",
        "cognitive_rhythm": "iterative",
        "uncertainty_handling": "probabilistic",
        "collaboration_posture": "collaborative",
        "creativity_level": "incremental",
        "quality_bar": "pragmatic",
        "scope_instinct": "minimal",
    },
    "hacker": {
        "epistemic_style": "empirical",
        "cognitive_rhythm": "burst",
        "uncertainty_handling": "aggressive",
        "collaboration_posture": "autonomous",
        "creativity_level": "inventive",
        "quality_bar": "mvp",
        "scope_instinct": "minimal",
    },
    "guardian": {
        "epistemic_style": "deductive",
        "cognitive_rhythm": "deep_focus",
        "uncertainty_handling": "cautious",
        "collaboration_posture": "directive",
        "creativity_level": "conservative",
        "quality_bar": "perfectionist",
        "scope_instinct": "focused",
    },
    "mentor": {
        "epistemic_style": "analogical",
        "cognitive_rhythm": "iterative",
        "uncertainty_handling": "probabilistic",
        "collaboration_posture": "collaborative",
        "creativity_level": "incremental",
        "quality_bar": "craftsperson",
        "scope_instinct": "expansive",
    },
    "operator": {
        "epistemic_style": "empirical",
        "cognitive_rhythm": "iterative",
        "uncertainty_handling": "conservative",
        "collaboration_posture": "directive",
        "creativity_level": "conservative",
        "quality_bar": "pragmatic",
        "scope_instinct": "focused",
    },
    "visionary": {
        "epistemic_style": "abductive",
        "cognitive_rhythm": "burst",
        "uncertainty_handling": "aggressive",
        "collaboration_posture": "directive",
        "creativity_level": "radical",
        "quality_bar": "pragmatic",
        "scope_instinct": "expansive",
    },
}


# ── Layer 2: Figures ─────────────────────────────────────────────────────────
# Historical thinkers extending archetypes with specific atom overrides.
# Each figure has: extends (base archetype), atom overrides, brief description.

@dataclass
class FigureDef:
    extends: str
    overrides: dict[str, str]
    description: str = ""

FIGURES: dict[str, FigureDef] = {
    # --- Systems & Algorithms ---
    "turing": FigureDef(
        extends="architect",
        overrides={"quality_bar": "perfectionist", "scope_instinct": "minimal"},
        description="Core algorithms, type systems, formal computation.",
    ),
    "von_neumann": FigureDef(
        extends="architect",
        overrides={"cognitive_rhythm": "burst", "scope_instinct": "expansive"},
        description="Systems-level thinking. Full problem in working memory.",
    ),
    "dijkstra": FigureDef(
        extends="scholar",
        overrides={"epistemic_style": "deductive", "quality_bar": "perfectionist",
                   "collaboration_posture": "autonomous"},
        description="Correctness-obsessed. Epistemic precision. Formal verification.",
    ),
    "knuth": FigureDef(
        extends="scholar",
        overrides={"cognitive_rhythm": "deep_focus", "quality_bar": "perfectionist"},
        description="Algorithm implementation. Literate programming. Perfectionist.",
    ),
    # --- Pragmatic Builders ---
    "hopper": FigureDef(
        extends="pragmatist",
        overrides={"collaboration_posture": "collaborative", "quality_bar": "pragmatic"},
        description="Ship under constraints. Empirical. 'It's easier to ask forgiveness.'",
    ),
    "linus_torvalds": FigureDef(
        extends="hacker",
        overrides={"quality_bar": "craftsperson", "collaboration_posture": "directive"},
        description="Decisive. High quality bar. Direct communication. Systems programming.",
    ),
    "kent_beck": FigureDef(
        extends="pragmatist",
        overrides={"cognitive_rhythm": "iterative", "creativity_level": "incremental"},
        description="TDD. Red-green-refactor. Iterative. Extreme Programming.",
    ),
    "rob_pike": FigureDef(
        extends="pragmatist",
        overrides={"creativity_level": "conservative", "scope_instinct": "minimal"},
        description="Simplicity. Less is more. Clear over clever.",
    ),
    "guido_van_rossum": FigureDef(
        extends="pragmatist",
        overrides={"quality_bar": "craftsperson", "creativity_level": "conservative"},
        description="Readability counts. Explicit over implicit. One obvious way.",
    ),
    # --- Mentors & Communicators ---
    "feynman": FigureDef(
        extends="scholar",
        overrides={"epistemic_style": "analogical", "creativity_level": "inventive",
                   "collaboration_posture": "collaborative"},
        description="Analogical thinker. Deep explanations. Teaching orientation.",
    ),
    "martin_fowler": FigureDef(
        extends="mentor",
        overrides={"epistemic_style": "inductive", "quality_bar": "craftsperson"},
        description="Refactoring. Design patterns. Communicative architecture.",
    ),
    # --- Security & Defense ---
    "bruce_schneier": FigureDef(
        extends="guardian",
        overrides={"epistemic_style": "deductive", "creativity_level": "conservative"},
        description="Threat-model first. Trust nothing. Defense in depth.",
    ),
    # --- Product & Vision ---
    "don_norman": FigureDef(
        extends="architect",
        overrides={"epistemic_style": "empirical", "creativity_level": "inventive",
                   "collaboration_posture": "collaborative", "scope_instinct": "expansive"},
        description="User-centered design. Affordances. Emotional design.",
    ),
    "steve_jobs": FigureDef(
        extends="visionary",
        overrides={"quality_bar": "perfectionist", "collaboration_posture": "directive"},
        description="Taste-driven. Radical simplicity. Product excellence.",
    ),
    # --- Scale & Performance ---
    "jeff_dean": FigureDef(
        extends="architect",
        overrides={"cognitive_rhythm": "burst", "uncertainty_handling": "aggressive",
                   "scope_instinct": "expansive"},
        description="Scale thinking. 10x solutions. Infrastructure that enables.",
    ),
}


# ── Layer 3: Pressure Adaptation ─────────────────────────────────────────────
# PUA pressure levels shift cognitive atoms to adapt agent behavior under stress.
# Higher pressure → more conservative, focused, iterative.

PRESSURE_SHIFTS: dict[int, dict[str, str]] = {
    # L0: no shift (normal operation)
    0: {},
    # L1: light pressure — shift to iterative rhythm
    1: {
        "cognitive_rhythm": "iterative",
    },
    # L2: medium pressure — conservative + pragmatic
    2: {
        "cognitive_rhythm": "iterative",
        "uncertainty_handling": "conservative",
        "quality_bar": "pragmatic",
    },
    # L3: heavy pressure — minimal scope, conservative creativity
    3: {
        "cognitive_rhythm": "iterative",
        "uncertainty_handling": "cautious",
        "creativity_level": "conservative",
        "quality_bar": "pragmatic",
        "scope_instinct": "minimal",
    },
    # L4: critical — full defensive mode
    4: {
        "cognitive_rhythm": "deep_focus",
        "uncertainty_handling": "cautious",
        "creativity_level": "conservative",
        "quality_bar": "perfectionist",
        "scope_instinct": "minimal",
        "collaboration_posture": "consultative",
    },
}


# ── Role → Archetype Auto-Assignment ─────────────────────────────────────────
# Map agent roles to default cognitive archetypes for bulk assignment.

ROLE_ARCHETYPE_MAP: dict[str, str] = {
    # Development
    "developer": "pragmatist",
    "dev": "pragmatist",
    "engineer": "pragmatist",
    "fullstack": "pragmatist",
    "frontend": "pragmatist",
    "backend": "pragmatist",
    "worker": "pragmatist",
    "implementer": "pragmatist",
    "coder": "pragmatist",
    # Architecture
    "architect": "architect",
    "architecte": "architect",
    "tech_lead": "architect",
    "lead_dev": "architect",
    "cto": "visionary",
    # Quality
    "qa": "scholar",
    "tester": "scholar",
    "testeur": "scholar",
    "qa_lead": "scholar",
    "reviewer": "scholar",
    "critic": "guardian",
    "code-critic": "guardian",
    # Security
    "security": "guardian",
    "pentester": "hacker",
    "security_critic": "guardian",
    "pentester_lead": "hacker",
    # Ops
    "devops": "operator",
    "sre": "operator",
    "ops": "operator",
    "infra": "operator",
    "dba": "operator",
    # Management
    "product": "mentor",
    "po": "mentor",
    "scrum_master": "mentor",
    "rte": "operator",
    "release_train_engineer": "operator",
    "pm": "mentor",
    "manager": "mentor",
    # Design
    "designer": "visionary",
    "ux": "visionary",
    "ui": "pragmatist",
    # Strategy
    "brain": "visionary",
    "strategist": "visionary",
    "innovation": "visionary",
    # Documentation
    "documenter": "mentor",
    "tech_writer": "mentor",
    # Data
    "data_engineer": "pragmatist",
    "data_scientist": "scholar",
    "ml_engineer": "scholar",
    "analyst": "scholar",
}


# ── Cognitive Profile ────────────────────────────────────────────────────────

@dataclass
class CognitiveProfile:
    """Resolved cognitive profile for an agent."""
    archetypes: list[str] = field(default_factory=list)
    figures: list[str] = field(default_factory=list)
    atoms: dict[str, str] = field(default_factory=dict)
    overrides: dict[str, str] = field(default_factory=dict)
    pressure_level: int = 0

    def get_atom(self, atom_name: str) -> Optional[str]:
        return self.atoms.get(atom_name)

    def get_prompt_fragment(self, atom_name: str) -> Optional[str]:
        value = self.atoms.get(atom_name)
        if not value:
            return None
        atom_def = ATOMS.get(atom_name, {})
        return atom_def.get(value)

    def fingerprint(self) -> str:
        """Short fingerprint e.g. 'turing(deductive/deep_focus/perfectionist)'."""
        if self.figures:
            name_str = "+".join(self.figures)
        elif self.archetypes:
            name_str = "+".join(self.archetypes)
        else:
            name_str = "custom"
        key_atoms = [
            self.atoms.get("epistemic_style", "?"),
            self.atoms.get("cognitive_rhythm", "?"),
            self.atoms.get("quality_bar", "?"),
        ]
        suffix = f"/P{self.pressure_level}" if self.pressure_level else ""
        return f"{name_str}({'/'.join(key_atoms)}{suffix})"


# ── Resolution ───────────────────────────────────────────────────────────────

def resolve_cognitive_arch(arch_string: str) -> CognitiveProfile:
    """
    Resolve a cognitive architecture string into a profile.

    Supports archetypes, figures, blending, and overrides.
    Figures are tried first; if not found, falls back to archetype lookup.

    Format: "name1,name2+override_atom=value"
    Examples:
        "pragmatist"                          — single archetype
        "architect,scholar"                   — blended archetypes (last-wins)
        "turing"                              — figure (extends architect)
        "turing,don_norman"                   — blended figures
        "turing+quality_bar=pragmatic"        — figure with override
        "hacker+quality_bar=craftsperson"     — archetype with override
    """
    if not arch_string or not arch_string.strip():
        return CognitiveProfile()

    arch_string = arch_string.strip()

    # Split overrides (after +)
    override_part = ""
    if "+" in arch_string:
        arch_string, override_part = arch_string.split("+", 1)

    # Parse name list
    names = [a.strip() for a in arch_string.split(",") if a.strip()]

    # Resolve atoms: walk names (figure → archetype fallback), last-wins
    merged_atoms: dict[str, str] = {}
    valid_archs: list[str] = []
    valid_figures: list[str] = []

    for name in names:
        fig_def = FIGURES.get(name)
        if fig_def:
            # Figure: first apply base archetype, then figure overrides
            base = ARCHETYPES.get(fig_def.extends, {})
            merged_atoms.update(base)
            merged_atoms.update(fig_def.overrides)
            valid_figures.append(name)
            if fig_def.extends not in valid_archs:
                valid_archs.append(fig_def.extends)
        else:
            arch_def = ARCHETYPES.get(name)
            if arch_def:
                merged_atoms.update(arch_def)
                valid_archs.append(name)
            else:
                logger.warning("Unknown archetype/figure %r — skipped", name)

    # Apply explicit overrides (only if we have a base profile to override)
    overrides: dict[str, str] = {}
    if override_part and merged_atoms:
        for pair in override_part.split(","):
            if "=" in pair:
                key, val = pair.split("=", 1)
                key, val = key.strip(), val.strip()
                if key in ATOMS and val in ATOMS.get(key, {}):
                    merged_atoms[key] = val
                    overrides[key] = val
                else:
                    logger.warning("Invalid override %s=%s — skipped", key, val)

    return CognitiveProfile(
        archetypes=valid_archs,
        figures=valid_figures,
        atoms=merged_atoms,
        overrides=overrides,
    )


def apply_pressure_shift(
    profile: CognitiveProfile, pressure_level: int
) -> CognitiveProfile:
    """
    Apply PUA pressure shift to a cognitive profile.

    Higher pressure → more conservative, focused, iterative atoms.
    Returns a new profile with shifted atoms (original untouched).
    Explicit overrides are never shifted (user intent preserved).
    """
    if pressure_level <= 0:
        return profile

    level = min(pressure_level, 4)
    shifts = PRESSURE_SHIFTS.get(level, {})
    if not shifts:
        return profile

    new_atoms = dict(profile.atoms)
    for atom, value in shifts.items():
        # Never override explicit user overrides
        if atom not in profile.overrides:
            new_atoms[atom] = value

    return CognitiveProfile(
        archetypes=list(profile.archetypes),
        figures=list(profile.figures),
        atoms=new_atoms,
        overrides=dict(profile.overrides),
        pressure_level=level,
    )


def infer_archetype_for_role(role: str) -> str:
    """
    Infer the best cognitive archetype for a given agent role.

    Checks ROLE_ARCHETYPE_MAP with progressive normalization:
    exact match → longest substring match → default 'pragmatist'.
    Longer patterns match first to avoid 'architect' eating 'security architect'.
    """
    if not role:
        return "pragmatist"

    r = role.lower().strip().replace("-", "_")

    # Exact match
    if r in ROLE_ARCHETYPE_MAP:
        return ROLE_ARCHETYPE_MAP[r]

    # Longest substring match (prevents "architect" eating "security architect")
    best_match = ""
    best_arch = ""
    for pattern, archetype in ROLE_ARCHETYPE_MAP.items():
        if pattern in r or r in pattern:
            if len(pattern) > len(best_match):
                best_match = pattern
                best_arch = archetype

    return best_arch if best_arch else "pragmatist"


# ── Prompt Rendering ─────────────────────────────────────────────────────────

def render_cognitive_prompt(profile: CognitiveProfile) -> str:
    """
    Render cognitive profile as a markdown block for system prompt injection.

    Includes figure descriptions if present.
    Returns empty string if profile has no atoms (no-op).
    """
    if not profile.atoms:
        return ""

    lines = [f"## Cognitive Profile [{profile.fingerprint()}]"]

    # Figure descriptions
    for fig_name in profile.figures:
        fig_def = FIGURES.get(fig_name)
        if fig_def and fig_def.description:
            lines.append(f"*{fig_name.replace('_', ' ').title()}*: {fig_def.description}")

    # Atom values
    for atom_name in ATOM_NAMES:
        value = profile.atoms.get(atom_name)
        if not value:
            continue
        fragment = ATOMS.get(atom_name, {}).get(value, "")
        if fragment:
            label = atom_name.replace("_", " ").title()
            lines.append(f"- **{label}** ({value}): {fragment}")

    # Pressure indicator
    if profile.pressure_level >= 2:
        lines.append(f"\n> Pressure L{profile.pressure_level}: cognitive atoms shifted "
                      "toward conservative/focused mode.")

    return "\n".join(lines)


# ── A/B Experiment Helpers ───────────────────────────────────────────────────

def cognitive_ab_variants(
    arch_a: str, arch_b: str
) -> tuple[CognitiveProfile, CognitiveProfile]:
    """
    Create two cognitive profiles for A/B testing.

    Returns (profile_a, profile_b) resolved from their arch strings.
    Use with ac/experiments.py to compare agent performance.
    """
    return resolve_cognitive_arch(arch_a), resolve_cognitive_arch(arch_b)


def diff_profiles(a: CognitiveProfile, b: CognitiveProfile) -> dict[str, tuple[str, str]]:
    """
    Show atom differences between two profiles.

    Returns dict of {atom_name: (value_a, value_b)} for differing atoms only.
    """
    diffs = {}
    all_atoms = set(a.atoms.keys()) | set(b.atoms.keys())
    for atom in sorted(all_atoms):
        va = a.atoms.get(atom, "—")
        vb = b.atoms.get(atom, "—")
        if va != vb:
            diffs[atom] = (va, vb)
    return diffs
