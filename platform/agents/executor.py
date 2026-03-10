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
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path

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
from .tool_selector import select_tools as _bm25_select
from ..db.migrations import get_db
from ..hooks import HookContext, HookType, registry as _hook_registry

logger = logging.getLogger(__name__)

# Max tool-calling rounds to prevent infinite loops
# Increased from 8→15: complex agents (devops, E2E) need more budget for
# multi-step operations (read config → write Dockerfile → docker_deploy → check)
MAX_TOOL_ROUNDS = 15

# REF: arXiv:2602.20021 — SBD-05: per-run tool call budget to prevent resource exhaustion
MAX_TOOL_CALLS_PER_RUN = int(os.getenv("MAX_TOOL_CALLS_PER_RUN", "50"))

# Tools that produce code changes and should trigger auto-verification
_CODE_WRITE_TOOLS = frozenset({"code_write", "code_edit", "code_create"})
# Max automatic repair rounds after a failed verification (lint/build)
MAX_REPAIR_ROUNDS = 3

# Secrets detection patterns (block hardcoded credentials in code writes)
import re as _re_secrets  # noqa: E402

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

# Workspace file write lock: maps (project_id, normalized_path) → agent_id
# Prevents concurrent agents from clobbering the same file
_file_write_locks: dict[tuple[str, str], str] = {}
_file_write_lock_meta: dict = {}  # (project_id, path) → {"agent": str, "ts": float}


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
    epic_run_id: str | None = None
    # Uruk capability grade: 'organizer' (full context) or 'executor' (task-scoped)
    capability_grade: str = "executor"
    # Lineage chain: explains WHY this agent is being called (fractal vertical traceability)
    # Format: ["Vision: <v>", "Epic: <e>", "Story: <s>", "Task: <t>"]
    lineage: list[str] = field(default_factory=list)


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


class BudgetExceededError(RuntimeError):
    """Raised when a session exceeds its configured USD budget."""


# ── Settings cache (refreshed every 60 s) ────────────────────────────────────
_settings_cache: dict[str, str] = {}
_settings_cache_ts: float = 0.0
_SETTINGS_TTL = 60.0


def _get_rate_limit_setting(key: str, default: str) -> str:
    """Return a rate-limit setting from platform_settings, with 60 s cache."""
    global _settings_cache, _settings_cache_ts
    now = time.monotonic()
    if now - _settings_cache_ts > _SETTINGS_TTL:
        try:
            with get_db() as db:
                rows = db.execute(
                    "SELECT key, value FROM platform_settings WHERE key LIKE 'rate_limit_%'"
                ).fetchall()
            _settings_cache = {r[0]: r[1] for r in rows}
            _settings_cache_ts = now
        except Exception:
            pass
    return _settings_cache.get(key, default)


def _check_session_budget(session_id: str) -> None:
    """Raise BudgetExceededError if the session has exceeded its per-session USD cap."""
    try:
        enabled = _get_rate_limit_setting("rate_limit_enabled", "true")
        if enabled.lower() not in ("true", "1", "yes"):
            return
        cap_str = _get_rate_limit_setting("rate_limit_usd_per_session", "10.00")
        cap = float(cap_str)
        if cap <= 0:
            return

        with get_db() as db:
            row = db.execute(
                "SELECT COALESCE(SUM(cost_usd),0) FROM llm_traces WHERE session_id=?",
                (session_id,),
            ).fetchone()
        spent = float(row[0]) if row else 0.0
        if spent >= cap:
            logger.warning(
                "Session %s exceeded budget cap $%.2f (spent $%.4f)",
                session_id,
                cap,
                spent,
            )
            raise BudgetExceededError(
                f"Session budget cap of ${cap:.2f} exceeded (spent ${spent:.4f})"
            )
    except BudgetExceededError:
        raise
    except Exception:
        pass  # never block on DB errors


def _write_llm_usage(
    provider: str,
    model: str,
    tokens_in: int,
    tokens_out: int,
    project_id: str | None,
    agent_id: str,
    session_id: str,
) -> None:
    """Insert one row into llm_usage. Never raises."""
    try:
        from ..llm.observability import _estimate_cost

        cost = _estimate_cost(model, tokens_in, tokens_out)
        with get_db() as db:
            db.execute(
                "INSERT INTO llm_usage (provider, model, tokens_in, tokens_out,"
                " cost_estimate, project_id, agent_id, session_id) VALUES (?,?,?,?,?,?,?,?)",
                (
                    provider,
                    model,
                    tokens_in,
                    tokens_out,
                    cost,
                    project_id or "",
                    agent_id,
                    session_id,
                ),
            )
            db.commit()
    except Exception:
        pass


def _debit_project_wallet(project_id: str, cost_usd: float, reference_id: str) -> None:
    """Debit project wallet for LLM cost. Never raises."""
    if not cost_usd or cost_usd <= 0 or not project_id:
        return
    try:
        import uuid as _uuid_w

        with get_db() as db:
            row = db.execute(
                "SELECT balance FROM project_wallets WHERE project_id=?", (project_id,)
            ).fetchone()
            if not row:
                db.execute(
                    "INSERT INTO project_wallets (project_id, balance, total_earned, total_spent)"
                    " VALUES (?,100.0,100.0,0)",
                    (project_id,),
                )
            db.execute(
                "UPDATE project_wallets SET balance=balance-?, total_spent=total_spent+?,"
                " updated_at=datetime('now') WHERE project_id=?",
                (cost_usd, cost_usd, project_id),
            )
            db.execute(
                "INSERT INTO token_transactions (id, project_id, amount, reason, reference_id)"
                " VALUES (?,?,?,?,?)",
                (
                    str(_uuid_w.uuid4()),
                    project_id,
                    -cost_usd,
                    "llm_usage",
                    reference_id,
                ),
            )
            db.commit()
    except Exception:
        pass


