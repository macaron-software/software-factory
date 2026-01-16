"""
RLM Brain - Codebase Analysis Orchestrator.

Scans the Fervenza codebase using static analysis tools,
parses findings into tasks, enriches with context, and prioritizes using WSJF.

LLM: Claude Opus 4.5 via claude CLI (for orchestration and sub-agents)
Sub-agents: Qwen 30B via opencode + llama serve
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import (
    Backlog,
    Domain,
    DOMAIN_ANALYSIS_COMMANDS,
    DOMAIN_CONVENTIONS,
    Finding,
    Task,
    TaskStatus,
    TaskType,
)

logger = logging.getLogger(__name__)

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent  # Fervenza root
BACKLOG_PATH = Path(__file__).parent / "backlog_tasks.json"
CACHE_PATH = Path(__file__).parent / "analysis_cache.json"

# Severity mapping
SEVERITY_MAP = {
    "error": "high",
    "warning": "medium",
    "note": "low",
    "help": "low",
    "deny": "critical",
    "allow": "low",
}


class RLMBrain:
    """
    RLM Brain - Analyzes codebase and generates prioritized backlog.

    Usage:
        brain = RLMBrain()
        await brain.analyze()  # Full analysis
        await brain.analyze(domain=Domain.RUST)  # Single domain
    """

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or PROJECT_ROOT
        self.backlog = Backlog()
        self.cache: dict = {}
        self._load_cache()

    def _load_cache(self) -> None:
        """Load analysis cache from disk."""
        if CACHE_PATH.exists():
            try:
                self.cache = json.loads(CACHE_PATH.read_text())
            except json.JSONDecodeError:
                self.cache = {}

    def _save_cache(self) -> None:
        """Save analysis cache to disk."""
        CACHE_PATH.write_text(json.dumps(self.cache, indent=2, default=str))

    def _file_hash(self, path: Path) -> str:
        """Get hash of file content for cache invalidation."""
        if not path.exists():
            return ""
        content = path.read_bytes()
        return hashlib.md5(content).hexdigest()

    async def analyze(
        self,
        domain: Optional[Domain] = None,
        quick: bool = False,
    ) -> Backlog:
        """
        Analyze codebase and generate backlog.

        Args:
            domain: Specific domain to analyze (None = all)
            quick: Skip slow analyses (security, deep lint)

        Returns:
            Backlog with prioritized tasks
        """
        logger.info(f"Starting RLM analysis (domain={domain}, quick={quick})")

        domains = [domain] if domain else list(Domain)

        for d in domains:
            if d == Domain.RUST:
                await self._analyze_rust()
            elif d == Domain.PYTHON:
                await self._analyze_python()
            elif d == Domain.PROTO:
                await self._analyze_proto()
            elif d == Domain.SQL:
                await self._analyze_sql()
            elif d == Domain.E2E:
                await self._analyze_e2e()

        # Calculate WSJF scores
        for task in self.backlog.tasks:
            task.calculate_wsjf()

        # Sort by WSJF score (highest first)
        self.backlog.tasks.sort(key=lambda t: t.wsjf_score, reverse=True)
        self.backlog.update_stats()

        # Save backlog
        self._save_backlog()
        self._save_cache()

        logger.info(
            f"Analysis complete: {self.backlog.total_tasks} tasks, "
            f"{self.backlog.pending_count} pending"
        )

        return self.backlog

    async def _analyze_rust(self) -> None:
        """Analyze Rust crates with clippy and cargo."""
        logger.info("Analyzing Rust crates...")

        # Run clippy
        result = subprocess.run(
            ["cargo", "clippy", "--workspace", "--message-format=json"],
            cwd=self.project_root,
            capture_output=True,
            text=True,
        )

        # Parse clippy JSON output
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            try:
                msg = json.loads(line)
                if msg.get("reason") == "compiler-message":
                    self._parse_clippy_message(msg)
            except json.JSONDecodeError:
                continue

        # Run cargo build to catch additional errors
        result = subprocess.run(
            ["cargo", "build", "--workspace"],
            cwd=self.project_root,
            capture_output=True,
            text=True,
        )

        # Parse build errors from stderr
        self._parse_cargo_errors(result.stderr)

    def _parse_clippy_message(self, msg: dict) -> None:
        """Parse a clippy JSON message into a task."""
        message = msg.get("message", {})
        level = message.get("level", "")

        # Skip notes and helps unless they contain actionable info
        if level in ("note", "help"):
            return

        code = message.get("code", {})
        code_str = code.get("code", "") if code else ""

        # Get primary span
        spans = message.get("spans", [])
        primary_span = next((s for s in spans if s.get("is_primary")), None)

        if not primary_span:
            return

        file_path = primary_span.get("file_name", "")
        line = primary_span.get("line_start")

        # Skip external crates
        if file_path.startswith("/") and "crates/" not in file_path:
            return

        # Create finding
        finding = Finding(
            type="clippy",
            severity=SEVERITY_MAP.get(level, "medium"),
            message=message.get("message", ""),
            file=file_path,
            line=line,
            code=code_str,
            suggestion=message.get("rendered"),
        )

        # Determine task type
        task_type = TaskType.LINT
        if "unused" in finding.message.lower():
            task_type = TaskType.REFACTOR
        elif "error" in level:
            task_type = TaskType.FIX

        # Generate task ID
        task_id = f"rust-{code_str or 'err'}-{Path(file_path).stem}-{line}"

        # Skip if already in backlog
        if any(t.id == task_id for t in self.backlog.tasks):
            return

        # Create task
        task = Task(
            id=task_id,
            type=task_type,
            domain=Domain.RUST,
            description=f"Fix {code_str}: {finding.message[:100]}",
            files=[file_path],
            finding=finding,
            conventions=DOMAIN_CONVENTIONS[Domain.RUST],
        )

        # Set WSJF weights based on severity
        if finding.severity == "critical":
            task.business_value = 10
            task.risk_reduction = 10
        elif finding.severity == "high":
            task.business_value = 8
            task.risk_reduction = 8
        elif finding.severity == "medium":
            task.business_value = 5
            task.risk_reduction = 5

        # Enrich with file content
        self._enrich_task(task)

        self.backlog.tasks.append(task)

    def _parse_cargo_errors(self, stderr: str) -> None:
        """Parse cargo build errors from stderr."""
        error_pattern = re.compile(
            r"error\[E(\d+)\]: (.+)\n\s*-->\s*([^:]+):(\d+):(\d+)"
        )

        for match in error_pattern.finditer(stderr):
            code = f"E{match.group(1)}"
            message = match.group(2)
            file_path = match.group(3)
            line = int(match.group(4))

            task_id = f"rust-{code}-{Path(file_path).stem}-{line}"

            if any(t.id == task_id for t in self.backlog.tasks):
                continue

            finding = Finding(
                type="cargo_build",
                severity="high",
                message=message,
                file=file_path,
                line=line,
                code=code,
            )

            task = Task(
                id=task_id,
                type=TaskType.FIX,
                domain=Domain.RUST,
                description=f"Fix build error {code}: {message[:100]}",
                files=[file_path],
                finding=finding,
                conventions=DOMAIN_CONVENTIONS[Domain.RUST],
                business_value=9,
                risk_reduction=9,
            )

            self._enrich_task(task)
            self.backlog.tasks.append(task)

    async def _analyze_python(self) -> None:
        """Analyze Python code with ruff."""
        logger.info("Analyzing Python agents...")

        agents_dir = self.project_root / "agents"
        if not agents_dir.exists():
            return

        # Run ruff
        result = subprocess.run(
            ["ruff", "check", ".", "--output-format=json"],
            cwd=agents_dir,
            capture_output=True,
            text=True,
        )

        try:
            findings = json.loads(result.stdout) if result.stdout else []
        except json.JSONDecodeError:
            findings = []

        for item in findings:
            code = item.get("code", "")
            message = item.get("message", "")
            file_path = item.get("filename", "")
            line = item.get("location", {}).get("row")

            # Make path relative to agents dir
            rel_path = f"agents/{file_path}" if not file_path.startswith("agents/") else file_path

            task_id = f"python-{code}-{Path(file_path).stem}-{line}"

            if any(t.id == task_id for t in self.backlog.tasks):
                continue

            finding = Finding(
                type="ruff",
                severity="medium" if code.startswith("W") else "high",
                message=message,
                file=rel_path,
                line=line,
                code=code,
            )

            task = Task(
                id=task_id,
                type=TaskType.LINT,
                domain=Domain.PYTHON,
                description=f"Fix {code}: {message[:100]}",
                files=[rel_path],
                finding=finding,
                conventions=DOMAIN_CONVENTIONS[Domain.PYTHON],
            )

            self._enrich_task(task)
            self.backlog.tasks.append(task)

    async def _analyze_proto(self) -> None:
        """Analyze protobuf files with buf lint."""
        logger.info("Analyzing proto files...")

        proto_dir = self.project_root / "proto"
        if not proto_dir.exists():
            return

        # Check if buf is available
        result = subprocess.run(
            ["buf", "lint", "."],
            cwd=proto_dir,
            capture_output=True,
            text=True,
        )

        # Parse buf output (format: file:line:column:message)
        for line in result.stdout.splitlines():
            if not line.strip():
                continue

            parts = line.split(":", 3)
            if len(parts) < 4:
                continue

            file_path = parts[0]
            line_num = int(parts[1]) if parts[1].isdigit() else 1
            message = parts[3].strip() if len(parts) > 3 else ""

            task_id = f"proto-lint-{Path(file_path).stem}-{line_num}"

            if any(t.id == task_id for t in self.backlog.tasks):
                continue

            finding = Finding(
                type="buf_lint",
                severity="medium",
                message=message,
                file=f"proto/{file_path}",
                line=line_num,
            )

            task = Task(
                id=task_id,
                type=TaskType.LINT,
                domain=Domain.PROTO,
                description=f"Fix proto lint: {message[:100]}",
                files=[f"proto/{file_path}"],
                finding=finding,
                conventions=DOMAIN_CONVENTIONS[Domain.PROTO],
            )

            self.backlog.tasks.append(task)

    async def _analyze_sql(self) -> None:
        """Analyze SQL migrations for common issues."""
        logger.info("Analyzing SQL migrations...")

        migrations_dir = self.project_root / "migrations"
        if not migrations_dir.exists():
            return

        for sql_file in migrations_dir.glob("*.sql"):
            content = sql_file.read_text()

            # Check for common issues
            issues = []

            # Missing IF NOT EXISTS
            if "CREATE TABLE" in content and "IF NOT EXISTS" not in content:
                issues.append("Missing IF NOT EXISTS on CREATE TABLE")

            # Missing IF EXISTS on DROP
            if "DROP TABLE" in content and "IF EXISTS" not in content:
                issues.append("Missing IF EXISTS on DROP TABLE")

            # Hardcoded values that should be parameterized
            if re.search(r"VALUES\s*\([^)]*'[^']+@[^']+\.[^']+'", content):
                issues.append("Hardcoded email in VALUES")

            for issue in issues:
                task_id = f"sql-{sql_file.stem}-{hashlib.md5(issue.encode()).hexdigest()[:8]}"

                if any(t.id == task_id for t in self.backlog.tasks):
                    continue

                finding = Finding(
                    type="sql_lint",
                    severity="medium",
                    message=issue,
                    file=str(sql_file.relative_to(self.project_root)),
                )

                task = Task(
                    id=task_id,
                    type=TaskType.FIX,
                    domain=Domain.SQL,
                    description=f"Fix SQL: {issue}",
                    files=[str(sql_file.relative_to(self.project_root))],
                    finding=finding,
                    conventions=DOMAIN_CONVENTIONS[Domain.SQL],
                )

                self.backlog.tasks.append(task)

    async def _analyze_e2e(self) -> None:
        """Analyze E2E tests for skipped tests and issues."""
        logger.info("Analyzing E2E tests...")

        e2e_dir = self.project_root / "e2e"
        if not e2e_dir.exists():
            return

        for test_file in e2e_dir.rglob("*.spec.ts"):
            content = test_file.read_text()
            lines = content.splitlines()

            for i, line in enumerate(lines, 1):
                # Check for skipped tests
                if "test.skip" in line or "describe.skip" in line:
                    task_id = f"e2e-skip-{test_file.stem}-{i}"

                    if any(t.id == task_id for t in self.backlog.tasks):
                        continue

                    finding = Finding(
                        type="skipped_test",
                        severity="high",
                        message="Skipped test found - tests should not be skipped",
                        file=str(test_file.relative_to(self.project_root)),
                        line=i,
                    )

                    task = Task(
                        id=task_id,
                        type=TaskType.TEST,
                        domain=Domain.E2E,
                        description=f"Re-enable skipped test in {test_file.name}",
                        files=[str(test_file.relative_to(self.project_root))],
                        finding=finding,
                        conventions=DOMAIN_CONVENTIONS[Domain.E2E],
                        business_value=7,
                        risk_reduction=8,
                    )

                    self._enrich_task(task)
                    self.backlog.tasks.append(task)

    def _enrich_task(self, task: Task) -> None:
        """Enrich task with file content and context."""
        if not task.files:
            return

        file_path = self.project_root / task.files[0]
        if not file_path.exists():
            return

        try:
            content = file_path.read_text()
        except Exception:
            return

        # Extract relevant portion (around the error line)
        if task.finding.line:
            lines = content.splitlines()
            start = max(0, task.finding.line - 10)
            end = min(len(lines), task.finding.line + 10)
            task.file_content = "\n".join(lines[start:end])[:3000]
        else:
            task.file_content = content[:3000]

        # Extract imports
        if task.domain == Domain.RUST:
            task.imports = re.findall(r"^use .+;$", content, re.MULTILINE)[:20]
            task.types_defined = re.findall(
                r"^(?:pub\s+)?(?:struct|enum|trait|impl)\s+(\w+)", content, re.MULTILINE
            )
        elif task.domain == Domain.PYTHON:
            task.imports = re.findall(r"^(?:from|import) .+$", content, re.MULTILINE)[
                :20
            ]
            task.types_defined = re.findall(r"^class\s+(\w+)", content, re.MULTILINE)

    def _save_backlog(self) -> None:
        """Save backlog to JSON file."""
        BACKLOG_PATH.write_text(
            self.backlog.model_dump_json(indent=2, exclude_none=True)
        )
        logger.info(f"Backlog saved to {BACKLOG_PATH}")

    def load_backlog(self) -> Backlog:
        """Load existing backlog from disk."""
        if BACKLOG_PATH.exists():
            try:
                data = json.loads(BACKLOG_PATH.read_text())
                self.backlog = Backlog.model_validate(data)
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Failed to load backlog: {e}")
                self.backlog = Backlog()
        return self.backlog

    def get_status(self) -> dict:
        """Get backlog status summary."""
        self.load_backlog()
        self.backlog.update_stats()

        by_domain = {}
        for domain in Domain:
            tasks = self.backlog.get_tasks_by_domain(domain)
            by_domain[domain.value] = {
                "total": len(tasks),
                "pending": sum(1 for t in tasks if t.status == TaskStatus.PENDING),
                "completed": sum(1 for t in tasks if t.status == TaskStatus.COMPLETED),
                "failed": sum(1 for t in tasks if t.status == TaskStatus.FAILED),
            }

        return {
            "total_tasks": self.backlog.total_tasks,
            "pending": self.backlog.pending_count,
            "completed": self.backlog.completed_count,
            "failed": self.backlog.failed_count,
            "by_domain": by_domain,
            "updated": self.backlog.updated.isoformat(),
        }


async def main():
    """CLI entry point for RLM Brain."""
    import argparse

    parser = argparse.ArgumentParser(description="RLM Brain - Codebase Analyzer")
    parser.add_argument("--domain", choices=[d.value for d in Domain], help="Specific domain")
    parser.add_argument("--quick", action="store_true", help="Skip slow analyses")
    parser.add_argument("--status", action="store_true", help="Show backlog status")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    brain = RLMBrain()

    if args.status:
        status = brain.get_status()
        print(json.dumps(status, indent=2))
        return

    domain = Domain(args.domain) if args.domain else None
    await brain.analyze(domain=domain, quick=args.quick)


if __name__ == "__main__":
    asyncio.run(main())
