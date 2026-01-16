#!/usr/bin/env python3
"""
FRACTAL Decomposition - MIT CSAIL Recursive Language Model
==========================================================
Based on MIT CSAIL arXiv:2512.24601 "Recursive Language Models"

Automatically decomposes large tasks into atomic sub-tasks to prevent
partial/incomplete code generation.

Thresholds (configurable per project):
- max_files: 5 (more files = decompose)
- max_loc: 400 (more LOC estimate = decompose)
- max_items: 10 (more acceptance criteria = decompose)
- max_depth: 3 (recursion limit)

Usage:
    from core.fractal import FractalDecomposer

    decomposer = FractalDecomposer(project_config)
    if decomposer.should_decompose(task):
        subtasks = await decomposer.decompose(task)
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path


def log(msg: str, level: str = "INFO"):
    """Log with timestamp"""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [FRACTAL] [{level}] {msg}", flush=True)


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class FractalConfig:
    """FRACTAL decomposition thresholds"""
    max_files: int = 5        # Max files touched per atomic task
    max_loc: int = 400        # Max LOC estimate per task
    max_items: int = 10       # Max acceptance criteria/items
    max_depth: int = 3        # Max recursion depth
    enabled: bool = True


def load_fractal_config(project_config: Any = None) -> FractalConfig:
    """Load FRACTAL config from project configuration"""
    if project_config is None:
        return FractalConfig()

    # Support both ProjectConfig and dict
    if hasattr(project_config, "fractal"):
        fc = project_config.fractal
    elif isinstance(project_config, dict):
        fc = project_config.get("fractal", {})
    else:
        return FractalConfig()

    if isinstance(fc, dict):
        return FractalConfig(
            max_files=fc.get("max_files", 5),
            max_loc=fc.get("max_loc", 400),
            max_items=fc.get("max_items", 10),
            max_depth=fc.get("max_depth", 3),
            enabled=fc.get("enabled", True),
        )

    return FractalConfig()


# ============================================================================
# TASK COMPLEXITY ANALYSIS
# ============================================================================

@dataclass
class ComplexityAnalysis:
    """Analysis result for task complexity"""
    files_count: int = 0
    loc_estimate: int = 0
    items_count: int = 0
    current_depth: int = 0
    exceeds_files: bool = False
    exceeds_loc: bool = False
    exceeds_items: bool = False
    exceeds_depth: bool = False

    @property
    def should_decompose(self) -> bool:
        """Returns True if any threshold is exceeded"""
        return (
            (self.exceeds_files or self.exceeds_loc or self.exceeds_items)
            and not self.exceeds_depth
        )

    @property
    def reason(self) -> str:
        """Human-readable reason for decomposition"""
        reasons = []
        if self.exceeds_files:
            reasons.append(f"files={self.files_count}")
        if self.exceeds_loc:
            reasons.append(f"loc={self.loc_estimate}")
        if self.exceeds_items:
            reasons.append(f"items={self.items_count}")
        return ", ".join(reasons) if reasons else "within limits"


def analyze_complexity(
    task: Dict[str, Any],
    config: FractalConfig,
    current_depth: int = 0,
) -> ComplexityAnalysis:
    """
    Analyze task complexity against FRACTAL thresholds.

    Task dict should contain:
    - files: List[str] - files to be modified
    - description: str - task description (used for LOC estimation)
    - acceptance_criteria: List[str] - or any items list
    - context: Dict - optional enriched context
    """
    # Extract file count
    files = task.get("files", [])
    if isinstance(files, str):
        files = [files]
    files_count = len(files)

    # Estimate LOC from description and context
    description = task.get("description", "")
    context = task.get("context", {})
    loc_estimate = _estimate_loc(description, context)

    # Count acceptance criteria or items
    items = (
        task.get("acceptance_criteria", []) or
        task.get("items", []) or
        task.get("criteria", []) or
        []
    )
    if isinstance(items, str):
        # Parse from description if comma/newline separated
        items = [i.strip() for i in re.split(r"[,\n]", items) if i.strip()]
    items_count = len(items)

    return ComplexityAnalysis(
        files_count=files_count,
        loc_estimate=loc_estimate,
        items_count=items_count,
        current_depth=current_depth,
        exceeds_files=files_count > config.max_files,
        exceeds_loc=loc_estimate > config.max_loc,
        exceeds_items=items_count > config.max_items,
        exceeds_depth=current_depth >= config.max_depth,
    )


def _estimate_loc(description: str, context: Dict) -> int:
    """
    Estimate lines of code from task description and context.

    Heuristics:
    - Base: 50 LOC for simple tasks
    - +50 for each "and" or "also"
    - +100 for "refactor" or "restructure"
    - +100 for file content in context (already substantial)
    """
    estimate = 50  # Base estimate

    desc_lower = description.lower()

    # Complexity indicators in description
    if " and " in desc_lower:
        estimate += 50 * desc_lower.count(" and ")
    if " also " in desc_lower:
        estimate += 50 * desc_lower.count(" also ")
    if "refactor" in desc_lower or "restructure" in desc_lower:
        estimate += 100
    if "implement" in desc_lower:
        estimate += 75
    if "test" in desc_lower:
        estimate += 50

    # Context-based adjustments
    if context:
        file_content = context.get("file_content", "")
        if file_content:
            # Existing code to modify
            existing_loc = len(file_content.split("\n"))
            estimate += min(existing_loc // 2, 200)  # Cap at 200 additional

        imports = context.get("imports", [])
        if len(imports) > 10:
            estimate += 50  # Complex file

        types_defined = context.get("types_defined", [])
        if len(types_defined) > 5:
            estimate += 50  # Complex types

    return estimate


# ============================================================================
# FRACTAL DECOMPOSER
# ============================================================================

class FractalDecomposer:
    """
    FRACTAL decomposition engine.

    Decomposes large tasks into atomic sub-tasks that fit within thresholds.
    Uses LLM for intelligent decomposition when available.
    """

    def __init__(
        self,
        project_config: Any = None,
        llm_client: Any = None,
    ):
        """
        Initialize decomposer.

        Args:
            project_config: ProjectConfig from project_registry
            llm_client: Optional LLMClient for intelligent decomposition
        """
        self.config = load_fractal_config(project_config)
        self.llm_client = llm_client

    def should_decompose(
        self,
        task: Dict[str, Any],
        current_depth: int = 0,
    ) -> Tuple[bool, ComplexityAnalysis]:
        """
        Check if task should be decomposed.

        Returns:
            Tuple of (should_decompose: bool, analysis: ComplexityAnalysis)
        """
        if not self.config.enabled:
            return False, ComplexityAnalysis()

        analysis = analyze_complexity(task, self.config, current_depth)
        return analysis.should_decompose, analysis

    async def decompose(
        self,
        task: Dict[str, Any],
        current_depth: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Decompose a task into atomic sub-tasks.

        Uses LLM if available for intelligent decomposition,
        otherwise falls back to rule-based decomposition.

        Args:
            task: Task dict with description, files, etc.
            current_depth: Current recursion depth

        Returns:
            List of sub-task dicts
        """
        should_decompose, analysis = self.should_decompose(task, current_depth)

        if not should_decompose:
            log(f"Task within limits ({analysis.reason}), no decomposition needed")
            return [task]

        log(f"Decomposing task (depth={current_depth}, {analysis.reason})")

        # Try LLM decomposition first
        if self.llm_client:
            subtasks = await self._llm_decompose(task, analysis)
            if subtasks:
                return subtasks

        # Fallback to rule-based decomposition
        return self._rule_based_decompose(task, analysis)

    async def _llm_decompose(
        self,
        task: Dict[str, Any],
        analysis: ComplexityAnalysis,
    ) -> Optional[List[Dict[str, Any]]]:
        """Decompose using LLM for intelligent splitting"""
        try:
            prompt = self._build_decomposition_prompt(task, analysis)
            response = await self.llm_client.query(prompt, role="sub")

            # Parse subtasks from response
            subtasks = self._parse_subtasks(response, task)
            if subtasks and len(subtasks) > 1:
                log(f"LLM decomposed into {len(subtasks)} sub-tasks")
                return subtasks

        except Exception as e:
            log(f"LLM decomposition failed: {e}", "WARN")

        return None

    def _build_decomposition_prompt(
        self,
        task: Dict[str, Any],
        analysis: ComplexityAnalysis,
    ) -> str:
        """Build prompt for LLM decomposition"""
        return f"""You are a task decomposition expert. Break down this large task into 2-4 smaller, atomic sub-tasks.

ORIGINAL TASK:
- Description: {task.get('description', '')}
- Files: {task.get('files', [])}
- Type: {task.get('type', 'fix')}
- Domain: {task.get('domain', 'unknown')}

COMPLEXITY (exceeds thresholds):
- Files: {analysis.files_count} (max {self.config.max_files})
- Estimated LOC: {analysis.loc_estimate} (max {self.config.max_loc})
- Items: {analysis.items_count} (max {self.config.max_items})

RULES for sub-tasks:
1. Each sub-task must be ATOMIC (one logical change)
2. Each sub-task should touch max {self.config.max_files} files
3. Each sub-task should be ~{self.config.max_loc // 2} LOC or less
4. Sub-tasks must be INDEPENDENT (can be done in parallel)
5. No overlapping file modifications

RESPOND IN JSON:
{{
  "subtasks": [
    {{
      "description": "Clear, specific sub-task description",
      "files": ["file1.rs"],
      "type": "fix|feature|refactor|test",
      "acceptance_criteria": ["criterion 1", "criterion 2"]
    }}
  ]
}}
"""

    def _parse_subtasks(
        self,
        response: str,
        parent_task: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Parse subtasks from LLM response"""
        try:
            # Find JSON in response
            json_match = re.search(r'\{[^{}]*"subtasks"[^{}]*\[.*?\]\s*\}', response, re.DOTALL)
            if not json_match:
                return []

            data = json.loads(json_match.group())
            subtasks = []

            for i, st in enumerate(data.get("subtasks", [])):
                subtask = {
                    "id": f"{parent_task.get('id', 'task')}_sub{i+1}",
                    "parent_id": parent_task.get("id"),
                    "description": st.get("description", ""),
                    "files": st.get("files", []),
                    "type": st.get("type", parent_task.get("type", "fix")),
                    "domain": parent_task.get("domain", "unknown"),
                    "acceptance_criteria": st.get("acceptance_criteria", []),
                    "context": parent_task.get("context", {}),
                    "fractal_depth": parent_task.get("fractal_depth", 0) + 1,
                }
                subtasks.append(subtask)

            return subtasks

        except (json.JSONDecodeError, KeyError) as e:
            log(f"Failed to parse subtasks: {e}", "WARN")
            return []

    def _rule_based_decompose(
        self,
        task: Dict[str, Any],
        analysis: ComplexityAnalysis,
    ) -> List[Dict[str, Any]]:
        """
        Rule-based decomposition fallback.

        Strategies:
        1. Split by files (if exceeds_files)
        2. Split by acceptance criteria (if exceeds_items)
        3. Split description by conjunctions (if exceeds_loc)
        """
        subtasks = []
        parent_id = task.get("id", "task")
        base_task = {
            "type": task.get("type", "fix"),
            "domain": task.get("domain", "unknown"),
            "context": task.get("context", {}),
            "parent_id": parent_id,
            "fractal_depth": task.get("fractal_depth", 0) + 1,
        }

        # Strategy 1: Split by files
        if analysis.exceeds_files:
            files = task.get("files", [])
            chunk_size = self.config.max_files
            for i in range(0, len(files), chunk_size):
                chunk_files = files[i:i + chunk_size]
                subtasks.append({
                    **base_task,
                    "id": f"{parent_id}_files{i // chunk_size + 1}",
                    "description": f"{task.get('description', '')} (files: {', '.join(chunk_files)})",
                    "files": chunk_files,
                })
            log(f"Split by files into {len(subtasks)} sub-tasks")
            return subtasks

        # Strategy 2: Split by acceptance criteria
        if analysis.exceeds_items:
            criteria = task.get("acceptance_criteria", [])
            chunk_size = self.config.max_items
            for i in range(0, len(criteria), chunk_size):
                chunk_criteria = criteria[i:i + chunk_size]
                subtasks.append({
                    **base_task,
                    "id": f"{parent_id}_criteria{i // chunk_size + 1}",
                    "description": f"{task.get('description', '')} (criteria {i+1}-{i+len(chunk_criteria)})",
                    "files": task.get("files", []),
                    "acceptance_criteria": chunk_criteria,
                })
            log(f"Split by criteria into {len(subtasks)} sub-tasks")
            return subtasks

        # Strategy 3: Split by description conjunctions
        if analysis.exceeds_loc:
            description = task.get("description", "")
            parts = re.split(r"\s+(?:and|also|additionally)\s+", description, flags=re.IGNORECASE)
            if len(parts) > 1:
                for i, part in enumerate(parts):
                    subtasks.append({
                        **base_task,
                        "id": f"{parent_id}_part{i + 1}",
                        "description": part.strip(),
                        "files": task.get("files", []),
                    })
                log(f"Split by description into {len(subtasks)} sub-tasks")
                return subtasks

        # No decomposition possible, return original (will be at depth limit)
        log("No decomposition strategy applicable, returning original", "WARN")
        return [task]

    async def decompose_recursive(
        self,
        task: Dict[str, Any],
        current_depth: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Recursively decompose task until all sub-tasks are atomic.

        Returns flat list of all atomic tasks.
        """
        if current_depth >= self.config.max_depth:
            log(f"Max depth {self.config.max_depth} reached", "WARN")
            return [task]

        should_decompose, analysis = self.should_decompose(task, current_depth)

        if not should_decompose:
            return [task]

        subtasks = await self.decompose(task, current_depth)

        # Recursively check each subtask
        all_atomic = []
        for subtask in subtasks:
            atomic_tasks = await self.decompose_recursive(
                subtask,
                current_depth + 1,
            )
            all_atomic.extend(atomic_tasks)

        return all_atomic


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def should_decompose(
    task: Dict[str, Any],
    config: Any = None,
    current_depth: int = 0,
) -> bool:
    """Quick check if task should be decomposed"""
    decomposer = FractalDecomposer(config)
    should, _ = decomposer.should_decompose(task, current_depth)
    return should


async def decompose_task(
    task: Dict[str, Any],
    config: Any = None,
    llm_client: Any = None,
    recursive: bool = True,
) -> List[Dict[str, Any]]:
    """
    Decompose a task into atomic sub-tasks.

    Args:
        task: Task dict
        config: Project config
        llm_client: Optional LLM client for intelligent decomposition
        recursive: If True, recursively decompose until all atomic

    Returns:
        List of atomic sub-tasks
    """
    decomposer = FractalDecomposer(config, llm_client)

    if recursive:
        return await decomposer.decompose_recursive(task)
    else:
        return await decomposer.decompose(task)


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="FRACTAL Task Decomposition")
    parser.add_argument("--test", action="store_true", help="Run test")
    parser.add_argument("--task", type=str, help="Task JSON file to analyze")

    args = parser.parse_args()

    if args.test:
        # Test with sample task
        sample_task = {
            "id": "test-001",
            "description": "Refactor authentication module and also update user service and additionally fix the session handling",
            "files": [
                "src/auth/mod.rs",
                "src/auth/jwt.rs",
                "src/auth/session.rs",
                "src/services/user.rs",
                "src/services/session.rs",
                "tests/auth_test.rs",
            ],
            "type": "refactor",
            "domain": "rust",
            "acceptance_criteria": [
                "All tests pass",
                "No security vulnerabilities",
                "Backwards compatible API",
                "Documentation updated",
                "Performance maintained",
            ],
        }

        print("\n=== FRACTAL Decomposition Test ===")
        print(f"Original task: {sample_task['description'][:50]}...")
        print(f"Files: {len(sample_task['files'])}")
        print(f"Criteria: {len(sample_task['acceptance_criteria'])}")

        config = FractalConfig()
        decomposer = FractalDecomposer()

        should, analysis = decomposer.should_decompose(sample_task)
        print(f"\nAnalysis:")
        print(f"  Files: {analysis.files_count}/{config.max_files}")
        print(f"  LOC estimate: {analysis.loc_estimate}/{config.max_loc}")
        print(f"  Items: {analysis.items_count}/{config.max_items}")
        print(f"  Should decompose: {should} ({analysis.reason})")

        if should:
            subtasks = asyncio.run(decomposer.decompose(sample_task))
            print(f"\nDecomposed into {len(subtasks)} sub-tasks:")
            for st in subtasks:
                print(f"  - {st.get('id')}: {st.get('description', '')[:50]}...")
                print(f"    Files: {st.get('files', [])}")

    elif args.task:
        # Analyze task from file
        with open(args.task) as f:
            task = json.load(f)

        decomposer = FractalDecomposer()
        should, analysis = decomposer.should_decompose(task)

        print(f"Task: {task.get('id', 'unknown')}")
        print(f"Should decompose: {should}")
        print(f"Reason: {analysis.reason}")

    else:
        parser.print_help()
