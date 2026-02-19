#!/usr/bin/env python3
"""
Wiggum TDD - Parallel TDD Workers
=================================
Based on MIT CSAIL arXiv:2512.24601 "Recursive Language Models"

50 parallel workers that execute TDD cycle:
1. Analyze task, check FRACTAL thresholds
2. If too large → decompose into sub-tasks
3. RED: Write failing test
4. GREEN: Write code to pass test
5. VERIFY: Run test
6. ADVERSARIAL: Check code quality
7. COMMIT: If all pass

Uses MiniMax M2.5 via `opencode` for code generation.

Usage:
    from core.wiggum_tdd import WiggumPool

    pool = WiggumPool("ppz", workers=5)  # OOM safe
    await pool.run()  # Daemon mode
    await pool.run_once()  # Single task
"""

import asyncio
import json
import os
import shutil
import subprocess
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.project_registry import get_project, ProjectConfig
from core.task_store import TaskStore, Task, TaskStatus
from core.adversarial import AdversarialGate, CheckResult
from core.fractal import FractalDecomposer, should_decompose
from core.llm_client import run_opencode, run_claude_haiku
from core.error_capture import ErrorCapture, ErrorType, ErrorSeverity
from core.daemon import Daemon, DaemonManager, print_daemon_status, print_all_status
from core.skills import load_skills_for_task
from core.subprocess_util import run_subprocess
from core.log import get_logger
from core.error_patterns import is_transient


_module_logger = get_logger("wiggum-tdd")


def log(msg: str, level: str = "INFO", worker_id: int = None):
    """Log with timestamp and optional worker ID"""
    prefix = f"W{worker_id}" if worker_id is not None else "POOL"
    _module_logger.log(f"[{prefix}] {msg}", level)


# ============================================================================
# TDD WORKER
# ============================================================================

@dataclass
class TDDResult:
    """Result of a TDD cycle"""
    success: bool
    task_id: str
    test_written: bool = False
    code_written: bool = False
    test_passed: bool = False
    adversarial_passed: bool = False
    committed: bool = False
    error: str = ""
    iterations: int = 0


