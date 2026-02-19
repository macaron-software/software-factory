#!/usr/bin/env python3
"""
RLM Brain - Deep Recursive Analysis Engine with MCP
====================================================
Based on MIT CSAIL arXiv:2512.24601 "Recursive Language Models"

Uses MCP (Model Context Protocol) for project navigation:
- Opus 4.5 via `claude` CLI with MCP tools
- MiniMax M2.5 via `opencode` with MCP tools
- Both can navigate the codebase using lrm_* tools

COST TIER ARCHITECTURE (like GPT-5 → GPT-5-mini in paper):
  depth=0: Opus 4.5 ($$$) - Strategic orchestration via `claude` + MCP
  depth=1: MiniMax M2.5 ($$) - Deep analysis via `opencode` + MCP  
  depth=2: MiniMax M2.5 ($) - Sub-analysis via `opencode` + MCP
  depth=3: Qwen 30B local (free) - Simple queries

MCP Tools available (from mcp_lrm):
- lrm_locate: Find files matching pattern
- lrm_summarize: Summarize file content
- lrm_conventions: Get domain conventions
- lrm_examples: Get example code
- lrm_build: Run build/test commands

Usage:
    from core.brain import RLMBrain

    brain = RLMBrain("ppz")
    tasks = await brain.run(vision_prompt="Focus on iOS security")
"""

import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.project_registry import get_project, ProjectConfig
from core.task_store import TaskStore, Task
from core.llm_client import run_opencode
from core.project_context import ProjectContext
from core.log import get_logger
from core.subprocess_util import run_subprocess_exec

_brain_logger = get_logger("brain")


def log(msg: str, level: str = "INFO"):
    """Log with timestamp"""
    _brain_logger.log(msg, level)


# ============================================================================
# BRAIN MODES - Specialized analysis prompts
# ============================================================================

BRAIN_MODES = {
    "fix": {
        "name": "FIX",
        "description": "Bugs, build errors, crashes, compilation issues",
        "focus": """Focus on QUALITY & FIXES only:
1. Build errors and compilation issues
2. Runtime crashes and panics (.unwrap() abuse)
3. Logic bugs and incorrect behavior
4. Missing error handling
5. Broken tests
Do NOT generate new features - only FIX existing broken code.
Task types: fix only.""",
        "task_types": ["fix"],
    },
    "vision": {
        "name": "VISION",
        "description": "AO-compliant features from VISION.md with REQ-IDs",
        "focus": """STRICT AO COMPLIANCE MODE - No SLOP, No Gold Plating

RULES (MANDATORY):
1. ONLY generate tasks for features with explicit REQ-ID in VISION.md
2. EVERY task description MUST include the REQ-ID (e.g., REQ-AUTH-001, REQ-RGPD-002)
3. EVERY task MUST reference the AO source (e.g., "IDFM T6 p.89", "Nantes Lisa-2.5")
4. REJECT any "nice-to-have" or "innovation" without AO backing
5. If VISION.md says "EXCLUDED" or "Pas d'AO" - DO NOT GENERATE

WHAT TO GENERATE:
- Features explicitly listed in VISION.md with REQ-* IDs
- Features traced to real AO documents (IDFM, Nantes)
- Tests for existing REQ-* requirements

WHAT TO REJECT (SLOP):
- "Innovation" features without AO reference
- "Nice-to-have" improvements
- Features for tenants without real AO (e.g., Lyon)
- Social features, gamification, AI predictions (unless in AO)
- Anything not traceable to a signed contract/tender

FORMAT: Each task MUST start with [REQ-XXX-NNN] in description.
Example: "[REQ-AUTH-001] Implement MFA for admin users per IDFM T6 p.89"

Task types: feature only. NO feature without REQ-ID.""",
        "task_types": ["feature"],
    },
    "security": {
        "name": "SECURITY",
        "description": "OWASP, secrets, vulnerabilities, auth issues",
        "focus": """Focus on SECURITY only:
1. OWASP Top 10 vulnerabilities (injection, XSS, CSRF, etc.)
2. Hardcoded secrets and credentials
3. Authentication and authorization flaws
4. Data exposure and privacy issues
5. Insecure dependencies
Do NOT generate feature/refactor tasks - only SECURITY fixes.
Task types: security only.""",
        "task_types": ["security"],
    },
    "perf": {
        "name": "PERF",
        "description": "Performance optimization, caching, queries",
        "focus": """Focus on PERFORMANCE only:
1. N+1 database queries
2. Missing caching opportunities
3. Slow algorithms and data structures
4. Memory leaks and excessive allocations
5. Blocking I/O and concurrency issues
Do NOT generate feature/security tasks - only PERFORMANCE improvements.
Task types: refactor (perf) only.""",
        "task_types": ["refactor"],
    },
    "refactor": {
        "name": "REFACTOR",
        "description": "Evidence-based refactoring with metrics and patterns",
        "focus": """EVIDENCE-BASED REFACTORING - Metrics + Patterns + SOLID

PHASE 1 - METRICS (Deterministic thresholds):
- Cyclomatic complexity > 10 → Split function
- LOC per function > 50 → Extract methods
- LOC per file > 500 → Split into modules (God Class)
- Parameters > 5 → Parameter Object or Builder
- Nesting depth > 4 → Early returns, extract
- Methods per class > 10 → SRP violation

PHASE 2 - ANTI-PATTERNS (Detect & Fix):
| Pattern | Detection | Fix |
|---------|-----------|-----|
| God Class | >500 LOC, >10 methods | Split by responsibility |
| Feature Envy | Cross-class data access | Move method |
| Shotgun Surgery | 1 change → N files | Consolidate |
| Primitive Obsession | Strings for types | Value Objects |
| Long Parameter List | >5 params | Builder pattern |
| Data Clumps | Repeated param groups | Extract class |
| Dead Code | Unused functions | Delete |

PHASE 3 - GOF PATTERNS (Apply when appropriate):
- Multiple if/switch on type → Strategy
- Complex creation → Factory/Builder
- State-dependent behavior → State
- Notifications needed → Observer
- Behavior decoration → Decorator

PHASE 4 - SOLID COMPLIANCE:
- S: One class = one reason to change
- O: Extend without modifying
- L: Subtypes substitutable
- I: Specific interfaces
- D: Depend on abstractions

TASK FORMAT:
[REF-XXX] description
- Metric: current → target
- Pattern: antipattern → GOF solution
- Files: list affected files

Do NOT generate feature/fix tasks - only EVIDENCE-BASED REFACTORING.
Task types: refactor only.""",
        "task_types": ["refactor"],
    },
    "test": {
        "name": "TEST",
        "description": "Test coverage gaps, missing tests, edge cases",
        "focus": """Focus on TEST COVERAGE only:
1. Untested public functions
2. Missing edge case tests
3. Missing integration tests
4. Missing E2E tests
5. Flaky tests that need fixing
Do NOT generate feature/fix tasks - only TEST tasks.
Task types: test only.""",
        "task_types": ["test"],
    },
    "migrate": {
        "name": "MIGRATE",
        "description": "REST→gRPC, v1→v2, deprecations, upgrades",
        "focus": """Focus on MIGRATIONS only:
1. Legacy API migrations (REST→gRPC, etc.)
2. Version upgrades (v1→v2)
3. Deprecated code removal
4. Library/framework upgrades
5. Protocol changes
Do NOT generate feature/fix tasks - only MIGRATION tasks.
Task types: refactor (migrate) only.""",
        "task_types": ["refactor"],
    },
    "debt": {
        "name": "DEBT",
        "description": "TODOs, FIXMEs, deprecated, technical debt",
        "focus": """Focus on TECHNICAL DEBT only:
1. TODO comments that need implementation
2. FIXME comments that need fixing
3. Deprecated code that needs updating
4. Hack/workaround code that needs proper solution
5. Dead code that needs removal
Do NOT generate feature/security tasks - only DEBT cleanup.
Task types: fix, refactor.""",
        "task_types": ["fix", "refactor"],
    },
    "integrator": {
        "name": "INTEGRATOR",
        "description": "Cross-layer integration gap detection",
        "focus": """Analyze the project for INTEGRATION GAPS between layers.

You have access to the FULL codebase via MCP tools. For each gap found, create a task.

CHECK LIST:
1. SERVER BOOTSTRAP: Does main.rs/server.rs boot ALL services? Are routes mounted?
   Look for empty main.rs, missing service registrations, incomplete router setup.
2. DATABASE: Are migrations applied? Schema matches code expectations?
   Check if migration files exist but tables are missing in DB.
3. FRONTEND→BACKEND: Are API calls real or mocked? gRPC client generated?
   Search for 'mock', 'hardcoded', 'TODO: connect' in frontend stores/services.
4. PROXY: Is gRPC-Web proxy configured and matching backend ports?
   Check nginx config matches backend port, grpc-web layer present.
5. CONFIG: Are env vars consistent across layers (.env, docker-compose, nginx)?
   Cross-reference DATABASE_URL, ports, API URLs between configs.
6. MODULE SYSTEM: Are modules activated at runtime? Hook system wired?
   Check if module trait/interface exists but activation logic is TODO.
7. CROSS-SERVICE: Do services reference each other correctly? Shared types match?
   Check proto definitions match Rust/TS implementations.

For each gap, create a task with:
- type: "integration"
- domain: the PRIMARY layer to fix (rust, svelte, config, proto)
- files: ALL files involved (cross-layer list)
- wsjf_score: 9-10 (integration = highest priority, blocks everything)
- context.integration_type: one of "bootstrap|api_connection|migration|proxy|config|module_wiring|proto_gen"

Task types: integration only.""",
        "task_types": ["integration"],
        "detector": "detect_integration_gaps",
    },
    "missing": {
        "name": "MISSING",
        "description": "Tests referencing non-existent modules - TDD RED phase",
        "focus": """Focus on MISSING IMPLEMENTATIONS only:

This is TRUE TDD - tests already exist but the code they test doesn't.
Your job is to find these tests and create tasks to IMPLEMENT the missing code.

1. Find test files that import modules that don't exist
2. Find test files that reference classes/functions not yet implemented
3. Find mock objects that should be real implementations
4. Find interface definitions without concrete implementations

For each missing implementation, analyze:
- What the test expects (interface, methods, behavior)
- Where the implementation should live
- What minimal code would make the test pass

DO NOT suggest deleting tests - implement the code they need!
Task types: implement only.""",
        "task_types": ["implement"],
        "detector": "detect_missing_implementations",  # Special handler
    },
    "ui": {
        "name": "UI",
        "description": "UI/UX audit: design tokens, Figma compliance, WCAG accessibility",
        "focus": """Focus on UI/UX QUALITY only:

DESIGN SYSTEM VALIDATION:
1. Hardcoded colors instead of CSS tokens (DSV-001)
2. Hardcoded spacing values (DSV-002)
3. Hardcoded fonts (DSV-003)
4. Hardcoded border-radius (DSV-004)
5. Hardcoded shadows (DSV-005)
6. Tailwind arbitrary colors (DSV-006)

FIGMA COMPLIANCE:
1. Color mismatches vs Figma specs (FIG-001)
2. Spacing mismatches (FIG-002)
3. Font-size mismatches (FIG-003)
4. Border-radius mismatches (FIG-004)
5. Orphaned components not in Figma (FIG-005)

WCAG 2.1 AA ACCESSIBILITY:
1. Interactive elements without keyboard access (A11Y-001)
2. Color contrast below 4.5:1 (A11Y-002)
3. Icon buttons without aria-label (A11Y-003)
4. Modals without focus trap (A11Y-004)
5. Images without alt text (A11Y-005)
6. Touch targets below 44px (A11Y-006)

UX ANTI-PATTERNS:
1. Forms without error states (UXF-001)
2. Inputs without labels (UXF-002)
3. Submit without loading state (UXF-003)
4. Lists without empty state (UXL-001)
5. Async content without loader (UXL-002)
6. Missing error boundaries (UXL-003)

For each issue, create a task with:
- type: "ui-token-fix", "ui-figma-fix", "ui-a11y-fix", or "ui-ux-fix"
- domain: svelte, php, or css depending on project frontend
- files: Component file path
- context.wcag_criterion: If accessibility (e.g., "2.1.1 Keyboard")
- context.figma_node: If Figma discrepancy

PRIORITY (WSJF):
- ui-a11y-fix: 12-15 (legal risk, ADA/RGAA compliance)
- ui-token-fix: 8-12 (design consistency)
- ui-ux-fix: 8-11 (user experience)
- ui-figma-fix: 6-10 (designer alignment)

Task types: ui-token-fix, ui-figma-fix, ui-a11y-fix, ui-ux-fix only.""",
        "task_types": ["ui-token-fix", "ui-figma-fix", "ui-a11y-fix", "ui-ux-fix"],
    },
}

