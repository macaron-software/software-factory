#!/usr/bin/env python3
"""
Brain with MCP LRM - Uses Claude + MCP tools to explore project
================================================================
Adaptation of MIT CSAIL RLM where REPL is replaced by MCP tools.

Instead of a Python REPL, the Brain uses MCP tools to:
- lrm_locate: Find files in project
- lrm_summarize: Summarize files content
- lrm_conventions: Get domain conventions
- lrm_build: Run build/test commands

Architecture:
┌─────────────────────────────────────────────────────────────────┐
│  BRAIN (Claude + MCP LRM tools)                                 │
│  └── Claude calls MCP tools to explore project                  │
│  └── Can "see" entire project via tool calls                    │
│  └── Generates BACKLOG of tasks                                 │
└─────────────────────────────────────────────────────────────────┘

Usage:
    from core.brain_mcp import MCPBrain

    brain = MCPBrain("ppz")
    tasks = await brain.run(focus="mobile features")
"""

import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.project_registry import get_project, ProjectConfig
from core.task_store import TaskStore, Task


def log(msg: str, level: str = "INFO"):
    """Log with timestamp"""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [BRAIN-MCP] [{level}] {msg}", flush=True)


class MCPBrain:
    """
    Brain that uses Claude + MCP LRM tools to analyze project.

    The MCP server provides tools that let Claude explore the entire
    project without loading everything into context.
    """

    def __init__(self, project_name: str = None):
        """
        Initialize MCP Brain.

        Args:
            project_name: Project name from projects/*.yaml
        """
        self.project = get_project(project_name)
        self.task_store = TaskStore()
        self.mcp_server_path = Path(__file__).parent.parent / "mcp_lrm" / "server.py"

        log(f"MCP Brain initialized for project: {self.project.name}")
        log(f"Root: {self.project.root_path}")
        log(f"Domains: {list(self.project.domains.keys())}")

    async def run(
        self,
        focus: str = None,
        domains: List[str] = None,
    ) -> List[Task]:
        """
        Run MCP Brain analysis.

        Uses Claude with MCP LRM tools to explore and analyze the project.

        Args:
            focus: Optional focus prompt
            domains: Specific domains to analyze

        Returns:
            List of created Task objects
        """
        log("=" * 60)
        log("Starting MCP Brain analysis")
        log("=" * 60)

        # Load vision document
        vision_content = self.project.get_vision_content() or ""
        log(f"Vision doc: {len(vision_content)} chars")

        # Build prompt for Claude
        prompt = self._build_prompt(vision_content, focus, domains)

        # Run Claude with MCP tools
        log("Running Claude with MCP LRM tools...")
        response = await self._run_claude_with_mcp(prompt)

        if not response:
            log("Claude returned empty response", "ERROR")
            return []

        log(f"Response: {len(response)} chars")

        # Parse tasks from response
        tasks = self._parse_tasks(response)
        log(f"Parsed {len(tasks)} tasks")

        # Save to store
        created_tasks = self._save_tasks(tasks)
        log(f"Created {len(created_tasks)} tasks in store")

        log("=" * 60)
        log("MCP Brain analysis complete")
        log("=" * 60)

        return created_tasks

    def _build_prompt(
        self,
        vision: str,
        focus: str = None,
        domains: List[str] = None,
    ) -> str:
        """Build prompt for Claude with MCP tools."""

        domains_list = domains or list(self.project.domains.keys())

        return f"""You are an RLM Brain (MIT CSAIL) analyzing a software project.

PROJECT: {self.project.name} ({self.project.display_name})
ROOT: {self.project.root_path}
DOMAINS: {domains_list}

VISION DOCUMENT:
{vision[:8000] if vision else "No vision document"}

{f"FOCUS: {focus}" if focus else ""}

You have access to MCP tools to explore the project:
- lrm_locate(query, scope, limit): Find files matching pattern
- lrm_summarize(files, goal): Get file summaries
- lrm_conventions(domain): Get coding conventions
- lrm_build(domain, command): Run build/test/lint

YOUR TASK:
1. Use lrm_locate to find files across domains
2. Use lrm_summarize to understand code structure
3. Use lrm_build to identify build errors
4. Generate a backlog of actionable tasks

For each issue, create a task with:
- type: fix|feature|refactor|test|security
- domain: {domains_list}
- description: Clear description
- files: Files to modify
- severity: critical|high|medium|low
- wsjf_score: Priority (1-10, higher = more important)

OUTPUT at the end as JSON:
```json
[
  {{"type": "fix", "domain": "rust", "description": "...", "files": ["..."], "severity": "high", "wsjf_score": 8.5}}
]
```

Begin by exploring the project structure with lrm_locate."""

    async def _run_claude_with_mcp(self, prompt: str) -> str:
        """
        Run Claude CLI with MCP LRM server.

        Uses claude --mcp-config to enable MCP tools.
        """
        # Create MCP config file for this session
        mcp_config = {
            "mcpServers": {
                "lrm": {
                    "command": "python3",
                    "args": [str(self.mcp_server_path), "-p", self.project.name],
                    "env": {
                        "FACTORY_PROJECT": self.project.name,
                    }
                }
            }
        }

        config_path = Path(__file__).parent.parent / "data" / "mcp_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(mcp_config, indent=2))

        try:
            log("Starting Claude with MCP config...")
            proc = await asyncio.create_subprocess_exec(
                "claude",
                "-p",  # Print mode
                "--model", "claude-opus-4-5-20251101",
                "--mcp-config", str(config_path),
                "--max-turns", "20",
                "--dangerously-skip-permissions",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.project.root_path),
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=prompt.encode()),
                timeout=900,  # 15 min timeout
            )

            if proc.returncode != 0:
                log(f"Claude error: {stderr.decode()[:500]}", "ERROR")
                return ""

            return stdout.decode()

        except asyncio.TimeoutError:
            log("Claude timeout (15min)", "ERROR")
            return ""
        except FileNotFoundError:
            log("claude CLI not found", "ERROR")
            return ""
        except Exception as e:
            log(f"Claude exception: {e}", "ERROR")
            return ""

    def _parse_tasks(self, response: str) -> List[Dict]:
        """Parse tasks from Claude response."""
        import re

        try:
            # Find JSON array
            match = re.search(r'```json\s*(\[.*?\])\s*```', response, re.DOTALL)
            if match:
                return json.loads(match.group(1))

            # Try raw JSON
            match = re.search(r'\[\s*\{.*?"description".*?\}\s*\]', response, re.DOTALL)
            if match:
                return json.loads(match.group())

        except json.JSONDecodeError as e:
            log(f"JSON parse error: {e}", "WARN")

        return []

    def _save_tasks(self, tasks: List[Dict]) -> List[Task]:
        """Save tasks to store."""
        created = []

        for idx, task_dict in enumerate(tasks):
            try:
                task_id = f"{self.project.name}-mcp-{idx:04d}"
                task_obj = Task(
                    id=task_id,
                    project_id=self.project.id,
                    type=task_dict.get("type", "fix"),
                    domain=task_dict.get("domain", "unknown"),
                    description=task_dict.get("description", ""),
                    files=task_dict.get("files", []),
                    context=task_dict,
                    wsjf_score=float(task_dict.get("wsjf_score", 5.0)),
                )
                self.task_store.create_task(task_obj)
                created.append(task_obj)
            except Exception as e:
                log(f"Failed to create task: {e}", "ERROR")

        return created

    def get_status(self) -> Dict:
        """Get brain status."""
        tasks = self.task_store.get_tasks_by_project(self.project.id)
        by_status = {}
        for t in tasks:
            by_status[t.status] = by_status.get(t.status, 0) + 1

        return {
            "project": self.project.name,
            "total_tasks": len(tasks),
            "by_status": by_status,
        }


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="MCP Brain")
    parser.add_argument("--project", "-p", help="Project name")
    parser.add_argument("--focus", "-f", help="Focus prompt")
    parser.add_argument("--domain", "-d", help="Domain")
    parser.add_argument("--status", action="store_true", help="Show status")

    args = parser.parse_args()

    brain = MCPBrain(args.project)

    if args.status:
        print(json.dumps(brain.get_status(), indent=2))
        return

    domains = [args.domain] if args.domain else None
    tasks = asyncio.run(brain.run(focus=args.focus, domains=domains))

    print(f"\nCreated {len(tasks)} tasks")
    for task in tasks[:10]:
        print(f"  - [{task.domain}] {task.description[:60]}...")


if __name__ == "__main__":
    main()
