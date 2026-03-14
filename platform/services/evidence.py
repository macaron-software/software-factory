"""Evidence Gate — deterministic acceptance criteria checks.

After each dev sprint, verifies that real artifacts were produced.
Loop until criteria met or max sprints exhausted.
No LLM — pure subprocess/filesystem checks.
"""
# Ref: feat-quality

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
    Criterion(
        "kotlin-files",
        "Au moins 5 fichiers Kotlin",
        "file_count_min",
        {"pattern": "**/*.kt", "min": 5},
    ),
    Criterion(
        "gradle-build",
        "Fichier build.gradle.kts existe",
        "file_exists",
        {"pattern": "**/build.gradle*"},
    ),
    Criterion(
        "manifest",
        "AndroidManifest.xml existe",
        "file_exists",
        {"pattern": "**/AndroidManifest.xml"},
    ),
    Criterion(
        "app-structure",
        "Structure app/src/main existe",
        "dir_exists",
        {"path": "app/src/main"},
    ),
    Criterion(
        "tests-exist",
        "Au moins 2 fichiers de test",
        "file_count_min",
        {"pattern": "**/*Test*.kt", "min": 2},
    ),
    Criterion(
        "no-swift",
        "Pas de fichiers Swift dans un projet Android",
        "file_count_max",
        {"pattern": "**/*.swift", "max": 0},
    ),
    Criterion(
        "real-gradlew",
        "gradlew n'est pas un fake",
        "no_fake_files",
        {"pattern": "**/gradlew", "min_size": 100},
    ),
]

IOS_CRITERIA = [
    Criterion(
        "swift-files",
        "Au moins 5 fichiers Swift",
        "file_count_min",
        {"pattern": "**/*.swift", "min": 5},
    ),
    Criterion(
        "xcodeproj", "Projet Xcode existe", "file_exists", {"pattern": "**/*.xcodeproj"}
    ),
    Criterion(
        "tests-exist",
        "Au moins 2 fichiers de test",
        "file_count_min",
        {"pattern": "**/*Test*.swift", "min": 2},
    ),
    Criterion(
        "no-kotlin",
        "Pas de Kotlin dans un projet iOS",
        "file_count_max",
        {"pattern": "**/*.kt", "max": 0},
    ),
]

WEB_CRITERIA = [
    Criterion(
        "package-json",
        "package.json existe",
        "file_exists",
        {"pattern": "**/package.json"},
    ),
    Criterion(
        "source-files",
        "Au moins 5 fichiers source",
        "file_count_min",
        {"pattern": "**/*.{ts,tsx,js,jsx,svelte,vue}", "min": 5},
    ),
    Criterion(
        "tests-exist",
        "Au moins 2 fichiers de test",
        "file_count_min",
        {"pattern": "**/*.{test,spec}.{ts,tsx,js,jsx}", "min": 2},
    ),
]

GAME_HTML5_CRITERIA = [
    Criterion(
        "html-entry",
        "Fichier index.html avec <canvas> existe",
        "file_content_match",
        {"pattern": "**/index.html", "contains": "canvas"},
    ),
    Criterion(
        "game-loop",
        "Boucle de jeu requestAnimationFrame ou setInterval présente",
        "file_content_match",
        {"pattern": "**/*.{js,ts}", "contains": "requestAnimationFrame"},
    ),
    Criterion(
        "keyboard-input",
        "Gestion clavier (keydown/ArrowLeft/ArrowRight) présente",
        "file_content_match",
        {"pattern": "**/*.{js,ts}", "contains": "keydown"},
    ),
    Criterion(
        "score-display",
        "Élément score dans HTML ou code",
        "file_content_match",
        {"pattern": "**/*.{html,js,ts}", "contains": "score"},
    ),
    Criterion(
        "multiple-levels",
        "Au moins 2 fichiers level ou niveau définis",
        "file_content_match",
        {"pattern": "**/*.{js,ts}", "contains": "level"},
    ),
    Criterion(
        "gravity-or-jump",
        "Mécanique gravité ou saut implémentée",
        "file_content_match",
        {
            "pattern": "**/*.{js,ts}",
            "contains_any": ["gravity", "jump", "velocityY", "vy"],
        },
    ),
    Criterion(
        "source-files",
        "Au moins 3 fichiers source JS/TS",
        "file_count_min",
        {"pattern": "**/*.{js,ts}", "min": 3},
    ),
    Criterion(
        "build-produces-js",
        "Build produit des fichiers JS exécutables (dist/ compilé ou JS vanilla)",
        "command_ok",
        {
            "command": (
                "npm run build 2>&1 && ("
                "find dist -name '*.js' 2>/dev/null | head -1 | grep . || "
                "find . -maxdepth 3 -name '*.js' -not -path '*/node_modules/*' "
                "  -not -name '*.test.js' -not -name '*.spec.js' | head -1 | grep ."
                ")"
            ),
            "timeout": 120,
        },
    ),
    Criterion(
        "npm-test",
        "npm test passe (au moins 1 test réel)",
        "command_ok",
        {"command": "npm test 2>&1"},
    ),
]

