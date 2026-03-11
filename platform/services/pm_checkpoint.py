"""PM Checkpoint — Evidence-based phase gate with build validation and judge LLM.

After each phase, the PM checkpoint:
1. Runs deterministic build validation (build gate)
2. Calls a judge LLM with all evidence (build result, deliverables, adversarial scores)
3. Returns a decision: next / retry / done

This replaces blind phase transitions with evidence-driven decisions.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import subprocess
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
class PMDecision:
    action: str  # "next" | "retry" | "done" | "abort"
    reason: str
    build_result: BuildResult | None = None
    quality_score: float = 0.0
    evidence_summary: str = ""


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
    error_lines = [
        ln.strip()
        for ln in raw.splitlines()
        if "error:" in ln.lower() or "error[" in ln.lower()
    ]
    seen_msgs = set()
    unique_errors = []
    for ln in error_lines:
        # Extract just the error message part (after "error:")
        match = re.search(r"error[:\[](.+)", ln, re.IGNORECASE)
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

## Response Format (JSON only)
{{"compilation": 0-10, "completeness": 0-10, "quality": 0-10, "tests": 0-10, "acceptance": 0-10, "overall": 0-10, "verdict": "APPROVE|RETRY|REJECT", "reason": "one sentence"}}
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
    """Parse judge LLM JSON response into (score, verdict)."""
    import json

    # Strip markdown fences and thinking blocks
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
    content = re.sub(r"```json\s*", "", content)
    content = re.sub(r"```\s*", "", content)
    content = content.strip()

    try:
        data = json.loads(content)
        overall = float(data.get("overall", 5)) / 10.0
        verdict = data.get("verdict", "RETRY")
        reason = data.get("reason", "")
        compilation = data.get("compilation", 5)
        return overall, f"{verdict}: {reason} (compile={compilation}/10)"
    except (json.JSONDecodeError, ValueError):
        # Try to extract score from text
        match = re.search(r'"overall"\s*:\s*(\d+)', content)
        if match:
            return float(match.group(1)) / 10.0, content[:200]
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
) -> PMDecision:
    """PM checkpoint: collect evidence, run build gate, call judge, decide.

    This is the PM's decision point between phases. It uses:
    1. Deterministic build result (ground truth)
    2. Judge LLM quality score (independent evaluation)
    3. Phase success flag from pattern engine
    4. Adversarial rejection count
    5. Sprint count for retry awareness
    6. Prior feedback for learning across retries
    """
    from ..llm.client import LLMMessage, get_llm_client

    # Step 1: Build gate (deterministic)
    build_result = await run_build_gate(workspace)

    logger.warning(
        "PM_GATE build=%s errors=%d phase=%s sprint=%d/%d",
        "OK" if build_result.success else "FAIL",
        build_result.error_count,
        phase_id,
        sprint_num,
        max_sprints,
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
    evidence_summary = (
        f"Build: {'PASS' if build_result.success else f'FAIL ({build_result.error_count} errors)'}\n"
        f"Judge: {quality_score:.1%} — {judge_verdict}\n"
        f"Pattern: {'success' if phase_success else 'failed'}\n"
        f"Adversarial rejections: {adversarial_rejections}\n"
        f"Sprint: {sprint_num}/{max_sprints}"
    )

    # Hard rules (deterministic, no LLM needed):
    is_code_phase = any(
        k in (phase_id or "").lower()
        for k in ("dev", "sprint", "impl", "code", "fix", "tdd")
    )

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
            )
        else:
            return PMDecision(
                action="next",
                reason=f"Build still failing after {max_sprints} sprints — moving on with issues",
                build_result=build_result,
                quality_score=quality_score,
                evidence_summary=evidence_summary,
            )

    # Build passes — use judge score + phase success for decision
    if is_last_phase:
        return PMDecision(
            action="done",
            reason=f"Last phase complete — quality {quality_score:.0%}",
            build_result=build_result,
            quality_score=quality_score,
            evidence_summary=evidence_summary,
        )

    # Quality threshold: 0.6 = 60% minimum to proceed
    # Stricter on later sprints (already had chances to fix)
    quality_threshold = 0.6 if sprint_num <= 1 else 0.5
    if phase_success and quality_score >= quality_threshold:
        return PMDecision(
            action="next",
            reason=f"Phase approved — build OK, quality {quality_score:.0%}",
            build_result=build_result,
            quality_score=quality_score,
            evidence_summary=evidence_summary,
        )

    if not phase_success and sprint_num < max_sprints:
        return PMDecision(
            action="retry",
            reason=f"Phase failed, quality {quality_score:.0%} — retrying sprint {sprint_num}/{max_sprints}",
            build_result=build_result,
            quality_score=quality_score,
            evidence_summary=evidence_summary,
        )

    if phase_success and quality_score < quality_threshold and sprint_num < max_sprints:
        return PMDecision(
            action="retry",
            reason=f"Quality too low ({quality_score:.0%} < {quality_threshold:.0%}) — retrying sprint {sprint_num}/{max_sprints}",
            build_result=build_result,
            quality_score=quality_score,
            evidence_summary=evidence_summary,
        )

    # Default: proceed (max sprints exhausted or non-code phase)
    return PMDecision(
        action="next",
        reason=f"Phase complete — quality {quality_score:.0%}",
        build_result=build_result,
        quality_score=quality_score,
        evidence_summary=evidence_summary,
    )
