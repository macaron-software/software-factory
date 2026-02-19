"""Pattern Execution Engine — runs pattern graphs with real agents.

Takes a PatternDef (graph of agent nodes + edges), resolves agents,
and executes them according to the pattern type (sequential, parallel,
loop, hierarchical, network/debate, wave).

All agent execution goes through the existing AgentExecutor + LLMClient.
Messages are stored in the session for WhatsApp-style display.

Context Rot Mitigation: older agent outputs are compressed to key points
to keep the context window fresh for each agent (inspired by GSD).

Wave Dependencies: nodes are grouped into waves based on dependency edges.
Agents within a wave run in parallel, waves run sequentially.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

# Prevent RecursionError in deep async pattern chains
sys.setrecursionlimit(max(sys.getrecursionlimit(), 5000))

from ..agents.store import get_agent_store, AgentDef
from ..agents.executor import get_executor, ExecutionContext, ExecutionResult
from ..sessions.store import get_session_store, SessionDef, MessageDef
from ..projects.manager import get_project_store
from ..memory.manager import get_memory_manager
from ..skills.library import get_skill_library
from .store import PatternDef

logger = logging.getLogger(__name__)

# Context rot mitigation: max chars of accumulated context per agent
CONTEXT_BUDGET = 6000
# Max chars to keep from each older agent's output when compressing
COMPRESSED_OUTPUT_SIZE = 400


class NodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    VETOED = "vetoed"
    FAILED = "failed"


@dataclass
class NodeState:
    node_id: str
    agent_id: str
    agent: Optional[AgentDef] = None
    status: NodeStatus = NodeStatus.PENDING
    result: Optional[ExecutionResult] = None
    output: str = ""


@dataclass
class PatternRun:
    """Runtime state of a pattern execution."""
    pattern: PatternDef
    session_id: str
    project_id: str = ""
    project_path: str = ""  # workspace filesystem path for tools
    phase_id: str = ""  # mission phase_id for SSE routing
    nodes: dict[str, NodeState] = field(default_factory=dict)
    iteration: int = 0
    max_iterations: int = 5
    finished: bool = False
    success: bool = False
    error: str = ""
    flow_step: str = ""


# SSE push (import from runner to share the same queues)
from ..sessions.runner import _push_sse


async def _sse(run: PatternRun, event: dict):
    """Push SSE event with automatic phase_id injection."""
    if run.phase_id and "phase_id" not in event:
        event["phase_id"] = run.phase_id
    await _push_sse(run.session_id, event)

# Protocol that makes agents produce trackable PRs/deliverables
_PR_PROTOCOL = """[IMPORTANT — Team Protocol]
You are part of a team working together. Address your colleague directly.
When you produce deliverables or action items, list them as:
- [PR] Short title — description
Example: [PR] Update Angular deps — Upgrade @angular/core from 16.2 to 17.3
Each [PR] will be tracked in the project dashboard."""

# Execution protocol for worker agents — they must USE tools to actually do the work
_EXEC_PROTOCOL = """[EXECUTION MODE — MANDATORY: You MUST produce REAL code changes]

CRITICAL RULE: You are a DEVELOPER, not a consultant. Your job is to WRITE CODE, not reports.
If your response contains NO code_write or code_edit calls, YOU HAVE FAILED your task.

Available tools: list_files, code_read, code_search, code_edit, code_write, git_status.

MANDATORY WORKFLOW (all steps required):
1. EXPLORE: Use list_files and code_read to understand the current codebase
2. PLAN: Identify exactly what files need to change (1-2 sentences max)
3. EXECUTE: Use code_edit (for modifications) or code_write (for new files) — THIS IS THE MAIN STEP
4. VERIFY: Use code_read to confirm your changes are correct
5. REPORT: List each change as [PR] with the actual file path you modified

RULES:
- You MUST call code_write or code_edit at least once. Describing changes without making them = FAILURE.
- Use relative paths (e.g. "src/app/auth/auth.component.ts"), they are resolved automatically.
- For new files: code_write with full content.
- For modifications: code_edit with old_str (exact match) and new_str.
- Each [PR] MUST reference a file you actually changed with code_write/code_edit.
- Do NOT say "here's what should be done" — DO IT."""

# Validation protocol for QA agents
_QA_PROTOCOL = """[VALIDATION MODE — Verify changes are correct]
Your job is to VERIFY that changes are correct, not to describe what should be tested.

MANDATORY WORKFLOW:
1. READ the changed files (code_read) — verify the modifications
2. SEARCH for regressions (code_search) — check no broken references
3. CHECK consistency — imports, types, configs must be coherent
4. VERDICT — MUST end with EXACTLY one of these tags:
   - [APPROVE] if all changes are correct and complete
   - [VETO] if ANY issue found — list specific problems

IMPORTANT: You MUST include [APPROVE] or [VETO] in your response. No other verdict format accepted.
If stories are not delivered or code is incomplete → [VETO]
Be concrete: cite file names, line numbers, specific problems."""

# Review protocol for lead agents
_REVIEW_PROTOCOL = """[REVIEW MODE — Quality gate]
Review the work done by your team. Use tools to verify claims.

MANDATORY:
1. READ the actual code changes (code_read, code_search) — don't trust descriptions blindly
2. CHECK completeness — are all subtasks addressed?
3. CHECK quality — no shortcuts, no skipped validations
4. VERDICT — MUST end with EXACTLY one of these tags:
   - [APPROVE] if all work is complete and verified
   - [VETO] if ANY deliverable is missing or broken
5. SYNTHESIZE: consolidated status with specific file references

IMPORTANT: You MUST include [APPROVE] or [VETO] in your response. The workflow will be blocked if you VETO."""

# Research protocol for ideation/discussion — agents can READ docs, search memory, but NOT write code
_RESEARCH_PROTOCOL = """[DISCUSSION MODE]

You are an EXPERT in a collaborative team discussion.
Respond DIRECTLY with your analysis — do NOT use tools or write code.

