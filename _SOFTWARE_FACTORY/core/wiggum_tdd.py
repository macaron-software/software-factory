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

Uses MiniMax M2.1 via `opencode` for code generation.

Usage:
    from core.wiggum_tdd import WiggumPool

    pool = WiggumPool("ppz", workers=50)
    await pool.run()  # Daemon mode
    await pool.run_once()  # Single task
"""

import asyncio
import json
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
from core.llm_client import run_opencode
from core.error_capture import ErrorCapture, ErrorType, ErrorSeverity
from core.daemon import Daemon, DaemonManager, print_daemon_status, print_all_status


def log(msg: str, level: str = "INFO", worker_id: int = None):
    """Log with timestamp and optional worker ID"""
    ts = datetime.now().strftime("%H:%M:%S")
    prefix = f"W{worker_id}" if worker_id is not None else "POOL"
    print(f"[{ts}] [{prefix}] [{level}] {msg}", flush=True)


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
    OPENCODE_TIMEOUT = 600  # 10 min per iteration

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

    async def run_single(self, task: Task) -> TDDResult:
        """Run TDD cycle for a single task"""
        result = TDDResult(success=False, task_id=task.id)

        self.log(f"Starting task: {task.id}")
        self.log(f"Description: {task.description[:80]}...")

        try:
            # 1. Check FRACTAL - decompose if needed (FORCED at depth 0)
            task_dict = task.to_dict()
            current_depth = task_dict.get("fractal_depth", 0)
            
            should_split, analysis = self.decomposer.should_decompose(task_dict, current_depth)
            
            if should_split:
                force_l1 = getattr(analysis, 'force_level1', False)
                self.log(f"Decomposing task (force_L1={force_l1}, {analysis.reason})...")
                
                subtasks = await self.decomposer.decompose(task_dict, current_depth)
                
                if len(subtasks) > 1:
                    # Check if we should run subtasks in parallel (L1 with parallel_subagents)
                    if force_l1 and self.decomposer.config.parallel_subagents:
                        self.log(f"🔀 Running {len(subtasks)} sub-agents in PARALLEL...")
                        result = await self._run_parallel_subtasks(task, subtasks)
                        return result
                    else:
                        # Standard: Create subtasks in store for pool workers
                        for st in subtasks:
                            self.task_store.create_task(
                                project_id=self.project.id,
                                task_type=st.get("type", task.type),
                                domain=st.get("domain", task.domain),
                                description=st.get("description", ""),
                                files=st.get("files", []),
                                context=st,
                                parent_id=task.id,
                            )
                        # Mark parent as decomposed
                        self.task_store.transition(task.id, TaskStatus.DECOMPOSED)
                        result.success = True
                        result.error = f"Decomposed into {len(subtasks)} subtasks"
                        return result

            # 2. Lock task and transition to TDD in progress
            # PENDING → LOCKED → TDD_IN_PROGRESS (per VALID_TRANSITIONS)
            if not self.task_store.transition(task.id, TaskStatus.LOCKED, changed_by=self.worker_id):
                self.log("Failed to lock task, may be taken by another worker", "WARN")
                return result
            self.task_store.transition(task.id, TaskStatus.TDD_IN_PROGRESS, changed_by=self.worker_id)

            # 3. TDD iterations - loop until validation (RLM pattern)
            feedback = ""  # Accumulated feedback from adversarial
            for iteration in range(self.MAX_ITERATIONS):
                result.iterations = iteration + 1
                self.log(f"Iteration {iteration + 1}/{self.MAX_ITERATIONS}")

                # Reload task to get latest context (including feedback)
                task = self.task_store.get_task(task.id) or task

                # Build TDD prompt with feedback
                prompt = self._build_tdd_prompt(task, iteration, feedback)

                # Capture git status before running opencode
                git_before = self._get_git_status()

                # Run opencode with MCP LRM access
                returncode, output = await run_opencode(
                    prompt,
                    model="minimax/MiniMax-M2.1",
                    cwd=str(self.project.root_path),
                    timeout=self.OPENCODE_TIMEOUT,
                    project=self.project.name,  # Pass project for MCP LRM tools
                )

                if returncode != 0:
                    self.log(f"opencode failed: {output[:200]}", "WARN")
                    continue

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

                result.code_written = True

                # 4. LEAN: Verify compilation first
                build_success, build_error_tasks = await self._run_build(task.domain)
                if not build_success:
                    self.log("Build failed, retrying...", "WARN")
                    # 🔴 CREATE FEEDBACK TASKS FROM BUILD ERRORS
                    if build_error_tasks:
                        self._create_feedback_tasks(build_error_tasks, task)
                    continue

                # 4.5. Run lint
                lint_result = await self._run_lint(task.domain)
                if not lint_result:
                    self.log("Lint failed, retrying...", "WARN")
                    continue

                # 5. Run tests
                test_success, test_error_tasks = await self._run_tests(task.domain)
                if test_success:
                    result.test_passed = True

                    # 5.5. Transition to TDD_SUCCESS (tests passed)
                    self.task_store.transition(task.id, TaskStatus.TDD_SUCCESS)

                    # 5. Adversarial check
                    adv_result = self._run_adversarial(code_changes)
                    if adv_result.approved:
                        result.adversarial_passed = True

                        # 6. Commit
                        commit_success = await self._git_commit(task)
                        if commit_success:
                            result.committed = True
                            result.success = True

                            # Transition: TDD_SUCCESS → MERGED (adversarial passed + committed)
                            self.task_store.transition(task.id, TaskStatus.MERGED)

                            # Check if deploy is enabled
                            deploy_strategy = self.project.deploy.get("strategy", "validation-only")
                            if deploy_strategy != "validation-only":
                                # Queue for deployment
                                self.task_store.transition(task.id, TaskStatus.QUEUED_FOR_DEPLOY)
                                self.log("✅ Task completed, queued for deploy")
                            else:
                                # No deploy, mark as completed
                                self.task_store.transition(task.id, TaskStatus.COMPLETED)
                                self.log("✅ Task completed successfully")
                            return result
                    else:
                        self.log(f"Adversarial rejected: {adv_result.feedback[:100]}", "WARN")
                        # Transition: TDD_SUCCESS → ADVERSARIAL_REJECTED
                        self.task_store.transition(task.id, TaskStatus.ADVERSARIAL_REJECTED)
                        # Accumulate feedback for next iteration (RLM loop pattern)
                        feedback = f"ADVERSARIAL REJECTED (iteration {iteration + 1}):\n{adv_result.feedback}\n\nFix these issues and try again."
                        # Transition back to TDD_IN_PROGRESS for retry
                        self.task_store.transition(task.id, TaskStatus.TDD_IN_PROGRESS)
                        # Continue loop - don't break!
                else:
                    self.log("Tests failed", "WARN")
                    # 🔴 CREATE FEEDBACK TASKS FROM TEST ERRORS
                    if test_error_tasks:
                        self._create_feedback_tasks(test_error_tasks, task)

            # Max iterations reached
            result.error = "Max iterations reached"
            self.task_store.transition(task.id, TaskStatus.TDD_FAILED)
            self.log("❌ Task failed after max iterations", "WARN")

        except Exception as e:
            result.error = str(e)
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

        prompt = f"""You are a TDD agent. Complete this task using strict TDD.

