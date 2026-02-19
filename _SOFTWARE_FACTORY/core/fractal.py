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
    max_files: int = 3        # Max files touched per atomic task (was 5, lowered to prevent truncation)
    max_loc: int = 250        # Max LOC estimate per task (was 400, lowered to prevent truncation)
    max_items: int = 8        # Max acceptance criteria/items (was 10)
    max_depth: int = 3        # Max recursion depth
    enabled: bool = True
    force_level1: bool = True      # Always decompose depth=0 tasks
    min_subtasks: int = 0          # 0 = LLM can decide no split needed
    parallel_subagents: bool = True  # Run subtasks in parallel
    llm_first: bool = True         # Prefer LLM over rule-based decomposition


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
            force_level1=fc.get("force_level1", True),
            min_subtasks=fc.get("min_subtasks", 0),
            parallel_subagents=fc.get("parallel_subagents", True),
            llm_first=fc.get("llm_first", True),
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
    force_level1: bool = False  # NEW: Forced L1 decomposition

    @property
    def should_decompose(self) -> bool:
        """Returns True if any threshold is exceeded or force_level1"""
        return (
            self.force_level1 or
            (self.exceeds_files or self.exceeds_loc or self.exceeds_items)
        ) and not self.exceeds_depth

    @property
    def reason(self) -> str:
        """Human-readable reason for decomposition"""
        reasons = []
        if self.force_level1:
            reasons.append("force_level1")
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
    project_root: Path = None,
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

    # Check ACTUAL file size for single-file tasks (more accurate than estimation)
    actual_file_loc = 0
    if files_count == 1 and project_root:
        file_path = Path(files[0])
        if not file_path.is_absolute():
            file_path = project_root / files[0]
        if file_path.exists():
            try:
                actual_file_loc = len(file_path.read_text(errors='ignore').split('\n'))
                # Use actual file size if larger than estimate
                if actual_file_loc > loc_estimate:
                    loc_estimate = actual_file_loc
            except Exception:
                pass

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
        # Store project root for file access
        self.project_root = None
        if project_config:
            if hasattr(project_config, 'root_path'):
                self.project_root = Path(project_config.root_path)
            elif isinstance(project_config, dict) and 'root_path' in project_config:
                self.project_root = Path(project_config['root_path'])

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

        desc = task.get("description", "").lower()

        # Pre-filter: trivially simple tasks never need decomposition
        SIMPLE_TASK_PATTERNS = [
            "typo", "rename", "remove unused", "delete",
            "update version", "bump", "change import",
            "fix import", "add import", "missing import",
            "single file", "one line",
        ]
        if any(pattern in desc for pattern in SIMPLE_TASK_PATTERNS):
            log(f"Skipping FRACTAL for trivial task: {desc[:50]}...")
            return False, ComplexityAnalysis()

        # Force decomposition for root tasks (depth=0) — LLM will decide how many
        if self.config.force_level1 and current_depth == 0:
            analysis = analyze_complexity(task, self.config, current_depth, self.project_root)
            analysis.force_level1 = True
            return True, analysis

        analysis = analyze_complexity(task, self.config, current_depth, self.project_root)
        return analysis.should_decompose, analysis

    async def decompose(
        self,
        task: Dict[str, Any],
        current_depth: int = 0,
        force_count: int = None,
    ) -> List[Dict[str, Any]]:
        """
        Decompose a task into atomic sub-tasks.

        Uses LLM if available for intelligent decomposition,
        otherwise falls back to rule-based decomposition.

        Args:
            task: Task dict with description, files, etc.
            current_depth: Current recursion depth
            force_count: Force minimum number of subtasks (for L1 forcing)

        Returns:
            List of sub-task dicts
        """
        should_decompose, analysis = self.should_decompose(task, current_depth)

        if not should_decompose:
            log(f"Task within limits ({analysis.reason}), no decomposition needed")
            return [task]

        min_subtasks = force_count if force_count is not None else self.config.min_subtasks

        log(f"Decomposing task (depth={current_depth}, {analysis.reason}, min={min_subtasks})")

        # LLM-first: let the LLM decide how many sub-agents (0-10)
        if self.llm_client and self.config.llm_first:
            subtasks = await self._llm_decompose(task, analysis, min_subtasks)
            if subtasks is not None:  # None = LLM failed; [] = LLM says no split
                if len(subtasks) == 0:
                    log("LLM decided no decomposition needed")
                    return [task]
                return subtasks

        # Fallback to rule-based decomposition
        return self._rule_based_decompose(task, analysis, max(min_subtasks, 2))

    async def _llm_decompose(
        self,
        task: Dict[str, Any],
        analysis: ComplexityAnalysis,
        min_subtasks: int = 0,
    ) -> Optional[List[Dict[str, Any]]]:
        """Decompose using LLM for intelligent splitting.

        Returns:
            List of subtasks (may be empty = no split needed), or None if LLM failed.
        """
        try:
            prompt = self._build_decomposition_prompt(task, analysis, min_subtasks)
            response = await self.llm_client.query(prompt, role="sub")

            subtasks = self._parse_subtasks(response, task)
            if subtasks is not None:
                log(f"LLM decomposed into {len(subtasks)} sub-tasks")
                return subtasks

        except Exception as e:
            log(f"LLM decomposition failed: {e}", "WARN")

        return None

    # Task-type-aware decomposition guidance
    TYPE_GUIDANCE = {
        "integration": (
            "Split by LAYER or COMPONENT. Each sub-agent wires a different layer.\n"
            "Examples: backend bootstrap, DB migrations, gRPC client gen, frontend API wiring, proxy config.\n"
            "Order matters — return subtasks in dependency order (bootstrap first)."
        ),
        "feature": (
            "Split by CONCERN or COMPONENT.\n"
            "Examples: core business logic, input validation & auth guards, error handling & edge cases.\n"
            "Or by UI component if the feature spans multiple screens."
        ),
        "fix": (
            "Usually 1-2 sub-agents: root cause fix + regression test.\n"
            "Return 0 subtasks (empty array) if the fix is trivial and one agent can handle it."
        ),
        "security": (
            "Split by VULNERABILITY TYPE.\n"
            "Examples: SQL injection fixes, XSS sanitization, auth hardening, secret rotation."
        ),
        "refactor": (
            "Split by REFACTORING OPERATION.\n"
            "Examples: extract shared interface, migrate callers, remove old code & update tests."
        ),
        "test": (
            "Split by TEST CATEGORY.\n"
            "Examples: unit tests for module A, integration tests for API, edge case coverage."
        ),
        "implement": (
            "Split by MODULE or LAYER.\n"
            "Examples: data model, business logic, API endpoint, frontend component."
        ),
    }

    def _build_decomposition_prompt(
        self,
        task: Dict[str, Any],
        analysis: ComplexityAnalysis,
        min_subtasks: int = 0,
    ) -> str:
        """Build task-type-aware prompt for LLM decomposition"""
        task_type = task.get("type", "feature")
        guidance = self.TYPE_GUIDANCE.get(task_type, self.TYPE_GUIDANCE["feature"])

        return f"""Analyze this task and decide how to split it into sub-agents (0 to 10).

TASK:
- Type: {task_type}
- Description: {task.get('description', '')}
- Files: {task.get('files', [])}
- Domain: {task.get('domain', 'unknown')}

COMPLEXITY:
- Files: {analysis.files_count} (max {self.config.max_files})
- Estimated LOC: {analysis.loc_estimate} (max {self.config.max_loc})

DECOMPOSITION GUIDANCE for "{task_type}" tasks:
{guidance}

RULES:
1. Return 0 subtasks (empty array) if the task is simple enough for 1 agent
2. Return 1-10 subtasks based on actual complexity — no arbitrary minimum
3. Each subtask = 1 independent sub-agent with its own files
4. Each subtask touches max {self.config.max_files} files
5. No overlapping file modifications between subtasks
6. Be precise: don't create subtasks for the sake of it

RESPOND IN JSON ONLY:
{{"subtasks": [
    {{"description": "...", "files": ["..."], "type": "...", "domain": "{task.get('domain', 'unknown')}"}}
]}}
Return {{"subtasks": []}} if no decomposition needed.
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
        min_subtasks: int = 2,
    ) -> List[Dict[str, Any]]:
        """
        Rule-based decomposition fallback (when LLM is unavailable).

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
            orig_desc = task.get("description", "")
            for i in range(0, len(files), chunk_size):
                chunk_files = files[i:i + chunk_size]
                # Make description SPECIFIC to this file only
                file_specific_desc = (
                    f"[TARGET FILE: {chunk_files[0]}] "
                    f"Apply the following fix ONLY to this specific file. "
                    f"Original issue: {orig_desc}"
                )
                subtasks.append({
                    **base_task,
                    "id": f"{parent_id}_files{i // chunk_size + 1}",
                    "description": file_specific_desc,
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

        # Strategy 4: Split by function for large single-file tasks
        # Skip if already function-focused (prevent infinite recursion)
        description = task.get("description", "")
        if "[FUNCTION:" in description or "target_function" in task.get("context", {}):
            log("Task already function-focused, skipping further decomposition")
            return [task]

        files = task.get("files", [])
        if len(files) == 1:
            file_path = files[0]
            functions = self._extract_functions_from_file(file_path, task.get("domain", ""))
            if functions:
                # Find functions mentioned in the description or create focused subtask
                for i, (func_name, func_lines) in enumerate(functions[:5]):  # Max 5 subtasks
                    # Extract ONLY the function code to include in context
                    func_code = self._extract_function_code(file_path, func_lines)
                    subtasks.append({
                        **base_task,
                        "id": f"{parent_id}_fn{i + 1}",
                        "description": (
                            f"⚠️ SCOPE LIMIT: ONLY modify function `{func_name}` (lines {func_lines[0]}-{func_lines[1]})\n"
                            f"📁 File: {file_path}\n"
                            f"🎯 Task: {task.get('description', '')}\n\n"
                            f"RULES:\n"
                            f"1. Output ONLY the modified function code (max ~50 lines)\n"
                            f"2. Do NOT output the entire file\n"
                            f"3. Do NOT modify other functions\n"
                            f"4. If function > 50 LOC, SPLIT it (KISS principle)\n"
                            f"5. Cyclomatic complexity must stay < 10"
                        ),
                        "files": [file_path],
                        "context": {
                            **task.get("context", {}),
                            "target_function": func_name,
                            "target_lines": func_lines,
                            "function_code": func_code,  # Include actual code
                            "max_output_lines": 60,  # Soft limit hint
                        },
                    })
                if subtasks:
                    log(f"Split by function into {len(subtasks)} sub-tasks")
                    return subtasks

        # No decomposition possible, return original (will be at depth limit)
        log("No decomposition strategy applicable, returning original", "WARN")
        return [task]

    def _extract_functions_from_file(
        self,
        file_path: str,
        domain: str,
    ) -> List[Tuple[str, Tuple[int, int]]]:
        """
        Extract function/method names and line ranges from a file.
        Returns list of (function_name, (start_line, end_line)).
        Only returns functions from files > 300 lines.
        """
        try:
            # Try to find the file
            path = Path(file_path)
            if not path.is_absolute():
                # Try relative to project root first
                if self.project_root:
                    candidate = self.project_root / file_path
                    if candidate.exists():
                        path = candidate
                # Fallback to cwd
                if not path.exists():
                    for root in [Path.cwd(), Path.cwd().parent]:
                        candidate = root / file_path
                        if candidate.exists():
                            path = candidate
                            break

            if not path.exists():
                log(f"File not found: {file_path} (project_root={self.project_root})", "DEBUG")
                return []

            content = path.read_text(encoding='utf-8', errors='ignore')
            lines = content.split('\n')

            # Only process large files
            if len(lines) < 300:
                log(f"File {file_path} has {len(lines)} lines, not splitting", "DEBUG")
                return []

            log(f"Large file detected: {file_path} ({len(lines)} lines), extracting functions")

            functions = []

            if domain == "rust" or file_path.endswith('.rs'):
                # Rust: fn, pub fn, async fn, impl blocks
                fn_pattern = re.compile(r'^\s*(pub\s+)?(async\s+)?fn\s+(\w+)')
                impl_pattern = re.compile(r'^\s*impl\s+(?:<[^>]+>\s+)?(\w+)')

                current_fn = None
                current_start = 0
                brace_count = 0

                for i, line in enumerate(lines, 1):
                    fn_match = fn_pattern.match(line)
                    impl_match = impl_pattern.match(line)

                    if fn_match:
                        if current_fn and brace_count == 0:
                            functions.append((current_fn, (current_start, i - 1)))
                        current_fn = fn_match.group(3)
                        current_start = i
                        brace_count = 0
                    elif impl_match:
                        if current_fn and brace_count == 0:
                            functions.append((current_fn, (current_start, i - 1)))
                        current_fn = f"impl_{impl_match.group(1)}"
                        current_start = i
                        brace_count = 0

                    brace_count += line.count('{') - line.count('}')

                    if current_fn and brace_count == 0 and '{' in line:
                        functions.append((current_fn, (current_start, i)))
                        current_fn = None

            elif domain in ("typescript", "svelte") or file_path.endswith(('.ts', '.tsx', '.svelte')):
                # TypeScript: function, const = () =>, export function
                fn_pattern = re.compile(r'^\s*(export\s+)?(async\s+)?function\s+(\w+)')
                arrow_pattern = re.compile(r'^\s*(export\s+)?(const|let)\s+(\w+)\s*=\s*(async\s*)?\(')

                for i, line in enumerate(lines, 1):
                    fn_match = fn_pattern.match(line)
                    arrow_match = arrow_pattern.match(line)

                    if fn_match:
                        functions.append((fn_match.group(3), (i, min(i + 50, len(lines)))))
                    elif arrow_match:
                        functions.append((arrow_match.group(3), (i, min(i + 50, len(lines)))))

            log(f"Found {len(functions)} functions in {file_path}")
            return functions[:10]  # Max 10 functions

        except Exception as e:
            log(f"Error extracting functions from {file_path}: {e}", "WARN")
            return []

    def _extract_function_code(
        self,
        file_path: str,
        line_range: Tuple[int, int],
    ) -> str:
        """
        Extract the actual code for a function given its line range.
        Returns the function code as a string.
        """
        try:
            path = Path(file_path)
            if not path.is_absolute() and self.project_root:
                path = self.project_root / file_path

            if not path.exists():
                return ""

            content = path.read_text(encoding='utf-8', errors='ignore')
            lines = content.split('\n')

            start, end = line_range
            # Add some context (2 lines before, ensure we don't go negative)
            start = max(0, start - 3)
            # Limit to ~80 lines max to keep context manageable
            end = min(len(lines), start + 80)

            func_lines = lines[start:end]
            return '\n'.join(func_lines)
        except Exception as e:
            log(f"Error extracting function code: {e}", "WARN")
            return ""

    def _distribute_files(self, files: List[str], ratios: List[float]) -> List[List[str]]:
        """Distribute files across chunks based on ratios"""
        if not files:
            return [[] for _ in ratios]
        
        result = []
        start = 0
        n = len(files)
        
        for i, ratio in enumerate(ratios):
            if i == len(ratios) - 1:
                # Last chunk gets remaining files
                result.append(files[start:])
            else:
                chunk_size = max(1, int(n * ratio))
                result.append(files[start:start + chunk_size])
                start += chunk_size
        
        return result

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
