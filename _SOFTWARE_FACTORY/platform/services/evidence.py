"""Evidence Gate — deterministic acceptance criteria checks.

After each dev sprint, verifies that real artifacts were produced.
Loop until criteria met or max sprints exhausted.
No LLM — pure subprocess/filesystem checks.
"""
from __future__ import annotations

import glob
import logging
import os
import subprocess
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Criterion:
    id: str
    description: str
    check: str  # file_exists, file_count_min, command_ok, no_fake_files
    params: dict = field(default_factory=dict)
    passed: bool = False
    detail: str = ""


# ── Default criteria per project type ──

ANDROID_CRITERIA = [
    Criterion("kotlin-files", "Au moins 5 fichiers Kotlin", "file_count_min",
              {"pattern": "**/*.kt", "min": 5}),
    Criterion("gradle-build", "Fichier build.gradle.kts existe", "file_exists",
              {"pattern": "**/build.gradle*"}),
    Criterion("manifest", "AndroidManifest.xml existe", "file_exists",
              {"pattern": "**/AndroidManifest.xml"}),
    Criterion("app-structure", "Structure app/src/main existe", "dir_exists",
              {"path": "app/src/main"}),
    Criterion("tests-exist", "Au moins 2 fichiers de test", "file_count_min",
              {"pattern": "**/*Test*.kt", "min": 2}),
    Criterion("no-swift", "Pas de fichiers Swift dans un projet Android", "file_count_max",
              {"pattern": "**/*.swift", "max": 0}),
    Criterion("real-gradlew", "gradlew n'est pas un fake", "no_fake_files",
              {"pattern": "**/gradlew", "min_size": 100}),
]

IOS_CRITERIA = [
    Criterion("swift-files", "Au moins 5 fichiers Swift", "file_count_min",
              {"pattern": "**/*.swift", "min": 5}),
    Criterion("xcodeproj", "Projet Xcode existe", "file_exists",
              {"pattern": "**/*.xcodeproj"}),
    Criterion("tests-exist", "Au moins 2 fichiers de test", "file_count_min",
              {"pattern": "**/*Test*.swift", "min": 2}),
    Criterion("no-kotlin", "Pas de Kotlin dans un projet iOS", "file_count_max",
              {"pattern": "**/*.kt", "max": 0}),
]

WEB_CRITERIA = [
    Criterion("package-json", "package.json existe", "file_exists",
              {"pattern": "**/package.json"}),
    Criterion("source-files", "Au moins 5 fichiers source", "file_count_min",
              {"pattern": "**/*.{ts,tsx,js,jsx,svelte,vue}", "min": 5}),
    Criterion("tests-exist", "Au moins 2 fichiers de test", "file_count_min",
              {"pattern": "**/*.{test,spec}.{ts,tsx,js,jsx}", "min": 2}),
]

BACKEND_CRITERIA = [
    Criterion("source-files", "Au moins 5 fichiers source", "file_count_min",
              {"pattern": "**/*.{py,rs,go,java}", "min": 5}),
    Criterion("tests-exist", "Au moins 2 fichiers de test", "file_count_min",
              {"pattern": "**/*test*.*", "min": 2}),
]

_TYPE_MAP = {
    "android": ANDROID_CRITERIA,
    "ios": IOS_CRITERIA,
    "web": WEB_CRITERIA,
    "frontend": WEB_CRITERIA,
    "backend": BACKEND_CRITERIA,
}


def get_criteria_for_workflow(workflow_id: str, workflow_config: dict | None = None) -> list[Criterion]:
    """Get acceptance criteria — from workflow config or defaults."""
    # 1. Check workflow config for explicit criteria
    if workflow_config and "acceptance_criteria" in workflow_config:
        return [Criterion(**c) for c in workflow_config["acceptance_criteria"]]

    # 2. Auto-detect from workflow name
    wid = (workflow_id or "").lower()
    for key, criteria in _TYPE_MAP.items():
        if key in wid:
            # Deep copy to avoid mutating defaults
            return [Criterion(c.id, c.description, c.check, dict(c.params)) for c in criteria]

    # 3. Minimal fallback
    return [
        Criterion("has-files", "Au moins 3 fichiers source créés", "file_count_min",
                  {"pattern": "**/*.*", "min": 3}),
    ]


