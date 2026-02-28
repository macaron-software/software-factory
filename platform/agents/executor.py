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
from .prompt_builder import _build_messages, _build_system_prompt
from .routing import _route_provider, _strip_raw_tokens
from .tool_runner import (
    _execute_tool,
    _get_tool_registry,
    _parse_xml_tool_calls,
    _record_artifact,
)
from .tool_schemas import _filter_schemas, _get_tool_schemas

logger = logging.getLogger(__name__)

# Max tool-calling rounds to prevent infinite loops
MAX_TOOL_ROUNDS = 8

# Tools that produce code changes and should trigger auto-verification
_CODE_WRITE_TOOLS = frozenset({"code_write", "code_edit", "code_create"})
# Max automatic repair rounds after a failed verification (lint/build)
MAX_REPAIR_ROUNDS = 3

# Secrets detection patterns (block hardcoded credentials in code writes)
import re as _re_secrets

_SECRET_PATTERNS = [
    _re_secrets.compile(
        r'(?i)(api[_\-]?key|apikey|api[_\-]?secret)\s*[=:]\s*["\']?[A-Za-z0-9+/]{20,}'
    ),
    _re_secrets.compile(r'(?i)(password|passwd|pwd)\s*[=:]\s*["\'][^"\']{6,}["\']'),
    _re_secrets.compile(r'(?i)(secret[_\-]?key|secret)\s*[=:]\s*["\'][^"\']{8,}["\']'),
    _re_secrets.compile(
        r'(?i)(aws_access_key_id|aws_secret)\s*[=:]\s*["\']?[A-Z0-9]{16,}'
    ),
    _re_secrets.compile(r"sk-[A-Za-z0-9\-]{20,}"),  # OpenAI-style key (sk- or sk-proj-)
    _re_secrets.compile(r"ghp_[A-Za-z0-9]{36,}"),  # GitHub personal access token
]


def _scan_for_secrets(content: str) -> list[str]:
    """Return list of secret pattern matches found in content."""
    hits = []
    for pat in _SECRET_PATTERNS:
        m = pat.search(content)
        if m:
            hits.append(m.group(0)[:40] + "…")
    return hits


