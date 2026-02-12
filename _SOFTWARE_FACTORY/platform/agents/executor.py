"""Agent Executor — runs an agent: receive message → think (LLM) → act → respond.

This is the runtime loop that makes agents actually work. It:
1. Builds the prompt (system + skills + memory + conversation)
2. Calls the LLM
3. Parses tool calls if any
4. Executes tools
5. Sends response back via MessageBus or returns it
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from ..llm.client import LLMClient, LLMMessage, LLMResponse, get_llm_client
from ..agents.store import AgentDef

logger = logging.getLogger(__name__)


@dataclass
class ExecutionContext:
    """Everything an agent needs to process a message."""
    agent: AgentDef
    session_id: str
    project_id: Optional[str] = None
    # Conversation history (recent messages for context window)
    history: list[dict] = field(default_factory=list)
    # Project memory snippets
    project_context: str = ""
    # Skills content (injected into system prompt)
    skills_prompt: str = ""
    # Vision document (if project has one)
    vision: str = ""


@dataclass
class ExecutionResult:
    """Result of running an agent on a message."""
    content: str
    agent_id: str
    model: str = ""
    provider: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: int = 0
    tool_calls: list[dict] = field(default_factory=list)
    delegations: list[dict] = field(default_factory=list)
    error: Optional[str] = None


class AgentExecutor:
    """Executes agent logic: prompt → LLM → response."""

    def __init__(self, llm: Optional[LLMClient] = None):
        self._llm = llm or get_llm_client()

    async def run(self, ctx: ExecutionContext, user_message: str) -> ExecutionResult:
        """Run the agent on a user message and return the response."""
        t0 = time.monotonic()
        agent = ctx.agent

        try:
            # Build system prompt
            system = self._build_system_prompt(ctx)

            # Build conversation messages
            messages = self._build_messages(ctx, user_message)

            # Call LLM
            llm_resp = await self._llm.chat(
                messages=messages,
                provider=agent.provider,
                model=agent.model,
                temperature=agent.temperature,
                max_tokens=agent.max_tokens,
                system_prompt=system,
            )

            elapsed = int((time.monotonic() - t0) * 1000)

            # Parse response for delegation markers
            content = llm_resp.content
            delegations = self._parse_delegations(content)

            return ExecutionResult(
                content=content,
                agent_id=agent.id,
                model=llm_resp.model,
                provider=llm_resp.provider,
                tokens_in=llm_resp.tokens_in,
                tokens_out=llm_resp.tokens_out,
                duration_ms=elapsed,
                delegations=delegations,
            )

        except Exception as exc:
            elapsed = int((time.monotonic() - t0) * 1000)
            logger.error("Agent %s execution failed: %s", agent.id, exc)
            return ExecutionResult(
                content=f"Error: {exc}",
                agent_id=agent.id,
                duration_ms=elapsed,
                error=str(exc),
            )

    def _build_system_prompt(self, ctx: ExecutionContext) -> str:
        """Compose the full system prompt from agent config + skills + context."""
        parts = []
        agent = ctx.agent

        # Base system prompt
        if agent.system_prompt:
            parts.append(agent.system_prompt)

        # Identity
        parts.append(f"\nYou are {agent.name}, role: {agent.role}.")
        if agent.description:
            parts.append(f"Description: {agent.description}")

        # Skills injection
        if ctx.skills_prompt:
            parts.append(f"\n## Skills\n{ctx.skills_prompt}")

        # Vision
        if ctx.vision:
            parts.append(f"\n## Project Vision\n{ctx.vision[:3000]}")

        # Project context
        if ctx.project_context:
            parts.append(f"\n## Project Context\n{ctx.project_context[:2000]}")

        # Permissions
        perms = agent.permissions or {}
        if perms.get("can_delegate"):
            parts.append("\nYou CAN delegate tasks to other agents by writing: [DELEGATE:agent_id] task description")
        if perms.get("can_veto"):
            parts.append("\nYou CAN veto decisions by writing: [VETO] reason")
        if perms.get("can_approve"):
            parts.append("\nYou CAN approve work by writing: [APPROVE] reason")

        return "\n".join(parts)

    def _build_messages(self, ctx: ExecutionContext, user_message: str) -> list[LLMMessage]:
        """Build the message list from conversation history."""
        messages = []

        # Recent history (sliding window)
        for h in ctx.history[-20:]:
            role = "assistant" if h.get("from_agent") != "user" else "user"
            name = h.get("from_agent")
            messages.append(LLMMessage(
                role=role,
                content=h.get("content", ""),
                name=name if name != "user" else None,
            ))

        # Current user message
        messages.append(LLMMessage(role="user", content=user_message))

        return messages

    def _parse_delegations(self, content: str) -> list[dict]:
        """Parse [DELEGATE:agent_id] markers from response."""
        delegations = []
        for line in content.split("\n"):
            if "[DELEGATE:" in line:
                try:
                    start = line.index("[DELEGATE:") + len("[DELEGATE:")
                    end = line.index("]", start)
                    agent_id = line[start:end]
                    task = line[end + 1:].strip()
                    delegations.append({"to_agent": agent_id, "task": task})
                except (ValueError, IndexError):
                    pass
        return delegations


# Singleton
_executor: Optional[AgentExecutor] = None


def get_executor() -> AgentExecutor:
    global _executor
    if _executor is None:
        _executor = AgentExecutor()
    return _executor
