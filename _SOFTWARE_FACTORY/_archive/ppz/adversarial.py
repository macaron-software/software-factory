#!/usr/bin/env python3
"""
Adversarial Agent - Code Quality Red Team
==========================================

ZÉRO SLOP. ZÉRO FAKE. ZÉRO CONTOURNEMENT.

Two modes:
1. FAST (regex): Pattern matching for known issues
2. DEEP (Qwen 30B via opencode): AI-powered semantic analysis

Checks:
- test.skip/describe.skip → REJECT (+5 pts)
- @ts-ignore/@ts-expect-error → REJECT (+2 pts)
- .unwrap() > 3 occurrences → WARNING (+1 pt)
- type 'any' in TypeScript → WARNING (+1 pt)
- TODO/FIXME/STUB > 2 → WARNING (+1 pt)
- "100%", "perfect", "complete" in comments → SLOP (+2 pts)
- Empty catch blocks → WARNING (+1 pt)
- Unimplemented methods with just panic!() → WARNING (+1 pt)

Score >= 5 → REJECT with feedback for retry

Usage:
    from adversarial import AdversarialAgent

    # Fast mode (regex only)
    agent = AdversarialAgent()
    result = agent.check_code(code_content, file_type="rust")

    # Deep mode (Qwen 30B via opencode)
    result = await agent.check_code_deep(code_content, file_type="rust")
"""

import re
import asyncio
import shutil
import tempfile
from dataclasses import dataclass
from typing import List, Dict
from datetime import datetime
from pathlib import Path


def log(msg: str, level: str = "INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [ADVERSARIAL] [{level}] {msg}", flush=True)


@dataclass
class AdversarialIssue:
    rule: str
    severity: str  # "reject", "warning"
    points: int
    message: str
    line: int = 0
    context: str = ""


