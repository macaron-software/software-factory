"""
Lint Tools — Bridge to ruff, eslint, golint with auto-detection.
"""
# Ref: feat-tool-builder

from __future__ import annotations

import os
import shutil

from .registry import BaseTool
from ._helpers import run_proc as _run_base
from ..models import AgentInstance

TIMEOUT = 30

EXT_LANG = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
}

# Ruff rules: E=style, F=pyflakes, C901=complexity, S=security(bandit), B=bugbear, PERF=perf, SIM=simplify
# S rules catch: eval, exec, shell=True, pickle, weak crypto, hardcoded passwords, assert in prod, etc.
_RUFF_SELECT = "E,F,C901,S,B,PERF,SIM"
_RUFF_MAX_COMPLEXITY = "10"

LINT_CONFIG = {
    "python": {
        "bin": "ruff",
        "check": lambda p: [
            "ruff",
            "check",
            "--select",
            _RUFF_SELECT,
            "--per-file-ignores",
            "__init__.py:F401",
            "--max-doc-length",
            "120",
            p,
        ],
        "fix": lambda p: ["ruff", "check", "--fix", "--select", _RUFF_SELECT, p],
    },
    "javascript": {
        "bin": "eslint",
        "check": lambda p: ["eslint", p],
        "fix": lambda p: ["eslint", "--fix", p],
    },
    "typescript": {
        "bin": "eslint",
        "check": lambda p: ["eslint", p],
        "fix": lambda p: ["eslint", "--fix", p],
    },
    "go": {"bin": "go", "check": lambda p: ["go", "vet", "./..."], "fix": None},
    "rust": {
        "bin": "cargo",
        "check": lambda p: ["cargo", "clippy", "--", "-D", "warnings"],
        "fix": None,
    },
}


def _detect_language(path: str) -> str | None:
    if os.path.isdir(path):
        for root, _, files in os.walk(path):
            for f in files:
                ext = os.path.splitext(f)[1]
                if ext in EXT_LANG:
                    return EXT_LANG[ext]
        return None
    return EXT_LANG.get(os.path.splitext(path)[1])


async def _run(cmd: list[str], cwd: str | None = None) -> tuple[int, str]:
    return await _run_base(cmd, cwd, timeout=TIMEOUT)


class LintTool(BaseTool):
    name = "lint"
    description = "Run linter (ruff/eslint/golint) on a file or directory."
    category = "analysis"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        path = params.get("path", "")
        if not path or not os.path.exists(path):
            return f"Error: path not found: {path}"

        lang = _detect_language(path)
        if not lang:
            return f"Error: cannot detect language for {path}"

        cfg = LINT_CONFIG.get(lang)
        if not cfg:
            return f"Error: no linter configured for {lang}"

        if not shutil.which(cfg["bin"]):
            return (
                f"Error: {cfg['bin']} not installed. Install it to lint {lang} files."
            )

        code, output = await _run(cfg["check"](path))
        if code == 0:
            return "No lint issues found."

        lines = output.splitlines()
        detail = "\n".join(lines[:50])
        if len(lines) > 50:
            detail += f"\n... ({len(lines) - 50} more lines)"
        return f"Lint issues:\n{detail}"


class LintFixTool(BaseTool):
    name = "lint_fix"
    description = "Run linter with auto-fix (ruff --fix / eslint --fix)."
    category = "code"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        path = params.get("path", "")
        if not path or not os.path.exists(path):
            return f"Error: path not found: {path}"

        lang = _detect_language(path)
        if not lang:
            return f"Error: cannot detect language for {path}"

        cfg = LINT_CONFIG.get(lang)
        if not cfg:
            return f"Error: no linter configured for {lang}"

        if cfg["fix"] is None:
            return f"Error: auto-fix not supported for {lang} ({cfg['bin']})"

        if not shutil.which(cfg["bin"]):
            return (
                f"Error: {cfg['bin']} not installed. Install it to lint {lang} files."
            )

        code, output = await _run(cfg["fix"](path))
        if code == 0:
            return "Lint fix applied successfully. No remaining issues."

        lines = output.splitlines()
        detail = "\n".join(lines[:50])
        if len(lines) > 50:
            detail += f"\n... ({len(lines) - 50} more lines)"
        return f"Fix applied with remaining issues:\n{detail}"