# Default mode runs all types
BRAIN_MODES["all"] = {
    "name": "ALL",
    "description": "Complete analysis (all modes)",
    "focus": None,  # No focus restriction
    "task_types": ["fix", "feature", "refactor", "test", "security"],
}


# ============================================================================
# MISSING IMPLEMENTATIONS DETECTOR (TDD RED Phase)
# ============================================================================

import re
from dataclasses import dataclass
from typing import Tuple


@dataclass
class MissingImplementation:
    """A test that references code that doesn't exist yet."""
    test_file: str
    missing_module: str
    expected_interface: str
    domain: str
    priority: int = 100  # High priority - blocks other tests


def detect_missing_implementations(project: ProjectConfig) -> List[Dict[str, Any]]:
    """
    Scan test files to find imports/references to non-existent modules.

    This is TRUE TDD - the tests exist, the code doesn't.
    Returns tasks to IMPLEMENT the missing code.
    """
    log("🔍 Scanning for missing implementations (TDD RED phase)...")

    missing = []

    # Known external packages to SKIP (not things we should implement)
    SKIP_PATTERNS = {
        "swift": {
            # System frameworks
            "Foundation", "UIKit", "SwiftUI", "Combine", "XCTest",
            "CoreData", "CoreGraphics", "CoreFoundation", "Security",
            "LocalAuthentication", "CryptoKit", "Network", "WebKit",
            "AVFoundation", "MediaPlayer", "Photos", "EventKit",
            "StoreKit", "CloudKit", "GameKit", "SpriteKit", "SceneKit",
            "Metal", "MetalKit", "Vision", "NaturalLanguage", "CoreML",
            "ARKit", "MapKit", "HealthKit", "HomeKit", "WatchKit",
            "Intents", "UserNotifications", "MessageUI", "SafariServices",
            "SystemConfiguration", "DeviceCheck", "AppTrackingTransparency",
            "CoreBluetooth", "CoreLocation", "CoreMotion", "CoreTelephony",
            "CoreServices", "CoreText", "CoreImage", "CoreMedia", "CoreAudio",
            "QuartzCore", "Dispatch", "ObjectiveC", "Darwin", "os", "os_log",
        },
        "kotlin": {
            # Standard library & Android
            "kotlin", "java", "javax", "android", "androidx",
            "kotlinx", "org.junit", "io.mockk", "org.mockito",
            "com.google", "io.grpc", "okhttp3", "retrofit2",
        },
        "java": {
            "java", "javax", "org.junit", "org.mockito", "org.hamcrest",
            "android", "androidx", "com.google",
        },
        "typescript": {
            # Node modules patterns - if starts with these, skip
            "node_modules", "undici", "@types", "@jest", "@testing-library",
            "vitest", "jest", "mocha", "chai", "sinon", "ajv",
        },
        "python": {
            # Standard library
            "os", "sys", "re", "json", "typing", "unittest", "pytest",
            "pathlib", "datetime", "collections", "itertools", "functools",
            "asyncio", "logging", "subprocess", "threading", "multiprocessing",
        },
        "rust": {
            # Standard library (std::) - we only look at crate:: and super::
            "std", "core", "alloc",
        },
    }

    def should_skip_import(module_path: str, lang: str) -> bool:
        """Check if an import should be skipped (external package)."""
        skip_set = SKIP_PATTERNS.get(lang, set())

        # For languages with package prefixes
        if lang in ("kotlin", "java", "python"):
            prefix = module_path.split(".")[0]
            for skip in skip_set:
                if module_path.startswith(skip):
                    return True

        elif lang == "swift":
            # Swift imports are single words for frameworks
            if module_path in skip_set:
                return True

        elif lang == "typescript":
            # Skip node_modules paths
            if "node_modules" in module_path:
                return True
            # Skip if starts with known external packages
            for skip in skip_set:
                if module_path.startswith(skip) or skip in module_path:
                    return True

        elif lang == "rust":
            # We only capture crate:: and super:: imports, std is not captured
            pass

        return False

    # Language-specific patterns for imports
    import_patterns = {
        ".kt": [
            (r'import\s+([\w.]+)', "kotlin"),  # import com.foo.Bar
        ],
        ".java": [
            (r'import\s+([\w.]+)', "java"),
        ],
        ".ts": [
            (r"from\s+['\"]([^'\"]+)['\"]", "typescript"),  # from './module'
            (r"import\s+['\"]([^'\"]+)['\"]", "typescript"),
        ],
        ".tsx": [
            (r"from\s+['\"]([^'\"]+)['\"]", "typescript"),
            (r"import\s+['\"]([^'\"]+)['\"]", "typescript"),
        ],
        ".rs": [
            (r'use\s+crate::([\w:]+)', "rust"),  # use crate::module::Type
            (r'use\s+super::([\w:]+)', "rust"),
            (r'mod\s+(\w+);', "rust"),  # mod module_name;
        ],
        ".py": [
            (r'from\s+([\w.]+)\s+import', "python"),  # from module import
            (r'import\s+([\w.]+)', "python"),
        ],
        ".swift": [
            (r'import\s+(\w+)', "swift"),
        ],
    }

    # Find test directories
    test_patterns = ["**/test/**", "**/tests/**", "**/*Test*", "**/*_test*", "**/*spec*"]

    for domain_name, domain_config in project.domains.items():
        paths = domain_config.get("paths", [])
        extensions = domain_config.get("extensions", [])

        for path_str in paths:
            domain_path = project.root_path / path_str
            if not domain_path.exists():
                continue

            for ext in extensions:
                if ext not in import_patterns:
                    continue

                # Find test files
                for test_file in domain_path.rglob(f"*[Tt]est*{ext}"):
                    if "node_modules" in str(test_file) or "target" in str(test_file):
                        continue

                    try:
                        content = test_file.read_text(errors='ignore')
                        rel_path = str(test_file.relative_to(project.root_path))

                        # Check each import pattern
                        for pattern, lang in import_patterns[ext]:
                            imports = re.findall(pattern, content)

                            for imp in imports:
                                # Skip external packages (system frameworks, node_modules)
                                if should_skip_import(imp, lang):
                                    continue

                                # Check if the imported module exists
                                if not _module_exists(project, imp, lang, test_file):
                                    # Extract expected interface from test
                                    interface = _extract_expected_interface(content, imp)

                                    missing.append({
                                        "test_file": rel_path,
                                        "missing_module": imp,
                                        "expected_interface": interface,
                                        "domain": domain_name,
                                        "lang": lang,
                                    })
                    except Exception as e:
                        continue

    log(f"Found {len(missing)} missing implementations")

    # Convert to tasks
    tasks = []
    seen_modules = set()

    for m in missing:
        # Deduplicate by module
        if m["missing_module"] in seen_modules:
            continue
        seen_modules.add(m["missing_module"])

        tasks.append({
            "type": "implement",
            "domain": m["domain"],
            "description": f"Implement {m['missing_module']} to satisfy test: {m['test_file']}",
            "files": [m["test_file"]],
            "context": {
                "tdd_phase": "RED",
                "test_file": m["test_file"],
                "missing_module": m["missing_module"],
                "expected_interface": m["expected_interface"],
                "lang": m["lang"],
                "approach": "Test exists - implement the code to make it pass",
            },
            "wsjf_score": 15.0,  # High priority - unblocks tests
            "priority": 100,
        })

    return tasks


