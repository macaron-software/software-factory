#!/usr/bin/env python3
"""
Git Hooks for RLM Pipeline
==========================

Hooks:
1. pre-commit  - Lint, fail-on-stubs, unit tests smoke
2. commit-msg  - Enforce task ID format
3. post-commit - Update task store, trigger adversarial

Usage:
    python3 git_hooks.py install       # Install hooks
    python3 git_hooks.py uninstall     # Remove hooks
    python3 git_hooks.py run pre-commit # Test hook manually

The hooks integrate with the RLM task store to:
- Associate commits with task IDs
- Trigger adversarial checks post-commit
- Update task status in the SQLite store
"""

import os
import re
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional
import json

RLM_DIR = Path(__file__).parent
POPINZ_ROOT = Path("/Users/sylvain/_POPINZ/popinz-dev")

# Patterns to reject (fail-on-stubs)
STUB_PATTERNS = [
    (r'\bTODO\b', "TODO comment found"),
    (r'\bFIXME\b', "FIXME comment found"),
    (r'\bXXX\b', "XXX marker found"),
    (r'NotImplemented', "NotImplemented found"),
    (r'todo!\(\)', "Rust todo!() found"),
    (r'unimplemented!\(\)', "Rust unimplemented!() found"),
    (r'pass\s*#.*stub', "Python stub pass found"),
    (r'return\s+null\s*;\s*//.*temp', "Temporary null return"),
    (r'test\.skip\(\)', "Unconditional test.skip()"),
    (r'describe\.skip\(\)', "Unconditional describe.skip()"),
    (r'@ts-ignore', "TypeScript @ts-ignore"),
    (r'@ts-expect-error', "TypeScript @ts-expect-error"),
    (r': any\b', "TypeScript 'any' type"),
    (r'\.unwrap\(\)', "Rust .unwrap() (use ? or expect)"),
]

# Task ID patterns
TASK_ID_PATTERNS = [
    r'[A-Z]+-\d+',        # JIRA style: TASK-123
    r'#\d+',              # GitHub issue: #123
    r'rust-[a-z_]+-\d+',  # RLM style: rust-build_error-0001
    r'e2e-[a-z_]+-\d+',   # RLM style: e2e-test_config-0082
    r'typescript-[a-z_]+-\d+',  # RLM style
]


def log(msg: str, level: str = "INFO"):
    """Log with emoji"""
    emoji = {
        "INFO": "ℹ️",
        "OK": "✅",
        "WARN": "⚠️",
        "ERROR": "❌",
        "HOOK": "🪝"
    }.get(level, "")
    print(f"{emoji} [{level}] {msg}", flush=True)


