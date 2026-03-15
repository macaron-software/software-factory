# Ref: feat-skills, feat-subagent-prompts
"""
Subagent Prompt Templates — Formalized roles for task delegation
================================================================

Inspired by obra/superpowers subagent-driven-development.
Three specialized roles with clear boundaries:
  - Implementer: writes code, runs tests, self-reviews
  - Spec Reviewer: validates output matches requirements
  - Code Quality Reviewer: checks style, patterns, security

Usage:
    from platform.agents.subagent_prompts import build_implementer_prompt, build_spec_reviewer_prompt
    prompt = build_implementer_prompt(task_spec="Add login endpoint", context={...})
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def build_implementer_prompt(
    task_spec: str,
    context: dict | None = None,
    project_id: str = "",
    constraints: list[str] | None = None,
) -> str:
    """
    Build prompt for implementer subagent.
    Implementer writes code, runs tests, self-reviews, commits.

    Returns structured prompt with task, context, and methodology.
    """
    ctx = context or {}
    file_hints = ctx.get("files", [])
    tech_stack = ctx.get("tech_stack", "")
    test_framework = ctx.get("test_framework", "")
    branch = ctx.get("branch", "")

    parts = [
        "# Implementation Task",
        "",
        f"## Specification\n{task_spec}",
        "",
        "## Methodology (mandatory)",
        "1. **Understand** — Read the spec completely. If anything is ambiguous, report status NEEDS_CONTEXT.",
        "2. **Test first** — Write a failing test that validates the spec. Run it. Confirm RED.",
        "3. **Implement** — Write the minimal code to make the test pass. Confirm GREEN.",
        "4. **Refactor** — Clean up without changing behavior. Tests still GREEN.",
        "5. **Self-review** — Check your own code against the spec. Fix issues before reporting.",
        "6. **Commit** — Atomic commit with descriptive message.",
        "",
        "## Status Protocol",
        "Report exactly ONE of:",
        "- **DONE** — Task complete, tests pass, committed.",
        "- **DONE_WITH_CONCERNS** — Complete but flagging doubts (explain).",
        "- **NEEDS_CONTEXT** — Cannot proceed without more information (list what's needed).",
        "- **BLOCKED** — Cannot complete (explain why, suggest alternatives).",
        "",
        "## Constraints",
        "- NO code before tests (delete code written before tests)",
        "- NO mock/fake/stub data — live data only",
        "- NO fallback to empty/placeholder implementations",
        "- Commit only when tests pass",
    ]

    if constraints:
        for c in constraints:
            parts.append(f"- {c}")

    if file_hints:
        parts.extend(["", "## Files to modify", *[f"- `{f}`" for f in file_hints]])

    if tech_stack:
        parts.extend(["", f"## Tech Stack\n{tech_stack}"])

    if test_framework:
        parts.extend(["", f"## Test Framework\n{test_framework}"])

    if branch:
        parts.extend(["", f"## Branch\n`{branch}`"])

    return "\n".join(parts)


def build_spec_reviewer_prompt(
    task_spec: str,
    implementation_summary: str = "",
    changed_files: list[str] | None = None,
) -> str:
    """
    Build prompt for spec compliance reviewer subagent.
    Validates that implementation matches the original specification.
    Does NOT review code quality — only spec compliance.
    """
    files_section = ""
    if changed_files:
        files_section = "\n## Changed Files\n" + "\n".join(f"- `{f}`" for f in changed_files)

    return f"""# Spec Compliance Review

## Original Specification
{task_spec}

## Implementation Summary
{implementation_summary}
{files_section}

## Review Checklist
For each requirement in the spec, verify:
1. **Implemented** — Is the requirement present in the code?
2. **Correct** — Does the implementation match the spec exactly?
3. **Complete** — No requirements missing?
4. **No extras** — Nothing added that wasn't requested?

## Verdict
Report:
- **APPROVED** — All spec requirements met, nothing extra.
- **REJECTED** — List each issue:
  - MISSING: requirement X not implemented
  - WRONG: requirement Y implemented incorrectly (expected vs actual)
  - EXTRA: feature Z added but not in spec (remove it)

Be strict. Spec compliance is binary — it either matches or it doesn't.
"""


def build_code_quality_reviewer_prompt(
    changed_files: list[str] | None = None,
    git_diff: str = "",
    project_conventions: str = "",
) -> str:
    """
    Build prompt for code quality reviewer subagent.
    Reviews code quality AFTER spec compliance is confirmed.
    """
    files_section = ""
    if changed_files:
        files_section = "\n## Files Changed\n" + "\n".join(f"- `{f}`" for f in changed_files)

    diff_section = ""
    if git_diff:
        truncated = git_diff[:3000] + ("..." if len(git_diff) > 3000 else "")
        diff_section = f"\n## Diff\n```\n{truncated}\n```"

    conventions_section = ""
    if project_conventions:
        conventions_section = f"\n## Project Conventions\n{project_conventions}"

    return f"""# Code Quality Review

Review the implementation for quality issues. Spec compliance is already confirmed.
{files_section}
{diff_section}
{conventions_section}

## Review Dimensions (by severity)

### Critical (blocks merge)
- Security vulnerabilities (injection, hardcoded secrets, SSRF)
- Data loss risks
- Race conditions / deadlocks
- Broken error handling (swallowed exceptions)

### Important (should fix)
- Missing error handling for external calls
- Magic numbers / hardcoded values
- Duplicate code (DRY violations)
- Missing input validation
- Performance issues (N+1 queries, unbounded loops)

### Minor (note but don't block)
- Naming clarity
- Documentation gaps
- Test coverage gaps

## Verdict
- **APPROVED** — No critical or important issues.
- **APPROVED_WITH_NOTES** — Minor issues noted but not blocking.
- **CHANGES_REQUESTED** — Critical or important issues found. List each with:
  - Severity (Critical/Important)
  - File and line
  - Issue description
  - Suggested fix
"""


def build_finish_prompt(
    branch: str,
    tasks_completed: int = 0,
    test_results: str = "",
) -> str:
    """
    Build prompt for finishing a development branch.
    Options: merge, PR, keep, discard.
    """
    return f"""# Branch Completion: `{branch}`

## Summary
- Tasks completed: {tasks_completed}
- Test results: {test_results or "not available"}

## Options
1. **Merge to main** — All tests pass, ready to ship.
2. **Create PR** — Needs human review before merge.
3. **Keep branch** — Work in progress, will continue later.
4. **Discard** — Experiment failed, delete branch and worktree.

## Pre-merge Checklist
- [ ] All tests pass
- [ ] No uncommitted changes
- [ ] Commit messages are descriptive
- [ ] No debug/console.log left in code
"""
"""
Subagent Prompt Templates — Formalized roles for task delegation.
Inspired by obra/superpowers subagent-driven-development.
"""
