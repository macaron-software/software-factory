"""RBAC enforcement for hook registration and execution.

Rules:
- PRE_TOOL with can_block=True → agents with scope=platform OR category in (security, architecture)
- PRE_TOOL non-blocking       → any agent with can_execute=True
- POST_TOOL                   → any agent with can_execute=True
- SESSION_START / SESSION_END → scope=platform agents or whitelist
- PRE_COMPACT                 → any active agent
"""
# Ref: feat-rbac

from __future__ import annotations


# Agents that may register SESSION_START / SESSION_END hooks
_SESSION_HOOK_WHITELIST = {
    "ac-architect",
    "ac-coach",
    "strat-cto",
    "rte",
    "product",
    "scrum_master",
}

# Agent categories/scopes allowed to register blocking PRE_TOOL hooks
_BLOCKING_ALLOWED_SCOPES = {"platform"}
_BLOCKING_ALLOWED_CATEGORIES = {"security", "architecture", "strategique"}


def can_register_hook(
    agent: dict,
    hook_type: str,
    can_block: bool = False,
) -> tuple[bool, str]:
    """Return (allowed, reason).

    agent dict keys: id, scope, category, permissions (dict).
    """
    agent_id = agent.get("id", "")
    scope = agent.get("scope", "project")
    category = agent.get("category", "")
    perms = agent.get("permissions") or {}
    can_exec = perms.get("can_execute", True)

    if hook_type == "pre_tool":
        if can_block:
            if (
                scope in _BLOCKING_ALLOWED_SCOPES
                or category in _BLOCKING_ALLOWED_CATEGORIES
            ):
                return True, ""
            return (
                False,
                "Blocking PRE_TOOL hooks require scope=platform or security/architecture category",
            )
        if not can_exec:
            return False, "Agent lacks can_execute permission"
        return True, ""

    if hook_type == "post_tool":
        if not can_exec:
            return False, "Agent lacks can_execute permission"
        return True, ""

    if hook_type in ("session_start", "session_end"):
        if scope in _BLOCKING_ALLOWED_SCOPES or agent_id in _SESSION_HOOK_WHITELIST:
            return True, ""
        return False, "SESSION hooks require scope=platform or whitelisted agent"

    if hook_type == "pre_compact":
        return True, ""

    return False, f"Unknown hook type: {hook_type}"


def can_view_hooks(agent: dict) -> bool:
    """Returns True if the agent may list/read the hook registry."""
    scope = agent.get("scope", "project")
    perms = agent.get("permissions") or {}
    return scope in _BLOCKING_ALLOWED_SCOPES or perms.get("can_execute", True)
