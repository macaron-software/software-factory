"""PM Checkpoint — Evidence-based phase gate with build validation and judge LLM.

After each phase, the PM checkpoint:
1. Runs deterministic build validation (build gate)
2. Calls a judge LLM with all evidence (build result, deliverables, adversarial scores)
3. Returns a decision: next / retry / done

This replaces blind phase transitions with evidence-driven decisions.
"""
# Ref: feat-mission-control

from __future__ import annotations

import asyncio
import logging
import os
import re
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class BuildResult:
    success: bool
    command: str
    error_output: str = ""
    error_count: int = 0
    first_errors: list[str] | None = None


@dataclass
class TestResult:
    """Test runner output parsed into pass/fail counts."""
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    command: str = ""


@dataclass
class ANCScore:
    """Average Normalized Change — SWE-CI inspired maintainability metric.

    Tracks test pass count evolution across sprint iterations.
    NC = (p_i - p_0) / (p_* - p_0) for improvements (p_i >= p_0)
    NC = (p_i - p_0) / p_0           for regressions (p_i < p_0)
    ANC = mean(NC) across iterations.
    Positive = improving, negative = regressing, 1.0 = target reached.
    """
    baseline_passed: int = 0       # p_0 — tests passing at sprint start
    current_passed: int = 0        # p_i — tests passing now
    target_passed: int = 0         # p_* — tests passing in reference (all tests)
    nc: float = 0.0                # Normalized Change this iteration
    history: list[float] | None = None  # NC values per iteration
    anc: float = 0.0               # Average NC across all iterations

    def compute_nc(self) -> float:
        """Compute NC for current iteration."""
        if self.current_passed >= self.baseline_passed:
            denom = self.target_passed - self.baseline_passed
            if denom <= 0:
                return 1.0 if self.current_passed >= self.target_passed else 0.0
            return (self.current_passed - self.baseline_passed) / denom
        else:
            if self.baseline_passed <= 0:
                return -1.0
            return (self.current_passed - self.baseline_passed) / self.baseline_passed

    def compute_anc(self) -> float:
        """Compute ANC from history."""
        if not self.history:
            return self.nc
        return sum(self.history) / len(self.history)


@dataclass
class PMDecision:
    action: str  # "next" | "retry" | "done" | "abort"
    reason: str
    build_result: BuildResult | None = None
    quality_score: float = 0.0
    evidence_summary: str = ""
    test_result: TestResult | None = None
    anc_score: ANCScore | None = None


def _evaluate_ko_drift(project_id: str, evidence_text: str) -> tuple[bool, list[str]]:
    """Check if mandatory Knowledge Objects are still represented in phase evidence."""
    if not project_id:
        return False, []
    try:
        from ..memory.manager import get_memory_manager

        mandatory = get_memory_manager().ko_list_mandatory(project_id, limit=100)
        if not mandatory:
            return False, []
        haystack = (evidence_text or "").lower()
        missing: list[str] = []
        for ko in mandatory:
            key = str(ko.get("key", "") or "").strip()
            value = str(ko.get("value", "") or "").strip()
            if not key:
                continue
            key_hit = key.lower() in haystack
            value_hit = False
            if value:
                pivot = value[:80].lower()
                value_hit = pivot in haystack if len(pivot) >= 8 else False
            if not key_hit and not value_hit:
                missing.append(key)
        return len(missing) > 0, missing
    except Exception as e:
        logger.debug("KO drift evaluation skipped: %s", e)
        return False, []


# ── Build Gate ─────────────────────────────────────────────────


def _detect_build_cmd(workspace: str) -> list[str]:
    """Detect build command from workspace files. Mirrors workflows/store.py."""
    if os.path.isfile(os.path.join(workspace, "Package.swift")):
        return ["/usr/bin/swift", "build"]
    if os.path.isfile(os.path.join(workspace, "package.json")):
        if os.path.isdir(os.path.join(workspace, "node_modules")):
            return ["npm", "run", "build", "--if-present"]
        return ["npm", "install", "--ignore-scripts"]
    if os.path.isfile(os.path.join(workspace, "Cargo.toml")):
        return ["cargo", "check"]
    if os.path.isfile(os.path.join(workspace, "requirements.txt")):
        for f in ("main.py", "app.py", "server.py"):
            if os.path.isfile(os.path.join(workspace, f)):
                return ["python3", "-m", "py_compile", os.path.join(workspace, f)]
    if os.path.isfile(os.path.join(workspace, "go.mod")):
        return ["go", "build", "./..."]
    if os.path.isfile(os.path.join(workspace, "pom.xml")):
        return ["mvn", "-q", "compile", "-DskipTests"]
    return []