def run_evidence_checks(workspace: str, criteria: list[Criterion]) -> tuple[bool, list[Criterion]]:
    """Run all acceptance criteria checks. Returns (all_passed, results)."""
    if not workspace or not os.path.isdir(workspace):
        for c in criteria:
            c.passed = False
            c.detail = f"Workspace not found: {workspace}"
        return False, criteria

    all_passed = True
    for c in criteria:
        try:
            if c.check == "file_exists":
                found = _glob_recursive(workspace, c.params["pattern"])
                c.passed = len(found) > 0
                c.detail = f"{len(found)} found" if c.passed else "0 found"

            elif c.check == "file_count_min":
                found = _glob_recursive(workspace, c.params["pattern"])
                minimum = c.params.get("min", 1)
                c.passed = len(found) >= minimum
                c.detail = f"{len(found)}/{minimum} found"

            elif c.check == "file_count_max":
                found = _glob_recursive(workspace, c.params["pattern"])
                maximum = c.params.get("max", 0)
                c.passed = len(found) <= maximum
                c.detail = f"{len(found)} found (max {maximum})"

            elif c.check == "dir_exists":
                path = os.path.join(workspace, c.params["path"])
                c.passed = os.path.isdir(path)
                c.detail = "exists" if c.passed else "missing"

            elif c.check == "no_fake_files":
                found = _glob_recursive(workspace, c.params["pattern"])
                min_size = c.params.get("min_size", 100)
                if not found:
                    c.passed = True
                    c.detail = "no file to check"
                else:
                    fakes = []
                    for f in found:
                        if os.path.getsize(f) < min_size:
                            fakes.append(f)
                        else:
                            # Check content for placeholder patterns
                            try:
                                with open(f, 'r', errors='ignore') as fh:
                                    content = fh.read(200)
                                if any(p in content.lower() for p in ('placeholder', 'echo', '/dev/null', 'stub')):
                                    fakes.append(f)
                            except Exception:
                                pass
                    c.passed = len(fakes) == 0
                    c.detail = f"{len(fakes)} fake(s) detected" if fakes else "genuine"

            elif c.check == "command_ok":
                cmd = c.params.get("command", "true")
                try:
                    result = subprocess.run(
                        cmd, shell=True, cwd=workspace,
                        capture_output=True, text=True, timeout=60,
                    )
                    c.passed = result.returncode == 0
                    c.detail = "exit 0" if c.passed else f"exit {result.returncode}"
                except subprocess.TimeoutExpired:
                    c.passed = False
                    c.detail = "timeout"

            else:
                c.passed = False
                c.detail = f"unknown check type: {c.check}"

        except Exception as e:
            c.passed = False
            c.detail = f"error: {e}"

        if not c.passed:
            all_passed = False

    return all_passed, criteria


def format_evidence_report(criteria: list[Criterion]) -> str:
    """Format criteria results as human-readable feedback for agents."""
    lines = ["--- ACCEPTANCE CRITERIA CHECK ---"]
    passed = sum(1 for c in criteria if c.passed)
    total = len(criteria)
    lines.append(f"Score: {passed}/{total} critères remplis\n")

    for c in criteria:
        icon = "PASS" if c.passed else "FAIL"
        lines.append(f"  [{icon}] {c.description}: {c.detail}")

    failed = [c for c in criteria if not c.passed]
    if failed:
        lines.append("\n--- ACTIONS REQUISES (MANDATORY) ---")
        for c in failed:
            lines.append(f"  - {c.description} ({c.detail})")
        lines.append("\nNe PAS passer au sprint suivant tant que ces critères ne sont pas remplis.")
        lines.append("Utilisez les VRAIS outils de build (android_build, build, test) — pas de faux scripts.")

    return "\n".join(lines)


def _glob_recursive(workspace: str, pattern: str) -> list[str]:
    """Glob with brace expansion support."""
    # Handle {a,b} patterns by expanding manually
    if '{' in pattern and '}' in pattern:
        import re
        m = re.search(r'\{([^}]+)\}', pattern)
        if m:
            options = m.group(1).split(',')
            results = []
            for opt in options:
                expanded = pattern[:m.start()] + opt.strip() + pattern[m.end():]
                results.extend(glob.glob(os.path.join(workspace, expanded), recursive=True))
            # Deduplicate
            return list(set(f for f in results if not f.endswith('/.git') and '/.git/' not in f))

    found = glob.glob(os.path.join(workspace, pattern), recursive=True)
    return [f for f in found if not f.endswith('/.git') and '/.git/' not in f]
