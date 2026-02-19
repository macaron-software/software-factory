"""
Adversarial Guard — Detect slop, hallucination, mock, and lies in agent output.
================================================================================

Two-layer Swiss Cheese model:
- L0: Deterministic fast checks (regex, heuristics) — 0ms
- L1: Semantic LLM check (different model than producer) — optional, ~5s

Runs INSIDE _execute_node() after agent produces output, BEFORE storing in memory.
Rejects output with a reason; the pattern engine can retry or flag.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class GuardResult:
    """Result of adversarial guard check."""
    passed: bool
    score: int = 0           # 0 = clean, higher = worse
    issues: list[str] = None # list of detected issues
    level: str = ""          # "L0" or "L1"

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
    (r'\blorem ipsum\b', "Lorem ipsum placeholder text"),
    (r'\bfoo\s*bar\s*baz\b', "Placeholder foo/bar/baz"),
    (r'(?:https?://)?example\.com', "example.com placeholder URL"),
    (r'\bplaceholder\b.*\btext\b', "Placeholder text"),
    (r'\bTBD\b', "TBD marker — incomplete work"),
    (r'\bXXX\b', "XXX marker — needs attention"),
]

# Mock/stub patterns — fake implementations
_MOCK_PATTERNS = [
    (r'#\s*TODO\s*:?\s*implement', "TODO implement marker"),
    (r'//\s*TODO\s*:?\s*implement', "TODO implement marker"),
    (r'raise\s+NotImplementedError\b(?!\s*#\s*pragma)', "NotImplementedError without pragma"),
    (r'pass\s*#\s*(?:todo|fixme|implement)', "pass with TODO comment"),
    (r'return\s+(?:None|null|undefined)\s*#\s*(?:todo|stub|mock)', "Stub return with TODO"),
    (r'(?:fake|mock|dummy|hardcoded)\s+(?:data|response|result|value)', "Fake/mock data"),
    (r'def\s+\w+\([^)]*\)\s*:\s*\n\s+pass\s*$', "Empty function body (pass)"),
    (r'console\.log\s*\(\s*["\']test', "console.log('test') — debug leftover"),
]

# Hallucination patterns — claiming actions without evidence
_HALLUCINATION_PATTERNS = [
    (r"j'ai\s+(?:deploye|déployé|lancé|exécuté|testé|vérifié|créé le fichier|commit)", "Claims action without tool evidence"),
    (r"i(?:'ve| have)\s+(?:deployed|tested|created|committed|executed|verified)", "Claims action without tool evidence"),
    (r"le\s+(?:build|test|deploy)\s+(?:a|est)\s+(?:réussi|passé|ok)", "Claims success without evidence"),
    (r"voici\s+(?:le|les)\s+résultat", "Claims to show results"),
]

# Lie patterns — inventing file paths, URLs, or data
_LIE_PATTERNS = [
    (r'(?:fichier|file)\s+(?:créé|created|saved)\s*:\s*\S+', "Claims file creation — verify with tool_calls"),
    (r'(?:http|https)://(?:staging|prod|api)\.\S+(?:\.local|\.internal)', "Invented internal URL"),
]

# Minimum content thresholds by context
_MIN_CONTENT_LENGTH = {
    "dev": 200,
    "qa": 150,
    "devops": 150,
    "architecture": 200,
    "default": 80,
}


def check_l0(content: str, agent_role: str = "", tool_calls: list = None) -> GuardResult:
    """L0: Fast deterministic checks. Returns immediately."""
    if not content or not content.strip():
        return GuardResult(passed=False, score=10, issues=["Empty output"], level="L0")

    issues = []
    score = 0
    content_lower = content.lower()
    tool_calls = tool_calls or []

    # Tool call names for evidence checking
    tool_names = {tc.get("name", "") for tc in tool_calls}
    has_write_tool = bool(tool_names & {"code_write", "code_edit", "git_commit", "deploy_azure", "docker_build"})
    has_test_tool = bool(tool_names & {"test", "build", "playwright_test"})

    # Check slop
    for pattern, desc in _SLOP_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            issues.append(f"SLOP: {desc}")
            score += 3

    # Check mock/stub
    for pattern, desc in _MOCK_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
            issues.append(f"MOCK: {desc}")
            score += 4

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
    if not has_write_tool and not any(marker in content_lower for marker in ("[approve]", "[veto]", "go/nogo")):
        if len(content.strip()) < min_len:
            issues.append(f"TOO_SHORT: {len(content.strip())} chars (min {min_len} for {role_key})")
            score += 2

    # Check for copy-paste of task (agent echoing the prompt)
    # Heuristic: if >70% of content is a quote block, it's probably echo
    quote_lines = sum(1 for l in content.split('\n') if l.strip().startswith('>'))
    total_lines = max(len(content.split('\n')), 1)
    if quote_lines / total_lines > 0.7 and total_lines > 5:
        issues.append("ECHO: Agent mostly quoted the task back")
        score += 4

    # Check for suspicious repeated blocks (copy-paste slop)
    lines = [l.strip() for l in content.split('\n') if len(l.strip()) > 20]
    if len(lines) > 5:
        seen = {}
        for l in lines:
            seen[l] = seen.get(l, 0) + 1
        repeated = sum(1 for c in seen.values() if c > 2)
        if repeated > 3:
            issues.append(f"REPETITION: {repeated} lines repeated >2 times")
            score += 3

    threshold = 5  # reject if score >= threshold
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
) -> GuardResult:
    """L1: Semantic LLM check using a DIFFERENT model than the producer.

    Asks a reviewer LLM to evaluate the output for:
    - Completeness vs the task
    - Factual accuracy (no hallucination)
    - Genuine work (no slop/mock/stub)
    - Honesty (claims match tool evidence)
    """
    try:
        from ..llm.client import get_llm_client, LLMMessage

        # Build evidence summary from tool calls
        evidence = "No tools used."
        if tool_calls:
            evidence_lines = []
            for tc in tool_calls[:10]:
                name = tc.get("name", "?")
                result_preview = str(tc.get("result", ""))[:200]
                evidence_lines.append(f"- {name}: {result_preview}")
            evidence = "\n".join(evidence_lines)

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

Check for:
1. SLOP: Generic filler, placeholder text, no real substance
2. HALLUCINATION: Claims actions not supported by tool evidence
3. MOCK: Fake implementations (TODO, pass, NotImplementedError, dummy data)
4. LIES: Invented file paths, URLs, results not in tool output
5. ECHO: Just rephrasing the task without doing real work
6. COMPLETENESS: Did the agent actually address the task? (via tools OR text)

Respond ONLY with JSON:
{{"score": <0-10>, "issues": ["issue1", "issue2"], "verdict": "APPROVE" or "REJECT"}}"""

        client = get_llm_client()
        resp = await client.chat(
            messages=[LLMMessage(role="user", content=prompt)],
            system_prompt="You are an adversarial code reviewer. Be strict. Reject slop and hallucination. Real work only.",
            temperature=0.1,
            max_tokens=300,
        )

        import json
        raw = resp.content.strip()
        if "```json" in raw:
            raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in raw:
            raw = raw.split("```", 1)[1].split("```", 1)[0].strip()

        data = json.loads(raw)
        l1_score = int(data.get("score", 0))
        l1_issues = data.get("issues", [])
        verdict = data.get("verdict", "APPROVE")

        return GuardResult(
            passed=verdict == "APPROVE" and l1_score < 6,
            score=l1_score,
            issues=[f"L1: {i}" for i in l1_issues],
            level="L1",
        )

    except Exception as e:
        logger.warning(f"L1 adversarial check failed: {e}")
        # On failure, don't block — L0 is the safety net
        return GuardResult(passed=True, score=0, issues=[], level="L1-skipped")


