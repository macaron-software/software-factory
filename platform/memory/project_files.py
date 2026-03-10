"""Project Memory Loader — auto-load instruction files from project directory.

Files scanned (in order):
1. CLAUDE.md — Claude Code project instructions
2. .github/copilot-instructions.md — GitHub Copilot instructions
3. README.md — Project documentation
4. SPECS.md — Project specifications
5. VISION.md — Project vision/roadmap
6. .cursorrules — Cursor rules
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Files to auto-load from project root (ordered by priority)
MEMORY_FILES = [
    ("CLAUDE.md", "Claude Code Instructions"),
    (".github/copilot-instructions.md", "GitHub Copilot Instructions"),
    ("SPECS.md", "Project Specifications"),
    ("VISION.md", "Project Vision"),
    ("README.md", "Project README"),
    (".cursorrules", "Cursor Rules"),
    ("CONVENTIONS.md", "Project Conventions"),
]

MAX_FILE_CHARS = 3000  # Max chars per file
MAX_TOTAL_CHARS = 8000  # Max total project memory


@dataclass
class ProjectMemoryFile:
    """A loaded memory file."""
    path: str
    label: str
    content: str
    size: int = 0


@dataclass
class ProjectMemory:
    """All loaded memory files for a project."""
    project_id: str
    project_path: str
    files: list[ProjectMemoryFile] = field(default_factory=list)

    @property
    def combined(self) -> str:
        """Combine all memory files into a single string for prompt injection."""
        if not self.files:
            return ""
        parts = []
        total = 0
        for f in self.files:
            chunk = f"### {f.label} ({f.path})\n{f.content}"
            if total + len(chunk) > MAX_TOTAL_CHARS:
                remaining = MAX_TOTAL_CHARS - total
                if remaining > 200:
                    parts.append(chunk[:remaining] + "\n... (truncated)")
                break
            parts.append(chunk)
            total += len(chunk)
        return "\n\n".join(parts)


def load_project_memory(project_id: str, project_path: str) -> ProjectMemory:
    """Load all instruction/memory files from a project directory."""
    mem = ProjectMemory(project_id=project_id, project_path=project_path)

    if not project_path or not os.path.isdir(project_path):
        return mem

    for rel_path, label in MEMORY_FILES:
        full_path = os.path.join(project_path, rel_path)
        if os.path.isfile(full_path):
            try:
                with open(full_path, 'r', errors='replace') as f:
                    content = f.read(MAX_FILE_CHARS + 100)
                if len(content) > MAX_FILE_CHARS:
                    content = content[:MAX_FILE_CHARS] + "\n... (truncated)"
                mem.files.append(ProjectMemoryFile(
                    path=rel_path,
                    label=label,
                    content=content,
                    size=os.path.getsize(full_path),
                ))
                logger.debug("[Memory] Loaded %s from %s", rel_path, project_id)
            except Exception as e:
                logger.warning("[Memory] Failed to read %s: %s", full_path, e)

    logger.info("[Memory] %s: loaded %d memory files", project_id, len(mem.files))
    return mem


# Cache per project
_memory_cache: dict[str, ProjectMemory] = {}


def get_project_memory(project_id: str, project_path: str = "") -> ProjectMemory:
    """Get or load project memory (cached)."""
    if project_id in _memory_cache:
        return _memory_cache[project_id]

    if not project_path:
        from ..projects.manager import get_project_store
        proj = get_project_store().get(project_id)
        if proj:
            project_path = proj.path

    mem = load_project_memory(project_id, project_path)
    _memory_cache[project_id] = mem
    return mem


def invalidate_project_memory(project_id: str):
    """Clear cache for a project (e.g. after file edit)."""
    _memory_cache.pop(project_id, None)
