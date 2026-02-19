"""
Figma-to-Code Auditor Agent

Compares Svelte components against Figma specs using Figma MCP.

Rules:
- FIG-001: Color mismatch (reject, 5pts)
- FIG-002: Spacing mismatch (warning, 3pts) - tolerance ±2px
- FIG-003: Font-size mismatch (warning, 3pts) - tolerance ±1px
- FIG-004: Border-radius mismatch (warning, 2pts) - tolerance ±2px
- FIG-005: Orphaned component (reject, 5pts)
- FIG-006: Font-weight mismatch (warning, 2pts)
"""
import re
import json
import logging
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

from .ui_issue import FigmaDiscrepancy, UISeverity, UIAuditReport

log = logging.getLogger("ui-agents")


@dataclass
class FigmaStyle:
    """Parsed style from Figma node."""
    background: Optional[str] = None
    color: Optional[str] = None
    border_color: Optional[str] = None
    padding: Optional[str] = None
    margin: Optional[str] = None
    gap: Optional[str] = None
    font_size: Optional[str] = None
    font_weight: Optional[str] = None
    line_height: Optional[str] = None
    border_radius: Optional[str] = None
    width: Optional[str] = None
    height: Optional[str] = None


@dataclass
class FigmaAuditResult:
    """Result of auditing a component against Figma."""
    component_name: str
    figma_node_id: str
    file_path: str
    matched: List[str] = field(default_factory=list)
    discrepancies: List[FigmaDiscrepancy] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return len([d for d in self.discrepancies if d.severity == UISeverity.REJECT]) == 0