class WiggumWorker:
    """
    Single Wiggum TDD worker.

    Executes the TDD cycle for a single task:
    1. Claim task from store
    2. Check FRACTAL → decompose if needed
    3. RED: Write test
    4. GREEN: Write code
    5. VERIFY: Run test
    6. ADVERSARIAL: Quality gate
    7. COMMIT: Git commit if passed
    """

    MAX_ITERATIONS = 10  # Max retry iterations
    OPENCODE_TIMEOUT = 600  # 10 min - let model work. Fallback only on RATE LIMIT, not timeout.

    # Transient error detection delegated to core.error_patterns

    def __init__(
        self,
        worker_id: int,
        project: ProjectConfig,
        task_store: TaskStore,
        adversarial: AdversarialGate,
        decomposer: FractalDecomposer,
    ):
        self.worker_id = worker_id
        self.project = project
        self.task_store = task_store
        self.adversarial = adversarial
        self.decomposer = decomposer
        self.error_capture = ErrorCapture(project)  # Error capture for feedback loop
        self._running = True

    def log(self, msg: str, level: str = "INFO"):
        log(msg, level, self.worker_id)

    def _is_transient_error(self, output: str) -> bool:
        """Check if the error is transient/infra (not a code issue, should retry)"""
        from core.error_patterns import is_infra
        return is_transient(output) or is_infra(output)

    def _is_truncated_output(self, output: str) -> bool:
        """Detect if LLM output was truncated (hit token limit).
        Truncated = task too large for single agent, needs FRACTAL decomposition."""
        if not output:
            return False
        # Common truncation indicators
        if output.rstrip().endswith(('...', '``', '```', '// ...', '/* ...', '...')):
            return True
        # Unbalanced braces/brackets (code cut mid-block)
        opens = output.count('{') + output.count('[')
        closes = output.count('}') + output.count(']')
        if opens > closes + 3:  # Significant imbalance
            return True
        return False

    async def run_single(self, task: Task) -> TDDResult:
        """Run TDD cycle for a single task"""
        result = TDDResult(success=False, task_id=task.id)

        self.log(f"Starting task: {task.id}")
        self.log(f"Description: {task.description[:80]}...")

        try:
            # 1. LOCK FIRST to prevent race conditions (before FRACTAL check)
            # PENDING → LOCKED
            if not self.task_store.transition(task.id, TaskStatus.LOCKED, changed_by=self.worker_id):
                self.log("Failed to lock task, may be taken by another worker", "WARN")
                return result

            # 2. FRACTAL: Check if task should be decomposed into atomic sub-tasks
            # Purpose: Prevent agents from responding partially and leaving gaps
            task_dict = task.to_dict()
            current_depth = task_dict.get("depth", 0)
            should_split, analysis = self.decomposer.should_decompose(task_dict, current_depth)

            if should_split and current_depth < 3:  # Max 3 levels deep
                self.log(f"🔀 FRACTAL: Decomposing task (depth={current_depth}, reason={analysis.reason})")
                subtasks = await self.decomposer.decompose(task_dict, current_depth)
                if subtasks and len(subtasks) > 0:
                    return await self._run_parallel_subtasks(task, subtasks)
                else:
                    self.log("FRACTAL: No subtasks generated, processing directly", "WARN")

            # 3. Transition to TDD in progress
            # LOCKED → TDD_IN_PROGRESS
            self.task_store.transition(task.id, TaskStatus.TDD_IN_PROGRESS, changed_by=self.worker_id)

            # 3. TDD iterations - loop until validation (RLM pattern)
            feedback = ""  # Accumulated feedback from adversarial
            last_adversarial_issues = []  # Store last issues for feedback loop
            last_code_changes = {}  # Store last code changes for context
            transient_failures = 0  # Track transient errors for retry logic
            total_failures = 0  # Track all failures
            for iteration in range(self.MAX_ITERATIONS):
                result.iterations = iteration + 1
                self.log(f"Iteration {iteration + 1}/{self.MAX_ITERATIONS}")

                # Reload task to get latest context (including feedback)
                task = self.task_store.get_task(task.id) or task

                # Build TDD prompt with feedback
                prompt = self._build_tdd_prompt(task, iteration, feedback)

                # Capture git status before running opencode
                git_before = self._get_git_status()

                # Run MiniMax for TDD (prompt already enforces strict scope)
                returncode, output = await run_opencode(
                    prompt,
                    model="minimax/MiniMax-M2.5",
                    cwd=str(self.project.root_path),
                    timeout=self.OPENCODE_TIMEOUT,
                )


                if returncode != 0:
                    total_failures += 1
                    if self._is_transient_error(output):
                        transient_failures += 1
                        self.log(f"⚡ Transient error (infra): {output[:100]}", "WARN")
                    else:
                        self.log(f"opencode failed: {output[:200]}", "WARN")
                    continue

                # Detect truncated output (task too large, needs better FRACTAL split)
                if self._is_truncated_output(output or ""):
                    self.log(f"⚠️ TRUNCATED output detected — task may be too large for single agent", "WARN")
                    feedback = ("TRUNCATED: Your previous output was cut off (token limit). "
                                "Write LESS code. Focus on the MINIMUM change needed. "
                                "Do NOT write full files — only the changed parts.")

                # Detect code changes using git (more reliable than output parsing)
                code_changes = self._detect_git_changes(git_before)
                if not code_changes:
                    # Fallback to output parsing
                    code_changes = self._extract_code_changes(output)
                if not code_changes:
                    self.log("No code changes extracted", "WARN")
                    continue
                else:
                    self.log(f"Detected {len(code_changes)} file changes: {list(code_changes.keys())[:3]}")

                # SCOPE CHECK: Reject if files outside task scope were modified
                if task.files:
                    allowed_files = set(task.files)
                    modified_files = set(code_changes.keys())
                    # Normalize paths (remove leading ./ and trailing /)
                    allowed_normalized = {f.strip('./').rstrip('/') for f in allowed_files}

                    # Handle LLM hallucination: it creates files at wrong paths like "eligo-platform"
                    # Strategy: delete hallucinated paths, only check real veligo-platform paths
                    hallucinated_paths = {f for f in modified_files if f.startswith('eligo-platform/')}
                    if hallucinated_paths:
                        self.log(f"🗑️ Ignoring hallucinated paths: {hallucinated_paths}", "INFO")
                        for hp in hallucinated_paths:
                            hp_abs = os.path.join(self.project.root_path, hp)
                            if os.path.exists(hp_abs):
                                os.remove(hp_abs)
                            modified_files.discard(hp)
                            code_changes.pop(hp, None)
                        # Clean up empty eligo-platform directory if created
                        eligo_dir = os.path.join(self.project.root_path, 'eligo-platform')
                        if os.path.exists(eligo_dir):
                            shutil.rmtree(eligo_dir, ignore_errors=True)

                    modified_normalized = {f.strip('./').rstrip('/') for f in modified_files}
                    out_of_scope = modified_normalized - allowed_normalized
                    # Filter out auto-generated files (e.g., .sqlx/, node_modules/, dist/)
                    out_of_scope = {f for f in out_of_scope if not any(x in f for x in ['.sqlx/', 'node_modules/', 'dist/', 'target/', '.cache/'])}
                    if out_of_scope:
                        self.log(f"⛔ OUT OF SCOPE: Modified {out_of_scope} but task only allows {allowed_files}", "WARN")

                        # CREATE FEEDBACK TASKS for out-of-scope files
                        # The LLM clearly saw something to fix there - don't lose this insight
                        # FILTER: Skip generated/build/archived files (LLM hallucination, not real insight)
                        SKIP_PATTERNS = (
                            '.svelte-kit/', '/build/', '/dist/', '/target/',
                            'node_modules/', '__pycache__/', '.next/',
                            '_archived', '-archived', '/build/_app/',
                            '.class', '.pyc', '.o', '.so', '.dylib',
                        )
                        created_feedback = []
                        for oos_file in out_of_scope:
                            if any(p in oos_file for p in SKIP_PATTERNS):
                                self.log(f"⏭️ Skipping feedback for generated/archived file: {oos_file}")
                                continue
                            # Find the code written to this file
                            oos_code = code_changes.get(oos_file, "")
                            if not oos_code:
                                # Try with normalized path
                                oos_code = code_changes.get(f"./{oos_file}", "")

                            # Create feedback task for this file
                            feedback_task_id = f"feedback-scope-{self.project.id}-{oos_file.replace('/', '-')[:50]}"
                            existing = self.task_store.get_task(feedback_task_id)
                            if not existing:
                                # Detect domain from file extension
                                oos_domain = self._detect_domain_from_file(oos_file)
                                feedback_task = Task(
                                    id=feedback_task_id,
                                    project_id=self.project.id,
                                    domain=oos_domain,
                                    type="fix",
                                    description=f"Fix issues in {oos_file} (detected during scope violation, LLM wanted to modify this)",
                                    files=[oos_file],
                                    wsjf_score=12.0,  # High priority - LLM clearly saw something
                                    status="pending",
                                    context={
                                        "source_task": task.id,
                                        "attempted_code": oos_code[:2000] if oos_code else None,
                                        "reason": "scope_violation_feedback",
                                    },
                                )
                                self.task_store.create_task(feedback_task, skip_dedup=True)
                                created_feedback.append(oos_file)
                                self.log(f"📝 Created feedback task for out-of-scope file: {oos_file}")

                        feedback = (f"OUT OF SCOPE ERROR: You modified files outside your scope!\n"
                                   f"ALLOWED: {list(allowed_files)}\n"
                                   f"VIOLATED: {list(out_of_scope)}\n"
                                   f"Feedback tasks created for: {created_feedback}\n"
                                   f"ONLY modify the files in ALLOWED list. Start over.")
                        await self._git_reset()
                        continue

                result.code_written = True
                last_code_changes = code_changes  # Store for feedback loop

                # 4. ADVERSARIAL CHECK - LLM validates code quality (context-aware)
                check_result = await self._run_adversarial(code_changes)
                if not check_result.approved:
                    self.log(f"❌ Adversarial REJECTED (score={check_result.score}): {check_result.issues[:200]}", "WARN")
                    feedback = f"ADVERSARIAL REJECTED (score {check_result.score}/{check_result.threshold}):\n{check_result.issues}"
                    last_adversarial_issues = check_result.issues  # Store for feedback loop
                    # Revert changes and retry
                    await self._git_reset()
                    continue

                self.log(f"✅ Adversarial APPROVED (score={check_result.score})")

                # 5. Transition to CODE_WRITTEN → Build worker will pick it up
                self.task_store.transition(task.id, TaskStatus.CODE_WRITTEN)
                self.log(f"✅ Code written, queued for build ({len(code_changes)} files)")
                result.success = True
                return result

            # Max iterations reached - check if all failures were transient
            if total_failures > 0 and transient_failures == total_failures:
                # ALL failures were transient (infra issues) → release lock for retry
                result.error = "All iterations failed due to transient errors (infra)"
                self.task_store.transition(task.id, TaskStatus.PENDING, changed_by=self.worker_id)
                self.log(f"⚡ All {transient_failures} failures were transient - released for retry", "WARN")
                return result

            # RLM FEEDBACK LOOP: Create tasks from adversarial issues
            result.error = "Max iterations reached"
            self.task_store.transition(task.id, TaskStatus.TDD_FAILED)
            self.log("❌ Task failed after max iterations", "WARN")

            # Create feedback tasks from adversarial issues (RLM pattern)
            if last_adversarial_issues:
                source_files = list(last_code_changes.keys()) if last_code_changes else task.files
                created_tasks = self.task_store.create_tasks_from_adversarial(
                    project_id=self.project.id,
                    domain=task.domain,
                    issues=last_adversarial_issues,
                    source_files=source_files,
                )
                if created_tasks:
                    self.log(f"🔄 RLM FEEDBACK: Created {len(created_tasks)} fix tasks from adversarial issues")

        except Exception as e:
            result.error = str(e)
            # Check if exception is transient
            if self._is_transient_error(str(e)):
                self.log(f"⚡ Transient exception: {e}", "WARN")
                self.task_store.transition(task.id, TaskStatus.PENDING, changed_by=self.worker_id)
            else:
                self.log(f"Exception: {e}", "ERROR")
                self.task_store.transition(task.id, TaskStatus.TDD_FAILED)

        return result

    def _build_tdd_prompt(self, task: Task, iteration: int, feedback: str = "") -> str:
        """Build prompt for TDD cycle with accumulated feedback (RLM pattern)"""
        context = task.get_context() or {}

        feedback_section = ""

        # Check for deploy feedback (RLM loop from Deploy → TDD)
        deploy_feedback = context.get("deploy_feedback", "")
        if deploy_feedback:
            feedback_section += f"""
🔴 DEPLOY PIPELINE FAILED - RETURNED TO TDD:
{deploy_feedback}

The code passed TDD but FAILED in Deploy. You MUST fix the issues above.
"""

        # Check for adversarial feedback from current TDD iteration
        if feedback:
            feedback_section += f"""
⚠️ ADVERSARIAL REJECTED (iteration {iteration}):
{feedback}

You MUST address ALL the issues above before proceeding.
"""

        # Check if project has Figma integration
        figma_config = self.project.figma or {}
        figma_enabled = figma_config.get('enabled', False)

        figma_instructions = ""
        if figma_enabled and task.domain in ['svelte', 'typescript', 'frontend']:
            figma_instructions = """
⚠️ MANDATORY FIGMA CHECK (Design System Source of Truth):
Before writing ANY CSS or styling code, you MUST:
1. Call figma_get_design_context to get exact specs for the component
2. Call figma_get_variable_defs to get design tokens (colors, spacing, radius)
3. Use ONLY values from Figma (no hardcoded colors/spacing)

Figma tools (USE THEM):
- figma_get_design_context(fileKey, nodeId, clientFrameworks="svelte"): Get CSS specs
- figma_get_variable_defs(fileKey): Get design tokens
- figma_get_screenshot(fileKey, nodeId): Get visual reference

If you skip Figma check, the adversarial gate will REJECT your code.
"""

        # Playwright MCP instructions for E2E/frontend domains
        playwright_instructions = ""
        if task.domain in ['e2e', 'svelte', 'frontend', 'typescript']:
            playwright_instructions = """
PLAYWRIGHT MCP TOOLS (use for E2E testing and content verification):
- browser_navigate(url): Navigate to URL
- browser_snapshot(): Get page content as accessibility tree - USE THIS to see actual content
- browser_click(ref): Click element by ref from snapshot
- browser_type(ref, text): Type in input field
- browser_console_messages(): Check for console errors

WHEN WRITING E2E TESTS:
1. ALWAYS use browser_snapshot() to see actual page content BEFORE writing assertions
2. Write assertions for SPECIFIC content (NOT just HTTP 200):
   - expect(page.locator('h1')).toContainText('Expected Title')
   - expect(page.locator('[data-testid="user-email"]')).toHaveText('user@example.com')
3. NEVER just check HTTP status - verify the actual content matches expectations
4. Check for ABSENCE of error states:
   - expect(page.locator('.error-message')).not.toBeVisible()
   - expect(page.locator('.loading')).not.toBeVisible() // after page loads
5. Use browser_console_messages() to verify no JS errors
"""

        # Get domain-specific stack versions and framework conventions from YAML
        stack_instructions = ""
        if self.project.raw_config:
            domains_config = self.project.raw_config.get("domains", {})
            domain_config = domains_config.get(task.domain, {})

            stack = domain_config.get("stack", {})
            conventions = domain_config.get("conventions", [])

            if stack or conventions:
                stack_instructions = "\n⚠️ STACK VERSIONS & FRAMEWORK CONVENTIONS (MUST FOLLOW):\n"

                if stack:
                    stack_instructions += f"Stack: {', '.join(f'{k} {v}' for k, v in stack.items())}\n\n"

                if conventions:
                    for conv in conventions:
                        name = conv.get("name", "")
                        rule = conv.get("rule", "")
                        fix = conv.get("fix", "")
                        example = conv.get("example", "")

                        stack_instructions += f"📌 {name}:\n"
                        stack_instructions += f"   Rule: {rule}\n"
                        if fix:
                            stack_instructions += f"   Fix: {fix}\n"
                        if example:
                            # Truncate long examples
                            example_preview = example[:300] + "..." if len(example) > 300 else example
                            stack_instructions += f"   Example:\n{example_preview}\n"
                        stack_instructions += "\n"

        # Load domain-specific skills
        task_type = task.type if hasattr(task, 'type') else ""
        skills_prompt = load_skills_for_task(task.domain, task_type, max_chars=6000)

        # Build explicit file instruction
        allowed_files = task.files if task.files else []
        target_file = allowed_files[0] if allowed_files else "unknown"

        # Include FULL file content to avoid Read tool usage
        full_file_content = self._read_full_file(target_file, max_lines=800)

        # STRICT PROMPT - NO READ TOOL, file already provided
        prompt = f"""⛔ SINGLE-FILE EDIT - NO READ ALLOWED ⛔

═══════════════════════════════════════════════════════════════════════
TARGET FILE: {target_file}
═══════════════════════════════════════════════════════════════════════
ISSUE: {task.description}
═══════════════════════════════════════════════════════════════════════

FULL FILE CONTENT (already loaded, DO NOT use Read tool):
```
{full_file_content}
```

═══════════════════════════════════════════════════════════════════════
YOUR TASK - SINGLE EDIT ONLY:
═══════════════════════════════════════════════════════════════════════
1. Find the EXACT issue in the code above
2. Use ONLY the Edit tool with old_string/new_string to fix it
3. Make the SMALLEST possible change (ideally < 20 lines)

⛔⛔⛔ FORBIDDEN ACTIONS (= IMMEDIATE FAILURE) ⛔⛔⛔
✗ Do NOT use the Read tool (file is already above)
✗ Do NOT modify any file except: {target_file}
✗ Do NOT create new files
✗ Do NOT output the entire file - use Edit with small old_string/new_string
✗ Do NOT touch: tests/e2e/, package.json, Cargo.toml (unless it's {target_file})

If output > 100 lines or wrong file touched → REJECTED + RETRY
{feedback_section}"""
        return prompt

    def _read_full_file(self, target_file: str, max_lines: int = 1500) -> str:
        """Read full file content to include in prompt (avoids agent using Read tool)"""
        file_path = os.path.join(self.project.root_path, target_file)
        if not os.path.exists(file_path):
            return f"[File not found: {target_file}]"

        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()

            # Truncate if too long
            if len(lines) > max_lines:
                lines = lines[:max_lines]
                lines.append(f"\n... [TRUNCATED at {max_lines} lines] ...")

            # Add line numbers
            numbered_lines = [f"{i+1:4d}| {line.rstrip()}" for i, line in enumerate(lines)]
            return '\n'.join(numbered_lines)
        except Exception as e:
            return f"[Error reading file: {e}]"

    def _extract_focused_section(self, target_file: str, description: str, context_lines: int = 30) -> str:
        """Extract relevant section from file based on line number in description"""
        import re

        # Extract line number from description (e.g., "line=63", "Line 63", "line 63")
        line_match = re.search(r'line[= ]+(\d+)', description, re.IGNORECASE)
        target_line = int(line_match.group(1)) if line_match else 50  # Default to line 50

        # Read the file
        file_path = os.path.join(self.project.root_path, target_file)
        if not os.path.exists(file_path):
            return f"[File not found: {target_file}]"

        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()

            # Calculate range (±context_lines around target)
            start = max(0, target_line - context_lines - 1)
            end = min(len(lines), target_line + context_lines)

            # Build section with line numbers
            section_lines = []
            for i in range(start, end):
                line_num = i + 1
                marker = " >>> " if line_num == target_line else "     "
                section_lines.append(f"{line_num:4d}{marker}{lines[i].rstrip()}")

            return '\n'.join(section_lines)
        except Exception as e:
            return f"[Error reading file: {e}]"

    def _detect_domain_from_file(self, file_path: str) -> str:
        """Detect domain from file path/extension"""
        fp = file_path.lower()

        # E2E tests
        if '.spec.ts' in fp or '.spec.js' in fp or 'tests/e2e' in fp or 'e2e/' in fp:
            return 'e2e'

        # Rust
        if fp.endswith('.rs'):
            return 'rust'

        # Svelte
        if fp.endswith('.svelte'):
            return 'svelte'

        # TypeScript/Frontend
        if fp.endswith('.ts') or fp.endswith('.tsx'):
            if 'frontend' in fp or 'src/lib' in fp or 'src/routes' in fp:
                return 'svelte'
            return 'typescript'

        # Mobile (Swift/Kotlin)
        if fp.endswith('.swift'):
            return 'swift'
        if fp.endswith('.kt') or fp.endswith('.java'):
            return 'kotlin'

        # Proto
        if fp.endswith('.proto'):
            return 'proto'

        # Default
        return 'unknown'

    def _get_git_status(self) -> set:
        """Get set of modified files from git.

        Filters out build artifacts to prevent ARG_MAX overflow when passing
        thousands of generated files to adversarial review.
        """
        import subprocess

        # Build artifacts that should NEVER be in scope (even if not gitignored)
        BUILD_ARTIFACT_PATTERNS = (
            'target/',           # Rust/Cargo
            '.svelte-kit/',      # SvelteKit
            'build/',            # Generic build
            'dist/',             # Generic dist
            'node_modules/',     # Node.js
            '.next/',            # Next.js
            '__pycache__/',      # Python
            '.gradle/',          # Android/Gradle
            'DerivedData/',      # Xcode iOS
            '.build/',           # Swift Package Manager
        )

        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(self.project.root_path),
                capture_output=True,
                text=True,
                timeout=10
            )
            files = set()
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    # Format: XY filename or XY "filename with spaces"
                    parts = line[3:].strip().strip('"')
                    if parts and not any(p in parts for p in BUILD_ARTIFACT_PATTERNS):
                        files.add(parts)
            return files
        except Exception:
            return set()

    def _detect_git_changes(self, before: set) -> Dict[str, str]:
        """Detect file changes by comparing git status before and after.

        Excludes pre-existing dirty files (submodules, build artifacts) that
        existed BEFORE the worker started, to avoid false scope violations.
        """
        after = self._get_git_status()
        new_changes = after - before

        changes = {}
        for f in new_changes:
            changes[f] = "modified"

        # Also check for modifications in existing files
        # --ignore-submodules: avoid dirty submodules polluting scope check
        import subprocess
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "--ignore-submodules"],
                cwd=str(self.project.root_path),
                capture_output=True,
                text=True,
                timeout=10
            )
            for f in result.stdout.strip().split("\n"):
                f = f.strip()
                if f and f not in before:
                    changes[f] = "modified"
        except Exception:
            pass

        return changes

    async def _run_parallel_subtasks(self, parent_task: Task, subtasks: List[Dict]) -> TDDResult:
        """
        Run subtasks SEQUENTIALLY by concern order: feature → guards → failures.

        This ensures each concern builds on the previous:
        - feature: implements happy path
        - guards: adds validation/auth to feature code
        - failures: adds error handling to guards code

        Args:
            parent_task: The parent task being decomposed
            subtasks: List of subtask dicts from FRACTAL decomposition

        Returns:
            TDDResult with success=True if all subtasks passed
        """
        result = TDDResult(success=False, task_id=parent_task.id)

        # Sort subtasks by concern order: feature → guards → failures
        concern_order = {"feature": 0, "guards": 1, "failures": 2}
        sorted_subtasks = sorted(
            subtasks,
            key=lambda st: concern_order.get(st.get("aspect", ""), 99)
        )

        self.log(f"🔀 Running {len(sorted_subtasks)} sub-agents SEQUENTIALLY (feature→guards→failures)...")

        # Create subtasks in store first (in sorted order)
        import uuid
        subtask_ids = []
        for st in sorted_subtasks:
            subtask = Task(
                id=f"subtask-{parent_task.domain}-{uuid.uuid4().hex[:8]}",
                project_id=self.project.id,
                parent_id=parent_task.id,
                type=st.get("type", parent_task.type),
                domain=st.get("domain", parent_task.domain),
                description=st.get("description", ""),
                status="pending",
                files=st.get("files", []),
                context=st,
                depth=parent_task.depth + 1,
            )
            self.task_store.create_task(subtask)
            subtask_ids.append(subtask.id)
            self.log(f"  Created subtask: {subtask.id} ({st.get('aspect', 'sub')})")
        
        if not subtask_ids:
            self.log("Failed to create subtasks", "ERROR")
            result.error = "Failed to create subtasks"
            return result
        
        # Mark parent as decomposed and in progress
        self.task_store.transition(parent_task.id, TaskStatus.DECOMPOSED, changed_by=self.worker_id)
        
        # Run all subtasks in parallel
        async def run_subtask(subtask_id: str, index: int) -> Tuple[str, bool, str]:
            """Run a single subtask and return (id, success, error)"""
            subtask = self.task_store.get_task(subtask_id)
            if not subtask:
                return (subtask_id, False, "Task not found")
            
            self.log(f"  🚀 Sub-agent {index+1}: {subtask_id}")
            
            # Create a mini-worker for this subtask
            from core.fractal import FractalDecomposer
            sub_decomposer = FractalDecomposer(self.project)
            sub_decomposer.config.force_level1 = False  # Don't force L1 for subtasks
            
            sub_worker = WiggumWorker(
                worker_id=f"{self.worker_id}-S{index}",  # Unique sub-worker ID (string safe)
                project=self.project,
                task_store=self.task_store,
                adversarial=self.adversarial,
                decomposer=sub_decomposer,
            )
            
            try:
                sub_result = await sub_worker.run_single(subtask)
                return (subtask_id, sub_result.success, sub_result.error)
            except Exception as e:
                return (subtask_id, False, str(e))
        
        # Execute subtasks SEQUENTIALLY (feature → guards → failures)
        # Each concern builds on the code written by the previous one
        successes = 0
        failures = []

        for i, sid in enumerate(subtask_ids):
            aspect = sorted_subtasks[i].get("aspect", "sub")
            self.log(f"  [{i+1}/{len(subtask_ids)}] Running {aspect.upper()} concern...")

            try:
                res = await run_subtask(sid, i)
                sid, success, error = res

                if success:
                    successes += 1
                    self.log(f"  ✅ {sid} ({aspect}): PASSED")
                else:
                    failures.append(f"{sid}: {error}")
                    self.log(f"  ❌ {sid} ({aspect}): {error[:50]}")
                    # Continue to next concern even if this one fails
                    # (guards can still add validation even if feature failed)
            except Exception as e:
                failures.append(f"{sid}: Exception {e}")
                self.log(f"  ❌ {sid} ({aspect}): Exception {e}")
        
        # Parent succeeds only if ALL subtasks succeed
        if successes == len(subtask_ids):
            result.success = True
            result.error = f"All {len(subtask_ids)} sub-agents completed successfully"
            self.task_store.transition(parent_task.id, TaskStatus.CODE_WRITTEN, changed_by=self.worker_id)
            self.log(f"✅ Parent {parent_task.id}: ALL sub-agents passed")
        else:
            result.success = False
            result.error = f"{len(failures)}/{len(subtask_ids)} sub-agents failed: {'; '.join(failures[:3])}"
            self.log(f"❌ Parent {parent_task.id}: {len(failures)} sub-agents failed")
        
        return result

    def _extract_code_changes(self, output: str) -> Dict[str, str]:
        """Extract code changes from opencode output (fallback for non-git)"""
        changes = {}

        # Look for file write patterns
        # Pattern: Writing to file: path/to/file.rs
        # Pattern: Edited file: path/to/file.rs
        # etc.

        import re
        file_patterns = [
            r"(?:Writing to|Edited|Created|Modified)\s+(?:file:?\s+)?([^\s]+\.(rs|ts|tsx|py|js))",
            r"```(\w+)\n// FILE: ([^\n]+)",
        ]

        for pattern in file_patterns:
            matches = re.findall(pattern, output, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    file_path = match[0] if len(match[0]) > 3 else match[1] if len(match) > 1 else ""
                else:
                    file_path = match
                if file_path and len(file_path) > 3:
                    changes[file_path] = "modified"

        return changes

    async def _run_tests(self, domain: str, capture_errors: bool = True) -> Tuple[bool, List[Dict]]:
        """
        Run tests for domain using project CLI.

        Returns:
            Tuple of (success, list of captured error tasks)
        """
        # Use project CLI command
        test_cmd = self.project.get_test_cmd(domain)
        captured_tasks = []

        self.log(f"Running tests: {test_cmd}")

        try:
            rc, stdout, stderr = await run_subprocess(
                test_cmd, timeout=120, cwd=str(self.project.root_path),
                log_fn=self.log,
            )

            if rc == -1:  # timeout
                self.log("Tests timed out - killed process group", "WARN")
                return False, []

            full_output = stdout + "\n" + stderr

            if rc == 0:
                self.log("Tests passed ✓")
                return True, []
            else:
                self.log(f"Tests failed: {stderr[:200]}", "WARN")

                # 🔴 CAPTURE TEST ERRORS FOR FEEDBACK LOOP
                if capture_errors:
                    errors = self.error_capture.parse_e2e_output(full_output, domain)
                    if errors:
                        self.log(f"Captured {len(errors)} test errors for backlog")
                        captured_tasks = self.error_capture.errors_to_tasks(errors)
                        self.error_capture.clear()

                return False, captured_tasks
        except Exception as e:
            self.log(f"Test error: {e}", "ERROR")
            return False, []

    async def _run_build(self, domain: str, capture_errors: bool = True) -> Tuple[bool, List[Dict]]:
        """
        Run build for domain using project CLI (LEAN: verify compilation).

        Returns:
            Tuple of (success, list of captured error tasks)
        """
        build_cmd = self.project.get_build_cmd(domain)
        captured_tasks = []

        self.log(f"Building: {build_cmd}")

        try:
            rc, stdout, stderr = await run_subprocess(
                build_cmd, timeout=300, cwd=str(self.project.root_path),
                log_fn=self.log,
            )

            if rc == -1:  # timeout
                self.log("Build timed out - killed process group", "WARN")
                return False, []

            full_output = stdout + "\n" + stderr

            if rc == 0:
                self.log("Build passed ✓")
                return True, []
            else:
                self.log(f"Build failed: {stderr[:200]}", "WARN")

                # 🔴 CAPTURE BUILD ERRORS FOR FEEDBACK LOOP
                if capture_errors:
                    errors = self.error_capture.parse_build_output(full_output, domain)
                    if errors:
                        self.log(f"Captured {len(errors)} build errors for backlog")
                        captured_tasks = self.error_capture.errors_to_tasks(errors)
                        self.error_capture.clear()

                return False, captured_tasks
        except Exception as e:
            self.log(f"Build error: {e}", "ERROR")
            return False, []

    async def _run_lint(self, domain: str) -> bool:
        """Run lint for domain using project CLI"""
        lint_cmd = self.project.get_lint_cmd(domain)

        self.log(f"Linting: {lint_cmd}")

        try:
            rc, stdout, stderr = await run_subprocess(
                lint_cmd, timeout=120, cwd=str(self.project.root_path),
                log_fn=self.log,
            )

            if rc == -1:  # timeout
                self.log("Lint timed out - killed process group", "WARN")
                return False

            if rc == 0:
                self.log("Lint passed ✓")
                return True
            else:
                self.log(f"Lint failed: {stderr[:200]}", "WARN")
                return False
        except Exception as e:
            self.log(f"Lint error: {e}", "ERROR")
            return False

    async def _run_adversarial(self, code_changes: Dict[str, str]) -> CheckResult:
        """
        Run TEAM OF RIVALS adversarial check (arXiv:2601.14351).

        Cascade: L0 (fast) → L1a (code) → L1b (security) → L2 (arch)
        Multi-vendor: MiniMax, GLM-4.7-free, Opus for cognitive diversity.
        """
        from core.adversarial import CheckResult

        # 0. File protection check (reject protected/forbidden files)
        protection_issues = self.adversarial.check_file_protection(code_changes)
        if protection_issues:
            total_score = sum(i.points for i in protection_issues)
            if total_score >= self.adversarial.threshold:
                feedback = self.adversarial._generate_feedback(protection_issues, {})
                return CheckResult(
                    approved=False,
                    score=total_score,
                    threshold=self.adversarial.threshold,
                    issues=protection_issues,
                    feedback=feedback,
                )

        # Combine changed files for cascade review
        # For large files (>500 lines): use git diff (avoids KISS_FILE_TOO_LARGE on pre-existing code)
        # For small files: full content (gives L2 complete context)
        combined_code = ""
        first_file = ""
        file_type = "code"

        for file_path in list(code_changes.keys())[:5]:  # Limit to 5 files
            full_path = self.project.root_path / file_path
            if not full_path.exists():
                continue

            try:
                full_content = full_path.read_text()
                line_count = full_content.count('\n')

                if line_count > 500:
                    # Large file: use git diff to only review CHANGES (not pre-existing code)
                    import subprocess
                    diff_result = subprocess.run(
                        ["git", "diff", "-U20", "--", file_path],
                        cwd=str(self.project.root_path),
                        capture_output=True, text=True, timeout=10,
                    )
                    diff_text = diff_result.stdout[:30000] if diff_result.stdout else ""
                    if diff_text:
                        combined_code += (
                            f"\n// === FILE: {file_path} (DIFF - {line_count} lines total, showing changes only) ===\n"
                            f"{diff_text}\n"
                        )
                    else:
                        # Fallback: read full file if diff is empty
                        combined_code += f"\n// === FILE: {file_path} ===\n{full_content[:45000]}\n"
                else:
                    # Small file: full content for complete context
                    combined_code += f"\n// === FILE: {file_path} ===\n{full_content[:45000]}\n"

                if not first_file:
                    first_file = file_path
                    file_type = "rust" if file_path.endswith(".rs") else \
                               "typescript" if file_path.endswith((".ts", ".tsx")) else \
                               "python" if file_path.endswith(".py") else \
                               "kotlin" if file_path.endswith(".kt") else \
                               "swift" if file_path.endswith(".swift") else "code"
            except Exception:
                continue

        if not combined_code:
            return CheckResult(approved=True, score=0, threshold=self.adversarial.threshold)

        # TEAM OF RIVALS: Cascaded critics with multi-vendor cognitive diversity
        # L0: Fast deterministic → L1a: Code (MiniMax) → L1b: Security (GLM) → L2: Arch (Opus)
        return await self.adversarial.check_cascade(
            combined_code,
            file_type=file_type,
            filename=first_file,
            timeout=120,
        )

    async def _git_commit(self, task: Task) -> bool:
        """Commit changes to git"""
        try:
            cwd = str(self.project.root_path)
            # Stage all changes
            rc, _, _ = await run_subprocess("git add -A", timeout=60, cwd=cwd, log_fn=self.log)
            if rc != 0:
                self.log("Git add failed", "ERROR")
                return False

            # Commit (use -- to prevent injection via task.description)
            message = f"fix({task.domain}): {task.description[:50]}\n\nTask: {task.id}"
            # Escape double quotes in message for shell safety
            safe_msg = message.replace('"', '\\"')
            rc, _, stderr = await run_subprocess(
                f'git commit -m "{safe_msg}"', timeout=60, cwd=cwd, log_fn=self.log,
            )
            return rc == 0

        except Exception as e:
            self.log(f"Git commit error: {e}", "ERROR")
            return False

    async def _git_reset(self):
        """Reset git changes (revert uncommitted code)"""
        try:
            rc, _, _ = await run_subprocess(
                "git checkout -- . && git clean -fd",
                timeout=60, cwd=str(self.project.root_path), log_fn=self.log,
            )
            self.log("Git reset completed")
        except Exception as e:
            self.log(f"Git reset error: {e}", "WARN")

    def stop(self):
        """Stop the worker"""
        self._running = False

    def _create_feedback_tasks(self, error_tasks: List[Dict], source_task: Task):
        """
        Create feedback tasks in the backlog from captured errors.

        This is the RLM feedback loop:
        Build/Test Error → Capture → Parse → Create Task → Backlog → TDD Worker
        """
        from core.feedback import create_feedback_tasks_from_errors

        create_feedback_tasks_from_errors(
            project_id=self.project.id,
            source_task_id=source_task.id,
            error_tasks=error_tasks,
            task_store=self.task_store,
            log_fn=self.log,
        )


# ============================================================================
# WIGGUM POOL
# ============================================================================

class WiggumPool:
    """
    Pool of Wiggum TDD workers.

    Manages parallel task execution with configurable concurrency.
    """

    def __init__(
        self,
        project_name: str = None,
        workers: int = 3,  # OOM safe (was 50→5→3)
    ):
        """
        Initialize worker pool.

        Args:
            project_name: Project from projects/*.yaml
            workers: Number of parallel workers (default: 5, OOM safe)
        """
        self.project = get_project(project_name)
        self.task_store = TaskStore()
        self.adversarial = AdversarialGate(self.project)
        self.decomposer = FractalDecomposer(self.project)

        self.num_workers = workers
        self.workers: List[WiggumWorker] = []
        self._running = False
        self._semaphore: Optional[asyncio.Semaphore] = None

        log(f"Pool initialized: {workers} workers for {self.project.name}")

    async def run(self):
        """
        Run in daemon mode - continuously process tasks.

        Press Ctrl+C to stop.
        """
        self._running = True
        self._semaphore = asyncio.Semaphore(self.num_workers)

        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._handle_signal)

        log("=" * 60)
        log(f"Starting Wiggum Pool: {self.num_workers} workers")
        log("=" * 60)

        last_cleanup = 0
        CLEANUP_INTERVAL = 300  # 5 minutes

        try:
            while self._running:
                # Periodic cleanup of stuck tasks (every 5 min)
                import time
                now = time.time()
                if now - last_cleanup > CLEANUP_INTERVAL:
                    reset_count = self.task_store.cleanup_stuck_tasks(
                        self.project.id, max_age_minutes=60
                    )
                    if reset_count > 0:
                        log(f"🔄 Cleanup: reset {reset_count} stuck tasks")
                    last_cleanup = now

                # Get pending tasks (excluding problematic files that cause scope pollution)
                exclude_patterns = self.project.raw_config.get("tdd", {}).get("exclude_patterns", [])
                pending = self.task_store.get_pending_tasks(
                    self.project.id, limit=100, exclude_patterns=exclude_patterns
                )

                if not pending:
                    log("No pending tasks, waiting...")
                    await asyncio.sleep(10)
                    continue

                log(f"Found {len(pending)} pending tasks")

                # Process tasks in parallel
                tasks_coros = []
                for task in pending[:self.num_workers]:
                    tasks_coros.append(self._process_task(task))

                if tasks_coros:
                    results = await asyncio.gather(*tasks_coros, return_exceptions=True)
                    success = sum(1 for r in results if isinstance(r, TDDResult) and r.success)
                    log(f"Batch complete: {success}/{len(results)} successful")

                # Brief pause between batches
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            log("Pool cancelled")
        finally:
            self._running = False
            log("Pool stopped")

    async def run_once(self, task_id: str = None) -> Optional[TDDResult]:
        """
        Process a single task.

        Args:
            task_id: Specific task ID, or None to pick next pending

        Returns:
            TDDResult or None
        """
        if task_id:
            task = self.task_store.get_task(task_id)
        else:
            pending = self.task_store.get_pending_tasks(self.project.id, limit=1)
            task = pending[0] if pending else None

        if not task:
            log("No task to process")
            return None

        # AO COMPLIANCE CHECK - Reject SLOP features without REQ-ID
        if task.type == "feature":
            from core.adversarial import check_ao_compliance
            ao_result = check_ao_compliance(task.description or "", task.type, self.project.raw_config, task.id)
            if not ao_result.approved:
                log(f"AO REJECTED: {task.id} - {ao_result.feedback[:60]}", "WARN")
                self.task_store.update_task_status(
                    task.id,
                    TaskStatus.SKIPPED,
                    notes=f"AO compliance failed: {ao_result.feedback}"
                )
                return TDDResult(
                    success=False,
                    task_id=task.id,
                    error=f"AO compliance rejected: {ao_result.feedback}",
                )

        worker = WiggumWorker(
            worker_id=0,
            project=self.project,
            task_store=self.task_store,
            adversarial=self.adversarial,
            decomposer=self.decomposer,
        )

        return await worker.run_single(task)

    async def _process_task(self, task: Task) -> TDDResult:
        """Process a task with semaphore"""
        async with self._semaphore:
            # AO COMPLIANCE CHECK - Reject SLOP features without REQ-ID
            if task.type == "feature":
                from core.adversarial import check_ao_compliance
                ao_result = check_ao_compliance(task.description or "", task.type, self.project.raw_config, task.id)
                if not ao_result.approved:
                    log(f"AO REJECTED: {task.id} - {ao_result.feedback[:60]}", "WARN")
                    self.task_store.update_task_status(
                        task.id,
                        TaskStatus.SKIPPED,
                        notes=f"AO compliance failed: {ao_result.feedback}"
                    )
                    return TDDResult(
                        success=False,
                        task_id=task.id,
                        error=f"AO compliance rejected: {ao_result.feedback}",
                    )

            worker_id = hash(task.id) % self.num_workers
            worker = WiggumWorker(
                worker_id=worker_id,
                project=self.project,
                task_store=self.task_store,
                adversarial=self.adversarial,
                decomposer=self.decomposer,
            )
            return await worker.run_single(task)

    def _handle_signal(self):
        """Handle shutdown signal"""
        log("Received shutdown signal")
        self._running = False

    def get_status(self) -> Dict:
        """Get pool status"""
        tasks = self.task_store.get_tasks_by_project(self.project.id)
        status_counts = {}
        for task in tasks:
            status = task.status
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "project": self.project.name,
            "workers": self.num_workers,
            "running": self._running,
            "total_tasks": len(tasks),
            "by_status": status_counts,
        }


