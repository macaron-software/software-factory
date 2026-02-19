"""
Feedback Task Creation - Unified error-to-task pipeline
======================================================
Centralizes feedback task creation from build/test/deploy errors.

Uses error_patterns.classify_error() for consistent classification:
- "transient" → retry, no task
- "infra" → log warning, no task (factory/config issue)
- "security" → high priority fix task
- "code" → standard fix task

Usage:
    from core.feedback import create_feedback_task

    task_id = create_feedback_task(
        project_id="ppz",
        source_task_id="rust-001",
        error_text="error[E0433]: failed to resolve",
        stage="build",
        task_store=store,
    )
"""

import hashlib
import uuid
from typing import List, Optional

from core.error_patterns import classify_error, is_infra
from core.task_store import TaskStore, Task, TaskStatus


def create_feedback_task(
    project_id: str,
    source_task_id: str,
    error_text: str,
    stage: str,
    task_store: TaskStore,
    domain: str = None,
    files: List[str] = None,
    related_task_ids: List[str] = None,
    log_fn=None,
) -> Optional[str]:
    """
    Classify error and create appropriate feedback task.

    Args:
        project_id: Project identifier
        source_task_id: Task that triggered this error
        error_text: Full error output
        stage: Pipeline stage ("tdd", "build", "deploy", "e2e")
        task_store: TaskStore instance
        domain: Code domain (rust, typescript, etc.)
        files: Related files
        related_task_ids: IDs of tasks affected by this error
        log_fn: Optional log function(msg, level)

    Returns:
        Created task ID, or None if error is transient/infra
    """
    category = classify_error(error_text)

    if category == "transient":
        if log_fn:
            log_fn(f"[TRANSIENT ERROR] Skipping feedback - will retry: {error_text[:100]}...", "DEBUG")
        return None

    if category == "infra":
        if log_fn:
            log_fn(f"[INFRA ERROR] Skipping feedback - not a code issue: {error_text[:100]}...", "WARN")
        # Still record in meta-awareness for systemic detection
        _record_meta_awareness(project_id, error_text, log_fn)
        return None

    # Filter build artifacts and protected paths (LLM hallucination prevention)
    PROTECTED_PATTERNS = [
        'target/debug/', 'target/release/', 'node_modules/',
        '.fingerprint/', 'build.gradle', 'package-lock.json',
        'Cargo.lock', '.git/', 'LICENSE',
    ]
    files_str = str(files or [])
    if any(pat in error_text or pat in files_str for pat in PROTECTED_PATTERNS):
        if log_fn:
            log_fn(f"[PROTECTED PATH] Skipping feedback for build artifact/protected file: {files_str[:80]}", "WARN")
        return None

    # Code or security error → create feedback task
    error_hash = hashlib.md5(error_text[:500].encode()).hexdigest()[:8]
    feedback_id = f"feedback-{stage}-{domain or 'unknown'}-{error_hash}"

    # Check for duplicates
    try:
        existing = task_store.find_task_by_error_id(project_id, feedback_id)
        if existing:
            if log_fn:
                log_fn(f"Skipping duplicate feedback task: {feedback_id}", "DEBUG")
            return None
    except (AttributeError, Exception):
        pass  # find_task_by_error_id may not exist

    # Set priority based on category
    wsjf = 12.0 if category == "security" else 8.0
    priority = 15 if category == "security" else 10
    task_type = "security_fix" if category == "security" else "fix"

    feedback = Task(
        id=feedback_id,
        project_id=project_id,
        type=task_type,
        domain=domain or "unknown",
        description=f"[{stage.upper()} FEEDBACK] Fix {category} error: {error_text[:200]}",
        status=TaskStatus.PENDING.value,
        priority=priority,
        files=files or [],
        context={
            "error": error_text[:2000],
            "stage": stage,
            "source_task_id": source_task_id,
            "related_tasks": related_task_ids or [],
            "category": category,
            "feedback_loop": True,
        },
        wsjf_score=wsjf,
    )

    try:
        task_store.create_task(feedback)
        if log_fn:
            log_fn(f"Created feedback task: {feedback_id} ({category}, stage={stage})")
        return feedback_id
    except Exception:
        return None  # May already exist


def create_feedback_tasks_from_errors(
    project_id: str,
    source_task_id: str,
    error_tasks: list,
    task_store: TaskStore,
    log_fn=None,
) -> int:
    """
    Create feedback tasks from ErrorCapture.errors_to_tasks() output.

    This is the RLM feedback loop:
    Build/Test Error → Capture → Parse → Create Task → Backlog → TDD Worker

    Args:
        project_id: Project identifier
        source_task_id: Task that triggered these errors
        error_tasks: List of task dicts from ErrorCapture.errors_to_tasks()
        task_store: TaskStore instance
        log_fn: Optional log function

    Returns:
        Number of tasks created
    """
    created_count = 0

    for task_dict in error_tasks:
        try:
            task_dict.setdefault("context", {})
            task_dict["context"]["source_task_id"] = source_task_id
            task_dict["context"]["feedback_loop"] = True

            # Check for duplicates
            error_id = task_dict["context"].get("error_id", "")
            if error_id:
                try:
                    existing = task_store.find_task_by_error_id(project_id, error_id)
                    if existing:
                        continue
                except (AttributeError, Exception):
                    pass

            feedback_task = Task(
                id=f"feedback-{task_dict.get('domain', 'unknown')}-{uuid.uuid4().hex[:8]}",
                project_id=project_id,
                type=task_dict.get("type", "fix"),
                domain=task_dict.get("domain", "unknown"),
                description=task_dict.get("description", "Fix captured error"),
                status="pending",
                files=task_dict.get("files", []),
                context=task_dict.get("context", {}),
                wsjf_score=task_dict.get("wsjf_score", 5.0),
            )
            task_store.create_task(feedback_task)
            created_count += 1

        except Exception as e:
            if log_fn:
                log_fn(f"Failed to create feedback task: {e}", "ERROR")

    if created_count > 0 and log_fn:
        log_fn(f"Created {created_count} feedback tasks from errors (RLM loop)")

    return created_count


def _record_meta_awareness(project_id: str, error_text: str, log_fn=None):
    """Record error in meta-awareness for systemic detection."""
    try:
        from core.meta_awareness import record_build_error
        factory_task_id = record_build_error(project_id, error_text)
        if factory_task_id and log_fn:
            log_fn(f"[META-AWARENESS] Systemic error detected -> Factory task: {factory_task_id}", "WARN")
    except Exception:
        pass