RULES:
- Speak naturally as a domain expert in a meeting
- @mention colleagues when addressing them or asking questions
- React to what others have said, don't repeat
- Be concise: 150-300 words max
- Give concrete recommendations, not generic advice
- Challenge ideas constructively when you disagree"""


def _build_team_context(run: PatternRun, current_node: str, to_agent_id: str) -> str:
    """Build team awareness: who's on the team, what's the communication flow."""
    parts = []
    current = run.nodes.get(current_node)
    if not current or not current.agent:
        return ""

    # List team members
    team = []
    for nid, ns in run.nodes.items():
        if ns.agent and nid != current_node:
            status = ""
            if ns.status == NodeStatus.COMPLETED and ns.output:
                status = " (has already contributed)"
            team.append(f"  - {ns.agent.name} ({ns.agent.role}){status}")
    if team:
        parts.append(f"[Your team]:\n" + "\n".join(team))

    # Who are you addressing?
    if to_agent_id and to_agent_id not in ("all", "session"):
        target = None
        for ns in run.nodes.values():
            if ns.agent and ns.agent.id == to_agent_id:
                target = ns.agent
                break
        if target:
            parts.append(f"[You are addressing]: {target.name} ({target.role})")

    return "\n".join(parts)


async def run_pattern(
    pattern: PatternDef,
    session_id: str,
    initial_task: str,
    project_id: str = "",
    project_path: str = "",
    phase_id: str = "",
) -> PatternRun:
    """Execute a pattern graph in a session. Returns the run state."""
    run = PatternRun(
        pattern=pattern,
        session_id=session_id,
        project_id=project_id,
        project_path=project_path,
        phase_id=phase_id,
        max_iterations=pattern.config.get("max_iterations", 5),
    )

    # Resolve agents for each node
    agent_store = get_agent_store()
    for node in pattern.agents:
        nid = node["id"]
        agent_id = node.get("agent_id") or ""
        agent = agent_store.get(agent_id) if agent_id else None
        run.nodes[nid] = NodeState(node_id=nid, agent_id=agent_id, agent=agent)

    # Determine pattern leader (first agent in the pattern)
    first_node = pattern.agents[0] if pattern.agents else None
    pattern_leader = (first_node.get("agent_id") or "") if first_node else ""

    # Log pattern start — target the leader, not broadcast
    store = get_session_store()
    store.add_message(MessageDef(
        session_id=session_id,
        from_agent="system",
        to_agent=pattern_leader or "all",
        message_type="system",
        content=f"Pattern **{pattern.name}** started ({pattern.type})",
    ))
    await _sse(run, {
        "type": "pattern_start",
        "pattern_id": pattern.id,
        "pattern_name": pattern.name,
    })

    try:
        import sys
        # Prevent recursion errors from deep async/httpx stacks during concurrent LLM calls
        if sys.getrecursionlimit() < 3000:
            sys.setrecursionlimit(3000)

        ptype = pattern.type
        if ptype == "solo":
            await _run_solo(run, initial_task)
        elif ptype == "sequential":
            await _run_sequential(run, initial_task)
        elif ptype == "parallel":
            await _run_parallel(run, initial_task)
        elif ptype == "loop":
            await _run_loop(run, initial_task)
        elif ptype == "hierarchical":
            await _run_hierarchical(run, initial_task)
        elif ptype == "network":
            await _run_network(run, initial_task)
        elif ptype == "router":
            await _run_router(run, initial_task)
        elif ptype == "aggregator":
            await _run_aggregator(run, initial_task)
        elif ptype == "wave":
            await _run_wave(run, initial_task)
        elif ptype == "human-in-the-loop":
            await _run_human_in_the_loop(run, initial_task)
        else:
            await _run_sequential(run, initial_task)

        run.finished = True
        has_vetoes = any(n.status == NodeStatus.VETOED for n in run.nodes.values())
        all_ok = all(
            n.status in (NodeStatus.COMPLETED, NodeStatus.PENDING)
            for n in run.nodes.values()
        )
        run.success = all_ok and not has_vetoes
    except Exception as e:
        run.finished = True
        run.error = str(e)
        has_vetoes = False
        logger.error("Pattern %s failed: %s", pattern.name, e, exc_info=True)

    # Log pattern end
    if run.success:
        status = "COMPLETED"
    elif has_vetoes:
        status = "NOGO — vetoes non résolus"
    else:
        status = f"FAILED: {run.error}"
    store.add_message(MessageDef(
        session_id=session_id,
        from_agent="system",
        to_agent=pattern_leader or "all",
        message_type="system",
        content=f"Pattern **{pattern.name}** {status}",
    ))
    await _sse(run, {
        "type": "pattern_end",
        "success": run.success,
        "error": run.error,
    })

    return run


async def _execute_node(
    run: PatternRun, node_id: str, task: str,
    context_from: str = "", to_agent_id: str = "",
) -> str:
    """Execute a single node: call its agent with the task, store messages."""
    state = run.nodes.get(node_id)
    if not state or not state.agent:
        return f"[Node {node_id} has no agent assigned]"

    state.status = NodeStatus.RUNNING
    agent = state.agent
    store = get_session_store()

    # Push thinking status
    await _sse(run, {
        "type": "agent_status",
        "agent_id": agent.id,
        "node_id": node_id,
        "status": "thinking",
    })

    # Build context
    ctx = await _build_node_context(agent, run)

    # Build team-aware context
    team_info = _build_team_context(run, node_id, to_agent_id)
    full_task = ""
    if team_info:
        full_task += f"{team_info}\n\n"
    if context_from:
        full_task += f"[Message from colleague]:\n{context_from}\n\n"
    full_task += f"[Your task]:\n{task}\n\n"

    # Inject role-based execution protocol
    role_lower = (agent.role or "").lower()
    rank = getattr(agent, "hierarchy_rank", 50)
    has_project = bool(run.project_id)
    if has_project:
        if rank >= 40 or "dev" in role_lower:
            full_task += _EXEC_PROTOCOL
        elif "qa" in role_lower or "test" in role_lower:
            full_task += _QA_PROTOCOL
        elif "lead" in role_lower:
            full_task += _REVIEW_PROTOCOL
        full_task += "\n\n" + _PR_PROTOCOL
    else:
        # Ideation / research — read tools OK, no code writing
        full_task += _RESEARCH_PROTOCOL

    # Execute with streaming SSE
    executor = get_executor()
    result = None

    await _sse(run, {
        "type": "stream_start",
        "agent_id": agent.id,
        "agent_name": agent.name,
        "node_id": node_id,
        "pattern_type": run.pattern.type,
        "to_agent": to_agent_id or "all",
        "iteration": run.iteration,
        "flow_step": run.flow_step,
    })

    import re as _re
    in_think = False
    in_tool_call = False
    think_chunks = 0
    try:
        async for kind, value in executor.run_streaming(ctx, full_task):
            if kind == "delta":
                delta = value
                # Filter <think> blocks
                if "<think>" in delta:
                    in_think = True
                if "</think>" in delta:
                    in_think = False
                    continue
                # Filter <minimax:tool_call> artifacts
                if "<minimax:tool_call>" in delta or "<tool_call>" in delta:
                    in_tool_call = True
                if "</minimax:tool_call>" in delta or "</tool_call>" in delta:
                    in_tool_call = False
                    continue
                if in_think:
                    think_chunks += 1
                    # Send heartbeat every 20 think chunks so frontend knows agent is alive
                    if think_chunks % 20 == 0:
                        await _sse(run, {
                            "type": "stream_thinking",
                            "agent_id": agent.id,
                        })
                elif not in_tool_call:
                    await _sse(run, {
                        "type": "stream_delta",
                        "agent_id": agent.id,
                        "delta": delta,
                    })
            elif kind == "result":
                result = value
    except Exception as exc:
        logger.error("Streaming failed for %s, falling back: %s", agent.id, exc)
        result = await executor.run(ctx, full_task)

    if result is None:
        result = await executor.run(ctx, full_task)

    # Strip <think> and tool-call artifacts from final content
    content = result.content or ""
    if "<think>" in content:
        content = _re.sub(r"<think>.*?</think>\s*", "", content, flags=_re.DOTALL).strip()
    if "<minimax:tool_call>" in content or "<tool_call>" in content:
        content = _re.sub(r"<minimax:tool_call>.*?</minimax:tool_call>\s*", "", content, flags=_re.DOTALL).strip()
        content = _re.sub(r"<tool_call>.*?</tool_call>\s*", "", content, flags=_re.DOTALL).strip()
    if content != (result.content or ""):
        result = ExecutionResult(
            content=content, agent_id=result.agent_id, model=result.model,
            provider=result.provider, tokens_in=result.tokens_in,
            tokens_out=result.tokens_out, duration_ms=result.duration_ms,
            tool_calls=result.tool_calls, delegations=result.delegations,
            error=result.error,
        )

    state.result = result
    state.output = content

    # Detect VETO/NOGO/APPROVE — must be explicit decisions, not mentions
    msg_type = "text"
    content_upper = content.upper()
    # Only detect NOGO as explicit status declarations, not mentions in text
    is_veto = (
        "[VETO]" in content
        or "[NOGO]" in content_upper
        or "STATUT: NOGO" in content_upper
        or "STATUT : NOGO" in content_upper
        or "DÉCISION: NOGO" in content_upper
        or "DÉCISION : NOGO" in content_upper
        or "DECISION: NOGO" in content_upper
        or "DECISION : NOGO" in content_upper
        or "\nNOGO\n" in content_upper
        or content_upper.strip() == "NOGO"
    )
    is_approve = (
        "[APPROVE]" in content
        or "STATUT: GO" in content_upper
        or "STATUT : GO" in content_upper
        or "DÉCISION: GO" in content_upper
        or "DÉCISION : GO" in content_upper
        or "DECISION: GO" in content_upper
        or "DECISION : GO" in content_upper
    )
    if is_approve and not is_veto:
        msg_type = "approve"
        state.status = NodeStatus.COMPLETED
    elif is_veto:
        msg_type = "veto"
        state.status = NodeStatus.VETOED
        logger.warning("VETO detected from %s: %s", agent.id, content[:200])
    elif result.error:
        msg_type = "system"
        state.status = NodeStatus.FAILED
    else:
        state.status = NodeStatus.COMPLETED

    store.add_message(MessageDef(
        session_id=run.session_id,
        from_agent=agent.id,
        to_agent=to_agent_id or "all",
        message_type=msg_type,
        content=content,
        metadata={
            "model": result.model,
            "provider": result.provider,
            "tokens_in": result.tokens_in,
            "tokens_out": result.tokens_out,
            "duration_ms": result.duration_ms,
            "node_id": node_id,
            "pattern_id": run.pattern.id,
            "pattern_type": run.pattern.type,
            "tool_calls": result.tool_calls if result.tool_calls else None,
        },
    ))

    # Compute activity counts for UI badges
    tcs = result.tool_calls or []
    edit_count = sum(1 for tc in tcs if tc.get("name") in ("code_edit", "code_write"))
    read_count = sum(1 for tc in tcs if tc.get("name") in ("code_read", "code_search", "list_files"))

    await _sse(run, {
        "type": "stream_end",
        "agent_id": agent.id,
        "content": content,
        "message_type": msg_type,
        "to_agent": to_agent_id or "all",
        "flow_step": run.flow_step,
    })

    await _sse(run, {
        "type": "message",
        "from_agent": agent.id,
        "to_agent": to_agent_id or "all",
        "content": content,
        "message_type": msg_type,
        "pattern_type": run.pattern.type,
        "node_id": node_id,
        "edits": edit_count,
        "reads": read_count,
        "tool_count": len(tcs),
    })

    await _sse(run, {
        "type": "agent_status",
        "agent_id": agent.id,
        "status": "idle",
    })

    # Store key insights in project memory + notify frontend
    if run.project_id and content and not result.error:
        try:
            mem = get_memory_manager()
            import re as _re2
            clean = _re2.sub(r'\[.*?\]', '', content).strip()
            # Extract structured decisions: [PR], architecture choices, tech decisions
            decisions = []
            for line in content.split('\n'):
                line_s = line.strip()
                if line_s.startswith('[PR]'):
                    decisions.append(line_s)
                elif any(kw in line_s.lower() for kw in ('decision:', 'choix:', 'stack:', 'architecture:')):
                    decisions.append(line_s)
            summary = "\n".join(decisions[:5]) if decisions else clean[:300]
            # Use semantic category based on agent role
            role_lower = (agent.role or "").lower()
            if "archi" in role_lower:
                cat = "architecture"
            elif "qa" in role_lower or "test" in role_lower:
                cat = "quality"
            elif "dev" in role_lower or "lead" in role_lower:
                cat = "development"
            elif "secu" in role_lower:
                cat = "security"
            elif "devops" in role_lower or "sre" in role_lower or "pipeline" in role_lower:
                cat = "infrastructure"
            elif "product" in role_lower or "business" in role_lower:
                cat = "product"
            else:
                cat = "decisions"
            mem.project_store(
                run.project_id,
                key=f"{agent.name}: {run.flow_step or run.pattern.type}",
                value=summary,
                category=cat,
                source=agent.id,
            )
            await _sse(run, {
                "type": "memory_stored",
                "category": cat,
                "key": f"{agent.name}: {run.flow_step or 'contribution'}",
                "value": summary[:200],
                "agent_id": agent.id,
            })
        except Exception:
            pass

    return content


async def _build_node_context(agent: AgentDef, run: PatternRun) -> ExecutionContext:
    """Build execution context for a node's agent."""
    store = get_session_store()
    history = store.get_messages(run.session_id, limit=30)
    history_dicts = [{"from_agent": m.from_agent, "content": m.content,
                      "message_type": m.message_type} for m in history]

    project_context = ""
    vision = ""
    project_path = ""
    if run.project_id:
        try:
            proj_store = get_project_store()
            project = proj_store.get(run.project_id)
            if project:
                vision = project.vision[:3000] if project.vision else ""
                project_path = getattr(project, "path", "") or ""
                mem = get_memory_manager()
                entries = mem.project_get(run.project_id, limit=10)
                if entries:
                    project_context = "\n".join(
                        f"[{e['category']}] {e['key']}: {e['value'][:200]}"
                        for e in entries
                    )
        except Exception:
            pass

    # Fallback: use workspace_path from mission if project_path not found from registry
    if not project_path and run.project_path:
        project_path = run.project_path

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

    has_project = bool(run.project_id)
    # Enable tools only for execution phases with a real workspace AND dev-role agents
    # Ideation/research/comite agents should stream directly without tool round overhead
    rank = getattr(agent, "hierarchy_rank", 50)
    role_lower = (agent.role or "").lower()
    is_dev_agent = rank >= 40 or any(k in role_lower for k in ("dev", "qa", "test", "devops", "pipeline", "sre", "secur", "secu"))
    tools_for_agent = has_project and bool(project_path) and is_dev_agent

    # Role-based tool filtering — each agent only sees tools relevant to their role
    from ..agents.executor import _get_tools_for_agent
    allowed_tools = _get_tools_for_agent(agent) if tools_for_agent else None

    return ExecutionContext(
        agent=agent,
        session_id=run.session_id,
        project_id=run.project_id,
        project_path=project_path,
        history=history_dicts,
        project_context=project_context,
        skills_prompt=skills_prompt,
        vision=vision,
        tools_enabled=tools_for_agent,
        allowed_tools=allowed_tools,
    )


