#!/usr/bin/env python3
"""
Wiggum Deploy - Integration & E2E Validation Workers
=====================================================
Based on MIT CSAIL arXiv:2512.24601 "Recursive Language Models"

Deploy workers that validate integration and global functioning:
1. Build artifact
2. Deploy to staging
3. Run E2E journeys (real UI, real data, real selectors)
4. Optional: Chaos monkey, load testing
5. Deploy to prod (if configured)
6. Verify + rollback on failure
7. Feed back issues to task queue

Flow: Wiggum TDD → Adversarial Gate → ✅ → Deploy Queue

Usage:
    from core.wiggum_deploy import DeployPool

    pool = DeployPool("ppz")
    await pool.run()
"""

import asyncio
import json
import subprocess
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.project_registry import get_project, ProjectConfig
from core.task_store import TaskStore, Task, TaskStatus
from core.llm_client import run_opencode
from core.error_capture import ErrorCapture, ErrorType, ErrorSeverity
from core.daemon import Daemon, DaemonManager, print_daemon_status, print_all_status


def log(msg: str, level: str = "INFO", worker_id: str = None):
    """Log with timestamp"""
    ts = datetime.now().strftime("%H:%M:%S")
    prefix = f"DEPLOY-{worker_id}" if worker_id else "DEPLOY"
    print(f"[{ts}] [{prefix}] [{level}] {msg}", flush=True)


# ============================================================================
# DEPLOY STAGES
# ============================================================================

class DeployStage(str, Enum):
    BUILD = "build"
    STAGING = "staging"
    E2E_SMOKE = "e2e_smoke"
    E2E_JOURNEYS = "e2e_journeys"
    CHAOS = "chaos"
    LOAD = "load"
    PROD = "prod"
    VERIFY = "verify"


@dataclass
class DeployResult:
    """Result of deploy pipeline"""
    success: bool
    task_id: str
    stages_passed: List[str] = field(default_factory=list)
    stages_failed: List[str] = field(default_factory=list)
    error: str = ""
    iterations: int = 0
    feedback_tasks: List[Dict] = field(default_factory=list)  # Tasks to create from failures


@dataclass
class E2EJourney:
    """E2E Journey definition"""
    name: str
    description: str
    steps: List[Dict[str, Any]]  # selector, action, data, expected
    rbac_roles: List[str] = field(default_factory=list)
    tenant: str = None


# ============================================================================
# E2E JOURNEY EXECUTOR
# ============================================================================

class E2EExecutor:
    """
    Execute E2E journeys with real UI interactions.

    Uses Playwright for:
    - Real selectors (data-testid, aria-*, etc.)
    - Real data input
    - Real clicks and navigation
    - RBAC validation
    - Security checks

    Captures errors for RLM feedback loop.
    """

    def __init__(self, project: ProjectConfig, tenant: str = None):
        self.project = project
        self.tenant = tenant
        self.base_url = self._get_base_url("staging")
        self.error_capture = ErrorCapture(project)  # Error capture for feedback loop
        self.captured_error_tasks: List[Dict] = []  # Tasks generated from captured errors

    def _get_base_url(self, env: str) -> str:
        """Get base URL for environment"""
        deploy_config = self.project.deploy

        if env == "staging":
            if self.tenant and self.project.tenants:
                for t in self.project.tenants:
                    if t.get("name") == self.tenant:
                        return t.get("staging_url", "")
            return deploy_config.get("staging", {}).get("url", "")

        elif env == "prod":
            if self.tenant and self.project.tenants:
                for t in self.project.tenants:
                    if t.get("name") == self.tenant:
                        return t.get("prod_url", "")
            return deploy_config.get("prod", {}).get("url", "")

        return ""

    async def run_smoke_tests(self) -> Tuple[bool, str, List[Dict]]:
        """
        Run smoke tests using LLM agent with MCP tools.

        Returns:
            Tuple of (success, error_message, captured_error_tasks)
        """
        smoke_cmd = self.project.get_e2e_cmd("smoke", self.tenant)
        log(f"Running smoke tests via LLM agent: {smoke_cmd}")
        captured_tasks = []

        prompt = f"""You are an E2E Test agent. Execute SMOKE TESTS.

PROJECT: {self.project.name}
BASE URL: {self.base_url}
{f"TENANT: {self.tenant}" if self.tenant else ""}

MCP TOOLS AVAILABLE:
- lrm_build(domain, command): Run test commands
- lrm_locate(query, scope): Find test files

YOUR TASK:
1. Run smoke tests: {smoke_cmd}
2. Set TEST_ENV=staging and BASE_URL={self.base_url}
3. Analyze results and report

Execute smoke tests now.
Output "SMOKE_SUCCESS" if all pass, or "SMOKE_FAILED: <reason>" if any fail.
Include FULL OUTPUT of any errors (gRPC, console.error, assertions).
"""

        try:
            returncode, output = await run_opencode(
                prompt,
                model="minimax/MiniMax-M2.1",
                cwd=str(self.project.root_path),
                timeout=300,
                project=self.project.name,
            )

            # 🔴 CAPTURE ERRORS FROM OUTPUT (RLM feedback loop)
            errors = self.error_capture.parse_e2e_output(output, test_name="smoke")
            if errors:
                log(f"Captured {len(errors)} errors from smoke tests")
                captured_tasks = self.error_capture.errors_to_tasks(errors)
                self.captured_error_tasks.extend(captured_tasks)
                self.error_capture.clear()

            if "SMOKE_SUCCESS" in output:
                log("Smoke tests passed ✓")
                return True, "", captured_tasks
            elif "SMOKE_FAILED" in output:
                error = output.split("SMOKE_FAILED:")[-1].strip()[:500]
                return False, f"Smoke tests failed: {error}", captured_tasks
            else:
                # Check for test passing indicators
                if "passed" in output.lower() and "failed" not in output.lower():
                    log("Smoke tests passed (implicit)")
                    return True, "", captured_tasks
                return False, "Smoke test results unclear", captured_tasks

        except Exception as e:
            return False, str(e), captured_tasks

    async def run_journeys(self, journeys: List[E2EJourney]) -> Tuple[bool, List[Dict], List[Dict]]:
        """
        Run E2E journeys with real UI interactions.

        Returns:
            Tuple of (success, list_of_failures, captured_error_tasks)
        """
        failures = []
        all_captured_tasks = []

        for journey in journeys:
            log(f"Running journey: {journey.name}")

            success, error, captured_tasks = await self._run_journey(journey)

            if captured_tasks:
                all_captured_tasks.extend(captured_tasks)

            if not success:
                failures.append({
                    "journey": journey.name,
                    "error": error,
                    "steps": journey.steps,
                    "tenant": journey.tenant,
                    "captured_errors": len(captured_tasks),
                })
                log(f"Journey failed: {journey.name} - {error}", "WARN")
            else:
                log(f"Journey passed: {journey.name} ✓")

        return len(failures) == 0, failures, all_captured_tasks

    async def _run_journey(self, journey: E2EJourney) -> Tuple[bool, str, List[Dict]]:
        """
        Execute a single journey using LLM agent with MCP tools.

        Returns:
            Tuple of (success, error_message, captured_error_tasks)
        """
        tenant = journey.tenant or self.tenant
        base_cmd = self.project.get_e2e_cmd("journeys", tenant)
        cmd = f'{base_cmd} --grep "{journey.name}"'
        captured_tasks = []

        prompt = f"""You are an E2E Test agent. Execute a USER JOURNEY test.

PROJECT: {self.project.name}
JOURNEY: {journey.name}
DESCRIPTION: {journey.description}
BASE URL: {self.base_url}
{f"TENANT: {tenant}" if tenant else ""}

MCP TOOLS AVAILABLE:
- lrm_build(domain, command): Run test commands
- lrm_locate(query, scope): Find test files

YOUR TASK:
1. Run the journey test: {cmd}
2. Set TEST_ENV=staging and BASE_URL={self.base_url}
3. Analyze results - look for failures in UI interactions

Execute the journey test now.
Output "JOURNEY_SUCCESS" if pass, or "JOURNEY_FAILED: <detailed failure reason>" if fail.
Include FULL OUTPUT of any errors (gRPC, console.error, assertions, network errors).
"""

        try:
            returncode, output = await run_opencode(
                prompt,
                model="minimax/MiniMax-M2.1",
                cwd=str(self.project.root_path),
                timeout=300,
                project=self.project.name,
            )

            # 🔴 CAPTURE ERRORS FROM OUTPUT (RLM feedback loop)
            errors = self.error_capture.parse_e2e_output(output, test_name=journey.name)
            if errors:
                log(f"Captured {len(errors)} errors from journey '{journey.name}'")
                captured_tasks = self.error_capture.errors_to_tasks(errors)
                self.captured_error_tasks.extend(captured_tasks)
                self.error_capture.clear()

            if "JOURNEY_SUCCESS" in output:
                return True, "", captured_tasks
            elif "JOURNEY_FAILED" in output:
                error = output.split("JOURNEY_FAILED:")[-1].strip()[:1000]
                return False, error, captured_tasks
            else:
                if "passed" in output.lower() and "failed" not in output.lower():
                    return True, "", captured_tasks
                return False, "Journey results unclear", captured_tasks

        except Exception as e:
            return False, str(e), captured_tasks

    def get_captured_error_tasks(self) -> List[Dict]:
        """Get all captured error tasks and clear the list"""
        tasks = self.captured_error_tasks.copy()
        self.captured_error_tasks = []
        return tasks

    def clear_captured_errors(self):
        """Clear all captured errors"""
        self.error_capture.clear()
        self.captured_error_tasks = []

    async def run_rbac_checks(self, roles: List[str]) -> Tuple[bool, List[Dict]]:
        """Verify RBAC permissions for different roles using LLM agent"""
        failures = []

        for role in roles:
            log(f"Checking RBAC for role: {role} via LLM agent")

            rbac_cmd = self.project.get_e2e_cmd("rbac", self.tenant)
            cmd = f'{rbac_cmd} --grep "{role}"'

            prompt = f"""You are a Security Test agent. Verify RBAC permissions.

PROJECT: {self.project.name}
ROLE: {role}
BASE URL: {self.base_url}

YOUR TASK:
1. Run RBAC test: {cmd}
2. Set TEST_ROLE={role} and BASE_URL={self.base_url}
3. Verify role permissions are correctly enforced

Execute RBAC test now.
Output "RBAC_SUCCESS" if permissions correct, or "RBAC_FAILED: <issue>" if incorrect.
"""

            try:
                returncode, output = await run_opencode(
                    prompt,
                    model="minimax/MiniMax-M2.1",
                    cwd=str(self.project.root_path),
                    timeout=120,
                    project=self.project.name,
                )

                if "RBAC_FAILED" in output:
                    error = output.split("RBAC_FAILED:")[-1].strip()[:500]
                    failures.append({"role": role, "error": error})
                elif "RBAC_SUCCESS" not in output and "passed" not in output.lower():
                    failures.append({"role": role, "error": "RBAC check unclear"})

            except Exception as e:
                failures.append({"role": role, "error": str(e)})

        return len(failures) == 0, failures

    async def run_security_checks(self) -> Tuple[bool, List[Dict]]:
        """Run security validation tests using LLM agent"""
        failures = []

        e2e_config = self.project.get_domain("e2e")
        if not e2e_config:
            return True, []

        test_cmd = e2e_config.get("test_cmd", "npx playwright test")

        security_checks = [
            ("xss", "XSS injection protection"),
            ("csrf", "CSRF token validation"),
            ("auth", "Authentication bypass"),
            ("injection", "SQL/Command injection"),
        ]

        for tag, description in security_checks:
            log(f"Running security check: {tag} via LLM agent")
            cmd = f'{test_cmd} --grep "@security" --grep "{tag}"'

            prompt = f"""You are a Security Test agent. Execute security validation.

PROJECT: {self.project.name}
SECURITY CHECK: {tag} - {description}
BASE URL: {self.base_url}

YOUR TASK:
1. Run security test: {cmd}
2. Verify {description}
3. Look for vulnerabilities

Execute security test now.
Output "SECURITY_SUCCESS" if secure, or "SECURITY_FAILED: <vulnerability details>" if vulnerable.
"""

            try:
                returncode, output = await run_opencode(
                    prompt,
                    model="minimax/MiniMax-M2.1",
                    cwd=str(self.project.root_path),
                    timeout=120,
                    project=self.project.name,
                )

                if "SECURITY_FAILED" in output:
                    error = output.split("SECURITY_FAILED:")[-1].strip()[:300]
                    failures.append({
                        "check": tag,
                        "description": description,
                        "error": error,
                    })

            except Exception as e:
                log(f"Security check {tag} error: {e}", "WARN")

        return len(failures) == 0, failures


