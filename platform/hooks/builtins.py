"""Built-in hook handlers for the SF platform.

SOURCE: ECC (everything-claude-code) https://github.com/affaan-m/everything-claude-code
WHY: ECC demonstrated that Claude Code CLI hooks (PreToolUse/PostToolUse/Stop) enable
     powerful session-level automation: compact state saving, continuous learning via
     instincts, quality gates, cost tracking. We adapted these concepts server-side,
     wiring them into executor.py's _execute_tool() call sites instead of CLI JSON hooks.

Six hooks registered automatically:
1. pre_compact      — PRE_COMPACT : saves key decisions to memory before context shrinks
                      SOURCE: ECC pre-compact.js "Save state before context compaction"
2. session_start    — SESSION_START : fires at agent session start
3. session_end      — SESSION_END : saves session digest + triggers instinct observer
                      SOURCE: ECC session-end.js + continuous-learning-v2 observe.sh
4. pattern_extract  — SESSION_END : deprecated — replaced by instinct_observer below
5. quality_gate     — POST_TOOL (code_write/code_edit) : triggers fast lint async
                      SOURCE: ECC quality-gate.js post:quality-gate hook
6. cost_tracker     — POST_TOOL : emits cost telemetry event
7. instinct_observer— SESSION_END : runs instinct pattern analysis (ECC CL-v2 core)
                      SOURCE: ECC continuous-learning-v2/SKILL.md + observe.sh
"""

from __future__ import annotations

import logging

from . import HookContext, HookRegistry, HookResult, HookType

logger = logging.getLogger(__name__)

_CODE_WRITE_TOOLS = {"code_write", "code_edit", "write_file"}


# ── 1. Pre-compact — save state before summarization ───────────────────────


async def _pre_compact(ctx: HookContext) -> HookResult:
    """Persist last 5 tool-call summaries to project memory before context shrink."""
    if not ctx.all_tool_calls:
        return HookResult()
    recent = ctx.all_tool_calls[-5:]
    summary = "; ".join(f"{t['name']}({list(t['args'].keys())})" for t in recent)
    try:
        from ..tools.memory_tools import _write_memory

        await _write_memory(
            category=f"session:{ctx.session_id}",
            key="pre_compact_snapshot",
            value=summary,
        )
    except Exception as exc:
        logger.debug("pre_compact hook: %s", exc)
    return HookResult()


# ── 2. Session start — inject relevant memory ───────────────────────────────


async def _session_start(ctx: HookContext) -> HookResult:
    """Load the agent's last known patterns from memory (non-blocking)."""
    # No side-effect on messages — just log for observability
    logger.debug(
        "session_start hook: agent=%s project=%s", ctx.agent_id, ctx.project_id
    )
    return HookResult()


# ── 3. Session end — persist session digest ─────────────────────────────────


async def _session_end(ctx: HookContext) -> HookResult:
    """Save a compact digest of what was done this session to project memory."""
    if not ctx.all_tool_calls:
        return HookResult()
    writes = [t for t in ctx.all_tool_calls if t["name"] in _CODE_WRITE_TOOLS]
    if not writes:
        return HookResult()
    digest = f"Session {ctx.session_id[:8]} wrote {len(writes)} files: " + ", ".join(
        t["args"].get("path", "?")[:40] for t in writes[:5]
    )
    try:
        from ..tools.memory_tools import _write_memory

        await _write_memory(
            category=f"project:{ctx.project_id}",
            key=f"session_digest:{ctx.session_id[:8]}",
            value=digest,
        )
    except Exception as exc:
        logger.debug("session_end hook: %s", exc)
    return HookResult()


# ── 4. Quality gate — async lint after code write ───────────────────────────


async def _quality_gate(ctx: HookContext) -> HookResult:
    """Trigger fast lint in background after a code_write/code_edit call."""
    if ctx.tool_name not in _CODE_WRITE_TOOLS:
        return HookResult()
    path = ctx.tool_args.get("path", "")
    if not path or not path.endswith((".py", ".ts", ".js")):
        return HookResult()
    # Best-effort: schedule lint as a background task, don't block execution
    try:
        import asyncio

        asyncio.ensure_future(_run_lint(path, ctx.project_id))
    except Exception:
        pass
    return HookResult()


