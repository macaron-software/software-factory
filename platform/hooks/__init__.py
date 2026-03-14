"""Hook system — PreToolUse / PostToolUse / SessionStart / SessionEnd / PreCompact.

SOURCE: ECC (everything-claude-code) https://github.com/affaan-m/everything-claude-code
WHY: ECC demonstrated that Claude Code CLI hooks enable powerful automation. We adapted
     the concept server-side, hooking into executor.py's _execute_tool() call sites.

     Key ECC concepts adopted:
     - PRE_TOOL / POST_TOOL hooks around every tool execution (ECC: PreToolUse/PostToolUse)
     - PRE_COMPACT hook before context summarization (ECC: PreCompact)
     - SESSION_START / SESSION_END lifecycle hooks (ECC: SessionStart / Stop)
     - HookResult.blocked — only PRE_TOOL hooks may block (ECC: exit code 2 = block)
     - Priority-ordered execution — higher priority fires first

     Key differences from ECC:
     - No CLI JSON stdin/stdout — we use Python async handlers in-process
     - No shell scripts — pure Python, no node.js dependency
     - RBAC-gated registration (see hooks/rbac.py)
     - Hook log persisted to DB (hook_log table) for observability

Usage (built-in registration happens automatically at module import):

    from platform.hooks import registry, HookType, HookContext

    async def my_hook(ctx: HookContext) -> HookResult:
        return HookResult()

    registry.register(HookType.POST_TOOL, "my-hook", my_hook, agent_id="ac-codex")

    # Executor fires PRE_TOOL (can block):
    result = await registry.fire_pre(HookType.PRE_TOOL, ctx)
    if result.blocked:
        return f"[BLOCKED: {result.message}]"

    # Executor fires POST_TOOL (no block):
    await registry.fire(HookType.POST_TOOL, ctx)
"""
# Ref: feat-quality

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

logger = logging.getLogger(__name__)


class HookType(str, Enum):
    PRE_TOOL = "pre_tool"
    POST_TOOL = "post_tool"
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    PRE_COMPACT = "pre_compact"


@dataclass
class HookContext:
    """Context passed to every hook handler."""

    hook_type: HookType
    agent_id: str = ""
    session_id: str = ""
    project_id: str = ""
    tool_name: str = ""
    tool_args: dict = field(default_factory=dict)
    tool_result: str = ""
    messages: list = field(default_factory=list)
    all_tool_calls: list = field(default_factory=list)
    extra: dict = field(default_factory=dict)


@dataclass
class HookResult:
    """Result returned by a hook handler."""

    blocked: bool = False
    message: str = ""
    data: dict = field(default_factory=dict)


HookHandler = Callable[[HookContext], Coroutine[Any, Any, HookResult]]


@dataclass
class _Registration:
    id: str
    hook_type: HookType
    handler_name: str
    handler: HookHandler
    agent_id: Optional[str]  # None = global (fires for all agents)
    priority: int = 0
    enabled: bool = True
    can_block: bool = False  # only PRE_TOOL may block
    required_role: Optional[str] = None


