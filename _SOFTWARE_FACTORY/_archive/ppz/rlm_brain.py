#!/usr/bin/env python3 -u
"""
LRM Brain - LEAN Requirements Manager (REAL Autonomous Analyzer)
================================================================

Le VRAI cerveau du système RLM qui:
1. SCANNE récursivement TOUT le projet avec sub-agents
2. ANALYSE chaque domaine en profondeur (Rust, TypeScript, PHP, Proto, SQL)
3. IDENTIFIE les problèmes, dette technique, opportunités
4. PRIORISE avec WSJF (Weighted Shortest Job First)
5. CRÉE des tâches actionnables dans le backlog

Architecture:
- Brain principal orchestre les sub-agents
- Sub-agents spécialisés par domaine (rust, typescript, php, proto, sql, security)
- Sub-sub-agents pour analyse approfondie si nécessaire

Usage:
    python3 rlm_brain.py              # Run full analysis
    python3 rlm_brain.py --quick      # Quick scan only
    python3 rlm_brain.py --domain X   # Analyze specific domain
"""

import asyncio
import json
import subprocess
import re
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
import hashlib

# Setup
RLM_DIR = Path(__file__).parent
POPINZ_ROOT = Path("/Users/sylvain/_POPINZ/popinz-dev")
RUST_DIR = POPINZ_ROOT / "popinz-v2-rust"

# Files
BACKLOG_FILE = RLM_DIR / "backlog_tasks.json"
DEPLOY_BACKLOG = RLM_DIR / "deploy_backlog.json"
ANALYSIS_CACHE = RLM_DIR / "analysis_cache.json"

# Project structure
PROJECT_DOMAINS = {
    "rust": {
        "paths": ["popinz-v2-rust"],
        "extensions": [".rs"],
        "build_cmd": ["cargo", "check", "--workspace"],
        "test_cmd": ["cargo", "test", "--workspace", "--no-run"],
    },
    "typescript": {
        "paths": ["popinz-saas", "popinz-entities", "popinz-tasks"],
        "extensions": [".ts", ".tsx"],
        "build_cmd": ["npm", "run", "build"],
        "test_cmd": ["npm", "run", "test"],
    },
    "php": {
        "paths": ["popinz-api-php"],
        "extensions": [".php"],
        "build_cmd": ["php", "-l"],
        "test_cmd": ["./vendor/bin/phpunit"],
    },
    "proto": {
        "paths": ["popinz-v2-rust/proto"],
        "extensions": [".proto"],
        "build_cmd": None,
        "test_cmd": None,
    },
    "sql": {
        "paths": ["docker/migrations", "popinz-v2-rust/migrations"],
        "extensions": [".sql"],
        "build_cmd": None,
        "test_cmd": None,
    },
    "e2e": {
        "paths": ["popinz-tests"],
        "extensions": [".spec.ts"],
        "build_cmd": None,
        "test_cmd": ["npx", "playwright", "test", "--list"],
    },
}


def log(msg: str, level: str = "INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [BRAIN] [{level}] {msg}", flush=True)


def load_backlog() -> dict:
    if BACKLOG_FILE.exists():
        return json.loads(BACKLOG_FILE.read_text())
    return {"tasks": [], "updated": None}


def save_backlog(data: dict):
    data["updated"] = datetime.now().isoformat()
    BACKLOG_FILE.write_text(json.dumps(data, indent=2))


