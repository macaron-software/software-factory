#!/usr/bin/env python3
"""
Real TDD Agent - Execute REAL code changes and tests
No simulation, no fake, no slop.

This agent:
1. Reads the task
2. Calls LLM to get a plan
3. EXECUTES the plan (bash commands, file edits)
4. Runs REAL tests
5. Git commits on success

Based on RLM pattern (arXiv:2512.24601) but with REAL execution.
"""

import os
import sys
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

# ============================================================================
# CONFIG
# ============================================================================
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent

# Load .env.local if exists
env_file = SCRIPT_DIR / ".env.local"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

# Agent Config - opencode run only (tools + MCP + fractal RML)
# No direct API calls - always use opencode for full tool access

MAX_ITERATIONS = 10  # Max iterations per task
MAX_TOKENS = 4096
TIMEOUT = 300  # 5 min per LLM call

# Global state for fractal delegation
CURRENT_TASK_ID = None  # Set when running a task

# Colors
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
BLUE = "\033[0;34m"
NC = "\033[0m"

def log(msg: str, color: str = NC):
    print(f"{color}[AGENT] {msg}{NC}", file=sys.stderr)

def log_cmd(cmd: str):
    print(f"{BLUE}$ {cmd}{NC}", file=sys.stderr)

# ============================================================================
# LLM CALLS - Via opencode (tools + MCP + fractal RML)
# ============================================================================
OPENCODE_MODEL = os.getenv("OPENCODE_MODEL", "anthropic/claude-sonnet-4-20250514")
OPENCODE_TIMEOUT = int(os.getenv("OPENCODE_TIMEOUT", "600"))

def call_llm(messages: List[Dict], max_tokens: int = MAX_TOKENS) -> Optional[str]:
    """
    Call LLM via opencode run - gives access to:
    - All tools (Read, Write, Edit, Bash, Grep, etc.)
    - MCP servers (veligo-rag, playwright, etc.)
    - Fractal sub-agent creation
    """
    # Build prompt from messages
    prompt_parts = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "system":
            prompt_parts.append(f"=== CONTEXT ===\n{content}\n")
        elif role == "user":
            prompt_parts.append(f"=== INSTRUCTION ===\n{content}\n")
        elif role == "assistant":
            prompt_parts.append(f"=== PREVIOUS RESPONSE ===\n{content[:1000]}...\n")

    full_prompt = "\n".join(prompt_parts)

    # Call opencode run with tools
    try:
        log(f"Calling opencode with model: {OPENCODE_MODEL}", NC)
        result = subprocess.run(
            ["opencode", "run", "-m", OPENCODE_MODEL, full_prompt],
            capture_output=True,
            text=True,
            timeout=OPENCODE_TIMEOUT,
            cwd=str(PROJECT_ROOT)
        )

        if result.returncode == 0:
            output = result.stdout + result.stderr
            return output if output.strip() else None
        else:
            log(f"opencode failed (exit {result.returncode}): {result.stderr[:500]}", RED)
            return result.stdout + result.stderr if result.stdout or result.stderr else None

    except subprocess.TimeoutExpired:
        log(f"opencode timeout after {OPENCODE_TIMEOUT}s", YELLOW)
        return None
    except FileNotFoundError:
        log("opencode not found - install with: npm install -g @anthropic/opencode", RED)
        return None
    except Exception as e:
        log(f"opencode error: {e}", RED)
        return None

# ============================================================================
# TOOL EXECUTION - REAL ACTIONS
# ============================================================================
def execute_bash(cmd: str, cwd: Optional[str] = None, timeout: int = 120) -> Tuple[int, str, str]:
    """Execute a real bash command."""
    log_cmd(cmd)
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd or str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout
        )
        stdout = result.stdout[:5000] if result.stdout else ""
        stderr = result.stderr[:2000] if result.stderr else ""
        return result.returncode, stdout, stderr
    except subprocess.TimeoutExpired:
        return 124, "", "Command timed out"
    except Exception as e:
        return 1, "", str(e)

def read_file(path: str) -> Optional[str]:
    """Read a file."""
    try:
        full_path = Path(path)
        if not full_path.is_absolute():
            full_path = PROJECT_ROOT / path
        if full_path.exists():
            return full_path.read_text()[:50000]
        return None
    except Exception as e:
        return None