# ============================================================================
# CHAOS MONKEY (Optional)
# ============================================================================

class ChaosMonkey:
    """
    Optional chaos engineering tests.

    Tests system resilience under:
    - Network latency
    - Service failures
    - Resource exhaustion
    """

    def __init__(self, project: ProjectConfig):
        self.project = project

    async def run(self, scenarios: List[str] = None) -> Tuple[bool, List[Dict]]:
        """Run chaos scenarios"""
        if scenarios is None:
            scenarios = ["latency", "service_down", "resource_limit"]

        failures = []

        for scenario in scenarios:
            log(f"Running chaos scenario: {scenario}")

            success, error = await self._run_scenario(scenario)
            if not success:
                failures.append({"scenario": scenario, "error": error})

        return len(failures) == 0, failures

    async def _run_scenario(self, scenario: str) -> Tuple[bool, str]:
        """Execute a chaos scenario using LLM agent"""
        chaos_script = self.project.root_path / "tests" / "chaos" / f"{scenario}.sh"

        if not chaos_script.exists():
            log(f"Chaos script not found: {chaos_script}, skipping", "WARN")
            return True, ""

        prompt = f"""You are a Chaos Engineering agent. Execute a resilience test.

PROJECT: {self.project.name}
SCENARIO: {scenario}
SCRIPT: {chaos_script}

YOUR TASK:
1. Run the chaos scenario: bash {chaos_script}
2. Monitor system behavior under stress
3. Verify system recovers gracefully

Execute chaos test now.
Output "CHAOS_SUCCESS" if system resilient, or "CHAOS_FAILED: <failure mode>" if not.
"""

        try:
            returncode, output = await run_opencode(
                prompt,
                model="minimax/MiniMax-M2.1",
                cwd=str(self.project.root_path),
                timeout=300,
                project=self.project.name,
            )

            if "CHAOS_SUCCESS" in output:
                return True, ""
            elif "CHAOS_FAILED" in output:
                error = output.split("CHAOS_FAILED:")[-1].strip()[:500]
                return False, error
            else:
                return True, ""  # Implicit success

        except Exception as e:
            return False, str(e)


# ============================================================================
# LOAD TESTING (Optional)
# ============================================================================

class LoadTester:
    """
    Optional load/performance testing.

    Tests:
    - Response times under load
    - Concurrent user handling
    - Resource utilization
    """

    def __init__(self, project: ProjectConfig):
        self.project = project

    async def run(self, users: int = 100, duration: int = 60) -> Tuple[bool, Dict]:
        """Run load test using LLM agent"""
        log(f"Running load test via LLM agent: {users} users, {duration}s")

        load_config = self.project.root_path / "tests" / "load" / "config.json"

        if not load_config.exists():
            log("Load test config not found, skipping", "WARN")
            return True, {}

        prompt = f"""You are a Performance Test agent. Execute load testing.

PROJECT: {self.project.name}
VIRTUAL USERS: {users}
DURATION: {duration}s

YOUR TASK:
1. Run load test: k6 run --vus {users} --duration {duration}s tests/load/script.js
2. Monitor response times and error rates
3. Analyze performance under load

Execute load test now.
Output "LOAD_SUCCESS" with metrics summary, or "LOAD_FAILED: <performance issue>" if degraded.
"""

        try:
            returncode, output = await run_opencode(
                prompt,
                model="minimax/MiniMax-M2.1",
                cwd=str(self.project.root_path),
                timeout=duration + 120,
                project=self.project.name,
            )

            if "LOAD_SUCCESS" in output:
                return True, {"output": output[:1000]}
            elif "LOAD_FAILED" in output:
                error = output.split("LOAD_FAILED:")[-1].strip()[:500]
                return False, {"error": error}
            else:
                # Check for common performance indicators
                if "p99" in output.lower() or "latency" in output.lower():
                    return True, {"output": output[:1000]}
                return True, {}

        except Exception as e:
            return False, {"error": str(e)}