def enrich_task_context(task: dict) -> dict:
    """
    Enrichit une tâche avec le contexte nécessaire pour MiniMax.

    Ajoute:
    - file_content: Le code source du fichier (max 3000 chars)
    - error_context: L'erreur exacte si disponible
    - imports: Les imports du fichier
    - test_example: Un exemple de test du projet
    - related_types: Types/structs utilisés
    """
    files = task.get("files", [])
    if not files:
        return task

    file_path = files[0]
    domain = task.get("domain", "")

    # 1. Read file content
    full_path = POPINZ_ROOT / file_path
    if full_path.exists():
        try:
            content = full_path.read_text()
            task["file_content"] = content[:3000]  # First 3000 chars
            task["file_lines"] = len(content.split("\n"))

            # 2. Extract imports
            if domain in ["rust", "api-saas", "api-central", "api-registrations"]:
                imports = re.findall(r'^use\s+([^;]+);', content, re.MULTILINE)
                task["imports"] = imports[:20]  # Max 20 imports
            elif domain in ["e2e", "typescript"]:
                imports = re.findall(r"^import\s+.*?from\s+['\"]([^'\"]+)['\"]", content, re.MULTILINE)
                task["imports"] = imports[:20]

            # 3. Extract types/structs used
            if domain in ["rust", "api-saas"]:
                structs = re.findall(r'\b(struct|enum|trait)\s+(\w+)', content)
                task["types_defined"] = [s[1] for s in structs][:10]

        except Exception as e:
            task["file_content"] = f"Error reading file: {e}"

    # 4. Get error context from finding
    finding = task.get("finding", {})
    if finding:
        task["error_context"] = {
            "type": finding.get("type", ""),
            "message": finding.get("message", "")[:500],
            "severity": finding.get("severity", ""),
            "line": finding.get("line"),
        }

    # 5. Find test example from same domain
    test_example = _find_test_example(domain, file_path)
    if test_example:
        task["test_example"] = test_example

    # 6. Add project conventions
    task["conventions"] = _get_conventions(domain)

    return task


def _find_test_example(domain: str, file_path: str) -> Optional[str]:
    """Find a similar test file as example"""
    if domain == "e2e":
        # Find another .spec.ts file
        test_dir = POPINZ_ROOT / "popinz-tests" / "e2e"
        if test_dir.exists():
            for spec in test_dir.rglob("*.spec.ts"):
                content = spec.read_text()
                # Return first 1500 chars of a test that has good patterns
                if "test(" in content and "expect(" in content and "test.skip" not in content:
                    return f"// Example from {spec.name}\n{content[:1500]}"
        return None

    elif domain in ["rust", "api-saas"]:
        # Find a Rust test
        rust_dir = POPINZ_ROOT / "popinz-v2-rust"
        for rs_file in rust_dir.rglob("*_test.rs"):
            content = rs_file.read_text()
            if "#[test]" in content:
                return f"// Example from {rs_file.name}\n{content[:1500]}"
        # Also check inline tests
        for rs_file in rust_dir.rglob("*.rs"):
            content = rs_file.read_text()
            if "#[cfg(test)]" in content and "#[test]" in content:
                # Extract just the test module
                match = re.search(r'#\[cfg\(test\)\].*?mod tests \{.*?\n\}', content, re.DOTALL)
                if match:
                    return f"// Example from {rs_file.name}\n{match.group(0)[:1500]}"
        return None

    elif domain == "typescript":
        ts_dir = POPINZ_ROOT / "popinz-saas"
        for test_file in ts_dir.rglob("*.test.ts"):
            content = test_file.read_text()
            if "describe(" in content or "it(" in content:
                return f"// Example from {test_file.name}\n{content[:1500]}"
        return None

    return None


def _get_conventions(domain: str) -> dict:
    """Get project conventions for a domain"""
    conventions = {
        "rust": {
            "error_handling": "Use ? operator, avoid unwrap(). Use anyhow::Result or custom Error types.",
            "testing": "Add #[cfg(test)] mod tests { use super::*; #[test] fn test_xxx() {...} }",
            "naming": "snake_case for functions/vars, CamelCase for types",
            "async": "Use async/await with tokio runtime",
        },
        "e2e": {
            "framework": "Playwright with TypeScript",
            "structure": "test.describe() > test() > expect()",
            "skip_pattern": "Use test.skip(IS_STAGING, 'reason') for conditional skips, NEVER bare test.skip()",
            "selectors": "Prefer data-testid, role selectors, or text selectors",
            "assertions": "Use expect(locator).toBeVisible(), toHaveText(), etc.",
        },
        "typescript": {
            "types": "Strict TypeScript, no 'any'. Use interfaces/types.",
            "testing": "Vitest with describe/it/expect",
            "imports": "Use named imports, absolute paths with @/",
        },
        "api-saas": {
            "framework": "Rust with tonic for gRPC",
            "proto": "Proto files in popinz-v2-rust/proto/",
            "error_handling": "Use Status::internal() etc for gRPC errors",
        },
    }
    return conventions.get(domain, {})


