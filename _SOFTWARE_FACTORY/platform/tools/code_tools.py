"""
Code Tools - File read/write/search operations for agents.
============================================================
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

from ..models import AgentInstance
from .registry import BaseTool


class CodeReadTool(BaseTool):
    name = "code_read"
    description = "Read the contents of a file"
    category = "code"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        path = params.get("path", "")
        if not path or not os.path.exists(path):
            return f"Error: File not found: {path}"
        try:
            max_lines = params.get("max_lines", 500)
            with open(path) as f:
                lines = f.readlines()[:max_lines]
            return "".join(lines)
        except Exception as e:
            return f"Error reading {path}: {e}"


class CodeWriteTool(BaseTool):
    name = "code_write"
    description = "Write content to a file (creates backup)"
    category = "code"
    requires_approval = True

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        path = params.get("path", "")
        content = params.get("content", "")
        if not path:
            return "Error: path required"
        try:
            p = Path(path)
            if p.exists():
                p.with_suffix(p.suffix + ".bak").write_text(p.read_text())
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            return f"Written {len(content)} chars to {path}"
        except Exception as e:
            return f"Error writing {path}: {e}"


class CodeEditTool(BaseTool):
    name = "code_edit"
    description = "Replace a string in a file"
    category = "code"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        path = params.get("path", "")
        old = params.get("old_str", "")
        new = params.get("new_str", "")
        if not path or not old:
            return "Error: path and old_str required"
        try:
            content = Path(path).read_text()
            if old not in content:
                return f"Error: old_str not found in {path}"
            if content.count(old) > 1:
                return f"Error: old_str found multiple times in {path}"
            content = content.replace(old, new, 1)
            Path(path).write_text(content)
            return f"Edited {path}"
        except Exception as e:
            return f"Error editing {path}: {e}"


class CodeSearchTool(BaseTool):
    name = "code_search"
    description = "Search for a pattern in files using ripgrep"
    category = "code"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        pattern = params.get("pattern", "")
        path = params.get("path", ".")
        glob = params.get("glob", "")
        if not pattern:
            return "Error: pattern required"
        cmd = ["rg", "--no-heading", "-n", "--max-count", "20", pattern, path]
        if glob:
            cmd.extend(["--glob", glob])
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return result.stdout[:5000] or "No matches found"
        except Exception as e:
            return f"Error: {e}"


def register_code_tools(registry):
    """Register all code tools."""
    registry.register(CodeReadTool())
    registry.register(CodeWriteTool())
    registry.register(CodeEditTool())
    registry.register(CodeSearchTool())
