"""Session Runner — connects user messages to agent execution.

When a user sends a message in a session:
1. Find the lead agent (or target agent)
2. Build execution context (history, project memory, skills, vision)
3. Call AgentExecutor → LLM
4. Store response as agent message
5. Handle delegations (spawn sub-agent calls)
6. Push SSE events for live UI
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from ..agents.store import get_agent_store, AgentDef
from ..agents.executor import get_executor, ExecutionContext
from ..sessions.store import get_session_store, MessageDef, SessionDef
from ..projects.manager import get_project_store
from ..memory.manager import get_memory_manager
from ..skills.library import get_skill_library

logger = logging.getLogger(__name__)

# Track running agent tasks
_running_tasks: dict[str, asyncio.Task] = {}
# SSE event queues for live updates
_sse_queues: dict[str, list[asyncio.Queue]] = {}


def add_sse_listener(session_id: str) -> asyncio.Queue:
    """Register a queue to receive live events for a session."""
    q: asyncio.Queue = asyncio.Queue(maxsize=200)
    _sse_queues.setdefault(session_id, []).append(q)
    return q


def remove_sse_listener(session_id: str, q: asyncio.Queue):
    if session_id in _sse_queues:
        try:
            _sse_queues[session_id].remove(q)
        except ValueError:
            pass
        if not _sse_queues[session_id]:
            del _sse_queues[session_id]


async def _push_sse(session_id: str, event: dict):
    """Push an event to all SSE listeners for this session."""
    for q in _sse_queues.get(session_id, []):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


async def handle_user_message(session_id: str, content: str, to_agent: str = "") -> Optional[MessageDef]:
    """Process a user message: call the lead agent, return its response.

    This is the main entry point called from the route handler.
    It runs the agent asynchronously and stores the response.
    """
    store = get_session_store()
    session = store.get(session_id)
    if not session:
        return None

    # Determine target agent
    agent_id = to_agent or session.config.get("lead_agent") or "brain"
    agent_store = get_agent_store()
    agent = agent_store.get(agent_id)
    if not agent:
        # Fallback: use first available agent
        all_agents = agent_store.list_all()
        agent = all_agents[0] if all_agents else None
    if not agent:
        return store.add_message(MessageDef(
            session_id=session_id,
            from_agent="system",
            message_type="system",
            content="No agent available to respond.",
        ))

    # Push "thinking" event
    await _push_sse(session_id, {
        "type": "agent_status",
        "agent_id": agent.id,
        "status": "thinking",
    })

    # Build context
    ctx = await _build_context(agent, session)

    # Run executor
    executor = get_executor()
    result = await executor.run(ctx, content)

    # Store agent response
    msg_type = "text"
    if result.error:
        msg_type = "system"
    elif "[VETO]" in result.content:
        msg_type = "veto"
    elif "[APPROVE]" in result.content:
        msg_type = "approve"
    elif "[DELEGATE:" in result.content:
        msg_type = "delegate"

    agent_msg = store.add_message(MessageDef(
        session_id=session_id,
        from_agent=agent.id,
        to_agent="user",
        message_type=msg_type,
        content=result.content,
        metadata={
            "model": result.model,
            "provider": result.provider,
            "tokens_in": result.tokens_in,
            "tokens_out": result.tokens_out,
            "duration_ms": result.duration_ms,
        },
    ))

    # Push SSE
    await _push_sse(session_id, {
        "type": "message",
        "id": agent_msg.id,
        "from_agent": agent.id,
        "content": result.content,
        "message_type": msg_type,
        "model": result.model,
        "tokens": result.tokens_in + result.tokens_out,
    })

    await _push_sse(session_id, {
        "type": "agent_status",
        "agent_id": agent.id,
        "status": "idle",
    })

    # Handle delegations
    for d in result.delegations:
        asyncio.create_task(_handle_delegation(
            session_id, agent.id, d["to_agent"], d["task"]))

    # Store in project memory if meaningful
    if session.project_id and not result.error:
        try:
            mem = get_memory_manager()
            mem.project_store(
                session.project_id,
                key=f"conversation:{session_id}",
                value=f"Q: {content[:100]}\nA: {result.content[:200]}",
                category="conversations",
                source=agent.id,
            )
        except Exception:
            pass

    return agent_msg


async def _build_context(agent: AgentDef, session: SessionDef) -> ExecutionContext:
    """Build the execution context for an agent."""
    store = get_session_store()
    history = store.get_messages(session.id, limit=30)
    history_dicts = [{"from_agent": m.from_agent, "content": m.content,
                      "message_type": m.message_type} for m in history]

    # Load project context if available
    project_context = ""
    vision = ""
    if session.project_id:
        try:
            proj_store = get_project_store()
            project = proj_store.get(session.project_id)
            if project:
                vision = project.vision[:3000] if project.vision else ""
                # Load project memory
                mem = get_memory_manager()
                entries = mem.project_get(session.project_id, limit=10)
                if entries:
                    project_context = "\n".join(
                        f"[{e['category']}] {e['key']}: {e['value'][:200]}"
                        for e in entries
                    )
        except Exception as exc:
            logger.debug("Failed to load project context: %s", exc)

    # Load skills prompt
    skills_prompt = ""
    if agent.skills:
        try:
            lib = get_skill_library()
            parts = []
            for sid in agent.skills[:5]:
                skill = lib.get(sid)
                if skill and skill.get("content"):
                    parts.append(f"### {skill['name']}\n{skill['content'][:1500]}")
            skills_prompt = "\n\n".join(parts)
        except Exception:
            pass

    return ExecutionContext(
        agent=agent,
        session_id=session.id,
        project_id=session.project_id,
        history=history_dicts,
        project_context=project_context,
        skills_prompt=skills_prompt,
        vision=vision,
    )


async def _handle_delegation(session_id: str, from_agent: str,
                              to_agent_id: str, task: str):
    """Handle an agent delegating a task to another agent."""
    store = get_session_store()
    agent_store = get_agent_store()
    target = agent_store.get(to_agent_id)

    if not target:
        store.add_message(MessageDef(
            session_id=session_id,
            from_agent="system",
            message_type="system",
            content=f"Delegation failed: agent '{to_agent_id}' not found.",
        ))
        return

    # Log delegation
    store.add_message(MessageDef(
        session_id=session_id,
        from_agent=from_agent,
        to_agent=to_agent_id,
        message_type="delegate",
        content=f"Delegating to {target.name}: {task}",
    ))

    await _push_sse(session_id, {
        "type": "delegation",
        "from": from_agent,
        "to": to_agent_id,
        "task": task,
    })

    # Execute the delegated agent
    session = store.get(session_id)
    if session:
        ctx = await _build_context(target, session)
        executor = get_executor()
        result = await executor.run(ctx, f"[Task from {from_agent}]: {task}")

        store.add_message(MessageDef(
            session_id=session_id,
            from_agent=to_agent_id,
            to_agent=from_agent,
            message_type="text",
            content=result.content,
            metadata={
                "model": result.model, "provider": result.provider,
                "tokens_in": result.tokens_in, "tokens_out": result.tokens_out,
            },
        ))

        await _push_sse(session_id, {
            "type": "message",
            "id": "",
            "from_agent": to_agent_id,
            "content": result.content,
            "message_type": "text",
        })