# ============================================================================
# DAEMON
# ============================================================================

class WiggumTDDDaemon(Daemon):
    """
    Wiggum TDD as a system daemon.

    Usage:
        daemon = WiggumTDDDaemon("ppz", workers=3)  # OOM safe
        daemon.start()   # Daemonize and run
        daemon.stop()    # Graceful shutdown
        daemon.status()  # Check status
    """

    def __init__(self, project: str, workers: int = 3):  # OOM safe (was 50→5→3)
        super().__init__(name="wiggum-tdd", project=project)
        self.workers = workers
        self.pool: Optional[WiggumPool] = None

    async def run(self):
        """Main daemon loop"""
        self.log(f"Starting Wiggum TDD daemon with {self.workers} workers")

        self.pool = WiggumPool(self.project, self.workers)
        # Initialize semaphore (normally done in pool.run())
        self.pool._semaphore = asyncio.Semaphore(self.workers)

        try:
            while self.running:
                # Get pending tasks
                pending = self.pool.task_store.get_pending_tasks(
                    self.pool.project.id, limit=100
                )

                if not pending:
                    self.log("No pending tasks, waiting...")
                    await asyncio.sleep(10)
                    continue

                self.log(f"Found {len(pending)} pending tasks")

                # Process tasks in parallel
                tasks_coros = []
                for task in pending[: self.workers]:
                    tasks_coros.append(self.pool._process_task(task))

                if tasks_coros:
                    results = await asyncio.gather(*tasks_coros, return_exceptions=True)
                    success = 0
                    failed = 0
                    errors = []
                    for r in results:
                        if isinstance(r, TDDResult):
                            if r.success:
                                success += 1
                            else:
                                failed += 1
                        elif isinstance(r, Exception):
                            errors.append(str(r)[:100])

                    self.log(f"Batch complete: {success} success, {failed} failed, {len(errors)} errors")
                    if errors:
                        self.log(f"  Errors: {errors[:3]}", "WARN")

                # Brief pause between batches
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            self.log("Daemon cancelled")
        except Exception as e:
            self.log(f"Daemon error: {e}", "ERROR")
        finally:
            self.running = False
            self.log("Daemon stopped")


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Wiggum TDD - Parallel Workers (Daemon)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  start     Start the daemon (background)
  stop      Stop the daemon gracefully
  restart   Restart the daemon
  status    Show daemon status
  run       Run in foreground (no daemonization)
  once      Process single task and exit

