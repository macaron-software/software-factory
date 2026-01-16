#!/usr/bin/env python3
"""
LRM Brain v2 - Recursive Language Model Brain
Based on arXiv:2512.24601 (MIT CSAIL)

This brain:
1. RECURSIVELY analyzes the REAL codebase
2. Uses sub-agents for deep analysis
3. Creates tasks based on ACTUAL problems found
4. Has access to ALL code via MCP tools

NO SIMULATION. NO FAKE. REAL ANALYSIS.
"""

import os
import sys
import json
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

# ============================================================================
# CONFIG
# ============================================================================
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
TASKS_DIR = SCRIPT_DIR / "tasks"
STATUS_DIR = SCRIPT_DIR / "status"

# LLM Config
LLM_BACKEND = os.getenv("LLM_BACKEND", "auto")
LOCAL_API_URL = os.getenv("LOCAL_API_URL", "http://127.0.0.1:8002/v1/chat/completions")
LOCAL_MODEL = os.getenv("LOCAL_MODEL", "qwen3")
CLOUD_API_URL = os.getenv("CLOUD_API_URL", "https://api.minimax.io/v1/chat/completions")
CLOUD_API_KEY = os.getenv("CLOUD_API_KEY", "")
CLOUD_MODEL = os.getenv("CLOUD_MODEL", "MiniMax-M2.1")

MAX_DEPTH = 5  # Max recursion depth
MAX_TOKENS = 8192
TIMEOUT = 300

# Colors
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
BLUE = "\033[0;34m"
MAGENTA = "\033[1;35m"
NC = "\033[0m"

def log(msg: str, color: str = NC):
    print(f"{color}[BRAIN] {msg}{NC}", file=sys.stderr)

# ============================================================================
# REAL TOOLS - Execute actual commands
# ============================================================================
def bash(cmd: str, cwd: str = None, timeout: int = 60) -> Tuple[int, str]:
    """Execute real bash command."""
    try:
        result = subprocess.run(
            cmd, shell=True,
            cwd=cwd or str(PROJECT_ROOT),
            capture_output=True, text=True,
            timeout=timeout
        )
        output = (result.stdout + result.stderr)[:10000]
        return result.returncode, output
    except Exception as e:
        return 1, str(e)

def grep(pattern: str, path: str = ".", glob: str = "*") -> str:
    """Grep for pattern in files."""
    cmd = f"grep -rn '{pattern}' --include='{glob}' {path} 2>/dev/null | head -50"
    code, output = bash(cmd)
    return output if output else "No matches"

def find_files(pattern: str, path: str = ".") -> List[str]:
    """Find files matching pattern."""
    cmd = f"find {path} -name '{pattern}' -type f 2>/dev/null | head -100"
    code, output = bash(cmd)
    return [f.strip() for f in output.split('\n') if f.strip()]

def read_file(path: str, limit: int = 200) -> str:
    """Read file content."""
    try:
        full_path = Path(path)
        if not full_path.is_absolute():
            full_path = PROJECT_ROOT / path
        if full_path.exists():
            lines = full_path.read_text().split('\n')[:limit]
            return '\n'.join(lines)
        return f"FILE NOT FOUND: {path}"
    except Exception as e:
        return f"ERROR: {e}"

def count_lines(path: str, glob: str = "*") -> int:
    """Count lines in files."""
    cmd = f"find {path} -name '{glob}' -type f -exec wc -l {{}} + 2>/dev/null | tail -1 | awk '{{print $1}}'"
    code, output = bash(cmd)
    try:
        return int(output.strip())
    except:
        return 0

# ============================================================================
# LLM CALL
# ============================================================================
def call_llm(messages: List[Dict], max_tokens: int = MAX_TOKENS) -> Optional[str]:
    """Call LLM with auto backend selection."""
    import requests

    # Try cloud first if available
    if CLOUD_API_KEY and LLM_BACKEND in ["cloud", "auto"]:
        try:
            response = requests.post(
                CLOUD_API_URL,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {CLOUD_API_KEY}"},
                json={"model": CLOUD_MODEL, "messages": messages, "max_tokens": max_tokens, "temperature": 0.7},
                timeout=TIMEOUT
            )
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            log(f"Cloud failed: {e}", YELLOW)

    # Fallback to local
    try:
        import requests
        response = requests.post(
            LOCAL_API_URL,
            json={"model": LOCAL_MODEL, "messages": messages, "max_tokens": max_tokens, "temperature": 0.7},
            timeout=TIMEOUT
        )
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        log(f"Local failed: {e}", RED)

    return None

