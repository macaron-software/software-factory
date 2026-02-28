"""Session Runner — connects user messages to agent execution.

When a user sends a message in a session:
1. Find the lead agent (or target agent)
2. Build execution context (history, project memory, skills, vision)
3. Call AgentExecutor → LLM (with optional SSE streaming)
4. Store response as agent message
5. Handle delegations / multi-agent conversation rounds
6. Push SSE events for live UI
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional

from ..agents.store import get_agent_store, AgentDef
from ..agents.executor import get_executor, ExecutionContext
from ..sessions.store import get_session_store, MessageDef, SessionDef
from ..projects.manager import get_project_store
from ..memory.manager import get_memory_manager
from ..skills.library import get_skill_library
from ..llm.client import LLMMessage, get_llm_client

logger = logging.getLogger(__name__)

# Track running agent tasks
_running_tasks: dict[str, asyncio.Task] = {}
# SSE event queues for live updates
_sse_queues: dict[str, list[asyncio.Queue]] = {}


def add_sse_listener(session_id: str) -> asyncio.Queue:
    """Register a queue to receive live events for a session."""
    q: asyncio.Queue = asyncio.Queue(maxsize=2000)
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
    """Push an event to all SSE listeners for this session.

    Delivers to both the runner's per-session queues AND the bus's global SSE listeners
    so that the /sse/session/{id} endpoint picks up mission control events.
    """
    # Runner queues (per-session, used by conversation pages)
    for q in _sse_queues.get(session_id, []):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("SSE queue full for session %s, dropping %s event", session_id, event.get("type"))

    # Bus SSE listeners (global, used by /sse/session/{id} endpoint)
    try:
        from ..a2a.bus import get_bus
        bus = get_bus()
        # Inject session_id into dict so the SSE filter in ws.py can match
        enriched = {**event, "session_id": session_id}
        for q in bus._sse_listeners:
            try:
                q.put_nowait(enriched)
            except asyncio.QueueFull:
                pass
    except Exception:
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
            "tool_calls": result.tool_calls if result.tool_calls else None,
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

    # Store in project memory if meaningful (skip short/trivial)
    if session.project_id and not result.error and len(result.content) > 50:
        try:
            mem = get_memory_manager()
            # Extract key info, not raw Q&A dump
            answer = result.content[:300].strip()
            mem.project_store(
                session.project_id,
                key=f"{agent.name}: {content[:60]}",
                value=answer,
                category="conversations",
                source=agent.id,
            )
        except Exception:
            pass

    return agent_msg


async def _build_context(agent: AgentDef, session: SessionDef) -> ExecutionContext:
    """Build the execution context for an agent."""
    store = get_session_store()
    history = store.get_messages(session.id, limit=50)
    history_dicts = [{"from_agent": m.from_agent, "content": m.content,
                      "message_type": m.message_type} for m in history]

    # Compress history if too long
    project_name = ""
    if session.project_id:
        try:
            proj_store = get_project_store()
            p = proj_store.get(session.project_id)
            project_name = p.name if p else ""
        except Exception:
            pass

    try:
        from .compressor import compress_history
        cached_summary = session.config.get("_summary")
        cached_hash = session.config.get("_summary_hash")
        history_dicts, new_summary, new_hash = await compress_history(
            history_dicts, project_name, cached_summary, cached_hash
        )
        # Cache the summary in session config for next time
        if new_summary and new_hash:
            session.config["_summary"] = new_summary
            session.config["_summary_hash"] = new_hash
            store.update_config(session.id, session.config)
    except Exception as exc:
        logger.debug("Context compression skipped: %s", exc)

    # Load project context if available
    project_context = ""
    vision = ""
    project_path = ""
    if session.project_id:
        try:
            proj_store = get_project_store()
            project = proj_store.get(session.project_id)
            if project:
                vision = project.vision[:3000] if project.vision else ""
                project_path = getattr(project, "path", "") or ""
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

    # Load project memory files (CLAUDE.md, copilot-instructions.md, etc.)
    project_memory_str = ""
    if project_path:
        try:
            from ..memory.project_files import get_project_memory
            pmem = get_project_memory(session.project_id or "", project_path)
            project_memory_str = pmem.combined
        except Exception as exc:
            logger.debug("Failed to load project memory files: %s", exc)

    # Load domain context (projects/domains/<arch_domain>.yaml)
    domain_context_str = ""
    try:
        from ..projects.manager import get_project_store
        from ..projects.domains import load_domain
        proj = get_project_store().get(session.project_id or "")
        if proj and proj.arch_domain:
            domain = load_domain(proj.arch_domain)
            if domain:
                domain_context_str = domain.to_context_string()
                logger.info("[Domain] Injecting domain '%s' into agent %s", proj.arch_domain, agent.id)
    except Exception as exc:
        logger.debug("Failed to load domain context: %s", exc)

    # Apply role-based tool restrictions
    from ..agents.tool_schemas import _classify_agent_role, ROLE_TOOL_MAP
    _role_cat = _classify_agent_role(agent)
    _allowed_tools = ROLE_TOOL_MAP.get(_role_cat)  # None = all tools (fallback)

    return ExecutionContext(
        agent=agent,
        session_id=session.id,
        project_id=session.project_id,
        project_path=project_path,
        history=history_dicts,
        project_context=project_context,
        project_memory=project_memory_str,
        domain_context=domain_context_str,
        skills_prompt=skills_prompt,
        vision=vision,
        allowed_tools=_allowed_tools,
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


# ── Multi-agent conversation with streaming ─────────────────────

# Regex to parse @mentions and [DELEGATE:id] in agent output
_MENTION_RE = re.compile(r"@(\w[\w_-]*)")
_DELEGATE_RE = re.compile(r"\[DELEGATE:([^\]]+)\]\s*(.*?)(?=\[DELEGATE:|\[VETO|\[APPROVE\]|\[ASK:|\[ESCALATE|\Z)", re.DOTALL)


async def run_conversation(
    session_id: str,
    initial_message: str,
    agent_ids: list[str],
    max_rounds: int = 8,
    lead_agent_id: str = "",
):
    """Run a real multi-agent conversation with streaming.

    Agents discuss in rounds: each agent sees the full conversation so far,
    can @mention others, delegate, agree, or disagree. The conversation
    continues until agents reach consensus or max_rounds is hit.

    SSE events emitted:
      - stream_start: agent begins speaking (shows typing indicator)
      - stream_delta: token chunk (for progressive display)
      - stream_end:   agent finished (full message stored)
      - conversation_end: all rounds done
    """
    store = get_session_store()
    agent_store = get_agent_store()
    session = store.get(session_id)
    if not session:
        return

    # Resolve agents
    agents: list[AgentDef] = []
    for aid in agent_ids:
        a = agent_store.get(aid)
        if a:
            agents.append(a)
    if not agents:
        return

    lead = agent_store.get(lead_agent_id) if lead_agent_id else agents[0]
    if not lead:
        lead = agents[0]

    # Store initial user/system message
    store.add_message(MessageDef(
        session_id=session_id, from_agent="user",
        message_type="delegate", content=initial_message,
    ))
    await _push_sse(session_id, {
        "type": "message", "from_agent": "user",
        "content": initial_message, "message_type": "delegate",
    })

    # Build agent name map for context
    agent_names = {a.id: a.name for a in agents}
    agent_roles = {a.id: a.role for a in agents}

    # Conversation loop: lead speaks first, then others respond
    conversation_msgs: list[dict] = [
        {"from": "user", "name": "User", "content": initial_message}
    ]

    for round_num in range(max_rounds):
        # Determine speaking order: lead first in round 0, then rotate
        if round_num == 0:
            order = [lead] + [a for a in agents if a.id != lead.id]
        else:
            # Only agents that were mentioned or need to respond
            order = _determine_speakers(conversation_msgs, agents, round_num)

        if not order:
            break  # No one needs to speak

        anyone_spoke = False
        for agent in order:
            # Build conversation context for this agent
            ctx = await _build_context(agent, session)

            # Build the prompt with full conversation history
            conv_prompt = _build_conversation_prompt(
                agent, agents, conversation_msgs, round_num, initial_message,
            )

            # Signal: agent starts thinking
            await _push_sse(session_id, {
                "type": "stream_start",
                "agent_id": agent.id,
                "agent_name": agent.name,
                "round": round_num,
            })

            # Stream the response
            full_content = await _stream_agent_response(
                session_id, agent, ctx, conv_prompt
            )

            if not full_content or full_content.strip() == "":
                await _push_sse(session_id, {
                    "type": "stream_end", "agent_id": agent.id,
                    "content": "", "skipped": True,
                })
                continue

            anyone_spoke = True

            # Store in DB
            msg = store.add_message(MessageDef(
                session_id=session_id,
                from_agent=agent.id,
                message_type="text",
                content=full_content,
            ))

            # Push full message for non-streaming clients
            await _push_sse(session_id, {
                "type": "stream_end",
                "agent_id": agent.id,
                "msg_id": msg.id if msg else "",
                "content": full_content,
                "message_type": "text",
            })

            # Track in conversation
            conversation_msgs.append({
                "from": agent.id,
                "name": agent.name,
                "role": agent.role,
                "content": full_content,
            })

            # Small delay between agents for readability
            await asyncio.sleep(0.3)

        if not anyone_spoke:
            break

        # Check for consensus or explicit end
        if _conversation_concluded(conversation_msgs):
            break

    # Signal conversation end
    await _push_sse(session_id, {
        "type": "conversation_end",
        "rounds": round_num + 1,
        "messages": len(conversation_msgs),
    })


def _determine_speakers(
    conversation: list[dict], agents: list[AgentDef], round_num: int
) -> list[AgentDef]:
    """Determine which agents should speak in this round.

    Logic: agents who were @mentioned, delegated to, or asked a question
    in the previous messages should respond. If none targeted specifically,
    all agents respond (round-robin).
    """
    if round_num == 0:
        return agents

    # Scan last round's messages for mentions/delegates
    mentioned_ids: set[str] = set()
    agent_ids = {a.id for a in agents}
    agent_name_to_id = {}
    for a in agents:
        # Map both ID and parts of the name
        agent_name_to_id[a.id] = a.id
        for part in a.name.lower().split():
            agent_name_to_id[part] = a.id

    # Look at messages from the last round
    for msg in conversation[-len(agents):]:
        content = msg.get("content", "")
        # @mentions
        for m in _MENTION_RE.finditer(content):
            ref = m.group(1).lower().replace("-", "_")
            if ref in agent_name_to_id:
                mentioned_ids.add(agent_name_to_id[ref])
            # Also try partial name match
            for name_part, aid in agent_name_to_id.items():
                if ref == name_part:
                    mentioned_ids.add(aid)
        # [DELEGATE:xxx] tags
        for d in _DELEGATE_RE.finditer(content):
            target = d.group(1).strip()
            if target in agent_ids:
                mentioned_ids.add(target)
        # Questions (contains ?)
        if "?" in content:
            # If a question was asked, let everyone respond
            mentioned_ids = agent_ids
            break

    # If nobody specifically mentioned, let everyone talk (max 3 rounds)
    if not mentioned_ids and round_num < 3:
        return agents

    return [a for a in agents if a.id in mentioned_ids]


def _build_conversation_prompt(
    agent: AgentDef,
    all_agents: list[AgentDef],
    conversation: list[dict],
    round_num: int,
    topic: str,
) -> str:
    """Build the prompt injecting conversation history for this agent."""
    team_desc = "\n".join(
        f"- {a.name} ({a.role}) [@{a.id}]" for a in all_agents if a.id != agent.id
    )

    conv_text = ""
    for msg in conversation:
        speaker = msg.get("name", msg.get("from", "?"))
        role = msg.get("role", "")
        role_tag = f" ({role})" if role else ""
        conv_text += f"\n**{speaker}{role_tag}:**\n{msg['content']}\n"

    prompt = f"""Tu es {agent.name}, {agent.role}.
{agent.persona if agent.persona else ''}

