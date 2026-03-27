"""Prompt builder — system prompt construction, message building, and agent classification.

Extracted from executor.py to keep the main file focused on the agent loop.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..llm.client import LLMMessage

# Re-export from tool_schemas for convenience
from .tool_schemas import (
    _classify_agent_role,
)

if TYPE_CHECKING:
    from .executor import ExecutionContext

# ─── QA Role Boundary (PUA-derived) ──────────────────────────────────────────
# Source: github.com/tanweai/pua (MIT) — adapted for SF QA agents.
# Full PUA engine (Iron Rules, L1-L4 pressure, 5-step debug) is in pua.py and
# injected for ALL agents via build_motivation_block() at prompt assembly time.
# This block adds QA-specific role boundary enforcement (REVIEW ≠ IMPLEMENT).
_PUA_QA_BLOCK = """
## QA Role Boundaries (CRITICAL)
You are a REVIEWER / VALIDATOR — NOT an implementer.
Your job: validate existing code against specs, find bugs, write test verdicts.
**FORBIDDEN**: code_write to create implementation files, writing business logic, adding features.
**ALLOWED**: code_write only to create/update TEST files (test_*.py, *.spec.ts, *.test.js).

### QA Persistence (PUA adapted — source: github.com/tanweai/pua MIT)
1. **Run all tests** — never report "PASS" without actually executing the test suite.
2. **Verify against specs** — read SPECS.md AC items (look for `[AC:ac-xxx]` tags), confirm each one is implemented AND tested.
3. **Report with evidence** — every FAIL must cite: file + line + expected vs actual behavior.
4. **Proactive** — find bugs beyond the obvious: edge cases, missing error handling, security gaps, traceability gaps (no `# Ref:` header).
5. **Verdict format**: [PASS] or [FAIL: reason] — never "it looks correct" without proof.
"""
# ─────────────────────────────────────────────────────────────────────────────

# Roles that benefit from architecture guidelines injection
_GUIDELINES_ROLES = {
    "dev",
    "architecture",
    "security",
    "reviewer",
    "qa",
    "backend",
    "frontend",
}

# Simple LRU-style cache to avoid DB hit on every message (project_id → (summary, timestamp))
_guidelines_cache: dict[str, tuple[str, float]] = {}
_GUIDELINES_CACHE_TTL = 300  # 5 minutes


def _get_project_domain(project_id: str) -> str:
    """Read domain field from projects/{project_id}.yaml. Returns empty string if not set."""
    try:
        from pathlib import Path
        import yaml as _yaml

        p = Path(__file__).parent.parent.parent / "projects" / f"{project_id}.yaml"
        if not p.exists():
            return ""
        data = _yaml.safe_load(p.read_text()) or {}
        return data.get("project", {}).get("domain", "") or data.get("domain", "") or ""
    except Exception:
        return ""


def _load_guidelines_for_prompt(ctx: "ExecutionContext") -> str:
    """Load architecture guidelines from DB and return compact summary for system prompt injection.

    Lookup order: project_id → domain:{project.domain}
    Only injects for roles that need tech constraints (dev, architecture, security, ...).
    Returns empty string if no guidelines configured for this project.
    """
    import time

    if not ctx.project_id:
        return ""

    # Role filter — skip for product/marketing/ideation-only roles
    role = _classify_agent_role(ctx.agent)
    if role not in _GUIDELINES_ROLES:
        return ""

    # Determine which project keys to try (project-level first, then domain-level)
    keys_to_try = [ctx.project_id]
    domain = _get_project_domain(ctx.project_id)
    if domain:
        keys_to_try.append(f"domain:{domain}")

    for proj_key in keys_to_try:
        cached = _guidelines_cache.get(proj_key)
        if cached:
            summary, ts = cached
            if time.time() - ts < _GUIDELINES_CACHE_TTL:
                return summary

    try:
        from ..db.adapter import get_connection

        conn = get_connection()

        from mcp_lrm.guidelines_scraper import build_guidelines_summary

        for proj_key in keys_to_try:
            meta = conn.execute(
                "SELECT page_count FROM guideline_meta WHERE project = ?", (proj_key,)
            ).fetchone()
            if meta and meta["page_count"] > 0:
                conn.close()
                summary = build_guidelines_summary(proj_key, role, max_chars=600)
                _guidelines_cache[proj_key] = (summary, time.time())
                return summary

        conn.close()
        return ""
    except Exception:
        return ""


def _build_system_prompt(ctx: ExecutionContext) -> str:
    """Compose the full system prompt from agent config + skills + context."""
    parts = []
    agent = ctx.agent

    if agent.system_prompt:
        parts.append(agent.system_prompt)

    if agent.persona:
        parts.append(f"\n## Persona & Character\n{agent.persona}")

    if agent.motivation:
        parts.append(f"\n## Motivation & Drive\n{agent.motivation}")

    # Cognitive architecture — composable profile (inspired by AgentCeption, MIT)
    # Resolves archetypes/figures, then applies PUA pressure shift if agent is failing.
    _cog_arch = getattr(agent, "cognitive_arch", "")
    if not _cog_arch:
        # Auto-infer from role if not explicitly set
        try:
            from .cognitive import infer_archetype_for_role
            _cog_arch = infer_archetype_for_role(agent.role)
        except Exception:
            pass
    if _cog_arch:
        try:
            from .cognitive import resolve_cognitive_arch, render_cognitive_prompt, apply_pressure_shift
            _cog_profile = resolve_cognitive_arch(_cog_arch)
            # Apply PUA pressure adaptation if agent has consecutive failures
            _pressure = getattr(ctx, "consecutive_failures", 0) or 0
            if _pressure > 0:
                from .pua import get_pressure_level
                _plevel = get_pressure_level(_pressure)
                _cog_profile = apply_pressure_shift(_cog_profile, _plevel)
            _cog_block = render_cognitive_prompt(_cog_profile)
            if _cog_block:
                parts.append(f"\n{_cog_block}")
        except Exception:
            pass

    parts.append(f"\nYou are {agent.name}, role: {agent.role}.")
    if agent.description:
        parts.append(f"Description: {agent.description}")

    # PUA motivation baseline — Iron Rules + Proactivity (source: tanweai/pua MIT)
    from .pua import build_motivation_block
    parts.append(build_motivation_block())

    # Adversarial feedback from prior rejection — injected into system prompt
    # so the agent's behavioral baseline changes, not just the user message
    if ctx.adversarial_feedback:
        parts.append(f"""
