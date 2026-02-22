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
import os
import re
import time
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

from ..llm.client import LLMClient, LLMMessage, LLMResponse, LLMToolCall, get_llm_client
from ..agents.store import AgentDef

logger = logging.getLogger(__name__)

# Max tool-calling rounds to prevent infinite loops
MAX_TOOL_ROUNDS = 8

# Regex to strip raw MiniMax/internal tool-call tokens from LLM output
_RAW_TOKEN_RE = re.compile(
    r'<\|(?:tool_calls_section_begin|tool_calls_section_end|tool_call_begin|tool_call_end|'
    r'tool_call_argument_begin|tool_call_argument_end|tool_sep|im_end|im_start)\|>'
)

def _strip_raw_tokens(text: str) -> str:
    """Remove raw model tokens that leak into content (e.g. MiniMax format)."""
    if '<|' not in text:
        return text
    cleaned = _RAW_TOKEN_RE.sub('', text)
    # Also remove raw function call lines like "functions.code_read:0"
    cleaned = re.sub(r'^functions\.\w+:\d+$', '', cleaned, flags=re.MULTILINE)
    return cleaned.strip()


# Tool registry, schemas, execution — extracted to tool_runner.py
from .tool_runner import (
    _get_tool_registry,
    _execute_tool,
    _parse_xml_tool_calls,
    _record_artifact,
)

# Tool schemas, role mapping — from tool_schemas.py
from .tool_schemas import (
    _get_tool_schemas,
    ROLE_TOOL_MAP,
    _classify_agent_role,
    _get_tools_for_agent,
    _filter_schemas,
)

# Prompt building — extracted to prompt_builder.py
from .prompt_builder import (
    _build_system_prompt,
    _build_messages,
)



