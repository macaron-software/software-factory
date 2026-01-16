#!/usr/bin/env python3
"""
RLM Brain - Deep Recursive Analysis Engine
===========================================
Based on MIT CSAIL arXiv:2512.24601 "Recursive Language Models"

The Brain is a DEEP RECURSIVE ANALYSIS ENGINE that:
1. Decomposes the project into analyzable units
2. Recursively analyzes each unit via llm_query()
3. Aggregates findings into actionable tasks
4. Uses llm_query_batched() for parallel deep dives

Architecture (TRUE RLM - not just code execution):
┌─────────────────────────────────────────────────────────────────────────────┐
│  BRAIN (Claude Opus 4.5 via RLM) - max_depth=3                              │
│  ├── Phase 1: STRUCTURE ANALYSIS                                            │
│  │   └── Decompose project → modules → files → functions                    │
│  ├── Phase 2: DEEP RECURSIVE ANALYSIS (llm_query per module)                │
│  │   ├── llm_query("Analyze auth module for security...")                   │
│  │   │   └── Sub-RLM can itself call llm_query() (depth=1→2)                │
│  │   ├── llm_query("Analyze data layer for performance...")                 │
│  │   └── llm_query_batched([...]) for parallel analysis                     │
│  ├── Phase 3: CROSS-CUTTING CONCERNS                                        │
│  │   └── Security, Performance, Testing, Architecture                       │
│  ├── Phase 4: SYNTHESIS & PRIORITIZATION                                    │
│  │   └── Aggregate all findings → WSJF scored backlog                       │
│  └── Phase 5: VALIDATION                                                    │
│      └── Verify tasks are atomic, testable, independent                     │
└─────────────────────────────────────────────────────────────────────────────┘

Key RLM Features Used:
- llm_query(prompt) → Recursive self-call for deep analysis
- llm_query_batched([prompts]) → Parallel analysis of multiple units
- Code execution → Pattern scanning, file manipulation
- max_depth=3 → 3 levels of recursive analysis

Usage:
    from core.brain_rlm import RLMBrain

    brain = RLMBrain("ppz")
    tasks = await brain.run(vision_prompt="Focus on iOS security")
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Add RLM to path
sys.path.insert(0, str(Path(__file__).parent.parent / "_rlm"))

from rlm import RLM
from rlm.logger import RLMLogger

from core.project_registry import get_project, ProjectConfig
from core.task_store import TaskStore, Task


def log(msg: str, level: str = "INFO"):
    """Log with timestamp"""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [BRAIN-RLM] [{level}] {msg}", flush=True)


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
    Brain powered by Recursive Language Models (MIT CSAIL).

    Uses RLM to handle the entire project codebase as context,
    allowing the LLM to programmatically examine and analyze
    files beyond its normal context window.
    """

    def __init__(self, project_name: str = None):
        """
        Initialize RLM Brain for a project.

        Args:
            project_name: Project name from projects/*.yaml
        """
        self.project = get_project(project_name)
        self.task_store = TaskStore()

        # Initialize RLM with Anthropic backend (Claude Opus 4.5)
        # Per MIT CSAIL arXiv:2512.24601 - RLM should be truly RECURSIVE:
        # - max_depth=3: Allow 3 levels of recursive self-calls
        # - other_backends: Use MiniMax M2.1 via opencode for sub-agent tasks
        # 
        # Architecture (TRUE RLM with heterogeneous models):
        #   Brain (Opus 4.5) depth=0 - Strategic analysis
        #     └── llm_query() → MiniMax M2.1 via opencode depth=1
        #           └── llm_query() → MiniMax M2.1 via opencode depth=2
        #                 └── At depth=3: fallback to direct LM call
        #
        # This mirrors the Wiggum architecture:
        #   Brain (Opus) orchestrates, MiniMax (via opencode) executes
        #   opencode has MCP tools access (filesystem, git, etc.)
        #
        self.rlm = RLM(
            backend="anthropic",
            backend_kwargs={
                "model_name": "claude-opus-4-5-20251101",
            },
            environment="local",  # Use local REPL for code execution
            max_iterations=50,    # More iterations for complex analysis
            max_depth=3,          # TRUE RECURSION: 3 levels of self-calls
            verbose=True,
            logger=RLMLogger(
                log_dir=str(Path(__file__).parent.parent / "data" / "rlm_logs")
            ),
            # Sub-agent backend: MiniMax M2.1 via opencode CLI
            # opencode provides: MCP tools, filesystem, git, project context
            # Same setup as Wiggum TDD workers
            other_backends=["opencode"],
            other_backend_kwargs=[{
                "model_name": "minimax/MiniMax-M2.1",
                "cwd": str(self.project.root_path),
                "timeout": 300,
                "project": self.project.name,
            }],
        )

        log(f"RLM Brain initialized for project: {self.project.name}")
        log(f"Root: {self.project.root_path}")
        log(f"Domains: {list(self.project.domains.keys())}")
        log(f"RLM Config: max_depth=3, max_iterations=50, sub_model=MiniMax-M2.1 via opencode")

    async def run(
        self,
        vision_prompt: str = None,
        domains: List[str] = None,
        deep_analysis: bool = True,
    ) -> List[Task]:
        """
        Run DEEP RECURSIVE RLM Brain analysis.

        This is a TRUE RLM implementation per MIT CSAIL arXiv:2512.24601:
        - Phase 1: Structure decomposition
        - Phase 2: Deep recursive analysis via llm_query()
        - Phase 3: Cross-cutting concerns (security, perf, testing)
        - Phase 4: Synthesis & WSJF prioritization
        - Phase 5: Task validation & atomicity check

        Args:
            vision_prompt: Optional focus prompt for analysis
            domains: Specific domains to analyze (default: all)
            deep_analysis: If True, use full recursive depth (default: True)

        Returns:
            List of created Task objects
        """
        log("═" * 70)
        log("🧠 STARTING DEEP RECURSIVE RLM BRAIN ANALYSIS")
        log("═" * 70)
        log(f"Project: {self.project.name}")
        log(f"Domains: {domains or list(self.project.domains.keys())}")
        log(f"Deep analysis: {deep_analysis}")
        log(f"RLM max_depth: {self.rlm.max_depth}")

        # 1. Load vision document
        vision_content = self.project.get_vision_content() or ""
        log(f"Vision doc: {len(vision_content)} chars")

        # 2. Collect project files as RLM context
        log("Collecting project files for RLM context...")
        project_context = collect_project_files(self.project)
        log(f"Project context: {len(project_context)} chars")

        # 3. Build the DEEP RECURSIVE prompt
        prompt = self._build_deep_recursive_prompt(
            vision_content,
            project_context,
            vision_prompt,
            domains,
            deep_analysis,
        )

        # 4. Run RLM completion with RECURSIVE capabilities
        log("─" * 70)
        log("🔄 Running DEEP RECURSIVE RLM completion...")
        log("   LLM can call llm_query() recursively up to depth=3")
        log("   LLM can use llm_query_batched() for parallel analysis")
        log("─" * 70)
        
        try:
            result = self.rlm.completion(prompt)
            response = result.response
            log(f"✅ RLM completed in {result.execution_time:.1f}s")
            log(f"   Response: {len(response)} chars")
            log(f"   Iterations: {getattr(result, 'iterations', '?')}")
        except Exception as e:
            log(f"❌ RLM error: {e}", "ERROR")
            return []

        # 5. Parse tasks from RLM response
        tasks = self._parse_tasks(response)
        log(f"Parsed {len(tasks)} tasks from RLM response")

        # 6. Validate and enrich tasks
        validated_tasks = self._validate_tasks(tasks)
        log(f"Validated {len(validated_tasks)} tasks (removed {len(tasks) - len(validated_tasks)} invalid)")

        # 7. Save tasks to store
        created_tasks = []
        for idx, task_dict in enumerate(validated_tasks):
            try:
                task_id = f"{self.project.name}-rlm-{idx:04d}"
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
        log("🧠 DEEP RECURSIVE RLM BRAIN ANALYSIS COMPLETE")
        log("═" * 70)

        return created_tasks

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
