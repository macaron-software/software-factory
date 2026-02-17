"""
BaseAgent - Abstract base class for all platform agents.
=========================================================
Provides the common interface: think, act, respond, delegate, veto, approve.
Each agent has a role, memory, tools, and an LLM connection.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

from ..models import (
    AgentInstance, AgentRole, AgentStatus, A2AMessage, MessageType,
    ToolResult, NegotiationState,
)


class BaseAgent:
    """
    A running agent with role-defined behavior.
    Not abstract — instantiated with an AgentRole that defines its persona.
    """

    def __init__(
        self,
        role: AgentRole,
        instance: AgentInstance,
        llm_provider: Any = None,
        tools: dict[str, Any] | None = None,
        memory: Any = None,
        bus: Any = None,
    ):
        self.role = role
        self.instance = instance
        self.llm = llm_provider
        self.tools = tools or {}
        self.memory = memory
        self.bus = bus
        self._inbox: asyncio.Queue[A2AMessage] = asyncio.Queue()
        self._running = False
        self._task: Optional[asyncio.Task] = None

    @property
    def id(self) -> str:
        return self.instance.id

    @property
    def role_id(self) -> str:
        return self.role.id

    @property
    def status(self) -> AgentStatus:
        return self.instance.status

    # ── Lifecycle ─────────────────────────────────────────────────────

    async def start(self):
        """Start the agent's main loop."""
        self._running = True
        self.instance.status = AgentStatus.IDLE
        self._task = asyncio.create_task(self._main_loop())

    async def pause(self):
        self.instance.status = AgentStatus.PAUSED

    async def resume(self):
        self.instance.status = AgentStatus.IDLE

    async def stop(self):
        self._running = False
        self.instance.status = AgentStatus.STOPPED
        if self._task and not self._task.done():
            self._task.cancel()

    async def _main_loop(self):
        """Process incoming messages continuously."""
        while self._running:
            if self.instance.status == AgentStatus.PAUSED:
                await asyncio.sleep(1)
                continue

            try:
                msg = await asyncio.wait_for(self._inbox.get(), timeout=5.0)
                self.instance.status = AgentStatus.THINKING
                self.instance.last_active = datetime.utcnow()
                self.instance.messages_received += 1

                response = await self.think(msg)

                if response and self.bus:
                    await self.bus.publish(response)
                    self.instance.messages_sent += 1

                self.instance.status = AgentStatus.IDLE

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.instance.status = AgentStatus.ERROR
                self.instance.error_count += 1
                # Log error but continue running
                await asyncio.sleep(2)
                self.instance.status = AgentStatus.IDLE

    # ── Message handling ──────────────────────────────────────────────

    async def receive(self, message: A2AMessage):
        """Receive a message into the inbox."""
        await self._inbox.put(message)

    async def think(self, message: A2AMessage) -> Optional[A2AMessage]:
        """
        Process an incoming message using the LLM.
        Returns a response message or None.
        """
        if not self.llm:
            return None

        # Build prompt with role context + conversation history
        prompt = self._build_prompt(message)
        start = time.monotonic()

        try:
            llm_response = await self.llm.query(
                prompt=prompt,
                model=self.role.llm.model,
                temperature=self.role.llm.temperature,
                max_tokens=self.role.llm.max_tokens,
                system=self.role.system_prompt,
            )
        except Exception:
            if self.role.llm.fallback_model:
                llm_response = await self.llm.query(
                    prompt=prompt,
                    model=self.role.llm.fallback_model,
                    temperature=self.role.llm.temperature,
                    max_tokens=self.role.llm.max_tokens,
                    system=self.role.system_prompt,
                )
            else:
                raise

        elapsed_ms = int((time.monotonic() - start) * 1000)
        self.instance.tokens_used += len(llm_response) // 4  # rough estimate

        # Check if the LLM wants to call tools
        tool_results = await self._execute_tool_calls(llm_response)

        # Build response message
        response_content = llm_response
        if tool_results:
            response_content += "\n\n---\nTool Results:\n"
            for tr in tool_results:
                response_content += f"- {tr.tool_name}: {'+' if tr.success else '-'} {tr.output[:200]}\n"

        response = A2AMessage(
            session_id=message.session_id,
            from_agent=self.id,
            to_agent=message.from_agent if message.requires_response else None,
            message_type=MessageType.RESPONSE,
            content=response_content,
            parent_id=message.id,
            metadata={"elapsed_ms": elapsed_ms, "model": self.role.llm.model},
        )

        # Store in memory
        if self.memory:
            await self.memory.store_message(self.id, message)
            await self.memory.store_message(self.id, response)

        return response

    # ── Actions ───────────────────────────────────────────────────────

    async def respond(self, to: str, content: str, session_id: str) -> A2AMessage:
        """Send a direct response to another agent."""
        msg = A2AMessage(
            session_id=session_id,
            from_agent=self.id,
            to_agent=to,
            message_type=MessageType.RESPONSE,
            content=content,
        )
        if self.bus:
            await self.bus.publish(msg)
        self.instance.messages_sent += 1
        return msg

    async def delegate(self, to: str, task: str, session_id: str) -> A2AMessage:
        """Delegate a task to another agent."""
        if not self.role.permissions.can_delegate:
            raise PermissionError(f"Agent {self.role_id} cannot delegate")
        msg = A2AMessage(
            session_id=session_id,
            from_agent=self.id,
            to_agent=to,
            message_type=MessageType.DELEGATE,
            content=task,
            requires_response=True,
        )
        if self.bus:
            await self.bus.publish(msg)
        self.instance.messages_sent += 1
        return msg

    async def veto(self, message_id: str, reason: str, session_id: str) -> A2AMessage:
        """Veto a proposal/action with justification."""
        if not self.role.permissions.can_veto:
            raise PermissionError(f"Agent {self.role_id} cannot veto")
        msg = A2AMessage(
            session_id=session_id,
            from_agent=self.id,
            message_type=MessageType.VETO,
            content=reason,
            parent_id=message_id,
            priority=9,
        )
        if self.bus:
            await self.bus.publish(msg)
        self.instance.messages_sent += 1
        return msg

    async def approve(self, message_id: str, session_id: str) -> A2AMessage:
        """Approve a proposal/action."""
        if not self.role.permissions.can_approve:
            raise PermissionError(f"Agent {self.role_id} cannot approve")
        msg = A2AMessage(
            session_id=session_id,
            from_agent=self.id,
            message_type=MessageType.APPROVE,
            content="Approved",
            parent_id=message_id,
        )
        if self.bus:
            await self.bus.publish(msg)
        self.instance.messages_sent += 1
        return msg

    async def escalate(self, reason: str, session_id: str) -> Optional[A2AMessage]:
        """Escalate to the configured superior."""
        target = self.role.permissions.escalation_to
        if not target:
            return None
        msg = A2AMessage(
            session_id=session_id,
            from_agent=self.id,
            to_agent=target,
            message_type=MessageType.ESCALATE,
            content=reason,
            priority=8,
            requires_response=True,
        )
        if self.bus:
            await self.bus.publish(msg)
        self.instance.messages_sent += 1
        return msg

    async def inform(self, content: str, session_id: str, channel: str = None) -> A2AMessage:
        """Broadcast information (no response expected)."""
        msg = A2AMessage(
            session_id=session_id,
            from_agent=self.id,
            to_agent=None,  # broadcast
            message_type=MessageType.INFORM,
            content=content,
            metadata={"channel": channel} if channel else {},
        )
        if self.bus:
            await self.bus.publish(msg)
        self.instance.messages_sent += 1
        return msg

    # ── Memory ────────────────────────────────────────────────────────

    async def remember(self, key: str, value: str):
        if self.memory:
            await self.memory.store(self.id, key, value)

    async def recall(self, query: str) -> list[str]:
        if self.memory:
            return await self.memory.search(self.id, query)
        return []

    # ── Internal ──────────────────────────────────────────────────────

    def _build_prompt(self, message: A2AMessage) -> str:
        """Build the full prompt for the LLM including context."""
        parts = []

        # Role persona
        if self.role.persona_traits:
            parts.append(f"Traits: {', '.join(self.role.persona_traits)}")

        # Message context
        parts.append(f"\n[{message.message_type.value.upper()}] from {message.from_agent}:")
        parts.append(message.content)

        # Available tools
        if self.tools:
            tool_list = ", ".join(self.tools.keys())
            parts.append(f"\nAvailable tools: {tool_list}")

        return "\n".join(parts)

    async def _execute_tool_calls(self, llm_response: str) -> list[ToolResult]:
        """Parse and execute any tool calls from LLM response."""
        # Simple JSON tool call detection
        results = []
        if "```tool_call" in llm_response:
            try:
                start = llm_response.index("```tool_call") + len("```tool_call")
                end = llm_response.index("```", start)
                call_json = json.loads(llm_response[start:end].strip())
                tool_name = call_json.get("tool")
                params = call_json.get("params", {})

                if tool_name in self.tools:
                    tool = self.tools[tool_name]
                    t0 = time.monotonic()
                    try:
                        output = await tool.execute(params, self.instance)
                        results.append(ToolResult(
                            tool_name=tool_name,
                            success=True,
                            output=str(output),
                            duration_ms=int((time.monotonic() - t0) * 1000),
                            agent_id=self.id,
                        ))
                    except Exception as e:
                        results.append(ToolResult(
                            tool_name=tool_name,
                            success=False,
                            error=str(e),
                            duration_ms=int((time.monotonic() - t0) * 1000),
                            agent_id=self.id,
                        ))
            except (ValueError, json.JSONDecodeError):
                pass

        return results

    def __repr__(self) -> str:
        return f"<Agent {self.role_id}:{self.id[:8]} status={self.status.value}>"