## Réunion en cours — Tour {round_num + 1}

**Sujet:** {topic}

**Participants (tu peux les @mentionner):**
{team_desc}

## Conversation jusqu'ici:
{conv_text}

## Consignes:
- Réponds EN TANT QUE {agent.name} avec ton expertise ({agent.role}).
- Réagis aux interventions précédentes. Rebondis, questionne, challenge.
- @mentionne les collègues quand tu t'adresses à eux (ex: @Pierre, @Nadia).
- Si tu es d'accord avec un point, dis-le explicitement. Si tu n'es pas d'accord, argumente.
- Sois concis mais substantiel (200-400 mots max).
- Ne répète pas ce qui a déjà été dit. Apporte de la valeur ajoutée.
- Si tu n'as rien de nouveau à ajouter, réponds juste "[PASS]".
"""
    return prompt


def _conversation_concluded(conversation: list[dict]) -> bool:
    """Check if the conversation has reached consensus."""
    if len(conversation) < 3:
        return False
    # If last 2+ messages contain approval/consensus markers
    recent = conversation[-3:]
    passes = sum(1 for m in recent if "[PASS]" in m.get("content", ""))
    approves = sum(1 for m in recent if "[APPROVE]" in m.get("content", ""))
    if passes >= 2 or approves >= 2:
        return True
    return False


async def _stream_agent_response(
    session_id: str, agent: AgentDef, ctx: ExecutionContext, prompt: str
) -> str:
    """Stream an agent's LLM response token by token via SSE."""
    llm = get_llm_client()
    system = _build_system_for_conversation(agent, ctx)
    messages = [LLMMessage(role="user", content=prompt)]

    full_content = ""
    in_think = False
    try:
        async for chunk in llm.stream(
            messages=messages,
            provider=agent.provider or "minimax",
            model=agent.model or "",
            temperature=agent.temperature if agent.temperature else 0.7,
            max_tokens=agent.max_tokens or 2000,
            system_prompt=system,
        ):
            if chunk.delta:
                full_content += chunk.delta
                # Don't stream <think> blocks to the frontend
                if "<think>" in chunk.delta:
                    in_think = True
                if "</think>" in chunk.delta:
                    in_think = False
                    continue
                if not in_think:
                    await _push_sse(session_id, {
                        "type": "stream_delta",
                        "agent_id": agent.id,
                        "delta": chunk.delta,
                    })
            if chunk.done:
                break
        # Strip <think> blocks from final content
        if "<think>" in full_content:
            full_content = re.sub(r"<think>.*?</think>\s*", "", full_content, flags=re.DOTALL).strip()
    except Exception as exc:
        logger.error("Streaming failed for %s: %s", agent.id, exc)
        # Fallback: non-streaming chat() which has its own provider fallback
        try:
            resp = await llm.chat(
                messages=messages,
                provider=agent.provider or "minimax",
                model=agent.model or "",
                temperature=agent.temperature if agent.temperature else 0.7,
                max_tokens=agent.max_tokens or 2000,
                system_prompt=system,
            )
            full_content = resp.content
            await _push_sse(session_id, {
                "type": "stream_delta",
                "agent_id": agent.id,
                "delta": full_content,
            })
        except Exception as exc2:
            logger.error("Fallback also failed for %s: %s", agent.id, exc2)
            full_content = f"(Error: {exc2})"

    return full_content


def _build_system_for_conversation(agent: AgentDef, ctx: ExecutionContext) -> str:
    """Build system prompt for conversation mode."""
    parts = [f"Tu es {agent.name}, {agent.role}."]
    if agent.persona:
        parts.append(agent.persona)
    if agent.motivation:
        parts.append(f"Motivation: {agent.motivation}")
    if ctx.skills_prompt:
        parts.append(f"\n## Compétences\n{ctx.skills_prompt[:1500]}")
    if ctx.vision:
        parts.append(f"\n## Vision Projet\n{ctx.vision[:1500]}")
    if ctx.project_context:
        parts.append(f"\n## Contexte Projet\n{ctx.project_context[:1000]}")
    return "\n".join(parts)