## ADVERSARIAL CORRECTION (PRIORITY ABSOLUE)
Your previous attempt was REJECTED. You MUST fix these issues:
{ctx.adversarial_feedback}
Failure to address these issues = automatic rejection again.
Do NOT repeat the same approach. Change your behavior fundamentally.""")

    if ctx.tools_enabled:
        parts.append("""
You have access to tools via function calling. Call tools directly — do NOT write tool calls as text.
CRITICAL: When asked to CREATE or IMPLEMENT something, call code_write WITHIN YOUR FIRST 3 ROUNDS.
Do not spend all rounds exploring — explore quickly (1 list_files), then WRITE code.

## Memory (recommended, not blocking)
- Call memory_search(query="<topic>") to check prior decisions — skip if the task is clear.
- Call memory_store() at the END to record key decisions.""")

        # RLM instruction — optional, not mandatory
        if ctx.allowed_tools is None or "deep_search" in (ctx.allowed_tools or []):
            parts.append("""
## Deep Search / RLM (optional — use only when exploring unfamiliar code)
Call deep_search(query="<question>") for complex codebase exploration.
Skip it when you already know what to build — go straight to code_write.""")

        # Role-specific tool instructions
        role_cat = _classify_agent_role(agent)
        if role_cat == "cto":
            parts.append("""
## Software Factory — Rôle CTO (PRIORITÉ ABSOLUE)
Tu es Karim Benali, CTO de la Software Factory. Tu es opérationnel : tu peux CONSULTER et CRÉER.

RÈGLES FONDAMENTALES :
1. Si le message contient un bloc "--- Contexte projet SF @NomProjet ---" :
   → RÉPONDS DIRECTEMENT en utilisant les infos de ce bloc (nom, description, vision, type, domaines)
   → NE PAS appeler list_files, code_search, code_read — les projets SF ne sont PAS dans le filesystem local
   → NE PAS dire "je ne trouve pas ce projet" — il est dans le bloc de contexte
   → Si le bloc indique des missions SF actives, tu peux appeler platform_missions(project_id="...")
2. Pour lister les projets SF : appelle platform_agents() ou demande à l'utilisateur d'utiliser @NomProjet
3. Pour les métriques globales : platform_metrics(), platform_sessions()
4. INTERDIT dans le contexte SF-Platform uniquement : list_files, code_search (cherchent dans le filesystem local, pas dans la SF)
5. INTERDIT : créer des fichiers locaux, demander des credentials, générer du SQL

POUR LES PROJETS CLIENTS (MobilityApp, LDP, PSY, FinApp, etc.) :
- Utilise memory_search pour lire la mémoire du projet (specs, architecture, décisions)
- Utilise jira_search(project="VELIGO") pour consulter les tickets Jira
- Utilise confluence_read(page_id="...") pour lire la documentation Confluence
- Utilise code_read / list_files si le projet a un workspace local
- Utilise deep_search pour une exploration récursive du codebase

