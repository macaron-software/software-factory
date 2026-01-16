#!/usr/bin/env python3
"""
SQLite Task Store - Machine à états unifiée pour RLM
====================================================

Store transactionnel pour tous les backlogs:
- Brain RLM tasks
- Wiggum TDD tasks
- Wiggum Deploy tasks
- TMC/Chaos results

États possibles:
  PENDING → IN_PROGRESS → READY_FOR_ADVERSARIAL → MERGED →
  QUEUED_FOR_DEPLOY → STAGING_OK → PERF_SMOKE_OK → PROD_OK

  (ou FAILED à tout moment)

Usage:
    from task_store import TaskStore
    store = TaskStore()
    store.create_task(task_id, domain, ...)
    store.transition(task_id, "IN_PROGRESS", worker_id=1)
"""

import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from enum import Enum
from contextlib import contextmanager
import threading

RLM_DIR = Path(__file__).parent
DB_PATH = RLM_DIR / "task_store.db"

class TaskStatus(Enum):
    """États possibles d'une tâche"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    READY_FOR_ADVERSARIAL = "ready_for_adversarial"
    ADVERSARIAL_FAILED = "adversarial_failed"
    MERGED = "merged"
    QUEUED_FOR_DEPLOY = "queued_for_deploy"
    DEPLOYING_STAGING = "deploying_staging"
    STAGING_OK = "staging_ok"
    STAGING_FAILED = "staging_failed"
    PERF_SMOKE_OK = "perf_smoke_ok"
    PERF_SMOKE_FAILED = "perf_smoke_failed"
    PERF_LOAD_OK = "perf_load_ok"
    PERF_LOAD_FAILED = "perf_load_failed"
    DEPLOYING_PROD = "deploying_prod"
    PROD_OK = "prod_ok"
    PROD_FAILED = "prod_failed"
    COMPLETED = "completed"
    FAILED = "failed"
    DECOMPOSED = "decomposed"  # Fractal: tâche découpée en sous-tâches

# Transitions valides
VALID_TRANSITIONS = {
    TaskStatus.PENDING: [TaskStatus.IN_PROGRESS, TaskStatus.FAILED],
    TaskStatus.IN_PROGRESS: [TaskStatus.READY_FOR_ADVERSARIAL, TaskStatus.FAILED, TaskStatus.DECOMPOSED],
    TaskStatus.READY_FOR_ADVERSARIAL: [TaskStatus.MERGED, TaskStatus.ADVERSARIAL_FAILED],
    TaskStatus.ADVERSARIAL_FAILED: [TaskStatus.IN_PROGRESS, TaskStatus.FAILED],  # Retour wiggum
    TaskStatus.MERGED: [TaskStatus.QUEUED_FOR_DEPLOY],
    TaskStatus.QUEUED_FOR_DEPLOY: [TaskStatus.DEPLOYING_STAGING, TaskStatus.FAILED],
    TaskStatus.DEPLOYING_STAGING: [TaskStatus.STAGING_OK, TaskStatus.STAGING_FAILED],
    TaskStatus.STAGING_FAILED: [TaskStatus.IN_PROGRESS, TaskStatus.FAILED],  # Retour wiggum
    TaskStatus.STAGING_OK: [TaskStatus.PERF_SMOKE_OK, TaskStatus.PERF_SMOKE_FAILED, TaskStatus.DEPLOYING_PROD],
    TaskStatus.PERF_SMOKE_OK: [TaskStatus.PERF_LOAD_OK, TaskStatus.PERF_LOAD_FAILED, TaskStatus.DEPLOYING_PROD],
    TaskStatus.PERF_SMOKE_FAILED: [TaskStatus.IN_PROGRESS, TaskStatus.FAILED],
    TaskStatus.PERF_LOAD_OK: [TaskStatus.DEPLOYING_PROD],
    TaskStatus.PERF_LOAD_FAILED: [TaskStatus.IN_PROGRESS, TaskStatus.FAILED],
    TaskStatus.DEPLOYING_PROD: [TaskStatus.PROD_OK, TaskStatus.PROD_FAILED],
    TaskStatus.PROD_OK: [TaskStatus.COMPLETED],
    TaskStatus.PROD_FAILED: [TaskStatus.IN_PROGRESS, TaskStatus.FAILED],  # Rollback + retry
    TaskStatus.COMPLETED: [],  # État final
    TaskStatus.FAILED: [TaskStatus.PENDING],  # Reset possible
    TaskStatus.DECOMPOSED: [],  # État final (sous-tâches créées)
}


@dataclass
class Task:
    """Représentation d'une tâche"""
    id: str
    domain: str
    description: str
    status: str = "pending"
    priority: float = 0.0
    wsjf_score: float = 0.0
    files: List[str] = None
    parent_task_id: Optional[str] = None  # Pour fractal
    subtask_ids: List[str] = None  # Pour fractal

    # Tracking
    created_at: str = None
    updated_at: str = None
    started_at: str = None
    completed_at: str = None

    # Worker/Agent info
    locked_by: Optional[int] = None
    lock_expires_at: Optional[str] = None
    attempt_count: int = 0
    max_attempts: int = 3

    # Artifacts
    commit_sha: Optional[str] = None
    artifact_id: Optional[str] = None
    branch_name: Optional[str] = None

    # Results
    last_error: Optional[str] = None
    e2e_run_id: Optional[str] = None
    perf_results: Optional[str] = None  # JSON
    adversarial_findings: Optional[str] = None  # JSON

    # Context (enriched by Brain)
    file_content: Optional[str] = None
    imports: List[str] = None
    types_defined: List[str] = None
    error_context: Optional[str] = None  # JSON
    test_example: Optional[str] = None
    conventions: Optional[str] = None  # JSON

    # Tags
    tags: List[str] = None  # perf-risk, db-risk, critical-path, etc.

    def __post_init__(self):
        if self.files is None:
            self.files = []
        if self.subtask_ids is None:
            self.subtask_ids = []
        if self.imports is None:
            self.imports = []
        if self.types_defined is None:
            self.types_defined = []
        if self.tags is None:
            self.tags = []
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if self.updated_at is None:
            self.updated_at = self.created_at


