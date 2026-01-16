#!/usr/bin/env python3
"""
SOLARIS LRM ORCHESTRATOR
========================
Lance le système LRM complet:
- Brain: Claude Opus 4.5 headless
- Sub-agents: Qwen3-30B local avec MCP tools
- Wiggum: MiniMax M2.1 Coding Plan (50 parallèles)

Usage:
    python3 tools/lrm/run.py brain --question "trouve les routes non implémentées"
    python3 tools/lrm/run.py wiggum --workers 50
    python3 tools/lrm/run.py all --question "..." --workers 50
"""

import argparse
import asyncio
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path("/Users/sylvain/_LAPOSTE/_SD3")
BACKLOG_FILE = PROJECT_ROOT / "tools" / "lrm" / "backlog_solaris.json"
COMPLETED_FILE = PROJECT_ROOT / "tools" / "lrm" / "completed_solaris.json"
LOGS_DIR = PROJECT_ROOT / "logs" / "lrm"

LOGS_DIR.mkdir(parents=True, exist_ok=True)


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


async def run_brain_opus(question: str) -> dict:
    """
    Run Brain with Claude Opus 4.5 headless
    """
    log("=" * 60)
    log("🧠 LRM BRAIN - Claude Opus 4.5 headless")
    log(f"   Question: {question[:80]}...")
    log("=" * 60)
    
    # Import MCP server for context
    sys.path.insert(0, str(PROJECT_ROOT))
    from mcp_solaris_server import SolarisMCPServer
    
    mcp = SolarisMCPServer()
    
    # Gather context
    log("📊 Gathering context via MCP...")
    stats = await mcp.get_stats()
    validation = await mcp.get_validation()
    components = await mcp.list_components()
    
    # Build prompt
    prompt = f"""Tu es le LRM Brain de Solaris Design System (La Poste).

QUESTION: {question}

CONTEXTE ACTUEL:
- Stats: {json.dumps(stats, indent=2)[:2000]}
- Validation: {validation.get('passRate', 'N/A')} ({validation.get('passed', 0)}/{validation.get('total', 0)})
- Composants: {len(components.get('components', [])) if isinstance(components, dict) else 0} familles

RÈGLES ABSOLUES:
1. NE JAMAIS inventer de fichiers ou valeurs
2. Chaque tâche DOIT citer des sources existantes
3. Utiliser les MCP tools pour vérifier les données

Génère un backlog de tâches concrètes au format JSON:
{{
  "tasks": [
    {{
      "id": "SOLAR-XXX",
      "type": "fix|feature|refactor",
      "priority": 1-10,
      "description": "...",
      "components": ["..."],
      "acceptance_criteria": ["..."],
      "sources": ["chemin/fichier:ligne"]
    }}
  ]
}}
"""
    
    log("🤖 Calling Claude Opus 4.5...")
    
    try:
        proc = await asyncio.create_subprocess_exec(
            "claude", "-p",
            "--model", "claude-opus-4-5-20251101",
            "--max-turns", "10",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=prompt.encode()),
            timeout=3600,  # 1h for complex analysis
        )
        
        if proc.returncode != 0:
            log(f"❌ Brain error: {stderr.decode()[:500]}")
            return {"error": stderr.decode()[:500]}
        
        response = stdout.decode()
        log(f"   Brain response: {len(response)} chars")
        
        # Parse JSON from response
        import re
        json_match = re.search(r'\{[\s\S]*"tasks"[\s\S]*\}', response)
        if json_match:
            data = json.loads(json_match.group())
            tasks = data.get("tasks", [])
            
            # Save backlog
            backlog = {
                "generated_at": datetime.now().isoformat(),
                "question": question,
                "brain_model": "claude-opus-4-5-20251101",
                "tasks": tasks
            }
            
            with open(BACKLOG_FILE, "w") as f:
                json.dump(backlog, f, indent=2)
            
            log(f"✅ Generated {len(tasks)} tasks")
            log(f"   Saved to {BACKLOG_FILE}")
            
            return backlog
        else:
            log("⚠️ Could not parse JSON, saving raw response")
            return {"raw": response}
            
    except asyncio.TimeoutError:
        log("❌ Brain timeout (10min)")
        return {"error": "timeout"}
    except Exception as e:
        log(f"❌ Brain error: {e}")
        return {"error": str(e)}


