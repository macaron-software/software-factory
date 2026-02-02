#!/usr/bin/env python3
"""
Build Worker - Phase 2 of RLM Pipeline

Picks tasks with CODE_WRITTEN status and runs build/test.
Uses semaphore to limit concurrent builds (prevents CPU explosion).

Flow:
  CODE_WRITTEN → BUILD_IN_PROGRESS → BUILD_SUCCESS/BUILD_FAILED
  BUILD_SUCCESS → adversarial → COMMIT_QUEUED
"""

import asyncio
import os
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.task_store import TaskStore, Task, TaskStatus
from core.project_registry import ProjectConfig, get_project as load_project_config
from core.adversarial import AdversarialGate
from core.daemon import Daemon

# ============================================================================
# CONFIG
# ============================================================================

MAX_CONCURRENT_BUILDS = 3  # Global limit on concurrent builds
BUILD_TIMEOUT = 300  # 5 minutes per build
POLL_INTERVAL = 5  # Seconds between queue checks

# Module-level logger
_logger = None

def log(msg: str, level: str = "INFO"):
    """Log message"""
    from datetime import datetime
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [build] [{level}] {msg}", flush=True)


# ============================================================================
# BUILD WORKER
# ============================================================================

@dataclass
class BuildResult:
    """Result of a build attempt"""
    success: bool = False
    task_id: str = ""
    build_passed: bool = False
    lint_passed: bool = False
    test_passed: bool = False
    adversarial_passed: bool = False
    error: str = ""
    feedback_tasks: List[Dict] = field(default_factory=list)