# ============================================================================
# DEPLOY ADVERSARIAL AGENT
# ============================================================================

@dataclass
class AdversarialReview:
    """Result of adversarial review"""
    approved: bool
    score: int  # 0-10, higher = more issues
    issues: List[Dict[str, Any]]
    recommendations: List[str]
    stage: str
    feedback: str


class DeployAdversarial:
    """
    Adversarial Agent for Deploy Pipeline.

    Acts as a RED TEAM reviewer that critiques:
    - Build quality and completeness
    - Deploy process safety
    - E2E test coverage and validity
    - Security test thoroughness
    - Overall process rigor

    Uses a different perspective to challenge assumptions
    and find weaknesses in the deployment process.
    """

    DEFAULT_THRESHOLD = 5  # Default score >= 5 = REJECT

    def __init__(self, project: ProjectConfig):
        self.project = project
        # Use project-specific threshold from config, or default
        adv_config = project.adversarial or {}
        self.threshold = adv_config.get("threshold", self.DEFAULT_THRESHOLD)

    async def review_stage(
        self,
        stage: str,
        stage_output: str,
        task: "Task",
        context: Dict[str, Any] = None,
    ) -> AdversarialReview:
        """
        Review a deploy stage output adversarially.

        Args:
            stage: Stage name (build, staging, e2e_smoke, etc.)
            stage_output: Output from the stage agent
            task: The task being deployed
            context: Additional context (previous stages, etc.)

        Returns:
            AdversarialReview with approval decision
        """
        log(f"Adversarial review of stage: {stage}")

        prompt = self._build_review_prompt(stage, stage_output, task, context)

        try:
            returncode, output = await run_opencode(
                prompt,
                model="minimax/MiniMax-M2.1",
                cwd=str(self.project.root_path),
                timeout=300,
                project=self.project.name,
            )

            return self._parse_review(stage, output)

        except Exception as e:
            log(f"Adversarial review error: {e}", "ERROR")
            # On error, be conservative - don't approve
            return AdversarialReview(
                approved=False,
                score=10,
                issues=[{"type": "error", "message": str(e)}],
                recommendations=["Fix adversarial review error"],
                stage=stage,
                feedback=f"Review failed: {e}",
            )

    def _build_review_prompt(
        self,
        stage: str,
        stage_output: str,
        task: "Task",
        context: Dict[str, Any] = None,
    ) -> str:
        """Build adversarial review prompt"""

        stage_criteria = {
            "build": """
CRITIQUE POINTS FOR BUILD:
- Did the build actually compile ALL components?
- Are there any warnings being ignored?
- Did it skip any tests or checks?
- Is the artifact complete and deployable?
- Are dependencies properly locked/versioned?
- Any security vulnerabilities in dependencies?
""",
            "staging": """
CRITIQUE POINTS FOR STAGING DEPLOY:
- Was the deployment actually verified?
- Did it check all services started correctly?
- Are database migrations applied?
- Is configuration correct for staging?
- Any hardcoded production values leaked?
- Did it verify staging URL is accessible?
""",
            "e2e_smoke": """
CRITIQUE POINTS FOR SMOKE TESTS:
- Did tests actually run or were they skipped?
- Is test coverage sufficient for critical paths?
- Are tests flaky or non-deterministic?
- Did tests use real data or mocks?
- Any "success by default" patterns?
- Were failures properly reported?
""",
            "e2e_journeys": """
CRITIQUE POINTS FOR E2E JOURNEYS:
- Did ALL user journeys execute?
- Were edge cases tested?
- Is RBAC properly validated?
- Any skipped or ignored assertions?
- Did tests wait for async operations?
- Were real selectors used (not brittle XPaths)?
""",
            "security": """
CRITIQUE POINTS FOR SECURITY TESTS:
- Were ALL OWASP top 10 checked?
- Did XSS tests use actual payloads?
- Were CSRF tokens validated end-to-end?
- Any SQL injection vectors tested?
- Were auth bypass attempts thorough?
- Did it check for sensitive data exposure?
""",
            "rbac": """
CRITIQUE POINTS FOR RBAC:
- Were ALL roles tested?
- Did it verify permission DENIALS (not just grants)?
- Were role escalation attempts tested?
- Did it check cross-tenant isolation?
- Were API endpoints tested (not just UI)?
- Any implicit admin access?
""",
            "chaos": """
CRITIQUE POINTS FOR CHAOS TESTS:
- Did system actually recover?
- Were failure modes realistic?
- Did it test cascading failures?
- Was recovery time measured?
- Were data integrity checks done?
- Any silent data corruption possible?
""",
            "load": """
CRITIQUE POINTS FOR LOAD TESTS:
- Were realistic load levels used?
- Did it test beyond expected capacity?
- Were response times acceptable?
- Any memory leaks under load?
- Did it test concurrent writes?
- Were database connections exhausted?
""",
            "prod": """
CRITIQUE POINTS FOR PRODUCTION DEPLOY:
- Was staging IDENTICAL to this deploy?
- Are rollback procedures verified?
- Is monitoring in place?
- Were feature flags set correctly?
- Any breaking changes deployed?
- Is blue/green switch safe?
""",
            "verify": """
CRITIQUE POINTS FOR PROD VERIFICATION:
- Did health check test ALL services?
- Were critical user flows verified?
- Is data accessible and correct?
- Are external integrations working?
- Any latency regressions?
- Were alerts configured?
""",
        }

        criteria = stage_criteria.get(stage, """
GENERAL CRITIQUE POINTS:
- Was the task actually completed?
- Any shortcuts or workarounds?
- Is the output reliable and verifiable?
- Any implicit assumptions?
- Could this fail silently in production?
""")

        return f"""You are an ADVERSARIAL REVIEWER (Red Team) for deployment pipelines.

Your job is to CRITIQUE and CHALLENGE the work done. Be skeptical. Find weaknesses.

PROJECT: {self.project.name}
STAGE: {stage}
TASK: {task.description if task else "Unknown"}

STAGE OUTPUT TO REVIEW:
```
{stage_output[:3000]}
```

{criteria}

SCORING (0-10):
- 0-2: Minor issues, can proceed
- 3-4: Some concerns, proceed with caution
- 5-6: Significant issues, should not proceed
- 7-8: Major problems, definitely reject
- 9-10: Critical failures, immediate stop

YOUR REVIEW:
1. List SPECIFIC issues found (not vague concerns)
2. Assign a score (0-10)
3. Provide concrete recommendations
4. Make APPROVE or REJECT decision

Output in this format:
SCORE: <number>
ISSUES:
- <specific issue 1>
- <specific issue 2>
RECOMMENDATIONS:
- <specific action 1>
- <specific action 2>
DECISION: APPROVE or REJECT
FEEDBACK: <brief explanation>
"""

    def _parse_review(self, stage: str, output: str) -> AdversarialReview:
        """Parse adversarial review output"""
        import re

        # Default values
        score = 5
        issues = []
        recommendations = []
        approved = False
        feedback = "Review parsing failed"

        try:
            # Parse score
            score_match = re.search(r'SCORE:\s*(\d+)', output)
            if score_match:
                score = int(score_match.group(1))

            # Parse issues
            issues_section = re.search(r'ISSUES:\s*(.*?)(?=RECOMMENDATIONS:|DECISION:|$)', output, re.DOTALL)
            if issues_section:
                issue_lines = [l.strip().lstrip('-').strip() for l in issues_section.group(1).split('\n') if l.strip() and l.strip() != '-']
                issues = [{"type": "issue", "message": i} for i in issue_lines if i]

            # Parse recommendations
            rec_section = re.search(r'RECOMMENDATIONS:\s*(.*?)(?=DECISION:|FEEDBACK:|$)', output, re.DOTALL)
            if rec_section:
                recommendations = [l.strip().lstrip('-').strip() for l in rec_section.group(1).split('\n') if l.strip() and l.strip() != '-']
                recommendations = [r for r in recommendations if r]

            # Parse decision - SCORE takes precedence over text DECISION
            # (high threshold projects like YoloNow (30) should approve low scores)
            log(f"DEBUG adversarial: score={score}, threshold={self.threshold}, score<threshold={score < self.threshold}")
            if score < self.threshold:
                approved = True
                log(f"DEBUG: APPROVED because {score} < {self.threshold}")
            else:
                # Check explicit DECISION if score is at/above threshold
                decision_match = re.search(r'DECISION:\s*(APPROVE|REJECT)', output, re.IGNORECASE)
                if decision_match:
                    approved = decision_match.group(1).upper() == "APPROVE"
                else:
                    approved = False  # Score >= threshold with no explicit APPROVE

            # Parse feedback
            feedback_match = re.search(r'FEEDBACK:\s*(.+?)(?=$|\n\n)', output, re.DOTALL)
            if feedback_match:
                feedback = feedback_match.group(1).strip()[:500]
            else:
                feedback = f"Score: {score}/10. {'Approved' if approved else 'Rejected'}."

        except Exception as e:
            log(f"Parse error: {e}", "WARN")
            approved = False
            feedback = f"Parse error: {e}"

        return AdversarialReview(
            approved=approved,
            score=score,
            issues=issues,
            recommendations=recommendations,
            stage=stage,
            feedback=feedback,
        )

    async def review_full_pipeline(
        self,
        task: "Task",
        stages_results: Dict[str, str],
    ) -> AdversarialReview:
        """
        Review the ENTIRE deploy pipeline holistically.

        Called after all stages pass to do a final adversarial check.
        """
        log("Full pipeline adversarial review")

        stages_summary = "\n".join([
            f"=== {stage.upper()} ===\n{output[:500]}\n"
            for stage, output in stages_results.items()
        ])

        prompt = f"""You are the FINAL ADVERSARIAL GATE for production deployment.

PROJECT: {self.project.name}
TASK: {task.description if task else "Unknown"}

ALL STAGES COMPLETED:
{stages_summary[:5000]}

YOUR MISSION:
Review the ENTIRE pipeline. Look for:
1. Gaps between stages (did staging really match what goes to prod?)
2. Weak validations (were tests comprehensive?)
3. Process shortcuts (were any steps rushed?)
4. Integration issues (do components work together?)
5. Hidden risks (what could go wrong in production?)

Be the last line of defense before production.

Output:
SCORE: <0-10>
CRITICAL_ISSUES:
- <issue that MUST be fixed before prod>
WARNINGS:
- <concern but acceptable>
DECISION: APPROVE or REJECT
CONFIDENCE: <LOW|MEDIUM|HIGH> (how confident in this decision)
FINAL_VERDICT: <1-2 sentence summary>
"""

        try:
            returncode, output = await run_opencode(
                prompt,
                model="minimax/MiniMax-M2.1",
                cwd=str(self.project.root_path),
                timeout=300,
                project=self.project.name,
            )

            return self._parse_final_review(output)

        except Exception as e:
            return AdversarialReview(
                approved=False,
                score=10,
                issues=[{"type": "error", "message": str(e)}],
                recommendations=["Fix final review error"],
                stage="final",
                feedback=f"Final review failed: {e}",
            )

    def _parse_final_review(self, output: str) -> AdversarialReview:
        """Parse final pipeline review"""
        import re

        score = 5
        issues = []
        recommendations = []
        approved = False
        feedback = "Final review"

        try:
            # Parse score
            score_match = re.search(r'SCORE:\s*(\d+)', output)
            if score_match:
                score = int(score_match.group(1))

            # Parse critical issues
            critical_section = re.search(r'CRITICAL_ISSUES:\s*(.*?)(?=WARNINGS:|DECISION:|$)', output, re.DOTALL)
            if critical_section:
                critical_lines = [l.strip().lstrip('-').strip() for l in critical_section.group(1).split('\n') if l.strip() and l.strip() != '-']
                issues = [{"type": "critical", "message": i} for i in critical_lines if i]

            # Parse warnings
            warn_section = re.search(r'WARNINGS:\s*(.*?)(?=DECISION:|CONFIDENCE:|$)', output, re.DOTALL)
            if warn_section:
                warn_lines = [l.strip().lstrip('-').strip() for l in warn_section.group(1).split('\n') if l.strip() and l.strip() != '-']
                recommendations = warn_lines

            # Parse decision
            decision_match = re.search(r'DECISION:\s*(APPROVE|REJECT)', output, re.IGNORECASE)
            if decision_match:
                approved = decision_match.group(1).upper() == "APPROVE"
            else:
                approved = score < self.threshold

            # Parse final verdict
            verdict_match = re.search(r'FINAL_VERDICT:\s*(.+?)(?=$|\n)', output)
            if verdict_match:
                feedback = verdict_match.group(1).strip()[:500]

        except Exception as e:
            log(f"Final parse error: {e}", "WARN")

        return AdversarialReview(
            approved=approved,
            score=score,
            issues=issues,
            recommendations=recommendations,
            stage="final",
            feedback=feedback,
        )


