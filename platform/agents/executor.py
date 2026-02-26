"""Agent Executor — runs an agent: receive message → think (LLM) → act → respond.

This is the runtime loop that makes agents actually work. It:
1. Builds the prompt (system + skills + memory + conversation)
2. Calls the LLM with tools definitions
3. If LLM returns tool_calls → execute tools → feed results back → repeat
4. When LLM returns text (no tool_calls) → done
5. Sends response back via MessageBus or returns it
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from ..agents.store import AgentDef
from ..llm.client import LLMClient, LLMMessage, LLMResponse, get_llm_client

logger = logging.getLogger(__name__)

# Max tool-calling rounds to prevent infinite loops
MAX_TOOL_ROUNDS = 8

# Regex to strip raw MiniMax/internal tool-call tokens from LLM output
_RAW_TOKEN_RE = re.compile(
    r"<\|(?:tool_calls_section_begin|tool_calls_section_end|tool_call_begin|tool_call_end|"
    r"tool_call_argument_begin|tool_call_argument_end|tool_sep|im_end|im_start)\|>"
)

# Provider for tool-calling agents (OpenAI models handle tools reliably)
_TOOL_PROVIDER = "azure-openai"
_TOOL_MODEL = "gpt-5-mini"
# Providers that support native function calling
_TOOL_CAPABLE_PROVIDERS = {"azure-openai", "azure-ai", "openai"}

# Multi-model routing — roles/tags → (provider, model)
# gpt-5.2:        deep reasoning — architecture, leadership, planning
# gpt-5.1-codex:  code production — developer, tester, security
# gpt-5.1-mini:   light tasks — routing, summaries, docs, discussion
_REASONING_ROLES = {
    "architect",
    "product_owner",
    "scrum_master",
    "tech_lead",
    "cto",
    "ceo",
}
_REASONING_TAGS = {
    "architecture",
    "reasoning",
    "leadership",
    "planning",
    "strategy",
    "analysis",
}
_CODE_ROLES = {
    "developer",
    "tester",
    "qa",
    "security",
    "devops",
    "data_engineer",
    "ml_engineer",
}
_CODE_TAGS = {
    "code",
    "coding",
    "test",
    "tests",
    "security",
    "refactor",
    "review",
    "ci",
    "cd",
    "devops",
}

# Cache for routing config loaded from DB
_routing_cache: dict | None = None
_routing_cache_ts: float = 0.0
_ROUTING_CACHE_TTL = 60.0  # 1 min


def _invalidate_routing_cache():
    global _routing_cache, _routing_cache_ts
    _routing_cache = None
    _routing_cache_ts = 0.0


def _load_routing_config() -> dict:
    """Load LLM routing config from DB (cached 60s)."""
    import time

    global _routing_cache, _routing_cache_ts
    now = time.time()
    if _routing_cache is not None and (now - _routing_cache_ts) < _ROUTING_CACHE_TTL:
        return _routing_cache
    try:
        from ..db.migrations import get_db
        import json

        db = get_db()
        row = db.execute(
            "SELECT value FROM session_state WHERE key='llm_routing'"
        ).fetchone()
        db.close()
        if row:
            _routing_cache = json.loads(row[0])
            _routing_cache_ts = now
            return _routing_cache
    except Exception:
        pass
    _routing_cache = {}
    return {}


def _select_model_for_agent(
    agent: "AgentDef",
    technology: str = "generic",
    phase_type: str = "generic",
    pattern_id: str = "",
    mission_id: str | None = None,
) -> tuple[str, str]:
    """Select (provider, model) using routing config + Darwin LLM Thompson Sampling.

    Priority:
    1. Darwin LLM Thompson Sampling (if multiple models tested for this agent×context)
    2. DB routing config (Settings → LLM tab)
    3. Hardcoded role/tag defaults
    Falls back to minimax on local dev (AZURE_DEPLOY unset).
    """
    import os

    if not os.environ.get("AZURE_DEPLOY", ""):
        return agent.provider, agent.model

    azure_ai_key = os.environ.get("AZURE_AI_API_KEY", "")
    role = (agent.role or "").lower().replace("-", "_").replace(" ", "_")
    tags = {t.lower() for t in (agent.tags or [])}

    # Determine task category from role/tags
    if role in _REASONING_ROLES or tags & _REASONING_TAGS:
        category_heavy, category_light = "reasoning_heavy", "reasoning_light"
    elif role in _CODE_ROLES or tags & _CODE_TAGS:
        category_heavy, category_light = "production_heavy", "production_light"
    else:
        category_heavy, category_light = "tasks_heavy", "tasks_light"

    # Load routing config from DB
    routing = _load_routing_config()
    heavy_cfg = routing.get(category_heavy, {})
    light_cfg = routing.get(category_light, {})

    # Build candidate models for Darwin LLM Thompson Sampling
    candidates: list[tuple[str, str]] = []
    if azure_ai_key:
        # Add both heavy and light candidates so Darwin can compare
        h_provider = heavy_cfg.get("provider", "azure-ai")
        h_model = heavy_cfg.get(
            "model",
            "gpt-5.2" if category_heavy == "reasoning_heavy" else "gpt-5.1-codex",
        )
        l_provider = light_cfg.get("provider", "azure-openai")
        l_model = light_cfg.get("model", "gpt-5-mini")
        candidates = [(h_model, h_provider), (l_model, l_provider)]
    else:
        candidates = [("gpt-5-mini", "azure-openai")]

    # Darwin LLM Thompson Sampling (if pattern_id available and Azure key present)
    if pattern_id and azure_ai_key and len(candidates) > 1:
        try:
            from ..patterns.team_selector import LLMTeamSelector

            model, provider = LLMTeamSelector.select_model(
                agent_id=agent.id,
                pattern_id=pattern_id,
                technology=technology,
                phase_type=phase_type,
                candidate_models=candidates,
                mission_id=mission_id,
            )
            if model and model != "default":
                return provider, model
        except Exception as exc:
            logger.debug("LLMTeamSelector.select_model error: %s", exc)

    # Fallback: use static routing config
    if heavy_cfg.get("provider") and azure_ai_key:
        return heavy_cfg["provider"], heavy_cfg.get("model", "gpt-5-mini")

    # Hardcoded defaults
    if role in _REASONING_ROLES or tags & _REASONING_TAGS:
        return (
            ("azure-ai", "gpt-5.2") if azure_ai_key else ("azure-openai", "gpt-5-mini")
        )
    if role in _CODE_ROLES or tags & _CODE_TAGS:
        return (
            ("azure-ai", "gpt-5.1-codex")
            if azure_ai_key
            else ("azure-openai", "gpt-5-mini")
        )
    return "azure-openai", "gpt-5-mini"


def _route_provider(
    agent: AgentDef,
    tools: list | None,
    technology: str = "generic",
    phase_type: str = "generic",
    pattern_id: str = "",
    mission_id: str | None = None,
) -> tuple[str, str]:
    """Route to the best provider+model using Darwin LLM Thompson Sampling + routing config.

    Priority:
    1. Darwin LLM Thompson Sampling (same team, competing models)
    2. DB routing config (Settings → LLM tab)
    3. Hardcoded role/tag defaults (gpt-5.2 / gpt-5.1-codex / gpt-5-mini)
    Overrides: tool-calling → must use _TOOL_CAPABLE_PROVIDERS; high rejection → escalate
    """
    best_provider, best_model = _select_model_for_agent(
        agent,
        technology=technology,
        phase_type=phase_type,
        pattern_id=pattern_id,
        mission_id=mission_id,
    )

    # Override: if tools required and selected provider can't do tool-calling, escalate
    if tools and best_provider not in _TOOL_CAPABLE_PROVIDERS:
        return _TOOL_PROVIDER, _TOOL_MODEL

    # Quality escalation: if agent has high rejection rate, use gpt-5-mini as floor
    if best_provider not in _TOOL_CAPABLE_PROVIDERS:
        try:
            from .selection import rejection_rate

            if rejection_rate(agent.id) > 0.40:
                logger.debug(
                    "Escalating %s to azure-openai (high rejection rate)", agent.id
                )
                return _TOOL_PROVIDER, _TOOL_MODEL
        except Exception:
            pass

    return best_provider, best_model


def _strip_raw_tokens(text: str) -> str:
    """Remove raw model tokens that leak into content (e.g. MiniMax format)."""
    if "<|" not in text:
        return text
    cleaned = _RAW_TOKEN_RE.sub("", text)
    # Also remove raw function call lines like "functions.code_read:0"
    cleaned = re.sub(r"^functions\.\w+:\d+$", "", cleaned, flags=re.MULTILINE)
    return cleaned.strip()


# Tool registry, schemas, execution — extracted to tool_runner.py
# Prompt building — extracted to prompt_builder.py
from .prompt_builder import (
    _build_messages,
    _build_system_prompt,
)
from .tool_runner import (
    _execute_tool,
    _get_tool_registry,
    _parse_xml_tool_calls,
    _record_artifact,
)

# Tool schemas, role mapping — from tool_schemas.py
from .tool_schemas import (
    _filter_schemas,
    _get_tool_schemas,
)


@dataclass
class ExecutionContext:
    """Everything an agent needs to process a message."""

    agent: AgentDef
    session_id: str
    project_id: str | None = None
    project_path: str | None = None  # filesystem path for tools
    # Conversation history (recent messages for context window)
    history: list[dict] = field(default_factory=list)
    # Project memory snippets
    project_context: str = ""
    # Project memory files (CLAUDE.md, copilot-instructions.md, etc.)
    project_memory: str = ""
    # Skills content (injected into system prompt)
    skills_prompt: str = ""
    # Vision document (if project has one)
    vision: str = ""
    # Enable tool-calling (default True)
    tools_enabled: bool = True
    # Filter tools by name — only these tools are available to the agent (None = all)
    allowed_tools: list[str] | None = None
    # Callback for SSE tool events
    on_tool_call: object | None = None  # async callable(tool_name, args, result)
    # Mission run ID (for CDP phase tools)
    mission_run_id: str | None = None


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
    error: str | None = None


class AgentExecutor:
    """Executes agent logic: prompt → LLM → tool loop → response."""

    def __init__(self, llm: LLMClient | None = None):
        self._llm = llm or get_llm_client()
        self._registry = _get_tool_registry()

    async def _push_mission_sse(self, session_id: str, event: dict):
        """Push SSE event for mission control updates."""
        from ..sessions.runner import _push_sse

        await _push_sse(session_id, event)

    async def run(self, ctx: ExecutionContext, user_message: str) -> ExecutionResult:
        """Run the agent with tool-calling loop."""
        t0 = time.monotonic()
        agent = ctx.agent
        total_tokens_in = 0
        total_tokens_out = 0
        all_tool_calls = []

        # ── Prompt injection guard ──
        try:
            from ..security.prompt_guard import get_prompt_guard

            user_message, inj_score = get_prompt_guard().check_and_sanitize(
                user_message, source=f"user→{agent.id}"
            )
            if inj_score.blocked:
                return ExecutionResult(
                    content=user_message,
                    agent_id=agent.id,
                    error="prompt_injection_blocked",
                )
        except ImportError:
            pass

        # Set trace context for observability
        self._llm.set_trace_context(
            agent_id=agent.id,
            session_id=ctx.session_id,
        )

        try:
            system = _build_system_prompt(ctx)
            messages = _build_messages(ctx, user_message)
            tools = (
                _filter_schemas(_get_tool_schemas(), ctx.allowed_tools)
                if ctx.tools_enabled
                else None
            )

            # Route provider: Darwin LLM Thompson Sampling + routing config
            use_provider, use_model = _route_provider(
                agent, tools, mission_id=ctx.mission_run_id
            )

            # Tool-calling loop
            deep_search_used = False
            for round_num in range(MAX_TOOL_ROUNDS):
                llm_resp = await self._llm.chat(
                    messages=messages,
                    provider=use_provider,
                    model=use_model,
                    temperature=agent.temperature,
                    max_tokens=agent.max_tokens,
                    system_prompt=system if round_num == 0 else "",
                    tools=tools,
                )

                total_tokens_in += llm_resp.tokens_in
                total_tokens_out += llm_resp.tokens_out

                # Parse XML tool calls from content (MiniMax sometimes returns these)
                if not llm_resp.tool_calls and llm_resp.content:
                    xml_tcs = _parse_xml_tool_calls(llm_resp.content)
                    if xml_tcs:
                        llm_resp = LLMResponse(
                            content="",
                            model=llm_resp.model,
                            provider=llm_resp.provider,
                            tokens_in=llm_resp.tokens_in,
                            tokens_out=llm_resp.tokens_out,
                            duration_ms=llm_resp.duration_ms,
                            finish_reason="tool_calls",
                            tool_calls=xml_tcs,
                        )

                # No tool calls → final response
                if not llm_resp.tool_calls:
                    content = llm_resp.content
                    break

                # Process tool calls
                # Add assistant message with tool_calls to conversation
                tc_msg_data = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function_name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in llm_resp.tool_calls
                ]

                messages.append(
                    LLMMessage(
                        role="assistant",
                        content=llm_resp.content or "",
                        tool_calls=tc_msg_data,
                    )
                )

                for tc in llm_resp.tool_calls:
                    result = await _execute_tool(tc, ctx, self._registry, self._llm)
                    all_tool_calls.append(
                        {
                            "name": tc.function_name,
                            "args": tc.arguments,
                            "result": result[:500],  # truncate for storage
                        }
                    )

                    if tc.function_name == "deep_search":
                        deep_search_used = True

                    # Track code changes as artifacts
                    if tc.function_name in (
                        "code_write",
                        "code_edit",
                    ) and not result.startswith("Error"):
                        try:
                            _record_artifact(ctx, tc, result)
                        except Exception:
                            pass

                    # Notify UI via callback
                    if ctx.on_tool_call:
                        try:
                            await ctx.on_tool_call(
                                tc.function_name, tc.arguments, result
                            )
                        except Exception:
                            pass

                    # Add tool result to conversation (truncate to keep memory bounded)
                    messages.append(
                        LLMMessage(
                            role="tool",
                            content=result[:2000],
                            tool_call_id=tc.id,
                            name=tc.function_name,
                        )
                    )

                # After deep_search, disable tools to force synthesis
                if deep_search_used:
                    tools = None
                    # Notify: agent is now synthesizing
                    if ctx.on_tool_call:
                        try:
                            await ctx.on_tool_call(
                                "deep_search", {"status": "Generating response…"}, ""
                            )
                        except Exception:
                            pass

                logger.info(
                    "Agent %s tool round %d: %d calls",
                    agent.id,
                    round_num + 1,
                    len(llm_resp.tool_calls),
                )

                # Limit message window to prevent OOM (keep first 2 + last 15)
                if len(messages) > 20:
                    tail = messages[-15:]
                    # Don't start tail with orphaned tool results
                    while tail and getattr(tail[0], "role", "") == "tool":
                        tail = tail[1:]
                    messages = messages[:2] + tail

                # On penultimate round, disable tools to force synthesis next iteration
                if round_num >= MAX_TOOL_ROUNDS - 2 and tools is not None:
                    tools = None
                    messages.append(
                        LLMMessage(
                            role="system",
                            content="You have used many tool calls. Now synthesize your findings and respond to the user. Do not call more tools.",
                        )
                    )
            else:
                content = llm_resp.content or "(Max tool rounds reached)"

            elapsed = int((time.monotonic() - t0) * 1000)
            # Strip raw MiniMax tool-call tokens that leak into content
            content = _strip_raw_tokens(content)
            # Strip <think> blocks (MiniMax chain-of-thought) from stored content
            content = re.sub(r"<think>[\s\S]*?</think>\s*", "", content).strip()
            if "<think>" in content and "</think>" not in content:
                content = content[: content.index("<think>")].strip()
            delegations = self._parse_delegations(content)

            return ExecutionResult(
                content=content,
                agent_id=agent.id,
                model=llm_resp.model,
                provider=llm_resp.provider,
                tokens_in=total_tokens_in,
                tokens_out=total_tokens_out,
                duration_ms=elapsed,
                tool_calls=all_tool_calls,
                delegations=delegations,
            )

        except Exception as exc:
            err_str = str(exc)
            is_llm_error = (
                "All LLM providers failed" in err_str or "rate" in err_str.lower()
            )
            # Retry once with backoff for transient LLM errors
            if is_llm_error and not getattr(ctx, "_retried", False):
                ctx._retried = True  # type: ignore[attr-defined]
                wait = 30 + (time.monotonic() % 30)  # 30-60s jittered backoff
                logger.warning(
                    "Agent %s LLM error, retrying in %ds: %s",
                    agent.id,
                    int(wait),
                    err_str[:100],
                )
                await asyncio.sleep(wait)
                return await self.run(ctx, user_message)
            elapsed = int((time.monotonic() - t0) * 1000)
            logger.error("Agent %s execution failed: %s", agent.id, exc, exc_info=True)
            return ExecutionResult(
                content=f"Error: {exc}",
                agent_id=agent.id,
                duration_ms=elapsed,
                error=str(exc),
            )

    async def run_streaming(
        self, ctx: ExecutionContext, user_message: str
    ) -> AsyncIterator[tuple[str, str | ExecutionResult]]:
        """Run agent with streaming — yields ("delta", text) chunks then ("result", ExecutionResult).

        For agents without tools: streams the entire response token-by-token.
        For agents with tools: runs tool rounds non-streaming, then streams final response.
        """
        t0 = time.monotonic()
        agent = ctx.agent
        total_tokens_in = 0
        total_tokens_out = 0
        all_tool_calls = []

        # ── Prompt injection guard ──
        try:
            from ..security.prompt_guard import get_prompt_guard

            user_message, inj_score = get_prompt_guard().check_and_sanitize(
                user_message, source=f"user→{agent.id}"
            )
            if inj_score.blocked:
                result = ExecutionResult(
                    content=user_message,
                    agent_id=agent.id,
                    error="prompt_injection_blocked",
                )
                yield ("result", result)
                return
        except ImportError:
            pass

        # Set trace context for observability
        self._llm.set_trace_context(
            agent_id=agent.id,
            session_id=ctx.session_id,
        )

        try:
            system = _build_system_prompt(ctx)
            messages = _build_messages(ctx, user_message)
            tools = (
                _filter_schemas(_get_tool_schemas(), ctx.allowed_tools)
                if ctx.tools_enabled
                else None
            )

            # Tool-calling rounds (non-streaming) — same as run()
            deep_search_used = False
            final_content = ""
            logger.warning(
                "Agent %s: tools_enabled=%s, tools=%s, allowed=%s",
                agent.id,
                ctx.tools_enabled,
                "YES" if tools else "NO",
                ctx.allowed_tools[:3] if ctx.allowed_tools else "all",
            )

            # Route provider: Darwin LLM Thompson Sampling + routing config
            use_provider, use_model = _route_provider(
                agent, tools, mission_id=ctx.mission_run_id
            )

            for round_num in range(MAX_TOOL_ROUNDS):
                is_last_possible = (round_num >= MAX_TOOL_ROUNDS - 1) or tools is None

                # On last round or no tools: use streaming
                if is_last_possible or not ctx.tools_enabled:
                    # Stream the final response — buffer to strip <think> blocks first
                    accumulated = ""
                    async for chunk in self._llm.stream(
                        messages=messages,
                        provider=use_provider,
                        model=use_model,
                        temperature=agent.temperature,
                        max_tokens=agent.max_tokens,
                        system_prompt=system if round_num == 0 else "",
                    ):
                        if chunk.delta:
                            accumulated += chunk.delta
                        if chunk.done:
                            break
                    # Strip <think> blocks (MiniMax chain-of-thought) before streaming to client
                    import re as _re_str

                    accumulated = _re_str.sub(
                        r"<think>[\s\S]*?</think>\s*", "", accumulated
                    ).strip()
                    if "<think>" in accumulated and "</think>" not in accumulated:
                        accumulated = accumulated[
                            : accumulated.index("<think>")
                        ].strip()
                    # Re-emit in small chunks for streaming UX
                    chunk_size = 8
                    for ci in range(0, len(accumulated), chunk_size):
                        yield ("delta", accumulated[ci : ci + chunk_size])
                        await asyncio.sleep(0.02)
                    final_content = accumulated
                    break

                # Non-streaming tool round
                llm_resp = await self._llm.chat(
                    messages=messages,
                    provider=use_provider,
                    model=use_model,
                    temperature=agent.temperature,
                    max_tokens=agent.max_tokens,
                    system_prompt=system if round_num == 0 else "",
                    tools=tools,
                )

                total_tokens_in += llm_resp.tokens_in
                total_tokens_out += llm_resp.tokens_out
                logger.warning(
                    "TOOL_DBG agent=%s round=%d tc=%d clen=%d fin=%s",
                    agent.id,
                    round_num,
                    len(llm_resp.tool_calls),
                    len(llm_resp.content or ""),
                    llm_resp.finish_reason,
                )

                # Parse XML tool calls
                if not llm_resp.tool_calls and llm_resp.content:
                    xml_tcs = _parse_xml_tool_calls(llm_resp.content)
                    if xml_tcs:
                        llm_resp = LLMResponse(
                            content="",
                            model=llm_resp.model,
                            provider=llm_resp.provider,
                            tokens_in=llm_resp.tokens_in,
                            tokens_out=llm_resp.tokens_out,
                            duration_ms=llm_resp.duration_ms,
                            finish_reason="tool_calls",
                            tool_calls=xml_tcs,
                        )

                # No tool calls → stream remaining content in chunks
                if not llm_resp.tool_calls:
                    final_content = llm_resp.content or ""
                    # Strip <think> blocks before chunking (tags would split across chunks)
                    import re as _re_exec

                    final_content = _re_exec.sub(
                        r"<think>[\s\S]*?</think>\s*", "", final_content
                    ).strip()
                    # Also strip unclosed <think> at the end
                    if "<think>" in final_content and "</think>" not in final_content:
                        final_content = final_content[
                            : final_content.index("<think>")
                        ].strip()
                    # Strip tool call artifacts
                    final_content = _re_exec.sub(
                        r"<minimax:tool_call>[\s\S]*?</minimax:tool_call>\s*",
                        "",
                        final_content,
                    ).strip()
                    final_content = _re_exec.sub(
                        r"<tool_call>[\s\S]*?</tool_call>\s*", "", final_content
                    ).strip()
                    if final_content:
                        # Emit in word-sized chunks for natural streaming UX
                        chunk_size = 8
                        for ci in range(0, len(final_content), chunk_size):
                            yield ("delta", final_content[ci : ci + chunk_size])
                            await asyncio.sleep(0.03)
                    break

                # Process tool calls (same as run())
                tc_msg_data = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function_name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in llm_resp.tool_calls
                ]

                messages.append(
                    LLMMessage(
                        role="assistant",
                        content=llm_resp.content or "",
                        tool_calls=tc_msg_data,
                    )
                )

                for tc in llm_resp.tool_calls:
                    yield ("tool", tc.function_name)
                    result = await _execute_tool(tc, ctx, self._registry, self._llm)
                    logger.warning(
                        "TOOL_EXEC agent=%s tool=%s args=%s result=%s",
                        agent.id,
                        tc.function_name,
                        str(tc.arguments)[:200],
                        result[:200],
                    )
                    all_tool_calls.append(
                        {
                            "name": tc.function_name,
                            "args": tc.arguments,
                            "result": result[:500],
                        }
                    )
                    # Persist tool call to DB for monitoring
                    try:
                        from ..db.migrations import get_db

                        db = get_db()
                        db.execute(
                            "INSERT INTO tool_calls (agent_id, session_id, tool_name, parameters_json, result_json, success, timestamp) "
                            "VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
                            (
                                agent.id,
                                ctx.session_id,
                                tc.function_name,
                                str(tc.arguments)[:1000],
                                result[:1000],
                                1
                                if not result.startswith(
                                    ("Error", "LRM error", "MCP error")
                                )
                                else 0,
                            ),
                        )
                        db.commit()
                    except Exception:
                        pass
                    if tc.function_name == "deep_search":
                        deep_search_used = True
                    if ctx.on_tool_call:
                        try:
                            await ctx.on_tool_call(
                                tc.function_name, tc.arguments, result
                            )
                        except Exception:
                            pass
                    messages.append(
                        LLMMessage(
                            role="tool",
                            content=result[:2000],
                            tool_call_id=tc.id,
                            name=tc.function_name,
                        )
                    )

                # Limit message window to prevent OOM
                if len(messages) > 20:
                    tail = messages[-15:]
                    # Don't start tail with orphaned tool results
                    while tail and getattr(tail[0], "role", "") == "tool":
                        tail = tail[1:]
                    messages = messages[:2] + tail

                if deep_search_used:
                    tools = None
                # Nudge: if round 2+ and no code_write yet, inject urgent reminder
                # Only nudge if write tools are available (not for read-only contexts like CDP chat)
                write_count = sum(
                    1
                    for tc_rec in all_tool_calls
                    if tc_rec["name"] in ("code_write", "code_edit", "fractal_code")
                )
                has_written = write_count > 0
                has_write_tools = any(
                    t.get("function", {}).get("name")
                    in ("code_write", "code_edit", "fractal_code")
                    for t in (tools or [])
                )
                if (
                    round_num >= 1
                    and not has_written
                    and tools is not None
                    and has_write_tools
                ):
                    # Strip read-only tools — force write
                    write_only_tools = [
                        t
                        for t in tools
                        if t.get("function", {}).get("name")
                        in ("code_write", "code_edit", "fractal_code", "git_commit")
                    ]
                    if write_only_tools:
                        tools = write_only_tools
                    messages.append(
                        LLMMessage(
                            role="system",
                            content="⚠️ STOP reading. Call code_write NOW.\n"
                            'code_write(path="src/index.ts", content="// your code here\\n...")',
                        )
                    )
                elif (
                    round_num >= 2
                    and has_written
                    and write_count < 2
                    and tools is not None
                ):
                    messages.append(
                        LLMMessage(
                            role="system",
                            content="⚠️ 1 file written. Call code_write for remaining files.",
                        )
                    )
                if round_num >= MAX_TOOL_ROUNDS - 2 and tools is not None:
                    if has_written:
                        tools = None
                        messages.append(
                            LLMMessage(
                                role="system", content="Tools done. Summarize changes."
                            )
                        )
                    # else: keep write-only tools — agent MUST write code
            else:
                final_content = final_content or "(Max tool rounds reached)"

            elapsed = int((time.monotonic() - t0) * 1000)
            final_content = _strip_raw_tokens(final_content)
            delegations = self._parse_delegations(final_content)

            yield (
                "result",
                ExecutionResult(
                    content=final_content,
                    agent_id=agent.id,
                    model=use_model,
                    provider=use_provider,
                    tokens_in=total_tokens_in,
                    tokens_out=total_tokens_out,
                    duration_ms=elapsed,
                    tool_calls=all_tool_calls,
                    delegations=delegations,
                ),
            )

        except Exception as exc:
            err_str = str(exc)
            is_llm_error = (
                "All LLM providers failed" in err_str or "rate" in err_str.lower()
            )
            # Retry once with backoff for transient LLM errors
            if is_llm_error and not getattr(ctx, "_stream_retried", False):
                ctx._stream_retried = True  # type: ignore[attr-defined]
                wait = 30 + (time.monotonic() % 30)
                logger.warning(
                    "Agent %s streaming LLM error, retrying in %ds: %s",
                    agent.id,
                    int(wait),
                    err_str[:100],
                )
                await asyncio.sleep(wait)
                async for item in self.run_streaming(ctx, user_message):
                    yield item
                return
            elapsed = int((time.monotonic() - t0) * 1000)
            logger.error("Agent %s streaming failed: %s", agent.id, exc, exc_info=True)
            yield (
                "result",
                ExecutionResult(
                    content=f"Error: {exc}",
                    agent_id=agent.id,
                    duration_ms=elapsed,
                    error=str(exc),
                ),
            )

    def _parse_delegations(self, content: str) -> list[dict]:
        """Parse [DELEGATE:agent_id] markers from response."""
        delegations = []
        for line in content.split("\n"):
            if "[DELEGATE:" in line:
                try:
                    start = line.index("[DELEGATE:") + len("[DELEGATE:")
                    end = line.index("]", start)
                    agent_id = line[start:end]
                    task = line[end + 1 :].strip()
                    delegations.append({"to_agent": agent_id, "task": task})
                except (ValueError, IndexError):
                    pass
        return delegations


# Singleton
_executor: AgentExecutor | None = None


def get_executor() -> AgentExecutor:
    global _executor
    if _executor is None:
        _executor = AgentExecutor()
    return _executor
