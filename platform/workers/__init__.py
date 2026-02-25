"""SQLite-backed async job queue — deports phase execution from the FastAPI process.

No Redis needed. Uses SQLite atomic UPDATE with WHERE for claim semantics.

Usage:
    queue = JobQueue()
    job_id = queue.enqueue("phase_exec", {"mission_id": "m-1", "phase": "design"})
    job = queue.claim(worker_id="worker-1")  # atomic claim
    queue.complete(job.id, result={"output": "..."})
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "platform.db"

# Job statuses
PENDING = "pending"
CLAIMED = "claimed"
RUNNING = "running"
COMPLETED = "completed"
FAILED = "failed"
CANCELLED = "cancelled"


@dataclass
class Job:
    """A queued job."""

    id: str = ""
    job_type: str = ""
    payload: dict = field(default_factory=dict)
    status: str = PENDING
    priority: int = 0  # higher = more urgent
    claimed_by: str = ""
    result: dict = field(default_factory=dict)
    error: str = ""
    created_at: float = 0.0
    claimed_at: float = 0.0
    completed_at: float = 0.0
    max_retries: int = 3
    retry_count: int = 0

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = time.time()


def _ensure_table(db: sqlite3.Connection) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS job_queue (
            id           TEXT PRIMARY KEY,
            job_type     TEXT NOT NULL,
            payload      TEXT DEFAULT '{}',
            status       TEXT DEFAULT 'pending',
            priority     INTEGER DEFAULT 0,
            claimed_by   TEXT DEFAULT '',
            result       TEXT DEFAULT '{}',
            error        TEXT DEFAULT '',
            created_at   REAL NOT NULL,
            claimed_at   REAL DEFAULT 0,
            completed_at REAL DEFAULT 0,
            max_retries  INTEGER DEFAULT 3,
            retry_count  INTEGER DEFAULT 0
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_job_status ON job_queue(status, priority DESC, created_at)")


class JobQueue:
    """SQLite-backed job queue with atomic claim semantics."""

    def __init__(self, db_path: Path | str | None = None):
        self._db_path = Path(db_path) if db_path else _DB_PATH
        self._initialized = False

    def _db(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self._db_path))
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        if not self._initialized:
            _ensure_table(db)
            self._initialized = True
        return db

    def enqueue(
        self,
        job_type: str,
        payload: dict | None = None,
        priority: int = 0,
        max_retries: int = 3,
    ) -> str:
        """Add a job to the queue. Returns job ID."""
        job = Job(job_type=job_type, payload=payload or {}, priority=priority, max_retries=max_retries)
        db = self._db()
        try:
            db.execute(
                "INSERT INTO job_queue (id, job_type, payload, status, priority, created_at, max_retries) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (job.id, job.job_type, json.dumps(job.payload), PENDING, priority, job.created_at, max_retries),
            )
            db.commit()
            return job.id
        finally:
            db.close()

    def claim(self, worker_id: str, job_types: list[str] | None = None) -> Job | None:
        """Atomically claim the highest-priority pending job. Returns None if queue empty."""
        db = self._db()
        try:
            type_filter = ""
            params: list = []
            if job_types:
                placeholders = ",".join("?" for _ in job_types)
                type_filter = f"AND job_type IN ({placeholders})"
                params.extend(job_types)

            # Atomic: SELECT + UPDATE in one transaction
            row = db.execute(
                f"SELECT id FROM job_queue WHERE status = 'pending' {type_filter} "
                "ORDER BY priority DESC, created_at ASC LIMIT 1",
                params,
            ).fetchone()

            if row is None:
                return None

            now = time.time()
            db.execute(
                "UPDATE job_queue SET status = ?, claimed_by = ?, claimed_at = ? WHERE id = ? AND status = 'pending'",
                (CLAIMED, worker_id, now, row["id"]),
            )
            db.commit()

            # Re-read the full job
            full = db.execute("SELECT * FROM job_queue WHERE id = ?", (row["id"],)).fetchone()
            if full is None or full["status"] != CLAIMED:
                return None  # Race condition: another worker claimed it

            return self._row_to_job(full)
        finally:
            db.close()

    def complete(self, job_id: str, result: dict | None = None) -> None:
        """Mark a job as completed."""
        db = self._db()
        try:
            db.execute(
                "UPDATE job_queue SET status = ?, result = ?, completed_at = ? WHERE id = ?",
                (COMPLETED, json.dumps(result or {}), time.time(), job_id),
            )
            db.commit()
        finally:
            db.close()

    def fail(self, job_id: str, error: str = "") -> bool:
        """Mark a job as failed. Returns True if it should be retried."""
        db = self._db()
        try:
            row = db.execute("SELECT retry_count, max_retries FROM job_queue WHERE id = ?", (job_id,)).fetchone()
            if row and row["retry_count"] < row["max_retries"]:
                db.execute(
                    "UPDATE job_queue SET status = 'pending', retry_count = retry_count + 1, "
                    "error = ?, claimed_by = '' WHERE id = ?",
                    (error, job_id),
                )
                db.commit()
                return True  # Will be retried
            else:
                db.execute(
                    "UPDATE job_queue SET status = ?, error = ?, completed_at = ? WHERE id = ?",
                    (FAILED, error, time.time(), job_id),
                )
                db.commit()
                return False  # Permanently failed
        finally:
            db.close()

    def cancel(self, job_id: str) -> None:
        """Cancel a pending or claimed job."""
        db = self._db()
        try:
            db.execute(
                "UPDATE job_queue SET status = ? WHERE id = ? AND status IN ('pending', 'claimed')",
                (CANCELLED, job_id),
            )
            db.commit()
        finally:
            db.close()

    def get(self, job_id: str) -> Job | None:
        """Get a job by ID."""
        db = self._db()
        try:
            row = db.execute("SELECT * FROM job_queue WHERE id = ?", (job_id,)).fetchone()
            return self._row_to_job(row) if row else None
        finally:
            db.close()

    def stats(self) -> dict:
        """Queue statistics."""
        db = self._db()
        try:
            rows = db.execute("SELECT status, COUNT(*) FROM job_queue GROUP BY status").fetchall()
            by_status = dict(rows)
            total = sum(by_status.values())
            return {"total": total, **by_status}
        finally:
            db.close()

    def cleanup(self, older_than_hours: int = 24) -> int:
        """Remove completed/failed jobs older than N hours."""
        cutoff = time.time() - (older_than_hours * 3600)
        db = self._db()
        try:
            cur = db.execute(
                "DELETE FROM job_queue WHERE status IN ('completed', 'failed', 'cancelled') AND completed_at < ?",
                (cutoff,),
            )
            db.commit()
            return cur.rowcount
        finally:
            db.close()

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> Job:
        return Job(
            id=row["id"],
            job_type=row["job_type"],
            payload=json.loads(row["payload"]) if row["payload"] else {},
            status=row["status"],
            priority=row["priority"],
            claimed_by=row["claimed_by"],
            result=json.loads(row["result"]) if row["result"] else {},
            error=row["error"],
            created_at=row["created_at"],
            claimed_at=row["claimed_at"],
            completed_at=row["completed_at"],
            max_retries=row["max_retries"],
            retry_count=row["retry_count"],
        )