class AdversarialAgent:
    """
    Red Team agent that checks code for slop, bypass, and hallucinations.
    """
    
    # REJECT rules (immediate failure patterns)
    REJECT_PATTERNS = {
        # Test skipping (SLOP)
        r'\btest\.skip\b': ("test.skip", 5, "Test skip detected - tests must run"),
        r'\bdescribe\.skip\b': ("describe.skip", 5, "Describe skip detected - tests must run"),
        r'\bit\.skip\b': ("it.skip", 5, "It skip detected - tests must run"),
        r'#\[ignore\]': ("ignore_attr", 5, "Rust #[ignore] detected - tests must run"),
        
        # TypeScript bypass
        r'@ts-ignore': ("ts-ignore", 2, "@ts-ignore bypasses type checking"),
        r'@ts-expect-error': ("ts-expect-error", 2, "@ts-expect-error bypasses type checking"),
        r'as\s+any\b': ("as_any", 2, "'as any' bypasses type checking"),
        
        # Slop words in comments
        r'//.*\b100%\b': ("slop_100", 2, "Slop: claiming '100%' in comments"),
        r'//.*\bperfect\b': ("slop_perfect", 2, "Slop: claiming 'perfect' in comments"),
        r'//.*\ball\s+cases\s+handled\b': ("slop_all", 2, "Slop: claiming 'all cases handled'"),
    }
    
    # WARNING rules (accumulate points)
    WARNING_PATTERNS = {
        r'\.unwrap\(\)': ("unwrap", 1, "Rust .unwrap() can panic"),
        r'\bany\b': ("any_type", 1, "TypeScript 'any' type detected"),
        r'//\s*TODO\b': ("todo", 1, "TODO comment - incomplete code"),
        r'//\s*FIXME\b': ("fixme", 1, "FIXME comment - known issue"),
        r'//\s*STUB\b': ("stub", 1, "STUB comment - placeholder code"),
        r'catch\s*\([^)]*\)\s*\{\s*\}': ("empty_catch", 1, "Empty catch block"),
        r'panic!\s*\(\s*"not\s+implemented': ("panic_unimpl", 1, "panic!(not implemented) - incomplete"),
        r'todo!\s*\(\)': ("todo_macro", 1, "Rust todo!() macro - incomplete"),
        r'unimplemented!\s*\(\)': ("unimpl_macro", 1, "Rust unimplemented!() - incomplete"),
    }
    
    # Threshold for rejection
    REJECT_THRESHOLD = 5
    
    def check_code(self, code: str, file_type: str = "rust") -> Dict:
        """
        Check code for adversarial issues.
        
        Returns:
            {
                "approved": bool,
                "score": int,
                "issues": [...],
                "feedback": str  # For retry if rejected
            }
        """
        issues: List[AdversarialIssue] = []
        lines = code.split('\n')
        
        # Check REJECT patterns
        for pattern, (rule, points, message) in self.REJECT_PATTERNS.items():
            for i, line in enumerate(lines, 1):
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append(AdversarialIssue(
                        rule=rule,
                        severity="reject",
                        points=points,
                        message=message,
                        line=i,
                        context=line.strip()[:80]
                    ))
        
        # Check WARNING patterns with count limits
        pattern_counts = {}
        for pattern, (rule, points, message) in self.WARNING_PATTERNS.items():
            count = 0
            for i, line in enumerate(lines, 1):
                if re.search(pattern, line, re.IGNORECASE):
                    count += 1
                    if count <= 3:  # Only add first 3 occurrences
                        issues.append(AdversarialIssue(
                            rule=rule,
                            severity="warning",
                            points=points,
                            message=message,
                            line=i,
                            context=line.strip()[:80]
                        ))
            pattern_counts[rule] = count
        
        # Calculate score
        total_score = sum(issue.points for issue in issues)
        approved = total_score < self.REJECT_THRESHOLD
        
        # Generate feedback for retry
        feedback = ""
        if not approved:
            feedback = self._generate_feedback(issues, pattern_counts)
        
        log(f"Score: {total_score} | Approved: {approved} | Issues: {len(issues)}")
        
        return {
            "approved": approved,
            "score": total_score,
            "issues": [
                {
                    "rule": i.rule,
                    "severity": i.severity,
                    "points": i.points,
                    "message": i.message,
                    "line": i.line,
                    "context": i.context
                }
                for i in issues
            ],
            "feedback": feedback
        }
    
    def _generate_feedback(self, issues: List[AdversarialIssue], counts: Dict) -> str:
        """Generate actionable feedback for the LLM to retry"""
        feedback_parts = ["CODE REJECTED by Adversarial Agent. Fix the following:"]
        
        # Group by severity
        rejects = [i for i in issues if i.severity == "reject"]
        warnings = [i for i in issues if i.severity == "warning"]
        
        if rejects:
            feedback_parts.append("\n🔴 MUST FIX (reject rules):")
            for issue in rejects[:5]:
                feedback_parts.append(f"  - Line {issue.line}: {issue.message}")
                feedback_parts.append(f"    Context: {issue.context}")
        
        if warnings:
            feedback_parts.append("\n🟡 SHOULD FIX (warnings):")
            for issue in warnings[:5]:
                feedback_parts.append(f"  - Line {issue.line}: {issue.message}")
        
        # Add counts if high
        for rule, count in counts.items():
            if count > 3:
                feedback_parts.append(f"\n⚠️ {rule}: {count} occurrences (too many)")
        
        feedback_parts.append("\nRegenerate the code without these issues.")
        
        return "\n".join(feedback_parts)
    
    def check_file(self, file_path: str) -> Dict:
        """Check a file on disk"""
        p = Path(file_path)

        if not p.exists():
            return {"approved": False, "score": 100, "issues": [], "feedback": f"File not found: {file_path}"}

        code = p.read_text()
        file_type = "rust" if p.suffix == ".rs" else "typescript" if p.suffix in [".ts", ".tsx"] else "other"

        return self.check_code(code, file_type)

    async def check_code_deep(self, code: str, file_type: str = "rust", timeout: int = 60) -> Dict:
        """
        Deep semantic analysis using Qwen 30B via opencode.
        Catches issues that regex can't detect (logic errors, security flaws, etc.)
        """
        # First run fast regex check
        fast_result = self.check_code(code, file_type)

        # If already rejected by regex, no need for deep analysis
        if not fast_result["approved"]:
            return fast_result

        # Run deep analysis with opencode + Qwen 30B
        if not shutil.which("opencode"):
            log("opencode not found, skipping deep analysis", "WARN")
            return fast_result

        prompt = f"""Tu es un agent Adversarial Red Team. Analyse ce code {file_type} pour détecter:

1. SLOP: Code généré par IA qui "semble bien" mais ne fonctionne pas vraiment
2. BYPASS: Contournements de types, tests, ou sécurité
3. INCOMPLET: Fonctions stub, TODO cachés, logique manquante
4. SECURITY: Injections, XSS, auth bypass, secrets hardcodés

CODE À ANALYSER:
```{file_type}
{code[:4000]}
```

RÉPONDS EN JSON STRICT:
{{
  "approved": true/false,
  "issues": [
    {{"rule": "nom", "severity": "reject|warning", "message": "description", "line": N}}
  ],
  "reasoning": "explication courte"
}}

Si le code est OK, retourne: {{"approved": true, "issues": [], "reasoning": "Code validé"}}
"""

        try:
            # Write prompt to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(prompt)
                prompt_file = f.name

            # Run opencode with Qwen 30B (via llama serve)
            proc = await asyncio.create_subprocess_exec(
                "opencode",
                "--model", "qwen3-30b-a3b",
                "--no-interactive",
                "--max-turns", "1",
                prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            output = stdout.decode()

            # Parse JSON from output
            import json
            # Find JSON in output
            json_match = re.search(r'\{[^{}]*"approved"[^{}]*\}', output, re.DOTALL)
            if json_match:
                deep_result = json.loads(json_match.group())

                # Merge with fast result
                if not deep_result.get("approved", True):
                    fast_result["approved"] = False
                    fast_result["issues"].extend(deep_result.get("issues", []))
                    fast_result["score"] += len(deep_result.get("issues", [])) * 2
                    fast_result["feedback"] = deep_result.get("reasoning", "")
                    log(f"Deep analysis REJECTED: {deep_result.get('reasoning', 'N/A')}", "WARN")
                else:
                    log("Deep analysis APPROVED")

            Path(prompt_file).unlink(missing_ok=True)

        except asyncio.TimeoutError:
            log(f"Deep analysis timeout ({timeout}s)", "WARN")
        except Exception as e:
            log(f"Deep analysis error: {e}", "ERROR")

        return fast_result


# Convenience function
def check_code(code: str, file_type: str = "rust") -> Dict:
    return AdversarialAgent().check_code(code, file_type)


# Test
if __name__ == "__main__":
    agent = AdversarialAgent()
    
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
    
    result = agent.check_code(test_code, "rust")
    
    print("\n=== Adversarial Check Result ===")
    print(f"Approved: {result['approved']}")
    print(f"Score: {result['score']}")
    print(f"Issues: {len(result['issues'])}")
    
    if not result['approved']:
        print(f"\nFeedback:\n{result['feedback']}")