def load_cache() -> dict:
    if ANALYSIS_CACHE.exists():
        return json.loads(ANALYSIS_CACHE.read_text())
    return {"file_hashes": {}, "last_full_scan": None}


def save_cache(data: dict):
    ANALYSIS_CACHE.write_text(json.dumps(data, indent=2))


def file_hash(path: Path) -> str:
    """Calculate MD5 hash of file content"""
    if not path.exists():
        return ""
    return hashlib.md5(path.read_bytes()).hexdigest()


class SubAgent:
    """Sub-agent for domain-specific analysis"""

    def __init__(self, domain: str, config: dict):
        self.domain = domain
        self.config = config
        self.findings = []

    async def analyze(self) -> List[Dict]:
        """Run domain-specific analysis"""
        log(f"  [SUB-AGENT:{self.domain.upper()}] Starting analysis...")

        findings = []

        # 1. Find all files in domain
        files = self._find_files()
        log(f"  [SUB-AGENT:{self.domain.upper()}] Found {len(files)} files")

        if not files:
            return findings

        # 2. Run build check if available
        if self.config.get("build_cmd"):
            build_findings = await self._check_build()
            findings.extend(build_findings)

        # 3. Run test check if available
        if self.config.get("test_cmd"):
            test_findings = await self._check_tests()
            findings.extend(test_findings)

        # 4. Domain-specific deep analysis
        if self.domain == "rust":
            findings.extend(await self._analyze_rust_deep(files))
        elif self.domain == "typescript":
            findings.extend(await self._analyze_typescript_deep(files))
        elif self.domain == "proto":
            findings.extend(await self._analyze_proto_deep(files))
        elif self.domain == "sql":
            findings.extend(await self._analyze_sql_deep(files))
        elif self.domain == "e2e":
            findings.extend(await self._analyze_e2e_deep(files))

        log(f"  [SUB-AGENT:{self.domain.upper()}] Found {len(findings)} issues")
        return findings

    def _find_files(self) -> List[Path]:
        """Find all files for this domain"""
        files = []
        for path in self.config.get("paths", []):
            full_path = POPINZ_ROOT / path
            if not full_path.exists():
                continue
            for ext in self.config.get("extensions", []):
                files.extend(full_path.rglob(f"*{ext}"))
        return files

    async def _check_build(self) -> List[Dict]:
        """Run build command and parse errors"""
        findings = []
        cmd = self.config["build_cmd"]

        try:
            # Determine working directory
            if self.domain == "rust":
                cwd = RUST_DIR
            else:
                cwd = POPINZ_ROOT / self.config["paths"][0]

            if not cwd.exists():
                return findings

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(cwd)
            )

            if result.returncode != 0:
                # Parse errors
                errors = self._parse_build_errors(result.stderr + result.stdout)
                for error in errors:
                    findings.append({
                        "type": "build_error",
                        "domain": self.domain,
                        "severity": "high",
                        "file": error.get("file", "unknown"),
                        "line": error.get("line"),
                        "message": error.get("message", "Build error"),
                        "raw": error.get("raw", "")[:200]
                    })

        except subprocess.TimeoutExpired:
            findings.append({
                "type": "build_timeout",
                "domain": self.domain,
                "severity": "medium",
                "message": f"Build command timeout for {self.domain}"
            })
        except Exception as e:
            log(f"  [SUB-AGENT:{self.domain.upper()}] Build check error: {e}", "WARN")

        return findings

    async def _check_tests(self) -> List[Dict]:
        """Run test command and parse failures"""
        findings = []
        cmd = self.config["test_cmd"]

        try:
            if self.domain == "rust":
                cwd = RUST_DIR
            else:
                cwd = POPINZ_ROOT / self.config["paths"][0]

            if not cwd.exists():
                return findings

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(cwd)
            )

            if result.returncode != 0:
                findings.append({
                    "type": "test_failure",
                    "domain": self.domain,
                    "severity": "high",
                    "message": f"Test compilation/run failed for {self.domain}",
                    "raw": (result.stderr + result.stdout)[:500]
                })

        except subprocess.TimeoutExpired:
            pass  # Tests timeout is OK for --no-run
        except Exception as e:
            log(f"  [SUB-AGENT:{self.domain.upper()}] Test check error: {e}", "WARN")

        return findings

    def _parse_build_errors(self, output: str) -> List[Dict]:
        """Parse build errors from compiler output"""
        errors = []

        if self.domain == "rust":
            # Parse Rust errors: error[E0XXX]: message
            for match in re.finditer(r'error\[E\d+\]: (.+?)(?:\n|$)', output):
                errors.append({"message": match.group(1)})
            # Parse file locations
            for match in re.finditer(r'--> ([^:]+):(\d+):\d+', output):
                if errors:
                    errors[-1]["file"] = match.group(1)
                    errors[-1]["line"] = int(match.group(2))

        elif self.domain == "typescript":
            # Parse TS errors
            for match in re.finditer(r'([^:\s]+\.tsx?)\((\d+),\d+\): error TS\d+: (.+)', output):
                errors.append({
                    "file": match.group(1),
                    "line": int(match.group(2)),
                    "message": match.group(3)
                })

        return errors[:20]  # Limit to 20 errors

    async def _analyze_rust_deep(self, files: List[Path]) -> List[Dict]:
        """Deep analysis of Rust code"""
        findings = []

        for file in files[:100]:  # Limit files analyzed
            try:
                content = file.read_text()
                rel_path = file.relative_to(POPINZ_ROOT)

                # Check for TODO/FIXME comments
                for i, line in enumerate(content.split('\n'), 1):
                    if 'TODO' in line or 'FIXME' in line:
                        findings.append({
                            "type": "todo",
                            "domain": "rust",
                            "severity": "low",
                            "file": str(rel_path),
                            "line": i,
                            "message": line.strip()[:100]
                        })

                # Check for unwrap() calls (potential panics)
                unwrap_count = content.count('.unwrap()')
                if unwrap_count > 10:
                    findings.append({
                        "type": "code_smell",
                        "domain": "rust",
                        "severity": "medium",
                        "file": str(rel_path),
                        "message": f"High unwrap() usage ({unwrap_count} calls) - consider error handling"
                    })

                # Check for unimplemented!() or todo!() macros
                if 'unimplemented!()' in content or 'todo!()' in content:
                    findings.append({
                        "type": "incomplete",
                        "domain": "rust",
                        "severity": "medium",
                        "file": str(rel_path),
                        "message": "Contains unimplemented!() or todo!() macro"
                    })

            except Exception:
                continue

        return findings

    async def _analyze_typescript_deep(self, files: List[Path]) -> List[Dict]:
        """Deep analysis of TypeScript code"""
        findings = []

        for file in files[:100]:
            try:
                content = file.read_text()
                rel_path = file.relative_to(POPINZ_ROOT)

                # Check for any type usage
                any_count = len(re.findall(r': any\b', content))
                if any_count > 5:
                    findings.append({
                        "type": "type_safety",
                        "domain": "typescript",
                        "severity": "medium",
                        "file": str(rel_path),
                        "message": f"High 'any' type usage ({any_count} occurrences)"
                    })

                # Check for console.log in production code
                if 'console.log' in content and 'test' not in str(file).lower():
                    findings.append({
                        "type": "debug_code",
                        "domain": "typescript",
                        "severity": "low",
                        "file": str(rel_path),
                        "message": "Contains console.log statements"
                    })

            except Exception:
                continue

        return findings

    async def _analyze_proto_deep(self, files: List[Path]) -> List[Dict]:
        """Deep analysis of Proto files"""
        findings = []

        for file in files:
            try:
                content = file.read_text()
                rel_path = file.relative_to(POPINZ_ROOT)

                # Check for missing comments on services
                services = re.findall(r'service (\w+)', content)
                for service in services:
                    if f'// {service}' not in content and f'/* {service}' not in content:
                        findings.append({
                            "type": "documentation",
                            "domain": "proto",
                            "severity": "low",
                            "file": str(rel_path),
                            "message": f"Service '{service}' lacks documentation"
                        })

            except Exception:
                continue

        return findings

    async def _analyze_sql_deep(self, files: List[Path]) -> List[Dict]:
        """Deep analysis of SQL migrations"""
        findings = []

        for file in files:
            try:
                content = file.read_text()
                rel_path = file.relative_to(POPINZ_ROOT)

                # Check for DROP without IF EXISTS
                if 'DROP TABLE' in content and 'IF EXISTS' not in content:
                    findings.append({
                        "type": "migration_safety",
                        "domain": "sql",
                        "severity": "high",
                        "file": str(rel_path),
                        "message": "DROP TABLE without IF EXISTS"
                    })

                # Check for missing indexes on foreign keys
                fk_columns = re.findall(r'REFERENCES \w+\((\w+)\)', content)
                for col in fk_columns:
                    if f'INDEX' not in content or col not in content:
                        pass  # Would need more context

            except Exception:
                continue

        return findings

    async def _analyze_e2e_deep(self, files: List[Path]) -> List[Dict]:
        """Deep analysis of E2E tests"""
        findings = []

        for file in files:
            try:
                content = file.read_text()
                rel_path = file.relative_to(POPINZ_ROOT)

                # Check for test.skip or test.only
                if 'test.skip' in content or 'test.only' in content:
                    findings.append({
                        "type": "test_config",
                        "domain": "e2e",
                        "severity": "medium",
                        "file": str(rel_path),
                        "message": "Contains test.skip or test.only"
                    })

                # Check for hardcoded credentials
                if 'password' in content.lower() and ('test123' in content or 'admin' in content.lower()):
                    findings.append({
                        "type": "security",
                        "domain": "e2e",
                        "severity": "low",
                        "file": str(rel_path),
                        "message": "Hardcoded test credentials (review for security)"
                    })

            except Exception:
                continue

        return findings


