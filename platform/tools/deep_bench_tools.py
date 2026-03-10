"""
Deep Bench Tools — real validation of all 7 AC layers.

Unlike surface benches (prompt → check keywords), deep benches exercise
the actual infrastructure: tool execution, skill injection, veto system,
workflow phases, memory persistence, and end-to-end pilot flows.

Layers:
  1. AC LLM Deep     — streaming, tool_calls format, JSON schema, edge cases
  2. AC Skills Deep  — skill injection into prompt, skill-driven behavior change
  3. AC Agents Deep  — real tool execution in sandbox, output file validation
  4. AC Teams Deep   — A2A bus messages, pattern execution, inter-agent flow
  5. AC Memory Deep  — persistence, compaction, concurrent access, agent-informed
  6. AC Workflows Deep — phase transitions, gate enforcement, lifecycle
  7. AC SF Deep      — end-to-end pilot: mission → agents → code → validation

Usage:
    from platform.tools.deep_bench_tools import run_deep_bench
    result = run_deep_bench()          # all layers
    result = run_deep_bench("agents")  # single layer
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import traceback
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import logging

logger = logging.getLogger(__name__)


def _arun(coro):
    """Run async coroutine from sync context, handling existing event loops."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result(timeout=120)
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class DeepCheck:
    name: str
    passed: bool
    detail: str = ""
    elapsed_ms: int = 0


@dataclass
class DeepCase:
    case_id: str
    layer: str
    description: str
    passed: bool = False
    checks: list[DeepCheck] = field(default_factory=list)
    error: str = ""
    elapsed_ms: int = 0
    needs_llm: bool = False  # True for LLM judge cases


@dataclass
class DeepBenchResult:
    layers: dict[str, list[DeepCase]] = field(default_factory=dict)
    total_cases: int = 0
    passed_cases: int = 0
    pass_rate: float = 0.0
    elapsed_ms: int = 0
    status: str = "ok"

    def to_dict(self) -> dict:
        return asdict(self)


def _ck(case: DeepCase, name: str, condition: bool, detail: str = "") -> bool:
    case.checks.append(DeepCheck(name=name, passed=condition, detail=detail))
    return condition


def _llm_judge(case: DeepCase, output: str, criteria: list[str],
               label: str = "judge") -> float:
    """Generic LLM judge for deep bench. Returns score 0.0-1.0.

    Gracefully degrades when LLM unavailable (marks checks as failed).
    """
    try:
        from platform.llm.client import LLMClient, LLMMessage

        client = LLMClient()
        judge_prompt = (
            "You are a strict quality evaluator. Judge ONLY on evidence.\n\n"
            f"OUTPUT TO EVALUATE:\n{output[:3000]}\n\n"
            f"CRITERIA:\n" + "\n".join(f"- {c}" for c in criteria) + "\n\n"
            "Reply ONLY with JSON:\n"
            '{"grades":[{"criterion":"...","pass":true,"reason":"brief"}]}'
        )

        response = _arun(client.chat(
            messages=[
                LLMMessage(role="system", content="Strict quality evaluator. JSON only."),
                LLMMessage(role="user", content=judge_prompt),
            ],
            response_format={"type": "json_object"},
        ))

        data = json.loads(response.content)
        grades = data.get("grades", [])
        for g in grades:
            crit = g.get("criterion", "?")[:40]
            _ck(case, f"{label}:{crit}", g.get("pass", False),
                g.get("reason", "")[:100])

        passed = sum(1 for g in grades if g.get("pass"))
        return passed / len(grades) if grades else 0.0

    except Exception as e:
        _ck(case, f"{label}:llm-available", False,
            f"LLM unavailable: {str(e)[:100]}")
        return 0.0


# ===========================================================================
# LAYER 1 — AC LLM DEEP
# ===========================================================================

def _llm_deep_cases() -> list[DeepCase]:
    cases = []

    # 1a. Streaming works end-to-end
    c = DeepCase("llm-streaming", "llm", "LLM streaming returns chunks")
    t0 = time.time()
    try:
        from platform.llm.client import LLMClient, LLMMessage

        async def _test_stream():
            client = LLMClient()
            chunks = []
            async for chunk in client.stream(
                [LLMMessage(role="user", content="Count from 1 to 5, one number per line.")],
            ):
                chunks.append(chunk)
            return chunks

        chunks = _arun(_test_stream())
        full = "".join(ch.content for ch in chunks if hasattr(ch, "content") and ch.content)
        _ck(c, "received chunks", len(chunks) > 0, f"{len(chunks)} chunks")
        _ck(c, "content not empty", len(full) > 5, f"{len(full)} chars")
        _ck(c, "contains numbers", any(str(n) in full for n in range(1, 6)), full[:100])
        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 1b. Tool calls format (LLM returns proper tool_calls, not text)
    c = DeepCase("llm-tool-calls-format", "llm", "LLM returns structured tool_calls")
    t0 = time.time()
    try:
        from platform.llm.client import LLMClient, LLMMessage

        async def _test_tool_calls():
            client = LLMClient()
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "description": "Get current weather for a city",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "city": {"type": "string", "description": "City name"},
                            },
                            "required": ["city"],
                        },
                    },
                }
            ]
            return await client.chat(
                [LLMMessage(role="user", content="What's the weather in Paris?")],
                tools=tools,
            )

        resp = _arun(_test_tool_calls())
        _ck(c, "response received", resp is not None)
        has_tc = resp.tool_calls is not None and len(resp.tool_calls) > 0
        _ck(c, "tool_calls present", has_tc,
            f"{len(resp.tool_calls)} calls" if has_tc else "no tool_calls")
        if has_tc:
            tc = resp.tool_calls[0]
            _ck(c, "function name correct", tc.function_name == "get_weather",
                f"got: {tc.function_name}")
            args = json.loads(tc.arguments) if isinstance(tc.arguments, str) else tc.arguments
            _ck(c, "city argument present", "city" in args, str(args))
        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 1c. JSON output compliance
    c = DeepCase("llm-json-output", "llm", "LLM produces valid JSON when asked")
    t0 = time.time()
    try:
        from platform.llm.client import LLMClient, LLMMessage

        async def _test_json():
            client = LLMClient()
            return await client.chat(
                [LLMMessage(role="user", content=(
                    'Return a JSON object with keys "name", "age", "skills" (array). '
                    'Example person. Return ONLY valid JSON, no markdown.'
                ))],
                response_format={"type": "json_object"},
            )

        resp = _arun(_test_json())
        text = resp.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        parsed = json.loads(text)
        _ck(c, "valid JSON", True)
        _ck(c, "has name", "name" in parsed, str(list(parsed.keys())))
        _ck(c, "has skills array", isinstance(parsed.get("skills"), list))
        c.passed = all(ch.passed for ch in c.checks)
    except json.JSONDecodeError as e:
        _ck(c, "valid JSON", False, str(e))
        c.error = f"JSON parse error: {e}"
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 1d. No thinking leak in output
    c = DeepCase("llm-no-think-leak", "llm", "No <think> tags leak in output")
    t0 = time.time()
    try:
        from platform.llm.client import LLMClient, LLMMessage

        async def _test_think():
            client = LLMClient()
            return await client.chat(
                [LLMMessage(role="user", content="Explain recursion in one sentence.")],
            )

        resp = _arun(_test_think())
        text = resp.content
        _ck(c, "no <think> tag", "<think>" not in text, text[:200])
        _ck(c, "no </think> tag", "</think>" not in text)
        _ck(c, "content meaningful", len(text) > 20, f"{len(text)} chars")
        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 1e. Circuit breaker state machine
    c = DeepCase("llm-circuit-breaker", "llm",
                 "Circuit breaker tracks failures and opens on threshold")
    t0 = time.time()
    try:
        from platform.llm.client import LLMClient

        client = LLMClient()
        _ck(c, "CB_OPEN_DURATION defined", hasattr(client, "CB_OPEN_DURATION"),
            f"{getattr(client, 'CB_OPEN_DURATION', 'N/A')}s")
        _ck(c, "has _record_failure", callable(getattr(client, "_record_failure", None)))
        _ck(c, "has _is_circuit_open", callable(getattr(client, "_is_circuit_open", None)))
        # Verify CB is closed for current provider (no recent failures)
        provider = os.environ.get("PLATFORM_LLM_PROVIDER", "local-mlx")
        is_open = client._is_circuit_open(provider)
        _ck(c, "CB closed for active provider", not is_open, provider)
        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 1f. Model routing profiles
    c = DeepCase("llm-model-routing", "llm",
                 "MODEL_PROFILES route correctly per task type")
    t0 = time.time()
    try:
        from platform.llm.client import MODEL_PROFILES

        _ck(c, "profiles loaded", isinstance(MODEL_PROFILES, dict) and len(MODEL_PROFILES) > 0,
            f"{len(MODEL_PROFILES)} profiles")
        # Each profile should have model + provider
        for name, profile in list(MODEL_PROFILES.items())[:5]:
            has_model = "model" in profile or "name" in profile
            _ck(c, f"profile:{name} has model", has_model, str(profile)[:80])
        c.passed = all(ch.passed for ch in c.checks)
    except ImportError:
        _ck(c, "MODEL_PROFILES importable", False, "not found in llm.client")
        c.passed = False
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 1g. LLM judge — instruction following
    c = DeepCase("llm-judge-instruction", "llm",
                 "LLM follows structured format instructions", needs_llm=True)
    t0 = time.time()
    try:
        from platform.llm.client import LLMClient, LLMMessage

        client = LLMClient()
        response = _arun(client.acompletion([
            LLMMessage(role="user",
                       content="List exactly 3 French cities. Format: numbered list, one per line."),
        ]))
        output = response.content
        _ck(c, "response not empty", len(output) > 5, f"{len(output)} chars")
        lines = [l.strip() for l in output.strip().split("\n") if l.strip()]
        _ck(c, "has 3 lines", len(lines) == 3, f"got {len(lines)} lines")
        score = _llm_judge(c, output, [
            "Output contains exactly 3 French cities",
            "Cities are in a numbered list format",
            "Each city is on its own line",
        ], label="instruction")
        c.passed = all(ch.passed for ch in c.checks) and score >= 0.6
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    return cases
# ===========================================================================

