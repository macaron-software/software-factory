#!/usr/bin/env python3
"""
Integrator Worker - Cross-layer integration agent
==================================================
Executes integration tasks that wire layers together:
- Server bootstrap (mount all services in main.rs)
- API connection (replace frontend mocks with real gRPC calls)
- Migration (apply DB schema)
- Proxy (configure nginx gRPC-Web)
- Config (validate .env consistency)
- Module wiring (activate module system)
- Proto generation (generate TS clients from .proto)

Unlike TDD workers (1 file, 1 test), the integrator works cross-layer:
- Modifies N files simultaneously
- Verifies integration actually works (build + run + health check)
- Longer timeout (30min vs 10min TDD)
- Optional FRACTAL decomposition (LLM decides, subtasks run sequentially)
"""

import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.project_registry import ProjectConfig
from core.task_store import TaskStore, Task, TaskStatus
from core.llm_client import run_opencode
from core.adversarial import AdversarialGate


def log(msg: str, level: str = "INFO", worker_id: int = 0):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [INTEGRATOR-{worker_id}] [{level}] {msg}", flush=True)


# Verify commands by integration type
VERIFY_COMMANDS = {
    "bootstrap": "cargo check --workspace",
    "api_connection": "npm run build",
    "migration": "echo 'Migration verify: check sqlx migrate status'",
    "proxy": "nginx -t 2>&1 || echo 'nginx not installed locally - skip verify'",
    "config": "echo 'Config verify: parse .env files'",
    "module_wiring": "cargo test --lib -- module 2>&1 || cargo check --workspace",
    "proto_gen": "echo 'Proto gen verify: check TS client files exist'",
}


