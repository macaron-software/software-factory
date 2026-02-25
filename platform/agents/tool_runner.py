"""Tool runner — tool registry, execution, and individual tool handlers.

Extracted from executor.py to keep the main file focused on the agent loop.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..llm.client import LLMToolCall
    from .executor import ExecutionContext

logger = logging.getLogger(__name__)


def _get_tool_registry():
    """Lazy import to avoid circular imports."""
    from ..tools.build_tools import register_build_tools
    from ..tools.code_tools import register_code_tools
    from ..tools.git_tools import register_git_tools
    from ..tools.registry import ToolRegistry

    reg = ToolRegistry()
    register_code_tools(reg)
    register_git_tools(reg)
    register_build_tools(reg)
    try:
        from ..tools.mcp_bridge import register_mcp_tools

        register_mcp_tools(reg)
    except Exception:
        pass
    # Solaris Design System tools
    try:
        from ..tools.mcp_bridge import register_solaris_tools

        register_solaris_tools(reg)
    except Exception:
        pass
    # Memory tools
    try:
        from ..tools.memory_tools import register_memory_tools

        register_memory_tools(reg)
    except Exception:
        pass
    # Web research tools
    try:
        from ..tools.web_tools import register_web_tools

        register_web_tools(reg)
    except Exception:
        pass
    # Deploy tools (docker build + Azure VM)
    try:
        from ..tools.deploy_tools import register_deploy_tools

        register_deploy_tools(reg)
    except Exception:
        pass
    # Phase orchestration tools (mission control)
    try:
        from ..tools.phase_tools import register_phase_tools

        register_phase_tools(reg)
    except Exception:
        pass
    # Playwright test/screenshot tools
    try:
        from ..tools.test_tools import register_test_tools

        register_test_tools(reg)
    except Exception:
        pass
    # Platform introspection tools (agents, missions, memory, metrics)
    try:
        from ..tools.platform_tools import register_platform_tools

        register_platform_tools(reg)
    except Exception:
        pass
    # Composition tools (dynamic workflow/team/mission creation)
    try:
        from ..tools.compose_tools import register_compose_tools

        register_compose_tools(reg)
    except Exception:
        pass
    # Android build tools (gradle, emulator, lint)
    try:
        from ..tools.android_tools import register_android_tools

        register_android_tools(reg)
    except Exception:
        pass
    # Quality scanning tools (complexity, coverage, security metrics)
    try:
        from ..tools.quality_tools import register_quality_tools

        register_quality_tools(reg)
    except Exception:
        pass
    return reg


# ── Helpers ──────────────────────────────────────────────────────


def _parse_xml_tool_calls(content: str) -> list:
    """Parse tool calls from LLM content (multiple formats)."""
    import uuid as _uuid

    from ..llm.client import LLMToolCall as _TC

    calls = []

    # Format 1: <invoke name="tool_name"><parameter name="key">value</parameter>...</invoke>
    invoke_re = re.compile(r'<invoke\s+name="([^"]+)">(.*?)</invoke>', re.DOTALL)
    param_re = re.compile(r'<parameter\s+name="([^"]+)">(.*?)</parameter>', re.DOTALL)
    for m in invoke_re.finditer(content):
        fn_name = m.group(1)
        body = m.group(2)
        args = {}
        for pm in param_re.finditer(body):
            args[pm.group(1)] = pm.group(2).strip()
        calls.append(
            _TC(
                id=f"call_{_uuid.uuid4().hex[:12]}",
                function_name=fn_name,
                arguments=args,
            )
        )
    if calls:
        return calls

    # Format 2: [TOOL_CALL]{ tool => 'name', args => { --KEY "value" }}[/TOOL_CALL]
    tc_re = re.compile(
        r'\[TOOL_CALL\]\s*\{[^}]*tool\s*=>\s*[\'"]([^\'"]+)[\'"].*?args\s*=>\s*\{(.*?)\}\s*\}?\s*\[/TOOL_CALL\]',
        re.DOTALL,
    )
    arg_re = re.compile(r'--(\w+)\s+"([^"]*)"')
    for m in tc_re.finditer(content):
        fn_name = m.group(1)
        args_block = m.group(2)
        args = {}
        for am in arg_re.finditer(args_block):
            key = am.group(1).lower()
            # Normalize arg names to match tool schemas
            if key == "file_path":
                key = "path"
            elif key == "project_path":
                key = "cwd"
            elif key == "phase_name":
                key = "phase_id"
            elif key == "context":
                key = "brief"
            args[key] = am.group(2)
        calls.append(
            _TC(
                id=f"call_{_uuid.uuid4().hex[:12]}",
                function_name=fn_name,
                arguments=args,
            )
        )
    if calls:
        return calls

    # Format 3: <tool_call>{"name":"tool","arguments":{...}}</tool_call> (JSON inside XML)
    tc_json_re = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)
    for m in tc_json_re.finditer(content):
        try:
            data = json.loads(m.group(1))
            fn_name = data.get("name", "")
            args = data.get("arguments", {})
            if fn_name:
                calls.append(
                    _TC(
                        id=f"call_{_uuid.uuid4().hex[:12]}",
                        function_name=fn_name,
                        arguments=args if isinstance(args, dict) else {},
                    )
                )
        except json.JSONDecodeError:
            pass

    return calls


def _record_artifact(ctx: ExecutionContext, tc: LLMToolCall, result: str):
    """Record a code_write/code_edit as an artifact in the DB."""
    import uuid

    from ..db.migrations import get_db

    path = tc.arguments.get("path", "unknown")
    art_type = "edit" if tc.function_name == "code_edit" else "create"
    content = (
        tc.arguments.get("content", "")
        or f"Edit: {tc.arguments.get('old_str', '')[:100]} → {tc.arguments.get('new_str', '')[:100]}"
    )
    lang = os.path.splitext(path)[1].lstrip(".")
    db = get_db()
    try:
        db.execute(
            "INSERT INTO artifacts (id, session_id, type, name, content, language, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4())[:8],
                ctx.session_id,
                art_type,
                f"[{art_type.upper()}] {path}",
                content[:2000],
                lang,
                ctx.agent.id,
            ),
        )
        db.commit()
    except Exception as e:
        logger.warning("Failed to record artifact: %s", e)
    finally:
        db.close()


def _build_phase_edges(pattern_type: str, agents: list[dict]) -> list[dict]:
    """Build edges for a phase pattern based on type."""
    edges = []
    ids = [a["id"] for a in agents]
    if not ids:
        return edges
    if pattern_type in ("sequential",):
        for i in range(len(ids) - 1):
            edges.append({"from": ids[i], "to": ids[i + 1], "type": "then"})
    elif pattern_type in ("hierarchical",):
        for worker in ids[1:]:
            edges.append({"from": ids[0], "to": worker, "type": "delegate"})
    elif pattern_type in ("parallel", "aggregator"):
        for worker in ids[:-1]:
            edges.append({"from": worker, "to": ids[-1], "type": "aggregate"})
    elif pattern_type in ("loop",):
        if len(ids) >= 2:
            edges.append({"from": ids[0], "to": ids[1], "type": "review"})
            edges.append({"from": ids[1], "to": ids[0], "type": "feedback"})
    elif pattern_type in ("network",):
        for i, a in enumerate(ids):
            for b in ids[i + 1 :]:
                edges.append({"from": a, "to": b, "type": "discuss"})
    elif pattern_type in ("router",):
        for specialist in ids[1:]:
            edges.append({"from": ids[0], "to": specialist, "type": "route"})
    elif pattern_type in ("human-in-the-loop",):
        for i in range(len(ids) - 1):
            edges.append({"from": ids[i], "to": ids[i + 1], "type": "then"})
    return edges


async def _push_mission_sse(session_id: str, event: dict):
    """Push SSE event for mission control updates."""
    from ..sessions.runner import _push_sse

    await _push_sse(session_id, event)


# ── Individual tool handlers (standalone functions) ──────────────


async def _tool_list_files(args: dict) -> str:
    """List directory contents."""
    import os

    path = args.get("path", ".")
    depth = int(args.get("depth", 2))
    # Fix path doubling: if path doesn't exist, try stripping duplicate basename
    if not os.path.isdir(path):
        parent = os.path.dirname(path)
        base = os.path.basename(path)
        # e.g. /app/workspace/devpulse/devpulse → /app/workspace/devpulse
        if os.path.basename(parent) == base and os.path.isdir(parent):
            path = parent
        elif not os.path.exists(path):
            return f"Error: not a directory: {path}"
        elif os.path.isfile(path):
            return (
                f"Note: '{path}' is a file, not a directory. Use code_read to view it."
            )
        else:
            return f"Error: not a directory: {path}"
    lines = []
    for root, dirs, files in os.walk(path):
        level = root.replace(path, "").count(os.sep)
        if level >= depth:
            dirs.clear()
            continue
        indent = "  " * level
        lines.append(f"{indent}{os.path.basename(root)}/")
        subindent = "  " * (level + 1)
        for f in sorted(files)[:50]:
            lines.append(f"{subindent}{f}")
        dirs[:] = sorted(dirs)[:20]
    return "\n".join(lines[:200]) or "Empty directory"


async def _tool_memory_search(args: dict, ctx: ExecutionContext) -> str:
    """Search project + session memory (scoped to project_id — agents cannot cross-project)."""
    from ..memory.manager import get_memory_manager

    mem = get_memory_manager()
    query = args.get("query", "")
    try:
        results = []
        if ctx.project_id:
            # FTS search first
            results = mem.project_search(ctx.project_id, query, limit=8)
            # If FTS yields nothing, fallback to recent entries from project
            if not results:
                results = mem.project_get(ctx.project_id, limit=8)
        else:
            results = mem.global_search(query, limit=5)
        # Also search session pattern memory (what other agents decided in THIS session)
        if ctx.session_id:
            pattern_results = mem.pattern_search(ctx.session_id, query, limit=5)
            # Also get ALL recent pattern entries if search yielded nothing
            if not pattern_results:
                pattern_results = mem.pattern_get(ctx.session_id, limit=5)
            for r in pattern_results:
                if r.get("author_agent") != ctx.agent.id:  # skip self
                    results.append(
                        {
                            "key": r.get("key", ""),
                            "value": r.get("value", ""),
                            "category": f"session:{r.get('type', '')}",
                        }
                    )
        if not results:
            return "No memory entries found for this project yet."
        return "\n".join(
            f"[{r.get('category', r.get('key', ''))}] {r.get('key', '')}: {r.get('value', '')[:300]}"
            for r in results[:12]
        )
    except Exception as e:
        return f"Memory search error: {e}"


async def _tool_memory_store(args: dict, ctx: ExecutionContext) -> str:
    """Store a fact in project memory (scoped to project_id, tagged with agent_id)."""
    from ..memory.manager import get_memory_manager

    mem = get_memory_manager()
    key = args.get("key", "")
    value = args.get("value", "")
    category = args.get("category", "fact")
    if not key or not value:
        return "Error: key and value required"
    try:
        # ISOLATION: must have project_id, store with agent_id traceability
        if not ctx.project_id:
            return (
                "Error: no project context — cannot store memory without project scope"
            )
        mem.project_store(
            ctx.project_id, key, value, category=category, source=ctx.agent.id
        )
        return f"Stored in project memory: [{key}] (by {ctx.agent.id})"
    except Exception as e:
        return f"Memory store error: {e}"


async def _tool_deep_search(args: dict, ctx: ExecutionContext) -> str:
    """RLM: Deep recursive search (MIT CSAIL arXiv:2512.24601)."""
    from .rlm import get_project_rlm

    query = args.get("query", "")
    if not query:
        return "Error: query is required"
    if not ctx.project_id and not ctx.project_path:
        return "Error: no project context for RLM"

    print(f"[EXECUTOR] deep_search called: {query[:80]}", flush=True)
    rlm = get_project_rlm(
        ctx.project_id or "workspace", workspace_path=ctx.project_path
    )
    if not rlm:
        return f"Error: could not initialize RLM for project {ctx.project_id} (no path found)"

    max_iter = int(args.get("max_iterations", 3))

    # Forward progress to the tool_call callback
    async def rlm_progress(label: str):
        if ctx.on_tool_call:
            try:
                await ctx.on_tool_call("deep_search", {"status": label}, label)
            except Exception:
                pass

    result = await rlm.search(
        query=query,
        context=ctx.project_context or "",
        max_iterations=min(max_iter, 3),
        on_progress=rlm_progress,
    )

    print(
        f"[EXECUTOR] deep_search done: {result.iterations} iters, {result.total_queries} queries, {len(result.answer)} chars",
        flush=True,
    )
    header = f"RLM Deep Search ({result.iterations} iterations, {result.total_queries} queries)\n\n"
    return header + result.answer


# ── Phase orchestration tools (Mission Control) ──


async def _tool_run_phase(args: dict, ctx: ExecutionContext) -> str:
    """Run a mission phase via pattern engine."""
    from datetime import datetime

    from ..missions.store import get_mission_run_store
    from ..models import PhaseStatus
    from ..patterns.engine import run_pattern
    from ..patterns.store import get_pattern_store
    from ..workflows.store import get_workflow_store

    phase_id = args.get("phase_id", "")
    brief = args.get("brief", "")
    if not phase_id:
        return "Error: phase_id is required"

    run_store = get_mission_run_store()
    mission = run_store.get(ctx.mission_run_id) if ctx.mission_run_id else None
    if not mission:
        return "Error: no active mission. Start a mission first."

    # Find the phase
    phase_run = None
    for p in mission.phases:
        if p.phase_id == phase_id:
            phase_run = p
            break
    if not phase_run:
        return f"Error: phase '{phase_id}' not found in mission"

    if phase_run.status == PhaseStatus.RUNNING:
        return f"Phase '{phase_id}' is already running"

    # Get workflow to find phase config
    wf_store = get_workflow_store()
    workflow = wf_store.get(mission.workflow_id)
    if not workflow:
        return f"Error: workflow '{mission.workflow_id}' not found"

    wf_phase = None
    for wp in workflow.phases:
        if wp.id == phase_id:
            wf_phase = wp
            break
    if not wf_phase:
        return f"Error: phase '{phase_id}' not in workflow"

    # Build pattern from phase config
    pat_store = get_pattern_store()
    base_pattern = pat_store.get(wf_phase.pattern_id)
    if not base_pattern:
        return f"Error: pattern '{wf_phase.pattern_id}' not found"

    # Build agents list from phase config
    agent_ids = wf_phase.config.get("agents", [])
    agents = [
        {"id": f"ph-{i}", "agent_id": aid, "label": aid}
        for i, aid in enumerate(agent_ids)
    ]
    # Build edges based on pattern type
    edges = _build_phase_edges(base_pattern.type, agents)

    from ..patterns.store import PatternDef

    phase_pattern = PatternDef(
        id=f"mission-{mission.id}-{phase_id}",
        name=f"{wf_phase.name}",
        type=base_pattern.type,
        agents=agents,
        edges=edges,
        config=wf_phase.config,
    )

    # Update phase status
    phase_run.status = PhaseStatus.RUNNING
    phase_run.started_at = datetime.utcnow()
    phase_run.iteration += 1
    phase_run.agent_count = len(agent_ids)
    mission.current_phase = phase_id
    mission.status = "running"
    run_store.update(mission)

    # Push SSE event
    await _push_mission_sse(
        ctx.session_id,
        {
            "type": "phase_started",
            "mission_id": mission.id,
            "phase_id": phase_id,
            "phase_name": wf_phase.name,
            "pattern": base_pattern.type,
            "agents": agent_ids,
        },
    )

    try:
        print(
            f"[MISSION] Running phase '{phase_id}' ({base_pattern.type}) with {len(agent_ids)} agents",
            flush=True,
        )
        pattern_run = await run_pattern(
            phase_pattern,
            session_id=ctx.session_id,
            initial_task=brief,
            project_id=ctx.project_id or "",
        )

        # Gather results from node outputs
        summaries = []
        for nid, node in pattern_run.nodes.items():
            if node.output:
                agent_label = node.agent.name if node.agent else nid
                summaries.append(f"**{agent_label}**: {node.output[:500]}")

        phase_run.status = (
            PhaseStatus.DONE if pattern_run.success else PhaseStatus.FAILED
        )
        phase_run.completed_at = datetime.utcnow()
        phase_run.summary = "\n\n".join(summaries)[:3000]
        if not pattern_run.success:
            phase_run.error = "Phase ended with vetoes or failures"
        run_store.update(mission)

        await _push_mission_sse(
            ctx.session_id,
            {
                "type": "phase_completed" if pattern_run.success else "phase_failed",
                "mission_id": mission.id,
                "phase_id": phase_id,
                "success": pattern_run.success,
            },
        )

        status = "DONE" if pattern_run.success else "FAILED"
        return f"Phase '{wf_phase.name}' {status}\n\n{phase_run.summary[:2000]}"

    except Exception as e:
        phase_run.status = PhaseStatus.FAILED
        phase_run.error = str(e)
        run_store.update(mission)
        return f"Phase '{phase_id}' error: {e}"


async def _tool_get_phase_status(args: dict, ctx: ExecutionContext) -> str:
    """Get status of a specific phase."""
    from ..missions.store import get_mission_run_store

    phase_id = args.get("phase_id", "")
    run_store = get_mission_run_store()
    mission = run_store.get(ctx.mission_run_id) if ctx.mission_run_id else None
    if not mission:
        return "Error: no active mission"

    for p in mission.phases:
        if p.phase_id == phase_id:
            lines = [
                f"Phase: {p.phase_name} ({p.phase_id})",
                f"Status: {p.status.value}",
                f"Pattern: {p.pattern_id}",
                f"Agents: {p.agent_count}",
                f"Iteration: {p.iteration}",
            ]
            if p.summary:
                lines.append(f"Summary: {p.summary[:500]}")
            if p.error:
                lines.append(f"Error: {p.error}")
            return "\n".join(lines)
    return f"Phase '{phase_id}' not found"


async def _tool_list_phases(args: dict, ctx: ExecutionContext) -> str:
    """List all phases with status."""
    from ..missions.store import get_mission_run_store

    run_store = get_mission_run_store()
    mission = run_store.get(ctx.mission_run_id) if ctx.mission_run_id else None
    if not mission:
        return "Error: no active mission"

    lines = [f"Mission: {mission.workflow_name} ({mission.status.value})\n"]
    status_icons = {
        "pending": "·",
        "running": "~",
        "done": "✓",
        "failed": "✗",
        "skipped": "-",
        "waiting_validation": "?",
    }
    for i, p in enumerate(mission.phases, 1):
        icon = status_icons.get(p.status.value, "•")
        current = " ← CURRENT" if p.phase_id == mission.current_phase else ""
        lines.append(
            f"{i}. {icon} {p.phase_name} [{p.pattern_id}] — {p.status.value}{current}"
        )
    return "\n".join(lines)


async def _tool_request_validation(args: dict, ctx: ExecutionContext) -> str:
    """Request human validation — emit SSE checkpoint event."""
    from ..missions.store import get_mission_run_store
    from ..models import PhaseStatus
    from ..sessions.store import MessageDef, get_session_store

    question = args.get("question", "Proceed?")
    options = args.get("options", "GO,NOGO,PIVOT")

    run_store = get_mission_run_store()
    mission = run_store.get(ctx.mission_run_id) if ctx.mission_run_id else None

    # Update current phase to waiting
    if mission and mission.current_phase:
        for p in mission.phases:
            if p.phase_id == mission.current_phase:
                p.status = PhaseStatus.WAITING_VALIDATION
        run_store.update(mission)

    # Store as system message
    store = get_session_store()
    store.add_message(
        MessageDef(
            session_id=ctx.session_id,
            from_agent=ctx.agent.id,
            to_agent="human",
            message_type="system",
            content=f"**CHECKPOINT** — {question}\n\nOptions: {options}",
        )
    )

    # SSE event for Mission Control UI
    await _push_mission_sse(
        ctx.session_id,
        {
            "type": "checkpoint",
            "mission_id": mission.id if mission else "",
            "phase_id": mission.current_phase if mission else "",
            "question": question,
            "options": options.split(","),
            "requires_input": True,
        },
    )

    return f"CHECKPOINT: Waiting for human validation.\nQuestion: {question}\nOptions: {options}\n\n(The user will respond via Mission Control UI)"


async def _tool_get_project_context(args: dict, ctx: ExecutionContext) -> str:
    """Get project context for the CDP."""
    parts = []
    if ctx.vision:
        parts.append(f"## Vision\n{ctx.vision[:2000]}")
    if ctx.project_context:
        parts.append(f"## Project Context\n{ctx.project_context[:2000]}")
    if ctx.project_memory:
        parts.append(f"## Project Memory\n{ctx.project_memory[:1000]}")
    if not parts:
        return (
            "No project context available. This mission is running without a project."
        )
    return "\n\n".join(parts)


async def _tool_build_test(tool_name: str, args: dict, ctx: ExecutionContext) -> str:
    """Run build or test command in workspace."""
    command = args.get("command", "")
    if not command:
        return "Error: command is required"
    workspace = ctx.project_path
    if not workspace:
        return "Error: no workspace available"
    import os
    import subprocess

    # Intercept Android builds — redirect to android_build tool
    if any(
        kw in command
        for kw in ["gradlew", "gradle ", "assembleDebug", "assembleRelease"]
    ):
        return (
            "⚠️ WRONG TOOL: Do NOT use build() for Android/Gradle projects.\n"
            "Use android_build() instead — it runs in the android-builder container with real SDK.\n"
            "Generic build() has no Android SDK and will silently produce nothing."
        )

    # Fix swift command to use Apple Swift (not OpenStack CLI)
    if command.strip().startswith("swift ") and os.path.isfile("/usr/bin/swift"):
        command = "/usr/bin/" + command.strip()
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=120,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        status = (
            "SUCCESS" if proc.returncode == 0 else f"FAILED (exit {proc.returncode})"
        )
        return f"[{tool_name.upper()}] {status}\n$ {command}\n{out[-3000:]}"
    except subprocess.TimeoutExpired:
        return f"[{tool_name.upper()}] TIMEOUT after 120s: {command}"
    except Exception as exc:
        return f"[{tool_name.upper()}] ERROR: {exc}"


async def _tool_browser_screenshot(args: dict, ctx: ExecutionContext) -> str:
    """Take a real browser screenshot using Playwright."""
    from ..tools.build_tools import BrowserScreenshotTool

    if "cwd" not in args and ctx.project_path:
        import os

        if os.path.isdir(ctx.project_path):
            args["cwd"] = ctx.project_path
    try:
        tool = BrowserScreenshotTool()
        return await tool.execute(args)
    except Exception as e:
        return f"[browser_screenshot] ERROR: {e}"


# ── Playwright shortcut aliases (simple names for LLM compatibility) ──


async def _tool_browse(args: dict, ctx: ExecutionContext) -> str:
    """Navigate browser to a URL. Alias for mcp_playwright_browser_navigate."""
    return await _tool_mcp_dynamic(
        "mcp_playwright_browser_navigate", {"url": args.get("url", "")}, ctx
    )


async def _tool_take_screenshot(args: dict, ctx: ExecutionContext) -> str:
    """Take a PNG screenshot. Alias for mcp_playwright_browser_take_screenshot."""
    return await _tool_mcp_dynamic(
        "mcp_playwright_browser_take_screenshot",
        {
            "name": args.get("name", "screenshot"),
            "selector": args.get("selector", ""),
        },
        ctx,
    )


async def _tool_inspect_page(args: dict, ctx: ExecutionContext) -> str:
    """Get accessibility tree of current page. Alias for mcp_playwright_browser_snapshot."""
    return await _tool_mcp_dynamic("mcp_playwright_browser_snapshot", {}, ctx)


async def _tool_run_e2e_tests(args: dict, ctx: ExecutionContext) -> str:
    """Run full E2E test suite: start server, take screenshots, run tests."""
    import glob as glob_mod
    import os
    import subprocess
    import time

    workspace = ctx.project_path
    if not workspace:
        return "Error: no workspace"

    results = []

    # 1. Find app entry point
    pkg_files = glob_mod.glob(
        os.path.join(workspace, "**/package.json"), recursive=True
    )
    pkg_files = [p for p in pkg_files if "node_modules" not in p]

    # 2. Install + build
    for pkg in pkg_files[:2]:
        pkg_dir = os.path.dirname(pkg)
        label = os.path.basename(pkg_dir) or "root"
        try:
            proc = subprocess.run(
                "npm install --legacy-peer-deps 2>&1 | tail -3",
                shell=True,
                cwd=pkg_dir,
                capture_output=True,
                text=True,
                timeout=60,
            )
            results.append(
                f"[{label}] npm install: {'OK' if proc.returncode == 0 else 'FAIL'}"
            )
        except Exception as e:
            results.append(f"[{label}] npm install: {e}")

    # 3. Try starting dev server
    server_proc = None
    port = args.get("port", 3000)
    for pkg in pkg_files[:2]:
        pkg_dir = os.path.dirname(pkg)
        try:
            import json as json_mod

            with open(pkg) as f:
                pj = json_mod.load(f)
            scripts = pj.get("scripts", {})
            start_cmd = None
            if "dev" in scripts:
                start_cmd = f"npm run dev -- --port {port}"
            elif "start" in scripts:
                start_cmd = f"PORT={port} npm start"
            if start_cmd:
                server_proc = subprocess.Popen(
                    start_cmd,
                    shell=True,
                    cwd=pkg_dir,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                results.append(f"[server] Started: {start_cmd} (pid={server_proc.pid})")
                # Wait for server to be ready (up to 15s)
                import urllib.request

                ready = False
                for attempt in range(15):
                    time.sleep(1)
                    try:
                        urllib.request.urlopen(f"http://localhost:{port}", timeout=1)
                        ready = True
                        break
                    except Exception:
                        pass
                results.append(
                    f"[server] {'Ready' if ready else 'Not responding (continuing anyway)'} after {attempt + 1}s"
                )
                break
        except Exception:
            pass

    # 4. Take screenshots via MCP Playwright
    screenshots_taken = 0
    try:
        nav_result = await _tool_mcp_dynamic(
            "mcp_playwright_browser_navigate", {"url": f"http://localhost:{port}"}, ctx
        )
        results.append(f"[browse] {nav_result[:200]}")

        for name in ["homepage", "main-view"]:
            ss_result = await _tool_mcp_dynamic(
                "mcp_playwright_browser_take_screenshot", {"name": name}, ctx
            )
            results.append(f"[screenshot:{name}] {ss_result[:200]}")
            screenshots_taken += 1

        snap_result = await _tool_mcp_dynamic(
            "mcp_playwright_browser_snapshot", {}, ctx
        )
        results.append(f"[inspect] {snap_result[:500]}")
    except Exception as e:
        results.append(f"[playwright] Error: {e}")

    # 5. Run unit tests
    for pkg in pkg_files[:2]:
        pkg_dir = os.path.dirname(pkg)
        label = os.path.basename(pkg_dir) or "root"
        try:
            proc = subprocess.run(
                "npm test -- --watchAll=false 2>&1 | tail -20",
                shell=True,
                cwd=pkg_dir,
                capture_output=True,
                text=True,
                timeout=60,
            )
            status = "PASS" if proc.returncode == 0 else "FAIL"
            results.append(f"[test:{label}] {status}\n{proc.stdout[-500:]}")
        except subprocess.TimeoutExpired:
            results.append(f"[test:{label}] TIMEOUT")
        except Exception as e:
            results.append(f"[test:{label}] Error: {e}")

    # 6. Cleanup server
    if server_proc:
        try:
            server_proc.terminate()
            server_proc.wait(timeout=5)
        except Exception:
            pass

    results.append(
        f"\n📊 Summary: {screenshots_taken} screenshots taken, {len(pkg_files)} packages found"
    )
    return "\n".join(results)


async def _tool_security_chaos(name: str, args: dict, ctx: ExecutionContext) -> str:
    """Dispatch security/chaos/TMC/infra tools to their BaseTool implementations."""
    from ..tools.chaos_tools import ChaosTestTool, InfraCheckTool, TmcLoadTestTool
    from ..tools.security_tools import (
        DependencyAuditTool,
        SastScanTool,
        SecretsScanTool,
    )

    _MAP = {
        "sast_scan": SastScanTool,
        "dependency_audit": DependencyAuditTool,
        "secrets_scan": SecretsScanTool,
        "chaos_test": ChaosTestTool,
        "tmc_load_test": TmcLoadTestTool,
        "infra_check": InfraCheckTool,
    }
    cls = _MAP.get(name)
    if not cls:
        return f"Error: unknown security tool '{name}'"
    # Inject workspace cwd from context if not provided — validate path exists
    if "cwd" not in args and ctx.workspace_path:
        import os

        if os.path.isdir(ctx.workspace_path):
            args["cwd"] = ctx.workspace_path
    try:
        tool = cls()
        return await tool.execute(args)
    except Exception as e:
        return f"[{name}] ERROR: {e}"


async def _tool_platform_backlog(name: str, args: dict, ctx: ExecutionContext) -> str:
    """Delegate create_feature/create_story to platform_tools registry."""
    from ..tools.platform_tools import (
        PlatformCreateFeatureTool,
        PlatformCreateStoryTool,
    )

    tool = (
        PlatformCreateFeatureTool()
        if name == "create_feature"
        else PlatformCreateStoryTool()
    )
    return await tool.execute(args, ctx.agent)


async def _tool_create_ticket(args: dict, ctx: ExecutionContext) -> str:
    """Create a support ticket in the platform DB."""
    import uuid

    from ..db import get_db

    title = args.get("title", "")
    desc = args.get("description", "")
    severity = args.get("severity", "medium")
    category = args.get("category", "bug")
    if not title:
        return "Error: ticket title required"
    tid = str(uuid.uuid4())[:8]
    agent_id = ctx.agent.id if ctx.agent else "unknown"
    mission_id = getattr(ctx, "mission_run_id", "") or ""
    try:
        db = get_db()
        db.execute(
            "INSERT INTO support_tickets (id, mission_id, title, description, severity, category, reporter, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'open')",
            (tid, mission_id, title, desc, severity, category, agent_id),
        )
        db.commit()
        db.close()
        return f"Ticket {tid} created: [{severity}] {title}"
    except Exception as e:
        return f"Error creating ticket: {e}"


async def _tool_local_ci(args: dict, ctx: ExecutionContext) -> str:
    """Run local CI pipeline: install → build → lint → test → commit."""
    import os
    import subprocess

    cwd = args.get("cwd", ctx.project_path or ".")
    steps = args.get("steps", ["install", "build", "lint", "test", "commit"])
    commit_msg = args.get("commit_message", "ci: automated build pass")
    results = []

    # Auto-detect stack
    has_pkg = os.path.isfile(os.path.join(cwd, "package.json"))
    has_req = os.path.isfile(os.path.join(cwd, "requirements.txt"))
    has_cargo = os.path.isfile(os.path.join(cwd, "Cargo.toml"))

    cmds = {}
    if has_pkg:
        cmds = {
            "install": "npm install",
            "build": "npm run build",
            "lint": "npm run lint",
            "test": "npm test",
        }
    elif has_req:
        cmds = {
            "install": "pip install -r requirements.txt",
            "build": "python -m py_compile *.py",
            "lint": "python -m flake8 . --max-line-length=120 --count",
            "test": "python -m pytest -v",
        }
    elif has_cargo:
        cmds = {
            "install": "cargo fetch",
            "build": "cargo build",
            "lint": "cargo clippy -- -D warnings",
            "test": "cargo test",
        }
    else:
        return "Error: no package.json, requirements.txt, or Cargo.toml found — cannot detect stack"

    for step in steps:
        if step == "commit":
            try:
                subprocess.run(
                    ["git", "add", "-A"], cwd=cwd, timeout=10, capture_output=True
                )
                r = subprocess.run(
                    ["git", "commit", "-m", commit_msg],
                    cwd=cwd,
                    timeout=30,
                    capture_output=True,
                    text=True,
                )
                results.append(
                    f"[commit] {'OK' if r.returncode == 0 else 'SKIP (nothing to commit)'}"
                )
            except Exception as e:
                results.append(f"[commit] ERROR: {e}")
            continue

        cmd = cmds.get(step)
        if not cmd:
            results.append(f"[{step}] SKIP (unknown step)")
            continue
        try:
            r = subprocess.run(
                cmd, shell=True, cwd=cwd, timeout=300, capture_output=True, text=True
            )
            status = "OK" if r.returncode == 0 else f"FAIL (exit {r.returncode})"
            output = (
                r.stdout[-500:]
                if r.returncode == 0
                else (r.stderr[-500:] or r.stdout[-500:])
            ).strip()
            results.append(
                f"[{step}] {status}\n{output}" if output else f"[{step}] {status}"
            )
            if r.returncode != 0 and step in ("build", "test"):
                results.append(f"⛔ Pipeline stopped at '{step}'")
                break
        except subprocess.TimeoutExpired:
            results.append(f"[{step}] TIMEOUT (300s)")
            break
        except Exception as e:
            results.append(f"[{step}] ERROR: {e}")

    return "\n".join(results)


async def _tool_si_blueprint(args: dict, ctx: ExecutionContext) -> str:
    """Read the SI blueprint for a project."""
    import yaml

    project_id = args.get("project_id", "")
    if not project_id and ctx.project_id:
        project_id = ctx.project_id

    bp_path = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "si_blueprints"
        / f"{project_id}.yaml"
    )
    if not bp_path.exists():
        return (
            f"No SI blueprint found for project '{project_id}'. "
            f"Create one at {bp_path} with: cloud, compute, cicd, databases, "
            f"monitoring, existing_services, conventions."
        )
    try:
        with open(bp_path) as f:
            bp = yaml.safe_load(f)
        return f"[SI Blueprint] {project_id}:\n{yaml.dump(bp, default_flow_style=False, allow_unicode=True)}"
    except Exception as e:
        return f"[SI Blueprint] Error reading: {e}"


async def _tool_compose(name: str, args: dict, ctx: ExecutionContext) -> str:
    """Execute composition tools via the registry."""
    from ..models import AgentInstance

    registry = _get_tool_registry()
    tool = registry.get(name)
    if not tool:
        return f"Error: composition tool '{name}' not found"
    agent_inst = (
        AgentInstance(id=ctx.agent.id, name=ctx.agent.name, role=ctx.agent.role)
        if ctx.agent
        else None
    )
    return await tool.execute(args, agent_inst)


async def _tool_android(name: str, args: dict, ctx: ExecutionContext) -> str:
    """Execute Android build/test tools via docker exec."""
    reg = _get_tool_registry()
    tool = reg.get(name)
    if not tool:
        return f"Error: android tool '{name}' not found"
    # Set workspace path from mission context if not provided
    if not args.get("workspace_path") and ctx.project_path:
        args["workspace_path"] = (
            f"/workspace/workspaces/{ctx.project_path.split('/')[-1]}"
        )
    return await tool.execute(args)


async def _tool_fractal_code(args: dict, ctx: ExecutionContext, registry, llm) -> str:
    """Spawn a focused sub-agent LLM to complete an atomic coding task.

    The sub-agent runs autonomously with code tools for up to 8 rounds.
    Like wiggum TDD from the Software Factory: write code → write tests → run → fix.
    """
    from ..llm.client import LLMMessage, LLMResponse
    from .tool_schemas import _filter_schemas, _get_tool_schemas

    task = args.get("task", "")
    extra_context = args.get("context", "")
    if not task:
        return "Error: task description required"
    if not ctx.project_path:
        return "Error: no project workspace available"

    # Build a focused system prompt for the sub-agent
    project_path = ctx.project_path
    sub_system = f"""You are a focused coding sub-agent. Your ONLY job is to complete this atomic task by writing real code files.

