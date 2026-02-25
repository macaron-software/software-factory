"""
Code Tools - File read/write/search operations for agents.
============================================================
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

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
        # Resolve symlinks to prevent path traversal
        path = os.path.realpath(path)
        # If path is a directory, fallback to listing its contents
        if os.path.isdir(path):
            try:
                entries = sorted(os.listdir(path))[:100]
                listing = "\n".join(
                    f"{'  ' if not os.path.isdir(os.path.join(path, e)) else ''}{e}{'/' if os.path.isdir(os.path.join(path, e)) else ''}"
                    for e in entries
                )
                return f"Note: '{path}' is a directory. Contents:\n{listing}"
            except Exception as e:
                return f"Error listing directory {path}: {e}"
        try:
            max_lines = int(params.get("max_lines", 500))
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
        # Reject placeholder/slop content
        stripped = content.strip()
        if stripped in ("// your code here\n...", "// your code here", "// TODO", "..."):
            return "Error: placeholder content rejected — write real implementation code"
        if len(stripped) < 10 and not path.endswith((".env", ".gitignore", ".gitkeep")):
            return f"Error: content too short ({len(stripped)} chars) — write real code"
        # Resolve symlinks to prevent path traversal
        path = os.path.realpath(path)
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
        # Resolve symlinks to prevent path traversal
        path = os.path.realpath(path)
        try:
            content = Path(path).read_text()
            if old not in content:
                # Fuzzy fallback: normalize whitespace (trailing spaces, CRLF, indent drift)
                import re as _re
                _norm = lambda s: _re.sub(r'[ \t]+\n', '\n', s.replace('\r\n', '\n'))
                old_n, content_n = _norm(old), _norm(content)
                if old_n in content_n:
                    # Apply on normalized content
                    content = _norm(content).replace(old_n, _norm(new), 1)
                    Path(path).write_text(content)
                    return f"Edited {path} (whitespace-normalized match)"
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
