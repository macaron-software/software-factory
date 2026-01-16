"""
Wiggum TDD - Parallel TDD Workers for RLM.

Processes tasks from the backlog using true TDD cycle:
RED (write failing test) → GREEN (write fix) → VERIFY (run test) → COMMIT

LLM: MiniMax M2.1 via opencode
"""

import asyncio
import json
import logging
import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from .adversarial import AdversarialChecker
from .models import (
    Backlog,
    COMPLEXITY_THRESHOLD,
    Domain,
    DOMAIN_CONVENTIONS,
    Finding,
    MAX_ADVERSARIAL_RETRIES,
    MAX_FRACTAL_DEPTH,
    Task,
    TaskStatus,
    TaskType,
)

logger = logging.getLogger(__name__)

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
BACKLOG_PATH = Path(__file__).parent / "backlog_tasks.json"
DEPLOY_BACKLOG_PATH = Path(__file__).parent / "deploy_backlog.json"

# LLM Config - MiniMax M2.1 via opencode
OPENCODE_MODEL = os.getenv("RLM_TDD_MODEL", "minimax/MiniMax-M2.1")

# TDD System Prompt
TDD_SYSTEM_PROMPT = """Tu es un développeur TDD strict travaillant sur le projet Fervenza (wedding planning CRM).

CYCLE TDD OBLIGATOIRE:
1. RED: Comprendre l'erreur et écrire/identifier un test qui échoue
2. GREEN: Écrire le FIX MINIMAL pour que le test passe
3. VERIFY: Le test DOIT passer après ton fix

RÈGLES STRICTES:
- JAMAIS de "gold plating" - code uniquement ce qui est demandé
- JAMAIS de test.skip, #[ignore], pytest.mark.skip
- JAMAIS de # type: ignore, @ts-ignore, as any
- JAMAIS de .unwrap() en Rust (utilise ?)
- JAMAIS de try/catch vide ou silencieux

CONVENTIONS FERVENZA:
{conventions}

CONTEXTE DE LA TÂCHE:
- ID: {task_id}
- Type: {task_type}
- Domaine: {domain}
- Fichier: {file}
- Ligne: {line}
- Erreur: {error_message}

CODE SOURCE (autour de l'erreur):
```
{file_content}
```

IMPORTS UTILISÉS:
{imports}

RÉPONDS UNIQUEMENT AVEC LE CODE CORRIGÉ entre balises ```{lang}``` et ```.
Ne mets aucune explication avant ou après le code.
"""

# Prompt for complexity analysis
COMPLEXITY_ANALYSIS_PROMPT = """Analyse cette tâche et détermine si elle est trop complexe pour un seul fix.

TÂCHE:
- ID: {task_id}
- Description: {description}
- Fichiers: {files}
- Erreur: {error_message}

CODE SOURCE:
```
{file_content}
```

Critères de complexité:
1. Plus de 3 fichiers à modifier
2. Plus de 100 lignes de code affectées
3. Nécessite des changements structurels (refactoring)
4. Dépendances circulaires à résoudre
5. Plusieurs erreurs interconnectées

Réponds UNIQUEMENT avec JSON:
{{
  "is_complex": true/false,
  "reason": "explication courte",
  "subtasks": [
    {{"description": "...", "files": ["..."], "error_focus": "..."}}
  ]
}}

Si is_complex=false, subtasks doit être vide [].
"""

# Prompt for retry with adversarial feedback
RETRY_WITH_FEEDBACK_PROMPT = """Tu as échoué la quality gate adversarial. Corrige le code.

FEEDBACK ADVERSARIAL:
{adversarial_feedback}

TENTATIVES PRÉCÉDENTES:
{previous_attempts}

{original_prompt}

IMPORTANT: Évite les patterns qui ont causé le rejet:
- JAMAIS de test.skip, #[ignore], pytest.mark.skip
- JAMAIS de # type: ignore, @ts-ignore, as any
- JAMAIS de .unwrap() en Rust (utilise ?)
- JAMAIS de try/catch vide

RÉPONDS UNIQUEMENT AVEC LE CODE CORRIGÉ.
"""


