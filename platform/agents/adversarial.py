"""
Adversarial Guard — Detect slop, hallucination, mock, and lies in agent output.
================================================================================

Two-layer Swiss Cheese model:
- L0: Deterministic fast checks (regex, heuristics) — 0ms
- L1: Semantic LLM check (different model than producer) — optional, ~5s

Runs INSIDE _execute_node() after agent produces output, BEFORE storing in memory.
Rejects output with a reason; the pattern engine can retry or flag.

SCOPE — what this guard covers (OUTPUT quality):
-------------------------------------------------
  ✓ Slop / filler / placeholder text
  ✓ Mock/stub implementations (NotImplementedError, TODO, pass)
  ✓ Fake build scripts (echo "BUILD SUCCESS")
  ✓ Test cheating — skip/xtest/empty body/assert True/except:pass/coverage=0
  ✓ Code slop — @ts-ignore, # type:ignore, !important, dead vendor prefixes
  ✓ Hallucination — claims actions without tool evidence
  ✓ Stack mismatch — wrong language for declared project tech stack
  ✓ Missing tests when source files are written
  ✓ L1: semantic review via a *different* LLM than the producer

SCOPE — what is NOT here (see skills/qa-adversarial-llm.md):
--------------------------------------------------------------
  ✗ Prompt injection attacks on the platform itself (SBD-02)
  ✗ System prompt leakage resistance (SBD-17)
  ✗ RAG data isolation — cross-user retrieval (SBD-18)
  ✗ LLM output → exec/DB injection (SBD-19)
  ✗ Jailbreak / role-play bypasses
  Those are in the qa-adversarial-llm skill and the security-hacking workflow.

INSPIRATION:
------------
  Swiss Cheese model: James Reason (1990) — each layer catches what others miss.
  L1 adversarial reviewer idea: inspired by Constitutional AI (Anthropic, 2022)
  and adversarial collaboration pattern in GoodAI / Pentagi red-team workflows
  (https://github.com/vxcontrol/pentagi). Our RSSI team (security-hacking.yaml)
  is the offensive counterpart — agents actively attack the system they built.
"""

from __future__ import annotations

import json
import logging
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GuardResult:
    """Result of adversarial guard check."""

    passed: bool
    score: int = 0  # 0 = clean, higher = worse
    issues: list[str] = None  # list of detected issues
    level: str = ""  # "L0" or "L1"

    def __post_init__(self):
        if self.issues is None:
            self.issues = []

    @property
    def summary(self) -> str:
        if self.passed:
            return "APPROVED"
        return f"REJECTED (score={self.score}): " + "; ".join(self.issues[:5])


# ── L0: Deterministic Fast Checks ──────────────────────────────

# Slop patterns — generic filler that adds no value
_SLOP_PATTERNS = [
    (r"\blorem ipsum\b", "Lorem ipsum placeholder text"),
    (r"\bfoo\s*bar\s*baz\b", "Placeholder foo/bar/baz"),
    (r"(?:https?://)?example\.com", "example.com placeholder URL"),
    (r"\bplaceholder\b.*\btext\b", "Placeholder text"),
    (r"\bTBD\b", "TBD marker — incomplete work"),
    (r"\bXXX\b", "XXX marker — needs attention"),
]

# Mock/stub patterns — fake implementations
_MOCK_PATTERNS = [
    (r"#\s*TODO\s*:?\s*implement", "TODO implement marker"),
    (r"//\s*TODO\s*:?\s*implement", "TODO implement marker"),
    (
        r"raise\s+NotImplementedError\b(?!\s*#\s*pragma)",
        "NotImplementedError without pragma",
    ),
    (r"pass\s*#\s*(?:todo|fixme|implement)", "pass with TODO comment"),
    (
        r"return\s+(?:None|null|undefined)\s*#\s*(?:todo|stub|mock)",
        "Stub return with TODO",
    ),
    (
        r"(?:fake|mock|dummy|hardcoded)\s+(?:data|response|result|value)",
        "Fake/mock data",
    ),
    (r"def\s+\w+\([^)]*\)\s*:\s*\n\s+pass\s*$", "Empty function body (pass)"),
    (r'console\.log\s*\(\s*["\']test', "console.log('test') — debug leftover"),
]

# Fake build script patterns — scripts that do nothing
_FAKE_BUILD_PATTERNS = [
    (r'echo\s+["\'].*placeholder', "Fake build script — placeholder echo"),
    (r'echo\s+["\'].*stub', "Fake build script — stub echo"),
    (r'echo\s+["\']BUILD\s+SUCCESS', "Fake build script — hardcoded SUCCESS"),
    (r'echo\s+["\']Tests?\s+passed', "Fake build script — hardcoded test pass"),
    (
        r"exit\s+0\s*#?\s*(?:stub|fake|placeholder|todo)",
        "Fake script — exit 0 placeholder",
    ),
    (r"#!/bin/sh\s*\n\s*(?:echo|true|:)\s", "Empty shell script — does nothing"),
]

# Test integrity patterns — agents cheating tests so they pass
# Applied ONLY to test files (path contains test/spec/__tests__)
# SOURCE: internal rule — "do not cheat tests or test libraries so tests pass"
# WHY: an agent that skips failing tests, weakens assertions, or mocks the SUT
#      produces a false green CI. The bug is hidden, not fixed.
_TEST_CHEAT_PATTERNS = [
    # Skipping tests instead of fixing them
    (r"@pytest\.mark\.skip\b", "pytest.mark.skip — test bypassed instead of fixed"),
    (r"@pytest\.mark\.skipif\b", "pytest.mark.skipif — conditional test bypass"),
    (r"\bxit\s*\(", "xit() — Jasmine/Jest skipped test"),
    (r"\bxtest\s*\(", "xtest() — skipped test"),
    (r"\bxdescribe\s*\(", "xdescribe() — skipped test suite"),
    (r"test\.skip\s*\(", "test.skip() — Jest/Vitest skipped test"),
    (r"it\.skip\s*\(", "it.skip() — Jest skipped test"),
    (r"describe\.skip\s*\(", "describe.skip() — Jest skipped suite"),
    # Trivially-passing (useless) assertions
    (r"\bassert\s+True\s*(?:#|$)", "assert True — trivially passes, tests nothing"),
    (r"\bassert\s+1\s*(?:#|$)", "assert 1 — trivially passes, tests nothing"),
    (r"expect\([^)]+\)\.toBeTruthy\(\)\s*;?\s*$", "toBeTruthy() — weak, tests nothing concrete"),
    # Empty test bodies — test exists but does nothing
    (
        r"def test_\w+\s*\([^)]*\)\s*:\s*\n\s+(?:pass|\.\.\.)$",
        "Empty test function — passes trivially",
    ),
    (r"it\s*\([^,]+,\s*\(\)\s*=>\s*\{\s*\}\s*\)", "Empty Jest/Vitest test body"),
    # Swallowing failures in test code
    (
        r"except\s+(?:Exception|BaseException|AssertionError)\s*:\s*\n\s+pass\s*$",
        "except Exception: pass in test — silences assertion failures",
    ),
    # Coverage configuration lowered to pass
    (r"--cov-fail-under\s*=\s*0\b", "Coverage threshold set to 0 — defeats coverage"),
    (r"fail_under\s*=\s*0\b", "fail_under=0 in coverage config — defeats coverage"),
    (r"--cov-fail-under\s*=\s*[1-9]\b", "Coverage threshold ≤9% — effectively zero"),
    # Conditional bypass injected into source code (not test file) to make test pass
    (
        r"if\s+os\.(?:getenv|environ).*[\"'](?:TEST_MODE|CI_SKIP|SKIP_TESTS|TESTING_BYPASS)[\"']",
        "TEST_MODE bypass in production code — cheats test by changing real behavior",
    ),
]

