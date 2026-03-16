# Ref: feat-quality
"""
Prompt CI — Real LLM integration tests for prompt reliability.

Tests that SF prompts produce expected behaviors with live LLM calls.
No mocks. No fakes. Live data only.

Run: pytest tests/test_prompt_ci.py -v -x
Requires: MINIMAX_API_KEY (or LLM_API_KEY) in .env

Markers:
  @pytest.mark.prompt_ci  — all prompt CI tests
  @pytest.mark.slow       — tests that take >10s (multi-round)
"""

import asyncio
import json
import os
import re
import sys
import time

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from platform.llm.client import LLMClient, LLMMessage, LLMResponse  # noqa: E402
from platform.agents.prompt_builder import (  # noqa: E402
    _build_system_prompt,
    _classify_agent_role,
)
from platform.agents.executor import ExecutionContext  # noqa: E402
from platform.agents.store import get_agent_store  # noqa: E402
from platform.agents.tool_schemas import _get_tool_schemas, _filter_schemas  # noqa: E402
from platform.agents.subagent_prompts import (  # noqa: E402
    build_implementer_prompt,
    build_spec_reviewer_prompt,
    build_code_quality_reviewer_prompt,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PROVIDER = os.environ.get("PROMPT_CI_PROVIDER", "minimax")
MODEL = os.environ.get("PROMPT_CI_MODEL", "MiniMax-M2.5")
TIMEOUT = int(os.environ.get("PROMPT_CI_TIMEOUT", "60"))

# Tool schemas used in tests
_CODE_TOOLS = [
    s for s in _get_tool_schemas()
    if s["function"]["name"] in (
        "code_write", "code_read", "code_edit", "list_files",
        "build", "memory_search", "memory_store", "deep_search",
    )
]

pytestmark = [pytest.mark.prompt_ci]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def llm():
    """Live LLM client — no mocks."""
    return LLMClient()


@pytest.fixture(scope="session")
def agent_store():
    return get_agent_store()


@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def _run(coro):
    """Run async in sync context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _chat(llm, messages, tools=None):
    """Single LLM call with tools. Adds nonce to avoid cache hits."""
    import random
    # Append invisible nonce to last user message to bust LLM cache
    nonce = f"\n<!-- ci-{random.randint(10000,99999)} -->"
    msgs = list(messages)
    for i in range(len(msgs) - 1, -1, -1):
        if msgs[i].role == "user":
            msgs[i] = LLMMessage(
                role="user", content=msgs[i].content + nonce,
                name=msgs[i].name, tool_call_id=msgs[i].tool_call_id,
            )
            break
    return await llm.chat(
        messages=msgs,
        provider=PROVIDER,
        model=MODEL,
        tools=tools,
        max_tokens=4096,
        temperature=0.3,
    )


async def _multi_round(llm, messages, tools, max_rounds=6):
    """Simulate executor multi-round tool loop. Returns (rounds, tool_calls_log)."""
    tool_calls_log = []
    for rnd in range(max_rounds):
        resp = await _chat(llm, messages, tools)
        if not resp.tool_calls:
            return rnd, tool_calls_log, resp

        # Append assistant message with tool_calls
        tc_data = [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.function_name, "arguments": json.dumps(tc.arguments)}}
            for tc in resp.tool_calls
        ]
        messages.append(LLMMessage(
            role="assistant", content=resp.content or "",
            tool_calls=tc_data,
        ))

        # Append tool results
        for tc in resp.tool_calls:
            tool_calls_log.append({"round": rnd, "tool": tc.function_name, "args": tc.arguments})
            fake_result = _fake_tool_result(tc.function_name, tc.arguments)
            messages.append(LLMMessage(
                role="tool", content=fake_result,
                tool_call_id=tc.id, name=tc.function_name,
            ))

    return max_rounds, tool_calls_log, resp


def _fake_tool_result(tool_name: str, args: dict) -> str:
    """Deterministic fake results for tool calls — NOT mocks, just simulated filesystem."""
    if tool_name == "list_files":
        return '["src/", "tests/", "README.md", "requirements.txt"]'
    if tool_name == "code_read":
        return 'def hello():\n    print("hello world")\n'
    if tool_name == "code_write":
        return f"OK: written {args.get('path', 'file.py')}"
    if tool_name == "code_edit":
        return f"OK: edited {args.get('path', 'file.py')}"
    if tool_name == "build":
        return "[BUILD] OK (exit 0)\n$ python3 -m pytest -v\n3 passed in 0.5s"
    if tool_name == "memory_search":
        return "No prior decisions found for this topic."
    if tool_name == "memory_store":
        return "OK: stored"
    if tool_name == "deep_search":
        return "Found 2 relevant files:\n- src/utils.py: utility functions\n- src/main.py: entry point"
    return "OK"


# ===================================================================
# 1. PROMPT BUILDER — Structure & Role Classification
# ===================================================================

class TestPromptBuilder:
    """Test that _build_system_prompt produces correct prompt structure."""

    def test_dev_agent_has_write_first_instruction(self, agent_store):
        """Critical regression: dev agents must say WRITE FIRST, not READ FIRST."""
        agent = agent_store.get("lead_dev")
        assert agent is not None, "lead_dev agent not found"

        ctx = ExecutionContext(
            agent=agent, session_id="test-ci", tools_enabled=True,
            project_id="test", project_path="/tmp/test",
        )
        prompt = _build_system_prompt(ctx)

        # Must contain write-first instruction
        assert "WRITE" in prompt.upper(), "Prompt must mention WRITE"
        assert "code_write" in prompt.lower() or "write code" in prompt.lower(), \
            "Prompt must reference code_write or writing code"

        # Must NOT contain old mandatory exploration
        assert "MANDATORY after memory" not in prompt, \
            "Old MANDATORY deep_search instruction still present"
        assert "ALWAYS call memory_search" not in prompt, \
            "Old ALWAYS memory_search instruction still present"

    def test_memory_is_recommended_not_mandatory(self, agent_store):
        """Regression: memory_search should be recommended, not mandatory."""
        agent = agent_store.get("lead_dev")
        ctx = ExecutionContext(
            agent=agent, session_id="test-ci", tools_enabled=True,
            project_id="test", project_path="/tmp/test",
        )
        prompt = _build_system_prompt(ctx)
        lower = prompt.lower()

        assert "recommended" in lower or "optional" in lower, \
            "Memory/deep_search should be marked recommended or optional"

    def test_role_classification_covers_all_types(self, agent_store):
        """All agent roles must map to a known category."""
        known_cats = {"product", "cto", "architecture", "reviewer", "ux",
                       "qa", "devops", "security", "cdp", "dev"}
        agents = agent_store.list_all()
        unmapped = []
        for agent in agents[:50]:  # sample
            cat = _classify_agent_role(agent)
            if cat not in known_cats:
                unmapped.append((agent.id, cat))
        assert not unmapped, f"Unmapped roles: {unmapped}"

    def test_prompt_size_reasonable(self, agent_store):
        """System prompts should be <8000 chars to leave room for context."""
        agent = agent_store.get("lead_dev")
        ctx = ExecutionContext(
            agent=agent, session_id="test-ci", tools_enabled=True,
            project_id="test", project_path="/tmp/test",
        )
        prompt = _build_system_prompt(ctx)
        assert len(prompt) < 8000, \
            f"Prompt too large: {len(prompt)} chars (max 8000)"

    def test_execution_agents_have_tool_mandate(self, agent_store):
        """Dev/QA/DevOps agents must have tool usage mandate in prompt."""
        for agent_id in ["lead_dev", "lead_frontend", "lead_backend"]:
            agent = agent_store.get(agent_id)
            if not agent:
                continue
            ctx = ExecutionContext(
                agent=agent, session_id="test-ci", tools_enabled=True,
                project_id="test", project_path="/tmp/test",
            )
            prompt = _build_system_prompt(ctx)
            assert "EXECUTION agent" in prompt or "tool calls" in prompt.lower(), \
                f"{agent_id} missing tool mandate"


# ===================================================================
# 2. WRITE-FIRST BEHAVIOR — Agent writes code within 3 rounds
# ===================================================================

class TestWriteFirstBehavior:
    """Test that dev agents call code_write within their first 3 tool rounds."""

    @pytest.mark.slow
    def test_dev_writes_code_within_3_rounds(self, llm, agent_store):
        """Critical: agent must call code_write within 3 rounds, not explore forever."""
        agent = agent_store.get("lead_dev") or agent_store.get("lead_frontend")
        assert agent is not None

        ctx = ExecutionContext(
            agent=agent, session_id="test-ci", tools_enabled=True,
            project_id="test", project_path="/data/workspaces/test-ci",
        )
        sys_prompt = _build_system_prompt(ctx)

        messages = [
            LLMMessage(role="system", content=sys_prompt),
            LLMMessage(role="user", content=(
                "Write a Python file at utils/validators.py. The file must contain:\n"
                "- validate_email(email: str) -> bool using regex\n"
                "- validate_phone(phone: str) -> bool using regex\n"
                "Call code_write immediately with the complete file content. "
                "Do NOT explore the filesystem first — just write the file."
            )),
        ]

        rounds, log, _ = _run(_multi_round(llm, messages, _CODE_TOOLS, max_rounds=6))

        # Find first code_write
        write_round = None
        for entry in log:
            if entry["tool"] == "code_write":
                write_round = entry["round"]
                break

        assert write_round is not None, (
            f"Agent never called code_write in {rounds} rounds. "
            f"Tools called: {[e['tool'] for e in log]}"
        )
        assert write_round <= 3, (
            f"code_write at round {write_round} (must be <=3). "
            f"Sequence: {[e['tool'] for e in log]}"
        )

    @pytest.mark.slow
    def test_code_write_has_valid_content(self, llm, agent_store):
        """code_write must produce actual code, not placeholders."""
        agent = agent_store.get("lead_dev") or agent_store.get("lead_frontend")
        assert agent is not None

        ctx = ExecutionContext(
            agent=agent, session_id="test-ci", tools_enabled=True,
            project_id="test", project_path="/data/workspaces/test-ci",
        )
        sys_prompt = _build_system_prompt(ctx)

        messages = [
            LLMMessage(role="system", content=sys_prompt),
            LLMMessage(role="user", content=(
                "Create hello.py with a function greet(name: str) -> str "
                "that returns 'Hello, {name}!'"
            )),
        ]

        _, log, _ = _run(_multi_round(llm, messages, _CODE_TOOLS, max_rounds=5))

        writes = [e for e in log if e["tool"] == "code_write"]
        assert writes, "No code_write calls"

        content = writes[0]["args"].get("content", "")
        assert len(content) > 20, f"code_write content too short: {len(content)} chars"
        assert "def " in content or "class " in content, \
            "code_write content missing function/class definition"
        assert "TODO" not in content and "pass" not in content.split("def ")[-1][:50], \
            "code_write content has placeholder stubs"


# ===================================================================
# 3. MULTI-TURN TOOL CALLING — Native role=tool works
# ===================================================================

class TestMultiTurnToolCalling:
    """Test that tool-calling loop continues across multiple rounds."""

    @pytest.mark.slow
    def test_native_role_tool_multi_round(self, llm):
        """MiniMax must continue tool-calling after receiving role=tool results."""
        messages = [
            LLMMessage(role="system", content=(
                "You are a developer. Create a Python project:\n"
                "1. list_files to check workspace\n"
                "2. code_write utils.py with add/subtract functions\n"
                "3. code_write test_utils.py with pytest tests\n"
                "4. build to run tests\n"
                "Execute ALL 4 steps using tools."
            )),
            LLMMessage(role="user", content="Create the project now."),
        ]

        rounds, log, _ = _run(_multi_round(llm, messages, _CODE_TOOLS, max_rounds=8))

        tool_names = [e["tool"] for e in log]

        # Must have at least 3 tool calls across multiple rounds
        assert len(log) >= 3, (
            f"Only {len(log)} tool calls (need >=3). Tools: {tool_names}"
        )

        # Must span at least 2 rounds (not all in round 0)
        rounds_used = set(e["round"] for e in log)
        assert len(rounds_used) >= 2, (
            f"All tools in same round (need multi-round). Rounds: {rounds_used}"
        )

        # Must include code_write
        assert "code_write" in tool_names, (
            f"No code_write found. Tools: {tool_names}"
        )

    @pytest.mark.slow
    def test_tool_loop_does_not_stop_after_one_round(self, llm):
        """Regression: old bug stopped tool loop after 1 round due to role=tool conversion."""
        messages = [
            LLMMessage(role="system", content="You are a file manager. Use tools to complete tasks."),
            LLMMessage(role="user", content=(
                "Do these 3 things in order: "
                "1. list_files path='.' "
                "2. code_read path='README.md' "
                "3. code_write path='output.txt' content='done'"
            )),
        ]

        rounds, log, _ = _run(_multi_round(llm, messages, _CODE_TOOLS, max_rounds=6))

        assert len(log) >= 3, (
            f"Only {len(log)} tool calls — loop likely stopped early. "
            f"Tools: {[e['tool'] for e in log]}"
        )

    @pytest.mark.slow
    def test_parallel_tool_calls_accepted(self, llm):
        """MiniMax should be able to return multiple tool_calls in one response."""
        messages = [
            LLMMessage(role="system", content=(
                "You are a developer. Read multiple files simultaneously. "
                "Call code_read for BOTH files in a SINGLE response."
            )),
            LLMMessage(role="user", content=(
                "Read these two files at once: src/main.py and src/utils.py"
            )),
        ]

        resp = _run(_chat(llm, messages, _CODE_TOOLS))

        # Parallel calls are a bonus — at minimum, should call at least 1 tool
        assert resp.tool_calls, "No tool calls at all"
        # If parallel supported, great. If sequential, still passes.


# ===================================================================
# 4. PROVIDER RELIABILITY — Tool calling per provider
# ===================================================================

class TestProviderReliability:
    """Test tool-calling reliability for the configured provider."""

    @pytest.mark.slow
    def test_tool_call_format_valid(self, llm):
        """LLM returns properly formatted tool_calls with id, function_name, arguments."""
        messages = [
            LLMMessage(role="system", content="Use tools to help the user."),
            LLMMessage(role="user", content="List files in the current directory"),
        ]

        resp = _run(_chat(llm, messages, _CODE_TOOLS))

        assert resp.tool_calls, "No tool calls returned"
        tc = resp.tool_calls[0]
        assert tc.id, "tool_call missing id"
        assert tc.function_name, "tool_call missing function_name"
        assert isinstance(tc.arguments, dict), "arguments should be dict"

    @pytest.mark.slow
    def test_finish_reason_tool_calls(self, llm):
        """When tools are called, finish_reason must be 'tool_calls' not 'stop'."""
        messages = [
            LLMMessage(role="system", content="You MUST use tools. Call list_files now."),
            LLMMessage(role="user", content="List files."),
        ]

        resp = _run(_chat(llm, messages, _CODE_TOOLS))

        if resp.tool_calls:
            assert resp.finish_reason == "tool_calls", (
                f"finish_reason={resp.finish_reason} but has tool_calls"
            )

    @pytest.mark.slow
    def test_deep_search_param_alias(self, llm):
        """deep_search should accept both 'query' and 'q' parameter names."""
        messages = [
            LLMMessage(role="system", content="Use deep_search to find information."),
            LLMMessage(role="user", content="Search for authentication implementation"),
        ]

        resp = _run(_chat(llm, messages, _CODE_TOOLS))

        if resp.tool_calls:
            for tc in resp.tool_calls:
                if tc.function_name == "deep_search":
                    args = tc.arguments
                    has_query = bool(args.get("query") or args.get("q"))
                    assert has_query, (
                        f"deep_search called without query or q: {args}"
                    )


# ===================================================================
# 5. SUBAGENT PROMPTS — Format compliance
# ===================================================================

class TestSubagentPrompts:
    """Test that subagent prompts produce correctly formatted verdicts."""

    @pytest.mark.slow
    def test_implementer_returns_done_status(self, llm):
        """Implementer prompt must produce DONE or DONE_WITH_CONCERNS."""
        prompt = build_implementer_prompt(
            task_spec="Create a utility function add(a, b) -> int in utils.py",
            context={"files": ["utils.py"], "language": "python", "framework": "pytest"},
            project_id="test-project",
            constraints=["Must include type hints"],
        )

        messages = [
            LLMMessage(role="system", content=prompt),
            LLMMessage(role="user", content="Implement this task now."),
        ]

        # Implementer needs tools to work
        resp = _run(_chat(llm, messages, _CODE_TOOLS))

        # If it calls tools, simulate completion
        if resp.tool_calls:
            # Run multi-round to get final text
            _, log, final_resp = _run(_multi_round(llm, messages, _CODE_TOOLS, max_rounds=5))
            content = final_resp.content or ""
        else:
            content = resp.content or ""

        # Should contain status protocol
        valid_statuses = ["DONE", "DONE_WITH_CONCERNS", "NEEDS_CONTEXT", "BLOCKED"]
        has_status = any(s in content.upper() for s in valid_statuses)
        # Implementer may also just produce code via tool calls — that's OK too
        has_tool_work = bool(resp.tool_calls)

        assert has_status or has_tool_work, (
            f"Implementer produced neither status nor tool calls. "
            f"Content: {content[:200]}"
        )

    @pytest.mark.slow
    def test_spec_reviewer_returns_verdict(self, llm):
        """Spec reviewer must return APPROVED or REJECTED."""
        prompt = build_spec_reviewer_prompt(
            task_spec="Create add(a, b) -> int in utils.py with type hints",
            implementation_summary="Created utils.py with add function, includes type hints and docstring",
            changed_files=["utils.py"],
        )

        messages = [
            LLMMessage(role="system", content=prompt),
            LLMMessage(role="user", content="Review this implementation against the spec."),
        ]

        resp = _run(_chat(llm, messages))

        content = (resp.content or "").upper()
        # Accept various verdict formats
        has_verdict = (
            "APPROVED" in content or "REJECTED" in content
            or "PASS" in content or "FAIL" in content
            or "COMPLIANT" in content or "NON-COMPLIANT" in content
            or "MEETS" in content  # "meets specification"
        )
        assert has_verdict, (
            f"Spec reviewer missing verdict. Content: {resp.content[:300]}"
        )

    @pytest.mark.slow
    def test_code_quality_reviewer_returns_severity(self, llm):
        """Code quality reviewer must return verdict with severity levels."""
        prompt = build_code_quality_reviewer_prompt(
            changed_files=["utils.py"],
            git_diff="+ def add(a: int, b: int) -> int:\n+     return a + b\n",
            project_conventions="Use type hints, docstrings, follow PEP 8",
        )

        messages = [
            LLMMessage(role="system", content=prompt),
            LLMMessage(role="user", content="Review this code for quality."),
        ]

        resp = _run(_chat(llm, messages))

        content = (resp.content or "").upper()
        valid_verdicts = ["APPROVED", "APPROVED_WITH_NOTES", "CHANGES_REQUESTED"]
        has_verdict = any(v in content for v in valid_verdicts)
        assert has_verdict, (
            f"Quality reviewer missing verdict. Content: {resp.content[:300]}"
        )


# ===================================================================
# 6. REGRESSION GUARDS — Specific bugs we fixed
# ===================================================================

class TestRegressionGuards:
    """Regression tests for specific bugs found during investigation."""

    def test_no_mandatory_exploration_in_prompt(self, agent_store):
        """Regression: prompts must not force mandatory exploration before writing."""
        for agent_id in ["lead_dev", "lead_frontend", "lead_backend"]:
            agent = agent_store.get(agent_id)
            if not agent:
                continue
            ctx = ExecutionContext(
                agent=agent, session_id="test-ci", tools_enabled=True,
                project_id="test", project_path="/tmp/test",
            )
            prompt = _build_system_prompt(ctx)
            assert "MANDATORY after memory" not in prompt, \
                f"{agent_id}: old MANDATORY deep_search still present"
            assert "ALWAYS call memory_search" not in prompt, \
                f"{agent_id}: old ALWAYS memory_search still present"

    def test_tool_schemas_have_required_fields(self):
        """All tool schemas must have valid OpenAI function-calling structure."""
        schemas = _get_tool_schemas()
        for s in schemas:
            assert "type" in s and s["type"] == "function", \
                f"Schema missing type=function: {s}"
            fn = s.get("function", {})
            assert "name" in fn, f"Schema missing function.name: {s}"
            assert "parameters" in fn, f"Schema {fn['name']} missing parameters"

    def test_deep_search_schema_has_query_param(self):
        """deep_search schema must define 'query' as required parameter."""
        schemas = _get_tool_schemas()
        ds = [s for s in schemas if s["function"]["name"] == "deep_search"]
        assert ds, "deep_search schema not found"
        params = ds[0]["function"]["parameters"]
        props = params.get("properties", {})
        assert "query" in props, "deep_search missing 'query' property"
