"""Agent Loop — autonomous agent that checks inbox, thinks via LLM, communicates via bus.

Each agent runs as an independent asyncio.Task:
  1. Wait for message from inbox
  2. Build execution context (skills, memory, history)
  3. Call AgentExecutor.run() for LLM reasoning + tool use
  4. Parse structured actions from LLM output
  5. Route actions through the MessageBus
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime

from ..models import A2AMessage, AgentInstance, AgentStatus, MessageType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Action dataclass
# ---------------------------------------------------------------------------


@dataclass
class AgentAction:
    """Parsed structured action from LLM output."""

    type: str = ""  # respond, delegate, veto, approve, ask, escalate
    target: str = ""  # agent_id for delegate/ask
    content: str = ""
    reason: str = ""


# Regex patterns for action tags in LLM output
_ACTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "delegate",
        re.compile(
            r"\[DELEGATE:([^\]]+)\]\s*(.*?)(?=\[DELEGATE:|\[VETO|\[APPROVE\]|\[ASK:|\[ESCALATE|\Z)",
            re.MULTILINE | re.DOTALL,
        ),
    ),
    ("veto", re.compile(r"\[VETO:([^\]]*)\]", re.MULTILINE)),
    ("approve", re.compile(r"\[APPROVE\]", re.MULTILINE)),
    ("ask", re.compile(r"\[ASK:([^\]:]+):([^\]]*)\]", re.MULTILINE)),
    ("escalate", re.compile(r"\[ESCALATE:?([^\]]*)\]", re.MULTILINE)),
]

# ---------------------------------------------------------------------------
# AgentLoop
# ---------------------------------------------------------------------------


class AgentLoop:
    """Autonomous agent that checks inbox, thinks via LLM, communicates via bus."""

    def __init__(
        self,
        agent_def: AgentDef,
        session_id: str,
        project_id: str = "",
        project_path: str = "",
        think_timeout: float = 300.0,
        max_rounds: int = 10,
        workspace_id: str = "default",
    ):
        from .store import AgentDef as _AD  # noqa: F811 — type hint only

        self.agent: _AD = agent_def
        self.session_id = session_id
        self.project_id = project_id
        self.project_path = project_path
        self.think_timeout = think_timeout
        self.max_rounds = max_rounds
        self.workspace_id = workspace_id
        self.status: AgentStatus = AgentStatus.IDLE

        self.instance = AgentInstance(
            role_id=agent_def.id,
            session_id=session_id,
            status=AgentStatus.IDLE,
        )

        self._task: asyncio.Task | None = None
        self._inbox: asyncio.Queue[A2AMessage] = asyncio.Queue(maxsize=100)
        self._stop_event = asyncio.Event()
        self._rounds = 0
        self._pair_counts: dict[
            str, int
        ] = {}  # track msg counts per conversation partner

        # Lazy — initialised in start()
        self._executor: AgentExecutor | None = None  # type: ignore[name-defined]
        self._bus: MessageBus | None = None  # type: ignore[name-defined]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Register on the bus, replay pending messages, and launch the run-loop task."""
        from ..a2a.bus import get_bus
        from .executor import get_executor

        self._executor = get_executor()
        self._bus = get_bus()

        self._bus.register_agent(self.agent.id, handler=self._handle_message)
        self._stop_event.clear()

        # Replay unprocessed messages from DB for this agent in this session
        await self._replay_pending_messages()

        self._task = asyncio.create_task(
            self._run_loop(),
            name=f"agent-loop:{self.session_id}:{self.agent.id}",
        )
        logger.info(
            "AgentLoop started  agent=%s session=%s", self.agent.id, self.session_id
        )

    async def _replay_pending_messages(self) -> None:
        """Load recent messages from DB and enqueue ones addressed to this agent."""
        if not self._bus or not self._bus.db:
            return
        try:
            rows = self._bus.db.execute(
                """SELECT id, session_id, from_agent, to_agent, message_type,
                          content, metadata_json, parent_id, timestamp
                   FROM messages
                   WHERE session_id = ? AND (to_agent = ? OR to_agent IS NULL)
                     AND message_type != 'system' AND LENGTH(content) > 0
                     AND from_agent != ?
                   ORDER BY timestamp DESC LIMIT 5""",
                (self.session_id, self.agent.id, self.agent.id),
            ).fetchall()
            for row in reversed(rows):  # oldest first
                msg = A2AMessage(
                    id=row[0],
                    session_id=row[1],
                    from_agent=row[2],
                    to_agent=row[3],
                    message_type=MessageType(row[4]),
                    content=row[5],
                    parent_id=row[7],
                )
                try:
                    self._inbox.put_nowait(msg)
                except asyncio.QueueFull:
                    break
            if rows:
                logger.info(
                    "Replayed %d messages for agent=%s session=%s",
                    len(rows),
                    self.agent.id,
                    self.session_id,
                )
        except Exception as exc:
            logger.debug("Replay failed for agent=%s: %s", self.agent.id, exc)

    async def stop(self) -> None:
        """Signal stop, cancel task, unregister from bus."""
        self._stop_event.set()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._bus:
            self._bus.unregister_agent(self.agent.id)
        self.status = AgentStatus.STOPPED
        self.instance.status = AgentStatus.STOPPED
        logger.info(
            "AgentLoop stopped  agent=%s session=%s", self.agent.id, self.session_id
        )

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def _run_loop(self) -> None:
        """Core event loop: wait for message → think → act → repeat."""
        assert self._executor is not None
        assert self._bus is not None

        while not self._stop_event.is_set():
            # 1. Wait for a message (1s timeout to check stop flag)
            try:
                msg = await asyncio.wait_for(self._inbox.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            # Skip messages that agents shouldn't process
            if self._should_skip(msg):
                continue

            # Round limit to prevent infinite loops
            self._rounds += 1
            if self._rounds > self.max_rounds:
                logger.warning(
                    "Agent %s hit max rounds (%d), pausing  session=%s",
                    self.agent.id,
                    self.max_rounds,
                    self.session_id,
                )
                await self._set_status(AgentStatus.IDLE)
                break

            t0 = time.monotonic()
            try:
                # 2. Update status → THINKING
                await self._set_status(AgentStatus.THINKING)

                # 3. Build execution context
                ctx = await self._build_context()

                # 4. Run executor with streaming
                try:
                    logger.warning("LOOP calling executor for agent=%s", self.agent.id)
                    result = None
                    stream_started = False

                    async def _run_streaming():
                        nonlocal result, stream_started
                        from ..sessions.runner import _push_sse

                        in_think = False
                        async for event_type, data in self._executor.run_streaming(
                            ctx, msg.content
                        ):
                            if event_type == "delta":
                                # Filter out <think> blocks (MiniMax internal reasoning)
                                if "<think>" in data:
                                    in_think = True
                                if "</think>" in data:
                                    in_think = False
                                    continue
                                if in_think:
                                    continue

                                if not stream_started:
                                    stream_started = True
                                    await _push_sse(
                                        self.session_id,
                                        {
                                            "type": "stream_start",
                                            "agent_id": self.agent.id,
                                            "agent_name": self.agent.name,
                                        },
                                    )
                                await _push_sse(
                                    self.session_id,
                                    {
                                        "type": "stream_delta",
                                        "agent_id": self.agent.id,
                                        "delta": data,
                                    },
                                )
                            elif event_type == "result":
                                if stream_started:
                                    await _push_sse(
                                        self.session_id,
                                        {
                                            "type": "stream_end",
                                            "agent_id": self.agent.id,
                                            "content": data.content,
                                        },
                                    )
                                result = data

                    await asyncio.wait_for(
                        _run_streaming(),
                        timeout=self.think_timeout,
                    )
                    if result is None:
                        logger.error(
                            "Executor returned no result agent=%s", self.agent.id
                        )
                        await self._set_status(AgentStatus.ERROR)
                        continue
                    logger.warning(
                        "LOOP executor returned for agent=%s content_len=%d",
                        self.agent.id,
                        len(result.content or ""),
                    )
                except asyncio.TimeoutError:
                    logger.error(
                        "Executor timeout  agent=%s session=%s timeout=%.0fs",
                        self.agent.id,
                        self.session_id,
                        self.think_timeout,
                    )
                    await self._set_status(AgentStatus.ERROR)
                    continue

                if result.error:
                    logger.error(
                        "Executor error  agent=%s session=%s error=%s",
                        self.agent.id,
                        self.session_id,
                        result.error,
                    )
                    await self._set_status(AgentStatus.ERROR)
                    continue

                # 5. Track metrics
                self.instance.tokens_used += result.tokens_in + result.tokens_out
                self.instance.messages_received += 1
                self.instance.last_active = datetime.utcnow()

                # 6. Parse and execute actions
                actions = self._parse_actions(result.content)
                logger.warning(
                    "LOOP parsed %d actions for agent=%s", len(actions), self.agent.id
                )
                if actions:
                    await self._set_status(AgentStatus.ACTING)
                    for action in actions:
                        await self._execute_action(
                            action, parent_id=msg.id, full_context=result.content
                        )
                else:
                    # No structured actions — send plain response
                    await self.send_message(
                        to=msg.from_agent,
                        content=result.content,
                        msg_type=MessageType.RESPONSE,
                        parent_id=msg.id,
                    )

                elapsed = int((time.monotonic() - t0) * 1000)
                logger.info(
                    "AgentLoop cycle  agent=%s session=%s duration_ms=%d actions=%d",
                    self.agent.id,
                    self.session_id,
                    elapsed,
                    len(actions),
                )

                # 7. Update PROGRESS.md in project workspace (Codex-style living status doc)
                if self.project_path:
                    try:
                        _update_progress_md(
                            self.project_path, self.agent, result, msg.content
                        )
                    except Exception:
                        pass

            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "AgentLoop error  agent=%s session=%s",
                    self.agent.id,
                    self.session_id,
                )
                self.instance.error_count += 1
                await self._set_status(AgentStatus.ERROR)
                continue

            # 7. Back to idle
            await self._set_status(AgentStatus.IDLE)

    # ------------------------------------------------------------------
    # Bus handler (called by MessageBus._deliver)
    # ------------------------------------------------------------------

    async def _handle_message(self, msg: A2AMessage) -> None:
        """Enqueue incoming message (called by bus handler)."""
        # Only accept messages for our session
        if msg.session_id != self.session_id:
            return
        try:
            self._inbox.put_nowait(msg)
        except asyncio.QueueFull:
            logger.warning(
                "Inbox full  agent=%s session=%s, dropping message %s",
                self.agent.id,
                self.session_id,
                msg.id,
            )

    # ------------------------------------------------------------------
    # Message filtering
    # ------------------------------------------------------------------

    def _should_skip(self, msg: A2AMessage) -> bool:
        """Filter out messages that agents shouldn't LLM-process."""
        # Skip SYSTEM status events (they're for SSE/UI only)
        if msg.message_type == MessageType.SYSTEM:
            return True
        # Skip empty content (bus noise)
        if not msg.content or not msg.content.strip():
            return True
        # Skip own messages (echo prevention)
        if msg.from_agent == self.agent.id:
            return True
        # Limit exchanges with same agent (prevent ping-pong loops)
        partner = msg.from_agent or ""
        if partner:
            self._pair_counts[partner] = self._pair_counts.get(partner, 0) + 1
            if self._pair_counts[partner] > 3:
                logger.info(
                    "Pair limit reached  agent=%s partner=%s count=%d, skipping",
                    self.agent.id,
                    partner,
                    self._pair_counts[partner],
                )
                return True
        return False

    # ------------------------------------------------------------------
    # Context builder
    # ------------------------------------------------------------------

    async def _build_context(self) -> ExecutionContext:
        """Assemble ExecutionContext with history, memory, skills.

        Context is scoped by Uruk capability grade (ADR-0010/ADR-0013 from Orthanc):
        - Organizers (cto, arch, cdp, product, reviewer): full project context, 50 msgs
        - Executors (dev, qa, security, ux, devops): task-scoped, 15 msgs, no vision
        This reduces token usage by ~60% for executor-grade agents.
        """
        from ..memory.manager import get_memory_manager
        from ..sessions.store import get_session_store
        from ..skills.library import get_skill_library
        from .executor import ExecutionContext
        from .tool_schemas import _get_capability_grade

        # Determine capability grade
        grade = _get_capability_grade(self.agent)
        is_organizer = grade == "organizer"

        # History window: organizers need full project thread, executors need only recent
        history_limit = 50 if is_organizer else 15

        history_dicts: list[dict] = []
        try:
            store = get_session_store()
            messages = store.get_messages(self.session_id, limit=history_limit)
            history_dicts = [
                {
                    "from_agent": m.from_agent,
                    "content": m.content,
                    "message_type": m.message_type,
                }
                for m in messages
            ]
        except Exception as exc:
            logger.debug("Failed to load history: %s", exc)

        # Project memory — organizers get more context entries, executors get fewer
        project_context = ""
        if self.project_id:
            try:
                mem = get_memory_manager()
                memory_limit = 10 if is_organizer else 3
                entries = mem.project_get(self.project_id, limit=memory_limit)
                if entries:
                    project_context = "\n".join(
                        f"[{e['category']}] {e['key']}: {e['value'][:200]}"
                        for e in entries
                    )
            except Exception as exc:
                logger.debug("Failed to load project context: %s", exc)

        # Project memory files (CLAUDE.md, etc.) — organizers only
        # Executors don't need the full project constitution to implement a task
        project_memory_str = ""
        if is_organizer and self.project_path:
            try:
                from ..memory.project_files import get_project_memory

                pmem = get_project_memory(self.project_id, self.project_path)
                project_memory_str = pmem.combined
            except Exception as exc:
                logger.debug("Failed to load project memory files: %s", exc)

        # Skills - Auto-inject relevant skills based on mission context
        skills_prompt = ""

        # Try automatic skills injection first
        try:
            from .skills_integration import enrich_agent_with_skills

            # Get mission description for context
            mission_desc = None
            if history_dicts:
                # Use first user message as mission context
                for msg in history_dicts:
                    if msg.get("from_agent") == "user":
                        mission_desc = msg.get("content", "")[:500]
                        break

            skills_prompt = enrich_agent_with_skills(
                agent_id=self.agent.id,
                agent_role=self.agent.role,
                mission_description=mission_desc,
                project_id=self.project_id,
                fallback_skills=self.agent.skills,  # Fallback to manual skills
            )
        except Exception as exc:
            logger.debug(f"Auto skills injection failed: {exc}, using manual skills")

            # Fallback to original manual skill loading
            if self.agent.skills:
                try:
                    lib = get_skill_library()
                    parts = []
                    for sid in self.agent.skills[:5]:
                        skill = lib.get(sid)
                        if skill and skill.get("content"):
                            parts.append(
                                f"### {skill['name']}\n{skill['content'][:1500]}"
                            )
                    skills_prompt = "\n\n".join(parts)
                except Exception:
                    pass

        # Vision — organizers only (executors don't need strategic vision to implement a task)
        vision = ""
        if is_organizer and self.project_id:
            try:
                from ..projects.manager import get_project_store

                proj = get_project_store().get(self.project_id)
                if proj and proj.vision:
                    vision = proj.vision[:3000]
            except Exception:
                pass

        # Disable tools for strategic/management agents (they think, not code)
        # BUT enable for agents with explicit tools (like CDP with phase tools)
        agent_tools_enabled = self.agent.hierarchy_rank >= 30 or bool(self.agent.tools)

        # Resolve mission_run_id for CDP agent
        mission_run_id = None
        if self.agent.id == "chef_de_programme":
            try:
                from ..missions.store import get_mission_run_store

                runs = get_mission_run_store().list_runs(limit=10)
                for mr in runs:
                    if mr.session_id == self.session_id:
                        mission_run_id = mr.id
                        break
            except Exception:
                pass

        return ExecutionContext(
            agent=self.agent,
            session_id=self.session_id,
            project_id=self.project_id or None,
            project_path=self.project_path or None,
            history=history_dicts,
            project_context=project_context,
            project_memory=project_memory_str,
            skills_prompt=skills_prompt,
            vision=vision,
            tools_enabled=agent_tools_enabled,
            mission_run_id=mission_run_id,
            capability_grade=grade,
        )

    # ------------------------------------------------------------------
    # Action parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_actions(content: str) -> list[AgentAction]:
        """Parse structured action tags from LLM output."""
        actions: list[AgentAction] = []

        for action_type, pattern in _ACTION_PATTERNS:
            for m in pattern.finditer(content):
                if action_type == "delegate":
                    actions.append(
                        AgentAction(
                            type="delegate",
                            target=m.group(1).strip(),
                            content=m.group(2).strip(),
                        )
                    )
                elif action_type == "veto":
                    actions.append(
                        AgentAction(
                            type="veto",
                            reason=m.group(1).strip(),
                        )
                    )
                elif action_type == "approve":
                    actions.append(AgentAction(type="approve"))
                elif action_type == "ask":
                    actions.append(
                        AgentAction(
                            type="ask",
                            target=m.group(1).strip(),
                            content=m.group(2).strip(),
                        )
                    )
                elif action_type == "escalate":
                    actions.append(
                        AgentAction(
                            type="escalate",
                            reason=m.group(1).strip(),
                        )
                    )

        return actions

    # ------------------------------------------------------------------
    # Action execution
    # ------------------------------------------------------------------

    async def _execute_action(
        self, action: AgentAction, parent_id: str = "", full_context: str = ""
    ) -> None:
        """Route a parsed action through the message bus."""
        type_map = {
            "delegate": MessageType.DELEGATE,
            "veto": MessageType.VETO,
            "approve": MessageType.APPROVE,
            "ask": MessageType.REQUEST,
            "escalate": MessageType.ESCALATE,
        }
        msg_type = type_map.get(action.type, MessageType.INFORM)
        content = action.content or action.reason or ""

        # For delegations with minimal content, include the full context
        if action.type == "delegate" and len(content.strip()) < 20 and full_context:
            content = f"Tâche déléguée par {self.agent.name}:\n\n{full_context}"

        await self.send_message(
            to=action.target or None,
            content=content,
            msg_type=msg_type,
            parent_id=parent_id,
            metadata={"action_type": action.type},
        )

        self.instance.messages_sent += 1
        logger.info(
            "Action executed  agent=%s type=%s target=%s session=%s",
            self.agent.id,
            action.type,
            action.target,
            self.session_id,
        )

    # ------------------------------------------------------------------
    # Messaging convenience
    # ------------------------------------------------------------------

    async def send_message(
        self,
        to: str | None,
        content: str,
        msg_type: MessageType = MessageType.INFORM,
        parent_id: str = "",
        metadata: dict | None = None,
    ) -> None:
        """Publish a message through the bus."""
        assert self._bus is not None
        msg = A2AMessage(
            session_id=self.session_id,
            from_agent=self.agent.id,
            to_agent=to,
            message_type=msg_type,
            content=content,
            parent_id=parent_id or None,
            metadata=metadata or {},
        )
        await self._bus.publish(msg)
        self.instance.messages_sent += 1

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    async def _set_status(self, status: AgentStatus) -> None:
        """Update status and notify SSE listeners (not other agents)."""
        self.status = status
        self.instance.status = status
        self.instance.last_active = datetime.utcnow()

        # Only notify SSE listeners — do NOT publish to bus (avoids flooding agents)
        if self._bus:
            event_msg = A2AMessage(
                session_id=self.session_id,
                from_agent=self.agent.id,
                message_type=MessageType.SYSTEM,
                content="",
                metadata={
                    "event": "status_change",
                    "status": status.value,
                    "agent_id": self.agent.id,
                },
            )
            # Persist for history but don't route to agents
            if self._bus.db:
                self._bus._persist_message(event_msg)
            await self._bus._notify_sse(event_msg)

    def get_status(self) -> dict:
        """Return current status and metrics."""
        return {
            "agent_id": self.agent.id,
            "session_id": self.session_id,
            "status": self.status.value,
            "messages_sent": self.instance.messages_sent,
            "messages_received": self.instance.messages_received,
            "tokens_used": self.instance.tokens_used,
            "error_count": self.instance.error_count,
            "last_active": self.instance.last_active.isoformat(),
        }


