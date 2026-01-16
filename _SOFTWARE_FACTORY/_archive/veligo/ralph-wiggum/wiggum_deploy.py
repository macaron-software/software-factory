#!/usr/bin/env python3
"""
wiggum_deploy.py - Wiggum Deploy Agent

Pipeline de déploiement avec validation E2E et load tests:
1. Deploy staging via veligo CLI
2. Run Playwright smoke E2E
3. Run Playwright journey E2E (si risk)
4. Run load tests k6 (si perf-risk)
5. Deploy prod
6. Run Playwright prod smoke
7. Chaos tests (optionnel, staging only)

Usage:
    python3 wiggum_deploy.py --task D001
    python3 wiggum_deploy.py --task D001 --skip-load
"""

import os
import sys
import json
import subprocess
import time
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime

# ============================================================================
# CONFIG
# ============================================================================
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent.parent
TASKS_DIR = SCRIPT_DIR / "tasks"
STATUS_DIR = SCRIPT_DIR / "status"
LOGS_DIR = SCRIPT_DIR / "logs"

# Timeouts
E2E_TIMEOUT = 600       # 10 min pour E2E
LOAD_TIMEOUT = 300      # 5 min pour load tests
DEPLOY_TIMEOUT = 900    # 15 min pour deploy (build + rsync)

# Retry policy
MAX_E2E_RETRIES = 2     # 1 retry si flaky
MAX_DEPLOY_RETRIES = 1

# Colors
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
BLUE = "\033[0;34m"
NC = "\033[0m"

def log(msg: str, color: str = NC):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{color}[DEPLOY {ts}] {msg}{NC}")

def log_step(step: int, msg: str):
    log(f"[{step}/7] {msg}", BLUE)

# ============================================================================
# DATA STRUCTURES
# ============================================================================
@dataclass
class DeployResult:
    """Résultat d'une étape de déploiement."""
    step: str
    success: bool
    output: str
    duration_ms: int
    retries: int = 0

@dataclass
class DeployReport:
    """Rapport complet de déploiement."""
    task_id: str
    timestamp: str
    steps: List[DeployResult] = field(default_factory=list)
    success: bool = True
    environment: str = ""

    def add_step(self, result: DeployResult):
        self.steps.append(result)
        if not result.success:
            self.success = False

    def summary(self) -> str:
        lines = [f"=== Deploy Report: {self.task_id} ({self.environment}) ==="]
        for s in self.steps:
            icon = "✓" if s.success else "✗"
            lines.append(f"  {icon} {s.step} ({s.duration_ms}ms, retries={s.retries})")
        lines.append(f"  {'SUCCESS' if self.success else 'FAILED'}")
        return "\n".join(lines)

