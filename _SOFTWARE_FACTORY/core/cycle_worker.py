"""
Cycle Worker - Phased Development Pipeline

PHASE 1: TDD MASSIF
- N workers write code in parallel
- No builds during this phase
- Ends when: batch_size tasks CODE_WRITTEN or timeout

PHASE 2: BUILD
- Compile ALL CODE_WRITTEN tasks
- If errors → create feedback tasks → back to PHASE 1
- If OK → PHASE 3

PHASE 3: DEPLOY
- Staging → E2E → Prod
- If errors → rollback + feedback → PHASE 1
- If OK → back to PHASE 1 for next batch
"""

import asyncio
import os
import signal
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from core.daemon import Daemon
from core.task_store import TaskStore, TaskStatus
from core.project_registry import ProjectConfig
from core.subprocess_util import run_subprocess
from core.error_patterns import classify_error, is_infra


class CyclePhase(Enum):
    TDD = "tdd"
    BUILD = "build"
    DEPLOY = "deploy"
    IDLE = "idle"


@dataclass
class CycleConfig:
    """Configuration for development cycle"""
    # Phase 1: TDD
    tdd_workers: int = 3  # OOM safe (was 5)
    tdd_batch_size: int = 10  # Tasks to complete before build
    tdd_timeout_minutes: int = 30  # Max time in TDD phase

    # Phase 2: Build
    build_timeout_minutes: int = 15
    max_build_retries: int = 2

    # Phase 3: Deploy
    deploy_timeout_minutes: int = 20
    skip_deploy: bool = False  # For testing

    # Auto-cleanup: Reset stuck tasks
    stuck_task_hours: float = 1.0  # Hours before a task is considered stuck

    # Auto-Brain: Trigger Brain when backlog empty
    auto_brain: bool = True  # Auto-run Brain analysis when pending=0
    auto_brain_cooldown_minutes: int = 10  # Min time between auto Brain runs


@dataclass
class CycleState:
    """Current state of the cycle"""
    phase: CyclePhase = CyclePhase.IDLE
    phase_start: Optional[datetime] = None
    cycle_count: int = 0

    # Phase 1 stats
    tdd_started: int = 0
    tdd_completed: int = 0

    # Phase 2 stats
    build_attempted: int = 0
    build_success: int = 0
    build_failed: int = 0

    # Phase 3 stats
    deploy_attempted: int = 0
    commit_success: int = 0

    # Auto-Brain tracking
    last_brain_run: Optional[datetime] = None


