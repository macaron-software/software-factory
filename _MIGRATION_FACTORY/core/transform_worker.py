"""
Transform Worker - Migration execution worker

Different from SF TDD Worker:
- SF TDD: RED → GREEN → REFACTOR
- Migration Transform: PRE-VALIDATE → TRANSFORM → POST-VALIDATE → COMPARE

Workflow:
1. PRE-VALIDATE: Capture before state (golden files)
2. TRANSFORM: Apply codemod OR LLM
3. POST-VALIDATE: Capture after state
4. COMPARE: Comparative adversarial (old === new?)
5. COMMIT/ROLLBACK: If approved commit, else git reset
"""

import os
import asyncio
import subprocess
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime

from core.migration_state import MigrationState
from core.comparative_adversarial import ComparativeAdversarial, ValidationResult


class TransformWorker:
    """
    Execute migration transform tasks

    Usage:
        worker = TransformWorker('sharelook', config)
        result = await worker.execute_task(task)
        # → TransformResult(success=True, ...)
    """

    def __init__(self, project_id: str, config: Dict, mcp_client=None):
        self.project_id = project_id
        self.config = config
        self.mcp = mcp_client

        self.root_path = Path(config['migration']['root_path'])
        self.state = MigrationState(project_id)
        self.adversarial = ComparativeAdversarial(
            config.get('adversarial', {}),
            mcp_client=mcp_client
        )

    async def execute_task(self, task: Dict) -> Dict:
        """
        Execute single migration task

        Returns: {
            'success': True/False,
            'task_id': '...',
            'status': 'verified'|'rollback'|'failed',
            'details': {...}
        }
        """
        task_id = task['id']
        phase = task['phase']
        files = task['files']

        print(f"\n[Transform Worker] Starting task: {task_id}")
        print(f"  Phase: {phase}")
        print(f"  Files: {len(files)}")

        try:
            # Mark files as IN_PROGRESS
            for file_path in files:
                self.state.mark_in_progress(file_path, phase, task_id)

            # 1. PRE-VALIDATE (capture before state)
            print(f"[Transform Worker] 1. PRE-VALIDATE...")
            pre_state = await self._capture_state('legacy', task)

            # 2. TRANSFORM (codemod or LLM)
            print(f"[Transform Worker] 2. TRANSFORM...")
            if task['codemod_available']:
                transform_result = await self._run_codemod(task)
            else:
                transform_result = await self._llm_transform(task)

            if not transform_result['success']:
                return {
                    'success': False,
                    'task_id': task_id,
                    'status': 'failed',
                    'details': {'error': 'Transform failed', 'result': transform_result}
                }

            # 3. POST-VALIDATE (capture after state)
            print(f"[Transform Worker] 3. POST-VALIDATE...")
            post_state = await self._capture_state('migration', task)

            # 4. COMPARE (comparative adversarial)
            print(f"[Transform Worker] 4. COMPARE...")
            validation = await self._compare_states(pre_state, post_state, task)

            if not validation.approved:
                # ROLLBACK
                print(f"[Transform Worker] ❌ REJECTED: {validation.reason}")
                await self._rollback(task, files)

                return {
                    'success': False,
                    'task_id': task_id,
                    'status': 'rollback',
                    'details': {
                        'reason': validation.reason,
                        'layer': validation.layer,
                        'details': validation.details
                    }
                }

            # 5. COMMIT (mark verified)
            print(f"[Transform Worker] 5. COMMIT...")
            await self._commit_transform(task, files, validation)

            print(f"[Transform Worker] ✅ SUCCESS: {task_id}")

            return {
                'success': True,
                'task_id': task_id,
                'status': 'verified',
                'details': {
                    'validation': validation.layer,
                    'files_modified': len(files)
                }
            }

        except Exception as e:
            print(f"[Transform Worker] ❌ ERROR: {e}")

            # Mark files as failed (can retry)
            for file_path in files:
                self.state.rollback_file(file_path)

            return {
                'success': False,
                'task_id': task_id,
                'status': 'failed',
                'details': {'error': str(e)}
            }

    async def _capture_state(self, state_type: str, task: Dict) -> Dict:
        """
        Capture app state (before or after transform)

        Captures:
        - Build status (compiles?)
        - Tests output
        - Golden files (API, screenshots) - if configured
        - Console logs

        Returns: {
            'build_ok': True,
            'tests_pass': True,
            'golden_files': {...}
        }
        """
        state = {
            'type': state_type,  # 'legacy' or 'migration'
            'timestamp': datetime.now().isoformat(),
            'build_ok': False,
            'tests_pass': False,
            'golden_files': {}
        }

        # Build check
        try:
            build_result = await self._run_build()
            state['build_ok'] = build_result['success']
        except Exception as e:
            print(f"[Transform Worker] Build check failed: {e}")

        # Tests
        if state['build_ok']:
            try:
                test_result = await self._run_tests()
                state['tests_pass'] = test_result['success']
            except Exception as e:
                print(f"[Transform Worker] Tests failed: {e}")

        # Golden files (if enabled)
        if self.config.get('adversarial', {}).get('l0_golden_diff', {}).get('enabled', False):
            try:
                golden_files = await self._capture_golden_files(state_type)
                state['golden_files'] = golden_files
            except Exception as e:
                print(f"[Transform Worker] Golden files capture failed: {e}")

        return state

    async def _run_codemod(self, task: Dict) -> Dict:
        """
        Run jscodeshift codemod

        Example:
            jscodeshift -t codemods/angular/standalone.ts \
                src/app/auth/auth.module.ts \
                --task-id=standalone-auth-001 \
                --phase=standalone
        """
        phase = task['phase']
        files = task['files']

        # Get codemod path from breaking change
        codemod_path = None
        for change_id in task['breaking_changes']:
            change = self.adversarial.db.get_by_id(change_id)
            if change and change.codemod:
                codemod_path = change.codemod
                break

        if not codemod_path:
            return {'success': False, 'error': 'No codemod found'}

        codemod_file = Path(__file__).parent.parent / codemod_path

        if not codemod_file.exists():
            return {'success': False, 'error': f'Codemod not found: {codemod_file}'}

        # Run jscodeshift
        cmd = [
            'jscodeshift',
            '-t', str(codemod_file),
            *files,
            '--task-id', task['id'],
            '--phase', phase
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.root_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                return {
                    'success': True,
                    'stdout': stdout.decode(),
                    'stderr': stderr.decode()
                }
            else:
                return {
                    'success': False,
                    'error': stderr.decode(),
                    'returncode': proc.returncode
                }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def _llm_transform(self, task: Dict) -> Dict:
        """
        LLM-based transform (fallback if no codemod)

        Uses opencode with MCP LRM context
        """
        # TODO: Implement LLM transform
        return {'success': False, 'error': 'LLM transform not implemented yet'}

    async def _compare_states(
        self,
        pre_state: Dict,
        post_state: Dict,
        task: Dict
    ) -> ValidationResult:
        """
        Run comparative adversarial (L0+L1a+L1b+L2)

        Compares:
        - Golden files (L0)
        - Backward compat (L1a)
        - RLM exhaustiveness (L1b)
        - Breaking docs (L2)
        """
        # Prepare golden files for comparison
        golden_files = {
            'legacy': pre_state.get('golden_files', {}),
            'migration': post_state.get('golden_files', {})
        }

        # Run full adversarial cascade
        result = await self.adversarial.validate_transform(
            task=task,
            legacy_path=str(self.root_path),
            migrated_path=str(self.root_path),  # Same path (files transformed in place)
            golden_files=golden_files
        )

        return result

    async def _rollback(self, task: Dict, files: List[str]):
        """
        Rollback changes (git reset)

        Uses git to restore files to previous state
        """
        print(f"[Transform Worker] Rolling back {len(files)} files...")

        try:
            # Git checkout files
            cmd = ['git', 'checkout', 'HEAD', '--', *files]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.root_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            await proc.communicate()

            # Update state DB
            for file_path in files:
                self.state.rollback_file(file_path)

        except Exception as e:
            print(f"[Transform Worker] Rollback failed: {e}")

    async def _commit_transform(
        self,
        task: Dict,
        files: List[str],
        validation: ValidationResult
    ):
        """
        Commit transform (mark verified in DB)

        Does NOT git commit - that's done by deploy worker
        """
        task_id = task['id']
        phase = task['phase']

        # Mark files as MIGRATED
        for file_path in files:
            self.state.mark_migrated(
                file_path,
                phase,
                task_id,
                metadata={
                    'breaking_changes': task['breaking_changes'],
                    'codemod_used': task['codemod_available']
                }
            )

        # Mark as VERIFIED (adversarial approved)
        for file_path in files:
            self.state.mark_verified(
                file_path,
                verified_by=f"adversarial-{validation.layer}"
            )

        print(f"[Transform Worker] Marked {len(files)} files as VERIFIED")

    async def _run_build(self) -> Dict:
        """Run build (ng build or npm run build)"""
        # TODO: Implement build check
        return {'success': True}

    async def _run_tests(self) -> Dict:
        """Run tests"""
        # TODO: Implement tests
        return {'success': True}

    async def _capture_golden_files(self, state_type: str) -> Dict:
        """Capture golden files (API, screenshots)"""
        # TODO: Implement golden file capture
        return {}


# ===== CLI Helper =====

async def main():
    import sys
    import yaml

    if len(sys.argv) < 3:
        print("Usage: python transform_worker.py <project_id> <task_id>")
        sys.exit(1)

    project_id = sys.argv[1]
    task_id = sys.argv[2]

    # Load config
    config_path = Path(__file__).parent.parent / f"projects/{project_id}.yaml"

    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Load backlog
    from core.migration_brain import MigrationBrain

    brain = MigrationBrain(project_id)
    tasks = brain.load_backlog()

    # Find task
    task = next((t for t in tasks if t.id == task_id), None)

    if not task:
        print(f"Task not found: {task_id}")
        sys.exit(1)

    # Execute
    worker = TransformWorker(project_id, config)
    result = await worker.execute_task(task.__dict__)

    print(f"\n{'='*80}")
    print(f"Result: {result['status'].upper()}")
    print(f"{'='*80}")

    if result['success']:
        print("✅ Transform successful and verified")
    else:
        print(f"❌ Transform failed: {result['details']}")


if __name__ == "__main__":
    asyncio.run(main())
