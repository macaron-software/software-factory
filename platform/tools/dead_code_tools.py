"""
Dead Code Tools — Find potentially unused Python symbols via AST analysis.
"""

from __future__ import annotations

import ast
import os

from .registry import BaseTool
from ..models import AgentInstance


def _collect_py_files(path: str) -> list[str]:
    if os.path.isfile(path) and path.endswith(".py"):
        return [path]
    files = []
    for root, _, names in os.walk(path):
        for name in names:
            if name.endswith(".py"):
                files.append(os.path.join(root, name))
    return files


def _extract_definitions(filepath: str, source: str) -> list[tuple[str, str, int]]:
    """Return list of (name, kind, lineno) for top-level public defs."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    defs = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            defs.append((node.name, "class", node.lineno))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            defs.append((node.name, "function", node.lineno))
    return defs


def _collect_all_names(source: str) -> set[str]:
    """Collect all Name nodes from a source file (references)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, (ast.ImportFrom, ast.Import)):
            for alias in node.names:
                name = alias.asname or alias.name
                names.add(name.split(".")[0])
    return names


class DeadCodeTool(BaseTool):
    name = "dead_code"
    description = "Find potentially unused functions/classes in a Python project."
    category = "analysis"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        path = params.get("path", "")
        if not path or not os.path.exists(path):
            return f"Error: path not found: {path}"

        py_files = _collect_py_files(path)
        if not py_files:
            return f"No Python files found in {path}"

        # Phase 1: collect all definitions
        all_defs: list[tuple[str, str, str, int]] = []  # (name, kind, file, line)
        sources: dict[str, str] = {}
        for fp in py_files:
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as f:
                    src = f.read()
            except OSError:
                continue
            sources[fp] = src
            for name, kind, lineno in _extract_definitions(fp, src):
                all_defs.append((name, kind, fp, lineno))

        if not all_defs:
            return "No public definitions found."

        # Phase 2: collect all references across all files
        all_refs: set[str] = set()
        for fp, src in sources.items():
            all_refs.update(_collect_all_names(src))

        # Phase 3: find defs that are never referenced in OTHER files
        unused = []
        for name, kind, filepath, lineno in all_defs:
            # Check if name appears in any file other than its definition file
            referenced = False
            for fp, src in sources.items():
                if fp == filepath:
                    continue
                if name in _collect_all_names(src):
                    referenced = True
                    break
            # Also skip if referenced in its own file beyond the def itself
            if not referenced:
                own_refs = _collect_all_names(sources[filepath])
                # Name will always appear as its own def; count occurrences in AST
                try:
                    tree = ast.parse(sources[filepath])
                except SyntaxError:
                    continue
                count = sum(1 for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == name)
                if count <= 1:
                    rel = os.path.relpath(filepath)
                    unused.append(f"  {kind} {name} — {rel}:{lineno}")

        if not unused:
            return f"No potentially unused symbols found ({len(all_defs)} definitions checked)."

        header = f"Potentially unused symbols ({len(unused)} of {len(all_defs)} definitions):"
        return header + "\n" + "\n".join(unused[:100])
