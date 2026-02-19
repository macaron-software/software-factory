#!/usr/bin/env python3
"""
Global Build Queue - Cross-Project Singleton

Prevents CPU/IO saturation by serializing build/test jobs across all projects.
Single daemon processes queue, 1 job at a time (configurable).

Usage:
    from core.build_queue import GlobalBuildQueue
    q = GlobalBuildQueue.instance()
    job_id = q.enqueue(project="ppz", cmd="npm test", priority=10)
    result = await q.wait_for(job_id)

CLI:
    factory queue start/stop/status/list/clear
"""

import asyncio
import json
import os
import sqlite3
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.daemon import Daemon


# ============================================================================
# CONFIG
# ============================================================================

DATA_DIR = Path(__file__).parent.parent / "data"
QUEUE_DB = DATA_DIR / "build_queue.db"
DEFAULT_MAX_JOBS = 1  # Sequential by default
DEFAULT_TIMEOUT = 300  # 5 minutes per job
POLL_INTERVAL = 1  # Check queue every second


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class BuildJob:
    """A build/test job in the queue"""
    id: str
    project: str
    cmd: str
    cwd: str
    priority: int = 10  # Higher = first
    timeout: int = DEFAULT_TIMEOUT
    status: JobStatus = JobStatus.PENDING
    created_at: str = ""
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    error: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


# ============================================================================
# QUEUE STORE (SQLite)
# ============================================================================

class QueueStore:
    """SQLite-backed persistent queue"""
    
    _instance = None
    
    def __init__(self, db_path: Path = QUEUE_DB):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    @classmethod
    def instance(cls) -> "QueueStore":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def _init_db(self):
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    project TEXT NOT NULL,
                    cmd TEXT NOT NULL,
                    cwd TEXT NOT NULL,
                    priority INTEGER DEFAULT 10,
                    timeout INTEGER DEFAULT 300,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT,
                    started_at TEXT,
                    finished_at TEXT,
                    exit_code INTEGER,
                    stdout TEXT,
                    stderr TEXT,
                    error TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON jobs(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_priority ON jobs(priority DESC, created_at ASC)")
            conn.commit()
    
    def enqueue(self, job: BuildJob) -> str:
        """Add job to queue"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO jobs (id, project, cmd, cwd, priority, timeout, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (job.id, job.project, job.cmd, job.cwd, job.priority, job.timeout, 
                  job.status.value, job.created_at))
            conn.commit()
        return job.id
    
    def get_next_pending(self) -> Optional[BuildJob]:
        """Get highest priority pending job"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("""
                SELECT * FROM jobs 
                WHERE status = 'pending'
                ORDER BY priority DESC, created_at ASC
                LIMIT 1
            """).fetchone()
            if row:
                return self._row_to_job(row)
        return None
    
    def get_job(self, job_id: str) -> Optional[BuildJob]:
        """Get job by ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if row:
                return self._row_to_job(row)
        return None
    
    def update_status(self, job_id: str, status: JobStatus, **kwargs):
        """Update job status and optional fields"""
        fields = ["status = ?"]
        values = [status.value]
        
        for k, v in kwargs.items():
            fields.append(f"{k} = ?")
            values.append(v)
        
        values.append(job_id)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(f"UPDATE jobs SET {', '.join(fields)} WHERE id = ?", values)
            conn.commit()
    
    def get_running_count(self) -> int:
        """Count currently running jobs"""
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE status = 'running'"
            ).fetchone()[0]
    
    def get_pending_count(self) -> int:
        """Count pending jobs"""
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE status = 'pending'"
            ).fetchone()[0]
    
    def list_jobs(self, status: Optional[JobStatus] = None, limit: int = 50) -> List[BuildJob]:
        """List jobs, optionally filtered by status"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if status:
                rows = conn.execute(
                    "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                    (status.value, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            return [self._row_to_job(r) for r in rows]
    
    def clear_completed(self):
        """Remove completed jobs (success/failed/timeout/cancelled)"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                DELETE FROM jobs 
                WHERE status IN ('success', 'failed', 'timeout', 'cancelled')
            """)
            conn.commit()
    
    def clear_all(self):
        """Remove all jobs"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM jobs")
            conn.commit()
    
    def cancel_pending(self, project: Optional[str] = None):
        """Cancel all pending jobs, optionally for a specific project"""
        with sqlite3.connect(self.db_path) as conn:
            if project:
                conn.execute(
                    "UPDATE jobs SET status = 'cancelled' WHERE status = 'pending' AND project = ?",
                    (project,)
                )
            else:
                conn.execute("UPDATE jobs SET status = 'cancelled' WHERE status = 'pending'")
            conn.commit()
    
    def _row_to_job(self, row: sqlite3.Row) -> BuildJob:
        """Convert DB row to BuildJob"""
        return BuildJob(
            id=row["id"],
            project=row["project"],
            cmd=row["cmd"],
            cwd=row["cwd"],
            priority=row["priority"],
            timeout=row["timeout"],
            status=JobStatus(row["status"]),
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            exit_code=row["exit_code"],
            stdout=row["stdout"] or "",
            stderr=row["stderr"] or "",
            error=row["error"] or "",
        )


