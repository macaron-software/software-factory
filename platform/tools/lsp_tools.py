"""
LSP Tools — Code intelligence via Jedi + Pyright + tree-sitter
===============================================================
Provides precise symbol navigation and static analysis for codebases.
Uses jedi (pure Python) for Python semantics, pyright CLI for full type
diagnostics, and tree-sitter for multi-language structural analysis.

Python tools (Jedi):
  lsp_definition      — go-to-definition for a symbol at file:line:col
  lsp_references      — find all usages of a symbol across the project
  lsp_diagnostics     — type errors / import errors in a file
  lsp_symbols         — list all symbols in a file (classes, functions, vars)
  lsp_call_hierarchy  — incoming/outgoing call graph for a function
  lsp_rename          — preview rename refactoring (all locations)
  lsp_hover           — type info + docstring at a position

Multi-language tools (tree-sitter):
  ts_definitions      — find class/function definitions in any language
  ts_references       — find symbol usages via structural matching
  ts_symbols          — list all symbols with scope hierarchy

When to use LSP over code_search:
  - Symbol definition lookup  → lsp_definition  (exact, no grep noise)
  - All call sites of a func  → lsp_references  (structural, not textual)
  - Post-edit type checking   → lsp_diagnostics (catch errors before commit)
  - File structure overview   → lsp_symbols     (semantic, not line-scan)
  - Call graph analysis       → lsp_call_hierarchy (who calls what)
  - Safe rename preview       → lsp_rename      (all locations, no regex)
  - Quick type/doc lookup     → lsp_hover       (inline docs)
  - Non-Python code nav       → ts_definitions  (TS, JS, Rust, Go, Java...)
"""
# Ref: feat-tool-builder

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


class LspCallHierarchyTool(BaseTool):
    name = "lsp_call_hierarchy"
    description = (
        "Show call hierarchy for a Python function — who calls it (incoming) and "
        "what it calls (outgoing). "
        "Params: file (str), line (int, 1-based), column (int, 0-based), "
        "direction ('incoming'|'outgoing'|'both', default 'both'), "
        "project_root (str, optional)."
    )
    category = "code"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        file_path = params.get("file", "")
        line = int(params.get("line", 1))
        col = int(params.get("column", 0))
        direction = params.get("direction", "both")
        project_root = params.get("project_root")

        if not file_path or not Path(file_path).exists():
            return f"Error: file not found: {file_path}"
        if not _jedi_available():
            return "Error: jedi not installed — run: pip install jedi"

        try:
            script = _make_script(file_path, project_root)
            parts = []

            if direction in ("incoming", "both"):
                refs = script.get_references(line=line, column=col, include_builtins=False)
                callers = []
                for r in refs:
                    if r.type in ("statement", "expression") and r.module_path:
                        ctx = r.parent() if hasattr(r, "parent") else None
                        ctx_name = ctx.name if ctx else "?"
                        callers.append(f"  {r.module_path}:{r.line} in {ctx_name}")
                if callers:
                    parts.append(f"Incoming ({len(callers)} caller(s)):\n" + "\n".join(callers[:20]))
                else:
                    parts.append("Incoming: no callers found")

            if direction in ("outgoing", "both"):
                defs = script.goto(line=line, column=col)
                if defs:
                    target = defs[0]
                    if target.module_path and target.line:
                        callee_script = _make_script(str(target.module_path), project_root)
                        source_lines = Path(target.module_path).read_text(
                            encoding="utf-8", errors="replace"
                        ).splitlines()
                        callees = []
                        start = target.line - 1
                        indent = len(source_lines[start]) - len(source_lines[start].lstrip()) if start < len(source_lines) else 0
                        for i in range(start + 1, min(start + 100, len(source_lines))):
                            ln = source_lines[i]
                            if ln.strip() and not ln.startswith(" " * (indent + 1)) and not ln.startswith("\t" * (indent + 1)):
                                if i > start + 1:
                                    break
                            for name_obj in callee_script.get_names(all_scopes=True, references=True, definitions=False):
                                if name_obj.line == i + 1 and name_obj.type in ("function", "class"):
                                    try:
                                        call_defs = callee_script.goto(line=name_obj.line, column=name_obj.column)
                                        for cd in call_defs[:1]:
                                            loc = f"{cd.module_path}:{cd.line}" if cd.module_path else "<builtin>"
                                            callees.append(f"  {name_obj.name}() → {loc}")
                                    except Exception:
                                        callees.append(f"  {name_obj.name}()")
                        if callees:
                            seen = list(dict.fromkeys(callees))
                            parts.append(f"Outgoing ({len(seen)} call(s)):\n" + "\n".join(seen[:20]))
                        else:
                            parts.append("Outgoing: no calls detected")
                    else:
                        parts.append("Outgoing: target is builtin (no source)")
                else:
                    parts.append("Outgoing: could not resolve function")

            return "\n".join(parts) if parts else "No call hierarchy data"
        except Exception as e:
            return f"lsp_call_hierarchy error: {e}"