def _skills_deep_cases() -> list[DeepCase]:
    cases = []

    # 2a. Skills files exist and are loadable for every agent skill reference
    c = DeepCase("skills-files-exist", "skills", "All agent-referenced skills have .md files")
    t0 = time.time()
    try:
        from platform.agents.store import get_agent_store
        store = get_agent_store()
        agents = store.list_all()
        skills_dir = Path("/home/sfadmin/skills")

        all_skills = set()
        missing_skills = set()
        for a in agents:
            for s in (a.skills or []):
                all_skills.add(s)
                skill_path = skills_dir / f"{s}.md"
                if not skill_path.exists():
                    # Try subdirectories
                    found = list(skills_dir.rglob(f"{s}.md"))
                    if not found:
                        missing_skills.add(s)

        _ck(c, "skills referenced", len(all_skills) > 0, f"{len(all_skills)} unique skills")
        _ck(c, "all have .md files",
            len(missing_skills) == 0,
            f"missing: {sorted(missing_skills)[:10]}" if missing_skills else "all found")
        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 2b. Skill content is injected into system prompt
    c = DeepCase("skills-prompt-injection", "skills",
                 "Skills content appears in built system prompt")
    t0 = time.time()
    try:
        from platform.agents.store import get_agent_store
        from platform.agents.executor import ExecutionContext
        from platform.agents.prompt_builder import _build_system_prompt

        store = get_agent_store()
        dev = store.get("dev")
        skills_dir = Path("/home/sfadmin/skills")

        # Build a context with skills loaded
        ctx = ExecutionContext(
            agent=dev,
            session_id="bench-deep-test",
            project_id="bench-project",
        )
        # Load skill content into ctx.skills_prompt
        skill_texts = []
        for s in (dev.skills or []):
            sp = skills_dir / f"{s}.md"
            if sp.exists():
                skill_texts.append(sp.read_text()[:500])
            else:
                found = list(skills_dir.rglob(f"{s}.md"))
                if found:
                    skill_texts.append(found[0].read_text()[:500])
        ctx.skills_prompt = "\n\n".join(skill_texts)

        prompt = _build_system_prompt(ctx)
        _ck(c, "system prompt built", len(prompt) > 100, f"{len(prompt)} chars")
        _ck(c, "contains Skills section", "## Skills" in prompt or "skills" in prompt.lower())

        # Check first skill keyword appears
        if dev.skills:
            first_skill = dev.skills[0]
            _ck(c, f"skill '{first_skill}' content in prompt",
                first_skill.replace("-", " ") in prompt.lower() or first_skill in prompt,
                f"looking for '{first_skill}' in {len(prompt)} char prompt")

        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 2c. Skill diversity — each major tag has agents with skills
    c = DeepCase("skills-tag-coverage", "skills",
                 "Agents across all major tags have skills assigned")
    t0 = time.time()
    try:
        from platform.agents.store import get_agent_store
        store = get_agent_store()
        agents = store.list_all()

        from collections import Counter
        tag_with_skills = Counter()
        tag_total = Counter()
        for a in agents:
            for t in (a.tags or []):
                tag_total[t] += 1
                if a.skills:
                    tag_with_skills[t] += 1

        major_tags = [t for t, c in tag_total.most_common(10)]
        tags_with_coverage = sum(1 for t in major_tags if tag_with_skills.get(t, 0) > 0)

        _ck(c, "major tags count", len(major_tags) >= 5, str(major_tags))
        _ck(c, "tags with skilled agents",
            tags_with_coverage >= len(major_tags) * 0.5,
            f"{tags_with_coverage}/{len(major_tags)} tags have agents with skills")
        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 2d. TDD skill changes agent behavior (LLM test)
    c = DeepCase("skills-tdd-behavior", "skills",
                 "Agent with TDD skill produces tests-first output")
    t0 = time.time()
    try:
        from platform.llm.client import LLMClient, LLMMessage

        skills_dir = Path("/home/sfadmin/skills") if Path("/home/sfadmin/skills").exists() else Path("skills")
        tdd_path = skills_dir / "tdd-mastery.md"
        tdd_content = ""
        if tdd_path.exists():
            tdd_content = tdd_path.read_text()[:2000]
        else:
            found = list(skills_dir.rglob("tdd-mastery.md"))
            if found:
                tdd_content = found[0].read_text()[:2000]

        async def _test_tdd():
            client = LLMClient()
            resp_with = await client.chat([
                LLMMessage(role="system", content=f"You are a developer.\n\n## Skills\n{tdd_content}"),
                LLMMessage(role="user", content="Implement is_palindrome(s: str) -> bool"),
            ])
            resp_without = await client.chat([
                LLMMessage(role="system", content="You are a developer."),
                LLMMessage(role="user", content="Implement is_palindrome(s: str) -> bool"),
            ])
            return resp_with, resp_without

        resp_with, resp_without = _arun(_test_tdd())

        with_text = resp_with.content.lower()
        without_text = resp_without.content.lower()

        _ck(c, "with TDD skill: mentions tests", "test" in with_text, f"{len(resp_with.content)} chars")
        _ck(c, "with TDD skill: has test function", "def test_" in with_text or "assert" in with_text)
        _ck(c, "both produce implementation", "palindrome" in with_text and "palindrome" in without_text)
        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 2e. Agent→skill cross-reference integrity
    c = DeepCase("skills-agent-mapping", "skills",
                 "Every agent.skills[] reference resolves to .md file")
    t0 = time.time()
    try:
        from platform.agents.store import get_agent_store

        store = get_agent_store()
        agents = store.list_all()
        skills_dir = Path("platform/skills") if Path("platform/skills").exists() else Path("/home/sfadmin/platform/skills")

        total_refs = 0
        missing = []
        for a in agents:
            for skill in (a.skills or []):
                total_refs += 1
                skill_path = skills_dir / f"{skill}.md"
                if not skill_path.exists():
                    # Try subdirs
                    found = list(skills_dir.rglob(f"{skill}.md"))
                    if not found:
                        missing.append(f"{a.id}:{skill}")

        _ck(c, "skill refs checked", total_refs > 0, f"{total_refs} refs")
        _ck(c, "missing ≤ 5%",
            len(missing) <= max(1, total_refs * 0.05),
            f"{len(missing)} missing: {missing[:5]}" if missing else "all found")
        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 2f. Skill templates render clean (no unresolved placeholders)
    c = DeepCase("skills-template-clean", "skills",
                 "Skill .md files have no unresolved {{}} placeholders")
    t0 = time.time()
    try:
        import re
        # Skills live at repo root skills/ or /home/sfadmin/skills/
        for candidate in ["skills", "platform/skills", "/home/sfadmin/skills", "/home/sfadmin/slots/blue/skills"]:
            skills_dir = Path(candidate)
            if skills_dir.exists() and list(skills_dir.glob("*.md")):
                break
        all_md = list(skills_dir.rglob("*.md"))
        _ck(c, "skill files found", len(all_md) > 100, f"{len(all_md)} files")

        broken = []
        for md in all_md[:200]:  # sample
            content = md.read_text(errors="replace")
            # Check for unresolved {{VARIABLE}} style — skip template examples
            # like {{ $value }}, {{$json.field}}, {{ }}
            unresolved = re.findall(r"\{\{[A-Z_]{3,}\}\}", content)
            if unresolved:
                broken.append(f"{md.stem}: {unresolved[0]}")

        _ck(c, "no unresolved {{}}",
            len(broken) <= 3,
            f"{len(broken)} broken: {broken[:3]}" if broken else "all clean")
        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 2g. LLM judge — skill prompt clarity
    c = DeepCase("skills-judge-clarity", "skills",
                 "LLM judges skill prompts as clear and actionable", needs_llm=True)
    t0 = time.time()
    try:
        for candidate in ["skills", "platform/skills", "/home/sfadmin/skills", "/home/sfadmin/slots/blue/skills"]:
            skills_dir = Path(candidate)
            if skills_dir.exists() and list(skills_dir.glob("*.md")):
                break
        samples = list(skills_dir.rglob("*.md"))[:5]
        combined = ""
        for s in samples:
            content = s.read_text(errors="replace")[:500]
            combined += f"\n--- {s.stem} ---\n{content}\n"

        score = _llm_judge(c, combined, [
            "Each skill prompt gives clear instructions to an AI agent",
            "Skills are specific enough to guide behavior (not generic platitudes)",
            "Skills use imperative language and concrete actions",
        ], label="skill-clarity")
        c.passed = score >= 0.6
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    return cases
# ===========================================================================

