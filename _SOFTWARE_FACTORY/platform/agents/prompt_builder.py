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
        if role_cat == "qa":
            parts.append("""
## QA Tools — E2E Testing with Playwright (IMPORTANT)
You MUST use Playwright MCP tools to verify the application visually:
1. First, start the dev server: build(command="npm run dev -- --port 4173 &")
2. Navigate: mcp_playwright_browser_navigate(url="http://localhost:4173")
3. Screenshot: mcp_playwright_browser_screenshot(name="homepage")
4. Inspect: mcp_playwright_browser_snapshot() → get accessibility tree
5. Interact: mcp_playwright_browser_click(element="Login button", ref="ref_from_snapshot")
6. Fill forms: mcp_playwright_browser_type(element="Email input", ref="ref", text="test@example.com")
7. Screenshot again: mcp_playwright_browser_screenshot(name="after-login")

EVERY QA validation MUST include at least:
- 1 screenshot of the main page
- 1 screenshot of a key user flow
- build(command="npm test") to run unit tests
Use create_ticket(title="...", severity="P2", description="...") for any bug found.""")
        elif role_cat == "security":
            parts.append("""
## Security Tools (IMPORTANT)
Run SAST scans on the codebase:
- build(command="bandit -r . -f json") for Python projects
- build(command="semgrep --config auto .") for any project
- build(command="npm audit") for Node.js projects
Report findings with severity ratings.""")
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
        parts.append(f"\n## Project Memory (auto-loaded instructions)\n{ctx.project_memory[:4000]}")

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
