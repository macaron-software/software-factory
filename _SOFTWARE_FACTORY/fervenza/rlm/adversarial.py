"""
Adversarial Checker - Quality Gate for RLM.

Red team that validates generated code before it gets committed.
Two modes:
- Fast: Regex pattern matching (instant)
- Deep: LLM-based semantic analysis via Qwen 30B (opencode + llama serve)
"""

import json
import logging
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# LLM Config - Qwen 30B via llama serve (local)
LLAMA_SERVE_URL = os.getenv("LLAMA_SERVE_URL", "http://localhost:8080")
QWEN_MODEL = os.getenv("RLM_ADVERSARIAL_MODEL", "qwen3-30b-a3b")


@dataclass
class CheckResult:
    """Result of adversarial check."""

    reject: bool = False
    score: int = 0
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# Rejection patterns (5+ points = REJECT)
REJECT_PATTERNS = [
    # Skipped tests (5 points each)
    (r"test\.skip\s*\(", 5, "test.skip found - tests must not be skipped"),
    (r"describe\.skip\s*\(", 5, "describe.skip found - tests must not be skipped"),
    (r"it\.skip\s*\(", 5, "it.skip found - tests must not be skipped"),
    (r"#\[ignore\]", 5, "#[ignore] found - Rust tests must not be ignored"),
    (r"pytest\.mark\.skip", 5, "pytest.mark.skip found - tests must not be skipped"),
    (r"@pytest\.mark\.skip", 5, "@pytest.mark.skip found - tests must not be skipped"),
    (r"@unittest\.skip", 5, "@unittest.skip found - tests must not be skipped"),
    # Type suppressions (2 points each)
    (r"#\s*type:\s*ignore", 2, "# type: ignore found - fix the type error"),
    (r"@ts-ignore", 2, "@ts-ignore found - fix the TypeScript error"),
    (r"@ts-expect-error", 2, "@ts-expect-error found - fix the TypeScript error"),
    (r"as\s+any\b", 2, "as any found - use proper types"),
    (r":\s*any\b", 2, ": any found - use proper types"),
    # Dangerous patterns (2-3 points each)
    (r"\.unwrap\(\)", 2, ".unwrap() found - use ? operator for error handling"),
    (r"panic!\s*\(", 3, "panic! found - handle errors gracefully"),
    (r"unimplemented!\s*\(", 3, "unimplemented! found - implement the code"),
    (r"todo!\s*\(", 2, "todo! found - complete the implementation"),
    # Empty error handling (2 points each)
    (r"catch\s*\{\s*\}", 2, "Empty catch block found - handle errors"),
    (r"except:\s*pass", 2, "Bare except: pass found - handle errors"),
    (r"except Exception:\s*pass", 2, "except Exception: pass found - handle errors"),
]

# Warning patterns (1 point each, informational)
WARNING_PATTERNS = [
    (r"TODO\b", 1, "TODO comment found"),
    (r"FIXME\b", 1, "FIXME comment found"),
    (r"HACK\b", 1, "HACK comment found"),
    (r"XXX\b", 1, "XXX comment found"),
    (r"console\.log\(", 1, "console.log found - remove debug logging"),
    (r"print\s*\(", 1, "print() found - use logging instead"),
    (r"debugger\b", 1, "debugger statement found"),
]

# SLOP patterns (AI-generated junk)
SLOP_PATTERNS = [
    (r"100%", 2, "SLOP: '100%' claim found - be realistic"),
    (r"perfect(?:ly)?", 2, "SLOP: 'perfect' claim found - be realistic"),
    (r"seamless(?:ly)?", 1, "SLOP: 'seamless' buzzword found"),
    (r"cutting.?edge", 1, "SLOP: 'cutting-edge' buzzword found"),
    (r"state.?of.?the.?art", 1, "SLOP: 'state-of-the-art' buzzword found"),
    (r"revolutionary", 1, "SLOP: 'revolutionary' buzzword found"),
    (r"game.?changer", 1, "SLOP: 'game-changer' buzzword found"),
]