# ============================================================================
# DEPLOYMENT STEPS
# ============================================================================
class DeployPipeline:
    """Pipeline de déploiement complet."""

    def __init__(self, task_id: str, task_file: Path):
        self.task_id = task_id
        self.task_file = task_file
        self.task_content = task_file.read_text() if task_file.exists() else ""
        self.report = DeployReport(
            task_id=task_id,
            timestamp=datetime.now().isoformat()
        )
        self.log_file = LOGS_DIR / f"deploy_{task_id}_{datetime.now():%Y%m%d_%H%M%S}.log"

    def _run_command(self, cmd: str, timeout: int = 120, cwd: Optional[Path] = None) -> Tuple[int, str]:
        """Execute a command and return (exit_code, output)."""
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                timeout=timeout,
                cwd=str(cwd or PROJECT_ROOT)
            )
            # Handle encoding safely - some CLI tools output non-UTF8
            try:
                output = result.stdout.decode('utf-8', errors='replace') + result.stderr.decode('utf-8', errors='replace')
            except Exception:
                output = str(result.stdout) + str(result.stderr)
            return result.returncode, output[:10000]
        except subprocess.TimeoutExpired:
            return 124, "Command timed out"
        except Exception as e:
            return 1, str(e)

    def _log_to_file(self, msg: str):
        """Append to log file."""
        with open(self.log_file, "a") as f:
            f.write(f"[{datetime.now():%H:%M:%S}] {msg}\n")

    def _is_perf_risk(self) -> bool:
        """Check if task is marked as perf-risk."""
        return "perf-risk" in self.task_content.lower() or \
               "performance" in self.task_content.lower() or \
               "database" in self.task_content.lower() or \
               "query" in self.task_content.lower()

    def _is_critical_path(self) -> bool:
        """Check if task is on critical path."""
        return "P0" in self.task_content or \
               "critical" in self.task_content.lower() or \
               "auth" in self.task_content.lower() or \
               "payment" in self.task_content.lower()

    # ========================================================================
    # STEP 1: Deploy to Staging
    # ========================================================================
    def deploy_staging(self) -> DeployResult:
        """Deploy to staging environment."""
        log_step(1, "Deploying to staging...")
        start = time.time()

        # Use veligo CLI - real deploy to staging/prod
        # Staging and prod share the same infra, deploy actually pushes code
        code, output = self._run_command(
            "veligo deploy rsync 2>&1",
            timeout=DEPLOY_TIMEOUT
        )

        duration = int((time.time() - start) * 1000)
        success = code == 0

        self._log_to_file(f"STAGING DEPLOY: code={code}\n{output}")

        result = DeployResult(
            step="deploy-staging",
            success=success,
            output=output[:500],
            duration_ms=duration
        )
        self.report.add_step(result)
        self.report.environment = "staging"

        if success:
            log("Staging deploy: SUCCESS", GREEN)
        else:
            log(f"Staging deploy: FAILED\n{output[:200]}", RED)

        return result

    # ========================================================================
    # STEP 2: Playwright Smoke E2E
    # ========================================================================
    def run_e2e_smoke(self, env: str = "staging") -> DeployResult:
        """Run Playwright smoke tests."""
        log_step(2, f"Running E2E smoke tests ({env})...")
        start = time.time()

        retries = 0
        success = False
        output = ""

        for attempt in range(MAX_E2E_RETRIES + 1):
            # Run critical page smoke tests - verify pages render (not blank)
            # Uses dedicated smoke-check tests that detect JS errors and blank pages
            code, output = self._run_command(
                f"npx playwright test smoke-check/critical-pages.spec.ts --project=idfm-chromium --reporter=list 2>&1",
                timeout=E2E_TIMEOUT,
                cwd=PROJECT_ROOT / "veligo-platform" / "tests" / "e2e"
            )
            success = code == 0

            if success:
                break
            retries = attempt + 1
            log(f"E2E smoke attempt {retries} failed, retrying...", YELLOW)
            time.sleep(5)

        duration = int((time.time() - start) * 1000)

        self._log_to_file(f"E2E SMOKE ({env}): code={code}, retries={retries}\n{output}")

        result = DeployResult(
            step=f"e2e-smoke-{env}",
            success=success,
            output=output[:500],
            duration_ms=duration,
            retries=retries
        )
        self.report.add_step(result)

        if success:
            log(f"E2E smoke ({env}): PASS", GREEN)
        else:
            log(f"E2E smoke ({env}): FAIL after {retries} retries", RED)

        return result

    # ========================================================================
    # STEP 3: Playwright Journey E2E (si critical)
    # ========================================================================
    def run_e2e_journey(self, env: str = "staging") -> DeployResult:
        """Run Playwright journey tests for critical paths."""
        log_step(3, f"Running E2E journey tests ({env})...")

        if not self._is_critical_path():
            log("Skipping journey tests (not critical path)", YELLOW)
            return DeployResult(
                step=f"e2e-journey-{env}",
                success=True,
                output="Skipped - not critical path",
                duration_ms=0
            )

        start = time.time()

        code, output = self._run_command(
            f"npx playwright test --project=journey --reporter=list 2>&1",
            timeout=E2E_TIMEOUT * 2,
            cwd=PROJECT_ROOT / "veligo-platform" / "frontend"
        )

        duration = int((time.time() - start) * 1000)
        success = code == 0

        self._log_to_file(f"E2E JOURNEY ({env}): code={code}\n{output}")

        result = DeployResult(
            step=f"e2e-journey-{env}",
            success=success,
            output=output[:500],
            duration_ms=duration
        )
        self.report.add_step(result)

        if success:
            log(f"E2E journey ({env}): PASS", GREEN)
        else:
            log(f"E2E journey ({env}): FAIL", RED)

        return result

    # ========================================================================
    # STEP 4: Load Tests (si perf-risk)
    # ========================================================================
    def run_load_tests(self, env: str = "staging") -> DeployResult:
        """Run k6 load tests."""
        log_step(4, f"Running load tests ({env})...")

        if not self._is_perf_risk():
            log("Skipping load tests (not perf-risk)", YELLOW)
            return DeployResult(
                step=f"load-test-{env}",
                success=True,
                output="Skipped - not perf-risk",
                duration_ms=0
            )

        start = time.time()

        # Check if k6 is available
        k6_script = PROJECT_ROOT / "veligo-platform" / "tests" / "perf" / "smoke.js"

        if not k6_script.exists():
            log("k6 script not found, skipping", YELLOW)
            return DeployResult(
                step=f"load-test-{env}",
                success=True,
                output="Skipped - no k6 script",
                duration_ms=0
            )

        code, output = self._run_command(
            f"k6 run --quiet {k6_script} 2>&1",
            timeout=LOAD_TIMEOUT
        )

        duration = int((time.time() - start) * 1000)

        # Parse k6 output for thresholds
        success = code == 0 and "✓" in output

        self._log_to_file(f"LOAD TEST ({env}): code={code}\n{output}")

        result = DeployResult(
            step=f"load-test-{env}",
            success=success,
            output=output[:500],
            duration_ms=duration
        )
        self.report.add_step(result)

        if success:
            log(f"Load tests ({env}): PASS", GREEN)
        else:
            log(f"Load tests ({env}): FAIL", RED)

        return result

    # ========================================================================
    # STEP 5: Deploy to Production
    # ========================================================================
    def deploy_prod(self) -> DeployResult:
        """Deploy to production."""
        log_step(5, "Deploying to production...")
        start = time.time()

        # Use veligo CLI
        code, output = self._run_command(
            "veligo deploy rsync --env prod 2>&1 || veligo cicd deploy --env prod 2>&1",
            timeout=DEPLOY_TIMEOUT
        )

        duration = int((time.time() - start) * 1000)
        success = code == 0

        self._log_to_file(f"PROD DEPLOY: code={code}\n{output}")

        result = DeployResult(
            step="deploy-prod",
            success=success,
            output=output[:500],
            duration_ms=duration
        )
        self.report.add_step(result)
        self.report.environment = "prod"

        if success:
            log("Prod deploy: SUCCESS", GREEN)
        else:
            log(f"Prod deploy: FAILED\n{output[:200]}", RED)

        return result

    # ========================================================================
    # STEP 6: Prod Smoke E2E
    # ========================================================================
    def run_prod_smoke(self) -> DeployResult:
        """Run smoke tests on production."""
        log_step(6, "Running prod smoke E2E...")
        return self.run_e2e_smoke("prod")

    # ========================================================================
    # STEP 7: Chaos Tests (optional, staging only)
    # ========================================================================
    def run_chaos_tests(self) -> DeployResult:
        """Run chaos monkey tests on staging."""
        log_step(7, "Running chaos tests (staging)...")

        chaos_script = PROJECT_ROOT / "veligo-platform" / "tests" / "chaos" / "run.sh"

        if not chaos_script.exists():
            log("Chaos script not found, skipping", YELLOW)
            return DeployResult(
                step="chaos-test",
                success=True,
                output="Skipped - no chaos script",
                duration_ms=0
            )

        start = time.time()

        code, output = self._run_command(
            f"bash {chaos_script} 2>&1",
            timeout=E2E_TIMEOUT
        )

        duration = int((time.time() - start) * 1000)
        success = code == 0

        self._log_to_file(f"CHAOS TEST: code={code}\n{output}")

        result = DeployResult(
            step="chaos-test",
            success=success,
            output=output[:500],
            duration_ms=duration
        )
        self.report.add_step(result)

        if success:
            log("Chaos tests: PASS", GREEN)
        else:
            log("Chaos tests: FAIL (non-blocking)", YELLOW)

        return result

    # ========================================================================
    # FULL PIPELINE
    # ========================================================================
    def run(self, skip_load: bool = False, skip_chaos: bool = False, staging_only: bool = False) -> DeployReport:
        """Run full deployment pipeline."""
        log(f"=== Starting Deploy Pipeline for {self.task_id} ===", BLUE)

        # Step 1: Deploy staging
        result = self.deploy_staging()
        if not result.success:
            return self.report

        # Step 2: E2E smoke staging
        result = self.run_e2e_smoke("staging")
        if not result.success:
            return self.report

        # Step 3: E2E journey staging (if critical)
        result = self.run_e2e_journey("staging")
        if not result.success:
            return self.report

        # Step 4: Load tests (if perf-risk)
        if not skip_load:
            result = self.run_load_tests("staging")
            if not result.success:
                return self.report

        if staging_only:
            log("Staging-only mode, stopping here", YELLOW)
            return self.report

        # Step 5: Deploy prod
        result = self.deploy_prod()
        if not result.success:
            return self.report

        # Step 6: Prod smoke
        result = self.run_prod_smoke()
        if not result.success:
            # ROLLBACK would go here
            log("PROD SMOKE FAILED - Manual rollback may be needed!", RED)
            return self.report

        # Step 7: Chaos tests (optional)
        if not skip_chaos:
            self.run_chaos_tests()  # Non-blocking

        log(f"=== Deploy Pipeline {'COMPLETE' if self.report.success else 'FAILED'} ===",
            GREEN if self.report.success else RED)

        return self.report


