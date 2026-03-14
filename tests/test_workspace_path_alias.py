"""
Unit tests for _resolve_file_path() — workspace path aliasing.

Agents see their workspace as /workspace (or relative paths).
These tests verify every path pattern is correctly resolved — including
attempts to escape the sandbox via other project paths, real system paths, etc.

Run: pytest tests/test_workspace_path_alias.py -v
"""
# Ref: feat-workspaces
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from platform.agents.tool_runner import _resolve_file_path

WS = "/app/data/workspaces/ac-hello-vue"
OTHER_WS = "/app/data/workspaces/ac-ecommerce"


# ---------------------------------------------------------------------------
# /workspace alias
# ---------------------------------------------------------------------------

class TestWorkspaceAlias:
    """/workspace  →  project_path"""

    def test_workspace_root(self):
        assert _resolve_file_path("/workspace", WS) == WS

    def test_workspace_root_trailing_slash(self):
        assert _resolve_file_path("/workspace/", WS) == WS

    def test_workspace_file(self):
        assert _resolve_file_path("/workspace/src/main.py", WS) == f"{WS}/src/main.py"

    def test_workspace_nested(self):
        assert _resolve_file_path("/workspace/src/components/App.vue", WS) == \
            f"{WS}/src/components/App.vue"

    def test_workspace_inception_md(self):
        assert _resolve_file_path("/workspace/INCEPTION.md", WS) == f"{WS}/INCEPTION.md"

    def test_workspace_dockerfile(self):
        assert _resolve_file_path("/workspace/Dockerfile", WS) == f"{WS}/Dockerfile"


# ---------------------------------------------------------------------------
# Empty / dot  →  project root
# ---------------------------------------------------------------------------

class TestEmptyAndDot:
    def test_empty_string(self):
        assert _resolve_file_path("", WS) == WS

    def test_dot(self):
        assert _resolve_file_path(".", WS) == WS

    def test_no_project_path_returns_empty(self):
        assert _resolve_file_path("", None) == ""

    def test_no_project_path_returns_path_unchanged(self):
        assert _resolve_file_path("/workspace/src/main.py", None) == "/workspace/src/main.py"


# ---------------------------------------------------------------------------
# Already-correct absolute paths (inside workspace)
# ---------------------------------------------------------------------------

class TestCorrectAbsolutePaths:
    def test_exact_project_path(self):
        assert _resolve_file_path(WS, WS) == WS

    def test_file_under_project_path(self):
        p = f"{WS}/src/main.py"
        assert _resolve_file_path(p, WS) == p

    def test_nested_file_under_project_path(self):
        p = f"{WS}/src/components/Button.vue"
        assert _resolve_file_path(p, WS) == p


# ---------------------------------------------------------------------------
# Relative paths  →  joined with project_path
# ---------------------------------------------------------------------------

class TestRelativePaths:
    def test_simple_filename(self):
        assert _resolve_file_path("INCEPTION.md", WS) == f"{WS}/INCEPTION.md"

    def test_nested_relative(self):
        assert _resolve_file_path("src/main.py", WS) == f"{WS}/src/main.py"

    def test_relative_with_ws_id_prefix(self):
        # Agent may prefix path with workspace ID (common MiniMax pattern)
        assert _resolve_file_path("ac-hello-vue/src/main.py", WS) == f"{WS}/src/main.py"

    def test_relative_without_leading_slash(self):
        assert _resolve_file_path("Dockerfile", WS) == f"{WS}/Dockerfile"


# ---------------------------------------------------------------------------
# OTHER project paths  →  NOT remapped (kept as-is)
# ---------------------------------------------------------------------------

class TestOtherProjectPaths:
    """Paths that belong to another project must NOT be silently redirected."""

    def test_other_workspace_root(self):
        # Should be returned unchanged — it's an allowed workspace, just not ours
        assert _resolve_file_path(OTHER_WS, WS) == OTHER_WS

    def test_other_workspace_file(self):
        p = f"{OTHER_WS}/src/index.ts"
        assert _resolve_file_path(p, WS) == p

    def test_other_workspace_inception(self):
        p = f"{OTHER_WS}/INCEPTION.md"
        assert _resolve_file_path(p, WS) == p


# ---------------------------------------------------------------------------
# System / dangerous paths  →  NOT remapped (kept as-is, blocked by code_tools)
# ---------------------------------------------------------------------------

class TestSystemPaths:
    """
    _resolve_file_path does NOT sandbox — system paths pass through unchanged.
    The security boundary is in code_tools._is_path_allowed(), not here.
    These tests document the expected behavior and ensure we don't accidentally
    remap system paths INTO the workspace.
    """

    def test_etc_passwd(self):
        assert _resolve_file_path("/etc/passwd", WS) == "/etc/passwd"

    def test_etc_shadow(self):
        assert _resolve_file_path("/etc/shadow", WS) == "/etc/shadow"

    def test_root_home(self):
        assert _resolve_file_path("/root/.ssh/id_rsa", WS) == "/root/.ssh/id_rsa"

    def test_proc_self(self):
        assert _resolve_file_path("/proc/self/environ", WS) == "/proc/self/environ"

    def test_tmp_file(self):
        # /tmp is allowed by code_tools but not the workspace alias — pass through
        assert _resolve_file_path("/tmp/scratch.py", WS) == "/tmp/scratch.py"

    def test_platform_source(self):
        # Platform self-improvement paths also pass through unchanged
        p = "/app/platform/agents/executor.py"
        assert _resolve_file_path(p, WS) == p


# ---------------------------------------------------------------------------
# Edge cases / path confusion
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_workspace_prefix_in_name(self):
        # File literally named "workspace_config.py" must not be aliased
        assert _resolve_file_path("workspace_config.py", WS) == f"{WS}/workspace_config.py"

    def test_partial_workspace_prefix(self):
        # /workspaceXYZ should NOT match /workspace alias
        assert _resolve_file_path("/workspaceXYZ/file.py", WS) == "/workspaceXYZ/file.py"

    def test_workspace_double_slash(self):
        # /workspace//src/main.py — still resolves correctly
        result = _resolve_file_path("/workspace//src/main.py", WS)
        assert result == f"{WS}//src/main.py" or result == f"{WS}/src/main.py"

    def test_path_traversal_via_workspace(self):
        # /workspace/../../../etc/passwd  — resolve_file_path doesn't canonicalize,
        # but code_tools.realpath() will catch this; we just confirm no silent remap to system
        result = _resolve_file_path("/workspace/../etc/passwd", WS)
        # Must start with workspace path (not /etc)
        assert result.startswith(WS)

    def test_no_project_path_system_path_unchanged(self):
        assert _resolve_file_path("/etc/passwd", None) == "/etc/passwd"

    def test_no_project_path_workspace_alias_unchanged(self):
        # Without a project_path we can't resolve /workspace — return as-is
        assert _resolve_file_path("/workspace/src/main.py", None) == "/workspace/src/main.py"

    def test_deeply_nested_workspace_path(self):
        deep = "/workspace/src/components/ui/atoms/Button/index.vue"
        expected = f"{WS}/src/components/ui/atoms/Button/index.vue"
        assert _resolve_file_path(deep, WS) == expected