ACTIONS QUE TU PEUX EFFECTUER :
- Créer un projet complet : create_project(name, description, vision, factory_type)
  → crée automatiquement : workspace, git init + commit, Dockerfile, docker-compose, README
  → lance automatiquement 3 missions standards : TMA/MCO (tma-maintenance), Sécurité (security-hacking), Dette Tech + Légalité (tech-debt-reduction)
  → retourne project_id, workspace path, liste des actions scaffold et des missions créées
- Créer une mission spécifique : create_mission(name, goal, project_id, workflow_id) → lance l'orchestrateur
- Monter une équipe : create_team(team_name, domain, stack, roles=[{id, name, role, skills, prompt}])
- Composer un workflow : compose_workflow(workflow_id, project_id, overrides)
- Quand l'utilisateur dit "crée", "lance", "monte", "démarre" → AGIS directement sans demander de confirmation
- Après create_project/create_mission, informe l'utilisateur avec l'ID et un lien vers la ressource créée""")
        elif role_cat == "qa":
            parts.append("""
## QA Testing (MANDATORY — read carefully)
You have a tool called run_e2e_tests. You MUST call it.
It automatically: installs deps, starts the server, takes screenshots, runs tests.

STEP 1: Call run_e2e_tests() — this is REQUIRED, do it FIRST
STEP 2: Read the results and report bugs with create_ticket()
STEP 3: Call build(command="npm test") for additional unit tests if needed

DO NOT skip run_e2e_tests(). Your validation is REJECTED without it.""")
            parts.append(_PUA_QA_BLOCK)
        elif role_cat == "security":
            parts.append("""
## Security Tools (IMPORTANT)
Run SAST scans on the codebase:
- build(command="bandit -r . -f json") for Python projects
- build(command="semgrep --config auto .") for any project
- build(command="npm audit") for Node.js projects
Report findings with severity ratings.""")
        elif role_cat == "product":
            parts.append("""
## Backlog Tools (IMPORTANT — AO Traceability)
When decomposing an epic into features and stories, you MUST persist them:
- create_feature(epic_id="<mission_id>", name="Feature name", priority=1, story_points=8)
- create_story(feature_id="<id>", title="US-E1-01: Story title", story_points=5)

EVERY requirement from the AO/epic description must have at least one feature.
Items marked "hors MVP" or "P2" must STILL be created with status 'deferred'.
Format stories as US-<Epic>-<Num> for traceability (e.g. US-E1-01, US-E2-03).""")
        elif role_cat == "ux":
            parts.append("""
## Design System (MANDATORY — you MUST create these files)
You are the UX Designer. You MUST use code_write to create a design system BEFORE any dev sprint.

STEP 1: Create design tokens file:
  code_write(path="src/styles/tokens.css", content="... CSS custom properties ...")
  Include: --color-primary, --color-secondary, --color-background, --color-surface,
  --color-text, --color-error, --color-success, --font-family, --font-size-sm/md/lg/xl,
  --spacing-xs/sm/md/lg/xl, --radius-sm/md/lg, --shadow-sm/md/lg, --transition-fast/normal

STEP 2: Create base layout with responsive breakpoints:
  code_write(path="src/styles/base.css", content="... reset + responsive grid ...")
  Include: CSS reset, responsive breakpoints (320px/768px/1024px/1440px), container,
  skip-to-content link, focus-visible styles, reduced-motion media query

STEP 3: Create component library (at minimum):
  code_write(path="src/styles/components.css", content="... buttons, cards, forms ...")
  Include: .btn (primary/secondary/ghost), .card, .form-group, .input, .badge, .alert
  ALL using var(--token-*). NO hardcoded colors. NO hardcoded font sizes.

STEP 4: Store design decisions in memory:
  memory_store(key="design-system", value="Tokens: ..., Components: ..., A11y: WCAG AA")

RULES:
- Contrast ratio ≥ 4.5:1 (text) and ≥ 3:1 (large text, UI components)
- All interactive elements must have :focus-visible styles
- prefers-reduced-motion: reduce → disable animations
- Mobile-first responsive (min-width breakpoints)
- All colors via CSS custom properties (tokens), NEVER hardcoded hex/rgb""")
        # Universal tool-use mandate for ALL execution agents (dev, qa, devops, security)
        # Prevents hallucination: agents describing work instead of doing it
        if role_cat in ("dev", "qa", "devops", "security"):
            parts.append("""