class SecuritySubAgent(SubAgent):
    """Specialized sub-agent for security analysis"""

    def __init__(self):
        super().__init__("security", {"paths": [], "extensions": []})

    async def analyze(self) -> List[Dict]:
        """Run security-focused analysis across all domains"""
        log("  [SUB-AGENT:SECURITY] Starting security scan...")
        findings = []

        # Scan for secrets in all files
        secret_patterns = [
            (r'password\s*=\s*["\'][^"\']+["\']', "Hardcoded password"),
            (r'api[_-]?key\s*=\s*["\'][^"\']+["\']', "Hardcoded API key"),
            (r'secret\s*=\s*["\'][^"\']+["\']', "Hardcoded secret"),
            (r'sk_live_[a-zA-Z0-9]+', "Stripe live key"),
            (r'AKIA[A-Z0-9]{16}', "AWS access key"),
        ]

        # Scan common locations
        scan_paths = [
            POPINZ_ROOT / "popinz-v2-rust",
            POPINZ_ROOT / "popinz-saas",
            POPINZ_ROOT / "popinz-tests",
        ]

        for scan_path in scan_paths:
            if not scan_path.exists():
                continue

            for ext in ['.rs', '.ts', '.tsx', '.js', '.json', '.env', '.yaml', '.yml']:
                for file in scan_path.rglob(f'*{ext}'):
                    if '.git' in str(file) or 'node_modules' in str(file):
                        continue

                    try:
                        content = file.read_text()
                        rel_path = file.relative_to(POPINZ_ROOT)

                        for pattern, desc in secret_patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                # Exclude test files and examples
                                if 'test' in str(file).lower() or 'example' in str(file).lower():
                                    continue
                                findings.append({
                                    "type": "security",
                                    "domain": "security",
                                    "severity": "critical",
                                    "file": str(rel_path),
                                    "message": f"Potential {desc} detected"
                                })
                                break  # One finding per file

                    except Exception:
                        continue

        log(f"  [SUB-AGENT:SECURITY] Found {len(findings)} security issues")
        return findings


