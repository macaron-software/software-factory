"""Quality Tools — agent-facing tools for code quality scanning.

Exposes QualityScanner capabilities as tools that agents can call during
missions/sessions. Integrated into the tool registry.
"""

from __future__ import annotations

import json
from ..models import AgentInstance
from .registry import BaseTool


class QualityScanTool(BaseTool):
    """Run a full or partial quality scan on workspace code."""

    name = "quality_scan"
    description = (
        "Run deterministic quality scan on workspace code. "
        "Scans complexity, test coverage, security, documentation, architecture, maintainability. "
        "Returns scorecard with global score (0-100) and per-dimension breakdown. "
        "Use dimensions param to scan specific areas: complexity, coverage_ut, security, documentation, architecture, maintainability."
    )
    category = "quality"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        from ..metrics.quality import QualityScanner

        cwd = params.get("cwd", ".")
        project_id = params.get("project_id", "")
        mission_id = params.get("mission_id", "")
        dimensions = params.get("dimensions", "all")
        url = params.get("url", "")

        scanner = QualityScanner()

        if dimensions == "all":
            scorecard = await scanner.full_scan(
                cwd, project_id=project_id, mission_id=mission_id, url=url
            )
            result = scorecard.to_dict()
            # Format for agent consumption
            lines = [f"Quality Score: {result['global_score']}/100\n"]
            for dim, data in result["dimensions"].items():
                status = (
                    "OK"
                    if data["score"] >= 70
                    else "WARN"
                    if data["score"] >= 40
                    else "FAIL"
                )
                lines.append(f"  {dim}: {data['score']}/100 [{status}]")
                if data.get("error"):
                    lines.append(f"    Error: {data['error']}")
            return "\n".join(lines)

        # Single dimension scan
        dim_method = f"scan_{dimensions}"
        if hasattr(scanner, dim_method):
            result = await getattr(scanner, dim_method)(cwd, stack=None)
            return json.dumps(
                {
                    "dimension": dimensions,
                    "score": result.score,
                    "details": result.details,
                },
                indent=2,
            )

        return f"Unknown dimension: {dimensions}. Available: complexity, coverage_ut, coverage_e2e, security, accessibility, performance, documentation, architecture, maintainability, adversarial"


class ComplexityCheckTool(BaseTool):
    """Quick cyclomatic complexity check on a file or directory."""

    name = "complexity_check"
    description = (
        "Check cyclomatic complexity of code. Returns average complexity, "
        "high-complexity functions (CC > 10), and overall grade (A-F). "
        "Uses radon (Python) or lizard (multi-language)."
    )
    category = "quality"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        from ..metrics.quality import QualityScanner

        cwd = params.get("cwd", ".")
        scanner = QualityScanner()
        result = await scanner.scan_complexity(cwd)

        lines = [f"Complexity Score: {result.score}/100 (tool: {result.tool_used})"]
        if result.details.get("avg_cc"):
            lines.append(f"Average CC: {result.details['avg_cc']}")
            lines.append(f"Functions analyzed: {result.details.get('functions', 0)}")
            lines.append(
                f"High complexity (CC>10): {result.details.get('high_complexity', 0)}"
            )
        if result.error:
            lines.append(f"Error: {result.error}")
        return "\n".join(lines)


class CoverageCheckTool(BaseTool):
    """Run tests with coverage and report results."""

    name = "coverage_check"
    description = (
        "Run unit tests with code coverage measurement. "
        "Returns coverage percentage, covered/total lines. "
        "Supports Python (coverage.py), JS/TS (nyc), Go (go test -cover)."
    )
    category = "quality"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        from ..metrics.quality import QualityScanner

        cwd = params.get("cwd", ".")
        scanner = QualityScanner()
        result = await scanner.scan_coverage_ut(cwd)

        lines = [f"Coverage: {result.score}% (tool: {result.tool_used})"]
        if result.details.get("percent_covered"):
            lines.append(
                f"Lines covered: {result.details.get('lines_covered', '?')}/{result.details.get('lines_total', '?')}"
            )
        if result.details.get("error"):
            lines.append(f"Note: {result.details['error']}")
        return "\n".join(lines)


class DocCoverageCheckTool(BaseTool):
    """Check documentation completeness."""

    name = "doc_coverage_check"
    description = (
        "Check documentation coverage: docstrings (Python via interrogate), "
        "README presence, API docs, CHANGELOG, CONTRIBUTING. "
        "Returns coverage percentage."
    )
    category = "quality"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        from ..metrics.quality import QualityScanner

        cwd = params.get("cwd", ".")
        scanner = QualityScanner()
        result = await scanner.scan_documentation(cwd)

        lines = [f"Documentation Score: {result.score}/100 (tool: {result.tool_used})"]
        if result.details.get("docstring_coverage") is not None:
            lines.append(f"Docstring coverage: {result.details['docstring_coverage']}%")
        if result.details.get("checks"):
            for check, present in result.details["checks"].items():
                lines.append(f"  {'[x]' if present else '[ ]'} {check}")
        return "\n".join(lines)


def register_quality_tools(registry):
    """Register all quality tools with the tool registry."""
    registry.register(QualityScanTool())
    registry.register(ComplexityCheckTool())
    registry.register(CoverageCheckTool())
    registry.register(DocCoverageCheckTool())