async def run_build_gate(workspace: str, timeout: int = 300) -> BuildResult:
    """Run build command and return structured result with first unique errors."""
    build_cmd = _detect_build_cmd(workspace)
    if not build_cmd:
        return BuildResult(success=True, command="(no build system detected)")

    cmd_str = " ".join(build_cmd)
    try:
        proc = await asyncio.create_subprocess_exec(
            *build_cmd,
            cwd=workspace,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return BuildResult(
            success=False,
            command=cmd_str,
            error_output=f"Build timed out after {timeout}s",
            error_count=1,
        )
    except Exception as e:
        return BuildResult(
            success=False,
            command=cmd_str,
            error_output=str(e),
            error_count=1,
        )

    if proc.returncode == 0:
        return BuildResult(success=True, command=cmd_str)

    # Combine stdout + stderr — some compilers (Swift) output errors to stdout
    raw = ((stderr or b"") + b"\n" + (stdout or b"")).decode("utf-8", errors="replace")
    # Extract unique errors (dedup by message content)
    # Patterns: "error:" (gcc/clang/python) · "error[" (rust) · "error TS" (typescript)
    # · ": error " (go) · "ERROR:" (maven/gradle) · "Error:" (dotnet/swift)
    error_lines = [
        ln.strip()
        for ln in raw.splitlines()
        if re.search(r"error[:\[\s]|:\s*error\b|^ERROR:", ln, re.IGNORECASE)
    ]
    seen_msgs = set()
    unique_errors = []
    for ln in error_lines:
        # Extract just the error message part (after error marker)
        match = re.search(r"error[:\[\s](.+)", ln, re.IGNORECASE)
        msg = match.group(1).strip() if match else ln
        if msg not in seen_msgs:
            seen_msgs.add(msg)
            unique_errors.append(ln)

    return BuildResult(
        success=False,
        command=cmd_str,
        error_output=raw[-2000:],
        error_count=len(error_lines),
        first_errors=unique_errors[:15],
    )


# ── Test Runner & ANC Tracking ─────────────────────────────────
# Ref: feat-anc-metric (SWE-CI inspired)


def _detect_test_cmd(workspace: str) -> list[str]:
    """Detect test command from workspace files."""
    if os.path.isfile(os.path.join(workspace, "Cargo.toml")):
        return ["cargo", "test", "--no-fail-fast", "--", "-q"]
    if os.path.isfile(os.path.join(workspace, "package.json")):
        return ["npm", "test", "--", "--passWithNoTests"]
    if os.path.isfile(os.path.join(workspace, "pyproject.toml")):
        return ["python3", "-m", "pytest", "-q", "--tb=no"]
    if os.path.isfile(os.path.join(workspace, "requirements.txt")):
        return ["python3", "-m", "pytest", "-q", "--tb=no"]
    if os.path.isfile(os.path.join(workspace, "go.mod")):
        return ["go", "test", "-count=1", "./..."]
    if os.path.isfile(os.path.join(workspace, "Package.swift")):
        return ["swift", "test", "--skip-build"]
    return []


# Regex patterns to extract test pass/fail counts from runner output
_TEST_RESULT_PATTERNS = [
    # pytest: "5 passed, 2 failed, 1 skipped"
    re.compile(r"(\d+)\s+passed"),
    re.compile(r"(\d+)\s+failed"),
    re.compile(r"(\d+)\s+skipped"),
    # Jest/Vitest: "Tests: 2 failed, 5 passed, 7 total"
    re.compile(r"Tests:\s*(?:(\d+)\s+failed,\s*)?(\d+)\s+passed,\s*(\d+)\s+total"),
    # cargo test: "test result: ok. 5 passed; 0 failed; 0 ignored"
    re.compile(r"(\d+)\s+passed;\s*(\d+)\s+failed;\s*(\d+)\s+ignored"),
    # Go: "ok  ... (pass implicit)" / "FAIL ... "
    re.compile(r"^ok\s+", re.MULTILINE),
    re.compile(r"^FAIL\s+", re.MULTILINE),
]


def _parse_test_output(raw: str) -> TestResult:
    """Parse test runner output into pass/fail/skip counts."""
    passed = failed = skipped = 0

    # pytest format
    m = re.search(r"(\d+)\s+passed", raw)
    if m:
        passed = int(m.group(1))
    m = re.search(r"(\d+)\s+failed", raw)
    if m:
        failed = int(m.group(1))
    m = re.search(r"(\d+)\s+(?:skipped|deselected)", raw)
    if m:
        skipped = int(m.group(1))

    # Jest/Vitest format
    m = re.search(r"Tests:\s*(?:(\d+)\s+failed,\s*)?(\d+)\s+passed,\s*(\d+)\s+total", raw)
    if m:
        failed = int(m.group(1) or 0)
        passed = int(m.group(2))
        total = int(m.group(3))
        skipped = total - passed - failed

    # cargo test format
    m = re.search(r"(\d+)\s+passed;\s*(\d+)\s+failed;\s*(\d+)\s+ignored", raw)
    if m:
        passed = int(m.group(1))
        failed = int(m.group(2))
        skipped = int(m.group(3))

    # Go format — count ok/FAIL lines
    if not passed and not failed:
        passed = len(re.findall(r"^ok\s+\S+", raw, re.MULTILINE))
        failed = len(re.findall(r"^FAIL\s+\S+", raw, re.MULTILINE))

    return TestResult(
        total=passed + failed + skipped,
        passed=passed,
        failed=failed,
        skipped=skipped,
    )


async def run_test_gate(workspace: str, timeout: int = 300) -> TestResult:
    """Run test suite and return structured pass/fail counts."""
    test_cmd = _detect_test_cmd(workspace)
    if not test_cmd:
        return TestResult(command="(no test runner detected)")

    cmd_str = " ".join(test_cmd)
    try:
        proc = await asyncio.create_subprocess_exec(
            *test_cmd,
            cwd=workspace,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return TestResult(command=cmd_str)
    except Exception:
        return TestResult(command=cmd_str)

    raw = ((stdout or b"") + b"\n" + (stderr or b"")).decode("utf-8", errors="replace")
    result = _parse_test_output(raw)
    result.command = cmd_str
    return result


def compute_anc(
    baseline_passed: int,
    current_passed: int,
    target_passed: int,
    prior_ncs: list[float] | None = None,
) -> ANCScore:
    """Compute ANC score for current sprint iteration.

    SWE-CI metric: tracks test improvement trajectory over sprints.
    Positive NC = tests improving. Negative = regression. 1.0 = target reached.
    """
    anc = ANCScore(
        baseline_passed=baseline_passed,
        current_passed=current_passed,
        target_passed=target_passed,
        history=list(prior_ncs) if prior_ncs else [],
    )
    anc.nc = anc.compute_nc()
    anc.history.append(anc.nc)
    anc.anc = anc.compute_anc()
    return anc


# ── Judge LLM ──────────────────────────────────────────────────


def _load_specs(workspace: str) -> str:
    """Load project SPECS.md or acceptance criteria for judge context."""
    for name in ("SPECS.md", "specs.md", "REQUIREMENTS.md", "README.md"):
        path = os.path.join(workspace, name)
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read(2000)
                return f"(from {name})\n{content}"
            except Exception:
                pass
    return "(no specs found)"


async def judge_phase_quality(
    phase_name: str,
    phase_output: str,
    build_result: BuildResult,
    workspace: str,
    adversarial_rejections: int = 0,
    sprint_num: int = 1,
    max_sprints: int = 1,
    prior_feedback: str = "",
) -> tuple[float, str]:
    """Call judge LLM to evaluate phase deliverables quality.

    Returns (score 0.0-1.0, verdict_text).
    Uses different temperature than producer for independence.
    """
    from ..llm.client import LLMMessage, get_llm_client

    # Collect workspace evidence
    files_evidence = _list_deliverables(workspace)
    specs_evidence = _load_specs(workspace)

    build_evidence = "BUILD: SUCCESS" if build_result.success else (
        f"BUILD: FAILED ({build_result.error_count} errors)\n"
        + "\n".join(build_result.first_errors[:10] if build_result.first_errors else [])
    )

    # Sprint context for retry awareness
    sprint_context = f"Sprint {sprint_num}/{max_sprints}"
    if sprint_num > 1:
        sprint_context += f" (this is retry #{sprint_num - 1} — be stricter: same issues recurring = lower score)"
    if sprint_num >= max_sprints:
        sprint_context += " — LAST SPRINT: score harshly, no more retries possible"

    # Prior feedback for learning across retries
    prior_section = ""
    if prior_feedback:
        prior_section = f"""
## Prior Sprint Feedback (issues from previous attempts)
{prior_feedback[:1000]}
Check whether these issues have been FIXED. If they recur, score lower.
"""

    prompt = f"""You are a strict QA judge evaluating a software development phase.
Your job is to score the deliverables objectively based on EVIDENCE, not claims.

## Phase: {phase_name}
## Sprint: {sprint_context}

## Project Acceptance Criteria
{specs_evidence}

## Build Result (DETERMINISTIC — ground truth)
{build_evidence}

## Files in Workspace
{files_evidence}

## Adversarial Rejections This Phase: {adversarial_rejections}
{prior_section}
## Phase Output Summary
{phase_output[:2000]}

## Evaluation Criteria
Score each criterion 0-10:
1. **Compilation**: Does the code compile? (BUILD result is ground truth — if FAILED, compilation=0)
2. **Completeness**: Are ALL required files present? Check against acceptance criteria above
3. **Quality**: Code structure, no obvious issues, follows project specs
4. **Tests**: Are test files present AND do they pass? (BUILD result is ground truth)
5. **Acceptance**: Does the output meet the acceptance criteria from SPECS?

IMPORTANT: Be strict. A score of 6/10 means "barely acceptable". 8+ means "good quality".
If build FAILED, overall MUST be ≤3. If tests fail, overall MUST be ≤5.

## Response Format (XML only)
<judge>
  <compilation>0-10</compilation>
  <completeness>0-10</completeness>
  <quality>0-10</quality>
  <tests>0-10</tests>
  <acceptance>0-10</acceptance>
  <overall>0-10</overall>
  <verdict>APPROVE|RETRY|REJECT</verdict>
  <reason>one sentence</reason>
</judge>
"""

    llm = get_llm_client()
    try:
        resp = await asyncio.wait_for(
            llm.chat(
                [LLMMessage(role="user", content=prompt)],
                temperature=0.1,
                max_tokens=400,
            ),
            timeout=30,
        )
        content = (resp.content or "").strip()
        return _parse_judge_response(content)
    except Exception as e:
        logger.warning("Judge LLM failed: %s", e)
        score = 1.0 if build_result.success else 0.2
        return score, f"Judge unavailable — build {'passed' if build_result.success else 'failed'}"


def _parse_judge_response(content: str) -> tuple[float, str]:
    """Parse judge LLM response into (score, verdict), XML only."""

    # Strip markdown fences and thinking blocks
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
    content = re.sub(r"```xml\s*", "", content)
    content = re.sub(r"```\s*", "", content)
    content = content.strip()

    try:
        xml = content
        m = re.search(r"<judge>.*?</judge>", xml, re.DOTALL)
        if m:
            xml = m.group(0)
        root = ET.fromstring(xml)
        if root.tag == "judge":
            def _txt(tag: str, default: str = "") -> str:
                n = root.find(tag)
                return (n.text or "").strip() if n is not None and n.text else default

            overall = float(_txt("overall", "5")) / 10.0
            verdict = _txt("verdict", "RETRY")
            reason = _txt("reason", "")
            compilation = _txt("compilation", "5")
            return overall, f"{verdict}: {reason} (compile={compilation}/10)"
    except Exception:
        return 0.5, f"Judge parse error: {content[:200]}"

    return 0.5, f"Judge parse error: {content[:200]}"


def _list_deliverables(workspace: str) -> str:
    """List files in workspace for evidence."""
    if not workspace or not os.path.isdir(workspace):
        return "(no workspace)"

    lines = []
    for root, dirs, files in os.walk(workspace):
        # Skip hidden dirs and build dirs
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "__pycache__", "target", ".build")]
        rel_root = os.path.relpath(root, workspace)
        for f in sorted(files):
            if f.startswith("."):
                continue
            rel_path = os.path.join(rel_root, f) if rel_root != "." else f
            size = os.path.getsize(os.path.join(root, f))
            lines.append(f"  {rel_path} ({size}b)")
            if len(lines) >= 30:
                lines.append(f"  ... and more files")
                return "\n".join(lines)
    return "\n".join(lines) if lines else "(empty workspace)"


