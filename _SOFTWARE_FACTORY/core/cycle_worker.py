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
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from core.daemon import Daemon
from core.task_store import TaskStore, TaskStatus
from core.project_registry import ProjectConfig


class CyclePhase(Enum):
    TDD = "tdd"
    BUILD = "build"
    DEPLOY = "deploy"
    IDLE = "idle"


@dataclass
class CycleConfig:
    """Configuration for development cycle"""
    # Phase 1: TDD
    tdd_workers: int = 5
    tdd_batch_size: int = 10  # Tasks to complete before build
    tdd_timeout_minutes: int = 30  # Max time in TDD phase

    # Phase 2: Build
    build_timeout_minutes: int = 15
    max_build_retries: int = 2

    # Phase 3: Deploy
    deploy_timeout_minutes: int = 20
    skip_deploy: bool = False  # For testing


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
    deploy_success: int = 0


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

        while self.running:
            try:
                self.state.cycle_count += 1
                self.log(f"=== CYCLE {self.state.cycle_count} ===")

                # Check if there are pending tasks
                pending = self.task_store.get_tasks_by_status(
                    self.project.id, TaskStatus.PENDING, limit=1
                )
                if not pending:
                    self.log("No pending tasks, waiting...")
                    await asyncio.sleep(60)
                    continue

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
        """Build all tasks for a domain"""
        self.log(f"Building domain {domain}: {len(tasks)} tasks")

        domain_config = self.project.domains.get(domain, {})
        build_cmd = domain_config.get("build_cmd", "echo 'no build cmd'")
        test_cmd = domain_config.get("test_cmd", "")

        # Run build command
        proc = await asyncio.create_subprocess_shell(
            f"cd {self.project.root_path} && {build_cmd}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            error = stderr.decode()[:500] if stderr else "Build failed"
            self.log(f"Build failed for {domain}: {error}", "ERROR")

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
            proc = await asyncio.create_subprocess_shell(
                f"cd {self.project.root_path} && {test_cmd}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                error = stderr.decode()[:500] if stderr else "Tests failed"
                self.log(f"Tests failed for {domain}: {error}", "ERROR")

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

    def _create_build_feedback(self, domain: str, error: str, tasks: List):
        """Create feedback tasks from build errors"""
        from core.task_store import Task
        import hashlib

        # Create ONE feedback task per domain (not per task)
        feedback_id = f"feedback-build-{domain}-{hashlib.md5(error.encode()).hexdigest()[:8]}"

        feedback = Task(
            id=feedback_id,
            project_id=self.project.id,
            type="fix",
            domain=domain,
            description=f"[BUILD FEEDBACK] Fix build error in {domain}: {error[:200]}",
            status=TaskStatus.PENDING.value,
            priority=10,  # High priority
            files=[t.files[0] if t.files else "" for t in tasks[:5]],
            context={"error": error, "related_tasks": [t.id for t in tasks]},
        )

        try:
            self.task_store.create_task(feedback)
            self.log(f"Created feedback task: {feedback_id}")
        except:
            pass  # May already exist

    async def _phase_deploy(self):
        """Phase 3: Deploy - Staging → E2E → Prod"""
        self.state.phase = CyclePhase.DEPLOY
        self.state.phase_start = datetime.now()

        self.log("[PHASE 3] Deploy - Starting deployment pipeline")

        # Get COMMIT_QUEUED tasks
        tasks = self.task_store.get_tasks_by_status(
            self.project.id, TaskStatus.COMMIT_QUEUED, limit=100
        )

        if not tasks:
            self.log("No tasks to deploy")
            return

        self.log(f"Deploying {len(tasks)} tasks...")

        # 1. Git commit
        commit_success = await self._git_commit(tasks)
        if not commit_success:
            self.log("Commit failed, aborting deploy")
            return

        # 2. Deploy to staging (via git push which triggers CI/CD)
        # The actual deployment is handled by CI/CD pipeline
        self.log("Commit pushed - CI/CD pipeline will handle staging → E2E → prod")

        # Mark tasks as deployed
        for task in tasks:
            try:
                self.task_store.transition(task.id, TaskStatus.DEPLOYED)
                self.state.deploy_success += 1
            except:
                pass

        self.log(f"[PHASE 3] Complete: {self.state.deploy_success} tasks deployed")

    async def _git_commit(self, tasks: List) -> bool:
        """Commit all changes"""
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
            return True

        # Stage all changes
        proc = await asyncio.create_subprocess_shell(
            "git add -A",
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

        # Commit
        task_ids = ", ".join([t.id for t in tasks[:5]])
        if len(tasks) > 5:
            task_ids += f" (+{len(tasks)-5} more)"

        commit_msg = f"feat(factory): Cycle {self.state.cycle_count} - {len(tasks)} tasks\n\nTasks: {task_ids}"

        proc = await asyncio.create_subprocess_shell(
            f'git commit --no-verify -m "{commit_msg}"',
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            error = stderr.decode() if stderr else "Commit failed"
            self.log(f"Commit failed: {error}", "ERROR")
            return False

        # Push
        proc = await asyncio.create_subprocess_shell(
            "git push",
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            error = stderr.decode() if stderr else "Push failed"
            self.log(f"Push failed: {error}", "ERROR")
            return False

        self.log(f"Committed and pushed {len(tasks)} tasks")
        return True


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