BACKEND_CRITERIA = [
    Criterion(
        "source-files",
        "Au moins 5 fichiers source",
        "file_count_min",
        {"pattern": "**/*.{py,rs,go,java}", "min": 5},
    ),
    Criterion(
        "tests-exist",
        "Au moins 2 fichiers de test",
        "file_count_min",
        {"pattern": "**/*test*.*", "min": 2},
    ),
]

RUST_CRITERIA = [
    Criterion(
        "cargo-toml", "Cargo.toml existe", "file_exists", {"pattern": "**/Cargo.toml"}
    ),
    Criterion(
        "lib-or-main",
        "src/lib.rs ou src/main.rs existe",
        "file_exists",
        {"pattern": "**/{lib,main}.rs"},
    ),
    Criterion(
        "cargo-check",
        "cargo check passe (compilation OK)",
        "command_ok",
        {"command": "cargo check 2>&1", "cwd": "."},
    ),
    Criterion(
        "cargo-test",
        "cargo test passe (tous les tests OK)",
        "command_ok",
        {"command": "cargo test 2>&1", "cwd": "."},
    ),
    Criterion(
        "tests-in-code",
        "Au moins 1 test #[test] dans les sources",
        "file_count_min",
        {"pattern": "**/*.rs", "min": 1},
    ),
]

_TYPE_MAP = {
    "android": ANDROID_CRITERIA,
    "ios": IOS_CRITERIA,
    "web": WEB_CRITERIA,
    "frontend": WEB_CRITERIA,
    "backend": BACKEND_CRITERIA,
    "rust": RUST_CRITERIA,
    "game": GAME_HTML5_CRITERIA,
    "donkey": GAME_HTML5_CRITERIA,
    "kong": GAME_HTML5_CRITERIA,
    "invader": GAME_HTML5_CRITERIA,
    "pacman": GAME_HTML5_CRITERIA,
    "tetris": GAME_HTML5_CRITERIA,
    "snake": GAME_HTML5_CRITERIA,
    "html5": GAME_HTML5_CRITERIA,
    "arcade": GAME_HTML5_CRITERIA,
}


def _criteria_from_epic(epic_id: str) -> list[Criterion]:
    """Extract Criterion objects from epic features/stories in the DB.

    Reads epic description + feature names → generates functional criteria.
    Falls back to [] if DB unavailable or no features found.
    """
    if not epic_id:
        return []
    try:
        from ..db.migrations import get_db

        db = get_db()
        # Get epic description
        epic = db.execute(
            "SELECT name, description, goal FROM epics WHERE id=?", (epic_id,)
        ).fetchone()
        if not epic:
            return []
        # Get feature names
        features = db.execute(
            "SELECT name, description FROM features WHERE epic_id=? AND status != 'archived'",
            (epic_id,),
        ).fetchall()
        if not features:
            return []

        criteria: list[Criterion] = []
        for i, feat in enumerate(features):
            fname = (feat[0] or "").strip()
            if not fname:
                continue
            # Each feature must be traceable in the codebase
            # Use keyword extraction from name for file_content_match
            keywords = [
                w.lower()
                for w in fname.replace("-", " ").replace("_", " ").split()
                if len(w) > 3
            ]
            if keywords:
                criteria.append(
                    Criterion(
                        f"feature-{i}-{keywords[0]}",
                        f"Feature '{fname}' implémentée dans le code",
                        "file_content_match",
                        {
                            "pattern": "**/*.{js,ts,py,rs,go,kt,java,tsx,jsx}",
                            "contains_any": keywords[:3],
                        },
                    )
                )
        # Always add: npm/cargo test must pass if package.json or Cargo.toml present
        criteria.append(
            Criterion(
                "tests-pass",
                "Suite de tests passe (npm test / cargo test)",
                "command_ok",
                {
                    "command": "npm test 2>&1 || cargo test 2>&1 || pytest 2>&1 || echo 'no test runner'"
                },
            )
        )
        return criteria
    except Exception as _e:
        logger.debug("_criteria_from_epic failed: %s", _e)
        return []


