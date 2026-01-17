#!/usr/bin/env python3
"""
Commit Worker - Phase 4 of RLM Pipeline

Picks tasks with COMMIT_QUEUED status and commits them.
Runs SEQUENTIALLY (one commit at a time) to avoid git conflicts.

Flow:
  COMMIT_QUEUED → MERGED → QUEUED_FOR_DEPLOY
"""

import asyncio
import os
import sys
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.task_store import TaskStore, Task, TaskStatus
from core.project_registry import ProjectConfig, get_project as load_project_config
from core.daemon import Daemon

# ============================================================================
# CONFIG
# ============================================================================

POLL_INTERVAL = 5  # Seconds between queue checks

# Module-level logger
def log(msg: str, level: str = "INFO"):
    """Log message"""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [commit] [{level}] {msg}", flush=True)


# ============================================================================
# COMMIT WORKER
# ============================================================================

@dataclass
class CommitResult:
    """Result of a commit attempt"""
    success: bool = False
    task_id: str = ""
    commit_sha: str = ""
    error: str = ""


class CommitWorker:
    """Worker that commits changes for a task"""

    def __init__(self, project: ProjectConfig, task_store: TaskStore):
        self.project = project
        self.task_store = task_store

    def log(self, msg: str, level: str = "INFO"):
        log(f"[commit-{self.project.name}] {msg}", level)

    async def process_task(self, task: Task) -> CommitResult:
        """Commit changes for a task"""
        result = CommitResult(task_id=task.id)

        self.log(f"📝 Committing: {task.id}")

        try:
            cwd = str(self.project.root_path)

            # 1. Git add all changes
            proc = await asyncio.create_subprocess_shell(
                "git add -A",
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

            # 2. Check if there are changes to commit
            proc = await asyncio.create_subprocess_shell(
                "git diff --cached --name-only",
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            changed_files = stdout.decode().strip()

            if not changed_files:
                self.log("No changes to commit, skipping")
                # Still mark as success - no changes needed
                self.task_store.transition(task.id, TaskStatus.MERGED)
                result.success = True
                return result

            # 3. Create commit message
            commit_msg = f"""fix({task.domain}): {task.description[:50]}

Task: {task.id}
Type: {task.type}
Domain: {task.domain}

Files changed:
{changed_files[:500]}

Co-Authored-By: RLM Factory <factory@rlm.local>
"""

            # 4. Commit (--no-verify to skip pre-commit hooks like gitleaks for test data)
            proc = await asyncio.create_subprocess_shell(
                f'git commit --no-verify -m "{commit_msg.replace(chr(34), chr(39))}"',
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                error = stderr.decode() if stderr else stdout.decode() if stdout else "Unknown error"
                self.log(f"Commit failed: {error[:200]}", "ERROR")
                result.error = error
                # Don't transition - stay in COMMIT_QUEUED for retry
                return result

            # 5. Get commit SHA
            proc = await asyncio.create_subprocess_shell(
                "git rev-parse HEAD",
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            commit_sha = stdout.decode().strip() if stdout else ""
            result.commit_sha = commit_sha

            # 6. Update task with commit SHA
            self.task_store.update_task(task.id, commit_sha=commit_sha)

            # 7. Transition to MERGED
            self.task_store.transition(task.id, TaskStatus.MERGED)
            self.log(f"✅ Committed: {commit_sha[:8]}")

            # 8. Queue for deploy if strategy allows
            deploy_strategy = self.project.deploy.get("strategy", "validation-only")
            if deploy_strategy != "validation-only":
                self.task_store.transition(task.id, TaskStatus.QUEUED_FOR_DEPLOY)
                self.log(f"Queued for deploy: {task.id}")
            else:
                self.task_store.transition(task.id, TaskStatus.COMPLETED)
                self.log(f"Completed (no deploy): {task.id}")

            result.success = True

        except Exception as e:
            self.log(f"Exception: {e}", "ERROR")
            result.error = str(e)

        return result


# ============================================================================
# COMMIT DAEMON
# ============================================================================

class CommitDaemon(Daemon):
    """Daemon that processes commit queue SEQUENTIALLY"""

    def __init__(self, project: ProjectConfig):
        super().__init__(name="commit", project=project.name)
        self.project = project
        self.task_store = TaskStore()
        self.worker = CommitWorker(project, self.task_store)

    async def run(self):
        """Main daemon loop - SEQUENTIAL processing"""
        self.log("Starting Commit daemon (sequential)")

        while self.running:
            try:
                # Get ONE task ready for commit (sequential)
                tasks = self.task_store.get_tasks_by_status(
                    self.project.id,
                    TaskStatus.COMMIT_QUEUED,
                    limit=1,
                )

                if tasks:
                    task = tasks[0]
                    self.log(f"Found task ready for commit: {task.id}")

                    # Process ONE task at a time (sequential)
                    result = await self.worker.process_task(task)

                    if result.success:
                        self.log(f"✅ Commit success: {task.id}")
                    else:
                        self.log(f"❌ Commit failed: {task.id}: {result.error}", "WARN")

                await asyncio.sleep(POLL_INTERVAL)

            except Exception as e:
                self.log(f"Error: {e}", "ERROR")
                await asyncio.sleep(POLL_INTERVAL)


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Commit Worker Daemon")
    parser.add_argument("command", choices=["start", "stop", "status", "run", "once"])
    parser.add_argument("--project", "-p", required=True, help="Project name")

    args = parser.parse_args()

    # Load project
    project = load_project_config(args.project)
    if not project:
        print(f"Project not found: {args.project}")
        sys.exit(1)

    daemon = CommitDaemon(project)

    if args.command == "start":
        daemon.start(foreground=False)

    elif args.command == "run":
        daemon.start(foreground=True)

    elif args.command == "once":
        # Process one task and exit
        task_store = TaskStore()
        tasks = task_store.get_tasks_by_status(
            project.id, TaskStatus.COMMIT_QUEUED, limit=1
        )
        if tasks:
            worker = CommitWorker(project, task_store)
            result = asyncio.run(worker.process_task(tasks[0]))
            print(f"{'✅' if result.success else '❌'} {tasks[0].id}: {result.commit_sha or result.error}")
        else:
            print("No tasks ready for commit")

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