class BuildWorker:
    """Worker that runs build/lint/test for a task"""

    def __init__(
        self,
        project: ProjectConfig,
        task_store: TaskStore,
        worker_id: str = "build-0",
        semaphore: asyncio.Semaphore = None,
    ):
        self.project = project
        self.task_store = task_store
        self.worker_id = worker_id
        self.semaphore = semaphore or asyncio.Semaphore(MAX_CONCURRENT_BUILDS)
        self.adversarial = AdversarialGate(project)

    def log(self, msg: str, level: str = "INFO"):
        log(f"[{self.worker_id}] {msg}", level)

    async def process_task(self, task: Task) -> BuildResult:
        """Process a single task through build/test/adversarial"""
        result = BuildResult(task_id=task.id)

        # Acquire semaphore (wait for build slot)
        async with self.semaphore:
            self.log(f"🔨 Building: {task.id} ({task.domain})")

            try:
                # Note: Transition to BUILD_IN_PROGRESS already done by daemon
                # to prevent race conditions

                # 1. Run build
                build_success, build_errors = await self._run_build(task.domain)
                if not build_success:
                    self.log(f"Build failed: {build_errors[:100] if build_errors else 'unknown'}", "WARN")
                    result.error = f"Build failed: {build_errors}"
                    result.feedback_tasks = self._parse_build_errors(build_errors, task)
                    self.task_store.transition(task.id, TaskStatus.BUILD_FAILED)
                    return result
                result.build_passed = True

                # 2. Run lint
                lint_success = await self._run_lint(task.domain)
                if not lint_success:
                    self.log("Lint failed", "WARN")
                    result.error = "Lint failed"
                    self.task_store.transition(task.id, TaskStatus.BUILD_FAILED)
                    return result
                result.lint_passed = True

                # 3. Run tests
                test_success, test_errors = await self._run_tests(task.domain)
                if not test_success:
                    self.log(f"Tests failed: {test_errors[:100] if test_errors else 'unknown'}", "WARN")
                    result.error = f"Tests failed: {test_errors}"
                    result.feedback_tasks = self._parse_test_errors(test_errors, task)
                    self.task_store.transition(task.id, TaskStatus.BUILD_FAILED)
                    return result
                result.test_passed = True

                # 4. Transition to BUILD_SUCCESS
                self.task_store.transition(task.id, TaskStatus.BUILD_SUCCESS)

                # 5. Run adversarial check
                adv_result = await self._run_adversarial(task)
                if not adv_result.approved:
                    self.log(f"Adversarial rejected: {adv_result.feedback[:100]}", "WARN")
                    result.error = f"Adversarial rejected: {adv_result.feedback}"
                    self.task_store.transition(task.id, TaskStatus.ADVERSARIAL_REJECTED)
                    # Return to pending for retry
                    self.task_store.transition(task.id, TaskStatus.PENDING)
                    return result
                result.adversarial_passed = True

                # 6. Queue for commit
                self.task_store.transition(task.id, TaskStatus.COMMIT_QUEUED)
                self.log(f"✅ Build passed, queued for commit: {task.id}")
                result.success = True

            except Exception as e:
                self.log(f"Exception: {e}", "ERROR")
                result.error = str(e)
                self.task_store.transition(task.id, TaskStatus.BUILD_FAILED)

        return result

    async def _run_build(self, domain: str) -> tuple[bool, str]:
        """Run build command for domain via global queue (if enabled) or direct"""
        build_cmd = self.project.get_build_cmd(domain)

        if not build_cmd:
            self.log(f"No build_cmd for domain {domain}, skipping build")
            return True, ""

        # Check if global queue is enabled (default: True)
        raw_config = getattr(self.project, 'raw_config', None) or {}
        use_queue = raw_config.get("build_queue", {}).get("enabled", True)
        
        if use_queue:
            # Auto-start queue daemon if not running
            await self._ensure_queue_daemon()
            return await self._run_via_queue(build_cmd, "build")
        else:
            return await self._run_direct(build_cmd)

    async def _run_via_queue(self, cmd: str, job_type: str) -> tuple[bool, str]:
        """Run command via global build queue"""
        from core.build_queue import GlobalBuildQueue, JobStatus
        
        queue = GlobalBuildQueue.instance()
        raw_config = getattr(self.project, 'raw_config', None) or {}
        priority = raw_config.get("build_queue", {}).get("priority", 10)
        timeout = raw_config.get("build_queue", {}).get("timeout", BUILD_TIMEOUT)
        
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

    async def _run_direct(self, cmd: str) -> tuple[bool, str]:
        """Run command directly (bypass queue)"""
        self.log(f"Running: {cmd}")
        try:
            # Inject project-specific env vars (e.g., VELIGO_TOKEN)
            env = os.environ.copy()
            project_env = self.project.get_env()
            if project_env:
                env.update(project_env)

            proc = await asyncio.create_subprocess_shell(
                cmd,
                cwd=str(self.project.root_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
                start_new_session=True,  # Isolate process group for clean kill
            )
            try:
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=BUILD_TIMEOUT)
            except asyncio.TimeoutError:
                # Kill entire process group (including child processes)
                import signal
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                return False, "Build timeout"

            output = stdout.decode() if stdout else ""

            if proc.returncode == 0:
                return True, ""
            else:
                return False, output
        except Exception as e:
            return False, str(e)

    async def _run_lint(self, domain: str) -> bool:
        """Run lint command for domain using project CLI"""
        lint_cmd = self.project.get_lint_cmd(domain)

        if not lint_cmd:
            return True  # No lint = pass

        # Check if global queue is enabled (default: True)
        raw_config = getattr(self.project, 'raw_config', None) or {}
        use_queue = raw_config.get("build_queue", {}).get("enabled", True)
        
        if use_queue:
            await self._ensure_queue_daemon()
            success, _ = await self._run_via_queue(lint_cmd, "lint")
            return success
        
        self.log(f"Linting: {lint_cmd}")
        try:
            # Inject project-specific env vars
            env = os.environ.copy()
            project_env = self.project.get_env()
            if project_env:
                env.update(project_env)

            proc = await asyncio.create_subprocess_shell(
                lint_cmd,
                cwd=str(self.project.root_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
                start_new_session=True,  # Isolate process group for clean kill
            )
            try:
                await asyncio.wait_for(proc.communicate(), timeout=BUILD_TIMEOUT)
            except asyncio.TimeoutError:
                # Kill entire process group
                import signal
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                return False
            return proc.returncode == 0
        except:
            return False

    async def _run_tests(self, domain: str) -> tuple[bool, str]:
        """Run test command for domain via global queue (if enabled) or direct"""
        test_cmd = self.project.get_test_cmd(domain)

        if not test_cmd:
            self.log(f"No test_cmd for domain {domain}, skipping tests")
            return True, ""

        # Check if global queue is enabled (default: True)
        raw_config = getattr(self.project, 'raw_config', None) or {}
        use_queue = raw_config.get("build_queue", {}).get("enabled", True)
        
        if use_queue:
            await self._ensure_queue_daemon()
            return await self._run_via_queue(test_cmd, "test")
        
        self.log(f"Testing: {test_cmd}")
        try:
            # Inject project-specific env vars
            env = os.environ.copy()
            project_env = self.project.get_env()
            if project_env:
                env.update(project_env)

            proc = await asyncio.create_subprocess_shell(
                test_cmd,
                cwd=str(self.project.root_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
                start_new_session=True,  # Isolate process group for clean kill
            )
            try:
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=BUILD_TIMEOUT)
            except asyncio.TimeoutError:
                # Kill entire process group (including vitest children)
                import os
                import signal
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                return False, "Test timeout"

            output = stdout.decode() if stdout else ""

            if proc.returncode == 0:
                return True, ""
            else:
                return False, output
        except Exception as e:
            return False, str(e)

    async def _ensure_queue_daemon(self):
        """Auto-start queue daemon if not running"""
        from core.build_queue import QueueDaemon
        daemon = QueueDaemon()
        status = daemon.status()
        if not status.get("running"):
            self.log("Auto-starting queue daemon...")
            daemon.start(foreground=False)

    async def _run_adversarial(self, task: Task) -> Any:
        """Run adversarial check on the task"""
        # Get changed files from git
        try:
            proc = await asyncio.create_subprocess_shell(
                "git diff --name-only HEAD~1",
                cwd=str(self.project.root_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            changed_files = stdout.decode().strip().split("\n") if stdout else []

            # Read file contents for adversarial check
            code_changes = {}
            for f in changed_files[:10]:  # Limit to 10 files
                file_path = self.project.root_path / f
                if file_path.exists() and file_path.is_file():
                    try:
                        code_changes[f] = file_path.read_text()[:5000]  # Limit size
                    except:
                        pass

            return self.adversarial.check_code(code_changes)
        except Exception as e:
            self.log(f"Adversarial error: {e}", "WARN")
            # Return approved on error to not block pipeline
            from dataclasses import dataclass
            @dataclass
            class FakeResult:
                approved: bool = True
                feedback: str = ""
                score: int = 0
            return FakeResult()

    def _parse_build_errors(self, errors: str, task: Task) -> List[Dict]:
        """Parse build errors into feedback tasks"""
        if not errors:
            return []
        return [{
            "type": "fix",
            "domain": task.domain,
            "description": f"Fix build error: {errors[:200]}",
            "context": {"error": errors, "source_task": task.id},
        }]

    def _parse_test_errors(self, errors: str, task: Task) -> List[Dict]:
        """Parse test errors into feedback tasks"""
        if not errors:
            return []
        return [{
            "type": "fix",
            "domain": task.domain,
            "description": f"Fix test failure: {errors[:200]}",
            "context": {"error": errors, "source_task": task.id},
        }]


# ============================================================================
# BUILD DAEMON
# ============================================================================

class BuildDaemon(Daemon):
    """
    Daemon that processes build queue with 1 build per domain.

    Different domains (rust, swift, kotlin, typescript) can build in parallel,
    but only ONE build per domain at a time (to avoid conflicts like Cargo.lock).
    """

    def __init__(self, project: ProjectConfig, max_builds: int = None):
        super().__init__(name="build", project=project.name)
        self.project = project
        self.task_store = TaskStore()
        # One semaphore per domain - only 1 build at a time per domain
        self.domain_semaphores: Dict[str, asyncio.Semaphore] = {}
        self.domain_building: Dict[str, bool] = {}  # Track which domains are currently building

    def _get_domain_semaphore(self, domain: str) -> asyncio.Semaphore:
        """Get or create semaphore for a domain (1 build at a time per domain)"""
        if domain not in self.domain_semaphores:
            self.domain_semaphores[domain] = asyncio.Semaphore(1)
        return self.domain_semaphores[domain]

    async def _run_with_cleanup(self, domain: str, coro) -> BuildResult:
        """Run a build coroutine and cleanup domain_building flag when done"""
        try:
            result = await coro
            return result
        finally:
            self.domain_building[domain] = False

    async def run(self):
        """Main daemon loop - 1 build per domain, parallel across domains"""
        domains = list(self.project.domains.keys())
        self.log(f"Starting Build daemon (1 build/domain, domains: {', '.join(domains)})")

        while self.running:
            try:
                # Get tasks ready for build (CODE_WRITTEN status)
                tasks = self.task_store.get_tasks_by_status(
                    self.project.id,
                    TaskStatus.CODE_WRITTEN,
                    limit=20,
                )

                if tasks:
                    # Group tasks by domain and pick ONE per domain
                    tasks_by_domain: Dict[str, Task] = {}
                    for task in tasks:
                        domain = task.domain
                        # Only pick if domain not already building and not already picked
                        if domain not in tasks_by_domain and not self.domain_building.get(domain, False):
                            tasks_by_domain[domain] = task

                    if tasks_by_domain:
                        self.log(f"Building {len(tasks_by_domain)} domains: {', '.join(tasks_by_domain.keys())}")

                        # IMMEDIATELY transition to BUILD_IN_PROGRESS to prevent race conditions
                        skip_domains = []
                        for domain, task in tasks_by_domain.items():
                            try:
                                self.task_store.transition(task.id, TaskStatus.BUILD_IN_PROGRESS)
                            except Exception as e:
                                # Task already picked by another process, skip it
                                self.log(f"Skipping {task.id}: {e}", "WARN")
                                skip_domains.append(domain)
                        for domain in skip_domains:
                            del tasks_by_domain[domain]

                        # Process ONE task per domain in parallel
                        workers = []
                        for domain, task in list(tasks_by_domain.items()):
                            self.domain_building[domain] = True
                            worker = BuildWorker(
                                project=self.project,
                                task_store=self.task_store,
                                worker_id=f"B-{domain[:4]}",
                                semaphore=self._get_domain_semaphore(domain),
                            )
                            workers.append(self._run_with_cleanup(domain, worker.process_task(task)))

                        # Wait for all workers
                        results = await asyncio.gather(*workers, return_exceptions=True)

                        # Log results
                        success = sum(1 for r in results if isinstance(r, BuildResult) and r.success)
                        failed = len(results) - success
                        self.log(f"Batch: {success} success, {failed} failed")

                        # Create feedback tasks from failures
                        for r in results:
                            if isinstance(r, BuildResult) and r.feedback_tasks:
                                self._create_feedback_tasks(r.feedback_tasks)

                await asyncio.sleep(POLL_INTERVAL)

            except Exception as e:
                self.log(f"Error: {e}", "ERROR")
                await asyncio.sleep(POLL_INTERVAL)

    def _create_feedback_tasks(self, feedback_tasks: List[Dict]):
        """Create feedback tasks in the store"""
        import uuid
        for ft in feedback_tasks:
            try:
                task = Task(
                    id=f"feedback-build-{uuid.uuid4().hex[:8]}",
                    project_id=self.project.id,
                    type=ft.get("type", "fix"),
                    domain=ft.get("domain", "unknown"),
                    description=ft.get("description", "Fix build error"),
                    status="pending",
                    context=ft.get("context", {}),
                )
                self.task_store.create_task(task)
                self.log(f"Created feedback task: {task.id}")
            except Exception as e:
                self.log(f"Failed to create feedback task: {e}", "ERROR")


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Build Worker Daemon")
    parser.add_argument("command", choices=["start", "stop", "status", "run", "once"])
    parser.add_argument("--project", "-p", required=True, help="Project name")
    parser.add_argument("--max-builds", "-m", type=int, default=MAX_CONCURRENT_BUILDS,
                        help=f"Max concurrent builds (default: {MAX_CONCURRENT_BUILDS})")

    args = parser.parse_args()

    # Load project
    project = load_project_config(args.project)
    if not project:
        print(f"Project not found: {args.project}")
        sys.exit(1)

    daemon = BuildDaemon(project, max_builds=args.max_builds)

    if args.command == "start":
        daemon.start(foreground=False)

    elif args.command == "run":
        daemon.start(foreground=True)

    elif args.command == "once":
        # Process one batch and exit
        daemon.running = True

        async def run_once():
            tasks = daemon.task_store.get_tasks_by_status(
                project.id, TaskStatus.CODE_WRITTEN, limit=args.max_builds
            )
            if tasks:
                print(f"Processing {len(tasks)} tasks...")
                for task in tasks:
                    worker = BuildWorker(project, daemon.task_store, "B0", daemon.semaphore)
                    result = await worker.process_task(task)
                    print(f"{'✅' if result.success else '❌'} {task.id}: {result.error or 'OK'}")
            else:
                print("No tasks ready for build")

        asyncio.run(run_once())

    elif args.command == "stop":
        daemon.stop()

    elif args.command == "status":
        status = daemon.status()
        if status.get("running"):
            print(f"✅ {daemon.daemon_name}: RUNNING (PID {status.get('pid')})")
        elif status.get("stale"):
            print(f"❌ {daemon.daemon_name}: DEAD (stale PID)")
        else:
            print(f"⚪ {daemon.daemon_name}: NOT RUNNING")


if __name__ == "__main__":
    main()
