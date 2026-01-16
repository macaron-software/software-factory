"""
Software Factory Core
=====================
Core modules for the multi-project Software Factory.
"""

from core.project_registry import get_project, list_projects, ProjectConfig
from core.task_store import TaskStore, Task, TaskStatus
from core.llm_client import LLMClient, get_client
from core.adversarial import AdversarialGate, check_code
from core.fractal import FractalDecomposer, should_decompose
from core.brain import RLMBrain
from core.wiggum_tdd import WiggumPool, WiggumWorker

__all__ = [
    "get_project",
    "list_projects",
    "ProjectConfig",
    "TaskStore",
    "Task",
    "TaskStatus",
    "LLMClient",
    "get_client",
    "AdversarialGate",
    "check_code",
    "FractalDecomposer",
    "should_decompose",
    "RLMBrain",
    "WiggumPool",
    "WiggumWorker",
]