def write_file(path: str, content: str) -> bool:
    """Write a file."""
    try:
        full_path = Path(path)
        if not full_path.is_absolute():
            full_path = PROJECT_ROOT / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
        log(f"Wrote {full_path}", GREEN)
        return True
    except Exception as e:
        log(f"Failed to write {path}: {e}", RED)
        return False

def edit_file(path: str, old_string: str, new_string: str) -> bool:
    """Edit a file by replacing old_string with new_string."""
    content = read_file(path)
    if content is None:
        log(f"File not found: {path}", RED)
        return False

    if old_string not in content:
        log(f"String not found in {path}", RED)
        return False

    new_content = content.replace(old_string, new_string, 1)
    return write_file(path, new_content)

def grep_files(pattern: str, path: str = ".", file_glob: str = "*") -> str:
    """Grep for a pattern."""
    cmd = f"grep -rn '{pattern}' --include='{file_glob}' {path} 2>/dev/null | head -30"
    code, stdout, stderr = execute_bash(cmd)
    return stdout if stdout else "No matches found"

# ============================================================================
# ACTION PARSER - Extract actions from LLM response
# ============================================================================
def parse_actions(response: str) -> List[Dict[str, Any]]:
    """
    Parse LLM response to extract executable actions.

    Supported formats:
    - ```bash\n<command>\n```
    - <bash>command</bash>
    - <edit file="path" old="..." new="..."/>
    - <write file="path">content</write>
    - <read file="path"/>
    """
    actions = []

    # Parse ```bash blocks
    bash_blocks = re.findall(r'```bash\n(.*?)\n```', response, re.DOTALL)
    for cmd in bash_blocks:
        cmd = cmd.strip()
        if cmd and not cmd.startswith('#'):
            actions.append({"type": "bash", "command": cmd})

    # Parse <bash> tags
    bash_tags = re.findall(r'<bash>(.*?)</bash>', response, re.DOTALL)
    for cmd in bash_tags:
        cmd = cmd.strip()
        if cmd:
            actions.append({"type": "bash", "command": cmd})

    # Parse <edit> tags
    edit_matches = re.findall(
        r'<edit\s+file=["\']([^"\']+)["\']\s+old=["\']([^"\']+)["\']\s+new=["\']([^"\']+)["\']',
        response, re.DOTALL
    )
    for match in edit_matches:
        actions.append({
            "type": "edit",
            "file": match[0],
            "old": match[1],
            "new": match[2]
        })

    # Parse <write> tags
    write_matches = re.findall(
        r'<write\s+file=["\']([^"\']+)["\']>(.*?)</write>',
        response, re.DOTALL
    )
    for match in write_matches:
        actions.append({
            "type": "write",
            "file": match[0],
            "content": match[1].strip()
        })

    # Parse inline commands like: Run: `command`
    inline_cmds = re.findall(r'(?:Run|Execute|Bash):\s*`([^`]+)`', response)
    for cmd in inline_cmds:
        actions.append({"type": "bash", "command": cmd})

    # Parse <invoke bash><parameter>...</parameter></invoke> format (some LLMs use this)
    invoke_bash = re.findall(r'<invoke\s+bash>\s*<parameter>(.*?)</parameter>\s*</invoke>', response, re.DOTALL)
    for cmd in invoke_bash:
        cmd = cmd.strip()
        if cmd:
            actions.append({"type": "bash", "command": cmd})

    # Parse <fractal_delegate> tags - LLM decides to split and delegate
    # Format: <fractal_delegate reason="too complex">
    #           <subtask>Description of subtask 1</subtask>
    #           <subtask>Description of subtask 2</subtask>
    #         </fractal_delegate>
    fractal_match = re.search(
        r'<fractal_delegate\s+reason=["\']([^"\']+)["\']>(.*?)</fractal_delegate>',
        response, re.DOTALL
    )
    if fractal_match:
        reason = fractal_match.group(1)
        subtasks_content = fractal_match.group(2)
        subtasks = re.findall(r'<subtask>(.*?)</subtask>', subtasks_content, re.DOTALL)
        if subtasks:
            actions.append({
                "type": "fractal_delegate",
                "reason": reason,
                "subtasks": [s.strip() for s in subtasks]
            })

    return actions

