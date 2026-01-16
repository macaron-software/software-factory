#!/usr/bin/env python3
"""
RLM Brain - LEAN Requirements Manager Orchestrator
==================================================
Based on MIT CSAIL arXiv:2512.24601 "Recursive Language Models"

The Brain is the central orchestrator that:
1. SCANS the project recursively using vision document
2. ANALYZES each domain (build errors, tests, tech debt)
3. IDENTIFIES problems and opportunities
4. PRIORITIZES with WSJF (Weighted Shortest Job First)
5. CREATES actionable tasks for Wiggum TDD workers

Uses Claude Opus 4.5 via `claude` CLI for heavy analysis.

Usage:
    from core.brain import RLMBrain

    brain = RLMBrain("ppz")
    await brain.run(question="focus on mobile features")
"""

import asyncio
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import sys

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.project_registry import get_project, ProjectConfig
from core.task_store import TaskStore, Task
from core.llm_client import run_claude_agent, run_opencode


def log(msg: str, level: str = "INFO"):
    """Log with timestamp"""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [BRAIN] [{level}] {msg}", flush=True)


# ============================================================================
# CONTEXT ENRICHMENT
# ============================================================================

def enrich_task_context(
    task: Dict,
    project_root: Path,
    domain: str,
) -> Dict:
    """
    Enrich task with context needed by Wiggum workers.

    Adds:
    - file_content: Source code (max 3000 chars)
    - imports: File imports
    - types_defined: Structs/classes defined
    - error_context: Error details if available
    - test_example: Example test from project
    - conventions: Domain conventions
    """
    files = task.get("files", [])
    if not files:
        return task

    file_path = files[0]
    full_path = project_root / file_path

    if not full_path.exists():
        return task

    try:
        content = full_path.read_text()
        task["file_content"] = content[:3000]
        task["file_lines"] = len(content.split("\n"))

        # Extract imports based on domain
        if domain == "rust":
            imports = re.findall(r"^use\s+([^;]+);", content, re.MULTILINE)
            structs = re.findall(r"\b(struct|enum|trait)\s+(\w+)", content)
            task["imports"] = imports[:20]
            task["types_defined"] = [s[1] for s in structs][:10]
        elif domain in ["typescript", "e2e"]:
            imports = re.findall(r"^import\s+.*?from\s+['\"]([^'\"]+)['\"]", content, re.MULTILINE)
            classes = re.findall(r"\b(class|interface|type)\s+(\w+)", content)
            task["imports"] = imports[:20]
            task["types_defined"] = [c[1] for c in classes][:10]
        elif domain == "python":
            imports = re.findall(r"^(?:from\s+\S+\s+)?import\s+(\S+)", content, re.MULTILINE)
            classes = re.findall(r"^class\s+(\w+)", content, re.MULTILINE)
            task["imports"] = imports[:20]
            task["types_defined"] = classes[:10]

    except Exception as e:
        task["file_content"] = f"Error reading file: {e}"

    # Add conventions
    task["conventions"] = {
        "rust": {
            "error_handling": "Use ? operator, avoid .unwrap()",
            "testing": "#[cfg(test)] mod tests { ... }",
            "skip_pattern": "NEVER use #[ignore]",
        },
        "typescript": {
            "error_handling": "Use try/catch or Result pattern",
            "testing": "describe/it with vitest",
            "skip_pattern": "NEVER use test.skip()",
        },
        "python": {
            "error_handling": "Use try/except with specific exceptions",
            "testing": "pytest with test_ prefix",
            "skip_pattern": "NEVER use pytest.mark.skip",
        },
    }.get(domain, {})

    return task


def calculate_wsjf(task: Dict) -> float:
    """
    Calculate WSJF (Weighted Shortest Job First) score.

    WSJF = (Business Value + Time Criticality + Risk Reduction) / Job Size

    Higher score = higher priority.
    """
    # Default values
    business_value = task.get("business_value", 5)
    time_criticality = task.get("time_criticality", 3)
    risk_reduction = task.get("risk_reduction", 3)
    job_size = task.get("job_size", 3)

    # Adjust based on task type
    task_type = task.get("type", "fix")
    type_multipliers = {
        "security": 2.0,
        "fix": 1.5,
        "test": 1.2,
        "feature": 1.0,
        "refactor": 0.8,
    }
    multiplier = type_multipliers.get(task_type, 1.0)

    # Adjust based on severity if present
    severity = task.get("severity", "medium")
    severity_bonus = {"critical": 5, "high": 3, "medium": 1, "low": 0}.get(severity, 1)

    numerator = (business_value + time_criticality + risk_reduction + severity_bonus) * multiplier
    denominator = max(job_size, 1)

    return round(numerator / denominator, 2)


