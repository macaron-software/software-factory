#!/usr/bin/env python3
"""
RUN PARALLEL WIGGUMS - Lance N Wiggums en parallèle
====================================================
Utilise MiniMax M2.1 Coding Plan (1000 prompts/5h)

Usage:
    python3 tools/lrm/run_parallel_wiggums.py [--workers 36]
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path("/Users/sylvain/_LAPOSTE/_SD3")
BACKLOG_FILE = PROJECT_ROOT / "tools" / "lrm" / "backlog_solaris.json"
LOGS_DIR = PROJECT_ROOT / "logs" / "lrm"

# Import Wiggum
sys.path.insert(0, str(PROJECT_ROOT / "tools" / "lrm"))
from wiggum_solaris import WiggumSolaris, AdversarialAgent, log

# Semaphore to limit concurrent API calls (avoid rate limit)
# MiniMax Coding Plan: 1000 prompts/5h = ~3.3 prompts/min
MAX_CONCURRENT = 50  # 50 parallel workers


async def process_task(worker_id: int, task: dict, semaphore: asyncio.Semaphore) -> dict:
    """Process a single task with a Wiggum"""
    async with semaphore:
        task_id = task.get("id", "unknown")
        log(f"[W{worker_id:02d}] Starting {task_id}: {task.get('description', '')[:50]}...")
        
        wiggum = WiggumSolaris()
        
        try:
            # Build prompt from task
            prompt = f"""
Tâche: {task.get('description', '')}

Composant: {task.get('component', '')}
Type: {task.get('type', '')}

Instructions:
1. Lire les specs Figma via MCP (solaris_component, solaris_variant)
2. Générer le code CSS/SCSS conforme
3. NE JAMAIS hardcoder de valeurs (borderRadius, padding, colors)
4. Utiliser les tokens du design system

Génère le code correctif.
"""
            
            # Call MiniMax
            result = await wiggum.call_wiggum(prompt)
            
            # Check for errors
            if result.startswith("Error:"):
                log(f"[W{worker_id:02d}] {task_id} FAILED: {result[:100]}")
                return {"id": task_id, "status": "failed", "error": result}
            
            # Run adversarial check
            approved, score, issues = wiggum.adversarial.analyze(result)
            
            if not approved:
                log(f"[W{worker_id:02d}] {task_id} SLOP detected (score={score})")
                return {"id": task_id, "status": "failed", "error": f"SLOP score={score}", "issues": issues}
            
            log(f"[W{worker_id:02d}] {task_id} COMPLETED")
            return {"id": task_id, "status": "completed", "result": result[:500]}
            
        except Exception as e:
            log(f"[W{worker_id:02d}] {task_id} EXCEPTION: {e}")
            return {"id": task_id, "status": "failed", "error": str(e)}


async def main(max_workers: int = 36, backlog_path: Path = None):
    """Launch parallel Wiggums"""
    backlog_file = backlog_path or BACKLOG_FILE
    log(f"=== PARALLEL WIGGUMS ({max_workers} workers) ===")
    log(f"Using MiniMax M2.1 Coding Plan")
    log(f"Backlog: {backlog_file}")
    
    # Load backlog
    with open(backlog_file) as f:
        backlog = json.load(f)
    
    # Get pending tasks
    pending = [t for t in backlog["tasks"] if t.get("status") == "pending"]
    log(f"Found {len(pending)} pending tasks")
    
    if not pending:
        log("No pending tasks!")
        return
    
    # Create semaphore
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    
    # Launch all tasks in parallel
    tasks = [
        process_task(i, task, semaphore) 
        for i, task in enumerate(pending)
    ]
    
    log(f"Launching {len(tasks)} Wiggums...")
    start = datetime.now()
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    elapsed = (datetime.now() - start).total_seconds()
    log(f"Completed in {elapsed:.1f}s")
    
    # Update backlog
    completed = 0
    failed = 0
    
    results_map = {}
    for r in results:
        if isinstance(r, dict):
            results_map[r["id"]] = r
    
    for task in backlog["tasks"]:
        if task["id"] in results_map:
            result = results_map[task["id"]]
            task["status"] = result["status"]
            if result["status"] == "completed":
                completed += 1
            else:
                failed += 1
                task["error"] = result.get("error", "")
    
    # Save backlog
    with open(backlog_file, "w") as f:
        json.dump(backlog, f, indent=2)
    
    log(f"=== RESULTS ===")
    log(f"Completed: {completed}")
    log(f"Failed: {failed}")
    if completed + failed > 0:
        log(f"Rate: {completed}/{completed+failed} = {100*completed/(completed+failed):.1f}%")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=50)
    parser.add_argument("--backlog", type=str, default=str(BACKLOG_FILE))
    args = parser.parse_args()
    
    asyncio.run(main(args.workers, Path(args.backlog)))
