"""
RLM Models - Pydantic models for the LEAN Requirements Manager.

Defines Task, Finding, Backlog structures for codebase analysis and TDD fixing.
Supports fractal decomposition and feedback loops.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

# Fractal decomposition limits
MAX_FRACTAL_DEPTH = 3  # Maximum recursion depth for subtasks
MAX_ADVERSARIAL_RETRIES = 2  # Max retries after adversarial rejection
COMPLEXITY_THRESHOLD = 100  # Lines of code to consider "complex"


class TaskStatus(str, Enum):
    """Status of a task in the backlog."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ADVERSARIAL_FAILED = "adversarial_failed"  # Rejected by quality gate
    DECOMPOSED = "decomposed"  # Split into subtasks (fractal)


class TaskType(str, Enum):
    """Type of task to perform."""

    FIX = "fix"
    REFACTOR = "refactor"
    TEST = "test"
    SECURITY = "security"
    LINT = "lint"
    BUILD = "build"


class Domain(str, Enum):
    """Codebase domain for analysis."""

    RUST = "rust"
    PYTHON = "python"
    TYPESCRIPT = "typescript"
    PROTO = "proto"
    SQL = "sql"
    E2E = "e2e"


class Finding(BaseModel):
    """A finding from static analysis or tests."""

    type: str = Field(..., description="Type of finding (clippy, ruff, pytest, etc)")
    severity: str = Field(
        ..., description="Severity level: low, medium, high, critical"
    )
    message: str = Field(..., description="Error/warning message")
    file: Optional[str] = Field(None, description="File path where issue was found")
    line: Optional[int] = Field(None, description="Line number of the issue")
    column: Optional[int] = Field(None, description="Column number of the issue")
    code: Optional[str] = Field(None, description="Error code (e.g., E0001, W0123)")
    suggestion: Optional[str] = Field(None, description="Suggested fix if available")


class Task(BaseModel):
    """A task in the RLM backlog."""

    id: str = Field(..., description="Unique task identifier")
    type: TaskType = Field(..., description="Type of task")
    domain: Domain = Field(..., description="Codebase domain")
    description: str = Field(..., description="Human-readable description")
    files: list[str] = Field(default_factory=list, description="Affected files")
    finding: Finding = Field(..., description="The original finding")

    # Context for LLM (enriched by Brain)
    file_content: Optional[str] = Field(
        None, description="Source code context (max 3000 chars)"
    )
    imports: list[str] = Field(
        default_factory=list, description="Import statements in the file"
    )
    types_defined: list[str] = Field(
        default_factory=list, description="Types/classes defined in the file"
    )
    test_example: Optional[str] = Field(
        None, description="Example test from the project"
    )
    conventions: dict = Field(
        default_factory=dict, description="Project conventions for this domain"
    )

    # Status tracking
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="Task status")
    retry_count: int = Field(default=0, description="Number of retry attempts")

    # Fractal decomposition
    parent_task_id: Optional[str] = Field(None, description="Parent task ID (for subtasks)")
    subtask_ids: list[str] = Field(default_factory=list, description="Child task IDs")
    depth: int = Field(default=0, description="Fractal depth (0 = root task)")
    is_complex: bool = Field(default=False, description="Marked as too complex for single fix")

    # Adversarial feedback (for retry)
    adversarial_feedback: Optional[str] = Field(
        None, description="Feedback from adversarial rejection"
    )
    previous_attempts: list[str] = Field(
        default_factory=list, description="Previous fix attempts (for context)"
    )

    # WSJF scoring
    business_value: int = Field(default=5, ge=1, le=10, description="Business value")
    time_criticality: int = Field(
        default=5, ge=1, le=10, description="Time criticality"
    )
    risk_reduction: int = Field(
        default=5, ge=1, le=10, description="Risk/opportunity reduction"
    )
    job_size: int = Field(default=5, ge=1, le=10, description="Job size (effort)")
    wsjf_score: float = Field(default=0.0, description="Calculated WSJF score")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = Field(None)
    completed_at: Optional[datetime] = Field(None)

    # Results
    commit_hash: Optional[str] = Field(None, description="Git commit if completed")
    error: Optional[str] = Field(None, description="Error message if failed")
    test_output: Optional[str] = Field(None, description="Test output after fix")

    def calculate_wsjf(self) -> float:
        """Calculate WSJF score for prioritization."""
        if self.job_size == 0:
            self.wsjf_score = 0.0
        else:
            self.wsjf_score = (
                self.business_value + self.time_criticality + self.risk_reduction
            ) / self.job_size
        return self.wsjf_score