PROJECT: {self.project.name} ({self.project.display_name})
ROOT: {self.project.root_path}

TASK: {task.description}
DOMAIN: {task.domain}
FILES: {task.files}

CONTEXT:
{json.dumps(context, indent=2)[:3000]}
{feedback_section}
MCP TOOLS AVAILABLE (use these to explore the project):
- lrm_locate(query, scope, limit): Find files matching pattern
- lrm_summarize(files, goal): Get file summaries
- lrm_conventions(domain): Get coding conventions for this domain
- lrm_examples(type, domain): Get example tests/code
- lrm_build(domain, command): Run build/test/lint commands

TDD CYCLE:
1. Use lrm_locate and lrm_summarize to understand the codebase context
2. Use lrm_conventions to follow project patterns
3. RED: Write a failing test that verifies the fix
4. GREEN: Write minimal code to make the test pass
5. VERIFY: The test must pass

RULES:
- NO test.skip, @ts-ignore, or #[ignore]
- NO .unwrap() abuse (max 3 per file)
- NO TODO/FIXME in committed code
- Complete, working code only

Start by exploring the relevant files with lrm_locate, then execute the TDD cycle.
"""
        return prompt

    def _get_git_status(self) -> set:
        """Get set of modified files from git"""
        import subprocess
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
                    if parts:
                        files.add(parts)
            return files
        except Exception:
            return set()

    def _detect_git_changes(self, before: set) -> Dict[str, str]:
        """Detect file changes by comparing git status before and after"""
        after = self._get_git_status()
        new_changes = after - before

        changes = {}
        for f in new_changes:
            changes[f] = "modified"

        # Also check for modifications in existing files
        import subprocess
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only"],
                cwd=str(self.project.root_path),
                capture_output=True,
                text=True,
                timeout=10
            )
            for f in result.stdout.strip().split("\n"):
                if f.strip():
                    changes[f.strip()] = "modified"
        except Exception:
            pass

        return changes

    async def _run_parallel_subtasks(self, parent_task: Task, subtasks: List[Dict]) -> TDDResult:
        """
        Run subtasks in parallel using sub-agents.
        
        Each subtask is executed concurrently. Parent task is marked DONE
        only if ALL subtasks succeed.
        
        Args:
            parent_task: The parent task being decomposed
            subtasks: List of subtask dicts from FRACTAL decomposition
            
        Returns:
            TDDResult with success=True if all subtasks passed
        """
        result = TDDResult(success=False, task_id=parent_task.id)
        
        self.log(f"🔀 Launching {len(subtasks)} parallel sub-agents...")
        
        # Create subtasks in store first
        subtask_ids = []
        for st in subtasks:
            created = self.task_store.create_task(
                project_id=self.project.id,
                task_type=st.get("type", parent_task.type),
                domain=st.get("domain", parent_task.domain),
                description=st.get("description", ""),
                files=st.get("files", []),
                context=st,
                parent_id=parent_task.id,
            )
            if created:
                subtask_ids.append(created.id)
                self.log(f"  Created subtask: {created.id} ({st.get('aspect', 'sub')})")
        
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
                worker_id=self.worker_id * 100 + index,  # Unique sub-worker ID
                project=self.project,
                task_store=self.task_store,
                adversarial=self.adversarial,
                decomposer=sub_decomposer,
            )
            
            try:
                sub_result = await sub_worker.run_cycle(subtask)
                return (subtask_id, sub_result.success, sub_result.error)
            except Exception as e:
                return (subtask_id, False, str(e))
        
        # Execute all subtasks concurrently
        tasks = [
            run_subtask(sid, i) 
            for i, sid in enumerate(subtask_ids)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Aggregate results
        successes = 0
        failures = []
        
        for res in results:
            if isinstance(res, Exception):
                failures.append(f"Exception: {res}")
            else:
                sid, success, error = res
                if success:
                    successes += 1
                    self.log(f"  ✅ {sid}: PASSED")
                else:
                    failures.append(f"{sid}: {error}")
                    self.log(f"  ❌ {sid}: {error[:50]}")
        
        # Parent succeeds only if ALL subtasks succeed
        if successes == len(subtask_ids):
            result.success = True
            result.error = f"All {len(subtask_ids)} sub-agents completed successfully"
            self.task_store.transition(parent_task.id, TaskStatus.DONE, changed_by=self.worker_id)
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
            proc = await asyncio.create_subprocess_shell(
                test_cmd,
                cwd=str(self.project.root_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)

            # Combine output for error parsing
            full_output = stdout.decode() + "\n" + stderr.decode()

            if proc.returncode == 0:
                self.log("Tests passed ✓")
                return True, []
            else:
                self.log(f"Tests failed: {stderr.decode()[:200]}", "WARN")

                # 🔴 CAPTURE TEST ERRORS FOR FEEDBACK LOOP
                if capture_errors:
                    # Parse both E2E errors and console errors
                    errors = self.error_capture.parse_e2e_output(full_output, domain)
                    if errors:
                        self.log(f"Captured {len(errors)} test errors for backlog")
                        captured_tasks = self.error_capture.errors_to_tasks(errors)
                        self.error_capture.clear()

                return False, captured_tasks

        except asyncio.TimeoutError:
            self.log("Tests timed out", "WARN")
            return False, []
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
            proc = await asyncio.create_subprocess_shell(
                build_cmd,
                cwd=str(self.project.root_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)

            # Combine stdout and stderr for error parsing
            full_output = stdout.decode() + "\n" + stderr.decode()

            if proc.returncode == 0:
                self.log("Build passed ✓")
                return True, []
            else:
                self.log(f"Build failed: {stderr.decode()[:200]}", "WARN")

                # 🔴 CAPTURE BUILD ERRORS FOR FEEDBACK LOOP
                if capture_errors:
                    errors = self.error_capture.parse_build_output(full_output, domain)
                    if errors:
                        self.log(f"Captured {len(errors)} build errors for backlog")
                        captured_tasks = self.error_capture.errors_to_tasks(errors)
                        self.error_capture.clear()  # Clear for next run

                return False, captured_tasks

        except asyncio.TimeoutError:
            self.log("Build timed out", "WARN")
            return False, []
        except Exception as e:
            self.log(f"Build error: {e}", "ERROR")
            return False, []

    async def _run_lint(self, domain: str) -> bool:
        """Run lint for domain using project CLI"""
        lint_cmd = self.project.get_lint_cmd(domain)

        self.log(f"Linting: {lint_cmd}")

        try:
            proc = await asyncio.create_subprocess_shell(
                lint_cmd,
                cwd=str(self.project.root_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)

            if proc.returncode == 0:
                self.log("Lint passed ✓")
                return True
            else:
                self.log(f"Lint failed: {stderr.decode()[:200]}", "WARN")
                return False

        except asyncio.TimeoutError:
            self.log("Lint timed out", "WARN")
            return False
        except Exception as e:
            self.log(f"Lint error: {e}", "ERROR")
            return False

    def _run_adversarial(self, code_changes: Dict[str, str]) -> CheckResult:
        """Run adversarial check on changed files"""
        all_code = ""

        for file_path in code_changes.keys():
            full_path = self.project.root_path / file_path
            if full_path.exists():
                try:
                    all_code += f"\n// FILE: {file_path}\n"
                    all_code += full_path.read_text()[:5000]
                except Exception:
                    pass

        if not all_code:
            # No code to check = pass
            return CheckResult(approved=True, score=0, threshold=self.adversarial.threshold)

        return self.adversarial.check_code(all_code)

    async def _git_commit(self, task: Task) -> bool:
        """Commit changes to git"""
        try:
            # Stage all changes
            proc = await asyncio.create_subprocess_shell(
                "git add -A",
                cwd=str(self.project.root_path),
            )
            await proc.wait()

            # Commit
            message = f"fix({task.domain}): {task.description[:50]}\n\nTask: {task.id}"
            proc = await asyncio.create_subprocess_shell(
                f'git commit -m "{message}"',
                cwd=str(self.project.root_path),
            )
            await proc.wait()

            return proc.returncode == 0

        except Exception as e:
            self.log(f"Git commit error: {e}", "ERROR")
            return False

    def stop(self):
        """Stop the worker"""
        self._running = False

    def _create_feedback_tasks(self, error_tasks: List[Dict], source_task: Task):
        """
        Create feedback tasks in the backlog from captured errors.

        This is the RLM feedback loop:
        Build/Test Error → Capture → Parse → Create Task → Backlog → TDD Worker

        Args:
            error_tasks: List of task dicts from ErrorCapture.errors_to_tasks()
            source_task: The task that triggered these errors
        """
        created_count = 0

        for task_dict in error_tasks:
            try:
                # Add source task reference
                task_dict["context"]["source_task_id"] = source_task.id
                task_dict["context"]["feedback_loop"] = True

                # Check for duplicates (same error already in backlog)
                error_id = task_dict["context"].get("error_id", "")
                if error_id:
                    existing = self.task_store.find_task_by_error_id(
                        self.project.id,
                        error_id
                    )
                    if existing:
                        self.log(f"Skipping duplicate error task: {error_id}", "DEBUG")
                        continue

                # Create the task
                new_task_id = self.task_store.create_task(
                    project_id=self.project.id,
                    task_type=task_dict.get("type", "fix"),
                    domain=task_dict.get("domain", source_task.domain),
                    description=task_dict.get("description", "Fix captured error"),
                    files=task_dict.get("files", []),
                    context=task_dict.get("context", {}),
                    wsjf_score=task_dict.get("wsjf_score", 5.0),
                )

                self.log(f"Created feedback task: {new_task_id} ({task_dict.get('description', '')[:40]}...)")
                created_count += 1

            except Exception as e:
                self.log(f"Failed to create feedback task: {e}", "ERROR")

        if created_count > 0:
            self.log(f"🔄 Created {created_count} feedback tasks from errors (RLM loop)")


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
        workers: int = 50,
    ):
        """
        Initialize worker pool.

        Args:
            project_name: Project from projects/*.yaml
            workers: Number of parallel workers (default: 50)
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

        try:
            while self._running:
                # Get pending tasks
                pending = self.task_store.get_pending_tasks(self.project.id, limit=100)

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
        daemon = WiggumTDDDaemon("ppz", workers=50)
        daemon.start()   # Daemonize and run
        daemon.stop()    # Graceful shutdown
        daemon.status()  # Check status
    """

    def __init__(self, project: str, workers: int = 50):
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
    parser.add_argument("--workers", "-w", type=int, default=50, help="Number of workers")
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