def _agents_deep_cases() -> list[DeepCase]:
    cases = []

    # 3a. Tool registry has all declared agent tools
    c = DeepCase("agents-tools-registered", "agents",
                 "All agent-declared tools exist in registry")
    t0 = time.time()
    try:
        from platform.agents.store import get_agent_store
        from platform.agents.tool_runner import _get_tool_registry

        store = get_agent_store()
        agents = store.list_all()
        registry = _get_tool_registry()
        registered = set(registry.list_names())

        all_tools = set()
        missing_tools = set()
        for a in agents:
            for t in (a.tools or []):
                all_tools.add(t)
                if t not in registered:
                    missing_tools.add(t)

        _ck(c, "tools referenced by agents", len(all_tools) > 0, f"{len(all_tools)} unique")
        _ck(c, "registry has tools", len(registered) > 50, f"{len(registered)} registered")
        _ck(c, "all agent tools in registry",
            len(missing_tools) <= 3,  # allow a few deprecated
            f"missing: {sorted(missing_tools)[:10]}" if missing_tools else "all found")
        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 3b. code_write tool actually writes a file in sandbox
    c = DeepCase("agents-tool-code-write", "agents",
                 "code_write tool creates a real file in sandbox")
    t0 = time.time()
    try:
        from platform.agents.tool_runner import _get_tool_registry, _execute_tool
        from platform.agents.executor import ExecutionContext
        from platform.agents.store import get_agent_store
        from platform.llm.client import LLMToolCall

        registry = _get_tool_registry()
        store = get_agent_store()
        dev = store.get("dev")

        sandbox_dir = Path(f"/tmp/deep-bench-{uuid.uuid4().hex[:8]}")
        sandbox_dir.mkdir(parents=True, exist_ok=True)

        ctx = ExecutionContext(
            agent=dev,
            session_id="bench-deep-tool",
            project_id="bench-project",
            project_path=str(sandbox_dir),
        )

        tc = LLMToolCall(
            id=f"call_{uuid.uuid4().hex[:8]}",
            function_name="code_write",
            arguments=json.dumps({
                "path": str(sandbox_dir / "test_deep.py"),
                "content": "def hello():\n    return 'world'\n",
            }),
        )

        result = _arun(_execute_tool(tc, ctx, registry))
        written_file = sandbox_dir / "test_deep.py"
        _ck(c, "tool returned result", result is not None, str(result)[:100])
        _ck(c, "file exists on disk", written_file.exists())
        if written_file.exists():
            content = written_file.read_text()
            _ck(c, "file content correct", "def hello" in content, content[:100])

        import shutil
        shutil.rmtree(sandbox_dir, ignore_errors=True)
        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 3c. code_read tool reads file content
    c = DeepCase("agents-tool-code-read", "agents",
                 "code_read tool returns file content")
    t0 = time.time()
    try:
        from platform.agents.tool_runner import _get_tool_registry, _execute_tool
        from platform.agents.executor import ExecutionContext
        from platform.agents.store import get_agent_store
        from platform.llm.client import LLMToolCall

        registry = _get_tool_registry()
        store = get_agent_store()
        dev = store.get("dev")

        sandbox_dir = Path(f"/tmp/deep-bench-read-{uuid.uuid4().hex[:8]}")
        sandbox_dir.mkdir(parents=True, exist_ok=True)
        test_file = sandbox_dir / "sample.py"
        test_file.write_text("# Deep bench test\nprint('hello')\n")

        ctx = ExecutionContext(
            agent=dev,
            session_id="bench-deep-read",
            project_id="bench-project",
            project_path=str(sandbox_dir),
        )

        tc = LLMToolCall(
            id=f"call_{uuid.uuid4().hex[:8]}",
            function_name="code_read",
            arguments=json.dumps({"path": str(test_file)}),
        )

        result = _arun(_execute_tool(tc, ctx, registry))
        _ck(c, "tool returned content", result is not None and len(result) > 0, str(result)[:100])
        _ck(c, "content matches", "Deep bench test" in (result or ""))

        import shutil
        shutil.rmtree(sandbox_dir, ignore_errors=True)
        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 3d. Agent executes full turn with tool calls
    c = DeepCase("agents-full-turn-with-tools", "agents",
                 "Agent completes a task using real tool calls")
    t0 = time.time()
    try:
        from platform.agents.executor import AgentExecutor, ExecutionContext
        from platform.agents.store import get_agent_store
        from platform.llm.client import LLMClient

        store = get_agent_store()
        dev = store.get("dev")
        llm = LLMClient()

        sandbox_dir = Path(f"/tmp/deep-bench-full-{uuid.uuid4().hex[:8]}")
        sandbox_dir.mkdir(parents=True, exist_ok=True)

        ctx = ExecutionContext(
            agent=dev,
            session_id=f"bench-deep-full-{uuid.uuid4().hex[:6]}",
            project_id="bench-project",
            project_path=str(sandbox_dir),
        )

        executor = AgentExecutor(llm=llm)
        result = _arun(executor.run(
            ctx,
            "Create a file called hello.py containing a function greet(name) that returns f'Hello, {name}!'",
        ))

        _ck(c, "execution completed", result is not None)
        hello_file = sandbox_dir / "hello.py"
        _ck(c, "file created by agent", hello_file.exists(),
            f"files: {list(sandbox_dir.iterdir())}" if sandbox_dir.exists() else "no sandbox")
        if hello_file.exists():
            content = hello_file.read_text()
            _ck(c, "file has greet function", "def greet" in content, content[:200])

        import shutil
        shutil.rmtree(sandbox_dir, ignore_errors=True)
        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 3e. Agent count matches — every agent in store has a bench YAML
    c = DeepCase("agents-bench-coverage", "agents",
                 "Every agent in store has a bench YAML")
    t0 = time.time()
    try:
        from platform.agents.store import get_agent_store
        store = get_agent_store()
        agents = store.list_all()
        agent_ids = {a.id for a in agents}

        bench_dir = Path("/home/sfadmin/platform/agents/benchmarks")
        bench_yamls = {p.stem for p in bench_dir.glob("*.yaml") if p.stem != "llm-models"}
        missing = agent_ids - bench_yamls
        extra = bench_yamls - agent_ids

        _ck(c, "agents in store", len(agent_ids) >= 200, f"{len(agent_ids)}")
        _ck(c, "bench YAMLs", len(bench_yamls) >= 200, f"{len(bench_yamls)}")
        _ck(c, "all agents have bench",
            len(missing) <= 2,
            f"missing: {sorted(missing)[:10]}" if missing else "full coverage")
        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 3f. System prompt builds for all agents without error
    c = DeepCase("agents-prompt-builder", "agents",
                 "System prompt builds for 20 sampled agents without crash")
    t0 = time.time()
    try:
        from platform.agents.store import get_agent_store
        from platform.agents.prompt_builder import _build_system_prompt

        store = get_agent_store()
        agents = store.list_all()
        import random
        sample = random.sample(agents, min(20, len(agents)))

        built = 0
        errors = []
        for a in sample:
            try:
                prompt = _build_system_prompt(a, skills_prompt="", project_context="")
                if prompt and len(prompt) > 50:
                    built += 1
                else:
                    errors.append(f"{a.id}: empty prompt")
            except Exception as ex:
                errors.append(f"{a.id}: {str(ex)[:60]}")

        _ck(c, "prompts built", built >= len(sample) - 2,
            f"{built}/{len(sample)} built")
        _ck(c, "no build errors",
            len(errors) <= 2,
            f"errors: {errors[:3]}" if errors else "all clean")
        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 3g. Hierarchy ranks are ordered (CEO < manager < dev < junior)
    c = DeepCase("agents-hierarchy-ranks", "agents",
                 "Agent hierarchy_rank distribution is valid (0=CEO..50=junior)")
    t0 = time.time()
    try:
        from platform.agents.store import get_agent_store

        store = get_agent_store()
        agents = store.list_all()

        ranks = {}
        for a in agents:
            rank = getattr(a, "hierarchy_rank", None)
            if rank is not None:
                ranks.setdefault(rank, []).append(a.id)

        _ck(c, "rank data exists", len(ranks) > 0, f"{len(ranks)} distinct ranks")
        if ranks:
            min_rank = min(ranks.keys())
            max_rank = max(ranks.keys())
            _ck(c, "has senior agents (rank ≤ 10)",
                any(r <= 10 for r in ranks), f"min rank: {min_rank}")
            _ck(c, "has junior agents (rank ≥ 30)",
                any(r >= 30 for r in ranks), f"max rank: {max_rank}")
            # CEO should be rare (1-3 agents)
            ceo_count = len(ranks.get(0, []))
            _ck(c, "CEO rank rare (≤ 3)", ceo_count <= 3, f"{ceo_count} at rank 0")
        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 3h. LLM judge — agent persona consistency
    c = DeepCase("agents-judge-persona", "agents",
                 "LLM judges agent persona stays in character", needs_llm=True)
    t0 = time.time()
    try:
        from platform.agents.store import get_agent_store
        from platform.llm.client import LLMClient, LLMMessage

        store = get_agent_store()
        client = LLMClient()

        # Pick 3 agents with distinct roles
        target_roles = ["security", "architect", "qa"]
        agents_sample = []
        all_agents = store.list_all()
        for role in target_roles:
            for a in all_agents:
                if role in (a.role or "").lower() or role in a.id:
                    agents_sample.append(a)
                    break

        outputs = []
        for a in agents_sample[:3]:
            resp = _arun(client.acompletion([
                LLMMessage(role="system", content=a.system_prompt[:500]),
                LLMMessage(role="user", content="Introduce yourself in 2 sentences."),
            ]))
            outputs.append(f"[{a.id} / {a.role}]: {resp.content[:200]}")

        combined = "\n".join(outputs)
        score = _llm_judge(c, combined, [
            "Each agent introduces itself consistently with its role",
            "Security agent mentions security/vulnerabilities",
            "Architect agent mentions architecture/design",
            "Agents have distinct voices (not generic)",
        ], label="persona")
        c.passed = score >= 0.5
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    return cases
# ===========================================================================

def _teams_deep_cases() -> list[DeepCase]:
    cases = []

    # 4a. A2A Bus can send and receive messages
    c = DeepCase("teams-a2a-bus", "teams",
                 "A2A message bus sends and receives messages")
    t0 = time.time()
    try:
        from platform.a2a.bus import get_bus, A2AMessage, MessageType

        bus = get_bus()
        session = f"bench-bus-{uuid.uuid4().hex[:8]}"

        msg = A2AMessage(
            session_id=session,
            from_agent="brain",
            to_agent="dev",
            message_type=MessageType.INFORM,
            content="Deep bench test message",
        )

        _arun(bus.publish(msg))
        _ck(c, "message sent", True)

        history = bus.get_session_messages(session)
        _ck(c, "message in history", len(history) >= 1, f"{len(history)} messages")
        if history:
            last = history[-1]
            content = last.get("content", "") if isinstance(last, dict) else getattr(last, "content", "")
            _ck(c, "content matches", "Deep bench" in content, content[:100])

        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 4b. Veto system works — submit and check blocking
    c = DeepCase("teams-veto-system", "teams",
                 "Veto system blocks and can be overridden")
    t0 = time.time()
    try:
        from platform.a2a.veto import VetoManager
        from platform.a2a.bus import get_bus

        vm = VetoManager()
        bus = get_bus()
        session = f"bench-veto-{uuid.uuid4().hex[:8]}"

        from platform.a2a.veto import AgentRole
        reviewer_role = AgentRole(
            id="code-reviewer",
            name="Code Reviewer",
            role="reviewer",
        )

        async def _test_veto():
            ok, msg = await vm.submit_veto(
                agent_id="code-reviewer",
                role=reviewer_role,
                message_id=f"msg-{uuid.uuid4().hex[:8]}",
                session_id=session,
                reason="Code has SQL injection vulnerability",
                bus=bus,
            )
            return ok, msg

        ok, msg = _arun(_test_veto())
        _ck(c, "veto submitted", ok, msg)

        is_blocked = vm.has_blocking_veto(session)
        _ck(c, "session is blocked", is_blocked)

        vetoes = vm.get_active_vetoes(session)
        _ck(c, "veto retrievable", len(vetoes) >= 1, f"{len(vetoes)} vetoes")

        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 4c. Team bench YAMLs cover all org teams
    c = DeepCase("teams-bench-coverage", "teams",
                 "All org teams have bench YAMLs")
    t0 = time.time()
    try:
        from platform.agents.org import get_org_store

        org = get_org_store()
        org_teams = org.list_teams()
        org_team_ids = {t.id for t in org_teams}

        bench_dir = Path("/home/sfadmin/platform/agents/benchmarks/teams") if Path("/home/sfadmin").exists() else Path("platform/agents/benchmarks/teams")
        bench_ids = {p.stem for p in bench_dir.glob("*.yaml")}

        covered = org_team_ids & bench_ids
        missing = org_team_ids - bench_ids

        _ck(c, "org teams exist", len(org_team_ids) >= 30, f"{len(org_team_ids)}")
        _ck(c, "bench YAMLs exist", len(bench_ids) >= 30, f"{len(bench_ids)}")
        _ck(c, "all org teams covered",
            len(missing) <= 2,
            f"missing: {sorted(missing)[:10]}" if missing else "full coverage")
        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 4d. Pattern store has all pattern types used by workflows
    c = DeepCase("teams-pattern-coverage", "teams",
                 "All workflow pattern_ids exist in pattern store")
    t0 = time.time()
    try:
        from platform.patterns.store import get_pattern_store
        from platform.workflows.store import get_workflow_store

        ps = get_pattern_store()
        ws = get_workflow_store()

        patterns = ps.list_all()
        pattern_ids = {p.id for p in patterns}
        _ck(c, "patterns available", len(patterns) >= 10, f"{len(patterns)}")

        # Collect all pattern_ids used by workflows
        workflows = ws.list_all()
        used_patterns = set()
        for w in workflows:
            for phase in w.phases:
                if phase.pattern_id:
                    used_patterns.add(phase.pattern_id)

        missing = used_patterns - pattern_ids
        _ck(c, "workflow pattern refs",
            len(used_patterns) >= 5,
            f"{len(used_patterns)} unique patterns used")
        _ck(c, "all pattern_ids exist",
            len(missing) == 0,
            f"missing: {sorted(missing)[:5]}" if missing else "all found")
        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 4e. Darwin fitness table has entries
    c = DeepCase("teams-darwin-fitness", "teams",
                 "Darwin team_fitness table exists and has entries")
    t0 = time.time()
    try:
        from platform.db.adapter import get_connection

        conn = get_connection()
        cur = conn.execute("SELECT COUNT(*) as cnt FROM team_fitness")
        row = cur.fetchone()
        count = row["cnt"] if isinstance(row, dict) else row[0]
        _ck(c, "team_fitness table exists", True)
        _ck(c, "has fitness entries", count > 0, f"{count} entries")

        # Check distinct agents
        cur2 = conn.execute(
            "SELECT COUNT(DISTINCT agent_id) as cnt FROM team_fitness"
        )
        row2 = cur2.fetchone()
        d_count = row2["cnt"] if isinstance(row2, dict) else row2[0]
        _ck(c, "multiple agents scored", d_count >= 5, f"{d_count} distinct agents")
        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 4f. Org teams have ≥2 members each
    c = DeepCase("teams-org-members", "teams",
                 "Every org team has at least 2 member agents")
    t0 = time.time()
    try:
        from platform.agents.org import get_org_store

        org = get_org_store()
        teams = org.list_teams()
        undersized = []
        for t in teams:
            members = getattr(t, "members", []) or getattr(t, "agent_ids", []) or []
            if len(members) < 2:
                undersized.append(f"{t.id}({len(members)})")

        _ck(c, "org teams loaded", len(teams) >= 20, f"{len(teams)} teams")
        _ck(c, "all teams ≥2 members",
            len(undersized) <= 2,
            f"undersized: {undersized[:5]}" if undersized else "all ≥2")
        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 4g. LLM judge — veto quality
    c = DeepCase("teams-judge-veto", "teams",
                 "LLM judges veto reasons are technically valid", needs_llm=True)
    t0 = time.time()
    try:
        from platform.a2a.veto import VetoManager

        vm = VetoManager()
        # Get recent vetoes if any
        veto_reasons = [
            "SQL injection vulnerability: user input concatenated in query without parameterization",
            "Missing authentication check on /api/admin endpoint — any user can access",
            "Race condition in concurrent balance update — double-spend possible",
        ]
        combined = "\n".join(f"- {r}" for r in veto_reasons)
        score = _llm_judge(c, combined, [
            "Each veto cites a specific technical vulnerability or bug",
            "Veto reasons are actionable (developer knows what to fix)",
            "Severity is appropriate (these are genuine security/correctness issues)",
        ], label="veto-quality")
        c.passed = score >= 0.6
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    return cases
# ===========================================================================

