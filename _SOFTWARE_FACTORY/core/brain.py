#!/usr/bin/env python3
"""
RLM Brain - Deep Recursive Analysis Engine with MCP
====================================================
Based on MIT CSAIL arXiv:2512.24601 "Recursive Language Models"

Uses MCP (Model Context Protocol) for project navigation:
- Opus 4.5 via `claude` CLI with MCP tools
- MiniMax M2.1 via `opencode` with MCP tools
- Both can navigate the codebase using lrm_* tools

COST TIER ARCHITECTURE (like GPT-5 → GPT-5-mini in paper):
  depth=0: Opus 4.5 ($$$) - Strategic orchestration via `claude` + MCP
  depth=1: MiniMax M2.1 ($$) - Deep analysis via `opencode` + MCP  
  depth=2: MiniMax M2.1 ($) - Sub-analysis via `opencode` + MCP
  depth=3: Qwen 30B local (free) - Simple queries

MCP Tools available (from mcp_lrm):
- lrm_locate: Find files matching pattern
- lrm_summarize: Summarize file content
- lrm_conventions: Get domain conventions
- lrm_examples: Get example code
- lrm_build: Run build/test commands

Usage:
    from core.brain import RLMBrain

    brain = RLMBrain("ppz")
    tasks = await brain.run(vision_prompt="Focus on iOS security")
"""

import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.project_registry import get_project, ProjectConfig
from core.task_store import TaskStore, Task
from core.llm_client import run_opencode


def log(msg: str, level: str = "INFO"):
    """Log with timestamp"""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [BRAIN] [{level}] {msg}", flush=True)


# ============================================================================
# FILE COLLECTOR
# ============================================================================

def collect_project_files(project: ProjectConfig, max_chars: int = 500000) -> str:
    """
    Collect all project files as a single context string.

    This becomes the RLM context that the LLM can programmatically examine.
    """
    files_content = []
    total_chars = 0

    # Patterns to exclude
    exclude_patterns = {
        '.git', 'node_modules', 'target', '__pycache__', '.pyc',
        'dist', 'build', '.next', '.svelte-kit', 'coverage',
        '.DS_Store', '.env', 'Thumbs.db', '*.lock', 'package-lock.json'
    }

    def should_exclude(path: Path) -> bool:
        for pattern in exclude_patterns:
            if pattern in str(path):
                return True
        return False

    # Collect files from each domain
    for domain_name, domain_config in project.domains.items():
        paths = domain_config.get("paths", [])
        extensions = domain_config.get("extensions", [])

        for path_str in paths:
            domain_path = project.root_path / path_str
            if not domain_path.exists():
                continue

            for ext in extensions:
                for file in domain_path.rglob(f"*{ext}"):
                    if should_exclude(file):
                        continue

                    try:
                        content = file.read_text(errors='ignore')
                        rel_path = str(file.relative_to(project.root_path))

                        # Limit per file
                        if len(content) > 10000:
                            content = content[:10000] + "\n... [truncated]"

                        file_entry = f"\n{'='*60}\nFILE: {rel_path}\n{'='*60}\n{content}\n"

                        if total_chars + len(file_entry) > max_chars:
                            break

                        files_content.append(file_entry)
                        total_chars += len(file_entry)

                    except Exception as e:
                        continue

    log(f"Collected {len(files_content)} files ({total_chars} chars)")
    return "".join(files_content)


# ============================================================================
# RLM BRAIN
# ============================================================================

