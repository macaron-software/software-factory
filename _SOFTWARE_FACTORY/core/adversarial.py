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
    # Test skipping (SLOP) - instant reject
    r"\btest\.skip\b": ("test_skip", 5, "Test skip detected - tests must run"),
    r"\bdescribe\.skip\b": ("describe_skip", 5, "Describe skip detected - tests must run"),
    r"\bit\.skip\b": ("it_skip", 5, "It skip detected - tests must run"),
    r"#\[ignore\]": ("ignore_attr", 5, "Rust #[ignore] detected - tests must run"),

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
    r"raise\s+NotImplementedError": ("not_impl_py", 3, "NotImplementedError - incomplete code"),
}

# WARNING patterns: accumulate points
CORE_WARNING_PATTERNS = {
    r"\.unwrap\(\)": ("unwrap", 1, "Rust .unwrap() can panic", 3),  # max 3 occurrences
    r"\bany\b": ("any_type", 1, "TypeScript 'any' type detected", 5),  # max 5
    r"//\s*TODO\b": ("todo", 1, "TODO comment - incomplete code", 2),
    r"//\s*FIXME\b": ("fixme", 1, "FIXME comment - known issue", 2),
    r"//\s*STUB\b": ("stub", 2, "STUB comment - placeholder code", 1),
    r"catch\s*\([^)]*\)\s*\{\s*\}": ("empty_catch", 1, "Empty catch block", 3),
    r"todo!\s*\(\)": ("todo_macro", 2, "Rust todo!() macro - incomplete", 2),
    r"except:\s*pass": ("except_pass", 2, "Bare except: pass - swallows errors", 2),
}

# Security patterns
SECURITY_PATTERNS = {
    r'password\s*=\s*["\'][^"\']{3,}["\']': ("hardcoded_password", 5, "Hardcoded password detected"),
    r'api_key\s*=\s*["\'][^"\']{10,}["\']': ("hardcoded_api_key", 5, "Hardcoded API key detected"),
    r'secret\s*=\s*["\'][^"\']{10,}["\']': ("hardcoded_secret", 5, "Hardcoded secret detected"),
    r'Bearer\s+[a-zA-Z0-9_-]{20,}': ("hardcoded_token", 5, "Hardcoded bearer token"),
}


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

        # Security patterns
        if self.security_check:
            for pattern, (rule, points, message) in SECURITY_PATTERNS.items():
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