## Tool Usage (MANDATORY — zero tolerance)
You are an EXECUTION agent. Every response MUST include tool calls.
1. WRITE code FIRST: code_write / code_edit — this is your PRIMARY action
2. Read only if needed: code_read / list_files to check existing code (max 2 calls)
3. VERIFY after writing: build / test to confirm your changes work
NEVER describe what you would do — DO IT with tool calls.
Text-only responses WITHOUT tool calls = automatic REJECTION.
If a tool fails, try a different approach — do NOT give up and describe instead.""")
    else:
        parts.append(
            "\nYou do NOT have tools. Do NOT write [TOOL_CALL] or attempt to use tools. Focus on analysis, synthesis, and delegation to your team."
        )

    # Traceability requirement for all dev roles
    role_cat = _classify_agent_role(agent)
    _dev_roles = {"backend", "frontend", "fullstack", "dev", "mobile", "architect", "architecture"}
    if role_cat in _dev_roles:
        parts.append("""
## Traceability (MANDATORY)
Every source file you create with code_write MUST include a traceability header:
  # Ref: {feature_id} — {feature_name}
  # Story: {story_id} — {story_title}
Example: # Ref: feat-a1b2 — User authentication endpoint

This enables full audit trail: feature → code → test.
If you don't have a feature ID, use the task name (e.g., # Ref: task-auth — Login flow).
""")

    if ctx.skills_prompt:
        parts.append(f"\n## Skills\n{ctx.skills_prompt}")

    # Apply tier-aware budgets for guidelines/memory/vision
    from ..llm.context_tiers import ContextTier, apply_tier_to_context
    tier = ContextTier(ctx.context_tier)

    # Inject architecture/tech guidelines if available for this project
    guidelines = _load_guidelines_for_prompt(ctx)
    if guidelines:
        tiered = apply_tier_to_context(tier, guidelines=guidelines)
        if tiered["guidelines"]:
            parts.append(f"\n## Architecture & Tech Guidelines (DSI)\n{tiered['guidelines']}")
    else:
        tiered = apply_tier_to_context(
            tier,
            project_context=ctx.project_context,
            project_memory=ctx.project_memory,
            vision=ctx.vision,
        )

    if tier == ContextTier.L2:
        # L2: full project context (organizers, reviewers)
        if tiered.get("vision"):
            parts.append(f"\n## Project Vision\n{tiered['vision']}")
        if tiered.get("project_context"):
            parts.append(f"\n## Project Context\n{tiered['project_context']}")
        if tiered.get("project_memory"):
            parts.append(
                f"\n## Project Memory (auto-loaded instructions)\n{tiered['project_memory']}"
            )
    elif tier == ContextTier.L1:
        # L1: condensed context (standard agents)
        if tiered.get("project_context"):
            parts.append(
                f"\n## Task Context (relevant memory)\n{tiered['project_context']}"
            )
    # L0: no memory/vision injected (routing only)

    if ctx.project_path:
        parts.append(f"\n## Project Path\n{ctx.project_path}")

    # Inject constraints — adversarial L1 reviewer enforces these
    parts.append("""
## CONSTRAINTS (adversarial reviewer will VETO violations)
- No emoji in code. Use text or SVG icons only.
- If brief says "single file": ALL code in ONE file. Inline CSS+JS. No external src/href.
- Never concatenate two implementations. Clean before rewriting.
- Write files ONLY inside the project workspace path shown above.
- Output must match the brief: requested stack, theme, features, architecture.
""")

    perms = agent.permissions or {}
    if perms.get("can_delegate"):
        parts.append("""
## Delegation (IMPORTANT)
You MUST delegate tasks to your team using this exact format on separate lines:
[DELEGATE:agent_id] clear task description

Example:
[DELEGATE:strat-cpo] Analyser la vision produit et valider les objectifs business
[DELEGATE:strat-cto] Évaluer la faisabilité technique et recommander le stack

As a leader, your job is to DELEGATE to team members, then SYNTHESIZE their responses.
Do NOT try to do everything yourself — leverage your team.""")
    if perms.get("can_veto"):
        parts.append("\nYou CAN veto decisions by writing: [VETO] reason")
    if perms.get("can_approve"):
        parts.append("\nYou CAN approve work by writing: [APPROVE] reason")

    return "\n".join(parts)


def _build_messages(ctx: ExecutionContext, user_message: str) -> list[LLMMessage]:
    """Build the message list from conversation history."""
    messages = []
    for h in ctx.history[-20:]:
        role = "assistant" if h.get("from_agent") != "user" else "user"
        name = h.get("from_agent")
        messages.append(
            LLMMessage(
                role=role,
                content=h.get("content", ""),
                name=name if name != "user" else None,
            )
        )
    messages.append(LLMMessage(role="user", content=user_message))
    return messages