# ---------------------------------------------------------------------------
# PROGRESS.md — living status document (Codex-style)
# ---------------------------------------------------------------------------


def _update_progress_md(
    project_path: str, agent: "AgentInstance", result: object, user_message: str
) -> None:
    """Write/update PROGRESS.md in the project workspace after each agent cycle.

    This mirrors Codex's Documentation.md: current milestone status, decisions,
    last tool calls, and how to run the project.
    """
    import os
    from datetime import datetime as _dt

    progress_path = os.path.join(project_path, "PROGRESS.md")

    # Read existing header/decisions section to preserve it
    existing_decisions = ""
    if os.path.exists(progress_path):
        with open(progress_path) as f:
            content = f.read()
        # Preserve ## Décisions section if present
        if "## Décisions" in content:
            idx = content.index("## Décisions")
            end = content.find("\n## ", idx + 1)
            existing_decisions = content[
                idx : end if end != -1 else len(content)
            ].strip()

    now = _dt.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    agent_name = getattr(agent, "name", getattr(agent, "id", "agent"))

    # Summarize tool calls
    tool_calls = getattr(result, "tool_calls", []) or []
    tools_summary = ""
    if tool_calls:
        for tc in tool_calls[-5:]:  # last 5 tools
            name = tc.get("name", "?")
            args = tc.get("args", {})
            path = args.get("path") or args.get("file") or args.get("cwd") or ""
            tools_summary += f"  - `{name}`"
            if path:
                tools_summary += f" → `{path}`"
            # Show lint/test status
            res_snip = tc.get("result", "")[:80].replace("\n", " ")
            if res_snip:
                tools_summary += f" — {res_snip}"
            tools_summary += "\n"
    else:
        tools_summary = "  _(aucun outil appelé)_\n"

    # Truncate agent response for summary
    response_summary = (getattr(result, "content", "") or "")[:300].replace("\n", " ")

    # Tokens used
    tok_in = getattr(result, "tokens_in", 0)
    tok_out = getattr(result, "tokens_out", 0)

    _decisions_fallback = "## Décisions\n\n_(à compléter)_"
    progress = f"""# PROGRESS — {agent_name}

> Mis à jour automatiquement après chaque cycle agent. Ne pas modifier manuellement.

## Dernier cycle

- **Agent** : {agent_name}
- **Date** : {now}
- **Tokens** : {tok_in} in / {tok_out} out
- **Message** : {(user_message or "")[:120]}

## Résumé

{response_summary}{"..." if len(getattr(result, "content", "") or "") > 300 else ""}

## Outils utilisés

{tools_summary}
## Statut

- Erreur : {getattr(result, "error", None) or "Aucune"}
- Durée : {getattr(result, "duration_ms", 0)} ms

{existing_decisions if existing_decisions else _decisions_fallback}
"""
    os.makedirs(project_path, exist_ok=True)
    with open(progress_path, "w") as f:
        f.write(progress)


