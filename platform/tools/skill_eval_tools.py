"""Skill Eval Tools — deterministic + LLM-as-judge evaluation harness for SF skills.

SOURCE: philschmid.de/testing-skills (public article, free content)
  https://www.philschmid.de/testing-skills

WHY WE BUILT THIS:
  SF has 60+ skills shipped without systematic evals — exactly the "vibe-checked
  with a handful of manual runs, then shipped" anti-pattern the article describes.
  SkillsBench (arxiv 2602.12670) found 47k+ skills across GitHub with almost no
  eval coverage. We adopt the article's harness approach:
    1. Deterministic checks  — regex/keyword, fast, zero LLM cost
    2. LLM-as-judge          — structured output for qualitative dimensions
    3. Multi-trial           — 3 trials per case, report distribution (not single pass/fail)
    4. 3 evaluation dims     — outcome (works?), style (conventions?), efficiency (tokens)
    5. Negative tests        — should_trigger:false cases catch over-broad skill descriptions
    6. Retirement detection  — if skill passes without being loaded, retire it

  The same principles power the existing skill-eval workflow (skill-eval.yaml),
  but this module adds an *automated* runner so metrics appear in /art without
  human intervention per run.

Eval case format (YAML frontmatter in skills/*.md):
  eval_cases:
    - id: basic-auth-jwt
      prompt: "Generate JWT auth middleware for FastAPI"
      should_trigger: true          # false = negative test (skill should NOT be used)
      checks:                       # deterministic checks (fast, no LLM cost)
        - "regex:import jwt"
        - "not_regex:TODO|FIXME"
        - "length_min:200"
        - "has_keyword:Bearer"
      expectations:                 # qualitative expectations for LLM judge
        - "generates complete working code, not a stub"
        - "includes error handling for invalid tokens"
      tags: [basic, python]

  Checks syntax:
    regex:PATTERN      — output matches regex (re.IGNORECASE)
    not_regex:PATTERN  — output does NOT match regex
    length_min:N       — output length >= N chars
    has_keyword:WORD   — case-insensitive substring present
    has_section:TITLE  — markdown heading present
    no_placeholder     — no TODO/FIXME/placeholder/... patterns
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..config import LEGACY_SKILLS_DIR, DATA_DIR

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────────────────

EVAL_RESULTS_DIR = DATA_DIR / "skill_evals"
EVAL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_TRIALS = 3          # trials per case (article: 3-5)
PASS_RATE_GREEN = 0.80      # ≥80% → green / ready
PASS_RATE_YELLOW = 0.60     # ≥60% → yellow / needs work

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# Placeholder patterns that indicate superficial compliance (from skill-grader)
_PLACEHOLDER_RE = re.compile(
    r"\bTODO\b|\bFIXME\b|\bplaceholder\b|\.{3}\s*#.*|pass\s*#\s*(TODO|implement)",
    re.IGNORECASE,
)

# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    """Result of a single deterministic check."""
    check_id: str
    check_spec: str
    passed: bool
    notes: str = ""


@dataclass
class CaseResult:
    """Result of one eval_case across N trials."""
    case_id: str
    prompt: str
    should_trigger: bool
    trials: int
    checks_pass_rate: float     # fraction of deterministic checks passing (avg over trials)
    llm_judge_score: float      # 0.0–1.0 from LLM-as-judge (avg over trials), -1 if no expectations
    overall_pass_rate: float    # combined (checks * weight + judge * weight)
    dimension_outcome: float    # did it produce a working artifact?
    dimension_style: float      # does it follow skill conventions?
    dimension_efficiency: float # avg tokens used (normalised)
    check_details: list[CheckResult] = field(default_factory=list)
    judge_notes: str = ""
    avg_tokens: int = 0
    avg_latency_ms: float = 0.0
    tags: list[str] = field(default_factory=list)


@dataclass
class SkillEvalResult:
    """Full eval result for one skill."""
    skill_name: str
    skill_version: str
    eval_cases_total: int
    pass_rate: float            # 0.0–1.0 — key metric (article: aim for ≥0.80)
    case_results: list[CaseResult] = field(default_factory=list)
    coverage_gap: list[str] = field(default_factory=list)   # missing test types
    retirement_signal: bool = False  # True if skill passes WITHOUT being loaded
    ran_at: str = ""
    duration_s: float = 0.0
    status: str = "ok"          # ok | error | no_cases
    error: str = ""


# ── Frontmatter loader ───────────────────────────────────────────────────────

def _load_skill_frontmatter(skill_name: str) -> tuple[dict, str]:
    """Load a skill's YAML frontmatter and full body.
    Returns (frontmatter_dict, body_markdown).
    """
    path = LEGACY_SKILLS_DIR / f"{skill_name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Skill not found: {skill_name} ({path})")
    text = path.read_text(encoding="utf-8")
    m = _FM_RE.match(text)
    fm: dict = {}
    if m:
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except Exception:
            pass
    return fm, text


def list_skills_with_evals() -> list[dict]:
    """Return all skills, annotated with eval_cases count and last result."""
    skills = []
    for path in sorted(LEGACY_SKILLS_DIR.glob("*.md")):
        name = path.stem
        try:
            fm, _ = _load_skill_frontmatter(name)
        except Exception:
            continue
        cases = fm.get("eval_cases", [])
        last_result = _load_last_result(name)
        skills.append({
            "name": name,
            "description": fm.get("description", "")[:120],
            "category": fm.get("metadata", {}).get("category", ""),
            "eval_cases": len(cases),
            "has_evals": len(cases) > 0,
            "pass_rate": last_result.get("pass_rate") if last_result else None,
            "ran_at": last_result.get("ran_at") if last_result else None,
            "status": last_result.get("status", "never_run") if last_result else "never_run",
        })
    return skills


def coverage_summary() -> dict:
    """Skills eval coverage summary for /art dashboard."""
    skills = list_skills_with_evals()
    total = len(skills)
    with_evals = sum(1 for s in skills if s["has_evals"])
    run = sum(1 for s in skills if s["pass_rate"] is not None)
    passing = sum(1 for s in skills if (s["pass_rate"] or 0) >= PASS_RATE_GREEN)
    return {
        "total": total,
        "with_evals": with_evals,
        "coverage_pct": round(100 * with_evals / total) if total else 0,
        "run": run,
        "passing": passing,
        "needing_work": [s for s in skills if s["has_evals"] and (s["pass_rate"] or 0) < PASS_RATE_GREEN],
        "without_evals": [s["name"] for s in skills if not s["has_evals"]],
    }


# ── Deterministic checks ─────────────────────────────────────────────────────

def _run_check(spec: str, output: str) -> CheckResult:
    """Run a single deterministic check against an output string.

    Spec syntax — see module docstring.
    """
    if ":" not in spec:
        # No-arg checks (no colon required)
        kind_solo = spec.strip().lower()
        if kind_solo == "no_placeholder":
            match = bool(_PLACEHOLDER_RE.search(output))
            notes = "Placeholder/TODO detected (FAIL)" if match else "No placeholder"
            return CheckResult(spec, spec, not match, notes)
        return CheckResult(spec, spec, False, "invalid check spec — missing ':'")

    kind, _, arg = spec.partition(":")
    kind = kind.strip().lower()

    try:
        if kind == "regex":
            match = bool(re.search(arg, output, re.IGNORECASE))
            notes = f"Pattern '{arg}' {'found' if match else 'NOT found'}"
            return CheckResult(spec, spec, match, notes)

        if kind == "not_regex":
            match = bool(re.search(arg, output, re.IGNORECASE))
            notes = f"Pattern '{arg}' {'found (FAIL)' if match else 'absent (OK)'}"
            return CheckResult(spec, spec, not match, notes)

        if kind == "length_min":
            n = int(arg.strip())
            ok = len(output) >= n
            notes = f"Output length {len(output)} {'≥' if ok else '<'} {n}"
            return CheckResult(spec, spec, ok, notes)

        if kind == "has_keyword":
            ok = arg.lower() in output.lower()
            notes = f"Keyword '{arg}' {'found' if ok else 'NOT found'}"
            return CheckResult(spec, spec, ok, notes)

        if kind == "has_section":
            ok = bool(re.search(rf"^#+\s+{re.escape(arg)}", output, re.MULTILINE | re.IGNORECASE))
            notes = f"Section '{arg}' {'found' if ok else 'NOT found'}"
            return CheckResult(spec, spec, ok, notes)

        if kind == "no_placeholder":
            match = bool(_PLACEHOLDER_RE.search(output))
            notes = "Placeholder/TODO detected (FAIL)" if match else "No placeholder"
            return CheckResult(spec, spec, not match, notes)

    except Exception as exc:
        return CheckResult(spec, spec, False, f"check error: {exc}")

    return CheckResult(spec, spec, False, f"unknown check kind: {kind}")


# ── LLM-as-judge ─────────────────────────────────────────────────────────────

async def _llm_judge(
    skill_content: str,
    prompt: str,
    output: str,
    expectations: list[str],
) -> tuple[float, str]:
    """Use LLM-as-judge with structured output to evaluate qualitative expectations.

    Returns (score 0.0–1.0, notes string).

    Design from article:
      "Use structured output to constrain the LLM's response to a typed schema
       so that results become parseable and trackable."
    Each expectation is graded independently → overall = fraction passing.
    """
    if not expectations:
        return -1.0, "no expectations"

    from ..llm.client import LLMClient, LLMMessage

    # Build grading prompt — structured output via JSON schema
    exp_list = "\n".join(f"{i+1}. {e}" for i, e in enumerate(expectations))
    judge_prompt = f"""You are an evaluator grading an AI agent's output against a skill's expectations.

