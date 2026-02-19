#!/usr/bin/env python3
"""
Wiggum Infra - Infrastructure Verification & Correction Agent
==============================================================
Based on:
- MIT CSAIL arXiv:2512.24601 "Recursive Language Models"
- arXiv:2309.11495 "Chain-of-Verification" (CoVe)

Verifies infrastructure is working BEFORE E2E tests run.
Uses CoVe to reduce hallucinations in diagnostics.

Flow:
1. DRAFT: Check infrastructure status
2. VERIFY: Generate verification questions, answer independently
3. CORRECT: Fix issues found
4. CONFIRM: Re-verify after fixes

Tools:
- infra_check_site: HTTP status check
- infra_check_docker: Container status
- infra_check_nginx: Config validation
- infra_check_db: Database connectivity
- infra_ssh: Remote command execution
- infra_restart: Service restart
- infra_deploy_config: Deploy configuration files

Usage:
    from core.wiggum_infra import InfraAgent

    agent = InfraAgent("veligo")
    issues = await agent.verify_all()
    if issues:
        await agent.fix_issues(issues)
"""

import asyncio
import subprocess
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.project_registry import get_project, ProjectConfig
from core.task_store import TaskStore
from core.llm_client import run_opencode


def log(msg: str, level: str = "INFO"):
    """Log with timestamp"""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [INFRA] [{level}] {msg}", flush=True)