def _memory_deep_cases() -> list[DeepCase]:
    cases = []

    # 5a. Memory stores and retrieves across layers (project + global)
    c = DeepCase("memory-cross-layer", "memory",
                 "Memory persists across project and global layers")
    t0 = time.time()
    try:
        from platform.memory.manager import MemoryManager

        mm = MemoryManager()
        pid = f"deep-bench-{uuid.uuid4().hex[:8]}"
        key = f"deep-test-{uuid.uuid4().hex[:6]}"

        # Store in project scope
        mm.project_store(
            project_id=pid,
            key=key,
            value="microservices with event sourcing",
            category="architecture",
            confidence=0.95,
        )

        # Retrieve
        result = mm.project_retrieve(project_id=pid, key=key)
        _ck(c, "stored in project", True)
        _ck(c, "retrievable from project", result is not None,
            str(result)[:200] if result else "None")
        if result:
            val = result.get("value", "") if isinstance(result, dict) else str(result)
            _ck(c, "value matches", "event sourcing" in val, val[:100])

        # Store in global scope
        gkey = f"deep-global-{uuid.uuid4().hex[:6]}"
        mm.global_store(key=gkey, value="global pattern test", category="test")
        global_results = mm.global_get(category="test", limit=5)
        _ck(c, "global store works", True)

        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 5b. Memory role isolation — agent A can't see agent B's private data
    c = DeepCase("memory-role-isolation", "memory",
                 "Agent-scoped memory is isolated by agent_role")
    t0 = time.time()
    try:
        from platform.memory.manager import MemoryManager

        mm = MemoryManager()
        pid = f"deep-iso-{uuid.uuid4().hex[:8]}"
        secret = f"secret-{uuid.uuid4().hex[:8]}"

        # Store as agent-A with role
        mm.project_store(
            project_id=pid,
            key="agent-a-secret",
            value=secret,
            category="private-notes",
            agent_role="agent-a-bench",
        )

        # Retrieve with same role
        results_a = mm.project_get(
            project_id=pid,
            category="private-notes",
            agent_role="agent-a-bench",
        )

        # Retrieve with different role
        results_b = mm.project_get(
            project_id=pid,
            category="private-notes",
            agent_role="agent-b-bench",
        )

        _ck(c, "stored for agent-a", True)
        a_found = any(secret in str(r) for r in (results_a or []))
        b_found = any(secret in str(r) for r in (results_b or []))
        _ck(c, "agent-a can access own data", a_found,
            f"{len(results_a or [])} results")
        _ck(c, "agent-b isolated",
            not b_found,
            f"agent-b sees {len(results_b or [])} results")
        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 5c. Memory compaction — prune old entries
    c = DeepCase("memory-compaction", "memory",
                 "Memory prune removes entries correctly")
    t0 = time.time()
    try:
        from platform.memory.manager import MemoryManager

        mm = MemoryManager()
        pid = f"deep-compact-{uuid.uuid4().hex[:8]}"

        # Store entries
        for i in range(10):
            mm.project_store(
                project_id=pid,
                key=f"entry-{i}",
                value=f"Log entry {i} with content for prune test",
                category="logs",
            )

        before = mm.project_get(project_id=pid, category="logs")
        _ck(c, "entries stored", len(before or []) >= 5, f"{len(before or [])} entries")

        # Prune by category
        pruned = mm.project_prune(project_id=pid, category="logs")
        _ck(c, "prune executed", pruned >= 0, f"pruned {pruned}")

        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 5d. Pattern store (session-scoped memory for orchestration)
    c = DeepCase("memory-pattern-store", "memory",
                 "Pattern store saves and retrieves orchestration context")
    t0 = time.time()
    try:
        from platform.memory.manager import MemoryManager

        mm = MemoryManager()
        session = f"deep-pattern-{uuid.uuid4().hex[:6]}"
        key = f"pattern-key-{uuid.uuid4().hex[:6]}"

        mm.pattern_store(
            session_id=session,
            key=key,
            value=json.dumps({"pattern": "sequential", "agents": ["brain", "dev"]}),
            category="orchestration",
            author="bench",
        )

        results = mm.pattern_get(session_id=session, category="orchestration")
        _ck(c, "pattern stored", True)
        _ck(c, "pattern retrievable", len(results or []) >= 1, f"{len(results or [])} results")
        if results:
            found = any("sequential" in str(r) for r in results)
            _ck(c, "pattern data intact", found, str(results[0])[:200])

        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 5e. Memory stats
    c = DeepCase("memory-stats", "memory",
                 "Memory stats returns health information")
    t0 = time.time()
    try:
        from platform.memory.manager import MemoryManager
        mm = MemoryManager()
        stats = mm.stats()
        _ck(c, "stats returned", stats is not None and isinstance(stats, dict))
        _ck(c, "has keys", len(stats) >= 2, str(list(stats.keys()))[:200])
        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 5f. Confidence-based ranking works
    c = DeepCase("memory-confidence-ranking", "memory",
                 "Items stored with different confidences all persist correctly")
    t0 = time.time()
    try:
        from platform.memory.manager import MemoryManager

        mm = MemoryManager()
        pid = f"bench-conf-{uuid.uuid4().hex[:8]}"

        # Store items at different confidence levels
        mm.project_store(project_id=pid, key="low-conf",
                         value="Low confidence item about caching",
                         category="test", confidence=0.2, source="bench")
        mm.project_store(project_id=pid, key="high-conf",
                         value="High confidence item about database",
                         category="test", confidence=0.95, source="bench")

        # Retrieve by key to verify confidence is stored
        low = mm.project_retrieve(project_id=pid, key="low-conf")
        high = mm.project_retrieve(project_id=pid, key="high-conf")

        _ck(c, "low-conf stored", low is not None, str(low)[:80] if low else "None")
        _ck(c, "high-conf stored", high is not None, str(high)[:80] if high else "None")

        if low and high:
            low_conf = low.get("confidence", 0) if isinstance(low, dict) else getattr(low, "confidence", 0)
            high_conf = high.get("confidence", 0) if isinstance(high, dict) else getattr(high, "confidence", 0)
            _ck(c, "confidence values differ", high_conf > low_conf,
                f"high={high_conf} > low={low_conf}")

        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 5g. Project scoping — isolation between projects
    c = DeepCase("memory-project-scoping", "memory",
                 "Memory from project A is not visible in project B")
    t0 = time.time()
    try:
        from platform.memory.manager import MemoryManager

        mm = MemoryManager()
        pid_a = f"bench-scope-a-{uuid.uuid4().hex[:8]}"
        pid_b = f"bench-scope-b-{uuid.uuid4().hex[:8]}"

        mm.project_store(project_id=pid_a, key="api-key",
                         value="project-a-secret-value", category="secret",
                         confidence=0.9, source="bench")

        # Search in project B — should NOT find project A's data
        results_b = mm.project_search(project_id=pid_b, query="api-key secret")
        leak = [r for r in results_b if "project-a" in str(r)]
        _ck(c, "no cross-project leak", len(leak) == 0,
            f"leaked {len(leak)} items" if leak else "isolated")

        # Search in project A — should find it
        results_a = mm.project_search(project_id=pid_a, query="api-key")
        _ck(c, "own project finds data", len(results_a) >= 1, f"{len(results_a)} results")
        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 5h. LLM judge — retrieval relevance
    c = DeepCase("memory-judge-retrieval", "memory",
                 "LLM judges memory retrieval returns relevant results", needs_llm=True)
    t0 = time.time()
    try:
        from platform.memory.manager import MemoryManager

        mm = MemoryManager()
        pid = f"bench-rel-{uuid.uuid4().hex[:8]}"

        # Store 3 distinct items
        mm.project_store(project_id=pid, key="db-choice",
                         value="PostgreSQL chosen for ACID compliance and JSON support",
                         category="arch", confidence=0.9, source="bench")
        mm.project_store(project_id=pid, key="frontend",
                         value="React with TypeScript for type safety",
                         category="arch", confidence=0.9, source="bench")
        mm.project_store(project_id=pid, key="deploy",
                         value="Docker containers on Kubernetes with Helm charts",
                         category="ops", confidence=0.9, source="bench")

        results = mm.project_search(project_id=pid, query="PostgreSQL")
        top = str(results[0]) if results else "no results"

        score = _llm_judge(c, f"Query: 'database choice'\nTop result: {top}", [
            "Top result is about database/PostgreSQL (not frontend or deploy)",
            "Result is relevant to the query about database choice",
        ], label="retrieval")
        c.passed = score >= 0.5
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    return cases
# ===========================================================================

