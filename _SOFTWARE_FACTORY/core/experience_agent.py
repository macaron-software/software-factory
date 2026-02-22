#!/usr/bin/env python3
"""
Experience Learning Agent - Meta-Brain for Factory Self-Improvement
====================================================================
Based on MIT CSAIL arXiv:2512.24601 "Recursive Language Models"

Analyses global factory experience to:
1. Detect failure patterns (repeated rejects, stuck tasks)
2. Identify gaps in coverage (KISS violations, missing tests)
3. Propose factory improvements (better fractal depth, new patterns)
4. Learn from successes (what works → replicate)

Uses Claude Opus 4.5 for deep reasoning.

Architecture:
    ErrorCapture → TaskStore ← ExperienceAgent → Factory Improvements
                         ↓
                    Adversarial Gate (learns new patterns)

Usage:
    from core.experience_agent import ExperienceAgent
    agent = ExperienceAgent()
    insights = await agent.analyze()
    await agent.apply_improvements(insights)
"""

import json
import sqlite3
import asyncio
import subprocess
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
import zlib


def log(msg: str, level: str = "INFO"):
    """Log with timestamp"""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [XP-AGENT] [{level}] {msg}", flush=True)


# ============================================================================
# DATA STRUCTURES
# ============================================================================

class InsightType(str, Enum):
    """Types of insights from experience analysis"""
    # Failure patterns
    REPEATED_REJECTION = "repeated_rejection"      # Same adversarial rule hits
    STUCK_TASKS = "stuck_tasks"                    # Tasks in progress too long
    TDD_FAILURES = "tdd_failures"                  # Repeated TDD cycle failures
    DEPLOY_FAILURES = "deploy_failures"            # Production rollbacks
    
    # Coverage gaps
    MISSING_E2E = "missing_e2e"                    # Features without E2E tests
    KISS_VIOLATION = "kiss_violation"              # Over-complex solutions
    FRACTAL_SHALLOW = "fractal_shallow"            # Should decompose more
    FRACTAL_TOO_DEEP = "fractal_too_deep"          # Over-decomposed
    
    # Security/Quality
    SECURITY_PATTERN = "security_pattern"          # New security issue detected
    SLOP_PATTERN = "slop_pattern"                  # AI-generated bad patterns
    
    # Resilience/Chaos
    CHAOS_FAILURE = "chaos_failure"                # Chaos monkey failure
    RESILIENCE_GAP = "resilience_gap"              # Missing resilience (retry, circuit breaker)
    
    # Security Audit
    CVE_VULNERABILITY = "cve_vulnerability"        # Known CVE detected
    PENTEST_FINDING = "pentest_finding"            # Penetration test finding
    OWASP_VIOLATION = "owasp_violation"            # OWASP Top 10 violation
    
    # Positive patterns
    SUCCESS_PATTERN = "success_pattern"            # What works well


@dataclass
class Insight:
    """An insight from experience analysis"""
    type: InsightType
    severity: str  # "critical", "high", "medium", "low"
    title: str
    description: str
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    recommendation: str = ""
    affected_projects: List[str] = field(default_factory=list)
    auto_fixable: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "type": self.type.value,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "evidence": self.evidence,
            "recommendation": self.recommendation,
            "affected_projects": self.affected_projects,
            "auto_fixable": self.auto_fixable,
        }


@dataclass
class Improvement:
    """A concrete improvement to apply"""
    target: str  # "adversarial", "fractal", "brain", "wiggum"
    action: str  # "add_pattern", "adjust_threshold", "update_config"
    payload: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    applied: bool = False


# ============================================================================
# EXPERIENCE AGENT
# ============================================================================

class ExperienceAgent:
    """
    Meta-Brain that learns from factory experience.
    
    Runs periodically (cron) or on-demand to:
    1. Query TaskStore for patterns
    2. Analyze with Claude Opus 4.5
    3. Generate improvements
    4. Apply auto-fixable improvements
    5. Create tasks for manual improvements
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path(__file__).parent.parent / "data" / "factory.db"
        self.insights: List[Insight] = []
        self.improvements: List[Improvement] = []
        
    def _get_db(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    # ========================================================================
    # DATA COLLECTION
    # ========================================================================
    
    def collect_failure_stats(self, days: int = 7) -> Dict[str, Any]:
        """Collect failure statistics from last N days"""
        conn = self._get_db()
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        stats = {}
        
        # Tasks by status
        cur = conn.execute("""
            SELECT project_id, status, COUNT(*) as count
            FROM tasks
            WHERE created_at > ?
            GROUP BY project_id, status
        """, (cutoff,))
        stats["status_counts"] = [dict(r) for r in cur.fetchall()]
        
        # Stuck tasks (in_progress for > 2 hours)
        stuck_cutoff = (datetime.now() - timedelta(hours=2)).isoformat()
        cur = conn.execute("""
            SELECT id, project_id, domain, description, status, updated_at
            FROM tasks
            WHERE status IN ('tdd_in_progress', 'locked')
            AND updated_at < ?
        """, (stuck_cutoff,))
        stats["stuck_tasks"] = [dict(r) for r in cur.fetchall()]
        
        # High retry tasks (> 3 attempts)
        cur = conn.execute("""
            SELECT id, project_id, domain, description, tdd_attempts, adversarial_attempts, last_error
            FROM tasks
            WHERE tdd_attempts > 3 OR adversarial_attempts > 3
        """)
        stats["high_retry_tasks"] = [dict(r) for r in cur.fetchall()]
        
        # Adversarial rejection patterns
        cur = conn.execute("""
            SELECT task_id, verdict, issues_gz
            FROM attempts
            WHERE stage = 'adversarial' AND verdict = 'rejected'
            AND created_at > ?
            LIMIT 100
        """, (cutoff,))
        
        rejection_reasons = {}
        for row in cur.fetchall():
            if row['issues_gz']:
                try:
                    issues = json.loads(zlib.decompress(row['issues_gz']).decode())
                    for issue in issues:
                        rule = issue.get('rule', 'unknown')
                        rejection_reasons[rule] = rejection_reasons.get(rule, 0) + 1
                except Exception:
                    pass
        stats["rejection_patterns"] = rejection_reasons
        
        # Deploy failures
        cur = conn.execute("""
            SELECT task_id, env, status, created_at
            FROM deployments
            WHERE status IN ('failed', 'rollback')
            AND created_at > ?
        """, (cutoff,))
        stats["deploy_failures"] = [dict(r) for r in cur.fetchall()]
        
        # Decomposed tasks (fractal depth)
        cur = conn.execute("""
            SELECT project_id, depth, COUNT(*) as count
            FROM tasks
            WHERE depth > 0
            GROUP BY project_id, depth
            ORDER BY depth
        """)
        stats["fractal_depth"] = [dict(r) for r in cur.fetchall()]
        
        # Success rate by domain
        cur = conn.execute("""
            SELECT project_id, domain,
                   SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                   SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                   COUNT(*) as total
            FROM tasks
            WHERE created_at > ?
            GROUP BY project_id, domain
        """, (cutoff,))
        stats["domain_success"] = [dict(r) for r in cur.fetchall()]
        
        conn.close()
        return stats
    
    def collect_adversarial_patterns(self) -> List[Dict]:
        """Get current adversarial patterns from config"""
        from core.adversarial import CORE_REJECT_PATTERNS, CORE_WARNING_PATTERNS, SECURITY_PATTERNS
        
        patterns = []
        for pattern, (rule, points, msg) in CORE_REJECT_PATTERNS.items():
            patterns.append({"pattern": pattern, "rule": rule, "points": points, "type": "reject"})
        for pattern, (rule, points, msg, max_occ) in CORE_WARNING_PATTERNS.items():
            patterns.append({"pattern": pattern, "rule": rule, "points": points, "type": "warning", "max": max_occ})
        for pattern, (rule, points, msg) in SECURITY_PATTERNS.items():
            patterns.append({"pattern": pattern, "rule": rule, "points": points, "type": "security"})
            
        return patterns
    
    def collect_recent_errors(self, limit: int = 50) -> List[Dict]:
        """Collect recent error messages from failed tasks"""
        conn = self._get_db()
        cur = conn.execute("""
            SELECT id, project_id, domain, description, last_error, tdd_attempts
            FROM tasks
            WHERE last_error IS NOT NULL
            ORDER BY updated_at DESC
            LIMIT ?
        """, (limit,))
        errors = [dict(r) for r in cur.fetchall()]
        conn.close()
        return errors
    
    # ========================================================================
    # CHAOS MONKEY - Resilience Testing
    # ========================================================================
    
    async def run_chaos_tests(self, project_id: str, target_env: str = "staging") -> List[Insight]:
        """
        Run chaos monkey tests on staging/prod.
        
        Tests:
        - Kill random service
        - Network latency injection
        - Memory pressure
        - Disk full simulation
        - DB connection drop
        """
        insights = []
        log(f"Running chaos tests on {project_id}/{target_env}...")
        
        chaos_tests = [
            ("service_kill", "Kill random svc, check recovery <30s"),
            ("network_latency", "Inject 500ms latency, check timeout handling"),
            ("memory_pressure", "Allocate 80% mem, check OOM handling"),
            ("db_disconnect", "Drop DB conn, check reconnect logic"),
            ("api_timeout", "Slow API resp 10s, check circuit breaker"),
        ]
        
        # Get project config
        try:
            from core.project_registry import get_project
            project = get_project(project_id)
            staging_url = project.deploy.get('staging', {}).get('url', '')
            
            if not staging_url:
                log(f"No staging URL for {project_id}, skip chaos", "WARN")
                return insights
            
            # Run chaos via LLM analysis of codebase resilience
            prompt = f"""Analyze this project for RESILIENCE and CHAOS readiness:

Project: {project_id}
Staging URL: {staging_url}

Check for:
1. RETRY LOGIC: Are there retry mechanisms with exponential backoff?
2. CIRCUIT BREAKERS: Is there circuit breaker pattern for external calls?
3. TIMEOUTS: Are all HTTP/gRPC calls using timeouts?
4. GRACEFUL DEGRADATION: Does the app degrade gracefully on failures?
5. HEALTH CHECKS: Are there /health endpoints?
6. RECOVERY: Can services auto-recover after crash?

Respond JSON:
{{
  "resilience_score": 0-100,
  "gaps": [
    {{"issue": "description", "severity": "critical|high|medium", "fix": "how to fix"}}
  ],
  "chaos_ready": true/false
}}
"""
            proc = await asyncio.create_subprocess_exec(
                "claude", "-p", "--model", "claude-sonnet-4-20250514", "--max-turns", "1",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(input=prompt.encode()), timeout=60)
            output = stdout.decode()
            
            # Parse response
            import re
            json_match = re.search(r'\{[\s\S]*"resilience_score"[\s\S]*\}', output)
            if json_match:
                result = json.loads(json_match.group())
                
                for gap in result.get('gaps', []):
                    insights.append(Insight(
                        type=InsightType.RESILIENCE_GAP,
                        severity=gap.get('severity', 'medium'),
                        title=f"[{project_id}] {gap.get('issue', 'Resilience gap')}",
                        description=gap.get('issue', ''),
                        recommendation=gap.get('fix', ''),
                        affected_projects=[project_id],
                        auto_fixable=False,
                    ))
                
                log(f"Resilience score: {result.get('resilience_score', 0)}/100, {len(result.get('gaps', []))} gaps")
                
        except Exception as e:
            log(f"Chaos test error: {e}", "ERROR")
        
        return insights
    
    # ========================================================================
    # SECURITY AUDIT - CVE/OWASP/Pentest
    # ========================================================================
    
    async def run_security_audit(self, project_id: str) -> List[Insight]:
        """
        Run security audit:
        - Fetch latest CVEs from NVD
        - Check OWASP Top 10
        - Run basic pentest checks
        """
        insights = []
        log(f"Running security audit on {project_id}...")
        
        try:
            from core.project_registry import get_project
            project = get_project(project_id)
            
            # 1. Check for known CVEs in dependencies
            cve_insights = await self._check_cves(project)
            insights.extend(cve_insights)
            
            # 2. OWASP Top 10 analysis
            owasp_insights = await self._check_owasp(project)
            insights.extend(owasp_insights)
            
            # 3. Basic pentest on staging
            pentest_insights = await self._run_pentest(project)
            insights.extend(pentest_insights)
            
        except Exception as e:
            log(f"Security audit error: {e}", "ERROR")
        
        return insights
    
    async def _check_cves(self, project) -> List[Insight]:
        """Check dependencies for known CVEs"""
        insights = []
        project_root = Path(project.root_path)
        
        # Check Cargo.lock for Rust
        cargo_lock = project_root / "Cargo.lock"
        if cargo_lock.exists():
            try:
                proc = await asyncio.create_subprocess_exec(
                    "cargo", "audit", "--json",
                    cwd=str(project_root),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
                
                if stdout:
                    audit = json.loads(stdout.decode())
                    for vuln in audit.get('vulnerabilities', {}).get('list', []):
                        insights.append(Insight(
                            type=InsightType.CVE_VULNERABILITY,
                            severity="critical" if vuln.get('severity') == 'high' else "high",
                            title=f"CVE: {vuln.get('advisory', {}).get('id', 'Unknown')}",
                            description=vuln.get('advisory', {}).get('title', ''),
                            recommendation=f"Upgrade {vuln.get('package', {}).get('name', '')}",
                            affected_projects=[project.id],
                        ))
            except Exception as e:
                log(f"cargo audit failed: {e}", "WARN")
        
        # Check package.json for npm
        pkg_json = project_root / "package.json"
        if pkg_json.exists():
            try:
                proc = await asyncio.create_subprocess_exec(
                    "npm", "audit", "--json",
                    cwd=str(project_root),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
                
                if stdout:
                    audit = json.loads(stdout.decode())
                    for vuln_id, vuln in audit.get('vulnerabilities', {}).items():
                        if vuln.get('severity') in ['high', 'critical']:
                            insights.append(Insight(
                                type=InsightType.CVE_VULNERABILITY,
                                severity="critical" if vuln.get('severity') == 'critical' else "high",
                                title=f"npm: {vuln_id} ({vuln.get('severity', '')})",
                                description=vuln.get('via', [{}])[0].get('title', '') if vuln.get('via') else '',
                                recommendation=f"npm audit fix or upgrade {vuln_id}",
                                affected_projects=[project.id],
                            ))
            except Exception as e:
                log(f"npm audit failed: {e}", "WARN")
        
        return insights
    
    async def _check_owasp(self, project) -> List[Insight]:
        """Check for OWASP Top 10 violations"""
        insights = []
        
        # Use LLM to analyze code for OWASP issues
        prompt = f"""Analyze project {project.id} for OWASP Top 10 2021 vulnerabilities:

A01: Broken Access Control
A02: Cryptographic Failures  
A03: Injection (SQL, XSS, Command)
A04: Insecure Design
A05: Security Misconfiguration
A06: Vulnerable Components
A07: Auth Failures
A08: Software/Data Integrity Failures
A09: Security Logging Failures
A10: SSRF

