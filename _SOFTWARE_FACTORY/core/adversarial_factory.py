#!/usr/bin/env python3
"""
Factory Adversarial Agent - Meta-Level Process Critique
========================================================
Reviews and critiques the ENTIRE Software Factory process:

1. BRAIN: Task generation quality, prioritization, coverage
2. WIGGUM TDD: Implementation rigor, test quality, code standards
3. WIGGUM DEPLOY: Validation thoroughness, deployment safety
4. METHODOLOGY: RLM approach, agent coordination, feedback loops
5. SYSTEMIC: Blind spots, assumptions, failure modes

This is the "adversarial of adversarials" - a meta-level critique
that challenges the entire software factory architecture.

Usage:
    from core.adversarial_factory import FactoryAdversarial

    adversarial = FactoryAdversarial(project)

    # Review entire factory run
    review = await adversarial.review_factory_run(
        brain_output=brain_tasks,
        tdd_results=tdd_results,
        deploy_results=deploy_results,
    )

    # Periodic methodology audit
    audit = await adversarial.audit_methodology()
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.project_registry import get_project, ProjectConfig
from core.task_store import TaskStore, Task
from core.llm_client import run_opencode


def log(msg: str, level: str = "INFO"):
    """Log with timestamp"""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [FACTORY-ADV] [{level}] {msg}", flush=True)


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class FactoryReview:
    """Result of factory-wide adversarial review"""
    approved: bool
    overall_score: int  # 0-10
    brain_score: int
    tdd_score: int
    deploy_score: int
    methodology_score: int

    critical_issues: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    blind_spots: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    summary: str = ""


@dataclass
class MethodologyAudit:
    """Result of RLM methodology audit"""
    conformant: bool
    score: int

    rlm_violations: List[str] = field(default_factory=list)
    architecture_issues: List[str] = field(default_factory=list)
    process_gaps: List[str] = field(default_factory=list)
    improvement_areas: List[str] = field(default_factory=list)

    verdict: str = ""


# ============================================================================
# FACTORY ADVERSARIAL AGENT
# ============================================================================

class FactoryAdversarial:
    """
    Meta-level Adversarial Agent for the entire Software Factory.

    Critiques:
    - Brain: Is task generation comprehensive? Are priorities correct?
    - TDD: Are tests meaningful? Is code quality enforced?
    - Deploy: Is validation thorough? Are risks mitigated?
    - Methodology: Does it follow RLM principles? Are there gaps?
    - Systemic: What could fail? What are we missing?
    """

    REJECTION_THRESHOLD = 5

    def __init__(self, project: ProjectConfig):
        self.project = project
        self.task_store = TaskStore()

    # ========================================================================
    # BRAIN CRITIQUE
    # ========================================================================

    async def review_brain(
        self,
        tasks_generated: List[Dict],
        vision_doc: str = None,
        focus: str = None,
    ) -> Dict[str, Any]:
        """
        Critique Brain's task generation.

        Questions:
        - Are tasks comprehensive? Missing areas?
        - Is prioritization (WSJF) sensible?
        - Are task descriptions actionable?
        - Is context enrichment sufficient?
        - Are there duplicate or conflicting tasks?
        """
        log("Reviewing Brain task generation...")

        tasks_summary = json.dumps(tasks_generated[:20], indent=2)[:4000]

        prompt = f"""You are an ADVERSARIAL REVIEWER critiquing a Brain (task generator).

PROJECT: {self.project.name}
VISION: {(vision_doc or "Not provided")[:2000]}
FOCUS: {focus or "General analysis"}

TASKS GENERATED ({len(tasks_generated)} total):
```json
{tasks_summary}
```

CRITIQUE THE BRAIN'S WORK:

1. COVERAGE:
   - Are all project areas covered?
   - Any obvious gaps or missing domains?
   - Are edge cases considered?

2. PRIORITIZATION:
   - Do WSJF scores make sense?
   - Are critical issues prioritized correctly?
   - Is there priority inflation (everything "high")?