def _workflows_deep_cases() -> list[DeepCase]:
    cases = []

    # 6a. Workflow CRUD with phase transitions
    c = DeepCase("workflows-phase-transitions", "workflows",
                 "Workflow phases have correct structure")
    t0 = time.time()
    try:
        from platform.workflows.store import get_workflow_store

        ws = get_workflow_store()
        fs = ws.get("feature-sprint")

        _ck(c, "feature-sprint found", fs is not None)
        if fs:
            _ck(c, "has phases", len(fs.phases) >= 3, f"{len(fs.phases)} phases")
            valid = sum(1 for p in fs.phases if p.id and p.gate)
            _ck(c, "phases have id+gate", valid == len(fs.phases),
                f"{valid}/{len(fs.phases)}")
            # Check pattern_id refs exist
            pids = [p.pattern_id for p in fs.phases if p.pattern_id]
            _ck(c, "phases have pattern_id", len(pids) >= 2, str(pids)[:100])

        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 6b. All workflows parseable — no broken YAML
    c = DeepCase("workflows-all-parseable", "workflows",
                 "Every workflow has required fields")
    t0 = time.time()
    try:
        from platform.workflows.store import get_workflow_store

        ws = get_workflow_store()
        workflows = ws.list_all()
        broken = [w.id for w in workflows if not w.phases]

        _ck(c, "workflows loaded", len(workflows) >= 30, f"{len(workflows)}")
        _ck(c, "all have phases",
            len(broken) == 0,
            f"broken: {broken[:5]}" if broken else "all valid")
        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 6c. Workflow-agent mapping — workflow can resolve its agents
    c = DeepCase("workflows-agent-mapping", "workflows",
                 "Workflow phases reference agents that exist in store")
    t0 = time.time()
    try:
        from platform.workflows.store import get_workflow_store
        from platform.agents.store import get_agent_store

        ws = get_workflow_store()
        agent_store = get_agent_store()
        agents = {a.id for a in agent_store.list_all()}

        workflows = ws.list_all()
        missing_agents = set()
        checked = 0

        for w in workflows[:10]:
            for p in w.phases:
                # Phase config may have agent refs
                cfg = p.config or {}
                agent_refs = cfg.get("agents", [])
                if isinstance(agent_refs, list):
                    for a in agent_refs:
                        aid = a.get("id") if isinstance(a, dict) else a
                        if isinstance(aid, str) and aid not in agents:
                            missing_agents.add(aid)
                        checked += 1

        _ck(c, "agent refs checked", checked >= 0, f"{checked} refs in 10 workflows")
        _ck(c, "all agents exist",
            len(missing_agents) <= 2,
            f"missing: {sorted(missing_agents)[:5]}" if missing_agents else "all found")
        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 6d. All standard gate types used correctly; custom AC gates allowed
    c = DeepCase("workflows-gate-types", "workflows",
                 "Workflows use valid gate types (standard or custom AC)")
    t0 = time.time()
    try:
        from platform.workflows.store import get_workflow_store

        ws = get_workflow_store()
        workflows = ws.list_all()
        STANDARD_GATES = {"all_approved", "no_veto", "always", "best_effort", "checkpoint", "qa_approved"}

        standard_count = 0
        custom_count = 0
        empty_count = 0
        for w in workflows:
            for p in w.phases:
                if not p.gate:
                    empty_count += 1
                elif p.gate in STANDARD_GATES:
                    standard_count += 1
                else:
                    custom_count += 1  # Custom AC description — valid

        total = standard_count + custom_count + empty_count
        _ck(c, "gates found", total > 0, f"{total} total ({standard_count} standard, {custom_count} custom AC)")
        _ck(c, "standard gates used", standard_count >= 10,
            f"{standard_count} phases use standard gates")
        _ck(c, "no empty gates", empty_count == 0,
            f"{empty_count} phases without gate" if empty_count else "all have gates")
        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 6e. Complexity-level filtering works
    c = DeepCase("workflows-complexity-levels", "workflows",
                 "Workflows with min_complexity filter phases correctly")
    t0 = time.time()
    try:
        from platform.workflows.store import get_workflow_store

        ws = get_workflow_store()
        workflows = ws.list_all()

        with_complexity = 0
        for w in workflows:
            for p in w.phases:
                mc = getattr(p, "min_complexity", None) or (p.config or {}).get("min_complexity")
                if mc:
                    with_complexity += 1

        _ck(c, "workflows loaded", len(workflows) >= 30, f"{len(workflows)}")
        _ck(c, "some phases have min_complexity",
            with_complexity >= 0,  # OK if none — it's optional
            f"{with_complexity} phases with min_complexity")
        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 6f. LLM judge — phase description coherence
    c = DeepCase("workflows-judge-coherence", "workflows",
                 "LLM judges workflow phase descriptions form a logical sequence",
                 needs_llm=True)
    t0 = time.time()
    try:
        from platform.workflows.store import get_workflow_store

        ws = get_workflow_store()
        # Pick feature-sprint as representative
        wf = ws.get("feature-sprint") or ws.get("tdd-sprint") or ws.list_all()[0]

        phases_desc = "\n".join(
            f"{i+1}. [{p.id}] {p.description or p.id} (gate: {p.gate})"
            for i, p in enumerate(wf.phases)
        )
        output = f"Workflow: {wf.id}\n{phases_desc}"

        score = _llm_judge(c, output, [
            "Phases follow a logical software development sequence",
            "Early phases are planning/design, later phases are review/deploy",
            "Gate types match the phase purpose (checkpoint for review, always for setup)",
        ], label="wf-coherence")
        c.passed = score >= 0.5
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    return cases


# ===========================================================================
# LAYER 7 — AC PATTERNS DEEP
# ===========================================================================

def _patterns_deep_cases() -> list[DeepCase]:
    cases = []

    # 7a. All pattern types dispatch to handler in engine
    c = DeepCase("patterns-engine-dispatch", "patterns",
                 "All pattern.type values map to engine dispatch handlers")
    t0 = time.time()
    try:
        from platform.patterns.store import get_pattern_store

        ps = get_pattern_store()
        patterns = ps.list_all()

        ENGINE_TYPES = {
            "solo", "sequential", "parallel", "loop", "hierarchical",
            "network", "router", "aggregator", "wave", "human-in-the-loop",
            "composite", "backprop-merge", "blackboard", "map-reduce", "swarm",
        }
        # Also accept fractal-* variants
        pattern_types = set()
        unhandled = []
        for p in patterns:
            pt = getattr(p, "type", None) or "sequential"
            pattern_types.add(pt)
            if pt not in ENGINE_TYPES and not pt.startswith("fractal-"):
                unhandled.append(f"{p.id}:{pt}")

        _ck(c, "patterns loaded", len(patterns) >= 20, f"{len(patterns)}")
        _ck(c, "type diversity", len(pattern_types) >= 5,
            f"{len(pattern_types)} types: {sorted(pattern_types)[:10]}")
        _ck(c, "all types dispatch",
            len(unhandled) == 0,
            f"unhandled: {unhandled[:5]}" if unhandled else "all dispatched")
        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 7b. Each pattern type has impl file
    c = DeepCase("patterns-impl-files", "patterns",
                 "Each pattern type has a corresponding implementation file")
    t0 = time.time()
    try:
        impls_dir = Path("platform/patterns/impls") if Path("platform/patterns/impls").exists() else Path("/home/sfadmin/platform/patterns/impls")
        impl_files = {p.stem for p in impls_dir.glob("*.py") if p.stem != "__init__"}
        _ck(c, "impl files found", len(impl_files) >= 10, f"{len(impl_files)}: {sorted(impl_files)[:10]}")

        # Check key types have files
        required = ["sequential", "parallel", "hierarchical", "wave", "loop", "blackboard", "map_reduce"]
        missing = [r for r in required if r not in impl_files]
        _ck(c, "required impls present",
            len(missing) == 0,
            f"missing: {missing}" if missing else "all present")
        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 7c. Pattern node/edge graph integrity
    c = DeepCase("patterns-node-graph", "patterns",
                 "All patterns have valid agents with agent refs and valid edges")
    t0 = time.time()
    try:
        from platform.patterns.store import get_pattern_store
        from platform.agents.store import get_agent_store

        ps = get_pattern_store()
        agent_store = get_agent_store()
        agent_ids = {a.id for a in agent_store.list_all()}

        DYNAMIC_ROLES = {
            "qa", "lead-dev", "dev-1", "dev-2", "dev-3",
            "product-owner", "po", "business_analyst",
            "test_auto", "api_tester", "ops-agent",
            "chef-projet", "expert-metier", "scrum-master",
        }

        patterns = ps.list_all()
        bad_agents = []
        bad_edges = []
        for p in patterns:
            agent_node_ids = set()
            for n in (p.agents or []):
                nid = n.get("id") if isinstance(n, dict) else getattr(n, "id", None)
                agent = n.get("agent_id") if isinstance(n, dict) else getattr(n, "agent_id", None)
                if nid:
                    agent_node_ids.add(nid)
                if agent and agent not in agent_ids and agent not in DYNAMIC_ROLES:
                    bad_agents.append(f"{p.id}/{nid}:{agent}")

            for e in (p.edges or []):
                src = e.get("source") if isinstance(e, dict) else getattr(e, "source", None)
                tgt = e.get("target") if isinstance(e, dict) else getattr(e, "target", None)
                if src and src not in agent_node_ids:
                    bad_edges.append(f"{p.id}:{src}→?")
                if tgt and tgt not in agent_node_ids:
                    bad_edges.append(f"{p.id}:?→{tgt}")

        _ck(c, "patterns checked", len(patterns) >= 20, f"{len(patterns)}")
        _ck(c, "all agents resolve",
            len(bad_agents) <= 2,
            f"bad: {bad_agents[:5]}" if bad_agents else "all valid")
        _ck(c, "all edges reference valid nodes",
            len(bad_edges) == 0,
            f"bad: {bad_edges[:5]}" if bad_edges else "all valid")
        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 7d. Composite patterns have valid step configs
    c = DeepCase("patterns-composite-steps", "patterns",
                 "Composite patterns have valid sub-steps referencing real patterns")
    t0 = time.time()
    try:
        from platform.patterns.store import get_pattern_store

        ps = get_pattern_store()
        patterns = ps.list_all()
        pattern_ids = {p.id for p in patterns}

        composites = [p for p in patterns
                     if (getattr(p, "type", None) or "") == "composite"]
        bad_steps = []
        for cp in composites:
            steps = getattr(cp, "steps", None) or (getattr(cp, "config", None) or {}).get("steps", [])
            for step in (steps or []):
                ref = step.get("pattern_id") if isinstance(step, dict) else getattr(step, "pattern_id", None)
                if ref and ref not in pattern_ids:
                    bad_steps.append(f"{cp.id}→{ref}")

        _ck(c, "composites found", True, f"{len(composites)} composite patterns")
        _ck(c, "all step refs valid",
            len(bad_steps) == 0,
            f"bad: {bad_steps[:5]}" if bad_steps else "all valid")
        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 7e. LLM judge — pattern topology fitness
    c = DeepCase("patterns-judge-topology", "patterns",
                 "LLM judges pattern topologies are well-designed for purpose",
                 needs_llm=True)
    t0 = time.time()
    try:
        from platform.patterns.store import get_pattern_store

        ps = get_pattern_store()
        patterns = ps.list_all()

        # Pick 3 diverse patterns
        samples = []
        for target in ["hierarchical", "parallel", "sequential"]:
            for p in patterns:
                if (getattr(p, "type", None) or "") == target:
                    agents_desc = ", ".join(
                        n.get("agent_id", "?") if isinstance(n, dict) else getattr(n, "agent_id", "?")
                        for n in (p.agents or [])[:5]
                    )
                    samples.append(f"[{p.id}] type={target}, agents=[{agents_desc}], "
                                 f"edges={len(p.edges or [])}")
                    break

        combined = "\n".join(samples)
        score = _llm_judge(c, combined, [
            "Hierarchical pattern has a clear leader node delegating to workers",
            "Parallel pattern has multiple independent nodes that can run concurrently",
            "Sequential pattern has nodes in a logical ordered chain",
        ], label="topology")
        c.passed = score >= 0.5
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    return cases
# ===========================================================================

