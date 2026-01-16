#!/usr/bin/env python3
"""
Task Store - SQLite + zlib compression for Software Factory
============================================================
Conforme MIT CSAIL arXiv:2512.24601 (Recursive Language Models)

Store transactionnel unifié pour tous les projets:
- Multi-projet avec project_id
- Compression zlib pour les contextes JSON volumineux
- Support FRACTAL (parent_id pour sous-tâches)
- Audit trail (attempts, deployments)

Usage:
    from core.task_store import TaskStore, Task
    store = TaskStore()
    store.create_project("ppz", "/path/to/ppz.yaml", "/path/to/project")
    store.create_task(Task(id="T001", project_id="ppz", ...))
"""

import sqlite3
import json
import zlib
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from contextlib import contextmanager
import threading

# Default DB path
DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "factory.db"


class TaskStatus(Enum):
    """Task states following the RLM pipeline"""
    # Initial
    PENDING = "pending"

    # TDD Queue
    LOCKED = "locked"
    TDD_IN_PROGRESS = "tdd_in_progress"
    TDD_SUCCESS = "tdd_success"
    TDD_FAILED = "tdd_failed"  # TDD cycle failed after max retries

    # Adversarial Gate
    ADVERSARIAL_REJECTED = "adversarial_rejected"

    # Git
    MERGED = "merged"

    # Deploy Queue
    QUEUED_FOR_DEPLOY = "queued_for_deploy"
    DEPLOYING_STAGING = "deploying_staging"
    STAGING_OK = "staging_ok"
    STAGING_FAILED = "staging_failed"
    PERF_SMOKE_OK = "perf_smoke_ok"
    PERF_SMOKE_FAILED = "perf_smoke_failed"
    E2E_JOURNEYS_OK = "e2e_journeys_ok"  # E2E journeys passed
    E2E_JOURNEYS_FAILED = "e2e_journeys_failed"  # E2E journeys failed
    CHAOS_OK = "chaos_ok"  # Chaos monkey passed
    CHAOS_FAILED = "chaos_failed"  # Chaos monkey failed
    LOAD_OK = "load_ok"  # Load testing passed
    LOAD_FAILED = "load_failed"  # Load testing failed
    DEPLOYING_PROD = "deploying_prod"
    PROD_OK = "prod_ok"
    PROD_FAILED = "prod_failed"

    # Final states
    COMPLETED = "completed"
    DEPLOYED = "deployed"  # Successfully deployed to production
    FAILED = "failed"
    DEPLOY_FAILED = "deploy_failed"  # Deploy pipeline failed after max retries
    BLOCKED = "blocked"  # Escalated to Brain
    DECOMPOSED = "decomposed"  # FRACTAL: split into subtasks


