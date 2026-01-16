#!/usr/bin/env python3
"""
RUN PARALLEL WIGGUMS - Claude Opus 4.5
======================================
Lance N Wiggums en parallèle avec Claude Opus 4.5 headless.

Usage:
    python3 tools/lrm/run_wiggums_claude.py [--workers 12]
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path("/Users/sylvain/_LAPOSTE/_SD3")
BACKLOG_FILE = PROJECT_ROOT / "tools" / "lrm" / "backlog_solaris.json"
COMPLETED_FILE = PROJECT_ROOT / "tools" / "lrm" / "completed_solaris.json"
LOGS_DIR = PROJECT_ROOT / "logs" / "lrm"

# Claude config - Use Sonnet for speed
CLAUDE_MODEL = "claude-sonnet-4-20250514"

# Semaphore for concurrent calls (limit to avoid rate limits)
MAX_CONCURRENT = 2


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


# Import Adversarial from wiggum_solaris
sys.path.insert(0, str(PROJECT_ROOT / "tools" / "lrm"))
from wiggum_solaris import AdversarialAgent


async def call_claude(prompt: str) -> str:
    """Call Claude Sonnet via headless CLI from temp dir (no project context)"""
    import tempfile
    
    try:
        # Run from temp dir to avoid project tool context
        proc = await asyncio.create_subprocess_exec(
            "claude",
            "-p",
            "--model", CLAUDE_MODEL,
            "--max-turns", "1",  # Just 1 turn - pure text generation
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE,
            cwd="/tmp"  # Run from temp to avoid project tools
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=prompt.encode()),
            timeout=300,  # 5 min timeout
        )
        
        if proc.returncode == 0:
            return stdout.decode()[:20000]
        else:
            return f"Error: Claude returned {proc.returncode} - {stderr.decode()[:200]}"
    except asyncio.TimeoutError:
        return "Error: Claude timeout (5min)"
    except Exception as e:
        return f"Error: {e}"


async def process_task(worker_id: int, task: dict, semaphore: asyncio.Semaphore, adversarial: AdversarialAgent) -> dict:
    """Process a single task with a Wiggum"""
    async with semaphore:
        task_id = task.get("id", "unknown")
        description = task.get("description", "")
        components = task.get("components", [])
        criteria = task.get("acceptance_criteria", [])
        
        log(f"[W{worker_id:02d}] Starting {task_id}: {description[:50]}...")
        
        # Build prompt
        prompt = f"""Expert Design System developer task for Solaris (La Poste).

TASK: {description}
COMPONENTS: {', '.join(components[:3]) if components else 'design-system/knowledge'}
ACCEPTANCE CRITERIA:
{chr(10).join(f'- {c}' for c in criteria[:5]) if criteria else '- Complete the task'}

CONTEXT:
- Design System Solaris uses WCAG patterns stored in design-system/knowledge/2-wcag-patterns/
- All values must come from Figma via MCP (solaris_variant, solaris_component)
- Interactive JS goes in generated-pages/solaris-interactive.js

Generate the complete implementation as a JSON file content for the knowledge base:"""
        
        # Retry loop with adversarial control
        max_retries = 3
        last_issues = []
        
        for attempt in range(1, max_retries + 1):
            log(f"[W{worker_id:02d}] {task_id} attempt {attempt}/{max_retries}...")
            
            response = await call_claude(prompt)
            
            # Check for errors
            if response.startswith("Error:"):
                log(f"[W{worker_id:02d}] {task_id} LLM error: {response[:80]}")
                if attempt < max_retries:
                    await asyncio.sleep(5)
                    continue
                return {"id": task_id, "status": "failed", "error": response}
            
            # Adversarial check
            approved, score, issues = adversarial.analyze(response, description)
            
            if approved:
                log(f"[W{worker_id:02d}] {task_id} APPROVED (score={score})")
                return {"id": task_id, "status": "completed", "result": response[:5000], "score": score}
            else:
                log(f"[W{worker_id:02d}] {task_id} REJECTED (score={score})")
                for issue in issues[:3]:
                    log(f"[W{worker_id:02d}]   - {issue}")
                last_issues = issues
                
                # Add feedback for retry
                feedback = adversarial.format_feedback(issues)
                prompt = f"{feedback}\n\n{prompt}"
                
                await asyncio.sleep(2)
        
        log(f"[W{worker_id:02d}] {task_id} FAILED after {max_retries} attempts")
        return {"id": task_id, "status": "failed", "error": "max_retries", "issues": last_issues}


async def main(max_workers: int = 12):
    """Launch parallel Wiggums"""
    log(f"=== PARALLEL WIGGUMS ({max_workers} workers) ===")
    log(f"Using Claude Opus 4.5 headless")
    
    # Load backlog
    with open(BACKLOG_FILE) as f:
        backlog = json.load(f)
    
    tasks = backlog.get("tasks", [])
    
    # Load completed to filter
    completed_ids = set()
    if COMPLETED_FILE.exists():
        with open(COMPLETED_FILE) as f:
            completed = json.load(f)
        for item in completed.get("completed", []):
            if isinstance(item, dict) and "task" in item:
                completed_ids.add(item["task"].get("id"))
    
    pending = [t for t in tasks if t.get("id") not in completed_ids]
    
    log(f"Found {len(pending)} pending tasks (of {len(tasks)} total)")
    
    if not pending:
        log("No pending tasks!")
        return
    
    # Create semaphore and adversarial
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    adversarial = AdversarialAgent()
    
    # Launch all tasks
    tasks_coros = [
        process_task(i, task, semaphore, adversarial) 
        for i, task in enumerate(pending[:max_workers])
    ]
    
    log(f"Launching {len(tasks_coros)} Wiggums...")
    start = datetime.now()
    
    results = await asyncio.gather(*tasks_coros, return_exceptions=True)
    
    elapsed = (datetime.now() - start).total_seconds()
    log(f"Completed in {elapsed:.1f}s")
    
    # Process results
    completed_list = []
    failed_list = []
    
    for r in results:
        if isinstance(r, Exception):
            failed_list.append({"error": str(r)})
        elif isinstance(r, dict):
            if r.get("status") == "completed":
                completed_list.append({"task": {"id": r["id"]}, "result": r.get("result", ""), "score": r.get("score", 0)})
            else:
                failed_list.append({"task": {"id": r["id"]}, "error": r.get("error", ""), "issues": r.get("issues", [])})
    
    # Save results
    output = {
        "completed": completed_list,
        "failed": failed_list,
        "updated_at": datetime.now().isoformat()
    }
    
    with open(COMPLETED_FILE, "w") as f:
        json.dump(output, f, indent=2)
    
    log(f"=== RESULTS ===")
    log(f"Completed: {len(completed_list)}")
    log(f"Failed: {len(failed_list)}")
    if completed_list + failed_list:
        log(f"Rate: {100*len(completed_list)/(len(completed_list)+len(failed_list)):.1f}%")


if __name__ == "__main__":
    workers = 12
    if len(sys.argv) > 2 and sys.argv[1] == "--workers":
        workers = int(sys.argv[2])
    
    asyncio.run(main(workers))