async def run_wiggum_parallel(workers: int = 50):
    """
    Run Wiggum agents in parallel with MiniMax M2.1
    """
    log("=" * 60)
    log(f"🔧 WIGGUM PARALLEL - {workers} workers")
    log("   Model: MiniMax M2.1 Coding Plan via opencode")
    log("=" * 60)
    
    # Load backlog
    if not BACKLOG_FILE.exists():
        log("❌ No backlog found. Run brain first!")
        return {"error": "no_backlog"}
    
    with open(BACKLOG_FILE) as f:
        backlog = json.load(f)
    
    tasks = backlog.get("tasks", [])
    log(f"📋 Found {len(tasks)} tasks in backlog")
    
    # Load completed
    completed_ids = set()
    if COMPLETED_FILE.exists():
        with open(COMPLETED_FILE) as f:
            completed = json.load(f)
        completed_ids = {t["task"]["id"] for t in completed.get("completed", [])}
    
    pending = [t for t in tasks if t.get("id") not in completed_ids]
    log(f"   Pending: {len(pending)}, Already completed: {len(completed_ids)}")
    
    if not pending:
        log("✅ All tasks already completed!")
        return {"status": "all_done"}
    
    # Import Wiggum
    sys.path.insert(0, str(PROJECT_ROOT / "tools" / "lrm"))
    from wiggum_solaris import WiggumSolaris
    
    # Create semaphore for rate limiting
    semaphore = asyncio.Semaphore(workers)
    
    async def process_task(task: dict, worker_id: int) -> dict:
        async with semaphore:
            task_id = task.get("id", "unknown")
            log(f"[W{worker_id:02d}] Starting {task_id}...")
            
            wiggum = WiggumSolaris()
            result = await wiggum.process_task(task)
            
            log(f"[W{worker_id:02d}] {task_id} -> {result.get('status')}")
            return result
    
    # Launch all tasks
    start = datetime.now()
    results = await asyncio.gather(*[
        process_task(task, i) for i, task in enumerate(pending[:workers])
    ], return_exceptions=True)
    elapsed = (datetime.now() - start).total_seconds()
    
    # Count results
    completed = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "completed")
    failed = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "failed")
    errors = sum(1 for r in results if isinstance(r, Exception))
    
    log("=" * 60)
    log(f"📊 WIGGUM RESULTS ({elapsed:.1f}s)")
    log(f"   Completed: {completed}")
    log(f"   Failed: {failed}")
    log(f"   Errors: {errors}")
    log(f"   Rate: {100*completed/(completed+failed+errors):.1f}%" if (completed+failed+errors) > 0 else "N/A")
    log("=" * 60)
    
    return {
        "completed": completed,
        "failed": failed,
        "errors": errors,
        "elapsed": elapsed
    }


async def main():
    parser = argparse.ArgumentParser(description="Solaris LRM Orchestrator")
    parser.add_argument("command", choices=["brain", "wiggum", "all"], help="Command to run")
    parser.add_argument("--question", default="Analyse le Design System et propose des améliorations concrètes", help="Question for Brain")
    parser.add_argument("--workers", type=int, default=50, help="Number of parallel Wiggum workers")
    
    args = parser.parse_args()
    
    if args.command == "brain":
        await run_brain_opus(args.question)
    elif args.command == "wiggum":
        await run_wiggum_parallel(args.workers)
    elif args.command == "all":
        await run_brain_opus(args.question)
        await run_wiggum_parallel(args.workers)


if __name__ == "__main__":
    asyncio.run(main())