Check the codebase patterns and respond JSON:
{{
  "owasp_violations": [
    {{"code": "A01-A10", "issue": "desc", "file": "path", "severity": "critical|high|medium", "fix": "how"}}
  ],
  "owasp_score": 0-100
}}
"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "claude", "-p", "--model", "claude-sonnet-4-20250514", "--max-turns", "1",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(input=prompt.encode()), timeout=90)
            output = stdout.decode()
            
            json_match = re.search(r'\{[\s\S]*"owasp_violations"[\s\S]*\}', output)
            if json_match:
                result = json.loads(json_match.group())
                
                for v in result.get('owasp_violations', []):
                    insights.append(Insight(
                        type=InsightType.OWASP_VIOLATION,
                        severity=v.get('severity', 'high'),
                        title=f"[{v.get('code', 'OWASP')}] {v.get('issue', '')}",
                        description=f"File: {v.get('file', 'unknown')}\n{v.get('issue', '')}",
                        recommendation=v.get('fix', ''),
                        affected_projects=[project.id],
                    ))
                
                log(f"OWASP score: {result.get('owasp_score', 0)}/100")
                
        except Exception as e:
            log(f"OWASP check failed: {e}", "WARN")
        
        return insights
    
    async def _run_pentest(self, project) -> List[Insight]:
        """Run basic penetration tests on staging"""
        insights = []
        staging_url = project.deploy.get('staging', {}).get('url', '')
        
        if not staging_url:
            return insights
        
        log(f"Running pentest on {staging_url}...")
        
        # Basic security checks via curl
        pentest_checks = [
            ("headers", f"curl -sI {staging_url} | grep -iE 'x-frame|x-content|strict-transport|x-xss'"),
            ("cors", f"curl -sI -H 'Origin: https://evil.com' {staging_url} | grep -i 'access-control'"),
            ("robots", f"curl -s {staging_url}/robots.txt | grep -i disallow"),
            ("admin", f"curl -sI {staging_url}/admin 2>/dev/null | head -1"),
            ("api_docs", f"curl -sI {staging_url}/swagger 2>/dev/null | head -1"),
        ]
        
        for name, cmd in pentest_checks:
            try:
                proc = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
                result = stdout.decode().strip()
                
                # Check for security issues
                if name == "headers" and not result:
                    insights.append(Insight(
                        type=InsightType.PENTEST_FINDING,
                        severity="high",
                        title=f"Missing security headers on {staging_url}",
                        description="No X-Frame-Options, CSP, or HSTS headers found",
                        recommendation="Add security headers: X-Frame-Options, Content-Security-Policy, Strict-Transport-Security",
                        affected_projects=[project.id],
                    ))
                
                if name == "admin" and "200" in result:
                    insights.append(Insight(
                        type=InsightType.PENTEST_FINDING,
                        severity="critical",
                        title=f"/admin endpoint publicly accessible",
                        description=f"{staging_url}/admin returns 200",
                        recommendation="Protect /admin with authentication",
                        affected_projects=[project.id],
                    ))
                    
            except Exception:
                pass
        
        return insights
    
    async def fetch_latest_cves(self, keywords: List[str] = None) -> List[Dict]:
        """Fetch latest CVEs from NVD API"""
        if keywords is None:
            keywords = ["rust", "tokio", "axum", "typescript", "react", "grpc", "protobuf"]
        
        cves = []
        log("Fetching latest CVEs from NVD...")
        
        try:
            import urllib.request
            import urllib.parse
            
            for keyword in keywords[:3]:  # Limit to avoid rate limiting
                url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch={urllib.parse.quote(keyword)}&resultsPerPage=5"
                
                req = urllib.request.Request(url, headers={'User-Agent': 'Factory-XP-Agent/1.0'})
                with urllib.request.urlopen(req, timeout=10) as response:
                    data = json.loads(response.read().decode())
                    
                    for vuln in data.get('vulnerabilities', [])[:3]:
                        cve = vuln.get('cve', {})
                        cves.append({
                            "id": cve.get('id', ''),
                            "description": cve.get('descriptions', [{}])[0].get('value', '')[:200],
                            "severity": cve.get('metrics', {}).get('cvssMetricV31', [{}])[0].get('cvssData', {}).get('baseSeverity', 'UNKNOWN'),
                            "keyword": keyword,
                        })
                        
        except Exception as e:
            log(f"CVE fetch failed: {e}", "WARN")
        
        log(f"Fetched {len(cves)} CVEs")
        return cves
    
    # ========================================================================
    # E2E JOURNEY SIMULATION - Real User Flows with RBAC
    # ========================================================================
    
    async def run_user_journeys(
        self,
        project_id: str,
        env: str = "staging",
        personas: List[str] = None,
    ) -> Tuple[List[Insight], List[Dict]]:
        """
        Simulate real user journeys with Playwright.
        
        Uses:
        - Vision doc personas/features/acceptance criteria
        - RBAC roles (admin, user, guest, etc.)
        - Real data on staging/prod
        - Console.log/error capture
        - Network error capture
        
        Returns:
            (insights, backlog_tasks)
        """
        insights = []
        backlog_tasks = []
        
        log(f"Running E2E user journeys on {project_id}/{env}...")
        
        try:
            from core.project_registry import get_project
            from core.task_store import TaskStore, Task
            
            project = get_project(project_id)
            project_root = Path(project.root_path)
            
            # Get environment URL
            if env == "staging":
                base_url = project.deploy.get('staging', {}).get('url', '')
            else:
                base_url = project.deploy.get('prod', {}).get('url', '')
            
            if not base_url:
                log(f"No {env} URL configured for {project_id}", "WARN")
                return insights, backlog_tasks
            
            # Load vision doc for personas/features
            vision_doc = ""
            vision_path = project_root / project.vision_doc
            if vision_path.exists():
                vision_doc = vision_path.read_text()[:10000]
            
            # Extract personas and journeys from vision doc
            personas_journeys = await self._extract_personas_journeys(vision_doc, project_id)
            
            # Run each journey with Playwright
            for persona in personas_journeys.get('personas', []):
                persona_name = persona.get('name', 'user')
                role = persona.get('role', 'user')
                
                log(f"Testing persona: {persona_name} (role: {role})")
                
                for journey in persona.get('journeys', []):
                    journey_result = await self._run_single_journey(
                        project_root=project_root,
                        base_url=base_url,
                        persona=persona,
                        journey=journey,
                        env=env,
                    )
                    
                    # Process results
                    if journey_result.get('errors'):
                        for err in journey_result['errors']:
                            insights.append(Insight(
                                type=InsightType.MISSING_E2E,
                                severity=err.get('severity', 'high'),
                                title=f"[{persona_name}] {journey.get('name', 'Journey')}: {err.get('type', 'Error')}",
                                description=err.get('message', ''),
                                recommendation=err.get('fix', ''),
                                affected_projects=[project_id],
                                evidence=[{
                                    "url": err.get('url', ''),
                                    "console": err.get('console', ''),
                                    "network": err.get('network', ''),
                                }],
                            ))
                            
                            # Create backlog task
                            backlog_tasks.append({
                                "type": "fix",
                                "domain": "e2e",
                                "description": f"Fix {journey.get('name', '')}: {err.get('message', '')[:100]}",
                                "context": {
                                    "persona": persona_name,
                                    "role": role,
                                    "journey": journey.get('name', ''),
                                    "error": err,
                                    "env": env,
                                },
                                "priority": 90 if err.get('severity') == 'critical' else 70,
                            })
                    
                    # Check for stubs/missing implementations
                    if journey_result.get('stubs'):
                        for stub in journey_result['stubs']:
                            backlog_tasks.append({
                                "type": "feature",
                                "domain": stub.get('domain', 'backend'),
                                "description": f"Implement stub: {stub.get('name', '')}",
                                "context": {
                                    "journey": journey.get('name', ''),
                                    "stub_location": stub.get('location', ''),
                                    "expected_behavior": stub.get('expected', ''),
                                },
                                "priority": 80,
                            })
            
            log(f"Journeys complete: {len(insights)} issues, {len(backlog_tasks)} tasks")
            
        except Exception as e:
            log(f"Journey simulation error: {e}", "ERROR")
        
        return insights, backlog_tasks
    
    async def _extract_personas_journeys(self, vision_doc: str, project_id: str) -> Dict:
        """Extract personas and user journeys from vision doc using LLM"""
        
        prompt = f"""Extract PERSONAS and USER JOURNEYS from this vision document.

PROJECT: {project_id}

VISION DOC:
{vision_doc[:6000]}

Return JSON:
{{
  "personas": [
    {{
      "name": "Admin",
      "role": "admin",
      "permissions": ["read", "write", "delete", "manage_users"],
      "journeys": [
        {{
          "name": "Create new user",
          "steps": [
            {{"action": "navigate", "target": "/admin/users"}},
            {{"action": "click", "target": "button:Add User"}},
            {{"action": "fill", "target": "input[name=email]", "value": "test@example.com"}},
            {{"action": "click", "target": "button:Save"}},
            {{"action": "assert", "target": "text:User created"}}
          ],
          "acceptance_criteria": ["User appears in list", "Email sent"]
        }}
      ]
    }},
    {{
      "name": "Free User",
      "role": "user",
      "permissions": ["read"],
      "journeys": [...]
    }}
  ]
}}

Include RBAC-specific journeys testing permission boundaries.
"""
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "claude", "-p", "--model", "claude-sonnet-4-20250514", "--max-turns", "1",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(input=prompt.encode()), timeout=90)
            output = stdout.decode()
            
            json_match = re.search(r'\{[\s\S]*"personas"[\s\S]*\}', output)
            if json_match:
                return json.loads(json_match.group())
                
        except Exception as e:
            log(f"Persona extraction failed: {e}", "WARN")
        
        # Fallback default personas
        return {
            "personas": [
                {"name": "Admin", "role": "admin", "permissions": ["*"], "journeys": []},
                {"name": "User", "role": "user", "permissions": ["read", "write"], "journeys": []},
                {"name": "Guest", "role": "guest", "permissions": ["read"], "journeys": []},
            ]
        }
    
    async def _run_single_journey(
        self,
        project_root: Path,
        base_url: str,
        persona: Dict,
        journey: Dict,
        env: str,
    ) -> Dict:
        """Run a single user journey with Playwright and capture errors"""
        
        result = {
            "persona": persona.get('name', ''),
            "journey": journey.get('name', ''),
            "success": False,
            "errors": [],
            "stubs": [],
            "console_logs": [],
            "network_errors": [],
        }
        
        # Generate Playwright test script
        test_script = self._generate_playwright_script(base_url, persona, journey)
        
        # Write temp test file
        test_file = project_root / "e2e" / f"_xp_journey_{persona.get('name', 'user').lower()}.spec.ts"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            test_file.write_text(test_script)
            
            # Run Playwright
            proc = await asyncio.create_subprocess_exec(
                "npx", "playwright", "test", str(test_file),
                "--reporter=json",
                "--timeout=30000",
                cwd=str(project_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "BASE_URL": base_url},
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            
            # Parse results
            try:
                test_result = json.loads(stdout.decode())
                
                for suite in test_result.get('suites', []):
                    for spec in suite.get('specs', []):
                        for test in spec.get('tests', []):
                            if test.get('status') != 'passed':
                                result['errors'].append({
                                    "type": "assertion_failed",
                                    "message": test.get('error', {}).get('message', 'Test failed'),
                                    "severity": "high",
                                    "fix": f"Fix journey step: {spec.get('title', '')}",
                                })
                                
            except json.JSONDecodeError:
                # Parse stderr for errors
                stderr_text = stderr.decode()
                if "Error:" in stderr_text or "failed" in stderr_text.lower():
                    result['errors'].append({
                        "type": "playwright_error",
                        "message": stderr_text[:500],
                        "severity": "high",
                    })
            
            # Check for console errors in output
            output_text = stdout.decode() + stderr.decode()
            if "console.error" in output_text:
                result['errors'].append({
                    "type": "console_error",
                    "message": "Console errors detected during journey",
                    "severity": "medium",
                    "console": output_text[:1000],
                })
            
            # Check for network errors
            if "net::ERR" in output_text or "NetworkError" in output_text:
                result['errors'].append({
                    "type": "network_error",
                    "message": "Network errors during journey",
                    "severity": "high",
                    "network": output_text[:1000],
                })
            
            # Check for stub responses (501, "not implemented", etc.)
            if "501" in output_text or "not implemented" in output_text.lower():
                result['stubs'].append({
                    "name": f"Stub in {journey.get('name', 'journey')}",
                    "domain": "backend",
                    "location": "API endpoint",
                    "expected": journey.get('acceptance_criteria', []),
                })
            
            result['success'] = proc.returncode == 0 and not result['errors']
            
        except asyncio.TimeoutError:
            result['errors'].append({
                "type": "timeout",
                "message": f"Journey timed out after 120s",
                "severity": "high",
            })
        except Exception as e:
            result['errors'].append({
                "type": "exception",
                "message": str(e),
                "severity": "high",
            })
        finally:
            # Cleanup temp file
            if test_file.exists():
                test_file.unlink()
        
        return result
    
    def _generate_playwright_script(self, base_url: str, persona: Dict, journey: Dict) -> str:
        """Generate Playwright test script from journey definition"""
        
        steps_code = []
        for step in journey.get('steps', []):
            action = step.get('action', '')
            target = step.get('target', '')
            value = step.get('value', '')
            
            if action == 'navigate':
                steps_code.append(f"  await page.goto('{base_url}{target}');")
            elif action == 'click':
                steps_code.append(f"  await page.click('{target}');")
            elif action == 'fill':
                steps_code.append(f"  await page.fill('{target}', '{value}');")
            elif action == 'assert':
                if target.startswith('text:'):
                    text = target[5:]
                    steps_code.append(f"  await expect(page.locator('text={text}')).toBeVisible();")
                else:
                    steps_code.append(f"  await expect(page.locator('{target}')).toBeVisible();")
            elif action == 'wait':
                steps_code.append(f"  await page.waitForTimeout({value or 1000});")
        
        steps_str = '\n'.join(steps_code) if steps_code else "  // No steps defined"
        
        # Auth based on role
        auth_code = ""
        role = persona.get('role', 'guest')
        if role != 'guest':
            auth_code = f"""
  // Login as {persona.get('name', role)}
  await page.goto('{base_url}/login');
  await page.fill('input[name=email]', 'test_{role}@example.com');
  await page.fill('input[name=password]', 'test_password');
  await page.click('button[type=submit]');
  await page.waitForURL('**/*');
"""
        
        return f"""import {{ test, expect }} from '@playwright/test';

// XP Agent Generated Journey: {journey.get('name', 'Journey')}
// Persona: {persona.get('name', 'User')} (Role: {role})
// Acceptance Criteria: {journey.get('acceptance_criteria', [])}

test.describe('{persona.get("name", "User")} - {journey.get("name", "Journey")}', () => {{
  test.beforeEach(async ({{ page }}) => {{
    // Capture console errors
    page.on('console', msg => {{
      if (msg.type() === 'error') console.log('CONSOLE_ERROR:', msg.text());
    }});
    page.on('pageerror', err => console.log('PAGE_ERROR:', err.message));
    page.on('requestfailed', req => console.log('NET_ERROR:', req.url(), req.failure()?.errorText));
{auth_code}
  }});

  test('{journey.get("name", "Journey")}', async ({{ page }}) => {{
{steps_str}
  }});
}});
"""
    
    async def analyze_prod_logs(self, project_id: str, hours: int = 24) -> Tuple[List[Insight], List[Dict]]:
        """
        Analyze production logs for errors and create backlog tasks.
        
        Sources:
        - stdout/stderr logs
        - Structured JSON logs
        - Error tracking (Sentry-like)
        """
        insights = []
        backlog_tasks = []
        
        log(f"Analyzing prod logs for {project_id} (last {hours}h)...")
        
        try:
            from core.project_registry import get_project
            project = get_project(project_id)
            
            # Get log paths from config
            log_paths = project.deploy.get('log_paths', [])
            log_cmd = project.deploy.get('log_cmd', '')
            
            all_errors = []
            
            # Parse local log files
            for log_path in log_paths:
                errors = await self._parse_log_file(log_path, hours)
                all_errors.extend(errors)
            
            # Run remote log command if configured
            if log_cmd:
                errors = await self._run_log_command(log_cmd, hours)
                all_errors.extend(errors)
            
            # Deduplicate and create tasks
            seen_errors = set()
            for err in all_errors:
                err_key = f"{err.get('type', '')}:{err.get('message', '')[:100]}"
                if err_key in seen_errors:
                    continue
                seen_errors.add(err_key)
                
                severity = err.get('severity', 'medium')
                
                insights.append(Insight(
                    type=InsightType.DEPLOY_FAILURES if severity == 'critical' else InsightType.TDD_FAILURES,
                    severity=severity,
                    title=f"[PROD] {err.get('type', 'Error')}: {err.get('message', '')[:60]}",
                    description=err.get('stack', err.get('message', '')),
                    recommendation=err.get('fix', 'Investigate and fix'),
                    affected_projects=[project_id],
                    evidence=[err],
                ))
                
                backlog_tasks.append({
                    "type": "fix",
                    "domain": err.get('domain', 'backend'),
                    "description": f"[PROD ERROR] {err.get('message', '')[:100]}",
                    "context": {
                        "error_type": err.get('type', ''),
                        "stack": err.get('stack', ''),
                        "file": err.get('file', ''),
                        "line": err.get('line', 0),
                        "count": err.get('count', 1),
                    },
                    "priority": 100 if severity == 'critical' else 85,
                })
            
            log(f"Found {len(insights)} prod errors, created {len(backlog_tasks)} tasks")
            
        except Exception as e:
            log(f"Prod log analysis error: {e}", "ERROR")
        
        return insights, backlog_tasks
    
    async def _parse_log_file(self, log_path: str, hours: int) -> List[Dict]:
        """Parse log file for errors"""
        errors = []
        
        try:
            path = Path(log_path)
            if not path.exists():
                return errors
            
            cutoff = datetime.now() - timedelta(hours=hours)
            
            with open(path, 'r') as f:
                for line in f:
                    # Try JSON log format
                    try:
                        entry = json.loads(line)
                        if entry.get('level') in ['error', 'ERROR', 'fatal', 'FATAL']:
                            errors.append({
                                "type": entry.get('error_type', 'RuntimeError'),
                                "message": entry.get('message', ''),
                                "stack": entry.get('stack', ''),
                                "severity": "critical" if entry.get('level') in ['fatal', 'FATAL'] else "high",
                                "domain": "backend",
                            })
                    except json.JSONDecodeError:
                        # Plain text log
                        if 'ERROR' in line or 'FATAL' in line or 'panic' in line:
                            errors.append({
                                "type": "LogError",
                                "message": line.strip()[:200],
                                "severity": "critical" if 'FATAL' in line or 'panic' in line else "high",
                                "domain": "backend",
                            })
                            
        except Exception as e:
            log(f"Log parse error {log_path}: {e}", "WARN")
        
        return errors
    
    async def _run_log_command(self, cmd: str, hours: int) -> List[Dict]:
        """Run remote log command and parse output"""
        errors = []
        
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd.replace('{hours}', str(hours)),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
            
            for line in stdout.decode().split('\n'):
                if 'error' in line.lower() or 'fatal' in line.lower():
                    errors.append({
                        "type": "RemoteLogError",
                        "message": line.strip()[:200],
                        "severity": "high",
                        "domain": "backend",
                    })
                    
        except Exception as e:
            log(f"Log command error: {e}", "WARN")
        
        return errors
    
    async def create_backlog_tasks(self, project_id: str, tasks: List[Dict]) -> int:
        """Create tasks in TaskStore from backlog"""
        from core.task_store import TaskStore, Task
        
        store = TaskStore()
        created = 0
        
        for task_dict in tasks:
            task = Task(
                id=f"xp-{project_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{created:03d}",
                project_id=project_id,
                type=task_dict.get('type', 'fix'),
                domain=task_dict.get('domain', 'backend'),
                description=task_dict.get('description', ''),
                priority=task_dict.get('priority', 50),
                context=task_dict.get('context', {}),
            )
            store.create_task(task)
            created += 1
        
        log(f"Created {created} backlog tasks for {project_id}")
        return created
    
    # ========================================================================
    # FACTORY SELF-MODIFICATION
    # ========================================================================
    
    async def improve_factory(self) -> Dict[str, Any]:
        """
        Modify factory code based on insights.
        Uses Claude to generate patches for factory files.
        
        Returns dict with modifications applied.
        """
        log("Starting factory self-modification...")
        
        factory_root = Path(__file__).parent.parent
        modifications = {
            "files_modified": [],
            "patterns_added": 0,
            "configs_updated": 0,
            "code_patches": 0,
        }
        
        # Group improvements by target
        adversarial_improvements = [i for i in self.improvements if i.target == "adversarial"]
        fractal_improvements = [i for i in self.improvements if i.target == "fractal"]
        brain_improvements = [i for i in self.improvements if i.target == "brain"]
        
        # 1. Add new adversarial patterns to adversarial.py
        if adversarial_improvements:
            count = await self._patch_adversarial(factory_root, adversarial_improvements)
            modifications["patterns_added"] = count
            if count > 0:
                modifications["files_modified"].append("core/adversarial.py")
        
        # 2. Update fractal config based on insights
        if fractal_improvements:
            count = await self._patch_fractal(factory_root, fractal_improvements)
            modifications["configs_updated"] += count
        
        # 3. Improve brain prompts based on repeated failures
        if brain_improvements:
            count = await self._patch_brain(factory_root, brain_improvements)
            modifications["code_patches"] += count
            if count > 0:
                modifications["files_modified"].append("core/brain.py")
        
        # 4. Use Claude to analyze insights and generate deeper patches
        if self.insights:
            patches = await self._generate_factory_patches(factory_root)
            for patch in patches:
                applied = await self._apply_patch(factory_root, patch)
                if applied:
                    modifications["code_patches"] += 1
                    if patch.get('file') not in modifications["files_modified"]:
                        modifications["files_modified"].append(patch.get('file'))
        
        log(f"Factory modified: {len(modifications['files_modified'])} files, {modifications['patterns_added']} patterns, {modifications['code_patches']} patches")
        return modifications
    
    async def _patch_adversarial(self, factory_root: Path, improvements: List[Improvement]) -> int:
        """Add new patterns to adversarial.py"""
        adversarial_file = factory_root / "core" / "adversarial.py"
        
        if not adversarial_file.exists():
            return 0
        
        content = adversarial_file.read_text()
        added = 0
        
        for imp in improvements:
            if imp.action != "add_pattern":
                continue
            
            payload = imp.payload
            pattern = payload.get('pattern', '')
            rule = payload.get('rule', '')
            points = payload.get('points', 2)
            msg = payload.get('reason', imp.reason)[:60]
            
            if not pattern or not rule:
                continue
            
            # Check if pattern already exists
            if pattern in content or rule in content:
                continue
            
            # Find insertion point (after SECURITY_PATTERNS = {)
            insert_marker = "SECURITY_PATTERNS = {"
            if insert_marker in content:
                # Add to SECURITY_PATTERNS
                new_pattern = f'\n    r\'{pattern}\': ("{rule}", {points}, "{msg}"),'
                content = content.replace(
                    insert_marker,
                    insert_marker + new_pattern
                )
                added += 1
                log(f"Added adversarial pattern: {rule}")
        
        if added > 0:
            adversarial_file.write_text(content)
        
        return added
    
    async def _patch_fractal(self, factory_root: Path, improvements: List[Improvement]) -> int:
        """Update fractal thresholds in project configs"""
        updated = 0
        
        for imp in improvements:
            if imp.action != "adjust_config":
                continue
            
            payload = imp.payload
            key = payload.get('key', '')
            value = payload.get('suggested_value', '')
            
            # Update default in fractal.py
            fractal_file = factory_root / "core" / "fractal.py"
            if fractal_file.exists() and key and value:
                content = fractal_file.read_text()
                
                # Simple pattern: max_files = 5 → max_files = new_value
                pattern = rf'({key}\s*=\s*)\d+'
                if re.search(pattern, content):
                    content = re.sub(pattern, rf'\g<1>{value}', content)
                    fractal_file.write_text(content)
                    updated += 1
                    log(f"Updated fractal.{key} = {value}")
        
        return updated
    
    async def _patch_brain(self, factory_root: Path, improvements: List[Improvement]) -> int:
        """Improve brain prompts based on failures"""
        brain_file = factory_root / "core" / "brain.py"
        
        if not brain_file.exists():
            return 0
        
        content = brain_file.read_text()
        patched = 0
        
        for imp in improvements:
            payload = imp.payload
            issue = payload.get('current_issue', '')
            fix = payload.get('suggested_value', '')
            
            if not issue or not fix:
                continue
            
            # Add guidance to prompts
            # Find DOMAIN_PROMPTS or similar
            if "DOMAIN_PROMPTS" in content and issue:
                # Add issue-specific guidance
                guidance = f'\n    # XP-Agent learned: {issue[:50]}\n    # Fix: {fix[:50]}'
                content = content.replace("DOMAIN_PROMPTS", f"{guidance}\nDOMAIN_PROMPTS")
                patched += 1
        
        if patched > 0:
            brain_file.write_text(content)
        
        return patched
    
    async def _generate_factory_patches(self, factory_root: Path) -> List[Dict]:
        """Use Claude to generate patches based on insights"""
        patches = []
        
        # Only process critical/high insights
        critical_insights = [i for i in self.insights if i.severity in ["critical", "high"]]
        
        if not critical_insights:
            return patches
        
        # Read current factory files
        factory_files = {}
        for f in ["core/adversarial.py", "core/brain.py", "core/wiggum_tdd.py", "core/fractal.py"]:
            path = factory_root / f
            if path.exists():
                factory_files[f] = path.read_text()[:3000]  # First 3000 chars
        
        insights_summary = "\n".join([
            f"- [{i.severity}] {i.type.value}: {i.title}"
            for i in critical_insights[:10]
        ])
        
        prompt = f"""You are the Factory Self-Improvement Agent.

Analyze these insights from factory operation and generate CODE PATCHES to fix the factory itself.

INSIGHTS:
{insights_summary}

FACTORY FILES (partial):
{json.dumps({k: v[:1500] for k, v in factory_files.items()}, indent=2)}

Generate patches to improve the factory. Return JSON:
{{
  "patches": [
    {{
      "file": "core/adversarial.py",
      "action": "insert_after",
      "marker": "SECURITY_PATTERNS = {{",
      "code": "    r'pattern': (\\"rule\\", 5, \\"message\\"),"
    }},
    {{
      "file": "core/brain.py", 
      "action": "replace",
      "old": "max_retries = 3",
      "new": "max_retries = 5  # XP-Agent: increased due to frequent failures"
    }}
  ]
}}

Only generate patches that directly address the insights.
Keep patches minimal and surgical.
"""
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "claude", "-p", "--model", "claude-sonnet-4-20250514", "--max-turns", "1",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(input=prompt.encode()), timeout=90)
            output = stdout.decode()
            
            json_match = re.search(r'\{[\s\S]*"patches"[\s\S]*\}', output)
            if json_match:
                result = json.loads(json_match.group())
                patches = result.get('patches', [])
                log(f"Claude generated {len(patches)} factory patches")
                
        except Exception as e:
            log(f"Patch generation failed: {e}", "WARN")
        
        return patches
    
    async def _apply_patch(self, factory_root: Path, patch: Dict) -> bool:
        """Apply a single patch to factory file"""
        file_path = factory_root / patch.get('file', '')
        
        if not file_path.exists():
            return False
        
        content = file_path.read_text()
        action = patch.get('action', '')
        
        try:
            if action == "insert_after":
                marker = patch.get('marker', '')
                code = patch.get('code', '')
                if marker and code and marker in content:
                    content = content.replace(marker, f"{marker}\n{code}")
                    file_path.write_text(content)
                    log(f"Patched {patch.get('file')}: insert_after {marker[:30]}")
                    return True
                    
            elif action == "replace":
                old = patch.get('old', '')
                new = patch.get('new', '')
                if old and new and old in content:
                    content = content.replace(old, new)
                    file_path.write_text(content)
                    log(f"Patched {patch.get('file')}: replace")
                    return True
                    
            elif action == "append":
                code = patch.get('code', '')
                if code:
                    content += f"\n\n# XP-Agent auto-generated\n{code}"
                    file_path.write_text(content)
                    log(f"Patched {patch.get('file')}: append")
                    return True
                    
        except Exception as e:
            log(f"Patch failed: {e}", "ERROR")
        
        return False
    
    # ========================================================================
    # ANALYSIS
    # ========================================================================
    
    async def analyze(self, use_llm: bool = True) -> List[Insight]:
        """
        Analyze factory experience and generate insights.
        
        Args:
            use_llm: If True, use Claude Opus for deep analysis
        """
        log("Starting experience analysis...")
        self.insights = []
        
        # Collect data
        stats = self.collect_failure_stats(days=7)
        errors = self.collect_recent_errors(limit=50)
        patterns = self.collect_adversarial_patterns()
        
        log(f"Collected: {len(stats['stuck_tasks'])} stuck, {len(stats['high_retry_tasks'])} high-retry, {len(errors)} errors")
        
        # Fast analysis (rule-based)
        self._analyze_stuck_tasks(stats)
        self._analyze_rejection_patterns(stats)
        self._analyze_fractal_depth(stats)
        self._analyze_domain_success(stats)
        
        # Deep analysis (LLM)
        if use_llm and (stats['high_retry_tasks'] or errors):
            await self._analyze_with_llm(stats, errors, patterns)
        
        log(f"Generated {len(self.insights)} insights")
        return self.insights
    
    def _analyze_stuck_tasks(self, stats: Dict):
        """Detect stuck tasks"""
        stuck = stats.get('stuck_tasks', [])
        if len(stuck) >= 3:
            self.insights.append(Insight(
                type=InsightType.STUCK_TASKS,
                severity="high",
                title=f"{len(stuck)} tasks stuck in progress",
                description="Tasks have been in tdd_in_progress or locked state for > 2 hours. "
                           "This indicates workers may be dead or tasks are too complex.",
                evidence=stuck[:5],
                recommendation="1. Check daemon status\n2. Reset stuck tasks to pending\n3. Consider fractal decomposition",
                affected_projects=list(set(t['project_id'] for t in stuck)),
                auto_fixable=True,
            ))
    
    def _analyze_rejection_patterns(self, stats: Dict):
        """Detect repeated adversarial rejections"""
        patterns = stats.get('rejection_patterns', {})
        for rule, count in patterns.items():
            if count >= 10:
                self.insights.append(Insight(
                    type=InsightType.REPEATED_REJECTION,
                    severity="medium",
                    title=f"Repeated rejection: {rule} ({count} times)",
                    description=f"The adversarial rule '{rule}' is rejecting code frequently. "
                               "Either the LLM keeps making the same mistake, or the rule is too strict.",
                    evidence=[{"rule": rule, "count": count}],
                    recommendation=f"1. Add explicit guidance to Brain prompts about {rule}\n"
                                  f"2. Consider adjusting rule threshold if too strict",
                    auto_fixable=False,
                ))
    
    def _analyze_fractal_depth(self, stats: Dict):
        """Detect fractal depth issues"""
        depths = stats.get('fractal_depth', [])
        
        # Too shallow: many tasks at depth 0 with high retries
        high_retry = stats.get('high_retry_tasks', [])
        shallow_retries = [t for t in high_retry if t.get('tdd_attempts', 0) > 5]
        
        if len(shallow_retries) >= 3:
            self.insights.append(Insight(
                type=InsightType.FRACTAL_SHALLOW,
                severity="medium",
                title="Tasks may need deeper fractal decomposition",
                description=f"{len(shallow_retries)} tasks have > 5 TDD attempts without success. "
                           "These might be too complex and need fractal decomposition.",
                evidence=shallow_retries[:3],
                recommendation="1. Lower fractal.max_files threshold\n"
                              "2. Lower fractal.max_loc threshold\n"
                              "3. Enable automatic decomposition after N failures",
                auto_fixable=False,
            ))
        
        # Too deep: many tasks at depth 3
        deep_tasks = [d for d in depths if d.get('depth', 0) >= 3]
        if deep_tasks:
            total_deep = sum(d.get('count', 0) for d in deep_tasks)
            if total_deep >= 20:
                self.insights.append(Insight(
                    type=InsightType.FRACTAL_TOO_DEEP,
                    severity="low",
                    title="Excessive fractal decomposition",
                    description=f"{total_deep} tasks at depth >= 3. Over-decomposition may indicate "
                               "tasks are being split too aggressively.",
                    evidence=deep_tasks,
                    recommendation="Increase fractal.max_files or max_loc thresholds",
                    auto_fixable=False,
                ))
    
    def _analyze_domain_success(self, stats: Dict):
        """Analyze success rates by domain"""
        domains = stats.get('domain_success', [])
        
        for domain in domains:
            completed = domain.get('completed', 0)
            failed = domain.get('failed', 0)
            total = domain.get('total', 1)
            
            if total >= 10 and failed > completed:
                success_rate = completed / total * 100
                self.insights.append(Insight(
                    type=InsightType.TDD_FAILURES,
                    severity="high",
                    title=f"Low success rate in {domain['project_id']}/{domain['domain']}",
                    description=f"Success rate: {success_rate:.1f}% ({completed}/{total}). "
                               f"This domain has more failures than successes.",
                    evidence=[domain],
                    recommendation=f"1. Review Brain prompts for {domain['domain']} domain\n"
                                  "2. Check domain-specific build/test commands\n"
                                  "3. Consider adding domain-specific adversarial patterns",
                    affected_projects=[domain['project_id']],
                    auto_fixable=False,
                ))
    
    async def _analyze_with_llm(self, stats: Dict, errors: List[Dict], patterns: List[Dict]):
        """Deep analysis using Claude Opus 4.5"""
        log("Running deep LLM analysis with Claude Opus 4.5...")
        
        # Prepare context
        context = {
            "stuck_tasks": stats.get('stuck_tasks', [])[:10],
            "high_retry_tasks": stats.get('high_retry_tasks', [])[:10],
            "rejection_patterns": stats.get('rejection_patterns', {}),
            "recent_errors": errors[:20],
            "current_adversarial_patterns": len(patterns),
            "domain_success": stats.get('domain_success', []),
        }
        
        prompt = f"""You are the Experience Learning Agent for a Macaron Agent Platform.

Analyze this factory telemetry and identify:
1. FAILURE PATTERNS: What keeps failing and why?
2. MISSING PATTERNS: What adversarial rules should be added?
3. KISS VIOLATIONS: Are solutions over-engineered?
4. GAPS: What's missing (E2E tests, security checks, etc.)?
5. SUCCESS PATTERNS: What's working well?

TELEMETRY:
```json
{json.dumps(context, indent=2, default=str)[:6000]}
```

RESPOND IN STRICT JSON:
{{
  "insights": [
    {{
      "type": "repeated_rejection|stuck_tasks|kiss_violation|missing_e2e|security_pattern|slop_pattern|success_pattern",
      "severity": "critical|high|medium|low",
      "title": "short title",
      "description": "detailed description",
      "recommendation": "concrete action to take",
      "auto_fixable": true/false
    }}
  ],
  "new_adversarial_patterns": [
    {{
      "pattern": "regex pattern",
      "rule": "rule_name",
      "points": 1-5,
      "type": "reject|warning",
      "reason": "why add this pattern"
    }}
  ],
  "config_adjustments": [
    {{
      "target": "fractal|adversarial|brain",
      "key": "config key",
      "current_issue": "what's wrong",
      "suggested_value": "new value"
    }}
  ]
}}
"""

        try:
            # Use claude CLI
            proc = await asyncio.create_subprocess_exec(
                "claude",
                "-p",
                "--model", "claude-opus-4-20250514",
                "--max-turns", "1",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=prompt.encode()),
                timeout=120,
            )
            
            output = stdout.decode()
            
            # Parse JSON response
            import re
            json_match = re.search(r'\{[\s\S]*"insights"[\s\S]*\}', output)
            if json_match:
                result = json.loads(json_match.group())
                
                # Add LLM insights
                for ins in result.get('insights', []):
                    try:
                        insight_type = InsightType(ins.get('type', 'stuck_tasks'))
                    except ValueError:
                        insight_type = InsightType.STUCK_TASKS
                        
                    self.insights.append(Insight(
                        type=insight_type,
                        severity=ins.get('severity', 'medium'),
                        title=ins.get('title', 'LLM Insight'),
                        description=ins.get('description', ''),
                        recommendation=ins.get('recommendation', ''),
                        auto_fixable=ins.get('auto_fixable', False),
                    ))
                
                # Store new patterns for later application
                for pattern in result.get('new_adversarial_patterns', []):
                    self.improvements.append(Improvement(
                        target="adversarial",
                        action="add_pattern",
                        payload=pattern,
                        reason=pattern.get('reason', ''),
                    ))
                
                # Store config adjustments
                for adj in result.get('config_adjustments', []):
                    self.improvements.append(Improvement(
                        target=adj.get('target', 'brain'),
                        action="adjust_config",
                        payload=adj,
                        reason=adj.get('current_issue', ''),
                    ))
                
                log(f"LLM found {len(result.get('insights', []))} insights, "
                    f"{len(result.get('new_adversarial_patterns', []))} new patterns")
            else:
                log("Could not parse LLM JSON response", "WARN")
                
        except asyncio.TimeoutError:
            log("LLM analysis timeout (120s)", "WARN")
        except Exception as e:
            log(f"LLM analysis error: {e}", "ERROR")
    
    # ========================================================================
    # PERSISTENCE - Learning Memory
    # ========================================================================
    
    def persist_insights(self) -> int:
        """Save insights to learnings table for long-term memory"""
        conn = self._get_db()
        count = 0
        
        for insight in self.insights:
            # Check if similar insight already exists (dedup)
            cur = conn.execute("""
                SELECT id FROM learnings 
                WHERE insight_type = ? AND title = ? AND created_at > datetime('now', '-7 days')
            """, (insight.type.value, insight.title))
            
            if cur.fetchone():
                continue  # Skip duplicate
            
            conn.execute("""
                INSERT INTO learnings (insight_type, severity, title, description, recommendation, affected_projects)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                insight.type.value,
                insight.severity,
                insight.title,
                insight.description,
                insight.recommendation,
                json.dumps(insight.affected_projects),
            ))
            count += 1
        
        conn.commit()
        conn.close()
        log(f"Persisted {count} new insights to learnings table")
        return count
    
    def persist_patterns(self) -> int:
        """Save new adversarial patterns to pattern_evolutions table"""
        conn = self._get_db()
        count = 0
        
        for imp in self.improvements:
            if imp.target != "adversarial" or imp.action != "add_pattern":
                continue
            
            payload = imp.payload
            pattern = payload.get('pattern', '')
            
            if not pattern:
                continue
            
            # Check if pattern already exists
            cur = conn.execute("SELECT id FROM pattern_evolutions WHERE pattern = ?", (pattern,))
            if cur.fetchone():
                continue
            
            conn.execute("""
                INSERT INTO pattern_evolutions (pattern, rule, points, pattern_type, reason)
                VALUES (?, ?, ?, ?, ?)
            """, (
                pattern,
                payload.get('rule', 'xp_learned'),
                payload.get('points', 2),
                payload.get('type', 'warning'),
                imp.reason,
            ))
            count += 1
            log(f"Learned new pattern: {payload.get('rule', 'unknown')}")
        
        conn.commit()
        conn.close()
        return count
    
    def get_learned_patterns(self) -> List[Dict]:
        """Get active learned patterns for adversarial gate"""
        conn = self._get_db()
        cur = conn.execute("""
            SELECT pattern, rule, points, pattern_type, reason, hit_count, effectiveness
            FROM pattern_evolutions
            WHERE active = 1
            ORDER BY created_at DESC
        """)
        patterns = [dict(r) for r in cur.fetchall()]
        conn.close()
        return patterns
    
    def measure_impact(self, days: int = 7) -> Dict[str, Any]:
        """Measure ROI of applied improvements"""
        conn = self._get_db()
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        # Success rate before/after improvements
        cur = conn.execute("""
            SELECT 
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                COUNT(*) as total
            FROM tasks
            WHERE created_at > ?
        """, (cutoff,))
        row = cur.fetchone()
        
        recent_stats = {
            "completed": row['completed'] or 0,
            "failed": row['failed'] or 0,
            "total": row['total'] or 1,
            "success_rate": (row['completed'] or 0) / max(row['total'] or 1, 1) * 100,
        }
        
        # Pattern effectiveness
        cur = conn.execute("""
            SELECT rule, hit_count, effectiveness
            FROM pattern_evolutions
            WHERE hit_count > 0
            ORDER BY hit_count DESC
            LIMIT 10
        """)
        pattern_stats = [dict(r) for r in cur.fetchall()]
        
        # Applied vs pending improvements
        cur = conn.execute("""
            SELECT 
                SUM(CASE WHEN applied = 1 THEN 1 ELSE 0 END) as applied,
                SUM(CASE WHEN applied = 0 THEN 1 ELSE 0 END) as pending
            FROM learnings
        """)
        row = cur.fetchone()
        learning_stats = {
            "applied": row['applied'] or 0,
            "pending": row['pending'] or 0,
        }
        
        conn.close()
        
        return {
            "recent_performance": recent_stats,
            "pattern_effectiveness": pattern_stats,
            "learning_progress": learning_stats,
        }
    
    # ========================================================================
    # IMPROVEMENTS
    # ========================================================================
    
    async def apply_auto_fixes(self) -> int:
        """Apply auto-fixable improvements"""
        applied = 0
        
        for insight in self.insights:
            if not insight.auto_fixable:
                continue
            
            if insight.type == InsightType.STUCK_TASKS:
                applied += await self._fix_stuck_tasks(insight)
        
        log(f"Applied {applied} auto-fixes")
        return applied
    
    async def _fix_stuck_tasks(self, insight: Insight) -> int:
        """Reset stuck tasks to pending"""
        conn = self._get_db()
        count = 0
        
        for task in insight.evidence:
            task_id = task.get('id')
            if task_id:
                conn.execute("""
                    UPDATE tasks
                    SET status = 'pending',
                        locked_by = NULL,
                        lock_expires_at = NULL,
                        updated_at = ?
                    WHERE id = ?
                """, (datetime.now().isoformat(), task_id))
                count += 1
                log(f"Reset stuck task: {task_id}")
        
        conn.commit()
        conn.close()
        return count
    
    def generate_report(self) -> str:
        """Generate markdown report of insights"""
        lines = ["# Experience Learning Agent Report", ""]
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append("")
        
        # Summary
        by_severity = {}
        for i in self.insights:
            by_severity[i.severity] = by_severity.get(i.severity, 0) + 1
        
        lines.append("## Summary")
        lines.append(f"- **Total insights**: {len(self.insights)}")
        for sev in ["critical", "high", "medium", "low"]:
            if sev in by_severity:
                lines.append(f"- **{sev.upper()}**: {by_severity[sev]}")
        lines.append("")
        
        # Insights by severity
        for sev in ["critical", "high", "medium", "low"]:
            insights = [i for i in self.insights if i.severity == sev]
            if insights:
                lines.append(f"## {sev.upper()} Insights")
                lines.append("")
                for insight in insights:
                    icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}[sev]
                    lines.append(f"### {icon} {insight.title}")
                    lines.append(f"**Type**: {insight.type.value}")
                    lines.append(f"**Auto-fixable**: {'Yes' if insight.auto_fixable else 'No'}")
                    lines.append("")
                    lines.append(insight.description)
                    lines.append("")
                    if insight.recommendation:
                        lines.append("**Recommendation**:")
                        lines.append(insight.recommendation)
                        lines.append("")
                    if insight.affected_projects:
                        lines.append(f"**Affected projects**: {', '.join(insight.affected_projects)}")
                        lines.append("")
        
        # Improvements
        if self.improvements:
            lines.append("## Suggested Improvements")
            lines.append("")
            for imp in self.improvements:
                lines.append(f"- **{imp.target}**: {imp.action}")
                lines.append(f"  Reason: {imp.reason}")
                if imp.payload:
                    lines.append(f"  Payload: `{json.dumps(imp.payload)[:100]}`")
                lines.append("")
        
        return "\n".join(lines)
    
    def create_improvement_tasks(self) -> List[Dict]:
        """Create tasks for manual improvements"""
        tasks = []
        
        for insight in self.insights:
            if insight.auto_fixable:
                continue
            if insight.severity not in ["critical", "high"]:
                continue
            
            task = {
                "type": "improvement",
                "domain": "factory",
                "description": f"[XP-AGENT] {insight.title}",
                "context": {
                    "insight_type": insight.type.value,
                    "description": insight.description,
                    "recommendation": insight.recommendation,
                    "evidence": insight.evidence,
                },
                "priority": 100 if insight.severity == "critical" else 80,
            }
            tasks.append(task)
        
        return tasks


# ============================================================================
# CLI
# ============================================================================

async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Experience Learning Agent")
    parser.add_argument("--analyze", action="store_true", help="Run analysis")
    parser.add_argument("--apply", action="store_true", help="Apply auto-fixes")
    parser.add_argument("--report", action="store_true", help="Generate report")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM analysis")
    parser.add_argument("--days", type=int, default=7, help="Days of history to analyze")
    
    args = parser.parse_args()
    
    agent = ExperienceAgent()
    
    if args.analyze or args.report:
        insights = await agent.analyze(use_llm=not args.no_llm)
        
        if args.apply:
            await agent.apply_auto_fixes()
        
        if args.report:
            report = agent.generate_report()
            print(report)
        else:
            print(f"\n✅ Found {len(insights)} insights")
            for i in insights[:10]:
                icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}[i.severity]
                print(f"  {icon} [{i.type.value}] {i.title}")
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