class LspRenameTool(BaseTool):
    name = "lsp_rename"
    description = (
        "Preview a safe rename refactoring for a Python symbol. Shows all locations "
        "that would change — does NOT apply changes (use code_edit for that). "
        "Params: file (str), line (int, 1-based), column (int, 0-based), "
        "new_name (str), project_root (str, optional)."
    )
    category = "code"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        file_path = params.get("file", "")
        line = int(params.get("line", 1))
        col = int(params.get("column", 0))
        new_name = params.get("new_name", "")
        project_root = params.get("project_root")

        if not file_path or not Path(file_path).exists():
            return f"Error: file not found: {file_path}"
        if not new_name:
            return "Error: new_name is required"
        if not _jedi_available():
            return "Error: jedi not installed — run: pip install jedi"

        try:
            script = _make_script(file_path, project_root)
            refs = script.get_references(line=line, column=col, include_builtins=False)
            if not refs:
                return "No symbol found at that position"

            old_name = refs[0].name
            by_file: dict[str, list] = {}
            for r in refs:
                fpath = str(r.module_path) if r.module_path else r.module_name
                by_file.setdefault(fpath, []).append(r.line)

            lines = [f"Rename `{old_name}` → `{new_name}` ({len(refs)} occurrence(s) in {len(by_file)} file(s)):"]
            for fpath, lnums in sorted(by_file.items()):
                lines.append(f"  {fpath}: lines {', '.join(str(l) for l in sorted(set(lnums)))}")
            lines.append("\nUse code_edit to apply each change. Check imports and string references manually.")
            return "\n".join(lines)
        except Exception as e:
            return f"lsp_rename error: {e}"


