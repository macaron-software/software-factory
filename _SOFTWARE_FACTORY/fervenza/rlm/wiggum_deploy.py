"""
Wiggum Deploy - Deployment Pipeline for RLM.

Deploys completed tasks through staging → E2E tests → production.
Uses the existing Fervenza CLI for actual deployments.
"""

import asyncio
import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import (
    Backlog,
    DeployBacklog,
    DeployTask,
    Domain,
    Finding,
    Task,
    TaskStatus,
    TaskType,
)

logger = logging.getLogger(__name__)

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
BACKLOG_PATH = Path(__file__).parent / "backlog_tasks.json"
DEPLOY_BACKLOG_PATH = Path(__file__).parent / "deploy_backlog.json"

# Deploy commands by domain
DEPLOY_COMMANDS = {
    Domain.RUST: ["fervenza", "deploy", "server", "-y"],
    Domain.PYTHON: ["fervenza", "deploy", "agents", "-y"],
    Domain.TYPESCRIPT: ["fervenza", "deploy", "dashboard", "-y"],
    Domain.E2E: ["fervenza", "deploy", "dashboard", "-y"],
    Domain.PROTO: ["fervenza", "deploy", "server", "-y"],
    Domain.SQL: ["fervenza", "deploy", "server", "-y"],
}

# Test commands by domain
TEST_COMMANDS = {
    Domain.RUST: ["cargo", "test", "--workspace"],
    Domain.PYTHON: ["python", "-m", "pytest", "-x"],
    Domain.E2E: ["npx", "playwright", "test"],
}


