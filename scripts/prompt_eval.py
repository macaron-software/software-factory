#!/usr/bin/env python3
"""Prompt CI Evaluator — regression testing for LLM prompt behavior.

Runs prompt evals against configured providers to catch regressions:
- Tool calling reliability (does the LLM call tools vs describe them?)
- Multi-turn continuation (after tool results, does the LLM keep acting?)
- Output format compliance (verdicts, code blocks, structured output)
- Prompt size budgets (token/char limits)

Usage:
    python scripts/prompt_eval.py                    # run all evals
    python scripts/prompt_eval.py --provider minimax  # single provider
    python scripts/prompt_eval.py --suite tool_call   # single suite
    python scripts/prompt_eval.py --ci                # CI mode (exit 1 on failure)
    python scripts/prompt_eval.py --list              # list available evals

Designed for CI integration:
    - Exit 0 if all pass, exit 1 if any fail
    - Deterministic retries for flaky providers (MiniMax ~33% tool call rate)
    - JSON output with --json flag
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import os
import re
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─── Data Model ──────────────────────────────────────────────────────────────


@dataclasses.dataclass
class Assertion:
    """Single assertion on an LLM response."""

    type: str  # tool_called | no_tool_call | content_contains | content_matches | verdict_format | has_content
    value: str = ""
    description: str = ""

    def check(self, response) -> tuple[bool, str]:
        """Check assertion against LLMResponse. Returns (passed, reason)."""
        tc_names = [tc.function_name for tc in (response.tool_calls or [])]
        content = response.content or ""

        if self.type == "tool_called":
            if self.value in tc_names:
                return True, f"✓ called {self.value}"
            return False, f"✗ expected tool_call '{self.value}', got: {tc_names or 'none'}"

        if self.type == "no_tool_call":
            if not tc_names:
                return True, "✓ no tool calls (expected)"
            return False, f"✗ unexpected tool calls: {tc_names}"

        if self.type == "has_content":
            if content.strip():
                return True, f"✓ has content ({len(content)} chars)"
            return False, "✗ empty content"

        if self.type == "content_contains":
            if self.value.lower() in content.lower():
                return True, f"✓ contains '{self.value}'"
            return False, f"✗ missing '{self.value}' in: {content[:100]}..."

        if self.type == "content_matches":
            if re.search(self.value, content, re.IGNORECASE | re.DOTALL):
                return True, f"✓ matches /{self.value}/"
            return False, f"✗ no match for /{self.value}/ in: {content[:100]}..."

        if self.type == "verdict_format":
            # Check for structured verdict (APPROVED, REJECTED, DONE, BLOCKED, etc.)
            pattern = self.value or r"\b(APPROVED|REJECTED|DONE|BLOCKED|NEEDS_CONTEXT|DONE_WITH_CONCERNS|CHANGES_REQUESTED)\b"
            if re.search(pattern, content):
                return True, f"✓ verdict found"
            return False, f"✗ no verdict matching {pattern} in: {content[:100]}..."

        if self.type == "finish_reason":
            if response.finish_reason == self.value:
                return True, f"✓ finish_reason={self.value}"
            return False, f"✗ finish_reason={response.finish_reason}, expected {self.value}"

        return False, f"✗ unknown assertion type: {self.type}"


@dataclasses.dataclass
class Round:
    """One round in a multi-turn eval."""

    messages: list[dict]  # [{role, content}]
    assertions: list[Assertion]
    mock_tool_result: str | None = None  # Injected as tool result for next round
    mock_tool_name: str | None = None


@dataclasses.dataclass
class PromptEval:
    """Single prompt evaluation case."""

    id: str
    name: str
    suite: str  # grouping key

    # Single-round eval
    system_prompt: str = ""
    user_message: str = ""
    tools: list[dict] | None = None
    assertions: list[Assertion] = dataclasses.field(default_factory=list)

    # Multi-round eval (if set, overrides single-round)
    rounds: list[Round] | None = None

    # Execution config
    retries: int = 3  # max attempts (for flaky providers)
    max_tokens: int = 500
    temperature: float = 0.7


@dataclasses.dataclass
class EvalResult:
    """Result of running one eval against one provider."""

    eval_id: str
    provider: str
    passed: bool
    attempts: int
    assertion_results: list[tuple[bool, str]]
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: int = 0
    error: str = ""


# ─── Tool Schemas (minimal set for testing) ──────────────────────────────────

TOOL_LIST_FILES = {
    "type": "function",
    "function": {
        "name": "list_files",
        "description": "List directory contents",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Directory path"}},
            "required": ["path"],
        },
    },
}

TOOL_CODE_WRITE = {
    "type": "function",
    "function": {
        "name": "code_write",
        "description": "Write content to a file. Creates or overwrites.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path"},
                "content": {"type": "string", "description": "File content"},
            },
            "required": ["path", "content"],
        },
    },
}

TOOL_CODE_READ = {
    "type": "function",
    "function": {
        "name": "code_read",
        "description": "Read file contents",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "File path"}},
            "required": ["path"],
        },
    },
}

TOOL_BUILD = {
    "type": "function",
    "function": {
        "name": "build",
        "description": "Build the project",
        "parameters": {
            "type": "object",
            "properties": {"command": {"type": "string", "description": "Build command"}},
            "required": [],
        },
    },
}

TOOL_MEMORY_SEARCH = {
    "type": "function",
    "function": {
        "name": "memory_search",
        "description": "Search project memory/knowledge base",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        },
    },
}

DEV_TOOLS = [TOOL_LIST_FILES, TOOL_CODE_WRITE, TOOL_CODE_READ, TOOL_BUILD, TOOL_MEMORY_SEARCH]


# ─── Eval Definitions ────────────────────────────────────────────────────────


def get_evals() -> list[PromptEval]:
    """All registered prompt evals."""
    return [
        # ── Suite: tool_call ──────────────────────────────────────────────
        PromptEval(
            id="tc-single",
            name="Single tool call (list_files)",
            suite="tool_call",
            system_prompt="You are a coding assistant. ALWAYS use tools directly — never describe what you would do.",
            user_message="List files in /data/workspaces/test-project",
            tools=[TOOL_LIST_FILES, TOOL_CODE_WRITE],
            assertions=[Assertion("tool_called", "list_files")],
        ),
        PromptEval(
            id="tc-write",
            name="Direct code_write call",
            suite="tool_call",
            system_prompt="You are a coding assistant. ALWAYS use tools directly. Call code_write IMMEDIATELY.",
            user_message="Create a file src/hello.py with a hello() function that returns 'Hello World'",
            tools=[TOOL_CODE_WRITE, TOOL_CODE_READ],
            assertions=[Assertion("tool_called", "code_write")],
        ),
        PromptEval(
            id="tc-with-context",
            name="Tool call with heavy context",
            suite="tool_call",
            system_prompt=(
                "ALWAYS use tools directly — NEVER describe what you would do.\n"
                "Call code_write IMMEDIATELY to create files. Do NOT explain first.\n\n"
                "You are lead_frontend, a senior frontend developer.\n"
                "Project: sf-dashboard — a React+TypeScript dashboard.\n"
                "Tech stack: React 18, TypeScript 5, Vite, TailwindCSS.\n"
                "Architecture guidelines: Use functional components with hooks. "
                "Follow atomic design (atoms/molecules/organisms). "
                "All components must have unit tests. Use CSS modules."
            ),
            user_message="Create the file src/components/atoms/Button/Button.tsx with a simple Button component.",
            tools=[TOOL_CODE_WRITE],
            assertions=[Assertion("tool_called", "code_write")],
            retries=5,
        ),

        # ── Suite: multi_turn ─────────────────────────────────────────────
        PromptEval(
            id="mt-two-rounds",
            name="Multi-turn: 2 rounds of tool calls",
            suite="multi_turn",
            system_prompt="You are a coding assistant. ALWAYS use tools directly.",
            tools=[TOOL_LIST_FILES, TOOL_CODE_WRITE],
            rounds=[
                Round(
                    messages=[{"role": "user", "content": "List files in /project"}],
                    assertions=[Assertion("tool_called", "list_files")],
                    mock_tool_result="src/\npackage.json\ntsconfig.json\nREADME.md",
                    mock_tool_name="list_files",
                ),
                Round(
                    messages=[
                        {
                            "role": "user",
                            "content": "Good. Now create src/hello.ts with: export function hello(): string { return 'Hello'; }",
                        }
                    ],
                    assertions=[Assertion("tool_called", "code_write")],
                    mock_tool_result="File written: src/hello.ts (62 bytes)",
                    mock_tool_name="code_write",
                ),
            ],
        ),
        PromptEval(
            id="mt-three-rounds",
            name="Multi-turn: 3 rounds deep",
            suite="multi_turn",
            system_prompt="You are a coding assistant. ALWAYS use tools directly.",
            tools=[TOOL_LIST_FILES, TOOL_CODE_WRITE, TOOL_CODE_READ],
            rounds=[
                Round(
                    messages=[{"role": "user", "content": "List files in /project/src"}],
                    assertions=[Assertion("tool_called", "list_files")],
                    mock_tool_result="app.ts\nutils.ts\nindex.ts",
                    mock_tool_name="list_files",
                ),
                Round(
                    messages=[{"role": "user", "content": "Read src/app.ts"}],
                    assertions=[Assertion("tool_called", "code_read")],
                    mock_tool_result='export function main() { console.log("hello"); }',
                    mock_tool_name="code_read",
                ),
                Round(
                    messages=[
                        {
                            "role": "user",
                            "content": "Create src/app.test.ts with a test for the main function",
                        }
                    ],
                    assertions=[Assertion("tool_called", "code_write")],
                ),
            ],
        ),

        # ── Suite: format ─────────────────────────────────────────────────
        PromptEval(
            id="fmt-implementer-verdict",
            name="Implementer prompt produces verdict",
            suite="format",
            system_prompt=(
                "You are an implementer agent. After completing work, you MUST end with "
                "exactly one of: DONE, DONE_WITH_CONCERNS, NEEDS_CONTEXT, BLOCKED.\n"
                "Always provide a status line at the end."
            ),
            user_message="Task: Create a hello.py file. Status: I have created the file with a hello() function. Report your final status.",
            assertions=[
                Assertion("verdict_format", r"\b(DONE|DONE_WITH_CONCERNS|NEEDS_CONTEXT|BLOCKED)\b"),
                Assertion("has_content"),
            ],
        ),
        PromptEval(
            id="fmt-reviewer-verdict",
            name="Reviewer prompt produces verdict",
            suite="format",
            system_prompt=(
                "You are a spec reviewer. Review the implementation against specs.\n"
                "End with exactly one verdict: APPROVED or REJECTED.\n"
                "If REJECTED, list issues as MISSING, WRONG, or EXTRA."
            ),
            user_message=(
                "Spec: Create hello.py with hello(name) returning 'Hello {name}'.\n"
                "Implementation: def hello(name): return f'Hello {name}'\n"
                "Review this implementation."
            ),
            assertions=[
                Assertion("verdict_format", r"\b(APPROVED|REJECTED)\b"),
                Assertion("has_content"),
            ],
        ),
        PromptEval(
            id="fmt-quality-verdict",
            name="Code quality reviewer verdict",
            suite="format",
            system_prompt=(
                "You are a code quality reviewer. Review code changes.\n"
                "Severity levels: Critical, Important, Minor.\n"
                "End with: APPROVED, APPROVED_WITH_NOTES, or CHANGES_REQUESTED."
            ),
            user_message=(
                "Review this Python code:\n"
                "```python\n"
                "def process(data):\n"
                "    result = []\n"
                "    for item in data:\n"
                "        if item > 0:\n"
                "            result.append(item * 2)\n"
                "    return result\n"
                "```"
            ),
            assertions=[
                Assertion(
                    "verdict_format",
                    r"\b(APPROVED|APPROVED_WITH_NOTES|CHANGES_REQUESTED)\b",
                ),
                Assertion("has_content"),
            ],
        ),

        # ── Suite: regression ─────────────────────────────────────────────
        PromptEval(
            id="reg-no-describe",
            name="Regression: doesn't describe tool calls as text",
            suite="regression",
            system_prompt="You are a dev agent. Use tools. NEVER say 'I will use' or 'I would call' — call the tool directly.",
            user_message="Create src/utils.py with a function add(a, b) that returns a+b",
            tools=[TOOL_CODE_WRITE],
            assertions=[
                Assertion("tool_called", "code_write"),
            ],
        ),
        PromptEval(
            id="reg-write-first",
            name="Regression: writes code before exploring",
            suite="regression",
            system_prompt=(
                "You are a dev agent. Your task is to write code.\n"
                "WRITE code FIRST. Call code_write WITHIN YOUR FIRST RESPONSE.\n"
                "Do NOT explore or read files before writing. Write immediately."
            ),
            user_message="Create src/calculator.py with add, subtract, multiply, divide functions.",
            tools=DEV_TOOLS,
            assertions=[
                Assertion("tool_called", "code_write", "Agent should write code, not explore first"),
            ],
        ),
    ]


# ─── Runner ──────────────────────────────────────────────────────────────────


async def run_single_eval(
    llm,
    eval_case: PromptEval,
    provider: str,
) -> EvalResult:
    """Run a single eval against a single provider."""
    from platform.llm.client import LLMMessage

    total_tokens_in = 0
    total_tokens_out = 0
    t0 = time.monotonic()

    for attempt in range(1, eval_case.retries + 1):
        try:
            if eval_case.rounds:
                # Multi-turn eval
                all_passed, assertion_results = await _run_multi_turn(
                    llm, eval_case, provider, LLMMessage,
                )
                return EvalResult(
                    eval_id=eval_case.id,
                    provider=provider,
                    passed=all_passed,
                    attempts=attempt,
                    assertion_results=assertion_results,
                    duration_ms=int((time.monotonic() - t0) * 1000),
                )
            else:
                # Single-round eval
                # Bust LLM cache on retries with invisible suffix
                user_msg = eval_case.user_message
                if attempt > 1:
                    user_msg += f"\n(attempt {attempt})"
                msgs = [LLMMessage(role="user", content=user_msg)]
                resp = await llm.chat(
                    msgs,
                    provider=provider,
                    max_tokens=eval_case.max_tokens,
                    tools=eval_case.tools,
                    system_prompt=eval_case.system_prompt,
                    temperature=eval_case.temperature,
                )
                total_tokens_in += resp.tokens_in
                total_tokens_out += resp.tokens_out

                assertion_results = [a.check(resp) for a in eval_case.assertions]
                all_passed = all(r[0] for r in assertion_results)

                if all_passed or attempt == eval_case.retries:
                    return EvalResult(
                        eval_id=eval_case.id,
                        provider=provider,
                        passed=all_passed,
                        attempts=attempt,
                        assertion_results=assertion_results,
                        tokens_in=total_tokens_in,
                        tokens_out=total_tokens_out,
                        duration_ms=int((time.monotonic() - t0) * 1000),
                    )
                # Retry on failure
        except Exception as e:
            if attempt == eval_case.retries:
                return EvalResult(
                    eval_id=eval_case.id,
                    provider=provider,
                    passed=False,
                    attempts=attempt,
                    assertion_results=[(False, f"✗ error: {e}")],
                    duration_ms=int((time.monotonic() - t0) * 1000),
                    error=str(e),
                )

    # Should not reach here
    return EvalResult(
        eval_id=eval_case.id,
        provider=provider,
        passed=False,
        attempts=eval_case.retries,
        assertion_results=[(False, "✗ exhausted retries")],
        duration_ms=int((time.monotonic() - t0) * 1000),
    )


async def _run_multi_turn(llm, eval_case, provider, LLMMessage):
    """Execute multi-turn eval with mock tool results between rounds."""
    conversation: list[LLMMessage] = []
    all_assertion_results = []

    for i, rnd in enumerate(eval_case.rounds):
        # Add round messages to conversation
        for msg in rnd.messages:
            conversation.append(LLMMessage(role=msg["role"], content=msg["content"]))

        # Call LLM
        for attempt in range(eval_case.retries):
            # Bust cache on retries — modify last message slightly
            if attempt > 0 and conversation:
                last = conversation[-1]
                conversation[-1] = LLMMessage(
                    role=last.role,
                    content=(last.content or "") + f"\n(attempt {attempt + 1})",
                    name=last.name,
                    tool_call_id=last.tool_call_id,
                    tool_calls=last.tool_calls,
                )
            resp = await llm.chat(
                conversation,
                provider=provider,
                max_tokens=eval_case.max_tokens,
                tools=eval_case.tools,
                system_prompt=eval_case.system_prompt,
                temperature=eval_case.temperature,
            )
            # Restore original message
            if attempt > 0 and conversation:
                orig_content = conversation[-1].content.rsplit("\n(attempt ", 1)[0]
                conversation[-1] = LLMMessage(
                    role=conversation[-1].role,
                    content=orig_content,
                    name=conversation[-1].name,
                    tool_call_id=conversation[-1].tool_call_id,
                    tool_calls=conversation[-1].tool_calls,
                )

            round_results = [a.check(resp) for a in rnd.assertions]
            round_passed = all(r[0] for r in round_results)

            if round_passed or attempt == eval_case.retries - 1:
                break

        all_assertion_results.extend(round_results)

        if not round_passed:
            # Fail early — no point continuing if a round fails
            return False, all_assertion_results

        # Inject mock tool result for next round
        if rnd.mock_tool_result and resp.tool_calls:
            tc = resp.tool_calls[0]
            # Add assistant response with tool_calls
            conversation.append(
                LLMMessage(
                    role="assistant",
                    content=resp.content or "",
                    tool_calls=[
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function_name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                    ],
                )
            )
            # Add tool result
            conversation.append(
                LLMMessage(
                    role="tool",
                    content=rnd.mock_tool_result,
                    tool_call_id=tc.id,
                    name=rnd.mock_tool_name or tc.function_name,
                )
            )

    return all(r[0] for r in all_assertion_results), all_assertion_results


async def run_suite(
    providers: list[str] | None = None,
    suite_filter: str | None = None,
    eval_filter: str | None = None,
) -> list[EvalResult]:
    """Run all matching evals against all matching providers."""
    from platform.llm.client import get_llm_client

    llm = get_llm_client()
    evals = get_evals()

    if suite_filter:
        evals = [e for e in evals if e.suite == suite_filter]
    if eval_filter:
        evals = [e for e in evals if e.id == eval_filter]

    if not providers:
        providers = _detect_providers()

    results = []
    for ev in evals:
        for prov in providers:
            result = await run_single_eval(llm, ev, prov)
            results.append(result)

    return results


def _detect_providers() -> list[str]:
    """Detect available providers from environment."""
    providers = []
    if os.environ.get("MINIMAX_API_KEY"):
        providers.append("minimax")
    if os.environ.get("AZURE_OPENAI_API_KEY"):
        providers.append("azure-openai")
    if os.environ.get("AZURE_AI_API_KEY"):
        providers.append("azure-ai")
    if os.environ.get("NVIDIA_API_KEY"):
        providers.append("nvidia")
    if not providers:
        # Fallback: use whatever the platform default is
        providers.append(os.environ.get("PLATFORM_LLM_PROVIDER", "minimax"))
    return providers


# ─── Output Formatting ───────────────────────────────────────────────────────


def print_results(results: list[EvalResult], verbose: bool = False):
    """Print results as a formatted table."""
    if not results:
        print("No results.")
        return

    # Group by suite
    evals_by_id = {e.id: e for e in get_evals()}
    suites: dict[str, list[EvalResult]] = {}
    for r in results:
        ev = evals_by_id.get(r.eval_id)
        suite = ev.suite if ev else "unknown"
        suites.setdefault(suite, []).append(r)

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    print()
    print(f"  Prompt CI Eval — {passed}/{total} passed" + (f", {failed} FAILED" if failed else ""))
    print()

    for suite, suite_results in suites.items():
        print(f"  ┌─ {suite} {'─' * (58 - len(suite))}┐")

        for r in suite_results:
            ev = evals_by_id.get(r.eval_id)
            name = ev.name if ev else r.eval_id
            status = "✅" if r.passed else "❌"
            attempts = f"({r.attempts}/{ev.retries if ev else '?'})" if r.attempts > 1 else ""
            tokens = f"{r.tokens_in + r.tokens_out}tok" if r.tokens_in else ""
            dur = f"{r.duration_ms}ms" if r.duration_ms else ""

            # Truncate name to fit
            max_name = 35
            display_name = name[:max_name] + "…" if len(name) > max_name else name

            line = f"  │ {status} {display_name:<{max_name + 1}} {r.provider:<14} {attempts:<6} {dur:>7} │"
            print(line)

            if verbose or not r.passed:
                for ok, reason in r.assertion_results:
                    print(f"  │   {reason:<61}│")
                if r.error:
                    print(f"  │   error: {r.error[:55]:<61}│")

        print(f"  └{'─' * 64}┘")
        print()

    # Summary
    providers_tested = sorted(set(r.provider for r in results))
    total_tokens = sum(r.tokens_in + r.tokens_out for r in results)
    total_time = sum(r.duration_ms for r in results)
    print(f"  Providers: {', '.join(providers_tested)}")
    print(f"  Total: {total_tokens} tokens, {total_time / 1000:.1f}s")
    print()


def results_to_json(results: list[EvalResult]) -> str:
    """Convert results to JSON for CI consumption."""
    evals_by_id = {e.id: e for e in get_evals()}
    return json.dumps(
        {
            "passed": all(r.passed for r in results),
            "total": len(results),
            "failures": sum(1 for r in results if not r.passed),
            "results": [
                {
                    "eval_id": r.eval_id,
                    "eval_name": evals_by_id.get(r.eval_id, PromptEval(id="?", name="?", suite="?")).name,
                    "suite": evals_by_id.get(r.eval_id, PromptEval(id="?", name="?", suite="?")).suite,
                    "provider": r.provider,
                    "passed": r.passed,
                    "attempts": r.attempts,
                    "tokens": r.tokens_in + r.tokens_out,
                    "duration_ms": r.duration_ms,
                    "assertions": [{"passed": ok, "reason": reason} for ok, reason in r.assertion_results],
                    "error": r.error or None,
                }
                for r in results
            ],
        },
        indent=2,
    )


# ─── CLI ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Prompt CI Evaluator")
    parser.add_argument("--provider", "-p", help="Single provider to test")
    parser.add_argument("--suite", "-s", help="Suite filter (tool_call, multi_turn, format, regression)")
    parser.add_argument("--eval", "-e", help="Single eval ID to run")
    parser.add_argument("--ci", action="store_true", help="CI mode: exit 1 on any failure")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show all assertion details")
    parser.add_argument("--list", "-l", action="store_true", help="List available evals")
    args = parser.parse_args()

    if args.list:
        evals = get_evals()
        suites = {}
        for e in evals:
            suites.setdefault(e.suite, []).append(e)
        for suite, suite_evals in suites.items():
            print(f"\n  {suite}:")
            for e in suite_evals:
                rounds = f" ({len(e.rounds)} rounds)" if e.rounds else ""
                print(f"    {e.id:<25} {e.name}{rounds}")
        print()
        return

    providers = [args.provider] if args.provider else None

    results = asyncio.run(
        run_suite(
            providers=providers,
            suite_filter=args.suite,
            eval_filter=args.eval,
        )
    )

    if args.json:
        print(results_to_json(results))
    else:
        print_results(results, verbose=args.verbose)

    if args.ci and any(not r.passed for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
