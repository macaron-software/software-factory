"""
UI Agents for the Software Factory.

Three specialized agents for IHM/UX/UI validation:
1. DesignSystemValidator - Validates design token usage
2. FigmaAuditor - Compares components with Figma specs
3. UXPatternEnforcer - Detects UX anti-patterns and WCAG violations
"""

from .ui_issue import (
    UIIssue,
    UISeverity,
    DesignTokenViolation,
    FigmaDiscrepancy,
    UXViolation,
    UIAuditReport,
)
from .design_system_validator import DesignSystemValidator
from .figma_auditor import FigmaAuditor, FigmaAuditResult
from .ux_pattern_enforcer import UXPatternEnforcer

__all__ = [
    # Issue types
    "UIIssue",
    "UISeverity",
    "DesignTokenViolation",
    "FigmaDiscrepancy",
    "UXViolation",
    "UIAuditReport",
    # Agents
    "DesignSystemValidator",
    "FigmaAuditor",
    "FigmaAuditResult",
    "UXPatternEnforcer",
]
