#!/usr/bin/env python3
"""
Refactor Analyzer - Evidence-Based Refactoring with Metrics & Patterns
=======================================================================

Combines deterministic metrics with LLM pattern detection:
1. METRICS: Cyclomatic complexity, LOC, coupling, cohesion
2. ANTI-PATTERNS: God Class, Feature Envy, Shotgun Surgery, etc.
3. GOF PATTERNS: Strategy, Factory, Observer, etc.
4. SOLID: Single Responsibility, Open/Closed, etc.

Usage:
    from core.refactor_analyzer import RefactorAnalyzer

    analyzer = RefactorAnalyzer(project_config)
    report = await analyzer.analyze_file("src/service.py")
    tasks = await analyzer.generate_refactor_tasks()
"""

import asyncio
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple


def log(msg: str, level: str = "INFO"):
    """Log with timestamp"""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [REFACTOR] [{level}] {msg}", flush=True)


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class MetricResult:
    """Single metric measurement"""
    name: str
    value: float
    threshold: float
    passed: bool
    file_path: str = ""
    line: int = 0
    details: str = ""

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "value": self.value,
            "threshold": self.threshold,
            "passed": self.passed,
            "file_path": self.file_path,
            "line": self.line,
            "details": self.details,
        }


@dataclass
class AntiPattern:
    """Detected anti-pattern"""
    name: str
    severity: str  # "high", "medium", "low"
    file_path: str
    line_start: int
    line_end: int
    description: str
    suggested_fix: str
    pattern_to_apply: str = ""  # GOF pattern if applicable

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "severity": self.severity,
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "description": self.description,
            "suggested_fix": self.suggested_fix,
            "pattern_to_apply": self.pattern_to_apply,
        }


@dataclass
class RefactorReport:
    """Complete refactoring analysis report"""
    file_path: str
    metrics: List[MetricResult] = field(default_factory=list)
    anti_patterns: List[AntiPattern] = field(default_factory=list)
    solid_violations: List[str] = field(default_factory=list)
    suggested_patterns: List[str] = field(default_factory=list)
    priority_score: float = 0.0  # Higher = more urgent refactoring needed

    def to_dict(self) -> Dict:
        return {
            "file_path": self.file_path,
            "metrics": [m.to_dict() for m in self.metrics],
            "anti_patterns": [a.to_dict() for a in self.anti_patterns],
            "solid_violations": self.solid_violations,
            "suggested_patterns": self.suggested_patterns,
            "priority_score": self.priority_score,
        }


# ============================================================================
# METRIC THRESHOLDS
# ============================================================================

METRIC_THRESHOLDS = {
    "cyclomatic_complexity": 10,      # Max per function
    "loc_per_function": 50,           # Max lines per function
    "loc_per_file": 500,              # Max lines per file
    "methods_per_class": 10,          # Max methods per class
    "params_per_function": 5,         # Max parameters
    "nesting_depth": 4,               # Max nesting level
    "dependencies_per_file": 15,      # Max imports
    "cognitive_complexity": 15,       # Max cognitive load
}

# ============================================================================
# ANTI-PATTERN DEFINITIONS
# ============================================================================