class RLMBrain:
    """
    Brain powered by Recursive Language Models (MIT CSAIL) with MCP.

    Uses `claude` CLI and `opencode` with MCP tools to navigate and analyze
    the entire project codebase.
    
    COST TIER ARCHITECTURE:
      depth=0: Opus 4.5 via `claude` + MCP ($$$)
      depth=1-2: MiniMax M2.1 via `opencode` + MCP ($$)
      depth=3: Qwen 30B local (free fallback)
    """

    def __init__(self, project_name: str = None):
        """
        Initialize Brain for a project.

        Args:
            project_name: Project name from projects/*.yaml
        """
        self.project = get_project(project_name)
        self.task_store = TaskStore()
        self.max_depth = 3
        self.current_depth = 0

        log(f"Brain initialized for project: {self.project.name}")
        log(f"Root: {self.project.root_path}")
        log(f"Domains: {list(self.project.domains.keys())}")
        log(f"Cost tiers: Opus(d0) → MiniMax(d1-2) → Qwen(d3)")

    async def run(
        self,
        vision_prompt: str = None,
        domains: List[str] = None,
        deep_analysis: bool = True,
    ) -> List[Task]:
        """
        Run DEEP RECURSIVE Brain analysis with MCP.

        Uses `claude` CLI with MCP tools for deep project navigation.
        Sub-analyses delegated to `opencode` with MiniMax.

        Args:
            vision_prompt: Optional focus prompt for analysis
            domains: Specific domains to analyze (default: all)
            deep_analysis: If True, use full recursive depth

        Returns:
            List of created Task objects
        """
        log("═" * 70)
        log("🧠 STARTING DEEP RECURSIVE BRAIN ANALYSIS WITH MCP")
        log("═" * 70)
        log(f"Project: {self.project.name}")
        log(f"Domains: {domains or list(self.project.domains.keys())}")
        log(f"Deep analysis: {deep_analysis}")

        # 1. Load vision document
        vision_content = self.project.get_vision_content() or ""
        log(f"Vision doc: {len(vision_content)} chars")

        # 2. Build the analysis prompt
        prompt = self._build_analysis_prompt(
            vision_content,
            vision_prompt,
            domains,
            deep_analysis,
        )

        # 3. Run analysis with Opus via `claude` CLI
        # Claude has access to MCP tools for project navigation
        log("─" * 70)
        log("🔄 Running Opus analysis via `claude` CLI + MCP...")
        log("─" * 70)
        
        response = await self._call_claude(prompt)
        
        if not response:
            log("❌ Claude analysis failed", "ERROR")
            return []

        log(f"✅ Analysis complete: {len(response)} chars")

        # 4. Parse tasks from response
        tasks = self._parse_tasks(response)
        log(f"Parsed {len(tasks)} tasks")

        # 5. Validate tasks
        validated_tasks = self._validate_tasks(tasks)
        log(f"Validated {len(validated_tasks)} tasks")

        # 6. If deep analysis, run sub-analyses with MiniMax
        if deep_analysis and validated_tasks:
            validated_tasks = await self._deep_analyze_tasks(validated_tasks)

        # 7. Save tasks to store
        created_tasks = []
        for idx, task_dict in enumerate(validated_tasks):
            try:
                task_id = f"{self.project.name}-brain-{idx:04d}"
                task_obj = Task(
                    id=task_id,
                    project_id=self.project.id,
                    type=task_dict.get("type", "fix"),
                    domain=task_dict.get("domain", "unknown"),
                    description=task_dict.get("description", ""),
                    files=task_dict.get("files", []),
                    context=task_dict,
                    wsjf_score=task_dict.get("wsjf_score", 5.0),
                )
                self.task_store.create_task(task_obj)
                created_tasks.append(task_obj)
            except Exception as e:
                log(f"Failed to create task: {e}", "ERROR")

        log(f"Created {len(created_tasks)} tasks in store")
        log("═" * 70)
        log("🧠 BRAIN ANALYSIS COMPLETE")
        log("═" * 70)

        return created_tasks

    async def _call_claude(self, prompt: str, timeout: int = 600) -> Optional[str]:
        """
        Call Claude Opus via `claude` CLI.
        
        Claude has access to MCP tools configured in ~/.claude/settings.json
        including our mcp_lrm tools for project navigation.
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "claude",
                "-p",  # Print mode (non-interactive)
                "--model", "claude-opus-4-5-20251101",
                "--max-turns", "10",  # Allow multiple tool calls
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.project.root_path),
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=prompt.encode()),
                timeout=timeout,
            )
            
            if proc.returncode == 0:
                return stdout.decode().strip()
            else:
                error = stderr.decode()[:500]
                log(f"Claude error: {error}", "ERROR")
                return None
                
        except asyncio.TimeoutError:
            log(f"Claude timeout ({timeout}s)", "ERROR")
            return None
        except FileNotFoundError:
            log("claude CLI not found", "ERROR")
            return None
        except Exception as e:
            log(f"Claude exception: {e}", "ERROR")
            return None

    async def _call_opencode(self, prompt: str, timeout: int = 300) -> Optional[str]:
        """
        Call MiniMax via `opencode` CLI.
        
        Used for sub-analyses (depth 1-2) to save cost.
        opencode has MCP tools access.
        """
        returncode, output = await run_opencode(
            prompt,
            model="minimax/MiniMax-M2.1",
            cwd=str(self.project.root_path),
            timeout=timeout,
            project=self.project.name,
        )
        
        if returncode == 0:
            return output
        else:
            log(f"opencode failed: {output[:200]}", "WARN")
            return None

    async def _deep_analyze_tasks(self, tasks: List[Dict]) -> List[Dict]:
        """
        Run deep analysis on tasks using MiniMax sub-agents.
        
        For each task, spawn a MiniMax sub-agent to:
        - Verify the issue exists
        - Identify exact files/lines
        - Suggest specific fixes
        """
        log(f"🔍 Running deep analysis on {len(tasks)} tasks with MiniMax...")
        
        enhanced_tasks = []
        
        for i, task in enumerate(tasks[:10]):  # Limit to 10 for cost
            log(f"  [{i+1}/{min(len(tasks), 10)}] Analyzing: {task.get('description', '')[:50]}...")
            
            prompt = f"""Analyze this task and provide detailed implementation guidance:

