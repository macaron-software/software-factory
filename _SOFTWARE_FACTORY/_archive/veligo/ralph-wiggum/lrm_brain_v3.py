#!/usr/bin/env python3
"""
LRM Brain v3 - Deterministic Analysis + LLM Task Generation

Unlike v2 which relied on LLM for recursion decisions, v3:
1. Uses DETERMINISTIC code analysis (grep, find, cargo, npm)
2. Categorizes findings programmatically
3. Uses LLM ONLY to format task descriptions

This works even with slow/dumb LLMs.
"""

import os
import sys
import json
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Tuple
from datetime import datetime

# ============================================================================
# CONFIG
# ============================================================================
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
TASKS_DIR = SCRIPT_DIR / "tasks"
STATUS_DIR = SCRIPT_DIR / "status"

# Colors
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
BLUE = "\033[0;34m"
MAGENTA = "\033[1;35m"
NC = "\033[0m"

def log(msg: str, color: str = NC):
    print(f"{color}[BRAIN] {msg}{NC}", file=sys.stderr)

def bash(cmd: str, cwd: str = None, timeout: int = 60) -> Tuple[int, str]:
    """Execute real bash command."""
    try:
        result = subprocess.run(
            cmd, shell=True,
            cwd=cwd or str(PROJECT_ROOT),
            capture_output=True, text=True,
            timeout=timeout
        )
        return result.returncode, (result.stdout + result.stderr)[:20000]
    except Exception as e:
        return 1, str(e)

# ============================================================================
# DETERMINISTIC ANALYZERS
# ============================================================================

def analyze_rust_compilation() -> List[Dict]:
    """Find Rust compilation errors."""
    log("Analyzing Rust compilation...", BLUE)
    findings = []

    # Run cargo check
    code, output = bash("cd veligo-platform/backend && cargo check 2>&1 | head -100")

    # Parse errors
    error_pattern = r'error\[E\d+\]: (.+)\n\s+-->\s+([^:]+):(\d+):(\d+)'
    for match in re.finditer(error_pattern, output):
        msg, file, line, col = match.groups()
        findings.append({
            "type": "compilation_error",
            "severity": "P0",
            "message": msg,
            "file": file,
            "line": int(line),
            "ao_ref": ""
        })

    # Check for DB connection errors (SQLx)
    if "Connection refused" in output:
        log("  Note: SQLx errors are DB connection issues, not code errors", YELLOW)

    return findings

def analyze_skipped_tests() -> List[Dict]:
    """Find test.skip() in E2E tests."""
    log("Analyzing skipped tests...", BLUE)
    findings = []

    code, output = bash("grep -rn 'test\\.skip' tests --include='*.spec.ts' 2>/dev/null")

    for line in output.strip().split('\n'):
        if not line.strip():
            continue
        match = re.match(r'([^:]+):(\d+):', line)
        if match:
            file, lineno = match.groups()
            # Determine AO ref from path
            ao_ref = ""
            if "idfm" in file.lower():
                ao_ref = "AO-IDFM"
            elif "nantes" in file.lower():
                ao_ref = "AO-NANTES"
            elif "lyon" in file.lower():
                ao_ref = "AO-LYON"

            findings.append({
                "type": "skipped_test",
                "severity": "P1",
                "message": f"test.skip() blocks deployment",
                "file": file,
                "line": int(lineno),
                "ao_ref": ao_ref
            })

    return findings

def analyze_todos() -> List[Dict]:
    """Find TODO/FIXME comments."""
    log("Analyzing TODOs...", BLUE)
    findings = []

    # Backend TODOs
    code, output = bash("grep -rn 'TODO:\\|FIXME:' veligo-platform/backend/src --include='*.rs' 2>/dev/null | head -50")

    for line in output.strip().split('\n'):
        if not line.strip():
            continue
        match = re.match(r'([^:]+):(\d+):\s*//\s*(TODO|FIXME):\s*(.+)', line)
        if match:
            file, lineno, tag, msg = match.groups()
            findings.append({
                "type": "todo",
                "severity": "P2",
                "message": msg.strip(),
                "file": file,
                "line": int(lineno),
                "ao_ref": ""
            })

    return findings

def analyze_missing_testids() -> List[Dict]:
    """Find components missing data-testid attributes."""
    log("Analyzing missing data-testid...", BLUE)
    findings = []

    # Check login/auth pages for FranceConnect testid
    code, output = bash("grep -l 'FranceConnect\\|franceconnect' veligo-platform/frontend/src --include='*.svelte' -r 2>/dev/null")

    for file in output.strip().split('\n'):
        if not file.strip():
            continue
        # Check if file has the expected testid
        code2, content = bash(f"grep 'data-testid=\"franceconnect-login\"' '{file}'")
        if code2 != 0:  # testid not found
            findings.append({
                "type": "missing_testid",
                "severity": "P1",
                "message": f"FranceConnect component missing data-testid='franceconnect-login'",
                "file": file,
                "line": 0,
                "ao_ref": "AO-IDFM-AUTH"
            })

    return findings

def analyze_panic_stubs() -> List[Dict]:
    """Find panic!() calls that should be proper error handling."""
    log("Analyzing panic stubs...", BLUE)
    findings = []

    code, output = bash("grep -rn 'panic!' veligo-platform/backend/src --include='*.rs' 2>/dev/null | grep -v '#\\[should_panic\\]' | grep -v 'tests/' | head -30")

    for line in output.strip().split('\n'):
        if not line.strip():
            continue
        # Skip test files and expected panics
        if '/tests/' in line or 'should_panic' in line or '#[test]' in line:
            continue
        match = re.match(r'([^:]+):(\d+):', line)
        if match:
            file, lineno = match.groups()
            findings.append({
                "type": "panic_stub",
                "severity": "P1",
                "message": "panic!() should be replaced with proper error handling",
                "file": file,
                "line": int(lineno),
                "ao_ref": ""
            })

    return findings

