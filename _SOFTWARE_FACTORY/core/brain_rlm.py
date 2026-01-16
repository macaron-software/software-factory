#!/usr/bin/env python3
"""
RLM Brain - Recursive Language Model based Brain
=================================================
Based on MIT CSAIL arXiv:2512.24601 "Recursive Language Models"

The Brain uses RLM to "see" the ENTIRE project codebase, even if it
exceeds the model's context window. RLM treats the codebase as an
external environment that the LLM can programmatically examine,
decompose, and recursively call itself over.

Key difference from regular LLM:
- llm.completion(prompt) → limited by context window
- rlm.completion(prompt) → can handle entire codebase via REPL

Architecture:
┌─────────────────────────────────────────────────────────────────┐
│  BRAIN (Claude via RLM)                                         │
│  └── RLM loads ENTIRE project as context                        │
│  └── LLM can execute code to examine files                      │
│  └── LLM can call llm_query() for deep analysis                 │
│  └── Generates BACKLOG of tasks                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                    backlog_tasks.json
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  WIGGUM TDD (separate workers, NOT RLM)                         │
│  └── Takes tasks from backlog                                   │
│  └── Implements via MiniMax M2.1                                │
└─────────────────────────────────────────────────────────────────┘

Usage:
    from core.brain_rlm import RLMBrain

    brain = RLMBrain("ppz")
    tasks = await brain.run(vision_prompt="Focus on mobile features")
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Add RLM to path
sys.path.insert(0, str(Path(__file__).parent.parent / "_rlm"))

from rlm import RLM
from rlm.logger import RLMLogger

from core.project_registry import get_project, ProjectConfig
from core.task_store import TaskStore, Task


def log(msg: str, level: str = "INFO"):
    """Log with timestamp"""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [BRAIN-RLM] [{level}] {msg}", flush=True)


# ============================================================================
# FILE COLLECTOR
# ============================================================================

def collect_project_files(project: ProjectConfig, max_chars: int = 500000) -> str:
    """
    Collect all project files as a single context string.

    This becomes the RLM context that the LLM can programmatically examine.
    """
    files_content = []
    total_chars = 0

    # Patterns to exclude
    exclude_patterns = {
        '.git', 'node_modules', 'target', '__pycache__', '.pyc',
        'dist', 'build', '.next', '.svelte-kit', 'coverage',
        '.DS_Store', '.env', 'Thumbs.db', '*.lock', 'package-lock.json'
    }

    def should_exclude(path: Path) -> bool:
        for pattern in exclude_patterns:
            if pattern in str(path):
                return True
        return False

    # Collect files from each domain
    for domain_name, domain_config in project.domains.items():
        paths = domain_config.get("paths", [])
        extensions = domain_config.get("extensions", [])

        for path_str in paths:
            domain_path = project.root_path / path_str
            if not domain_path.exists():
                continue

            for ext in extensions:
                for file in domain_path.rglob(f"*{ext}"):
                    if should_exclude(file):
                        continue

                    try:
                        content = file.read_text(errors='ignore')
                        rel_path = str(file.relative_to(project.root_path))

                        # Limit per file
                        if len(content) > 10000:
                            content = content[:10000] + "\n... [truncated]"

                        file_entry = f"\n{'='*60}\nFILE: {rel_path}\n{'='*60}\n{content}\n"

                        if total_chars + len(file_entry) > max_chars:
                            break

                        files_content.append(file_entry)
                        total_chars += len(file_entry)

                    except Exception as e:
                        continue

    log(f"Collected {len(files_content)} files ({total_chars} chars)")
    return "".join(files_content)


# ============================================================================
# RLM BRAIN
# ============================================================================

class RLMBrain:
    """
    Brain powered by Recursive Language Models (MIT CSAIL).

    Uses RLM to handle the entire project codebase as context,
    allowing the LLM to programmatically examine and analyze
    files beyond its normal context window.
    """

    def __init__(self, project_name: str = None):
        """
        Initialize RLM Brain for a project.

        Args:
            project_name: Project name from projects/*.yaml
        """
        self.project = get_project(project_name)
        self.task_store = TaskStore()

        # Initialize RLM with Anthropic backend (Claude)
        self.rlm = RLM(
            backend="anthropic",
            backend_kwargs={
                "model_name": "claude-opus-4-5-20251101",
            },
            environment="local",  # Use local REPL
            max_iterations=30,
            max_depth=1,  # Allow one level of recursive sub-calls
            verbose=True,
            logger=RLMLogger(
                log_dir=str(Path(__file__).parent.parent / "data" / "rlm_logs")
            ),
        )

        log(f"RLM Brain initialized for project: {self.project.name}")
        log(f"Root: {self.project.root_path}")
        log(f"Domains: {list(self.project.domains.keys())}")

    async def run(
        self,
        vision_prompt: str = None,
        domains: List[str] = None,
    ) -> List[Task]:
        """
        Run RLM Brain analysis.

        The Brain:
        1. Loads the entire project as RLM context
        2. Uses RLM to analyze (LLM can examine files programmatically)
        3. Generates a prioritized backlog of tasks

        Args:
            vision_prompt: Optional focus prompt for analysis
            domains: Specific domains to analyze (default: all)

        Returns:
            List of created Task objects
        """
        log("=" * 60)
        log("Starting RLM Brain analysis")
        log("=" * 60)

        # 1. Load vision document
        vision_content = self.project.get_vision_content() or ""
        log(f"Vision doc: {len(vision_content)} chars")

        # 2. Collect project files as RLM context
        log("Collecting project files for RLM context...")
        project_context = collect_project_files(self.project)

        # 3. Build RLM prompt
        prompt = self._build_rlm_prompt(
            vision_content,
            project_context,
            vision_prompt,
            domains,
        )

        # 4. Run RLM completion (this is where the magic happens)
        log("Running RLM completion (LLM can programmatically examine codebase)...")
        try:
            result = self.rlm.completion(prompt)
            response = result.response
            log(f"RLM completed in {result.execution_time:.1f}s")
            log(f"Response: {len(response)} chars")
        except Exception as e:
            log(f"RLM error: {e}", "ERROR")
            return []

        # 5. Parse tasks from RLM response
        tasks = self._parse_tasks(response)
        log(f"Parsed {len(tasks)} tasks from RLM response")

        # 6. Save tasks to store
        created_tasks = []
        for idx, task_dict in enumerate(tasks):
            try:
                task_id = f"{self.project.name}-rlm-{idx:04d}"
                task_obj = Task(
                    id=task_id,
                    project_id=self.project.id,
                    type=task_dict.get("type", "fix"),
                    domain=task_dict.get("domain", "unknown"),
                    description=task_dict.get("description", ""),
                    files=task_dict.get("files", []),
                    context=task_dict,
                    wsjf_score=task_dict.get("wsjf_score", 5.0),
                )
                self.task_store.create_task(task_obj)
                created_tasks.append(task_obj)
            except Exception as e:
                log(f"Failed to create task: {e}", "ERROR")

        log(f"Created {len(created_tasks)} tasks in store")
        log("=" * 60)
        log("RLM Brain analysis complete")
        log("=" * 60)

        return created_tasks

    def _build_rlm_prompt(
        self,
        vision: str,
        project_context: str,
        focus: str = None,
        domains: List[str] = None,
    ) -> str:
        """Build the RLM prompt with project context."""

        domains_list = domains or list(self.project.domains.keys())

        return f"""You are an RLM (Recursive Language Model) Brain analyzing a software project.

PROJECT: {self.project.name} ({self.project.display_name})
DOMAINS: {domains_list}

VISION DOCUMENT:
{vision[:5000] if vision else "No vision document available"}

{f"FOCUS: {focus}" if focus else ""}

PROJECT CODEBASE:
The following is the project codebase. You can programmatically examine it.
You have access to Python code execution to analyze patterns, search for issues, etc.

{project_context}

YOUR TASK:
Analyze this codebase and generate a backlog of actionable tasks.

For each issue found, create a task with:
1. type: fix|feature|refactor|test|security
2. domain: {domains_list}
3. description: Clear, specific description
4. files: List of files to modify
5. severity: critical|high|medium|low
6. wsjf_score: Priority score (higher = more important)

You can use Python code blocks to:
- Count patterns (e.g., TODO comments, .unwrap() calls)
- Search for security issues
- Analyze code structure
- Call llm_query() for deeper analysis of specific files

OUTPUT FORMAT:
Return a JSON array of tasks at the end:
```json
[
  {{"type": "fix", "domain": "rust", "description": "...", "files": ["..."], "severity": "high", "wsjf_score": 8.5}},
  ...
]
```

Begin your analysis. Use code blocks to examine the codebase programmatically."""

    def _parse_tasks(self, response: str) -> List[Dict]:
        """Parse tasks from RLM response."""
        import re

        try:
            # Find JSON array in response
            match = re.search(r'```json\s*(\[.*?\])\s*```', response, re.DOTALL)
            if match:
                tasks = json.loads(match.group(1))
                return [t for t in tasks if isinstance(t, dict) and "description" in t]

            # Try finding raw JSON array
            match = re.search(r'\[\s*\{.*?"description".*?\}\s*\]', response, re.DOTALL)
            if match:
                return json.loads(match.group())

        except json.JSONDecodeError as e:
            log(f"JSON parse error: {e}", "WARN")

        return []

    def get_status(self) -> Dict:
        """Get current brain status."""
        tasks = self.task_store.get_tasks_by_project(self.project.id)
        status_counts = {}
        for task in tasks:
            status = task.status
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "project": self.project.name,
            "total_tasks": len(tasks),
            "by_status": status_counts,
        }

    def close(self):
        """Clean up RLM resources."""
        self.rlm.close()


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="RLM Brain - Project Analyzer")
    parser.add_argument("--project", "-p", help="Project name")
    parser.add_argument("--focus", "-f", help="Focus prompt")
    parser.add_argument("--domain", "-d", help="Specific domain")
    parser.add_argument("--status", action="store_true", help="Show status only")

    args = parser.parse_args()

    brain = RLMBrain(args.project)

    if args.status:
        status = brain.get_status()
        print(json.dumps(status, indent=2))
        return

    domains = [args.domain] if args.domain else None

    tasks = asyncio.run(brain.run(
        vision_prompt=args.focus,
        domains=domains,
    ))

    print(f"\nCreated {len(tasks)} tasks")
    for task in tasks[:10]:
        print(f"  - [{task.domain}] {task.description[:60]}...")

    brain.close()


if __name__ == "__main__":
    main()