@dataclass
class ExecutionContext:
    """Everything an agent needs to process a message."""
    agent: AgentDef
    session_id: str
    project_id: Optional[str] = None
    project_path: Optional[str] = None  # filesystem path for tools
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
    allowed_tools: Optional[list[str]] = None
    # Callback for SSE tool events
    on_tool_call: Optional[object] = None  # async callable(tool_name, args, result)
    # Mission run ID (for CDP phase tools)
    mission_run_id: Optional[str] = None


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
    """Executes agent logic: prompt → LLM → tool loop → response."""

    def __init__(self, llm: Optional[LLMClient] = None):
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
            tools = _filter_schemas(_get_tool_schemas(), ctx.allowed_tools) if ctx.tools_enabled else None

            # Tool-calling loop
            deep_search_used = False
            for round_num in range(MAX_TOOL_ROUNDS):
                llm_resp = await self._llm.chat(
                    messages=messages,
                    provider=agent.provider,
                    model=agent.model,
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
                            content="", model=llm_resp.model, provider=llm_resp.provider,
                            tokens_in=llm_resp.tokens_in, tokens_out=llm_resp.tokens_out,
                            duration_ms=llm_resp.duration_ms, finish_reason="tool_calls",
                            tool_calls=xml_tcs,
                        )

                # No tool calls → final response
                if not llm_resp.tool_calls:
                    content = llm_resp.content
                    break

                # Process tool calls
                # Add assistant message with tool_calls to conversation
                tc_msg_data = [{
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function_name, "arguments": json.dumps(tc.arguments)},
                } for tc in llm_resp.tool_calls]

                messages.append(LLMMessage(
                    role="assistant",
                    content=llm_resp.content or "",
                    tool_calls=tc_msg_data,
                ))

                for tc in llm_resp.tool_calls:
                    result = await _execute_tool(tc, ctx, self._registry, self._llm)
                    all_tool_calls.append({
                        "name": tc.function_name,
                        "args": tc.arguments,
                        "result": result[:500],  # truncate for storage
                    })

                    if tc.function_name == "deep_search":
                        deep_search_used = True

                    # Track code changes as artifacts
                    if tc.function_name in ("code_write", "code_edit") and not result.startswith("Error"):
                        try:
                            _record_artifact(ctx, tc, result)
                        except Exception:
                            pass

                    # Notify UI via callback
                    if ctx.on_tool_call:
                        try:
                            await ctx.on_tool_call(tc.function_name, tc.arguments, result)
                        except Exception:
                            pass

                    # Add tool result to conversation (truncate to keep memory bounded)
                    messages.append(LLMMessage(
                        role="tool",
                        content=result[:2000],
                        tool_call_id=tc.id,
                        name=tc.function_name,
                    ))

                # After deep_search, disable tools to force synthesis
                if deep_search_used:
                    tools = None
                    # Notify: agent is now synthesizing
                    if ctx.on_tool_call:
                        try:
                            await ctx.on_tool_call("deep_search", {"status": "Generating response…"}, "")
                        except Exception:
                            pass

                logger.info("Agent %s tool round %d: %d calls", agent.id, round_num + 1,
                            len(llm_resp.tool_calls))

                # Limit message window to prevent OOM (keep first 2 + last 15)
                if len(messages) > 20:
                    tail = messages[-15:]
                    # Don't start tail with orphaned tool results
                    while tail and getattr(tail[0], 'role', '') == 'tool':
                        tail = tail[1:]
                    messages = messages[:2] + tail

                # On penultimate round, disable tools to force synthesis next iteration
                if round_num >= MAX_TOOL_ROUNDS - 2 and tools is not None:
                    tools = None
                    messages.append(LLMMessage(
                        role="system",
                        content="You have used many tool calls. Now synthesize your findings and respond to the user. Do not call more tools.",
                    ))
            else:
                content = llm_resp.content or "(Max tool rounds reached)"

            elapsed = int((time.monotonic() - t0) * 1000)
            # Strip raw MiniMax tool-call tokens that leak into content
            content = _strip_raw_tokens(content)
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
                    content=user_message, agent_id=agent.id,
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
            tools = _filter_schemas(_get_tool_schemas(), ctx.allowed_tools) if ctx.tools_enabled else None

            # Tool-calling rounds (non-streaming) — same as run()
            deep_search_used = False
            final_content = ""
            logger.warning("Agent %s: tools_enabled=%s, tools=%s, allowed=%s",
                           agent.id, ctx.tools_enabled, "YES" if tools else "NO",
                           ctx.allowed_tools[:3] if ctx.allowed_tools else "all")

            for round_num in range(MAX_TOOL_ROUNDS):
                is_last_possible = (round_num >= MAX_TOOL_ROUNDS - 1) or tools is None

                # On last round or no tools: use streaming
                if is_last_possible or not ctx.tools_enabled:
                    # Stream the final response
                    accumulated = ""
                    async for chunk in self._llm.stream(
                        messages=messages,
                        provider=agent.provider,
                        model=agent.model,
                        temperature=agent.temperature,
                        max_tokens=agent.max_tokens,
                        system_prompt=system if round_num == 0 else "",
                    ):
                        if chunk.delta:
                            accumulated += chunk.delta
                            yield ("delta", chunk.delta)
                        if chunk.done:
                            break
                    final_content = accumulated
                    break

                # Non-streaming tool round
                llm_resp = await self._llm.chat(
                    messages=messages,
                    provider=agent.provider,
                    model=agent.model,
                    temperature=agent.temperature,
                    max_tokens=agent.max_tokens,
                    system_prompt=system if round_num == 0 else "",
                    tools=tools,
                )

                total_tokens_in += llm_resp.tokens_in
                total_tokens_out += llm_resp.tokens_out
                logger.warning("TOOL_DBG agent=%s round=%d tc=%d clen=%d fin=%s", agent.id, round_num, len(llm_resp.tool_calls), len(llm_resp.content or ""), llm_resp.finish_reason)

                # Parse XML tool calls
                if not llm_resp.tool_calls and llm_resp.content:
                    xml_tcs = _parse_xml_tool_calls(llm_resp.content)
                    if xml_tcs:
                        llm_resp = LLMResponse(
                            content="", model=llm_resp.model, provider=llm_resp.provider,
                            tokens_in=llm_resp.tokens_in, tokens_out=llm_resp.tokens_out,
                            duration_ms=llm_resp.duration_ms, finish_reason="tool_calls",
                            tool_calls=xml_tcs,
                        )

                # No tool calls → stream remaining content in chunks
                if not llm_resp.tool_calls:
                    final_content = llm_resp.content or ""
                    # Strip <think> blocks before chunking (tags would split across chunks)
                    import re as _re_exec
                    final_content = _re_exec.sub(r"<think>[\s\S]*?</think>\s*", "", final_content).strip()
                    # Also strip unclosed <think> at the end
                    if "<think>" in final_content and "</think>" not in final_content:
                        final_content = final_content[:final_content.index("<think>")].strip()
                    # Strip tool call artifacts
                    final_content = _re_exec.sub(r"<minimax:tool_call>[\s\S]*?</minimax:tool_call>\s*", "", final_content).strip()
                    final_content = _re_exec.sub(r"<tool_call>[\s\S]*?</tool_call>\s*", "", final_content).strip()
                    if final_content:
                        # Emit in word-sized chunks for natural streaming UX
                        chunk_size = 8
                        for ci in range(0, len(final_content), chunk_size):
                            yield ("delta", final_content[ci:ci + chunk_size])
                            await asyncio.sleep(0.03)
                    break

                # Process tool calls (same as run())
                tc_msg_data = [{
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function_name, "arguments": json.dumps(tc.arguments)},
                } for tc in llm_resp.tool_calls]

                messages.append(LLMMessage(
                    role="assistant",
                    content=llm_resp.content or "",
                    tool_calls=tc_msg_data,
                ))

                for tc in llm_resp.tool_calls:
                    yield ("tool", tc.function_name)
                    result = await _execute_tool(tc, ctx, self._registry, self._llm)
                    logger.warning("TOOL_EXEC agent=%s tool=%s args=%s result=%s",
                                   agent.id, tc.function_name,
                                   str(tc.arguments)[:200], result[:200])
                    all_tool_calls.append({
                        "name": tc.function_name,
                        "args": tc.arguments,
                        "result": result[:500],
                    })
                    # Persist tool call to DB for monitoring
                    try:
                        from ..db.migrations import get_db
                        db = get_db()
                        db.execute(
                            "INSERT INTO tool_calls (agent_id, session_id, tool_name, parameters_json, result_json, success, timestamp) "
                            "VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
                            (agent.id, ctx.session_id, tc.function_name,
                             str(tc.arguments)[:1000], result[:1000],
                             1 if not result.startswith(("Error", "LRM error", "MCP error")) else 0),
                        )
                        db.commit()
                    except Exception:
                        pass
                    if tc.function_name == "deep_search":
                        deep_search_used = True
                    if ctx.on_tool_call:
                        try:
                            await ctx.on_tool_call(tc.function_name, tc.arguments, result)
                        except Exception:
                            pass
                    messages.append(LLMMessage(
                        role="tool",
                        content=result[:2000],
                        tool_call_id=tc.id,
                        name=tc.function_name,
                    ))

                # Limit message window to prevent OOM
                if len(messages) > 20:
                    tail = messages[-15:]
                    # Don't start tail with orphaned tool results
                    while tail and getattr(tail[0], 'role', '') == 'tool':
                        tail = tail[1:]
                    messages = messages[:2] + tail

                if deep_search_used:
                    tools = None
                # Nudge: if round 2+ and no code_write yet, inject urgent reminder
                # Only nudge if write tools are available (not for read-only contexts like CDP chat)
                write_count = sum(1 for tc_rec in all_tool_calls if tc_rec["name"] in ("code_write", "code_edit", "fractal_code"))
                has_written = write_count > 0
                has_write_tools = any(t.get("function", {}).get("name") in ("code_write", "code_edit", "fractal_code") for t in (tools or []))
                if round_num >= 1 and not has_written and tools is not None and has_write_tools:
                    # Strip read-only tools — force write
                    write_only_tools = [t for t in tools if t.get("function", {}).get("name") in ("code_write", "code_edit", "fractal_code", "git_commit")]
                    if write_only_tools:
                        tools = write_only_tools
                    messages.append(LLMMessage(
                        role="system",
                        content="⚠️ STOP reading. Call code_write NOW.\n"
                                "code_write(path=\"src/index.ts\", content=\"// your code here\\n...\")",
                    ))
                elif round_num >= 2 and has_written and write_count < 2 and tools is not None:
                    messages.append(LLMMessage(
                        role="system",
                        content="⚠️ 1 file written. Call code_write for remaining files.",
                    ))
                if round_num >= MAX_TOOL_ROUNDS - 2 and tools is not None:
                    if has_written:
                        tools = None
                        messages.append(LLMMessage(role="system", content="Tools done. Summarize changes."))
                    # else: keep write-only tools — agent MUST write code
            else:
                final_content = final_content or "(Max tool rounds reached)"

            elapsed = int((time.monotonic() - t0) * 1000)
            final_content = _strip_raw_tokens(final_content)
            delegations = self._parse_delegations(final_content)

            yield ("result", ExecutionResult(
                content=final_content,
                agent_id=agent.id,
                model=agent.model,
                provider=agent.provider,
                tokens_in=total_tokens_in,
                tokens_out=total_tokens_out,
                duration_ms=elapsed,
                tool_calls=all_tool_calls,
                delegations=delegations,
            ))

        except Exception as exc:
            elapsed = int((time.monotonic() - t0) * 1000)
            logger.error("Agent %s streaming failed: %s", agent.id, exc, exc_info=True)
            yield ("result", ExecutionResult(
                content=f"Error: {exc}",
                agent_id=agent.id,
                duration_ms=elapsed,
                error=str(exc),
            ))


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