# ============================================================================
# TASK STATUS MANAGEMENT
# ============================================================================
def update_task_status(task_id: str, status: str, report: Optional[DeployReport] = None):
    """Update task status and optionally append report."""
    status_file = STATUS_DIR / f"{task_id}.status"
    status_file.write_text(f"{status}\n")

    if report:
        task_file = TASKS_DIR / f"{task_id}.md"
        if task_file.exists():
            content = task_file.read_text()
            content += f"\n\n## Deploy Report ({report.timestamp})\n```\n{report.summary()}\n```\n"
            task_file.write_text(content)


def create_fix_task_from_failure(deploy_task_id: str, report: DeployReport) -> Optional[str]:
    """
    Create a new T* task to fix the issue detected during deployment.
    Returns the new task ID or None if no task was created.

    This closes the RLM feedback loop:
    Brain → T* (TDD) → D* (Deploy) → [FAILURE] → T* (Fix) → D* (Deploy) → ...
    """
    # Find the failed step
    failed_step = None
    for step in report.steps:
        if not step.success:
            failed_step = step
            break

    if not failed_step:
        return None

    # Extract error details from output
    error_summary = failed_step.output[:300] if failed_step.output else "Unknown error"

    # Parse specific errors from output
    blocking_errors = []
    if "Unexpected token" in error_summary:
        blocking_errors.append("JSON parse error - endpoint returning HTML instead of JSON")
    if "405" in error_summary:
        blocking_errors.append("gRPC-Web proxy not configured (405 Method Not Allowed)")
    if "UNIMPLEMENTED" in error_summary:
        blocking_errors.append("gRPC method not implemented on backend")
    if "blank" in error_summary.lower() or "renders content" in error_summary.lower():
        blocking_errors.append("Page renders blank - JS error blocking render")

    # Find next T* task ID
    existing_tasks = list(TASKS_DIR.glob("T*.md"))
    max_num = 0
    for f in existing_tasks:
        try:
            num = int(f.stem[1:])
            max_num = max(max_num, num)
        except ValueError:
            pass

    new_task_id = f"T{max_num + 1:03d}"

    # Create task content
    error_list = "\n".join(f"- {e}" for e in blocking_errors) if blocking_errors else f"- {error_summary}"

    task_content = f"""# Fix Task {new_task_id}: Fix deployment failure from {deploy_task_id}

**Priority**: P0
**Queue**: TDD
**Source**: Wiggum Deploy (automatic feedback loop)
**Created**: {datetime.now().isoformat()}

## Problem Detected

Deployment step `{failed_step.step}` failed during {deploy_task_id}.

### Errors Identified

{error_list}

### Raw Output

```
{failed_step.output[:500]}
```

## Required Fix

1. Identify the root cause of the failure
2. Implement the fix (backend gRPC, frontend fallback, or nginx config)
3. Write E2E test that verifies the fix
4. Ensure smoke tests pass before marking complete

## Acceptance Criteria

- [ ] The failed step `{failed_step.step}` passes on retry
- [ ] No new regressions introduced
- [ ] E2E smoke tests all pass

## Ralph Status Block
---RALPH_STATUS---
STATUS: PENDING
QUEUE: TDD
PRIORITY: P0
CREATED_BY: WIGGUM_DEPLOY
SOURCE_DEPLOY: {deploy_task_id}
---END_RALPH_STATUS---
"""

    # Write task file
    task_file = TASKS_DIR / f"{new_task_id}.md"
    task_file.write_text(task_content)

    # Set status to PENDING
    status_file = STATUS_DIR / f"{new_task_id}.status"
    status_file.write_text("PENDING\n")

    log(f"Created fix task {new_task_id} for failure in {deploy_task_id}", YELLOW)

    return new_task_id