class LRMBrain:
    """
    LEAN Requirements Manager Brain - Autonomous Analyzer

    Orchestrates sub-agents to analyze the entire codebase and create
    prioritized tasks using WSJF scoring.
    """

    def __init__(self):
        self.tasks = []
        self.existing_ids = set()
        self.findings = []

    async def analyze(self, domains: List[str] = None, quick: bool = False) -> List[Dict]:
        """Run full analysis with sub-agents"""
        log("=" * 60)
        log("LRM BRAIN - AUTONOMOUS ANALYSIS")
        log("=" * 60)

        # Load existing tasks to avoid duplicates
        existing = load_backlog()
        self.existing_ids = {t.get("id") for t in existing.get("tasks", [])}

        # Determine domains to analyze
        if domains:
            active_domains = {d: PROJECT_DOMAINS[d] for d in domains if d in PROJECT_DOMAINS}
        else:
            active_domains = PROJECT_DOMAINS

        log(f"\nAnalyzing {len(active_domains)} domains: {', '.join(active_domains.keys())}")

        # Create and run sub-agents in parallel
        sub_agents = []
        for domain, config in active_domains.items():
            sub_agents.append(SubAgent(domain, config))

        # Add security sub-agent
        if not quick:
            sub_agents.append(SecuritySubAgent())

        # Run all sub-agents
        log("\n[PHASE 1] Running domain sub-agents...")

        all_findings = []
        for agent in sub_agents:
            findings = await agent.analyze()
            all_findings.extend(findings)

        self.findings = all_findings
        log(f"\n[PHASE 2] Collected {len(all_findings)} findings")

        # Convert findings to tasks
        log("\n[PHASE 3] Creating prioritized tasks...")
        self._create_tasks_from_findings()

        # Calculate WSJF scores
        for task in self.tasks:
            task["wsjf_score"] = self._calculate_wsjf(task)

        # Sort by priority
        self.tasks.sort(key=lambda t: -t.get("wsjf_score", 0))

        log(f"\nCreated {len(self.tasks)} new tasks")

        return self.tasks

    def _calculate_wsjf(self, task: dict) -> float:
        """Calculate Weighted Shortest Job First score"""
        bv = task.get("business_value", 5)
        tc = task.get("time_criticality", 5)
        rr = task.get("risk_reduction", 5)
        job_size = task.get("job_size", 5)

        if job_size == 0:
            job_size = 1

        return round((bv + tc + rr) / job_size, 2)

    def _create_tasks_from_findings(self):
        """Convert findings into actionable tasks - ONE TASK PER FINDING"""

        # Severity scores
        severity_map = {
            "critical": {"bv": 10, "tc": 10, "rr": 9, "size": 2},
            "high": {"bv": 8, "tc": 8, "rr": 7, "size": 3},
            "medium": {"bv": 5, "tc": 5, "rr": 5, "size": 3},
            "low": {"bv": 3, "tc": 3, "rr": 3, "size": 2},
        }

        # Create ONE task per finding
        for i, finding in enumerate(self.findings):
            finding_type = finding.get("type", "unknown")
            domain = finding.get("domain", "unknown")
            severity = finding.get("severity", "low")
            file_path = finding.get("file", "")
            message = finding.get("message", "")[:80]
            line = finding.get("line", 0)

            # Generate unique task ID
            file_short = Path(file_path).name if file_path else "unknown"
            task_id = f"{domain}-{finding_type}-{i:04d}-{file_short[:20]}"

            # Skip if task exists
            if task_id in self.existing_ids:
                continue

            scores = severity_map.get(severity, severity_map["medium"])

            # Create task description
            if line:
                desc = f"[{severity.upper()}] {file_short}:{line} - {message}"
            else:
                desc = f"[{severity.upper()}] {file_short} - {message}"

            # Create base task
            task = {
                "id": task_id,
                "type": "fix" if severity in ["critical", "high"] else "improvement",
                "domain": domain,
                "description": desc[:100],
                "files": [file_path] if file_path else [],
                "line": line,
                "finding": finding,
                "status": "pending",
                "business_value": scores["bv"],
                "time_criticality": scores["tc"],
                "risk_reduction": scores["rr"],
                "job_size": scores["size"],
            }

            # Enrich with context for MiniMax
            task = enrich_task_context(task)

            self.tasks.append(task)

    def create_backlog(self) -> dict:
        """Create/update backlog with prioritized tasks"""
        existing = load_backlog()
        existing_tasks = existing.get("tasks", [])

        # Keep completed/in-progress tasks
        kept_tasks = [t for t in existing_tasks if t.get("status") in ("completed", "in_progress")]

        # Add new pending tasks
        new_tasks = [t for t in self.tasks if t.get("status") == "pending"]

        # Combine
        all_tasks = kept_tasks + new_tasks

        data = {
            "tasks": all_tasks,
            "source": "LRM Brain autonomous analysis",
            "analysis_summary": {
                "total_findings": len(self.findings),
                "domains_analyzed": list(set(f.get("domain") for f in self.findings)),
                "severity_breakdown": {
                    "critical": len([f for f in self.findings if f.get("severity") == "critical"]),
                    "high": len([f for f in self.findings if f.get("severity") == "high"]),
                    "medium": len([f for f in self.findings if f.get("severity") == "medium"]),
                    "low": len([f for f in self.findings if f.get("severity") == "low"]),
                }
            },
            "updated": datetime.now().isoformat()
        }

        save_backlog(data)

        return data