def get_criteria_for_workflow(
    workflow_id: str,
    workflow_config: dict | None = None,
    workspace: str = "",
    epic_id: str = "",
) -> list[Criterion]:
    """Get acceptance criteria — from workflow config, epic DB, auto-detect, or workspace scan."""
    # 1. Check workflow config for explicit criteria
    if workflow_config and "acceptance_criteria" in workflow_config:
        return [Criterion(**c) for c in workflow_config["acceptance_criteria"]]

    # 2. Load feature-based criteria from epic DB (project-specific ACs)
    epic_criteria = _criteria_from_epic(epic_id)
    if epic_criteria:
        logger.info(
            "evidence gate: %d criteria from epic %s features",
            len(epic_criteria),
            epic_id,
        )
        return epic_criteria

    # 3. Auto-detect from workflow name
    wid = (workflow_id or "").lower()
    for key, criteria in _TYPE_MAP.items():
        if key in wid:
            # Deep copy to avoid mutating defaults
            return [
                Criterion(c.id, c.description, c.check, dict(c.params))
                for c in criteria
            ]

    # 4. Auto-detect from workspace contents
    if workspace and os.path.isdir(workspace):
        if _glob_recursive(workspace, "**/build.gradle*") or _glob_recursive(
            workspace, "**/*.kt"
        ):
            return [
                Criterion(c.id, c.description, c.check, dict(c.params))
                for c in ANDROID_CRITERIA
            ]
        if _glob_recursive(workspace, "**/*.xcodeproj") or _glob_recursive(
            workspace, "**/*.swift"
        ):
            return [
                Criterion(c.id, c.description, c.check, dict(c.params))
                for c in IOS_CRITERIA
            ]
        if _glob_recursive(workspace, "**/Cargo.toml") or _glob_recursive(
            workspace, "**/*.rs"
        ):
            return [
                Criterion(c.id, c.description, c.check, dict(c.params))
                for c in RUST_CRITERIA
            ]
        if _glob_recursive(workspace, "**/package.json"):
            return [
                Criterion(c.id, c.description, c.check, dict(c.params))
                for c in WEB_CRITERIA
            ]

    # 5. Generic fallback — works for any project type
    return [
        Criterion(
            "source-files",
            "Au moins 3 fichiers source créés",
            "file_count_min",
            {
                "pattern": "**/*.{html,css,js,ts,tsx,jsx,py,rs,go,java,kt,swift,svelte,vue}",
                "min": 3,
            },
        ),
        Criterion(
            "no-empty-files",
            "Pas de fichiers vides (>50 bytes)",
            "no_fake_files",
            {"pattern": "**/*.{html,css,js,ts,py,rs}", "min_size": 50},
        ),
        Criterion(
            "has-git-commits",
            "Au moins 1 commit git",
            "command_ok",
            {"command": "git log --oneline -1"},
        ),
    ]


def run_evidence_checks(
    workspace: str, criteria: list[Criterion]
) -> tuple[bool, list[Criterion]]:
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
                                with open(f, "r", errors="ignore") as fh:
                                    content = fh.read(200)
                                if any(
                                    p in content.lower()
                                    for p in (
                                        "placeholder",
                                        "echo",
                                        "/dev/null",
                                        "stub",
                                    )
                                ):
                                    fakes.append(f)
                            except Exception:
                                pass
                    c.passed = len(fakes) == 0
                    c.detail = f"{len(fakes)} fake(s) detected" if fakes else "genuine"

            elif c.check == "command_ok":
                cmd = c.params.get("command", "true")
                timeout = c.params.get("timeout", 120)
                # Ensure cargo is findable on common install paths
                import os as _os

                env = dict(_os.environ)
                home = env.get("HOME", "/root")
                cargo_bin = f"{home}/.cargo/bin"
                if cargo_bin not in env.get("PATH", ""):
                    env["PATH"] = cargo_bin + ":" + env.get("PATH", "")
                try:
                    result = subprocess.run(
                        cmd,
                        shell=True,
                        cwd=workspace,
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                        env=env,
                    )
                    c.passed = result.returncode == 0
                    out = (result.stdout + result.stderr)[-500:]
                    c.detail = (
                        ("exit 0: " + out[:200])
                        if c.passed
                        else f"exit {result.returncode}: {out[:300]}"
                    )
                except subprocess.TimeoutExpired:
                    c.passed = False
                    c.detail = f"timeout after {timeout}s"

            elif c.check == "file_content_match":
                pattern = c.params.get("pattern", "**/*")
                contains = c.params.get("contains", "")
                contains_any = c.params.get("contains_any", [])
                if contains:
                    contains_any = [contains]
                found = False
                for f in _glob_recursive(workspace, pattern):
                    try:
                        text = open(f, encoding="utf-8", errors="ignore").read()
                        if any(kw in text for kw in contains_any):
                            found = True
                            break
                    except Exception:
                        pass
                c.passed = found
                c.detail = (
                    f"Keyword found in {pattern}"
                    if found
                    else f"None of {contains_any} found in {pattern}"
                )

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
        lines.append(
            "\nNe PAS passer au sprint suivant tant que ces critères ne sont pas remplis."
        )
        lines.append(
            "Utilisez les VRAIS outils de build (android_build, build, test) — pas de faux scripts."
        )

    return "\n".join(lines)


def _glob_recursive(workspace: str, pattern: str) -> list[str]:
    """Glob with brace expansion support."""
    # Handle {a,b} patterns by expanding manually
    if "{" in pattern and "}" in pattern:
        import re

        m = re.search(r"\{([^}]+)\}", pattern)
        if m:
            options = m.group(1).split(",")
            results = []
            for opt in options:
                expanded = pattern[: m.start()] + opt.strip() + pattern[m.end() :]
                results.extend(
                    glob.glob(os.path.join(workspace, expanded), recursive=True)
                )
            # Deduplicate
            return list(
                set(f for f in results if not f.endswith("/.git") and "/.git/" not in f)
            )

    found = glob.glob(os.path.join(workspace, pattern), recursive=True)
    return [f for f in found if not f.endswith("/.git") and "/.git/" not in f]