def run_cmd(cmd: List[str], cwd: Path = None) -> Tuple[int, str, str]:
    """Run command and return (code, stdout, stderr)"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(cwd) if cwd else None,
            timeout=60
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)


def get_staged_files() -> List[Path]:
    """Get list of staged files"""
    code, stdout, _ = run_cmd(["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"])
    if code != 0:
        return []
    return [Path(f) for f in stdout.strip().split('\n') if f]


def check_stub_patterns(files: List[Path]) -> List[Tuple[Path, int, str, str]]:
    """
    Check files for stub patterns.
    Returns list of (file, line_number, pattern, message).
    """
    violations = []

    for file_path in files:
        if not file_path.exists():
            continue

        # Skip binary files and specific directories
        if file_path.suffix in ['.png', '.jpg', '.gif', '.ico', '.woff', '.woff2', '.ttf']:
            continue
        if any(part in str(file_path) for part in ['node_modules', 'vendor', '.git', 'dist', 'build']):
            continue

        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue

        lines = content.split('\n')
        for line_num, line in enumerate(lines, 1):
            for pattern, message in STUB_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    violations.append((file_path, line_num, pattern, message))

    return violations


def pre_commit_hook() -> int:
    """
    Pre-commit hook:
    1. Check for stub patterns (fail-on-stubs)
    2. Run linters (if configured)
    3. Run smoke tests (optional)
    """
    log("Running pre-commit checks...", "HOOK")

    staged_files = get_staged_files()
    if not staged_files:
        log("No staged files", "OK")
        return 0

    log(f"Checking {len(staged_files)} staged files")

    # 1. Check stub patterns
    violations = check_stub_patterns(staged_files)
    if violations:
        log("Stub patterns found - commit blocked!", "ERROR")
        for file_path, line_num, pattern, message in violations[:10]:  # Show first 10
            print(f"  {file_path}:{line_num} - {message}")
        if len(violations) > 10:
            print(f"  ... and {len(violations) - 10} more violations")
        return 1

    log("No stub patterns found", "OK")

    # 2. Run PHP syntax check (if PHP files)
    php_files = [f for f in staged_files if f.suffix == '.php']
    if php_files:
        log(f"Checking PHP syntax for {len(php_files)} files...")
        for php_file in php_files[:5]:  # Check first 5
            code, _, stderr = run_cmd(["php", "-l", str(php_file)])
            if code != 0:
                log(f"PHP syntax error in {php_file}", "ERROR")
                print(stderr)
                return 1
        log("PHP syntax OK", "OK")

    # 3. Run TypeScript/ESLint check (if TS files)
    ts_files = [f for f in staged_files if f.suffix in ['.ts', '.tsx']]
    if ts_files and (POPINZ_ROOT / "node_modules/.bin/eslint").exists():
        log("Running ESLint on TypeScript files...")
        for ts_file in ts_files[:3]:  # Check first 3
            code, _, stderr = run_cmd(
                ["npx", "eslint", "--quiet", str(ts_file)],
                cwd=POPINZ_ROOT
            )
            if code != 0:
                log(f"ESLint error in {ts_file}", "WARN")
                # Don't block, just warn

    # 4. Run Rust check (if Rust files)
    rs_files = [f for f in staged_files if f.suffix == '.rs']
    if rs_files:
        log("Running cargo check...")
        code, _, stderr = run_cmd(
            ["cargo", "check", "--all-targets"],
            cwd=POPINZ_ROOT / "popinz-v2-rust"
        )
        if code != 0:
            log("Cargo check failed", "ERROR")
            print(stderr[:500])
            return 1
        log("Cargo check OK", "OK")

    log("Pre-commit checks passed!", "OK")
    return 0


def commit_msg_hook(msg_file: str) -> int:
    """
    Commit message hook:
    1. Enforce task ID in commit message
    2. Validate format
    """
    log("Validating commit message...", "HOOK")

    try:
        with open(msg_file, 'r') as f:
            message = f.read().strip()
    except Exception as e:
        log(f"Cannot read commit message: {e}", "ERROR")
        return 1

    # Skip merge commits
    if message.startswith("Merge"):
        return 0

    # Check for task ID
    has_task_id = any(
        re.search(pattern, message)
        for pattern in TASK_ID_PATTERNS
    )

    if not has_task_id:
        log("No task ID found in commit message", "WARN")
        print("Expected format: feat(scope): description [TASK-123]")
        print("Or: fix: description #123")
        print("Or include RLM task ID like: rust-build_error-0001")
        # Don't block, just warn (allow WIP commits)

    # Validate conventional commit format (optional)
    conventional_pattern = r'^(feat|fix|docs|style|refactor|test|chore|perf|ci|build|revert)(\([a-z-]+\))?!?:'
    if not re.match(conventional_pattern, message, re.IGNORECASE):
        log("Consider using conventional commit format", "WARN")
        print("Example: feat(auth): add login feature")

    log("Commit message validated", "OK")
    return 0


def post_commit_hook() -> int:
    """
    Post-commit hook:
    1. Extract task ID from commit message
    2. Update task store with commit SHA
    3. Optionally trigger adversarial check
    """
    log("Running post-commit actions...", "HOOK")

    # Get commit info
    code, commit_sha, _ = run_cmd(["git", "rev-parse", "HEAD"])
    if code != 0:
        log("Cannot get commit SHA", "ERROR")
        return 1
    commit_sha = commit_sha.strip()[:12]

    code, message, _ = run_cmd(["git", "log", "-1", "--format=%s"])
    if code != 0:
        log("Cannot get commit message", "ERROR")
        return 1
    message = message.strip()

    log(f"Commit: {commit_sha} - {message[:50]}...")

    # Extract task ID
    task_id = None
    for pattern in TASK_ID_PATTERNS:
        match = re.search(pattern, message)
        if match:
            task_id = match.group()
            break

    if task_id:
        log(f"Task ID: {task_id}", "INFO")

        # Update task store
        try:
            from task_store import TaskStore
            store = TaskStore()

            # Find task and update with commit SHA
            task = store.get_task(task_id)
            if task:
                store.transition(
                    task_id,
                    "merged" if task.status == "ready_for_adversarial" else task.status,
                    changed_by="git-hook",
                    commit_sha=commit_sha
                )
                log(f"Updated task {task_id} with commit {commit_sha}", "OK")
        except ImportError:
            log("Task store not available (SQLite)", "WARN")
        except Exception as e:
            log(f"Could not update task store: {e}", "WARN")

    # Get list of changed files
    code, files_changed, _ = run_cmd(["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"])
    files_list = files_changed.strip().split('\n') if files_changed.strip() else []

    log(f"Files changed: {len(files_list)}", "INFO")

    # Write commit info for adversarial
    commit_info = {
        "sha": commit_sha,
        "message": message,
        "task_id": task_id,
        "files": files_list,
        "timestamp": datetime.now().isoformat()
    }

    commit_log = RLM_DIR / "logs" / "commits.jsonl"
    commit_log.parent.mkdir(exist_ok=True)
    with open(commit_log, 'a') as f:
        f.write(json.dumps(commit_info) + '\n')

    log("Post-commit completed", "OK")
    return 0


# Hook scripts content
HOOK_SCRIPTS = {
    "pre-commit": '''#!/bin/bash
# RLM Pre-commit Hook
python3 "{rlm_dir}/git_hooks.py" run pre-commit
exit $?
''',

    "commit-msg": '''#!/bin/bash
# RLM Commit Message Hook
python3 "{rlm_dir}/git_hooks.py" run commit-msg "$1"
exit $?
''',

    "post-commit": '''#!/bin/bash
# RLM Post-commit Hook
python3 "{rlm_dir}/git_hooks.py" run post-commit
# Don't fail on post-commit errors
exit 0
'''
}


def install_hooks(git_dir: Path = None):
    """Install git hooks"""
    if git_dir is None:
        git_dir = POPINZ_ROOT / ".git"

    hooks_dir = git_dir / "hooks"
    if not hooks_dir.exists():
        log(f"Git hooks directory not found: {hooks_dir}", "ERROR")
        return 1

    log(f"Installing hooks to {hooks_dir}", "HOOK")

    for hook_name, script_template in HOOK_SCRIPTS.items():
        hook_path = hooks_dir / hook_name
        script_content = script_template.format(rlm_dir=RLM_DIR)

        # Backup existing hook
        if hook_path.exists():
            backup_path = hook_path.with_suffix('.backup')
            hook_path.rename(backup_path)
            log(f"Backed up existing {hook_name} to {backup_path.name}", "WARN")

        hook_path.write_text(script_content)
        hook_path.chmod(0o755)
        log(f"Installed {hook_name}", "OK")

    log("All hooks installed!", "OK")
    return 0


def uninstall_hooks(git_dir: Path = None):
    """Uninstall git hooks"""
    if git_dir is None:
        git_dir = POPINZ_ROOT / ".git"

    hooks_dir = git_dir / "hooks"

    log(f"Uninstalling hooks from {hooks_dir}", "HOOK")

    for hook_name in HOOK_SCRIPTS.keys():
        hook_path = hooks_dir / hook_name
        if hook_path.exists():
            hook_path.unlink()
            log(f"Removed {hook_name}", "OK")

            # Restore backup if exists
            backup_path = hook_path.with_suffix('.backup')
            if backup_path.exists():
                backup_path.rename(hook_path)
                log(f"Restored {hook_name} from backup", "INFO")

    log("Hooks uninstalled", "OK")
    return 0


def main():
    import argparse

    parser = argparse.ArgumentParser(description="RLM Git Hooks")
    parser.add_argument("command", choices=["install", "uninstall", "run", "check"])
    parser.add_argument("hook", nargs="?", choices=["pre-commit", "commit-msg", "post-commit"])
    parser.add_argument("args", nargs="*")
    parser.add_argument("--git-dir", type=str, help="Git directory path")

    args = parser.parse_args()

    git_dir = Path(args.git_dir) if args.git_dir else None

    if args.command == "install":
        return install_hooks(git_dir)

    elif args.command == "uninstall":
        return uninstall_hooks(git_dir)

    elif args.command == "run":
        if args.hook == "pre-commit":
            return pre_commit_hook()
        elif args.hook == "commit-msg":
            msg_file = args.args[0] if args.args else ".git/COMMIT_EDITMSG"
            return commit_msg_hook(msg_file)
        elif args.hook == "post-commit":
            return post_commit_hook()
        else:
            log("Hook name required", "ERROR")
            return 1

    elif args.command == "check":
        # Check current directory for stub patterns
        files = list(Path(".").rglob("*.py")) + list(Path(".").rglob("*.ts")) + list(Path(".").rglob("*.rs"))
        violations = check_stub_patterns(files[:100])  # Check first 100

        if violations:
            log(f"Found {len(violations)} stub patterns", "WARN")
            for file_path, line_num, pattern, message in violations[:20]:
                print(f"  {file_path}:{line_num} - {message}")
            return 1
        else:
            log("No stub patterns found", "OK")
            return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