# ============================================================================
# RECURSIVE ANALYSIS ENGINE
# ============================================================================
class LRMBrain:
    """
    Recursive Language Model Brain.
    Analyzes codebase recursively with sub-agents.
    """

    def __init__(self):
        self.depth = 0
        self.findings = []
        self.tasks_created = []
        self.call_count = 0

    def analyze(self, query: str, context: str = "", depth: int = 0) -> Dict[str, Any]:
        """
        Recursively analyze with sub-agents.
        Returns findings and recommended tasks.
        """
        self.depth = depth
        self.call_count += 1

        if depth > MAX_DEPTH:
            log(f"Max depth {MAX_DEPTH} reached", YELLOW)
            return {"status": "max_depth", "findings": []}

        log(f"[Depth {depth}] Analyzing: {query[:50]}...", MAGENTA)

        # Build prompt with real tools
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(query, context)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # Call LLM
        response = call_llm(messages)
        if not response:
            return {"status": "llm_failed", "findings": []}

        # Parse response for actions and sub-queries
        return self._process_response(response, depth)

    def _build_system_prompt(self) -> str:
        return """You are an LRM Brain - a recursive analyzer for the Veligo codebase.

You MUST use these REAL tools to analyze. Do NOT guess or hallucinate.

## TOOLS (use these exact formats)

1. GREP: Find patterns in code
   <grep pattern="TODO|FIXME" glob="*.rs" path="veligo-platform/backend/src"/>

2. FIND: List files
   <find pattern="*.spec.ts" path="tests/e2e"/>

3. READ: Read file content
   <read path="veligo-platform/backend/src/main.rs" limit="100"/>

4. BASH: Run command
   <bash cmd="cargo check 2>&1 | grep error | head -10"/>

5. RECURSE: Spawn sub-agent for deeper analysis
   <recurse query="Analyze auth module" context="Found auth issues in..."/>

6. TASK: Create a task for Wiggum to execute
   <task id="T101" priority="P0" title="Fix compilation error in auth.rs"
         description="..." files="src/auth.rs" ao_ref="AO-IDFM-AUTH-001"/>

7. FINDING: Report a finding
   <finding type="error|warning|info" message="..."/>

## RULES
- ALWAYS use tools to verify before creating tasks
- RECURSE for complex sub-problems (auth, payments, tests separately)
- Create CONCRETE tasks with real file paths
- Link tasks to AO requirements when applicable
- Output DONE when analysis is complete

## AO REFERENCES (use for traceability)
- AO-IDFM-AUTH: FranceConnect SSO, MFA
- AO-IDFM-BOOKING: Réservation vélos
- AO-NANTES-BOX: Box sécurisés
- AO-LYON-TCL: Intégration TCL
"""

    def _build_user_prompt(self, query: str, context: str) -> str:
        # Gather real project state
        rust_errors = bash("cd veligo-platform/backend && cargo check 2>&1 | grep -E '^error' | head -5")[1]
        todo_count = bash("grep -rn 'TODO\\|FIXME' veligo-platform --include='*.rs' --include='*.ts' 2>/dev/null | wc -l")[1].strip()
        test_files = bash("find tests -name '*.spec.ts' 2>/dev/null | wc -l")[1].strip()

        return f"""## QUERY
{query}

## CONTEXT
{context if context else "Initial analysis"}

## CURRENT PROJECT STATE (REAL DATA)
- Rust compilation errors: {rust_errors[:500] if rust_errors.strip() else "None"}
- TODO/FIXME count: {todo_count}
- E2E test files: {test_files}

## YOUR TASK
1. Use GREP/FIND/READ to analyze the REAL code
2. Use RECURSE for sub-problems
3. Create TASK entries for real issues found
4. Report FINDING for each problem discovered
5. Output DONE when complete

Start analyzing NOW. Use the tools.
"""

    def _process_response(self, response: str, depth: int) -> Dict[str, Any]:
        """Process LLM response, execute tools, handle recursion."""
        results = {
            "status": "ok",
            "findings": [],
            "tasks": [],
            "sub_results": []
        }

        # Execute GREP commands
        for match in re.finditer(r'<grep\s+pattern="([^"]+)"\s+glob="([^"]+)"\s+path="([^"]+)"/?>', response):
            pattern, glob_pattern, path = match.groups()
            log(f"  GREP: {pattern} in {path}", BLUE)
            output = grep(pattern, path, glob_pattern)
            results["findings"].append({"type": "grep", "pattern": pattern, "output": output[:1000]})

        # Execute FIND commands
        for match in re.finditer(r'<find\s+pattern="([^"]+)"\s+path="([^"]+)"/?>', response):
            pattern, path = match.groups()
            log(f"  FIND: {pattern} in {path}", BLUE)
            files = find_files(pattern, path)
            results["findings"].append({"type": "find", "pattern": pattern, "files": files[:20]})

        # Execute READ commands
        for match in re.finditer(r'<read\s+path="([^"]+)"(?:\s+limit="(\d+)")?/?>', response):
            path = match.group(1)
            limit = int(match.group(2)) if match.group(2) else 100
            log(f"  READ: {path}", BLUE)
            content = read_file(path, limit)
            results["findings"].append({"type": "read", "path": path, "content": content[:2000]})

        # Execute BASH commands
        for match in re.finditer(r'<bash\s+cmd="([^"]+)"/?>', response):
            cmd = match.group(1)
            log(f"  BASH: {cmd[:50]}...", BLUE)
            code, output = bash(cmd)
            results["findings"].append({"type": "bash", "cmd": cmd, "output": output[:1000]})

        # Handle RECURSE (sub-agents)
        for match in re.finditer(r'<recurse\s+query="([^"]+)"\s+context="([^"]*)"/?>', response):
            query, context = match.groups()
            log(f"  RECURSE: {query[:40]}...", MAGENTA)
            sub_result = self.analyze(query, context, depth + 1)
            results["sub_results"].append(sub_result)

        # Collect TASK definitions
        for match in re.finditer(
            r'<task\s+id="([^"]+)"\s+priority="([^"]+)"\s+title="([^"]+)"\s+description="([^"]+)"\s+files="([^"]+)"(?:\s+ao_ref="([^"]+)")?/?>',
            response, re.DOTALL
        ):
            task = {
                "id": match.group(1),
                "priority": match.group(2),
                "title": match.group(3),
                "description": match.group(4),
                "files": match.group(5),
                "ao_ref": match.group(6) or ""
            }
            log(f"  TASK: {task['id']} - {task['title'][:40]}", GREEN)
            results["tasks"].append(task)
            self._create_task_file(task)

        # Collect FINDINGS
        for match in re.finditer(r'<finding\s+type="([^"]+)"\s+message="([^"]+)"/?>', response):
            finding = {"type": match.group(1), "message": match.group(2)}
            results["findings"].append(finding)
            self.findings.append(finding)

        return results

    def _create_task_file(self, task: Dict) -> None:
        """Create actual task file for Wiggum."""
        TASKS_DIR.mkdir(parents=True, exist_ok=True)

        task_file = TASKS_DIR / f"{task['id']}.md"

        ao_line = f"**AO_REF**: {task['ao_ref']}" if task['ao_ref'] else ""

        content = f"""# Task {task['id']}: {task['title']}

**Priority**: {task['priority']}
**Queue**: TDD
{ao_line}

## Description
{task['description']}

## Files to Modify
{task['files']}

## Success Criteria
- [ ] Code compiles without errors
- [ ] Tests pass
- [ ] No regressions

## Ralph Status Block
---RALPH_STATUS---
STATUS: PENDING
COMPLEXITY: medium
WSJF: 8.0
---END_RALPH_STATUS---
"""
        task_file.write_text(content)

        # Also create status file
        STATUS_DIR.mkdir(parents=True, exist_ok=True)
        (STATUS_DIR / f"{task['id']}.status").write_text("PENDING")

        self.tasks_created.append(task['id'])
        log(f"Created task file: {task_file}", GREEN)