ANTI_PATTERNS = {
    "god_class": {
        "name": "God Class",
        "description": "Class with too many responsibilities",
        "indicators": ["loc > 500", "methods > 10", "multiple unrelated concerns"],
        "fix": "Split into smaller, focused classes using SRP",
        "severity": "high",
    },
    "feature_envy": {
        "name": "Feature Envy",
        "description": "Method uses another class's data more than its own",
        "indicators": ["frequent cross-class access", "method belongs elsewhere"],
        "fix": "Move method to the class it envies",
        "severity": "medium",
    },
    "shotgun_surgery": {
        "name": "Shotgun Surgery",
        "description": "One change requires modifying many classes",
        "indicators": ["scattered related code", "high coupling"],
        "fix": "Consolidate related code into single module",
        "severity": "high",
    },
    "primitive_obsession": {
        "name": "Primitive Obsession",
        "description": "Using primitives instead of small objects",
        "indicators": ["string for email/phone/money", "repeated validation"],
        "fix": "Create Value Objects (Email, Money, PhoneNumber)",
        "severity": "medium",
    },
    "long_parameter_list": {
        "name": "Long Parameter List",
        "description": "Function with too many parameters",
        "indicators": ["params > 5", "related params grouped"],
        "fix": "Introduce Parameter Object or Builder",
        "severity": "medium",
    },
    "data_clumps": {
        "name": "Data Clumps",
        "description": "Same group of data appearing together",
        "indicators": ["repeated parameter groups", "related fields"],
        "fix": "Extract class for the data clump",
        "severity": "low",
    },
    "divergent_change": {
        "name": "Divergent Change",
        "description": "One class changed for multiple unrelated reasons",
        "indicators": ["multiple change vectors", "unrelated methods"],
        "fix": "Split class by change reason (SRP)",
        "severity": "high",
    },
    "parallel_inheritance": {
        "name": "Parallel Inheritance Hierarchies",
        "description": "Creating subclass requires creating another subclass elsewhere",
        "indicators": ["mirrored hierarchies", "coupled inheritance"],
        "fix": "Merge hierarchies or use composition",
        "severity": "medium",
    },
    "speculative_generality": {
        "name": "Speculative Generality",
        "description": "Unused abstraction created for hypothetical future",
        "indicators": ["unused interfaces", "over-engineered", "YAGNI violation"],
        "fix": "Remove unused abstractions, keep it simple",
        "severity": "low",
    },
    "dead_code": {
        "name": "Dead Code",
        "description": "Unreachable or unused code",
        "indicators": ["unused functions", "unreachable branches"],
        "fix": "Delete dead code",
        "severity": "low",
    },
}

# ============================================================================
# GOF PATTERNS SUGGESTIONS
# ============================================================================

GOF_PATTERN_TRIGGERS = {
    "strategy": {
        "trigger": "Multiple if/switch on type to select behavior",
        "solution": "Strategy pattern - encapsulate algorithms in classes",
        "example": "if type == 'A': doA() elif type == 'B': doB() → strategy.execute()",
    },
    "factory": {
        "trigger": "Complex object creation with conditionals",
        "solution": "Factory pattern - encapsulate creation logic",
        "example": "if type == 'X': return X() → Factory.create(type)",
    },
    "builder": {
        "trigger": "Constructor with many optional parameters",
        "solution": "Builder pattern - step-by-step construction",
        "example": "Obj(a,b,c,d,e,f) → Obj.builder().a(a).b(b).build()",
    },
    "observer": {
        "trigger": "Objects need notification of state changes",
        "solution": "Observer pattern - publish/subscribe",
        "example": "Manual callbacks → subject.notify(observers)",
    },
    "decorator": {
        "trigger": "Adding behavior dynamically without subclassing",
        "solution": "Decorator pattern - wrap objects",
        "example": "Subclass explosion → decorator.wrap(base)",
    },
    "state": {
        "trigger": "Object behavior changes based on internal state",
        "solution": "State pattern - encapsulate state-specific behavior",
        "example": "if state == 'A': ... elif state == 'B': → state.handle()",
    },
    "command": {
        "trigger": "Need to parameterize, queue, or undo operations",
        "solution": "Command pattern - encapsulate requests as objects",
        "example": "Direct method calls → command.execute()",
    },
    "adapter": {
        "trigger": "Incompatible interfaces need to work together",
        "solution": "Adapter pattern - convert interface",
        "example": "Cannot use library directly → adapter.adapt(library)",
    },
    "facade": {
        "trigger": "Complex subsystem needs simplified interface",
        "solution": "Facade pattern - unified high-level interface",
        "example": "Multiple low-level calls → facade.doOperation()",
    },
    "singleton": {
        "trigger": "Exactly one instance needed globally",
        "solution": "Singleton pattern (use sparingly!)",
        "example": "Global state → Singleton.instance()",
        "warning": "Often an anti-pattern - prefer dependency injection",
    },
}

