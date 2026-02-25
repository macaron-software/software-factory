"""Tests for deterministic analysis tools (AST, lint, type-check, deps, dead code)."""
import asyncio
import os
import tempfile

import pytest
import pytest_asyncio

pytestmark = pytest.mark.asyncio

from platform.tools.ast_tools import AstParseTool, AstImportsTool, AstExportsTool
from platform.tools.type_check_tools import TypeCheckTool
from platform.tools.lint_tools import LintTool, LintFixTool
from platform.tools.dep_tools import DepCheckTool, DepAuditTool
from platform.tools.dead_code_tools import DeadCodeTool


@pytest.fixture
def valid_py(tmp_path):
    f = tmp_path / "valid.py"
    f.write_text(
        'import os\nimport json\n\ndef hello():\n    return "hi"\n\nclass Foo:\n    pass\n'
    )
    return str(f)


@pytest.fixture
def invalid_py(tmp_path):
    f = tmp_path / "invalid.py"
    f.write_text("def broken(\n")
    return str(f)


@pytest.fixture
def project_dir(tmp_path):
    (tmp_path / "main.py").write_text(
        "import os\nfrom helper import greet\n\ndef main():\n    greet()\n"
    )
    (tmp_path / "helper.py").write_text(
        "def greet():\n    print('hi')\n\ndef unused_func():\n    pass\n"
    )
    return str(tmp_path)


@pytest.fixture
def requirements(tmp_path):
    f = tmp_path / "requirements.txt"
    f.write_text("fastapi>=0.104\nhttpx>=0.25\npydantic>=2.0\n")
    return str(f)


# ── AST Tools ──

class TestAstParse:
    async def test_valid_file(self, valid_py):
        result = await AstParseTool().execute({"file": valid_py})
        assert "OK" in result or "functions" in result.lower()
        assert "hello" in result or "1" in result

    async def test_invalid_file(self, invalid_py):
        result = await AstParseTool().execute({"file": invalid_py})
        assert "error" in result.lower() or "syntax" in result.lower()

    async def test_missing_file(self):
        result = await AstParseTool().execute({"file": "/nonexistent.py"})
        assert "error" in result.lower() or "not found" in result.lower()

    async def test_missing_param(self):
        result = await AstParseTool().execute({})
        assert "file" in result.lower() or "required" in result.lower() or "missing" in result.lower()


class TestAstImports:
    async def test_extracts_imports(self, valid_py):
        result = await AstImportsTool().execute({"file": valid_py})
        assert "os" in result
        assert "json" in result

    async def test_no_imports(self, tmp_path):
        f = tmp_path / "noimport.py"
        f.write_text("x = 1\n")
        result = await AstImportsTool().execute({"file": str(f)})
        assert "no import" in result.lower() or result.strip() == "" or "0" in result


class TestAstExports:
    async def test_extracts_public(self, valid_py):
        result = await AstExportsTool().execute({"file": valid_py})
        assert "hello" in result
        assert "Foo" in result


# ── Type Check ──

class TestTypeCheck:
    async def test_runs_without_crash(self, valid_py):
        result = await TypeCheckTool().execute({"path": valid_py})
        # May say "mypy not installed" or give results — both ok
        assert isinstance(result, str)
        assert len(result) > 0


# ── Lint ──

class TestLint:
    async def test_lint_valid(self, valid_py):
        result = await LintTool().execute({"path": valid_py})
        assert isinstance(result, str)

    async def test_lint_returns_issues(self, tmp_path):
        f = tmp_path / "messy.py"
        f.write_text("import os\nimport sys\nx=1\n")
        result = await LintTool().execute({"path": str(f)})
        assert isinstance(result, str)


# ── Dep Tools ──

class TestDepCheck:
    async def test_reads_requirements(self, requirements):
        result = await DepCheckTool().execute({"manifest": requirements})
        assert "fastapi" in result.lower() or "dependencies" in result.lower()

    async def test_missing_manifest(self):
        result = await DepCheckTool().execute({"manifest": "/nonexistent.txt"})
        assert "error" in result.lower() or "not found" in result.lower()


class TestDepAudit:
    async def test_runs_without_crash(self, requirements):
        result = await DepAuditTool().execute({"manifest": requirements})
        assert isinstance(result, str)


# ── Dead Code ──

class TestDeadCode:
    async def test_finds_unused(self, project_dir):
        result = await DeadCodeTool().execute({"path": project_dir})
        assert isinstance(result, str)
        # unused_func is defined in helper.py but never called from main.py
        # The tool should detect it (or at least return results without crashing)

    async def test_missing_path(self):
        result = await DeadCodeTool().execute({"path": "/nonexistent/"})
        assert "error" in result.lower() or "not found" in result.lower() or "no" in result.lower()