TASK:
- Type: {task.get('type', 'fix')}
- Domain: {task.get('domain', 'unknown')}
- Description: {task.get('description', '')}
- Files: {task.get('files', [])}

Use MCP tools to:
1. Locate the exact files involved (lrm_locate)
2. Read the current code (lrm_summarize)
3. Identify the exact lines to change

Respond with JSON:
{{
  "files": ["exact/file/paths.rs"],
  "changes": [
    {{"file": "path", "line": 42, "current": "...", "suggested": "..."}}
  ],
  "test_approach": "How to test this fix",
  "estimated_loc": 50
}}
"""
            
            result = await self._call_opencode(prompt, timeout=120)
            
            if result:
                # Try to extract enhanced info
                try:
                    import re
                    json_match = re.search(r'\{[^{}]*"files"[^{}]*\}', result, re.DOTALL)
                    if json_match:
                        enhanced = json.loads(json_match.group())
                        task.update({
                            "files": enhanced.get("files", task.get("files", [])),
                            "changes": enhanced.get("changes", []),
                            "test_approach": enhanced.get("test_approach", ""),
                            "estimated_loc": enhanced.get("estimated_loc", 50),
                            "deep_analyzed": True,
                        })
                except:
                    pass
            
            enhanced_tasks.append(task)
        
        # Add remaining tasks without deep analysis
        enhanced_tasks.extend(tasks[10:])
        
        return enhanced_tasks

    def _validate_tasks(self, tasks: List[Dict]) -> List[Dict]:
        """Validate tasks are atomic, testable, and have required fields."""
        validated = []
        for t in tasks:
            # Required fields
            if not t.get("description"):
                continue
            if len(t.get("description", "")) < 10:
                continue
            
            # Ensure atomicity (no "and also" patterns)
            desc = t.get("description", "").lower()
            if " and also " in desc or " additionally " in desc:
                # Task too complex, could be split but we'll let Wiggum handle it
                pass
            
            # Ensure files list
            if not t.get("files"):
                t["files"] = []
            
            # Ensure WSJF score
            if not t.get("wsjf_score"):
                t["wsjf_score"] = 5.0
            
            validated.append(t)
        
        return validated

    def _build_analysis_prompt(
        self,
        vision: str,
        focus: str = None,
        domains: List[str] = None,
        deep_analysis: bool = True,
    ) -> str:
        """Build analysis prompt for Claude with MCP tools."""

        domains_list = domains or list(self.project.domains.keys())
        vision_truncated = vision[:8000] if vision else "No vision document"

        return f'''You are a DEEP RECURSIVE ANALYSIS ENGINE for the "{self.project.name}" project.

IMPORTANT: You have access to MCP tools for project navigation. USE THEM:
- lrm_locate: Find files matching a pattern
- lrm_summarize: Get summary of file content
- lrm_conventions: Get coding conventions for a domain
- lrm_examples: Get example code
- lrm_build: Run build/test commands

══════════════════════════════════════════════════════════════════════════════
PROJECT: {self.project.name}
DOMAINS: {domains_list}
{f"FOCUS: {focus}" if focus else ""}
══════════════════════════════════════════════════════════════════════════════

VISION DOCUMENT:
{vision_truncated}

══════════════════════════════════════════════════════════════════════════════
YOUR MISSION: Deep recursive analysis
══════════════════════════════════════════════════════════════════════════════

1. Use MCP tools to explore the codebase:
   - lrm_locate("*.rs") to find Rust files
   - lrm_locate("*test*") to find test files
   - lrm_summarize("src/main.rs") to understand files

2. Analyze each domain for:
   - Security vulnerabilities
   - Performance issues
   - Missing tests
   - Code quality issues
   - Architecture violations

3. Generate ATOMIC tasks (one specific change each)

For each task, provide:
- type: fix|feature|refactor|test|security
- domain: one of {domains_list}
- description: Specific, actionable
- files: List of files to modify
- severity: critical|high|medium|low
- wsjf_score: 1-10

WSJF scoring:
- 10: Critical security/data loss, quick fix
- 8-9: High business impact
- 6-7: Important improvement
- 4-5: Nice to have
- 1-3: Minor polish

══════════════════════════════════════════════════════════════════════════════
OUTPUT FORMAT:
══════════════════════════════════════════════════════════════════════════════

After your analysis, output a JSON array:

```json
[
  {{"type": "security", "domain": "rust", "description": "Fix SQL injection in user_query()", "files": ["src/db.rs"], "severity": "critical", "wsjf_score": 9.5}},
  ...
]
```

BEGIN ANALYSIS NOW. Use MCP tools to explore the project!
'''

    def _build_deep_recursive_prompt(
        self,
        vision: str,
        project_context: str,
        focus: str = None,
        domains: List[str] = None,
        deep_analysis: bool = True,
    ) -> str:
        """Build the DEEP RECURSIVE RLM prompt."""

        domains_list = domains or list(self.project.domains.keys())
        
        # Truncate vision if too long
        vision_truncated = vision[:8000] if vision else "No vision document"

        return f'''You are a DEEP RECURSIVE ANALYSIS ENGINE based on MIT CSAIL arXiv:2512.24601 "Recursive Language Models".

You MUST use llm_query() for deep analysis - this is what makes RLM powerful!
You have max_depth=3 recursive calls available. USE THEM.

══════════════════════════════════════════════════════════════════════════════
PROJECT: {self.project.name}
DOMAINS: {domains_list}
{f"FOCUS: {focus}" if focus else ""}
══════════════════════════════════════════════════════════════════════════════

VISION DOCUMENT:
{vision_truncated}

══════════════════════════════════════════════════════════════════════════════
PROJECT CODEBASE (you can search/analyze this programmatically):
══════════════════════════════════════════════════════════════════════════════
{project_context}

══════════════════════════════════════════════════════════════════════════════
EXECUTE THIS 5-PHASE DEEP RECURSIVE ANALYSIS:
══════════════════════════════════════════════════════════════════════════════

PHASE 1: STRUCTURE DECOMPOSITION
────────────────────────────────
First, decompose the project into analyzable units:

```python
import re

# Extract all modules/files
files = re.findall(r'={10,}\\n// FILE: ([^\\n]+)', project_context)
print(f"Found {{len(files)}} files")

# Group by domain
modules = {{}}
for f in files:
    if '.rs' in f: modules.setdefault('rust', []).append(f)
    elif '.ts' in f or '.tsx' in f: modules.setdefault('typescript', []).append(f)
    elif '.swift' in f: modules.setdefault('swift', []).append(f)
    elif '.py' in f: modules.setdefault('python', []).append(f)

for domain, fs in modules.items():
    print(f"{{domain}}: {{len(fs)}} files")
```

PHASE 2: DEEP RECURSIVE ANALYSIS (USE llm_query!)
─────────────────────────────────────────────────
For EACH module/domain, call llm_query() for deep analysis:

```python
all_findings = []

# Example: Deep security analysis of authentication code
auth_code = # extract auth-related code from project_context
security_analysis = llm_query(f"""
You are a security expert. Analyze this authentication code for vulnerabilities:

<code>
{{auth_code[:5000]}}
</code>

List EACH vulnerability found with:
- Category (injection, auth bypass, data exposure, etc.)
- Severity (critical/high/medium/low)
- Exact location (file:line if possible)
- Recommended fix
- Code example of the fix

Be thorough and specific. This analysis will create security tasks.
""")
print("Security analysis:", security_analysis)
all_findings.append(("security", security_analysis))

# Example: Deep performance analysis
perf_code = # extract performance-critical code
perf_analysis = llm_query(f"""
You are a performance expert. Analyze this code for performance issues:

<code>
{{perf_code[:5000]}}
</code>

List EACH performance issue with:
- Type (N+1 query, memory leak, blocking I/O, etc.)
- Impact (latency, memory, CPU)
- Severity
- Recommended fix

Be thorough and specific.
""")
print("Performance analysis:", perf_analysis)
all_findings.append(("performance", perf_analysis))
```

PHASE 3: PARALLEL BATCH ANALYSIS (USE llm_query_batched!)
─────────────────────────────────────────────────────────
For multiple files, use parallel analysis:

```python
# Collect files that need analysis
files_to_analyze = []
for match in re.finditer(r'// FILE: ([^\\n]+)\\n(.*?)(?=// FILE:|$)', project_context, re.DOTALL):
    filename, content = match.groups()
    if len(content) > 500:  # Only non-trivial files
        files_to_analyze.append((filename, content[:3000]))

# Create analysis prompts
prompts = []
for filename, content in files_to_analyze[:10]:  # Limit to 10 for efficiency
    prompts.append(f"""