def _update_mission_cost(session_id: str, epic_run_id: str | None) -> None:
    """Update epic_runs.llm_cost_usd from llm_traces. Never raises."""
    try:
        with get_db() as db:
            mid = epic_run_id
            if not mid and session_id:
                row = db.execute(
                    "SELECT id FROM epic_runs WHERE session_id=? ORDER BY created_at DESC LIMIT 1",
                    (session_id,),
                ).fetchone()
                if row:
                    mid = row[0]
            if mid:
                db.execute(
                    "UPDATE epic_runs SET llm_cost_usd="
                    "(SELECT COALESCE(SUM(cost_usd),0) FROM llm_traces WHERE session_id=?)"
                    " WHERE id=?",
                    (session_id, mid),
                )
                db.commit()
    except Exception:
        pass


# Number of recent messages preserved intact during context summarization
# Context rot prevention inspired by Ralph (https://github.com/frankbria/ralph-claude-code)
_CTX_KEEP_RECENT = 6
# Summarize when message count exceeds this
_CTX_SUMMARIZE_THRESHOLD = 20


async def _summarize_context(
    messages: list, llm: "LLMClient", provider: str, model: str
) -> list:
    """Summarize old messages to compress context while preserving recent ones.

    Keeps: system messages (first 2) + last _CTX_KEEP_RECENT messages.
    Summarizes: everything in between via a cheap LLM call.
    Falls back to simple truncation if LLM call fails.
    """
    if len(messages) <= _CTX_SUMMARIZE_THRESHOLD:
        return messages

    # Separate system header (first 1-2 msgs) from the body
    header = [m for m in messages[:2] if getattr(m, "role", "") == "system"]
    tail = messages[-_CTX_KEEP_RECENT:]
    # Don't start tail with orphaned tool results
    while tail and getattr(tail[0], "role", "") == "tool":
        tail = tail[1:]
    middle = messages[len(header) : len(messages) - len(tail)]

    if not middle:
        return header + tail

    # Build compact text of middle messages to summarize
    middle_text = []
    for m in middle:
        role = getattr(m, "role", "")
        content = getattr(m, "content", "") or ""
        if isinstance(content, list):
            content = " ".join(
                p.get("text", "") for p in content if isinstance(p, dict)
            )
        if role in ("user", "assistant") and content:
            middle_text.append(f"[{role}] {str(content)[:400]}")
        elif role == "tool" and content:
            middle_text.append(f"[tool_result] {str(content)[:200]}")

    if not middle_text:
        return header + tail

    # GSD structured summarization — preserve decisions/progress/blockers/data
    # Pattern: Get Shit Done (https://github.com/gsd-build/get-shit-done, MIT)
    # WHY: flat paragraph summaries lose the decision trail and blockers. A
    #      structured format lets the agent resume work without re-deriving state.
    summary_prompt = (
        "Summarize the following agent conversation history using this EXACT format:\n\n"
        "DECISIONS: (bullet list — architectural/technical choices made; max 5)\n"
        "PROGRESS: (bullet list — what was completed; max 5)\n"
        "BLOCKERS: (bullet list — errors, failures, unknowns; max 3; NONE if empty)\n"
        "KEY DATA: (bullet list — file names, values, IDs, error messages to remember; max 5)\n\n"
        "Rules: be telegraphic. Preserve exact names, values, paths. No fluff.\n\n"
        + "\n".join(middle_text)
    )
    try:
        summary_resp = await llm.complete(
            messages=[LLMMessage(role="user", content=summary_prompt)],
            provider=provider,
            model=model,
            tools=None,
            stream=False,
        )
        summary_text = (summary_resp.content or "").strip()
        if summary_text:
            summary_msg = LLMMessage(
                role="system",
                content=f"[Context summary — earlier work]\n{summary_text}",
            )
            return header + [summary_msg] + tail
    except Exception:
        pass

    # Fallback: simple truncation
    return header + tail


# Minimum messages before memory extraction runs (avoid trivial exchanges)
_MEM_EXTRACT_MIN_MSGS = 4
# Throttle: don't extract more than once per N seconds for the same session
_mem_extract_last: dict[str, float] = {}
_MEM_EXTRACT_COOLDOWN = 120  # 2 minutes