# ── PM Checkpoint ──────────────────────────────────────────────


async def pm_checkpoint(
    phase_name: str,
    phase_id: str,
    phase_output: str,
    workspace: str,
    phase_success: bool,
    adversarial_rejections: int = 0,
    is_last_phase: bool = False,
    sprint_num: int = 1,
    max_sprints: int = 1,
    prior_feedback: str = "",
    baseline_tests_passed: int = 0,
    target_tests_passed: int = 0,
    prior_anc_history: list[float] | None = None,
    project_id: str = "",
) -> PMDecision:
    """PM checkpoint: collect evidence, run build gate, call judge, decide.

    This is the PM's decision point between phases. It uses:
    1. Deterministic build result (ground truth)
    2. Test runner result + ANC metric (SWE-CI inspired)
    3. Judge LLM quality score (independent evaluation)
    4. Phase success flag from pattern engine
    5. Adversarial rejection count
    6. Sprint count for retry awareness
    7. Prior feedback for learning across retries
    """
    # Step 1: Build gate (deterministic) — only for code-producing phases
    _BUILD_PHASE_KEYWORDS = ("dev", "sprint", "impl", "code", "fix", "tdd", "build", "cicd", "deploy")
    is_code_phase = any(
        k in (phase_id or "").lower()
        for k in _BUILD_PHASE_KEYWORDS
    )
    if is_code_phase:
        build_result = await run_build_gate(workspace)
    else:
        build_result = BuildResult(success=True, command="(skipped — non-code phase)")

    logger.warning(
        "PM_GATE build=%s errors=%d phase=%s sprint=%d/%d",
        "OK" if build_result.success else "FAIL",
        build_result.error_count,
        phase_id,
        sprint_num,
        max_sprints,
    )

    # Step 1b: Test runner + ANC tracking (SWE-CI CI-loop)
    # Run tests and compute Normalized Change to track improvement trajectory
    test_result = None
    anc_score = None
    if is_code_phase and build_result.success:
        test_result = await run_test_gate(workspace)
        if test_result.total > 0:
            target = target_tests_passed if target_tests_passed > 0 else test_result.total
            baseline = baseline_tests_passed if baseline_tests_passed > 0 else 0
            anc_score = compute_anc(
                baseline_passed=baseline,
                current_passed=test_result.passed,
                target_passed=target,
                prior_ncs=prior_anc_history,
            )
            logger.warning(
                "PM_ANC nc=%.3f anc=%.3f tests=%d/%d phase=%s sprint=%d/%d",
                anc_score.nc, anc_score.anc,
                test_result.passed, test_result.total,
                phase_id, sprint_num, max_sprints,
            )

    # Step 2: Judge LLM (independent quality evaluation)
    quality_score, judge_verdict = await judge_phase_quality(
        phase_name=phase_name,
        phase_output=phase_output,
        build_result=build_result,
        workspace=workspace,
        adversarial_rejections=adversarial_rejections,
        sprint_num=sprint_num,
        max_sprints=max_sprints,
        prior_feedback=prior_feedback,
    )

    logger.warning(
        "PM_JUDGE score=%.2f verdict=%s phase=%s sprint=%d/%d",
        quality_score,
        judge_verdict[:80],
        phase_id,
        sprint_num,
        max_sprints,
    )

    # Step 3: PM decision based on evidence
    test_line = ""
    if test_result and test_result.total > 0:
        test_line = f"\nTests: {test_result.passed}/{test_result.total} passed ({test_result.failed} failed)"
    anc_line = ""
    if anc_score:
        direction = "improving" if anc_score.nc > 0 else "regressing" if anc_score.nc < 0 else "stable"
        anc_line = f"\nANC: {anc_score.anc:+.3f} (NC={anc_score.nc:+.3f}, {direction})"
    ko_drift, missing_ko = _evaluate_ko_drift(
        project_id=project_id,
        evidence_text=f"{phase_output}\n{prior_feedback}",
    )
    ko_line = ""
    if missing_ko:
        ko_line = f"\nKO drift: missing mandatory constraints → {', '.join(missing_ko[:8])}"
    evidence_summary = (
        f"Build: {'PASS' if build_result.success else f'FAIL ({build_result.error_count} errors)'}\n"
        f"Judge: {quality_score:.1%} — {judge_verdict}\n"
        f"Pattern: {'success' if phase_success else 'failed'}\n"
        f"Adversarial rejections: {adversarial_rejections}\n"
        f"Sprint: {sprint_num}/{max_sprints}"
        f"{test_line}{anc_line}{ko_line}"
    )

    # Hard rules (deterministic, no LLM needed):

    if is_code_phase and not build_result.success:
        if sprint_num < max_sprints:
            error_feedback = ""
            if build_result.first_errors:
                error_feedback = "\n".join(build_result.first_errors[:10])
            return PMDecision(
                action="retry",
                reason=f"Build failed with {build_result.error_count} errors — sprint {sprint_num}/{max_sprints}",
                build_result=build_result,
                quality_score=quality_score,
                evidence_summary=evidence_summary + f"\n\nBuild errors:\n{error_feedback}",
                test_result=test_result,
                anc_score=anc_score,
            )
        else:
            return PMDecision(
                action="next",
                reason=f"Build still failing after {max_sprints} sprints — moving on with issues",
                build_result=build_result,
                quality_score=quality_score,
                evidence_summary=evidence_summary,
                test_result=test_result,
                anc_score=anc_score,
            )

    # ANC regression guard: if tests are regressing (NC < -0.2), force retry
    if anc_score and anc_score.nc < -0.2 and sprint_num < max_sprints:
        return PMDecision(
            action="retry",
            reason=f"Test regression — ANC NC={anc_score.nc:+.3f} (tests went from {anc_score.baseline_passed} to {anc_score.current_passed}). Fix regressions before proceeding.",
            build_result=build_result,
            quality_score=quality_score,
            evidence_summary=evidence_summary,
            test_result=test_result,
            anc_score=anc_score,
        )

    if ko_drift and sprint_num < max_sprints:
        return PMDecision(
            action="retry",
            reason=(
                "Mandatory knowledge constraints drifted — "
                f"missing: {', '.join(missing_ko[:8])}"
            ),
            build_result=build_result,
            quality_score=quality_score,
            evidence_summary=evidence_summary,
            test_result=test_result,
            anc_score=anc_score,
        )

    # Build passes — use judge score + phase success for decision
    MIN_DONE_QUALITY = 0.5
    if is_last_phase:
        if quality_score >= MIN_DONE_QUALITY or sprint_num >= max_sprints:
            return PMDecision(
                action="done",
                reason=f"Last phase complete — quality {quality_score:.0%}",
                build_result=build_result,
                quality_score=quality_score,
                evidence_summary=evidence_summary,
                test_result=test_result,
                anc_score=anc_score,
            )
        return PMDecision(
            action="retry",
            reason=f"Last phase — quality {quality_score:.0%} below {MIN_DONE_QUALITY:.0%} threshold, retrying sprint {sprint_num}/{max_sprints}",
            build_result=build_result,
            quality_score=quality_score,
            evidence_summary=evidence_summary,
            test_result=test_result,
            anc_score=anc_score,
        )

    quality_threshold = 0.6 if sprint_num <= 1 else 0.5
    if phase_success and quality_score >= quality_threshold:
        return PMDecision(
            action="next",
            reason=f"Phase approved — build OK, quality {quality_score:.0%}",
            build_result=build_result,
            quality_score=quality_score,
            evidence_summary=evidence_summary,
            test_result=test_result,
            anc_score=anc_score,
        )

    if not phase_success and sprint_num < max_sprints:
        return PMDecision(
            action="retry",
            reason=f"Phase failed, quality {quality_score:.0%} — retrying sprint {sprint_num}/{max_sprints}",
            build_result=build_result,
            quality_score=quality_score,
            evidence_summary=evidence_summary,
            test_result=test_result,
            anc_score=anc_score,
        )

    if phase_success and quality_score < quality_threshold and sprint_num < max_sprints:
        return PMDecision(
            action="retry",
            reason=f"Quality too low ({quality_score:.0%} < {quality_threshold:.0%}) — retrying sprint {sprint_num}/{max_sprints}",
            build_result=build_result,
            quality_score=quality_score,
            evidence_summary=evidence_summary,
            test_result=test_result,
            anc_score=anc_score,
        )

    # Default: proceed (max sprints exhausted or non-code phase)
    return PMDecision(
        action="next",
        reason=f"Phase complete — quality {quality_score:.0%}",
        build_result=build_result,
        quality_score=quality_score,
        evidence_summary=evidence_summary,
        test_result=test_result,
        anc_score=anc_score,
    )


