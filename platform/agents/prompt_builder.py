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
        from pathlib import Path

        db_path = Path(__file__).parent.parent.parent / "data" / "guidelines.db"
        if not db_path.exists():
            return ""

        import sqlite3

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

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

    parts.append(f"\nYou are {agent.name}, role: {agent.role}.")
    if agent.description:
        parts.append(f"Description: {agent.description}")

    if ctx.tools_enabled:
        parts.append("""
You have access to tools via function calling. When you need to take action, call the tools directly — do NOT write tool calls as text (no [TOOL_CALL], no JSON in your response). The system handles tool execution automatically when you use function calling.
CRITICAL: When the user asks you to DO something (lancer, fixer, chercher), USE your tools immediately. Do not just describe what you would do — actually do it.

## Memory (MANDATORY)
1. ALWAYS call memory_search(query="<topic>") at the START of your work to see what was already decided/built.
2. ALWAYS call memory_store() at the END to record your key decisions, findings, or deliverables.
   - key: short identifier (e.g. "auth-strategy", "db-schema", "api-design")
   - value: concrete decision/finding (1-3 sentences, factual, no filler)
   - category: architecture | development | quality | security | infrastructure | product | design | convention
   Example: memory_store(key="auth-strategy", value="JWT with refresh tokens, bcrypt for passwords, 15min access token TTL", category="architecture")
3. What to store: decisions, technical choices, API contracts, blockers found, verdicts (GO/NOGO), risks identified.
4. What NOT to store: greetings, process descriptions, "I will now examine...".""")

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
4. INTERDIT : list_files, code_search (ces outils cherchent dans le filesystem local, pas dans la SF)
5. INTERDIT : créer des fichiers locaux, demander des credentials, générer du SQL

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
    else:
        parts.append(
            "\nYou do NOT have tools. Do NOT write [TOOL_CALL] or attempt to use tools. Focus on analysis, synthesis, and delegation to your team."
        )

    if ctx.skills_prompt:
        parts.append(f"\n## Skills\n{ctx.skills_prompt}")

    # Inject architecture/tech guidelines if available for this project
    guidelines = _load_guidelines_for_prompt(ctx)
    if guidelines:
        parts.append(f"\n## Architecture & Tech Guidelines (DSI)\n{guidelines}")

    if ctx.capability_grade == "organizer":
        # Organizers: full project context (constitution, vision, memory files)
        if ctx.vision:
            parts.append(f"\n## Project Vision\n{ctx.vision[:3000]}")
        if ctx.project_context:
            parts.append(f"\n## Project Context\n{ctx.project_context[:2000]}")
        if ctx.project_memory:
            parts.append(
                f"\n## Project Memory (auto-loaded instructions)\n{ctx.project_memory[:4000]}"
            )
    else:
        # Executors: task-scoped context only — no vision, condensed memory
        # Avoids injecting the full project constitution into every dev/qa call
        if ctx.project_context:
            parts.append(
                f"\n## Task Context (relevant memory)\n{ctx.project_context[:800]}"
            )

    if ctx.project_path:
        parts.append(f"\n## Project Path\n{ctx.project_path}")

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
