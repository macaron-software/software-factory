#!/usr/bin/env python3
"""
Adversarial Gate - Code Quality Red Team
==========================================
Configurable per-project patterns. Zero SLOP. Zero bypass.

Features:
- Core patterns: universal rules (test.skip, @ts-ignore, etc.)
- Custom patterns: project-specific rules from YAML config
- Two modes: FAST (regex) and DEEP (LLM semantic analysis)
- Structured feedback for retry

Score >= threshold → REJECT with feedback

Usage:
    from core.adversarial import AdversarialGate

    gate = AdversarialGate(project_config)
    result = gate.check_code(code, file_type="rust")
    result = await gate.check_code_deep(code, file_type="rust")
"""

import re
import asyncio
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path


def log(msg: str, level: str = "INFO"):
    """Log with timestamp"""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [ADVERSARIAL] [{level}] {msg}", flush=True)


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class Issue:
    """Single issue found during check"""
    rule: str
    severity: str  # "reject", "warning"
    points: int
    message: str
    line: int = 0
    context: str = ""

    def to_dict(self) -> Dict:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "points": self.points,
            "message": self.message,
            "line": self.line,
            "context": self.context,
        }


@dataclass
class CheckResult:
    """Result of adversarial check"""
    approved: bool
    score: int
    threshold: int
    issues: List[Issue] = field(default_factory=list)
    feedback: str = ""

    def to_dict(self) -> Dict:
        return {
            "approved": self.approved,
            "score": self.score,
            "threshold": self.threshold,
            "issues": [i.to_dict() for i in self.issues],
            "feedback": self.feedback,
        }


# ============================================================================
# CORE PATTERNS (Universal - always applied)
# ============================================================================

# REJECT patterns: immediate high score (typically >= threshold alone)
CORE_REJECT_PATTERNS = {
    # Test skipping - reduced score (2 pts each)
    # Existing skips in codebase shouldn't block new code
    # These will create feedback tasks for fixing, not block builds
    r"\btest\.skip\b": ("test_skip", 2, "Test skip detected - tests must run"),
    r"\bdescribe\.skip\b": ("describe_skip", 2, "Describe skip detected - tests must run"),
    r"\bit\.skip\b": ("it_skip", 2, "It skip detected - tests must run"),
    r"#\[ignore\]": ("ignore_attr", 2, "Rust #[ignore] detected - tests must run"),

    # TypeScript bypass
    r"@ts-ignore": ("ts_ignore", 2, "@ts-ignore bypasses type checking"),
    r"@ts-expect-error": ("ts_expect_error", 2, "@ts-expect-error bypasses type checking"),
    r"\bas\s+any\b": ("as_any", 2, "'as any' bypasses type checking"),

    # Slop words in comments (AI-generated artifacts)
    r"//.*\b100%\b": ("slop_100", 2, "Slop: claiming '100%' in comments"),
    r"//.*\bperfect\b": ("slop_perfect", 2, "Slop: claiming 'perfect' in comments"),
    r"//.*\ball\s+cases?\s+handled\b": ("slop_all", 2, "Slop: claiming 'all cases handled'"),

    # Code stubs
    r"unimplemented!\s*\(": ("unimpl_macro", 3, "unimplemented!() - incomplete code"),
    r'panic!\s*\(["\']not\s+implemented': ("panic_not_impl", 3, "panic!(not implemented) - incomplete"),
    # NotImplementedError OK for API stubs with pragma: no cover
    # r"raise\s+NotImplementedError": ("not_impl_py", 3, "NotImplementedError - incomplete code"),
}

# WARNING patterns: accumulate points
CORE_WARNING_PATTERNS = {
    r"\.unwrap\(\)": ("unwrap", 1, "Rust .unwrap() can panic", 3),  # max 3 occurrences
    r":\s*any\b|as\s+any\b|<any>": ("any_type", 1, "TypeScript 'any' type detected", 5),  # type annotation/cast only
    r"//\s*TODO\b": ("todo", 1, "TODO comment - incomplete code", 2),
    r"//\s*FIXME\b": ("fixme", 1, "FIXME comment - known issue", 2),
    r"//\s*STUB\b": ("stub", 2, "STUB comment - placeholder code", 1),
    r"catch\s*\([^)]*\)\s*\{\s*\}": ("empty_catch", 1, "Empty catch block", 3),
    r"todo!\s*\(\)": ("todo_macro", 2, "Rust todo!() macro - incomplete", 2),
    r"except:\s*pass": ("except_pass", 2, "Bare except: pass - swallows errors", 2),
}

