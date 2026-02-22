#!/usr/bin/env python3
"""
Real A/B Test Runner: Standard vs Fractal

Runs Wiggum on two identical tasks:
- A: Standard (skip_fractal=True)
- B: Fractal (skip_fractal=False)

Captures generated code and compares.
"""

import asyncio
import json
import os
import sys
import sqlite3
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.task_store import TaskStore, TaskStatus
from core.wiggum_tdd import WiggumWorker
from core.adversarial import AdversarialGate
from core.fractal import FractalDecomposer
from core.project_registry import get_project
from tests.ab_fractal_test import analyze_code, print_comparison


class DisabledDecomposer:
    """Fake decomposer that never decomposes (for Standard mode)."""

    def should_decompose(self, task_dict, current_depth):
        class FakeAnalysis:
            reason = "disabled for A/B test"
        return False, FakeAnalysis()

    async def decompose(self, task_dict, current_depth):
        return []


class ABTestRunner:
    """Runs A/B test between Standard and Fractal Wiggum."""

    def __init__(self, project_id: str = "psy"):
        self.project_id = project_id
        self.task_store = TaskStore()
        self.results = {"standard": None, "fractal": None}
        self.generated_code = {"standard": "", "fractal": ""}

        # Get project config
        self.project = get_project(project_id)
        if not self.project:
            raise ValueError(f"Project {project_id} not found")

    def get_subtasks(self, parent_id: str) -> list:
        """Get subtasks by parent_id using direct SQL query."""
        db_path = Path(__file__).parent.parent / "data" / "factory.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM tasks WHERE parent_id = ? ORDER BY created_at",
            (parent_id,)
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    async def run_single_task(self, task_id: str, mode: str) -> dict:
        """Run Wiggum on a single task and capture output."""
        print(f"\n{'='*60}")
        print(f"Running {mode.upper()} mode on task: {task_id}")
        print(f"{'='*60}\n")

        # Get task
        task = self.task_store.get_task(task_id)
        if not task:
            print(f"ERROR: Task {task_id} not found")
            return None

        # Create components
        adversarial = AdversarialGate()

        if mode == "standard":
            decomposer = DisabledDecomposer()
        else:
            decomposer = FractalDecomposer(self.project)

        # Create Wiggum worker
        worker = WiggumWorker(
            worker_id=f"ab-test-{mode}",
            project=self.project,
            task_store=self.task_store,
            adversarial=adversarial,
            decomposer=decomposer,
        )

        start_time = time.time()

        try:
            # Run TDD cycle
            result = await worker.run_single(task)
            elapsed = time.time() - start_time

            print(f"\n{mode.upper()} completed in {elapsed:.1f}s")
            print(f"Result: success={result.success}, iterations={result.iterations}")

            # Get updated task to see what was generated
            updated_task = self.task_store.get_task(task_id)
            status = updated_task.status if updated_task else "unknown"
            print(f"Status: {status}")

            return {
                "task_id": task_id,
                "mode": mode,
                "elapsed": elapsed,
                "success": result.success,
                "iterations": result.iterations,
                "status": str(status),
            }

        except Exception as e:
            print(f"ERROR in {mode}: {e}")
            import traceback
            traceback.print_exc()
            return {"task_id": task_id, "mode": mode, "error": str(e)}

    async def run_ab_test(self):
        """Run the full A/B test."""
        print("\n" + "=" * 70)
        print("         A/B TEST: STANDARD vs FRACTAL IMPLEMENTATION")
        print("=" * 70)

        # Run Standard (A)
        self.results["standard"] = await self.run_single_task(
            "ab-test-standard-001", "standard"
        )

        # Reset task B to pending for fresh run
        self.task_store.unlock_task("ab-test-fractal-001")

        # Run Fractal (B)
        self.results["fractal"] = await self.run_single_task(
            "ab-test-fractal-001", "fractal"
        )

        # Analyze results
        self.analyze_results()

    def analyze_results(self):
        """Analyze and compare the generated code."""
        print("\n" + "=" * 70)
        print("                    ANALYSIS")
        print("=" * 70)

        # Check for subtasks (FRACTAL decomposition)
        print("\n### FRACTAL DECOMPOSITION ###")

        subtasks = self.get_subtasks("ab-test-fractal-001")
        if subtasks:
            print(f"\nFRACTAL created {len(subtasks)} subtasks:")
            for st in subtasks:
                print(f"  - {st['id']}: {st['status']}")
        else:
            print("No subtasks created by FRACTAL")

        # Summary from results
        print("\n### EXECUTION SUMMARY ###")
        for mode in ["standard", "fractal"]:
            r = self.results[mode]
            if r:
                if "error" in r:
                    print(f"{mode.upper()}: ERROR - {r['error']}")
                else:
                    print(f"{mode.upper()}: {r['status']} in {r.get('elapsed', 0):.1f}s, iterations={r.get('iterations', 0)}")


async def main():
    runner = ABTestRunner("psy")
    await runner.run_ab_test()


if __name__ == "__main__":
    asyncio.run(main())