# ---------------------------------------------------------------------------
# AgentLoopManager (singleton)
# ---------------------------------------------------------------------------


class AgentLoopManager:
    """Manages all running agent loops for a session."""

    def __init__(self) -> None:
        self._loops: dict[str, AgentLoop] = {}  # key = "{session_id}:{agent_id}"

    @staticmethod
    def _key(agent_id: str, session_id: str) -> str:
        return f"{session_id}:{agent_id}"

    async def start_agent(
        self,
        agent_id: str,
        session_id: str,
        project_id: str = "",
        project_path: str = "",
    ) -> AgentLoop:
        """Create and start an agent loop, returning it."""
        from .store import get_agent_store

        key = self._key(agent_id, session_id)
        if key in self._loops:
            return self._loops[key]

        agent_def = get_agent_store().get(agent_id)
        if agent_def is None:
            raise ValueError(f"Agent not found: {agent_id}")

        loop = AgentLoop(
            agent_def=agent_def,
            session_id=session_id,
            project_id=project_id,
            project_path=project_path,
        )
        await loop.start()
        self._loops[key] = loop
        logger.info("Manager started agent=%s session=%s", agent_id, session_id)
        return loop

    async def stop_agent(self, agent_id: str, session_id: str) -> None:
        """Stop a single agent loop."""
        key = self._key(agent_id, session_id)
        loop = self._loops.pop(key, None)
        if loop:
            await loop.stop()
            logger.info("Manager stopped agent=%s session=%s", agent_id, session_id)

    async def stop_session(self, session_id: str) -> None:
        """Stop all agent loops for a session."""
        keys = [k for k in self._loops if k.startswith(f"{session_id}:")]
        for key in keys:
            loop = self._loops.pop(key, None)
            if loop:
                await loop.stop()
        logger.info("Manager stopped session=%s (%d agents)", session_id, len(keys))

    def get_loop(self, agent_id: str, session_id: str) -> AgentLoop | None:
        """Get a running loop by agent + session."""
        return self._loops.get(self._key(agent_id, session_id))

    def get_session_loops(self, session_id: str) -> list[AgentLoop]:
        """Get all running loops for a session."""
        prefix = f"{session_id}:"
        return [loop for key, loop in self._loops.items() if key.startswith(prefix)]

    def get_all_statuses(self) -> dict:
        """Return status of all running loops (for monitoring)."""
        return {key: loop.get_status() for key, loop in self._loops.items()}


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_manager: AgentLoopManager | None = None


def get_loop_manager() -> AgentLoopManager:
    """Return the singleton AgentLoopManager."""
    global _manager
    if _manager is None:
        _manager = AgentLoopManager()
    return _manager