async def _extract_session_memory(
    ctx: "ExecutionContext", messages: list, llm: "LLMClient", provider: str, model: str
) -> None:
    """Background task: extract structured facts from a session into project memory.

    Extracts: tech stack decisions, coding preferences, architecture choices,
    recurring patterns, key constraints. Stored in memory_project for future sessions.
    Inspired by DeerFlow v2 memory extraction pipeline.
    """
    import time as _time

    session_id = ctx.session_id
    now = _time.monotonic()
    if now - _mem_extract_last.get(session_id, 0) < _MEM_EXTRACT_COOLDOWN:
        return
    _mem_extract_last[session_id] = now

    # Build compact conversation digest (last 10 exchanges max)
    relevant = [m for m in messages if getattr(m, "role", "") in ("user", "assistant")][
        -10:
    ]
    if len(relevant) < _MEM_EXTRACT_MIN_MSGS:
        return

    digest = []
    for m in relevant:
        role = getattr(m, "role", "")
        content = getattr(m, "content", "") or ""
        if isinstance(content, list):
            content = " ".join(
                p.get("text", "") for p in content if isinstance(p, dict)
            )
        digest.append(f"[{role}] {str(content)[:300]}")

    extract_prompt = (
        "Extract structured facts from this conversation that would be useful for future sessions. "
        "Return a JSON array of objects with keys: key (short label), value (the fact), category "
        "(one of: tech_stack | architecture | preference | constraint | pattern | decision). "
        "Only include facts with lasting value. Return [] if nothing notable.\n\n"
        "Conversation:\n" + "\n".join(digest)
    )
    try:
        resp = await llm.complete(
            messages=[LLMMessage(role="user", content=extract_prompt)],
            provider=provider,
            model=model,
            tools=None,
            stream=False,
        )
        raw = (resp.content or "").strip()
        # Strip markdown fences if any
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        import json as _json

        facts = _json.loads(raw)
        if not isinstance(facts, list):
            return
        from ..memory.manager import get_memory_manager
        from .tool_schemas import _classify_agent_role

        mem = get_memory_manager()
        agent_role = _classify_agent_role(ctx.agent)
        stored = 0
        for fact in facts[:10]:  # cap at 10 facts per session
            key = str(fact.get("key", ""))[:80]
            value = str(fact.get("value", ""))[:500]
            category = str(fact.get("category", "fact"))[:40]
            if key and value:
                mem.project_store(
                    ctx.project_id,
                    key,
                    value,
                    category=category,
                    source=ctx.agent.id,
                    agent_role=agent_role,
                )
                stored += 1
        if stored:
            logger.debug(
                "Memory extraction: stored %d facts for project %s",
                stored,
                ctx.project_id,
            )
    except Exception as e:
        logger.debug("Memory extraction failed (non-critical): %s", e)


def _priority_tool_list(tools: list) -> list:
    """Return single-item list with most important tool for forced calling.

    Used on nudge rounds: shrinking to 1 tool triggers MiniMax's single-tool
    forced mode (tool_choice by name) which is the only mode MiniMax respects.
    Priority order matches AC agent roles (architect/codex → code_write,
    qa-agent → docker_deploy, cicd → git_commit).
    """
    if not tools:
        return tools
    priority_names = (
        "code_write",
        "docker_deploy",
        "git_commit",
        "git_status",
        "list_files",
    )
    for name in priority_names:
        for t in tools:
            if t.get("function", {}).get("name") == name:
                return [t]
    return [tools[0]]


