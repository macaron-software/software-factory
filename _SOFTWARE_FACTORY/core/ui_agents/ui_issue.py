"""
Shared dataclasses for UI agents.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class UISeverity(Enum):
    """Severity levels for UI issues."""
    REJECT = "reject"      # Blocking, must fix
    WARNING = "warning"    # Should fix
    INFO = "info"          # Informational


@dataclass
class UIIssue:
    """Base class for all UI-related issues."""
    rule_id: str
    severity: UISeverity
    points: int
    message: str
    file_path: str
    line: int = 0
    column: int = 0
    context: str = ""
    fix_suggestion: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "points": self.points,
            "message": self.message,
            "file_path": self.file_path,
            "line": self.line,
            "column": self.column,
            "context": self.context,
            "fix_suggestion": self.fix_suggestion,
        }


@dataclass
class DesignTokenViolation(UIIssue):
    """Violation of design token usage."""
    hardcoded_value: str = ""
    suggested_token: str = ""
    category: str = "token"  # color, spacing, typography, radius, shadow

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "hardcoded_value": self.hardcoded_value,
            "suggested_token": self.suggested_token,
            "category": self.category,
        })
        return d


@dataclass
class FigmaDiscrepancy(UIIssue):
    """Discrepancy between Figma spec and code."""
    figma_node_id: str = ""
    property_name: str = ""
    figma_value: str = ""
    code_value: str = ""
    tolerance: float = 0
    category: str = "figma"

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "figma_node_id": self.figma_node_id,
            "property_name": self.property_name,
            "figma_value": self.figma_value,
            "code_value": self.code_value,
            "tolerance": self.tolerance,
            "category": self.category,
        })
        return d


@dataclass
class UXViolation(UIIssue):
    """UX anti-pattern or accessibility violation."""
    category: str = "ux"  # forms, loading, a11y, error, responsive
    wcag_criterion: str = ""  # e.g., "1.1.1", "2.1.1"

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "category": self.category,
            "wcag_criterion": self.wcag_criterion,
        })
        return d


@dataclass
class UIAuditReport:
    """Aggregated report from UI agents."""
    project_id: str
    total_files: int = 0
    total_issues: int = 0
    reject_count: int = 0
    warning_count: int = 0
    issues: List[UIIssue] = field(default_factory=list)

    def add_issue(self, issue: UIIssue):
        self.issues.append(issue)
        self.total_issues += 1
        if issue.severity == UISeverity.REJECT:
            self.reject_count += 1
        elif issue.severity == UISeverity.WARNING:
            self.warning_count += 1

    @property
    def passed(self) -> bool:
        """Audit passes if no reject-severity issues."""
        return self.reject_count == 0

    @property
    def total_points(self) -> int:
        return sum(i.points for i in self.issues)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "total_files": self.total_files,
            "total_issues": self.total_issues,
            "reject_count": self.reject_count,
            "warning_count": self.warning_count,
            "passed": self.passed,
            "total_points": self.total_points,
            "issues": [i.to_dict() for i in self.issues],
        }
