"""
LSP Tools — Code intelligence via Jedi + Pyright
=================================================
Provides precise symbol navigation and static analysis for Python codebases.
Uses jedi (pure Python) for definition/references/symbols, pyright CLI for
full type diagnostics when available.

Tools:
  lsp_definition   — go-to-definition for a symbol at file:line:col
  lsp_references   — find all usages of a symbol across the project
  lsp_diagnostics  — type errors / import errors in a file
  lsp_symbols      — list all symbols in a file (classes, functions, vars)

When to use LSP over code_search:
  - Symbol definition lookup  → lsp_definition  (exact, no grep noise)
  - All call sites of a func  → lsp_references  (structural, not textual)
  - Post-edit type checking   → lsp_diagnostics (catch errors before commit)
  - File structure overview   → lsp_symbols     (semantic, not line-scan)
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from .registry import BaseTool
from ..models import AgentInstance

logger = logging.getLogger(__name__)


# ── Jedi helpers ─────────────────────────────────────────────────────────────


def _jedi_available() -> bool:
    try:
        import jedi  # noqa: F401

        return True
    except ImportError:
        return False


def _make_script(file_path: str, project_root: Optional[str] = None):
    """Return a jedi.Script for the given file with project context."""
    import jedi

    source = Path(file_path).read_text(encoding="utf-8", errors="replace")
    if not project_root:
        # Walk up to find project root (contains platform/ or is the repo root)
        p = Path(file_path).resolve().parent
        for _ in range(6):
            if (
                (p / "platform").is_dir()
                or (p / "pyproject.toml").exists()
                or (p / "setup.py").exists()
            ):
                project_root = str(p)
                break
            p = p.parent
        if not project_root:
            project_root = str(Path.cwd())
    project = jedi.Project(path=project_root)
    return jedi.Script(source, path=str(Path(file_path).resolve()), project=project)


def _find_bin(name: str) -> Optional[str]:
    """Find a binary in PATH or common npm/brew install locations."""
    if path := shutil.which(name):
        return path
    for prefix in [
        Path.home() / ".npm-global" / "bin",
        Path("/usr/local/bin"),
        Path("/opt/homebrew/bin"),
    ]:
        p = prefix / name
        if p.exists():
            return str(p)
    return None


# ── Tools ─────────────────────────────────────────────────────────────────────


class LspDefinitionTool(BaseTool):
    name = "lsp_definition"
    description = (
        "Go-to-definition for a Python symbol. Returns the exact file and line "
        "where the symbol is defined — no grep noise. "
        "Params: file (str), line (int, 1-based), column (int, 0-based), "
        "project_root (str, optional)."
    )
    category = "code"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        file_path = params.get("file", "")
        line = int(params.get("line", 1))
        col = int(params.get("column", 0))
        project_root = params.get("project_root")

        if not file_path or not Path(file_path).exists():
            return f"Error: file not found: {file_path}"
        if not _jedi_available():
            return "Error: jedi not installed — run: pip install jedi"

        try:
            script = _make_script(file_path, project_root)
            defs = script.goto(line=line, column=col, follow_imports=True)
            if not defs:
                return "No definition found"
            results = []
            for d in defs[:5]:
                if d.module_path:
                    results.append(f"{d.type} `{d.name}` → {d.module_path}:{d.line}")
                else:
                    results.append(f"{d.type} `{d.name}` → <builtin>")
            return "\n".join(results)
        except Exception as e:
            return f"lsp_definition error: {e}"


class LspReferencesTool(BaseTool):
    name = "lsp_references"
    description = (
        "Find all usages of a Python symbol across the entire project. "
        "Returns exact file:line:col for each reference — structural, not textual. "
        "Params: file (str), line (int, 1-based), column (int, 0-based), "
        "project_root (str, optional)."
    )
    category = "code"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        file_path = params.get("file", "")
        line = int(params.get("line", 1))
        col = int(params.get("column", 0))
        project_root = params.get("project_root")

        if not file_path or not Path(file_path).exists():
            return f"Error: file not found: {file_path}"
        if not _jedi_available():
            return "Error: jedi not installed — run: pip install jedi"

        try:
            script = _make_script(file_path, project_root)
            refs = script.get_references(line=line, column=col, include_builtins=False)
            # If column pointed to a keyword (def/class/import) rather than the name,
            # walk forward on the line to find the actual identifier
            if not refs or len(refs) <= 1:
                source_lines = (
                    Path(file_path)
                    .read_text(encoding="utf-8", errors="replace")
                    .splitlines()
                )
                if 1 <= line <= len(source_lines):
                    line_text = source_lines[line - 1]
                    for try_col in range(col, min(col + 20, len(line_text))):
                        if (
                            line_text[try_col : try_col + 1].isalpha()
                            or line_text[try_col : try_col + 1] == "_"
                        ):
                            try_refs = script.get_references(
                                line=line, column=try_col, include_builtins=False
                            )
                            if len(try_refs) > len(refs):
                                refs = try_refs
                                break
            if not refs:
                return "No references found"
            lines = []
            for r in refs[:40]:
                mod = str(r.module_path) if r.module_path else r.module_name
                lines.append(f"  {mod}:{r.line}:{r.column}  ({r.type})")
            total = len(refs)
            shown = min(total, 40)
            header = (
                f"{total} reference(s){' (showing first 40)' if total > 40 else ''}:"
            )
            return header + "\n" + "\n".join(lines[:shown])
        except Exception as e:
            return f"lsp_references error: {e}"


class LspDiagnosticsTool(BaseTool):
    name = "lsp_diagnostics"
    description = (
        "Run type/import checks on a Python file. Uses pyright if installed "
        "(full type checking), otherwise jedi for syntax errors only. "
        "Call after editing a file to catch errors before commit. "
        "Params: file (str), project_root (str, optional)."
    )
    category = "code"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        file_path = params.get("file", "")
        project_root = params.get("project_root") or (
            str(Path(file_path).parent) if file_path else "."
        )

        if not file_path or not Path(file_path).exists():
            return f"Error: file not found: {file_path}"

        pyright = _find_bin("pyright")
        if pyright:
            return await self._pyright(pyright, file_path, project_root)
        if _jedi_available():
            return await self._jedi_syntax(file_path, project_root)
        return (
            "No diagnostic backend available. "
            "Install pyright (npm i -g pyright) for full type checking."
        )

    async def _pyright(self, binary: str, file_path: str, cwd: str) -> str:
        try:
            result = subprocess.run(
                [binary, "--outputjson", file_path],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=cwd,
            )
            data = json.loads(result.stdout)
            diags = data.get("generalDiagnostics", [])
            if not diags:
                return "✓ No errors (pyright)"
            lines = []
            for d in diags[:25]:
                sev = d.get("severity", "error")
                msg = d.get("message", "")
                ln = d.get("range", {}).get("start", {}).get("line", 0) + 1
                lines.append(f"  [{sev}] line {ln}: {msg}")
            return f"{len(diags)} diagnostic(s) (pyright):\n" + "\n".join(lines)
        except json.JSONDecodeError:
            # pyright returned non-JSON (e.g. plain text error)
            return result.stdout[:2000] or result.stderr[:500] or "pyright: no output"
        except Exception as e:
            return f"pyright error: {e}"

    async def _jedi_syntax(self, file_path: str, project_root: str) -> str:
        try:
            script = _make_script(file_path, project_root)
            errors = script.get_syntax_errors()
            if not errors:
                return (
                    "✓ No syntax errors (jedi — install pyright for full type checking)"
                )
            lines = [f"  [error] line {e.line}: {e.get_message()}" for e in errors]
            return f"{len(errors)} syntax error(s) (jedi):\n" + "\n".join(lines)
        except Exception as e:
            return f"jedi diagnostics error: {e}"


class LspSymbolsTool(BaseTool):
    name = "lsp_symbols"
    description = (
        "List all symbols (classes, functions, variables) defined in a Python file. "
        "Optional query string to filter by name. "
        "Params: file (str), query (str, optional filter), "
        "project_root (str, optional)."
    )
    category = "code"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        file_path = params.get("file", "")
        query = params.get("query", "").lower()
        project_root = params.get("project_root")

        if not file_path or not Path(file_path).exists():
            return f"Error: file not found: {file_path}"
        if not _jedi_available():
            return "Error: jedi not installed — run: pip install jedi"

        try:
            script = _make_script(file_path, project_root)
            names = script.get_names(
                all_scopes=True, definitions=True, references=False
            )
            results = []
            for s in names:
                if query and query not in s.name.lower():
                    continue
                results.append(f"  {s.type:12s}  {s.name:40s}  line {s.line}")
            if not results:
                return f"No symbols{f' matching {query!r}' if query else ''} in {Path(file_path).name}"
            header = f"{len(results)} symbol(s) in {Path(file_path).name}"
            if query:
                header += f" (filter: {query!r})"
            return header + ":\n" + "\n".join(results[:60])
        except Exception as e:
            return f"lsp_symbols error: {e}"


# ── Registration ──────────────────────────────────────────────────────────────


def register_lsp_tools(registry) -> None:
    """Register all LSP tools. Called from tool_runner._get_tool_registry()."""
    for cls in [
        LspDefinitionTool,
        LspReferencesTool,
        LspDiagnosticsTool,
        LspSymbolsTool,
    ]:
        registry.register(cls())
    logger.debug(
        "LSP tools registered: lsp_definition, lsp_references, lsp_diagnostics, lsp_symbols"
    )