3. TASK QUALITY:
   - Are descriptions actionable?
   - Is context sufficient for implementation?
   - Are files correctly identified?

4. METHODOLOGY:
   - Did Brain properly explore with MCP tools?
   - Is analysis evidence-based or hallucinated?
   - Are there tasks that seem fabricated?

5. BLIND SPOTS:
   - What is Brain likely missing?
   - What assumptions is Brain making?
   - What could go wrong with these tasks?

Output:
BRAIN_SCORE: <0-10>
COVERAGE_ISSUES:
- <gap 1>
PRIORITIZATION_ISSUES:
- <issue 1>
TASK_QUALITY_ISSUES:
- <issue 1>
METHODOLOGY_ISSUES:
- <issue 1>
BLIND_SPOTS:
- <blind spot 1>
RECOMMENDATIONS:
- <action 1>
VERDICT: <APPROVE or REJECT with reason>
"""

        try:
            returncode, output = await run_opencode(
                prompt,
                model="minimax/MiniMax-M2.1",
                cwd=str(self.project.root_path),
                timeout=300,
                project=self.project.name,
            )

            return self._parse_brain_review(output)

        except Exception as e:
            log(f"Brain review error: {e}", "ERROR")
            return {
                "score": 10,
                "approved": False,
                "issues": [{"type": "error", "message": str(e)}],
            }

    def _parse_brain_review(self, output: str) -> Dict[str, Any]:
        """Parse brain review output"""
        import re

        result = {
            "score": 5,
            "approved": False,
            "coverage_issues": [],
            "prioritization_issues": [],
            "task_quality_issues": [],
            "methodology_issues": [],
            "blind_spots": [],
            "recommendations": [],
            "verdict": "",
        }

        try:
            score_match = re.search(r'BRAIN_SCORE:\s*(\d+)', output)
            if score_match:
                result["score"] = int(score_match.group(1))

            for section in ["COVERAGE_ISSUES", "PRIORITIZATION_ISSUES",
                          "TASK_QUALITY_ISSUES", "METHODOLOGY_ISSUES",
                          "BLIND_SPOTS", "RECOMMENDATIONS"]:
                key = section.lower()
                match = re.search(rf'{section}:\s*(.*?)(?=[A-Z_]+:|VERDICT:|$)', output, re.DOTALL)
                if match:
                    items = [l.strip().lstrip('-').strip()
                            for l in match.group(1).split('\n')
                            if l.strip() and l.strip() != '-']
                    result[key] = [i for i in items if i]

            verdict_match = re.search(r'VERDICT:\s*(.+?)(?=$|\n)', output)
            if verdict_match:
                result["verdict"] = verdict_match.group(1).strip()
                result["approved"] = "APPROVE" in result["verdict"].upper()
            else:
                result["approved"] = result["score"] < self.REJECTION_THRESHOLD

        except Exception as e:
            log(f"Parse error: {e}", "WARN")

        return result

    # ========================================================================
    # TDD CRITIQUE
    # ========================================================================

    async def review_tdd(
        self,
        tdd_results: List[Dict],
        code_samples: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        """
        Critique Wiggum TDD's implementation quality.

        Questions:
        - Are tests actually testing the right things?
        - Is TDD cycle followed (RED-GREEN-REFACTOR)?
        - Is code quality acceptable?
        - Are edge cases handled?
        - Is the adversarial gate effective?
        """
        log("Reviewing Wiggum TDD quality...")

        results_summary = json.dumps(tdd_results[:10], indent=2)[:3000]
        code_summary = ""
        if code_samples:
            for path, code in list(code_samples.items())[:3]:
                code_summary += f"\n=== {path} ===\n{code[:1000]}\n"

        prompt = f"""You are an ADVERSARIAL REVIEWER critiquing TDD implementation.

PROJECT: {self.project.name}

TDD RESULTS ({len(tdd_results)} tasks):
```json
{results_summary}
```

CODE SAMPLES:
{code_summary[:3000] if code_summary else "No code samples provided"}

