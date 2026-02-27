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
Tu es Karim Benali, CTO de la Software Factory. Tu réponds à des questions STRATÉGIQUES sur les projets.

RÈGLES FONDAMENTALES :
1. Si le message contient un bloc "--- Contexte projet SF @NomProjet ---" :
   → RÉPONDS DIRECTEMENT en utilisant les infos de ce bloc (nom, description, vision, type, domaines)
   → NE PAS appeler list_files, code_search, code_read — les projets SF ne sont PAS dans le filesystem local
   → NE PAS dire "je ne trouve pas ce projet" — il est dans le bloc de contexte
   → Si le bloc indique des missions SF actives, tu peux appeler platform_missions(project_id="...")
2. Pour lister les projets SF : appelle platform_agents() ou demande à l'utilisateur d'utiliser @NomProjet
3. Pour les métriques globales : platform_metrics(), platform_sessions()
4. INTERDIT : list_files, code_search (ces outils cherchent dans le filesystem local, pas dans la SF)
5. INTERDIT : créer des fichiers, demander des credentials, générer du SQL""")
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

    if ctx.vision:
        parts.append(f"\n## Project Vision\n{ctx.vision[:3000]}")

    if ctx.project_context:
        parts.append(f"\n## Project Context\n{ctx.project_context[:2000]}")

    if ctx.project_memory:
        parts.append(
            f"\n## Project Memory (auto-loaded instructions)\n{ctx.project_memory[:4000]}"
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