def add_requirement_task(
    requirement: str,
    domain: str = "mobile",
    target_files: List[str] = None,
    context: str = None
) -> dict:
    """
    Add a mega-task (requirement) to the backlog.
    Fractal decomposition will auto-split it into subtasks.

    Args:
        requirement: High-level requirement description (e.g., "Mobile App v1 - iOS/Android")
        domain: Target domain (mobile, rust, typescript, e2e, etc.)
        target_files: List of target files/directories to create/modify
        context: Additional context (architecture, specs, constraints)

    Returns:
        The created task dict
    """
    import fcntl

    # Generate unique task ID
    task_id = f"{domain}-requirement-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    # Build enriched context for LLM
    enriched_context = f"""
MEGA-TASK: {requirement}

DOMAIN: {domain}

TARGET FILES/DIRECTORIES:
{chr(10).join(f'- {f}' for f in (target_files or []))}

CONTEXT:
{context or 'See CLAUDE.md for architecture details'}

INSTRUCTIONS:
1. This is a large requirement - analyze and decompose into subtasks
2. Use FRACTAL: prefix in output to trigger decomposition
3. Each subtask should be atomic (single file, single concern)
4. Follow TDD: write tests first, then implementation
5. Respect existing architecture and patterns in the codebase
"""

    # Create mega-task with high complexity to trigger fractal
    task = {
        "id": task_id,
        "type": "requirement",
        "domain": domain,
        "description": requirement,
        "status": "pending",
        "files": target_files or [],
        "file_content": enriched_context,
        "context": {
            "requirement": requirement,
            "target_files": target_files or [],
            "additional_context": context,
        },
        # High complexity markers to ensure fractal decomposition
        "complexity": 10,
        "loc_estimate": 5000,
        "file_count": len(target_files or []) or 20,
        # WSJF scoring - requirements are high priority
        "business_value": 10,
        "time_criticality": 8,
        "risk_reduction": 7,
        "job_size": 8,
        "wsjf_score": 3.13,  # (10+8+7)/8
        "created_at": datetime.now().isoformat(),
    }

    # Add to backlog
    backlog_path = Path(__file__).parent / "backlog_tasks.json"

    with open(backlog_path, 'r+') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            data = json.load(f)
            data["tasks"].insert(0, task)  # Add at top (high priority)
            data["updated"] = datetime.now().isoformat()
            f.seek(0)
            f.truncate()
            json.dump(data, f, indent=2)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)

    log(f"✅ Added mega-task: {task_id}")
    log(f"   Description: {requirement}")
    log(f"   Target files: {len(target_files or [])} files")
    log(f"   → Wiggum will fractal-decompose this into subtasks")

    return task