Analyze this file for issues:
FILE: {{filename}}
<code>
{{content}}
</code>

Return JSON: {{"issues": [{{"type": "...", "severity": "...", "description": "...", "line": ...}}]}}
""")

# Parallel analysis!
if prompts:
    results = llm_query_batched(prompts)
    for (filename, _), result in zip(files_to_analyze[:10], results):
        print(f"{{filename}}: {{result[:200]}}...")
        all_findings.append(("file_analysis", result))
```

PHASE 4: CROSS-CUTTING CONCERNS
───────────────────────────────
Analyze architecture-level issues:

```python
# Architecture analysis
arch_analysis = llm_query(f"""
Analyze the overall architecture of this codebase:

<structure>
{{str(modules)}}
</structure>

<sample_code>
{{project_context[:10000]}}
</sample_code>

Identify:
1. Architecture violations (circular deps, layer breaches)
2. Missing abstractions (code duplication patterns)
3. Testability issues (hard-coded deps, no interfaces)
4. Scalability concerns

For each issue, specify affected files and recommended refactoring.
""")
print("Architecture analysis:", arch_analysis)
all_findings.append(("architecture", arch_analysis))

# Testing coverage analysis
test_analysis = llm_query(f"""
Analyze testing coverage and quality:

<code>
{{project_context[:8000]}}
</code>