def execute_action(action: Dict[str, Any]) -> Tuple[bool, str]:
    """Execute a single action and return (success, output)."""
    action_type = action.get("type")

    if action_type == "bash":
        code, stdout, stderr = execute_bash(action["command"])
        output = stdout + stderr
        return code == 0, output

    elif action_type == "edit":
        success = edit_file(action["file"], action["old"], action["new"])
        return success, "Edit applied" if success else "Edit failed"

    elif action_type == "write":
        success = write_file(action["file"], action["content"])
        return success, "File written" if success else "Write failed"

    elif action_type == "read":
        content = read_file(action["file"])
        return content is not None, content or "File not found"

    elif action_type == "fractal_delegate":
        # LLM decided to delegate - create subtasks and spawn sub-agents
        return execute_fractal_delegate(action)

    return False, f"Unknown action type: {action_type}"


def execute_fractal_delegate(action: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Execute fractal delegation - create subtasks and spawn sub-agents.
    Called when LLM decides the task is too complex and wants to delegate.
    """
    global CURRENT_TASK_ID
    reason = action.get("reason", "too complex")
    subtasks = action.get("subtasks", [])
    parent_task_id = CURRENT_TASK_ID or "UNKNOWN"

    if not subtasks:
        return False, "No subtasks specified for delegation"

    log(f"FRACTAL DELEGATE: {reason}", YELLOW)
    log(f"Creating {len(subtasks)} sub-tasks...", YELLOW)

    # Find next available task ID
    tasks_dir = SCRIPT_DIR / "tasks"
    status_dir = SCRIPT_DIR / "status"
    existing = list(tasks_dir.glob("T*.md"))
    max_num = 0
    for f in existing:
        try:
            num = int(f.stem[1:])
            max_num = max(max_num, num)
        except ValueError:
            pass

    # Create subtask files
    sub_task_ids = []
    for i, subtask_desc in enumerate(subtasks):
        sub_id = f"T{max_num + i + 1:03d}"
        sub_task_ids.append(sub_id)

        content = f'''# Task {sub_id}: {subtask_desc[:60]}

**Priority**: P1
**WSJF Score**: 8.0
**Queue**: TDD
**Parent**: {parent_task_id}
**Generated by**: Fractal LLM Delegation

## Description
{subtask_desc}

## Reason for Delegation
{reason}

## Success Criteria
- [ ] Task completed
- [ ] Tests pass
- [ ] No stubs or TODOs

## Ralph Status Block
---RALPH_STATUS---
STATUS: PENDING
COMPLEXITY: medium
PARENT_TASK: {parent_task_id}
---END_RALPH_STATUS---
'''
        (tasks_dir / f"{sub_id}.md").write_text(content)
        (status_dir / f"{sub_id}.status").write_text("PENDING\n")
        log(f"Created {sub_id}: {subtask_desc[:40]}...", BLUE)

    # Spawn sub-agents for each subtask
    log(f"Spawning {len(sub_task_ids)} sub-agents...", YELLOW)
    sub_processes = []
    for sub_id in sub_task_ids:
        sub_task_path = tasks_dir / f"{sub_id}.md"
        proc = subprocess.Popen(
            ["python3", str(SCRIPT_DIR / "real_agent.py"), str(sub_task_path), "tdd"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=PROJECT_ROOT
        )
        sub_processes.append((sub_id, proc))

    # Wait for all sub-agents
    log(f"Waiting for {len(sub_processes)} sub-agents...", YELLOW)
    results = []
    for sub_id, proc in sub_processes:
        try:
            stdout, stderr = proc.communicate(timeout=7200)
            exit_code = proc.returncode
            success = exit_code == 0
            results.append((sub_id, success))
            log(f"Sub-agent {sub_id}: {'SUCCESS' if success else 'FAILED'}",
                GREEN if success else RED)
        except subprocess.TimeoutExpired:
            proc.kill()
            results.append((sub_id, False))
            log(f"Sub-agent {sub_id}: TIMEOUT", RED)

    all_success = all(r[1] for r in results)
    failed_count = sum(1 for r in results if not r[1])

    if all_success:
        return True, f"FRACTAL_COMPLETE: All {len(results)} sub-tasks done"
    else:
        return False, f"FRACTAL_PARTIAL: {failed_count}/{len(results)} failed"

# ============================================================================
# VALIDATION - cargo check OBLIGATOIRE
# ============================================================================
def run_cargo_check() -> Tuple[bool, str]:
    """Run cargo check - MUST pass before any tests."""
    log("Running cargo check (MANDATORY)...", BLUE)
    code, stdout, stderr = execute_bash(
        "cargo check 2>&1 | tail -100",
        cwd=str(PROJECT_ROOT / "veligo-platform" / "backend"),
        timeout=180
    )
    output = stdout + stderr
    passed = code == 0 and "error[E" not in output
    if not passed:
        log("cargo check FAILED - code won't compile!", RED)
    else:
        log("cargo check OK", GREEN)
    return passed, output

# ============================================================================
# TEST RUNNER - Run REAL tests
# ============================================================================
def run_tests(test_type: str = "all") -> Tuple[bool, str]:
    """Run real tests and return (all_passed, output)."""
    results = []
    all_passed = True

    # ALWAYS run cargo check first for Rust changes
    if test_type in ["all", "rust"]:
        check_passed, check_output = run_cargo_check()
        results.append(f"Cargo check: {'PASS' if check_passed else 'FAIL'}\n{check_output}")
        if not check_passed:
            all_passed = False
            return all_passed, "\n---\n".join(results)  # Stop here if check fails

    if test_type in ["all", "rust"]:
        log("Running Rust tests...", BLUE)
        code, stdout, stderr = execute_bash(
            "cargo test --lib 2>&1 | tail -50",
            cwd=str(PROJECT_ROOT / "veligo-platform" / "backend"),
            timeout=300
        )
        passed = code == 0 and "FAILED" not in stdout
        results.append(f"Rust tests: {'PASS' if passed else 'FAIL'}\n{stdout}")
        if not passed:
            all_passed = False

    if test_type in ["all", "frontend"]:
        log("Running Frontend tests...", BLUE)
        code, stdout, stderr = execute_bash(
            "npm run test 2>&1 | tail -30",
            cwd=str(PROJECT_ROOT / "veligo-platform" / "frontend"),
            timeout=180
        )
        passed = code == 0
        results.append(f"Frontend tests: {'PASS' if passed else 'FAIL'}\n{stdout}")
        if not passed:
            all_passed = False

    if test_type in ["all", "e2e"]:
        log("Running E2E tests...", BLUE)
        code, stdout, stderr = execute_bash(
            "npx playwright test --reporter=list 2>&1 | tail -50",
            cwd=str(PROJECT_ROOT / "veligo-platform" / "frontend"),
            timeout=600
        )
        passed = code == 0
        results.append(f"E2E tests: {'PASS' if passed else 'FAIL'}\n{stdout}")
        if not passed:
            all_passed = False

    return all_passed, "\n---\n".join(results)

def run_specific_test(test_file: str) -> Tuple[bool, str]:
    """Run a specific test file."""
    if test_file.endswith(".spec.ts"):
        log(f"Running E2E test: {test_file}", BLUE)
        code, stdout, stderr = execute_bash(
            f"npx playwright test {test_file} --reporter=list 2>&1",
            cwd=str(PROJECT_ROOT / "veligo-platform" / "frontend"),
            timeout=300
        )
        return code == 0, stdout + stderr
    elif test_file.endswith(".rs"):
        log(f"Running Rust test: {test_file}", BLUE)
        code, stdout, stderr = execute_bash(
            f"cargo test --lib 2>&1",
            cwd=str(PROJECT_ROOT / "veligo-platform" / "backend"),
            timeout=300
        )
        return code == 0 and "FAILED" not in stdout, stdout + stderr
    return False, "Unknown test type"

# ============================================================================
# GIT OPERATIONS
# ============================================================================
def git_status() -> str:
    """Get git status."""
    code, stdout, _ = execute_bash("git status --short", cwd=str(PROJECT_ROOT))
    return stdout

def git_diff() -> str:
    """Get git diff."""
    code, stdout, _ = execute_bash("git diff --stat HEAD", cwd=str(PROJECT_ROOT))
    return stdout

def create_deploy_task(task_id: str, description: str) -> Optional[str]:
    """
    Create a deploy task (D*.md) to trigger deployment after TDD success.
    Returns the deploy task ID or None if creation failed.
    """
    tasks_dir = SCRIPT_DIR / "tasks"
    status_dir = SCRIPT_DIR / "status"

    # Find next deploy task ID
    existing = list(tasks_dir.glob("D*.md"))
    max_num = 0
    for f in existing:
        try:
            num = int(f.stem[1:])
            max_num = max(max_num, num)
        except ValueError:
            pass

    deploy_id = f"D{max_num + 1:03d}"

    content = f'''# Deploy Task {deploy_id}: Deploy {task_id}

**Priority**: P0
**Queue**: DEPLOY
**Source Task**: {task_id}
**Generated by**: Wiggum TDD Agent

## Description
Deploy changes from task {task_id}: {description}

## Deploy Steps
- [ ] Deploy to staging
- [ ] Run E2E smoke tests
- [ ] Run E2E journey tests (if critical)
- [ ] Run load tests (if perf-risk)
- [ ] Deploy to production
- [ ] Run prod smoke tests

## Ralph Status Block
---RALPH_STATUS---
STATUS: PENDING
QUEUE: DEPLOY
SOURCE_TASK: {task_id}
---END_RALPH_STATUS---
'''
    try:
        (tasks_dir / f"{deploy_id}.md").write_text(content)
        (status_dir / f"{deploy_id}.status").write_text("PENDING\n")
        log(f"Created deploy task: {deploy_id}", GREEN)
        return deploy_id
    except Exception as e:
        log(f"Failed to create deploy task: {e}", RED)
        return None


def git_commit(task_id: str, description: str, ao_ref: str = "") -> bool:
    """Commit changes with proper message."""
    # Check if there are changes
    if not git_diff().strip():
        log("No changes to commit - CANNOT mark as success without changes!", RED)
        return False  # MUST have changes to succeed

    # Build commit message
    if ao_ref:
        msg = f"feat({task_id}): {description} [{ao_ref}]"
    else:
        msg = f"feat({task_id}): {description}"

    msg += f"\n\nCo-Authored-By: Wiggum Agent <wiggum@veligo.app>"

    log(f"Committing: {msg.split(chr(10))[0]}", GREEN)

    code, stdout, stderr = execute_bash(
        f'git add -A && git commit -m "{msg}"',
        cwd=str(PROJECT_ROOT)
    )

    return code == 0

# ============================================================================
# MAIN AGENT LOOP
# ============================================================================
def build_system_prompt(task_content: str, queue_type: str) -> str:
    """Build the system prompt for the LLM."""

    if queue_type == "deploy":
        # DEPLOY AGENT - Simple and direct
        return f"""You are a DEPLOY agent. Your ONLY job is to run deployment commands.

DO NOT explore, analyze, or implement code. Just run these commands:

## STEP 1 - Check veligo CLI:
```bash
which veligo || echo "NOT FOUND"
```

## STEP 2 - Run deployment pipeline:
```bash
veligo cicd pipeline 2>&1 | tail -100
```

## STEP 3 - If veligo not found, run tests manually:
```bash
cd veligo-platform/frontend && npm run test:e2e -- --reporter=list 2>&1 | tail -50
```

## STEP 4 - Validate production:
```bash
curl -sf https://veligo.app/api/health && echo "HEALTH OK"
```

## RULES:
- DO NOT use ls, find, cat, grep to explore
- EXECUTE the deployment commands above
- Output SUCCESS only after health check passes
- Output NEEDS_MORE_WORK if any command fails
"""

    # TDD AGENT - Default
    return f"""You are a TDD agent that writes REAL code. You must output executable actions.

## TASK
{task_content}

## OUTPUT FORMAT
You MUST output actions in these formats:

For bash commands:
```bash
cargo test --lib
```

For file edits:
<edit file="path/to/file.rs" old="old code" new="new code"/>

For new files:
<write file="path/to/file.rs">
file content here
</write>

## FRACTAL DELEGATION (for complex tasks)
If the task is TOO COMPLEX (>400 LOC, >5 files, multiple domains), you can DELEGATE to sub-agents:

<fractal_delegate reason="Task requires 8 files across backend+frontend+tests">
  <subtask>Implement BikeService.CreateBike gRPC handler in backend</subtask>
  <subtask>Add CreateBike proto definition and generate code</subtask>
  <subtask>Create frontend Svelte component for bike creation</subtask>
  <subtask>Write E2E tests for bike creation flow</subtask>
</fractal_delegate>

Each subtask will be assigned to a separate agent working in parallel.
Use this when you estimate the task would take >400 LOC or touch >5 files.

## RULES
1. ALWAYS verify files exist before editing (use `ls` or `cat`)
2. ALWAYS run tests after changes
3. Keep changes minimal - edit only what's needed
4. If tests fail, analyze the error and fix it
5. When done successfully, output: SUCCESS
6. If stuck, output: NEEDS_HELP
7. If task too complex, use <fractal_delegate> to split and delegate

## AVAILABLE TESTS
- Rust: `cargo test --lib` (in veligo-platform/backend)
- Frontend: `npm run test` (in veligo-platform/frontend)
- E2E: `npx playwright test <file>` (in veligo-platform/frontend)

## PROJECT STRUCTURE
- Backend Rust: veligo-platform/backend/src/
- Frontend Svelte: veligo-platform/frontend/src/
- E2E Tests: veligo-platform/frontend/tests/ or tests/e2e/

Start by analyzing the task complexity. If >400 LOC or >5 files, use fractal_delegate.
Otherwise, implement the solution directly.
"""

def run_agent(task_file: str, queue_type: str = "tdd") -> Tuple[bool, str]:
    """
    Run the agent on a task file.
    Returns (success, summary).
    """
    # Resolve task file path
    task_path = Path(task_file)
    if not task_path.is_absolute():
        # Try relative to SCRIPT_DIR first (for tasks/T001.md)
        script_relative = SCRIPT_DIR / task_file
        if script_relative.exists():
            task_path = script_relative
        else:
            # Try relative to PROJECT_ROOT
            task_path = PROJECT_ROOT / task_file

    # Read task
    task_content = None
    if task_path.exists():
        task_content = task_path.read_text()[:50000]

    if not task_content:
        return False, f"Cannot read task file: {task_file} (tried {task_path})"

    task_id = Path(task_file).stem
    log(f"Starting task: {task_id}", GREEN)

    # Store task_id globally for fractal delegation
    global CURRENT_TASK_ID
    CURRENT_TASK_ID = task_id

    # Extract AO ref if present
    ao_ref = ""
    ao_match = re.search(r'\*\*AO_REF\*\*:\s*(\S+)', task_content)
    if ao_match:
        ao_ref = ao_match.group(1)

    # Extract description
    desc_match = re.search(r'^# Task [^:]+:\s*(.+)$', task_content, re.MULTILINE)
    description = desc_match.group(1) if desc_match else task_id

    # Initialize conversation
    if queue_type == "deploy":
        user_msg = "Execute STEP 1 NOW: Run `which veligo || echo NOT FOUND`"
    else:
        user_msg = "Analyze the task and start implementing. Show me your plan first, then execute it."

    messages = [
        {"role": "system", "content": build_system_prompt(task_content, queue_type)},
        {"role": "user", "content": user_msg}
    ]

    iteration = 0
    success = False
    all_outputs = []
    total_actions_executed = 0  # Track if any real work was done

    while iteration < MAX_ITERATIONS:
        iteration += 1
        log(f"Iteration {iteration}/{MAX_ITERATIONS}", BLUE)

        # Call LLM
        response = call_llm(messages)
        if not response:
            all_outputs.append("ERROR: LLM call failed")
            break

        all_outputs.append(f"=== LLM Response ===\n{response[:2000]}")

        # Check for success
        if "SUCCESS" in response.upper():
            log("Agent reported SUCCESS, verifying...", GREEN)

            # Verify actual work was done
            if total_actions_executed == 0:
                log("No actions executed - cannot accept SUCCESS", RED)
                messages.append({"role": "assistant", "content": response})
                if queue_type == "deploy":
                    messages.append({"role": "user", "content": "You reported SUCCESS but executed no commands. Run `veligo cicd pipeline` or deployment commands."})
                else:
                    messages.append({"role": "user", "content": "You reported SUCCESS but made no file changes. Please implement the actual changes using <edit> or <write> tags."})
                continue

            # Deploy tasks: success only if deployment commands were executed
            if queue_type == "deploy":
                # Check that at least one command was a deployment command (not just ls/find/cat exploration)
                deploy_keywords = ['veligo', 'deploy', 'cicd', 'npm run test', 'curl', 'cargo test', 'playwright']
                executed_deploy_cmd = False
                for output in all_outputs:
                    if any(kw in output.lower() for kw in deploy_keywords):
                        executed_deploy_cmd = True
                        break

                if not executed_deploy_cmd:
                    log("No deployment commands found (veligo, npm test, curl, etc.) - rejecting SUCCESS", RED)
                    messages.append({"role": "assistant", "content": response})
                    messages.append({"role": "user", "content": "You reported SUCCESS but didn't run deployment commands. Execute: veligo cicd pipeline OR npm run test:e2e OR curl health check."})
                    continue

                success = True
                log(f"Task {task_id} COMPLETE! (deploy - {total_actions_executed} commands executed)", GREEN)
                break

            # TDD tasks: run tests and commit
            tests_pass, test_output = run_tests("all")
            all_outputs.append(f"=== Test Results ===\n{test_output[:2000]}")

            if tests_pass:
                # Commit changes
                if git_commit(task_id, description[:50], ao_ref):
                    success = True
                    log(f"Task {task_id} COMPLETE!", GREEN)

                    # Create deploy task to trigger deployment pipeline
                    deploy_id = create_deploy_task(task_id, description[:80])
                    if deploy_id:
                        log(f"Deploy task created: {deploy_id} → wiggum_deploy.py will pick it up", BLUE)

                    break
                else:
                    messages.append({"role": "assistant", "content": response})
                    messages.append({"role": "user", "content": "Git commit failed. Check for issues."})
            else:
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "user", "content": f"Tests failed:\n{test_output[:1000]}\n\nFix the issues."})
                continue

        # Check for help needed
        if "NEEDS_HELP" in response.upper():
            log("Agent needs help", YELLOW)
            all_outputs.append("Agent requested help")
            break

        # Parse and execute actions
        actions = parse_actions(response)

        if not actions:
            log("No actions found in response", YELLOW)
            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": "Please provide concrete actions using ```bash or <edit> tags."})
            continue

        # Execute each action
        action_results = []
        for action in actions:
            log(f"Executing: {action.get('type')} - {str(action)[:100]}", BLUE)
            ok, output = execute_action(action)
            action_results.append(f"{action.get('type')}: {'OK' if ok else 'FAIL'}\n{output[:500]}")
            if ok and action.get('type') in ['edit', 'write', 'bash']:
                total_actions_executed += 1  # Count successful actions (file mods + bash commands)

        results_text = "\n---\n".join(action_results)
        all_outputs.append(f"=== Action Results ===\n{results_text[:2000]}")

        # Add results to conversation
        messages.append({"role": "assistant", "content": response})
        messages.append({"role": "user", "content": f"Action results:\n{results_text}\n\nContinue with the task."})

    summary = "\n\n".join(all_outputs[-5:])  # Last 5 outputs
    return success, summary

# ============================================================================
# CLI
# ============================================================================
def main():
    if len(sys.argv) < 2:
        print("Usage: real_agent.py <task_file> [tdd|deploy]")
        print("\nExample: real_agent.py tasks/T001.md tdd")
        sys.exit(1)

    task_file = sys.argv[1]
    queue_type = sys.argv[2] if len(sys.argv) > 2 else "tdd"

    log(f"Real Agent starting", GREEN)
    log(f"Task: {task_file}", BLUE)
    log(f"Queue: {queue_type}", BLUE)
    log(f"Backend: opencode ({OPENCODE_MODEL})", BLUE)

    success, summary = run_agent(task_file, queue_type)

    print(f"\n{'='*60}")
    print(f"RESULT: {'SUCCESS' if success else 'FAILED'}")
    print(f"{'='*60}")
    print(summary[-3000:])

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