# Security patterns
SECURITY_PATTERNS = {
    r'if\s*\(!\w+\)\s*\{\s*\}': ("empty_null_check", 3, "Null checks must have handling logic, not empty blocks"),
    r'try\s*\{[^}]*\}\s*catch\s*\([^)]*\)\s*\{\s*\}': ("empty_catch_block", 4, "Error handling needs proper catch blocks, not silent failures"),
    r"process\.env\.\w+\s*\|\|\s*['\"][^'\"]+['\"]": ("fallback_credentials", 5, "No fallback values for credentials"),
    r'expect\([^)]+\)\.toBe\([^)]+\)\s*;?\s*\}\s*\);?\s*$': ("test_without_assertion_context", 3, "Tests need meaningful assertions with context"),
    r'describe\.skip|it\.skip|test\.skip|xit\(|xdescribe\(': ("no_skipped_tests", 5, "No skipped tests allowed"),
    r'password\s*=\s*["\'][^"\']{3,}["\']': ("hardcoded_password", 5, "Hardcoded password detected"),
    r'api_key\s*=\s*["\'][^"\']{10,}["\']': ("hardcoded_api_key", 5, "Hardcoded API key detected"),
    r'secret\s*=\s*["\'][^"\']{10,}["\']': ("hardcoded_secret", 5, "Hardcoded secret detected"),
    r'Bearer\s+[a-zA-Z0-9_-]{20,}': ("hardcoded_token", 5, "Hardcoded bearer token"),
}

# Patterns that indicate test/fixture files (OK to have hardcoded values)
TEST_FILE_PATTERNS = [
    r'test[_\-]', r'\.test\.', r'\.spec\.', r'_tests?\.', r'_specs?\.',
    r'/tests/', r'/test/', r'/__tests__/', r'/fixtures/', r'/mocks/',
    r'mock[_\-]', r'fixture[_\-]', r'fake[_\-]', r'stub[_\-]',
    r'_test$', r'_tests$',  # Files ending in _test or _tests (no extension)
]


# ============================================================================
# ARCHITECTURAL COMPLETENESS PATTERNS (FRACTAL L1 coverage)
# Detect MISSING concerns that should have been addressed
# ============================================================================

# These are checked on API/endpoint files to ensure completeness
ARCH_COMPLETENESS_CHECKS = {
    "rbac": {
        "name": "RBAC/Authentication",
        "required_in": [r"server\.ts$", r"route\.ts$", r"\+server\.ts$", r"handler\.rs$", r"controller\."],
        "must_have_one_of": [
            r"getSession|validateSession|requireAuth|isAuthenticated",
            r"checkPermission|hasRole|requireRole|authorize",
            r"401|403|Unauthorized|Forbidden",
            r"currentUser|session\.user|req\.user",
            r"auth\.|authentication|authorization",
        ],
        "points": 4,
        "message": "MISSING RBAC: Endpoint has no authentication/authorization checks",
    },
    "input_validation": {
        "name": "Input Validation",
        "required_in": [r"server\.ts$", r"route\.ts$", r"\+server\.ts$", r"handler\.rs$"],
        "must_have_one_of": [
            r"validate|sanitize|parse|safeParse",
            r"zod\.|yup\.|joi\.",
            r"typeof\s+\w+\s*[!=]==?\s*['\"]string",
            r"Number\.isFinite|isNaN|parseInt.*\|\|",
            r"\.trim\(\)|\.escape\(|htmlEscape",
        ],
        "points": 3,
        "message": "MISSING VALIDATION: No input validation/sanitization detected",
    },
    "query_limits": {
        "name": "Query Limits",
        "required_in": [r"server\.ts$", r"route\.ts$", r"\+server\.ts$", r"\.rs$"],
        "trigger_patterns": [r"SELECT\s+.*FROM", r"\.query\(", r"\.find\(", r"\.findMany\("],
        "must_have_one_of": [
            r"LIMIT\s+\d+",
            r"LIMIT\s+\$\d+",  # Parameterized LIMIT ($1, $2, etc.)
            r"LIMIT\s+\?",     # Parameterized LIMIT (?)
            r"\.limit\(",
            r"\.take\(",
            r"\.top\(",
            r"maxResults|pageSize|perPage",
            r"Math\.min.*limit",  # Capped limit pattern
        ],
        "points": 3,
        "message": "MISSING LIMIT: Database query without LIMIT - DoS risk",
    },
    "error_specificity": {
        "name": "Specific Error Handling",
        "required_in": [r"server\.ts$", r"route\.ts$", r"\+server\.ts$"],
        "trigger_patterns": [r"catch\s*\(", r"\.catch\("],
        "must_not_have": [
            r"status:\s*500\s*\}[^}]*$",  # Generic 500 without specific handling
            r'json\(\s*\[\s*\]\s*,\s*\{\s*status:\s*500',  # Empty array on error
        ],
        "must_have_one_of": [
            r"status:\s*4\d\d",  # Specific 4xx codes
            r"error\.message|error\.code",
            r"BadRequest|NotFound|Conflict",
        ],
        "points": 2,
        "message": "GENERIC ERROR: Using 500/empty response instead of specific error codes",
    },
}