# ── Pattern Runners ─────────────────────────────────────────────

def _ordered_nodes(pattern: PatternDef) -> list[str]:
    """Return node IDs in topological order based on edges."""
    node_ids = [n["id"] for n in pattern.agents]
    # Build adjacency from sequential/parallel edges
    incoming = {nid: set() for nid in node_ids}
    for edge in pattern.edges:
        if edge.get("type") in ("sequential", "parallel"):
            incoming[edge["to"]].add(edge["from"])

    ordered = []
    remaining = set(node_ids)
    while remaining:
        # Find nodes with no unresolved incoming
        ready = [n for n in remaining if not (incoming[n] - set(ordered))]
        if not ready:
            # Cycle detected, just add remaining
            ordered.extend(remaining)
            break
        ordered.extend(sorted(ready))
        remaining -= set(ready)
    return ordered


def _node_agent_id(run: PatternRun, node_id: str) -> str:
    """Get the agent ID assigned to a node."""
    state = run.nodes.get(node_id)
    return state.agent.id if state and state.agent else node_id


def _compress_output(text: str, max_chars: int = COMPRESSED_OUTPUT_SIZE) -> str:
    """Compress an agent's output to key points for context rot mitigation.

    Keeps: first paragraph, lines with decisions/actions/key markers.
    Discards: verbose analysis, repeated context, filler.
    """
    if len(text) <= max_chars:
        return text
    lines = text.split('\n')
    kept = []
    char_count = 0
    # Always keep first non-empty paragraph
    for line in lines:
        if line.strip():
            kept.append(line)
            char_count += len(line)
            break
    # Then scan for high-signal lines
    signal_markers = (
        'decision', 'choix', 'stack', 'conclusion', 'recommand',
        'action', 'verdict', 'valide', 'approve', 'reject', 'veto',
        '[pr]', 'architecture', 'technologie', 'priorit',
        '- ', '* ', '1.', '2.', '3.',
    )
    for line in lines[1:]:
        stripped = line.strip().lower()
        if not stripped:
            continue
        if any(m in stripped for m in signal_markers) or stripped.startswith('#'):
            kept.append(line)
            char_count += len(line)
            if char_count >= max_chars:
                break
    result = '\n'.join(kept)
    if len(result) > max_chars:
        result = result[:max_chars] + '...'
    return result