# ============================================================================
# GLOBAL BUILD QUEUE (Singleton API)
# ============================================================================

class GlobalBuildQueue:
    """
    Singleton API for enqueueing build jobs.
    
    Jobs are persisted to SQLite and processed by the queue daemon.
    """
    
    _instance = None
    
    def __init__(self):
        self.store = QueueStore.instance()
    
    @classmethod
    def instance(cls) -> "GlobalBuildQueue":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def enqueue(
        self,
        project: str,
        cmd: str,
        cwd: str = ".",
        priority: int = 10,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> str:
        """
        Enqueue a build/test job.
        
        Args:
            project: Project name (ppz, psy, veligo, etc.)
            cmd: Command to execute (npm test, gradle build, pytest, etc.)
            cwd: Working directory for command
            priority: Higher = executed first (default 10)
            timeout: Max execution time in seconds (default 300)
        
        Returns:
            Job ID for tracking
        """
        job = BuildJob(
            id=f"{project}-{uuid.uuid4().hex[:8]}",
            project=project,
            cmd=cmd,
            cwd=cwd,
            priority=priority,
            timeout=timeout,
        )
        return self.store.enqueue(job)
    
    async def wait_for(self, job_id: str, poll_interval: float = 0.5) -> BuildJob:
        """
        Wait for job to complete.
        
        Args:
            job_id: Job ID from enqueue()
            poll_interval: Seconds between status checks
        
        Returns:
            Completed BuildJob with results
        """
        while True:
            job = self.store.get_job(job_id)
            if job is None:
                raise ValueError(f"Job not found: {job_id}")
            
            if job.status in (JobStatus.SUCCESS, JobStatus.FAILED, 
                              JobStatus.TIMEOUT, JobStatus.CANCELLED):
                return job
            
            await asyncio.sleep(poll_interval)
    
    def get_status(self, job_id: str) -> Optional[BuildJob]:
        """Get current job status"""
        return self.store.get_job(job_id)
    
    def cancel(self, job_id: str) -> bool:
        """Cancel a pending job"""
        job = self.store.get_job(job_id)
        if job and job.status == JobStatus.PENDING:
            self.store.update_status(job_id, JobStatus.CANCELLED)
            return True
        return False
    
    def queue_stats(self) -> Dict[str, int]:
        """Get queue statistics"""
        return {
            "pending": self.store.get_pending_count(),
            "running": self.store.get_running_count(),
        }


# ============================================================================
# PROCESS DETECTION (I/O contention prevention)
# ============================================================================

# Patterns to detect running build processes (I/O heavy)
BUILD_PROCESS_PATTERNS = [
    "GradleDaemon",        # Gradle builds (Java/Kotlin)
    "KotlinCompileDaemon", # Kotlin compiler
    "vitest",              # Vitest (TypeScript tests)
    "jest",                # Jest (TypeScript tests)
    "pytest",              # Python tests
    "cargo build",         # Rust builds
    "cargo test",          # Rust tests
    "npm test",            # Node.js tests
    "npm run build",       # Node.js builds
    "tsc",                 # TypeScript compiler
    "swiftc",              # Swift compiler
    "xcodebuild",          # Xcode builds
    "kotlinc",             # Kotlin compiler
]

# Ignore our own queue daemon process
IGNORE_PATTERNS = ["build_queue.py", "factory.py queue"]


def get_running_build_processes() -> List[Dict[str, Any]]:
    """
    Detect running build processes that could cause I/O contention.

    Returns list of {pid, cmd, pattern} for matching processes.
    """
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        processes = []
        for line in result.stdout.split('\n')[1:]:  # Skip header
            if not line.strip():
                continue

            parts = line.split(None, 10)  # Split into max 11 parts
            if len(parts) < 11:
                continue

            pid = parts[1]
            cmd = parts[10]

            # Skip ignored patterns
            if any(ignore in cmd for ignore in IGNORE_PATTERNS):
                continue

            # Check for build patterns
            for pattern in BUILD_PROCESS_PATTERNS:
                if pattern.lower() in cmd.lower():
                    processes.append({
                        "pid": pid,
                        "cmd": cmd[:80],
                        "pattern": pattern,
                    })
                    break

        return processes

    except Exception:
        return []


def wait_for_build_processes(max_wait: int = 60, check_interval: float = 2.0) -> bool:
    """
    Wait for existing build processes to finish before starting new one.

    Args:
        max_wait: Maximum seconds to wait (0 = don't wait)
        check_interval: Seconds between checks

    Returns:
        True if clear to proceed, False if timed out with processes still running
    """
    if max_wait == 0:
        return True

    start = time.time()
    while time.time() - start < max_wait:
        procs = get_running_build_processes()
        if not procs:
            return True

        # Log what we're waiting for
        patterns = set(p["pattern"] for p in procs)
        log(f"⏳ Waiting for {len(procs)} process(es): {', '.join(patterns)}", "DEBUG")

        time.sleep(check_interval)

    return False


# ============================================================================
# QUEUE DAEMON
# ============================================================================

from core.log import get_logger
from core.subprocess_util import run_subprocess

_queue_logger = get_logger("queue")


def log(msg: str, level: str = "INFO"):
    """Log with timestamp"""
    _queue_logger.log(msg, level)


class QueueDaemon(Daemon):
    """
    Daemon that processes the global build queue.
    
    Runs as a single process, executing jobs sequentially (or with limited concurrency).
    """
    
    def __init__(self, max_jobs: int = DEFAULT_MAX_JOBS):
        super().__init__(name="queue", project="global")
        self.max_jobs = max_jobs
        self.store = QueueStore.instance()
        self.current_process: Optional[subprocess.Popen] = None
        self.current_job_id: Optional[str] = None
    
    async def run(self):
        """Main daemon loop"""
        log(f"Starting Build Queue daemon (max_jobs={self.max_jobs})")
        
        while self.running:
            try:
                # Check if we can run more jobs
                running = self.store.get_running_count()
                if running >= self.max_jobs:
                    await asyncio.sleep(POLL_INTERVAL)
                    continue
                
                # Get next job
                job = self.store.get_next_pending()
                if not job:
                    await asyncio.sleep(POLL_INTERVAL)
                    continue
                
                # Process job
                await self._process_job(job)
                
            except Exception as e:
                log(f"Error: {e}", "ERROR")
                await asyncio.sleep(POLL_INTERVAL)
    
    async def _process_job(self, job: BuildJob):
        """Execute a single job"""

        # Check for existing build processes (I/O contention prevention)
        existing = get_running_build_processes()
        if existing:
            patterns = set(p["pattern"] for p in existing)
            log(f"⏳ Waiting for {len(existing)} existing process(es): {', '.join(patterns)}")

            # Wait up to 60s for them to finish
            clear = await asyncio.get_event_loop().run_in_executor(
                None, lambda: wait_for_build_processes(max_wait=60)
            )
            if not clear:
                log(f"⚠ Still {len(get_running_build_processes())} processes running, proceeding anyway", "WARN")

        log(f"▶ Starting: {job.id} | {job.project} | {job.cmd[:50]}...")

        # Mark as running
        started_at = datetime.now().isoformat()
        self.store.update_status(job.id, JobStatus.RUNNING, started_at=started_at)
        self.current_job_id = job.id
        
        try:
            # Load project-specific env vars from config
            job_env = dict(os.environ)
            try:
                from core.project_registry import get_project
                proj_cfg = get_project(job.project)
                if proj_cfg:
                    job_env.update(proj_cfg.get_env())
            except Exception:
                pass  # No project env, use default

            rc, stdout_str, stderr_str = await run_subprocess(
                job.cmd, timeout=job.timeout, cwd=job.cwd, env=job_env, log_fn=log,
            )

            finished_at = datetime.now().isoformat()
            stdout_str = stdout_str[:50000]
            stderr_str = stderr_str[:50000]

            if rc == -1:  # timeout
                self.store.update_status(
                    job.id, JobStatus.TIMEOUT,
                    finished_at=finished_at,
                    error=f"Timeout after {job.timeout}s",
                )
                log(f"⏱ Timeout: {job.id} ({job.timeout}s)", "WARN")
            elif rc == 0:
                self.store.update_status(
                    job.id, JobStatus.SUCCESS,
                    finished_at=finished_at,
                    exit_code=rc,
                    stdout=stdout_str,
                    stderr=stderr_str,
                )
                log(f"✅ Success: {job.id}")
            else:
                self.store.update_status(
                    job.id, JobStatus.FAILED,
                    finished_at=finished_at,
                    exit_code=rc,
                    stdout=stdout_str,
                    stderr=stderr_str,
                )
                log(f"❌ Failed: {job.id} (exit={rc})")
                
        except Exception as e:
            finished_at = datetime.now().isoformat()
            self.store.update_status(
                job.id, JobStatus.FAILED,
                finished_at=finished_at,
                error=str(e),
            )
            log(f"💥 Exception: {job.id} - {e}", "ERROR")
        
        finally:
            self.current_job_id = None
    
    def cleanup(self):
        """Cleanup on shutdown"""
        # Cancel current job if running
        if self.current_job_id:
            self.store.update_status(
                self.current_job_id, 
                JobStatus.CANCELLED,
                error="Daemon shutdown"
            )


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Global Build Queue")
    parser.add_argument("command", choices=["start", "stop", "status", "list", "clear", "stats"])
    parser.add_argument("-j", "--max-jobs", type=int, default=DEFAULT_MAX_JOBS,
                        help=f"Max concurrent jobs (default: {DEFAULT_MAX_JOBS})")
    parser.add_argument("-f", "--foreground", action="store_true",
                        help="Run in foreground (don't daemonize)")
    parser.add_argument("--project", "-p", help="Filter by project (for list/clear)")
    parser.add_argument("--status", "-s", choices=["pending", "running", "success", "failed"],
                        help="Filter by status (for list)")
    parser.add_argument("--all", action="store_true", help="Clear all jobs (not just completed)")
    
    args = parser.parse_args()
    
    if args.command == "start":
        daemon = QueueDaemon(max_jobs=args.max_jobs)
        if args.foreground:
            daemon.start(foreground=True)
        else:
            daemon.start(foreground=False)
            print(f"✅ Queue daemon started (max_jobs={args.max_jobs})")
    
    elif args.command == "stop":
        daemon = QueueDaemon()
        daemon.stop()
        print("⏹ Queue daemon stopped")
    
    elif args.command == "status":
        daemon = QueueDaemon()
        status = daemon.status()
        store = QueueStore.instance()
        
        if status.get("running"):
            print(f"✅ Queue daemon: RUNNING (PID {status.get('pid')})")
        elif status.get("stale"):
            print("❌ Queue daemon: DEAD (stale PID)")
        else:
            print("⚪ Queue daemon: NOT RUNNING")
        
        print(f"📊 Pending: {store.get_pending_count()} | Running: {store.get_running_count()}")
    
    elif args.command == "stats":
        store = QueueStore.instance()
        jobs = store.list_jobs(limit=1000)
        
        by_status = {}
        by_project = {}
        for job in jobs:
            by_status[job.status.value] = by_status.get(job.status.value, 0) + 1
            by_project[job.project] = by_project.get(job.project, 0) + 1
        
        print("📊 Queue Statistics")
        print("─" * 40)
        print("By Status:")
        for s, c in sorted(by_status.items()):
            print(f"  {s}: {c}")
        print("By Project:")
        for p, c in sorted(by_project.items()):
            print(f"  {p}: {c}")
    
    elif args.command == "list":
        store = QueueStore.instance()
        status_filter = JobStatus(args.status) if args.status else None
        jobs = store.list_jobs(status=status_filter, limit=50)
        
        if not jobs:
            print("📭 No jobs in queue")
            return
        
        print(f"{'ID':<25} {'Project':<12} {'Status':<10} {'Command':<30}")
        print("─" * 80)
        for job in jobs:
            cmd_short = job.cmd[:28] + ".." if len(job.cmd) > 30 else job.cmd
            status_icon = {
                "pending": "⏳",
                "running": "▶️",
                "success": "✅",
                "failed": "❌",
                "timeout": "⏱",
                "cancelled": "🚫",
            }.get(job.status.value, "?")
            print(f"{job.id:<25} {job.project:<12} {status_icon} {job.status.value:<8} {cmd_short}")
    
    elif args.command == "clear":
        store = QueueStore.instance()
        if args.all:
            store.clear_all()
            print("🗑 Cleared all jobs")
        else:
            store.clear_completed()
            print("🗑 Cleared completed jobs")


if __name__ == "__main__":
    main()