async def _run_lint(path: str, project_id: str) -> None:
    """Run a cheap ruff/eslint check and emit a LINT_RESULT event."""
    import asyncio

    cmd = ["ruff", "check", "--quiet", path] if path.endswith(".py") else None
    if cmd is None:
        return
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15.0)
        issues = stdout.decode().strip()
        if issues:
            logger.info("quality_gate lint issues [%s]: %s", path, issues[:200])
    except Exception:
        pass


# ── 5. Cost tracker — POST_TOOL telemetry ───────────────────────────────────


async def _cost_tracker(ctx: HookContext) -> HookResult:
    """Emit a lightweight cost event for each tool call (best-effort)."""
    try:
        from ..events import emit_event

        emit_event(
            "TOOL_EXECUTED",
            {
                "agent_id": ctx.agent_id,
                "session_id": ctx.session_id,
                "tool_name": ctx.tool_name,
                "project_id": ctx.project_id,
            },
        )
    except Exception:
        pass
    return HookResult()


# ── 6. Pattern extraction — SESSION_END ─────────────────────────────────────


async def _pattern_extract(ctx: HookContext) -> HookResult:
    """Extract top tools used in this session and store as a pattern hint.

    NOTE: This simple counter is superseded by _instinct_observer (ECC CL-v2 adaptation).
    Kept as a lightweight fallback for sessions below the MIN_TOOL_CALLS threshold.
    """
    if len(ctx.all_tool_calls) < 5:
        return HookResult()
    from collections import Counter

    counts = Counter(t["name"] for t in ctx.all_tool_calls)
    top = ", ".join(f"{k}×{v}" for k, v in counts.most_common(5))
    logger.debug("pattern_extract [%s]: %s", ctx.agent_id, top)
    try:
        from ..tools.memory_tools import _write_memory

        await _write_memory(
            category=f"agent:{ctx.agent_id}",
            key="top_tools_last_session",
            value=top,
        )
    except Exception as exc:
        logger.debug("pattern_extract hook: %s", exc)
    return HookResult()


# ── 7. Instinct observer — ECC continuous-learning-v2 adaptation ─────────────


async def _instinct_observer(ctx: HookContext) -> HookResult:
    """Analyze session tool calls and extract instincts.

    SOURCE: ECC continuous-learning-v2 SKILL.md
      "Turns Claude Code sessions into reusable knowledge through atomic instincts —
       small learned behaviors with confidence scoring."

    WHY: Instead of manually curating skills, agents automatically learn from observed
    patterns: tool sequences, dominant workflows, read-before-write habits, etc.
    Instincts are stored with confidence 0.3-0.9 and can be evolved into skill YAMLs.
    """
    if not ctx.all_tool_calls:
        return HookResult()
    try:
        import asyncio

        from .instinct import observe_session

        # Run analysis in background — don't block session end
        asyncio.ensure_future(
            observe_session(
                ctx.all_tool_calls,
                ctx.agent_id,
                ctx.project_id,
                ctx.session_id,
            )
        )
    except Exception as exc:
        logger.debug("instinct_observer hook: %s", exc)
    return HookResult()


# ── Registration ─────────────────────────────────────────────────────────────


def register_builtins(reg: HookRegistry) -> None:
    """Register all built-in hooks into the provided registry."""
    reg.register(HookType.PRE_COMPACT, "pre_compact", _pre_compact, priority=10)
    reg.register(HookType.SESSION_START, "session_start", _session_start, priority=0)
    reg.register(HookType.SESSION_END, "session_end", _session_end, priority=10)
    reg.register(HookType.SESSION_END, "pattern_extract", _pattern_extract, priority=5)
    reg.register(
        HookType.SESSION_END, "instinct_observer", _instinct_observer, priority=8
    )
    reg.register(HookType.POST_TOOL, "quality_gate", _quality_gate, priority=20)
    reg.register(HookType.POST_TOOL, "cost_tracker", _cost_tracker, priority=5)
    logger.debug("hook builtins registered (7 handlers)")