class HookRegistry:
    """Central registry for hook handlers.

    Thread-safe for reads; registrations happen at startup or via API.
    """

    def __init__(self) -> None:
        self._hooks: dict[HookType, list[_Registration]] = {t: [] for t in HookType}
        self._by_id: dict[str, _Registration] = {}

    def register(
        self,
        hook_type: HookType,
        handler_name: str,
        handler: HookHandler,
        *,
        agent_id: Optional[str] = None,
        priority: int = 0,
        can_block: bool = False,
        required_role: Optional[str] = None,
        reg_id: Optional[str] = None,
    ) -> str:
        """Register a hook handler. Returns registration ID."""
        if can_block and hook_type != HookType.PRE_TOOL:
            raise ValueError("can_block=True is only valid for PRE_TOOL hooks")
        rid = reg_id or str(uuid.uuid4())
        reg = _Registration(
            id=rid,
            hook_type=hook_type,
            handler_name=handler_name,
            handler=handler,
            agent_id=agent_id,
            priority=priority,
            enabled=True,
            can_block=can_block,
            required_role=required_role,
        )
        self._hooks[hook_type].append(reg)
        self._hooks[hook_type].sort(key=lambda r: -r.priority)
        self._by_id[rid] = reg
        logger.debug(
            "hook registered: %s/%s (id=%s)", hook_type.value, handler_name, rid
        )
        return rid

    def unregister(self, reg_id: str) -> bool:
        reg = self._by_id.pop(reg_id, None)
        if reg is None:
            return False
        self._hooks[reg.hook_type] = [
            r for r in self._hooks[reg.hook_type] if r.id != reg_id
        ]
        return True

    def toggle(self, reg_id: str, enabled: bool) -> bool:
        reg = self._by_id.get(reg_id)
        if reg is None:
            return False
        reg.enabled = enabled
        return True

    def list_all(self, agent_id: Optional[str] = None) -> list[dict]:
        result = []
        for regs in self._hooks.values():
            for r in regs:
                if agent_id and r.agent_id and r.agent_id != agent_id:
                    continue
                result.append(
                    {
                        "id": r.id,
                        "hook_type": r.hook_type.value,
                        "handler_name": r.handler_name,
                        "agent_id": r.agent_id,
                        "priority": r.priority,
                        "enabled": r.enabled,
                        "can_block": r.can_block,
                        "required_role": r.required_role,
                    }
                )
        return result

    async def fire_pre(self, hook_type: HookType, ctx: HookContext) -> HookResult:
        """Fire PRE_TOOL hooks. Returns first blocking result, or empty HookResult."""
        for reg in self._hooks.get(hook_type, []):
            if not reg.enabled:
                continue
            if reg.agent_id and reg.agent_id != ctx.agent_id:
                continue
            t0 = time.monotonic()
            try:
                result = await asyncio.wait_for(reg.handler(ctx), timeout=5.0)
                _log_hook(reg, ctx, result, int((time.monotonic() - t0) * 1000))
                if result.blocked and reg.can_block:
                    return result
            except Exception as exc:
                logger.warning(
                    "hook %s/%s error: %s", hook_type.value, reg.handler_name, exc
                )
        return HookResult()

    async def fire(self, hook_type: HookType, ctx: HookContext) -> None:
        """Fire non-blocking hooks (fire-and-forget per handler)."""
        for reg in self._hooks.get(hook_type, []):
            if not reg.enabled:
                continue
            if reg.agent_id and reg.agent_id != ctx.agent_id:
                continue
            t0 = time.monotonic()
            try:
                result = await asyncio.wait_for(reg.handler(ctx), timeout=10.0)
                _log_hook(reg, ctx, result, int((time.monotonic() - t0) * 1000))
            except Exception as exc:
                logger.warning(
                    "hook %s/%s error: %s", hook_type.value, reg.handler_name, exc
                )


def _log_hook(
    reg: _Registration, ctx: HookContext, result: HookResult, ms: int
) -> None:
    """Persist hook execution to hook_log table (best-effort)."""
    try:
        from ..db.migrations import get_db

        with get_db() as db:
            db.execute(
                """INSERT OR IGNORE INTO hook_log
                   (id, hook_type, handler_name, agent_id, session_id, tool_name, blocked, message, duration_ms)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    str(uuid.uuid4()),
                    reg.hook_type.value,
                    reg.handler_name,
                    ctx.agent_id,
                    ctx.session_id,
                    ctx.tool_name,
                    1 if result.blocked else 0,
                    result.message[:500] if result.message else "",
                    ms,
                ),
            )
    except Exception:
        pass  # Never crash the executor over a logging failure


# Global singleton
registry = HookRegistry()


def _bootstrap_builtins() -> None:
    """Register all built-in hooks on first import."""
    try:
        from .builtins import register_builtins

        register_builtins(registry)
    except Exception as exc:
        logger.warning("hook builtins bootstrap failed: %s", exc)


_bootstrap_builtins()
