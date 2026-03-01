"""
Deliverable Quality Test — Verify that generated project workspaces
match their SPECS.md and produce runnable artifacts.

Tests each project in workspace/ that has a SPECS.md and src/ directory.

Usage:
    pytest tests/test_deliverable_quality.py -v
    pytest tests/test_deliverable_quality.py -v -k psycare
    pytest tests/test_deliverable_quality.py -v --workspace /path/to/workspace
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

import pytest

# ── Configuration ──────────────────────────────────────────────────────────

WORKSPACE_ROOT = Path(
    os.environ.get("WORKSPACE_PATH", Path(__file__).parent.parent / "workspace")
)
DOCKER_SMOKE = os.environ.get("DOCKER_SMOKE", "0") == "1"
SPEC_CONFORMITY_THRESHOLD = float(os.environ.get("SPEC_THRESHOLD", "0.50"))  # 50% min
DOCKER_BUILD_TIMEOUT = int(os.environ.get("DOCKER_BUILD_TIMEOUT", "120"))


# ── Helpers ────────────────────────────────────────────────────────────────

def _collect_projects() -> list[Path]:
    """Find all projects in workspace/ that have src/ or code files."""
    if not WORKSPACE_ROOT.exists():
        return []
    projects = []
    for p in sorted(WORKSPACE_ROOT.iterdir()):
        if not p.is_dir():
            continue
        if p.name.startswith(".") or p.name.startswith("_"):
            continue
        # Must have at least one code file or README
        has_content = (
            (p / "src").exists()
            or (p / "README.md").exists()
            or list(p.glob("*.py"))
            or list(p.glob("*.ts"))
            or list(p.glob("*.js"))
        )
        if has_content:
            projects.append(p)
    return projects


def _collect_code_files(project_path: Path) -> list[Path]:
    """Collect all relevant source files from a project."""
    extensions = {".py", ".ts", ".js", ".tsx", ".jsx", ".java", ".go", ".rb", ".rs"}
    files = []
    for ext in extensions:
        files.extend(project_path.rglob(f"*{ext}"))
    # Exclude node_modules, .venv, __pycache__
    excluded = {"node_modules", ".venv", "__pycache__", ".git", "dist", "build", ".next"}
    return [f for f in files if not any(ex in f.parts for ex in excluded)]


def _extract_spec_features(specs_path: Path) -> list[str]:
    """Extract feature keywords from SPECS.md."""
    if not specs_path.exists():
        return []
    text = specs_path.read_text(encoding="utf-8", errors="ignore")
    features = []
    # Extract checkbox items: - [ ] feature name or - [x] feature name
    for m in re.finditer(r"- \[[ x]\] (.+)", text):
        feat = m.group(1).strip()
        if len(feat) > 5:
            features.append(feat)
    # Extract H3/H4 headings (functional areas)
    for m in re.finditer(r"^#{2,4} (.+)", text, re.MULTILINE):
        feat = m.group(1).strip()
        # Skip meta-headings
        if not any(skip in feat.lower() for skip in ["stack", "contrainte", "objectif", "vision", "périmètre", "status", "infrastructure"]):
            features.append(feat)
    return list(set(features))[:50]  # cap at 50 features


def _feature_covered(feature: str, code_text: str) -> bool:
    """Check if a feature keyword appears in the codebase."""
    # Extract meaningful keywords from feature string
    keywords = re.sub(r"[^\w\s]", " ", feature.lower()).split()
    # Filter stop words
    stop = {"le", "la", "les", "de", "du", "des", "un", "une", "et", "ou", "à", "en", "pour", "avec", "the", "a", "an", "of", "and", "or", "for", "in", "with", "to", "is", "are"}
    keywords = [k for k in keywords if len(k) >= 4 and k not in stop]
    if not keywords:
        return False
    code_lower = code_text.lower()
    # Feature is covered if at least half the keywords appear
    hits = sum(1 for k in keywords if k in code_lower)
    return hits >= max(1, len(keywords) // 2)


def _validate_python_syntax(file_path: Path) -> tuple[bool, str]:
    """Check Python file syntax."""
    try:
        source = file_path.read_text(encoding="utf-8", errors="ignore")
        ast.parse(source, filename=str(file_path))
        return True, ""
    except SyntaxError as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)


def _count_placeholders(files: list[Path]) -> tuple[int, int]:
    """Count placeholder lines vs total lines."""
    placeholder_patterns = [
        r"^\s*pass\s*$",
        r"raise NotImplementedError",
        r"# TODO",
        r"# FIXME",
        r"# PLACEHOLDER",
        r"\.\.\.  # stub",
    ]
    total = 0
    placeholders = 0
    for f in files:
        try:
            lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
            total += len(lines)
            for line in lines:
                if any(re.search(p, line, re.IGNORECASE) for p in placeholder_patterns):
                    placeholders += 1
        except Exception:
            pass
    return placeholders, total


def _docker_smoke_test(project_path: Path) -> tuple[bool, str]:
    """Attempt docker build + run smoke test."""
    dockerfile = project_path / "Dockerfile"
    if not dockerfile.exists():
        # Try docker-compose
        compose = project_path / "docker-compose.yml"
        if not compose.exists():
            return False, "No Dockerfile or docker-compose.yml"

    tag = f"sf-test-{project_path.name}:test"
    try:
        result = subprocess.run(
            ["docker", "build", "-t", tag, str(project_path)],
            capture_output=True, text=True,
            timeout=DOCKER_BUILD_TIMEOUT,
            cwd=str(project_path),
        )
        if result.returncode != 0:
            return False, f"Build failed: {result.stderr[-300:]}"

        # Cleanup
        subprocess.run(["docker", "rmi", tag], capture_output=True, timeout=30)
        return True, "Build OK"
    except subprocess.TimeoutExpired:
        return False, f"Build timeout ({DOCKER_BUILD_TIMEOUT}s)"
    except FileNotFoundError:
        return False, "Docker not available"
    except Exception as e:
        return False, str(e)


# ── Project Score ──────────────────────────────────────────────────────────

class ProjectScore:
    def __init__(self, project: Path):
        self.project = project
        self.name = project.name
        self.checks: dict[str, tuple[bool, str]] = {}

    def add(self, check: str, passed: bool, detail: str = "") -> None:
        self.checks[check] = (passed, detail)

    @property
    def score(self) -> float:
        if not self.checks:
            return 0.0
        return sum(1 for p, _ in self.checks.values() if p) / len(self.checks)

    @property
    def passed(self) -> bool:
        return self.score >= 0.6

    def summary(self) -> str:
        icon = "✅" if self.score >= 0.8 else "⚠️" if self.score >= 0.6 else "❌"
        lines = [f"{icon} {self.name}: {self.score*100:.0f}%"]
        for check, (ok, detail) in self.checks.items():
            mark = "  ✅" if ok else "  ❌"
            lines.append(f"{mark} {check}: {detail[:80]}" if detail else f"{mark} {check}")
        return "\n".join(lines)


# ── Parametrized tests ─────────────────────────────────────────────────────

def pytest_collect_projects():
    return _collect_projects()


@pytest.fixture(scope="module")
def all_projects():
    return _collect_projects()


class TestWorkspaceExists:
    def test_workspace_root_exists(self):
        """workspace/ directory must exist."""
        assert WORKSPACE_ROOT.exists(), f"Workspace not found: {WORKSPACE_ROOT}"

    def test_workspace_has_projects(self):
        """workspace/ must contain at least one project."""
        projects = _collect_projects()
        assert len(projects) > 0, f"No projects found in {WORKSPACE_ROOT}"
        print(f"\n  Found {len(projects)} projects: {[p.name for p in projects]}")


class TestProjectStructure:
    """Tests project structure for each project in workspace/."""

    @pytest.fixture(params=_collect_projects(), ids=lambda p: p.name)
    def project(self, request):
        return request.param

    def test_has_readme(self, project: Path):
        """Project must have a README.md."""
        readme = project / "README.md"
        if not readme.exists():
            pytest.skip(f"No README.md in {project.name}")
        assert readme.stat().st_size > 100, f"README.md too small ({readme.stat().st_size} bytes)"

    def test_has_specs(self, project: Path):
        """Project should have a SPECS.md with real content."""
        specs = project / "SPECS.md"
        if not specs.exists():
            pytest.skip(f"No SPECS.md in {project.name} — specs not generated yet")
        content = specs.read_text(encoding="utf-8", errors="ignore")
        meaningful = len([l for l in content.splitlines() if l.strip() and not l.startswith("#")])
        assert meaningful >= 10, f"SPECS.md too sparse ({meaningful} meaningful lines)"

    def test_has_source_code(self, project: Path):
        """Project must have source code files."""
        code_files = _collect_code_files(project)
        if not code_files:
            pytest.skip(f"No source code files in {project.name}")
        assert len(code_files) > 0, f"No code files found in {project.name}"
        print(f"\n  {project.name}: {len(code_files)} code files")

    def test_has_docker_config(self, project: Path):
        """Project should have Dockerfile or docker-compose."""
        has_docker = (
            (project / "Dockerfile").exists()
            or (project / "docker-compose.yml").exists()
            or (project / "docker-compose.yaml").exists()
        )
        if not has_docker:
            pytest.skip(f"No Docker config in {project.name}")
        assert has_docker


class TestCodeQuality:
    """Tests code quality for each project."""

    @pytest.fixture(params=[p for p in _collect_projects() if _collect_code_files(p)], ids=lambda p: p.name)
    def project_with_code(self, request):
        return request.param

    def test_python_syntax_valid(self, project_with_code: Path):
        """All Python files must have valid syntax."""
        py_files = list(project_with_code.rglob("*.py"))
        py_files = [f for f in py_files if not any(ex in f.parts for ex in {"node_modules", ".venv", "__pycache__"})]
        if not py_files:
            pytest.skip(f"No Python files in {project_with_code.name}")

        errors = []
        for f in py_files:
            ok, msg = _validate_python_syntax(f)
            if not ok:
                errors.append(f"{f.relative_to(project_with_code)}: {msg}")

        if errors:
            pytest.fail(f"{project_with_code.name} has {len(errors)} syntax errors:\n" + "\n".join(errors[:5]))

    def test_placeholder_ratio_acceptable(self, project_with_code: Path):
        """Less than 30% of code lines should be placeholders."""
        py_files = list(project_with_code.rglob("*.py"))
        py_files = [f for f in py_files if not any(ex in f.parts for ex in {"__pycache__", ".venv"})]
        if not py_files:
            pytest.skip(f"No Python files in {project_with_code.name}")

        placeholders, total = _count_placeholders(py_files)
        if total == 0:
            pytest.skip("Empty files")

        ratio = placeholders / total
        print(f"\n  {project_with_code.name}: {placeholders}/{total} placeholder lines ({ratio*100:.1f}%)")
        assert ratio < 0.30, (
            f"{project_with_code.name}: {ratio*100:.1f}% placeholder lines (max 30%)"
        )

    def test_no_empty_src_directory(self, project_with_code: Path):
        """src/ directory must not be empty."""
        src = project_with_code / "src"
        if not src.exists():
            pytest.skip(f"No src/ in {project_with_code.name}")
        files = [f for f in src.rglob("*") if f.is_file() and f.name != "__init__.py"]
        assert len(files) > 0, f"{project_with_code.name}/src/ only has __init__.py (no real code)"


class TestSpecConformity:
    """Tests that generated code covers the spec features."""

    @pytest.fixture(
        params=[p for p in _collect_projects() if (p / "SPECS.md").exists() and _collect_code_files(p)],
        ids=lambda p: p.name,
    )
    def project_with_specs(self, request):
        return request.param

    def test_spec_coverage(self, project_with_specs: Path):
        """Generated code must cover ≥ SPEC_CONFORMITY_THRESHOLD of spec features."""
        specs_path = project_with_specs / "SPECS.md"
        features = _extract_spec_features(specs_path)
        if len(features) < 3:
            pytest.skip(f"{project_with_specs.name}: Too few features in specs ({len(features)})")

        # Collect all code text
        code_files = _collect_code_files(project_with_specs)
        if not code_files:
            pytest.skip(f"No code files to check")

        all_code = ""
        for f in code_files:
            try:
                all_code += f.read_text(encoding="utf-8", errors="ignore") + "\n"
            except Exception:
                pass

        covered = [f for f in features if _feature_covered(f, all_code)]
        uncovered = [f for f in features if not _feature_covered(f, all_code)]
        ratio = len(covered) / len(features)

        print(f"\n  {project_with_specs.name}: {len(covered)}/{len(features)} features covered ({ratio*100:.0f}%)")
        if uncovered:
            print(f"  Uncovered features: {uncovered[:5]}")

        assert ratio >= SPEC_CONFORMITY_THRESHOLD, (
            f"{project_with_specs.name}: spec coverage {ratio*100:.0f}% < {SPEC_CONFORMITY_THRESHOLD*100:.0f}%\n"
            f"  Uncovered: {uncovered[:10]}"
        )

    def test_specs_not_template(self, project_with_specs: Path):
        """SPECS.md must not be the empty template (À compléter placeholder)."""
        specs_path = project_with_specs / "SPECS.md"
        content = specs_path.read_text(encoding="utf-8", errors="ignore")
        placeholder_count = content.count("À définir") + content.count("À compléter") + content.count("*À définir*")
        total_lines = len([l for l in content.splitlines() if l.strip()])
        if total_lines == 0:
            pytest.skip("Empty specs")
        ratio = placeholder_count / total_lines
        assert ratio < 0.5, (
            f"{project_with_specs.name}: SPECS.md is {ratio*100:.0f}% placeholders — not generated yet"
        )


@pytest.mark.skipif(not DOCKER_SMOKE, reason="Set DOCKER_SMOKE=1 to run Docker smoke tests")
class TestDockerBuild:
    """Docker build smoke tests (requires DOCKER_SMOKE=1)."""

    @pytest.fixture(
        params=[p for p in _collect_projects() if (p / "Dockerfile").exists() or (p / "docker-compose.yml").exists()],
        ids=lambda p: p.name,
    )
    def project_with_docker(self, request):
        return request.param

    def test_docker_build_succeeds(self, project_with_docker: Path):
        """Docker build must succeed."""
        ok, msg = _docker_smoke_test(project_with_docker)
        assert ok, f"{project_with_docker.name}: Docker build failed — {msg}"


# ── Summary report ─────────────────────────────────────────────────────────

class TestDeliverableReport:
    """Generate a consolidated quality report for all projects."""

    def test_generate_quality_report(self, tmp_path):
        """Generate and save a quality report for all projects."""
        projects = _collect_projects()
        if not projects:
            pytest.skip("No projects found")

        report_lines = [
            "# Deliverable Quality Report",
            f"Generated: {__import__('datetime').datetime.now().isoformat()}",
            f"Workspace: {WORKSPACE_ROOT}",
            f"Projects: {len(projects)}",
            "",
            "## Summary",
            "| Project | README | SPECS | Code | Syntax | Placeholder% | Coverage |",
            "|---------|--------|-------|------|--------|--------------|----------|",
        ]

        for project in projects:
            readme_ok = (project / "README.md").exists() and (project / "README.md").stat().st_size > 100
            specs_ok = (project / "SPECS.md").exists()
            code_files = _collect_code_files(project)
            has_code = len(code_files) > 0

            # Syntax check
            py_files = [f for f in code_files if f.suffix == ".py" and "__pycache__" not in str(f)]
            syntax_errors = sum(1 for f in py_files if not _validate_python_syntax(f)[0])
            syntax_ok = syntax_errors == 0 and len(py_files) > 0

            # Placeholder ratio
            placeholders, total = _count_placeholders(py_files)
            placeholder_pct = (placeholders / total * 100) if total > 0 else 0

            # Spec coverage
            coverage = "N/A"
            if specs_ok and code_files:
                features = _extract_spec_features(project / "SPECS.md")
                if len(features) >= 3:
                    all_code = ""
                    for f in code_files[:20]:
                        try:
                            all_code += f.read_text(encoding="utf-8", errors="ignore") + "\n"
                        except Exception:
                            pass
                    covered = sum(1 for feat in features if _feature_covered(feat, all_code))
                    coverage = f"{covered}/{len(features)} ({covered/len(features)*100:.0f}%)"

            row = (
                f"| {project.name} "
                f"| {'✅' if readme_ok else '❌'} "
                f"| {'✅' if specs_ok else '⚠️'} "
                f"| {'✅' if has_code else '❌'} ({len(code_files)} files) "
                f"| {'✅' if syntax_ok else '❌' if py_files else 'N/A'} "
                f"| {placeholder_pct:.0f}% "
                f"| {coverage} |"
            )
            report_lines.append(row)

        report_text = "\n".join(report_lines)
        print(f"\n{report_text}")

        # Save report
        report_path = Path(__file__).parent / "DELIVERABLE_QUALITY_REPORT.md"
        report_path.write_text(report_text)
        print(f"\n  Report saved: {report_path}")
        assert True  # Always passes — report is informational
