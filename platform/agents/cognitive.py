# Ref: feat-cognitive-arch
"""
Cognitive Architecture for SF Platform agents.

Inspired by AgentCeption (cgcardona/agentception, MIT).
Composable cognitive profiles: atoms × archetypes × skills → prompt injection.

Usage:
    profile = resolve_cognitive_arch("analyst,pragmatist")
    prompt_block = render_cognitive_prompt(profile)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ── Atom Definitions ─────────────────────────────────────────────────────────
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


# ── Archetypes ───────────────────────────────────────────────────────────────
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


# ── Cognitive Profile ────────────────────────────────────────────────────────

@dataclass
class CognitiveProfile:
    """Resolved cognitive profile for an agent."""
    archetypes: list[str] = field(default_factory=list)
    atoms: dict[str, str] = field(default_factory=dict)
    overrides: dict[str, str] = field(default_factory=dict)

    def get_atom(self, atom_name: str) -> Optional[str]:
        return self.atoms.get(atom_name)

    def get_prompt_fragment(self, atom_name: str) -> Optional[str]:
        value = self.atoms.get(atom_name)
        if not value:
            return None
        atom_def = ATOMS.get(atom_name, {})
        return atom_def.get(value)

    def fingerprint(self) -> str:
        """Short fingerprint: arch(atoms) e.g. 'pragmatist(empirical/iterative/pragmatic)'."""
        arch_str = "+".join(self.archetypes) if self.archetypes else "custom"
        key_atoms = [
            self.atoms.get("epistemic_style", "?"),
            self.atoms.get("cognitive_rhythm", "?"),
            self.atoms.get("quality_bar", "?"),
        ]
        return f"{arch_str}({'/'.join(key_atoms)})"


# ── Resolution ───────────────────────────────────────────────────────────────

def resolve_cognitive_arch(arch_string: str) -> CognitiveProfile:
    """
    Resolve a cognitive architecture string into a profile.

    Format: "archetype1,archetype2" or "archetype1,archetype2+override_atom=value"
    Examples:
        "pragmatist"
        "architect,scholar"
        "hacker+quality_bar=craftsperson"
        "guardian,pragmatist+creativity_level=inventive"

    Blending: when multiple archetypes, last-wins for conflicting atoms.
    Overrides: explicit atom=value after + sign, highest priority.
    """
    if not arch_string or not arch_string.strip():
        return CognitiveProfile()

    arch_string = arch_string.strip()

    # Split overrides (after +)
    override_part = ""
    if "+" in arch_string:
        arch_string, override_part = arch_string.split("+", 1)

    # Parse archetype list
    arch_names = [a.strip() for a in arch_string.split(",") if a.strip()]

    # Resolve atoms: walk archetypes, last-wins
    merged_atoms: dict[str, str] = {}
    valid_archs: list[str] = []

    for arch_name in arch_names:
        arch_def = ARCHETYPES.get(arch_name)
        if arch_def:
            merged_atoms.update(arch_def)
            valid_archs.append(arch_name)
        else:
            logger.warning("Unknown archetype %r — skipped", arch_name)

    # Apply explicit overrides
    overrides: dict[str, str] = {}
    if override_part:
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
        atoms=merged_atoms,
        overrides=overrides,
    )


# ── Prompt Rendering ─────────────────────────────────────────────────────────

def render_cognitive_prompt(profile: CognitiveProfile) -> str:
    """
    Render cognitive profile as a markdown block for system prompt injection.

    Returns empty string if profile has no atoms (no-op).
    """
    if not profile.atoms:
        return ""

    lines = [f"## Cognitive Profile [{profile.fingerprint()}]"]

    for atom_name in ATOM_NAMES:
        value = profile.atoms.get(atom_name)
        if not value:
            continue
        fragment = ATOMS.get(atom_name, {}).get(value, "")
        if fragment:
            label = atom_name.replace("_", " ").title()
            lines.append(f"- **{label}** ({value}): {fragment}")

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
