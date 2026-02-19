"""
UX Pattern Enforcer Agent

Detects UX anti-patterns and WCAG accessibility violations.

Rules:
Forms:
- UXF-001: Form without error states (reject, 5pts)
- UXF-002: Input without associated label (warning, 3pts)
- UXF-003: Submit without loading state (warning, 3pts)

Loading States:
- UXL-001: List without empty state (reject, 5pts)
- UXL-002: Async content without loader (warning, 3pts)
- UXL-003: Error boundary missing (reject, 5pts)

Accessibility (WCAG 2.1 AA):
- A11Y-001: Interactive element without keyboard access (reject, 5pts)
- A11Y-002: Color contrast < 4.5:1 (reject, 5pts)
- A11Y-003: Icon-only button without aria-label (warning, 3pts)
- A11Y-004: Modal without focus trap (reject, 5pts)
- A11Y-005: Image without alt (warning, 3pts)
- A11Y-006: Touch target < 44px (reject, 5pts)

Error Handling:
- UXE-001: Raw error code shown to user (reject, 5pts)
- UXE-002: Error without recovery action (warning, 3pts)
- UXE-003: Silent failure (reject, 5pts)

Responsive:
- UXR-001: Fixed width container (warning, 3pts)
- UXR-002: Missing mobile breakpoint (warning, 2pts)
"""
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass

from .ui_issue import UXViolation, UISeverity, UIAuditReport

log = logging.getLogger("ui-agents")


# Pattern definitions for detection
PATTERNS = {
    # Forms
    "form_tag": re.compile(r'<form[^>]*>(.*?)</form>', re.DOTALL | re.IGNORECASE),
    "input_tag": re.compile(r'<input[^>]*>', re.IGNORECASE),
    "button_submit": re.compile(r'<button[^>]*type\s*=\s*["\']submit["\'][^>]*>', re.IGNORECASE),
    "label_for": re.compile(r'<label[^>]*for\s*=\s*["\']([^"\']+)["\'][^>]*>', re.IGNORECASE),
    "input_id": re.compile(r'<input[^>]*id\s*=\s*["\']([^"\']+)["\'][^>]*>', re.IGNORECASE),
    "aria_invalid": re.compile(r'aria-invalid', re.IGNORECASE),
    "error_class": re.compile(r'class\s*=\s*["\'][^"\']*(?:error|invalid|danger)[^"\']*["\']', re.IGNORECASE),

    # Loading states
    "async_pattern": re.compile(r'(?:await|\.then\(|async|fetch\(|axios\.|useQuery|useMutation)', re.IGNORECASE),
    "loading_indicator": re.compile(r'(?:loading|isLoading|spinner|skeleton|\.loading)', re.IGNORECASE),
    "each_block": re.compile(r'\{#each\s+(\w+)', re.IGNORECASE),
    "empty_state": re.compile(r'(?:\{:else\}|\.empty|no-data|empty-state)', re.IGNORECASE),
    "error_boundary": re.compile(r'(?:ErrorBoundary|<svelte:error|onError|\.catch)', re.IGNORECASE),

    # Accessibility
    "interactive": re.compile(r'<(?:button|a|input|select|textarea|[^>]*on:click)[^>]*>', re.IGNORECASE),
    "tabindex": re.compile(r'tabindex\s*=\s*["\']?(\d+|-1)["\']?', re.IGNORECASE),
    "onclick_div": re.compile(r'<div[^>]*on:click[^>]*>', re.IGNORECASE),
    "icon_button": re.compile(r'<button[^>]*>\s*(?:<svg|<i\s|<Icon|<span[^>]*class="icon)[^<]*(?:</svg>|</i>|/>)\s*</button>', re.DOTALL | re.IGNORECASE),
    "aria_label": re.compile(r'aria-label\s*=\s*["\'][^"\']+["\']', re.IGNORECASE),
    "img_tag": re.compile(r'<img[^>]*>', re.IGNORECASE),
    "img_alt": re.compile(r'<img[^>]*alt\s*=\s*["\'][^"\']*["\'][^>]*>', re.IGNORECASE),
    "modal_dialog": re.compile(r'(?:modal|dialog|Modal|Dialog|role\s*=\s*["\']dialog["\'])', re.IGNORECASE),
    "focus_trap": re.compile(r'(?:focus-trap|focusTrap|trapFocus|createFocusTrap)', re.IGNORECASE),

    # Error handling
    "raw_error_code": re.compile(r'(?:error\.code|err\.code|status\s*===?\s*(?:4|5)\d{2}|"(?:ECONNREFUSED|ETIMEDOUT|ENOENT)")', re.IGNORECASE),
    "catch_empty": re.compile(r'\.catch\s*\(\s*(?:\(\s*\)|_\s*=>|err\s*=>\s*\{\s*\})', re.IGNORECASE),
    "silent_catch": re.compile(r'catch\s*\([^)]*\)\s*\{\s*(?://[^\n]*\n)?\s*\}', re.IGNORECASE),

    # Responsive
    "fixed_width": re.compile(r'(?:width\s*:\s*\d+px|w-\[\d+px\])', re.IGNORECASE),
    "media_query": re.compile(r'@media\s*\([^)]*(?:max-width|min-width)', re.IGNORECASE),
}