class InfraStatus(Enum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class InfraCheck:
    """Result of an infrastructure check"""
    name: str
    status: InfraStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    fix_command: Optional[str] = None


@dataclass
class InfraIssue:
    """An infrastructure issue that needs fixing"""
    check: InfraCheck
    severity: str  # critical, high, medium, low
    auto_fixable: bool
    fix_steps: List[str] = field(default_factory=list)


class InfraAgent:
    """
    Infrastructure verification and correction agent.

    Uses Chain-of-Verification (CoVe) pattern:
    1. Draft check results
    2. Generate verification questions
    3. Answer independently (no bias)
    4. Produce verified assessment
    """

    def __init__(self, project_name: str):
        self.project = get_project(project_name)
        self.task_store = TaskStore()
        self.checks: List[InfraCheck] = []
        self.issues: List[InfraIssue] = []

    # =========================================================================
    # DIRECT VERIFICATION TOOLS (No LLM - deterministic)
    # =========================================================================

    async def check_site(self, url: str, expected_status: int = 200) -> InfraCheck:
        """Check if a site responds with expected HTTP status"""
        log(f"Checking site: {url}")

        try:
            proc = await asyncio.create_subprocess_exec(
                "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                "--max-time", "10", url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            status_code = int(stdout.decode().strip())

            if status_code == expected_status:
                return InfraCheck(
                    name=f"site_{url}",
                    status=InfraStatus.OK,
                    message=f"Site {url} responds with {status_code}",
                    details={"url": url, "status_code": status_code}
                )
            elif status_code == 403:
                # 403 often means nginx serving static files but no index.html
                # Common fix: proxy to Node.js SSR server instead of try_files
                return InfraCheck(
                    name=f"site_{url}",
                    status=InfraStatus.ERROR,
                    message=f"Site {url} returns 403 Forbidden - likely nginx static vs SSR mismatch",
                    details={"url": url, "status_code": status_code},
                    fix_command=self._generate_nginx_proxy_fix(url)
                )
            elif status_code == 502 or status_code == 503:
                return InfraCheck(
                    name=f"site_{url}",
                    status=InfraStatus.ERROR,
                    message=f"Site {url} returns {status_code} - backend down",
                    details={"url": url, "status_code": status_code},
                    fix_command="Restart backend service"
                )
            else:
                return InfraCheck(
                    name=f"site_{url}",
                    status=InfraStatus.WARNING,
                    message=f"Site {url} returns {status_code} (expected {expected_status})",
                    details={"url": url, "status_code": status_code}
                )

        except Exception as e:
            return InfraCheck(
                name=f"site_{url}",
                status=InfraStatus.ERROR,
                message=f"Cannot reach {url}: {str(e)}",
                details={"url": url, "error": str(e)}
            )

    async def check_docker(self, service: str, host: str = None) -> InfraCheck:
        """Check if a Docker container is running"""
        log(f"Checking Docker service: {service}")

        cmd = ["docker", "ps", "--filter", f"name={service}", "--format", "{{.Status}}"]
        if host:
            cmd = ["ssh", host] + cmd

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            status_output = stdout.decode().strip()

            if "Up" in status_output:
                return InfraCheck(
                    name=f"docker_{service}",
                    status=InfraStatus.OK,
                    message=f"Container {service} is running",
                    details={"service": service, "status": status_output}
                )
            elif status_output:
                return InfraCheck(
                    name=f"docker_{service}",
                    status=InfraStatus.WARNING,
                    message=f"Container {service} status: {status_output}",
                    details={"service": service, "status": status_output},
                    fix_command=f"docker restart {service}"
                )
            else:
                return InfraCheck(
                    name=f"docker_{service}",
                    status=InfraStatus.ERROR,
                    message=f"Container {service} not found or not running",
                    details={"service": service},
                    fix_command=f"docker-compose up -d {service}"
                )

        except Exception as e:
            return InfraCheck(
                name=f"docker_{service}",
                status=InfraStatus.ERROR,
                message=f"Docker check failed: {str(e)}",
                details={"service": service, "error": str(e)}
            )

    async def check_nginx(self, domain: str, host: str = None) -> InfraCheck:
        """Check nginx configuration for a domain"""
        log(f"Checking nginx config for: {domain}")

        # Check if config exists and is valid
        config_path = f"/etc/nginx/sites-enabled/{domain}"
        cmd = ["test", "-f", config_path, "&&", "nginx", "-t"]

        if host:
            cmd = ["ssh", host, " ".join(cmd)]
            shell = True
        else:
            cmd = " ".join(cmd)
            shell = True

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd if isinstance(cmd, str) else " ".join(cmd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            output = stderr.decode() + stdout.decode()

            if proc.returncode == 0 and "successful" in output.lower():
                return InfraCheck(
                    name=f"nginx_{domain}",
                    status=InfraStatus.OK,
                    message=f"Nginx config for {domain} is valid",
                    details={"domain": domain, "config_path": config_path}
                )
            else:
                return InfraCheck(
                    name=f"nginx_{domain}",
                    status=InfraStatus.ERROR,
                    message=f"Nginx config issue: {output[:200]}",
                    details={"domain": domain, "output": output},
                    fix_command="Check nginx config syntax and paths"
                )

        except Exception as e:
            return InfraCheck(
                name=f"nginx_{domain}",
                status=InfraStatus.UNKNOWN,
                message=f"Cannot check nginx: {str(e)}",
                details={"domain": domain, "error": str(e)}
            )

    async def check_db(self, connection_string: str = None) -> InfraCheck:
        """Check database connectivity"""
        log("Checking database connectivity")

        # Use project's DB connection or default
        db_cmd = "pg_isready" if not connection_string else f"pg_isready -d {connection_string}"

        try:
            proc = await asyncio.create_subprocess_shell(
                db_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                return InfraCheck(
                    name="database",
                    status=InfraStatus.OK,
                    message="Database is accepting connections",
                    details={"output": stdout.decode()}
                )
            else:
                return InfraCheck(
                    name="database",
                    status=InfraStatus.ERROR,
                    message="Database not responding",
                    details={"error": stderr.decode()},
                    fix_command="systemctl restart postgresql"
                )

        except Exception as e:
            return InfraCheck(
                name="database",
                status=InfraStatus.ERROR,
                message=f"Database check failed: {str(e)}",
                details={"error": str(e)}
            )

    def _generate_nginx_proxy_fix(self, url: str) -> str:
        """
        Generate fix command for 403 errors (nginx static vs SSR mismatch).

        Common pattern: nginx configured for static files (try_files)
        but SvelteKit is in SSR mode (needs proxy to Node.js).
        """
        # Extract domain from URL
        from urllib.parse import urlparse
        domain = urlparse(url).netloc

        # The fix is to change nginx from static to proxy
        return f"""ssh {self.project.name}-vm 'sudo sed -i "s|try_files \\$uri \\$uri/ /index.html;|proxy_pass http://localhost:3000;\\n        proxy_http_version 1.1;\\n        proxy_set_header Host \\$host;\\n        proxy_set_header X-Real-IP \\$remote_addr;|g" /etc/nginx/sites-available/{domain} && sudo nginx -t && sudo systemctl reload nginx'"""

    async def ssh_command(self, host: str, command: str, timeout: int = 30) -> Tuple[int, str, str]:
        """Execute command on remote host via SSH"""
        log(f"SSH [{host}]: {command}")

        try:
            proc = await asyncio.create_subprocess_exec(
                "ssh", "-o", "ConnectTimeout=10", host, command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout
            )
            return proc.returncode, stdout.decode(), stderr.decode()

        except asyncio.TimeoutError:
            return -1, "", f"SSH command timed out ({timeout}s)"
        except Exception as e:
            return -1, "", str(e)

    # =========================================================================
    # CHAIN-OF-VERIFICATION (CoVe) DIAGNOSIS
    # =========================================================================

    async def cove_diagnose(self, checks: List[InfraCheck]) -> List[InfraIssue]:
        """
        Apply Chain-of-Verification to diagnose infrastructure issues.

        1. DRAFT: Initial assessment from checks
        2. PLAN VERIFICATION: Generate questions to verify each issue
        3. ANSWER INDEPENDENTLY: Answer without bias from draft
        4. VERIFIED RESPONSE: Produce final diagnosis
        """
        failed_checks = [c for c in checks if c.status in (InfraStatus.ERROR, InfraStatus.WARNING)]

        if not failed_checks:
            log("All checks passed, no CoVe diagnosis needed")
            return []

        log(f"Running CoVe diagnosis on {len(failed_checks)} failed checks")

        # STAGE 1: Draft initial assessment
        draft_prompt = f"""You are an Infrastructure Diagnostic Agent.

FAILED CHECKS:
{json.dumps([{"name": c.name, "status": c.status.value, "message": c.message, "details": c.details} for c in failed_checks], indent=2)}

PROJECT: {self.project.name}
ROOT: {self.project.root_path}

Provide an initial assessment of what's wrong and why.
Be specific about root causes.
"""

        _, draft_response = await run_opencode(
            draft_prompt,
            model="minimax/MiniMax-M2.5",
            cwd=str(self.project.root_path),
            timeout=60,
            project=self.project.name,
        )

        # STAGE 2: Plan verification questions
        verify_prompt = f"""Based on this infrastructure assessment:

{draft_response[:2000]}

Generate 3-5 VERIFICATION QUESTIONS to check if the assessment is correct.
Questions should be answerable by running commands or checking configs.

Format as JSON array:
[
  {{"question": "Is nginx actually running?", "verify_cmd": "systemctl status nginx"}},
  ...
]
"""

        _, verify_response = await run_opencode(
            verify_prompt,
            model="minimax/MiniMax-M2.5",
            cwd=str(self.project.root_path),
            timeout=60,
            project=self.project.name,
        )

        # Extract verification questions
        questions = []
        try:
            json_match = re.search(r'\[[\s\S]*?\]', verify_response)
            if json_match:
                questions = json.loads(json_match.group())
        except:
            pass

        # STAGE 3: Answer independently (run actual commands)
        verification_results = []
        for q in questions[:5]:  # Limit to 5
            cmd = q.get("verify_cmd", "")
            if cmd:
                try:
                    proc = await asyncio.create_subprocess_shell(
                        cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
                    verification_results.append({
                        "question": q.get("question"),
                        "command": cmd,
                        "output": (stdout.decode() + stderr.decode())[:500],
                        "exit_code": proc.returncode
                    })
                except Exception as e:
                    verification_results.append({
                        "question": q.get("question"),
                        "command": cmd,
                        "error": str(e)
                    })

        # STAGE 4: Generate verified final response
        final_prompt = f"""You are an Infrastructure Diagnostic Agent using Chain-of-Verification.

ORIGINAL CHECKS FAILED:
{json.dumps([{"name": c.name, "message": c.message} for c in failed_checks], indent=2)}

INITIAL ASSESSMENT:
{draft_response[:1000]}

VERIFICATION RESULTS (actual command outputs):
{json.dumps(verification_results, indent=2)}

Based on the VERIFICATION RESULTS (not the initial assessment), provide:
1. CONFIRMED issues (verified by commands)
2. FALSE POSITIVES (initial assessment was wrong)
3. For each confirmed issue: severity (critical/high/medium/low), auto_fixable (true/false), fix_steps

Format as JSON:
{{
  "confirmed_issues": [
    {{
      "name": "issue_name",
      "description": "what's wrong",
      "severity": "critical|high|medium|low",
      "auto_fixable": true|false,
      "fix_steps": ["step1", "step2"]
    }}
  ],
  "false_positives": ["issue that wasn't actually broken"]
}}
"""

        _, final_response = await run_opencode(
            final_prompt,
            model="minimax/MiniMax-M2.5",
            cwd=str(self.project.root_path),
            timeout=60,
            project=self.project.name,
        )

        # Parse final diagnosis
        issues = []
        try:
            json_match = re.search(r'\{[\s\S]*\}', final_response)
            if json_match:
                diagnosis = json.loads(json_match.group())
                for issue_data in diagnosis.get("confirmed_issues", []):
                    # Find matching check
                    matching_check = next(
                        (c for c in failed_checks if issue_data.get("name", "") in c.name),
                        failed_checks[0] if failed_checks else None
                    )
                    if matching_check:
                        issues.append(InfraIssue(
                            check=matching_check,
                            severity=issue_data.get("severity", "medium"),
                            auto_fixable=issue_data.get("auto_fixable", False),
                            fix_steps=issue_data.get("fix_steps", [])
                        ))
        except Exception as e:
            log(f"Failed to parse CoVe diagnosis: {e}", "WARN")
            # Fallback: create issues from failed checks
            for check in failed_checks:
                issues.append(InfraIssue(
                    check=check,
                    severity="high" if check.status == InfraStatus.ERROR else "medium",
                    auto_fixable=bool(check.fix_command),
                    fix_steps=[check.fix_command] if check.fix_command else []
                ))

        return issues

    # =========================================================================
    # VERIFICATION & FIX WORKFLOW
    # =========================================================================

    async def verify_all(self) -> List[InfraIssue]:
        """
        Run all infrastructure checks for the project.

        Returns list of issues found (after CoVe verification).
        """
        log(f"Starting infrastructure verification for {self.project.name}")

        checks = []

        # Check all configured tenant URLs
        tenants = getattr(self.project, 'tenants', []) or []
        for tenant in tenants:
            staging_url = tenant.get("staging_url")
            prod_url = tenant.get("prod_url")

            if staging_url:
                checks.append(await self.check_site(staging_url))
            if prod_url:
                checks.append(await self.check_site(prod_url))

        # Check database (skip if project uses remote DB)
        # Config: infra.skip_db_check: true
        raw_config = getattr(self.project, 'raw_config', {}) or {}
        infra_config = raw_config.get('infra', {}) or {}
        if not infra_config.get('skip_db_check', False):
            checks.append(await self.check_db())
        else:
            log("Skipping local DB check (remote DB configured)")

        # Store checks
        self.checks = checks

        # Summarize
        ok_count = len([c for c in checks if c.status == InfraStatus.OK])
        error_count = len([c for c in checks if c.status == InfraStatus.ERROR])
        warn_count = len([c for c in checks if c.status == InfraStatus.WARNING])

        log(f"Check results: {ok_count} OK, {warn_count} WARNING, {error_count} ERROR")

        # Run CoVe diagnosis on failures
        if error_count > 0 or warn_count > 0:
            self.issues = await self.cove_diagnose(checks)
            log(f"CoVe diagnosed {len(self.issues)} confirmed issues")

        return self.issues

    async def fix_nginx_403(self, host: str, domain: str) -> bool:
        """
        Fix 403 Forbidden by converting nginx from static to proxy mode.

        Root cause: SvelteKit SSR needs proxy_pass, not try_files.
        This is the #1 cause of 403 on SvelteKit deployments.
        """
        log(f"Attempting nginx 403 fix for {domain} on {host}")

        # Step 1: Check if Node.js is running on port 3000
        rc, stdout, stderr = await self.ssh_command(host, "curl -sI localhost:3000 | head -1")
        if "200" not in stdout:
            log(f"Node.js not responding on port 3000, cannot fix nginx", "WARN")
            return False

        # Step 2: Backup current config
        backup_cmd = f"sudo cp /etc/nginx/sites-available/{domain} /etc/nginx/sites-available/{domain}.bak.$(date +%Y%m%d%H%M)"
        await self.ssh_command(host, backup_cmd)

        # Step 3: Replace try_files with proxy_pass
        fix_cmd = f'''sudo sed -i 's|try_files \\$uri \\$uri/ /index.html;|proxy_pass http://localhost:3000;\\n        proxy_http_version 1.1;\\n        proxy_set_header Upgrade \\$http_upgrade;\\n        proxy_set_header Connection "upgrade";\\n        proxy_set_header Host \\$host;\\n        proxy_set_header X-Real-IP \\$remote_addr;\\n        proxy_set_header X-Forwarded-For \\$proxy_add_x_forwarded_for;\\n        proxy_set_header X-Forwarded-Proto \\$scheme;|g' /etc/nginx/sites-available/{domain}'''
        rc, stdout, stderr = await self.ssh_command(host, fix_cmd)

        # Step 4: Test and reload nginx
        rc, stdout, stderr = await self.ssh_command(host, "sudo nginx -t && sudo systemctl reload nginx")
        if rc == 0:
            log(f"✅ Nginx fix applied for {domain}")
            return True
        else:
            log(f"❌ Nginx fix failed: {stderr}", "ERROR")
            # Rollback
            await self.ssh_command(host, f"sudo cp /etc/nginx/sites-available/{domain}.bak.* /etc/nginx/sites-available/{domain} && sudo systemctl reload nginx")
            return False

    async def fix_issues(self, issues: List[InfraIssue] = None) -> Dict[str, Any]:
        """
        Attempt to fix infrastructure issues.

        Returns summary of fixes attempted and results.
        """
        issues = issues or self.issues

        if not issues:
            log("No issues to fix")
            return {"fixed": 0, "failed": 0, "skipped": 0}

        results = {"fixed": 0, "failed": 0, "skipped": 0, "details": []}

        for issue in issues:
            if not issue.auto_fixable:
                log(f"Skipping non-auto-fixable issue: {issue.check.name}")
                results["skipped"] += 1
                results["details"].append({
                    "issue": issue.check.name,
                    "status": "skipped",
                    "reason": "Not auto-fixable"
                })
                continue

            log(f"Attempting to fix: {issue.check.name}")

            # Special case: 403 Forbidden on sites (nginx static vs SSR)
            if "403" in issue.check.message and issue.check.name.startswith("site_"):
                from urllib.parse import urlparse
                url = issue.check.details.get("url", "")
                domain = urlparse(url).netloc
                # Get deploy host from project config or default
                host = f"{self.project.name}-vm"  # Convention: {project}-vm

                fix_success = await self.fix_nginx_403(host, domain)
                if fix_success:
                    results["fixed"] += 1
                    results["details"].append({
                        "issue": issue.check.name,
                        "status": "fixed",
                        "method": "fix_nginx_403"
                    })
                else:
                    results["failed"] += 1
                    results["details"].append({
                        "issue": issue.check.name,
                        "status": "failed",
                        "method": "fix_nginx_403"
                    })
                continue

            fix_success = True
            for step in issue.fix_steps:
                try:
                    proc = await asyncio.create_subprocess_shell(
                        step,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)

                    if proc.returncode != 0:
                        log(f"Fix step failed: {step}", "WARN")
                        fix_success = False
                        break

                except Exception as e:
                    log(f"Fix step error: {e}", "ERROR")
                    fix_success = False
                    break

            if fix_success:
                results["fixed"] += 1
                results["details"].append({
                    "issue": issue.check.name,
                    "status": "fixed",
                    "steps": issue.fix_steps
                })
            else:
                results["failed"] += 1
                results["details"].append({
                    "issue": issue.check.name,
                    "status": "failed"
                })

        log(f"Fix results: {results['fixed']} fixed, {results['failed']} failed, {results['skipped']} skipped")
        return results

    async def create_feedback_tasks(self, issues: List[InfraIssue] = None) -> List[str]:
        """
        Create feedback tasks for issues that couldn't be auto-fixed.

        Returns list of created task IDs.
        """
        issues = issues or self.issues
        task_ids = []

        for issue in issues:
            if issue.auto_fixable:
                continue  # Skip auto-fixable, they should be fixed directly

            task_id = self.task_store.create_task(
                project_id=self.project.name,
                task_type="fix",
                domain="infra",
                description=f"[INFRA] {issue.check.message}",
                files=[],
                severity=issue.severity,
                context={
                    "check_name": issue.check.name,
                    "check_details": issue.check.details,
                    "fix_steps": issue.fix_steps,
                    "source": "wiggum_infra"
                }
            )
            task_ids.append(task_id)
            log(f"Created feedback task: {task_id}")

        return task_ids


# =============================================================================
# CLI
# =============================================================================

async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Infrastructure Verification Agent")
    parser.add_argument("project", help="Project name")
    parser.add_argument("--fix", action="store_true", help="Attempt to fix issues")
    parser.add_argument("--create-tasks", action="store_true", help="Create feedback tasks for unfixable issues")

    args = parser.parse_args()

    agent = InfraAgent(args.project)
    issues = await agent.verify_all()

    if issues:
        print(f"\n{'='*60}")
        print(f"INFRASTRUCTURE ISSUES FOUND: {len(issues)}")
        print(f"{'='*60}\n")

        for issue in issues:
            print(f"  [{issue.severity.upper()}] {issue.check.name}")
            print(f"    Message: {issue.check.message}")
            print(f"    Auto-fixable: {issue.auto_fixable}")
            if issue.fix_steps:
                print(f"    Fix steps: {issue.fix_steps}")
            print()

        if args.fix:
            results = await agent.fix_issues()
            print(f"\nFix results: {results}")

        if args.create_tasks:
            task_ids = await agent.create_feedback_tasks()
            print(f"\nCreated {len(task_ids)} feedback tasks")
    else:
        print("\n✅ All infrastructure checks passed!")


if __name__ == "__main__":
    asyncio.run(main())
