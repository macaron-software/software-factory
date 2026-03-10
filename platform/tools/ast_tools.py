"""
AST Parsing Tools — Python AST analysis with regex fallback for JS/TS.
"""

from __future__ import annotations

import ast
import os
import re

from .registry import BaseTool
from ..models import AgentInstance


def _parse_python(source: str):
    """Parse Python source, return (tree, error)."""
    try:
        tree = ast.parse(source)
        return tree, None
    except SyntaxError as e:
        return None, f"SyntaxError at line {e.lineno}: {e.msg}"


def _summarize_python(tree: ast.AST) -> dict:
    classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    functions = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)]
    imports = [n for n in ast.walk(tree) if isinstance(n, ast.Import | ast.ImportFrom)]
    return {"classes": classes, "functions": functions, "import_count": len(imports)}


def _extract_python_imports(tree: ast.AST) -> list[str]:
    results: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                results.append(f"import {alias.name}" + (f" as {alias.asname}" if alias.asname else ""))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                results.append(f"from {module} import {alias.name}" + (f" as {alias.asname}" if alias.asname else ""))
    return results


def _extract_python_exports(tree: ast.AST) -> list[str]:
    exports: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            exports.append(f"class {node.name}")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            exports.append(f"function {node.name}")
    return exports


def _is_python(path: str) -> bool:
    return path.endswith(".py")


def _is_js_ts(path: str) -> bool:
    return any(path.endswith(ext) for ext in (".js", ".jsx", ".ts", ".tsx", ".mjs"))


def _js_regex_parse(source: str) -> dict:
    imports = re.findall(r'^(?:import\s+.+|const\s+\w+\s*=\s*require\(.+\));?', source, re.MULTILINE)
    exports = re.findall(r'^export\s+(?:default\s+)?(?:function|class|const|let|var)\s+(\w+)', source, re.MULTILINE)
    functions = re.findall(r'^(?:export\s+)?(?:async\s+)?function\s+(\w+)', source, re.MULTILINE)
    classes = re.findall(r'^(?:export\s+)?class\s+(\w+)', source, re.MULTILINE)
    return {"imports": imports, "exports": exports, "functions": functions, "classes": classes}


def _read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


class AstParseTool(BaseTool):
    name = "ast_parse"
    description = "Parse a Python/JS/TS file and return syntax status + summary."
    category = "analysis"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        filepath = params.get("file", "")
        if not filepath or not os.path.isfile(filepath):
            return f"Error: file not found: {filepath}"
        source = _read_file(filepath)
        if _is_python(filepath):
            tree, err = _parse_python(source)
            if err:
                return f"SYNTAX ERROR — {err}"
            info = _summarize_python(tree)
            return (f"OK — classes: {len(info['classes'])}, "
                    f"functions: {len(info['functions'])}, "
                    f"imports: {info['import_count']}")
        if _is_js_ts(filepath):
            info = _js_regex_parse(source)
            return (f"OK (regex) — classes: {len(info['classes'])}, "
                    f"functions: {len(info['functions'])}, "
                    f"imports: {len(info['imports'])}")
        return f"Unsupported file type: {filepath}"


class AstImportsTool(BaseTool):
    name = "ast_imports"
    description = "Extract all import statements from a Python/JS/TS file."
    category = "analysis"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        filepath = params.get("file", "")
        if not filepath or not os.path.isfile(filepath):
            return f"Error: file not found: {filepath}"
        source = _read_file(filepath)
        if _is_python(filepath):
            tree, err = _parse_python(source)
            if err:
                return f"Parse error: {err}"
            imports = _extract_python_imports(tree)
            return "\n".join(imports) if imports else "No imports found."
        if _is_js_ts(filepath):
            info = _js_regex_parse(source)
            return "\n".join(info["imports"]) if info["imports"] else "No imports found."
        return f"Unsupported file type: {filepath}"


class AstExportsTool(BaseTool):
    name = "ast_exports"
    description = "List public functions and classes from a Python/JS/TS file."
    category = "analysis"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        filepath = params.get("file", "")
        if not filepath or not os.path.isfile(filepath):
            return f"Error: file not found: {filepath}"
        source = _read_file(filepath)
        if _is_python(filepath):
            tree, err = _parse_python(source)
            if err:
                return f"Parse error: {err}"
            exports = _extract_python_exports(tree)
            return "\n".join(exports) if exports else "No public symbols found."
        if _is_js_ts(filepath):
            info = _js_regex_parse(source)
            return "\n".join(info["exports"]) if info["exports"] else "No exports found."
        return f"Unsupported file type: {filepath}"