# Code slop patterns — lazy shortcuts that produce unmaintainable code
# Applied to ALL code_write files, lower score than test cheating
# SOURCE: internal clean-code rules (see skills/clean-code.md)
_CODE_SLOP_PATTERNS = [
    # TypeScript/JavaScript — type safety suppression
    (r"//\s*@ts-ignore\b", "@ts-ignore — TypeScript error suppressed instead of fixed"),
    (r"//\s*@ts-nocheck\b", "@ts-nocheck — TypeScript disabled for entire file"),
    (r"/\*\s*eslint-disable\b", "eslint-disable block — lint rules suppressed"),
    # Python — type/error suppression
    (r"#\s*type:\s*ignore\b", "# type: ignore — mypy error suppressed instead of fixed"),
    (
        r"except\s+(?:Exception|BaseException)\s*:\s*\n\s+pass\s*$",
        "except Exception: pass — silently swallows all errors",
    ),
    # CSS — specificity hacks and unnecessary vendor prefixes
    (r"!\s*important\b", "!important — lazy specificity override, fix the selector cascade"),
    (
        r"-webkit-(?:border-radius|box-shadow|transition|transform|animation)\s*:",
        "-webkit- vendor prefix not needed since 2017 (caniuse: >98%)",
    ),
    (
        r"-moz-(?:border-radius|box-shadow|transition|transform|animation)\s*:",
        "-moz- vendor prefix not needed since 2020",
    ),
    # UI/UX — banned patterns
    (
        r"linear-gradient\s*\(",
        "linear-gradient — banned: use flat solid colors from design tokens (var(--color-*))",
    ),
    (
        r"radial-gradient\s*\(",
        "radial-gradient — banned: use flat solid colors from design tokens",
    ),
    (
        r"[\U0001F300-\U0001F9FF\U00002600-\U000027BF\U0001FA00-\U0001FAFF]",
        "emoji in source — banned: use text labels or SVG icons from the design system",
    ),
    (
        r"style\s*=\s*\{\s*\{",
        "inline style object — banned: use CSS classes from design tokens / CSS modules",
    ),
    (
        r"(?:color|background|border-color)\s*:\s*#[0-9a-fA-F]{3,8}\b",
        "hardcoded hex color — use CSS custom property: var(--color-*) from tokens",
    ),
]
_HALLUCINATION_PATTERNS = [
    (
        r"j'ai\s+(?:deploye|déployé|lancé|exécuté|testé|vérifié|créé le fichier|commit)",
        "Claims action without tool evidence",
    ),
    (
        r"i(?:'ve| have)\s+(?:deployed|tested|created|committed|executed|verified)",
        "Claims action without tool evidence",
    ),
    (
        r"le\s+(?:build|test|deploy)\s+(?:a|est)\s+(?:réussi|passé|ok)",
        "Claims success without evidence",
    ),
    (r"voici\s+(?:le|les)\s+résultat", "Claims to show results"),
]

# Lie patterns — inventing file paths, URLs, or data
_LIE_PATTERNS = [
    (
        r"(?:fichier|file)\s+(?:créé|created|saved)\s*:\s*\S+",
        "Claims file creation — verify with tool_calls",
    ),
    (
        r"(?:http|https)://(?:staging|prod|api)\.\S+(?:\.local|\.internal)",
        "Invented internal URL",
    ),
]

# Security vulnerability patterns — hardcoded secrets and unsafe code
# SOURCE: OWASP Top 10 + internal security rules
_HARDCODED_SECRET_PATTERNS = [
    (r"""(?:password|passwd|pwd)\s*=\s*['"][^'"]{4,}['"]""", "Hardcoded password literal"),
    (r"""(?:api_key|apikey|api-key)\s*=\s*['"][^'"]{8,}['"]""", "Hardcoded API key"),
    (r"""(?:secret|token|auth_token)\s*=\s*['"][^'"]{8,}['"]""", "Hardcoded secret/token"),
    (r"""(?:private_key|privatekey)\s*=\s*['"][^'"]{8,}['"]""", "Hardcoded private key"),
    (r"""-----BEGIN (?:RSA |EC )?PRIVATE KEY-----""", "Private key embedded in code"),
    (r"""(?:access_key_id|aws_access)\s*=\s*['"][A-Z0-9]{16,}['"]""", "Hardcoded AWS access key"),
]

# Security vulnerability patterns — unsafe operations
_SECURITY_VULN_PATTERNS = [
    (r"""\beval\s*\(""", "eval() — arbitrary code execution risk"),
    (r"""\bexec\s*\(""", "exec() — arbitrary code execution risk"),
    (r"""\bpickle\.loads?\s*\(""", "pickle.loads() — deserialization RCE risk"),
    (r"""\bos\.system\s*\(""", "os.system() — shell injection risk, use subprocess"),
    (r"""cursor\.execute\s*\(f['"]""", "SQL f-string injection — use parameterized queries"),
    (r"""cursor\.execute\s*\(['"].*?%\s*(?:str|repr|format)""", "SQL string format — injection risk"),
    (r"""\bsubprocess\.(?:call|run|Popen)\s*\([^)]*shell\s*=\s*True""", "subprocess shell=True — shell injection"),
    (r"""__import__\s*\(\s*(?:input|request)""", "Dynamic import from user input — RCE risk"),
]

# Architecture violation patterns — structural anti-patterns
# SOURCE: clean architecture rules (see CLAUDE.md / SPECS.md)
_ARCHITECTURE_VIOLATION_PATTERNS = [
    (r"""(?:import|from)\s+.*(?:sqlite3|sqlalchemy|psycopg|pymysql).*\n.*(?:render_template|jinja2|Jinja2)""",
     "DB driver imported in template layer — violates clean architecture", True),
    (r"""cursor\.execute|conn\.execute|db\.execute""",
     "Direct SQL in non-store file — use the store layer", False),
    (r"""requests\.(?:get|post|put|delete)\s*\((?!.*test)""",
     "Raw HTTP call — use the LLM client or dedicated service layer", False),
]

# False fallback patterns — agents using stubs in production code
_FALSE_FALLBACK_PATTERNS = [
    (r"""raise\s+NotImplementedError\s*(?:\([^)]*\))?\s*#?\s*(?:TODO|FIXME|later|implement)""",
     "NotImplementedError with TODO — stub not replaced by real implementation"),
    (r"""#\s*TODO:\s*(?:implement|add|fix|handle|replace)\s+(?:this|later|me)""",
     "TODO comment in production code — work not complete"),
    (r"""return\s+(?:None|False|0|\[\]|\{\}|\"\"\|'')\s*#\s*(?:TODO|FIXME|placeholder|stub)""",
     "Stub return value — placeholder not replaced"),
    (r"""pass\s*#\s*(?:TODO|FIXME|implement|placeholder)""",
     "pass with TODO — implementation missing"),
]

# Maintainability anti-patterns (SWE-CI inspired)
# Shift from "it compiles" to "it is maintainable long-term"
# Applied to code_write files — checks extensibility, not just correctness
# Ref: feat-maintainability-detectors
_MAINTAINABILITY_PATTERNS = [
    # Magic numbers — hardcoded values that should be named constants
    (r"""(?:if|while|for|return|==|!=|<|>|<=|>=)\s*\(?[^0-9]*\b\d{3,}\b""",
     "MAGIC_NUMBER: Large numeric literal in logic — extract to named constant"),
    # Hardcoded string config — URLs, paths, timeouts that should be config
    (r"""(?:url|endpoint|host|server)\s*=\s*['"]https?://[^'"]+['"]""",
     "HARDCODED_CONFIG: URL hardcoded — use environment variable or config"),
    (r"""(?:timeout|delay|interval|retries)\s*=\s*\d{2,}""",
     "HARDCODED_CONFIG: Numeric config hardcoded — use constant or env var"),
    # God function — too many parameters (>5) = poor interface design
    (r"""def\s+\w+\s*\([^)]{200,}\)""",
     "GOD_FUNCTION: Function signature >200 chars — too many parameters, use a config object"),
    # Deep inheritance — extending 3+ levels is fragile
    (r"""class\s+\w+\s*\(\s*\w+\s*\)\s*:.*class\s+\w+\s*\(\s*\w+\s*\)\s*:""",
     "DEEP_INHERITANCE: Prefer composition over deep inheritance chains"),
    # Catch-all error handling — swallows specific errors
    (r"""except\s*:\s*$""",
     "BARE_EXCEPT: Bare except catches SystemExit/KeyboardInterrupt — use except Exception"),
    # String concatenation in loops (performance anti-pattern)
    (r"""for\s+.*:\s*\n\s+\w+\s*\+=\s*['"]""",
     "STRING_CONCAT_LOOP: String concatenation in loop — use join() or StringBuilder"),
    # Mutable default argument (Python footgun)
    (r"""def\s+\w+\s*\([^)]*=\s*(?:\[\]|\{\})\s*[,)]""",
     "MUTABLE_DEFAULT: Mutable default argument (list/dict) — use None + conditional"),
]