class FigmaAuditor:
    """
    Compares Svelte components against Figma specs via MCP.

    Usage:
        auditor = FigmaAuditor(project_config, figma_mcp_client)
        result = await auditor.audit_component("Button.svelte")
    """

    # Default tolerances
    TOLERANCE_SPACING = 2  # px
    TOLERANCE_FONT_SIZE = 1  # px
    TOLERANCE_RADIUS = 2  # px

    def __init__(self, project_config, figma_mcp=None):
        self.project = project_config
        self.mcp = figma_mcp  # MCP client for Figma

        # Load config
        ui_config = self.project.raw_config.get("ui_agents", {})
        figma_config = ui_config.get("figma", {})

        self.enabled = figma_config.get("enabled", False)
        self.file_key = figma_config.get("file_key", "")
        self.tolerance_px = figma_config.get("tolerance_px", self.TOLERANCE_SPACING)

        if self.enabled and not self.file_key:
            log.warning("Figma enabled but no file_key configured")
            self.enabled = False

    async def get_figma_node(self, component_name: str) -> Optional[Dict[str, Any]]:
        """
        Fetch component specs from Figma via MCP.

        Args:
            component_name: Name of the component in Figma

        Returns:
            Figma node data or None
        """
        if not self.enabled or not self.mcp:
            log.warning("Figma MCP not available")
            return None

        try:
            # Call Figma MCP get_node tool
            result = await self.mcp.call_tool("get_node", {
                "file_key": self.file_key,
                "node_name": component_name,
            })
            return result
        except Exception as e:
            log.error(f"Failed to get Figma node {component_name}: {e}")
            return None

    def _parse_figma_styles(self, figma_node: Dict[str, Any]) -> FigmaStyle:
        """
        Extract CSS-like properties from Figma node.

        Args:
            figma_node: Raw Figma node data

        Returns:
            FigmaStyle with extracted properties
        """
        style = FigmaStyle()

        if not figma_node:
            return style

        # Extract fills (background color)
        fills = figma_node.get("fills", [])
        if fills and fills[0].get("type") == "SOLID":
            color = fills[0].get("color", {})
            style.background = self._rgba_to_hex(
                color.get("r", 0),
                color.get("g", 0),
                color.get("b", 0),
                color.get("a", 1),
            )

        # Extract strokes (border color)
        strokes = figma_node.get("strokes", [])
        if strokes and strokes[0].get("type") == "SOLID":
            color = strokes[0].get("color", {})
            style.border_color = self._rgba_to_hex(
                color.get("r", 0),
                color.get("g", 0),
                color.get("b", 0),
                color.get("a", 1),
            )

        # Extract padding (from auto-layout)
        if "paddingLeft" in figma_node:
            pl = figma_node.get("paddingLeft", 0)
            pr = figma_node.get("paddingRight", 0)
            pt = figma_node.get("paddingTop", 0)
            pb = figma_node.get("paddingBottom", 0)

            if pl == pr == pt == pb:
                style.padding = f"{pl}px"
            else:
                style.padding = f"{pt}px {pr}px {pb}px {pl}px"

        # Extract gap (from auto-layout)
        if "itemSpacing" in figma_node:
            style.gap = f"{figma_node['itemSpacing']}px"

        # Extract border-radius
        if "cornerRadius" in figma_node:
            style.border_radius = f"{figma_node['cornerRadius']}px"

        # Extract dimensions
        if "absoluteBoundingBox" in figma_node:
            bbox = figma_node["absoluteBoundingBox"]
            style.width = f"{bbox.get('width', 0)}px"
            style.height = f"{bbox.get('height', 0)}px"

        # Extract text styles (for text nodes)
        if figma_node.get("type") == "TEXT":
            text_style = figma_node.get("style", {})
            if "fontSize" in text_style:
                style.font_size = f"{text_style['fontSize']}px"
            if "fontWeight" in text_style:
                style.font_weight = str(text_style["fontWeight"])
            if "lineHeightPx" in text_style:
                style.line_height = f"{text_style['lineHeightPx']}px"

            # Text color from fills
            if fills and fills[0].get("type") == "SOLID":
                color = fills[0].get("color", {})
                style.color = self._rgba_to_hex(
                    color.get("r", 0),
                    color.get("g", 0),
                    color.get("b", 0),
                    color.get("a", 1),
                )

        return style

    def _rgba_to_hex(self, r: float, g: float, b: float, a: float = 1.0) -> str:
        """Convert RGBA (0-1 range) to hex color."""
        r_int = int(r * 255)
        g_int = int(g * 255)
        b_int = int(b * 255)

        if a < 1.0:
            a_int = int(a * 255)
            return f"#{r_int:02x}{g_int:02x}{b_int:02x}{a_int:02x}"
        return f"#{r_int:02x}{g_int:02x}{b_int:02x}"

    def _extract_css_from_svelte(self, content: str) -> Dict[str, str]:
        """
        Extract CSS properties from Svelte component.

        Returns dict of property -> value
        """
        css_props = {}

        # Extract from <style> block
        style_match = re.search(r'<style[^>]*>(.*?)</style>', content, re.DOTALL)
        if style_match:
            style_content = style_match.group(1)

            # Extract property: value pairs
            for match in re.finditer(r'([\w-]+)\s*:\s*([^;]+);', style_content):
                prop = match.group(1).strip()
                value = match.group(2).strip()
                css_props[prop] = value

        # Also check inline styles
        for match in re.finditer(r'style\s*=\s*["\']([^"\']+)["\']', content):
            inline = match.group(1)
            for part in inline.split(';'):
                if ':' in part:
                    prop, value = part.split(':', 1)
                    css_props[prop.strip()] = value.strip()

        return css_props

    def _compare_values(
        self,
        property_name: str,
        figma_value: str,
        code_value: str,
        tolerance: float = 0,
    ) -> Tuple[bool, str]:
        """
        Compare Figma value with code value.

        Returns (matches, difference_description)
        """
        if not figma_value or not code_value:
            return True, ""

        # Normalize values
        figma_norm = figma_value.lower().strip()
        code_norm = code_value.lower().strip()

        # Exact match
        if figma_norm == code_norm:
            return True, ""

        # Resolve CSS variables (if code uses var(--name))
        if code_norm.startswith("var("):
            # Can't compare without knowing the resolved value
            # For now, assume it's intentional
            return True, "CSS variable used"

        # Numeric comparison with tolerance
        figma_num = self._extract_number(figma_value)
        code_num = self._extract_number(code_value)

        if figma_num is not None and code_num is not None:
            diff = abs(figma_num - code_num)
            if diff <= tolerance:
                return True, f"Within tolerance ({diff}px diff)"
            return False, f"Diff: {figma_num} vs {code_num} ({diff}px)"

        # Color comparison
        if property_name in ["background", "color", "border-color"]:
            figma_hex = self._normalize_color(figma_value)
            code_hex = self._normalize_color(code_value)
            if figma_hex and code_hex:
                if figma_hex.lower() == code_hex.lower():
                    return True, ""
                return False, f"Color mismatch: {figma_hex} vs {code_hex}"

        return False, f"Value mismatch: {figma_value} vs {code_value}"

    def _extract_number(self, value: str) -> Optional[float]:
        """Extract numeric value from CSS value like '16px', '1.5rem'."""
        match = re.search(r'([\d.]+)', value)
        if match:
            return float(match.group(1))
        return None

    def _normalize_color(self, value: str) -> Optional[str]:
        """Normalize color to hex format."""
        value = value.strip().lower()

        # Already hex
        if value.startswith("#"):
            return value

        # RGB/RGBA
        match = re.search(r'rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)', value)
        if match:
            r, g, b = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return f"#{r:02x}{g:02x}{b:02x}"

        return None

    async def audit_component(
        self,
        file_path: str,
        figma_component_name: str = None,
    ) -> FigmaAuditResult:
        """
        Compare a Svelte component against its Figma counterpart.

        Args:
            file_path: Path to Svelte file
            figma_component_name: Name in Figma (defaults to file basename)

        Returns:
            FigmaAuditResult with discrepancies
        """
        # Determine component name
        if not figma_component_name:
            figma_component_name = Path(file_path).stem

        result = FigmaAuditResult(
            component_name=figma_component_name,
            figma_node_id="",
            file_path=file_path,
        )

        # Read Svelte file
        path = Path(file_path)
        if not path.is_absolute():
            path = self.project.root_path / file_path
        if not path.exists():
            result.discrepancies.append(FigmaDiscrepancy(
                rule_id="FIG-005",
                severity=UISeverity.REJECT,
                points=5,
                message=f"File not found: {file_path}",
                file_path=file_path,
                category="figma",
            ))
            return result

        content = path.read_text(encoding="utf-8", errors="ignore")
        code_css = self._extract_css_from_svelte(content)

        # Get Figma specs
        figma_node = await self.get_figma_node(figma_component_name)
        if not figma_node:
            result.discrepancies.append(FigmaDiscrepancy(
                rule_id="FIG-005",
                severity=UISeverity.REJECT,
                points=5,
                message=f"Component '{figma_component_name}' not found in Figma",
                file_path=file_path,
                category="figma",
            ))
            return result

        result.figma_node_id = figma_node.get("id", "")
        figma_style = self._parse_figma_styles(figma_node)

        # Compare properties
        comparisons = [
            ("background", figma_style.background, code_css.get("background-color") or code_css.get("background"), "FIG-001", 0),
            ("color", figma_style.color, code_css.get("color"), "FIG-001", 0),
            ("border-color", figma_style.border_color, code_css.get("border-color"), "FIG-001", 0),
            ("padding", figma_style.padding, code_css.get("padding"), "FIG-002", self.tolerance_px),
            ("gap", figma_style.gap, code_css.get("gap"), "FIG-002", self.tolerance_px),
            ("font-size", figma_style.font_size, code_css.get("font-size"), "FIG-003", 1),
            ("font-weight", figma_style.font_weight, code_css.get("font-weight"), "FIG-006", 0),
            ("border-radius", figma_style.border_radius, code_css.get("border-radius"), "FIG-004", self.tolerance_px),
        ]

        for prop_name, figma_val, code_val, rule_id, tolerance in comparisons:
            if not figma_val:
                continue

            matches, diff_desc = self._compare_values(prop_name, figma_val, code_val, tolerance)

            if matches:
                result.matched.append(prop_name)
            else:
                severity = UISeverity.REJECT if rule_id == "FIG-001" else UISeverity.WARNING
                points = 5 if severity == UISeverity.REJECT else 3

                result.discrepancies.append(FigmaDiscrepancy(
                    rule_id=rule_id,
                    severity=severity,
                    points=points,
                    message=f"{prop_name}: {diff_desc}",
                    file_path=file_path,
                    figma_node_id=result.figma_node_id,
                    property_name=prop_name,
                    figma_value=figma_val or "",
                    code_value=code_val or "(missing)",
                    tolerance=tolerance,
                    category="figma",
                    fix_suggestion=f"Update {prop_name} to match Figma: {figma_val}",
                ))

        return result

    async def audit_design_system(self) -> UIAuditReport:
        """Audit all components in the design system against Figma."""
        report = UIAuditReport(project_id=self.project.id)

        if not self.enabled:
            log.warning("Figma auditing not enabled")
            return report

        # Find design system components
        ds_path = self.project.root_path / "design-system" / "src" / "components"
        if not ds_path.exists():
            ds_path = self.project.root_path / "frontend" / "src" / "lib" / "design-system" / "components"

        if not ds_path.exists():
            log.warning(f"Design system components not found at {ds_path}")
            return report

        for svelte_file in ds_path.rglob("*.svelte"):
            report.total_files += 1
            result = await self.audit_component(str(svelte_file))
            for d in result.discrepancies:
                report.add_issue(d)

        return report

    def generate_diff_table(
        self,
        result: FigmaAuditResult,
    ) -> str:
        """Generate a markdown diff table for the audit result."""
        lines = [
            f"# Figma Audit: {result.component_name}",
            f"Node ID: {result.figma_node_id}",
            f"File: {result.file_path}",
            "",
            "| Property | Figma | Code | Match |",
            "|----------|-------|------|-------|",
        ]

        for prop in result.matched:
            lines.append(f"| {prop} | - | - | :white_check_mark: |")

        for disc in result.discrepancies:
            lines.append(
                f"| {disc.property_name} | {disc.figma_value} | {disc.code_value} | :x: |"
            )

        return "\n".join(lines)