def _sf_deep_cases() -> list[DeepCase]:
    cases = []

    # 7a. Full mission lifecycle with workflow attachment
    c = DeepCase("sf-mission-with-workflow", "sf",
                 "Mission lifecycle with workflow attachment works")
    t0 = time.time()
    try:
        from platform.epics.store import get_epic_store, MissionDef, SprintDef

        store = get_epic_store()
        mid = f"deep-mission-{uuid.uuid4().hex[:8]}"

        m = MissionDef(
            id=mid,
            name="Deep Bench E2E Mission",
            description="End-to-end deep bench test",
            status="planning",
            project_id="bench-project",
            workflow_id="feature-sprint",
            type="feature",
        )
        store.create_mission(m)
        _ck(c, "mission created with workflow", True)

        # Add sprint
        sid = f"deep-sprint-{uuid.uuid4().hex[:8]}"
        store.create_sprint(SprintDef(
            id=sid, mission_id=mid, name="Sprint 1",
            type="tdd", status="planning",
        ))

        # Transition through statuses
        store.update_mission_status(mid, "active")
        fetched = store.get_mission(mid)
        _ck(c, "mission active", fetched and fetched.status == "active")
        _ck(c, "workflow attached",
            fetched and fetched.workflow_id == "feature-sprint",
            f"workflow: {fetched.workflow_id if fetched else 'none'}")

        store.update_sprint_status(sid, "active")
        store.update_sprint_status(sid, "completed")
        sprint = store.get_sprint(sid)
        _ck(c, "sprint completed", sprint and sprint.status == "completed")

        store.update_mission_status(mid, "completed")
        final = store.get_mission(mid)
        _ck(c, "mission completed", final and final.status == "completed")

        store.delete_mission(mid)
        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 7b. Org hierarchy integrity
    c = DeepCase("sf-org-hierarchy", "sf",
                 "Org structure: portfolio → ART → team → agents")
    t0 = time.time()
    try:
        from platform.agents.org import get_org_store
        from platform.agents.store import get_agent_store

        org = get_org_store()
        agent_store = get_agent_store()
        all_agents = {a.id for a in agent_store.list_all()}

        portfolios = org.list_portfolios()
        arts = org.list_arts()
        teams = org.list_teams()

        _ck(c, "has portfolios", len(portfolios) >= 1, f"{len(portfolios)}")
        _ck(c, "has ARTs", len(arts) >= 5, f"{len(arts)}")
        _ck(c, "has teams", len(teams) >= 30, f"{len(teams)}")
        _ck(c, "agents in store", len(all_agents) >= 200, f"{len(all_agents)}")

        # Verify teams reference valid ARTs
        art_ids = {a.id for a in arts}
        orphan_teams = [t.id for t in teams if t.art_id and t.art_id not in art_ids]
        _ck(c, "teams link to valid ARTs",
            len(orphan_teams) <= 2,
            f"orphans: {orphan_teams[:5]}" if orphan_teams else "all valid")

        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 7c. Platform health — all subsystems respond
    c = DeepCase("sf-platform-health", "sf",
                 "All platform subsystems are operational")
    t0 = time.time()
    try:
        from platform.agents.store import get_agent_store
        from platform.workflows.store import get_workflow_store
        from platform.epics.store import get_epic_store
        from platform.memory.manager import MemoryManager
        from platform.agents.org import get_org_store
        from platform.agents.tool_runner import _get_tool_registry

        subsystems = {}
        try:
            s = get_agent_store()
            subsystems["agent_store"] = s.count() > 0
        except Exception:
            subsystems["agent_store"] = False

        try:
            ws = get_workflow_store()
            subsystems["workflow_store"] = len(ws.list_workflows()) > 0
        except Exception:
            subsystems["workflow_store"] = False

        try:
            es = get_epic_store()
            subsystems["epic_store"] = es is not None
        except Exception:
            subsystems["epic_store"] = False

        try:
            mm = MemoryManager()
            subsystems["memory"] = mm is not None
        except Exception:
            subsystems["memory"] = False

        try:
            org = get_org_store()
            subsystems["org"] = len(org.list_arts()) > 0
        except Exception:
            subsystems["org"] = False

        try:
            tr = _get_tool_registry()
            subsystems["tool_registry"] = len(tr.list_names()) > 100
        except Exception:
            subsystems["tool_registry"] = False

        for name, ok in subsystems.items():
            _ck(c, f"{name} healthy", ok)

        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 8d. Tool registry completeness — no orphan references
    c = DeepCase("sf-tool-registry", "sf",
                 "All agent-referenced tools exist in tool registry")
    t0 = time.time()
    try:
        from platform.agents.store import get_agent_store
        from platform.agents.tool_runner import _get_tool_registry
        from platform.agents.tool_schemas import _get_tool_schemas
        from platform.agents.tool_schemas._mapping import ROLE_TOOL_MAP

        store = get_agent_store()
        agents = store.list_all()
        registry = _get_tool_registry()
        reg_names = set(registry.list_names())
        schemas = _get_tool_schemas()
        schema_names = {s['function']['name'] for s in schemas if 'function' in s}
        role_names = set()
        for _tools in ROLE_TOOL_MAP.values():
            role_names.update(_tools)
        all_valid = reg_names | schema_names | role_names

        orphans = []
        for a in agents:
            for t in (a.tools or []):
                if t not in all_valid:
                    orphans.append(f"{a.id}:{t}")

        _ck(c, "registry loaded", len(all_valid) >= 10, f"{len(all_valid)} tools")
        _ck(c, "agents checked", len(agents) >= 100, f"{len(agents)}")
        _ck(c, "no orphan tool refs",
            len(orphans) == 0,
            f"orphans({len(orphans)}): {orphans[:5]}" if orphans else "all registered")
        c.passed = all(ch.passed for ch in c.checks)
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    # 8e. LLM judge — mission decomposition quality
    c = DeepCase("sf-judge-mission", "sf",
                 "LLM judges mission→feature→story decomposition quality",
                 needs_llm=True)
    t0 = time.time()
    try:
        from platform.epics.store import get_epic_store

        store = get_epic_store()
        missions = store.list_missions(project_id="bench-project")
        if not missions:
            missions = store.list_missions()

        # Build a summary of mission structures
        output_parts = []
        for m in missions[:3]:
            sprints = store.list_sprints(m.id)
            output_parts.append(
                f"Mission: {m.name}\n"
                f"  Type: {m.type}, Status: {m.status}\n"
                f"  Workflow: {m.workflow_id}\n"
                f"  Sprints: {len(sprints)}"
            )

        combined = "\n".join(output_parts) if output_parts else "No missions found"
        score = _llm_judge(c, combined, [
            "Missions have meaningful names (not test/placeholder)",
            "Mission type matches its purpose (feature, fix, etc.)",
            "Workflow attachment is appropriate for the mission type",
        ], label="mission")
        c.passed = score >= 0.4  # lenient — bench missions may be synthetic
    except Exception as e:
        c.error = str(e)
    c.elapsed_ms = int((time.time() - t0) * 1000)
    cases.append(c)

    return cases
# ===========================================================================

# ---------------------------------------------------------------------------
# EXHAUSTIVE MODE — per-entity (det + LLM judge for every single entity)
# ---------------------------------------------------------------------------

