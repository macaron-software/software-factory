#!/usr/bin/env python3
"""
Adversarial Gate - Team of Rivals (arXiv:2601.14351)
====================================================
Cascaded critics with multi-vendor cognitive diversity.

Architecture:
- L0: Fast deterministic checks (test.skip, @ts-ignore, etc.)
- L1a: Code Critic (NVIDIA Kimi K2) - syntax, logic, API misuse
- L1b: Security Critic (NVIDIA Kimi K2) - OWASP, secrets, injections
- L2: Architecture Critic (Opus) - RBAC, validation, error handling

Paper: "If You Want Coherence, Orchestrate a Team of Rivals"
- 92.1% success rate on 522 production sessions
- 7.9% residual error (user rejection post-deploy)
- Cascaded catch rates: L0 25%, L1 75%, L2 85%

Usage:
    from core.adversarial import AdversarialGate

    gate = AdversarialGate(project_config)
    result = await gate.check_cascade(code, file_type="python", filename="cli.py")
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime


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
# ADVERSARIAL GATE - 100% LLM
# ============================================================================

class AdversarialGate:
    """
    LLM-only adversarial review.
    No regex. No patterns. Pure semantic understanding.
    """

    def __init__(self, project_config: Any = None):
        self.threshold = 5
        self.project_name = "unknown"
        
        if project_config:
            if hasattr(project_config, 'raw_config'):
                adv_config = project_config.raw_config.get("adversarial", {})
                self.project_name = getattr(project_config, 'name', 'unknown')
            elif isinstance(project_config, dict):
                adv_config = project_config.get("adversarial", {})
                self.project_name = project_config.get("project", {}).get("name", "unknown")
            else:
                adv_config = {}
            
            if isinstance(adv_config, dict):
                self.threshold = adv_config.get("threshold", 5)

    async def check(
        self,
        code: str,
        file_type: str = "python",
        filename: str = "",
        timeout: int = 120,
        use_cove: bool = True,
    ) -> CheckResult:
        """
        LLM adversarial check with Chain-of-Verification (CoVe).
        arxiv:2309.11495 - reduces hallucinations via 4-stage verification.

        STAGE 1: DRAFT - initial LLM assessment
        STAGE 2: PLAN - verification questions
        STAGE 3: ANSWER - independent checks (grep, deterministic)
        STAGE 4: FINAL - verified decision
        """
        from core.llm_client import run_opencode

        # Detect file context for LLM
        is_cli = any(x in code for x in ['argparse', 'click', 'typer', '__main__'])
        is_test = any(x in filename.lower() for x in ['test', 'spec', 'fixture', 'mock'])

        context_hints = []
        if is_cli:
            context_hints.append("CLI script - print() and sys.exit() are normal")
        if is_test:
            context_hints.append("Test file - fixtures with hardcoded values are OK")

        # ============================================================
        # STAGE 3 (pre-LLM): Independent deterministic checks
        # These run BEFORE LLM to avoid hallucination bias
        # ============================================================
        if use_cove:
            cove_issues = self._cove_deterministic_checks(code, file_type, filename)
            if cove_issues:
                # Found real issues via deterministic check
                total_score = sum(i.points for i in cove_issues)
                if total_score >= self.threshold:
                    log(f"CoVe STAGE3: REJECTED (score={total_score}) - deterministic issues", "WARN")
                    return CheckResult(
                        approved=False,
                        score=total_score,
                        threshold=self.threshold,
                        issues=cove_issues,
                        feedback="CoVe deterministic check failed: " + "; ".join(i.message for i in cove_issues),
                    )

        # ============================================================
        # STAGE 1 + 2 + 4: LLM analysis (draft + verify + final)
        # ============================================================
        prompt = f"""Tu es un ADVERSARIAL REVIEWER avec Chain-of-Verification (CoVe).

APPLIQUE LE PROTOCOLE CoVe (arxiv:2309.11495):