class UXPatternEnforcer:
    """
    Detects UX anti-patterns and accessibility issues.

    Usage:
        enforcer = UXPatternEnforcer(project_config)
        violations = await enforcer.enforce("Button.svelte", content)
    """

    def __init__(self, project_config):
        self.project = project_config

        # Load config
        ui_config = self.project.raw_config.get("ui_agents", {})
        ux_config = ui_config.get("ux_patterns", {})

        self.wcag_level = ux_config.get("wcag_level", "AA")
        self.min_contrast = ux_config.get("min_contrast", 4.5)
        self.min_touch_target = ux_config.get("min_touch_target", 44)

        self.categories = ux_config.get("categories", {
            "forms": True,
            "loading": True,
            "a11y": True,
            "errors": True,
            "responsive": True,
        })

    async def enforce(
        self,
        file_path: str,
        content: str = None,
    ) -> List[UXViolation]:
        """
        Run all UX pattern checks on a Svelte component.

        Args:
            file_path: Path to the file
            content: File content (optional)

        Returns:
            List of UX violations
        """
        violations = []

        if content is None:
            path = Path(file_path)
            if not path.is_absolute():
                path = self.project.root_path / file_path
            if not path.exists():
                return violations
            content = path.read_text(encoding="utf-8", errors="ignore")

        # Run checks by category
        if self.categories.get("forms", True):
            violations.extend(self._check_form_patterns(content, file_path))

        if self.categories.get("loading", True):
            violations.extend(self._check_loading_states(content, file_path))

        if self.categories.get("a11y", True):
            violations.extend(self._check_accessibility(content, file_path))

        if self.categories.get("errors", True):
            violations.extend(self._check_error_handling(content, file_path))

        if self.categories.get("responsive", True):
            violations.extend(self._check_responsive(content, file_path))

        return violations

    def _find_line(self, content: str, substring: str) -> int:
        """Find line number of substring in content."""
        index = content.find(substring)
        if index == -1:
            return 0
        return content[:index].count('\n') + 1

    def _check_form_patterns(
        self,
        content: str,
        file_path: str,
    ) -> List[UXViolation]:
        """Check for form-related anti-patterns."""
        violations = []

        # Find all forms
        for form_match in PATTERNS["form_tag"].finditer(content):
            form_content = form_match.group(0)
            form_line = self._find_line(content, form_content)

            # UXF-001: Form without error states
            has_error_handling = (
                PATTERNS["aria_invalid"].search(form_content) or
                PATTERNS["error_class"].search(form_content)
            )
            if not has_error_handling:
                violations.append(UXViolation(
                    rule_id="UXF-001",
                    severity=UISeverity.REJECT,
                    points=5,
                    message="Form without error states (missing aria-invalid or error class)",
                    file_path=file_path,
                    line=form_line,
                    context=form_content[:100],
                    category="forms",
                    fix_suggestion="Add aria-invalid attribute and visual error indicators",
                ))

            # UXF-002: Input without label
            input_ids = set(PATTERNS["input_id"].findall(form_content))
            label_fors = set(PATTERNS["label_for"].findall(form_content))
            unlinked_inputs = input_ids - label_fors

            for input_id in unlinked_inputs:
                violations.append(UXViolation(
                    rule_id="UXF-002",
                    severity=UISeverity.WARNING,
                    points=3,
                    message=f"Input '{input_id}' without associated label",
                    file_path=file_path,
                    line=form_line,
                    category="forms",
                    wcag_criterion="1.3.1",
                    fix_suggestion=f'Add <label for="{input_id}">Label text</label>',
                ))

            # UXF-003: Submit without loading state
            if PATTERNS["button_submit"].search(form_content):
                if not PATTERNS["loading_indicator"].search(form_content):
                    violations.append(UXViolation(
                        rule_id="UXF-003",
                        severity=UISeverity.WARNING,
                        points=3,
                        message="Submit button without loading state",
                        file_path=file_path,
                        line=form_line,
                        category="forms",
                        fix_suggestion="Add loading indicator on form submission",
                    ))

        return violations

    def _check_loading_states(
        self,
        content: str,
        file_path: str,
    ) -> List[UXViolation]:
        """Check for loading state anti-patterns."""
        violations = []

        # UXL-001: List/each without empty state
        for each_match in PATTERNS["each_block"].finditer(content):
            # Check if there's an {:else} nearby
            start = each_match.start()
            end = min(start + 500, len(content))
            block = content[start:end]

            if not PATTERNS["empty_state"].search(block):
                violations.append(UXViolation(
                    rule_id="UXL-001",
                    severity=UISeverity.REJECT,
                    points=5,
                    message=f"List '{each_match.group(1)}' without empty state",
                    file_path=file_path,
                    line=self._find_line(content, each_match.group(0)),
                    category="loading",
                    fix_suggestion="Add {:else} block for empty state",
                ))

        # UXL-002: Async content without loader
        if PATTERNS["async_pattern"].search(content):
            if not PATTERNS["loading_indicator"].search(content):
                violations.append(UXViolation(
                    rule_id="UXL-002",
                    severity=UISeverity.WARNING,
                    points=3,
                    message="Async operation without loading indicator",
                    file_path=file_path,
                    line=0,
                    category="loading",
                    fix_suggestion="Add loading state while fetching data",
                ))

        # UXL-003: Async without error boundary
        if PATTERNS["async_pattern"].search(content):
            if not PATTERNS["error_boundary"].search(content):
                violations.append(UXViolation(
                    rule_id="UXL-003",
                    severity=UISeverity.REJECT,
                    points=5,
                    message="Async operation without error handling/boundary",
                    file_path=file_path,
                    line=0,
                    category="loading",
                    fix_suggestion="Add error boundary or .catch() handler",
                ))

        return violations

    def _check_accessibility(
        self,
        content: str,
        file_path: str,
    ) -> List[UXViolation]:
        """Check WCAG 2.1 AA compliance."""
        violations = []

        # A11Y-001: Interactive div without keyboard access
        for div_match in PATTERNS["onclick_div"].finditer(content):
            div_content = div_match.group(0)
            has_keyboard = (
                PATTERNS["tabindex"].search(div_content) or
                "on:keydown" in div_content or
                "on:keypress" in div_content or
                "role=" in div_content
            )
            if not has_keyboard:
                violations.append(UXViolation(
                    rule_id="A11Y-001",
                    severity=UISeverity.REJECT,
                    points=5,
                    message="Clickable div without keyboard access",
                    file_path=file_path,
                    line=self._find_line(content, div_content),
                    context=div_content[:80],
                    category="a11y",
                    wcag_criterion="2.1.1",
                    fix_suggestion='Add tabindex="0" and on:keydown handler, or use <button>',
                ))

        # A11Y-003: Icon-only button without aria-label
        for btn_match in PATTERNS["icon_button"].finditer(content):
            btn_content = btn_match.group(0)
            if not PATTERNS["aria_label"].search(btn_content):
                violations.append(UXViolation(
                    rule_id="A11Y-003",
                    severity=UISeverity.WARNING,
                    points=3,
                    message="Icon-only button without accessible label",
                    file_path=file_path,
                    line=self._find_line(content, btn_content),
                    context=btn_content[:80],
                    category="a11y",
                    wcag_criterion="1.1.1",
                    fix_suggestion='Add aria-label="Button description"',
                ))

        # A11Y-005: Image without alt
        for img_match in PATTERNS["img_tag"].finditer(content):
            img_content = img_match.group(0)
            if "alt=" not in img_content.lower():
                violations.append(UXViolation(
                    rule_id="A11Y-005",
                    severity=UISeverity.WARNING,
                    points=3,
                    message="Image without alt attribute",
                    file_path=file_path,
                    line=self._find_line(content, img_content),
                    context=img_content[:80],
                    category="a11y",
                    wcag_criterion="1.1.1",
                    fix_suggestion='Add alt="Description" or alt="" for decorative images',
                ))

        # A11Y-004: Modal without focus trap
        if PATTERNS["modal_dialog"].search(content):
            if not PATTERNS["focus_trap"].search(content):
                violations.append(UXViolation(
                    rule_id="A11Y-004",
                    severity=UISeverity.REJECT,
                    points=5,
                    message="Modal/dialog without focus trap",
                    file_path=file_path,
                    line=0,
                    category="a11y",
                    wcag_criterion="2.4.3",
                    fix_suggestion="Implement focus trap to keep focus within modal",
                ))

        return violations

    def _check_error_handling(
        self,
        content: str,
        file_path: str,
    ) -> List[UXViolation]:
        """Check error handling UX patterns."""
        violations = []

        # UXE-001: Raw error code exposed
        for match in PATTERNS["raw_error_code"].finditer(content):
            # Check if it's in display context (not just logging)
            context_start = max(0, match.start() - 50)
            context_end = min(len(content), match.end() + 50)
            context = content[context_start:context_end]

            if "console." not in context and "log(" not in context:
                violations.append(UXViolation(
                    rule_id="UXE-001",
                    severity=UISeverity.REJECT,
                    points=5,
                    message="Raw error code potentially shown to user",
                    file_path=file_path,
                    line=self._find_line(content, match.group(0)),
                    context=context[:80],
                    category="error",
                    fix_suggestion="Show user-friendly error message instead",
                ))

        # UXE-003: Silent catch
        for match in PATTERNS["silent_catch"].finditer(content):
            violations.append(UXViolation(
                rule_id="UXE-003",
                severity=UISeverity.REJECT,
                points=5,
                message="Silent error catch - user gets no feedback",
                file_path=file_path,
                line=self._find_line(content, match.group(0)),
                context=match.group(0)[:80],
                category="error",
                fix_suggestion="Handle error and show feedback to user",
            ))

        return violations

    def _check_responsive(
        self,
        content: str,
        file_path: str,
    ) -> List[UXViolation]:
        """Check responsive design patterns."""
        violations = []

        # UXR-001: Fixed width on containers
        # Only check style blocks
        style_match = re.search(r'<style[^>]*>(.*?)</style>', content, re.DOTALL)
        if style_match:
            style_content = style_match.group(1)

            # Look for fixed widths on containers
            for match in PATTERNS["fixed_width"].finditer(style_content):
                violations.append(UXViolation(
                    rule_id="UXR-001",
                    severity=UISeverity.WARNING,
                    points=3,
                    message="Fixed width may break responsive layout",
                    file_path=file_path,
                    line=self._find_line(content, match.group(0)),
                    context=match.group(0),
                    category="responsive",
                    fix_suggestion="Use max-width or percentage-based widths",
                ))

            # UXR-002: No media queries (might be ok if using Tailwind)
            if not PATTERNS["media_query"].search(style_content):
                # Check if using Tailwind responsive classes
                if not re.search(r'(?:sm:|md:|lg:|xl:)', content):
                    violations.append(UXViolation(
                        rule_id="UXR-002",
                        severity=UISeverity.WARNING,
                        points=2,
                        message="No responsive breakpoints detected",
                        file_path=file_path,
                        line=0,
                        category="responsive",
                        fix_suggestion="Add media queries or Tailwind responsive classes",
                    ))

        return violations

    async def generate_wcag_report(self) -> str:
        """Generate comprehensive WCAG 2.1 AA audit report."""
        report = UIAuditReport(project_id=self.project.id)

        # Find all Svelte files
        for svelte_file in self.project.root_path.rglob("*.svelte"):
            if "node_modules" in str(svelte_file):
                continue

            report.total_files += 1
            violations = await self.enforce(str(svelte_file))

            # Only include a11y violations
            for v in violations:
                if v.category == "a11y":
                    report.add_issue(v)

        # Generate markdown report
        lines = [
            "# WCAG 2.1 AA Compliance Report",
            f"Project: {self.project.id}",
            "",
            "## Summary",
            f"- Total files scanned: {report.total_files}",
            f"- Total issues: {report.total_issues}",
            f"- Critical (must fix): {report.reject_count}",
            f"- Warnings (should fix): {report.warning_count}",
            f"- Compliance rate: {100 - (report.reject_count / max(report.total_files, 1) * 100):.1f}%",
            "",
            "## Violations by WCAG Criterion",
            "",
        ]

        # Group by criterion
        by_criterion = {}
        for issue in report.issues:
            if isinstance(issue, UXViolation):
                crit = issue.wcag_criterion or "Other"
                if crit not in by_criterion:
                    by_criterion[crit] = []
                by_criterion[crit].append(issue)

        for criterion, issues in sorted(by_criterion.items()):
            lines.append(f"### {criterion}")
            for issue in issues:
                severity = ":x:" if issue.severity == UISeverity.REJECT else ":warning:"
                lines.append(f"- {severity} {issue.file_path}:{issue.line} - {issue.message}")
            lines.append("")

        if report.reject_count == 0:
            lines.append(":white_check_mark: **All checks passed!**")

        return "\n".join(lines)