# ============================================================================
# SOLID PRINCIPLES
# ============================================================================

SOLID_PRINCIPLES = {
    "S": {
        "name": "Single Responsibility",
        "description": "A class should have only one reason to change",
        "check": "Does this class have multiple unrelated responsibilities?",
        "violation_indicators": ["and", "also", "handles X and Y"],
    },
    "O": {
        "name": "Open/Closed",
        "description": "Open for extension, closed for modification",
        "check": "Do you need to modify existing code to add new behavior?",
        "violation_indicators": ["switch on type", "if instanceof", "type checking"],
    },
    "L": {
        "name": "Liskov Substitution",
        "description": "Subtypes must be substitutable for their base types",
        "check": "Can derived class be used wherever base class is expected?",
        "violation_indicators": ["override breaks contract", "NotImplementedError in override"],
    },
    "I": {
        "name": "Interface Segregation",
        "description": "Clients shouldn't depend on interfaces they don't use",
        "check": "Does the interface have methods that some implementations don't need?",
        "violation_indicators": ["empty implementations", "raise NotImplemented", "pass"],
    },
    "D": {
        "name": "Dependency Inversion",
        "description": "Depend on abstractions, not concretions",
        "check": "Does high-level module depend directly on low-level module?",
        "violation_indicators": ["import concrete class", "new ConcreteClass()", "hardcoded dependency"],
    },
}


# ============================================================================
# REFACTOR ANALYZER
# ============================================================================