def get_pending_deploy_tasks() -> List[Tuple[str, Path]]:
    """Get list of pending deploy tasks (D*.md)."""
    pending = []

    for task_file in TASKS_DIR.glob("D*.md"):
        task_id = task_file.stem
        status_file = STATUS_DIR / f"{task_id}.status"

        if status_file.exists():
            status = status_file.read_text().strip()
            if status == "PENDING":
                pending.append((task_id, task_file))

    return pending


# ============================================================================
# MAIN
# ============================================================================
def main():
    import argparse

    parser = argparse.ArgumentParser(description="Wiggum Deploy Agent")
    parser.add_argument("--task", "-t", help="Specific task ID to deploy (D001)")
    parser.add_argument("--all", "-a", action="store_true", help="Process all pending deploy tasks")
    parser.add_argument("--skip-load", action="store_true", help="Skip load tests")
    parser.add_argument("--skip-chaos", action="store_true", help="Skip chaos tests")
    parser.add_argument("--staging-only", action="store_true", help="Deploy to staging only")

    args = parser.parse_args()

    LOGS_DIR.mkdir(exist_ok=True)

    if args.task:
        task_id = args.task
        task_file = TASKS_DIR / f"{task_id}.md"

        if not task_file.exists():
            log(f"Task file not found: {task_file}", RED)
            return 1

        update_task_status(task_id, "IN_PROGRESS")

        pipeline = DeployPipeline(task_id, task_file)
        report = pipeline.run(
            skip_load=args.skip_load,
            skip_chaos=args.skip_chaos,
            staging_only=args.staging_only
        )

        print(report.summary())

        if report.success:
            update_task_status(task_id, "COMPLETE", report)
            return 0
        else:
            update_task_status(task_id, "FAILED", report)
            # RLM Feedback Loop: Create fix task for Wiggum TDD
            fix_task_id = create_fix_task_from_failure(task_id, report)
            if fix_task_id:
                log(f"RLM Feedback: Created {fix_task_id} → Wiggum TDD will process", YELLOW)
            return 1

    elif args.all:
        pending = get_pending_deploy_tasks()
        log(f"Found {len(pending)} pending deploy tasks", BLUE)

        for task_id, task_file in pending:
            log(f"Processing {task_id}...", BLUE)

            update_task_status(task_id, "IN_PROGRESS")

            pipeline = DeployPipeline(task_id, task_file)
            report = pipeline.run(
                skip_load=args.skip_load,
                skip_chaos=args.skip_chaos,
                staging_only=args.staging_only
            )

            if report.success:
                update_task_status(task_id, "COMPLETE", report)
            else:
                update_task_status(task_id, "FAILED", report)
                # RLM Feedback Loop: Create fix task for Wiggum TDD
                fix_task_id = create_fix_task_from_failure(task_id, report)
                if fix_task_id:
                    log(f"RLM Feedback: Created {fix_task_id} → Wiggum TDD will process", YELLOW)
                log(f"Task {task_id} failed, continuing with feedback loop", YELLOW)
                # Don't stop - let the fix task be processed by TDD

        return 0

    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    exit(main())