CRITIQUE THE TDD PROCESS:

1. TEST QUALITY:
   - Do tests actually verify the intended behavior?
   - Are tests meaningful or just "green by default"?
   - Is there test coverage for edge cases?
   - Any test.skip or ignored assertions?

2. TDD CYCLE:
   - Was RED-GREEN-REFACTOR actually followed?
   - Did tests fail before implementation (real RED)?
   - Is code minimal for passing tests (true GREEN)?

3. CODE QUALITY:
   - Are there code smells?
   - Is error handling proper?
   - Any security issues?
   - Is the code maintainable?

4. ADVERSARIAL EFFECTIVENESS:
   - Is the TDD adversarial gate catching issues?
   - Are rejection reasons valid?
   - Is there pattern of bypassing?

5. SYSTEMIC ISSUES:
   - Are Wiggums hallucinating solutions?
   - Is there copy-paste without understanding?
   - Any "looks right but doesn't work" code?

Output:
TDD_SCORE: <0-10>
TEST_ISSUES:
- <issue 1>
CYCLE_ISSUES:
- <issue 1>
CODE_ISSUES:
- <issue 1>
ADVERSARIAL_ISSUES:
- <issue 1>
SYSTEMIC_ISSUES:
- <issue 1>
RECOMMENDATIONS:
- <action 1>
VERDICT: <APPROVE or REJECT with reason>
"""

        try:
            returncode, output = await run_opencode(
                prompt,
                model="minimax/MiniMax-M2.1",
                cwd=str(self.project.root_path),
                timeout=300,
                project=self.project.name,
            )

            return self._parse_tdd_review(output)

        except Exception as e:
            log(f"TDD review error: {e}", "ERROR")
            return {"score": 10, "approved": False, "issues": [str(e)]}

    def _parse_tdd_review(self, output: str) -> Dict[str, Any]:
        """Parse TDD review output"""
        import re

        result = {
            "score": 5,
            "approved": False,
            "test_issues": [],
            "cycle_issues": [],
            "code_issues": [],
            "adversarial_issues": [],
            "systemic_issues": [],
            "recommendations": [],
            "verdict": "",
        }

        try:
            score_match = re.search(r'TDD_SCORE:\s*(\d+)', output)
            if score_match:
                result["score"] = int(score_match.group(1))

            for section in ["TEST_ISSUES", "CYCLE_ISSUES", "CODE_ISSUES",
                          "ADVERSARIAL_ISSUES", "SYSTEMIC_ISSUES", "RECOMMENDATIONS"]:
                key = section.lower()
                match = re.search(rf'{section}:\s*(.*?)(?=[A-Z_]+:|VERDICT:|$)', output, re.DOTALL)
                if match:
                    items = [l.strip().lstrip('-').strip()
                            for l in match.group(1).split('\n')
                            if l.strip() and l.strip() != '-']
                    result[key] = [i for i in items if i]

            verdict_match = re.search(r'VERDICT:\s*(.+?)(?=$|\n)', output)
            if verdict_match:
                result["verdict"] = verdict_match.group(1).strip()
                result["approved"] = "APPROVE" in result["verdict"].upper()
            else:
                result["approved"] = result["score"] < self.REJECTION_THRESHOLD

        except Exception as e:
            log(f"Parse error: {e}", "WARN")

        return result

    # ========================================================================
    # DEPLOY CRITIQUE
    # ========================================================================

    async def review_deploy(
        self,
        deploy_results: List[Dict],
        stages_passed: List[str] = None,
        stages_failed: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Critique Wiggum Deploy's validation thoroughness.

        Questions:
        - Is E2E coverage sufficient?
        - Are security tests comprehensive?
        - Is the deploy process safe?
        - Are rollback procedures tested?
        - Is production verification adequate?
        """
        log("Reviewing Wiggum Deploy quality...")

        results_summary = json.dumps(deploy_results[:10], indent=2)[:3000]

        prompt = f"""You are an ADVERSARIAL REVIEWER critiquing the Deploy pipeline.

PROJECT: {self.project.name}

DEPLOY RESULTS ({len(deploy_results)} deployments):
```json
{results_summary}
```

STAGES PASSED: {stages_passed or []}
STAGES FAILED: {stages_failed or []}

CRITIQUE THE DEPLOY PROCESS:

1. E2E COVERAGE:
   - Are critical user journeys tested?
   - Is test coverage comprehensive?
   - Are tests deterministic (not flaky)?

2. SECURITY VALIDATION:
   - Are OWASP top 10 actually checked?
   - Is RBAC properly validated?
   - Are auth bypass attempts tested?

3. DEPLOY SAFETY:
   - Is staging identical to production?
   - Are rollback procedures verified?
   - Is there proper monitoring?

4. ADVERSARIAL EFFECTIVENESS:
   - Is the deploy adversarial catching issues?
   - Is the final gate effective?
   - Any patterns of approval without rigor?

5. PRODUCTION RISK:
   - What could fail in production?
   - Are there untested scenarios?
   - Is recovery tested?

Output:
DEPLOY_SCORE: <0-10>
E2E_ISSUES:
- <issue 1>
SECURITY_ISSUES:
- <issue 1>
SAFETY_ISSUES:
- <issue 1>
ADVERSARIAL_ISSUES:
- <issue 1>
PRODUCTION_RISKS:
- <risk 1>
RECOMMENDATIONS:
- <action 1>
VERDICT: <APPROVE or REJECT with reason>
"""

        try:
            returncode, output = await run_opencode(
                prompt,
                model="minimax/MiniMax-M2.1",
                cwd=str(self.project.root_path),
                timeout=300,
                project=self.project.name,
            )

            return self._parse_deploy_review(output)

        except Exception as e:
            log(f"Deploy review error: {e}", "ERROR")
            return {"score": 10, "approved": False, "issues": [str(e)]}

    def _parse_deploy_review(self, output: str) -> Dict[str, Any]:
        """Parse deploy review output"""
        import re

        result = {
            "score": 5,
            "approved": False,
            "e2e_issues": [],
            "security_issues": [],
            "safety_issues": [],
            "adversarial_issues": [],
            "production_risks": [],
            "recommendations": [],
            "verdict": "",
        }

        try:
            score_match = re.search(r'DEPLOY_SCORE:\s*(\d+)', output)
            if score_match:
                result["score"] = int(score_match.group(1))

            for section in ["E2E_ISSUES", "SECURITY_ISSUES", "SAFETY_ISSUES",
                          "ADVERSARIAL_ISSUES", "PRODUCTION_RISKS", "RECOMMENDATIONS"]:
                key = section.lower()
                match = re.search(rf'{section}:\s*(.*?)(?=[A-Z_]+:|VERDICT:|$)', output, re.DOTALL)
                if match:
                    items = [l.strip().lstrip('-').strip()
                            for l in match.group(1).split('\n')
                            if l.strip() and l.strip() != '-']
                    result[key] = [i for i in items if i]

            verdict_match = re.search(r'VERDICT:\s*(.+?)(?=$|\n)', output)
            if verdict_match:
                result["verdict"] = verdict_match.group(1).strip()
                result["approved"] = "APPROVE" in result["verdict"].upper()
            else:
                result["approved"] = result["score"] < self.REJECTION_THRESHOLD

        except Exception as e:
            log(f"Parse error: {e}", "WARN")

        return result

    # ========================================================================
    # METHODOLOGY AUDIT
    # ========================================================================

    async def audit_methodology(self) -> MethodologyAudit:
        """
        Audit the entire RLM methodology implementation.

        Questions:
        - Does this follow MIT CSAIL RLM principles?
        - Is MCP LRM properly replacing REPL?
        - Is the agent architecture sound?
        - Are feedback loops working?
        - What are the systemic weaknesses?
        """
        log("Auditing RLM methodology...")

        # Gather evidence about the factory
        tasks = self.task_store.get_tasks_by_project(self.project.id)
        task_stats = {
            "total": len(tasks),
            "by_status": {},
            "by_domain": {},
        }
        for t in tasks:
            task_stats["by_status"][t.status] = task_stats["by_status"].get(t.status, 0) + 1
            task_stats["by_domain"][t.domain] = task_stats["by_domain"].get(t.domain, 0) + 1

        prompt = f"""You are auditing a Software Factory based on MIT CSAIL RLM (arXiv:2512.24601).

PROJECT: {self.project.name}

ARCHITECTURE:
- Brain: Claude Opus 4.5 + MCP LRM tools (replaces REPL with project navigation)
- Wiggum TDD: MiniMax M2.1 + MCP LRM tools (50 parallel workers)
- Wiggum Deploy: MiniMax M2.1 + MCP LRM tools (10 workers)
- Adversarial gates at TDD and Deploy stages
- Task Store: SQLite with zlib compression

TASK STATISTICS:
{json.dumps(task_stats, indent=2)}

AUDIT THE METHODOLOGY:

1. RLM CONFORMANCE:
   - Is MCP LRM properly replacing REPL?
   - Do agents have proper project visibility?
   - Is recursive decomposition (FRACTAL) implemented?
   - Are sub-agents properly coordinated?

2. ARCHITECTURE SOUNDNESS:
   - Is Brain/Wiggum separation correct?
   - Are 50 parallel workers appropriate?
   - Is the adversarial approach effective?
   - Are feedback loops closed?

3. PROCESS INTEGRITY:
   - Is TDD actually enforced?
   - Are adversarial gates rigorous?
   - Is deploy pipeline thorough?
   - Are failures properly fed back?

4. SYSTEMIC WEAKNESSES:
   - What could fail silently?
   - Where are the blind spots?
   - What assumptions are dangerous?
   - How could agents game the system?

5. IMPROVEMENT OPPORTUNITIES:
   - What's missing from the architecture?
   - Where should controls be stronger?
   - What metrics should be tracked?

Output:
METHODOLOGY_SCORE: <0-10>
RLM_VIOLATIONS:
- <violation 1>
ARCHITECTURE_ISSUES:
- <issue 1>
PROCESS_GAPS:
- <gap 1>
SYSTEMIC_WEAKNESSES:
- <weakness 1>
IMPROVEMENT_AREAS:
- <area 1>
CONFORMANCE: <CONFORMANT or NON-CONFORMANT>
VERDICT: <assessment summary>
"""

        try:
            returncode, output = await run_opencode(
                prompt,
                model="minimax/MiniMax-M2.1",
                cwd=str(self.project.root_path),
                timeout=300,
                project=self.project.name,
            )

            return self._parse_methodology_audit(output)

        except Exception as e:
            log(f"Methodology audit error: {e}", "ERROR")
            return MethodologyAudit(
                conformant=False,
                score=10,
                rlm_violations=[str(e)],
                verdict=f"Audit failed: {e}",
            )

    def _parse_methodology_audit(self, output: str) -> MethodologyAudit:
        """Parse methodology audit output"""
        import re

        audit = MethodologyAudit(conformant=False, score=5)

        try:
            score_match = re.search(r'METHODOLOGY_SCORE:\s*(\d+)', output)
            if score_match:
                audit.score = int(score_match.group(1))

            sections = {
                "RLM_VIOLATIONS": "rlm_violations",
                "ARCHITECTURE_ISSUES": "architecture_issues",
                "PROCESS_GAPS": "process_gaps",
                "SYSTEMIC_WEAKNESSES": "improvement_areas",  # Map to improvement
                "IMPROVEMENT_AREAS": "improvement_areas",
            }

            for section, attr in sections.items():
                match = re.search(rf'{section}:\s*(.*?)(?=[A-Z_]+:|CONFORMANCE:|VERDICT:|$)', output, re.DOTALL)
                if match:
                    items = [l.strip().lstrip('-').strip()
                            for l in match.group(1).split('\n')
                            if l.strip() and l.strip() != '-']
                    current = getattr(audit, attr)
                    setattr(audit, attr, current + [i for i in items if i])

            conformance_match = re.search(r'CONFORMANCE:\s*(CONFORMANT|NON-CONFORMANT)', output, re.IGNORECASE)
            if conformance_match:
                audit.conformant = conformance_match.group(1).upper() == "CONFORMANT"
            else:
                audit.conformant = audit.score < self.REJECTION_THRESHOLD

            verdict_match = re.search(r'VERDICT:\s*(.+?)(?=$|\n\n)', output, re.DOTALL)
            if verdict_match:
                audit.verdict = verdict_match.group(1).strip()[:500]

        except Exception as e:
            log(f"Parse error: {e}", "WARN")

        return audit

    # ========================================================================
    # FULL FACTORY REVIEW
    # ========================================================================

    async def review_factory_run(
        self,
        brain_output: List[Dict] = None,
        tdd_results: List[Dict] = None,
        deploy_results: List[Dict] = None,
    ) -> FactoryReview:
        """
        Comprehensive review of an entire factory run.

        Reviews Brain, TDD, Deploy, and Methodology together
        to identify cross-cutting issues and systemic problems.
        """
        log("Starting full factory review...")

        # Run individual reviews
        brain_review = await self.review_brain(brain_output or [])
        tdd_review = await self.review_tdd(tdd_results or [])
        deploy_review = await self.review_deploy(deploy_results or [])
        methodology_audit = await self.audit_methodology()

        # Calculate overall score
        scores = [
            brain_review.get("score", 5),
            tdd_review.get("score", 5),
            deploy_review.get("score", 5),
            methodology_audit.score,
        ]
        overall_score = sum(scores) // len(scores)

        # Aggregate issues
        critical_issues = []
        warnings = []
        blind_spots = []
        recommendations = []

        # From Brain
        for issue in brain_review.get("coverage_issues", []):
            critical_issues.append({"source": "brain", "type": "coverage", "message": issue})
        for issue in brain_review.get("blind_spots", []):
            blind_spots.append(issue)
        recommendations.extend(brain_review.get("recommendations", []))

        # From TDD
        for issue in tdd_review.get("test_issues", []):
            critical_issues.append({"source": "tdd", "type": "test", "message": issue})
        for issue in tdd_review.get("systemic_issues", []):
            critical_issues.append({"source": "tdd", "type": "systemic", "message": issue})
        recommendations.extend(tdd_review.get("recommendations", []))

        # From Deploy
        for issue in deploy_review.get("security_issues", []):
            critical_issues.append({"source": "deploy", "type": "security", "message": issue})
        for risk in deploy_review.get("production_risks", []):
            warnings.append({"source": "deploy", "type": "risk", "message": risk})
        recommendations.extend(deploy_review.get("recommendations", []))

        # From Methodology
        for violation in methodology_audit.rlm_violations:
            critical_issues.append({"source": "methodology", "type": "rlm", "message": violation})
        for gap in methodology_audit.process_gaps:
            warnings.append({"source": "methodology", "type": "process", "message": gap})
        recommendations.extend(methodology_audit.improvement_areas)

        # Determine approval
        approved = (
            brain_review.get("approved", False) and
            tdd_review.get("approved", False) and
            deploy_review.get("approved", False) and
            methodology_audit.conformant and
            overall_score < self.REJECTION_THRESHOLD
        )

        # Build summary
        summary = f"""Factory Review Summary:
- Brain: {brain_review.get('score', '?')}/10 ({'APPROVED' if brain_review.get('approved') else 'REJECTED'})
- TDD: {tdd_review.get('score', '?')}/10 ({'APPROVED' if tdd_review.get('approved') else 'REJECTED'})
- Deploy: {deploy_review.get('score', '?')}/10 ({'APPROVED' if deploy_review.get('approved') else 'REJECTED'})
- Methodology: {methodology_audit.score}/10 ({'CONFORMANT' if methodology_audit.conformant else 'NON-CONFORMANT'})
- Overall: {overall_score}/10 ({'APPROVED' if approved else 'REJECTED'})
- Critical Issues: {len(critical_issues)}
- Warnings: {len(warnings)}
- Blind Spots: {len(blind_spots)}
"""

        return FactoryReview(
            approved=approved,
            overall_score=overall_score,
            brain_score=brain_review.get("score", 5),
            tdd_score=tdd_review.get("score", 5),
            deploy_score=deploy_review.get("score", 5),
            methodology_score=methodology_audit.score,
            critical_issues=critical_issues,
            warnings=warnings,
            blind_spots=blind_spots,
            recommendations=list(set(recommendations)),  # Dedupe
            summary=summary,
        )

    # ========================================================================
    # CONTINUOUS MONITORING
    # ========================================================================

    async def monitor_factory_health(self) -> Dict[str, Any]:
        """
        Continuous health check of the factory.

        Runs periodically to detect:
        - Task accumulation (backlog growing)
        - Failure patterns (same tasks failing repeatedly)
        - Adversarial bypasses (approvals without rigor)
        - Process degradation (quality declining)
        """
        log("Monitoring factory health...")

        tasks = self.task_store.get_tasks_by_project(self.project.id)

        # Calculate metrics
        metrics = {
            "total_tasks": len(tasks),
            "pending_count": 0,
            "failed_count": 0,
            "completed_count": 0,
            "retry_heavy": [],  # Tasks with many retries
            "stale_tasks": [],  # Tasks stuck for long time
        }

        now = datetime.now()
        for task in tasks:
            if task.status == "pending":
                metrics["pending_count"] += 1
            elif "failed" in task.status.lower():
                metrics["failed_count"] += 1
            elif task.status in ["completed", "deployed"]:
                metrics["completed_count"] += 1

        # Health assessment
        health = {
            "status": "healthy",
            "alerts": [],
            "metrics": metrics,
        }

        # Check for issues
        if metrics["pending_count"] > 100:
            health["alerts"].append({
                "level": "warning",
                "message": f"Large backlog: {metrics['pending_count']} pending tasks",
            })

        if metrics["failed_count"] > metrics["completed_count"] * 0.3:
            health["alerts"].append({
                "level": "critical",
                "message": f"High failure rate: {metrics['failed_count']} failed vs {metrics['completed_count']} completed",
            })
            health["status"] = "degraded"

        if metrics["total_tasks"] == 0:
            health["alerts"].append({
                "level": "info",
                "message": "No tasks in system - Brain may need to run",
            })

        return health


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Factory Adversarial Agent")
    parser.add_argument("--project", "-p", help="Project name")
    parser.add_argument("--audit", action="store_true", help="Run methodology audit")
    parser.add_argument("--health", action="store_true", help="Check factory health")
    parser.add_argument("--full", action="store_true", help="Full factory review")

    args = parser.parse_args()

    project = get_project(args.project)
    adversarial = FactoryAdversarial(project)

    if args.audit:
        audit = asyncio.run(adversarial.audit_methodology())
        print(f"\nMethodology Audit:")
        print(f"  Conformant: {audit.conformant}")
        print(f"  Score: {audit.score}/10")
        print(f"  Verdict: {audit.verdict}")
        if audit.rlm_violations:
            print(f"  RLM Violations: {audit.rlm_violations}")

    elif args.health:
        health = asyncio.run(adversarial.monitor_factory_health())
        print(f"\nFactory Health:")
        print(f"  Status: {health['status']}")
        print(f"  Metrics: {json.dumps(health['metrics'], indent=2)}")
        if health['alerts']:
            print(f"  Alerts: {health['alerts']}")

    elif args.full:
        review = asyncio.run(adversarial.review_factory_run())
        print(f"\n{review.summary}")
        if review.critical_issues:
            print(f"\nCritical Issues:")
            for issue in review.critical_issues[:5]:
                print(f"  - [{issue['source']}] {issue['message']}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