class CycleWorker:
    """
    Orchestrates phased development cycles.

    Instead of running TDD/Build/Deploy continuously in parallel,
    this runs them in sequential phases:

    1. TDD Phase: Workers write code until batch is ready
    2. Build Phase: Compile all written code
    3. Deploy Phase: If build OK, deploy to staging/prod
    """

    def __init__(self, project: ProjectConfig, config: CycleConfig = None, daemon: "CycleDaemon" = None):
        self.project = project
        self.config = config or CycleConfig()
        self.task_store = TaskStore()
        self.state = CycleState()
        self.daemon = daemon  # Reference to parent daemon for running check

        # TDD workers (spawned during Phase 1)
        self.tdd_workers: List[asyncio.Task] = []
        self.tdd_worker_stop = asyncio.Event()

    @property
    def running(self) -> bool:
        return self.daemon.running if self.daemon else True

    def log(self, msg: str, level: str = "INFO"):
        if self.daemon:
            self.daemon.log(msg, level)

    async def run(self):
        """Main cycle loop"""
        self.log(f"Starting Cycle Worker for {self.project.name}")
        self.log(f"Config: batch={self.config.tdd_batch_size}, workers={self.config.tdd_workers}")

        # Start orphan cleanup watchdog (runs in background)
        from core.daemon import start_watchdog_daemon
        try:
            start_watchdog_daemon(interval=300, min_age=600)  # 5min interval, kill if >10min old
            self.log("[WATCHDOG] Orphan cleanup watchdog started")
        except Exception as e:
            self.log(f"[WATCHDOG] Failed to start: {e}", "WARN")

        while self.running:
            try:
                self.state.cycle_count += 1
                self.log(f"=== CYCLE {self.state.cycle_count} ===")

                # AUTO-CLEANUP: Reset tasks stuck for >1h (crash/timeout recovery)
                stuck_reset = self.task_store.reset_stuck_tasks(
                    self.project.id, stuck_hours=self.config.stuck_task_hours
                )
                if stuck_reset > 0:
                    self.log(f"Auto-cleanup: reset {stuck_reset} stuck tasks to pending")

                # PHASE 0: Check for orphaned COMMIT_QUEUED tasks (from previous cycles)
                commit_queued = self.task_store.get_tasks_by_status(
                    self.project.id, TaskStatus.COMMIT_QUEUED, limit=100
                )
                if commit_queued and not self.config.skip_deploy:
                    self.log(f"Found {len(commit_queued)} orphaned COMMIT_QUEUED tasks, deploying first...")
                    await self._phase_deploy()

                # Check if there are pending tasks OR active work (decomposed, in-progress)
                pending = self.task_store.get_tasks_by_status(
                    self.project.id, TaskStatus.PENDING, limit=1
                )
                decomposed = self.task_store.get_tasks_by_status(
                    self.project.id, TaskStatus.DECOMPOSED, limit=1
                ) if hasattr(TaskStatus, 'DECOMPOSED') else []
                tdd_active = self.task_store.get_tasks_by_status(
                    self.project.id, TaskStatus.TDD_IN_PROGRESS, limit=1
                )
                integration_active = self.task_store.get_tasks_by_status(
                    self.project.id, TaskStatus.INTEGRATION_IN_PROGRESS, limit=1
                )

                if not pending and not decomposed and not tdd_active and not integration_active:
                    # Backlog truly empty — auto-brain
                    if self.config.auto_brain:
                        await self._auto_brain_if_needed()
                    else:
                        self.log("No pending tasks, waiting...")
                        await asyncio.sleep(60)
                    continue
                elif not pending:
                    # Tasks still being processed (decomposed/in-progress), wait
                    active_count = len(decomposed) + len(tdd_active) + len(integration_active)
                    self.log(f"No pending tasks but {active_count}+ still in progress, waiting...")
                    await asyncio.sleep(30)
                    continue

                # PHASE 0.5: INTEGRATION (cross-layer wiring, before TDD)
                await self._phase_integration()

                # PHASE 1: TDD Massif
                await self._phase_tdd()

                # Check if we have code to build
                code_written = self.task_store.get_tasks_by_status(
                    self.project.id, TaskStatus.CODE_WRITTEN, limit=100
                )
                if not code_written:
                    self.log("No CODE_WRITTEN tasks, skipping build phase")
                    continue

                # PHASE 2: Build
                build_ok = await self._phase_build()

                if not build_ok:
                    self.log("Build failed, returning to TDD phase")
                    continue

                # PHASE 3: Deploy (if enabled)
                if not self.config.skip_deploy:
                    await self._phase_deploy()
                else:
                    self.log("Deploy skipped (config)")

                self.log(f"=== CYCLE {self.state.cycle_count} COMPLETE ===")

            except Exception as e:
                self.log(f"Cycle error: {e}", "ERROR")
                await asyncio.sleep(30)

    async def _phase_integration(self):
        """Phase 0.5: Integration - Wire layers together before TDD"""
        # Check for pending integration tasks
        from core.task_store import TaskStatus
        integration_tasks = [
            t for t in self.task_store.get_tasks_by_status(
                self.project.id, TaskStatus.PENDING, limit=50
            ) if t.type == "integration"
        ]

        if not integration_tasks:
            return  # No integration work needed

        self.log(f"[PHASE 0.5] INTEGRATION - {len(integration_tasks)} tasks pending")

        from core.integrator_worker import IntegratorWorker
        from core.adversarial import AdversarialGate

        adversarial = AdversarialGate(self.project)
        integrator = IntegratorWorker(self.project, self.task_store, adversarial)

        # Run integration tasks sequentially (order matters: bootstrap → migration → api)
        completed = await integrator.run_pending()
        self.log(f"[PHASE 0.5] Integration complete: {completed}/{len(integration_tasks)} tasks done")

    async def _phase_tdd(self):
        """Phase 1: TDD Massif - Run workers until batch ready"""
        self.state.phase = CyclePhase.TDD
        self.state.phase_start = datetime.now()
        self.state.tdd_started = 0
        self.state.tdd_completed = 0

        self.log(f"[PHASE 1] TDD Massif - {self.config.tdd_workers} workers, batch={self.config.tdd_batch_size}")

        # Reset stop event
        self.tdd_worker_stop.clear()

        # Spawn TDD workers
        from core.wiggum_tdd import WiggumWorker
        from core.adversarial import AdversarialGate
        from core.fractal import FractalDecomposer

        # Create shared adversarial gate and decomposer
        adversarial = AdversarialGate(self.project)
        decomposer = FractalDecomposer(self.project)

        workers = []
        for i in range(self.config.tdd_workers):
            worker = WiggumWorker(
                worker_id=f"C{self.state.cycle_count}-W{i}",
                project=self.project,
                task_store=self.task_store,
                adversarial=adversarial,
                decomposer=decomposer,
            )
            task = asyncio.create_task(self._run_tdd_worker(worker, i))
            workers.append(task)

        # Wait for batch completion or timeout
        timeout = self.config.tdd_timeout_minutes * 60
        start = time.time()

        while time.time() - start < timeout:
            # Count CODE_WRITTEN tasks
            code_written = self.task_store.get_tasks_by_status(
                self.project.id, TaskStatus.CODE_WRITTEN, limit=self.config.tdd_batch_size + 1
            )

            if len(code_written) >= self.config.tdd_batch_size:
                self.log(f"Batch ready: {len(code_written)} tasks CODE_WRITTEN")
                break

            # Check for TDD failures too many
            tdd_in_progress = self.task_store.get_tasks_by_status(
                self.project.id, TaskStatus.TDD_IN_PROGRESS, limit=1
            )

            elapsed = int(time.time() - start)
            self.log(f"TDD progress: {len(code_written)}/{self.config.tdd_batch_size} ready, {elapsed}s elapsed")

            await asyncio.sleep(30)

        # Stop workers
        self.log("Stopping TDD workers...")
        self.tdd_worker_stop.set()

        # Wait for workers to finish current task
        await asyncio.gather(*workers, return_exceptions=True)

        self.log(f"[PHASE 1] Complete: {self.state.tdd_completed} tasks written")

    async def _run_tdd_worker(self, worker, worker_idx: int):
        """Run a single TDD worker until stop signal"""
        while not self.tdd_worker_stop.is_set():
            try:
                # Get next pending task
                tasks = self.task_store.get_tasks_by_status(
                    self.project.id, TaskStatus.PENDING, limit=1
                )

                if not tasks:
                    await asyncio.sleep(5)
                    continue

                task = tasks[0]

                # AO COMPLIANCE CHECK - Reject SLOP features without REQ-ID
                if task.type == "feature":
                    from core.adversarial import check_ao_compliance
                    ao_result = check_ao_compliance(task.description or "", task.type, self.project.raw_config, task.id)
                    if not ao_result.approved:
                        self.log(f"[W{worker_idx}] AO REJECTED: {task.id} - {ao_result.feedback[:60]}", "WARN")
                        self.task_store.update_task_status(
                            task.id,
                            TaskStatus.SKIPPED,
                            notes=f"AO compliance failed: {ao_result.feedback}"
                        )
                        continue

                self.state.tdd_started += 1

                # Process task
                result = await worker.run_single(task)

                if result.success:
                    self.state.tdd_completed += 1
                    self.log(f"[W{worker_idx}] Completed: {task.id}")
                else:
                    self.log(f"[W{worker_idx}] Failed: {task.id} - {result.error[:50] if result.error else 'unknown'}")

            except Exception as e:
                self.log(f"[W{worker_idx}] Error: {e}", "ERROR")
                await asyncio.sleep(5)

    async def _phase_build(self) -> bool:
        """Phase 2: Build - Compile all CODE_WRITTEN tasks"""
        self.state.phase = CyclePhase.BUILD
        self.state.phase_start = datetime.now()
        self.state.build_attempted = 0
        self.state.build_success = 0
        self.state.build_failed = 0

        self.log("[PHASE 2] Build - Compiling all CODE_WRITTEN tasks")

        # Get all CODE_WRITTEN tasks
        tasks = self.task_store.get_tasks_by_status(
            self.project.id, TaskStatus.CODE_WRITTEN, limit=100
        )

        if not tasks:
            self.log("No tasks to build")
            return True

        self.log(f"Building {len(tasks)} tasks...")

        # Group by domain for parallel builds
        from core.build_worker import BuildWorker

        tasks_by_domain: Dict[str, List] = {}
        for task in tasks:
            domain = task.domain
            if domain not in tasks_by_domain:
                tasks_by_domain[domain] = []
            tasks_by_domain[domain].append(task)

        # Build each domain (1 at a time per domain, domains in parallel)
        build_tasks = []
        for domain, domain_tasks in tasks_by_domain.items():
            build_tasks.append(self._build_domain(domain, domain_tasks))

        results = await asyncio.gather(*build_tasks, return_exceptions=True)

        # Count results
        all_success = True
        for result in results:
            if isinstance(result, Exception):
                self.log(f"Build exception: {result}", "ERROR")
                all_success = False
            elif not result:
                all_success = False

        self.log(f"[PHASE 2] Complete: {self.state.build_success} success, {self.state.build_failed} failed")

        return all_success

    async def _build_domain(self, domain: str, tasks: List) -> bool:
        """Build all tasks for a domain via global queue (if enabled) or direct"""
        self.log(f"Building domain {domain}: {len(tasks)} tasks")

        # Use get_build_cmd/get_test_cmd which respects CLI priority over legacy domain config
        build_cmd = self.project.get_build_cmd(domain)
        test_cmd = self.project.get_test_cmd(domain)

        # Check if global queue is enabled (default: True)
        raw_config = getattr(self.project, 'raw_config', None) or {}
        use_queue = raw_config.get("build_queue", {}).get("enabled", True)

        # Run build command
        if use_queue:
            await self._ensure_queue_daemon()
            success, error = await self._run_via_queue(build_cmd, f"build-{domain}")
        else:
            success, error = await self._run_direct(build_cmd)

        if not success:
            self.log(f"Build failed for {domain}: {error[:200] if error else 'unknown'}", "ERROR")

            # Mark tasks as BUILD_FAILED
            for task in tasks:
                self.state.build_attempted += 1
                self.state.build_failed += 1
                try:
                    self.task_store.transition(task.id, TaskStatus.BUILD_FAILED)
                except:
                    pass

            # Create feedback tasks
            self._create_build_feedback(domain, error, tasks)
            return False

        # Run tests if configured
        if test_cmd:
            if use_queue:
                success, error = await self._run_via_queue(test_cmd, f"test-{domain}")
            else:
                success, error = await self._run_direct(test_cmd)

            if not success:
                self.log(f"Tests failed for {domain}: {error[:200] if error else 'unknown'}", "ERROR")

                for task in tasks:
                    self.state.build_attempted += 1
                    self.state.build_failed += 1
                    try:
                        self.task_store.transition(task.id, TaskStatus.BUILD_FAILED)
                    except:
                        pass

                self._create_build_feedback(domain, error, tasks)
                return False

        # Success - transition to COMMIT_QUEUED
        for task in tasks:
            self.state.build_attempted += 1
            self.state.build_success += 1
            try:
                self.task_store.transition(task.id, TaskStatus.COMMIT_QUEUED)
            except Exception as e:
                self.log(f"Transition error: {e}", "WARN")

        self.log(f"Build success for {domain}: {len(tasks)} tasks")
        return True

    async def _ensure_queue_daemon(self):
        """Auto-start queue daemon if not running (via subprocess to avoid fork issues)"""
        from core.build_queue import QueueDaemon
        import subprocess
        daemon = QueueDaemon()
        status = daemon.status()
        if not status.get("running"):
            self.log("Auto-starting queue daemon via subprocess...")
            # Start daemon in separate process to avoid fork/async conflicts
            subprocess.Popen(
                ["python3", "cli/factory.py", "queue", "start"],
                cwd=str(Path(__file__).parent.parent),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            await asyncio.sleep(2)  # Give daemon time to start

    async def _run_via_queue(self, cmd: str, job_type: str) -> tuple:
        """Run command via global build queue"""
        from core.build_queue import GlobalBuildQueue, JobStatus

        queue = GlobalBuildQueue.instance()
        raw_config = getattr(self.project, 'raw_config', None) or {}
        priority = raw_config.get("build_queue", {}).get("priority", 10)
        timeout = raw_config.get("build_queue", {}).get("timeout", 300)

        self.log(f"Queueing {job_type}: {cmd[:50]}... (priority={priority})")
        job_id = queue.enqueue(
            project=self.project.name,
            cmd=cmd,
            cwd=str(self.project.root_path),
            priority=priority,
            timeout=timeout,
        )

        # Wait for completion
        job = await queue.wait_for(job_id)

        if job.status == JobStatus.SUCCESS:
            return True, ""
        elif job.status == JobStatus.TIMEOUT:
            return False, f"Queue timeout ({timeout}s)"
        else:
            return False, job.stderr or job.stdout or job.error or "Unknown error"

    async def _run_direct(self, cmd: str) -> tuple:
        """Run command directly (bypass queue)"""
        env = os.environ.copy()
        project_env = self.project.get_env()
        if project_env:
            env.update(project_env)

        rc, stdout, stderr = await run_subprocess(
            f"cd {self.project.root_path} && {cmd}",
            timeout=300, env=env, log_fn=self.log,
        )

        if rc == -1:  # timeout
            return False, "Command timeout (300s)"
        if rc == 0:
            return True, ""
        return False, stderr[:500] if stderr else "Command failed"

    def _create_build_feedback(self, domain: str, error: str, tasks: List):
        """Create feedback tasks from build errors - ONLY for code errors, NOT infra/CI/CD"""
        from core.feedback import create_feedback_task

        task_id = create_feedback_task(
            project_id=self.project.id,
            source_task_id=tasks[0].id if tasks else "unknown",
            error_text=error,
            stage="build",
            task_store=self.task_store,
            domain=domain,
            files=[t.files[0] if t.files else "" for t in tasks[:5]],
            related_task_ids=[t.id for t in tasks],
            log_fn=self.log,
        )

    def _check_deploy_daemon_alive(self) -> bool:
        """Check if the deploy daemon is running. Alert if dead."""
        from pathlib import Path
        pid_dir = Path("/tmp/factory")
        pidfile = pid_dir / f"wiggum-deploy-{self.project.id}.pid"

        if not pidfile.exists():
            self.log("DEPLOY DAEMON NOT RUNNING: no PID file", "ERROR")
            self._try_restart_deploy_daemon()
            return False

        try:
            pid = int(pidfile.read_text().strip())
            os.kill(pid, 0)  # Check if alive
            return True
        except (OSError, ValueError):
            self.log(f"DEPLOY DAEMON DEAD: PID file exists but process not running", "ERROR")
            pidfile.unlink(missing_ok=True)
            self._try_restart_deploy_daemon()
            return False

    def _try_restart_deploy_daemon(self):
        """Attempt to restart the deploy daemon."""
        import subprocess
        cmd = f"python3 cli/factory.py {self.project.id} deploy start --batch"
        self.log(f"AUTO-RESTART deploy daemon: {cmd}", "WARN")
        try:
            subprocess.Popen(
                cmd.split(),
                cwd=str(Path(__file__).parent.parent),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self.log("Deploy daemon restart initiated", "WARN")
        except Exception as e:
            self.log(f"Deploy daemon restart FAILED: {e}", "ERROR")

    async def _phase_deploy(self):
        """Phase 3: Deploy - Staging → E2E → Prod"""
        self.state.phase = CyclePhase.DEPLOY
        self.state.phase_start = datetime.now()

        self.log("[PHASE 3] Deploy - Starting deployment pipeline")

        # CHECK: Deploy daemon must be alive
        if not self._check_deploy_daemon_alive():
            self.log("[PHASE 3] Deploy daemon not available - tasks stay in commit_queued", "WARN")
            # Don't abort - still commit, but warn loudly
            # The watchdog or auto-restart should fix it

        # Get COMMIT_QUEUED tasks
        tasks = self.task_store.get_tasks_by_status(
            self.project.id, TaskStatus.COMMIT_QUEUED, limit=100
        )

        if not tasks:
            self.log("No tasks to deploy")
            return

        self.log(f"Committing {len(tasks)} tasks...")

        # 1. Git commit - returns commit_sha for batch deploy
        commit_sha = await self._git_commit(tasks)
        if not commit_sha:
            self.log("Commit failed, aborting deploy")
            return

        # 2. Queue for deploy daemon (real E2E validation)
        # The deploy daemon will handle: staging → adversarial → E2E → prod
        self.log(f"Commit {commit_sha[:8]} pushed - queueing for deploy daemon (batch of {len(tasks)})")

        # Mark tasks as queued_for_deploy with commit_sha for batch deploy
        for task in tasks:
            try:
                # Set commit_sha so deploy daemon can batch by commit
                self.task_store.update_task(task.id, commit_sha=commit_sha)
                self.task_store.transition(task.id, TaskStatus.QUEUED_FOR_DEPLOY)
                self.state.commit_success += 1
            except Exception as e:
                self.log(f"Failed to queue task {task.id}: {e}", "WARN")

        self.log(f"[PHASE 3] Complete: {self.state.commit_success} tasks committed (commit {commit_sha[:8]}) — awaiting real deploy")

    async def _auto_brain_if_needed(self):
        """Auto-trigger Brain analysis when backlog is empty.

        Order: 1) Integration gap detection  2) Phase-based brain (vision/fix/refactor)
        Integration runs FIRST because without wired layers, new features are useless.
        """
        from datetime import timedelta

        # Check cooldown
        if self.state.last_brain_run:
            elapsed = datetime.now() - self.state.last_brain_run
            cooldown = timedelta(minutes=self.config.auto_brain_cooldown_minutes)
            if elapsed < cooldown:
                remaining = int((cooldown - elapsed).total_seconds() / 60)
                self.log(f"Auto-Brain cooldown: {remaining}min remaining, waiting...")
                await asyncio.sleep(60)
                return

        self.state.last_brain_run = datetime.now()

        try:
            from core.brain import RLMBrain

            brain = RLMBrain(self.project.id)

            # STEP 1: Integration gap detection (deterministic + LLM)
            integrator_cfg = (self.project.raw_config or {}).get('integrator', {})
            if integrator_cfg.get('enabled', False):
                self.log("🔗 AUTO-BRAIN: Checking integration gaps...")
                try:
                    integration_tasks = await brain.run(mode="integrator", deep_analysis=True)
                    if integration_tasks and len(integration_tasks) > 0:
                        self.log(f"🔗 AUTO-BRAIN: Created {len(integration_tasks)} integration tasks")
                        return  # Let cycle process integration tasks first
                except Exception as e:
                    self.log(f"🔗 Integration detection error: {e}", "WARN")

            # STEP 2: Phase-based brain (vision/fix/refactor)
            mode = self.project.get_brain_mode() if hasattr(self.project, 'get_brain_mode') else "vision"
            self.log(f"🧠 AUTO-BRAIN: Running Brain analysis (mode={mode})...")
            tasks_created = await brain.run(mode=mode, deep_analysis=True)

            if tasks_created and len(tasks_created) > 0:
                self.log(f"🧠 AUTO-BRAIN: Created {len(tasks_created)} new tasks")
            else:
                self.log("🧠 AUTO-BRAIN: No new tasks created, waiting...")
                await asyncio.sleep(300)

        except Exception as e:
            self.log(f"🧠 AUTO-BRAIN error: {e}", "ERROR")
            await asyncio.sleep(60)

    async def _git_commit(self, tasks: List) -> Optional[str]:
        """Commit all changes. Returns commit_sha on success, None on failure."""
        import subprocess

        cwd = self.project.root_path

        # Check for changes
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=cwd,
            capture_output=True,
            text=True
        )

        if not result.stdout.strip():
            self.log("No changes to commit")
            # Return current HEAD as commit_sha (tasks still need to deploy)
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=cwd,
                capture_output=True,
                text=True
            )
            return result.stdout.strip() if result.returncode == 0 else None

        # Stage all changes
        rc, _, _ = await run_subprocess("git add -A", timeout=60, cwd=str(cwd), log_fn=self.log)

        # Commit
        task_ids = ", ".join([t.id for t in tasks[:5]])
        if len(tasks) > 5:
            task_ids += f" (+{len(tasks)-5} more)"

        commit_msg = f"feat(factory): Cycle {self.state.cycle_count} - {len(tasks)} tasks\n\nTasks: {task_ids}"
        safe_msg = commit_msg.replace('"', '\\"')

        rc, _, stderr = await run_subprocess(
            f'git commit --no-verify -m "{safe_msg}"',
            timeout=60, cwd=str(cwd), log_fn=self.log,
        )

        if rc != 0:
            self.log(f"Commit failed: {stderr}", "ERROR")
            return None

        # Get commit SHA
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True
        )
        commit_sha = result.stdout.strip() if result.returncode == 0 else None

        # Push - detect remote and branch automatically
        # Get current branch
        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True
        )
        branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "dev"

        # Get remote (prefer 'origin', fallback to first remote)
        remote_result = subprocess.run(
            ["git", "remote"],
            cwd=cwd,
            capture_output=True,
            text=True
        )
        remotes = remote_result.stdout.strip().split('\n') if remote_result.returncode == 0 else []
        remote = "origin" if "origin" in remotes else (remotes[0] if remotes else "origin")

        push_cmd = f"git push {remote} {branch}"
        self.log(f"Pushing: {push_cmd}")

        rc, _, stderr = await run_subprocess(push_cmd, timeout=120, cwd=str(cwd), log_fn=self.log)

        if rc != 0:
            self.log(f"Push failed: {stderr}", "ERROR")
            # Don't fail completely - commit exists locally, can be pushed manually
            self.log(f"Local commit {commit_sha[:8]} created, push manually: {push_cmd}", "WARN")
            return commit_sha  # Return sha anyway so deploy can continue

        self.log(f"Committed and pushed {len(tasks)} tasks (commit {commit_sha[:8] if commit_sha else 'unknown'})")
        return commit_sha


class CycleDaemon(Daemon):
    """Daemon wrapper for CycleWorker"""

    def __init__(self, project: ProjectConfig, config: CycleConfig = None):
        super().__init__(name="cycle", project=project.id)
        self.config = config
        self.worker = None  # Created in run() to pass self

    async def run(self):
        self.worker = CycleWorker(self.project_config, self.config, daemon=self)
        await self.worker.run()

    @property
    def project_config(self) -> ProjectConfig:
        from core.project_registry import get_project
        return get_project(self.project)