class AdversarialChecker:
    """
    Adversarial quality checker for generated code.

    Usage:
        checker = AdversarialChecker()
        result = checker.check_code(code)
        if result["reject"]:
            print(f"Rejected: {result['reasons']}")
    """

    def __init__(self, rejection_threshold: int = 5):
        self.rejection_threshold = rejection_threshold

    def check_code(self, code: str) -> dict:
        """
        Fast pattern-based code check.

        Args:
            code: The code to check

        Returns:
            dict with keys: reject, score, reasons, warnings
        """
        result = CheckResult()

        # Check rejection patterns
        for pattern, points, message in REJECT_PATTERNS:
            matches = re.findall(pattern, code, re.IGNORECASE)
            if matches:
                result.score += points * len(matches)
                result.reasons.append(f"{message} ({len(matches)}x)")

        # Check warning patterns
        for pattern, points, message in WARNING_PATTERNS:
            matches = re.findall(pattern, code)
            count = len(matches)
            if count > 2:  # Only warn if excessive
                result.score += points
                result.warnings.append(f"{message} ({count}x)")

        # Check SLOP patterns (only in comments)
        comment_lines = self._extract_comments(code)
        for pattern, points, message in SLOP_PATTERNS:
            for comment in comment_lines:
                if re.search(pattern, comment, re.IGNORECASE):
                    result.score += points
                    result.warnings.append(message)

        # Determine rejection
        result.reject = result.score >= self.rejection_threshold

        return {
            "reject": result.reject,
            "score": result.score,
            "reasons": result.reasons,
            "warnings": result.warnings,
        }

    def _extract_comments(self, code: str) -> list[str]:
        """Extract comment lines from code."""
        comments = []

        # Single-line comments
        comments.extend(re.findall(r"//.*$", code, re.MULTILINE))
        comments.extend(re.findall(r"#.*$", code, re.MULTILINE))

        # Multi-line comments
        comments.extend(re.findall(r"/\*.*?\*/", code, re.DOTALL))
        comments.extend(re.findall(r'""".*?"""', code, re.DOTALL))
        comments.extend(re.findall(r"'''.*?'''", code, re.DOTALL))

        return comments

    async def check_code_deep(self, code: str, task_description: str) -> dict:
        """
        Deep LLM-based semantic analysis via Qwen 30B.

        Uses opencode with llama serve for local inference.
        More thorough but slower. Use for critical fixes.

        Args:
            code: The code to check
            task_description: What the code is supposed to do

        Returns:
            dict with keys: reject, score, reasons, warnings, analysis
        """
        # First run fast check
        fast_result = self.check_code(code)

        # If already rejected, don't waste LLM call
        if fast_result["reject"]:
            return fast_result

        prompt = f"""Tu es un reviewer de code adversarial. Ton rôle est de trouver les problèmes.

TÂCHE ORIGINALE: {task_description}

CODE À VÉRIFIER:
```
{code}
```

Analyse ce code et identifie:
1. SLOP: Code qui "semble bien" mais ne fait rien d'utile
2. BYPASS: Contournements cachés (skip, ignore, stub)
3. INCOMPLET: Logique manquante ou TODO non résolus
4. SECURITY: Injections, secrets hardcodés, XSS
5. QUALITÉ: Mauvaises pratiques, code mort

Réponds en JSON strict:
{{
  "issues": [
    {{"type": "SLOP|BYPASS|INCOMPLET|SECURITY|QUALITÉ", "severity": "low|medium|high|critical", "message": "..."}}
  ],
  "verdict": "APPROVE|REJECT",
  "summary": "..."
}}
"""

        try:
            # Call opencode with llama serve (Qwen 30B)
            content = await self._call_qwen(prompt)

            if not content:
                fast_result["warnings"].append("Deep analysis unavailable (Qwen not running)")
                return fast_result

            # Extract JSON from response
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group())

                # Add LLM findings to result
                for issue in analysis.get("issues", []):
                    severity = issue.get("severity", "medium")
                    points = {"critical": 5, "high": 3, "medium": 2, "low": 1}.get(
                        severity, 1
                    )
                    fast_result["score"] += points

                    if points >= 3:
                        fast_result["reasons"].append(
                            f"[{issue['type']}] {issue['message']}"
                        )
                    else:
                        fast_result["warnings"].append(
                            f"[{issue['type']}] {issue['message']}"
                        )

                fast_result["analysis"] = analysis.get("summary", "")
                fast_result["reject"] = (
                    analysis.get("verdict") == "REJECT"
                    or fast_result["score"] >= self.rejection_threshold
                )

        except Exception as e:
            logger.warning(f"Deep check failed: {e}")
            fast_result["warnings"].append(f"Deep analysis failed: {e}")

        return fast_result

    async def _call_qwen(self, prompt: str) -> Optional[str]:
        """
        Call Qwen 30B via opencode + llama serve.

        Requires llama serve running locally with Qwen model:
            llama serve qwen3-30b-a3b
        """
        try:
            # Write prompt to temp file
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
                f.write(prompt)
                prompt_file = f.name

            # Call opencode with llama serve backend
            result = subprocess.run(
                [
                    "opencode",
                    "--model", f"ollama/{QWEN_MODEL}",
                    "--api-base", LLAMA_SERVE_URL,
                    "--prompt", f"@{prompt_file}",
                    "--no-interactive",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )

            # Clean up
            Path(prompt_file).unlink(missing_ok=True)

            if result.returncode != 0:
                logger.warning(f"opencode/qwen failed: {result.stderr[:200]}")
                return None

            return result.stdout

        except subprocess.TimeoutExpired:
            logger.warning("Qwen analysis timed out")
            return None
        except FileNotFoundError:
            logger.warning("opencode not found")
            return None
        except Exception as e:
            logger.warning(f"Qwen call error: {e}")
            return None

    def check_diff(self, diff: str) -> dict:
        """
        Check a git diff for issues.

        Args:
            diff: Git diff output

        Returns:
            dict with check result
        """
        # Extract added lines only (lines starting with +)
        added_lines = []
        for line in diff.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                added_lines.append(line[1:])

        code = "\n".join(added_lines)
        return self.check_code(code)


def main():
    """CLI entry point for Adversarial Checker."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Adversarial Code Checker")
    parser.add_argument("file", nargs="?", help="File to check")
    parser.add_argument("--stdin", action="store_true", help="Read from stdin")
    parser.add_argument("--diff", action="store_true", help="Check git diff format")
    parser.add_argument(
        "--threshold", type=int, default=5, help="Rejection threshold (default: 5)"
    )
    args = parser.parse_args()

    checker = AdversarialChecker(rejection_threshold=args.threshold)

    if args.stdin:
        code = sys.stdin.read()
    elif args.file:
        with open(args.file) as f:
            code = f.read()
    else:
        parser.print_help()
        sys.exit(1)

    if args.diff:
        result = checker.check_diff(code)
    else:
        result = checker.check_code(code)

    import json

    print(json.dumps(result, indent=2))

    sys.exit(1 if result["reject"] else 0)


if __name__ == "__main__":
    main()
