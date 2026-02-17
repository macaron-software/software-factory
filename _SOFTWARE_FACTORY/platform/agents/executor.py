"""Agent Executor — runs an agent: receive message → think (LLM) → act → respond.

This is the runtime loop that makes agents actually work. It:
1. Builds the prompt (system + skills + memory + conversation)
2. Calls the LLM with tools definitions
3. If LLM returns tool_calls → execute tools → feed results back → repeat
4. When LLM returns text (no tool_calls) → done
5. Sends response back via MessageBus or returns it
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Optional

from ..llm.client import LLMClient, LLMMessage, LLMResponse, LLMToolCall, get_llm_client
from ..agents.store import AgentDef

logger = logging.getLogger(__name__)

# Max tool-calling rounds to prevent infinite loops
MAX_TOOL_ROUNDS = 15

# Regex to strip raw MiniMax/internal tool-call tokens from LLM output
_RAW_TOKEN_RE = re.compile(
    r'<\|(?:tool_calls_section_begin|tool_calls_section_end|tool_call_begin|tool_call_end|'
    r'tool_call_argument_begin|tool_call_argument_end|tool_sep|im_end|im_start)\|>'
)

def _strip_raw_tokens(text: str) -> str:
    """Remove raw model tokens that leak into content (e.g. MiniMax format)."""
    if '<|' not in text:
        return text
    cleaned = _RAW_TOKEN_RE.sub('', text)
    # Also remove raw function call lines like "functions.code_read:0"
    cleaned = re.sub(r'^functions\.\w+:\d+$', '', cleaned, flags=re.MULTILINE)
    return cleaned.strip()


def _get_tool_registry():
    """Lazy import to avoid circular imports."""
    from ..tools.registry import ToolRegistry
    from ..tools.code_tools import register_code_tools
    from ..tools.git_tools import register_git_tools
    from ..tools.build_tools import register_build_tools
    reg = ToolRegistry()
    register_code_tools(reg)
    register_git_tools(reg)
    register_build_tools(reg)
    try:
        from ..tools.mcp_bridge import register_mcp_tools
        register_mcp_tools(reg)
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
    return reg


# Tool JSON schemas for OpenAI function-calling API
_TOOL_SCHEMAS: Optional[list[dict]] = None


def _get_tool_schemas() -> list[dict]:
    """Build OpenAI-compatible tool definitions from the registry."""
    global _TOOL_SCHEMAS
    if _TOOL_SCHEMAS is not None:
        return _TOOL_SCHEMAS

    schemas = [
        {
            "type": "function",
            "function": {
                "name": "code_read",
                "description": "Read the contents of a file. Use this to explore project files.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Absolute or relative file path"},
                        "max_lines": {"type": "integer", "description": "Max lines to read (default 500)"},
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "code_search",
                "description": "Search for a pattern in project files using ripgrep.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string", "description": "Regex pattern to search for"},
                        "path": {"type": "string", "description": "Directory to search in (default: project root)"},
                        "glob": {"type": "string", "description": "File glob filter, e.g. '*.py'"},
                    },
                    "required": ["pattern"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "code_write",
                "description": "Write content to a file (creates backup of existing).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path to write"},
                        "content": {"type": "string", "description": "Content to write"},
                    },
                    "required": ["path", "content"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "code_edit",
                "description": "Replace a specific string in a file (surgical edit).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path"},
                        "old_str": {"type": "string", "description": "Exact string to find and replace"},
                        "new_str": {"type": "string", "description": "Replacement string"},
                    },
                    "required": ["path", "old_str", "new_str"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "git_status",
                "description": "Show git status of the project.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cwd": {"type": "string", "description": "Working directory (default: project root)"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "git_log",
                "description": "Show recent git commits.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cwd": {"type": "string", "description": "Working directory"},
                        "limit": {"type": "integer", "description": "Number of commits (default 10)"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "git_diff",
                "description": "Show git diff of changes.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cwd": {"type": "string", "description": "Working directory"},
                        "path": {"type": "string", "description": "Specific file to diff"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "memory_search",
                "description": "Search project memory for stored knowledge, facts, and context.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "scope": {"type": "string", "description": "Memory scope: project | global", "enum": ["project", "global"]},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "memory_store",
                "description": "Store a fact or learning in project memory for future reference.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "Short key/title for the memory"},
                        "value": {"type": "string", "description": "Content to store"},
                        "category": {"type": "string", "description": "Category: decision | fact | learning | context"},
                    },
                    "required": ["key", "value"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files and directories at a given path.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path to list"},
                        "depth": {"type": "integer", "description": "Max depth (default 2)"},
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "deep_search",
                "description": "RLM Deep Search (MIT CSAIL arXiv:2512.24601). Recursive Language Model that iteratively explores the entire project codebase using a WRITE-EXECUTE-OBSERVE-DECIDE loop with parallel sub-agents. Use for complex questions like 'how does authentication work', 'find all API routes and their guards', 'explain the database schema'. Returns a comprehensive, factual analysis.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The question or exploration goal — e.g. 'how is authentication implemented', 'find all REST endpoints', 'explain the data model'"},
                        "max_iterations": {"type": "integer", "description": "Max RLM iterations (default 3, max 3). Higher = deeper but slower."},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "docker_build",
                "description": "Build a Docker image from a project directory containing a Dockerfile.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cwd": {"type": "string", "description": "Project directory containing the Dockerfile"},
                        "image_name": {"type": "string", "description": "Name for the Docker image (e.g. 'macaron-iot-dashboard')"},
                    },
                    "required": ["cwd", "image_name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "deploy_azure",
                "description": "Deploy a Docker image to the Azure VM (4.233.64.30). Saves the image, transfers via SCP, loads and runs on the VM. Returns the public URL.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "image_name": {"type": "string", "description": "Docker image name to deploy (must be built first)"},
                        "container_port": {"type": "integer", "description": "Port the app listens on inside the container (e.g. 8080)"},
                        "host_port": {"type": "integer", "description": "Port to expose on the VM (0 = auto-assign)"},
                    },
                    "required": ["image_name", "container_port"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "git_commit",
                "description": "Stage all changes and commit to git.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cwd": {"type": "string", "description": "Working directory"},
                        "message": {"type": "string", "description": "Commit message"},
                    },
                    "required": ["message"],
                },
            },
        },
    ]
    _TOOL_SCHEMAS = schemas
    return schemas


@dataclass
class ExecutionContext:
    """Everything an agent needs to process a message."""
    agent: AgentDef
    session_id: str
    project_id: Optional[str] = None
    project_path: Optional[str] = None  # filesystem path for tools
    # Conversation history (recent messages for context window)
    history: list[dict] = field(default_factory=list)
    # Project memory snippets
    project_context: str = ""
    # Project memory files (CLAUDE.md, copilot-instructions.md, etc.)
    project_memory: str = ""
    # Skills content (injected into system prompt)
    skills_prompt: str = ""
    # Vision document (if project has one)
    vision: str = ""
    # Enable tool-calling (default True)
    tools_enabled: bool = True
    # Callback for SSE tool events
    on_tool_call: Optional[object] = None  # async callable(tool_name, args, result)


@dataclass
class ExecutionResult:
    """Result of running an agent on a message."""
    content: str
    agent_id: str
    model: str = ""
    provider: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: int = 0
    tool_calls: list[dict] = field(default_factory=list)
    delegations: list[dict] = field(default_factory=list)
    error: Optional[str] = None


class AgentExecutor:
    """Executes agent logic: prompt → LLM → tool loop → response."""

    def __init__(self, llm: Optional[LLMClient] = None):
        self._llm = llm or get_llm_client()
        self._registry = _get_tool_registry()

    async def run(self, ctx: ExecutionContext, user_message: str) -> ExecutionResult:
        """Run the agent with tool-calling loop."""
        t0 = time.monotonic()
        agent = ctx.agent
        total_tokens_in = 0
        total_tokens_out = 0
        all_tool_calls = []

        try:
            system = self._build_system_prompt(ctx)
            messages = self._build_messages(ctx, user_message)
            tools = _get_tool_schemas() if ctx.tools_enabled else None

            # Tool-calling loop
            deep_search_used = False
            for round_num in range(MAX_TOOL_ROUNDS):
                llm_resp = await self._llm.chat(
                    messages=messages,
                    provider=agent.provider,
                    model=agent.model,
                    temperature=agent.temperature,
                    max_tokens=agent.max_tokens,
                    system_prompt=system if round_num == 0 else "",
                    tools=tools,
                )

                total_tokens_in += llm_resp.tokens_in
                total_tokens_out += llm_resp.tokens_out

                # Parse XML tool calls from content (MiniMax sometimes returns these)
                if not llm_resp.tool_calls and llm_resp.content:
                    xml_tcs = self._parse_xml_tool_calls(llm_resp.content)
                    if xml_tcs:
                        llm_resp = LLMResponse(
                            content="", model=llm_resp.model, provider=llm_resp.provider,
                            tokens_in=llm_resp.tokens_in, tokens_out=llm_resp.tokens_out,
                            duration_ms=llm_resp.duration_ms, finish_reason="tool_calls",
                            tool_calls=xml_tcs,
                        )

                # No tool calls → final response
                if not llm_resp.tool_calls:
                    content = llm_resp.content
                    break

                # Process tool calls
                # Add assistant message with tool_calls to conversation
                tc_msg_data = [{
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function_name, "arguments": json.dumps(tc.arguments)},
                } for tc in llm_resp.tool_calls]

                messages.append(LLMMessage(
                    role="assistant",
                    content=llm_resp.content or "",
                    tool_calls=tc_msg_data,
                ))

                for tc in llm_resp.tool_calls:
                    result = await self._execute_tool(tc, ctx)
                    all_tool_calls.append({
                        "name": tc.function_name,
                        "args": tc.arguments,
                        "result": result[:500],  # truncate for storage
                    })

                    if tc.function_name == "deep_search":
                        deep_search_used = True

                    # Track code changes as artifacts
                    if tc.function_name in ("code_write", "code_edit") and not result.startswith("Error"):
                        try:
                            self._record_artifact(ctx, tc, result)
                        except Exception:
                            pass

                    # Notify UI via callback
                    if ctx.on_tool_call:
                        try:
                            await ctx.on_tool_call(tc.function_name, tc.arguments, result)
                        except Exception:
                            pass

                    # Add tool result to conversation
                    messages.append(LLMMessage(
                        role="tool",
                        content=result[:4000],
                        tool_call_id=tc.id,
                        name=tc.function_name,
                    ))

                # After deep_search, disable tools to force synthesis
                if deep_search_used:
                    tools = None
                    # Notify: agent is now synthesizing
                    if ctx.on_tool_call:
                        try:
                            await ctx.on_tool_call("deep_search", {"status": "Generating response…"}, "")
                        except Exception:
                            pass

                logger.info("Agent %s tool round %d: %d calls", agent.id, round_num + 1,
                            len(llm_resp.tool_calls))

                # On penultimate round, disable tools to force synthesis next iteration
                if round_num >= MAX_TOOL_ROUNDS - 2 and tools is not None:
                    tools = None
                    messages.append(LLMMessage(
                        role="system",
                        content="You have used many tool calls. Now synthesize your findings and respond to the user. Do not call more tools.",
                    ))
            else:
                content = llm_resp.content or "(Max tool rounds reached)"

            elapsed = int((time.monotonic() - t0) * 1000)
            # Strip raw MiniMax tool-call tokens that leak into content
            content = _strip_raw_tokens(content)
            delegations = self._parse_delegations(content)

            return ExecutionResult(
                content=content,
                agent_id=agent.id,
                model=llm_resp.model,
                provider=llm_resp.provider,
                tokens_in=total_tokens_in,
                tokens_out=total_tokens_out,
                duration_ms=elapsed,
                tool_calls=all_tool_calls,
                delegations=delegations,
            )

        except Exception as exc:
            elapsed = int((time.monotonic() - t0) * 1000)
            logger.error("Agent %s execution failed: %s", agent.id, exc, exc_info=True)
            return ExecutionResult(
                content=f"Error: {exc}",
                agent_id=agent.id,
                duration_ms=elapsed,
                error=str(exc),
            )

    @staticmethod
    def _parse_xml_tool_calls(content: str) -> list:
        """Parse MiniMax XML-format tool calls from content."""
        from ..llm.client import LLMToolCall as _TC
        import uuid as _uuid

        calls = []
        # Match <invoke name="tool_name"><parameter name="key">value</parameter>...</invoke>
        invoke_re = re.compile(
            r'<invoke\s+name="([^"]+)">(.*?)</invoke>', re.DOTALL
        )
        param_re = re.compile(
            r'<parameter\s+name="([^"]+)">(.*?)</parameter>', re.DOTALL
        )
        for m in invoke_re.finditer(content):
            fn_name = m.group(1)
            body = m.group(2)
            args = {}
            for pm in param_re.finditer(body):
                args[pm.group(1)] = pm.group(2).strip()
            calls.append(_TC(
                id=f"call_{_uuid.uuid4().hex[:12]}",
                function_name=fn_name,
                arguments=args,
            ))
        return calls

    async def _execute_tool(self, tc: LLMToolCall, ctx: ExecutionContext) -> str:
        """Execute a single tool call and return string result."""
        name = tc.function_name
        args = dict(tc.arguments)

        # ── Resolve paths: project_path is the default for all file/git tools ──
        if ctx.project_path:
            # Git/build/deploy tools: inject cwd
            if name in ("git_status", "git_log", "git_diff", "git_commit", "build", "test", "lint", "docker_build"):
                if "cwd" not in args:
                    args["cwd"] = ctx.project_path
            # File tools: resolve relative paths to project root
            if name in ("code_read", "code_search", "code_write", "code_edit", "list_files"):
                path = args.get("path", "")
                if not path or path == ".":
                    args["path"] = ctx.project_path
                elif not os.path.isabs(path):
                    args["path"] = os.path.join(ctx.project_path, path)

        # Handle built-in tools that don't go through registry
        if name == "list_files":
            return await self._tool_list_files(args)
        if name == "memory_search":
            return await self._tool_memory_search(args, ctx)
        if name == "memory_store":
            return await self._tool_memory_store(args, ctx)
        if name == "deep_search":
            return await self._tool_deep_search(args, ctx)

        # Registry tools
        tool = self._registry.get(name)
        if not tool:
            return f"Error: unknown tool '{name}'"

        try:
            return await tool.execute(args)
        except Exception as e:
            return f"Tool '{name}' error: {e}"

    async def _tool_list_files(self, args: dict) -> str:
        """List directory contents."""
        import os
        path = args.get("path", ".")
        depth = int(args.get("depth", 2))
        if not os.path.isdir(path):
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

    async def _tool_memory_search(self, args: dict, ctx: ExecutionContext) -> str:
        """Search project/global memory."""
        from ..memory.manager import get_memory_manager
        mem = get_memory_manager()
        query = args.get("query", "")
        scope = args.get("scope", "project")
        try:
            if scope == "project" and ctx.project_id:
                results = mem.project_search(ctx.project_id, query, limit=10)
            else:
                results = mem.global_search(query, limit=10)
            if not results:
                return "No memory entries found."
            return "\n".join(f"[{r.get('key','')}] {r.get('value','')[:300]}" for r in results)
        except Exception as e:
            return f"Memory search error: {e}"

    async def _tool_memory_store(self, args: dict, ctx: ExecutionContext) -> str:
        """Store a fact in project memory."""
        from ..memory.manager import get_memory_manager
        mem = get_memory_manager()
        key = args.get("key", "")
        value = args.get("value", "")
        category = args.get("category", "fact")
        if not key or not value:
            return "Error: key and value required"
        try:
            if ctx.project_id:
                mem.project_store(ctx.project_id, key, value, category=category, author=ctx.agent.id)
                return f"Stored in project memory: [{key}]"
            return "Error: no project context"
        except Exception as e:
            return f"Memory store error: {e}"

    async def _tool_deep_search(self, args: dict, ctx: ExecutionContext) -> str:
        """RLM: Deep recursive search (MIT CSAIL arXiv:2512.24601)."""
        from .rlm import get_project_rlm
        query = args.get("query", "")
        if not query:
            return "Error: query is required"
        if not ctx.project_id:
            return "Error: no project context for RLM"

        print(f"[EXECUTOR] deep_search called: {query[:80]}", flush=True)
        rlm = get_project_rlm(ctx.project_id)
        if not rlm:
            return f"Error: could not initialize RLM for project {ctx.project_id}"

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

        print(f"[EXECUTOR] deep_search done: {result.iterations} iters, {result.total_queries} queries, {len(result.answer)} chars", flush=True)
        header = f"RLM Deep Search ({result.iterations} iterations, {result.total_queries} queries)\n\n"
        return header + result.answer

    def _record_artifact(self, ctx: ExecutionContext, tc: LLMToolCall, result: str):
        """Record a code_write/code_edit as an artifact in the DB."""
        import uuid
        from ..db.migrations import get_db
        path = tc.arguments.get("path", "unknown")
        art_type = "edit" if tc.function_name == "code_edit" else "create"
        content = tc.arguments.get("content", "") or f"Edit: {tc.arguments.get('old_str', '')[:100]} → {tc.arguments.get('new_str', '')[:100]}"
        lang = os.path.splitext(path)[1].lstrip(".")
        db = get_db()
        try:
            db.execute(
                "INSERT INTO artifacts (id, session_id, type, name, content, language, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4())[:8], ctx.session_id, art_type, f"[{art_type.upper()}] {path}", content[:2000], lang, ctx.agent.id),
            )
            db.commit()
        except Exception as e:
            logger.warning("Failed to record artifact: %s", e)
        finally:
            db.close()

    def _build_system_prompt(self, ctx: ExecutionContext) -> str:
        """Compose the full system prompt from agent config + skills + context."""
        parts = []
        agent = ctx.agent

        if agent.system_prompt:
            parts.append(agent.system_prompt)

        if agent.persona:
            parts.append(f"\n## Persona & Character\n{agent.persona}")

        parts.append(f"\nYou are {agent.name}, role: {agent.role}.")
        if agent.description:
            parts.append(f"Description: {agent.description}")

        if ctx.tools_enabled:
            parts.append("\nYou have access to tools. Use them to read files, search code, check git status, and access project memory. Call tools when you need concrete information rather than guessing.")

        if ctx.skills_prompt:
            parts.append(f"\n## Skills\n{ctx.skills_prompt}")

        if ctx.vision:
            parts.append(f"\n## Project Vision\n{ctx.vision[:3000]}")

        if ctx.project_context:
            parts.append(f"\n## Project Context\n{ctx.project_context[:2000]}")

        if ctx.project_memory:
            parts.append(f"\n## Project Memory (auto-loaded instructions)\n{ctx.project_memory[:4000]}")

        if ctx.project_path:
            parts.append(f"\n## Project Path\n{ctx.project_path}")

        perms = agent.permissions or {}
        if perms.get("can_delegate"):
            parts.append("\nYou CAN delegate tasks to other agents by writing: [DELEGATE:agent_id] task description")
        if perms.get("can_veto"):
            parts.append("\nYou CAN veto decisions by writing: [VETO] reason")
        if perms.get("can_approve"):
            parts.append("\nYou CAN approve work by writing: [APPROVE] reason")

        return "\n".join(parts)

    def _build_messages(self, ctx: ExecutionContext, user_message: str) -> list[LLMMessage]:
        """Build the message list from conversation history."""
        messages = []
        for h in ctx.history[-20:]:
            role = "assistant" if h.get("from_agent") != "user" else "user"
            name = h.get("from_agent")
            messages.append(LLMMessage(
                role=role,
                content=h.get("content", ""),
                name=name if name != "user" else None,
            ))
        messages.append(LLMMessage(role="user", content=user_message))
        return messages

    def _parse_delegations(self, content: str) -> list[dict]:
        """Parse [DELEGATE:agent_id] markers from response."""
        delegations = []
        for line in content.split("\n"):
            if "[DELEGATE:" in line:
                try:
                    start = line.index("[DELEGATE:") + len("[DELEGATE:")
                    end = line.index("]", start)
                    agent_id = line[start:end]
                    task = line[end + 1:].strip()
                    delegations.append({"to_agent": agent_id, "task": task})
                except (ValueError, IndexError):
                    pass
        return delegations


# Singleton
_executor: Optional[AgentExecutor] = None


def get_executor() -> AgentExecutor:
    global _executor
    if _executor is None:
        _executor = AgentExecutor()
    return _executor
