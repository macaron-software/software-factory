"""Factory bridge — integrates with existing Macaron Agent Platform core modules.

Allows platform agents to use Factory tools: brain, cycle, adversarial,
task_store, fractal, build_queue, etc.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Add parent directory to path for core imports
FACTORY_ROOT = Path(__file__).parents[2]
if str(FACTORY_ROOT) not in sys.path:
    sys.path.insert(0, str(FACTORY_ROOT))


class FactoryBridge:
    """Bridge between the Agent Platform and the existing Macaron Agent Platform."""

    def __init__(self):
        self._task_store = None
        self._brain = None

    # ── Task Store ──────────────────────────────────────

    def get_task_store(self):
        """Access Factory's TaskStore (SQLite)."""
        if self._task_store is None:
            try:
                from core.task_store import TaskStore
                self._task_store = TaskStore()
            except ImportError:
                logger.warning("core.task_store not available")
        return self._task_store

    def list_tasks(self, project_id: str, status: str | None = None) -> list[dict]:
        """List Factory tasks for a project."""
        store = self.get_task_store()
        if store is None:
            return []
        try:
            tasks = store.list_tasks(project_id, status=status)
            return [t.__dict__ if hasattr(t, "__dict__") else t for t in tasks]
        except Exception as exc:
            logger.error("Failed to list tasks: %s", exc)
            return []

    def create_task(self, project_id: str, task_data: dict) -> str | None:
        """Create a new Factory task."""
        store = self.get_task_store()
        if store is None:
            return None
        try:
            return store.create_task(project_id, **task_data)
        except Exception as exc:
            logger.error("Failed to create task: %s", exc)
            return None

    # ── Brain ──────────────────────────────────────────

    async def run_brain(self, project_id: str, mode: str = "all", query: str | None = None) -> dict:
        """Run the Factory Brain for analysis."""
        try:
            from core.brain import Brain
            brain = Brain(project_id)
            result = await brain.run(mode=mode, query=query)
            return {"success": True, "result": result}
        except Exception as exc:
            logger.error("Brain run failed: %s", exc)
            return {"success": False, "error": str(exc)}

    # ── Adversarial ────────────────────────────────────

    async def adversarial_review(self, code: str, filepath: str = "") -> dict:
        """Run adversarial review on code."""
        try:
            from core.adversarial import AdversarialReviewer
            reviewer = AdversarialReviewer()
            result = await reviewer.review(code, filepath=filepath)
            return {"success": True, "approved": result.approved, "feedback": result.feedback}
        except Exception as exc:
            logger.error("Adversarial review failed: %s", exc)
            return {"success": False, "error": str(exc)}

    # ── Fractal ────────────────────────────────────────

    async def fractal_decompose(self, task_description: str) -> list[dict]:
        """Decompose a task using FRACTAL (3 concerns)."""
        try:
            from core.fractal import FractalDecomposer
            decomposer = FractalDecomposer()
            subtasks = await decomposer.decompose(task_description)
            return subtasks
        except Exception as exc:
            logger.error("Fractal decomposition failed: %s", exc)
            return []

    # ── Build Queue ────────────────────────────────────

    async def enqueue_build(self, project_id: str, command: str, priority: int = 10) -> str | None:
        """Enqueue a build job in the global build queue."""
        try:
            from core.build_queue import BuildQueue
            queue = BuildQueue()
            job_id = await queue.enqueue(project_id, command, priority=priority)
            return job_id
        except Exception as exc:
            logger.error("Build enqueue failed: %s", exc)
            return None

    # ── Skills ─────────────────────────────────────────

    def load_factory_skills(self, domain: str) -> str:
        """Load existing Factory skills for a domain."""
        try:
            from core.skills import load_skills_for_task
            return load_skills_for_task(domain, "")
        except Exception as exc:
            logger.warning("Failed to load factory skills: %s", exc)
            return ""

    # ── Project Context ────────────────────────────────

    def get_project_context(self, project_id: str, category: str = "all") -> str:
        """Get project context from RAG store."""
        try:
            from core.project_context import ProjectContext
            ctx = ProjectContext(project_id)
            return ctx.get_summary(category=category)
        except Exception as exc:
            logger.warning("Failed to get project context: %s", exc)
            return ""


# Singleton
_bridge: FactoryBridge | None = None


def get_factory_bridge() -> FactoryBridge:
    global _bridge
    if _bridge is None:
        _bridge = FactoryBridge()
    return _bridge