# Stack mismatch detection — backend code in wrong language
# Maps declared stack keywords to expected/forbidden file extensions
_STACK_RULES = {
    # If task mentions these keywords, .ts/.js/.py files are wrong
    "rust_project": {
        "keywords": ["rust", "axum", "sqlx", "tonic", "cargo", "macroquad", "bevy", "ggez"],
        # If task ALSO mentions these, suppress the rule (mixed context from sprint learnings)
        "conflicts_with": ["typescript", "react", "next.js", "nextjs", "node.js", "npm run"],
        "wrong_extensions": [".ts", ".js", ".mjs", ".jsx", ".tsx", ".py"],
        "wrong_in_path": ["src/", "app/", "lib/"],
        "message": "STACK_MISMATCH: Code written in TypeScript/JavaScript/Python but project stack is Rust — use .rs files only",
    },
    "svelte_frontend": {
        "keywords": ["sveltekit", "svelte"],
        "conflicts_with": [],
        "wrong_extensions": [".jsx", ".tsx"],
        "wrong_in_path": ["src/frontend/", "src/routes/"],
        "message": "STACK_MISMATCH: Frontend code in React/JSX but project stack is SvelteKit",
    },
    # Mobile stack rules
    "ios_swift": {
        "keywords": ["swift", "swiftui", "ios", "xcode", "uikit"],
        "conflicts_with": [],
        "wrong_extensions": [".kt", ".java", ".ts", ".js", ".dart"],
        "wrong_in_path": ["Sources/", "App/", "Features/", "Models/"],
        "message": "STACK_MISMATCH: iOS app must use Swift/SwiftUI only — no Kotlin/Java/TypeScript",
    },
    "android_kotlin": {
        "keywords": ["kotlin", "jetpack compose", "android", "gradle"],
        "conflicts_with": [],
        "wrong_extensions": [".swift", ".m", ".dart"],
        "wrong_in_path": ["src/main/", "app/src/"],
        "message": "STACK_MISMATCH: Android app must use Kotlin/Compose only — no Swift",
    },
}


# --- Deterministic complexity helpers (no external deps) ---

# Control-flow keywords that add cognitive complexity increments
_CONTROL_FLOW_RE = re.compile(
    r"\b(if|else\s+if|elif|else|for|while|do|switch|case|catch|except|"
    r"guard|repeat|&&|\|\||ternary|\?.*:)\b"
)