def _module_exists(project: ProjectConfig, module_path: str, lang: str, test_file: Path) -> bool:
    """Check if a module/import actually exists in the project."""

    if lang == "kotlin" or lang == "java":
        # Convert package path to file path: com.foo.Bar -> com/foo/Bar.kt
        file_path = module_path.replace(".", "/")
        for ext in [".kt", ".java"]:
            # Check in src/main and src/test
            for src_dir in ["src/main/java", "src/main/kotlin", "src"]:
                full_path = project.root_path / src_dir / f"{file_path}{ext}"
                if full_path.exists():
                    return True
        return False

    elif lang == "rust":
        # use crate::module::Type -> check for module.rs or module/mod.rs
        parts = module_path.replace("::", "/").split("/")
        # Try relative to the crate root
        crate_root = test_file.parent
        while crate_root != project.root_path:
            if (crate_root / "Cargo.toml").exists():
                break
            crate_root = crate_root.parent

        src_dir = crate_root / "src"
        if src_dir.exists():
            # Check for module.rs
            mod_path = src_dir / "/".join(parts[:-1]) / f"{parts[-1]}.rs"
            if mod_path.exists():
                return True
            # Check for module/mod.rs
            mod_path = src_dir / "/".join(parts) / "mod.rs"
            if mod_path.exists():
                return True
            # Check in lib.rs or main.rs (might be inline module)
            for root_file in [src_dir / "lib.rs", src_dir / "main.rs"]:
                if root_file.exists():
                    content = root_file.read_text(errors='ignore')
                    # Simple check: is the module name defined?
                    if f"mod {parts[0]}" in content or f"pub mod {parts[0]}" in content:
                        return True
        return False

    elif lang == "typescript":
        # Relative imports: ./module or ../module
        if module_path.startswith("."):
            # Relative to test file
            base = test_file.parent
            resolved = (base / module_path).resolve()
            for ext in [".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.tsx"]:
                if Path(f"{resolved}{ext}").exists():
                    return True
            return False
        else:
            # Node module or alias - assume exists if not starting with project prefix
            # This is a heuristic; could check tsconfig paths
            return True

    elif lang == "python":
        # from mypackage.module import -> check mypackage/module.py
        file_path = module_path.replace(".", "/")
        for ext in [".py", "/__init__.py"]:
            full_path = project.root_path / f"{file_path}{ext}"
            if full_path.exists():
                return True
        return False

    elif lang == "swift":
        # Swift imports are usually frameworks/modules
        # Check for local source files
        for swift_file in project.root_path.rglob(f"**/{module_path}.swift"):
            if "Pods" not in str(swift_file) and "Carthage" not in str(swift_file):
                return True
        return False

    return True  # Default: assume exists


def _extract_expected_interface(test_content: str, module_name: str) -> str:
    """Extract what interface the test expects from the missing module."""

    # Find usages of the module in the test
    class_name = module_name.split(".")[-1].split("::")[-1]

    # Look for method calls, constructor calls, etc.
    patterns = [
        rf'{class_name}\s*\([^)]*\)',  # Constructor: ClassName(args)
        rf'{class_name}\.(\w+)\s*\(',  # Method calls: instance.method(
        rf'mock[A-Z]\w*{class_name}',  # Mock objects
        rf'@Mock.*{class_name}',       # Mock annotations
    ]

    usages = []
    for pattern in patterns:
        matches = re.findall(pattern, test_content, re.MULTILINE)
        usages.extend(matches)

    if usages:
        return f"Expected methods/constructors: {', '.join(set(usages)[:10])}"

    return "Interface to be determined from test file analysis"


# ============================================================================
# INTEGRATION GAP DETECTOR (Deterministic pre-checks)
# ============================================================================

def detect_integration_gaps(project: ProjectConfig) -> List[Dict[str, Any]]:
    """
    Detect integration gaps between layers WITHOUT LLM.

    Deterministic checks:
    - Server entry point empty/missing
    - Frontend using mocks instead of real API calls
    - Proto TS clients not generated
    - Config inconsistencies
    """
    log("🔗 Scanning for integration gaps...")

    tasks = []
    root = project.root_path

    # 1. SERVER BOOTSTRAP: Check main.rs / server entry points
    for pattern in ["**/main.rs", "**/server.rs", "**/bin/*.rs"]:
        for f in root.glob(pattern):
            try:
                content = f.read_text()
                # Empty or stub main.rs
                if len(content.strip()) < 50 or content.strip() == "fn main() {}":
                    tasks.append({
                        "type": "integration",
                        "domain": "rust",
                        "description": f"[INT-BOOT] Fix server bootstrap: {f.relative_to(root)} is empty/stub - must mount all gRPC services",
                        "files": [str(f.relative_to(root))],
                        "wsjf_score": 10,
                        "severity": "critical",
                        "context": {"integration_type": "bootstrap"},
                    })
            except Exception:
                pass

    # 2. FRONTEND MOCKS: Search for mock/hardcoded data in frontend
    mock_files = []
    for ext in ["*.ts", "*.svelte"]:
        for pattern_dir in ["frontend", "src", "web"]:
            for f in root.glob(f"**/{pattern_dir}/**/{ext}"):
                try:
                    content = f.read_text()
                    if any(kw in content.lower() for kw in ["mockstations", "mockdata", "hardcoded", "mock_", "fakeclient"]):
                        mock_files.append(str(f.relative_to(root)))
                except Exception:
                    pass

    if mock_files:
        tasks.append({
            "type": "integration",
            "domain": "svelte" if any(".svelte" in f for f in mock_files) else "typescript",
            "description": f"[INT-API] Replace mock/hardcoded data with real gRPC API calls in {len(mock_files)} frontend files",
            "files": mock_files[:10],
            "wsjf_score": 9,
            "severity": "high",
            "context": {"integration_type": "api_connection"},
        })

    # 3. PROTO TS CLIENTS: Check if proto exists but no TS client generated
    proto_files = list(root.glob("**/*.proto"))
    ts_client_files = list(root.glob("**/grpc-client/**/*.ts")) + list(root.glob("**/grpc/**/*.client.ts"))
    if proto_files and not ts_client_files:
        tasks.append({
            "type": "integration",
            "domain": "proto",
            "description": f"[INT-PROTO] Generate TypeScript gRPC-Web clients from {len(proto_files)} .proto files (protoc-gen-es)",
            "files": [str(f.relative_to(root)) for f in proto_files[:5]],
            "wsjf_score": 9,
            "severity": "high",
            "context": {"integration_type": "proto_gen"},
        })

    # 4. CONFIG: Check .env consistency
    env_files = list(root.glob("**/.env")) + list(root.glob("**/.env.*"))
    env_files = [f for f in env_files if "node_modules" not in str(f) and ".git" not in str(f)]
    if len(env_files) >= 2:
        # Check for DATABASE_URL consistency
        db_urls = set()
        for ef in env_files:
            try:
                for line in ef.read_text().splitlines():
                    if line.startswith("DATABASE_URL"):
                        db_urls.add(line.split("=", 1)[1].strip().strip('"'))
            except Exception:
                pass
        if len(db_urls) > 2:  # More than dev/docker variants = suspicious
            tasks.append({
                "type": "integration",
                "domain": "config",
                "description": f"[INT-CFG] Inconsistent DATABASE_URL across {len(env_files)} .env files ({len(db_urls)} variants)",
                "files": [str(f.relative_to(root)) for f in env_files],
                "wsjf_score": 8,
                "severity": "medium",
                "context": {"integration_type": "config"},
            })

    # 5. NGINX/PROXY: Check if backend port matches proxy config
    nginx_files = list(root.glob("**/nginx*.conf")) + list(root.glob("**/grpc-web.conf"))
    if nginx_files:
        # Just flag if nginx exists but docker-compose doesn't reference it
        compose_files = list(root.glob("**/docker-compose*.yml")) + list(root.glob("**/docker-compose*.yaml"))
        nginx_in_compose = False
        for cf in compose_files:
            try:
                if "nginx" in cf.read_text().lower():
                    nginx_in_compose = True
                    break
            except Exception:
                pass
        if not nginx_in_compose and compose_files:
            tasks.append({
                "type": "integration",
                "domain": "config",
                "description": f"[INT-PROXY] Nginx config exists but not referenced in docker-compose",
                "files": [str(f.relative_to(root)) for f in nginx_files + compose_files],
                "wsjf_score": 8,
                "severity": "medium",
                "context": {"integration_type": "proxy"},
            })

    log(f"🔗 Found {len(tasks)} integration gaps")
    return tasks


# ============================================================================
# FILE COLLECTOR
# ============================================================================

def collect_project_files(project: ProjectConfig, max_chars: int = 500000) -> str:
    """
    Collect all project files as a single context string.

    This becomes the RLM context that the LLM can programmatically examine.
    """
    files_content = []
    total_chars = 0

    # Patterns to exclude
    exclude_patterns = {
        '.git', 'node_modules', 'target', '__pycache__', '.pyc',
        'dist', 'build', '.next', '.svelte-kit', 'coverage',
        '.DS_Store', '.env', 'Thumbs.db', '*.lock', 'package-lock.json'
    }

    def should_exclude(path: Path) -> bool:
        for pattern in exclude_patterns:
            if pattern in str(path):
                return True
        return False

    # Collect files from each domain
    for domain_name, domain_config in project.domains.items():
        paths = domain_config.get("paths", [])
        extensions = domain_config.get("extensions", [])

        for path_str in paths:
            domain_path = project.root_path / path_str
            if not domain_path.exists():
                continue

            for ext in extensions:
                for file in domain_path.rglob(f"*{ext}"):
                    if should_exclude(file):
                        continue

                    try:
                        content = file.read_text(errors='ignore')
                        rel_path = str(file.relative_to(project.root_path))

                        # Limit per file
                        if len(content) > 10000:
                            content = content[:10000] + "\n... [truncated]"

                        file_entry = f"\n{'='*60}\nFILE: {rel_path}\n{'='*60}\n{content}\n"

                        if total_chars + len(file_entry) > max_chars:
                            break

                        files_content.append(file_entry)
                        total_chars += len(file_entry)

                    except Exception as e:
                        continue

    log(f"Collected {len(files_content)} files ({total_chars} chars)")
    return "".join(files_content)


# ============================================================================
# RLM BRAIN
# ============================================================================

