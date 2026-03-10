"""
Orchestration Patterns - All 8 agentic architecture patterns.
===============================================================
Parallel, Sequential, Loop, Router, Aggregator, Hierarchical, Network, Human-in-Loop.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Optional

from ..models import (
    A2AMessage, MessageType, OrchestrationPattern, Session,
)
from ..agents.base import BaseAgent

logger = logging.getLogger(__name__)


class PatternResult:
    """Result of a pattern execution."""

    def __init__(self, pattern: str, success: bool, outputs: list[str] = None, error: str = None):
        self.pattern = pattern
        self.success = success
        self.outputs = outputs or []
        self.error = error

    def __repr__(self):
        return f"<PatternResult {self.pattern} ok={self.success} outputs={len(self.outputs)}>"


# ── Pattern implementations ───────────────────────────────────────────

async def parallel(
    agents: list[BaseAgent],
    task: str,
    session_id: str,
) -> PatternResult:
    """All agents work on the same task simultaneously. Results aggregated."""
    msg = A2AMessage(
        session_id=session_id,
        from_agent="orchestrator",
        message_type=MessageType.REQUEST,
        content=task,
        requires_response=True,
    )

    async def agent_work(agent: BaseAgent) -> Optional[str]:
        try:
            response = await agent.think(msg)
            return response.content if response else None
        except Exception as e:
            logger.error(f"Parallel agent {agent.role_id} failed: {e}")
            return None

    results = await asyncio.gather(*[agent_work(a) for a in agents])
    outputs = [r for r in results if r is not None]

    return PatternResult(
        pattern="parallel",
        success=len(outputs) > 0,
        outputs=outputs,
    )


async def sequential(
    agents: list[BaseAgent],
    task: str,
    session_id: str,
) -> PatternResult:
    """Pipeline: output of agent N becomes input of agent N+1."""
    current_input = task
    outputs = []

    for agent in agents:
        msg = A2AMessage(
            session_id=session_id,
            from_agent="orchestrator",
            to_agent=agent.id,
            message_type=MessageType.REQUEST,
            content=current_input,
            requires_response=True,
        )
        try:
            response = await agent.think(msg)
            if response:
                current_input = response.content
                outputs.append(response.content)
            else:
                return PatternResult("sequential", False, outputs, f"Agent {agent.role_id} returned no response")
        except Exception as e:
            return PatternResult("sequential", False, outputs, str(e))

    return PatternResult("sequential", True, outputs)


async def loop(
    agents: list[BaseAgent],
    task: str,
    session_id: str,
    max_iterations: int = 10,
    convergence_check: Callable[[str, str], bool] = None,
) -> PatternResult:
    """Iterate through agents until convergence or max iterations."""
    current = task
    outputs = []

    for i in range(max_iterations):
        previous = current
        for agent in agents:
            msg = A2AMessage(
                session_id=session_id,
                from_agent="orchestrator",
                to_agent=agent.id,
                message_type=MessageType.REQUEST,
                content=current,
                requires_response=True,
                metadata={"iteration": i},
            )
            try:
                response = await agent.think(msg)
                if response:
                    current = response.content
            except Exception as e:
                logger.error(f"Loop iteration {i}, agent {agent.role_id}: {e}")

        outputs.append(current)

        # Check convergence
        if convergence_check and convergence_check(previous, current):
            logger.info(f"Loop converged after {i + 1} iterations")
            break
        # Default: stop if output unchanged
        elif not convergence_check and current == previous:
            break

    return PatternResult("loop", True, outputs)


async def router(
    router_agent: BaseAgent,
    specialists: dict[str, BaseAgent],
    task: str,
    session_id: str,
) -> PatternResult:
    """Router agent classifies the task and routes to the right specialist."""
    # Ask router to classify
    specialist_list = ", ".join(specialists.keys())
    classify_msg = A2AMessage(
        session_id=session_id,
        from_agent="orchestrator",
        to_agent=router_agent.id,
        message_type=MessageType.REQUEST,
        content=(
            f"Classify this task and choose ONE specialist from: [{specialist_list}]\n"
            f"Respond with ONLY the specialist name.\n\nTask: {task}"
        ),
        requires_response=True,
    )

    try:
        route_response = await router_agent.think(classify_msg)
        if not route_response:
            return PatternResult("router", False, error="Router returned no response")

        chosen = route_response.content.strip().lower()
        # Fuzzy match
        specialist = None
        for name, agent in specialists.items():
            if name.lower() in chosen or chosen in name.lower():
                specialist = agent
                break

        if not specialist:
            specialist = list(specialists.values())[0]
            logger.warning(f"Router chose unknown specialist '{chosen}', defaulting to {specialist.role_id}")

        # Forward to specialist
        work_msg = A2AMessage(
            session_id=session_id,
            from_agent=router_agent.id,
            to_agent=specialist.id,
            message_type=MessageType.DELEGATE,
            content=task,
            requires_response=True,
        )
        result = await specialist.think(work_msg)
        return PatternResult(
            "router",
            True,
            outputs=[result.content] if result else [],
        )

    except Exception as e:
        return PatternResult("router", False, error=str(e))


async def aggregator(
    workers: list[BaseAgent],
    synthesizer: BaseAgent,
    task: str,
    session_id: str,
) -> PatternResult:
    """Multiple workers propose, synthesizer merges results."""
    # Step 1: Workers produce in parallel
    worker_result = await parallel(workers, task, session_id)
    if not worker_result.success:
        return PatternResult("aggregator", False, error="Worker phase failed")

    # Step 2: Synthesizer merges
    proposals_text = "\n\n---\n\n".join(
        f"[Agent {i+1}]:\n{output}" for i, output in enumerate(worker_result.outputs)
    )
    synth_msg = A2AMessage(
        session_id=session_id,
        from_agent="orchestrator",
        to_agent=synthesizer.id,
        message_type=MessageType.REQUEST,
        content=(
            f"Synthesize these {len(worker_result.outputs)} proposals into a single coherent result:\n\n"
            f"{proposals_text}"
        ),
        requires_response=True,
    )

    try:
        result = await synthesizer.think(synth_msg)
        return PatternResult(
            "aggregator",
            True,
            outputs=worker_result.outputs + ([result.content] if result else []),
        )
    except Exception as e:
        return PatternResult("aggregator", False, error=str(e))


async def hierarchical(
    manager: BaseAgent,
    workers: list[BaseAgent],
    task: str,
    session_id: str,
) -> PatternResult:
    """Manager decomposes task, assigns to workers, integrates results."""
    # Step 1: Manager decomposes
    decompose_msg = A2AMessage(
        session_id=session_id,
        from_agent="orchestrator",
        to_agent=manager.id,
        message_type=MessageType.REQUEST,
        content=(
            f"Decompose this task into {len(workers)} subtasks "
            f"(one per worker). Format as JSON array of strings.\n\nTask: {task}"
        ),
        requires_response=True,
    )

    try:
        decompose_result = await manager.think(decompose_msg)
        if not decompose_result:
            return PatternResult("hierarchical", False, error="Manager decomposition failed")

        # Parse subtasks
        import json
        try:
            content = decompose_result.content
            # Extract JSON from possible markdown
            if "```" in content:
                start = content.index("[")
                end = content.rindex("]") + 1
                content = content[start:end]
            subtasks = json.loads(content)
        except (json.JSONDecodeError, ValueError):
            subtasks = [decompose_result.content]

        # Step 2: Assign subtasks to workers
        assignments = list(zip(workers, subtasks))
        worker_outputs = []

        for worker, subtask in assignments:
            work_msg = A2AMessage(
                session_id=session_id,
                from_agent=manager.id,
                to_agent=worker.id,
                message_type=MessageType.DELEGATE,
                content=str(subtask),
                requires_response=True,
            )
            result = await worker.think(work_msg)
            if result:
                worker_outputs.append(result.content)

        # Step 3: Manager integrates
        integration_input = "\n\n---\n\n".join(
            f"[Worker {i+1}]:\n{out}" for i, out in enumerate(worker_outputs)
        )
        integrate_msg = A2AMessage(
            session_id=session_id,
            from_agent="orchestrator",
            to_agent=manager.id,
            message_type=MessageType.REQUEST,
            content=f"Integrate these worker results:\n\n{integration_input}",
            requires_response=True,
        )
        final = await manager.think(integrate_msg)
        return PatternResult(
            "hierarchical",
            True,
            outputs=worker_outputs + ([final.content] if final else []),
        )

    except Exception as e:
        return PatternResult("hierarchical", False, error=str(e))


async def network(
    agents: list[BaseAgent],
    task: str,
    session_id: str,
    max_rounds: int = 5,
) -> PatternResult:
    """Full mesh: all agents communicate freely for N rounds."""
    # Initialize with task
    for agent in agents:
        init_msg = A2AMessage(
            session_id=session_id,
            from_agent="orchestrator",
            to_agent=agent.id,
            message_type=MessageType.REQUEST,
            content=task,
            metadata={"round": 0, "pattern": "network"},
        )
        await agent.receive(init_msg)

    outputs = []
    for round_num in range(max_rounds):
        round_messages = []

        # Each agent processes inbox and broadcasts thought
        for agent in agents:
            msg = A2AMessage(
                session_id=session_id,
                from_agent="orchestrator",
                to_agent=agent.id,
                message_type=MessageType.REQUEST,
                content=f"Round {round_num + 1}/{max_rounds}. Share your current thinking on: {task}",
                requires_response=True,
                metadata={"round": round_num + 1},
            )
            response = await agent.think(msg)
            if response:
                round_messages.append(f"[{agent.role_id}]: {response.content}")

        # Share everyone's thoughts with everyone
        round_summary = "\n\n".join(round_messages)
        outputs.append(round_summary)

        for agent in agents:
            context_msg = A2AMessage(
                session_id=session_id,
                from_agent="orchestrator",
                to_agent=agent.id,
                message_type=MessageType.INFORM,
                content=f"Round {round_num + 1} summary:\n{round_summary}",
            )
            await agent.receive(context_msg)

    return PatternResult("network", True, outputs)


async def human_in_loop(
    agent: BaseAgent,
    task: str,
    session_id: str,
    checkpoints: list[str] = None,
    human_callback: Callable[[str, str], Any] = None,
) -> PatternResult:
    """Agent works, human validates at checkpoints."""
    checkpoints = checkpoints or ["review"]

    msg = A2AMessage(
        session_id=session_id,
        from_agent="orchestrator",
        to_agent=agent.id,
        message_type=MessageType.REQUEST,
        content=task,
        requires_response=True,
    )

    try:
        result = await agent.think(msg)
        if not result:
            return PatternResult("human_in_loop", False, error="Agent returned no response")

        outputs = [result.content]

        for checkpoint in checkpoints:
            if human_callback:
                human_input = await human_callback(checkpoint, result.content)
                if human_input:
                    # Agent refines based on human feedback
                    refine_msg = A2AMessage(
                        session_id=session_id,
                        from_agent="user",
                        to_agent=agent.id,
                        message_type=MessageType.HUMAN_RESPONSE,
                        content=f"Feedback on {checkpoint}: {human_input}",
                        requires_response=True,
                    )
                    result = await agent.think(refine_msg)
                    if result:
                        outputs.append(result.content)

        return PatternResult("human_in_loop", True, outputs)

    except Exception as e:
        return PatternResult("human_in_loop", False, error=str(e))


# ── Pattern dispatch ──────────────────────────────────────────────────

PATTERN_MAP = {
    OrchestrationPattern.PARALLEL: parallel,
    OrchestrationPattern.SEQUENTIAL: sequential,
    OrchestrationPattern.LOOP: loop,
    OrchestrationPattern.ROUTER: router,
    OrchestrationPattern.AGGREGATOR: aggregator,
    OrchestrationPattern.HIERARCHICAL: hierarchical,
    OrchestrationPattern.NETWORK: network,
    OrchestrationPattern.HUMAN_IN_LOOP: human_in_loop,
}