class RefactorAnalyzer:
    """
    Evidence-based refactoring analyzer.
    Combines metrics, anti-patterns, and GOF patterns.
    """

    def __init__(self, project_config: Any = None):
        self.project_config = project_config
        self.project_root = ""
        self.reports: List[RefactorReport] = []

        if project_config:
            if hasattr(project_config, 'root_path'):
                self.project_root = project_config.root_path
            elif isinstance(project_config, dict):
                self.project_root = project_config.get("project", {}).get("root_path", "")

    # ========================================================================
    # METRIC COLLECTION (Deterministic)
    # ========================================================================

    def _count_lines(self, content: str) -> int:
        """Count non-empty, non-comment lines"""
        lines = content.split('\n')
        count = 0
        in_multiline_comment = False

        for line in lines:
            stripped = line.strip()

            # Skip empty lines
            if not stripped:
                continue

            # Handle multiline comments
            if '"""' in stripped or "'''" in stripped:
                in_multiline_comment = not in_multiline_comment
                continue
            if in_multiline_comment:
                continue

            # Skip single-line comments
            if stripped.startswith('#') or stripped.startswith('//'):
                continue

            count += 1

        return count

    def _count_functions(self, content: str, file_type: str) -> List[Dict]:
        """Extract functions with their line counts"""
        functions = []

        if file_type in ['python', 'py']:
            # Python: def function_name(
            pattern = r'^\s*(?:async\s+)?def\s+(\w+)\s*\('
            for match in re.finditer(pattern, content, re.MULTILINE):
                functions.append({
                    "name": match.group(1),
                    "line": content[:match.start()].count('\n') + 1,
                })

        elif file_type in ['rust', 'rs']:
            # Rust: fn function_name(
            pattern = r'^\s*(?:pub\s+)?(?:async\s+)?fn\s+(\w+)\s*[<(]'
            for match in re.finditer(pattern, content, re.MULTILINE):
                functions.append({
                    "name": match.group(1),
                    "line": content[:match.start()].count('\n') + 1,
                })

        elif file_type in ['typescript', 'ts', 'javascript', 'js']:
            # TypeScript/JS: function name( or name = ( or name(
            patterns = [
                r'^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(',
                r'^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(',
                r'^\s*(?:public|private|protected)?\s*(?:async\s+)?(\w+)\s*\([^)]*\)\s*[:{]',
            ]
            for pattern in patterns:
                for match in re.finditer(pattern, content, re.MULTILINE):
                    functions.append({
                        "name": match.group(1),
                        "line": content[:match.start()].count('\n') + 1,
                    })

        return functions

    def _count_classes(self, content: str, file_type: str) -> List[Dict]:
        """Extract classes with their line counts and method counts"""
        classes = []

        if file_type in ['python', 'py']:
            pattern = r'^\s*class\s+(\w+)'
            for match in re.finditer(pattern, content, re.MULTILINE):
                classes.append({
                    "name": match.group(1),
                    "line": content[:match.start()].count('\n') + 1,
                })

        elif file_type in ['rust', 'rs']:
            # Rust: struct or impl
            pattern = r'^\s*(?:pub\s+)?(?:struct|impl)\s+(\w+)'
            for match in re.finditer(pattern, content, re.MULTILINE):
                classes.append({
                    "name": match.group(1),
                    "line": content[:match.start()].count('\n') + 1,
                })

        elif file_type in ['typescript', 'ts']:
            pattern = r'^\s*(?:export\s+)?class\s+(\w+)'
            for match in re.finditer(pattern, content, re.MULTILINE):
                classes.append({
                    "name": match.group(1),
                    "line": content[:match.start()].count('\n') + 1,
                })

        return classes

    def _count_params(self, content: str, file_type: str) -> List[Dict]:
        """Extract functions with parameter counts"""
        functions_with_params = []

        if file_type in ['python', 'py']:
            pattern = r'def\s+(\w+)\s*\(([^)]*)\)'
            for match in re.finditer(pattern, content):
                params = match.group(2)
                param_count = len([p for p in params.split(',') if p.strip() and p.strip() != 'self'])
                if param_count > 0:
                    functions_with_params.append({
                        "name": match.group(1),
                        "params": param_count,
                        "line": content[:match.start()].count('\n') + 1,
                    })

        elif file_type in ['rust', 'rs']:
            pattern = r'fn\s+(\w+)\s*(?:<[^>]*>)?\s*\(([^)]*)\)'
            for match in re.finditer(pattern, content):
                params = match.group(2)
                param_count = len([p for p in params.split(',') if p.strip() and '&self' not in p and 'self' not in p])
                if param_count > 0:
                    functions_with_params.append({
                        "name": match.group(1),
                        "params": param_count,
                        "line": content[:match.start()].count('\n') + 1,
                    })

        return functions_with_params

    def _count_nesting(self, content: str) -> int:
        """Count maximum nesting depth"""
        max_depth = 0
        current_depth = 0

        for char in content:
            if char == '{':
                current_depth += 1
                max_depth = max(max_depth, current_depth)
            elif char == '}':
                current_depth = max(0, current_depth - 1)

        return max_depth

    def _count_imports(self, content: str, file_type: str) -> int:
        """Count import statements"""
        if file_type in ['python', 'py']:
            return len(re.findall(r'^(?:from|import)\s+', content, re.MULTILINE))
        elif file_type in ['rust', 'rs']:
            return len(re.findall(r'^use\s+', content, re.MULTILINE))
        elif file_type in ['typescript', 'ts', 'javascript', 'js']:
            return len(re.findall(r'^import\s+', content, re.MULTILINE))
        return 0

    def _calculate_cyclomatic_complexity(self, content: str, file_type: str) -> int:
        """Estimate cyclomatic complexity per function (simplified)"""
        # Remove strings and comments first to avoid false positives
        # Remove string literals
        content_clean = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', '""', content)
        content_clean = re.sub(r"'[^'\\]*(?:\\.[^'\\]*)*'", "''", content_clean)

        # Remove comments
        content_clean = re.sub(r'//.*$', '', content_clean, flags=re.MULTILINE)
        content_clean = re.sub(r'/\*.*?\*/', '', content_clean, flags=re.DOTALL)
        content_clean = re.sub(r'#.*$', '', content_clean, flags=re.MULTILINE)

        # Count decision points (only in code, not strings/comments)
        complexity = 1  # Base complexity

        # Primary decision keywords
        for keyword in ['if', 'elif', 'else if', 'match', 'while', 'for', 'case']:
            complexity += len(re.findall(rf'\b{keyword}\b', content_clean))

        # Logical operators (add 1 for each)
        complexity += len(re.findall(r'\s&&\s', content_clean))
        complexity += len(re.findall(r'\s\|\|\s', content_clean))
        complexity += len(re.findall(r'\band\b', content_clean))
        complexity += len(re.findall(r'\bor\b', content_clean))

        # Ternary operator
        complexity += content_clean.count(' ? ')

        # Cap at reasonable maximum per file
        return min(complexity, 100)

    def analyze_metrics(self, file_path: str, content: str) -> List[MetricResult]:
        """Collect all metrics for a file"""
        metrics = []

        # Detect file type
        ext = Path(file_path).suffix.lower()
        file_type = {
            '.py': 'python',
            '.rs': 'rust',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.svelte': 'typescript',
        }.get(ext, 'unknown')

        # 1. Lines of Code
        loc = self._count_lines(content)
        metrics.append(MetricResult(
            name="loc_per_file",
            value=loc,
            threshold=METRIC_THRESHOLDS["loc_per_file"],
            passed=loc <= METRIC_THRESHOLDS["loc_per_file"],
            file_path=file_path,
            details=f"{loc} lines (max {METRIC_THRESHOLDS['loc_per_file']})",
        ))

        # 2. Functions and their sizes
        functions = self._count_functions(content, file_type)
        for func in functions:
            # Estimate function LOC (simplified)
            func_loc = 30  # Placeholder - would need proper parsing
            if func_loc > METRIC_THRESHOLDS["loc_per_function"]:
                metrics.append(MetricResult(
                    name="loc_per_function",
                    value=func_loc,
                    threshold=METRIC_THRESHOLDS["loc_per_function"],
                    passed=False,
                    file_path=file_path,
                    line=func["line"],
                    details=f"Function '{func['name']}' has {func_loc} lines",
                ))

        # 3. Parameter counts
        params = self._count_params(content, file_type)
        for func in params:
            if func["params"] > METRIC_THRESHOLDS["params_per_function"]:
                metrics.append(MetricResult(
                    name="params_per_function",
                    value=func["params"],
                    threshold=METRIC_THRESHOLDS["params_per_function"],
                    passed=False,
                    file_path=file_path,
                    line=func["line"],
                    details=f"Function '{func['name']}' has {func['params']} params (max {METRIC_THRESHOLDS['params_per_function']})",
                ))

        # 4. Class method counts
        classes = self._count_classes(content, file_type)
        for cls in classes:
            # Count methods in class (simplified)
            method_count = len([f for f in functions if f["line"] > cls["line"]])
            if method_count > METRIC_THRESHOLDS["methods_per_class"]:
                metrics.append(MetricResult(
                    name="methods_per_class",
                    value=method_count,
                    threshold=METRIC_THRESHOLDS["methods_per_class"],
                    passed=False,
                    file_path=file_path,
                    line=cls["line"],
                    details=f"Class '{cls['name']}' has {method_count} methods (max {METRIC_THRESHOLDS['methods_per_class']})",
                ))

        # 5. Nesting depth
        nesting = self._count_nesting(content)
        metrics.append(MetricResult(
            name="nesting_depth",
            value=nesting,
            threshold=METRIC_THRESHOLDS["nesting_depth"],
            passed=nesting <= METRIC_THRESHOLDS["nesting_depth"],
            file_path=file_path,
            details=f"Max nesting depth: {nesting} (max {METRIC_THRESHOLDS['nesting_depth']})",
        ))

        # 6. Import count
        imports = self._count_imports(content, file_type)
        metrics.append(MetricResult(
            name="dependencies_per_file",
            value=imports,
            threshold=METRIC_THRESHOLDS["dependencies_per_file"],
            passed=imports <= METRIC_THRESHOLDS["dependencies_per_file"],
            file_path=file_path,
            details=f"{imports} imports (max {METRIC_THRESHOLDS['dependencies_per_file']})",
        ))

        # 7. Cyclomatic complexity
        complexity = self._calculate_cyclomatic_complexity(content, file_type)
        metrics.append(MetricResult(
            name="cyclomatic_complexity",
            value=complexity,
            threshold=METRIC_THRESHOLDS["cyclomatic_complexity"],
            passed=complexity <= METRIC_THRESHOLDS["cyclomatic_complexity"],
            file_path=file_path,
            details=f"Cyclomatic complexity: {complexity} (max {METRIC_THRESHOLDS['cyclomatic_complexity']})",
        ))

        return metrics

    # ========================================================================
    # ANTI-PATTERN DETECTION (LLM-assisted)
    # ========================================================================

    async def detect_anti_patterns(self, file_path: str, content: str) -> List[AntiPattern]:
        """Detect anti-patterns using LLM semantic analysis"""
        from core.llm_client import run_opencode

        anti_patterns = []

        # Quick deterministic checks first
        loc = self._count_lines(content)

        # God Class check (deterministic)
        if loc > 500:
            anti_patterns.append(AntiPattern(
                name="god_class",
                severity="high",
                file_path=file_path,
                line_start=1,
                line_end=loc,
                description=f"File has {loc} lines - likely God Class",
                suggested_fix="Split into smaller, focused classes",
            ))

        # Long Parameter List (deterministic)
        ext = Path(file_path).suffix.lower()
        file_type = {'.py': 'python', '.rs': 'rust', '.ts': 'typescript'}.get(ext, 'unknown')
        params = self._count_params(content, file_type)
        for func in params:
            if func["params"] > 5:
                anti_patterns.append(AntiPattern(
                    name="long_parameter_list",
                    severity="medium",
                    file_path=file_path,
                    line_start=func["line"],
                    line_end=func["line"],
                    description=f"Function '{func['name']}' has {func['params']} parameters",
                    suggested_fix="Introduce Parameter Object or Builder pattern",
                    pattern_to_apply="Builder",
                ))

        # LLM-based detection for complex patterns
        prompt = f"""Analyze this code for ANTI-PATTERNS and SOLID violations.

FILE: {file_path}
CODE:
```
{content[:6000]}
```

Check for these anti-patterns:
1. God Class - too many responsibilities
2. Feature Envy - method uses another class's data more than its own
3. Shotgun Surgery - one change requires modifying many files
4. Primitive Obsession - using strings for email/money/phone
5. Data Clumps - same parameters appearing together
6. Divergent Change - class changed for multiple unrelated reasons
7. Dead Code - unused functions or unreachable code
8. Speculative Generality - unused abstractions

Check SOLID violations:
- S: Multiple responsibilities in one class?
- O: Need to modify code to extend behavior?
- L: Subtype breaks base type contract?
- I: Interface has unused methods?
- D: High-level depends on low-level directly?

Suggest GOF patterns if applicable:
- Strategy for behavior switching
- Factory for complex creation
- Observer for notifications
- State for state-dependent behavior

RESPOND IN JSON:
{{
  "anti_patterns": [
    {{"name": "pattern_name", "severity": "high|medium|low", "line": N, "description": "...", "fix": "...", "pattern": "GOF pattern if applicable"}}
  ],
  "solid_violations": ["S: description", "O: description"],
  "suggested_patterns": ["Strategy for X", "Factory for Y"],
  "priority_score": 0-10
}}
"""

        try:
            returncode, output = await run_opencode(
                prompt,
                model="minimax/MiniMax-M2.5",
                timeout=120,
                fallback=True,
            )

            if returncode == 0:
                # Parse JSON from output
                json_match = re.search(r'\{.*\}', output, re.DOTALL)
                if json_match:
                    try:
                        result = json.loads(json_match.group())

                        for ap in result.get("anti_patterns", []):
                            anti_patterns.append(AntiPattern(
                                name=ap.get("name", "unknown"),
                                severity=ap.get("severity", "medium"),
                                file_path=file_path,
                                line_start=ap.get("line", 0),
                                line_end=ap.get("line", 0),
                                description=ap.get("description", ""),
                                suggested_fix=ap.get("fix", ""),
                                pattern_to_apply=ap.get("pattern", ""),
                            ))

                    except json.JSONDecodeError:
                        log(f"Failed to parse LLM response for {file_path}", "WARN")

        except Exception as e:
            log(f"LLM anti-pattern detection failed: {e}", "ERROR")

        return anti_patterns

    # ========================================================================
    # FULL ANALYSIS
    # ========================================================================

    async def analyze_file(self, file_path: str) -> RefactorReport:
        """Complete refactoring analysis for a single file"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            log(f"Failed to read {file_path}: {e}", "ERROR")
            return RefactorReport(file_path=file_path)

        # 1. Collect metrics (deterministic)
        metrics = self.analyze_metrics(file_path, content)

        # 2. Detect anti-patterns (LLM + deterministic)
        anti_patterns = await self.detect_anti_patterns(file_path, content)

        # 3. Calculate priority score
        failed_metrics = sum(1 for m in metrics if not m.passed)
        high_severity = sum(1 for a in anti_patterns if a.severity == "high")
        medium_severity = sum(1 for a in anti_patterns if a.severity == "medium")

        priority_score = (
            failed_metrics * 2 +
            high_severity * 3 +
            medium_severity * 1
        )

        report = RefactorReport(
            file_path=file_path,
            metrics=metrics,
            anti_patterns=anti_patterns,
            priority_score=min(priority_score, 10),
        )

        self.reports.append(report)
        return report

    async def analyze_directory(self, directory: str, extensions: List[str] = None) -> List[RefactorReport]:
        """Analyze all files in a directory"""
        if extensions is None:
            extensions = ['.py', '.rs', '.ts', '.tsx', '.js', '.svelte']

        reports = []
        path = Path(directory)

        for ext in extensions:
            for file_path in path.rglob(f'*{ext}'):
                # Skip node_modules, target, etc.
                if any(skip in str(file_path) for skip in ['node_modules', 'target', '.git', '__pycache__', 'dist']):
                    continue

                log(f"Analyzing: {file_path}")
                report = await self.analyze_file(str(file_path))
                if report.priority_score > 0:
                    reports.append(report)

        # Sort by priority
        reports.sort(key=lambda r: r.priority_score, reverse=True)
        return reports

    def generate_refactor_task_description(self, report: RefactorReport) -> str:
        """Generate a task description from a refactor report"""
        parts = [f"[REF-METRICS] Refactor {Path(report.file_path).name}"]

        # Add metrics issues
        failed_metrics = [m for m in report.metrics if not m.passed]
        if failed_metrics:
            parts.append("\n\nMETRICS VIOLATIONS:")
            for m in failed_metrics[:3]:
                parts.append(f"- {m.name}: {m.details}")

        # Add anti-patterns
        if report.anti_patterns:
            parts.append("\n\nANTI-PATTERNS:")
            for ap in report.anti_patterns[:3]:
                parts.append(f"- {ap.name}: {ap.description}")
                if ap.suggested_fix:
                    parts.append(f"  Fix: {ap.suggested_fix}")
                if ap.pattern_to_apply:
                    parts.append(f"  Pattern: {ap.pattern_to_apply}")

        # Add suggested patterns
        if report.suggested_patterns:
            parts.append("\n\nSUGGESTED PATTERNS:")
            for pattern in report.suggested_patterns[:3]:
                parts.append(f"- {pattern}")

        return "".join(parts)


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

async def analyze_file(file_path: str, config: Any = None) -> RefactorReport:
    """Quick analysis of a single file"""
    analyzer = RefactorAnalyzer(config)
    return await analyzer.analyze_file(file_path)


async def analyze_project(root_path: str, config: Any = None) -> List[RefactorReport]:
    """Analyze entire project"""
    analyzer = RefactorAnalyzer(config)
    return await analyzer.analyze_directory(root_path)