# Valid state transitions
# Flow: Wiggum TDD → Adversarial Gate → (if OK) → Deploy Queue
VALID_TRANSITIONS = {
    # TDD Queue
    TaskStatus.PENDING: [TaskStatus.LOCKED, TaskStatus.FAILED],
    TaskStatus.LOCKED: [TaskStatus.TDD_IN_PROGRESS, TaskStatus.PENDING],
    TaskStatus.TDD_IN_PROGRESS: [TaskStatus.TDD_SUCCESS, TaskStatus.TDD_FAILED, TaskStatus.DECOMPOSED],
    TaskStatus.TDD_SUCCESS: [TaskStatus.ADVERSARIAL_REJECTED, TaskStatus.MERGED],
    TaskStatus.TDD_FAILED: [TaskStatus.PENDING, TaskStatus.BLOCKED],  # Retry or escalate

    # Adversarial Gate
    TaskStatus.ADVERSARIAL_REJECTED: [TaskStatus.TDD_IN_PROGRESS, TaskStatus.BLOCKED],
    TaskStatus.MERGED: [TaskStatus.QUEUED_FOR_DEPLOY, TaskStatus.COMPLETED],  # COMPLETED if deploy disabled

    # Deploy Queue - Full pipeline (or DEPLOYED for validation-only)
    TaskStatus.QUEUED_FOR_DEPLOY: [TaskStatus.DEPLOYING_STAGING, TaskStatus.DEPLOY_FAILED, TaskStatus.DEPLOYED],
    TaskStatus.DEPLOYING_STAGING: [TaskStatus.STAGING_OK, TaskStatus.STAGING_FAILED],
    TaskStatus.STAGING_FAILED: [TaskStatus.QUEUED_FOR_DEPLOY, TaskStatus.DEPLOY_FAILED],  # Retry or fail

    # Smoke tests
    TaskStatus.STAGING_OK: [TaskStatus.PERF_SMOKE_OK, TaskStatus.PERF_SMOKE_FAILED, TaskStatus.E2E_JOURNEYS_OK],
    TaskStatus.PERF_SMOKE_OK: [TaskStatus.E2E_JOURNEYS_OK, TaskStatus.E2E_JOURNEYS_FAILED],
    TaskStatus.PERF_SMOKE_FAILED: [TaskStatus.QUEUED_FOR_DEPLOY, TaskStatus.DEPLOY_FAILED],

    # E2E Journeys (real UI tests)
    TaskStatus.E2E_JOURNEYS_OK: [TaskStatus.CHAOS_OK, TaskStatus.DEPLOYING_PROD],  # Chaos optional
    TaskStatus.E2E_JOURNEYS_FAILED: [TaskStatus.QUEUED_FOR_DEPLOY, TaskStatus.DEPLOY_FAILED],

    # Chaos Monkey (optional)
    TaskStatus.CHAOS_OK: [TaskStatus.LOAD_OK, TaskStatus.DEPLOYING_PROD],  # Load optional
    TaskStatus.CHAOS_FAILED: [TaskStatus.QUEUED_FOR_DEPLOY, TaskStatus.DEPLOY_FAILED],

    # Load Testing (optional)
    TaskStatus.LOAD_OK: [TaskStatus.DEPLOYING_PROD],
    TaskStatus.LOAD_FAILED: [TaskStatus.QUEUED_FOR_DEPLOY, TaskStatus.DEPLOY_FAILED],

    # Production deployment
    TaskStatus.DEPLOYING_PROD: [TaskStatus.PROD_OK, TaskStatus.PROD_FAILED],
    TaskStatus.PROD_OK: [TaskStatus.DEPLOYED, TaskStatus.COMPLETED],
    TaskStatus.PROD_FAILED: [TaskStatus.QUEUED_FOR_DEPLOY, TaskStatus.DEPLOY_FAILED],

    # Final states
    TaskStatus.COMPLETED: [],
    TaskStatus.DEPLOYED: [],  # Final: successfully in production
    TaskStatus.FAILED: [TaskStatus.PENDING],  # Can be reset by Brain
    TaskStatus.DEPLOY_FAILED: [TaskStatus.PENDING],  # Creates feedback task, can be reset
    TaskStatus.BLOCKED: [TaskStatus.PENDING],  # Brain can reset
    TaskStatus.DECOMPOSED: [],  # Final (subtasks created)
}


