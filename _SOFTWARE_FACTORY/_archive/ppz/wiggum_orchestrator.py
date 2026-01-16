#!/usr/bin/env python3 -u
"""
Wiggum Orchestrator - Parallel TDD Pipeline
============================================

Lance plusieurs Wiggum TDD en parallèle pour traiter le backlog rapidement.

Usage:
    python3 wiggum_orchestrator.py                    # Default 10 workers
    python3 wiggum_orchestrator.py --workers 50      # 50 parallel workers
    python3 wiggum_orchestrator.py --all             # Process ALL pending tasks
"""

import asyncio
import json
import subprocess
from datetime import datetime
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import multiprocessing

# Setup
RLM_DIR = Path(__file__).parent
POPINZ_ROOT = Path("/Users/sylvain/_POPINZ/popinz-dev")
RUST_DIR = POPINZ_ROOT / "popinz-v2-rust"

# Files
BACKLOG_FILE = RLM_DIR / "backlog_tasks.json"
DEPLOY_BACKLOG = RLM_DIR / "deploy_backlog.json"
RESULTS_FILE = RLM_DIR / "orchestrator_results.json"


def log(msg: str, level: str = "INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [ORCHESTRATOR] [{level}] {msg}", flush=True)


def load_backlog() -> dict:
    if BACKLOG_FILE.exists():
        return json.loads(BACKLOG_FILE.read_text())
    return {"tasks": [], "updated": None}


def save_backlog(data: dict):
    data["updated"] = datetime.now().isoformat()
    BACKLOG_FILE.write_text(json.dumps(data, indent=2))


def get_pending_tasks(domain_filter: str = None) -> list:
    """Get all pending tasks, optionally filtered by domain"""
    data = load_backlog()
    tasks = data.get("tasks", [])
    pending = [t for t in tasks if t.get("status") == "pending"]

    if domain_filter:
        pending = [t for t in pending if t.get("domain") == domain_filter]

    # Sort by WSJF score
    pending.sort(key=lambda t: -t.get("wsjf_score", 0))
    return pending


def process_task_sync(task: dict) -> dict:
    """Process a single task synchronously (for parallel execution)"""
    task_id = task.get("id", "unknown")
    domain = task.get("domain", "unknown")
    finding = task.get("finding", {})

    result = {
        "task_id": task_id,
        "success": False,
        "action": None,
        "error": None
    }

    try:
        # Determine action based on finding type
        finding_type = finding.get("type", "unknown")
        file_path = finding.get("file", "")
        line = finding.get("line", 0)
        message = finding.get("message", "")

        # For now, just log the task - real fixes need more context
        if finding_type == "build_error":
            result["action"] = "needs_manual_fix"
            result["details"] = f"Build error in {file_path}"
        elif finding_type == "todo":
            result["action"] = "acknowledged"
            result["details"] = f"TODO at {file_path}:{line}"
        elif finding_type == "security":
            result["action"] = "flagged_for_review"
            result["details"] = message
        elif finding_type == "test_config":
            result["action"] = "flagged_for_review"
            result["details"] = f"test.skip/only in {file_path}"
        elif finding_type == "documentation":
            result["action"] = "low_priority"
            result["details"] = message
        else:
            result["action"] = "acknowledged"
            result["details"] = message

        result["success"] = True

    except Exception as e:
        result["error"] = str(e)

    return result


async def run_parallel_tdd(workers: int = 10, max_tasks: int = None, domain: str = None):
    """Run TDD on multiple tasks in parallel"""
    log("=" * 60)
    log(f"WIGGUM ORCHESTRATOR - Parallel Processing")
    log(f"Workers: {workers} | Max tasks: {max_tasks or 'ALL'}")
    log("=" * 60)

    # Get pending tasks
    pending = get_pending_tasks(domain_filter=domain)

    if max_tasks:
        pending = pending[:max_tasks]

    total = len(pending)
    log(f"\nProcessing {total} tasks with {workers} parallel workers...")

    if total == 0:
        log("No pending tasks to process")
        return

    # Group tasks by domain for better processing
    by_domain = {}
    for task in pending:
        d = task.get("domain", "other")
        if d not in by_domain:
            by_domain[d] = []
        by_domain[d].append(task)

    log(f"\nTasks by domain:")
    for d, tasks in by_domain.items():
        log(f"  {d}: {len(tasks)}")

    # Process tasks in parallel using ThreadPoolExecutor
    results = {"processed": 0, "success": 0, "failed": 0, "by_action": {}}

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_task_sync, task): task for task in pending}

        for i, future in enumerate(asyncio.as_completed([asyncio.wrap_future(f) for f in futures])):
            try:
                result = await future
                results["processed"] += 1

                if result["success"]:
                    results["success"] += 1
                    action = result.get("action", "unknown")
                    results["by_action"][action] = results["by_action"].get(action, 0) + 1
                else:
                    results["failed"] += 1

                # Progress update every 50 tasks
                if results["processed"] % 50 == 0:
                    log(f"  Progress: {results['processed']}/{total} ({results['success']} OK, {results['failed']} FAIL)")

            except Exception as e:
                results["failed"] += 1
                log(f"  Error: {e}", "ERROR")

    # Update backlog with results
    log(f"\n[PHASE 2] Updating backlog...")
    data = load_backlog()

    processed_ids = {task["id"] for task in pending}
    for task in data.get("tasks", []):
        if task["id"] in processed_ids:
            task["status"] = "reviewed"
            task["reviewed_at"] = datetime.now().isoformat()

    save_backlog(data)

    # Save results
    results["completed_at"] = datetime.now().isoformat()
    RESULTS_FILE.write_text(json.dumps(results, indent=2))

    # Summary
    log("\n" + "=" * 60)
    log("ORCHESTRATOR COMPLETE")
    log("=" * 60)
    log(f"\nResults:")
    log(f"  Processed: {results['processed']}/{total}")
    log(f"  Success: {results['success']}")
    log(f"  Failed: {results['failed']}")
    log(f"\nActions breakdown:")
    for action, count in sorted(results["by_action"].items(), key=lambda x: -x[1]):
        log(f"  {action}: {count}")

    return results


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Wiggum Orchestrator - Parallel TDD")
    parser.add_argument("--workers", type=int, default=10, help="Number of parallel workers")
    parser.add_argument("--max", type=int, help="Maximum tasks to process")
    parser.add_argument("--domain", type=str, help="Filter by domain")
    parser.add_argument("--all", action="store_true", help="Process all pending tasks")
    args = parser.parse_args()

    max_tasks = None if args.all else (args.max or 100)

    await run_parallel_tdd(
        workers=args.workers,
        max_tasks=max_tasks,
        domain=args.domain
    )


if __name__ == "__main__":
    asyncio.run(main())