def _cognitive_complexity(source: str) -> int:
    """Lightweight cognitive complexity score (SonarQube-style).

    Each control-flow keyword adds 1 + current nesting depth.
    Nesting increments on blocks (braces or indent increase).
    """
    score = 0
    nesting = 0
    prev_indent = 0
    for line in source.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("#"):
            continue
        # Track nesting by indent level (language-agnostic)
        indent = len(line) - len(line.lstrip())
        if indent > prev_indent:
            nesting += 1
        elif indent < prev_indent:
            nesting = max(0, nesting - (prev_indent - indent) // 4)
        prev_indent = indent
        # Each control flow keyword adds 1 + nesting level
        hits = _CONTROL_FLOW_RE.findall(stripped)
        score += len(hits) * (1 + nesting)
    return score


def _max_nesting_depth(source: str) -> int:
    """Max nesting depth via indent tracking (works for any language)."""
    max_depth = 0
    for line in source.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        indent = len(line) - len(line.lstrip())
        depth = indent // 4  # 4-space or 1-tab = 1 level
        if depth > max_depth:
            max_depth = depth
    return max_depth


def _count_imports(source: str) -> int:
    """Count import statements (fan-in coupling proxy)."""
    return len(re.findall(
        r"^\s*(?:import |from .+ import |require\(|use |#include )",
        source, re.MULTILINE
    ))


def _check_stack_mismatch(tool_calls: list, task: str) -> list[str]:
    """Check if code_write tool calls use the wrong language for the declared stack.

    Only triggers when the task *explicitly* declares a stack (e.g. "STACK: Rust",
    "projet Rust/axum", "build with Cargo"). Generic protocol instructions that
    mention multiple stacks as examples (e.g. "Rust: cargo check") are excluded
    by requiring the keyword appears in the [Your task] section, not in the
    injected protocol boilerplate.
    """
    if not tool_calls or not task:
        return []

    # Extract only the user task section — ignore protocol boilerplate that lists
    # all stacks as examples (DEPENDENCY MANIFESTS, BUILD VERIFICATION, etc.)
    task_section = task
    task_marker = "[Your task]:"
    if task_marker in task:
        task_section = task[task.index(task_marker) :]
        # Also strip protocol sections that follow the task
        for proto_marker in (
            "CRITICAL BEHAVIOR RULES",
            "DEPENDENCY MANIFESTS",
            "BUILD VERIFICATION",
            "MANDATORY TOOL USAGE",
        ):
            idx = task_section.find(proto_marker)
            if idx > 0:
                task_section = task_section[:idx]

    task_lower = task_section.lower()
    issues = []
    for rule in _STACK_RULES.values():
        if not any(kw in task_lower for kw in rule["keywords"]):
            continue
        # If conflicting keywords also present, skip rule (mixed context from sprint learnings)
        if rule.get("conflicts_with") and any(cw in task_lower for cw in rule["conflicts_with"]):
            continue
        for tc in tool_calls:
            if tc.get("name") not in ("code_write", "code_edit"):
                continue
            file_path = str(
                tc.get("args", {}).get("file_path", "")
                or tc.get("args", {}).get("path", "")
            )
            if not file_path:
                continue
            has_wrong_ext = any(
                file_path.endswith(ext) for ext in rule["wrong_extensions"]
            )
            in_wrong_path = any(p in file_path for p in rule["wrong_in_path"])
            if has_wrong_ext and in_wrong_path:
                issues.append(rule["message"])
                break  # one issue per rule is enough
    return issues


# Minimum content thresholds by context
_MIN_CONTENT_LENGTH = {
    "dev": 200,
    "qa": 150,
    "devops": 150,
    "architecture": 200,
    "default": 80,
}


def check_l0(
    content: str, agent_role: str = "", tool_calls: list = None, task: str = ""
) -> GuardResult:
    """L0: Fast deterministic checks. Returns immediately."""
    if not content or not content.strip():
        return GuardResult(passed=False, score=10, issues=["Empty output"], level="L0")

    issues = []
    score = 0
    content_lower = content.lower()
    tool_calls = tool_calls or []

    # Tool call names for evidence checking
    tool_names = {tc.get("name", "") for tc in tool_calls}
    has_write_tool = bool(
        tool_names
        & {"code_write", "code_edit", "git_commit", "deploy_azure", "docker_build"}
    )
    # Check stack mismatch — wrong language for declared project stack
    stack_issues = _check_stack_mismatch(tool_calls, task)
    if stack_issues:
        import logging as _log_sm
        _log_sm.getLogger(__name__).warning("STACK_MISMATCH detected: %s", "; ".join(stack_issues))
    for si in stack_issues:
        issues.append(si)
        score += 7  # severe — wrong language is a hard reject

    # Check slop
    for pattern, desc in _SLOP_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            issues.append(f"SLOP: {desc}")
            score += 3

    # Check mock/stub in agent output
    for pattern, desc in _MOCK_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
            issues.append(f"MOCK: {desc}")
            score += 4

    # Check code_write content for fake/mock/stub patterns
    for tc in tool_calls:
        if tc.get("name") not in ("code_write", "code_edit"):
            continue
        file_content = str(tc.get("args", {}).get("content", ""))
        file_path = str(
            tc.get("args", {}).get("path", "")
            or tc.get("args", {}).get("file_path", "")
        )
        if not file_content:
            continue
        # Check for fake build scripts (gradlew, Makefile, build.sh)
        is_build_script = any(
            kw in file_path.lower()
            for kw in ["gradlew", "makefile", "build.sh", "build.bat", "compile.sh"]
        )
        for pattern, desc in _FAKE_BUILD_PATTERNS:
            if re.search(pattern, file_content, re.IGNORECASE | re.MULTILINE):
                issues.append(f"FAKE_BUILD: {desc} in {file_path}")
                score += 7  # severe — fake builds produce false success
                break
        # Check for tiny/empty build scripts
        if is_build_script and len(file_content.strip()) < 50:
            issues.append(
                f"FAKE_BUILD: Suspiciously small build script ({len(file_content)} chars) in {file_path}"
            )
            score += 7
        # Check mock/stub patterns in written files
        for pattern, desc in _MOCK_PATTERNS:
            if re.search(pattern, file_content, re.IGNORECASE | re.MULTILINE):
                issues.append(f"MOCK_IN_CODE: {desc} in {file_path}")
                score += 3
                break  # one mock per file is enough
        # Check test cheating patterns — only in test files
        is_test_file = any(
            kw in file_path.lower()
            for kw in ["test_", "_test.", "/test/", "/tests/", ".spec.", ".test.", "__tests__"]
        )
        if is_test_file:
            for pattern, desc in _TEST_CHEAT_PATTERNS:
                if re.search(pattern, file_content, re.IGNORECASE | re.MULTILINE):
                    issues.append(f"TEST_CHEAT: {desc} in {file_path}")
                    score += 5  # hard reject — cheated test = hidden bug
                    break  # one cheat per file flagged
        # Check code slop patterns — all code files (lower score, warning)
        is_code_file = file_path.lower().endswith(
            (".py", ".ts", ".tsx", ".js", ".jsx", ".css", ".scss", ".less")
        )
        if is_code_file:
            # Token/variable definition files legitimately contain hex colors
            _fn = file_path.lower().rsplit("/", 1)[-1] if "/" in file_path else file_path.lower()
            is_token_file = any(k in _fn for k in ("token", "variable", "theme", "palette"))
            # Scripts/tools use emoji in CLI output (✅/❌) — not user-facing UI
            is_script_file = "/scripts/" in file_path.lower() or "/tools/" in file_path.lower() or _fn.startswith("lint")
            slop_hits = 0
            for pattern, desc in _CODE_SLOP_PATTERNS:
                # Skip hex-color check in token definition files
                if is_token_file and "hardcoded hex" in desc:
                    continue
                # Skip emoji check in scripts/tools (CLI output, not UI)
                if is_script_file and "emoji" in desc:
                    continue
                if re.search(pattern, file_content, re.IGNORECASE | re.MULTILINE):
                    issues.append(f"CODE_SLOP: {desc} in {file_path}")
                    score += 2
                    slop_hits += 1
                    if slop_hits >= 3:
                        break  # cap at 3 slop warnings per file
            # Maintainability checks — extensibility anti-patterns (SWE-CI inspired)
            # Lower score than test cheating — these are warnings, not hard rejects
            maintain_hits = 0
            for pattern, desc in _MAINTAINABILITY_PATTERNS:
                if re.search(pattern, file_content, re.IGNORECASE | re.MULTILINE):
                    issues.append(f"MAINTAINABILITY: {desc} in {file_path}")
                    score += 1  # warning — cumulative
                    maintain_hits += 1
                    if maintain_hits >= 3:
                        break  # cap per file

    # Quality checks — no tests in code_write, high complexity indicators
    if has_write_tool:
        total_lines = 0
        test_files = 0
        source_files = 0
        for tc in tool_calls:
            if tc.get("name") not in ("code_write", "code_edit"):
                continue
            fp = str(
                tc.get("args", {}).get("path", "")
                or tc.get("args", {}).get("file_path", "")
            )
            fc = str(tc.get("args", {}).get("content", ""))
            lines = fc.count("\n") + 1
            total_lines += lines
            if any(kw in fp.lower() for kw in ["test", "spec", "__tests__"]):
                test_files += 1
            elif fp.endswith((".py", ".ts", ".js", ".rs", ".go", ".kt", ".swift")):
                source_files += 1
            # Skip structural quality checks for non-code files
            # (CSS, markdown, JSON, YAML, config — these naturally have deep
            # nesting / many lines without being "complex code")
            _is_code = fp.lower().endswith(
                (".py", ".ts", ".tsx", ".js", ".jsx", ".rs", ".go",
                 ".kt", ".swift", ".java", ".c", ".cpp", ".h", ".hpp",
                 ".cs", ".rb", ".php")
            )
            if not _is_code:
                continue
            # COGNITIVE_COMPLEXITY: nesting × control-flow increments
            # (SonarQube-style: each if/for/while/catch adds 1 + current nesting level)
            if lines > 30:
                cog_score = _cognitive_complexity(fc)
                if cog_score > 25:
                    issues.append(
                        f"HIGH_COGNITIVE_COMPLEXITY: score {cog_score} in {fp} "
                        f"(max 25) — simplify control flow, extract functions."
                    )
                    score += 4
                elif cog_score > 15:
                    issues.append(
                        f"MODERATE_COGNITIVE_COMPLEXITY: score {cog_score} in {fp} "
                        f"— consider splitting complex functions."
                    )
                    score += 2
            # DEEP_NESTING: >4 levels = hard to read
            if lines > 50:
                max_depth = _max_nesting_depth(fc)
                if max_depth > 4:
                    issues.append(
                        f"DEEP_NESTING: {max_depth} levels in {fp} "
                        f"(max 4) — extract inner logic to helper functions."
                    )
                    score += 3
            # HIGH_COUPLING: too many imports = tightly coupled
            if lines > 30:
                import_count = _count_imports(fc)
                if import_count > 12:
                    issues.append(
                        f"HIGH_COUPLING: {import_count} imports in {fp} "
                        f"— reduce dependencies, apply Interface Segregation."
                    )
                    score += 2
            # KISS: file too large — hard to review, edit, and maintain
            if lines > 200 and tc.get("name") == "code_write":
                issues.append(
                    f"FILE_TOO_LARGE: {lines} lines in {fp} — max 200. "
                    f"Split into focused modules (one class/struct per file)."
                )
                score += 4
            # GOD_FILE: multiple classes/structs in one file
            if tc.get("name") == "code_write" and lines > 50:
                _type_decls = len(re.findall(
                    r"^\s*(?:public |private |internal |final )?(?:class|struct|enum|protocol) \w+",
                    fc, re.MULTILINE
                ))
                if _type_decls > 3:
                    issues.append(
                        f"GOD_FILE: {_type_decls} type declarations in {fp} — "
                        f"split into one type per file for maintainability."
                    )
                    score += 3
        # NO_TESTS: agent wrote source code but zero test files
        # Also check if tests already exist via code_read calls (agent didn't write them)
        if source_files >= 3 and test_files == 0:
            # Check if tests were READ (already exist in project)
            tests_read = any(
                any(kw in str(tc.get("args", {}).get("path", "")).lower() for kw in ["test", "spec", "__tests__"])
                for tc in tool_calls
                if tc.get("name") in ("code_read", "list_files")
            )
            if not tests_read:
                issues.append(
                    f"NO_TESTS: {source_files} source files written but 0 test files"
                )
                score += 2  # Warning level — not rejection-worthy for bug-fix tasks

        # NO_BUILD_RUN: agent wrote source files but never called build/test tool
        if source_files >= 1:
            build_tools_used = {
                tc.get("name")
                for tc in tool_calls
                if tc.get("name") in ("build", "test", "lint", "android_build", "android_test")
            }
            if not build_tools_used:
                written_names = ", ".join(
                    os.path.basename(
                        str(tc.get("args", {}).get("path", ""))
                    )
                    for tc in tool_calls
                    if tc.get("name") in ("code_write", "code_edit")
                    and str(tc.get("args", {}).get("path", "")).endswith(
                        (".py", ".ts", ".js", ".rs", ".go", ".kt", ".swift", ".java")
                    )
                )[:120]
                issues.append(
                    f"NO_BUILD_RUN: Wrote {source_files} source files ({written_names}) "
                    f"but never ran build/test — run the compiler to verify code works"
                )
                score += 4

        # NO_TOOLS_USED: execution agents (dev, test, devops) MUST use tools
    # Text-only responses from execution agents are always hallucination
    _exec_roles = ("dev", "fullstack", "backend", "frontend", "worker", "coder",
                   "implementer", "lead", "test", "automation", "devops", "engineer")
    _role_lower_adv = (agent_role or "").lower()
    if any(r in _role_lower_adv for r in _exec_roles) and not tool_calls:
        issues.append(
            "NO_TOOLS_USED: Agent performed zero tool calls despite having access to tools. "
            "Execution agents MUST use tools (code_read, code_write, build, test) — "
            "text-only responses are not acceptable."
        )
        score += 8  # hard reject — must use tools

        # NO_CODE_WRITE: dev/worker/fullstack agents MUST produce code changes
    # If agent only read/listed/built but never wrote code, it's a failure
    _dev_roles = ("dev", "fullstack", "backend", "frontend", "worker", "coder", "implementer", "lead")
    if any(r in _role_lower_adv for r in _dev_roles) and not has_write_tool and tool_calls:
        read_only_tools = {tc.get("name") for tc in tool_calls}
        if read_only_tools <= {"code_read", "list_files", "file_read", "code_search", "build", "test", "memory_search", "deep_search"}:
            issues.append(
                f"NO_CODE_WRITE: Dev agent used {len(tool_calls)} tool calls "
                f"({', '.join(sorted(read_only_tools))}) but NEVER called code_write or code_edit. "
                f"Reading code without fixing it is NOT acceptable."
            )
            score += 7  # hard reject — must produce code

    # LOC_REGRESSION: detect when code_write replaces an existing file with a tiny stub.
    # Agents should use code_read BEFORE code_write to understand existing content.
    # A code_write with <10 lines to a file that was never code_read is suspicious.
    _read_paths = {
        str(tc.get("args", {}).get("path", ""))
        for tc in tool_calls
        if tc.get("name") in ("code_read", "file_read")
    }
    for tc in tool_calls:
        if tc.get("name") == "code_write":
            file_path = str(tc.get("args", {}).get("path", ""))
            new_content = str(tc.get("args", {}).get("content", ""))
            new_lines = len(new_content.strip().splitlines())
            # Flag if writing a tiny file (<10 lines) to a source path never read first
            is_source = any(file_path.endswith(ext) for ext in (".rs", ".py", ".ts", ".js", ".go", ".swift", ".java", ".kt"))
            if is_source and new_lines < 10 and file_path not in _read_paths:
                fname = file_path.rsplit("/", 1)[-1] if "/" in file_path else file_path
                issues.append(
                    f"LOC_REGRESSION: code_write to {fname} has only {new_lines} lines "
                    f"and file was never read first. Use code_read before overwriting "
                    f"existing files to avoid destroying prior work."
                )
                score += 6

    # Check hallucination — only flag if agent claims action WITHOUT corresponding tool call
    if not has_write_tool:
        for pattern, desc in _HALLUCINATION_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                issues.append(f"HALLUCINATION: {desc}")
                score += 5

    # Check lie — claims about file creation without code_write/code_edit tool
    if not has_write_tool:
        for pattern, desc in _LIE_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                issues.append(f"LIE: {desc}")
                score += 5

    # Check minimum content length for execution roles
    # SKIP if agent used write/commit tools — code is in the workspace, not in the response
    role_key = "default"
    role_lower = (agent_role or "").lower()
    for k in _MIN_CONTENT_LENGTH:
        if k in role_lower:
            role_key = k
            break
    min_len = _MIN_CONTENT_LENGTH[role_key]
    # Only check length for non-approve/non-veto responses AND when no code was written via tools
    if not has_write_tool and not any(
        marker in content_lower for marker in ("[approve]", "[veto]", "go/nogo")
    ):
        if len(content.strip()) < min_len:
            issues.append(
                f"TOO_SHORT: {len(content.strip())} chars (min {min_len} for {role_key})"
            )
            score += 2

    # Check for copy-paste of task (agent echoing the prompt)
    # Heuristic: if >70% of content is a quote block, it's probably echo
    quote_lines = sum(1 for line in content.split("\n") if line.strip().startswith(">"))
    total_lines = max(len(content.split("\n")), 1)
    if quote_lines / total_lines > 0.7 and total_lines > 5:
        issues.append("ECHO: Agent mostly quoted the task back")
        score += 4

    # Check for suspicious repeated blocks (copy-paste slop)
    # Use higher threshold for structured content (tables, org charts)
    lines = [line.strip() for line in content.split("\n") if len(line.strip()) > 20]
    if len(lines) > 10:
        seen = {}
        for line in lines:
            seen[line] = seen.get(line, 0) + 1
        repeated = sum(1 for c in seen.values() if c > 3)
        if repeated > 5:
            issues.append(f"REPETITION: {repeated} lines repeated >3 times")
            score += 3

    # Check for missing dependency manifests when code was written
    # Dev agents that write source code MUST also create dep manifests
    if has_write_tool and "dev" in role_lower:
        written_extensions = set()
        has_dep_manifest = False
        for tc in tool_calls:
            if tc.get("name") != "code_write":
                continue
            fpath = str(tc.get("args", {}).get("path", ""))
            # Track what languages were written
            if fpath.endswith((".go",)):
                written_extensions.add("go")
            elif fpath.endswith((".py",)):
                written_extensions.add("python")
            elif fpath.endswith((".ts", ".tsx", ".js", ".jsx")):
                written_extensions.add("node")
            elif fpath.endswith((".rs",)):
                written_extensions.add("rust")
            # Check if dep manifest was created
            fname = fpath.rsplit("/", 1)[-1] if "/" in fpath else fpath
            if fname in (
                "go.mod",
                "go.sum",
                "requirements.txt",
                "setup.py",
                "pyproject.toml",
                "package.json",
                "Cargo.toml",
                "Dockerfile",
                "docker-compose.yml",
            ):
                has_dep_manifest = True
        if written_extensions and not has_dep_manifest:
            lang_str = ", ".join(sorted(written_extensions))
            issues.append(
                f"MISSING_DEPS: Wrote {lang_str} source files but no dependency manifest "
                f"(requirements.txt/package.json/go.mod/Cargo.toml)"
            )
            score += 2  # warning, not hard reject

        # Detect fake test files — markdown/plan files created inside tests/ directory
        for tc in tool_calls:
            if tc.get("name") not in ("code_write", "code_edit"):
                continue
            fp = str(
                tc.get("args", {}).get("path", "")
                or tc.get("args", {}).get("file_path", "")
            ).lower()
            if (
                "tests/" in fp or "/test/" in fp or fp.startswith("test")
            ) and fp.endswith((".md", ".txt", ".plan", ".todo")):
                issues.append(
                    f"FAKE_TESTS: Non-code file '{fp}' created in test directory — use actual test code"
                )
                score += 6  # hard reject

    # ── NEW L0 CHECKS ────────────────────────────────────────────────────────

    # HARDCODED_SECRET: credentials hardcoded in source files (not .env/.example)
    for tc in tool_calls:
        if tc.get("name") not in ("code_write", "code_edit"):
            continue
        fp = str(tc.get("args", {}).get("path", "") or tc.get("args", {}).get("file_path", ""))
        fc = str(tc.get("args", {}).get("content", ""))
        if not fc or any(x in fp.lower() for x in [".env.example", ".env.sample", ".md", "readme"]):
            continue
        for pattern, desc in _HARDCODED_SECRET_PATTERNS:
            if re.search(pattern, fc, re.IGNORECASE):
                issues.append(f"HARDCODED_SECRET: {desc} in {fp}")
                score += 8  # near-hard-reject: security risk

    # SECURITY_VULN: unsafe operations in non-test code
    for tc in tool_calls:
        if tc.get("name") not in ("code_write", "code_edit"):
            continue
        fp = str(tc.get("args", {}).get("path", "") or tc.get("args", {}).get("file_path", ""))
        fc = str(tc.get("args", {}).get("content", ""))
        if not fc:
            continue
        is_test = any(kw in fp.lower() for kw in ["test_", "_test.", "/test/", "/tests/", ".spec."])
        for pattern, desc in _SECURITY_VULN_PATTERNS:
            if re.search(pattern, fc, re.IGNORECASE | re.MULTILINE):
                if is_test and "eval" in pattern:
                    continue  # eval in test fixtures is acceptable
                issues.append(f"SECURITY_VULN: {desc} in {fp}")
                score += 6

    # FALSE_FALLBACK: stubs/placeholders left in production code
    for tc in tool_calls:
        if tc.get("name") not in ("code_write", "code_edit"):
            continue
        fp = str(tc.get("args", {}).get("path", "") or tc.get("args", {}).get("file_path", ""))
        fc = str(tc.get("args", {}).get("content", ""))
        if not fc:
            continue
        is_test = any(kw in fp.lower() for kw in ["test_", "_test.", ".spec."])
        if not is_test:
            for pattern, desc in _FALSE_FALLBACK_PATTERNS:
                if re.search(pattern, fc, re.IGNORECASE | re.MULTILINE):
                    issues.append(f"FALSE_FALLBACK: {desc} in {fp}")
                    score += 4
                    break  # one per file

    # MISSING_TRACEABILITY: code written without any reference comment
    # Only for non-trivial source files (>30 lines), not config/migration/test files
    _TRACE_PATTERN = re.compile(
        r"#\s*(?:Ref|Feature|Story|Epic|Ticket|REQ|FEAT|US|EPIC|Traceability|TODO-\d+|JIRA)[\s:\-]",
        re.IGNORECASE,
    )
    _SKIP_TRACE_EXTS = {".md", ".txt", ".json", ".yml", ".yaml", ".env", ".toml", ".cfg", ".ini", ".lock"}
    for tc in tool_calls:
        if tc.get("name") != "code_write":  # only NEW files, not edits
            continue
        fp = str(tc.get("args", {}).get("path", "") or tc.get("args", {}).get("file_path", ""))
        fc = str(tc.get("args", {}).get("content", ""))
        if not fc or not fp:
            continue
        ext = "." + fp.rsplit(".", 1)[-1].lower() if "." in fp else ""
        is_config = any(kw in fp.lower() for kw in ["migration", "conftest", "settings", "__init__", "config."])
        is_test = any(kw in fp.lower() for kw in ["test_", "_test.", ".spec."])
        if ext in _SKIP_TRACE_EXTS or is_config or is_test:
            continue
        lines = fc.count("\n") + 1
        if lines < 30:
            continue  # small files exempt
        if not _TRACE_PATTERN.search(fc[:1500]):  # check header only (first 1500 chars)
            issues.append(
                f"MISSING_TRACEABILITY: No # Ref/Feature/Story comment in {fp} "
                f"({lines} lines) — add '# Ref: FEAT-xxx — <feature name>' at top"
            )
            score += 3  # warning: encourages but doesn't block

    # MISSING_UUID_REF: for migration projects, code/tests must reference legacy item UUIDs
    _UUID_REF_PATTERN = re.compile(
        r"(?:li-|feat-|us-|ac-)[a-f0-9]{6,8}", re.IGNORECASE,
    )
    for tc in tool_calls:
        if tc.get("name") not in ("code_write", "code_edit"):
            continue
        fp = str(tc.get("args", {}).get("path", "") or tc.get("args", {}).get("file_path", ""))
        fc = str(tc.get("args", {}).get("content", "") or tc.get("args", {}).get("new_content", ""))
        if not fc or not fp:
            continue
        is_test = any(kw in fp.lower() for kw in ["test_", "_test.", ".spec.", ".test."])
        if is_test and not _UUID_REF_PATTERN.search(fc):
            issues.append(
                f"MISSING_UUID_REF: Test file {fp} has no traceability UUID reference "
                f"(li-xxx, feat-xxx, us-xxx, ac-xxx) — add story/AC UUID in test name or comment"
            )
            score += 2  # soft encouragement

    # Check build tool failures — only flag if the LAST build/test call failed.
    # Earlier failures are OK if the agent self-corrected (iterative fix cycle).
    if tool_calls:
        last_build_result: dict | None = None
        for tc in tool_calls:
            if tc.get("name") in ("build", "test", "lint"):
                last_build_result = tc
        if last_build_result:
            result_str = str(last_build_result.get("result", ""))
            if "[FAIL]" in result_str or "command not found" in result_str.lower():
                cmd = str(last_build_result.get("args", {}).get("command", "?"))[:80]
                issues.append(
                    f"BUILD_FAILED: Tool '{last_build_result.get('name')}' failed: {cmd!r} — "
                    f"fix errors before approving"
                )
                score += 7  # hard reject — broken build cannot be approved

    # ── L0 deterministic: only things regex CAN reliably catch ─────────
    # Brief compliance, code quality, design coherence → L1 LLM reviewer.
    # L0 only catches structural/syntactic issues that are 100% deterministic.

    # CHECK: Duplicate HTML documents concatenated (agent wrote over without cleaning)
    for tc in tool_calls:
        if tc.get("name") != "code_write":
            continue
        fc = str(tc.get("args", {}).get("content", ""))
        fp = str(tc.get("args", {}).get("path", "") or "")
        if fp.endswith((".html", ".htm")):
            doctype_count = fc.lower().count("<!doctype")
            if doctype_count > 1:
                issues.append(f"DUPLICATE_CODE: {doctype_count} <!DOCTYPE> in {fp} — concatenated")
                score += 5

    threshold = 5  # reject if score >= threshold
    # QA/test agents get a higher threshold — their auto-injected reports
    # trigger false positives for "hallucination" (claiming actions without tool calls)
    if any(k in role_lower for k in ("qa", "test", "validation", "e2e")):
        threshold = 8

    # LLM-aware threshold scaling: weaker models (MiniMax-M2.7) produce more
    # false positives on SLOP/HALLUCINATION detectors — raise threshold to reduce
    # unrecoverable rejection loops (91.5% rejection rate observed with MiniMax)
    try:
        from ..config import get_config
        _llm_cfg = get_config().llm
        _primary = getattr(_llm_cfg, "default_provider", "") or ""
        _model = getattr(_llm_cfg, "default_model", "") or ""
        # Tier 1 (strong): gpt-5*, claude-*, gemini-* → default threshold
        # Tier 2 (medium): minimax, mistral, llama → +2 threshold
        # Tier 3 (weak): local-mlx, ollama → +3 threshold
        _weaker_providers = {"minimax", "nvidia", "mistral"}
        _weakest_providers = {"local-mlx", "ollama"}
        if _primary in _weakest_providers:
            threshold += 3
        elif _primary in _weaker_providers:
            threshold += 2
    except Exception:
        pass  # config unavailable — keep default threshold

    return GuardResult(
        passed=score < threshold,
        score=score,
        issues=issues,
        level="L0",
    )


async def check_l1(
    content: str,
    task: str,
    agent_role: str = "",
    agent_name: str = "",
    tool_calls: list = None,
    pattern_type: str = "",
) -> GuardResult:
    """L1: Semantic LLM check using a DIFFERENT model than the producer.

    Asks a reviewer LLM to evaluate the output for:
    - Completeness vs the task
    - Factual accuracy (no hallucination)
    - Genuine work (no slop/mock/stub)
    - Honesty (claims match tool evidence)
    """
    try:
        from ..llm.client import LLMMessage, get_llm_client

        # Build evidence summary from tool calls
        evidence = "No tools used."
        if tool_calls:
            evidence_lines = []
            for tc in tool_calls[:15]:
                name = tc.get("name", "?")
                result_preview = str(tc.get("result", ""))[:400]
                evidence_lines.append(f"- {name}: {result_preview}")
            evidence = "\n".join(evidence_lines)

        # Pattern-aware context for multi-agent patterns
        pattern_context = ""
        if pattern_type in ("aggregator", "parallel"):
            pattern_context = (
                f"\n- MULTI-AGENT PATTERN ({pattern_type}): This agent covers ONLY their role ({agent_role}). "
                "Other agents cover other roles. Do NOT reject for 'incomplete' if agent addressed their own expertise."
            )
        elif pattern_type == "hierarchical":
            pattern_context = (
                f"\n- HIERARCHICAL PATTERN: This agent ({agent_role}) may be a LEAD/COORDINATOR or a WORKER."
                "\n  LEADS/COORDINATORS: They REVIEW/SUMMARIZE work done by other agents. They KNOW about files"
                " that exist in the workspace because OTHER agents created them. A lead saying 'server.js has endpoints'"
                " is NOT hallucination — other workers created that file."
                "\n  WORKERS: They CREATE code via code_write. Workers MAY write extra files."
                "\n  TESTERS/QA: They VERIFY work from workers. They may reference files without code_read"
                " if they inspected them visually in the workspace."
                "\n  CRITICAL: In hierarchical patterns, files exist from OTHER agents' work."
                " Do NOT flag 'hallucination' for mentioning files that are NOT in THIS agent's tool evidence."
                " The agent can see the workspace and knows what other agents wrote."
                "\n  If list_files output is truncated (shows '...'), do NOT assume missing files are absent."
            )
        elif pattern_type == "sequential":
            pattern_context = (
                "\n- SEQUENTIAL PATTERN: This agent covers ONE step in a chain. "
                "Do NOT reject for 'incomplete' if agent addressed their own role contribution."
            )

        prompt = f"""Evaluate this agent output for quality. Score 0-10 (0=excellent, 10=garbage).

AGENT: {agent_name} ({agent_role})
TASK: {task[:500]}

TOOLS ACTUALLY USED:
{evidence}

AGENT OUTPUT:
{content[:2000]}

IMPORTANT CONTEXT:
- If the agent used code_write/code_edit tools, the REAL work is in the tool calls, not the text.
- A short text response is FINE if code_write was actually called with real content.
- Only flag HALLUCINATION if claims are NOT visible in tool evidence above.
- Only available tools: code_read, code_write, code_edit, list_files, deep_search, build, test. Do NOT penalize for not using tools that don't exist (git_commit, deploy, docker_deploy, etc).
- Do NOT penalize for missing Dockerfile if the project is a native app (Swift, macOS, iOS, Android, desktop). Docker is only relevant for web/server projects.
- If the agent found build errors but did NOT use code_edit/code_write to fix them, that IS a valid reason to reject.{pattern_context}

Check for:
1. SLOP: Generic filler, placeholder text, no real substance
2. HALLUCINATION: Claims actions not supported by tool evidence
3. MOCK: Fake implementations (TODO, pass, NotImplementedError, dummy data)
4. LIES: Invented file paths, URLs, results not in tool output
5. ECHO: Just rephrasing the task without doing real work
6. STACK_MISMATCH: Code written in wrong language for declared stack
7. BRIEF_VIOLATION: Output does not match what was asked. Examples:
   - Task says "single file" but multiple code files were written
   - Task says "dark theme" but output is light theme
   - Task says "Canvas" but output uses DOM elements
   - HTML references external files (src="...", href="...") when single-file was requested
8. EMOJI_IN_CODE: Emoji characters in user-facing HTML/CSS/JS. Use text or SVG icons.
9. DUPLICATE_CODE: Two implementations concatenated in one file (e.g. two <!DOCTYPE>)
10. DEAD_CODE: CSS/JS that is defined but never used (e.g. theme toggle without CSS variants)

Respond ONLY with XML:
<adversarial_review>
  <score>0-10</score>
  <issues>
    <issue>issue1</issue>
    <issue>issue2</issue>
  </issues>
  <verdict>APPROVE|REJECT</verdict>
</adversarial_review>"""

        client = get_llm_client()
        resp = await client.chat(
            messages=[LLMMessage(role="user", content=prompt)],
            system_prompt="You are an adversarial code reviewer. Be strict. Reject slop and hallucination. Real work only.",
            temperature=0.1,
            max_tokens=300,
        )

        raw = resp.content.strip()
        if "```xml" in raw:
            raw = raw.split("```xml", 1)[1].split("```", 1)[0].strip()
        elif "```" in raw:
            raw = raw.split("```", 1)[1].split("```", 1)[0].strip()

        xml = raw
        m = re.search(r"<adversarial_review>.*?</adversarial_review>", xml, re.DOTALL)
        if m:
            xml = m.group(0)
        root = ET.fromstring(xml)
        if root.tag != "adversarial_review":
            raise ValueError(f"Invalid adversarial XML root tag: {root.tag}")
        score_text = (root.findtext("score") or "0").strip()
        l1_score = int(score_text)
        l1_issues = [
            (n.text or "").strip()
            for n in root.findall("./issues/issue")
            if (n.text or "").strip()
        ]
        verdict = (root.findtext("verdict") or "APPROVE").strip()

        # HALLUCINATION/SLOP/STACK_MISMATCH in issues = reject UNLESS:
        # - agent used code_write/code_edit (wrote real code)
        # - agent is in hierarchical pattern and is a lead/tester (references others' work)
        has_critical = any(
            "HALLUCINATION" in i.upper()
            or "SLOP" in i.upper()
            or "STACK_MISMATCH" in i.upper()
            for i in l1_issues
        )
        # If agent actually wrote code, don't auto-reject for hallucination claims
        used_write_tools = tool_calls and any(
            tc.get("name", "") in ("code_write", "code_edit", "git_commit")
            for tc in tool_calls
        )
        # In hierarchical patterns, leads/testers reference files from workers — not hallucination
        is_hierarchical_reviewer = pattern_type == "hierarchical" and any(
            r in (agent_role or "").lower()
            for r in (
                "lead",
                "test",
                "qa",
                "review",
                "architect",
                "senior",
                "principal",
            )
        )
        if has_critical and not used_write_tools and not is_hierarchical_reviewer:
            l1_score = max(l1_score, 7)  # floor at 7 = force retry
            verdict = "REJECT"

        # Scale L1 threshold for weaker LLM providers (mirrors L0 scaling)
        _l1_threshold = 6
        try:
            from ..config import get_config
            _l1_prov = getattr(get_config().llm, "default_provider", "") or ""
            if _l1_prov in ("local-mlx", "ollama"):
                _l1_threshold += 3
            elif _l1_prov in ("minimax", "nvidia", "mistral"):
                _l1_threshold += 2
        except Exception:
            pass

        return GuardResult(
            passed=verdict == "APPROVE" and l1_score < _l1_threshold,
            score=l1_score,
            issues=[f"L1: {i}" for i in l1_issues],
            level="L1",
        )

    except Exception as e:
        logger.warning(f"L1 adversarial check failed: {e}")
        # On failure, don't block — L0 is the safety net
        return GuardResult(passed=True, score=0, issues=[], level="L1-skipped")


def record_guard_event(
    run_id: str,
    agent_name: str,
    agent_role: str,
    guard_result: "GuardResult",
) -> None:
    """Persist adversarial guard result to adversarial_events table (best-effort)."""
    try:
        from ..db.migrations import get_db
        # Extract dominant check type from first issue prefix
        check_type = "PASS"
        if guard_result.issues:
            first = guard_result.issues[0]
            check_type = first.split(":")[0].strip() if ":" in first else first[:30]
        db = get_db()
        try:
            db.execute(
                """INSERT INTO adversarial_events
                   (run_id, agent_name, agent_role, check_type, score, passed, issues_json, level)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run_id or "",
                    agent_name or "",
                    agent_role or "",
                    check_type,
                    guard_result.score,
                    guard_result.passed,
                    json.dumps(guard_result.issues[:10]),
                    guard_result.level,
                ),
            )
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.debug("record_guard_event failed: %s", e)


def record_code_traceability(
    run_id: str,
    agent_name: str,
    file_path: str,
    content: str,
    epic_id: str = "",
    feature_id: str = "",
) -> None:
    """Extract traceability refs from a written file and store in code_traceability."""
    try:
        import re as _re
        # Parse ref tags from file header (first 2000 chars)
        header = content[:2000]
        ref_pattern = _re.compile(
            r"#\s*(?:Ref|Feature|Story|Epic|Ticket|REQ|FEAT|US|EPIC)[\s:\-]+([A-Za-z0-9\-_\.]+)",
            _re.IGNORECASE,
        )
        refs = ref_pattern.findall(header)
        ref_tag = refs[0] if refs else ""

        # Extract feature_id from ref if not provided
        if not feature_id and refs:
            for ref in refs:
                if ref.lower().startswith("feat-") or ref.lower().startswith("feature-"):
                    feature_id = ref
                    break

        from ..db.migrations import get_db
        db = get_db()
        try:
            db.execute(
                """INSERT INTO code_traceability
                   (run_id, epic_id, feature_id, file_path, ref_tag, agent_name)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (run_id or "", epic_id or "", feature_id or "", file_path, ref_tag, agent_name or ""),
            )
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.debug("record_code_traceability failed: %s", e)


async def run_guard(
    content: str,
    task: str = "",
    agent_role: str = "",
    agent_name: str = "",
    tool_calls: list = None,
    pattern_type: str = "",
    enable_l1: bool = True,
    project_id: str = "",
) -> GuardResult:
    """Run the full adversarial guard pipeline: L0 then L1.

    L0 always runs (deterministic, 0ms).
    L1 runs only for execution patterns (not discussions) and if L0 passes.
    project_id: when set, loads custom_patterns from projects/<id>.yaml.
    """
    # Load project-specific custom patterns if project_id provided
    project_patterns: list[tuple[str, int, str]] = []
    project_threshold: int | None = None
    if project_id:
        try:
            import os as _os
            import yaml as _yaml  # optional dep

            _yaml_path = _os.path.join(
                _os.path.dirname(__file__), "..", "..", "projects", f"{project_id}.yaml"
            )
            _yaml_path = _os.path.normpath(_yaml_path)
            if _os.path.exists(_yaml_path):
                with open(_yaml_path) as _f:
                    _cfg = _yaml.safe_load(_f) or {}
                _adv = _cfg.get("adversarial", {})
                if isinstance(_adv.get("threshold"), int):
                    project_threshold = _adv["threshold"]
                for _pat in _adv.get("custom_patterns", []):
                    _p = _pat.get("pattern", "")
                    _s = int(_pat.get("score", 3))
                    _m = _pat.get("message", f"Project pattern: {_p}")
                    if _p:
                        project_patterns.append((_p, _s, _m))
        except Exception as _pe:
            logger.debug(
                "run_guard: failed to load project patterns for %s: %s", project_id, _pe
            )

    # L0: Fast deterministic
    l0 = check_l0(content, agent_role, tool_calls, task)

    # Apply project-specific L0 patterns on top of global ones
    if project_patterns:
        import re as _re2

        extra_score = 0
        extra_issues: list[str] = []
        for _pattern, _score, _msg in project_patterns:
            try:
                if _re2.search(_pattern, content, _re2.IGNORECASE | _re2.MULTILINE):
                    extra_score += _score
                    extra_issues.append(_msg)
            except re.error:
                pass
        if extra_issues:
            l0.score += extra_score
            l0.issues.extend(extra_issues)
            _eff_threshold = project_threshold if project_threshold is not None else 5
            l0.passed = l0.score < _eff_threshold
            if not l0.passed:
                logger.info(
                    "GUARD L0 PROJECT-REJECT [%s] project=%s score=%d: %s",
                    agent_name,
                    project_id,
                    l0.score,
                    "; ".join(extra_issues[:3]),
                )
                return l0

    if not l0.passed:
        logger.info(f"GUARD L0 REJECT [{agent_name}]: {l0.summary}")
        return l0

    # L1: Semantic LLM check — only for execution patterns AND dev/ops roles
    # Discussion patterns (network, human-in-the-loop) are debating, not producing code
    # Strategic/business/management roles produce analysis, not code — skip L1
    execution_patterns = {
        "sequential",
        "hierarchical",
        "parallel",
        "loop",
        "aggregator",
    }
    _non_dev_roles = {
        "strat",
        "dirprog",
        "product",
        "metier",
        "business",
        "portfolio",
        "lean",
        "scrum",
        "rh",
        "programme",
        # English equivalents (agent roles can be in English)
        "program",
        "director",
        "manager",
        "master",
        "officer",
        "chef",
        "coordinat",
    }
    role_lower = (agent_role or "").lower()
    agent_name_lower = (agent_name or "").lower()
    is_dev_role = not any(
        nr in role_lower or nr in agent_name_lower
        for nr in _non_dev_roles
    )
    if enable_l1 and pattern_type in execution_patterns and is_dev_role:
        l1 = await check_l1(
            content, task, agent_role, agent_name, tool_calls, pattern_type
        )
        if not l1.passed:
            logger.info(f"GUARD L1 REJECT [{agent_name}]: {l1.summary}")
            # Merge L0 warnings with L1 issues
            l1.issues = l0.issues + l1.issues
            l1.score = max(l0.score, l1.score)
            return l1

    # ── L2: Visual screenshot eval for UI phases ──
    # WHY: Anthropic harness used Playwright MCP to screenshot and evaluate live
    # interfaces, creating a feedback loop driving 5-15 iterations per design.
    # "The evaluator used Playwright MCP to interact with live interfaces directly,
    # screenshotting and evaluating implementations before providing critique."
    # Ref: https://anthropic.com/engineering/harness-design-long-running-apps
    # If the phase involves UI work AND a project URL is available, take a screenshot
    # and evaluate visual quality via LLM. Non-blocking: failures log but don't reject.
    # Detect UI phases from task content or agent role
    _ui_phase_markers = {"ui", "frontend", "design", "ux", "ihm", "screen", "layout", "css", "html", "canvas"}
    _task_lower = (task or "").lower()
    _phase_is_ui = any(m in _task_lower for m in _ui_phase_markers)
    # Also check if agent just wrote HTML/CSS files
    _wrote_ui_files = any(
        tc_name.endswith((".html", ".css", ".htm", ".svg"))
        for tc_name in (tool_calls or [])
        if isinstance(tc_name, str)
    )
    # Check for HTML content in the output itself
    _has_html_output = "<!DOCTYPE" in content or "<html" in content or "<canvas" in content

    # Resolve screenshot URL: project URL env var OR workspace index.html
    _project_url = os.environ.get("PLATFORM_PROJECT_URL", "")
    if not _project_url:
        # Try to find index.html in the workspace via tool_calls context
        _ws_index = None
        for _tc in (tool_calls or []):
            if isinstance(_tc, str) and "index.html" in _tc:
                _ws_index = _tc
                break
        if not _ws_index:
            # Scan common workspace paths
            import glob as _glob
            _ws_candidates = _glob.glob("/app/data/workspaces/*/index.html")
            if _ws_candidates:
                _ws_index = sorted(_ws_candidates, key=os.path.getmtime)[-1]  # most recent
        if _ws_index:
            _project_url = f"file://{_ws_index}"

    if (_phase_is_ui or _wrote_ui_files or _has_html_output) and _project_url and enable_l1:
        try:
            from ..tools.test_tools import playwright_screenshot
            _screenshot_path = await playwright_screenshot(_project_url)
            if _screenshot_path:
                from ..llm.client import get_llm_client, LLMMessage
                _vis_client = get_llm_client()
                _vis_resp = await _vis_client.chat(
                    messages=[
                        LLMMessage(role="system", content=(
                            "You are a strict UI quality gate. Binary verdict only.\n\n"
                            "Look at this screenshot and answer these YES/NO questions:\n"
                            "1. Is there visible, rendered content? (not blank/white/error page)\n"
                            "2. Is the layout functional? (elements visible, not overlapping garbage)\n"
                            "3. Does it match the task description?\n\n"
                            "If ALL three are YES → output exactly: PASS\n"
                            "If ANY is NO → output exactly: VETO\n"
                            "Then one sentence explaining why.\n"
                            "No scores. No percentages. Binary: PASS or VETO."
                        )),
                        LLMMessage(role="user", content=f"Screenshot: {_screenshot_path}\nTask: {task[:500]}"),
                    ],
                    temperature=0,
                )
                if "VETO" in _vis_resp.content.upper():
                    # Binary VETO — force recode, no partial credit
                    l0.issues.append(f"L2-VISUAL VETO: {_vis_resp.content[:200]}")
                    l0.score += 10  # guaranteed rejection (threshold is 5)
                    l0.passed = False
                    logger.warning("GUARD L2-VISUAL VETO [%s]: %s", agent_name, _vis_resp.content[:100])
                else:
                    logger.info("GUARD L2-VISUAL PASS [%s]: %s", agent_name, _vis_resp.content[:100])
        except Exception as _vis_err:
            logger.debug("L2-VISUAL skip: %s", _vis_err)

    # Both passed
    return GuardResult(
        passed=True,
        score=l0.score,
        issues=l0.issues,  # L0 warnings (below threshold) still reported
        level="L0+L1+L2" if _phase_is_ui and _project_url else (
            "L0+L1" if enable_l1 and pattern_type in execution_patterns else "L0"
        ),
    )
