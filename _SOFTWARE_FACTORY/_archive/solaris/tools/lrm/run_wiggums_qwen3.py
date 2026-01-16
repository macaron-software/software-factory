#!/usr/bin/env python3
"""
RUN PARALLEL WIGGUMS - Qwen3 Local
==================================
Lance N Wiggums en parallèle avec Qwen3-30B-A3B local.

Usage:
    python3 tools/lrm/run_wiggums_qwen3.py [--workers 10]
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

# Qwen3 local config
QWEN3_BASE_URL = "http://localhost:8002/v1"
QWEN3_MODEL = "Qwen3-30B-A3B-Instruct-Q4_K_S.gguf"

# Semaphore for concurrent calls (Qwen3 local can handle ~4 parallel)
MAX_CONCURRENT = 4


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


# Import Adversarial from wiggum_solaris
sys.path.insert(0, str(PROJECT_ROOT / "tools" / "lrm"))
from wiggum_solaris import AdversarialAgent


async def call_qwen3(prompt: str) -> str:
    """Call Qwen3 local via HTTP"""
    import aiohttp
    
    headers = {"Content-Type": "application/json"}
    payload = {
        "model": QWEN3_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4096,
        "temperature": 0.3
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{QWEN3_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=300)
            ) as resp:
                data = await resp.json()
                
                if resp.status == 200:
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "")[:20000]
                    return str(data)[:20000]
                else:
                    error = data.get("error", {}).get("message", str(data))
                    return f"Error: {error}"
    except asyncio.TimeoutError:
        return "Error: Qwen3 timeout (5min)"
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
        prompt = f"""Expert Design System developer task.

TASK: {description}
COMPONENTS: {', '.join(components[:3]) if components else 'N/A'}
ACCEPTANCE CRITERIA:
{chr(10).join(f'- {c}' for c in criteria[:5]) if criteria else '- Complete the task'}

⚠️ RÈGLES STRICTES - VIOLATION = REJET:
- NO test.skip, it.skip → INTERDIT
- NO TODO, FIXME, STUB → INTERDIT
- NO "ensures", "perfect", "100%" → OVERCONFIDENT
- NO hardcoded values → Use Figma/MCP

REQUIRED:
- Complete, working code
- Real tests without skip
- Values from Figma via MCP

Generate the implementation:"""
        
        # Retry loop with adversarial control
        max_retries = 5
        last_issues = []
        
        for attempt in range(1, max_retries + 1):
            log(f"[W{worker_id:02d}] {task_id} attempt {attempt}/{max_retries}...")
            
            response = await call_qwen3(prompt)
            
            # Check for errors
            if response.startswith("Error:"):
                log(f"[W{worker_id:02d}] {task_id} LLM error: {response[:80]}")
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return {"id": task_id, "status": "failed", "error": response}
            
            # Adversarial check
            approved, score, issues = adversarial.analyze(response, description)
            
            if approved:
                log(f"[W{worker_id:02d}] {task_id} APPROVED (score={score})")
                return {"id": task_id, "status": "completed", "result": response[:2000], "score": score}
            else:
                log(f"[W{worker_id:02d}] {task_id} REJECTED (score={score})")
                last_issues = issues
                
                # Add feedback for retry
                feedback = adversarial.format_feedback(issues)
                prompt = f"{feedback}\n\n{prompt}"
                
                await asyncio.sleep(2)
        
        log(f"[W{worker_id:02d}] {task_id} FAILED after {max_retries} attempts")
        return {"id": task_id, "status": "failed", "error": "max_retries", "issues": last_issues}


async def main(max_workers: int = 10):
    """Launch parallel Wiggums"""
    log(f"=== PARALLEL WIGGUMS ({max_workers} workers) ===")
    log(f"Using Qwen3-30B-A3B local (port 8002)")
    
    # Load backlog
    with open(BACKLOG_FILE) as f:
        backlog = json.load(f)
    
    tasks = backlog.get("tasks", [])
    
    # Load completed to filter
    completed_ids = set()
    if COMPLETED_FILE.exists():
        with open(COMPLETED_FILE) as f:
            completed = json.load(f)
        completed_ids = {t["task"]["id"] for t in completed.get("completed", []) if isinstance(t, dict) and "task" in t}
    
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
        for i, task in enumerate(pending[:max_workers])  # Limit to max_workers
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
                failed_list.append({"task": {"id": r["id"]}, "error": r.get("error", "")})
    
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
    workers = 12  # Process all 12 tasks
    if len(sys.argv) > 2 and sys.argv[1] == "--workers":
        workers = int(sys.argv[2])
    
    asyncio.run(main(workers))