# ============================================================================
# ANALYZERS
# ============================================================================

class DomainAnalyzer:
    """
    Analyze a specific domain using LLM sub-agents.

    Conforme MIT CSAIL RLM: spawns sub-agents (opencode) for deep analysis.
    """

    def __init__(self, project: ProjectConfig, domain: str):
        self.project = project
        self.domain = domain
        self.domain_config = project.get_domain(domain) or {}
        self.findings: List[Dict] = []

    async def analyze(self) -> List[Dict]:
        """
        Run LLM-based analysis for the domain.

        Uses opencode sub-agents for:
        1. Build error analysis
        2. Code quality analysis
        3. Security scanning
        """
        self.findings = []

        # 1. Run build and collect errors
        build_cmd = self.domain_config.get("build_cmd")
        if build_cmd:
            build_findings = await self._analyze_build_with_llm(build_cmd)
            self.findings.extend(build_findings)

        # 2. Run LLM sub-agent for code analysis
        code_findings = await self._analyze_code_with_llm()
        self.findings.extend(code_findings)

        return self.findings

    async def _analyze_build_with_llm(self, cmd: str) -> List[Dict]:
        """Run build and use LLM sub-agent to analyze errors"""
        log(f"Running build for {self.domain}: {cmd}")
        findings = []

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=str(self.project.root_path),
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode != 0:
                # Use LLM sub-agent to analyze build errors
                output = result.stderr + result.stdout

                if len(output) > 100:  # Only if there's meaningful output
                    prompt = f"""Analyze these build errors for {self.domain} domain.

BUILD OUTPUT:
{output[:8000]}

Return a JSON array of findings:
[{{"type": "build_error", "severity": "high|medium|low", "file": "path/to/file", "line": 123, "message": "description"}}]

Only return the JSON array, no other text."""

                    returncode, llm_output = await run_opencode(
                        prompt,
                        model="minimax/MiniMax-M2.1",
                        cwd=str(self.project.root_path),
                        timeout=120,
                    )

                    if returncode == 0:
                        findings = self._parse_llm_findings(llm_output)
                        log(f"LLM sub-agent found {len(findings)} build issues")
                    else:
                        # Fallback to regex parsing
                        findings = self._parse_build_errors_regex(output)

        except subprocess.TimeoutExpired:
            log(f"Build timeout for {self.domain}", "WARN")
        except Exception as e:
            log(f"Build error for {self.domain}: {e}", "ERROR")

        return findings

    async def _analyze_code_with_llm(self) -> List[Dict]:
        """Use LLM sub-agent for deep code analysis"""
        log(f"Running LLM code analysis for {self.domain}")

        paths = self.domain_config.get("paths", [])
        extensions = self.domain_config.get("extensions", [])

        # Collect sample files for analysis
        sample_files = []
        for path_str in paths:
            path = self.project.root_path / path_str
            if not path.exists():
                continue
            for ext in extensions:
                for file in list(path.rglob(f"*{ext}"))[:20]:  # Limit files
                    try:
                        content = file.read_text()[:2000]
                        rel_path = str(file.relative_to(self.project.root_path))
                        sample_files.append({"path": rel_path, "content": content})
                    except Exception:
                        continue

        if not sample_files:
            return []

        # Build prompt for LLM sub-agent
        files_summary = "\n\n".join([
            f"=== {f['path']} ===\n{f['content']}"
            for f in sample_files[:10]
        ])

        prompt = f"""Analyze this {self.domain} code for issues.

FILES:
{files_summary}

Find:
1. Skipped tests (test.skip, #[ignore], pytest.mark.skip)
2. TODO/FIXME comments that indicate incomplete work
3. Error handling issues (.unwrap() abuse, empty catch blocks)
4. Security issues (hardcoded secrets, SQL injection, XSS)
5. Code quality issues

Return a JSON array:
[{{"type": "skipped_test|todo|error_handling|security|quality", "severity": "critical|high|medium|low", "file": "path", "message": "description"}}]

Only return the JSON array."""

        returncode, output = await run_opencode(
            prompt,
            model="minimax/MiniMax-M2.1",
            cwd=str(self.project.root_path),
            timeout=180,
        )

        if returncode == 0:
            findings = self._parse_llm_findings(output)
            log(f"LLM sub-agent found {len(findings)} code issues")
            # Add domain to all findings
            for f in findings:
                f["domain"] = self.domain
            return findings
        else:
            log(f"LLM sub-agent failed for {self.domain}, using fallback", "WARN")
            return self._scan_files_regex()

    def _parse_llm_findings(self, output: str) -> List[Dict]:
        """Parse findings from LLM output"""
        try:
            # Find JSON array in output
            match = re.search(r'\[\s*\{.*?\}\s*\]', output, re.DOTALL)
            if match:
                findings = json.loads(match.group())
                return [f for f in findings if isinstance(f, dict) and "message" in f]
        except json.JSONDecodeError:
            pass
        return []

    def _parse_build_errors_regex(self, output: str) -> List[Dict]:
        """Fallback: parse build errors with regex"""
        errors = []

        # Rust errors
        for match in re.finditer(r"error\[E\d+\]: (.+?)\n\s*-->\s*([^:]+):(\d+)", output):
            errors.append({
                "type": "build_error",
                "domain": self.domain,
                "severity": "high",
                "file": match.group(2),
                "line": int(match.group(3)),
                "message": match.group(1).strip(),
            })

        # TypeScript errors
        for match in re.finditer(r"([^\s]+\.tsx?)\((\d+),\d+\):\s*error\s+TS\d+:\s*(.+)", output):
            errors.append({
                "type": "build_error",
                "domain": self.domain,
                "severity": "high",
                "file": match.group(1),
                "line": int(match.group(2)),
                "message": match.group(3).strip(),
            })

        return errors[:20]

    def _scan_files_regex(self) -> List[Dict]:
        """Fallback: scan files with regex patterns"""
        findings = []
        paths = self.domain_config.get("paths", [])
        extensions = self.domain_config.get("extensions", [])

        for path_str in paths:
            path = self.project.root_path / path_str
            if not path.exists():
                continue

            for ext in extensions:
                for file in path.rglob(f"*{ext}"):
                    try:
                        content = file.read_text()
                        rel_path = str(file.relative_to(self.project.root_path))

                        # Skipped tests
                        if re.search(r"\b(test\.skip|it\.skip|describe\.skip|#\[ignore\]|pytest\.mark\.skip)\b", content):
                            findings.append({
                                "type": "skipped_test",
                                "domain": self.domain,
                                "severity": "high",
                                "file": rel_path,
                                "message": "Skipped test detected",
                            })

                        # TODOs
                        for match in re.finditer(r"//\s*(TODO|FIXME):?\s*(.+)", content):
                            findings.append({
                                "type": "todo",
                                "domain": self.domain,
                                "severity": "low",
                                "file": rel_path,
                                "message": f"{match.group(1)}: {match.group(2).strip()[:80]}",
                            })

                    except Exception:
                        continue

        return findings[:50]

    def _analyze_build(self, cmd: str):
        """Run build command and extract errors"""
        log(f"Running build for {self.domain}: {cmd}")

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=str(self.project.root_path),
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode != 0:
                # Parse errors from output
                output = result.stderr + result.stdout
                errors = self._parse_errors(output)
                for error in errors:
                    self.findings.append({
                        "type": "build_error",
                        "domain": self.domain,
                        "severity": "high",
                        **error,
                    })

        except subprocess.TimeoutExpired:
            log(f"Build timeout for {self.domain}", "WARN")
        except Exception as e:
            log(f"Build error for {self.domain}: {e}", "ERROR")

    def _analyze_tests(self, cmd: str):
        """Run test discovery and check for issues"""
        log(f"Analyzing tests for {self.domain}")

        # Check for skipped tests
        paths = self.domain_config.get("paths", [])
        extensions = self.domain_config.get("extensions", [])

        for path_str in paths:
            path = self.project.root_path / path_str
            if not path.exists():
                continue

            for ext in extensions:
                for file in path.rglob(f"*{ext}"):
                    try:
                        content = file.read_text()
                        # Check for skipped tests
                        if re.search(r"\b(test\.skip|it\.skip|describe\.skip|#\[ignore\]|pytest\.mark\.skip)\b", content):
                            self.findings.append({
                                "type": "skipped_test",
                                "domain": self.domain,
                                "severity": "high",
                                "file": str(file.relative_to(self.project.root_path)),
                                "message": "Skipped test detected",
                            })
                    except Exception:
                        continue

    def _scan_files(self):
        """Scan files for common issues"""
        paths = self.domain_config.get("paths", [])
        extensions = self.domain_config.get("extensions", [])

        for path_str in paths:
            path = self.project.root_path / path_str
            if not path.exists():
                continue

            for ext in extensions:
                for file in path.rglob(f"*{ext}"):
                    self._scan_file(file)

    def _scan_file(self, file: Path):
        """Scan a single file for issues"""
        try:
            content = file.read_text()
            rel_path = str(file.relative_to(self.project.root_path))

            # TODO/FIXME comments
            todos = re.findall(r"//\s*(TODO|FIXME|HACK|XXX):?\s*(.+)", content)
            for todo_type, message in todos[:5]:  # Limit per file
                self.findings.append({
                    "type": "todo",
                    "domain": self.domain,
                    "severity": "low",
                    "file": rel_path,
                    "message": f"{todo_type}: {message.strip()[:100]}",
                })

            # Unwrap/panic patterns (Rust)
            if self.domain == "rust":
                unwraps = len(re.findall(r"\.unwrap\(\)", content))
                if unwraps > 5:
                    self.findings.append({
                        "type": "unwrap_abuse",
                        "domain": self.domain,
                        "severity": "medium",
                        "file": rel_path,
                        "message": f"{unwraps} .unwrap() calls - consider proper error handling",
                    })

        except Exception:
            pass

    def _parse_errors(self, output: str) -> List[Dict]:
        """Parse errors from build output"""
        errors = []

        # Rust error pattern
        rust_errors = re.findall(
            r"error\[E\d+\]: (.+?)\n\s*-->\s*([^:]+):(\d+)",
            output,
        )
        for message, file, line in rust_errors[:20]:
            errors.append({
                "file": file,
                "line": int(line),
                "message": message.strip(),
            })

        # TypeScript error pattern
        ts_errors = re.findall(
            r"([^\s]+\.tsx?)\((\d+),\d+\):\s*error\s+TS\d+:\s*(.+)",
            output,
        )
        for file, line, message in ts_errors[:20]:
            errors.append({
                "file": file,
                "line": int(line),
                "message": message.strip(),
            })

        return errors