async def run_guard(
    content: str,
    task: str = "",
    agent_role: str = "",
    agent_name: str = "",
    tool_calls: list = None,
    pattern_type: str = "",
    enable_l1: bool = True,
) -> GuardResult:
    """Run the full adversarial guard pipeline: L0 then L1.

    L0 always runs (deterministic, 0ms).
    L1 runs only for execution patterns (not discussions) and if L0 passes.
    """
    # L0: Fast deterministic
    l0 = check_l0(content, agent_role, tool_calls)

    if not l0.passed:
        logger.info(f"GUARD L0 REJECT [{agent_name}]: {l0.summary}")
        return l0

    # L1: Semantic LLM check — only for execution patterns
    # Discussion patterns (network, human-in-the-loop) are debating, not producing code
    execution_patterns = {"sequential", "hierarchical", "parallel", "loop", "aggregator"}
    if enable_l1 and pattern_type in execution_patterns:
        l1 = await check_l1(content, task, agent_role, agent_name, tool_calls)
        if not l1.passed:
            logger.info(f"GUARD L1 REJECT [{agent_name}]: {l1.summary}")
            # Merge L0 warnings with L1 issues
            l1.issues = l0.issues + l1.issues
            l1.score = max(l0.score, l1.score)
            return l1

    # Both passed
    return GuardResult(
        passed=True,
        score=l0.score,
        issues=l0.issues,  # L0 warnings (below threshold) still reported
        level="L0+L1" if enable_l1 and pattern_type in execution_patterns else "L0",
    )