class LspHoverTool(BaseTool):
    name = "lsp_hover"
    description = (
        "Show type info and docstring for a Python symbol at a given position. "
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
            completions = script.infer(line=line, column=col)
            if not completions:
                return "No type info at that position"

            parts = []
            for c in completions[:3]:
                sig = f"{c.type} `{c.name}`"
                if c.module_path:
                    sig += f" from {c.module_path}:{c.line}"
                elif c.module_name:
                    sig += f" from {c.module_name}"
                parts.append(sig)

                desc = c.description
                if desc and desc != c.name:
                    parts.append(f"  Type: {desc}")

                try:
                    sigs = c.get_signatures()
                    for s in sigs[:1]:
                        params_str = ", ".join(
                            f"{p.name}: {p.description}" if p.description else p.name
                            for p in s.params
                        )
                        parts.append(f"  Signature: {s.name}({params_str})")
                except Exception:
                    pass

                docstring = c.docstring(raw=False)
                if docstring:
                    doc_lines = docstring.strip().splitlines()
                    preview = "\n    ".join(doc_lines[:8])
                    parts.append(f"  Doc:\n    {preview}")
                    if len(doc_lines) > 8:
                        parts.append(f"    ... ({len(doc_lines) - 8} more lines)")

            return "\n".join(parts) if parts else "No hover info"
        except Exception as e:
            return f"lsp_hover error: {e}"


# ── tree-sitter helpers ──────────────────────────────────────────────────────

# Language → file extensions mapping
_TS_LANG_MAP = {
    ".py": "python", ".pyi": "python",
    ".ts": "typescript", ".tsx": "typescript",
    ".js": "javascript", ".jsx": "javascript",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".rb": "ruby",
    ".c": "c", ".h": "c",
    ".cpp": "cpp", ".cc": "cpp", ".hpp": "cpp",
    ".cs": "c_sharp",
}


def _ts_available() -> bool:
    try:
        import tree_sitter  # noqa: F401
        return True
    except ImportError:
        return False


def _get_ts_parser(lang_name: str):
    """Get a tree-sitter parser for the given language (v0.25+ API)."""
    import tree_sitter
    import importlib
    # tree-sitter-python → tree_sitter_python, tree-sitter-c-sharp → tree_sitter_c_sharp
    mod_name = f"tree_sitter_{lang_name}"
    try:
        ts_mod = importlib.import_module(mod_name)
        language = tree_sitter.Language(ts_mod.language())
        parser = tree_sitter.Parser(language)
        return parser, language
    except (ImportError, Exception):
        return None, None


def _detect_lang(file_path: str) -> Optional[str]:
    """Detect language from file extension."""
    ext = Path(file_path).suffix.lower()
    return _TS_LANG_MAP.get(ext)


# ── tree-sitter Tools ────────────────────────────────────────────────────────


class TsDefinitionsTool(BaseTool):
    name = "ts_definitions"
    description = (
        "Find all class/function/type definitions in a file using tree-sitter. "
        "Works for Python, TypeScript, JavaScript, Rust, Go, Java, C/C++. "
        "Optional query to filter by name. "
        "Params: file (str), query (str, optional filter)."
    )
    category = "code"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        file_path = params.get("file", "")
        query_filter = params.get("query", "").lower()

        if not file_path or not Path(file_path).exists():
            return f"Error: file not found: {file_path}"
        if not _ts_available():
            return "Error: tree-sitter not installed — run: pip install tree-sitter"

        lang = _detect_lang(file_path)
        if not lang:
            return f"Error: unsupported language for {Path(file_path).suffix}"

        parser, language = _get_ts_parser(lang)
        if not parser:
            return f"Error: tree-sitter-{lang} not installed — run: pip install tree-sitter-{lang.replace('_', '-')}"

        try:
            source = Path(file_path).read_bytes()
            tree = parser.parse(source)

            results = []
            self._find_definitions(tree.root_node, query_filter, results)

            if not results:
                return f"No definitions{f' matching {query_filter!r}' if query_filter else ''} in {Path(file_path).name}"

            seen = list(dict.fromkeys(results))
            return f"{len(seen)} definition(s) in {Path(file_path).name} [{lang}]:\n" + "\n".join(seen[:80])
        except Exception as e:
            return f"ts_definitions error: {e}"

    _DEF_NODE_TYPES = {
        "function_definition", "function_declaration", "function_item",
        "method_definition", "method_declaration",
        "class_definition", "class_declaration",
        "interface_declaration", "type_alias_declaration",
        "struct_item", "enum_item", "trait_item", "impl_item",
        "type_declaration", "type_spec",
        "assignment",
    }

    def _find_definitions(self, node, query_filter: str, results: list):
        """Walk AST to find definition nodes."""
        if node.type in self._DEF_NODE_TYPES:
            name_node = node.child_by_field_name("name")
            if not name_node:
                for child in node.children:
                    if child.type in ("identifier", "type_identifier", "property_identifier", "field_identifier"):
                        name_node = child
                        break
            if name_node:
                sym_name = name_node.text.decode("utf-8", errors="replace")
                if not query_filter or query_filter in sym_name.lower():
                    line = name_node.start_point[0] + 1
                    results.append(f"  {node.type:30s}  {sym_name:40s}  line {line}")
        for child in node.children:
            self._find_definitions(child, query_filter, results)


class TsReferencesTool(BaseTool):
    name = "ts_references"
    description = (
        "Find all usages of a symbol name in a file using tree-sitter. "
        "Structural matching (identifiers only, not strings/comments). "
        "Works for any tree-sitter supported language. "
        "Params: file (str), symbol (str), scope ('file'|'directory', default 'file'), "
        "directory (str, optional — search all files in dir when scope='directory')."
    )
    category = "code"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        file_path = params.get("file", "")
        symbol = params.get("symbol", "")
        scope = params.get("scope", "file")
        directory = params.get("directory", "")

        if not symbol:
            return "Error: symbol name is required"
        if not _ts_available():
            return "Error: tree-sitter not installed — run: pip install tree-sitter"

        files_to_search = []
        if scope == "directory" and directory:
            dir_path = Path(directory)
            if not dir_path.is_dir():
                return f"Error: directory not found: {directory}"
            for ext in _TS_LANG_MAP:
                files_to_search.extend(dir_path.rglob(f"*{ext}"))
            files_to_search = [str(f) for f in files_to_search if f.is_file()][:200]
        else:
            if not file_path or not Path(file_path).exists():
                return f"Error: file not found: {file_path}"
            files_to_search = [file_path]

        all_refs = []
        for fpath in files_to_search:
            lang = _detect_lang(fpath)
            if not lang:
                continue
            parser, language = _get_ts_parser(lang)
            if not parser:
                continue
            try:
                source = Path(fpath).read_bytes()
                tree = parser.parse(source)
                self._find_identifiers(tree.root_node, symbol, fpath, all_refs)
            except Exception:
                continue

        if not all_refs:
            return f"No references to `{symbol}` found"

        lines = [f"{len(all_refs)} reference(s) to `{symbol}`:"]
        for ref in all_refs[:50]:
            lines.append(f"  {ref['file']}:{ref['line']}:{ref['col']}  ({ref['type']})")
        if len(all_refs) > 50:
            lines.append(f"  ... and {len(all_refs) - 50} more")
        return "\n".join(lines)

    def _find_identifiers(self, node, symbol: str, file_path: str, results: list):
        """Recursively find identifier nodes matching the symbol name."""
        if node.type in ("identifier", "type_identifier", "property_identifier", "field_identifier"):
            name = node.text.decode("utf-8", errors="replace")
            if name == symbol:
                results.append({
                    "file": file_path,
                    "line": node.start_point[0] + 1,
                    "col": node.start_point[1],
                    "type": node.parent.type if node.parent else "unknown",
                })
        for child in node.children:
            self._find_identifiers(child, symbol, file_path, results)


class TsSymbolsTool(BaseTool):
    name = "ts_symbols"
    description = (
        "List all symbols with scope hierarchy in any tree-sitter supported file. "
        "Works for TypeScript, JavaScript, Rust, Go, Java, Python, C/C++. "
        "Shows nesting (class → method → variable). "
        "Params: file (str), query (str, optional filter)."
    )
    category = "code"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        file_path = params.get("file", "")
        query_filter = params.get("query", "").lower()

        if not file_path or not Path(file_path).exists():
            return f"Error: file not found: {file_path}"
        if not _ts_available():
            return "Error: tree-sitter not installed — run: pip install tree-sitter"

        lang = _detect_lang(file_path)
        if not lang:
            return f"Error: unsupported language for {Path(file_path).suffix}"

        parser, language = _get_ts_parser(lang)
        if not parser:
            return f"Error: tree-sitter-{lang} not installed"

        try:
            source = Path(file_path).read_bytes()
            tree = parser.parse(source)

            symbols = []
            self._extract_symbols(tree.root_node, symbols, depth=0)

            if query_filter:
                symbols = [s for s in symbols if query_filter in s["name"].lower()]

            if not symbols:
                return f"No symbols{f' matching {query_filter!r}' if query_filter else ''} in {Path(file_path).name}"

            lines = [f"{len(symbols)} symbol(s) in {Path(file_path).name} [{lang}]:"]
            for s in symbols[:80]:
                indent = "  " * (s["depth"] + 1)
                lines.append(f"{indent}{s['type']:25s}  {s['name']:35s}  line {s['line']}")
            return "\n".join(lines)
        except Exception as e:
            return f"ts_symbols error: {e}"

    _SYMBOL_TYPES = {
        "function_definition", "function_declaration", "function_item",
        "method_definition", "method_declaration",
        "class_definition", "class_declaration",
        "interface_declaration", "type_alias_declaration",
        "struct_item", "enum_item", "trait_item", "impl_item",
        "variable_declarator", "const_declaration",
        "type_declaration", "type_spec",
    }

    def _extract_symbols(self, node, symbols: list, depth: int):
        if node.type in self._SYMBOL_TYPES:
            name = ""
            for child in node.children:
                if child.type in ("identifier", "type_identifier", "property_identifier", "field_identifier"):
                    name = child.text.decode("utf-8", errors="replace")
                    break
            if name:
                symbols.append({
                    "name": name,
                    "type": node.type,
                    "line": node.start_point[0] + 1,
                    "depth": depth,
                })
            for child in node.children:
                self._extract_symbols(child, symbols, depth + 1)
        else:
            for child in node.children:
                self._extract_symbols(child, symbols, depth)


# ── Registration ──────────────────────────────────────────────────────────────


def register_lsp_tools(registry) -> None:
    """Register all LSP tools. Called from tool_runner._get_tool_registry()."""
    # Python LSP (Jedi)
    for cls in [
        LspDefinitionTool,
        LspReferencesTool,
        LspDiagnosticsTool,
        LspSymbolsTool,
        LspCallHierarchyTool,
        LspRenameTool,
        LspHoverTool,
    ]:
        registry.register(cls())

    # Multi-language (tree-sitter) — optional
    if _ts_available():
        for cls in [TsDefinitionsTool, TsReferencesTool, TsSymbolsTool]:
            registry.register(cls())
        logger.debug("tree-sitter tools registered: ts_definitions, ts_references, ts_symbols")
    else:
        logger.debug("tree-sitter not available — multi-lang tools skipped")

    logger.debug(
        "LSP tools registered: lsp_definition, lsp_references, lsp_diagnostics, "
        "lsp_symbols, lsp_call_hierarchy, lsp_rename, lsp_hover"
    )