class TaskStore:
    """Store SQLite transactionnel pour les tâches RLM"""

    _local = threading.local()

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _get_connection(self):
        """Thread-safe connection management"""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                str(self.db_path),
                timeout=30.0,
                isolation_level='IMMEDIATE'
            )
            self._local.conn.row_factory = sqlite3.Row
        try:
            yield self._local.conn
        except Exception:
            self._local.conn.rollback()
            raise

    def _init_db(self):
        """Initialize database schema"""
        with self._get_connection() as conn:
            conn.executescript("""
                -- Main tasks table
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    domain TEXT NOT NULL,
                    description TEXT,
                    status TEXT DEFAULT 'pending',
                    priority REAL DEFAULT 0.0,
                    wsjf_score REAL DEFAULT 0.0,
                    files TEXT,  -- JSON array
                    parent_task_id TEXT,
                    subtask_ids TEXT,  -- JSON array

                    created_at TEXT,
                    updated_at TEXT,
                    started_at TEXT,
                    completed_at TEXT,

                    locked_by INTEGER,
                    lock_expires_at TEXT,
                    attempt_count INTEGER DEFAULT 0,
                    max_attempts INTEGER DEFAULT 3,

                    commit_sha TEXT,
                    artifact_id TEXT,
                    branch_name TEXT,

                    last_error TEXT,
                    e2e_run_id TEXT,
                    perf_results TEXT,
                    adversarial_findings TEXT,

                    file_content TEXT,
                    imports TEXT,
                    types_defined TEXT,
                    error_context TEXT,
                    test_example TEXT,
                    conventions TEXT,

                    tags TEXT  -- JSON array
                );

                -- Status history for audit
                CREATE TABLE IF NOT EXISTS task_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    from_status TEXT,
                    to_status TEXT NOT NULL,
                    changed_at TEXT NOT NULL,
                    changed_by TEXT,  -- worker_id, agent name, etc.
                    metadata TEXT,  -- JSON
                    FOREIGN KEY (task_id) REFERENCES tasks(id)
                );

                -- Performance results
                CREATE TABLE IF NOT EXISTS perf_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    test_type TEXT NOT NULL,  -- smoke, load, stress
                    run_at TEXT NOT NULL,
                    duration_ms INTEGER,
                    passed INTEGER,
                    p50_ms REAL,
                    p95_ms REAL,
                    p99_ms REAL,
                    error_rate REAL,
                    throughput_rps REAL,
                    details TEXT,  -- JSON
                    FOREIGN KEY (task_id) REFERENCES tasks(id)
                );

                -- Chaos test results
                CREATE TABLE IF NOT EXISTS chaos_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT,
                    chaos_type TEXT NOT NULL,  -- network, db, service
                    run_at TEXT NOT NULL,
                    target TEXT,
                    duration_ms INTEGER,
                    impact TEXT,  -- JSON
                    recovery_time_ms INTEGER,
                    passed INTEGER,
                    FOREIGN KEY (task_id) REFERENCES tasks(id)
                );

                -- Indexes
                CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
                CREATE INDEX IF NOT EXISTS idx_tasks_domain ON tasks(domain);
                CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_task_id);
                CREATE INDEX IF NOT EXISTS idx_tasks_wsjf ON tasks(wsjf_score DESC);
                CREATE INDEX IF NOT EXISTS idx_history_task ON task_history(task_id);
            """)
            conn.commit()

    def create_task(self, task: Task) -> str:
        """Create a new task"""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO tasks (
                    id, domain, description, status, priority, wsjf_score,
                    files, parent_task_id, subtask_ids, created_at, updated_at,
                    attempt_count, max_attempts, file_content, imports,
                    types_defined, error_context, test_example, conventions, tags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.id, task.domain, task.description, task.status,
                task.priority, task.wsjf_score,
                json.dumps(task.files), task.parent_task_id,
                json.dumps(task.subtask_ids), task.created_at, task.updated_at,
                task.attempt_count, task.max_attempts, task.file_content,
                json.dumps(task.imports), json.dumps(task.types_defined),
                task.error_context, task.test_example, task.conventions,
                json.dumps(task.tags)
            ))

            # Record creation in history
            conn.execute("""
                INSERT INTO task_history (task_id, to_status, changed_at, changed_by)
                VALUES (?, ?, ?, ?)
            """, (task.id, task.status, task.created_at, "brain"))

            conn.commit()
        return task.id

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID"""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if row:
                return self._row_to_task(row)
        return None

    def _row_to_task(self, row: sqlite3.Row) -> Task:
        """Convert database row to Task object"""
        return Task(
            id=row['id'],
            domain=row['domain'],
            description=row['description'],
            status=row['status'],
            priority=row['priority'] or 0.0,
            wsjf_score=row['wsjf_score'] or 0.0,
            files=json.loads(row['files'] or '[]'),
            parent_task_id=row['parent_task_id'],
            subtask_ids=json.loads(row['subtask_ids'] or '[]'),
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            started_at=row['started_at'],
            completed_at=row['completed_at'],
            locked_by=row['locked_by'],
            lock_expires_at=row['lock_expires_at'],
            attempt_count=row['attempt_count'] or 0,
            max_attempts=row['max_attempts'] or 3,
            commit_sha=row['commit_sha'],
            artifact_id=row['artifact_id'],
            branch_name=row['branch_name'],
            last_error=row['last_error'],
            e2e_run_id=row['e2e_run_id'],
            perf_results=row['perf_results'],
            adversarial_findings=row['adversarial_findings'],
            file_content=row['file_content'],
            imports=json.loads(row['imports'] or '[]'),
            types_defined=json.loads(row['types_defined'] or '[]'),
            error_context=row['error_context'],
            test_example=row['test_example'],
            conventions=row['conventions'],
            tags=json.loads(row['tags'] or '[]'),
        )

    def transition(self, task_id: str, new_status: str,
                   changed_by: str = None, metadata: dict = None,
                   **updates) -> bool:
        """
        Transition a task to a new status with validation.
        Returns True if successful, False if invalid transition.
        """
        with self._get_connection() as conn:
            # Get current status
            row = conn.execute(
                "SELECT status FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if not row:
                return False

            current_status = TaskStatus(row['status'])
            try:
                target_status = TaskStatus(new_status)
            except ValueError:
                return False

            # Validate transition
            if target_status not in VALID_TRANSITIONS.get(current_status, []):
                print(f"Invalid transition: {current_status.value} → {target_status.value}")
                return False

            now = datetime.now().isoformat()

            # Build update query
            update_fields = ["status = ?", "updated_at = ?"]
            update_values = [target_status.value, now]

            if target_status == TaskStatus.IN_PROGRESS:
                update_fields.append("started_at = COALESCE(started_at, ?)")
                update_values.append(now)
                update_fields.append("attempt_count = attempt_count + 1")

            if target_status in [TaskStatus.COMPLETED, TaskStatus.PROD_OK]:
                update_fields.append("completed_at = ?")
                update_values.append(now)

            # Apply additional updates
            for key, value in updates.items():
                if key in ['commit_sha', 'artifact_id', 'branch_name',
                          'last_error', 'e2e_run_id', 'perf_results',
                          'adversarial_findings', 'locked_by', 'lock_expires_at']:
                    update_fields.append(f"{key} = ?")
                    update_values.append(value)

            update_values.append(task_id)

            conn.execute(
                f"UPDATE tasks SET {', '.join(update_fields)} WHERE id = ?",
                update_values
            )

            # Record in history
            conn.execute("""
                INSERT INTO task_history (task_id, from_status, to_status, changed_at, changed_by, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (task_id, current_status.value, target_status.value, now,
                  changed_by, json.dumps(metadata) if metadata else None))

            conn.commit()
        return True

    def get_pending_tasks(self, limit: int = 10, domain: str = None,
                          exclude_locked: bool = True) -> List[Task]:
        """Get pending tasks sorted by WSJF priority"""
        with self._get_connection() as conn:
            query = "SELECT * FROM tasks WHERE status = 'pending'"
            params = []

            if domain:
                query += " AND domain = ?"
                params.append(domain)

            if exclude_locked:
                query += " AND (locked_by IS NULL OR lock_expires_at < ?)"
                params.append(datetime.now().isoformat())

            query += " ORDER BY wsjf_score DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(query, params).fetchall()
            return [self._row_to_task(row) for row in rows]

    def lock_task(self, task_id: str, worker_id: int,
                  lock_duration_seconds: int = 3600) -> bool:
        """Lock a task for a worker"""
        with self._get_connection() as conn:
            now = datetime.now()
            expires = datetime.fromtimestamp(
                now.timestamp() + lock_duration_seconds
            ).isoformat()

            result = conn.execute("""
                UPDATE tasks
                SET locked_by = ?, lock_expires_at = ?, updated_at = ?
                WHERE id = ? AND (locked_by IS NULL OR lock_expires_at < ?)
            """, (worker_id, expires, now.isoformat(), task_id, now.isoformat()))

            conn.commit()
            return result.rowcount > 0

    def unlock_task(self, task_id: str):
        """Unlock a task"""
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE tasks SET locked_by = NULL, lock_expires_at = NULL
                WHERE id = ?
            """, (task_id,))
            conn.commit()

    def decompose_task(self, parent_task_id: str, subtasks: List[Task]) -> List[str]:
        """
        Fractal decomposition: mark parent as DECOMPOSED and create subtasks.
        Returns list of created subtask IDs.
        """
        with self._get_connection() as conn:
            subtask_ids = []

            for subtask in subtasks:
                subtask.parent_task_id = parent_task_id
                self.create_task(subtask)
                subtask_ids.append(subtask.id)

            # Update parent
            conn.execute("""
                UPDATE tasks
                SET status = 'decomposed',
                    subtask_ids = ?,
                    updated_at = ?
                WHERE id = ?
            """, (json.dumps(subtask_ids), datetime.now().isoformat(), parent_task_id))

            # Record in history
            conn.execute("""
                INSERT INTO task_history (task_id, from_status, to_status, changed_at, changed_by, metadata)
                VALUES (?, 'in_progress', 'decomposed', ?, 'fractal', ?)
            """, (parent_task_id, datetime.now().isoformat(),
                  json.dumps({"subtask_count": len(subtasks), "subtask_ids": subtask_ids})))

            conn.commit()

        return subtask_ids

    def record_perf_result(self, task_id: str, test_type: str,
                          passed: bool, duration_ms: int,
                          p50_ms: float = None, p95_ms: float = None,
                          p99_ms: float = None, error_rate: float = None,
                          throughput_rps: float = None, details: dict = None):
        """Record performance test results"""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO perf_results (
                    task_id, test_type, run_at, duration_ms, passed,
                    p50_ms, p95_ms, p99_ms, error_rate, throughput_rps, details
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (task_id, test_type, datetime.now().isoformat(), duration_ms,
                  1 if passed else 0, p50_ms, p95_ms, p99_ms, error_rate,
                  throughput_rps, json.dumps(details) if details else None))
            conn.commit()

    def record_chaos_result(self, chaos_type: str, target: str,
                           duration_ms: int, passed: bool,
                           recovery_time_ms: int = None,
                           impact: dict = None, task_id: str = None):
        """Record chaos test results"""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO chaos_results (
                    task_id, chaos_type, run_at, target, duration_ms,
                    impact, recovery_time_ms, passed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (task_id, chaos_type, datetime.now().isoformat(), target,
                  duration_ms, json.dumps(impact) if impact else None,
                  recovery_time_ms, 1 if passed else 0))
            conn.commit()

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about tasks"""
        with self._get_connection() as conn:
            stats = {}

            # By status
            rows = conn.execute("""
                SELECT status, COUNT(*) as count FROM tasks GROUP BY status
            """).fetchall()
            stats['by_status'] = {row['status']: row['count'] for row in rows}

            # By domain
            rows = conn.execute("""
                SELECT domain, COUNT(*) as count FROM tasks GROUP BY domain
            """).fetchall()
            stats['by_domain'] = {row['domain']: row['count'] for row in rows}

            # Total
            row = conn.execute("SELECT COUNT(*) as total FROM tasks").fetchone()
            stats['total'] = row['total']

            # Completed
            completed = stats['by_status'].get('completed', 0)
            stats['completed'] = completed
            stats['progress_pct'] = (completed / stats['total'] * 100) if stats['total'] > 0 else 0

            # Decomposed (fractal)
            stats['decomposed'] = stats['by_status'].get('decomposed', 0)

            # Failed
            stats['failed'] = stats['by_status'].get('failed', 0)

            return stats

    def import_from_json(self, json_path: Path):
        """Import tasks from legacy JSON backlog"""
        with open(json_path) as f:
            data = json.load(f)

        for t in data.get('tasks', []):
            task = Task(
                id=t.get('id', ''),
                domain=t.get('domain', 'unknown'),
                description=t.get('description', ''),
                status=t.get('status', 'pending'),
                priority=t.get('priority', 0),
                wsjf_score=t.get('wsjf_score', 0),
                files=t.get('files', []),
                file_content=t.get('file_content'),
                imports=t.get('imports', []),
                types_defined=t.get('types_defined', []),
                error_context=json.dumps(t.get('error_context')) if t.get('error_context') else None,
                test_example=t.get('test_example'),
                conventions=json.dumps(t.get('conventions')) if t.get('conventions') else None,
                tags=t.get('tags', []),
            )

            try:
                self.create_task(task)
            except sqlite3.IntegrityError:
                # Task already exists, skip
                pass

        print(f"Imported tasks from {json_path}")

    def export_to_json(self, json_path: Path):
        """Export tasks to JSON format"""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM tasks").fetchall()

        tasks = []
        for row in rows:
            task = self._row_to_task(row)
            tasks.append(asdict(task))

        data = {
            "tasks": tasks,
            "exported_at": datetime.now().isoformat(),
            "stats": self.get_stats()
        }

        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"Exported {len(tasks)} tasks to {json_path}")


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RLM Task Store")
    parser.add_argument("command", choices=["stats", "import", "export", "pending"])
    parser.add_argument("--json", type=str, help="JSON file path")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--domain", type=str)
    args = parser.parse_args()

    store = TaskStore()

    if args.command == "stats":
        stats = store.get_stats()
        print("=== TASK STORE STATS ===")
        print(f"Total: {stats['total']}")
        print(f"Completed: {stats['completed']} ({stats['progress_pct']:.1f}%)")
        print(f"Decomposed (fractal): {stats['decomposed']}")
        print(f"Failed: {stats['failed']}")
        print("\nBy status:")
        for status, count in sorted(stats['by_status'].items()):
            print(f"  {status}: {count}")
        print("\nBy domain:")
        for domain, count in sorted(stats['by_domain'].items()):
            print(f"  {domain}: {count}")

    elif args.command == "import":
        if not args.json:
            print("Error: --json required for import")
        else:
            store.import_from_json(Path(args.json))

    elif args.command == "export":
        if not args.json:
            print("Error: --json required for export")
        else:
            store.export_to_json(Path(args.json))

    elif args.command == "pending":
        tasks = store.get_pending_tasks(limit=args.limit, domain=args.domain)
        print(f"=== PENDING TASKS ({len(tasks)}) ===")
        for t in tasks:
            print(f"  [{t.domain}] {t.id} (WSJF: {t.wsjf_score:.2f})")