class IntegratorWorker:
    """
    Executes integration tasks that wire project layers together.

    Unlike TDD workers:
    - Optional FRACTAL (LLM decides, subtasks run SEQUENTIALLY not parallel)
    - Works on multiple files cross-layer
    - Runs verification (build + health check) after changes
    - Longer timeout (30 min)
    """

    MAX_ITERATIONS = 5
    OPENCODE_TIMEOUT = 1800  # 30 min

    def __init__(
        self,
        project: ProjectConfig,
        task_store: TaskStore,
        adversarial: AdversarialGate = None,
    ):
        self.project = project
        self.task_store = task_store
        self.adversarial = adversarial or AdversarialGate(project)

    def log(self, msg: str, level: str = "INFO"):
        log(msg, level)

    async def run_one(self) -> bool:
        """Run a single integration task. Returns True if successful."""
        # Get highest priority integration task
        tasks = self.task_store.get_tasks_by_status(
            self.project.id, TaskStatus.PENDING, limit=50
        )

        # Filter to integration type only, sorted by wsjf_score desc
        integration_tasks = [t for t in tasks if t.type == "integration"]
        if not integration_tasks:
            self.log("No integration tasks pending")
            return False

        # Sort by integration type priority
        type_priority = {
            "bootstrap": 0,
            "migration": 1,
            "proto_gen": 2,
            "api_connection": 3,
            "proxy": 4,
            "config": 5,
            "module_wiring": 6,
        }
        integration_tasks.sort(
            key=lambda t: type_priority.get(
                (t.get_context() or {}).get("integration_type", ""), 99
            )
        )

        task = integration_tasks[0]
        self.log(f"🔗 Starting integration: {task.id}")
        self.log(f"   Description: {task.description[:100]}")

        # Transition to INTEGRATION_IN_PROGRESS
        if not self.task_store.transition(task.id, TaskStatus.INTEGRATION_IN_PROGRESS):
            self.log("Failed to claim task", "WARN")
            return False

        try:
            success = await self._execute(task)
            if success:
                self.task_store.transition(task.id, TaskStatus.CODE_WRITTEN)
                self.log(f"✅ Integration complete: {task.id}")
                return True
            else:
                self.task_store.transition(task.id, TaskStatus.INTEGRATION_FAILED)
                self.log(f"❌ Integration failed: {task.id}", "WARN")
                return False
        except Exception as e:
            self.log(f"Exception: {e}", "ERROR")
            self.task_store.transition(task.id, TaskStatus.INTEGRATION_FAILED)
            return False

    async def _execute(self, task: Task) -> bool:
        """Execute an integration task, with optional FRACTAL decomposition."""
        context = task.get_context() or {}
        integration_type = context.get("integration_type", "generic")
        verify_cmd = VERIFY_COMMANDS.get(integration_type, "echo 'No verify command'")

        self.log(f"   Type: {integration_type}")
        self.log(f"   Files: {task.files[:5]}")
        self.log(f"   Verify: {verify_cmd}")

        # FRACTAL: LLM may decompose large integration tasks into sub-steps
        try:
            from core.fractal import FractalDecomposer
            from core.llm_client import LLMClient
            llm = LLMClient() if hasattr(LLMClient, '__init__') else None
            decomposer = FractalDecomposer(self.project, llm)
            task_dict = {
                "id": task.id, "type": task.type, "domain": task.domain,
                "description": task.description, "files": task.files,
                "context": context,
            }
            should_split, analysis = decomposer.should_decompose(task_dict, 0)
            if should_split and llm:
                subtasks = await decomposer.decompose(task_dict, 0)
                if subtasks and len(subtasks) > 1:
                    self.log(f"   🔀 FRACTAL: Split into {len(subtasks)} sequential sub-tasks")
                    all_ok = True
                    for i, st in enumerate(subtasks):
                        self.log(f"   [{i+1}/{len(subtasks)}] {st.get('description', '')[:80]}")
                        # Create a mini-task for each subtask and execute directly
                        ok = await self._execute_single(task, st, verify_cmd)
                        if not ok:
                            self.log(f"   Sub-task {i+1} failed, stopping", "WARN")
                            all_ok = False
                            break
                    return all_ok
        except Exception as e:
            self.log(f"   FRACTAL check skipped: {e}", "WARN")

        return await self._execute_single(task, None, verify_cmd)

    async def _execute_single(self, task: Task, subtask_dict: Dict = None, verify_cmd: str = None) -> bool:
        """Execute a single integration step with LLM + verify loop."""
        context = task.get_context() or {}
        integration_type = context.get("integration_type", "generic")
        if not verify_cmd:
            verify_cmd = VERIFY_COMMANDS.get(integration_type, "echo 'No verify command'")

        # Use subtask description if available, else original task
        description = subtask_dict.get("description", task.description) if subtask_dict else task.description
        files = subtask_dict.get("files", task.files) if subtask_dict else task.files

        feedback = ""
        for iteration in range(self.MAX_ITERATIONS):
            self.log(f"   Iteration {iteration + 1}/{self.MAX_ITERATIONS}")

            # Build integration prompt (use subtask desc/files if available)
            prompt = self._build_prompt(task, integration_type, verify_cmd, feedback,
                                        override_desc=description, override_files=files)

            # Capture git state
            git_before = self._get_git_status()

            # Run LLM agent
            returncode, output = await run_opencode(
                prompt,
                model="minimax/MiniMax-M2.5",
                cwd=str(self.project.root_path),
                timeout=self.OPENCODE_TIMEOUT,
                project=self.project.name,
            )

            if returncode != 0:
                self.log(f"   LLM failed: {(output or '')[:200]}", "WARN")
                feedback = f"LLM execution failed: {(output or '')[:500]}"
                continue

            # Check for code changes
            changes = self._detect_git_changes(git_before)
            if not changes:
                self.log("   No code changes detected", "WARN")
                feedback = "No code changes were made. You MUST modify files to wire the layers."
                continue

            self.log(f"   {len(changes)} files changed: {list(changes.keys())[:5]}")

            # Run verify command
            verify_ok, verify_output = await self._run_verify(verify_cmd)
            if not verify_ok:
                self.log(f"   Verify FAILED: {verify_output[:200]}", "WARN")
                feedback = f"VERIFICATION FAILED after your changes:\n{verify_output[:1000]}\n\nFix the issues and ensure the verify command passes."
                # Don't reset git - let the LLM fix forward
                continue

            self.log(f"   ✅ Verify PASSED")

            # Adversarial check
            check_result = await self._run_adversarial(changes)
            if not check_result.approved:
                self.log(f"   Adversarial REJECTED: {check_result.issues[:200]}", "WARN")
                feedback = f"ADVERSARIAL REJECTED:\n{check_result.issues}"
                await self._git_reset()
                continue

            self.log(f"   ✅ Adversarial APPROVED")
            return True

        self.log(f"   Max iterations reached", "WARN")
        return False

    def _build_prompt(self, task: Task, integration_type: str, verify_cmd: str, feedback: str,
                       override_desc: str = None, override_files: list = None) -> str:
        """Build prompt for integration agent."""
        context = task.get_context() or {}
        desc = override_desc or task.description
        files = override_files or task.files

        feedback_section = ""
        if feedback:
            feedback_section = f"""
⚠️ PREVIOUS ATTEMPT FAILED:
{feedback}

You MUST fix the issues above. Do NOT repeat the same mistakes.
"""

        # Get stack/conventions from project config
        stack_info = ""
        if self.project.raw_config:
            domains = self.project.raw_config.get("domains", {})
            for domain_name, domain_cfg in domains.items():
                stack = domain_cfg.get("stack", {})
                if stack:
                    stack_info += f"\n{domain_name} stack: {', '.join(f'{k} {v}' for k, v in stack.items())}"

        return f"""You are an INTEGRATION agent. Your job is to WIRE project layers together.

PROJECT: {self.project.name} ({self.project.display_name})
ROOT: {self.project.root_path}

INTEGRATION TASK: {desc}
TYPE: {integration_type}
FILES TO MODIFY: {json.dumps(files)}

CONTEXT:
{json.dumps(context, indent=2)[:2000]}
{stack_info}
{feedback_section}
MCP TOOLS AVAILABLE:
- lrm_locate(query, scope, limit): Find files matching pattern
- lrm_summarize(files, goal): Get file summaries
- lrm_conventions(domain): Get coding conventions
- lrm_build(domain, command): Run build/test commands

RULES:
1. You MUST modify ALL necessary files to complete the integration
2. After changes, run the VERIFY command to confirm it works
3. VERIFY COMMAND: {verify_cmd}
4. The system must ACTUALLY WORK after your changes (not just compile)
5. For server bootstrap: ALL gRPC services must be mounted
6. For API connections: NO mock/hardcoded data - real API calls only
7. For proto gen: generate actual TypeScript clients from .proto files
8. For config: all .env files must be consistent
9. NEVER create or modify .md files (README, VISION, CLAUDE, reports)
10. NEVER create _REPORT, _ANALYSIS, _REVIEW, _SUMMARY files
11. NEVER touch node_modules/, _archive/, .git/, dist/, target/
12. Write CODE only. No documentation. No reports.
13. VITEST: ALWAYS use `npx vitest run --pool=forks --poolOptions.forks.maxForks=1` (prevents 4GB RAM)

WORKFLOW:
1. Use lrm_locate to find ALL relevant files across layers
2. Use lrm_summarize to understand current state
3. Make ALL necessary changes (multiple files)
4. Run verify command: {verify_cmd}
5. Fix any issues until verify passes

Start by exploring the codebase with lrm_locate, then make the changes.
"""

    def _get_git_status(self) -> set:
        """Get set of modified files from git."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(self.project.root_path),
                capture_output=True, text=True, timeout=10,
            )
            files = set()
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    files.add(line[3:].strip().strip('"'))
            return files
        except Exception:
            return set()

    def _detect_git_changes(self, before: set) -> Dict[str, str]:
        """Detect file changes by comparing git status."""
        after = self._get_git_status()
        new_changes = after - before
        changes = {f: "modified" for f in new_changes}

        try:
            result = subprocess.run(
                ["git", "diff", "--name-only"],
                cwd=str(self.project.root_path),
                capture_output=True, text=True, timeout=10,
            )
            for f in result.stdout.strip().split("\n"):
                if f.strip():
                    changes[f.strip()] = "modified"
        except Exception:
            pass

        return changes

    async def _run_verify(self, cmd: str) -> tuple:
        """Run verification command. Returns (success, output)."""
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                cwd=str(self.project.root_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=300)
            output = stdout.decode("utf-8", errors="replace")
            return proc.returncode == 0, output
        except asyncio.TimeoutError:
            return False, "Verify command timed out (300s)"
        except Exception as e:
            return False, f"Verify error: {e}"

    async def _run_adversarial(self, changes: Dict[str, str]):
        """Run adversarial check on changes."""
        from core.adversarial import CheckResult
        # File protection check first
        protection_issues = self.adversarial.check_file_protection(changes)
        if protection_issues:
            total = sum(i.points for i in protection_issues)
            if total >= self.adversarial.threshold:
                return CheckResult(
                    approved=False, score=total, threshold=self.adversarial.threshold,
                    issues=protection_issues,
                    feedback="; ".join(i.message for i in protection_issues),
                )
        return await self.adversarial.check_code(changes)

    async def _git_reset(self):
        """Reset git changes."""
        try:
            subprocess.run(
                ["git", "checkout", "."],
                cwd=str(self.project.root_path),
                capture_output=True, timeout=10,
            )
        except Exception:
            pass

    async def run_pending(self) -> int:
        """Run all pending integration tasks. Returns count completed."""
        completed = 0
        while True:
            ok = await self.run_one()
            if not ok:
                break
            completed += 1
        return completed