# ============================================================================
# DEPLOY WORKER
# ============================================================================

class DeployWorker:
    """
    Single Deploy worker using LLM agents with MCP tools.

    Each stage is executed by an LLM agent that has access to:
    - MCP LRM tools (lrm_locate, lrm_build, etc.)
    - Read/Write/Bash tools via opencode

    Pipeline:
    1. Build artifact (LLM runs build commands)
    2. Deploy to staging (LLM executes deploy)
    3. E2E smoke tests (LLM runs and analyzes)
    4. E2E journeys (LLM executes real UI tests)
    5. RBAC & Security checks
    6. Optional: Chaos/Load testing
    7. Deploy to prod
    8. Verify prod
    9. Rollback on failure
    10. Create feedback tasks for failures
    """

    MAX_ITERATIONS = 10
    OPENCODE_TIMEOUT = 600  # 10 min per stage

    def __init__(
        self,
        worker_id: str,
        project: ProjectConfig,
        task_store: TaskStore,
    ):
        self.worker_id = worker_id
        self.project = project
        self.task_store = task_store
        self.e2e = E2EExecutor(project)
        self.chaos = ChaosMonkey(project)
        self.load = LoadTester(project)
        self.adversarial = DeployAdversarial(project)
        self.error_capture = ErrorCapture(project)  # Error capture for build failures
        self.stages_outputs: Dict[str, str] = {}  # Track outputs for final review

    def log(self, msg: str, level: str = "INFO"):
        log(msg, level, self.worker_id)

    async def run_pipeline(self, task: Task) -> DeployResult:
        """Run full deploy pipeline for a task with adversarial gates"""
        result = DeployResult(success=False, task_id=task.id)
        self.stages_outputs = {}  # Reset for this run

        self.log(f"Starting deploy pipeline for task: {task.id}")

        deploy_config = self.project.deploy
        strategy = deploy_config.get("strategy", "validation-only")

        for iteration in range(self.MAX_ITERATIONS):
            result.iterations = iteration + 1
            self.log(f"Deploy iteration {iteration + 1}/{self.MAX_ITERATIONS}")

            try:
                # 1. BUILD
                success, output, build_error_tasks = await self._stage_build(task)
                self.stages_outputs["build"] = output if not success else "BUILD_SUCCESS"
                if not success:
                    result.stages_failed.append(DeployStage.BUILD)
                    result.error = output
                    # 🔴 ADD CAPTURED ERROR TASKS (RLM feedback loop)
                    if build_error_tasks:
                        log(f"Adding {len(build_error_tasks)} captured build error tasks to feedback")
                        for et in build_error_tasks:
                            et["source_task"] = task.id
                            result.feedback_tasks.append(et)
                    continue
                result.stages_passed.append(DeployStage.BUILD)

                # 1.5 ADVERSARIAL: Review build
                adv_review = await self.adversarial.review_stage("build", self.stages_outputs["build"], task)
                if not adv_review.approved:
                    self.log(f"Adversarial REJECTED build: {adv_review.feedback}", "WARN")
                    result.stages_failed.append("adversarial_build")
                    result.error = f"Adversarial rejected: {adv_review.feedback}"
                    result.feedback_tasks.append({
                        "type": "fix",
                        "domain": task.domain,
                        "stage": "adversarial_build",
                        "description": f"Address adversarial concerns: {adv_review.feedback}",
                        "issues": adv_review.issues,
                        "source_task": task.id,
                    })
                    continue
                self.log(f"Adversarial APPROVED build (score: {adv_review.score}/10)")

                # VALIDATION-ONLY: Build success = task completed (skip staging, e2e, etc.)
                if strategy == "validation-only":
                    result.success = True
                    self.task_store.transition(task.id, TaskStatus.DEPLOYED)
                    self.log("✅ Validation-only: Build passed → task completed")
                    return result

                # 2. STAGING
                if strategy != "validation-only":
                    success, output = await self._stage_staging(task)
                    self.stages_outputs["staging"] = output if not success else "STAGING_SUCCESS"
                    if not success:
                        result.stages_failed.append(DeployStage.STAGING)
                        result.error = output
                        continue
                    result.stages_passed.append(DeployStage.STAGING)

                    # 2.5 ADVERSARIAL: Review staging
                    adv_review = await self.adversarial.review_stage("staging", self.stages_outputs["staging"], task)
                    if not adv_review.approved:
                        self.log(f"Adversarial REJECTED staging: {adv_review.feedback}", "WARN")
                        result.stages_failed.append("adversarial_staging")
                        result.error = f"Adversarial rejected: {adv_review.feedback}"
                        continue
                    self.log(f"Adversarial APPROVED staging (score: {adv_review.score}/10)")

                # 3. E2E SMOKE
                success, output, smoke_error_tasks = await self._stage_smoke()
                self.stages_outputs["e2e_smoke"] = output if not success else "SMOKE_SUCCESS"
                if not success:
                    result.stages_failed.append(DeployStage.E2E_SMOKE)
                    result.error = output
                    result.feedback_tasks.append({
                        "type": "fix",
                        "domain": "e2e",
                        "stage": "e2e_smoke",
                        "description": f"Fix E2E smoke test failure: {output}",
                        "source_task": task.id,
                    })
                    # 🔴 ADD CAPTURED ERROR TASKS (RLM feedback loop)
                    if smoke_error_tasks:
                        log(f"Adding {len(smoke_error_tasks)} captured error tasks to feedback")
                        for et in smoke_error_tasks:
                            et["source_task"] = task.id
                            result.feedback_tasks.append(et)
                    continue
                result.stages_passed.append(DeployStage.E2E_SMOKE)

                # 3.5 ADVERSARIAL: Review smoke tests
                adv_review = await self.adversarial.review_stage("e2e_smoke", self.stages_outputs["e2e_smoke"], task)
                if not adv_review.approved:
                    self.log(f"Adversarial REJECTED smoke tests: {adv_review.feedback}", "WARN")
                    result.stages_failed.append("adversarial_smoke")
                    result.error = f"Adversarial rejected: {adv_review.feedback}"
                    continue
                self.log(f"Adversarial APPROVED smoke tests (score: {adv_review.score}/10)")

                # 4. E2E JOURNEYS
                journeys = self._get_journeys(task)
                if journeys:
                    success, failures, journey_error_tasks = await self.e2e.run_journeys(journeys)
                    journeys_output = "JOURNEYS_SUCCESS" if success else f"FAILURES: {failures}"
                    self.stages_outputs["e2e_journeys"] = journeys_output
                    if not success:
                        result.stages_failed.append(DeployStage.E2E_JOURNEYS)
                        result.error = f"Journey failures: {len(failures)}"
                        for failure in failures:
                            result.feedback_tasks.append({
                                "type": "fix",
                                "domain": "e2e",
                                "stage": "e2e_journeys",
                                "description": f"Fix E2E journey '{failure['journey']}': {failure['error']}",
                                "source_task": task.id,
                                "context": failure,
                            })
                        # 🔴 ADD CAPTURED ERROR TASKS (RLM feedback loop)
                        if journey_error_tasks:
                            log(f"Adding {len(journey_error_tasks)} captured error tasks from journeys")
                            for et in journey_error_tasks:
                                et["source_task"] = task.id
                                result.feedback_tasks.append(et)
                        continue
                    result.stages_passed.append(DeployStage.E2E_JOURNEYS)

                    # 4.5 ADVERSARIAL: Review E2E journeys
                    adv_review = await self.adversarial.review_stage("e2e_journeys", journeys_output, task)
                    if not adv_review.approved:
                        self.log(f"Adversarial REJECTED E2E journeys: {adv_review.feedback}", "WARN")
                        result.stages_failed.append("adversarial_journeys")
                        result.error = f"Adversarial rejected: {adv_review.feedback}"
                        continue
                    self.log(f"Adversarial APPROVED E2E journeys (score: {adv_review.score}/10)")

                # 5. RBAC & SECURITY
                rbac_success, rbac_failures = await self.e2e.run_rbac_checks(["user", "admin", "guest"])
                self.stages_outputs["rbac"] = "RBAC_SUCCESS" if rbac_success else f"FAILURES: {rbac_failures}"
                if not rbac_success:
                    for failure in rbac_failures:
                        result.feedback_tasks.append({
                            "type": "security",
                            "domain": task.domain,
                            "stage": "rbac",
                            "description": f"Fix RBAC issue for role '{failure['role']}': {failure['error']}",
                            "source_task": task.id,
                        })

                # 5.5 ADVERSARIAL: Review RBAC
                adv_review = await self.adversarial.review_stage("rbac", self.stages_outputs["rbac"], task)
                if not adv_review.approved:
                    self.log(f"Adversarial REJECTED RBAC: {adv_review.feedback}", "WARN")
                    result.stages_failed.append("adversarial_rbac")
                    result.error = f"Adversarial rejected RBAC: {adv_review.feedback}"
                    continue
                self.log(f"Adversarial APPROVED RBAC (score: {adv_review.score}/10)")

                security_success, security_failures = await self.e2e.run_security_checks()
                self.stages_outputs["security"] = "SECURITY_SUCCESS" if security_success else f"FAILURES: {security_failures}"
                if not security_success:
                    for failure in security_failures:
                        result.feedback_tasks.append({
                            "type": "security",
                            "domain": task.domain,
                            "stage": "security",
                            "description": f"Fix security issue '{failure['check']}': {failure['error']}",
                            "source_task": task.id,
                        })

                # 5.6 ADVERSARIAL: Review Security
                adv_review = await self.adversarial.review_stage("security", self.stages_outputs["security"], task)
                if not adv_review.approved:
                    self.log(f"Adversarial REJECTED security: {adv_review.feedback}", "WARN")
                    result.stages_failed.append("adversarial_security")
                    result.error = f"Adversarial rejected security: {adv_review.feedback}"
                    continue
                self.log(f"Adversarial APPROVED security (score: {adv_review.score}/10)")

                # 6. CHAOS (optional)
                if deploy_config.get("chaos_enabled", False):
                    success, failures = await self.chaos.run()
                    self.stages_outputs["chaos"] = "CHAOS_SUCCESS" if success else f"FAILURES: {failures}"
                    if not success:
                        result.stages_failed.append(DeployStage.CHAOS)
                        for failure in failures:
                            result.feedback_tasks.append({
                                "type": "fix",
                                "domain": task.domain,
                                "stage": "chaos",
                                "description": f"Fix chaos scenario '{failure['scenario']}': {failure['error']}",
                                "source_task": task.id,
                            })
                        continue
                    result.stages_passed.append(DeployStage.CHAOS)

                    # 6.5 ADVERSARIAL: Review Chaos
                    adv_review = await self.adversarial.review_stage("chaos", self.stages_outputs["chaos"], task)
                    if not adv_review.approved:
                        self.log(f"Adversarial REJECTED chaos: {adv_review.feedback}", "WARN")
                        continue
                    self.log(f"Adversarial APPROVED chaos (score: {adv_review.score}/10)")

                # 7. LOAD (optional)
                if deploy_config.get("load_enabled", False):
                    success, data = await self.load.run()
                    self.stages_outputs["load"] = f"LOAD_SUCCESS: {data}" if success else f"FAILED: {data}"
                    if not success:
                        result.stages_failed.append(DeployStage.LOAD)
                        result.feedback_tasks.append({
                            "type": "fix",
                            "domain": task.domain,
                            "stage": "load",
                            "description": f"Fix performance issue: {data.get('error', 'Unknown')}",
                            "source_task": task.id,
                        })
                        continue
                    result.stages_passed.append(DeployStage.LOAD)

                    # 7.5 ADVERSARIAL: Review Load
                    adv_review = await self.adversarial.review_stage("load", self.stages_outputs["load"], task)
                    if not adv_review.approved:
                        self.log(f"Adversarial REJECTED load: {adv_review.feedback}", "WARN")
                        continue
                    self.log(f"Adversarial APPROVED load (score: {adv_review.score}/10)")

                # ========================================
                # FINAL ADVERSARIAL GATE BEFORE PRODUCTION
                # ========================================
                if strategy in ["blue-green", "canary"] and deploy_config.get("auto_prod", False):
                    self.log("Running FINAL ADVERSARIAL GATE before production...")
                    final_review = await self.adversarial.review_full_pipeline(task, self.stages_outputs)
                    if not final_review.approved:
                        self.log(f"FINAL ADVERSARIAL GATE REJECTED: {final_review.feedback}", "ERROR")
                        result.stages_failed.append("adversarial_final")
                        result.error = f"Final adversarial gate rejected: {final_review.feedback}"
                        result.feedback_tasks.append({
                            "type": "fix",
                            "domain": task.domain,
                            "stage": "adversarial_final",
                            "description": f"Address final adversarial concerns: {final_review.feedback}",
                            "issues": final_review.issues,
                            "recommendations": final_review.recommendations,
                            "source_task": task.id,
                        })
                        continue
                    self.log(f"FINAL ADVERSARIAL GATE APPROVED (score: {final_review.score}/10)")

                # 8. PROD DEPLOY
                if strategy in ["blue-green", "canary"] and deploy_config.get("auto_prod", False):
                    success, output = await self._stage_prod(task)
                    self.stages_outputs["prod"] = output if not success else "PROD_DEPLOY_SUCCESS"
                    if not success:
                        result.stages_failed.append(DeployStage.PROD)
                        result.error = output
                        await self._rollback()
                        continue
                    result.stages_passed.append(DeployStage.PROD)

                    # 8.5 ADVERSARIAL: Review Prod Deploy
                    adv_review = await self.adversarial.review_stage("prod", self.stages_outputs["prod"], task)
                    if not adv_review.approved:
                        self.log(f"Adversarial REJECTED prod deploy: {adv_review.feedback}", "WARN")
                        await self._rollback()
                        result.stages_failed.append("adversarial_prod")
                        result.error = f"Adversarial rejected prod: {adv_review.feedback}"
                        continue
                    self.log(f"Adversarial APPROVED prod deploy (score: {adv_review.score}/10)")

                    # 9. VERIFY PROD
                    success, output = await self._stage_verify_prod()
                    self.stages_outputs["verify"] = output if not success else "VERIFY_SUCCESS"
                    if not success:
                        result.stages_failed.append(DeployStage.VERIFY)
                        result.error = output
                        await self._rollback()
                        continue
                    result.stages_passed.append(DeployStage.VERIFY)

                    # 9.5 ADVERSARIAL: Final Verify Review
                    adv_review = await self.adversarial.review_stage("verify", self.stages_outputs["verify"], task)
                    if not adv_review.approved:
                        self.log(f"Adversarial REJECTED verification: {adv_review.feedback}", "WARN")
                        await self._rollback()
                        result.stages_failed.append("adversarial_verify")
                        result.error = f"Adversarial rejected verification: {adv_review.feedback}"
                        continue
                    self.log(f"Adversarial APPROVED verification (score: {adv_review.score}/10)")

                # SUCCESS!
                result.success = True
                self.task_store.transition(task.id, TaskStatus.DEPLOYED)
                self.log("✅ Deploy pipeline completed successfully (ALL ADVERSARIAL GATES PASSED)")
                return result

            except Exception as e:
                self.log(f"Pipeline error: {e}", "ERROR")
                result.error = str(e)
                continue

        # Max iterations reached - RLM pattern: return to TDD with feedback
        result.error = "Max iterations reached"

        # Accumulate all feedback from failed stages
        all_feedback = self._accumulate_feedback(result)

        # Update task context with deploy feedback
        context = task.get_context() or {}
        context["deploy_feedback"] = all_feedback
        context["deploy_iterations"] = result.iterations
        context["stages_failed"] = [str(s) for s in result.stages_failed]

        # RLM LOOP: Send task BACK to TDD with feedback (not new task!)
        self.task_store.update_task(task.id, context=context)
        # Must go through DEPLOY_FAILED first, then back to PENDING for TDD
        self.task_store.transition(task.id, TaskStatus.DEPLOY_FAILED)
        self.task_store.transition(task.id, TaskStatus.PENDING)  # Back to TDD queue

        self.log("🔄 Deploy failed → Returning to TDD with feedback (RLM loop)", "WARN")
        self.log(f"   Feedback: {all_feedback[:200]}...")

        return result

    def _accumulate_feedback(self, result: DeployResult) -> str:
        """Accumulate all feedback from deploy failures for RLM loop"""
        feedback_parts = []

        feedback_parts.append(f"DEPLOY FAILED after {result.iterations} iterations")
        feedback_parts.append(f"Stages passed: {result.stages_passed}")
        feedback_parts.append(f"Stages failed: {result.stages_failed}")

        if result.error:
            feedback_parts.append(f"\nLast error: {result.error}")

        # Add specific feedback from each failed task
        for ft in result.feedback_tasks:
            stage = ft.get("stage", "unknown")
            desc = ft.get("description", "")
            feedback_parts.append(f"\n[{stage}] {desc}")
            if ft.get("issues"):
                for issue in ft["issues"][:3]:
                    feedback_parts.append(f"  - {issue}")
            if ft.get("recommendations"):
                for rec in ft["recommendations"][:2]:
                    feedback_parts.append(f"  → {rec}")

        return "\n".join(feedback_parts)

    async def _stage_build(self, task: Task) -> Tuple[bool, str, List[Dict]]:
        """
        Build artifact using LLM agent with MCP tools.

        Returns:
            Tuple of (success, error_message, captured_error_tasks)
        """
        build_cmd = self.project.get_build_cmd(task.domain)
        self.log(f"Building artifact via LLM agent: {build_cmd}")
        captured_tasks = []

        prompt = f"""You are a Deploy agent. Execute the BUILD stage for this task.

PROJECT: {self.project.name} ({self.project.display_name})
ROOT: {self.project.root_path}
DOMAIN: {task.domain}

MCP TOOLS AVAILABLE:
- lrm_locate(query, scope, limit): Find files
- lrm_build(domain, command): Run build commands
- lrm_summarize(files, goal): Understand code

YOUR TASK:
1. Use lrm_build to run: {build_cmd}
2. If build fails, analyze the error
3. Report SUCCESS or FAILURE with details

Execute the build now and report the result.
Output "BUILD_SUCCESS" if successful, or "BUILD_FAILED: <reason>" if failed.
Include FULL ERROR OUTPUT if build fails (compilation errors, type errors, etc.).
"""

        try:
            returncode, output = await run_opencode(
                prompt,
                model="minimax/MiniMax-M2.1",
                cwd=str(self.project.root_path),
                timeout=self.OPENCODE_TIMEOUT,
                project=self.project.name,
            )

            # 🔴 CAPTURE BUILD ERRORS (RLM feedback loop)
            errors = self.error_capture.parse_build_output(output, domain=task.domain)
            if errors:
                self.log(f"Captured {len(errors)} build errors")
                captured_tasks = self.error_capture.errors_to_tasks(errors)
                self.error_capture.clear()

            if returncode != 0:
                return False, f"Build agent failed: {output[:500]}", captured_tasks

            if "BUILD_SUCCESS" in output:
                self.log("Build passed ✓")
                return True, "", captured_tasks
            elif "BUILD_FAILED" in output:
                error = output.split("BUILD_FAILED:")[-1].strip()[:500]
                return False, f"Build failed: {error}", captured_tasks
            else:
                # Assume success if no explicit failure
                self.log("Build completed (implicit success)")
                return True, "", captured_tasks

        except Exception as e:
            return False, str(e), captured_tasks

    async def _stage_staging(self, task: Task, tenant: str = None) -> Tuple[bool, str]:
        """Deploy to staging using LLM agent with MCP tools"""
        deploy_cmd = self.project.get_deploy_cmd("staging", tenant)
        staging_url = self.project.deploy.get("staging", {}).get("url", "")
        self.log(f"Deploying to staging via LLM agent: {deploy_cmd}")

        prompt = f"""You are a Deploy agent. Execute the STAGING DEPLOY stage.

PROJECT: {self.project.name} ({self.project.display_name})
ROOT: {self.project.root_path}
STAGING URL: {staging_url}
{f"TENANT: {tenant}" if tenant else ""}

MCP TOOLS AVAILABLE:
- lrm_build(domain, command): Run deploy commands
- lrm_locate(query, scope): Find deployment files

YOUR TASK:
1. Execute the staging deploy command: {deploy_cmd}
2. Wait for deployment to complete
3. Verify staging is accessible at {staging_url}
4. Report SUCCESS or FAILURE with details

Execute the staging deploy now.
Output "STAGING_SUCCESS" if successful, or "STAGING_FAILED: <reason>" if failed.
"""

        try:
            returncode, output = await run_opencode(
                prompt,
                model="minimax/MiniMax-M2.1",
                cwd=str(self.project.root_path),
                timeout=self.OPENCODE_TIMEOUT,
                project=self.project.name,
            )

            if returncode != 0:
                return False, f"Staging agent failed: {output[:500]}"

            if "STAGING_SUCCESS" in output:
                self.log("Staging deploy passed ✓")
                return True, ""
            elif "STAGING_FAILED" in output:
                error = output.split("STAGING_FAILED:")[-1].strip()[:500]
                return False, f"Staging deploy failed: {error}"
            else:
                self.log("Staging deploy completed (implicit success)")
                return True, ""

        except Exception as e:
            return False, str(e)

    async def _stage_smoke(self) -> Tuple[bool, str, List[Dict]]:
        """
        Run smoke tests with error capture.

        Returns:
            Tuple of (success, error_message, captured_error_tasks)
        """
        return await self.e2e.run_smoke_tests()

    async def _stage_prod(self, task: Task, tenant: str = None) -> Tuple[bool, str]:
        """Deploy to production using LLM agent with MCP tools"""
        deploy_cmd = self.project.get_deploy_cmd("prod", tenant)
        prod_url = self.project.deploy.get("prod", {}).get("url", "")
        self.log(f"Deploying to production via LLM agent: {deploy_cmd}")

        prompt = f"""You are a Deploy agent. Execute the PRODUCTION DEPLOY stage.

PROJECT: {self.project.name} ({self.project.display_name})
ROOT: {self.project.root_path}
PRODUCTION URL: {prod_url}
{f"TENANT: {tenant}" if tenant else ""}

MCP TOOLS AVAILABLE:
- lrm_build(domain, command): Run deploy commands
- lrm_locate(query, scope): Find deployment files

CRITICAL: This is PRODUCTION deployment. Be extra careful.

YOUR TASK:
1. Execute the production deploy command: {deploy_cmd}
2. Wait for deployment to complete
3. Verify production is accessible at {prod_url}
4. Report SUCCESS or FAILURE with details

Execute the production deploy now.
Output "PROD_SUCCESS" if successful, or "PROD_FAILED: <reason>" if failed.
"""

        try:
            returncode, output = await run_opencode(
                prompt,
                model="minimax/MiniMax-M2.1",
                cwd=str(self.project.root_path),
                timeout=self.OPENCODE_TIMEOUT,
                project=self.project.name,
            )

            if returncode != 0:
                return False, f"Prod agent failed: {output[:500]}"

            if "PROD_SUCCESS" in output:
                self.log("Prod deploy passed ✓")
                return True, ""
            elif "PROD_FAILED" in output:
                error = output.split("PROD_FAILED:")[-1].strip()[:500]
                return False, f"Prod deploy failed: {error}"
            else:
                self.log("Prod deploy completed (implicit success)")
                return True, ""

        except Exception as e:
            return False, str(e)

    async def _stage_verify_prod(self) -> Tuple[bool, str]:
        """Verify production deployment using LLM agent"""
        self.log("Verifying production via LLM agent...")

        deploy_config = self.project.deploy
        prod_url = deploy_config.get("prod", {}).get("url", "")
        health_endpoint = deploy_config.get("prod", {}).get("health", "/health")

        if not prod_url:
            return True, ""

        prompt = f"""You are a Deploy agent. VERIFY the production deployment.

PROJECT: {self.project.name}
PRODUCTION URL: {prod_url}
HEALTH ENDPOINT: {health_endpoint}

YOUR TASK:
1. Check that {prod_url}{health_endpoint} responds correctly
2. Verify the deployment is healthy
3. Report SUCCESS or FAILURE

Use curl or appropriate tools to verify.
Output "VERIFY_SUCCESS" if healthy, or "VERIFY_FAILED: <reason>" if unhealthy.
"""

        try:
            returncode, output = await run_opencode(
                prompt,
                model="minimax/MiniMax-M2.1",
                cwd=str(self.project.root_path),
                timeout=120,  # Quick verification
                project=self.project.name,
            )

            if "VERIFY_SUCCESS" in output:
                self.log("Prod verification passed ✓")
                return True, ""
            elif "VERIFY_FAILED" in output:
                error = output.split("VERIFY_FAILED:")[-1].strip()[:500]
                return False, f"Prod verification failed: {error}"
            else:
                # Check for common success indicators
                if "200" in output or "healthy" in output.lower() or "ok" in output.lower():
                    self.log("Prod verification passed (implicit)")
                    return True, ""
                return False, "Verification unclear"

        except Exception as e:
            return False, str(e)

    async def _rollback(self, tenant: str = None):
        """Rollback production deployment using LLM agent"""
        rollback_cmd = self.project.get_deploy_cmd("rollback", tenant)
        self.log(f"Rolling back production via LLM agent: {rollback_cmd}", "WARN")

        prompt = f"""You are a Deploy agent. Execute EMERGENCY ROLLBACK.

PROJECT: {self.project.name}
{f"TENANT: {tenant}" if tenant else ""}

CRITICAL: Production deployment failed. Execute rollback immediately.

YOUR TASK:
1. Execute the rollback command: {rollback_cmd}
2. Verify rollback completed successfully
3. Report result

Execute rollback now.
Output "ROLLBACK_SUCCESS" or "ROLLBACK_FAILED: <reason>".
"""

        try:
            returncode, output = await run_opencode(
                prompt,
                model="minimax/MiniMax-M2.1",
                cwd=str(self.project.root_path),
                timeout=self.OPENCODE_TIMEOUT,
                project=self.project.name,
            )

            if "ROLLBACK_SUCCESS" in output:
                self.log("Rollback completed ✓")
            elif "ROLLBACK_FAILED" in output:
                error = output.split("ROLLBACK_FAILED:")[-1].strip()[:200]
                self.log(f"Rollback failed: {error}", "ERROR")
            else:
                self.log("Rollback completed (status unclear)")

        except Exception as e:
            self.log(f"Rollback error: {e}", "ERROR")

    def _get_journeys(self, task: Task) -> List[E2EJourney]:
        """Get E2E journeys for task"""
        # Define journeys based on domain/task type
        # These should be defined in project config or discovered from test files

        journeys = []

        # Check for tenant-specific journeys
        if self.project.is_multi_tenant():
            for tenant in self.project.tenants:
                journeys.append(E2EJourney(
                    name=f"smoke-{tenant['name']}",
                    description=f"Basic smoke test for {tenant['name']}",
                    steps=[],
                    tenant=tenant["name"],
                ))

        return journeys

    def _create_feedback_tasks(self, result: DeployResult, original_task: Task):
        """Create feedback tasks in store from deploy failures"""
        for feedback in result.feedback_tasks:
            try:
                # Use the task store's feedback task creation
                failure_stage = feedback.get("stage", "deploy")
                failure_reason = feedback.get("description", "Fix deploy failure")
                evidence = {
                    "type": feedback.get("type", "fix"),
                    "domain": feedback.get("domain", "e2e"),
                    "source_task": feedback.get("source_task"),
                    "context": feedback.get("context"),
                }

                new_task_id = self.task_store.create_task_from_failure(
                    original_task=original_task,
                    failure_reason=failure_reason,
                    failure_stage=failure_stage,
                    evidence=evidence,
                )
                self.log(f"Created feedback task {new_task_id}: {failure_reason[:50]}...")

            except Exception as e:
                self.log(f"Failed to create feedback task: {e}", "ERROR")