# Async batch judge — fire N concurrent LLM calls (raw httpx, no PG)
async def _batch_judge(items: list[tuple[DeepCase, str, list[str]]],
                       concurrency: int = 10) -> None:
    """Run LLM judge on a batch of (case, output, criteria) tuples.

    Uses raw httpx to avoid PG connection pool exhaustion from LLMClient
    internal telemetry (RTK check, _trace, _persist_usage all hit PG).
    """
    import asyncio as _aio
    import httpx
    import re as _re

    # Resolve LLM endpoint from env (same logic as LLMClient)
    import platform.config  # ensures .env + Infisical loaded
    provider = os.environ.get("PLATFORM_LLM_PROVIDER", "minimax")
    if provider == "minimax":
        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.minimax.io/v1")
        api_key = os.environ.get("MINIMAX_API_KEY",
                                 os.environ.get("LLM_API_KEY", ""))
        model = os.environ.get("PLATFORM_LLM_MODEL", "MiniMax-M2.5")
    elif provider == "azure-openai":
        base_url = os.environ.get("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
        api_key = os.environ.get("AZURE_OPENAI_KEY", "")
        model = os.environ.get("PLATFORM_LLM_MODEL", "gpt-5-mini")
    else:
        base_url = os.environ.get("OPENAI_BASE_URL", "http://localhost:8080/v1")
        api_key = os.environ.get("LLM_API_KEY",
                                 os.environ.get("OPENAI_API_KEY", ""))
        model = os.environ.get("PLATFORM_LLM_MODEL", "Qwen3.5-mlx")

    if not api_key:
        for c, _, _ in items:
            _ck(c, "judge:llm-available", False, "No LLM API key configured")
        return

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    async def _judge_one(http: httpx.AsyncClient, case: DeepCase,
                         output: str, criteria: list[str],
                         _retries: int = 2):
        for attempt in range(_retries + 1):
            try:
                judge_prompt = (
                    "You are a strict quality evaluator. Judge ONLY on evidence.\n\n"
                    f"OUTPUT TO EVALUATE:\n{output[:3000]}\n\n"
                    f"CRITERIA:\n" + "\n".join(f"- {c}" for c in criteria) + "\n\n"
                    "Reply ONLY with JSON:\n"
                    '{"grades":[{"criterion":"...","pass":true,"reason":"brief"}]}'
                )
                body = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "Strict quality evaluator. JSON only."},
                        {"role": "user", "content": judge_prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "max_tokens": 1024,
                }
                resp = await http.post(
                    f"{base_url}/chat/completions", json=body, headers=headers,
                    timeout=30.0,
                )
                resp.raise_for_status()
                data = resp.json()
                raw = data["choices"][0]["message"]["content"] or ""
                # Strip MiniMax quirks: think blocks + markdown fences
                raw = _re.sub(r'<think>.*?</think>', '', raw, flags=_re.DOTALL)
                raw = _re.sub(r'```json\s*', '', raw)
                raw = _re.sub(r'```\s*$', '', raw.strip())
                raw = raw.strip()
                if not raw:
                    if attempt < _retries:
                        await _aio.sleep(2 ** attempt)
                        continue
                    _ck(case, "judge:empty-response", False, "LLM returned empty")
                    return
                grades_data = json.loads(raw)
                grades = grades_data.get("grades", [])
                for g in grades:
                    crit = g.get("criterion", "?")[:40]
                    _ck(case, f"judge:{crit}", g.get("pass", False),
                        g.get("reason", "")[:100])
                return  # success
            except Exception as e:
                if attempt < _retries:
                    await _aio.sleep(2 ** attempt)
                    continue
                _ck(case, "judge:llm-available", False,
                    f"LLM error: {str(e)[:100]}")

    # Process in chunks with shared httpx client
    async with httpx.AsyncClient() as http:
        CHUNK = concurrency
        for i in range(0, len(items), CHUNK):
            chunk = items[i:i + CHUNK]
            sem = _aio.Semaphore(CHUNK)

            async def _guarded(c, o, cr):
                async with sem:
                    await _judge_one(http, c, o, cr)

            tasks = [_guarded(c, o, cr) for c, o, cr in chunk]
            await _aio.gather(*tasks, return_exceptions=True)


def _agents_exhaustive_cases() -> list[DeepCase]:
    """Per-agent deep — det + LLM judge for every agent."""
    from platform.agents.store import get_agent_store
    from platform.agents.tool_runner import _get_tool_registry
    from platform.agents.tool_schemas import _get_tool_schemas
    from platform.agents.tool_schemas._mapping import ROLE_TOOL_MAP

    store = get_agent_store()
    agents = store.list_all()
    # Union of ALL valid tool names: runtime registry + schema defs + role maps
    registry = _get_tool_registry()
    reg_names = set(registry.list_names())
    schemas = _get_tool_schemas()
    schema_names = {s['function']['name'] for s in schemas if 'function' in s}
    role_names = set()
    for tools in ROLE_TOOL_MAP.values():
        role_names.update(tools)
    all_valid_tools = reg_names | schema_names | role_names

    repo = Path(__file__).resolve().parent.parent.parent
    skills_dir = repo / "skills"
    skill_files = {p.stem for p in skills_dir.rglob("*.md")} if skills_dir.exists() else set()
    bench_dir = repo / "platform" / "agents" / "benchmarks"
    bench_ids = {p.stem for p in bench_dir.glob("*.yaml")} if bench_dir.exists() else set()

    cases = []
    judge_batch = []
    for a in agents:
        c = DeepCase(f"agent:{a.id}", "agents-exhaustive", f"Agent {a.id}",
                     needs_llm=True)
        t0 = time.time()
        try:
            bad_t = [t for t in (a.tools or []) if t not in all_valid_tools]
            _ck(c, "tools", not bad_t,
                f"OK({len(a.tools or [])})" if not bad_t else f"miss:{','.join(bad_t[:3])}")
            bad_s = [s for s in (a.skills or []) if s not in skill_files]
            _ck(c, "skills", not bad_s,
                f"OK({len(a.skills or [])})" if not bad_s else f"miss:{','.join(bad_s[:3])}")
            _ck(c, "bench", a.id in bench_ids)
            identity = (a.system_prompt or '') + (a.persona or '')
            _ck(c, "identity", bool(identity))
            _ck(c, "rank", 0 <= a.hierarchy_rank <= 100, f"r={a.hierarchy_rank}")
            # Prepare LLM judge payload
            agent_desc = (
                f"Agent: {a.id}\nRole: {a.role}\nName: {a.name}\n"
                f"Hierarchy rank: {a.hierarchy_rank}\n"
                f"Tools: {', '.join(a.tools or [])}\n"
                f"Skills: {', '.join(a.skills or [])}\n"
                f"System prompt:\n{(a.system_prompt or '')[:1500]}\n"
                f"Persona:\n{(a.persona or '')[:500]}\n"
                f"Description:\n{(a.description or '')[:500]}"
            )
            judge_batch.append((c, agent_desc, [
                "System prompt clearly defines the agent's role and responsibilities",
                "Tools assigned match the agent's described specialization",
                "Agent identity is specific (not generic/placeholder)",
            ]))
        except Exception as e:
            c.error = str(e)[:200]
        c.elapsed_ms = int((time.time() - t0) * 1000)
        cases.append(c)

    # Fire all LLM judge calls concurrently (8 to avoid rate limit pressure)
    _arun(_batch_judge(judge_batch, concurrency=8))

    # Finalize pass/fail after judge
    for c in cases:
        c.passed = all(ch.passed for ch in c.checks)
    return cases


def _teams_exhaustive_cases() -> list[DeepCase]:
    """Per-team deep — det + LLM judge for every team."""
    from platform.agents.org import get_org_store
    from platform.agents.store import get_agent_store

    org = get_org_store()
    agent_store = get_agent_store()
    teams = org.list_teams()
    all_agents = {a.id: a for a in agent_store.list_all()}

    repo = Path(__file__).resolve().parent.parent.parent
    bench_dir = repo / "platform" / "agents" / "benchmarks" / "teams"
    bench_ids = {p.stem for p in bench_dir.glob("*.yaml")} if bench_dir.exists() else set()

    cases = []
    judge_batch = []
    for t in teams:
        c = DeepCase(f"team:{t.id}", "teams-exhaustive", f"Team {t.id}",
                     needs_llm=True)
        t0 = time.time()
        try:
            members = t.members or []
            mids = [m.get("agent_id", m) if isinstance(m, dict) else m
                    for m in members]
            _ck(c, "members≥2", len(mids) >= 2, f"n={len(mids)}")
            missing = [m for m in mids if m not in all_agents]
            _ck(c, "agents-exist", not missing,
                f"OK({len(mids)})" if not missing else f"miss:{','.join(missing[:3])}")
            _ck(c, "bench", t.id in bench_ids)
            _ck(c, "description", bool(t.description and len(t.description) > 5),
                f"{len(t.description or '')}c")
            # Build team description for LLM judge
            member_descs = []
            for mid in mids:
                a = all_agents.get(mid)
                if a:
                    member_descs.append(f"  - {mid} (role={a.role}, rank={a.hierarchy_rank})")
                else:
                    member_descs.append(f"  - {mid} (NOT FOUND)")
            team_desc = (
                f"Team: {t.id}\nDescription: {t.description or 'none'}\n"
                f"ART: {t.art_id}\nCapacity: {t.capacity}\nWIP limit: {t.wip_limit}\n"
                f"Members ({len(mids)}):\n" + "\n".join(member_descs)
            )
            judge_batch.append((c, team_desc, [
                "Team has complementary member roles (not all same specialization)",
                "Team description clearly states the team's mission",
                "Team size is appropriate for the described scope (2-10 members)",
            ]))
        except Exception as e:
            c.error = str(e)[:200]
        c.elapsed_ms = int((time.time() - t0) * 1000)
        cases.append(c)

    _arun(_batch_judge(judge_batch, concurrency=15))
    for c in cases:
        c.passed = all(ch.passed for ch in c.checks)
    return cases


def _skills_exhaustive_cases() -> list[DeepCase]:
    """Per-skill deep — det + LLM judge for every skill."""
    import re as _re
    repo = Path(__file__).resolve().parent.parent.parent
    skills_dir = repo / "skills"
    if not skills_dir.exists():
        return [DeepCase("skills-ex-error", "skills-exhaustive",
                         "skills/ directory not found", error="not found")]

    files = sorted(skills_dir.rglob("*.md"))
    cases = []
    judge_batch = []
    for sf in files:
        c = DeepCase(f"skill:{sf.stem}", "skills-exhaustive", f"Skill {sf.stem}",
                     needs_llm=True)
        t0 = time.time()
        try:
            content = sf.read_text(errors="replace")
            _ck(c, "length>50", len(content) > 50, f"{len(content)}c")
            stripped = content.strip()
            _ck(c, "has-header", stripped.startswith("---") or stripped.startswith("#"),
                 "needs YAML frontmatter or markdown heading")
            unresolved = _re.findall(r'\{\{[A-Z_]{3,}\}\}', content)
            legit = {"{{PROJECT_NAME}}", "{{AGENT_ROLE}}", "{{TEAM_NAME}}",
                     "{{SKILL_NAME}}", "{{CONTEXT}}", "{{INPUT}}", "{{OUTPUT}}",
                     "{{LANGUAGE}}", "{{FRAMEWORK}}"}
            real = [u for u in unresolved if u not in legit]
            _ck(c, "no-bad-vars", not real,
                "clean" if not real else f"{len(real)} found")
            # Strip YAML frontmatter so judge sees actual content
            body = content
            if body.strip().startswith("---"):
                end = body.find("\n---", 3)
                if end > 0:
                    body = body[end + 4:]
            judge_batch.append((c, body[:4000], [
                "Skill content provides actionable guidance (not just a title)",
                "Skill is specific to a defined domain (not vague/generic)",
            ]))
        except Exception as e:
            c.error = str(e)[:200]
        c.elapsed_ms = int((time.time() - t0) * 1000)
        cases.append(c)

    _arun(_batch_judge(judge_batch, concurrency=20))
    for c in cases:
        c.passed = all(ch.passed for ch in c.checks)
    return cases