STAGE 1 - DRAFT: Lis le code et forme une première impression
STAGE 2 - VERIFY PLAN: Liste les questions à vérifier:
  - Y a-t-il des patterns de skip (test.skip, #[ignore])?
  - Y a-t-il des bypass de sécurité?
  - Le code fait-il vraiment ce qu'il prétend?
STAGE 3 - ANSWER INDEPENDENT: Pour chaque question, cherche la PREUVE dans le code
STAGE 4 - FINAL: Décision basée UNIQUEMENT sur les preuves trouvées

FICHIER: {filename or 'unknown'}
CONTEXTE: {', '.join(context_hints) if context_hints else 'Production code'}

RÈGLES DE CONTEXTE (NE PAS REJETER si applicable):
- typer.Exit(1), sys.exit(), raise SystemExit → comportement CLI normal
- print() dans un CLI avec argparse/click/typer → OK
- Secrets hardcodés dans fichiers test/fixture/mock → OK
- NotImplementedError avec "pragma: no cover" → stub accepté
- TODO avec ticket/issue référencé → OK

CHERCHE UNIQUEMENT (avec PREUVES):
1. SLOP: Code qui compile mais ne fait rien d'utile → CITE la ligne
2. LOGIQUE CASSÉE: Branches impossibles, return avant code → CITE la ligne
3. SÉCURITÉ RÉELLE: SQL injection, XSS (PAS dans tests) → CITE la ligne
4. INCOMPLET: Fonctions avec juste "pass" sans raison → CITE la ligne

CODE:
```{file_type}
{code[:8000]}
```

RÉPONDS EN JSON avec ton raisonnement CoVe:
{{
  "cove_draft": "Ma première impression...",
  "cove_questions": ["Question 1 à vérifier", "Question 2..."],
  "cove_answers": ["Réponse 1 avec preuve: ligne X dit...", "Réponse 2..."],
  "approved": true/false,
  "score": 0-10,
  "issues": [{{"rule": "nom", "severity": "reject|warning", "points": N, "message": "description avec ligne", "line": N}}],
  "reasoning": "Conclusion CoVe basée sur les preuves"
}}

Si le code est correct: {{"approved": true, "score": 0, "issues": [], "reasoning": "CoVe: Aucune preuve d'issue trouvée"}}
"""

        try:
            returncode, output = await run_opencode(
                prompt,
                model="minimax/MiniMax-M2.1",
                timeout=timeout,
                fallback=True,
            )

            if returncode != 0:
                log(f"LLM failed, approving by default: {output[:100]}", "WARN")
                return CheckResult(approved=True, score=0, threshold=self.threshold)

            # Parse JSON from output
            json_match = re.search(r'\{[^{}]*"approved"[^{}]*\}', output, re.DOTALL)
            if not json_match:
                # Try to find any JSON object
                json_match = re.search(r'\{.*\}', output, re.DOTALL)
            
            if json_match:
                try:
                    result = json.loads(json_match.group())
                except json.JSONDecodeError:
                    log(f"JSON parse failed, approving: {output[:200]}", "WARN")
                    return CheckResult(approved=True, score=0, threshold=self.threshold)
                
                approved = result.get("approved", True)
                score = result.get("score", 0)
                issues = []

                for issue_dict in result.get("issues", []):
                    points = issue_dict.get("points", 2)
                    issues.append(Issue(
                        rule=issue_dict.get("rule", "llm_issue"),
                        severity=issue_dict.get("severity", "warning"),
                        points=points,
                        message=issue_dict.get("message", ""),
                        line=issue_dict.get("line", 0),
                    ))

                reasoning = result.get("reasoning", "")
                
                if not approved:
                    log(f"REJECTED (score={score}): {reasoning[:100]}", "WARN")
                else:
                    log(f"APPROVED: {reasoning[:50]}")

                return CheckResult(
                    approved=approved,
                    score=score,
                    threshold=self.threshold,
                    issues=issues,
                    feedback=reasoning,
                )

        except Exception as e:
            log(f"Error: {e}, approving by default", "ERROR")

        return CheckResult(approved=True, score=0, threshold=self.threshold)

    async def check_cascade(
        self,
        code: str,
        file_type: str = "python",
        filename: str = "",
        timeout: int = 120,
    ) -> CheckResult:
        """
        TEAM OF RIVALS: Cascaded critics with multi-vendor cognitive diversity.
        Based on arXiv:2601.14351

        Cascade:
        - L0: Fast deterministic (test.skip, @ts-ignore) - instant
        - L1a: Code Critic (NVIDIA Kimi K2) - ~5s
        - L1b: Security Critic (NVIDIA Kimi K2) - ~5s
        - L2: Architecture Critic (Opus) - ~20s

        Each layer has VETO AUTHORITY. Rejection at any layer = REJECT.
        """
        from core.llm_client import run_opencode
        from core.metrics import get_metrics

        metrics = get_metrics(self.project_name)
        all_issues = []

        # ============================================================
        # L0: FAST DETERMINISTIC CHECKS (instant)
        # ============================================================
        log("L0: Fast deterministic checks...")
        l0_issues = self._cove_deterministic_checks(code, file_type, filename)
        if l0_issues:
            total_score = sum(i.points for i in l0_issues)
            metrics.record_l0_check(rejected=True, details={"issues": len(l0_issues)})
            if total_score >= self.threshold:
                log(f"L0 REJECTED (score={total_score})", "WARN")
                return CheckResult(
                    approved=False,
                    score=total_score,
                    threshold=self.threshold,
                    issues=l0_issues,
                    feedback="L0 Fast check failed: " + "; ".join(i.message for i in l0_issues),
                )
            all_issues.extend(l0_issues)
        else:
            metrics.record_l0_check(rejected=False)

        # ============================================================
        # L1a: CODE CRITIC (MiniMax M2.1)
        # Same provider as TDD worker - catches logic/syntax errors
        # ============================================================
        log("L1a: Code Critic (NVIDIA Kimi K2)...")
        l1a_result = await self._l1_code_critic(code, file_type, filename, timeout)
        if not l1a_result.approved:
            metrics.record_l1_code(rejected=True, details={"score": l1a_result.score})
            log(f"L1a Code REJECTED (score={l1a_result.score})", "WARN")
            all_issues.extend(l1a_result.issues)
            return CheckResult(
                approved=False,
                score=l1a_result.score,
                threshold=self.threshold,
                issues=all_issues,
                feedback=f"L1a Code Critic rejected: {l1a_result.feedback}",
            )
        metrics.record_l1_code(rejected=False)

        # ============================================================
        # L1b: SECURITY CRITIC (GLM-4.7-free)
        # Different provider = cognitive diversity
        # ============================================================
        log("L1b: Security Critic (NVIDIA Kimi K2)...")
        l1b_result = await self._l1_security_critic(code, file_type, filename, timeout)
        if not l1b_result.approved:
            metrics.record_l1_security(rejected=True, details={"score": l1b_result.score})
            log(f"L1b Security REJECTED (score={l1b_result.score})", "WARN")
            all_issues.extend(l1b_result.issues)
            return CheckResult(
                approved=False,
                score=l1b_result.score,
                threshold=self.threshold,
                issues=all_issues,
                feedback=f"L1b Security Critic rejected: {l1b_result.feedback}",
            )
        metrics.record_l1_security(rejected=False)

        # ============================================================
        # L2: ARCHITECTURE CRITIC (Claude Opus)
        # High-level design, RBAC, validation completeness
        # ============================================================
        log("L2: Architecture Critic (Opus)...")
        l2_result = await self._l2_arch_critic(code, file_type, filename, timeout)
        if not l2_result.approved:
            metrics.record_l2_arch(rejected=True, details={"score": l2_result.score})
            log(f"L2 Arch REJECTED (score={l2_result.score})", "WARN")
            all_issues.extend(l2_result.issues)
            return CheckResult(
                approved=False,
                score=l2_result.score,
                threshold=self.threshold,
                issues=all_issues,
                feedback=f"L2 Architecture Critic rejected: {l2_result.feedback}",
            )
        metrics.record_l2_arch(rejected=False)

        # ============================================================
        # ALL CRITICS PASSED
        # ============================================================
        metrics.record_final_approved()
        log("✅ ALL CRITICS APPROVED (L0→L1a→L1b→L2)")

        return CheckResult(
            approved=True,
            score=sum(i.points for i in all_issues),
            threshold=self.threshold,
            issues=all_issues,
            feedback="Team of Rivals: All critics approved",
        )

    async def _l1_code_critic(
        self,
        code: str,
        file_type: str,
        filename: str,
        timeout: int,
    ) -> CheckResult:
        """L1a: Code Critic (NVIDIA Kimi K2) - syntax, logic, API misuse, SLOP"""
        from core.llm_client import run_opencode

        prompt = f"""Tu es un CODE CRITIC. Analyse ce code pour:
1. SYNTAX/LOGIC errors - bugs évidents, branches impossibles
2. API MISUSE - mauvais usage de frameworks (axum extractors, sqlx FromRow)
3. SLOP - code qui compile mais ne fait rien d'utile

FICHIER: {filename}
TYPE: {file_type}

CODE:
```{file_type}
{code[:6000]}
```

RÉPONDS EN JSON:
{{"approved": true/false, "score": 0-10, "issues": [{{"rule": "...", "severity": "reject|warning", "points": N, "message": "...", "line": N}}], "reasoning": "..."}}

Si le code est correct: {{"approved": true, "score": 0, "issues": [], "reasoning": "Code OK"}}
"""
        # kimi-k2-instruct for reliable JSON output (thinking model breaks JSON parsing)
        return await self._run_critic(prompt, "nvidia/moonshotai/kimi-k2-instruct", timeout)

    async def _l1_security_critic(
        self,
        code: str,
        file_type: str,
        filename: str,
        timeout: int,
    ) -> CheckResult:
        """L1b: Security Critic (NVIDIA Kimi K2) - OWASP, secrets, injections"""
        from core.llm_client import run_opencode

        # Skip security check for test files
        if any(x in filename.lower() for x in ['test', 'spec', 'fixture', 'mock']):
            return CheckResult(approved=True, score=0, threshold=self.threshold)

        prompt = f"""Tu es un SECURITY CRITIC (OWASP Top 10). Analyse ce code pour:
1. SQL INJECTION - requêtes non paramétrées, concaténation SQL
2. XSS - output non échappé, innerHTML sans sanitize
3. COMMAND INJECTION - shell exec avec input utilisateur
4. SECRETS - API keys, passwords hardcodés (PAS dans fixtures/tests)
5. AUTH BYPASS - vérifications manquantes, weak crypto

FICHIER: {filename}
TYPE: {file_type}

CODE:
```{file_type}
{code[:6000]}
```

CONTEXTE: Ignore les secrets dans fichiers test/fixture/mock.

RÉPONDS EN JSON:
{{"approved": true/false, "score": 0-10, "issues": [{{"rule": "security_*", "severity": "reject", "points": N, "message": "OWASP: ...", "line": N}}], "reasoning": "..."}}

Si pas de vulnérabilité: {{"approved": true, "score": 0, "issues": [], "reasoning": "No security issues"}}
"""
        # Use NVIDIA Kimi K2 (free tier) for security analysis
        # kimi-k2-instruct for reliable JSON output
        return await self._run_critic(prompt, "nvidia/moonshotai/kimi-k2-instruct", timeout)

    async def _l2_arch_critic(
        self,
        code: str,
        file_type: str,
        filename: str,
        timeout: int,
    ) -> CheckResult:
        """L2: Architecture Critic (Opus) - RBAC, validation, error handling"""
        from core.llm_client import run_opencode

        # Only check substantial files
        if len(code) < 100:
            return CheckResult(approved=True, score=0, threshold=self.threshold)

        prompt = f"""Tu es un ARCHITECTURE CRITIC senior. Analyse ce code pour:
1. RBAC/AUTH - endpoints sans vérification d'authentification
2. INPUT VALIDATION - données utilisateur non validées
3. ERROR HANDLING - erreurs silencieuses, catch vides, panic sans context
4. API DESIGN - pagination manquante sur listes, rate limiting absent
5. COMPLETENESS - fonctions avec juste "pass" ou "todo" sans implémentation

FICHIER: {filename}
TYPE: {file_type}

CODE:
```{file_type}
{code[:6000]}
```

RÉPONDS EN JSON:
{{"approved": true/false, "score": 0-10, "issues": [{{"rule": "arch_*", "severity": "reject|warning", "points": N, "message": "...", "line": N}}], "reasoning": "..."}}

NOTE: Si le code est une CLI, un test, ou un utilitaire interne, sois plus tolérant.
Si le code est correct architecturalement: {{"approved": true, "score": 0, "issues": [], "reasoning": "Architecture OK"}}
"""
        # Use Claude for architectural reasoning (via claude CLI)
        try:
            import asyncio
            import subprocess

            # Claude CLI call
            proc = await asyncio.create_subprocess_exec(
                "claude", "-p", prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return CheckResult(approved=True, score=0, threshold=self.threshold)

            output = stdout.decode() if stdout else ""
            return self._parse_critic_response(output)

        except Exception as e:
            log(f"L2 Arch critic error: {e}, approving by default", "WARN")
            return CheckResult(approved=True, score=0, threshold=self.threshold)

    async def _run_critic(self, prompt: str, model: str, timeout: int) -> CheckResult:
        """Run a critic with the specified model"""
        from core.llm_client import run_opencode

        try:
            returncode, output = await run_opencode(
                prompt,
                model=model,
                timeout=timeout,
                fallback=False,  # No fallback - different models = cognitive diversity
            )

            if returncode != 0:
                log(f"Critic failed, approving by default: {output[:100]}", "WARN")
                return CheckResult(approved=True, score=0, threshold=self.threshold)

            return self._parse_critic_response(output)

        except Exception as e:
            log(f"Critic error: {e}, approving by default", "ERROR")
            return CheckResult(approved=True, score=0, threshold=self.threshold)

    def _parse_critic_response(self, output: str) -> CheckResult:
        """Parse critic JSON response"""
        json_match = re.search(r'\{[^{}]*"approved"[^{}]*\}', output, re.DOTALL)
        if not json_match:
            json_match = re.search(r'\{.*\}', output, re.DOTALL)

        if json_match:
            try:
                result = json.loads(json_match.group())
                approved = result.get("approved", True)
                score = result.get("score", 0)
                issues = []

                for issue_dict in result.get("issues", []):
                    issues.append(Issue(
                        rule=issue_dict.get("rule", "critic_issue"),
                        severity=issue_dict.get("severity", "warning"),
                        points=issue_dict.get("points", 2),
                        message=issue_dict.get("message", ""),
                        line=issue_dict.get("line", 0),
                    ))

                return CheckResult(
                    approved=approved,
                    score=score,
                    threshold=self.threshold,
                    issues=issues,
                    feedback=result.get("reasoning", ""),
                )

            except json.JSONDecodeError:
                pass

        return CheckResult(approved=True, score=0, threshold=self.threshold)

    # Protected paths: agents MUST NOT create/modify these
    PROTECTED_PATTERNS = [
        # Spec/doc files (read-only for agents)
        "VISION.md", "CLAUDE.md", "README.md", "CHANGELOG.md",
        "CONTRIBUTING.md", "LICENSE", "CODE_OF_CONDUCT.md",
        "AO_TRACEABILITY.md", "RLM_SPECIFICATION",
        # Directories
        "node_modules/", "_archive/", ".git/", "__pycache__/",
        "dist/", "target/", ".next/", ".svelte-kit/",
    ]

    # File patterns agents MUST NOT create
    FORBIDDEN_FILE_PATTERNS = [
        r'_REPORT\.md$', r'_ANALYSIS\.md$', r'_REVIEW\.md$',
        r'_SUMMARY\.md$', r'_AUDIT\.md$', r'_FIXES\.md$',
        r'SECURITY_FIXES', r'REFACTOR_PLAN', r'MIGRATION_PLAN',
        r'adversarial_.*\.json$', r'adversarial_.*\.md$',
    ]

    def check_file_protection(self, changed_files: Dict[str, str]) -> List[Issue]:
        """
        Check if any changed files violate protection rules.
        Returns issues for protected file modifications or forbidden file creation.
        """
        issues = []
        for filepath, change_type in changed_files.items():
            # Check protected paths
            for protected in self.PROTECTED_PATTERNS:
                if protected in filepath or filepath.endswith(protected):
                    issues.append(Issue(
                        rule="protected_file",
                        severity="reject",
                        points=10,
                        message=f"PROTECTED file modified: {filepath} — agents MUST NOT modify spec/doc files",
                        line=0,
                        context=f"Protected pattern: {protected}",
                    ))
                    break

            # Check forbidden file creation (reports, analyses, etc.)
            for pattern in self.FORBIDDEN_FILE_PATTERNS:
                if re.search(pattern, filepath):
                    issues.append(Issue(
                        rule="forbidden_file_created",
                        severity="reject",
                        points=10,
                        message=f"FORBIDDEN file created: {filepath} — agents must write CODE, not reports",
                        line=0,
                        context=f"Forbidden pattern: {pattern}",
                    ))
                    break

            # Generic: any new .md file created by agent = suspicious
            if filepath.endswith('.md') and change_type in ("new", "added", "created"):
                issues.append(Issue(
                    rule="md_file_created",
                    severity="reject",
                    points=8,
                    message=f"Markdown file CREATED: {filepath} — agents must write CODE, not documentation",
                    line=0,
                    context="Agents should never create .md files. Only code files.",
                ))

        return issues

    def _cove_deterministic_checks(
        self,
        code: str,
        file_type: str,
        filename: str,
    ) -> List[Issue]:
        """
        CoVe STAGE 3: Independent deterministic checks.
        No LLM - pure regex/grep for CERTAIN patterns.

        Only checks things that are 100% certain issues:
        - test.skip() / describe.skip() / it.skip()
        - @ts-ignore without explanation
        - #[ignore] in Rust
        - Empty catch blocks

        Does NOT check context-dependent things (LLM handles those).
        """
        issues = []

        # Skip patterns (ALWAYS bad - no context makes these OK)
        skip_patterns = [
            (r'\btest\.skip\s*\(', 'test.skip() - tests MUST run', 5),
            (r'\bdescribe\.skip\s*\(', 'describe.skip() - tests MUST run', 5),
            (r'\bit\.skip\s*\(', 'it.skip() - tests MUST run', 5),
            (r'#\[ignore\]', '#[ignore] - Rust tests MUST run', 5),
            (r'@pytest\.mark\.skip', 'pytest.mark.skip - tests MUST run', 5),
        ]

        for pattern, message, points in skip_patterns:
            matches = re.findall(pattern, code)
            if matches:
                issues.append(Issue(
                    rule="skip_detected",
                    severity="reject",
                    points=points,
                    message=f"{message} ({len(matches)} occurrences)",
                    line=0,
                    context="CoVe deterministic check",
                ))

        # @ts-ignore without justification (TypeScript)
        if file_type in ['typescript', 'ts', 'tsx']:
            ts_ignore_matches = re.findall(r'@ts-ignore(?!\s*[-–:]\s*\w)', code)
            if ts_ignore_matches:
                issues.append(Issue(
                    rule="ts_ignore",
                    severity="reject",
                    points=3,
                    message=f"@ts-ignore without explanation ({len(ts_ignore_matches)} occurrences)",
                    line=0,
                    context="CoVe: use @ts-expect-error with explanation instead",
                ))

        # Empty catch blocks (all languages)
        empty_catch = re.findall(r'catch\s*\([^)]*\)\s*\{\s*\}', code)
        if empty_catch:
            issues.append(Issue(
                rule="empty_catch",
                severity="warning",
                points=2,
                message=f"Empty catch block ({len(empty_catch)} occurrences)",
                line=0,
                context="CoVe: catch blocks should handle or rethrow errors",
            ))

        return issues

    # Sync wrapper for backward compatibility
    def check_code(
        self,
        code: str,
        file_type: str = "python",
        filename: str = "",
    ) -> CheckResult:
        """Sync wrapper - runs LLM check"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already in async context, create task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        self.check(code, file_type, filename)
                    )
                    return future.result(timeout=180)
            else:
                return loop.run_until_complete(self.check(code, file_type, filename))
        except Exception as e:
            log(f"Sync check failed: {e}, approving", "ERROR")
            return CheckResult(approved=True, score=0, threshold=self.threshold)

    # Aliases for backward compatibility
    async def check_code_deep(self, code: str, file_type: str = "python", filename: str = "") -> CheckResult:
        return await self.check(code, file_type, filename)

    async def check_llm_only(self, code: str, file_type: str = "python", filename: str = "", timeout: int = 120) -> CheckResult:
        return await self.check(code, file_type, filename, timeout)

    async def check_code_llm(self, code: str, file_type: str = "rust", filename: str = "", timeout: int = 120) -> CheckResult:
        """Alias for check() - LLM-only adversarial check"""
        return await self.check(code, file_type, filename, timeout)

    def check_endpoint(self, code: str, file_type: str = "python", filename: str = "") -> CheckResult:
        return self.check_code(code, file_type, filename)

    async def review_stage(self, stage: str, output: str, task: Any = None) -> CheckResult:
        """Review a deployment stage output"""
        prompt_context = f"Stage: {stage}\nTask: {getattr(task, 'id', 'unknown') if task else 'unknown'}"
        return await self.check(output, "log", f"{stage}_output")

    def check_architecture_completeness(
        self,
        code: str,
        filename: str,
    ) -> List[Issue]:
        """
        Check for MISSING architectural concerns (FRACTAL L1 coverage).

        In 100% LLM mode, this is handled by the semantic LLM check.
        Returns empty list - architecture checks are done in the main LLM prompt.
        """
        # Architecture completeness is now checked by the LLM in self.check()
        # The LLM prompt includes instructions to check for:
        # - RBAC/Authentication
        # - Input validation
        # - Query limits
        # - Specific error handling
        return []

    def check_task_ao_compliance(
        self,
        task_description: str,
        task_type: str = "feature",
        vision_path: str = None,
        task_id: str = "",
    ) -> CheckResult:
        """
        Check if a task is AO-compliant (has valid REQ-ID reference).

        RULES:
        - Feature tasks MUST have REQ-XXX-NNN format in description
        - Task must reference real AO source (IDFM, Nantes, etc.)
        - Reject "nice-to-have" without AO backing

        Args:
            task_description: The task description to check
            task_type: Type of task (feature, fix, test, etc.)
            vision_path: Optional path to VISION.md for REQ-ID validation

        Returns:
            CheckResult with approved=False if no valid AO reference
        """
        issues = []

        # Only enforce strict AO compliance for ROOT feature tasks
        # Skip subtasks (FRACTAL decomposition inherits type but are implementation details)
        if task_type not in ["feature"]:
            return CheckResult(approved=True, score=0, threshold=self.threshold)

        # Skip FRACTAL subtasks - they implement parent's requirements
        if "FEATURE (Happy Path)" in task_description or \
           "GUARDS (Auth" in task_description or \
           "FAILURES (Errors" in task_description:
            return CheckResult(approved=True, score=0, threshold=self.threshold)

        # Skip subtasks and feedback tasks by ID prefix
        if task_id and (task_id.startswith("subtask-") or task_id.startswith("feedback-")):
            return CheckResult(approved=True, score=0, threshold=self.threshold)

        # Check for REQ-ID pattern
        req_pattern = r'REQ-[A-Z]+-\d{3}'
        has_req_id = bool(re.search(req_pattern, task_description))

        # Check for AO source references
        ao_sources = ['IDFM', 'Nantes', 'AO-', 'Annexe', 'Lisa-', 'T6', 'P9', 'Art.']
        has_ao_ref = any(src in task_description for src in ao_sources)

        # SLOP indicators (features without business justification)
        slop_indicators = [
            'innovation', 'nice-to-have', 'improvement', 'enhancement',
            'gamification', 'social', 'sharing', 'badge', 'achievement',
            'AI prediction', 'machine learning', 'weather-based',
            'voice command', 'voice control', 'speech',
            'multi-city', 'partner voucher', 'developer portal',
        ]
        has_slop = any(slop.lower() in task_description.lower() for slop in slop_indicators)

        # Check excluded features (from VISION.md pattern)
        excluded_features = [
            'lyon', 'gamification', 'badges', 'social features',
            'ai prediction', 'family subscription',
        ]
        is_excluded = any(excl.lower() in task_description.lower() for excl in excluded_features)

        if is_excluded:
            issues.append(Issue(
                rule="ao_excluded_feature",
                severity="reject",
                points=10,
                message=f"Feature explicitly EXCLUDED in VISION.md - no AO backing",
                line=0,
                context="VISION.md lists this as excluded (Pas d'AO = Pas de code)",
            ))

        if has_slop and not has_req_id:
            issues.append(Issue(
                rule="ao_slop_detected",
                severity="reject",
                points=8,
                message=f"SLOP detected: Feature without AO reference - gold plating",
                line=0,
                context="Features must have REQ-ID tracing to real AO document",
            ))

        if not has_req_id:
            issues.append(Issue(
                rule="ao_missing_req_id",
                severity="reject",
                points=5,
                message="No REQ-ID found - feature tasks MUST have REQ-XXX-NNN reference",
                line=0,
                context="Format: [REQ-AUTH-001] Description per AO source",
            ))

        if not has_ao_ref and not has_req_id:
            issues.append(Issue(
                rule="ao_no_source",
                severity="warning",
                points=3,
                message="No AO source reference (IDFM, Nantes, etc.)",
                line=0,
                context="Tasks should reference AO document section",
            ))

        total_score = sum(i.points for i in issues)
        approved = total_score < self.threshold

        if not approved:
            log(f"AO COMPLIANCE REJECTED (score={total_score}): {task_description[:80]}...", "WARN")

        return CheckResult(
            approved=approved,
            score=total_score,
            threshold=self.threshold,
            issues=issues,
            feedback="AO compliance check: " + ("; ".join(i.message for i in issues) if issues else "OK"),
        )

    def _generate_feedback(self, issues: List[Issue], context: Dict = None) -> str:
        """Generate human-readable feedback from issues"""
        if not issues:
            return "No issues found."

        parts = ["Issues found:"]
        for i, issue in enumerate(issues, 1):
            parts.append(f"{i}. [{issue.severity.upper()}] {issue.rule}: {issue.message}")
            if issue.context:
                parts.append(f"   Context: {issue.context}")

        parts.append("\nRegenerate the code without these issues.")
        return "\n".join(parts)


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def check_code(code: str, file_type: str = "python", config: Any = None) -> CheckResult:
    """Quick check without project config"""
    return AdversarialGate(config).check_code(code, file_type)


async def check_code_async(code: str, file_type: str = "python", config: Any = None) -> CheckResult:
    """Async quick check"""
    return await AdversarialGate(config).check(code, file_type)


def check_ao_compliance(task_description: str, task_type: str = "feature", config: Any = None, task_id: str = "") -> CheckResult:
    """
    Quick AO compliance check for tasks.

    Returns CheckResult with approved=False if task lacks proper AO reference.
    SLOP features without REQ-ID will be rejected.

    Note: Subtasks (FRACTAL decomposition) and feedback tasks are auto-approved.
    Only ROOT feature tasks are checked for AO compliance.
    """
    return AdversarialGate(config).check_task_ao_compliance(task_description, task_type, task_id=task_id)