@dataclass
class Task:
    """Task representation with zlib-compressed context"""
    id: str
    project_id: str
    domain: str
    description: str
    type: str = "fix"  # fix|feature|refactor|test
    status: str = "pending"
    priority: int = 0
    wsjf_score: float = 0.0

    # Files
    files: List[str] = field(default_factory=list)

    # FRACTAL support
    parent_id: Optional[str] = None
    depth: int = 0  # Fractal depth level

    # Tracking
    created_at: str = None
    updated_at: str = None
    completed_at: str = None

    # Locking
    locked_by: Optional[str] = None
    lock_expires_at: Optional[str] = None

    # Attempts counter
    tdd_attempts: int = 0
    adversarial_attempts: int = 0
    staging_attempts: int = 0
    prod_attempts: int = 0

    # Git
    commit_sha: Optional[str] = None

    # Context (will be compressed with zlib)
    context: Optional[Dict[str, Any]] = None

    # Error info
    last_error: Optional[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if self.updated_at is None:
            self.updated_at = self.created_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary"""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "parent_id": self.parent_id,
            "type": self.type,
            "domain": self.domain,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "wsjf_score": self.wsjf_score,
            "depth": self.depth,
            "files": self.files,
            "context": self.context,
            "locked_by": self.locked_by,
            "lock_expires_at": self.lock_expires_at,
            "tdd_attempts": self.tdd_attempts,
            "adversarial_attempts": self.adversarial_attempts,
            "staging_attempts": self.staging_attempts,
            "prod_attempts": self.prod_attempts,
            "commit_sha": self.commit_sha,
            "last_error": self.last_error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
        }

    def get_context(self) -> Optional[Dict[str, Any]]:
        """Get context dictionary"""
        return self.context


@dataclass
class Attempt:
    """Record of a task attempt"""
    task_id: str
    attempt_num: int
    stage: str  # tdd|adversarial|staging|prod
    verdict: str  # approved|rejected|failed|success
    issues: Optional[List[Dict]] = None
    response: Optional[str] = None
    created_at: str = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()


@dataclass
class Deployment:
    """Deployment record"""
    task_id: str
    env: str  # staging|prod
    status: str  # pending|success|failed|rolled_back
    commit_sha: Optional[str] = None
    evidence_path: Optional[str] = None
    created_at: str = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()


# ============================================================================
# AGGRESSIVE CONTEXT COMPRESSION
# ============================================================================

# Abbréviations sémantiques (sans grammaire, max compression)
SEMANTIC_ABBREVS = {
    # Common words → short
    "function": "fn",
    "implement": "impl",
    "implementation": "impl",
    "parameter": "p",
    "parameters": "ps",
    "return": "ret",
    "returns": "rets",
    "error": "err",
    "errors": "errs",
    "string": "str",
    "number": "num",
    "boolean": "bool",
    "object": "obj",
    "array": "arr",
    "undefined": "undef",
    "interface": "iface",
    "component": "comp",
    "components": "comps",
    "configuration": "cfg",
    "config": "cfg",
    "authentication": "auth",
    "authorization": "authz",
    "database": "db",
    "message": "msg",
    "messages": "msgs",
    "request": "req",
    "response": "res",
    "callback": "cb",
    "async": "async",
    "await": "await",
    "promise": "prom",
    "template": "tpl",
    "application": "app",
    "environment": "env",
    "development": "dev",
    "production": "prod",
    "directory": "dir",
    "file": "f",
    "files": "fs",
    "path": "p",
    "context": "ctx",
    "description": "desc",
    "example": "ex",
    "expected": "exp",
    "received": "rcv",
    "argument": "arg",
    "arguments": "args",
    "property": "prop",
    "properties": "props",
    "attribute": "attr",
    "attributes": "attrs",
    "element": "el",
    "elements": "els",
    "container": "ctnr",
    "wrapper": "wrap",
    "handler": "hndlr",
    "listener": "lstnr",
    "controller": "ctrl",
    "service": "svc",
    "repository": "repo",
    "factory": "fac",
    "builder": "bldr",
    "manager": "mgr",
    "provider": "prvdr",
    "consumer": "csmr",
    "producer": "prdcr",
    "subscriber": "sub",
    "publisher": "pub",
    "middleware": "mw",
    "validation": "val",
    "validator": "valr",
    "serialization": "ser",
    "deserialization": "deser",
    "encryption": "enc",
    "decryption": "dec",
    "connection": "conn",
    "transaction": "tx",
    "query": "q",
    "mutation": "mut",
    "subscription": "sub",
    "notification": "notif",
    "permissions": "perms",
    "successfully": "ok",
    "successfully created": "created",
    "successfully updated": "updated",
    "successfully deleted": "deleted",
    "should": "",  # remove filler
    "please": "",
    "the following": "",
    "in order to": "to",
    "make sure": "",
    "ensure that": "",
    "however": "",
    "therefore": "",
    "additionally": "+",
    "furthermore": "+",
    "nevertheless": "",
    "consequently": "→",
    "implementation details": "impl",
    "for example": "eg",
    "such as": "eg",
    "that is": "ie",
    "in other words": "ie",
}

# Remove verbose phrases
REMOVE_PHRASES = [
    "This function ",
    "This method ",
    "This component ",
    "The purpose of ",
    "It is important to note that ",
    "As mentioned earlier, ",
    "As you can see, ",
    "In this case, ",
    "At this point, ",
    "Going forward, ",
    "With that being said, ",
    "It should be noted that ",
    "Please note that ",
    "Keep in mind that ",
    "It is worth mentioning that ",
    "Based on the above, ",
]


def compress_semantic(text: str) -> str:
    """
    Compress text semantically before zlib.
    Removes grammar, uses abbreviations, strips filler.
    Typically 40-60% size reduction before zlib.
    """
    if not text or len(text) < 100:
        return text
    
    result = text
    
    # Remove verbose phrases
    for phrase in REMOVE_PHRASES:
        result = result.replace(phrase, "")
    
    # Apply abbreviations (case insensitive but preserve first match case)
    for long, short in SEMANTIC_ABBREVS.items():
        # Word boundary match
        result = re.sub(rf'\b{long}\b', short, result, flags=re.IGNORECASE)
    
    # Remove multiple spaces
    result = re.sub(r'\s+', ' ', result)
    
    # Remove empty sentences
    result = re.sub(r'\.\s*\.', '.', result)
    
    # Remove leading/trailing whitespace per line
    result = '\n'.join(line.strip() for line in result.split('\n') if line.strip())
    
    return result


def compress_json(data: Any) -> bytes:
    """Compress JSON data with semantic + zlib compression"""
    if data is None:
        return None
    
    # First pass: semantic compression on string values
    def compress_values(obj):
        if isinstance(obj, str):
            return compress_semantic(obj)
        elif isinstance(obj, dict):
            return {k: compress_values(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [compress_values(v) for v in obj]
        return obj
    
    compressed_data = compress_values(data)
    json_str = json.dumps(compressed_data, separators=(',', ':'))
    return zlib.compress(json_str.encode('utf-8'), level=9)  # max compression


def decompress_json(data: bytes) -> Any:
    """Decompress zlib JSON data"""
    if data is None:
        return None
    json_str = zlib.decompress(data).decode('utf-8')
    return json.loads(json_str)


class TaskStore:
    """SQLite store with zlib compression for Software Factory"""

    _local = threading.local()

    def __init__(self, db_path: Path = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
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
                -- Projects table
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    display_name TEXT,
                    config_path TEXT NOT NULL,
                    root_path TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                -- Tasks table
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    parent_id TEXT,
                    type TEXT NOT NULL DEFAULT 'fix',
                    domain TEXT NOT NULL,
                    description TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    priority INTEGER DEFAULT 0,
                    wsjf_score REAL DEFAULT 0.0,
                    depth INTEGER DEFAULT 0,

                    -- Files as JSON
                    files_json TEXT,

                    -- Context compressed with zlib
                    context_gz BLOB,

                    -- Locking
                    locked_by TEXT,
                    lock_expires_at TEXT,

                    -- Attempt counters
                    tdd_attempts INTEGER DEFAULT 0,
                    adversarial_attempts INTEGER DEFAULT 0,
                    staging_attempts INTEGER DEFAULT 0,
                    prod_attempts INTEGER DEFAULT 0,

                    -- Git
                    commit_sha TEXT,

                    -- Error
                    last_error TEXT,

                    -- Timestamps
                    created_at TEXT,
                    updated_at TEXT,
                    completed_at TEXT,

                    FOREIGN KEY (project_id) REFERENCES projects(id),
                    FOREIGN KEY (parent_id) REFERENCES tasks(id)
                );

                -- Attempts table
                CREATE TABLE IF NOT EXISTS attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    attempt_num INTEGER NOT NULL,
                    stage TEXT NOT NULL,
                    verdict TEXT,
                    issues_gz BLOB,
                    response_gz BLOB,
                    created_at TEXT,
                    FOREIGN KEY (task_id) REFERENCES tasks(id)
                );

                -- Deployments table
                CREATE TABLE IF NOT EXISTS deployments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    env TEXT NOT NULL,
                    status TEXT NOT NULL,
                    commit_sha TEXT,
                    evidence_path TEXT,
                    created_at TEXT,
                    FOREIGN KEY (task_id) REFERENCES tasks(id)
                );

                -- Indexes
                CREATE INDEX IF NOT EXISTS idx_tasks_project_status
                    ON tasks(project_id, status);
                CREATE INDEX IF NOT EXISTS idx_tasks_parent
                    ON tasks(parent_id);
                CREATE INDEX IF NOT EXISTS idx_tasks_wsjf
                    ON tasks(wsjf_score DESC);
                CREATE INDEX IF NOT EXISTS idx_attempts_task
                    ON attempts(task_id);
                CREATE INDEX IF NOT EXISTS idx_deployments_task
                    ON deployments(task_id);
            """)
            conn.commit()

    # ==================== PROJECTS ====================

    def create_project(self, project_id: str, name: str,
                      config_path: str, root_path: str,
                      display_name: str = None) -> str:
        """Register a new project"""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO projects
                (id, name, display_name, config_path, root_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (project_id, name, display_name or name,
                  config_path, root_path, datetime.now().isoformat()))
            conn.commit()
        return project_id

    def get_project(self, project_id: str) -> Optional[Dict]:
        """Get project by ID"""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            if row:
                return dict(row)
        return None

    def list_projects(self) -> List[Dict]:
        """List all projects"""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM projects").fetchall()
            return [dict(row) for row in rows]

    # ==================== TASKS ====================

    def create_task(self, task: Task) -> str:
        """Create a new task"""
        with self._get_connection() as conn:
            context_gz = compress_json(task.context) if task.context else None

            conn.execute("""
                INSERT INTO tasks (
                    id, project_id, parent_id, type, domain, description,
                    status, priority, wsjf_score, depth, files_json, context_gz,
                    locked_by, lock_expires_at, tdd_attempts, adversarial_attempts,
                    staging_attempts, prod_attempts, commit_sha, last_error,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.id, task.project_id, task.parent_id, task.type,
                task.domain, task.description, task.status, task.priority,
                task.wsjf_score, task.depth, json.dumps(task.files),
                context_gz, task.locked_by, task.lock_expires_at,
                task.tdd_attempts, task.adversarial_attempts,
                task.staging_attempts, task.prod_attempts,
                task.commit_sha, task.last_error,
                task.created_at, task.updated_at
            ))
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
        """Convert DB row to Task object"""
        context = decompress_json(row['context_gz']) if row['context_gz'] else None

        return Task(
            id=row['id'],
            project_id=row['project_id'],
            parent_id=row['parent_id'],
            type=row['type'],
            domain=row['domain'],
            description=row['description'],
            status=row['status'],
            priority=row['priority'] or 0,
            wsjf_score=row['wsjf_score'] or 0.0,
            depth=row['depth'] or 0,
            files=json.loads(row['files_json'] or '[]'),
            context=context,
            locked_by=row['locked_by'],
            lock_expires_at=row['lock_expires_at'],
            tdd_attempts=row['tdd_attempts'] or 0,
            adversarial_attempts=row['adversarial_attempts'] or 0,
            staging_attempts=row['staging_attempts'] or 0,
            prod_attempts=row['prod_attempts'] or 0,
            commit_sha=row['commit_sha'],
            last_error=row['last_error'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            completed_at=row['completed_at'],
        )

    def transition(self, task_id: str, new_status: str,
                   changed_by: str = None, **updates) -> bool:
        """
        Transition task to new status with validation.
        Returns True if successful.
        """
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT status FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if not row:
                return False

            try:
                current = TaskStatus(row['status'])
                target = TaskStatus(new_status)
            except ValueError:
                return False

            # Validate transition
            if target not in VALID_TRANSITIONS.get(current, []):
                print(f"Invalid transition: {current.value} -> {target.value}")
                return False

            now = datetime.now().isoformat()

            # Build update
            update_fields = ["status = ?", "updated_at = ?"]
            update_values = [target.value, now]

            # Increment attempt counter based on target status
            if target == TaskStatus.TDD_IN_PROGRESS:
                update_fields.append("tdd_attempts = tdd_attempts + 1")
            elif target == TaskStatus.ADVERSARIAL_REJECTED:
                update_fields.append("adversarial_attempts = adversarial_attempts + 1")
            elif target == TaskStatus.STAGING_FAILED:
                update_fields.append("staging_attempts = staging_attempts + 1")
            elif target == TaskStatus.PROD_FAILED:
                update_fields.append("prod_attempts = prod_attempts + 1")

            # Set completed_at for final states
            if target in [TaskStatus.COMPLETED, TaskStatus.PROD_OK]:
                update_fields.append("completed_at = ?")
                update_values.append(now)

            # Apply additional updates
            for key, value in updates.items():
                if key in ['commit_sha', 'last_error', 'locked_by', 'lock_expires_at']:
                    update_fields.append(f"{key} = ?")
                    update_values.append(value)
                elif key == 'context':
                    update_fields.append("context_gz = ?")
                    update_values.append(compress_json(value))

            update_values.append(task_id)

            conn.execute(
                f"UPDATE tasks SET {', '.join(update_fields)} WHERE id = ?",
                update_values
            )
            conn.commit()
        return True

    def get_pending_tasks(self, project_id: str, limit: int = 10,
                          domain: str = None) -> List[Task]:
        """Get pending tasks sorted by WSJF"""
        with self._get_connection() as conn:
            query = """
                SELECT * FROM tasks
                WHERE project_id = ? AND status = 'pending'
                AND (locked_by IS NULL OR lock_expires_at < ?)
            """
            params = [project_id, datetime.now().isoformat()]

            if domain:
                query += " AND domain = ?"
                params.append(domain)

            query += " ORDER BY wsjf_score DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(query, params).fetchall()
            return [self._row_to_task(row) for row in rows]

    def lock_task(self, task_id: str, worker_id: str,
                  duration_seconds: int = 3600) -> bool:
        """Lock a task for a worker"""
        with self._get_connection() as conn:
            now = datetime.now()
            expires = datetime.fromtimestamp(
                now.timestamp() + duration_seconds
            ).isoformat()

            result = conn.execute("""
                UPDATE tasks
                SET locked_by = ?, lock_expires_at = ?,
                    status = 'locked', updated_at = ?
                WHERE id = ? AND status = 'pending'
                AND (locked_by IS NULL OR lock_expires_at < ?)
            """, (worker_id, expires, now.isoformat(), task_id, now.isoformat()))

            conn.commit()
            return result.rowcount > 0

    def unlock_task(self, task_id: str):
        """Unlock a task"""
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE tasks
                SET locked_by = NULL, lock_expires_at = NULL,
                    status = 'pending', updated_at = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), task_id))
            conn.commit()

    def get_tasks_by_status(self, project_id: str, status: str,
                            limit: int = 10) -> List[Task]:
        """
        Get tasks filtered by status, sorted by WSJF.
        Used by wiggum_deploy to get tasks ready for deployment.
        """
        with self._get_connection() as conn:
            # Handle status as string or TaskStatus enum
            status_value = status.value if isinstance(status, TaskStatus) else status

            rows = conn.execute("""
                SELECT * FROM tasks
                WHERE project_id = ? AND status = ?
                ORDER BY wsjf_score DESC, created_at ASC
                LIMIT ?
            """, (project_id, status_value, limit)).fetchall()

            return [self._row_to_task(row) for row in rows]

    def get_deployable_tasks(self, project_id: str, limit: int = 10) -> List[Task]:
        """
        Get tasks ready for deployment (MERGED or QUEUED_FOR_DEPLOY).
        """
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM tasks
                WHERE project_id = ?
                AND status IN ('merged', 'queued_for_deploy')
                ORDER BY wsjf_score DESC, created_at ASC
                LIMIT ?
            """, (project_id, limit)).fetchall()

            return [self._row_to_task(row) for row in rows]

    def create_task_from_failure(self, original_task: Task, failure_reason: str,
                                  failure_stage: str, evidence: Dict = None) -> str:
        """
        Create a new task from a deploy failure.
        This implements the feedback loop: deploy failure → new TDD task.

        Args:
            original_task: The task that failed during deploy
            failure_reason: Human-readable description of the failure
            failure_stage: Which stage failed (staging, e2e, chaos, load, prod)
            evidence: Optional dict with logs, screenshots, etc.

        Returns:
            New task ID
        """
        import uuid

        # Generate new task ID
        new_id = f"feedback-{original_task.id}-{failure_stage}-{uuid.uuid4().hex[:8]}"

        # Build context with failure information
        context = {
            "original_task_id": original_task.id,
            "failure_stage": failure_stage,
            "failure_reason": failure_reason,
            "original_context": original_task.context,
            "evidence": evidence,
            "is_feedback_task": True,
        }

        # Create the feedback task
        feedback_task = Task(
            id=new_id,
            project_id=original_task.project_id,
            domain=original_task.domain,
            description=f"[DEPLOY FEEDBACK] {failure_stage}: {failure_reason}",
            type="fix",  # Feedback tasks are always fixes
            status="pending",
            priority=original_task.priority + 10,  # Higher priority
            wsjf_score=original_task.wsjf_score * 1.5,  # Boost WSJF
            files=original_task.files,
            parent_id=original_task.id,  # Link to original
            depth=original_task.depth + 1,
            context=context,
        )

        self.create_task(feedback_task)
        return new_id

    def get_feedback_tasks(self, project_id: str) -> List[Task]:
        """Get all pending feedback tasks (from deploy failures)."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM tasks
                WHERE project_id = ?
                AND description LIKE '[DEPLOY FEEDBACK]%'
                AND status = 'pending'
                ORDER BY wsjf_score DESC
            """, (project_id,)).fetchall()

            return [self._row_to_task(row) for row in rows]

    def get_tasks_by_project(self, project_id: str, limit: int = 1000) -> List[Task]:
        """Get all tasks for a project."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM tasks
                WHERE project_id = ?
                ORDER BY wsjf_score DESC
                LIMIT ?
            """, (project_id, limit)).fetchall()

            return [self._row_to_task(row) for row in rows]

    def find_task_by_error_id(self, project_id: str, error_id: str) -> Optional[Task]:
        """
        Find a task by its captured error ID.

        Used for deduplication in the RLM feedback loop:
        - When ErrorCapture captures an error, it generates a unique error_id
        - Before creating a new task, we check if one already exists with that error_id
        - This prevents duplicate tasks for the same error

        Args:
            project_id: Project to search in
            error_id: Error ID from CapturedError.id (hash of error signature)

        Returns:
            Task if found, None otherwise
        """
        with self._get_connection() as conn:
            # Search in context_gz for error_id
            # This requires decompressing, so we limit the search
            rows = conn.execute("""
                SELECT * FROM tasks
                WHERE project_id = ?
                AND status IN ('pending', 'locked', 'tdd_in_progress')
                AND context_gz IS NOT NULL
                ORDER BY created_at DESC
                LIMIT 100
            """, (project_id,)).fetchall()

            for row in rows:
                task = self._row_to_task(row)
                if task.context:
                    if task.context.get("error_id") == error_id:
                        return task

            return None

    def update_task(self, task_id: str, **updates) -> bool:
        """
        Update task fields directly (without status transition validation).
        For cases where we need to update fields like last_error, commit_sha, etc.
        """
        with self._get_connection() as conn:
            now = datetime.now().isoformat()

            # Build update fields
            allowed_fields = [
                'commit_sha', 'last_error', 'locked_by', 'lock_expires_at',
                'tdd_attempts', 'adversarial_attempts', 'staging_attempts', 'prod_attempts'
            ]

            update_fields = ["updated_at = ?"]
            update_values = [now]

            for key, value in updates.items():
                if key in allowed_fields:
                    update_fields.append(f"{key} = ?")
                    update_values.append(value)
                elif key == 'context':
                    update_fields.append("context_gz = ?")
                    update_values.append(compress_json(value))

            if len(update_fields) == 1:  # Only updated_at
                return False

            update_values.append(task_id)

            result = conn.execute(
                f"UPDATE tasks SET {', '.join(update_fields)} WHERE id = ?",
                update_values
            )
            conn.commit()
            return result.rowcount > 0

    # ==================== FRACTAL ====================

    def decompose_task(self, parent_id: str, subtasks: List[Task]) -> List[str]:
        """
        FRACTAL decomposition: mark parent as DECOMPOSED and create subtasks.
        """
        with self._get_connection() as conn:
            # Get parent task
            parent = self.get_task(parent_id)
            if not parent:
                return []

            subtask_ids = []
            for subtask in subtasks:
                subtask.parent_id = parent_id
                subtask.project_id = parent.project_id
                subtask.depth = parent.depth + 1
                self.create_task(subtask)
                subtask_ids.append(subtask.id)

            # Update parent status
            conn.execute("""
                UPDATE tasks
                SET status = 'decomposed', updated_at = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), parent_id))
            conn.commit()

        return subtask_ids

    def get_subtasks(self, parent_id: str) -> List[Task]:
        """Get all subtasks of a parent task"""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE parent_id = ?", (parent_id,)
            ).fetchall()
            return [self._row_to_task(row) for row in rows]

    # ==================== ATTEMPTS ====================

    def record_attempt(self, attempt: Attempt):
        """Record a task attempt"""
        with self._get_connection() as conn:
            issues_gz = compress_json(attempt.issues) if attempt.issues else None
            response_gz = compress_json(attempt.response) if attempt.response else None

            conn.execute("""
                INSERT INTO attempts
                (task_id, attempt_num, stage, verdict, issues_gz, response_gz, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (attempt.task_id, attempt.attempt_num, attempt.stage,
                  attempt.verdict, issues_gz, response_gz, attempt.created_at))
            conn.commit()

    def get_attempts(self, task_id: str) -> List[Attempt]:
        """Get all attempts for a task"""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM attempts WHERE task_id = ? ORDER BY attempt_num",
                (task_id,)
            ).fetchall()

            attempts = []
            for row in rows:
                attempts.append(Attempt(
                    task_id=row['task_id'],
                    attempt_num=row['attempt_num'],
                    stage=row['stage'],
                    verdict=row['verdict'],
                    issues=decompress_json(row['issues_gz']),
                    response=decompress_json(row['response_gz']),
                    created_at=row['created_at']
                ))
            return attempts

    # ==================== DEPLOYMENTS ====================

    def record_deployment(self, deployment: Deployment):
        """Record a deployment"""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO deployments
                (task_id, env, status, commit_sha, evidence_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (deployment.task_id, deployment.env, deployment.status,
                  deployment.commit_sha, deployment.evidence_path, deployment.created_at))
            conn.commit()

    def update_deployment(self, task_id: str, env: str, status: str,
                          evidence_path: str = None):
        """Update deployment status"""
        with self._get_connection() as conn:
            if evidence_path:
                conn.execute("""
                    UPDATE deployments SET status = ?, evidence_path = ?
                    WHERE task_id = ? AND env = ?
                """, (status, evidence_path, task_id, env))
            else:
                conn.execute("""
                    UPDATE deployments SET status = ?
                    WHERE task_id = ? AND env = ?
                """, (status, task_id, env))
            conn.commit()

    # ==================== STATS ====================

    def get_stats(self, project_id: str = None) -> Dict[str, Any]:
        """Get statistics, optionally filtered by project"""
        with self._get_connection() as conn:
            stats = {}

            # Filter clause
            where = "WHERE project_id = ?" if project_id else ""
            params = [project_id] if project_id else []

            # By status
            rows = conn.execute(f"""
                SELECT status, COUNT(*) as count FROM tasks {where}
                GROUP BY status
            """, params).fetchall()
            stats['by_status'] = {row['status']: row['count'] for row in rows}

            # By domain
            rows = conn.execute(f"""
                SELECT domain, COUNT(*) as count FROM tasks {where}
                GROUP BY domain
            """, params).fetchall()
            stats['by_domain'] = {row['domain']: row['count'] for row in rows}

            # Total
            row = conn.execute(f"SELECT COUNT(*) as total FROM tasks {where}", params).fetchone()
            stats['total'] = row['total']

            # Calculated metrics
            stats['pending'] = stats['by_status'].get('pending', 0)

            # TDD in progress
            stats['tdd_in_progress'] = sum(
                stats['by_status'].get(s, 0)
                for s in ['locked', 'tdd_in_progress', 'tdd_success', 'adversarial_rejected']
            )
            stats['tdd_failed'] = stats['by_status'].get('tdd_failed', 0)

            # Merged, awaiting deploy
            stats['merged'] = stats['by_status'].get('merged', 0)

            # Deploy pipeline in progress
            stats['deploying'] = sum(
                stats['by_status'].get(s, 0)
                for s in [
                    'queued_for_deploy', 'deploying_staging', 'staging_ok', 'staging_failed',
                    'perf_smoke_ok', 'perf_smoke_failed',
                    'e2e_journeys_ok', 'e2e_journeys_failed',
                    'chaos_ok', 'chaos_failed',
                    'load_ok', 'load_failed',
                    'deploying_prod', 'prod_ok', 'prod_failed'
                ]
            )

            # Final states
            stats['completed'] = stats['by_status'].get('completed', 0)
            stats['deployed'] = stats['by_status'].get('deployed', 0)
            stats['failed'] = stats['by_status'].get('failed', 0)
            stats['deploy_failed'] = stats['by_status'].get('deploy_failed', 0)
            stats['blocked'] = stats['by_status'].get('blocked', 0)
            stats['decomposed'] = stats['by_status'].get('decomposed', 0)

            # Total success = completed + deployed
            stats['total_success'] = stats['completed'] + stats['deployed']

            # Total failures = failed + tdd_failed + deploy_failed
            stats['total_failed'] = stats['failed'] + stats['tdd_failed'] + stats['deploy_failed']

            if stats['total'] > 0:
                stats['progress_pct'] = (stats['total_success'] / stats['total']) * 100
            else:
                stats['progress_pct'] = 0

            return stats

    def get_all_stats(self) -> Dict[str, Dict]:
        """Get stats for all projects"""
        projects = self.list_projects()
        return {p['id']: self.get_stats(p['id']) for p in projects}


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Software Factory Task Store")
    parser.add_argument("command", choices=["stats", "projects", "pending"])
    parser.add_argument("--project", "-p", help="Project ID")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--domain", type=str)
    args = parser.parse_args()

    store = TaskStore()

    if args.command == "stats":
        if args.project:
            stats = store.get_stats(args.project)
            print(f"=== {args.project.upper()} STATS ===")
        else:
            stats = store.get_stats()
            print("=== ALL PROJECTS STATS ===")

        print(f"Total: {stats['total']}")
        print(f"Pending: {stats['pending']}")
        print(f"TDD In Progress: {stats['tdd_in_progress']}")
        print(f"TDD Failed: {stats['tdd_failed']}")
        print(f"Merged (await deploy): {stats['merged']}")
        print(f"Deploying: {stats['deploying']}")
        print(f"Deployed: {stats['deployed']}")
        print(f"Deploy Failed: {stats['deploy_failed']}")
        print(f"Completed: {stats['completed']}")
        print(f"Total Success: {stats['total_success']} ({stats['progress_pct']:.1f}%)")
        print(f"Total Failed: {stats['total_failed']}")
        print(f"Blocked: {stats['blocked']}")
        print(f"Decomposed: {stats['decomposed']}")

    elif args.command == "projects":
        projects = store.list_projects()
        print("=== REGISTERED PROJECTS ===")
        for p in projects:
            stats = store.get_stats(p['id'])
            print(f"  {p['id']}: {stats['completed']}/{stats['total']} done")

    elif args.command == "pending":
        if not args.project:
            print("Error: --project required")
        else:
            tasks = store.get_pending_tasks(args.project, args.limit, args.domain)
            print(f"=== PENDING TASKS ({args.project}) ===")
            for t in tasks:
                print(f"  [{t.domain}] {t.id} (WSJF: {t.wsjf_score:.2f})")