WORKSPACE: {project_path}
RULES:
- Write REAL code using code_write tool. Every file must be complete and runnable.
- Write tests for every module you create.
- After writing, use code_read to verify files were written correctly.
- Use list_files to understand existing project structure BEFORE writing.
- If a test tool is available, run tests to verify your code works.
- Be surgical: modify only what's needed, don't overwrite unrelated files.
- Use git_commit to commit your work when done.

{f"CONTEXT: {extra_context}" if extra_context else ""}"""

    # Sub-agent tools: file ops + git + build/test
    sub_tools = _filter_schemas(
        _get_tool_schemas(),
        [
            "code_read",
            "code_write",
            "code_edit",
            "code_search",
            "list_files",
            "git_status",
            "git_diff",
            "git_commit",
            "build",
            "test",
        ],
    )

    messages = [LLMMessage(role="user", content=task)]
    files_changed = []
    MAX_SUB_ROUNDS = 8

    for rnd in range(MAX_SUB_ROUNDS):
        try:
            llm_resp = await llm.chat(
                messages=messages,
                provider=ctx.agent.provider,
                model=ctx.agent.model,
                temperature=0.3,  # more deterministic for coding
                max_tokens=ctx.agent.max_tokens,
                system_prompt=sub_system if rnd == 0 else "",
                tools=sub_tools,
            )
        except Exception as exc:
            logger.error("Fractal sub-agent LLM error round %d: %s", rnd, exc)
            break

        # Check for XML tool calls fallback
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

        # No tool calls → sub-agent is done
        if not llm_resp.tool_calls:
            break

        # Execute tool calls
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
                role="assistant", content=llm_resp.content or "", tool_calls=tc_msg_data
            )
        )

        for tc in llm_resp.tool_calls:
            result = await _execute_tool(tc, ctx, registry, llm)
            messages.append(
                LLMMessage(
                    role="tool",
                    content=result[:4000],
                    tool_call_id=tc.id,
                    name=tc.function_name,
                )
            )
            # Track file changes
            if tc.function_name in ("code_write", "code_edit"):
                path = tc.arguments.get("path", "?")
                if ctx.project_path and path.startswith(ctx.project_path):
                    path = path[len(ctx.project_path) :].lstrip("/")
                files_changed.append(f"{tc.function_name}: {path}")
            elif tc.function_name == "git_commit":
                files_changed.append(
                    f"committed: {tc.arguments.get('message', '?')[:60]}"
                )

            logger.warning(
                "FRACTAL sub-agent round=%d tool=%s path=%s",
                rnd,
                tc.function_name,
                tc.arguments.get("path", "?")[:60],
            )

        # Emit progress SSE
        if ctx.on_tool_call:
            try:
                await ctx.on_tool_call(
                    "fractal_code",
                    {"round": rnd, "tools": len(llm_resp.tool_calls)},
                    f"Sub-agent round {rnd + 1}: {len(llm_resp.tool_calls)} tool calls",
                )
            except Exception:
                pass

    # Build summary
    summary_parts = ["## Fractal Sub-Agent Result", f"**Task:** {task[:200]}"]
    if files_changed:
        summary_parts.append(f"**Changes ({len(files_changed)}):**")
        for fc in files_changed[:20]:
            summary_parts.append(f"- {fc}")
    else:
        summary_parts.append("*No file changes recorded*")
    # Get final LLM summary
    if llm_resp and llm_resp.content:
        summary_parts.append(f"\n**Summary:** {llm_resp.content[:500]}")

    return "\n".join(summary_parts)
    """Push a mission control SSE event via the A2A bus SSE listeners."""
    from ..a2a.bus import get_bus

    data["session_id"] = session_id
    bus = get_bus()
    dead = []
    for q in bus._sse_listeners:
        try:
            q.put_nowait(data)
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        bus._sse_listeners.remove(q)


# ── MCP Tool Handlers ─────────────────────────────────────────


async def _tool_mcp_lrm(name: str, args: dict, ctx: ExecutionContext) -> str:
    """Proxy to unified MCP SF server (localhost:9501, merged LRM+Platform)."""
    import aiohttp

    tool_name = name.replace("lrm_", "")
    if ctx.project_id:
        args.setdefault("project", ctx.project_id)
    try:
        async with (
            aiohttp.ClientSession() as session,
            session.post(
                "http://localhost:9501/tool",
                json={"name": tool_name, "arguments": args},
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp,
        ):
            if resp.status == 200:
                data = await resp.json()
                return str(data.get("result", data))[:8000]
            return f"LRM error {resp.status}"
    except Exception as e:
        return f"LRM server unavailable: {e}"


async def _tool_mcp_figma(name: str, args: dict, ctx: ExecutionContext) -> str:
    """Proxy to Figma MCP (desktop or remote)."""
    import aiohttp

    endpoints = ["http://127.0.0.1:3845/mcp", "https://mcp.figma.com/mcp"]
    tool_name = name.replace("figma_", "")
    payload = {"method": tool_name, "params": args}
    for endpoint in endpoints:
        try:
            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    endpoint,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp,
            ):
                if resp.status == 200:
                    data = await resp.json()
                    return str(data.get("result", data))[:8000]
        except Exception:
            continue
    return "Figma MCP unavailable (desktop + remote)"


async def _tool_mcp_solaris(name: str, args: dict, ctx: ExecutionContext) -> str:
    """Route to Solaris MCP server via MCPManager (stdio subprocess)."""
    from ..mcps.manager import get_mcp_manager

    mgr = get_mcp_manager()
    mcp_id = "mcp-solaris"

    # Auto-start if not running
    if mcp_id not in mgr.get_running_ids():
        ok, msg = await mgr.start(mcp_id)
        if not ok:
            return f"Solaris MCP failed to start: {msg}"

    result = await mgr.call_tool(mcp_id, name, args, timeout=30)
    return str(result)[:8000]


async def _tool_mcp_github(name: str, args: dict, ctx: ExecutionContext) -> str:
    """Execute GitHub operations via gh CLI."""
    import asyncio as _aio

    owner = args.get("owner", "")
    repo = args.get("repo", "")
    try:
        if name == "github_issues":
            state = args.get("state", "open")
            query = args.get("query", "")
            cmd = f"gh issue list --repo {owner}/{repo} --state {state} --limit 20"
            if query:
                cmd += f" --search '{query}'"
            proc = await _aio.create_subprocess_shell(
                cmd, stdout=_aio.subprocess.PIPE, stderr=_aio.subprocess.PIPE
            )
            out, err = await proc.communicate()
            return (out or err).decode()[:6000]
        if name == "github_prs":
            state = args.get("state", "open")
            cmd = f"gh pr list --repo {owner}/{repo} --state {state} --limit 20"
            proc = await _aio.create_subprocess_shell(
                cmd, stdout=_aio.subprocess.PIPE, stderr=_aio.subprocess.PIPE
            )
            out, err = await proc.communicate()
            return (out or err).decode()[:6000]
        if name == "github_code_search":
            query = args.get("query", "")
            cmd = f"gh search code '{query}' --limit 20"
            proc = await _aio.create_subprocess_shell(
                cmd, stdout=_aio.subprocess.PIPE, stderr=_aio.subprocess.PIPE
            )
            out, err = await proc.communicate()
            return (out or err).decode()[:6000]
        if name == "github_actions":
            cmd = f"gh run list --repo {owner}/{repo} --limit 10"
            status = args.get("status")
            if status:
                cmd += f" --status {status}"
            proc = await _aio.create_subprocess_shell(
                cmd, stdout=_aio.subprocess.PIPE, stderr=_aio.subprocess.PIPE
            )
            out, err = await proc.communicate()
            return (out or err).decode()[:6000]
    except Exception as e:
        return f"GitHub CLI error: {e}"
    return f"Unknown GitHub tool: {name}"


async def _tool_mcp_jira(name: str, args: dict, ctx: ExecutionContext) -> str:
    """JIRA/Confluence integration (needs ATLASSIAN_TOKEN env var)."""
    import os

    token = os.environ.get("ATLASSIAN_TOKEN")
    base_url = os.environ.get("ATLASSIAN_URL", "")
    if not token or not base_url:
        return "JIRA/Confluence not configured. Set ATLASSIAN_TOKEN and ATLASSIAN_URL env vars."
    import aiohttp

    headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json"}
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            if name == "jira_search":
                jql = args.get("jql", "")
                max_r = args.get("max_results", 10)
                async with session.get(
                    f"{base_url}/rest/api/3/search?jql={jql}&maxResults={max_r}",
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    data = await resp.json()
                    issues = data.get("issues", [])
                    return (
                        "\n".join(
                            f"[{i['key']}] {i['fields'].get('summary', '')} ({i['fields'].get('status', {}).get('name', '')})"
                            for i in issues
                        )
                        or "No issues found."
                    )
            if name == "jira_create":
                payload = {
                    "fields": {
                        "project": {"key": args["project"]},
                        "summary": args["summary"],
                        "issuetype": {"name": args["type"]},
                        "description": {
                            "type": "doc",
                            "version": 1,
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": args.get("description", ""),
                                        }
                                    ],
                                }
                            ],
                        },
                    }
                }
                async with session.post(
                    f"{base_url}/rest/api/3/issue",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    data = await resp.json()
                    return f"Created: {data.get('key', 'unknown')} — {data.get('self', '')}"
            if name == "confluence_read":
                title = args.get("title", "")
                space = args.get("space", "")
                page_id = args.get("page_id", "")
                if page_id:
                    url = f"{base_url}/wiki/rest/api/content/{page_id}?expand=body.storage"
                else:
                    url = f"{base_url}/wiki/rest/api/content?title={title}&spaceKey={space}&expand=body.storage"
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    data = await resp.json()
                    if "results" in data:
                        pages = data["results"]
                    else:
                        pages = [data]
                    parts = []
                    for p in pages[:3]:
                        parts.append(
                            f"# {p.get('title', '')}\n{p.get('body', {}).get('storage', {}).get('value', '')[:3000]}"
                        )
                    return "\n\n".join(parts) or "No page found."
    except Exception as e:
        return f"JIRA/Confluence error: {e}"
    return f"Unknown JIRA tool: {name}"


async def _tool_mcp_dynamic(name: str, args: dict, ctx: ExecutionContext) -> str:
    """Route tool calls to running MCP servers. Format: mcp_<server>_<tool>."""
    from ..mcps.manager import get_mcp_manager

    manager = get_mcp_manager()

    # Parse: mcp_fetch_fetch, mcp_memory_search_nodes, mcp_playwright_browser_navigate
    parts = name.split("_", 2)  # ['mcp', 'server', 'tool_name']
    if len(parts) < 3:
        return f"Invalid MCP tool format: {name}. Use mcp_<server>_<tool>"

    # Map short names to MCP IDs
    server_short = parts[1]
    tool_name = parts[2]
    mcp_id_map = {
        "fetch": "mcp-fetch",
        "memory": "mcp-memory",
        "playwright": "mcp-playwright",
        "github": "mcp-github",
    }
    mcp_id = mcp_id_map.get(server_short, f"mcp-{server_short}")

    # Auto-start if not running
    if mcp_id not in manager.get_running_ids():
        ok, msg = await manager.start(mcp_id)
        if not ok:
            return f"Failed to start MCP {mcp_id}: {msg}"

    timeout = 60 if server_short == "playwright" else 30
    result = await manager.call_tool(mcp_id, tool_name, args, timeout=timeout)
    return result[:8000] if result else "No response from MCP"


# ── Main tool dispatcher ─────────────────────────────────────────


async def _execute_tool(
    tc: LLMToolCall, ctx: ExecutionContext, registry, llm=None
) -> str:
    """Execute a single tool call and return string result."""
    name = tc.function_name
    args = dict(tc.arguments)

    # ── Resolve paths: project_path is the default for all file/git tools ──
    if ctx.project_path:
        # Git/build/deploy/test tools: inject cwd
        if name in (
            "git_status",
            "git_log",
            "git_diff",
            "git_commit",
            "build",
            "test",
            "lint",
            "docker_build",
            "docker_deploy",
            "screenshot",
            "playwright_test",
            "browser_screenshot",
        ):
            cwd_val = args.get("cwd", "")
            if not cwd_val or cwd_val in (".", "./"):
                args["cwd"] = ctx.project_path
            elif not os.path.isabs(cwd_val):
                # Agent may pass workspace ID or relative path — resolve to project_path
                ws_id = os.path.basename(ctx.project_path)
                if cwd_val == ws_id or cwd_val == ws_id + "/":
                    args["cwd"] = ctx.project_path
                else:
                    args["cwd"] = os.path.join(ctx.project_path, cwd_val)
        # File tools: resolve relative paths to project root
        if name in (
            "code_read",
            "code_search",
            "code_write",
            "code_edit",
            "list_files",
        ):
            path = args.get("path", "")
            if not path or path == ".":
                args["path"] = ctx.project_path
            elif os.path.isabs(path) and ctx.project_path:
                # Agent used absolute path — normalize to workspace-relative
                # e.g. /app/data/workspaces/abc123/src/main.ts → src/main.ts
                if path.startswith(ctx.project_path + "/"):
                    path = path[len(ctx.project_path) + 1 :]
                    args["path"] = os.path.join(ctx.project_path, path)
                elif path.startswith(ctx.project_path):
                    args["path"] = ctx.project_path
                else:
                    args["path"] = path  # truly external absolute path
            elif not os.path.isabs(path):
                # Strip workspace ID prefix if LLM included it (avoids path doubling)
                if ctx.project_path:
                    ws_id = os.path.basename(ctx.project_path)
                    if path.startswith(ws_id + "/"):
                        path = path[len(ws_id) + 1 :]
                    # Strip project_path prefix if LLM used it as relative
                    elif path.startswith("." + ctx.project_path):
                        path = path[1:]  # remove leading dot, keep absolute
                args["path"] = (
                    os.path.join(ctx.project_path, path)
                    if not os.path.isabs(path)
                    else path
                )

    # ── Permission enforcement ──
    try:
        from .permissions import get_permission_guard

        perms_dict = None
        if hasattr(ctx.agent, "permissions"):
            p = ctx.agent.permissions
            perms_dict = (
                p
                if isinstance(p, dict)
                else (p.model_dump() if hasattr(p, "model_dump") else {})
            )
        denied = get_permission_guard().check(
            agent_id=ctx.agent.id,
            tool_name=name,
            args=args,
            allowed_tools=ctx.allowed_tools,
            project_path=ctx.project_path or "",
            permissions=perms_dict,
            session_id=ctx.session_id,
        )
        if denied:
            return denied
    except Exception as e:
        logger.debug("Permission check skipped: %s", e)

    # Handle built-in tools that don't go through registry
    if name == "list_files":
        return await _tool_list_files(args)
    if name == "memory_search":
        return await _tool_memory_search(args, ctx)
    if name == "memory_store":
        return await _tool_memory_store(args, ctx)
    if name == "deep_search":
        return await _tool_deep_search(args, ctx)
    # Phase orchestration tools (mission control)
    if name == "run_phase":
        return await _tool_run_phase(args, ctx)
    if name == "get_phase_status":
        return await _tool_get_phase_status(args, ctx)
    if name == "list_phases":
        return await _tool_list_phases(args, ctx)
    if name == "request_validation":
        return await _tool_request_validation(args, ctx)
    if name == "get_project_context":
        return await _tool_get_project_context(args, ctx)
    if name == "fractal_code":
        return await _tool_fractal_code(args, ctx, registry, llm)
    if name in ("build", "test"):
        return await _tool_build_test(name, args, ctx)
    if name == "browser_screenshot":
        return await _tool_browser_screenshot(args, ctx)

    # ── Playwright shortcut aliases ──
    if name == "browse":
        return await _tool_browse(args, ctx)
    if name == "take_screenshot":
        return await _tool_take_screenshot(args, ctx)
    if name == "inspect_page":
        return await _tool_inspect_page(args, ctx)
    if name == "run_e2e_tests":
        return await _tool_run_e2e_tests(args, ctx)

    # ── Security & chaos tools ──
    if name in (
        "sast_scan",
        "dependency_audit",
        "secrets_scan",
        "chaos_test",
        "tmc_load_test",
        "infra_check",
    ):
        return await _tool_security_chaos(name, args, ctx)

    # ── Ticket/Incident management ──
    if name == "create_ticket":
        return await _tool_create_ticket(args, ctx)

    # ── Backlog tools (create_feature, create_story) — handled by platform_tools registry ──
    if name in ("create_feature", "create_story"):
        return await _tool_platform_backlog(name, args, ctx)

    # ── Local CI pipeline ──
    if name == "local_ci":
        return await _tool_local_ci(args, ctx)

    if name == "get_si_blueprint":
        return await _tool_si_blueprint(args, ctx)

    # ── Composition tools (dynamic workflow/team/mission) ──
    if name in (
        "compose_workflow",
        "create_team",
        "create_sub_mission",
        "list_sub_missions",
        "set_constraints",
    ):
        return await _tool_compose(name, args, ctx)

    # ── Android build tools (docker exec android-builder) ──
    if name.startswith("android_"):
        return await _tool_android(name, args, ctx)

    # ── MCP tools: proxy to external servers ──
    if name.startswith("lrm_"):
        return await _tool_mcp_lrm(name, args, ctx)
    if name.startswith("figma_"):
        return await _tool_mcp_figma(name, args, ctx)
    if name.startswith("solaris_"):
        return await _tool_mcp_solaris(name, args, ctx)
    if name.startswith("github_"):
        return await _tool_mcp_github(name, args, ctx)
    if name.startswith("jira_"):
        from ..tools.jira_tools import run_jira_tool

        return await run_jira_tool(name, args)
    if name == "confluence_read":
        return await _tool_mcp_jira(name, args, ctx)

    # ── Dynamic MCP tools (mcp_<server-id>_<tool>) ──
    if name.startswith("mcp_"):
        return await _tool_mcp_dynamic(name, args, ctx)

    # Registry tools
    # Inject agent context for git branch isolation
    if name == "git_commit":
        args["_agent_id"] = ctx.agent.id
        args["_session_id"] = ctx.session_id or ""
    tool = registry.get(name)
    if not tool:
        return f"Error: unknown tool '{name}'"

    try:
        return await tool.execute(args)
    except Exception as e:
        return f"Tool '{name}' error: {e}"