def analyze_missing_routes() -> List[Dict]:
    """Find routes expected by tests but missing in frontend."""
    log("Analyzing missing routes...", BLUE)
    findings = []

    # Check if /auth/login exists
    code, output = bash("ls -la veligo-platform/frontend/src/routes/auth/login/+page.svelte 2>/dev/null")
    if code != 0:
        findings.append({
            "type": "missing_route",
            "severity": "P0",
            "message": "/auth/login route missing - required by FranceConnect E2E tests",
            "file": "veligo-platform/frontend/src/routes/auth/login/+page.svelte",
            "line": 0,
            "ao_ref": "AO-IDFM-AUTH"
        })

    return findings

# ============================================================================
# TASK GENERATION
# ============================================================================

def create_task(task_id: str, finding: Dict) -> None:
    """Create a task file from a finding."""
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_DIR.mkdir(parents=True, exist_ok=True)

    # Map type to title prefix
    type_titles = {
        "compilation_error": "Fix compilation error",
        "skipped_test": "Implement or remove skipped test",
        "todo": "Complete TODO",
        "missing_testid": "Add missing data-testid",
        "panic_stub": "Replace panic with error handling",
        "missing_route": "Create missing route"
    }

    title = f"{type_titles.get(finding['type'], 'Fix issue')}: {finding['file'].split('/')[-1]}"
    if len(title) > 80:
        title = title[:77] + "..."

    ao_line = f"**AO_REF**: {finding['ao_ref']}\n" if finding.get('ao_ref') else ""

    content = f"""# Task {task_id}: {title}

**Priority**: {finding['severity']}
**Queue**: TDD
{ao_line}
## Description
{finding['message']}

## File
{finding['file']}:{finding.get('line', 0)}

## Success Criteria
- [ ] Issue fixed
- [ ] Code compiles
- [ ] Tests pass
- [ ] No regressions

## Ralph Status Block
---RALPH_STATUS---
STATUS: PENDING
COMPLEXITY: simple
WSJF: {10 if finding['severity'] == 'P0' else 8 if finding['severity'] == 'P1' else 5}
---END_RALPH_STATUS---
"""

    task_file = TASKS_DIR / f"{task_id}.md"
    task_file.write_text(content)
    (STATUS_DIR / f"{task_id}.status").write_text("PENDING")
    log(f"Created {task_id}: {title}", GREEN)

def get_next_task_id() -> int:
    """Get next available task ID."""
    existing = list(TASKS_DIR.glob("T*.md"))
    if not existing:
        return 100

    max_id = 0
    for f in existing:
        try:
            num = int(f.stem[1:])
            max_id = max(max_id, num)
        except:
            pass
    return max_id + 1

# ============================================================================
# MAIN
# ============================================================================

def run_analysis():
    """Run full deterministic analysis."""
    log("=" * 60, MAGENTA)
    log("LRM BRAIN v3 - DETERMINISTIC ANALYSIS", MAGENTA)
    log("=" * 60, MAGENTA)

    all_findings = []

    # Run all analyzers
    all_findings.extend(analyze_rust_compilation())
    all_findings.extend(analyze_skipped_tests())
    all_findings.extend(analyze_missing_routes())
    all_findings.extend(analyze_missing_testids())
    all_findings.extend(analyze_panic_stubs())
    all_findings.extend(analyze_todos()[:10])  # Limit TODOs

    log(f"\nTotal findings: {len(all_findings)}", BLUE)

    # Group by file to avoid duplicate tasks
    by_file = {}
    for f in all_findings:
        key = f['file']
        if key not in by_file:
            by_file[key] = f
        elif f['severity'] < by_file[key]['severity']:  # P0 < P1 < P2
            by_file[key] = f

    # Create tasks
    task_id = get_next_task_id()
    tasks_created = []

    # Sort by severity
    sorted_findings = sorted(by_file.values(), key=lambda x: x['severity'])

    for finding in sorted_findings[:20]:  # Max 20 tasks per run
        tid = f"T{task_id:03d}"
        create_task(tid, finding)
        tasks_created.append(tid)
        task_id += 1

    log("=" * 60, MAGENTA)
    log("ANALYSIS COMPLETE", MAGENTA)
    log(f"Tasks created: {len(tasks_created)}", GREEN)
    for tid in tasks_created:
        log(f"  - {tid}", GREEN)
    log("=" * 60, MAGENTA)

    return tasks_created

def list_tasks():
    """List all tasks with status."""
    for f in sorted(TASKS_DIR.glob("T*.md")):
        status_file = STATUS_DIR / f"{f.stem}.status"
        status = status_file.read_text().strip() if status_file.exists() else "UNKNOWN"
        print(f"{f.stem}: {status}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="LRM Brain v3 - Deterministic Analyzer")
    parser.add_argument("--analyze", action="store_true", help="Run analysis and create tasks")
    parser.add_argument("--list", action="store_true", help="List tasks")

    args = parser.parse_args()

    if args.analyze:
        run_analysis()
    elif args.list:
        list_tasks()
    else:
        parser.print_help()