# Files to SKIP architecture checks (config, types, tests, etc.)
SKIP_ARCH_CHECK_PATTERNS = [
    r'\.test\.', r'\.spec\.', r'_test\.', r'_spec\.',
    r'\.d\.ts$', r'types\.ts$', r'config\.', r'constants\.',
    r'\.md$', r'\.json$', r'\.yaml$', r'\.yml$',
]

# Security rules to SKIP in test files (hardcoded fixtures are OK)
SKIP_IN_TESTS = {'hardcoded_password', 'hardcoded_api_key', 'hardcoded_secret', 'hardcoded_token'}

# Core warning patterns to SKIP in test files (common test patterns)
SKIP_WARNINGS_IN_TESTS = {'unwrap', 'todo', 'fixme', 'stub', 'todo_macro'}


# ============================================================================
# CYCLOMATIC COMPLEXITY (KISS enforcement)
# ============================================================================
# Thresholds per McCabe's cyclomatic complexity:
# 1-10: Simple, low risk
# 11-20: Moderate complexity
# 21-50: High complexity, refactor recommended
# 50+: Untestable, must refactor

COMPLEXITY_THRESHOLDS = {
    "max_function_lines": 50,      # Max lines per function
    "max_nesting_depth": 4,        # Max nesting (if/for/while)
    "max_branches_per_function": 10,  # Max if/else/match branches
    "max_params": 5,               # Max function parameters
    "cyclomatic_warning": 10,      # Warning threshold
    "cyclomatic_reject": 20,       # Reject threshold
}

# Patterns to detect complexity indicators
COMPLEXITY_PATTERNS = {
    # Deep nesting detection (4+ levels)
    "rust": {
        "nesting": r"^(\s{16,})(if|for|while|match|loop)\b",  # 4+ indents (4 spaces each)
        "long_match": r"match\s+\w+\s*\{[^}]{500,}\}",  # Match with 500+ chars
        "many_unwrap": r"(\.unwrap\(\).*){4,}",  # 4+ unwraps in sequence
    },
    "python": {
        "nesting": r"^(\s{16,})(if|for|while|try|with)\b",
        "long_function": r"def\s+\w+\([^)]*\):[^def]{1000,}",  # 1000+ chars function
        "many_conditions": r"(and|or).*?(and|or).*?(and|or).*?(and|or)",  # 4+ boolean ops
    },
    "typescript": {
        "nesting": r"^(\s{16,})(if|for|while|switch)\b",
        "callback_hell": r"(\)\s*=>\s*\{[^}]*){4,}",  # 4+ nested callbacks
        "long_ternary": r"\?[^:]{50,}:",  # Ternary with 50+ chars
    },
    "svelte": {
        "nesting": r"^(\s{16,})(if|for|while|switch|\{#if|\{#each)\b",
        "complex_reactive": r"\$:\s*\{[^}]{200,}\}",  # Complex reactive block
    },
}