# ── Test Gap Analysis (SWE-CI CI-loop) ────────────────────────
# Ref: feat-test-gap-pattern


def generate_test_gap_requirements(
    test_result: TestResult,
    build_result: BuildResult,
    anc_score: ANCScore | None = None,
    phase_name: str = "",
) -> str:
    """Generate structured requirements document from test gap analysis.

    SWE-CI dual-agent pattern: Architect analyzes CI feedback → produces
    requirements → Programmer implements. This function generates the
    requirements document that bridges the two roles.

    The output is a structured natural language document that can be
    injected into the programmer agent's task context.
    """
    sections = []
    sections.append(f"# Test Gap Requirements — {phase_name}")
    sections.append(f"Generated from CI-loop analysis (SWE-CI pattern)\n")

    # Build status section
    if not build_result.success:
        sections.append("## 1. Build Failures (BLOCKING)")
        sections.append(f"Build command `{build_result.command}` failed with {build_result.error_count} errors.")
        sections.append("Fix these FIRST before addressing test failures:\n")
        if build_result.first_errors:
            for i, err in enumerate(build_result.first_errors[:10], 1):
                sections.append(f"  {i}. {err}")
        sections.append("")

    # Test gap section
    if test_result and test_result.total > 0:
        sections.append("## 2. Test Gap Analysis")
        sections.append(f"- Tests passing: {test_result.passed}/{test_result.total}")
        sections.append(f"- Tests failing: {test_result.failed}")
        sections.append(f"- Tests skipped: {test_result.skipped}")
        gap = test_result.total - test_result.passed
        if gap > 0:
            sections.append(f"\n**Test Gap: {gap} tests need to pass.**")
            sections.append("Requirements:")
            sections.append("  1. Run the test suite to identify failing tests")
            sections.append("  2. For each failing test, analyze the error message")
            sections.append("  3. Implement the minimum code change to make the test pass")
            sections.append("  4. Verify no regressions (previously passing tests still pass)")
        else:
            sections.append("\nAll tests passing — focus on maintainability improvements.")
        sections.append("")

    # ANC trajectory section
    if anc_score:
        sections.append("## 3. Improvement Trajectory (ANC)")
        sections.append(f"- Baseline: {anc_score.baseline_passed} tests passing")
        sections.append(f"- Current:  {anc_score.current_passed} tests passing")
        sections.append(f"- Target:   {anc_score.target_passed} tests passing")
        sections.append(f"- NC this iteration: {anc_score.nc:+.3f}")
        sections.append(f"- ANC overall: {anc_score.anc:+.3f}")
        if anc_score.nc < 0:
            sections.append("\n**WARNING: Tests are REGRESSING. Prioritize fixing regressions.**")
        elif anc_score.nc < 0.5 and anc_score.target_passed > anc_score.current_passed:
            sections.append("\n**Progress is slow. Focus on high-impact changes.**")
        sections.append("")

    # Constraints
    sections.append("## 4. Constraints")
    sections.append("- Do NOT skip, disable, or weaken existing tests")
    sections.append("- Do NOT add test-mode bypasses to production code")
    sections.append("- Prefer minimal, surgical changes over large refactors")
    sections.append("- Run tests after each change to verify no regressions")

    return "\n".join(sections)