class RLMBrain:
    """
    Brain powered by Recursive Language Models (MIT CSAIL) with MCP.

    Uses `copilot` CLI (or `claude`) and `opencode` with MCP tools to navigate
    and analyze the entire project codebase.

    COST TIER ARCHITECTURE:
      depth=0: Sonnet 4.6 via `copilot` + MCP ($$)
      depth=1-2: MiniMax M2.5 via `opencode` + MCP ($$)
      depth=3: Qwen 30B local (free fallback)
    """

    def __init__(self, project_name: str = None, cli_tool: str = "copilot"):
        """
        Initialize Brain for a project.

        Args:
            project_name: Project name from projects/*.yaml
            cli_tool: CLI tool to use for main analysis ("copilot" or "claude")
        """
        self.project = get_project(project_name)
        self.task_store = TaskStore()
        self.max_depth = 3
        self.current_depth = 0
        self.cli_tool = cli_tool  # "copilot" (Sonnet 4.6) or "claude" (Opus 4.5)

        log(f"Brain initialized for project: {self.project.name}")
        log(f"Root: {self.project.root_path}")
        log(f"Domains: {list(self.project.domains.keys())}")
        log(f"CLI tool: {self.cli_tool} (Sonnet 4.6)" if cli_tool == "copilot" else f"CLI tool: claude (Opus 4.5)")
        log(f"Cost tiers: {self.cli_tool}(d0) → MiniMax(d1-2) → Qwen(d3)")

    async def run(
        self,
        vision_prompt: str = None,
        domains: List[str] = None,
        deep_analysis: bool = True,
        mode: str = "all",
        iterative: bool = False,
        max_iterations: int = 30,
    ) -> List[Task]:
        """
        Run DEEP RECURSIVE Brain analysis with MCP.

        Uses `claude` CLI with MCP tools for deep project navigation.
        Sub-analyses delegated to `opencode` with MiniMax.

        Args:
            vision_prompt: Optional focus prompt for analysis
            domains: Specific domains to analyze (default: all)
            deep_analysis: If True, use full recursive depth
            mode: Brain mode (fix|vision|security|perf|refactor|test|migrate|debt|all)

        Returns:
            List of created Task objects
        """
        # Resolve mode
        mode_config = BRAIN_MODES.get(mode, BRAIN_MODES["all"])
        mode_name = mode_config["name"]

        log("═" * 70)
        log(f"🧠 STARTING BRAIN ANALYSIS [{mode_name}] WITH MCP")
        log("═" * 70)
        log(f"Project: {self.project.name}")
        log(f"Domains: {domains or list(self.project.domains.keys())}")
        log(f"Deep analysis: {deep_analysis}")
        log(f"Mode: {mode_name}")

        # SPECIAL: "missing" mode uses deterministic detector, not LLM
        if mode == "missing":
            return await self._run_missing_mode()

        # SPECIAL: "integrator" mode uses deterministic detector + LLM deep analysis
        if mode == "integrator":
            return await self._run_integrator_mode()

        # SPECIAL: "refactor" mode uses metrics-based analyzer
        if mode == "refactor":
            return await self._run_refactor_mode(domains)

        # 1. Load project context (RAG "Big Picture")
        log("Loading project context...")
        try:
            project_ctx = ProjectContext(self.project.id)
            # Check if context exists, refresh if older than 1 hour or missing
            state = project_ctx.get_category('state')
            if not state or (datetime.now() - datetime.fromisoformat(state.updated_at)).seconds > 3600:
                log("Context stale or missing, refreshing...")
                project_ctx.refresh()
            context_summary = project_ctx.get_summary(max_chars=12000)
            log(f"Context loaded: {len(context_summary)} chars")
        except Exception as e:
            log(f"Context load failed: {e}, using vision doc only", "WARN")
            context_summary = ""

        # 2. Load vision document (legacy, included in context but kept for compatibility)
        vision_content = self.project.get_vision_content() or ""
        log(f"Vision doc: {len(vision_content)} chars")

        # 4. Combine mode focus with user prompt
        combined_focus = vision_prompt or ""
        if mode_config.get("focus"):
            combined_focus = f"{mode_config['focus']}\n\n{combined_focus}" if combined_focus else mode_config["focus"]

        # 5. Build the analysis prompt with full context
        prompt = self._build_analysis_prompt(
            vision_content,
            combined_focus,
            domains,
            deep_analysis,
            project_context=context_summary,
        )

        # 3. Run analysis: iterative (RLM loop) or single-shot
        if iterative:
            log("─" * 70)
            log(f"🔄 Running ITERATIVE RLM analysis (max {max_iterations} iterations)...")
            log("─" * 70)

            tasks = await self._run_iterative(
                focus=combined_focus,
                context_summary=context_summary,
                vision_content=vision_content,
                mode_config=mode_config,
                domains=domains,
                max_iterations=max_iterations,
            )
            log(f"Iterative analysis produced {len(tasks)} raw tasks")
        else:
            # Single-shot analysis via configured CLI tool (copilot or claude)
            log("─" * 70)
            log(f"🔄 Running analysis via `{self.cli_tool}` CLI + MCP...")
            log("─" * 70)

            response = await self._call_llm(prompt)

            if not response:
                log(f"❌ {self.cli_tool} analysis failed", "ERROR")
                return []

            log(f"✅ Analysis complete: {len(response)} chars")

            # Parse tasks from response
            tasks = self._parse_tasks(response)
            log(f"Parsed {len(tasks)} tasks")

        # 5. Validate tasks
        validated_tasks = self._validate_tasks(tasks)
        log(f"Validated {len(validated_tasks)} tasks")

        # 5b. CoVe verification (Chain-of-Verification - arxiv:2309.11495)
        validated_tasks = await self._cove_verify_tasks(validated_tasks)

        # 6. If deep analysis, run sub-analyses with MiniMax
        if deep_analysis and validated_tasks:
            validated_tasks = await self._deep_analyze_tasks(validated_tasks)

        # 7. Save tasks to store (with unique IDs based on content hash)
        import hashlib
        created_tasks = []
        skipped_existing = 0
        for idx, task_dict in enumerate(validated_tasks):
            try:
                # Generate unique ID from content hash (avoids duplicates across runs)
                desc = task_dict.get("description", "")[:100]
                domain = task_dict.get("domain", "unknown")
                files_str = ",".join(sorted(task_dict.get("files", [])[:3]))
                content_hash = hashlib.md5(f"{desc}|{domain}|{files_str}".encode()).hexdigest()[:8]
                task_id = f"{self.project.name}-{domain}-{content_hash}"

                # Check if task already exists (avoid duplicates)
                existing = self.task_store.get_task(task_id)
                if existing:
                    skipped_existing += 1
                    continue

                task_obj = Task(
                    id=task_id,
                    project_id=self.project.id,
                    type=task_dict.get("type", "fix"),
                    domain=domain,
                    description=task_dict.get("description", ""),
                    files=task_dict.get("files", []),
                    context=task_dict,
                    wsjf_score=task_dict.get("wsjf_score", 5.0),
                )
                self.task_store.create_task(task_obj)
                created_tasks.append(task_obj)
            except Exception as e:
                log(f"Failed to create task: {e}", "ERROR")

        if skipped_existing > 0:
            log(f"Skipped {skipped_existing} existing tasks (already in store)")

        log(f"Created {len(created_tasks)} tasks in store")

        # 8. Check for phase rotation (after analysis completes)
        await self._check_phase_rotation(mode)

        log("═" * 70)
        log("🧠 BRAIN ANALYSIS COMPLETE")
        log("═" * 70)

        return created_tasks

    async def _check_phase_rotation(self, current_mode: str):
        """
        Check if phase rotation should occur.

        Phase rotation logic (from CLAUDE.md):
        1. FEATURES (vision) → all deployed → move to FIXES
        2. FIXES (fix) → all deployed → move to REFACTOR
        3. REFACTOR → all deployed → loop back to FEATURES

        Rotation only happens when:
        - auto_rotate is enabled
        - All tasks of the current phase type are deployed
        """
        # Check if auto-rotation is enabled
        if not self.project.is_auto_rotate_enabled():
            log("Phase auto-rotation disabled")
            return

        current_phase = self.project.get_brain_phase()
        phase_mode = self.project.get_brain_mode()

        # Only check rotation if we're in the mode matching our phase
        if current_mode != phase_mode and current_mode != "all":
            return

        # Get task types for current phase
        phase_task_types = {
            "features": ["feature"],
            "fixes": ["fix", "security"],
            "refactor": ["refactor"]
        }
        task_types = phase_task_types.get(current_phase, [])

        if not task_types:
            return

        # Check if all tasks of this phase type are deployed
        all_deployed = self._check_all_tasks_deployed(task_types)

        if all_deployed:
            next_phase = self.project.get_next_phase()
            log("─" * 70)
            log(f"🔄 PHASE ROTATION: {current_phase.upper()} → {next_phase.upper()}")
            log("─" * 70)
            log(f"All {current_phase} tasks deployed. Moving to {next_phase} phase.")

            if self.project.set_brain_phase(next_phase):
                log(f"✅ Phase updated to: {next_phase}")
                log(f"Next Brain run will use --mode {self.project.PHASE_MODE_MAP.get(next_phase)}")
            else:
                log("❌ Failed to update phase in config", "WARN")
        else:
            # Count pending tasks
            pending_count = self._count_pending_tasks(task_types)
            log(f"Phase {current_phase}: {pending_count} tasks still pending/in-progress")

    def _check_all_tasks_deployed(self, task_types: List[str]) -> bool:
        """Check if all tasks of given types are deployed"""
        try:
            from core.task_store import TaskStore
            store = TaskStore()

            for task_type in task_types:
                # Get tasks for this project and type
                pending = store.get_tasks_by_status(
                    self.project.id,
                    ["pending", "locked", "tdd_in_progress", "code_written", "build_failed", "tdd_failed"]
                )
                # Filter by type
                pending_of_type = [t for t in pending if t.type == task_type]
                if pending_of_type:
                    return False
            return True
        except Exception as e:
            log(f"Error checking task status: {e}", "WARN")
            return False

    def _count_pending_tasks(self, task_types: List[str]) -> int:
        """Count pending/in-progress tasks of given types"""
        try:
            from core.task_store import TaskStore
            store = TaskStore()
            count = 0
            for task_type in task_types:
                pending = store.get_tasks_by_status(
                    self.project.id,
                    ["pending", "locked", "tdd_in_progress", "code_written", "build_failed", "tdd_failed"]
                )
                count += len([t for t in pending if t.type == task_type])
            return count
        except Exception:
            return -1

    async def _run_missing_mode(self) -> List[Task]:
        """
        Run the MISSING IMPLEMENTATIONS mode (TDD RED phase).

        This is a deterministic detector - no LLM needed.
        Scans test files for imports that reference non-existent modules,
        then creates tasks to IMPLEMENT those modules.

        TRUE TDD: Tests exist first, code comes second.
        """
        log("═" * 70)
        log("🔴 RUNNING MISSING IMPLEMENTATIONS DETECTOR (TDD RED PHASE)")
        log("═" * 70)
        log("This is TRUE TDD - tests exist but code doesn't.")
        log("Creating tasks to IMPLEMENT the missing code.")

        # 1. Run the deterministic detector
        task_dicts = detect_missing_implementations(self.project)

        if not task_dicts:
            log("✅ No missing implementations found - all test imports resolved!")
            return []

        log(f"Found {len(task_dicts)} missing implementations to create")

        # 2. Save tasks to store
        created_tasks = []
        for idx, task_dict in enumerate(task_dicts):
            try:
                task_id = f"{self.project.name}-missing-{idx:04d}"

                # Check if task already exists (avoid duplicates)
                existing = self.task_store.get_task(task_id)
                if existing:
                    log(f"  Skip existing: {task_id}")
                    continue

                task_obj = Task(
                    id=task_id,
                    project_id=self.project.id,
                    type="implement",
                    domain=task_dict.get("domain", "unknown"),
                    description=task_dict.get("description", ""),
                    files=task_dict.get("files", []),
                    context=task_dict.get("context", {}),
                    wsjf_score=task_dict.get("wsjf_score", 15.0),  # High priority
                    priority=task_dict.get("priority", 100),
                )
                self.task_store.create_task(task_obj)
                created_tasks.append(task_obj)
                log(f"  ✅ Created: {task_obj.description[:60]}...")
            except Exception as e:
                log(f"  ❌ Failed to create task: {e}", "ERROR")

        log("─" * 70)
        log(f"Created {len(created_tasks)} IMPLEMENT tasks")
        log("These tasks will make the tests pass by implementing the missing code.")
        log("═" * 70)

        return created_tasks

    async def _run_integrator_mode(self) -> List[Task]:
        """
        Run INTEGRATION GAP DETECTION mode.

        Phase 1: Deterministic detector (fast, no LLM)
        Phase 2: LLM deep analysis for subtle integration issues
        """
        log("═" * 70)
        log("🔗 RUNNING INTEGRATION GAP DETECTOR")
        log("═" * 70)
        log("Phase 1: Deterministic checks (bootstrap, mocks, proto, config)")
        log("Phase 2: LLM deep analysis (cross-layer wiring)")

        # Phase 1: Deterministic detector
        task_dicts = detect_integration_gaps(self.project)

        # Phase 2: LLM deep analysis (uses standard brain flow with integrator focus)
        mode_config = BRAIN_MODES["integrator"]
        log(f"Phase 2: LLM analysis with focus on integration gaps...")

        try:
            # Build prompt for LLM
            project_ctx = ProjectContext(self.project.id)
            context_summary = project_ctx.get_summary(max_chars=8000)
            vision_content = self.project.get_vision_content() or ""

            prompt = f"""You are an INTEGRATION analyst for the {self.project.display_name} project.

PROJECT ROOT: {self.project.root_path}

VISION:
{vision_content[:3000]}

PROJECT CONTEXT:
{context_summary[:5000]}

DETERMINISTIC GAPS ALREADY FOUND ({len(task_dicts)}):
{json.dumps(task_dicts, indent=2)[:2000]}

{mode_config['focus']}

IMPORTANT:
- Do NOT duplicate the deterministic gaps already found above
- Focus on SUBTLE integration issues the deterministic check missed
- Look for semantic mismatches (types don't match between layers, missing middleware, etc.)
- Use MCP tools (lrm_locate, lrm_summarize) to explore the actual codebase

Output JSON array of tasks. Each task: {{"type": "integration", "domain": "...", "description": "[INT-xxx] ...", "files": [...], "wsjf_score": 9, "context": {{"integration_type": "..."}}}}
"""
            output = await self._call_llm(prompt)
            if output:
                llm_tasks = self._parse_tasks(output)
                if llm_tasks:
                    log(f"Phase 2: LLM found {len(llm_tasks)} additional integration gaps")
                    task_dicts.extend(llm_tasks)
        except Exception as e:
            log(f"Phase 2 LLM analysis failed (continuing with deterministic results): {e}", "WARN")

        if not task_dicts:
            log("✅ No integration gaps found - all layers connected!")
            return []

        log(f"Total integration gaps: {len(task_dicts)}")

        # Save tasks to store
        created_tasks = []
        for idx, task_dict in enumerate(task_dicts):
            try:
                import hashlib
                desc = task_dict.get("description", "")
                content_hash = hashlib.md5(desc.encode()).hexdigest()[:8]
                task_id = f"{self.project.name}-int-{content_hash}"

                existing = self.task_store.get_task(task_id)
                if existing:
                    log(f"  Skip existing: {task_id}")
                    continue

                task_obj = Task(
                    id=task_id,
                    project_id=self.project.id,
                    type="integration",
                    domain=task_dict.get("domain", "config"),
                    description=desc,
                    files=task_dict.get("files", []),
                    wsjf_score=task_dict.get("wsjf_score", 10),
                    severity=task_dict.get("severity", "critical"),
                    priority=100,  # Integration = highest priority
                )
                task_obj.context = task_dict.get("context", {})
                self.task_store.create_task(task_obj)
                created_tasks.append(task_obj)
                log(f"  ✅ Created: {task_id} — {desc[:80]}")
            except Exception as e:
                log(f"  ❌ Failed: {e}", "ERROR")

        log("─" * 70)
        log(f"Created {len(created_tasks)} INTEGRATION tasks (WSJF=10, highest priority)")
        log("These tasks wire layers together to make the product functional.")
        log("═" * 70)

        return created_tasks

    async def _run_refactor_mode(self, domains: List[str] = None) -> List[Task]:
        """
        Run EVIDENCE-BASED REFACTORING mode.

        Uses metrics + anti-patterns + GOF patterns to generate refactor tasks.
        Each task includes:
        - Metric violations (cyclomatic, LOC, params, etc.)
        - Anti-pattern detected (God Class, Feature Envy, etc.)
        - Suggested GOF pattern to apply
        - SOLID violation if any
        """
        log("═" * 70)
        log("🔧 RUNNING EVIDENCE-BASED REFACTORING ANALYSIS")
        log("═" * 70)
        log("Phase 1: Metrics collection (deterministic)")
        log("Phase 2: Anti-pattern detection (LLM + deterministic)")
        log("Phase 3: GOF pattern suggestions")
        log("Phase 4: SOLID compliance check")

        from core.refactor_analyzer import RefactorAnalyzer

        analyzer = RefactorAnalyzer(self.project)
        created_tasks = []

        # Get domains to analyze
        target_domains = domains or list(self.project.domains.keys())

        for domain in target_domains:
            domain_config = self.project.domains.get(domain)
            if not domain_config:
                continue

            log(f"\n📁 Analyzing domain: {domain}")

            # Get paths for this domain
            paths = domain_config.get("paths", [])
            extensions = domain_config.get("extensions", [])

            for path in paths:
                full_path = os.path.join(self.project.root_path, path)
                if not os.path.exists(full_path):
                    continue

                log(f"  Scanning: {path}")

                # Analyze files in this path
                try:
                    reports = await analyzer.analyze_directory(full_path, extensions)

                    for report in reports:
                        # Only create tasks for files with issues
                        if report.priority_score < 3:
                            continue

                        # Generate task
                        task_id = f"refactor-{domain}-{hash(report.file_path) & 0xFFFFFF:06x}"

                        # Check if task exists
                        existing = self.task_store.get_task(task_id)
                        if existing:
                            log(f"    Skip existing: {task_id}")
                            continue

                        # Build description with metrics evidence
                        desc_parts = [f"[REF-{domain.upper()}] Refactor {Path(report.file_path).name}"]

                        # Add failed metrics
                        failed_metrics = [m for m in report.metrics if not m.passed]
                        if failed_metrics:
                            desc_parts.append("\n\nMETRIC VIOLATIONS:")
                            for m in failed_metrics[:3]:
                                desc_parts.append(f"\n- {m.name}: {m.value} (threshold: {m.threshold})")

                        # Add anti-patterns
                        if report.anti_patterns:
                            desc_parts.append("\n\nANTI-PATTERNS:")
                            for ap in report.anti_patterns[:3]:
                                desc_parts.append(f"\n- {ap.name}: {ap.description}")
                                if ap.pattern_to_apply:
                                    desc_parts.append(f"\n  → Apply: {ap.pattern_to_apply} pattern")

                        description = "".join(desc_parts)

                        task_obj = Task(
                            id=task_id,
                            project_id=self.project.id,
                            type="refactor",
                            domain=domain,
                            description=description,
                            files=[report.file_path],
                            context={
                                "metrics": [m.to_dict() for m in failed_metrics],
                                "anti_patterns": [a.to_dict() for a in report.anti_patterns],
                                "priority_score": report.priority_score,
                            },
                            wsjf_score=report.priority_score,
                            priority=int(report.priority_score * 10),
                        )

                        self.task_store.create_task(task_obj)
                        created_tasks.append(task_obj)
                        log(f"    ✅ Created: {Path(report.file_path).name} (score={report.priority_score})")

                except Exception as e:
                    log(f"  ❌ Error analyzing {path}: {e}", "ERROR")

        log("\n" + "─" * 70)
        log(f"Created {len(created_tasks)} REFACTOR tasks with metrics evidence")
        log("Tasks include: metric violations, anti-patterns, suggested GOF patterns")
        log("═" * 70)

        return created_tasks

    async def _call_llm(self, prompt: str, timeout: int = 1800) -> Optional[str]:
        """
        Call LLM via configured CLI tool (copilot or claude).

        Routes to _call_copilot or _call_claude based on self.cli_tool.
        """
        if self.cli_tool == "copilot":
            return await self._call_copilot(prompt, timeout)
        else:
            return await self._call_claude(prompt, timeout)

    async def _call_copilot(self, prompt: str, timeout: int = 1800) -> Optional[str]:
        """
        Call Copilot CLI with Sonnet 4.6.

        Copilot has access to MCP tools via ~/.copilot/mcp-config.json
        including our mcp_lrm tools for project navigation.
        """
        rc, stdout, stderr = await run_subprocess_exec(
            ["copilot", "--model", "claude-sonnet-4-6",
             "-p", prompt, "--allow-all-tools", "--allow-all-paths"],
            timeout=timeout,
            cwd=str(self.project.root_path),
            register_pgroup=True,
            log_fn=log,
        )
        if rc == 0:
            return stdout.strip()
        if rc == -1:
            log(f"Copilot timeout ({timeout}s)", "ERROR")
        elif stderr:
            log(f"Copilot error: {stderr[:500]}", "ERROR")
        return None

    async def _call_claude(self, prompt: str, timeout: int = 1800) -> Optional[str]:
        """
        Call Claude Opus via `claude` CLI.

        Claude has access to MCP tools configured in ~/.claude/settings.json
        including our mcp_lrm tools for project navigation.
        """
        rc, stdout, stderr = await run_subprocess_exec(
            ["claude", "-p", "--model", "claude-opus-4-5-20251101",
             "--max-turns", "100"],
            timeout=timeout,
            cwd=str(self.project.root_path),
            stdin_data=prompt,
            register_pgroup=True,
            log_fn=log,
        )
        if rc == 0:
            return stdout.strip()
        if rc == -1:
            log(f"Claude timeout ({timeout}s)", "ERROR")
        elif stderr:
            log(f"Claude error: {stderr[:500]}", "ERROR")
        return None

    async def _call_opencode(self, prompt: str, timeout: int = 300) -> Optional[str]:
        """
        Call MiniMax via `opencode` CLI.
        
        Used for sub-analyses (depth 1-2) to save cost.
        opencode has MCP tools access.
        """
        returncode, output = await run_opencode(
            prompt,
            model="minimax/MiniMax-M2.5",
            cwd=str(self.project.root_path),
            timeout=timeout,
            project=self.project.name,
        )
        
        if returncode == 0:
            return output
        else:
            log(f"opencode failed: {output[:200]}", "WARN")
            return None

    # ========================================================================
    # RLM ITERATIVE LOOP (Write-Execute-Observe)
    # ========================================================================

    async def _run_iterative(
        self,
        focus: str,
        context_summary: str,
        vision_content: str,
        mode_config: Dict,
        domains: List[str] = None,
        max_iterations: int = 30,
    ) -> List[Dict]:
        """
        RLM Iterative Brain loop (arXiv:2512.24601).

        Brain (Opus) orchestrates the loop:
        - WRITE: Opus generates 1-3 exploration queries
        - EXECUTE: MiniMax sub-agents run queries in parallel
        - OBSERVE: Results accumulated as findings
        - DECIDE: Opus chooses to explore more or emit FINAL_ANSWER

        Returns raw task dicts (not yet validated/saved).
        """
        findings: List[str] = []

        for i in range(max_iterations):
            log(f"[RLM] Iteration {i + 1}/{max_iterations}")

            # WRITE: Opus decides what to explore
            iter_prompt = self._build_iteration_prompt(
                iteration=i,
                max_iterations=max_iterations,
                focus=focus,
                findings=findings,
                context_summary=context_summary,
                mode_config=mode_config,
                domains=domains,
            )
            response = await self._call_llm(iter_prompt, timeout=300)
            if not response:
                log("[RLM] LLM returned empty response, stopping", "WARN")
                break

            # PARSE: Extract JSON {action, queries/tasks}
            decision = self._parse_iteration_response(response)

            # FINAL_ANSWER? -> exit loop
            if decision["action"] == "final":
                log(f"[RLM] FINAL_ANSWER at iteration {i + 1}")
                return decision.get("tasks", [])

            # EXECUTE: Sub-agents MiniMax in parallel (max 3)
            queries = decision.get("queries", [])[:3]
            if not queries:
                log("[RLM] No queries generated, stopping", "WARN")
                break

            log(f"[RLM] Executing {len(queries)} exploration queries...")
            results = await asyncio.gather(*[
                self._execute_exploration(q) for q in queries
            ])

            # OBSERVE: Accumulate findings
            for q, result in zip(queries, results):
                query_text = q.get("query", str(q)) if isinstance(q, dict) else str(q)
                if result:
                    findings.append(
                        f"[iter {i + 1}] Q: {query_text}\n"
                        f"A: {result[:2000]}"
                    )

            total_chars = sum(len(f) for f in findings)
            log(f"[RLM] {len(findings)} findings accumulated ({total_chars} chars)")

        # Max iterations reached: force FINAL_ANSWER
        log(f"[RLM] Max iterations reached, forcing final answer")
        return await self._force_final_answer(findings, focus, mode_config)

    async def _execute_exploration(self, query: dict) -> Optional[str]:
        """Execute a single exploration query via MiniMax sub-agent."""
        prompt = self._build_exploration_prompt(query)
        return await self._call_opencode(prompt, timeout=120)

    def _build_iteration_prompt(
        self,
        iteration: int,
        max_iterations: int,
        focus: str,
        findings: List[str],
        context_summary: str,
        mode_config: Dict,
        domains: List[str] = None,
    ) -> str:
        """Build the short prompt for Opus at each iteration turn."""
        domains_list = domains or list(self.project.domains.keys())
        mode_focus = mode_config.get("focus", "General analysis")

        # Truncate findings to last 8K chars, prioritizing recent ones
        findings_text = ""
        if findings:
            # Keep last findings verbatim, summarize older ones if over 8K
            all_findings = "\n\n".join(findings)
            if len(all_findings) > 8000:
                # Keep last 5 verbatim
                recent = "\n\n".join(findings[-5:])
                older_summaries = [f.split("\n")[0] for f in findings[:-5]]  # Just Q: lines
                findings_text = (
                    "OLDER FINDINGS (summary):\n"
                    + "\n".join(older_summaries)
                    + "\n\nRECENT FINDINGS (full):\n"
                    + recent
                )
                findings_text = findings_text[-8000:]
            else:
                findings_text = all_findings

        context_snippet = context_summary[:3000] if context_summary else ""

        return f'''You are the RLM Brain for project "{self.project.name}".
Iteration {iteration + 1}/{max_iterations}. Root: {self.project.root_path}
Domains: {domains_list}

MODE: {mode_config.get("name", "ALL")}
{mode_focus[:500] if mode_focus else ""}

PROJECT CONTEXT (excerpt):
{context_snippet}

FINDINGS SO FAR:
{findings_text if findings_text else "(none yet — this is the first iteration)"}

YOUR TASK:
Generate 1-3 exploration queries for MiniMax sub-agents.
Each sub-agent has tools: Read, Grep, Glob, Bash (in the project directory).
Sub-agents can explore files, search code, run commands.

When you have gathered enough information, emit FINAL_ANSWER with tasks.

Respond with ONLY valid JSON (no markdown fences):
{{"action": "explore", "queries": [{{"query": "description of what to explore", "files": ["optional/target/files"], "reason": "why this matters"}}]}}

OR when ready:
{{"action": "final", "tasks": [{{"type": "fix|feature|refactor|test|security", "domain": "...", "description": "...", "files": ["..."], "wsjf_score": 5.0}}]}}
'''

    def _build_exploration_prompt(self, query: dict) -> str:
        """Build the prompt for a MiniMax sub-agent exploration."""
        if isinstance(query, str):
            query = {"query": query}

        query_text = query.get("query", "Explore the project")
        files = query.get("files", [])
        reason = query.get("reason", "")

        files_section = f"\nTARGET FILES: {', '.join(files)}" if files else ""
        reason_section = f"\nREASON: {reason}" if reason else ""

        return f"""Project: {self.project.name} ({self.project.root_path})

MISSION: {query_text}{files_section}{reason_section}

Use your tools to explore FACTUALLY:
- Read files to understand their content
- Grep/Glob to find patterns across the codebase
- Bash for structural commands (ls, wc, etc.)

Report your findings in 500 words max. Be SPECIFIC:
- Exact file paths and line numbers
- Code snippets that illustrate issues
- Concrete facts, NOT suppositions
"""

    def _parse_iteration_response(self, response: str) -> Dict:
        """
        Parse Opus iteration response into {action, queries/tasks}.

        Expected: JSON with action "explore" or "final".
        Fallback: treat as explore with generic query if parsing fails.
        """
        import re

        # Try to find JSON object in response
        # Strip markdown fences if present
        cleaned = response.strip()
        cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
        cleaned = re.sub(r'\s*```$', '', cleaned)

        # Find the outermost JSON object
        try:
            # Try direct parse first
            data = json.loads(cleaned)
            if isinstance(data, dict) and "action" in data:
                return data
        except json.JSONDecodeError:
            pass

        # Try to extract JSON object from mixed text
        match = re.search(r'\{[\s\S]*"action"[\s\S]*\}', response)
        if match:
            json_str = match.group()
            # Balance braces
            depth = 0
            end = 0
            for idx, c in enumerate(json_str):
                if c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        end = idx + 1
                        break
            if end > 0:
                try:
                    data = json.loads(json_str[:end])
                    if isinstance(data, dict) and "action" in data:
                        return data
                except json.JSONDecodeError:
                    pass

        # Fallback: treat entire response as a finding text, continue exploring
        log("[RLM] Could not parse iteration JSON, using fallback explore", "WARN")
        return {
            "action": "explore",
            "queries": [{"query": "Continue exploring the project for issues", "reason": "fallback"}],
        }

    async def _force_final_answer(
        self, findings: List[str], focus: str, mode_config: Dict
    ) -> List[Dict]:
        """Force a FINAL_ANSWER from Opus given all accumulated findings."""
        findings_text = "\n\n".join(findings)
        # Truncate to fit in context
        if len(findings_text) > 15000:
            findings_text = findings_text[-15000:]

        prompt = f'''You are the RLM Brain for project "{self.project.name}".
Mode: {mode_config.get("name", "ALL")}

You have explored the codebase over multiple iterations. Here are ALL your findings:

{findings_text}

PRODUCE THE FINAL TASK LIST NOW.

Output ONLY a valid JSON array of tasks:
[{{"type": "fix|feature|refactor|test|security", "domain": "...", "description": "...", "files": ["..."], "wsjf_score": 5.0}}]
'''
        response = await self._call_llm(prompt, timeout=300)
        if response:
            return self._parse_tasks(response)
        return []

    async def _deep_analyze_tasks(self, tasks: List[Dict]) -> List[Dict]:
        """
        Run deep analysis on tasks using MiniMax sub-agents.
        
        For each task, spawn a MiniMax sub-agent to:
        - Verify the issue exists
        - Identify exact files/lines
        - Suggest specific fixes
        """
        log(f"🔍 Running deep analysis on {len(tasks)} tasks with MiniMax...")
        
        enhanced_tasks = []
        
        for i, task in enumerate(tasks[:10]):  # Limit to 10 for cost
            log(f"  [{i+1}/{min(len(tasks), 10)}] Analyzing: {task.get('description', '')[:50]}...")
            
            prompt = f"""Analyze this task and provide detailed implementation guidance:

TASK:
- Type: {task.get('type', 'fix')}
- Domain: {task.get('domain', 'unknown')}
- Description: {task.get('description', '')}
- Files: {task.get('files', [])}

Use MCP tools to:
1. Locate the exact files involved (lrm_locate)
2. Read the current code (lrm_summarize)
3. Identify the exact lines to change

Respond with JSON:
{{
  "files": ["exact/file/paths.rs"],
  "changes": [
    {{"file": "path", "line": 42, "current": "...", "suggested": "..."}}
  ],
  "test_approach": "How to test this fix",
  "estimated_loc": 50
}}
"""
            
            result = await self._call_opencode(prompt, timeout=120)
            
            if result:
                # Try to extract enhanced info
                try:
                    import re
                    json_match = re.search(r'\{[^{}]*"files"[^{}]*\}', result, re.DOTALL)
                    if json_match:
                        enhanced = json.loads(json_match.group())
                        task.update({
                            "files": enhanced.get("files", task.get("files", [])),
                            "changes": enhanced.get("changes", []),
                            "test_approach": enhanced.get("test_approach", ""),
                            "estimated_loc": enhanced.get("estimated_loc", 50),
                            "deep_analyzed": True,
                        })
                except:
                    pass
            
            enhanced_tasks.append(task)
        
        # Add remaining tasks without deep analysis
        enhanced_tasks.extend(tasks[10:])
        
        return enhanced_tasks

    def _validate_tasks(self, tasks: List[Dict]) -> List[Dict]:
        """Validate tasks are atomic, testable, and have required fields."""
        validated = []
        for t in tasks:
            # Required fields
            if not t.get("description"):
                continue
            if len(t.get("description", "")) < 10:
                continue

            # Ensure atomicity (no "and also" patterns)
            desc = t.get("description", "").lower()
            if " and also " in desc or " additionally " in desc:
                # Task too complex, could be split but we'll let Wiggum handle it
                pass

            # Ensure files list
            if not t.get("files"):
                t["files"] = []

            # Ensure WSJF score
            if not t.get("wsjf_score"):
                t["wsjf_score"] = 5.0

            validated.append(t)

        # ADVERSARIAL GATE: Filter SLOP before injection
        validated = self._adversarial_filter_tasks(validated)

        return validated

    async def _cove_verify_tasks(self, tasks: List[Dict]) -> List[Dict]:
        """
        Chain-of-Verification (CoVe) for Brain Tasks - arxiv:2309.11495.

        Reduces hallucinations by independently verifying each task.

        STAGE 1 (already done): Draft - initial task generation
        STAGE 2: Plan verification questions for each task
        STAGE 3: Answer questions independently (grep, file checks)
        STAGE 4: Final verified task list
        """
        if not tasks:
            return tasks

        log(f"🔍 CoVe: Verifying {len(tasks)} tasks...")
        verified_tasks = []
        rejected_count = 0

        for task in tasks:
            desc = task.get("description", "")
            files = task.get("files", [])
            domain = task.get("domain", "unknown")

            # STAGE 2: Plan verification questions
            verify_questions = [
                f"Does file exist? {files[0] if files else 'no file'}",
                f"Is this a real feature from AO/VISION.md?",
                f"Is this actionable (specific change)?",
            ]

            # STAGE 3: Answer independently (deterministic checks)
            verified = True
            reasons = []

            # Check 1: Files exist (if specified)
            if files:
                for f in files[:3]:  # Check first 3 files
                    file_path = self.project.root_path / f
                    if not file_path.exists() and not "*" in f:
                        # File doesn't exist - might be hallucinated
                        # Unless it's a new file to create
                        if task.get("type") not in ["feature", "implement"]:
                            verified = False
                            reasons.append(f"File not found: {f}")
                            break

            # Check 2: Description is specific (not vague)
            vague_patterns = [
                "fix error", "fix issue", "fix bug",  # too vague
                "improve", "enhance",  # no specific action
                "maybe", "consider", "might",  # uncertain
            ]
            desc_lower = desc.lower()
            for pattern in vague_patterns:
                if pattern in desc_lower and len(desc) < 50:
                    verified = False
                    reasons.append(f"Vague description: '{pattern}'")
                    break

            # Check 3: Has AO traceability (for features)
            if task.get("type") == "feature":
                ao_keywords = ["REQ-", "AO-", "US-", "ao_ref", "IDFM", "Nantes", "MOBIA"]
                has_ao_ref = any(kw in desc for kw in ao_keywords)
                # Also check if it's from VISION.md
                vision_keywords = ["booking", "subscription", "payment", "station", "bike", "tenant", "auth"]
                has_vision = any(kw.lower() in desc_lower for kw in vision_keywords)

                if not has_ao_ref and not has_vision:
                    # Check context for AO ref
                    context = task.get("context", {})
                    if isinstance(context, dict) and not context.get("ao_ref"):
                        verified = False
                        reasons.append("Feature without AO/VISION traceability")

            # STAGE 4: Final decision
            if verified:
                verified_tasks.append(task)
            else:
                rejected_count += 1
                log(f"  ❌ CoVe REJECTED: {desc[:50]}... ({', '.join(reasons)})", "WARN")

        if rejected_count > 0:
            log(f"⚠️ CoVe: Rejected {rejected_count}/{len(tasks)} unverified tasks", "WARN")

        log(f"✅ CoVe: {len(verified_tasks)} tasks verified")
        return verified_tasks

    def _adversarial_filter_tasks(self, tasks: List[Dict]) -> List[Dict]:
        """
        Adversarial Gate for Brain Tasks - NO SLOP ALLOWED.

        Filters out:
        - Compilation errors (not business value)
        - Console/runtime errors
        - Build config errors
        - Hallucinated/stale tasks
        - Over-engineered non-actionable tasks
        """
        SLOP_PATTERNS = [
            # Compilation errors - not features
            "compilation error",
            "unresolved import",
            "failed to resolve",
            "[E0432]", "[E0433]", "[E0412]", "[E0425]",
            "cannot find",
            "not found in this scope",

            # Console/build errors - should be fixed directly, not as tasks
            "console error",
            "build error",
            "npm error",
            "command not found",
            "unrecognized subcommand",

            # Generic/vague tasks - no business value
            "fix error",
            "fix issue",
            "fix bug",  # too vague without specifics

            # Stale patterns
            "max timeout",
            "process stuck",
        ]

        VISION_KEYWORDS = [
            # Business value indicators
            "implement", "feature", "add", "create", "build",
            "integrate", "connect", "migrate", "upgrade",
            "user", "customer", "tenant", "booking", "payment",
            "subscription", "auth", "dashboard", "admin",
            "grpc", "api", "service", "endpoint",
        ]

        filtered = []
        rejected_count = 0

        for t in tasks:
            desc = t.get("description", "").lower()

            # REJECT: Slop patterns
            is_slop = any(pattern.lower() in desc for pattern in SLOP_PATTERNS)
            if is_slop:
                rejected_count += 1
                continue

            # REQUIRE: At least one vision keyword (business value)
            has_vision = any(kw in desc for kw in VISION_KEYWORDS)
            if not has_vision:
                # Check if it's a security task (also valuable)
                is_security = any(kw in desc for kw in ["security", "vulnerability", "injection", "xss", "csrf", "auth"])
                if not is_security:
                    rejected_count += 1
                    continue

            filtered.append(t)

        if rejected_count > 0:
            log(f"⚠️ ADVERSARIAL GATE: Rejected {rejected_count} slop tasks", "WARN")

        return filtered

    def _build_analysis_prompt(
        self,
        vision: str,
        focus: str = None,
        domains: List[str] = None,
        deep_analysis: bool = True,
        project_context: str = None,
    ) -> str:
        """Build analysis prompt for Claude with MCP tools and project context."""

        domains_list = domains or list(self.project.domains.keys())
        vision_truncated = vision[:8000] if vision else "No vision document"
        context_section = project_context or ""
        
        # Check if project has Figma integration
        figma_config = self.project.figma or {}
        figma_enabled = figma_config.get('enabled', False)
        
        figma_instructions = ""
        if figma_enabled:
            figma_instructions = """
FIGMA DESIGN SYSTEM INTEGRATION:
This project uses Figma as source of truth for UI components.
You have access to Figma MCP tools:
- get_design_context: Get design specs for selected Figma node
- get_variable_defs: Get design tokens (colors, spacing, typography)
- get_screenshot: Get visual of component
- add_code_connect_map: Map Figma node to Svelte component

For Svelte components:
1. Check Figma specs before generating/modifying components
2. Compare CSS values with Figma design tokens
3. Generate tasks if CSS doesn't match Figma specs (padding, colors, radius)
4. Use clientFrameworks="svelte" when calling Figma tools
"""

        return f'''You are a DEEP RECURSIVE ANALYSIS ENGINE for the "{self.project.name}" project.

IMPORTANT: You have access to MCP tools for project navigation. USE THEM:
- lrm_locate: Find files matching a pattern
- lrm_summarize: Get summary of file content
- lrm_conventions: Get coding conventions for a domain
- lrm_examples: Get example code
- lrm_build: Run build/test commands
{figma_instructions}

══════════════════════════════════════════════════════════════════════════════
PROJECT: {self.project.name}
DOMAINS: {domains_list}
{f"FOCUS: {focus}" if focus else ""}
══════════════════════════════════════════════════════════════════════════════

{f"""
══════════════════════════════════════════════════════════════════════════════
PROJECT CONTEXT (Auto-generated "Big Picture")
══════════════════════════════════════════════════════════════════════════════
{context_section}
""" if context_section else ""}

VISION DOCUMENT (Product Roadmap):
{vision_truncated}

══════════════════════════════════════════════════════════════════════════════
YOUR MISSION: Deep recursive analysis
══════════════════════════════════════════════════════════════════════════════

1. Use MCP tools to explore the codebase:
   - lrm_locate("*.rs") to find Rust files
   - lrm_locate("*test*") to find test files
   - lrm_summarize("src/main.rs") to understand files

2. Analyze each domain for:
   - Security vulnerabilities
   - Performance issues
   - Missing tests
   - Code quality issues
   - Architecture violations

3. Generate ATOMIC tasks (one specific change each)

For each task, provide:
- type: fix|feature|refactor|test|security
- domain: one of {domains_list}
- description: Specific, actionable
- files: List of files to modify
- severity: critical|high|medium|low
- wsjf_score: 1-10

WSJF scoring:
- 10: Critical security/data loss, quick fix
- 8-9: High business impact
- 6-7: Important improvement
- 4-5: Nice to have
- 1-3: Minor polish

══════════════════════════════════════════════════════════════════════════════
OUTPUT FORMAT:
══════════════════════════════════════════════════════════════════════════════

After your analysis, output a JSON array:

```json
[
  {{"type": "security", "domain": "rust", "description": "Fix SQL injection in user_query()", "files": ["src/db.rs"], "severity": "critical", "wsjf_score": 9.5}},
  ...
]
```

BEGIN ANALYSIS NOW. Use MCP tools to explore the project!
'''

    def _build_deep_recursive_prompt(
        self,
        vision: str,
        project_context: str,
        focus: str = None,
        domains: List[str] = None,
        deep_analysis: bool = True,
    ) -> str:
        """Build the DEEP RECURSIVE RLM prompt."""

        domains_list = domains or list(self.project.domains.keys())
        
        # Truncate vision if too long
        vision_truncated = vision[:8000] if vision else "No vision document"

        return f'''You are a DEEP RECURSIVE ANALYSIS ENGINE based on MIT CSAIL arXiv:2512.24601 "Recursive Language Models".

You MUST use llm_query() for deep analysis - this is what makes RLM powerful!
You have max_depth=3 recursive calls available. USE THEM.

══════════════════════════════════════════════════════════════════════════════
PROJECT: {self.project.name}
DOMAINS: {domains_list}
{f"FOCUS: {focus}" if focus else ""}
══════════════════════════════════════════════════════════════════════════════

VISION DOCUMENT:
{vision_truncated}

══════════════════════════════════════════════════════════════════════════════
PROJECT CODEBASE (you can search/analyze this programmatically):
══════════════════════════════════════════════════════════════════════════════
{project_context}

══════════════════════════════════════════════════════════════════════════════
EXECUTE THIS 5-PHASE DEEP RECURSIVE ANALYSIS:
══════════════════════════════════════════════════════════════════════════════

PHASE 1: STRUCTURE DECOMPOSITION
────────────────────────────────
First, decompose the project into analyzable units:

```python
import re

# Extract all modules/files
files = re.findall(r'={10,}\\n// FILE: ([^\\n]+)', project_context)
print(f"Found {{len(files)}} files")

# Group by domain
modules = {{}}
for f in files:
    if '.rs' in f: modules.setdefault('rust', []).append(f)
    elif '.ts' in f or '.tsx' in f: modules.setdefault('typescript', []).append(f)
    elif '.swift' in f: modules.setdefault('swift', []).append(f)
    elif '.py' in f: modules.setdefault('python', []).append(f)

for domain, fs in modules.items():
    print(f"{{domain}}: {{len(fs)}} files")
```

PHASE 2: DEEP RECURSIVE ANALYSIS (USE llm_query!)
─────────────────────────────────────────────────
For EACH module/domain, call llm_query() for deep analysis:

```python
all_findings = []

# Example: Deep security analysis of authentication code
auth_code = # extract auth-related code from project_context
security_analysis = llm_query(f"""
You are a security expert. Analyze this authentication code for vulnerabilities:

<code>
{{auth_code[:5000]}}
</code>

List EACH vulnerability found with:
- Category (injection, auth bypass, data exposure, etc.)
- Severity (critical/high/medium/low)
- Exact location (file:line if possible)
- Recommended fix
- Code example of the fix

Be thorough and specific. This analysis will create security tasks.
""")
print("Security analysis:", security_analysis)
all_findings.append(("security", security_analysis))

# Example: Deep performance analysis
perf_code = # extract performance-critical code
perf_analysis = llm_query(f"""
You are a performance expert. Analyze this code for performance issues:

<code>
{{perf_code[:5000]}}
</code>

List EACH performance issue with:
- Type (N+1 query, memory leak, blocking I/O, etc.)
- Impact (latency, memory, CPU)
- Severity
- Recommended fix

Be thorough and specific.
""")
print("Performance analysis:", perf_analysis)
all_findings.append(("performance", perf_analysis))
```

PHASE 3: PARALLEL BATCH ANALYSIS (USE llm_query_batched!)
─────────────────────────────────────────────────────────
For multiple files, use parallel analysis:

```python
# Collect files that need analysis
files_to_analyze = []
for match in re.finditer(r'// FILE: ([^\\n]+)\\n(.*?)(?=// FILE:|$)', project_context, re.DOTALL):
    filename, content = match.groups()
    if len(content) > 500:  # Only non-trivial files
        files_to_analyze.append((filename, content[:3000]))

# Create analysis prompts
prompts = []
for filename, content in files_to_analyze[:10]:  # Limit to 10 for efficiency
    prompts.append(f"""
Analyze this file for issues:
FILE: {{filename}}
<code>
{{content}}
</code>

Return JSON: {{"issues": [{{"type": "...", "severity": "...", "description": "...", "line": ...}}]}}
""")

# Parallel analysis!
if prompts:
    results = llm_query_batched(prompts)
    for (filename, _), result in zip(files_to_analyze[:10], results):
        print(f"{{filename}}: {{result[:200]}}...")
        all_findings.append(("file_analysis", result))
```

PHASE 4: CROSS-CUTTING CONCERNS
───────────────────────────────
Analyze architecture-level issues:

```python
# Architecture analysis
arch_analysis = llm_query(f"""
Analyze the overall architecture of this codebase:

<structure>
{{str(modules)}}
</structure>

<sample_code>
{{project_context[:10000]}}
</sample_code>

Identify:
1. Architecture violations (circular deps, layer breaches)
2. Missing abstractions (code duplication patterns)
3. Testability issues (hard-coded deps, no interfaces)
4. Scalability concerns

For each issue, specify affected files and recommended refactoring.
""")
print("Architecture analysis:", arch_analysis)
all_findings.append(("architecture", arch_analysis))

# Testing coverage analysis
test_analysis = llm_query(f"""
Analyze testing coverage and quality:

<code>
{{project_context[:8000]}}
</code>

Identify:
1. Missing test coverage (which modules have no tests?)
2. Test quality issues (tests that don't actually test anything)
3. Missing integration tests
4. Missing edge case tests

Be specific about WHICH functions/modules need tests.
""")
print("Test analysis:", test_analysis)
all_findings.append(("testing", test_analysis))
```

PHASE 5: SYNTHESIS & TASK GENERATION
─────────────────────────────────────
Aggregate all findings into prioritized tasks:

```python
# Synthesize all findings into tasks
synthesis = llm_query(f"""
You are a technical lead. Based on these analysis findings, create a prioritized backlog:

<findings>
{{str(all_findings)}}
</findings>

Create ATOMIC tasks (one specific change each). For each task:
- type: fix|feature|refactor|test|security
- domain: {domains_list}
- description: Specific, actionable (what exactly to change)
- files: List of files to modify
- severity: critical|high|medium|low
- wsjf_score: 1-10 (based on value/effort ratio)
- acceptance_criteria: List of testable criteria

WSJF scoring guide:
- 10: Critical security/data loss risk, quick fix
- 8-9: High business impact, moderate effort
- 6-7: Important improvement, reasonable effort
- 4-5: Nice to have, low effort
- 1-3: Minor polish

Return ONLY valid JSON array:
[{{"type": "...", "domain": "...", "description": "...", "files": [...], "severity": "...", "wsjf_score": N, "acceptance_criteria": [...]}}]
""")
print(synthesis)
```

══════════════════════════════════════════════════════════════════════════════
FINAL OUTPUT REQUIREMENT:
══════════════════════════════════════════════════════════════════════════════

After completing ALL 5 phases, output the final task list as:

```json
[
  {{"type": "security", "domain": "rust", "description": "...", "files": ["..."], "severity": "critical", "wsjf_score": 9.5, "acceptance_criteria": ["..."]}},
  ...
]
```

BEGIN DEEP RECURSIVE ANALYSIS NOW. Use llm_query() extensively!
'''

    def _parse_tasks(self, response: str) -> List[Dict]:
        """Parse tasks from RLM response."""
        import re

        # Log first 500 chars of response for debug
        log(f"Response preview: {response[:500]}..." if len(response) > 500 else f"Response: {response}")

        try:
            # Method 1: Find JSON array in ```json ... ``` (greedy to get full array)
            match = re.search(r'```json\s*(\[[\s\S]*?\])\s*```', response)
            if match:
                json_str = match.group(1)
                log(f"Found JSON block: {len(json_str)} chars")
                tasks = json.loads(json_str)
                return [t for t in tasks if isinstance(t, dict) and "description" in t]

            # Method 2: Find JSON array starting with [{ and ending with }]
            match = re.search(r'(\[\s*\{[\s\S]*?\}\s*\])', response)
            if match:
                json_str = match.group(1)
                log(f"Found raw JSON array: {len(json_str)} chars")
                try:
                    tasks = json.loads(json_str)
                    valid = [t for t in tasks if isinstance(t, dict) and "description" in t]
                    if valid:
                        return valid
                except json.JSONDecodeError:
                    pass  # Try next method

            # Method 3: Find any array with "type" and "description"
            match = re.search(r'\[[\s\S]*?"type"[\s\S]*?"description"[\s\S]*?\]', response)
            if match:
                json_str = match.group()
                log(f"Found array with type/description: {len(json_str)} chars")
                # Try to find the complete array by balancing brackets
                start = response.find('[', match.start())
                if start != -1:
                    depth = 0
                    for i, c in enumerate(response[start:]):
                        if c == '[':
                            depth += 1
                        elif c == ']':
                            depth -= 1
                            if depth == 0:
                                json_str = response[start:start + i + 1]
                                break
                    try:
                        tasks = json.loads(json_str)
                        return [t for t in tasks if isinstance(t, dict) and "description" in t]
                    except json.JSONDecodeError as e:
                        log(f"JSON parse failed: {e}", "WARN")

            log("No JSON array found in response", "WARN")

        except json.JSONDecodeError as e:
            log(f"JSON parse error: {e}", "WARN")
        except Exception as e:
            log(f"Parse exception: {e}", "ERROR")

        return []

    def get_status(self) -> Dict:
        """Get current brain status."""
        tasks = self.task_store.get_tasks_by_project(self.project.id)
        status_counts = {}
        for task in tasks:
            status = task.status
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "project": self.project.name,
            "total_tasks": len(tasks),
            "by_status": status_counts,
        }

    def close(self):
        """Clean up resources."""
        pass  # No persistent connections to close


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="RLM Brain - Project Analyzer")
    parser.add_argument("--project", "-p", help="Project name")
    parser.add_argument("--focus", "-f", help="Focus prompt")
    parser.add_argument("--domain", "-d", help="Specific domain")
    parser.add_argument("--status", action="store_true", help="Show status only")

    args = parser.parse_args()

    brain = RLMBrain(args.project)

    if args.status:
        status = brain.get_status()
        print(json.dumps(status, indent=2))
        return

    domains = [args.domain] if args.domain else None

    tasks = asyncio.run(brain.run(
        vision_prompt=args.focus,
        domains=domains,
    ))

    print(f"\nCreated {len(tasks)} tasks")
    for task in tasks[:10]:
        print(f"  - [{task.domain}] {task.description[:60]}...")

    brain.close()


if __name__ == "__main__":
    main()