# ============================================================================
# MAIN ANALYSIS FLOWS
# ============================================================================
def run_full_analysis():
    """Run comprehensive recursive analysis."""
    brain = LRMBrain()

    log("=" * 60, MAGENTA)
    log("LRM BRAIN v2 - RECURSIVE ANALYSIS", MAGENTA)
    log("=" * 60, MAGENTA)

    # Main analysis query
    main_query = """Analyze the Veligo codebase comprehensively:

1. RECURSE("Analyze Rust backend compilation and errors", "veligo-platform/backend")
2. RECURSE("Analyze E2E test coverage and failures", "tests/e2e")
3. RECURSE("Analyze AO compliance gaps", "Check FranceConnect, Box sécurisés, TCL")
4. RECURSE("Analyze technical debt", "TODO/FIXME in code")

For each problem found, create a TASK with concrete actions.
"""

    result = brain.analyze(main_query)

    # Summary
    log("=" * 60, MAGENTA)
    log("ANALYSIS COMPLETE", MAGENTA)
    log(f"Total LLM calls: {brain.call_count}", BLUE)
    log(f"Findings: {len(brain.findings)}", BLUE)
    log(f"Tasks created: {brain.tasks_created}", GREEN)
    log("=" * 60, MAGENTA)

    return result

def run_targeted_analysis(target: str):
    """Run targeted analysis on specific area."""
    brain = LRMBrain()

    log(f"Targeted analysis: {target}", MAGENTA)

    result = brain.analyze(f"Deep analysis of: {target}")

    log(f"Tasks created: {brain.tasks_created}", GREEN)
    return result

# ============================================================================
# CLI
# ============================================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="LRM Brain v2 - Recursive Analyzer")
    parser.add_argument("--analyze", action="store_true", help="Run full recursive analysis")
    parser.add_argument("--target", type=str, help="Run targeted analysis on specific area")
    parser.add_argument("--list-tasks", action="store_true", help="List created tasks")

    args = parser.parse_args()

    if args.analyze:
        run_full_analysis()
    elif args.target:
        run_targeted_analysis(args.target)
    elif args.list_tasks:
        for f in sorted(TASKS_DIR.glob("*.md")):
            status_file = STATUS_DIR / f"{f.stem}.status"
            status = status_file.read_text().strip() if status_file.exists() else "UNKNOWN"
            print(f"{f.stem}: {status}")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