Examples:
  wiggum_tdd.py --project ppz start          # Start daemon
  wiggum_tdd.py --project ppz stop           # Stop daemon
  wiggum_tdd.py --project ppz status         # Check status
  wiggum_tdd.py --project ppz run -w 10      # Run foreground
  wiggum_tdd.py --project ppz once           # Single task
        """,
    )
    parser.add_argument("command", nargs="?", default="status",
                        choices=["start", "stop", "restart", "status", "run", "once"],
                        help="Daemon command")
    parser.add_argument("--project", "-p", help="Project name")
    parser.add_argument("--workers", "-w", type=int, default=3, help="Number of workers (OOM safe)")
    parser.add_argument("--task", "-t", help="Specific task ID (for 'once')")
    parser.add_argument("--all", action="store_true", help="Show all projects status")

    args = parser.parse_args()

    # Handle --all status
    if args.all and args.command == "status":
        manager = DaemonManager(args.project or "all")
        print_all_status(manager.status_all())
        return

    # Project required for most commands
    if args.command in ["start", "stop", "restart", "run", "once"] and not args.project:
        print("Error: --project/-p required")
        sys.exit(1)

    if args.command == "status":
        if args.project:
            daemon = WiggumTDDDaemon(args.project, args.workers)
            status = daemon.status()
            print_daemon_status(status)

            # Also show task stats
            pool = WiggumPool(args.project, args.workers)
            pool_status = pool.get_status()
            print(f"\n   Tasks: {pool_status['total_tasks']} total")
            for s, count in pool_status.get("by_status", {}).items():
                print(f"     - {s}: {count}")
        else:
            manager = DaemonManager()
            print_all_status(manager.status_all())

    elif args.command == "start":
        daemon = WiggumTDDDaemon(args.project, args.workers)
        daemon.start(foreground=False)

    elif args.command == "stop":
        daemon = WiggumTDDDaemon(args.project, args.workers)
        daemon.stop()

    elif args.command == "restart":
        daemon = WiggumTDDDaemon(args.project, args.workers)
        daemon.restart()

    elif args.command == "run":
        # Run in foreground (for debugging)
        daemon = WiggumTDDDaemon(args.project, args.workers)
        daemon.start(foreground=True)

    elif args.command == "once":
        pool = WiggumPool(args.project, args.workers)
        result = asyncio.run(pool.run_once(args.task))
        if result:
            icon = "✅" if result.success else "❌"
            print(f"\n{icon} Result: {'SUCCESS' if result.success else 'FAILED'}")
            print(f"   Task: {result.task_id}")
            print(f"   Iterations: {result.iterations}")
            if result.error:
                print(f"   Error: {result.error}")


if __name__ == "__main__":
    main()