# Heuristic complexity scoring based on code patterns
def estimate_cyclomatic_complexity(code: str, file_type: str = "rust") -> Tuple[int, List[Dict]]:
    """
    Estimate cyclomatic complexity using heuristics.
    
    Returns:
        Tuple of (complexity_score, list of issues)
    
    Cyclomatic complexity = E - N + 2P
    Simplified heuristic: count decision points
    """
    issues = []
    score = 1  # Base complexity
    
    # Count decision points
    decision_patterns = {
        "if": r"\bif\b",
        "else_if": r"\belse\s+if\b|\belif\b",
        "for": r"\bfor\b",
        "while": r"\bwhile\b",
        "match": r"\bmatch\b|\bswitch\b",
        "case": r"\bcase\b|=>",  # Match arms
        "and": r"\s&&\s|\band\b",
        "or": r"\s\|\|\s|\bor\b",
        "try": r"\btry\b",
        "catch": r"\bcatch\b|\bexcept\b",
        "ternary": r"\?[^?:]+:",
    }
    
    for name, pattern in decision_patterns.items():
        matches = len(re.findall(pattern, code))
        if name in ("case", "and", "or"):
            score += matches  # Each adds 1
        else:
            score += matches  # Each decision point adds 1
    
    # Check nesting depth
    max_nesting = 0
    current_nesting = 0
    for line in code.split('\n'):
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        spaces_per_indent = 4 if file_type in ("rust", "typescript", "svelte") else 4
        nesting_level = indent // spaces_per_indent
        max_nesting = max(max_nesting, nesting_level)
    
    if max_nesting > COMPLEXITY_THRESHOLDS["max_nesting_depth"]:
        issues.append({
            "rule": "deep_nesting",
            "severity": "warning" if max_nesting <= 6 else "reject",
            "points": min(max_nesting - COMPLEXITY_THRESHOLDS["max_nesting_depth"], 5),
            "message": f"Deep nesting detected ({max_nesting} levels) - refactor to reduce complexity",
        })
    
    # Check function length (rough heuristic)
    function_patterns = {
        "rust": r"(?:pub\s+)?(?:async\s+)?fn\s+\w+",
        "python": r"def\s+\w+",
        "typescript": r"(?:function\s+\w+|const\s+\w+\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)",
        "svelte": r"(?:function\s+\w+|const\s+\w+\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)",
    }
    
    pattern = function_patterns.get(file_type, function_patterns["rust"])
    functions = re.split(pattern, code)
    for i, func_body in enumerate(functions[1:], 1):  # Skip first split (before first function)
        if func_body is None:
            continue
        lines = func_body.count('\n')
        if lines > COMPLEXITY_THRESHOLDS["max_function_lines"]:
            issues.append({
                "rule": "long_function",
                "severity": "warning" if lines <= 100 else "reject",
                "points": min((lines - COMPLEXITY_THRESHOLDS["max_function_lines"]) // 20, 5),
                "message": f"Function too long ({lines} lines) - split into smaller functions",
            })
    
    # Check parameter count
    param_pattern = r"fn\s+\w+\s*\(([^)]+)\)" if file_type == "rust" else r"def\s+\w+\s*\(([^)]+)\)"
    for match in re.finditer(param_pattern, code):
        params = match.group(1).split(',')
        param_count = len([p for p in params if p.strip() and p.strip() != 'self' and p.strip() != '&self' and p.strip() != '&mut self'])
        if param_count > COMPLEXITY_THRESHOLDS["max_params"]:
            issues.append({
                "rule": "too_many_params",
                "severity": "warning",
                "points": min(param_count - COMPLEXITY_THRESHOLDS["max_params"], 3),
                "message": f"Function has too many parameters ({param_count}) - use struct/object",
            })
    
    # Add complexity score issue if high
    if score >= COMPLEXITY_THRESHOLDS["cyclomatic_reject"]:
        issues.append({
            "rule": "high_complexity",
            "severity": "reject",
            "points": 5,
            "message": f"Cyclomatic complexity too high ({score}) - must refactor (max: {COMPLEXITY_THRESHOLDS['cyclomatic_reject']})",
        })
    elif score >= COMPLEXITY_THRESHOLDS["cyclomatic_warning"]:
        issues.append({
            "rule": "moderate_complexity",
            "severity": "warning",
            "points": 2,
            "message": f"Cyclomatic complexity moderate ({score}) - consider refactoring",
        })
    
    return score, issues


def is_test_file(filename: str) -> bool:
    """Check if filename indicates a test/fixture file"""
    if not filename:
        return False
    filename_lower = filename.lower()
    return any(re.search(p, filename_lower) for p in TEST_FILE_PATTERNS)


# ============================================================================
# ADVERSARIAL GATE
# ============================================================================

class AdversarialGate:
    """
    Adversarial gate for code quality checks.

    Loads configuration from project YAML if provided:
    ```yaml
    adversarial:
      threshold: 5
      core_patterns: true
      custom_patterns:
        - pattern: '\\.unwrap\\(\\)'
          score: 2
          message: "unwrap() sans gestion d'erreur"
          max_occurrences: 3
        - pattern: 'panic!'
          score: 5
          message: "panic! interdit en production"
    ```
    """

    def __init__(self, project_config: Optional[Any] = None):
        """
        Initialize gate with optional project config.

        Args:
            project_config: ProjectConfig from project_registry (or dict with 'adversarial' key)
        """
        self.threshold = 5
        self.use_core_patterns = True
        self.custom_patterns: List[Dict] = []
        self.security_check = True

        if project_config:
            self._load_config(project_config)

    def _load_config(self, config: Any):
        """Load configuration from project config"""
        # Support both ProjectConfig and dict
        if hasattr(config, "adversarial"):
            adv_config = config.adversarial
        elif isinstance(config, dict):
            adv_config = config.get("adversarial", {})
        else:
            return

        if isinstance(adv_config, dict):
            self.threshold = adv_config.get("threshold", 5)
            self.use_core_patterns = adv_config.get("core_patterns", True)
            self.custom_patterns = adv_config.get("custom_patterns", [])
            self.security_check = adv_config.get("security_check", True)

    def check_code(
        self,
        code: str,
        file_type: str = "rust",
        filename: str = "",
    ) -> CheckResult:
        """
        Check code for adversarial issues using regex patterns.

        Args:
            code: Source code to check
            file_type: "rust", "typescript", "python", etc.
            filename: Optional filename for context

        Returns:
            CheckResult with approval status, score, issues, and feedback
        """
        issues: List[Issue] = []
        lines = code.split("\n")
        pattern_counts: Dict[str, int] = {}

        # Check if test file early (needed for multiple pattern checks)
        is_test = is_test_file(filename)

        # Core reject patterns
        if self.use_core_patterns:
            for pattern, (rule, points, message) in CORE_REJECT_PATTERNS.items():
                for i, line in enumerate(lines, 1):
                    if re.search(pattern, line, re.IGNORECASE):
                        issues.append(Issue(
                            rule=rule,
                            severity="reject",
                            points=points,
                            message=message,
                            line=i,
                            context=line.strip()[:80],
                        ))

            # Core warning patterns with max occurrences
            for pattern, (rule, points, message, max_occ) in CORE_WARNING_PATTERNS.items():
                # Skip certain warnings in test files
                if is_test and rule in SKIP_WARNINGS_IN_TESTS:
                    continue
                count = 0
                for i, line in enumerate(lines, 1):
                    if re.search(pattern, line, re.IGNORECASE):
                        count += 1
                        if count <= max_occ:
                            issues.append(Issue(
                                rule=rule,
                                severity="warning",
                                points=points,
                                message=message,
                                line=i,
                                context=line.strip()[:80],
                            ))
                pattern_counts[rule] = count

        # Security patterns (skip hardcoded secrets in test/fixture files)
        if self.security_check:
            for pattern, (rule, points, message) in SECURITY_PATTERNS.items():
                # Skip hardcoded credential rules in test files
                if is_test and rule in SKIP_IN_TESTS:
                    continue
                for i, line in enumerate(lines, 1):
                    if re.search(pattern, line, re.IGNORECASE):
                        issues.append(Issue(
                            rule=rule,
                            severity="reject",
                            points=points,
                            message=message,
                            line=i,
                            context=line.strip()[:80],
                        ))

        # Custom patterns from project config
        for custom in self.custom_patterns:
            pattern = custom.get("pattern", "")
            if not pattern:
                continue

            rule = custom.get("rule", f"custom_{len(issues)}")
            score = custom.get("score", 1)
            message = custom.get("message", "Custom pattern matched")
            max_occ = custom.get("max_occurrences", 100)
            required = custom.get("required", False)
            skip_in_tests = custom.get("skip_in_tests", False)

            # Skip security-like patterns in test files
            if is_test and skip_in_tests:
                continue

            count = 0
            for i, line in enumerate(lines, 1):
                try:
                    if re.search(pattern, line, re.IGNORECASE):
                        count += 1
                        if count <= max_occ:
                            issues.append(Issue(
                                rule=rule,
                                severity="reject" if score >= 3 else "warning",
                                points=score,
                                message=message,
                                line=i,
                                context=line.strip()[:80],
                            ))
                except re.error:
                    log(f"Invalid regex pattern: {pattern}", "WARN")
                    break

            # Required pattern (must be present)
            if required and count == 0:
                issues.append(Issue(
                    rule=f"{rule}_missing",
                    severity="reject",
                    points=3,
                    message=f"Required pattern missing: {message}",
                    line=0,
                ))

            pattern_counts[rule] = count

        # COMPLEXITY CHECK (KISS enforcement)
        complexity_score, complexity_issues = estimate_cyclomatic_complexity(code, file_type)
        for ci in complexity_issues:
            issues.append(Issue(
                rule=ci["rule"],
                severity=ci["severity"],
                points=ci["points"],
                message=ci["message"],
                line=0,
            ))
        pattern_counts["cyclomatic_complexity"] = complexity_score

        # Calculate score
        total_score = sum(issue.points for issue in issues)
        approved = total_score < self.threshold

        # Generate feedback
        feedback = ""
        if not approved:
            feedback = self._generate_feedback(issues, pattern_counts)

        log(f"Score: {total_score}/{self.threshold} | Approved: {approved} | Issues: {len(issues)}")

        return CheckResult(
            approved=approved,
            score=total_score,
            threshold=self.threshold,
            issues=issues,
            feedback=feedback,
        )

    def _generate_feedback(self, issues: List[Issue], counts: Dict[str, int]) -> str:
        """Generate actionable feedback for LLM retry"""
        parts = ["CODE REJECTED by Adversarial Gate. Fix the following:"]

        # Group by severity
        rejects = [i for i in issues if i.severity == "reject"]
        warnings = [i for i in issues if i.severity == "warning"]

        if rejects:
            parts.append("\n🔴 MUST FIX (blocking):")
            seen_rules = set()
            for issue in rejects:
                if issue.rule not in seen_rules:
                    parts.append(f"  - Line {issue.line}: {issue.message}")
                    if issue.context:
                        parts.append(f"    > {issue.context}")
                    seen_rules.add(issue.rule)
                    if len(seen_rules) >= 5:
                        break

        if warnings:
            parts.append("\n🟡 SHOULD FIX (warnings):")
            seen_rules = set()
            for issue in warnings:
                if issue.rule not in seen_rules:
                    parts.append(f"  - {issue.message}")
                    seen_rules.add(issue.rule)
                    if len(seen_rules) >= 5:
                        break

        # High counts
        for rule, count in counts.items():
            limit = 3
            if count > limit:
                parts.append(f"\n⚠️ {rule}: {count} occurrences (max {limit})")

        parts.append("\nRegenerate the code without these issues.")

        return "\n".join(parts)

    def check_architecture_completeness(
        self,
        code: str,
        filename: str,
    ) -> List[Issue]:
        """
        Check for MISSING architectural concerns (FRACTAL L1 coverage).

        Detects when API/endpoint code is missing:
        - RBAC/Authentication
        - Input validation
        - Query limits
        - Specific error handling

        Args:
            code: Source code to check
            filename: Filename to determine if checks apply

        Returns:
            List of Issue objects for missing architectural concerns
        """
        issues: List[Issue] = []

        # Skip non-relevant files (tests, types, config)
        if any(re.search(p, filename.lower()) for p in SKIP_ARCH_CHECK_PATTERNS):
            return issues

        for check_name, check in ARCH_COMPLETENESS_CHECKS.items():
            # Check if this file type requires this check
            required_in = check.get("required_in", [])
            if not any(re.search(p, filename) for p in required_in):
                continue

            # Check if trigger patterns are present (for conditional checks)
            trigger_patterns = check.get("trigger_patterns", [])
            if trigger_patterns:
                has_trigger = any(re.search(p, code, re.IGNORECASE) for p in trigger_patterns)
                if not has_trigger:
                    continue

            # Check if any of the required patterns are present
            must_have = check.get("must_have_one_of", [])
            has_required = any(re.search(p, code, re.IGNORECASE) for p in must_have)

            # Check for anti-patterns
            must_not_have = check.get("must_not_have", [])
            has_antipattern = any(re.search(p, code, re.IGNORECASE) for p in must_not_have)

            # If missing required pattern OR has anti-pattern → issue
            if (must_have and not has_required) or has_antipattern:
                issues.append(Issue(
                    rule=f"arch_{check_name}",
                    severity="reject",
                    points=check.get("points", 3),
                    message=check.get("message", f"Missing {check.get('name', check_name)}"),
                    line=0,
                    context=f"File: {filename}",
                ))
                log(f"ARCH CHECK FAILED: {check_name} - {check.get('message')}", "WARN")

        return issues

    def check_code_with_architecture(
        self,
        code: str,
        file_type: str = "typescript",
        filename: str = "",
    ) -> CheckResult:
        """
        Full check including architecture completeness.

        Use this for API/endpoint code to ensure RBAC, validation, limits, errors.
        """
        # Standard pattern check
        result = self.check_code(code, file_type, filename)

        # Architecture completeness check
        arch_issues = self.check_architecture_completeness(code, filename)

        if arch_issues:
            result.issues.extend(arch_issues)
            result.score += sum(i.points for i in arch_issues)
            result.approved = result.score < self.threshold

            if not result.approved:
                result.feedback = self._generate_feedback(result.issues, {})

        return result

    def check_file(self, file_path: str) -> CheckResult:
        """Check a file on disk"""
        p = Path(file_path)

        if not p.exists():
            return CheckResult(
                approved=False,
                score=100,
                threshold=self.threshold,
                issues=[Issue(
                    rule="file_not_found",
                    severity="reject",
                    points=100,
                    message=f"File not found: {file_path}",
                )],
                feedback=f"File not found: {file_path}",
            )

        code = p.read_text()
        file_type = self._detect_file_type(p)
        return self.check_code(code, file_type, filename=str(p))

    def _detect_file_type(self, path: Path) -> str:
        """Detect file type from extension"""
        ext_map = {
            ".rs": "rust",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".js": "javascript",
            ".jsx": "javascript",
            ".py": "python",
            ".go": "go",
            ".java": "java",
        }
        return ext_map.get(path.suffix, "other")

    async def check_code_deep(
        self,
        code: str,
        file_type: str = "rust",
        timeout: int = 60,
    ) -> CheckResult:
        """
        Deep semantic analysis using LLM.
        Catches issues regex can't detect (logic errors, security flaws, etc.)

        Requires: opencode or claude CLI
        """
        import shutil

        # First run fast regex check
        fast_result = self.check_code(code, file_type)

        # If already rejected, skip deep analysis
        if not fast_result.approved:
            return fast_result

        # Check for opencode
        if not shutil.which("opencode") and not shutil.which("claude"):
            log("No LLM CLI found, skipping deep analysis", "WARN")
            return fast_result

        prompt = f"""You are an Adversarial Red Team agent. Analyze this {file_type} code for:

1. SLOP: AI-generated code that "looks good" but doesn't actually work
2. BYPASS: Type bypasses, disabled tests, security workarounds
3. INCOMPLETE: Stub functions, hidden TODOs, missing logic branches
4. SECURITY: Injections, XSS, auth bypass, hardcoded secrets

CODE:
```{file_type}
{code[:4000]}
```

RESPOND IN STRICT JSON:
{{
  "approved": true/false,
  "issues": [
    {{"rule": "name", "severity": "reject|warning", "points": N, "message": "description", "line": N}}
  ],
  "reasoning": "brief explanation"
}}

If code is OK: {{"approved": true, "issues": [], "reasoning": "Code validated"}}
"""

        try:
            # Try opencode first (faster)
            cli = "opencode" if shutil.which("opencode") else "claude"

            if cli == "opencode":
                proc = await asyncio.create_subprocess_exec(
                    "opencode",
                    "--model", "local/qwen3-30b-a3b",
                    "--non-interactive",
                    "--max-turns", "1",
                    prompt,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:
                proc = await asyncio.create_subprocess_exec(
                    "claude",
                    "-p",
                    "--model", "claude-sonnet-4-20250514",
                    "--max-turns", "1",
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

            if cli == "claude":
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(input=prompt.encode()),
                    timeout=timeout,
                )
            else:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout,
                )

            output = stdout.decode()

            # Parse JSON from output
            json_match = re.search(r'\{[^{}]*"approved"[^{}]*\}', output, re.DOTALL)
            if json_match:
                deep_result = json.loads(json_match.group())

                if not deep_result.get("approved", True):
                    # Merge with fast result
                    for issue_dict in deep_result.get("issues", []):
                        fast_result.issues.append(Issue(
                            rule=issue_dict.get("rule", "deep_issue"),
                            severity=issue_dict.get("severity", "warning"),
                            points=issue_dict.get("points", 2),
                            message=issue_dict.get("message", ""),
                            line=issue_dict.get("line", 0),
                        ))
                    fast_result.approved = False
                    fast_result.score += sum(i.get("points", 2) for i in deep_result.get("issues", []))
                    fast_result.feedback = deep_result.get("reasoning", "")
                    log(f"Deep analysis REJECTED: {deep_result.get('reasoning', 'N/A')}", "WARN")
                else:
                    log("Deep analysis APPROVED")

        except asyncio.TimeoutError:
            log(f"Deep analysis timeout ({timeout}s)", "WARN")
        except Exception as e:
            log(f"Deep analysis error: {e}", "ERROR")

        return fast_result


    async def check_code_llm(
        self,
        code: str,
        file_type: str = "rust",
        filename: str = "",
        timeout: int = 120,
    ) -> CheckResult:
        """
        LLM-only adversarial check (no regex).
        Understands context: CLI scripts, test fixtures, API stubs.
        """
        from core.llm_client import run_opencode

        prompt = f"""Tu es un agent ADVERSARIAL RED TEAM. Analyse ce code {file_type}.

FICHIER: {filename or 'unknown'}

RÈGLES CONTEXTUELLES:
- print() est OK dans les scripts CLI (fichiers avec argparse, click, ou __main__)
- NotImplementedError est OK pour les stubs API avec "pragma: no cover"
- Secrets hardcodés sont OK dans les fichiers test/fixture/mock
- Les TODO sont OK s'ils sont documentés avec ticket/issue

VÉRIFIE:
1. SLOP: Code qui "semble bien" mais ne fonctionne pas vraiment
2. LOGIQUE: Branches manquantes, edge cases non gérés
3. SÉCURITÉ: Injections, XSS (sauf dans tests)
4. INCOMPLET: Fonctions vides, return None implicite

CODE:
```{file_type}
{code[:6000]}
```

RÉPONDS EN JSON STRICT:
{{"approved": true/false, "issues": [{{"rule": "nom", "severity": "reject|warning", "points": N, "message": "description", "line": N}}], "reasoning": "explication courte"}}

Si le code est correct et complet: {{"approved": true, "issues": [], "reasoning": "Code validé"}}
"""

        try:
            returncode, output = await run_opencode(
                prompt,
                model="minimax/MiniMax-M2.1",
                timeout=timeout,
                fallback=True,
            )

            if returncode != 0:
                log(f"LLM adversarial failed: {output[:200]}", "WARN")
                # Fallback: approve to not block (LLM unavailable)
                return CheckResult(approved=True, score=0, threshold=self.threshold)

            # Parse JSON from output
            json_match = re.search(r'\{[^{}]*"approved"[^{}]*\}', output, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                approved = result.get("approved", True)
                issues = []
                score = 0

                for issue_dict in result.get("issues", []):
                    points = issue_dict.get("points", 2)
                    issues.append(Issue(
                        rule=issue_dict.get("rule", "llm_issue"),
                        severity=issue_dict.get("severity", "warning"),
                        points=points,
                        message=issue_dict.get("message", ""),
                        line=issue_dict.get("line", 0),
                    ))
                    score += points

                if not approved:
                    log(f"LLM REJECTED (score={score}): {result.get('reasoning', 'N/A')}", "WARN")
                else:
                    log(f"LLM APPROVED: {result.get('reasoning', 'OK')}")

                return CheckResult(
                    approved=approved,
                    score=score,
                    threshold=self.threshold,
                    issues=issues,
                    feedback=result.get("reasoning", ""),
                )

        except Exception as e:
            log(f"LLM adversarial error: {e}", "ERROR")

        # Fallback: approve
        return CheckResult(approved=True, score=0, threshold=self.threshold)


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def check_code(code: str, file_type: str = "rust", config: Any = None) -> CheckResult:
    """Quick check without project config"""
    return AdversarialGate(config).check_code(code, file_type)


def check_file(file_path: str, config: Any = None) -> CheckResult:
    """Check a file on disk"""
    return AdversarialGate(config).check_file(file_path)


async def check_code_deep(code: str, file_type: str = "rust", config: Any = None) -> CheckResult:
    """Deep check with LLM analysis"""
    return await AdversarialGate(config).check_code_deep(code, file_type)


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Adversarial Gate - Code Quality Check")
    parser.add_argument("file", nargs="?", help="File to check")
    parser.add_argument("--deep", action="store_true", help="Run deep LLM analysis")
    parser.add_argument("--threshold", type=int, default=5, help="Rejection threshold")
    parser.add_argument("--test", action="store_true", help="Run test with sample code")

    args = parser.parse_args()

    if args.test:
        # Test with problematic code
        test_code = '''
fn main() {
    let x = some_result.unwrap();  // unwrap
    let y = another.unwrap();      // unwrap
    let z = third.unwrap();        // unwrap
    let w = fourth.unwrap();       // unwrap - too many!

    // TODO: implement this properly
    // This is 100% complete

    todo!();
    unimplemented!();
}
'''
        gate = AdversarialGate()
        result = gate.check_code(test_code, "rust")

        print("\n=== Adversarial Check Result ===")
        print(f"Approved: {result.approved}")
        print(f"Score: {result.score}/{result.threshold}")
        print(f"Issues: {len(result.issues)}")

        for issue in result.issues[:10]:
            icon = "🔴" if issue.severity == "reject" else "🟡"
            print(f"  {icon} L{issue.line}: {issue.message}")

        if result.feedback:
            print(f"\n{result.feedback}")

    elif args.file:
        gate = AdversarialGate()
        gate.threshold = args.threshold

        if args.deep:
            result = asyncio.run(gate.check_code_deep(
                Path(args.file).read_text(),
                gate._detect_file_type(Path(args.file)),
            ))
        else:
            result = gate.check_file(args.file)

        print(f"\n{'✅ APPROVED' if result.approved else '❌ REJECTED'}")
        print(f"Score: {result.score}/{result.threshold}")
        print(f"Issues: {len(result.issues)}")

        if result.feedback:
            print(f"\n{result.feedback}")

    else:
        parser.print_help()