Identify:
1. Missing test coverage (which modules have no tests?)
2. Test quality issues (tests that don't actually test anything)
3. Missing integration tests
4. Missing edge case tests

Be specific about WHICH functions/modules need tests.
""")
print("Test analysis:", test_analysis)
all_findings.append(("testing", test_analysis))
```

PHASE 5: SYNTHESIS & TASK GENERATION
─────────────────────────────────────
Aggregate all findings into prioritized tasks:

```python
# Synthesize all findings into tasks
synthesis = llm_query(f"""
You are a technical lead. Based on these analysis findings, create a prioritized backlog:

<findings>
{{str(all_findings)}}
</findings>

Create ATOMIC tasks (one specific change each). For each task:
- type: fix|feature|refactor|test|security
- domain: {domains_list}
- description: Specific, actionable (what exactly to change)
- files: List of files to modify
- severity: critical|high|medium|low
- wsjf_score: 1-10 (based on value/effort ratio)
- acceptance_criteria: List of testable criteria

WSJF scoring guide:
- 10: Critical security/data loss risk, quick fix
- 8-9: High business impact, moderate effort
- 6-7: Important improvement, reasonable effort
- 4-5: Nice to have, low effort
- 1-3: Minor polish

Return ONLY valid JSON array:
[{{"type": "...", "domain": "...", "description": "...", "files": [...], "severity": "...", "wsjf_score": N, "acceptance_criteria": [...]}}]
""")
print(synthesis)
```

══════════════════════════════════════════════════════════════════════════════
FINAL OUTPUT REQUIREMENT:
══════════════════════════════════════════════════════════════════════════════

After completing ALL 5 phases, output the final task list as:

```json
[
  {{"type": "security", "domain": "rust", "description": "...", "files": ["..."], "severity": "critical", "wsjf_score": 9.5, "acceptance_criteria": ["..."]}},
  ...
]
```

BEGIN DEEP RECURSIVE ANALYSIS NOW. Use llm_query() extensively!
'''

    def _parse_tasks(self, response: str) -> List[Dict]:
        """Parse tasks from RLM response."""
        import re

        try:
            # Find JSON array in response
            match = re.search(r'```json\s*(\[.*?\])\s*```', response, re.DOTALL)
            if match:
                tasks = json.loads(match.group(1))
                return [t for t in tasks if isinstance(t, dict) and "description" in t]

            # Try finding raw JSON array
            match = re.search(r'\[\s*\{.*?"description".*?\}\s*\]', response, re.DOTALL)
            if match:
                return json.loads(match.group())

        except json.JSONDecodeError as e:
            log(f"JSON parse error: {e}", "WARN")

        return []

    def get_status(self) -> Dict:
        """Get current brain status."""
        tasks = self.task_store.get_tasks_by_project(self.project.id)
        status_counts = {}
        for task in tasks:
            status = task.status
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "project": self.project.name,
            "total_tasks": len(tasks),
            "by_status": status_counts,
        }

    def close(self):
        """Clean up RLM resources."""
        self.rlm.close()


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="RLM Brain - Project Analyzer")
    parser.add_argument("--project", "-p", help="Project name")
    parser.add_argument("--focus", "-f", help="Focus prompt")
    parser.add_argument("--domain", "-d", help="Specific domain")
    parser.add_argument("--status", action="store_true", help="Show status only")

    args = parser.parse_args()

    brain = RLMBrain(args.project)

    if args.status:
        status = brain.get_status()
        print(json.dumps(status, indent=2))
        return

    domains = [args.domain] if args.domain else None

    tasks = asyncio.run(brain.run(
        vision_prompt=args.focus,
        domains=domains,
    ))

    print(f"\nCreated {len(tasks)} tasks")
    for task in tasks[:10]:
        print(f"  - [{task.domain}] {task.description[:60]}...")

    brain.close()


if __name__ == "__main__":
    main()