class DeployTask(BaseModel):
    """A task in the deploy backlog."""

    id: str = Field(..., description="Unique deploy task identifier")
    source_task: str = Field(..., description="Original task ID from TDD backlog")
    commit_hash: str = Field(..., description="Git commit hash to deploy")
    domain: Domain = Field(..., description="Domain being deployed")

    # Status
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    staging_deployed: bool = Field(default=False)
    staging_tested: bool = Field(default=False)
    prod_deployed: bool = Field(default=False)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    deployed_at: Optional[datetime] = Field(None)

    # Results
    error: Optional[str] = Field(None)


class Backlog(BaseModel):
    """The RLM backlog containing all tasks."""

    version: str = Field(default="1.0", description="Backlog schema version")
    updated: datetime = Field(default_factory=datetime.utcnow)
    tasks: list[Task] = Field(default_factory=list)

    # Stats
    total_tasks: int = Field(default=0)
    pending_count: int = Field(default=0)
    completed_count: int = Field(default=0)
    failed_count: int = Field(default=0)

    def update_stats(self) -> None:
        """Update backlog statistics."""
        self.total_tasks = len(self.tasks)
        self.pending_count = sum(
            1 for t in self.tasks if t.status == TaskStatus.PENDING
        )
        self.completed_count = sum(
            1 for t in self.tasks if t.status == TaskStatus.COMPLETED
        )
        self.failed_count = sum(1 for t in self.tasks if t.status == TaskStatus.FAILED)
        self.updated = datetime.utcnow()

    def get_next_task(self) -> Optional[Task]:
        """Get next pending task with highest WSJF score."""
        pending = [t for t in self.tasks if t.status == TaskStatus.PENDING]
        if not pending:
            return None
        return max(pending, key=lambda t: t.wsjf_score)

    def get_tasks_by_domain(self, domain: Domain) -> list[Task]:
        """Get all tasks for a specific domain."""
        return [t for t in self.tasks if t.domain == domain]


class DeployBacklog(BaseModel):
    """The deploy backlog containing tasks ready for deployment."""

    version: str = Field(default="1.0")
    updated: datetime = Field(default_factory=datetime.utcnow)
    tasks: list[DeployTask] = Field(default_factory=list)

    def update_stats(self) -> None:
        """Update backlog timestamp."""
        self.updated = datetime.utcnow()


# Domain-specific conventions
DOMAIN_CONVENTIONS = {
    Domain.RUST: {
        "error_handling": "Use ? operator, not .unwrap()",
        "testing": "#[cfg(test)] mod tests { use super::*; }",
        "formatting": "cargo fmt",
        "skip_pattern": "NEVER use #[ignore] without good reason",
    },
    Domain.PYTHON: {
        "error_handling": "Explicit try/except, no bare except",
        "testing": "pytest with descriptive test names",
        "formatting": "ruff format",
        "skip_pattern": "NEVER use pytest.mark.skip without reason",
        "types": "Use type hints, avoid # type: ignore",
    },
    Domain.TYPESCRIPT: {
        "error_handling": "Explicit error handling",
        "testing": "vitest or playwright for e2e",
        "skip_pattern": "NEVER use test.skip or describe.skip",
        "types": "Strict TypeScript, no any",
    },
    Domain.PROTO: {
        "naming": "snake_case for fields, PascalCase for messages",
        "versioning": "Add new fields, never remove",
    },
    Domain.SQL: {
        "naming": "snake_case for tables and columns",
        "safety": "Always use IF NOT EXISTS, IF EXISTS",
        "indexes": "Index foreign keys and frequently queried columns",
    },
    Domain.E2E: {
        "selectors": "Use data-testid or accessible roles",
        "waits": "Use explicit waits, not sleep",
        "skip_pattern": "NEVER skip tests without documented reason",
    },
}


# Analysis commands per domain
DOMAIN_ANALYSIS_COMMANDS = {
    Domain.RUST: [
        ("cargo clippy --workspace --message-format=json 2>&1", "clippy"),
        ("cargo build --workspace 2>&1", "build"),
        ("cargo test --workspace --no-run 2>&1", "test_compile"),
    ],
    Domain.PYTHON: [
        ("cd agents && ruff check . --output-format=json 2>&1", "ruff"),
        ("cd agents && python -m pytest --collect-only -q 2>&1", "pytest_collect"),
    ],
    Domain.PROTO: [
        ("buf lint proto/ 2>&1 || true", "buf"),
    ],
    Domain.SQL: [
        # SQL is analyzed by reading migration files
    ],
    Domain.E2E: [
        ("cd e2e && npx playwright test --list 2>&1", "playwright_list"),
    ],
}