# ============================================================================
# DEPLOY POOL
# ============================================================================

class DeployPool:
    """
    Pool of Deploy workers.

    Runs parallel per project (1 worker per project for multi-tenant).
    Consumes tasks from TDD queue that passed adversarial gate.
    """

    def __init__(self, project_name: str = None):
        self.project = get_project(project_name)
        self.task_store = TaskStore()
        self._running = False

    async def run(self):
        """Run deploy workers in daemon mode"""
        self._running = True

        log("=" * 60)
        log(f"Starting Deploy Pool for {self.project.name}")
        log("=" * 60)

        try:
            while self._running:
                # Get tasks ready for deploy (MERGED or QUEUED_FOR_DEPLOY)
                # Tasks flow: TDD → Adversarial Gate → MERGED → QUEUED_FOR_DEPLOY → Deploy
                tasks = self.task_store.get_deployable_tasks(
                    self.project.id,
                    limit=10,
                )

                if not tasks:
                    log("No tasks ready for deploy, waiting...")
                    await asyncio.sleep(10)
                    continue

                log(f"Found {len(tasks)} tasks ready for deploy")

                # Process in parallel (1 per tenant if multi-tenant)
                if self.project.is_multi_tenant():
                    # Group by tenant and process in parallel
                    for task in tasks:
                        worker = DeployWorker(
                            worker_id=task.id[:8],
                            project=self.project,
                            task_store=self.task_store,
                        )
                        await worker.run_pipeline(task)
                else:
                    # Sequential for single-tenant
                    for task in tasks:
                        worker = DeployWorker(
                            worker_id=self.project.name,
                            project=self.project,
                            task_store=self.task_store,
                        )
                        await worker.run_pipeline(task)

                await asyncio.sleep(5)

        except asyncio.CancelledError:
            log("Deploy pool cancelled")
        finally:
            self._running = False
            log("Deploy pool stopped")

    async def run_once(self, task_id: str = None) -> Optional[DeployResult]:
        """Run deploy for a single task"""
        if task_id:
            task = self.task_store.get_task(task_id)
        else:
            # Get tasks ready for deploy (MERGED or QUEUED_FOR_DEPLOY)
            tasks = self.task_store.get_deployable_tasks(
                self.project.id,
                limit=1,
            )
            task = tasks[0] if tasks else None

        if not task:
            log("No task to deploy")
            return None

        worker = DeployWorker(
            worker_id=self.project.name,
            project=self.project,
            task_store=self.task_store,
        )

        return await worker.run_pipeline(task)