# ============================================================================
# RLM BRAIN
# ============================================================================

class RLMBrain:
    """
    RLM Brain - Central orchestrator for project analysis and task generation.

    Phases:
    1. VISION: Load vision document, understand project goals
    2. ANALYZE: Run domain analyzers, collect findings
    3. SYNTHESIZE: Use LLM to generate tasks from findings
    4. PRIORITIZE: Calculate WSJF scores, order backlog
    5. ENRICH: Add context to each task for Wiggum workers
    """

    def __init__(self, project_name: str = None):
        """
        Initialize Brain for a project.

        Args:
            project_name: Project name from projects/*.yaml
        """
        self.project = get_project(project_name)
        self.task_store = TaskStore()
        self.findings: List[Dict] = []
        self.tasks: List[Dict] = []

        log(f"Brain initialized for project: {self.project.name}")
        log(f"Root: {self.project.root_path}")
        log(f"Domains: {list(self.project.domains.keys())}")

    async def run(
        self,
        question: str = None,
        domains: List[str] = None,
        quick: bool = False,
    ) -> List[Task]:
        """
        Run the Brain analysis pipeline.

        Args:
            question: Focus prompt for analysis (e.g., "mobile features")
            domains: Specific domains to analyze (default: all)
            quick: Skip deep analysis for speed

        Returns:
            List of created Task objects
        """
        log("=" * 60)
        log("Starting RLM Brain analysis")
        log("=" * 60)

        # 1. VISION: Load and process vision document
        vision_content = self._load_vision()

        # 2. ANALYZE: Run domain analyzers with LLM sub-agents
        domains_to_analyze = domains or list(self.project.domains.keys())

        # Spawn sub-agents in parallel for each domain (RLM conformity)
        log(f"Spawning {len(domains_to_analyze)} LLM sub-agents for domain analysis...")
        analysis_tasks = []
        for domain in domains_to_analyze:
            if domain in self.project.domains:
                analyzer = DomainAnalyzer(self.project, domain)
                analysis_tasks.append((domain, analyzer.analyze()))

        # Run all domain analyses in parallel
        for domain, task in analysis_tasks:
            try:
                log(f"Analyzing domain: {domain}")
                domain_findings = await task
                self.findings.extend(domain_findings)
                log(f"Found {len(domain_findings)} findings in {domain}")
            except Exception as e:
                log(f"Domain {domain} analysis failed: {e}", "ERROR")

        log(f"Total findings: {len(self.findings)}")

        if not self.findings:
            log("No findings to process")
            return []

        # 3. SYNTHESIZE: Generate tasks from findings
        if quick:
            # Quick mode: create task for each finding directly
            self.tasks = self._quick_task_generation()
        else:
            # Full mode: use LLM to synthesize
            self.tasks = await self._llm_task_generation(vision_content, question)

        # 4. PRIORITIZE: Calculate WSJF and sort
        for task in self.tasks:
            task["wsjf_score"] = calculate_wsjf(task)

        self.tasks.sort(key=lambda t: t.get("wsjf_score", 0), reverse=True)

        # 5. ENRICH: Add context for Wiggum workers
        for task in self.tasks:
            task = enrich_task_context(
                task,
                self.project.root_path,
                task.get("domain", ""),
            )

        # 6. PERSIST: Save to task store
        created_tasks = []
        for idx, task_dict in enumerate(self.tasks):
            try:
                # Generate unique task ID
                task_id = self._generate_task_id(task_dict, idx)

                # Create Task object
                task_obj = Task(
                    id=task_id,
                    project_id=self.project.id,
                    type=task_dict.get("type", "fix"),
                    domain=task_dict.get("domain", "unknown"),
                    description=task_dict.get("description", ""),
                    files=task_dict.get("files", []),
                    context=task_dict,
                    wsjf_score=task_dict.get("wsjf_score", 0.0),
                )

                self.task_store.create_task(task_obj)
                created_tasks.append(task_obj)
            except Exception as e:
                log(f"Failed to create task: {e}", "ERROR")

        log(f"Created {len(created_tasks)} tasks in store")
        log("=" * 60)
        log("Brain analysis complete")
        log("=" * 60)

        return created_tasks

    def _load_vision(self) -> str:
        """Load vision document content"""
        vision_content = self.project.get_vision_content()
        if vision_content:
            log(f"Loaded vision doc: {self.project.vision_doc} ({len(vision_content)} chars)")
        else:
            log("No vision document found", "WARN")
        return vision_content

    def _quick_task_generation(self) -> List[Dict]:
        """Quick task generation without LLM"""
        tasks = []
        for finding in self.findings:
            task = {
                "type": self._finding_type_to_task_type(finding.get("type", "")),
                "domain": finding.get("domain", "unknown"),
                "description": finding.get("message", "Fix issue"),
                "files": [finding["file"]] if finding.get("file") else [],
                "severity": finding.get("severity", "medium"),
                "finding": finding,
            }
            tasks.append(task)
        return tasks

    def _finding_type_to_task_type(self, finding_type: str) -> str:
        """Map finding type to task type"""
        mapping = {
            "build_error": "fix",
            "test_failure": "fix",
            "skipped_test": "test",
            "todo": "feature",
            "unwrap_abuse": "refactor",
            "security": "security",
        }
        return mapping.get(finding_type, "fix")

    def _generate_task_id(self, task_dict: Dict, index: int) -> str:
        """Generate unique task ID based on domain, type, and file"""
        domain = task_dict.get("domain", "unknown")
        task_type = task_dict.get("type", "fix")
        files = task_dict.get("files", [])

        # Use file name if available
        if files:
            file_name = Path(files[0]).stem
            return f"{domain}-{task_type}-{index:04d}-{file_name}"
        else:
            return f"{domain}-{task_type}-{index:04d}"

    async def _llm_task_generation(
        self,
        vision: str,
        question: str = None,
    ) -> List[Dict]:
        """Use LLM to generate tasks from findings"""
        log("Generating tasks with LLM...")

        # Build prompt
        prompt = self._build_synthesis_prompt(vision, question)

        # Call Claude
        returncode, output = await run_claude_agent(
            prompt,
            cwd=str(self.project.root_path),
            max_turns=5,
            timeout=600,
        )

        if returncode != 0:
            log("LLM task generation failed, falling back to quick mode", "WARN")
            return self._quick_task_generation()

        # Parse tasks from output
        tasks = self._parse_llm_tasks(output)

        if not tasks:
            log("No tasks parsed from LLM, falling back to quick mode", "WARN")
            return self._quick_task_generation()

        log(f"LLM generated {len(tasks)} tasks")
        return tasks

    def _build_synthesis_prompt(self, vision: str, question: str = None) -> str:
        """Build the synthesis prompt for LLM"""
        findings_json = json.dumps(self.findings[:50], indent=2)  # Limit findings

        return f"""You are an RLM Brain analyzing a software project.

PROJECT: {self.project.name} ({self.project.display_name})
DOMAINS: {list(self.project.domains.keys())}

VISION DOCUMENT:
{vision[:5000] if vision else "No vision document available"}

ANALYSIS FINDINGS:
{findings_json}

{f"FOCUS: {question}" if question else ""}

TASK:
Generate HIGH-LEVEL FEATURES (not atomic tasks) from these findings.

IMPORTANT - MIT CSAIL RLM Pattern:
- Brain generates FEATURES/EPICS (broad scope, multiple files)
- FRACTAL system will decompose into atomic subtasks
- Group related findings into single features
- Think like a Product Owner, not a developer

Example transformations:
- 10 "null check" findings → 1 feature "Implement robust null safety across codebase"
- 5 "hardcoded value" findings → 1 feature "Externalize configuration to environment"
- 8 "missing test" findings → 1 feature "Achieve 80% test coverage for X module"

OUTPUT FORMAT (JSON array):
[
  {{
    "type": "feature|epic|refactor|security",
    "domain": "rust|typescript|e2e|...",
    "description": "High-level feature description (will be decomposed by FRACTAL)",
    "files": ["multiple/files/can/be/listed.rs", "another/file.ts"],
    "severity": "critical|high|medium|low",
    "acceptance_criteria": ["All related issues fixed", "Tests pass", "Build succeeds"],
    "estimated_subtasks": 3-10
  }}
]

Generate FEATURES (not atomic tasks) now:"""

    def _parse_llm_tasks(self, output: str) -> List[Dict]:
        """Parse tasks from LLM output"""
        try:
            # Find JSON array in output
            match = re.search(r"\[\s*\{.*?\}\s*\]", output, re.DOTALL)
            if match:
                return json.loads(match.group())
        except json.JSONDecodeError:
            pass

        # Try to find individual JSON objects
        tasks = []
        for match in re.finditer(r"\{[^{}]*\"type\"[^{}]*\}", output):
            try:
                task = json.loads(match.group())
                if "description" in task:
                    tasks.append(task)
            except json.JSONDecodeError:
                continue

        return tasks

    def get_status(self) -> Dict:
        """Get current brain status"""
        tasks = self.task_store.get_tasks_by_project(self.project.id)
        status_counts = {}
        for task in tasks:
            status = task.status
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "project": self.project.name,
            "total_tasks": len(tasks),
            "by_status": status_counts,
            "findings_count": len(self.findings),
        }


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="RLM Brain - Project Analyzer")
    parser.add_argument("--project", "-p", help="Project name")
    parser.add_argument("--question", "-q", help="Focus question")
    parser.add_argument("--domain", "-d", help="Specific domain to analyze")
    parser.add_argument("--quick", action="store_true", help="Quick mode (no LLM)")
    parser.add_argument("--status", action="store_true", help="Show status only")

    args = parser.parse_args()

    brain = RLMBrain(args.project)

    if args.status:
        status = brain.get_status()
        print(json.dumps(status, indent=2))
        return

    domains = [args.domain] if args.domain else None

    tasks = asyncio.run(brain.run(
        question=args.question,
        domains=domains,
        quick=args.quick,
    ))

    print(f"\nCreated {len(tasks)} tasks")
    for task in tasks[:10]:
        print(f"  - [{task.domain}] {task.description[:60]}...")


if __name__ == "__main__":
    main()