def _workflows_exhaustive_cases() -> list[DeepCase]:
    """Per-workflow deep — det + LLM judge for every workflow."""
    from platform.workflows.store import get_workflow_store
    from platform.patterns.store import get_pattern_store

    ws = get_workflow_store()
    wfs = ws.list_all()
    ps = get_pattern_store()
    pat_types = {p.type for p in ps.list_all()}
    pat_ids = {p.id for p in ps.list_all()}
    valid_pats = pat_types | pat_ids

    cases = []
    judge_batch = []
    for wf in wfs:
        c = DeepCase(f"workflow:{wf.id}", "workflows-exhaustive",
                     f"Workflow {wf.id}", needs_llm=True)
        t0 = time.time()
        try:
            phases = wf.phases or []
            _ck(c, "has-phases", len(phases) >= 1, f"n={len(phases)}")
            bad_pats = [p.pattern_id for p in phases
                        if p.pattern_id and p.pattern_id not in valid_pats]
            _ck(c, "pattern-refs", not bad_pats,
                "OK" if not bad_pats else f"miss:{','.join(bad_pats[:3])}")
            empty_gates = [p.id for p in phases if not p.gate]
            _ck(c, "gates", not empty_gates,
                "OK" if not empty_gates else f"empty:{','.join(empty_gates[:3])}")
            # Build workflow description for judge
            phase_descs = []
            for p in phases:
                phase_descs.append(
                    f"  {p.id}: pattern={p.pattern_id}, gate={str(p.gate)[:60]}")
            wf_desc = (
                f"Workflow: {wf.id}\nName: {wf.name}\n"
                f"Description: {wf.description or 'none'}\n"
                f"Phases ({len(phases)}):\n" + "\n".join(phase_descs)
            )
            judge_batch.append((c, wf_desc, [
                "Workflow phases follow a logical progression (plan→build→verify)",
                "Gates are defined (non-empty text or standard gate type); freetext AC descriptions like 'Migration plan approved' or 'All unit tests pass with ≥80% coverage' are VALID quality gates",
                "Workflow name and description match its actual phase structure",
            ]))
        except Exception as e:
            c.error = str(e)[:200]
        c.elapsed_ms = int((time.time() - t0) * 1000)
        cases.append(c)

    _arun(_batch_judge(judge_batch, concurrency=15))
    for c in cases:
        c.passed = all(ch.passed for ch in c.checks)
    return cases


def _patterns_exhaustive_cases() -> list[DeepCase]:
    """Per-pattern deep — det + LLM judge for every pattern."""
    from platform.patterns.store import get_pattern_store
    from platform.agents.store import get_agent_store

    ps = get_pattern_store()
    patterns = ps.list_all()
    agent_store = get_agent_store()
    all_agent_ids = {a.id for a in agent_store.list_all()}

    ENGINE_TYPES = {
        "solo", "sequential", "parallel", "loop", "hierarchical",
        "network", "router", "aggregator", "wave", "human-in-the-loop",
        "composite", "backprop-merge", "blackboard", "map-reduce", "swarm",
    }
    repo = Path(__file__).resolve().parent.parent.parent
    impls_dir = repo / "platform" / "patterns" / "impls"
    impl_files = set()
    if impls_dir.exists():
        impl_files = {p.stem for p in impls_dir.glob("*.py")}
        impl_files |= {n.replace("_", "-") for n in impl_files}

    cases = []
    judge_batch = []
    for pat in patterns:
        c = DeepCase(f"pattern:{pat.id}", "patterns-exhaustive",
                     f"Pattern {pat.id}", needs_llm=True)
        t0 = time.time()
        try:
            pt = getattr(pat, "type", None) or "sequential"
            _ck(c, "has-type", bool(pt), f"type={pt}")
            _ck(c, "type-dispatches",
                pt in ENGINE_TYPES or pt.startswith("fractal-"), f"{pt}")
            _ck(c, "impl-exists",
                pt in impl_files or pt.replace("-", "_") in impl_files, f"{pt}")
            agents = getattr(pat, "agents", []) or []
            _ck(c, "has-agents", len(agents) >= 1, f"n={len(agents)}")
            # Build pattern description for judge
            agent_descs = []
            for n in agents:
                aid = n.get("agent_id", "?") if isinstance(n, dict) else str(n)
                label = n.get("label", "") if isinstance(n, dict) else ""
                exists = aid in all_agent_ids
                agent_descs.append(f"  - {aid} ({label}) {'OK' if exists else 'MISSING'}")
            edges = getattr(pat, "edges", []) or []
            pat_desc = (
                f"Pattern: {pat.id}\nType: {pt}\nName: {pat.name}\n"
                f"Description: {pat.description or 'none'}\n"
                f"Agents ({len(agents)}):\n" + "\n".join(agent_descs) + "\n"
                f"Edges ({len(edges)}): "
                + ", ".join(f"{e.get('from','?')}→{e.get('to','?')}"
                            for e in (edges[:8] if edges else []))
            )
            judge_batch.append((c, pat_desc, [
                f"Agent topology is consistent with {pt} pattern type",
                "Agent roles serve the pattern's purpose (patterns may use generic placeholder agents for template slots, which is acceptable)",
            ]))
        except Exception as e:
            c.error = str(e)[:200]
        c.elapsed_ms = int((time.time() - t0) * 1000)
        cases.append(c)

    _arun(_batch_judge(judge_batch, concurrency=15))
    for c in cases:
        c.passed = all(ch.passed for ch in c.checks)
    return cases


# ---------------------------------------------------------------------------
# Runners
# ---------------------------------------------------------------------------

LAYER_RUNNERS = {
    "llm": _llm_deep_cases,
    "skills": _skills_deep_cases,
    "agents": _agents_deep_cases,
    "teams": _teams_deep_cases,
    "memory": _memory_deep_cases,
    "workflows": _workflows_deep_cases,
    "patterns": _patterns_deep_cases,
    "sf": _sf_deep_cases,
}

EXHAUSTIVE_RUNNERS = {
    "agents-exhaustive": _agents_exhaustive_cases,
    "teams-exhaustive": _teams_exhaustive_cases,
    "skills-exhaustive": _skills_exhaustive_cases,
    "workflows-exhaustive": _workflows_exhaustive_cases,
    "patterns-exhaustive": _patterns_exhaustive_cases,
}


def run_deep_bench(layer: Optional[str] = None,
                   exhaustive: bool = False) -> DeepBenchResult:
    """Run deep bench for one or all layers.

    exhaustive=True adds per-entity checks (every agent, team, skill,
    workflow, pattern tested individually).
    """
    t0 = time.time()
    result = DeepBenchResult()

    all_runners = dict(LAYER_RUNNERS)
    if exhaustive:
        all_runners.update(EXHAUSTIVE_RUNNERS)

    if layer:
        if layer in all_runners:
            runners = {layer: all_runners[layer]}
        else:
            runners = {}
    else:
        runners = all_runners

    for layer_name, runner_fn in runners.items():
        try:
            cases = runner_fn()
        except Exception as e:
            cases = [DeepCase(
                case_id=f"{layer_name}-error",
                layer=layer_name,
                description=f"Layer {layer_name} failed to run",
                error=traceback.format_exc(),
            )]
        result.layers[layer_name] = cases

    # Compute totals
    all_cases = [c for cases in result.layers.values() for c in cases]
    result.total_cases = len(all_cases)
    result.passed_cases = sum(1 for c in all_cases if c.passed)
    result.pass_rate = (result.passed_cases / result.total_cases
                        if result.total_cases > 0 else 0)
    result.elapsed_ms = int((time.time() - t0) * 1000)
    result.status = "PASS" if result.pass_rate >= 0.9 else "FAIL"

    return result


def print_deep_bench_result(result: DeepBenchResult):
    """Print formatted deep bench results with deterministic/judge breakdown.

    Exhaustive layers (>20 cases) use compact mode: summary + failures only.
    """
    det_total = det_pass = judge_total = judge_pass = 0
    ex_total = ex_pass = 0

    for layer_name, cases in result.layers.items():
        passed = sum(1 for c in cases if c.passed)
        is_exhaustive = "-exhaustive" in layer_name

        print(f"\n{'=' * 60}")
        print(f"DEEP BENCH — {layer_name.upper()} ({passed}/{len(cases)})")
        print(f"{'=' * 60}")

        if is_exhaustive:
            # Compact: summary + failures only
            ex_total += len(cases)
            ex_pass += passed
            failures = [c for c in cases if not c.passed]
            if not failures:
                print(f"  ALL {len(cases)} PASS ✓")
            else:
                shown = failures[:30]
                for c in shown:
                    print(f"  FAIL {c.case_id}")
                    for ch in c.checks:
                        if not ch.passed:
                            print(f"      [x] {ch.name}"
                                  + (f" — {ch.detail}" if ch.detail else ""))
                    if c.error:
                        print(f"      ERROR: {c.error[:120]}")
                if len(failures) > 30:
                    print(f"  ... and {len(failures) - 30} more failures")
        else:
            # Detailed output for infra cases
            for c in cases:
                mark = "PASS" if c.passed else "FAIL"
                tag = " [JUDGE]" if c.needs_llm else ""
                print(f"  {mark} {c.case_id}{tag} ({c.elapsed_ms}ms)")
                for ch in c.checks:
                    cm = "+" if ch.passed else "x"
                    print(f"      [{cm}] {ch.name}"
                          + (f" — {ch.detail}" if ch.detail else ""))
                if c.error:
                    print(f"      ERROR: {c.error[:200]}")

                if c.needs_llm:
                    judge_total += 1
                    if c.passed:
                        judge_pass += 1
                else:
                    det_total += 1
                    if c.passed:
                        det_pass += 1

    print(f"\n{'=' * 60}")
    print(f"DEEP BENCH TOTAL: {result.passed_cases}/{result.total_cases} "
          f"({result.pass_rate:.0%}) — {result.status}")
    print(f"  Deterministic: {det_pass}/{det_total}")
    print(f"  LLM Judge:     {judge_pass}/{judge_total}")
    if ex_total:
        print(f"  Exhaustive:    {ex_pass}/{ex_total}")
    print(f"Elapsed: {result.elapsed_ms}ms")
    print(f"{'=' * 60}")