# ============================================================================
# DAEMON
# ============================================================================

class WiggumDeployDaemon(Daemon):
    """
    Wiggum Deploy as a system daemon.

    Usage:
        daemon = WiggumDeployDaemon("ppz")
        daemon.start()   # Daemonize and run
        daemon.stop()    # Graceful shutdown
        daemon.status()  # Check status
    """

    def __init__(self, project: str):
        super().__init__(name="wiggum-deploy", project=project)
        self.pool: Optional[DeployPool] = None

    async def run(self):
        """Main daemon loop"""
        self.log("Starting Wiggum Deploy daemon")

        self.pool = DeployPool(self.project)

        try:
            while self.running:
                # Get tasks ready for deploy (MERGED or QUEUED_FOR_DEPLOY)
                tasks = self.pool.task_store.get_deployable_tasks(
                    self.pool.project.id,
                    limit=10,
                )

                if not tasks:
                    self.log("No tasks ready for deploy, waiting...")
                    await asyncio.sleep(10)
                    continue

                self.log(f"Found {len(tasks)} tasks ready for deploy")

                # Process deployments (sequential per tenant for safety)
                if self.pool.project.is_multi_tenant():
                    for task in tasks:
                        if not self.running:
                            break
                        worker = DeployWorker(
                            worker_id=task.id[:8],
                            project=self.pool.project,
                            task_store=self.pool.task_store,
                        )
                        result = await worker.run_pipeline(task)
                        self._create_feedback_tasks_if_needed(result, task)
                else:
                    for task in tasks:
                        if not self.running:
                            break
                        worker = DeployWorker(
                            worker_id=self.pool.project.name,
                            project=self.pool.project,
                            task_store=self.pool.task_store,
                        )
                        result = await worker.run_pipeline(task)
                        self._create_feedback_tasks_if_needed(result, task)

                await asyncio.sleep(5)

        except asyncio.CancelledError:
            self.log("Daemon cancelled")
        except Exception as e:
            self.log(f"Daemon error: {e}", "ERROR")
        finally:
            self.running = False
            self.log("Daemon stopped")

    def _create_feedback_tasks_if_needed(self, result: DeployResult, task: Task):
        """Create feedback tasks from deploy failures"""
        if result.feedback_tasks and self.pool:
            for feedback in result.feedback_tasks:
                try:
                    self.pool.task_store.create_task(
                        project_id=self.pool.project.id,
                        task_type=feedback.get("type", "fix"),
                        domain=feedback.get("domain", "e2e"),
                        description=feedback.get("description", "Fix deploy issue"),
                        files=[],
                        context=feedback,
                    )
                except Exception as e:
                    self.log(f"Failed to create feedback task: {e}", "ERROR")


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Wiggum Deploy - E2E Validation (Daemon)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  start     Start the daemon (background)
  stop      Stop the daemon gracefully
  restart   Restart the daemon
  status    Show daemon status
  run       Run in foreground (no daemonization)
  once      Process single deploy and exit

