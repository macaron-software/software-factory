"""
Type Check Tools — Bridge to mypy, tsc, go vet with auto-detection.
"""

from __future__ import annotations

import asyncio
import os
import shutil

from .registry import BaseTool
from ..models import AgentInstance

TIMEOUT = 30

LANG_MAP = {
    ".py": "python",
    ".pyi": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
}

TOOL_CONFIG = {
    "python": {"bin": "mypy", "args": lambda p: ["mypy", "--no-color-output", p]},
    "typescript": {"bin": "tsc", "args": lambda p: ["tsc", "--noEmit", "--pretty", "false", p]},
    "javascript": {"bin": "tsc", "args": lambda p: ["tsc", "--noEmit", "--allowJs", "--pretty", "false", p]},
    "go": {"bin": "go", "args": lambda p: ["go", "vet", p]},
}


def _detect_language(path: str) -> str | None:
    if os.path.isdir(path):
        for root, _, files in os.walk(path):
            for f in files:
                ext = os.path.splitext(f)[1]
                if ext in LANG_MAP:
                    return LANG_MAP[ext]
        return None
    ext = os.path.splitext(path)[1]
    return LANG_MAP.get(ext)


async def _run(cmd: list[str], cwd: str | None = None) -> tuple[int, str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT)
        output = (stdout.decode(errors="replace") + stderr.decode(errors="replace")).strip()
        return proc.returncode, output
    except FileNotFoundError:
        return -1, f"{cmd[0]}: command not found"
    except asyncio.TimeoutError:
        proc.kill()
        return -2, f"Timeout ({TIMEOUT}s) exceeded running {cmd[0]}"


class TypeCheckTool(BaseTool):
    name = "type_check"
    description = "Run type checker (mypy/tsc/go vet) on a file or directory."
    category = "analysis"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        path = params.get("path", "")
        if not path or not os.path.exists(path):
            return f"Error: path not found: {path}"

        language = params.get("language") or _detect_language(path)
        if not language:
            return f"Error: cannot detect language for {path}. Specify 'language' param."

        config = TOOL_CONFIG.get(language)
        if not config:
            return f"Error: unsupported language: {language}"

        if not shutil.which(config["bin"]):
            return f"Error: {config['bin']} not installed. Install it to use type checking for {language}."

        cmd = config["args"](path)
        code, output = await _run(cmd)

        if code == 0:
            return "No type errors found."

        lines = [l for l in output.splitlines() if l.strip()]
        error_count = len([l for l in lines if "error" in l.lower()])
        summary = f"Found {error_count} error(s):" if error_count else "Type check failed:"
        # Cap output to avoid huge responses
        detail = "\n".join(lines[:50])
        if len(lines) > 50:
            detail += f"\n... ({len(lines) - 50} more lines)"
        return f"{summary}\n{detail}"