_routing_cache: dict | None = None
_routing_cache_ts: float = 0.0


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
    # Domain context (injected from projects/domains/<id>.yaml)
    domain_context: str = ""
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
    # Uruk capability grade: 'organizer' (full context) or 'executor' (task-scoped)
    capability_grade: str = "executor"


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

    @staticmethod
    def _write_step_checkpoint(
        session_id: str,
        agent_id: str,
        step_index: int,
        tool_calls: list[dict],
        partial_content: str,
    ) -> None:
        """Persist a step checkpoint after each tool-call round.

        Enables crash recovery: if the agent crashes mid-run, the control plane
        can see how far it got and restart from the last completed step.
        Inspired by the Uruk stateless model (Orthanc ADR-0014).
        """
        try:
            import json as _json
            from ..db.migrations import get_db

            db = get_db()
            db.execute(
                """CREATE TABLE IF NOT EXISTS agent_step_checkpoints (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    step_index INTEGER NOT NULL,
                    tool_calls TEXT NOT NULL,
                    partial_content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            db.execute(
                """INSERT OR REPLACE INTO agent_step_checkpoints
                   (id, session_id, agent_id, step_index, tool_calls, partial_content)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    f"{session_id}:{agent_id}:{step_index}",
                    session_id,
                    agent_id,
                    step_index,
                    _json.dumps(tool_calls[-5:]),  # keep last 5 tool calls only
                    partial_content[:500] if partial_content else "",
                ),
            )
            db.commit()
            db.close()
        except Exception:
            pass  # checkpointing is best-effort, never block execution

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

                    # ── Auto-verification: after code writes, run lint and repair if needed ──
                    if (
                        tc.function_name in _CODE_WRITE_TOOLS
                        and not result.startswith("Error")
                        and ctx.project_path
                    ):
                        # Secrets scan: block if hardcoded secrets detected
                        _secret_content = str(tc.arguments.get("content", ""))
                        _secrets_found = _scan_for_secrets(_secret_content)
                        if _secrets_found:
                            logger.warning(
                                "Agent %s: SECRETS DETECTED in code_write: %s",
                                agent.id,
                                _secrets_found,
                            )
                            messages.append(
                                LLMMessage(
                                    role="system",
                                    content=(
                                        "🚨 SECURITY ALERT: Hardcoded secrets detected in your last code_write. "
                                        f"Found: {_secrets_found[:3]}. "
                                        "Remove ALL hardcoded credentials immediately. Use environment variables instead."
                                    ),
                                )
                            )

                        for _repair_round in range(MAX_REPAIR_ROUNDS):
                            try:
                                lint_tool = self._registry.get("lint")
                                if lint_tool is None:
                                    break
                                lint_result = await lint_tool.execute(
                                    {"cwd": ctx.project_path, "fix": False}, agent
                                )
                                if ctx.on_tool_call:
                                    try:
                                        await ctx.on_tool_call(
                                            "lint",
                                            {"cwd": ctx.project_path},
                                            lint_result,
                                        )
                                    except Exception:
                                        pass
                                # No errors → stop repair loop
                                if (
                                    "error" not in lint_result.lower()
                                    and "warning" not in lint_result.lower()[:100]
                                ):
                                    break
                                # Lint found issues → inject repair instruction
                                import uuid as _uuid

                                repair_id = f"auto_lint_{_uuid.uuid4().hex[:6]}"
                                messages.append(
                                    LLMMessage(
                                        role="tool",
                                        content=f"[AUTO-LINT] {lint_result[:1500]}",
                                        tool_call_id=repair_id,
                                        name="lint",
                                    )
                                )
                                messages.append(
                                    LLMMessage(
                                        role="system",
                                        content=(
                                            "⚠️ Lint/verification failed (see AUTO-LINT above). "
                                            "Fix all reported issues NOW before proceeding to the next step. "
                                            f"Repair round {_repair_round + 1}/{MAX_REPAIR_ROUNDS}."
                                        ),
                                    )
                                )
                                logger.info(
                                    "Agent %s: lint failed, repair round %d",
                                    agent.id,
                                    _repair_round + 1,
                                )
                                # Allow LLM to fix — fire one more tool round immediately
                                fix_resp = await self._llm.chat(
                                    messages=messages,
                                    provider=use_provider,
                                    model=use_model,
                                    temperature=agent.temperature,
                                    max_tokens=agent.max_tokens,
                                    system_prompt="",
                                    tools=tools,
                                )
                                total_tokens_in += fix_resp.tokens_in
                                total_tokens_out += fix_resp.tokens_out
                                if not fix_resp.tool_calls:
                                    break
                                for fix_tc in fix_resp.tool_calls:
                                    fix_res = await _execute_tool(
                                        fix_tc, ctx, self._registry, self._llm
                                    )
                                    all_tool_calls.append(
                                        {
                                            "name": fix_tc.function_name,
                                            "args": fix_tc.arguments,
                                            "result": fix_res[:500],
                                        }
                                    )
                                    messages.append(
                                        LLMMessage(
                                            role="tool",
                                            content=fix_res[:2000],
                                            tool_call_id=fix_tc.id,
                                            name=fix_tc.function_name,
                                        )
                                    )
                            except Exception as _ve:
                                logger.warning("Auto-verify error: %s", _ve)
                                break

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

                # Step checkpoint: persist progress after each tool round
                # so crash recovery can see how far this agent got
                self._write_step_checkpoint(
                    session_id=ctx.session_id,
                    agent_id=agent.id,
                    step_index=round_num,
                    tool_calls=all_tool_calls,
                    partial_content="",
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

                    # ── Auto-verification (streaming): after code writes, run lint ──
                    if (
                        tc.function_name in _CODE_WRITE_TOOLS
                        and not result.startswith("Error")
                        and ctx.project_path
                    ):
                        # Secrets scan
                        _ss_content = str(tc.arguments.get("content", ""))
                        _ss_hits = _scan_for_secrets(_ss_content)
                        if _ss_hits:
                            logger.warning(
                                "Agent %s (streaming): SECRETS DETECTED: %s",
                                agent.id,
                                _ss_hits,
                            )
                            messages.append(
                                LLMMessage(
                                    role="system",
                                    content=(
                                        "🚨 SECURITY ALERT: Hardcoded secrets detected in your last code_write. "
                                        f"Found: {_ss_hits[:3]}. Use environment variables instead."
                                    ),
                                )
                            )
                        for _srep in range(MAX_REPAIR_ROUNDS):
                            try:
                                _slint = self._registry.get("lint")
                                if _slint is None:
                                    break
                                _slint_res = await _slint.execute(
                                    {"cwd": ctx.project_path, "fix": False}, agent
                                )
                                if ctx.on_tool_call:
                                    try:
                                        await ctx.on_tool_call(
                                            "lint",
                                            {"cwd": ctx.project_path},
                                            _slint_res,
                                        )
                                    except Exception:
                                        pass
                                if (
                                    "error" not in _slint_res.lower()
                                    and "warning" not in _slint_res.lower()[:100]
                                ):
                                    break
                                import uuid as _uuid_s

                                _srid = f"auto_lint_{_uuid_s.uuid4().hex[:6]}"
                                messages.append(
                                    LLMMessage(
                                        role="tool",
                                        content=f"[AUTO-LINT] {_slint_res[:1500]}",
                                        tool_call_id=_srid,
                                        name="lint",
                                    )
                                )
                                messages.append(
                                    LLMMessage(
                                        role="system",
                                        content=(
                                            "⚠️ Lint/verification failed (see AUTO-LINT above). "
                                            f"Fix all reported issues NOW. Repair round {_srep + 1}/{MAX_REPAIR_ROUNDS}."
                                        ),
                                    )
                                )
                                logger.info(
                                    "Agent %s (streaming): lint failed, repair round %d",
                                    agent.id,
                                    _srep + 1,
                                )
                                _sfix = await self._llm.chat(
                                    messages=messages,
                                    provider=use_provider,
                                    model=use_model,
                                    temperature=agent.temperature,
                                    max_tokens=agent.max_tokens,
                                    system_prompt="",
                                    tools=tools,
                                )
                                total_tokens_in += _sfix.tokens_in
                                total_tokens_out += _sfix.tokens_out
                                if not _sfix.tool_calls:
                                    break
                                for _stc in _sfix.tool_calls:
                                    _sres = await _execute_tool(
                                        _stc, ctx, self._registry, self._llm
                                    )
                                    all_tool_calls.append(
                                        {
                                            "name": _stc.function_name,
                                            "args": _stc.arguments,
                                            "result": _sres[:500],
                                        }
                                    )
                                    messages.append(
                                        LLMMessage(
                                            role="tool",
                                            content=_sres[:2000],
                                            tool_call_id=_stc.id,
                                            name=_stc.function_name,
                                        )
                                    )
                            except Exception as _sve:
                                logger.warning(
                                    "Auto-verify (streaming) error: %s", _sve
                                )
                                break

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