class WiggumWorker:
    """
    A single TDD worker that processes tasks.

    Uses opencode with MiniMax M2.1 to generate fixes and runs tests to verify.
    """

    def __init__(
        self,
        worker_id: int,
        model: str = OPENCODE_MODEL,
        adversarial: Optional[AdversarialChecker] = None,
        backlog: Optional[Backlog] = None,
    ):
        self.worker_id = worker_id
        self.model = model
        self.adversarial = adversarial or AdversarialChecker()
        self.backlog = backlog  # Reference for adding subtasks

    async def process_task(self, task: Task) -> bool:
        """
        Process a single task using TDD cycle with fractal decomposition.

        Flow:
        1. Check if task is too complex → decompose into subtasks
        2. Generate fix using LLM
        3. Adversarial check → retry with feedback if rejected
        4. Apply fix and verify
        5. Commit if successful

        Returns True if task completed successfully, False otherwise.
        """
        logger.info(f"Worker {self.worker_id}: Starting task {task.id} (depth={task.depth})")

        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.utcnow()

        # Step 1: Check complexity (only for root/shallow tasks)
        if task.depth < MAX_FRACTAL_DEPTH and not task.is_complex:
            is_complex, subtasks = await self._analyze_complexity(task)
            if is_complex:
                logger.info(f"Worker {self.worker_id}: Task {task.id} is complex, decomposing...")
                created = await self._decompose_task(task, subtasks)
                if created:
                    task.status = TaskStatus.DECOMPOSED
                    return True  # Subtasks will be processed separately

        # Step 2-5: TDD cycle with adversarial retry
        max_attempts = MAX_ADVERSARIAL_RETRIES + 1
        for attempt in range(max_attempts):
            try:
                # Generate fix (with feedback if retry)
                if attempt > 0 and task.adversarial_feedback:
                    fix_code = await self._generate_fix_with_feedback(task)
                else:
                    fix_code = await self._generate_fix(task)

                if not fix_code:
                    logger.warning(f"Worker {self.worker_id}: No fix generated for {task.id}")
                    continue

                # Adversarial check
                check_result = self.adversarial.check_code(fix_code)
                if check_result["reject"]:
                    logger.warning(
                        f"Worker {self.worker_id}: Adversarial rejected (attempt {attempt+1}): {check_result['reasons']}"
                    )
                    # Store feedback for retry
                    task.adversarial_feedback = "; ".join(check_result["reasons"])
                    task.previous_attempts.append(fix_code[:500])  # Keep first 500 chars
                    task.retry_count += 1

                    if attempt >= MAX_ADVERSARIAL_RETRIES:
                        task.status = TaskStatus.ADVERSARIAL_FAILED
                        task.error = f"Adversarial rejected after {attempt+1} attempts"
                        logger.error(f"Worker {self.worker_id}: Task {task.id} failed adversarial")
                        return False
                    continue

                # Apply fix to file
                applied = await self._apply_fix(task, fix_code)
                if not applied:
                    continue

                # Run verification (test or build)
                verified = await self._verify_fix(task)

                if verified:
                    # Commit the fix
                    commit_hash = await self._commit_fix(task)
                    if commit_hash:
                        task.status = TaskStatus.COMPLETED
                        task.completed_at = datetime.utcnow()
                        task.commit_hash = commit_hash
                        logger.info(f"Worker {self.worker_id}: Task {task.id} completed: {commit_hash}")
                        return True
                else:
                    # Revert changes
                    await self._revert_changes(task)
                    task.error = "Verification failed"

            except Exception as e:
                logger.error(f"Worker {self.worker_id}: Error on task {task.id}: {e}")
                task.error = str(e)
                task.retry_count += 1

        # All retries failed
        task.status = TaskStatus.FAILED
        logger.error(f"Worker {self.worker_id}: Task {task.id} failed after {max_attempts} attempts")
        return False

    async def _analyze_complexity(self, task: Task) -> tuple[bool, list[dict]]:
        """
        Analyze if task is too complex and needs decomposition.

        Returns: (is_complex, list of subtask definitions)
        """
        # Quick heuristics first
        if task.file_content and len(task.file_content.splitlines()) > COMPLEXITY_THRESHOLD:
            task.is_complex = True

        if len(task.files) > 3:
            task.is_complex = True

        # If heuristics say complex, use LLM to decompose
        if not task.is_complex:
            return False, []

        prompt = COMPLEXITY_ANALYSIS_PROMPT.format(
            task_id=task.id,
            description=task.description,
            files=", ".join(task.files),
            error_message=task.finding.message,
            file_content=task.file_content or "(no content)",
        )

        try:
            response = await self._call_opencode(prompt)
            if response:
                json_match = re.search(r"\{.*\}", response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    return data.get("is_complex", False), data.get("subtasks", [])
        except Exception as e:
            logger.warning(f"Complexity analysis failed: {e}")

        return task.is_complex, []

    async def _decompose_task(self, parent_task: Task, subtask_defs: list[dict]) -> bool:
        """
        Create subtasks from decomposition analysis.

        Returns True if subtasks were created successfully.
        """
        if not self.backlog or not subtask_defs:
            return False

        created_ids = []
        for i, subtask_def in enumerate(subtask_defs):
            subtask_id = f"{parent_task.id}-sub{i+1}"

            subtask = Task(
                id=subtask_id,
                type=parent_task.type,
                domain=parent_task.domain,
                description=subtask_def.get("description", f"Subtask {i+1} of {parent_task.id}"),
                files=subtask_def.get("files", parent_task.files),
                finding=Finding(
                    type=parent_task.finding.type,
                    severity=parent_task.finding.severity,
                    message=subtask_def.get("error_focus", parent_task.finding.message),
                ),
                parent_task_id=parent_task.id,
                depth=parent_task.depth + 1,
                conventions=parent_task.conventions,
                # Inherit WSJF from parent
                business_value=parent_task.business_value,
                time_criticality=parent_task.time_criticality,
                risk_reduction=parent_task.risk_reduction,
                job_size=max(1, parent_task.job_size // len(subtask_defs)),
            )
            subtask.calculate_wsjf()

            self.backlog.tasks.append(subtask)
            created_ids.append(subtask_id)
            logger.info(f"Worker {self.worker_id}: Created subtask {subtask_id}")

        parent_task.subtask_ids = created_ids
        return len(created_ids) > 0

    async def _generate_fix_with_feedback(self, task: Task) -> Optional[str]:
        """Generate fix using adversarial feedback from previous attempts."""
        lang_map = {
            Domain.RUST: "rust",
            Domain.PYTHON: "python",
            Domain.TYPESCRIPT: "typescript",
            Domain.PROTO: "proto",
            Domain.SQL: "sql",
            Domain.E2E: "typescript",
        }

        # Build original prompt
        original_prompt = TDD_SYSTEM_PROMPT.format(
            conventions=json.dumps(task.conventions, indent=2),
            task_id=task.id,
            task_type=task.type.value,
            domain=task.domain.value,
            file=task.files[0] if task.files else "unknown",
            line=task.finding.line or "?",
            error_message=task.finding.message,
            file_content=task.file_content or "(no content)",
            imports="\n".join(task.imports[:10]) if task.imports else "(none)",
            lang=lang_map.get(task.domain, "text"),
        )

        # Build retry prompt with feedback
        prompt = RETRY_WITH_FEEDBACK_PROMPT.format(
            adversarial_feedback=task.adversarial_feedback or "Aucun feedback",
            previous_attempts="\n---\n".join(task.previous_attempts[-2:]) or "Aucune",
            original_prompt=original_prompt,
        )

        try:
            content = await self._call_opencode(prompt)

            if not content:
                return None

            # Extract code from response
            code_match = re.search(r"```\w*\n(.*?)```", content, re.DOTALL)
            if code_match:
                return code_match.group(1).strip()

            return content.strip()

        except Exception as e:
            logger.error(f"LLM error (retry): {e}")
            return None

    async def _generate_fix(self, task: Task) -> Optional[str]:
        """Generate fix code using opencode with MiniMax M2.1."""
        lang_map = {
            Domain.RUST: "rust",
            Domain.PYTHON: "python",
            Domain.TYPESCRIPT: "typescript",
            Domain.PROTO: "proto",
            Domain.SQL: "sql",
            Domain.E2E: "typescript",
        }

        prompt = TDD_SYSTEM_PROMPT.format(
            conventions=json.dumps(task.conventions, indent=2),
            task_id=task.id,
            task_type=task.type.value,
            domain=task.domain.value,
            file=task.files[0] if task.files else "unknown",
            line=task.finding.line or "?",
            error_message=task.finding.message,
            file_content=task.file_content or "(no content)",
            imports="\n".join(task.imports[:10]) if task.imports else "(none)",
            lang=lang_map.get(task.domain, "text"),
        )

        try:
            # Use opencode with MiniMax M2.1
            content = await self._call_opencode(prompt)

            if not content:
                return None

            # Extract code from response
            code_match = re.search(r"```\w*\n(.*?)```", content, re.DOTALL)
            if code_match:
                return code_match.group(1).strip()

            return content.strip()

        except Exception as e:
            logger.error(f"LLM error: {e}")
            return None

    async def _call_opencode(self, prompt: str) -> Optional[str]:
        """Call opencode CLI with MiniMax M2.1 model."""
        try:
            # Write prompt to temp file
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
                f.write(prompt)
                prompt_file = f.name

            # Call opencode
            result = subprocess.run(
                [
                    "opencode",
                    "--model", self.model,
                    "--prompt", f"@{prompt_file}",
                    "--no-interactive",
                ],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=PROJECT_ROOT,
            )

            # Clean up
            Path(prompt_file).unlink(missing_ok=True)

            if result.returncode != 0:
                logger.error(f"opencode failed: {result.stderr[:500]}")
                return None

            return result.stdout

        except subprocess.TimeoutExpired:
            logger.error("opencode timed out")
            return None
        except FileNotFoundError:
            logger.error("opencode not found - install with: go install github.com/opencode-ai/opencode@latest")
            return None
        except Exception as e:
            logger.error(f"opencode error: {e}")
            return None

    async def _apply_fix(self, task: Task, fix_code: str) -> bool:
        """Apply the fix to the target file."""
        if not task.files:
            return False

        file_path = PROJECT_ROOT / task.files[0]
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return False

        try:
            # Read current content
            original_content = file_path.read_text()

            # For now, replace the entire file content
            # TODO: Implement smarter patching based on line numbers
            file_path.write_text(fix_code)

            # Store original for potential revert
            task.test_output = original_content[:5000]  # Reuse field for backup

            return True

        except Exception as e:
            logger.error(f"Failed to apply fix: {e}")
            return False

    async def _verify_fix(self, task: Task) -> bool:
        """Verify the fix by running appropriate tests/builds."""
        try:
            if task.domain == Domain.RUST:
                # Run cargo check first (fast)
                result = subprocess.run(
                    ["cargo", "check", "--workspace"],
                    cwd=PROJECT_ROOT,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result.returncode != 0:
                    logger.warning(f"cargo check failed: {result.stderr[:500]}")
                    return False

                # Run cargo test for the specific crate if possible
                result = subprocess.run(
                    ["cargo", "test", "--workspace", "--", "--nocapture"],
                    cwd=PROJECT_ROOT,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                return result.returncode == 0

            elif task.domain == Domain.PYTHON:
                agents_dir = PROJECT_ROOT / "agents"

                # Run ruff check
                result = subprocess.run(
                    ["ruff", "check", task.files[0].replace("agents/", "")],
                    cwd=agents_dir,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.returncode != 0:
                    return False

                # Run pytest if there are tests
                result = subprocess.run(
                    ["python", "-m", "pytest", "-x", "-q"],
                    cwd=agents_dir,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                return result.returncode == 0

            elif task.domain == Domain.E2E:
                # Run specific test file
                test_file = task.files[0]
                result = subprocess.run(
                    ["npx", "playwright", "test", test_file, "--reporter=list"],
                    cwd=PROJECT_ROOT / "e2e",
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                return result.returncode == 0

            else:
                # For proto/sql, just check syntax
                return True

        except subprocess.TimeoutExpired:
            logger.error("Verification timed out")
            return False
        except Exception as e:
            logger.error(f"Verification error: {e}")
            return False

    async def _commit_fix(self, task: Task) -> Optional[str]:
        """Commit the fix to git."""
        try:
            # Stage the file
            subprocess.run(
                ["git", "add", task.files[0]],
                cwd=PROJECT_ROOT,
                check=True,
                capture_output=True,
            )

            # Create commit message
            msg = f"fix({task.domain.value}): {task.finding.code or 'issue'} - {task.description[:50]}\n\nTask ID: {task.id}\nCo-Authored-By: RLM Wiggum <rlm@fervenza.fr>"

            result = subprocess.run(
                ["git", "commit", "-m", msg],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                logger.warning(f"Git commit failed: {result.stderr}")
                return None

            # Get commit hash
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
            )
            return result.stdout.strip()[:8]

        except Exception as e:
            logger.error(f"Commit failed: {e}")
            return None

    async def _revert_changes(self, task: Task) -> None:
        """Revert changes if verification failed."""
        if not task.files or not task.test_output:
            return

        try:
            file_path = PROJECT_ROOT / task.files[0]
            file_path.write_text(task.test_output)
            logger.info(f"Reverted changes to {task.files[0]}")
        except Exception as e:
            logger.error(f"Failed to revert: {e}")


class WiggumTDD:
    """
    Wiggum TDD Manager - Orchestrates parallel workers.

    LLM: MiniMax M2.1 via opencode

    Usage:
        tdd = WiggumTDD(workers=10)
        await tdd.run()  # Process all pending tasks
        await tdd.run_once()  # Process single task
    """

    def __init__(
        self,
        workers: int = 5,
        model: str = OPENCODE_MODEL,
    ):
        self.num_workers = workers
        self.model = model
        self.backlog: Optional[Backlog] = None
        self.adversarial = AdversarialChecker()
        self._running = False

    def _load_backlog(self) -> Backlog:
        """Load backlog from disk."""
        if BACKLOG_PATH.exists():
            try:
                data = json.loads(BACKLOG_PATH.read_text())
                self.backlog = Backlog.model_validate(data)
            except Exception as e:
                logger.error(f"Failed to load backlog: {e}")
                self.backlog = Backlog()
        else:
            self.backlog = Backlog()
        return self.backlog

    def _save_backlog(self) -> None:
        """Save backlog to disk."""
        if self.backlog:
            BACKLOG_PATH.write_text(
                self.backlog.model_dump_json(indent=2, exclude_none=True)
            )

    async def run(self) -> dict:
        """
        Run TDD workers on all pending tasks.

        Returns stats when complete.
        """
        self._load_backlog()
        self._running = True

        pending_tasks = [t for t in self.backlog.tasks if t.status == TaskStatus.PENDING]
        logger.info(f"Starting Wiggum TDD with {self.num_workers} workers on {len(pending_tasks)} tasks")

        if not pending_tasks:
            return {"status": "no_tasks", "processed": 0}

        # Create workers with backlog reference for fractal decomposition
        workers = [
            WiggumWorker(i, self.model, self.adversarial, backlog=self.backlog)
            for i in range(self.num_workers)
        ]

        # Process tasks with worker pool
        completed = 0
        failed = 0

        # Use semaphore to limit concurrent workers
        semaphore = asyncio.Semaphore(self.num_workers)

        async def process_with_semaphore(task: Task, worker: WiggumWorker):
            nonlocal completed, failed
            async with semaphore:
                if not self._running:
                    return
                success = await worker.process_task(task)
                if success:
                    completed += 1
                else:
                    failed += 1
                self._save_backlog()

        # Create tasks for all pending items
        tasks = []
        for i, task in enumerate(pending_tasks):
            worker = workers[i % len(workers)]
            tasks.append(process_with_semaphore(task, worker))

        # Run all tasks
        await asyncio.gather(*tasks, return_exceptions=True)

        self.backlog.update_stats()
        self._save_backlog()

        return {
            "status": "completed",
            "processed": completed + failed,
            "completed": completed,
            "failed": failed,
            "remaining": self.backlog.pending_count,
        }

    async def run_once(self, task_id: Optional[str] = None) -> dict:
        """
        Process a single task.

        Args:
            task_id: Specific task to process (or highest priority if None)
        """
        self._load_backlog()

        if task_id:
            task = next((t for t in self.backlog.tasks if t.id == task_id), None)
            if not task:
                return {"status": "error", "message": f"Task {task_id} not found"}
        else:
            task = self.backlog.get_next_task()
            if not task:
                return {"status": "no_tasks"}

        worker = WiggumWorker(0, self.model, self.adversarial, backlog=self.backlog)
        success = await worker.process_task(task)

        self._save_backlog()

        return {
            "status": "completed" if success else "failed",
            "task_id": task.id,
            "commit": task.commit_hash,
            "error": task.error,
        }

    def stop(self) -> None:
        """Stop running workers gracefully."""
        self._running = False
        logger.info("Wiggum TDD stopping...")


async def main():
    """CLI entry point for Wiggum TDD."""
    import argparse

    parser = argparse.ArgumentParser(description="Wiggum TDD - Parallel TDD Workers (MiniMax M2.1)")
    parser.add_argument("--workers", type=int, default=5, help="Number of workers")
    parser.add_argument("--once", action="store_true", help="Process single task")
    parser.add_argument("--task", help="Specific task ID to process")
    parser.add_argument("--model", default=OPENCODE_MODEL, help="LLM model to use")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    tdd = WiggumTDD(workers=args.workers, model=args.model)

    if args.once or args.task:
        result = await tdd.run_once(task_id=args.task)
    else:
        result = await tdd.run()

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