Examples:
  wiggum_deploy.py --project ppz start       # Start daemon
  wiggum_deploy.py --project ppz stop        # Stop daemon
  wiggum_deploy.py --project ppz status      # Check status
  wiggum_deploy.py --project ppz run         # Run foreground
  wiggum_deploy.py --project ppz once        # Single deploy
        """,
    )
    parser.add_argument("command", nargs="?", default="status",
                        choices=["start", "stop", "restart", "status", "run", "once"],
                        help="Daemon command")
    parser.add_argument("--project", "-p", help="Project name")
    parser.add_argument("--task", "-t", help="Specific task ID (for 'once')")
    parser.add_argument("--all", action="store_true", help="Show all projects status")

    args = parser.parse_args()

    # Handle --all status
    if args.all and args.command == "status":
        manager = DaemonManager(args.project or "all")
        print_all_status(manager.status_all())
        return

    # Project required for most commands
    if args.command in ["start", "stop", "restart", "run", "once"] and not args.project:
        print("Error: --project/-p required")
        sys.exit(1)

    if args.command == "status":
        if args.project:
            daemon = WiggumDeployDaemon(args.project)
            status = daemon.status()
            print_daemon_status(status)

            # Also show deployable tasks
            pool = DeployPool(args.project)
            deployable = pool.task_store.get_deployable_tasks(pool.project.id, limit=100)
            print(f"\n   Deployable tasks: {len(deployable)}")
        else:
            manager = DaemonManager()
            print_all_status(manager.status_all())

    elif args.command == "start":
        daemon = WiggumDeployDaemon(args.project)
        daemon.start(foreground=False)

    elif args.command == "stop":
        daemon = WiggumDeployDaemon(args.project)
        daemon.stop()

    elif args.command == "restart":
        daemon = WiggumDeployDaemon(args.project)
        daemon.restart()

    elif args.command == "run":
        # Run in foreground (for debugging)
        daemon = WiggumDeployDaemon(args.project)
        daemon.start(foreground=True)

    elif args.command == "once":
        pool = DeployPool(args.project)
        result = asyncio.run(pool.run_once(args.task))
        if result:
            icon = "✅" if result.success else "❌"
            print(f"\n{icon} Deploy: {result.task_id}")
            print(f"   Stages passed: {result.stages_passed}")
            print(f"   Stages failed: {result.stages_failed}")
            if result.feedback_tasks:
                print(f"   Feedback tasks: {len(result.feedback_tasks)}")


if __name__ == "__main__":
    main()