def _build_compressed_context(accumulated: list[str], budget: int = CONTEXT_BUDGET) -> str:
    """Build context string with compression for older outputs.

    Last agent's output stays full. Earlier outputs are compressed
    to fit within the budget — preventing context rot.
    """
    if not accumulated:
        return ""
    if len(accumulated) == 1:
        return accumulated[0][:budget]

    last = accumulated[-1]
    older = accumulated[:-1]

    # Reserve half budget for last output, half for compressed older
    last_budget = budget // 2
    older_budget = budget - last_budget

    last_text = last[:last_budget]

    # Compress older outputs to fit
    per_agent = max(200, older_budget // len(older))
    compressed = []
    for entry in older:
        # Entry format: "[AgentName]:\n{output}"
        header_end = entry.find('\n')
        if header_end > 0:
            header = entry[:header_end]
            body = _compress_output(entry[header_end + 1:], per_agent)
            compressed.append(f"{header}\n{body}")
        else:
            compressed.append(_compress_output(entry, per_agent))

    return "\n\n---\n\n".join(compressed) + "\n\n---\n\n" + last_text


def _compute_waves(pattern: PatternDef) -> list[list[str]]:
    """Compute dependency waves for parallel execution.

    Groups nodes into waves: all nodes in a wave have their dependencies
    satisfied by previous waves. Nodes within a wave run in parallel.

    Returns: [[wave1_nodes], [wave2_nodes], ...]
    """
    node_ids = [n["id"] for n in pattern.agents]
    if not node_ids:
        return []

    # Build dependency graph from edges
    incoming = {nid: set() for nid in node_ids}
    for edge in pattern.edges:
        src, dst = edge.get("from"), edge.get("to")
        if src in incoming and dst in incoming:
            incoming[dst].add(src)

    waves = []
    done = set()
    remaining = set(node_ids)

    while remaining:
        # Nodes whose dependencies are all in 'done'
        wave = [n for n in remaining if incoming[n] <= done]
        if not wave:
            # Cycle — put all remaining in one final wave
            waves.append(sorted(remaining))
            break
        wave.sort()
        waves.append(wave)
        done.update(wave)
        remaining -= set(wave)

    return waves


async def _run_solo(run: PatternRun, task: str):
    """Single agent execution."""
    nodes = list(run.nodes.keys())
    if nodes:
        await _execute_node(run, nodes[0], task)


async def _run_sequential(run: PatternRun, task: str):
    """Execute nodes in sequence, with context rot mitigation.

    Each agent sees compressed older outputs + full last output,
    keeping the context window fresh.
    """
    order = _ordered_nodes(run.pattern)
    accumulated = []
    first_agent = _node_agent_id(run, order[0]) if order else "all"
    for i, nid in enumerate(order):
        if i + 1 < len(order):
            to = _node_agent_id(run, order[i + 1])
        else:
            to = first_agent
        # Compressed context: older outputs summarized, last one full
        context = _build_compressed_context(accumulated) if accumulated else ""
        output = await _execute_node(
            run, nid, task, context_from=context, to_agent_id=to,
        )
        ns = run.nodes.get(nid)
        label = ns.agent.name if ns and ns.agent else nid
        accumulated.append(f"[{label}]:\n{output}")


async def _run_parallel(run: PatternRun, task: str):
    """Find dispatcher, fan out to workers, then aggregate."""
    order = _ordered_nodes(run.pattern)
    if not order:
        return

    dispatcher_id = order[0]
    dispatcher_agent = _node_agent_id(run, dispatcher_id)

    # Find parallel targets and aggregator
    parallel_targets = []
    agg_node = None
    for edge in run.pattern.edges:
        if edge["from"] == dispatcher_id and edge.get("type") == "parallel":
            parallel_targets.append(edge["to"])
    for node in run.pattern.agents:
        nid = node["id"]
        if nid != dispatcher_id and nid not in parallel_targets:
            agg_node = nid

    # Dispatcher sends to workers (first worker as target for display)
    first_worker = _node_agent_id(run, parallel_targets[0]) if parallel_targets else "all"
    dispatcher_output = await _execute_node(
        run, dispatcher_id, task, to_agent_id=first_worker,
    )

    # Fan out — each worker reports to aggregator (or dispatcher)
    agg_agent = _node_agent_id(run, agg_node) if agg_node else dispatcher_agent
    if parallel_targets:
        tasks = [
            _execute_node(run, nid, task, context_from=dispatcher_output, to_agent_id=agg_agent)
            for nid in parallel_targets
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate — aggregator reports to dispatcher
        if agg_node:
            combined = "\n\n".join(
                f"[Worker {parallel_targets[i]}]: {r if isinstance(r, str) else str(r)}"
                for i, r in enumerate(results)
            )
            await _execute_node(
                run, agg_node, task, context_from=combined, to_agent_id=dispatcher_agent,
            )


async def _run_loop(run: PatternRun, task: str):
    """Loop between writer and reviewer until approval or max iterations."""
    nodes = _ordered_nodes(run.pattern)
    if len(nodes) < 2:
        return await _run_sequential(run, task)

    writer_id = nodes[0]
    reviewer_id = nodes[1]
    writer_agent = _node_agent_id(run, writer_id)
    reviewer_agent = _node_agent_id(run, reviewer_id)

    prev_output = ""
    for i in range(run.max_iterations):
        run.iteration = i + 1

        # Writer produces → sends to reviewer
        writer_output = await _execute_node(
            run, writer_id, task, context_from=prev_output,
            to_agent_id=reviewer_agent,
        )

        # Reviewer evaluates → sends to writer
        review_output = await _execute_node(
            run, reviewer_id,
            f"Review the following work and either APPROVE or provide specific feedback:\n{writer_output}",
            to_agent_id=writer_agent,
        )

        # Check for approval or veto
        state = run.nodes[reviewer_id]
        if state.status == NodeStatus.VETOED:
            prev_output = f"[Reviewer feedback, iteration {i+1}]:\n{review_output}"
            state.status = NodeStatus.PENDING
            run.nodes[writer_id].status = NodeStatus.PENDING
        else:
            break


def _classify_agents(run: PatternRun, node_ids: list[str]) -> dict:
    """Classify nodes by role: manager, workers, qa, based on agent role/rank."""
    classified = {"manager": None, "workers": [], "qa": []}
    for nid in node_ids:
        ns = run.nodes.get(nid)
        if not ns or not ns.agent:
            continue
        role = (ns.agent.role or "").lower()
        rank = getattr(ns.agent, "hierarchy_rank", 50)
        if "qa" in role or "test" in role:
            classified["qa"].append(nid)
        elif "lead" in role or rank <= 20:
            # First lead/manager found — if we already have one, second is worker
            if classified["manager"] is None:
                classified["manager"] = nid
            else:
                classified["workers"].append(nid)
        elif "dev" in role or rank >= 40:
            classified["workers"].append(nid)
        else:
            # Chef de projet, securite, etc. — treat as manager or worker
            if classified["manager"] is None:
                classified["manager"] = nid
            else:
                classified["workers"].append(nid)
    return classified


async def _run_hierarchical(run: PatternRun, task: str):
    """Real team flow with inner dev loop and outer QA validation loop.

    Flow:
      1. Manager (lead_dev) decomposes work into sub-tasks for devs
      2. INNER LOOP: Devs execute in parallel → Manager reviews completeness
         - If incomplete: manager re-briefs devs with what's missing → devs continue
         - If complete: proceed to QA
      3. QA validates the completed work
      4. OUTER LOOP: If QA VETOs → Manager gets feedback → back to inner loop
      Max 3 outer iterations.
    """
    nodes = _ordered_nodes(run.pattern)
    if len(nodes) < 2:
        return await _run_sequential(run, task)

    roles = _classify_agents(run, nodes)
    manager_id = roles["manager"] or nodes[0]
    worker_ids = roles["workers"]
    qa_ids = roles["qa"]

    # Fallback: if no workers found, all non-manager non-qa are workers
    if not worker_ids:
        worker_ids = [n for n in nodes if n != manager_id and n not in qa_ids]
    if not worker_ids:
        return await _run_sequential(run, task)

    manager_agent = _node_agent_id(run, manager_id)

    # Build team roster
    worker_roster = []
    for wid in worker_ids:
        ws = run.nodes.get(wid)
        if ws and ws.agent:
            worker_roster.append(f"- {ws.agent.name} ({ws.agent.role})")

    max_outer = 3   # QA validation retries
    max_inner = 2   # Dev completeness retries
    veto_feedback = ""

    for outer in range(max_outer):
        # ── Reset statuses ──
        if outer > 0:
            for nid in nodes:
                run.nodes[nid].status = NodeStatus.PENDING
            store = get_session_store()
            store.add_message(MessageDef(
                session_id=run.session_id,
                from_agent="system", to_agent=manager_agent,
                message_type="system",
                content=f"QA loop {outer + 1}/{max_outer} — addressing VETO feedback",
            ))
            await _sse(run, {
                "type": "system",
                "content": f"QA validation loop {outer + 1}/{max_outer}",
            })

        # ── Step 1: Manager decomposes ──
        if outer == 0:
            decompose_prompt = (
                f"You are the tech lead. Decompose this work for your dev team.\n\n"
                f"Your team:\n" + "\n".join(worker_roster) + "\n\n"
                f"Create specific, actionable sub-tasks. Each dev should work on "
                f"complementary parts (NO overlap). Format: [SUBTASK N]: description\n\n"
                f"They must use code_edit/code_write to make REAL changes.\n\n{task}"
            )
        else:
            decompose_prompt = (
                f"QA REJECTED the work (iteration {outer + 1}).\n\n"
                f"## QA Feedback:\n{veto_feedback}\n\n"
                f"Your team:\n" + "\n".join(worker_roster) + "\n\n"
                f"Re-assign CORRECTIVE tasks based on QA's specific issues. "
                f"Each dev must fix the problems QA found in their area. "
                f"Format: [SUBTASK N]: description\n\n{task}"
            )

        # Build targeted routing
        worker_agents = [_node_agent_id(run, w) for w in worker_ids]
        # For messages addressing multiple workers, use first worker (UI shows conversation)
        workers_target = worker_agents[0] if len(worker_agents) == 1 else ",".join(worker_agents)
        qa_agents = [_node_agent_id(run, q) for q in qa_ids]

        manager_output = await _execute_node(
            run, manager_id, decompose_prompt, to_agent_id=workers_target,
        )

        # Parse subtasks
        subtasks = _parse_subtasks(manager_output)
        if not subtasks:
            subtasks = [task] * len(worker_ids)

        # ── Step 2: INNER LOOP — Devs work until lead says complete ──
        all_dev_work = ""
        for inner in range(max_inner):
            # Workers execute in parallel
            worker_tasks = []
            for i, wid in enumerate(worker_ids):
                st = subtasks[i] if i < len(subtasks) else subtasks[-1]
                if inner > 0:
                    st = (
                        f"INCOMPLETE — Your lead reviewed and needs more work:\n"
                        f"{all_dev_work}\n\nContinue your task:\n{st}"
                    )
                elif outer > 0:
                    st = f"QA CORRECTION (round {outer + 1}):\n{veto_feedback}\n\nYour task:\n{st}"
                worker_tasks.append(
                    _execute_node(run, wid, st, context_from=manager_output, to_agent_id=manager_agent)
                )
            results = await asyncio.gather(*worker_tasks, return_exceptions=True)

            # Collect worker outputs
            combined_parts = []
            for i, r in enumerate(results):
                ws = run.nodes.get(worker_ids[i])
                name = ws.agent.name if ws and ws.agent else worker_ids[i]
                combined_parts.append(f"[{name}]:\n{r if isinstance(r, str) else str(r)}")
            all_dev_work = "\n\n---\n\n".join(combined_parts)

            # Manager reviews completeness — sends to QA if done, workers if not
            run.nodes[manager_id].status = NodeStatus.PENDING
            qa_target = qa_agents[0] if qa_agents else manager_agent
            review_output = await _execute_node(
                run, manager_id,
                f"Review your team's work for COMPLETENESS (not quality — QA does that).\n\n"
                f"Check: Did each dev complete their assigned subtask? Are there unfinished items?\n\n"
                f"If complete: say [COMPLETE] and produce a consolidated [PR] list.\n"
                f"If NOT complete: say [INCOMPLETE] with what's missing — devs will continue.\n\n"
                f"Work submitted:\n{all_dev_work}",
                context_from=all_dev_work, to_agent_id=qa_target,
            )

            if "[INCOMPLETE]" in review_output.upper():
                # Re-parse manager's updated subtasks for next inner iteration
                new_subtasks = _parse_subtasks(review_output)
                if new_subtasks:
                    subtasks = new_subtasks
                for wid in worker_ids:
                    run.nodes[wid].status = NodeStatus.PENDING
                logger.warning("Inner loop: lead says INCOMPLETE, iteration %d", inner + 1)
                continue
            else:
                # Lead says complete — move to QA
                break

        # ── Step 3: QA validates ──
        if not qa_ids:
            # No QA agent — phase done
            return

        for qid in qa_ids:
            run.nodes[qid].status = NodeStatus.PENDING
            await _execute_node(
                run, qid,
                f"Validate ALL the work completed by the dev team.\n\n"
                f"Lead's consolidated review:\n{review_output}\n\n"
                f"Dev work:\n{all_dev_work}",
                context_from=review_output, to_agent_id=manager_agent,
            )

        # ── Step 4: Check QA verdicts ──
        vetoes = []
        for qid in qa_ids:
            ns = run.nodes[qid]
            if ns.status == NodeStatus.VETOED:
                agent_name = ns.agent.name if ns.agent else qid
                vetoes.append(f"[VETO by {agent_name}]: {(ns.output or '')[:500]}")

        if not vetoes:
            # QA approved — phase done
            return

        # QA rejected — build feedback for outer loop
        veto_feedback = "\n\n".join(vetoes)
        logger.warning("QA VETO at outer iteration %d: %d veto(s)", outer + 1, len(vetoes))

        store = get_session_store()
        store.add_message(MessageDef(
            session_id=run.session_id,
            from_agent="system", to_agent=manager_agent,
            message_type="system",
            content=f"QA rejected — {len(vetoes)} VETO(s). Feedback loop — re-assign corrections.",
        ))
        await _sse(run, {
            "type": "message",
            "from_agent": "system",
            "content": f"{len(vetoes)} VETO(s) — correction loop {outer + 1}/{max_outer}",
            "message_type": "system",
        })

    # Exhausted retries
    logger.warning("Hierarchical phase exhausted %d QA iterations with unresolved VETOs", max_outer)


def _parse_subtasks(text: str) -> list[str]:
    """Extract [SUBTASK N] items from manager output."""
    subtasks = []
    for line in text.split("\n"):
        if "[SUBTASK" in line.upper():
            subtask = line.split("]", 1)[-1].strip() if "]" in line else line
            if subtask:
                subtasks.append(subtask)
    return subtasks


async def _run_network(run: PatternRun, task: str):
    """Debate/network: agents discuss in rounds, judge decides."""
    nodes = _ordered_nodes(run.pattern)
    if len(nodes) < 2:
        return await _run_sequential(run, task)

    max_rounds = run.pattern.config.get("max_rounds", 3)

    # Find judge (node with only incoming "report" edges, or last node)
    judge_id = None
    debaters = []
    for node in run.pattern.agents:
        nid = node["id"]
        has_report_to = any(
            e["from"] == nid and e.get("type") == "report"
            for e in run.pattern.edges
        )
        has_bidirectional = any(
            (e["from"] == nid or e["to"] == nid) and e.get("type") == "bidirectional"
            for e in run.pattern.edges
        )
        if has_bidirectional:
            debaters.append(nid)
        elif not has_bidirectional and has_report_to:
            debaters.append(nid)
        else:
            judge_id = nid

    if not judge_id and nodes:
        judge_id = nodes[-1]
    if not debaters:
        debaters = [n for n in nodes if n != judge_id]

    # ── Step 1: Leader brief (hierarchical) ──
    # The judge/PO frames the discussion and assigns each expert
    leader_brief = ""
    debater_names = []
    for did in debaters:
        ns = run.nodes.get(did)
        if ns and ns.agent:
            debater_names.append(f"@{ns.agent.name} ({ns.agent.role or did})")
    team_list = ", ".join(debater_names) if debater_names else "l'équipe"

    if judge_id:
        run.flow_step = "Brief"
        leader_brief = await _execute_node(
            run, judge_id,
            f"Tu diriges cette session d'analyse. Voici ton équipe : {team_list}.\n\n"
            f"1. Cadre le sujet en 2-3 phrases\n"
            f"2. Assigne à CHAQUE expert (@mention) ce que tu attends de lui\n"
            f"3. Pose 1-2 questions clés pour orienter la discussion\n\n"
            f"Sujet soumis par le client :\n{task}",
            to_agent_id="all",
        )
        run.nodes[judge_id].status = NodeStatus.PENDING

    # ── Step 2: Debate rounds (network) ──
    # Experts discuss IN PARALLEL — like a real meeting
    prev_round = leader_brief
    for rnd in range(max_rounds):
        run.iteration = rnd + 1
        run.flow_step = "Analyse" if rnd == 0 else f"Débat round {rnd + 1}"

        if rnd == 0:
            prompt_tpl = (
                "Ton responsable a briefé l'équipe (ci-dessous). "
                "Réponds à ce qui te concerne, pose des questions aux collègues (@mention), "
                "et donne ton analyse d'expert.\n\n"
                f"Sujet : {task}"
            )
        else:
            prompt_tpl = (
                "Poursuis la discussion. Réagis aux points soulevés par tes collègues, "
                "réponds à leurs questions, challenge leurs propositions.\n\n"
                f"Sujet : {task}\n\n[Échanges précédents]:\n{prev_round}"
            )

        # All debaters respond in parallel (like a real meeting)
        async def _run_debater(did, prompt, context):
            peers = [d for d in debaters if d != did]
            to = _node_agent_id(run, peers[0]) if len(peers) == 1 else "all"
            output = await _execute_node(run, did, prompt, context_from=context, to_agent_id=to)
            return f"[{did}]: {output}"

        tasks = [_run_debater(did, prompt_tpl, prev_round) for did in debaters]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        round_outputs = [r if isinstance(r, str) else f"[error]: {r}" for r in results]
        prev_round = "\n\n".join(round_outputs)

    # ── Step 3: Judge synthesis ──
    # PO consolidates all contributions into a decision
    if judge_id:
        run.flow_step = "Synthèse"
        await _execute_node(
            run, judge_id,
            f"Synthétise toutes les contributions de ton équipe.\n\n"
            f"1. Résume les points clés de chaque expert\n"
            f"2. Identifie les consensus et les points de désaccord\n"
            f"3. Propose une décision et les prochaines étapes\n\n"
            f"Contributions :\n{prev_round}",
            to_agent_id="all",
        )


async def _run_router(run: PatternRun, task: str):
    """Router: first agent analyzes input and routes to the best specialist.

    Flow: Router classifies → picks one specialist → specialist executes → reports back.
    """
    nodes = _ordered_nodes(run.pattern)
    if len(nodes) < 2:
        return await _run_sequential(run, task)

    router_id = nodes[0]
    specialist_ids = nodes[1:]
    router_agent = _node_agent_id(run, router_id)

    # Build specialist roster
    specialist_roster = []
    for sid in specialist_ids:
        ns = run.nodes.get(sid)
        if ns and ns.agent:
            specialist_roster.append(f"- [{sid}] {ns.agent.name} ({ns.agent.role})")
        else:
            specialist_roster.append(f"- [{sid}] (unknown)")
    roster_text = "\n".join(specialist_roster)

    # Router classifies and picks
    run.flow_step = "Routing"
    router_output = await _execute_node(
        run, router_id,
        f"Analyse la demande et choisis le spécialiste le plus qualifié.\n\n"
        f"Spécialistes disponibles :\n{roster_text}\n\n"
        f"Réponds avec exactement [ROUTE: <node_id>] pour indiquer ton choix, "
        f"puis explique brièvement pourquoi.\n\n"
        f"Demande :\n{task}",
        to_agent_id="all",
    )

    # Parse route decision
    chosen_id = None
    for sid in specialist_ids:
        if f"[ROUTE: {sid}]" in router_output or f"[ROUTE:{sid}]" in router_output:
            chosen_id = sid
            break
    if not chosen_id:
        chosen_id = specialist_ids[0]

    # Execute chosen specialist
    run.flow_step = f"Exécution ({chosen_id})"
    await _execute_node(
        run, chosen_id, task, context_from=router_output,
        to_agent_id=router_agent,
    )


async def _run_aggregator(run: PatternRun, task: str):
    """Aggregator: multiple agents work in parallel, one aggregator consolidates.

    Unlike parallel (dispatcher → workers → aggregator), aggregator has NO dispatcher.
    Workers start independently, then the aggregator synthesizes all results.
    """
    nodes = _ordered_nodes(run.pattern)
    if len(nodes) < 2:
        return await _run_sequential(run, task)

    # Find aggregator (node that receives "aggregate" edges)
    agg_id = None
    worker_ids = []
    agg_targets = set()
    for edge in run.pattern.edges:
        if edge.get("type") == "aggregate":
            agg_targets.add(edge["to"])
    if agg_targets:
        agg_id = list(agg_targets)[0]
        worker_ids = [n for n in nodes if n != agg_id]
    else:
        agg_id = nodes[-1]
        worker_ids = nodes[:-1]

    agg_agent = _node_agent_id(run, agg_id)

    # Workers execute in parallel
    run.flow_step = "Analyse parallèle"
    worker_tasks = [
        _execute_node(run, wid, task, to_agent_id=agg_agent)
        for wid in worker_ids
    ]
    results = await asyncio.gather(*worker_tasks, return_exceptions=True)

    # Build consolidated input
    combined_parts = []
    for i, r in enumerate(results):
        ns = run.nodes.get(worker_ids[i])
        name = ns.agent.name if ns and ns.agent else worker_ids[i]
        combined_parts.append(f"[{name}]:\n{r if isinstance(r, str) else str(r)}")
    combined = "\n\n---\n\n".join(combined_parts)

    # Aggregator synthesizes
    run.flow_step = "Consolidation"
    await _execute_node(
        run, agg_id,
        f"Consolide les analyses de tous les experts en une synthèse actionable.\n\n"
        f"1. Résume les contributions clés de chaque expert\n"
        f"2. Identifie les points de convergence et de divergence\n"
        f"3. Propose un plan d'action consolidé avec priorités\n\n"
        f"Contributions :\n{combined}",
        context_from=combined, to_agent_id="all",
    )


async def _run_wave(run: PatternRun, task: str):
    """Wave execution: parallel within waves, sequential across waves.

    Analyzes the dependency graph and groups independent nodes into waves.
    Agents within a wave run in parallel (asyncio.gather).
    Each wave waits for the previous wave to complete.
    Context from previous waves is compressed to prevent context rot.
    """
    waves = _compute_waves(run.pattern)
    if not waves:
        return

    accumulated = []  # compressed outputs from all previous waves

    for wave_idx, wave_nodes in enumerate(waves):
        wave_label = f"Wave {wave_idx + 1}/{len(waves)}"
        logger.info("Wave execution: %s — %d agents in parallel", wave_label, len(wave_nodes))

        # Announce wave
        await _sse(run, {
            "type": "message",
            "content": f"{wave_label} — {len(wave_nodes)} agent(s) en parallele",
            "from_agent": "system",
        })

        # Build compressed context from previous waves
        context = _build_compressed_context(accumulated) if accumulated else ""

        if len(wave_nodes) == 1:
            # Single node — run directly
            nid = wave_nodes[0]
            to = "all"
            output = await _execute_node(run, nid, task, context_from=context, to_agent_id=to)
            ns = run.nodes.get(nid)
            label = ns.agent.name if ns and ns.agent else nid
            accumulated.append(f"[{label}]:\n{output}")
        else:
            # Multiple nodes — run in parallel
            coros = [
                _execute_node(run, nid, task, context_from=context, to_agent_id="all")
                for nid in wave_nodes
            ]
            results = await asyncio.gather(*coros, return_exceptions=True)

            for nid, result in zip(wave_nodes, results):
                ns = run.nodes.get(nid)
                label = ns.agent.name if ns and ns.agent else nid
                output = result if isinstance(result, str) else str(result)
                accumulated.append(f"[{label}]:\n{output}")


async def _run_human_in_the_loop(run: PatternRun, task: str):
    """Human-in-the-loop: agents work, with human validation checkpoints.

    Checkpoint edges mark where human validation is required.
    Inserts a system message and SSE event for the UI to show a validation prompt.
    """
    nodes = _ordered_nodes(run.pattern)
    if not nodes:
        return

    store = get_session_store()

    # Find checkpoint edges
    checkpoint_sources = {
        e["from"] for e in run.pattern.edges if e.get("type") == "checkpoint"
    }

    prev_output = ""
    for i, nid in enumerate(nodes):
        ns = run.nodes.get(nid)

        # Skip "human" placeholder nodes (no agent_id)
        if ns and not ns.agent_id:
            checkpoint_msg = run.pattern.config.get(
                "checkpoint_message",
                "Point de contrôle — En attente de votre validation."
            )
            store.add_message(MessageDef(
                session_id=run.session_id,
                from_agent="system",
                to_agent="user",
                message_type="system",
                content=f"**CHECKPOINT HUMAIN**\n\n{checkpoint_msg}\n\n"
                        f"_Résumé du travail effectué :_\n{prev_output[:500]}",
            ))
            await _sse(run, {
                "type": "checkpoint",
                "content": checkpoint_msg,
                "requires_input": True,
            })
            run.flow_step = "Checkpoint humain"
            continue

        to_agent = "all"
        if i + 1 < len(nodes):
            next_ns = run.nodes.get(nodes[i + 1])
            if next_ns and next_ns.agent_id:
                to_agent = next_ns.agent_id

        output = await _execute_node(
            run, nid, task, context_from=prev_output, to_agent_id=to_agent,
        )
        prev_output = output

        # Insert checkpoint after this node if it has a checkpoint edge
        if nid in checkpoint_sources:
            store.add_message(MessageDef(
                session_id=run.session_id,
                from_agent="system",
                to_agent="user",
                message_type="system",
                content=f"**VALIDATION REQUISE**\n\n"
                        f"L'agent a terminé son travail. Validez ou demandez des corrections.\n\n"
                        f"_Résultat :_\n{output[:500]}",
            ))
            await _sse(run, {
                "type": "checkpoint",
                "content": "Validation humaine requise",
                "requires_input": True,
            })