class AgentExecutor:
    """Executes agent logic: prompt → LLM → tool loop → response."""

    def __init__(self, llm: LLMClient | None = None):
        self._llm = llm or get_llm_client()
        self._registry = _get_tool_registry()
        self._heartbeat_tasks: dict[str, asyncio.Task] = {}

    def _start_heartbeat(self, epic_run_id: str) -> None:
        """Start a background heartbeat task that updates epic_runs.updated_at every 30s.

        Allows external monitoring to detect stuck/crashed workflows.
        Inspired by Temporal activity heartbeating.
        """
        if not epic_run_id or epic_run_id in self._heartbeat_tasks:
            return

        async def _beat():
            try:
                while True:
                    await asyncio.sleep(30)
                    try:
                        with get_db() as db:
                            db.execute(
                                "UPDATE epic_runs SET updated_at=NOW() WHERE id=?",
                                (epic_run_id,),
                            )
                    except Exception:
                        pass
            except asyncio.CancelledError:
                pass

        task = asyncio.create_task(_beat(), name=f"heartbeat_{epic_run_id[:8]}")
        self._heartbeat_tasks[epic_run_id] = task

    def _stop_heartbeat(self, epic_run_id: str) -> None:
        """Cancel heartbeat task for a completed/failed epic run."""
        task = self._heartbeat_tasks.pop(epic_run_id, None)
        if task and not task.done():
            task.cancel()

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

            with get_db() as db:
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

            # BM25 prompt-aware tool selection — narrows role-filtered set to
            # the ~10-15 most relevant tools for the user's prompt.
            # Inspired by Agentica @agentica/vector-selector (wrtnlabs/agentica).
            if tools and len(tools) > 15:
                tools = _bm25_select(tools, user_message, top_k=10)

            # Fire SESSION_START hooks
            await _hook_registry.fire(
                HookType.SESSION_START,
                HookContext(
                    hook_type=HookType.SESSION_START,
                    agent_id=agent.id,
                    session_id=ctx.session_id or "",
                    project_id=ctx.project_id or "",
                ),
            )

            # Route provider: Darwin LLM Thompson Sampling + routing config
            # cheap_mode: if allowed_tools are all cheap (memory/read), use MiniMax
            from .routing import CHEAP_TOOLS as _CHEAP_TOOLS

            _cheap_mode = bool(
                ctx.allowed_tools
                and ctx.tools_enabled
                and all(t in _CHEAP_TOOLS for t in (ctx.allowed_tools or []))
            )
            use_provider, use_model = _route_provider(
                agent, tools, mission_id=ctx.epic_run_id, cheap_mode=_cheap_mode
            )

            # Tool-calling loop
            deep_search_used = False
            _run_tool_call_count = 0  # REF: arXiv:2602.20021 SBD-05 per-run tool budget
            _active_tools = tools  # may be narrowed to 1 tool on nudge rounds
            for round_num in range(MAX_TOOL_ROUNDS):
                llm_resp = await self._llm.chat(
                    messages=messages,
                    provider=use_provider,
                    model=use_model,
                    temperature=agent.temperature,
                    max_tokens=agent.max_tokens,
                    system_prompt=system if round_num == 0 else "",
                    tools=_active_tools,
                )

                total_tokens_in += llm_resp.tokens_in
                total_tokens_out += llm_resp.tokens_out
                _write_llm_usage(
                    llm_resp.provider,
                    llm_resp.model,
                    llm_resp.tokens_in,
                    llm_resp.tokens_out,
                    ctx.project_id,
                    agent.id,
                    ctx.session_id,
                )
                _check_session_budget(ctx.session_id)

                # Push live cost/token update via SSE (workspace live feed)
                if ctx.session_id:
                    try:
                        from ..llm.observability import _estimate_cost
                        import asyncio as _asyncio

                        _running_cost = _estimate_cost(
                            llm_resp.model, total_tokens_in, total_tokens_out
                        )
                        _asyncio.ensure_future(
                            self._push_mission_sse(
                                ctx.session_id,
                                {
                                    "type": "token_usage",
                                    "agent_id": agent.id,
                                    "tokens_in": total_tokens_in,
                                    "tokens_out": total_tokens_out,
                                    "tokens_total": total_tokens_in + total_tokens_out,
                                    "cost_usd": round(_running_cost, 6),
                                    "model": llm_resp.model,
                                    "runaway": (total_tokens_in + total_tokens_out)
                                    > 100_000,
                                },
                            )
                        )
                    except Exception:
                        pass

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
                    # Tool nudge: if tools are available and the model returned no tool calls,
                    # inject a mandatory "call a tool NOW" message and retry (up to 3 times).
                    # MiniMax M2.5 sometimes needs several nudges before it calls tools.
                    if (
                        tools
                        and round_num <= 3
                        and not any(
                            t in (content or "").lower()
                            for t in ["```", "result:", "output:", "error:"]
                        )
                    ):
                        messages.append(
                            LLMMessage(role="assistant", content=content or "")
                        )
                        messages.append(
                            LLMMessage(
                                role="user",
                                content=(
                                    "⚠️ ARRÊTE — ne décris pas ce que tu vas faire. "
                                    "APPELLE UN OUTIL MAINTENANT. "
                                    "Premier action = tool call obligatoire. "
                                    "Si tu es développeur : appelle code_write. "
                                    "Si tu es architecte : appelle code_write pour créer INCEPTION.md. "
                                    "Si tu es QA : appelle docker_deploy. "
                                    "Pas de texte introductif — agis directement."
                                ),
                            )
                        )
                        # Narrow to priority tool so MiniMax uses single-tool forced mode
                        _active_tools = _priority_tool_list(tools)
                        continue  # retry with nudge
                    break

                # Tool was called → restore full tools for next round
                _active_tools = tools

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
                    # Hard rejection: if active tools are narrowed (write-only nudge mode),
                    # block read-tool calls to force the model to write instead
                    _allowed_run_names = (
                        {t.get("function", {}).get("name") for t in _active_tools}
                        if _active_tools is not tools
                        else None
                    )
                    _read_run_tools = {
                        "code_read",
                        "list_files",
                        "code_search",
                        "file_search",
                    }
                    if (
                        _allowed_run_names is not None
                        and tc.function_name not in _allowed_run_names
                        and tc.function_name in _read_run_tools
                    ):
                        result = (
                            f"Error: '{tc.function_name}' is not available. "
                            "You have enough context. Call code_write NOW to create the files."
                        )
                        messages.append(
                            LLMMessage(
                                role="tool",
                                content=result[:2000],
                                tool_call_id=tc.id,
                                name=tc.function_name,
                            )
                        )
                        continue
                    # ── QA scope enforcement: only allow writes to QA_REPORT_* and Dockerfile ──
                    if tc.function_name in _CODE_WRITE_TOOLS:
                        _role_l = (agent.role or "").lower()
                        if "qa" in _role_l and "devops" not in _role_l:
                            _write_path = str(tc.arguments.get("path", ""))
                            _bn = _write_path.split("/")[-1]
                            _qa_allowed = (
                                _bn.startswith("QA_REPORT")
                                or _bn == "Dockerfile"
                                or _bn.startswith("Dockerfile.")
                            )
                            if not _qa_allowed:
                                messages.append(
                                    LLMMessage(
                                        role="tool",
                                        content=(
                                            f"Error: SCOPE VIOLATION — QA agent cannot write '{_bn}'. "
                                            "Only allowed: QA_REPORT_N.md, Dockerfile (Chromium fix). "
                                            "If docker_deploy fails for non-Chromium reasons → call veto_cycle."
                                        ),
                                        tool_call_id=tc.id,
                                        name=tc.function_name,
                                    )
                                )
                                continue
                    # ── Workspace conflict guard: warn if another agent is writing this file ──
                    if tc.function_name in _CODE_WRITE_TOOLS and ctx.project_id:
                        import time as _time

                        _fp = str(tc.arguments.get("path", "")).strip("/")
                        _lock_key = (ctx.project_id, _fp)
                        _existing = _file_write_locks.get(_lock_key)
                        if _existing and _existing != ctx.session_id:
                            _meta = _file_write_lock_meta.get(_lock_key, {})
                            _age = _time.time() - _meta.get("ts", 0)
                            if _age < 30:  # warn only if recent (< 30s)
                                logger.warning(
                                    "File conflict: %s already being written by agent %s (session %s) — %s proceeding",
                                    _fp,
                                    _meta.get("agent", "?"),
                                    _existing,
                                    agent.id,
                                )
                    # PRE_TOOL hook (may block)
                    _hook_ctx = HookContext(
                        hook_type=HookType.PRE_TOOL,
                        agent_id=agent.id,
                        session_id=ctx.session_id or "",
                        project_id=ctx.project_id or "",
                        tool_name=tc.function_name,
                        tool_args=dict(tc.arguments),
                    )
                    _pre_res = await _hook_registry.fire_pre(
                        HookType.PRE_TOOL, _hook_ctx
                    )
                    if _pre_res.blocked:
                        result = f"[BLOCKED by hook: {_pre_res.message}]"
                    else:
                        # REF: arXiv:2602.20021 SBD-05 — enforce per-run tool call budget
                        _run_tool_call_count += 1
                        if _run_tool_call_count > MAX_TOOL_CALLS_PER_RUN:
                            raise BudgetExceededError(
                                f"Tool call budget exceeded ({MAX_TOOL_CALLS_PER_RUN} calls/run). "
                                "Increase MAX_TOOL_CALLS_PER_RUN env var if needed."
                            )
                        result = await _execute_tool(tc, ctx, self._registry, self._llm)
                    # POST_TOOL hook
                    _hook_ctx.hook_type = HookType.POST_TOOL
                    _hook_ctx.tool_result = result[:200]
                    _hook_ctx.all_tool_calls = all_tool_calls
                    await _hook_registry.fire(HookType.POST_TOOL, _hook_ctx)
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
                                # Use role=user (not role=tool) to avoid requiring a
                                # matching tool_calls assistant message (Azure OpenAI strict ordering)
                                messages.append(
                                    LLMMessage(
                                        role="user",
                                        content=(
                                            f"[AUTO-LINT] Lint/verification failed (round {_repair_round + 1}/{MAX_REPAIR_ROUNDS}). "
                                            "Fix all reported issues NOW before proceeding.\n\n"
                                            f"{lint_result[:1500]}"
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
                                # Add assistant message with tool_calls before tool results (OpenAI strict ordering)
                                messages.append(
                                    LLMMessage(
                                        role="assistant",
                                        content=fix_resp.content or "",
                                        tool_calls=[
                                            {
                                                "id": ftc.id,
                                                "type": "function",
                                                "function": {
                                                    "name": ftc.function_name,
                                                    "arguments": json.dumps(
                                                        ftc.arguments
                                                    ),
                                                },
                                            }
                                            for ftc in fix_resp.tool_calls
                                        ],
                                    )
                                )
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

                        # ── SAST: run after lint loop completes ──────────────────────────
                        _written_path = tc.arguments.get("path", "")
                        if _written_path:
                            try:
                                sast_tool = self._registry.get("sast_check")
                                if sast_tool:
                                    _sast_result = await sast_tool.execute(
                                        {"path": _written_path}, agent
                                    )
                                    if "CRITICAL" in _sast_result:
                                        logger.warning(
                                            "Agent %s: SAST critical issues in %s",
                                            agent.id,
                                            _written_path,
                                        )
                                        messages.append(
                                            LLMMessage(
                                                role="user",
                                                content=(
                                                    "[SAST] Critical security/quality issues detected. "
                                                    "Fix ALL critical issues before proceeding:\n\n"
                                                    f"{_sast_result[:2000]}"
                                                ),
                                            )
                                        )
                                    elif (
                                        _sast_result
                                        and "no issues" not in _sast_result.lower()
                                    ):
                                        messages.append(
                                            LLMMessage(
                                                role="user",
                                                content=(
                                                    "[SAST] Quality warnings (fix if possible):\n\n"
                                                    f"{_sast_result[:1000]}"
                                                ),
                                            )
                                        )
                            except Exception as _se:
                                logger.debug("SAST check error (non-fatal): %s", _se)

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

                # Context summarization: when history grows large, summarize old messages
                # instead of simply truncating (inspired by DeerFlow v2)
                if len(messages) > 20:
                    # PRE_COMPACT hook — let hooks save state before shrinkage
                    await _hook_registry.fire(
                        HookType.PRE_COMPACT,
                        HookContext(
                            hook_type=HookType.PRE_COMPACT,
                            agent_id=agent.id,
                            session_id=ctx.session_id or "",
                            project_id=ctx.project_id or "",
                            messages=messages,
                            all_tool_calls=all_tool_calls,
                        ),
                    )
                    messages = await _summarize_context(
                        messages, self._llm, use_provider, use_model
                    )

                # On penultimate round, force synthesis or code-write depending on agent type
                if round_num >= MAX_TOOL_ROUNDS - 2 and tools is not None:
                    _has_write_tools = ctx.allowed_tools and any(
                        t in (ctx.allowed_tools or [])
                        for t in ["code_write", "code_edit"]
                    )
                    if _has_write_tools:
                        # Keep tools enabled so the agent CAN call code_write
                        messages.append(
                            LLMMessage(
                                role="system",
                                content=(
                                    "⚠️ DERNIER TOUR — tu dois maintenant ÉCRIRE le code avec code_write. "
                                    "Crée chaque fichier requis (tests d'abord, puis implémentation). "
                                    "Ne lis plus de fichiers — écris uniquement."
                                ),
                            )
                        )
                    else:
                        tools = None
                        messages.append(
                            LLMMessage(
                                role="system",
                                content="You have used many tool calls. Now synthesize your findings and respond to the user. Do not call more tools.",
                            )
                        )
            else:
                content = llm_resp.content or "(Max tool rounds reached)"

            # Auto-code-write: when agent has write tools but never called code_write,
            # extract fenced code blocks from content and write them.
            # MiniMax workaround — it sometimes puts code in text instead of tool calls.
            _wrote_code = any(
                tc.get("name") in ("code_write", "code_edit", "fractal_code")
                for tc in all_tool_calls
            )
            _has_write_tools_final = ctx.allowed_tools and any(
                t in ("code_write", "code_edit") for t in ctx.allowed_tools
            )
            if (
                _has_write_tools_final
                and not _wrote_code
                and content
                and "```" in content
            ):
                _code_blocks = re.findall(
                    r"```(?:python|javascript|typescript|java|go|rust|)\n(.*?)```",
                    content,
                    re.DOTALL,
                )
                _ws = getattr(ctx, "workspace_path", None) or "."
                for idx, code_block in enumerate(_code_blocks):
                    code_block = code_block.strip()
                    if len(code_block) < 50:
                        continue
                    _fname = f"generated_{idx}.py"
                    if "def test_" in code_block or "class Test" in code_block:
                        _fname = f"test_generated_{idx}.py"
                    _fpath = os.path.join(_ws, _fname)
                    try:
                        _fp = Path(_fpath)
                        _fp.parent.mkdir(parents=True, exist_ok=True)
                        _fp.write_text(code_block)
                        all_tool_calls.append(
                            {
                                "name": "code_write",
                                "args": {"path": _fpath, "content": code_block},
                                "result": f"Auto-written {len(code_block)} chars to {_fpath}",
                            }
                        )
                        logger.info(
                            "Auto-code-write: %d chars → %s", len(code_block), _fpath
                        )
                    except Exception as e:
                        logger.warning("Auto-code-write failed: %s", e)

            # Force synthesis if output is too short but tools were called
            # Prevents adversarial REJECT due to TOO_SHORT when agent read files but didn't write
            if content and len(content.strip()) < 80 and all_tool_calls:
                try:
                    messages.append(LLMMessage(role="assistant", content=content or ""))
                    messages.append(
                        LLMMessage(
                            role="system",
                            content=(
                                "Ton résumé est trop court. Rédige maintenant un rapport COMPLET de 200 mots :\n"
                                "- Quels fichiers as-tu créés, analysés ou mis à jour ?\n"
                                "- Quel contenu précis contiennent-ils ?\n"
                                "- Comment répondent-ils aux exigences du cycle ?\n"
                                "Minimum 200 mots. Rapport factuel direct, pas d'excuse."
                            ),
                        )
                    )
                    _synth = await self._llm.chat(
                        messages=messages,
                        provider=use_provider,
                        model=use_model,
                        temperature=agent.temperature,
                        max_tokens=2000,
                        system_prompt="",
                        tools=None,
                    )
                    if _synth.content and len(_synth.content.strip()) > len(
                        content.strip()
                    ):
                        content = _synth.content
                        total_tokens_in += _synth.tokens_in
                        total_tokens_out += _synth.tokens_out
                except Exception as _se:
                    logger.debug("Synthesis expansion failed: %s", _se)

            elapsed = int((time.monotonic() - t0) * 1000)
            # Strip raw MiniMax tool-call tokens that leak into content
            content = _strip_raw_tokens(content)
            # Strip <think> blocks (MiniMax chain-of-thought) from stored content
            content = re.sub(r"<think>[\s\S]*?</think>\s*", "", content).strip()
            if "<think>" in content and "</think>" not in content:
                content = content[: content.index("<think>")].strip()

            delegations = self._parse_delegations(content)

            _update_mission_cost(ctx.session_id, ctx.epic_run_id)
            result = ExecutionResult(
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
            # Debit project wallet for LLM cost
            try:
                from ..llm.observability import _estimate_cost

                _cost = _estimate_cost(
                    llm_resp.model, total_tokens_in, total_tokens_out
                )
                _debit_project_wallet(ctx.project_id, _cost, ctx.session_id)
            except Exception:
                pass
            # Background: extract structured memory facts from this interaction
            if ctx.project_id and len(messages) >= 4:
                asyncio.create_task(
                    _extract_session_memory(
                        ctx, messages, self._llm, use_provider, use_model
                    ),
                    name=f"mem_extract_{ctx.session_id[:8]}",
                )
            if ctx.epic_run_id:
                self._stop_heartbeat(ctx.epic_run_id)
            # SESSION_END hook (fire-and-forget)
            asyncio.ensure_future(
                _hook_registry.fire(
                    HookType.SESSION_END,
                    HookContext(
                        hook_type=HookType.SESSION_END,
                        agent_id=agent.id,
                        session_id=ctx.session_id or "",
                        project_id=ctx.project_id or "",
                        all_tool_calls=all_tool_calls,
                    ),
                )
            )
            return result

        except Exception as exc:
            if ctx.epic_run_id:
                self._stop_heartbeat(ctx.epic_run_id)
            err_str = str(exc)
            if isinstance(exc, BudgetExceededError):
                elapsed = int((time.monotonic() - t0) * 1000)
                return ExecutionResult(
                    content=f"Session budget exceeded: {exc}",
                    agent_id=agent.id,
                    duration_ms=elapsed,
                    error="budget_exceeded",
                )
            is_llm_error = (
                "All LLM providers failed" in err_str or "rate" in err_str.lower()
            )
            # Retry up to 3 times with exponential backoff for transient LLM errors
            # Skip retry if all providers are in long cooldown (quota exhaustion)
            _retry_count = getattr(ctx, "_retry_count", 0)
            if is_llm_error and _retry_count < 3:
                min_cooldown = min(
                    (
                        max(0, cd - time.monotonic())
                        for cd in self._llm._provider_cooldown.values()
                    ),
                    default=0,
                )
                if min_cooldown > 300:
                    # All providers in quota cooldown — no point retrying soon
                    elapsed = int((time.monotonic() - t0) * 1000)
                    logger.warning(
                        "Agent %s skipping retry — providers in cooldown for %ds",
                        agent.id,
                        int(min_cooldown),
                    )
                    return ExecutionResult(
                        content=f"Error: {exc}",
                        agent_id=agent.id,
                        duration_ms=elapsed,
                        error=str(exc),
                    )
                ctx._retry_count = _retry_count + 1  # type: ignore[attr-defined]
                _backoffs = [5, 15, 45]
                base_wait = _backoffs[min(_retry_count, len(_backoffs) - 1)]
                import random
                wait = base_wait * (0.8 + 0.4 * random.random())  # ±20% jitter
                logger.warning(
                    "Agent %s LLM error, retry %d/3 in %ds: %s",
                    agent.id,
                    _retry_count + 1,
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

            # BM25 prompt-aware tool selection (streaming path) — same as run()
            if tools and len(tools) > 15:
                tools = _bm25_select(tools, user_message, top_k=10)

            # Tool-calling rounds (non-streaming) — same as run()
            deep_search_used = False
            final_content = ""
            write_count = 0  # track code_write calls so far (used in nudge condition)
            logger.warning(
                "Agent %s: tools_enabled=%s, tools=%s, allowed=%s",
                agent.id,
                ctx.tools_enabled,
                "YES" if tools else "NO",
                ctx.allowed_tools[:3] if ctx.allowed_tools else "all",
            )

            # Route provider: Darwin LLM Thompson Sampling + routing config
            from .routing import CHEAP_TOOLS as _CHEAP_TOOLS_2

            _cheap_mode_2 = bool(
                ctx.allowed_tools
                and ctx.tools_enabled
                and all(t in _CHEAP_TOOLS_2 for t in (ctx.allowed_tools or []))
            )
            use_provider, use_model = _route_provider(
                agent, tools, mission_id=ctx.epic_run_id, cheap_mode=_cheap_mode_2
            )

            _active_tools_2 = tools  # may be narrowed to 1 tool on nudge rounds
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
                    tools=_active_tools_2,
                )

                total_tokens_in += llm_resp.tokens_in
                total_tokens_out += llm_resp.tokens_out
                _write_llm_usage(
                    llm_resp.provider,
                    llm_resp.model,
                    llm_resp.tokens_in,
                    llm_resp.tokens_out,
                    ctx.project_id,
                    agent.id,
                    ctx.session_id,
                )
                _check_session_budget(ctx.session_id)
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
                    # Tool nudge: same as run() — if tools available and no tool calls returned,
                    # inject a "call a tool NOW" message and retry (up to 3 rounds).
                    if (
                        tools
                        and round_num <= 3
                        and not any(
                            t in final_content.lower()
                            for t in ["```", "result:", "output:", "error:"]
                        )
                    ):
                        messages.append(
                            LLMMessage(role="assistant", content=final_content)
                        )
                        messages.append(
                            LLMMessage(
                                role="user",
                                content=(
                                    "⚠️ ARRÊTE — ne décris pas ce que tu vas faire. "
                                    "APPELLE UN OUTIL MAINTENANT. "
                                    "Premier action = tool call obligatoire. "
                                    "Si tu es développeur : appelle code_write. "
                                    "Si tu es architecte : appelle code_write pour créer INCEPTION.md. "
                                    "Si tu es QA : appelle docker_deploy. "
                                    "Pas de texte introductif — agis directement."
                                ),
                            )
                        )
                        # Narrow to priority tool so MiniMax uses single-tool forced mode
                        _active_tools_2 = _priority_tool_list(tools)
                        continue  # retry with nudge

                    # If work was done (files written) but output is too short,
                    # inject a synthesis prompt so the adversarial can evaluate.
                    _written_count = sum(
                        1
                        for tc_rec in all_tool_calls
                        if tc_rec["name"] in ("code_write", "code_edit", "fractal_code")
                    )
                    if (
                        _written_count > 0
                        and len(final_content.strip()) < 80
                        and round_num < MAX_TOOL_ROUNDS - 1
                    ):
                        messages.append(
                            LLMMessage(role="assistant", content=final_content)
                        )
                        written_files = list(
                            {
                                tc_rec["args"].get("path", "")
                                for tc_rec in all_tool_calls
                                if tc_rec["name"] in ("code_write", "code_edit")
                                and tc_rec["args"].get("path")
                            }
                        )
                        files_str = ", ".join(written_files[:3]) or "les fichiers créés"
                        messages.append(
                            LLMMessage(
                                role="user",
                                content=(
                                    f"✅ Tu as écrit : {files_str}. "
                                    "Maintenant affiche le CONTENU COMPLET de ce que tu as créé. "
                                    "L'adversarial doit pouvoir lire et évaluer ton travail. "
                                    "Minimum 200 mots décrivant ce qui a été produit."
                                ),
                            )
                        )
                        tools = None  # final synthesis round — no more tools
                        continue

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
                # Tool was called → restore full tools for next round
                _active_tools_2 = tools
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
                    # ── QA scope enforcement (streaming): only QA_REPORT_* and Dockerfile ──
                    if tc.function_name in _CODE_WRITE_TOOLS:
                        _role_l = (agent.role or "").lower()
                        if "qa" in _role_l and "devops" not in _role_l:
                            _write_path = str(tc.arguments.get("path", ""))
                            _bn = _write_path.split("/")[-1]
                            _qa_ok = (
                                _bn.startswith("QA_REPORT")
                                or _bn == "Dockerfile"
                                or _bn.startswith("Dockerfile.")
                            )
                            if not _qa_ok:
                                messages.append(
                                    LLMMessage(
                                        role="tool",
                                        content=(
                                            f"Error: SCOPE VIOLATION — QA agent cannot write '{_bn}'. "
                                            "Allowed: QA_REPORT_N.md, Dockerfile (Chromium only). "
                                            "If docker_deploy fails → VETO. Do not fix source code."
                                        ),
                                        tool_call_id=tc.id,
                                        name=tc.function_name,
                                    )
                                )
                                logger.warning(
                                    "QA SCOPE VIOLATION agent=%s path=%s", agent.id, _bn
                                )
                                continue
                    # PRE_TOOL hook (may block)
                    _hook_ctx2 = HookContext(
                        hook_type=HookType.PRE_TOOL,
                        agent_id=agent.id,
                        session_id=ctx.session_id or "",
                        project_id=ctx.project_id or "",
                        tool_name=tc.function_name,
                        tool_args=dict(tc.arguments),
                    )
                    _pre_res2 = await _hook_registry.fire_pre(
                        HookType.PRE_TOOL, _hook_ctx2
                    )
                    if _pre_res2.blocked:
                        result = f"[BLOCKED by hook: {_pre_res2.message}]"
                    else:
                        result = await _execute_tool(tc, ctx, self._registry, self._llm)
                    # POST_TOOL hook
                    _hook_ctx2.hook_type = HookType.POST_TOOL
                    _hook_ctx2.tool_result = result[:200]
                    await _hook_registry.fire(HookType.POST_TOOL, _hook_ctx2)
                    # If schema was stripped to write-only but model still calls read tools,
                    # append a write reminder to the result (don't block, give context + nudge)
                    _allowed_tc_names = (
                        {t.get("function", {}).get("name") for t in tools}
                        if tools is not None
                        else None
                    )
                    _read_tools = {
                        "code_read",
                        "list_files",
                        "code_search",
                        "file_search",
                    }
                    if (
                        _allowed_tc_names is not None
                        and tc.function_name not in _allowed_tc_names
                        and tc.function_name in _read_tools
                    ):
                        # Hard rejection: don't execute, return error + nudge
                        result = (
                            f"Error: '{tc.function_name}' is not available. "
                            "You have enough context. Call code_write NOW to create the files."
                        )
                        messages.append(
                            LLMMessage(
                                role="tool",
                                content=result[:2000],
                                tool_call_id=tc.id,
                                name=tc.function_name,
                            )
                        )
                        yield ("tool", f"BLOCKED:{tc.function_name}")
                        continue
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
                        with get_db() as db:
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
                                import uuid as _uuid_s  # noqa: F401 (kept for compat)

                                messages.append(
                                    LLMMessage(
                                        role="user",
                                        content=(
                                            f"[AUTO-LINT] Lint/verification failed (round {_srep + 1}/{MAX_REPAIR_ROUNDS}). "
                                            "Fix all reported issues NOW before proceeding.\n\n"
                                            f"{_slint_res[:1500]}"
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
                    # Strip read-only tools — force write (allow Claude aliases: read_file, write_file)
                    write_only_tools = [
                        t
                        for t in tools
                        if t.get("function", {}).get("name")
                        in (
                            "code_write",
                            "code_edit",
                            "fractal_code",
                            "git_commit",
                            "read_file",
                            "write_file",
                            "read_many_files",
                            "edit_file",
                        )
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
                    and write_count < 3
                    and tools is not None
                ):
                    _last_written = next(
                        (
                            t["args"].get("path", "")
                            for t in reversed(all_tool_calls)
                            if t["name"] in ("code_write", "code_edit")
                        ),
                        "",
                    )
                    messages.append(
                        LLMMessage(
                            role="user",
                            content=(
                                f"✅ {_last_written or 'file'} written ({write_count}/3). "
                                "Write the NEXT required file NOW. "
                                "TDD: if no test file yet → code_write(path=WORKSPACE/tests/test_*.py, content=...) "
                                "otherwise write next source file or Dockerfile. "
                                "Call code_write IMMEDIATELY."
                            ),
                        )
                    )
                if round_num >= MAX_TOOL_ROUNDS - 2 and tools is not None:
                    if has_written and write_count >= 2:
                        tools = None
                        written_paths = list(
                            {
                                tc_rec["args"].get("path", "?")
                                for tc_rec in all_tool_calls
                                if tc_rec["name"] in ("code_write", "code_edit")
                                and tc_rec["args"].get("path")
                            }
                        )
                        files_str = ", ".join(written_paths[:4]) or "les fichiers"
                        messages.append(
                            LLMMessage(
                                role="system",
                                content=(
                                    f"✅ Fichiers créés/mis à jour : {files_str}.\n"
                                    "MAINTENANT : décris en détail ce que tu as produit. "
                                    "Liste chaque fichier, son contenu clé, sa structure, "
                                    "et comment il répond aux exigences. Minimum 200 mots. "
                                    "C'est ton rapport final au comité de validation."
                                ),
                            )
                        )
                    # else: keep write-only tools — agent MUST write code
            else:
                final_content = final_content or "(Max tool rounds reached)"

            elapsed = int((time.monotonic() - t0) * 1000)
            final_content = _strip_raw_tokens(final_content)
            delegations = self._parse_delegations(final_content)

            _update_mission_cost(ctx.session_id, ctx.epic_run_id)
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
            # Retry up to 3 times with exponential backoff for transient LLM errors
            _stream_retry_count = getattr(ctx, "_stream_retry_count", 0)
            if is_llm_error and _stream_retry_count < 3:
                min_cooldown = min(
                    (
                        max(0, cd - time.monotonic())
                        for cd in self._llm._provider_cooldown.values()
                    ),
                    default=0,
                )
                if min_cooldown > 300:
                    elapsed = int((time.monotonic() - t0) * 1000)
                    logger.warning(
                        "Agent %s streaming: skipping retry — providers in cooldown for %ds",
                        agent.id,
                        int(min_cooldown),
                    )
                    yield (
                        "result",
                        ExecutionResult(
                            content=f"Error: {exc}",
                            agent_id=agent.id,
                            duration_ms=elapsed,
                            error=str(exc),
                        ),
                    )
                    return
                ctx._stream_retry_count = _stream_retry_count + 1  # type: ignore[attr-defined]
                _backoffs = [5, 15, 45]
                base_wait = _backoffs[min(_stream_retry_count, len(_backoffs) - 1)]
                import random
                wait = base_wait * (0.8 + 0.4 * random.random())
                logger.warning(
                    "Agent %s streaming LLM error, retry %d/3 in %ds: %s",
                    agent.id,
                    _stream_retry_count + 1,
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