async def run_analysis(domains: List[str] = None, quick: bool = False):
    """Run brain analysis"""
    brain = LRMBrain()
    tasks = await brain.analyze(domains=domains, quick=quick)

    if tasks:
        backlog = brain.create_backlog()
        log("\n" + "=" * 60)
        log(f"BACKLOG UPDATED: {len(backlog['tasks'])} total tasks")
        log("=" * 60)

        # Show top 10 tasks
        pending = [t for t in backlog["tasks"] if t.get("status") == "pending"]
        log(f"\nTop pending tasks (by WSJF):")
        for t in pending[:10]:
            wsjf = t.get("wsjf_score", 0)
            log(f"  [{wsjf:.1f}] {t['id']}: {t['description'][:50]}")

        # Show analysis summary
        summary = backlog.get("analysis_summary", {})
        log(f"\nAnalysis summary:")
        log(f"  Total findings: {summary.get('total_findings', 0)}")
        log(f"  Domains: {', '.join(summary.get('domains_analyzed', []))}")
        severity = summary.get("severity_breakdown", {})
        log(f"  Critical: {severity.get('critical', 0)}, High: {severity.get('high', 0)}, Medium: {severity.get('medium', 0)}, Low: {severity.get('low', 0)}")
    else:
        log("\nNo issues found - codebase is clean!")

    return tasks


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="LRM Brain - Autonomous Analyzer")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # analyze command (default)
    analyze_parser = subparsers.add_parser("analyze", help="Analyze codebase for issues")
    analyze_parser.add_argument("--quick", action="store_true", help="Quick scan (skip security)")
    analyze_parser.add_argument("--domain", type=str, help="Analyze specific domain")

    # requirement command
    req_parser = subparsers.add_parser("requirement", help="Add a mega-task requirement")
    req_parser.add_argument("description", type=str, help="Requirement description")
    req_parser.add_argument("--domain", type=str, default="mobile", help="Target domain")
    req_parser.add_argument("--files", type=str, nargs="*", help="Target files/directories")
    req_parser.add_argument("--context", type=str, help="Additional context")

    args = parser.parse_args()

    if args.command == "requirement":
        add_requirement_task(
            requirement=args.description,
            domain=args.domain,
            target_files=args.files,
            context=args.context
        )
    else:
        # Default: analyze
        quick = getattr(args, "quick", False)
        domain = getattr(args, "domain", None)
        domains = [domain] if domain else None
        await run_analysis(domains=domains, quick=quick)


if __name__ == "__main__":
    asyncio.run(main())