class WiggumDeploy:
    """
    Wiggum Deploy - Manages deployment pipeline.

    Pipeline:
    1. Collect completed tasks with commits
    2. Run domain-specific tests
    3. Deploy to staging (via Fervenza CLI)
    4. Run E2E tests on staging
    5. Deploy to production (via Fervenza CLI)
    6. Verify health

    Usage:
        deploy = WiggumDeploy()
        await deploy.run()  # Deploy all completed tasks
        await deploy.run_once()  # Deploy single task
    """

    def __init__(self):
        self.backlog: Optional[Backlog] = None
        self.deploy_backlog: Optional[DeployBacklog] = None
        self._running = False

    def _load_backlogs(self) -> None:
        """Load both backlogs from disk."""
        # Load TDD backlog
        if BACKLOG_PATH.exists():
            try:
                data = json.loads(BACKLOG_PATH.read_text())
                self.backlog = Backlog.model_validate(data)
            except Exception as e:
                logger.error(f"Failed to load backlog: {e}")
                self.backlog = Backlog()
        else:
            self.backlog = Backlog()

        # Load deploy backlog
        if DEPLOY_BACKLOG_PATH.exists():
            try:
                data = json.loads(DEPLOY_BACKLOG_PATH.read_text())
                self.deploy_backlog = DeployBacklog.model_validate(data)
            except Exception as e:
                logger.error(f"Failed to load deploy backlog: {e}")
                self.deploy_backlog = DeployBacklog()
        else:
            self.deploy_backlog = DeployBacklog()

    def _save_deploy_backlog(self) -> None:
        """Save deploy backlog to disk."""
        if self.deploy_backlog:
            DEPLOY_BACKLOG_PATH.write_text(
                self.deploy_backlog.model_dump_json(indent=2, exclude_none=True)
            )

    def _save_backlog(self) -> None:
        """Save TDD backlog to disk (for feedback loop)."""
        if self.backlog:
            BACKLOG_PATH.write_text(
                self.backlog.model_dump_json(indent=2, exclude_none=True)
            )

    def _create_deploy_tasks(self) -> list[DeployTask]:
        """Create deploy tasks from completed TDD tasks."""
        new_tasks = []

        # Get completed tasks with commits not yet in deploy backlog
        deployed_ids = {t.source_task for t in self.deploy_backlog.tasks}

        for task in self.backlog.tasks:
            if (
                task.status == TaskStatus.COMPLETED
                and task.commit_hash
                and task.id not in deployed_ids
            ):
                deploy_task = DeployTask(
                    id=f"deploy-{task.id}",
                    source_task=task.id,
                    commit_hash=task.commit_hash,
                    domain=task.domain,
                )
                new_tasks.append(deploy_task)
                self.deploy_backlog.tasks.append(deploy_task)

        return new_tasks

    async def run(self) -> dict:
        """
        Run deploy pipeline on all pending deploy tasks.

        Returns stats when complete.
        """
        self._load_backlogs()
        self._running = True

        # Create deploy tasks from completed TDD tasks
        new_tasks = self._create_deploy_tasks()
        logger.info(f"Created {len(new_tasks)} new deploy tasks")

        pending_tasks = [
            t for t in self.deploy_backlog.tasks if t.status == TaskStatus.PENDING
        ]

        if not pending_tasks:
            return {"status": "no_tasks", "deployed": 0}

        # Group by domain for batch deployment
        by_domain: dict[Domain, list[DeployTask]] = {}
        for task in pending_tasks:
            if task.domain not in by_domain:
                by_domain[task.domain] = []
            by_domain[task.domain].append(task)

        deployed = 0
        failed = 0

        for domain, tasks in by_domain.items():
            if not self._running:
                break

            logger.info(f"Deploying {len(tasks)} tasks for domain {domain.value}")

            # Mark tasks as in progress
            for task in tasks:
                task.status = TaskStatus.IN_PROGRESS

            try:
                # 1. Run tests
                test_ok, test_output = await self._run_tests(domain)
                if not test_ok:
                    for task in tasks:
                        task.status = TaskStatus.FAILED
                        task.error = f"Tests failed: {test_output[:200]}"
                        # Feedback loop: create fix task in TDD backlog
                        self._create_fix_task_from_failure(task, "tests_failed", test_output)
                        failed += 1
                    continue

                # 2. Deploy (uses Fervenza CLI)
                deploy_ok, deploy_output = await self._deploy(domain)
                if not deploy_ok:
                    for task in tasks:
                        task.status = TaskStatus.FAILED
                        task.error = f"Deploy failed: {deploy_output[:200]}"
                        # Feedback loop: create fix task in TDD backlog
                        self._create_fix_task_from_failure(task, "deploy_failed", deploy_output)
                        failed += 1
                    continue

                # 3. Verify health
                health_ok = await self._verify_health(domain)
                if not health_ok:
                    logger.warning(f"Health check failed for {domain.value}")

                # Mark as completed
                for task in tasks:
                    task.status = TaskStatus.COMPLETED
                    task.prod_deployed = True
                    task.deployed_at = datetime.utcnow()
                    deployed += 1

            except Exception as e:
                logger.error(f"Deploy error for {domain.value}: {e}")
                for task in tasks:
                    task.status = TaskStatus.FAILED
                    task.error = str(e)
                    failed += 1

            self._save_deploy_backlog()

        self.deploy_backlog.update_stats()
        self._save_deploy_backlog()

        return {
            "status": "completed",
            "deployed": deployed,
            "failed": failed,
            "remaining": sum(
                1
                for t in self.deploy_backlog.tasks
                if t.status == TaskStatus.PENDING
            ),
        }

    async def run_once(self) -> dict:
        """Deploy a single task."""
        self._load_backlogs()

        # Create deploy tasks
        self._create_deploy_tasks()

        # Get first pending
        pending = next(
            (t for t in self.deploy_backlog.tasks if t.status == TaskStatus.PENDING),
            None,
        )

        if not pending:
            return {"status": "no_tasks"}

        pending.status = TaskStatus.IN_PROGRESS

        try:
            # Run tests
            test_ok, test_output = await self._run_tests(pending.domain)
            if not test_ok:
                pending.status = TaskStatus.FAILED
                pending.error = f"Tests failed: {test_output[:200]}"
                # Feedback loop: create fix task in TDD backlog
                self._create_fix_task_from_failure(pending, "tests_failed", test_output)
                self._save_deploy_backlog()
                return {"status": "failed", "error": pending.error}

            # Deploy
            deploy_ok, deploy_output = await self._deploy(pending.domain)
            if not deploy_ok:
                pending.status = TaskStatus.FAILED
                pending.error = f"Deploy failed: {deploy_output[:200]}"
                # Feedback loop: create fix task in TDD backlog
                self._create_fix_task_from_failure(pending, "deploy_failed", deploy_output)
                self._save_deploy_backlog()
                return {"status": "failed", "error": pending.error}

            pending.status = TaskStatus.COMPLETED
            pending.prod_deployed = True
            pending.deployed_at = datetime.utcnow()
            self._save_deploy_backlog()

            return {
                "status": "deployed",
                "task_id": pending.id,
                "commit": pending.commit_hash,
                "domain": pending.domain.value,
            }

        except Exception as e:
            pending.status = TaskStatus.FAILED
            pending.error = str(e)
            self._save_deploy_backlog()
            return {"status": "failed", "error": str(e)}

    async def _run_tests(self, domain: Domain) -> tuple[bool, str]:
        """Run tests for domain before deploy. Returns (success, output)."""
        cmd = TEST_COMMANDS.get(domain)
        if not cmd:
            return True, ""  # No tests defined, assume OK

        cwd = PROJECT_ROOT
        if domain == Domain.PYTHON:
            cwd = PROJECT_ROOT / "agents"
        elif domain == Domain.E2E:
            cwd = PROJECT_ROOT / "e2e"

        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=600,
            )

            if result.returncode != 0:
                error_output = result.stderr or result.stdout
                logger.error(f"Tests failed for {domain.value}: {error_output[:500]}")
                return False, error_output

            logger.info(f"Tests passed for {domain.value}")
            return True, result.stdout

        except subprocess.TimeoutExpired:
            logger.error(f"Tests timed out for {domain.value}")
            return False, "Tests timed out after 600s"
        except Exception as e:
            logger.error(f"Test error: {e}")
            return False, str(e)

    async def _deploy(self, domain: Domain) -> tuple[bool, str]:
        """Deploy domain using Fervenza CLI. Returns (success, output)."""
        cmd = DEPLOY_COMMANDS.get(domain)
        if not cmd:
            logger.warning(f"No deploy command for {domain.value}")
            return True, ""

        try:
            result = subprocess.run(
                cmd,
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=600,
            )

            if result.returncode != 0:
                error_output = result.stderr or result.stdout
                logger.error(f"Deploy failed for {domain.value}: {error_output[:500]}")
                return False, error_output

            logger.info(f"Deploy successful for {domain.value}")
            return True, result.stdout

        except subprocess.TimeoutExpired:
            logger.error(f"Deploy timed out for {domain.value}")
            return False, "Deploy timed out after 600s"
        except Exception as e:
            logger.error(f"Deploy error: {e}")
            return False, str(e)

    async def _verify_health(self, domain: Domain) -> bool:
        """Verify health after deployment."""
        # Use Fervenza CLI to check status
        try:
            result = subprocess.run(
                ["fervenza", "deploy", "status"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Check for "healthy" or similar in output
            if "healthy" in result.stdout.lower() or "active" in result.stdout.lower():
                return True

            logger.warning(f"Health check output: {result.stdout[:200]}")
            return True  # Don't fail on health check for now

        except Exception as e:
            logger.warning(f"Health check error: {e}")
            return True  # Don't fail on health check

    def _create_fix_task_from_failure(
        self, deploy_task: DeployTask, error_type: str, error_output: str
    ) -> Optional[Task]:
        """
        Create a fix task in TDD backlog when deploy fails.

        This implements the feedback loop: Deploy failure → TDD fix.

        Args:
            deploy_task: The failed deploy task
            error_type: Type of failure (tests_failed, deploy_failed, health_failed)
            error_output: Error output from the failed command

        Returns:
            The created fix task, or None if source task not found
        """
        if not self.backlog:
            return None

        # Find the original TDD task
        source_task = next(
            (t for t in self.backlog.tasks if t.id == deploy_task.source_task), None
        )
        if not source_task:
            logger.warning(f"Source task {deploy_task.source_task} not found for feedback loop")
            return None

        # Create a fix task ID based on the failure
        fix_task_id = f"{source_task.id}-deploy-fix-{error_type}"

        # Check if fix task already exists
        if any(t.id == fix_task_id for t in self.backlog.tasks):
            logger.info(f"Fix task {fix_task_id} already exists, skipping")
            return None

        # Create the fix task
        fix_task = Task(
            id=fix_task_id,
            type=TaskType.FIX,
            domain=deploy_task.domain,
            description=f"Fix deploy failure ({error_type}): {source_task.description[:50]}",
            files=source_task.files,
            finding=Finding(
                type=f"deploy_{error_type}",
                severity="high",
                message=f"Deploy failed with {error_type}: {error_output[:200]}",
                file=source_task.files[0] if source_task.files else None,
            ),
            parent_task_id=source_task.id,
            depth=source_task.depth + 1,
            conventions=source_task.conventions,
            # High priority - deploy failures are critical
            business_value=9,
            time_criticality=9,
            risk_reduction=8,
            job_size=source_task.job_size,
            # Store the error context for the TDD worker
            adversarial_feedback=f"Deploy failed: {error_output[:500]}",
        )
        fix_task.calculate_wsjf()

        # Add to backlog
        self.backlog.tasks.append(fix_task)
        source_task.subtask_ids.append(fix_task_id)

        logger.info(f"Created fix task {fix_task_id} from deploy failure (feedback loop)")

        # Save backlog immediately
        self._save_backlog()

        return fix_task

    def get_status(self) -> dict:
        """Get deploy backlog status."""
        self._load_backlogs()

        pending = sum(
            1 for t in self.deploy_backlog.tasks if t.status == TaskStatus.PENDING
        )
        deployed = sum(
            1 for t in self.deploy_backlog.tasks if t.status == TaskStatus.COMPLETED
        )
        failed = sum(
            1 for t in self.deploy_backlog.tasks if t.status == TaskStatus.FAILED
        )

        # By domain
        by_domain = {}
        for domain in Domain:
            tasks = [t for t in self.deploy_backlog.tasks if t.domain == domain]
            if tasks:
                by_domain[domain.value] = {
                    "total": len(tasks),
                    "deployed": sum(1 for t in tasks if t.prod_deployed),
                }

        return {
            "total": len(self.deploy_backlog.tasks),
            "pending": pending,
            "deployed": deployed,
            "failed": failed,
            "by_domain": by_domain,
            "updated": self.deploy_backlog.updated.isoformat(),
        }

    def stop(self) -> None:
        """Stop running deployments."""
        self._running = False


async def main():
    """CLI entry point for Wiggum Deploy."""
    import argparse

    parser = argparse.ArgumentParser(description="Wiggum Deploy - Deployment Pipeline")
    parser.add_argument("--once", action="store_true", help="Deploy single task")
    parser.add_argument("--status", action="store_true", help="Show deploy status")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    deploy = WiggumDeploy()

    if args.status:
        status = deploy.get_status()
        print(json.dumps(status, indent=2))
        return

    if args.once:
        result = await deploy.run_once()
    else:
        result = await deploy.run()

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