SKILL (excerpt, first 600 chars):
{skill_content[:600]}

USER PROMPT:
{prompt}

AGENT OUTPUT:
{output[:3000]}

EXPECTATIONS TO EVALUATE:
{exp_list}

For each expectation, reply with a JSON object:
{{
  "grades": [
    {{"id": 1, "expectation": "...", "passed": true/false, "evidence": "quoted text or explanation"}},
    ...
  ],
  "overall_notes": "brief summary of quality assessment"
}}

Rules:
- passed=true only if the output ACTUALLY satisfies the expectation (not just promises to)
- Superficial compliance (promise without delivery, stub, placeholder) = FAIL
- Grade outcomes, not paths (creative correct solutions = PASS)
"""

    try:
        client = LLMClient()
        resp = await client.chat(
            messages=[LLMMessage(role="user", content=judge_prompt)],
            temperature=0.1,
            max_tokens=1024,
        )
        raw = resp.content.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
        data = json.loads(raw)
        grades = data.get("grades", [])
        if not grades:
            return 0.5, "could not parse grades"
        passed = sum(1 for g in grades if g.get("passed", False))
        score = passed / len(grades)
        notes = data.get("overall_notes", "")
        # Add evidence summary
        failed = [g for g in grades if not g.get("passed", False)]
        if failed:
            notes += " | FAILED: " + "; ".join(g.get("evidence", "?") for g in failed[:2])
        return score, notes
    except Exception as exc:
        logger.warning("LLM judge failed: %s", exc)
        return 0.5, f"judge error: {exc}"


# ── Eval runner ───────────────────────────────────────────────────────────────

async def run_skill_eval(
    skill_name: str,
    trials: int = DEFAULT_TRIALS,
    check_retirement: bool = False,
) -> SkillEvalResult:
    """Run full eval for a skill.

    Implementation follows article's eval harness:
      1. Load skill frontmatter (eval_cases, version)
      2. For each case, run N trials (article: 3-5)
      3. Deterministic checks first (fast, no LLM cost)
      4. LLM-as-judge for qualitative expectations
      5. Aggregate: pass_rate = fraction of cases passing threshold
      6. Optionally check retirement (does skill pass WITHOUT being loaded?)

    Reference: https://www.philschmid.de/testing-skills
    """
    t0 = time.time()
    result = SkillEvalResult(
        skill_name=skill_name,
        skill_version="",
        eval_cases_total=0,
        pass_rate=0.0,
        ran_at=_now_iso(),
    )

    try:
        fm, skill_body = _load_skill_frontmatter(skill_name)
    except FileNotFoundError as exc:
        result.status = "error"
        result.error = str(exc)
        return result

    result.skill_version = str(fm.get("version", fm.get("name", "?")))
    eval_cases = fm.get("eval_cases", [])

    if not eval_cases:
        result.status = "no_cases"
        result.error = "No eval_cases in skill frontmatter"
        return result

    result.eval_cases_total = len(eval_cases)
    case_results: list[CaseResult] = []

    from ..llm.client import LLMClient, LLMMessage

    for case in eval_cases:
        case_id = str(case.get("id") or case.get("prompt", "")[:30] or f"case-{len(case_results)}")
        prompt = str(case.get("prompt") or case.get("input", ""))
        should_trigger = bool(case.get("should_trigger", True))
        checks_spec: list[str] = case.get("checks", [])
        expectations: list[str] = case.get("expectations") or case.get("expect") or []
        tags: list[str] = case.get("tags", [])

        trial_check_rates: list[float] = []
        trial_judge_scores: list[float] = []
        trial_tokens: list[int] = []
        trial_latency: list[float] = []
        last_output = ""
        last_check_details: list[CheckResult] = []
        last_judge_notes = ""

        for _ in range(trials):
            # Build system prompt: inject skill content
            system = (
                f"You are an AI assistant. The following skill is active and you must follow it:\n\n"
                f"{skill_body}\n\n"
                f"Apply this skill to the user's request."
            )
            try:
                t_start = time.time()
                client = LLMClient()
                resp = await client.chat(
                    messages=[LLMMessage(role="user", content=prompt)],
                    system_prompt=system,
                    temperature=0.3,
                    max_tokens=2048,
                )
                latency_ms = (time.time() - t_start) * 1000
                output = resp.content
                tokens = (resp.tokens_in or 0) + (resp.tokens_out or 0)
            except Exception as exc:
                logger.warning("Skill eval run failed for %s/%s: %s", skill_name, case_id, exc)
                output = ""
                latency_ms = 0.0
                tokens = 0

            last_output = output

            # Deterministic checks
            check_details = [_run_check(spec, output) for spec in checks_spec]
            # If should_trigger=False (negative test), we expect a short "not applicable" response
            if not should_trigger:
                # Skill should NOT have been applied → output should be generic, not skill-specific
                # We check that NO skill-specific markers appear
                triggered_markers = _detect_skill_trigger(skill_body, output)
                check_details.append(CheckResult(
                    "trigger-check", "skill should NOT trigger",
                    not triggered_markers,
                    "Skill markers absent" if not triggered_markers else f"Skill triggered unexpectedly: {triggered_markers[:80]}",
                ))

            check_pass_rate = (
                sum(1 for c in check_details if c.passed) / len(check_details)
                if check_details else 1.0
            )
            last_check_details = check_details
            trial_check_rates.append(check_pass_rate)
            trial_tokens.append(tokens)
            trial_latency.append(latency_ms)

        # LLM judge (once on last output — article: LLM judge selectively, it adds cost)
        if expectations and last_output:
            judge_score, judge_notes = await _llm_judge(
                skill_body, prompt, last_output, expectations
            )
            last_judge_notes = judge_notes
            # Use same judge score across trials (deterministic checks vary, judge less so)
            trial_judge_scores = [judge_score] * trials
        else:
            trial_judge_scores = [-1.0] * trials
            last_judge_notes = "no expectations defined"

        avg_checks = sum(trial_check_rates) / len(trial_check_rates) if trial_check_rates else 0.0
        valid_judge = [s for s in trial_judge_scores if s >= 0]
        avg_judge = sum(valid_judge) / len(valid_judge) if valid_judge else -1.0

        # Overall = checks (60%) + judge (40%) when both available; else checks alone
        if avg_judge >= 0:
            overall = avg_checks * 0.60 + avg_judge * 0.40
        else:
            overall = avg_checks

        # 3 dimensions
        dim_outcome = avg_checks  # deterministic checks = outcome dimension
        dim_style = avg_judge if avg_judge >= 0 else avg_checks  # style = LLM judge
        max_tokens_expected = 1000
        avg_tok = sum(trial_tokens) / len(trial_tokens) if trial_tokens else 0
        dim_efficiency = max(0.0, 1.0 - (avg_tok / max_tokens_expected)) if avg_tok else 1.0

        case_results.append(CaseResult(
            case_id=case_id,
            prompt=prompt,
            should_trigger=should_trigger,
            trials=trials,
            checks_pass_rate=round(avg_checks, 3),
            llm_judge_score=round(avg_judge, 3),
            overall_pass_rate=round(overall, 3),
            dimension_outcome=round(dim_outcome, 3),
            dimension_style=round(dim_style, 3),
            dimension_efficiency=round(dim_efficiency, 3),
            check_details=last_check_details,
            judge_notes=last_judge_notes,
            avg_tokens=int(avg_tok),
            avg_latency_ms=round(sum(trial_latency) / len(trial_latency), 1) if trial_latency else 0.0,
            tags=tags,
        ))

    # Aggregate: pass_rate = fraction of cases with overall_pass_rate >= 0.8
    # Article: "pass_rate >= 0.8 — skill is ready to ship"
    passing_cases = sum(1 for c in case_results if c.overall_pass_rate >= PASS_RATE_GREEN)
    result.pass_rate = round(passing_cases / len(case_results), 3) if case_results else 0.0
    result.case_results = case_results
    result.duration_s = round(time.time() - t0, 2)

    # Coverage gap detection
    has_negative = any(not c.should_trigger for c in case_results)
    has_edge = any("edge" in c.tags for c in case_results)
    if not has_negative:
        result.coverage_gap.append("no negative tests (should_trigger:false cases)")
    if not has_edge:
        result.coverage_gap.append("no edge-case tests")
    if len(case_results) < 5:
        result.coverage_gap.append(f"only {len(case_results)} cases — aim for 10+")

    # Save result
    _save_result(skill_name, result)
    return result


def _detect_skill_trigger(skill_body: str, output: str) -> str:
    """Detect if skill-specific keywords appear in output (for negative test detection).
    Returns the matched marker or empty string."""
    # Extract key technical terms from skill body (code patterns, tool names)
    markers = re.findall(r"`([^`]{4,30})`", skill_body)[:5]
    for m in markers:
        if m.lower() in output.lower():
            return m
    return ""


# ── Persistence ──────────────────────────────────────────────────────────────

def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _result_path(skill_name: str) -> Path:
    return EVAL_RESULTS_DIR / f"{skill_name}.json"


def _save_result(skill_name: str, result: SkillEvalResult) -> None:
    """Persist eval result as JSON."""
    try:
        data: dict[str, Any] = {
            "skill_name": result.skill_name,
            "skill_version": result.skill_version,
            "eval_cases_total": result.eval_cases_total,
            "pass_rate": result.pass_rate,
            "ran_at": result.ran_at,
            "duration_s": result.duration_s,
            "status": result.status,
            "error": result.error,
            "retirement_signal": result.retirement_signal,
            "coverage_gap": result.coverage_gap,
            "case_results": [
                {
                    "case_id": c.case_id,
                    "prompt": c.prompt[:200],
                    "should_trigger": c.should_trigger,
                    "trials": c.trials,
                    "checks_pass_rate": c.checks_pass_rate,
                    "llm_judge_score": c.llm_judge_score,
                    "overall_pass_rate": c.overall_pass_rate,
                    "dimension_outcome": c.dimension_outcome,
                    "dimension_style": c.dimension_style,
                    "dimension_efficiency": c.dimension_efficiency,
                    "check_details": [
                        {"spec": cd.check_spec, "passed": cd.passed, "notes": cd.notes}
                        for cd in c.check_details
                    ],
                    "judge_notes": c.judge_notes,
                    "avg_tokens": c.avg_tokens,
                    "avg_latency_ms": c.avg_latency_ms,
                    "tags": c.tags,
                }
                for c in result.case_results
            ],
        }
        _result_path(skill_name).write_text(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception as exc:
        logger.warning("Could not save eval result for %s: %s", skill_name, exc)


def _load_last_result(skill_name: str) -> dict | None:
    """Load last eval result for a skill (lightweight summary)."""
    path = _result_path(skill_name)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def load_eval_result(skill_name: str) -> dict | None:
    """Load full eval result for a skill."""
    return _load_last_result(skill_name)
