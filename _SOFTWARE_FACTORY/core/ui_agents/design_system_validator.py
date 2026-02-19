"""
Design System Validator Agent

Validates that CSS/Svelte files use design tokens instead of hardcoded values.

Rules:
- DSV-001: Hardcoded hex color (reject, 5pts)
- DSV-002: Hardcoded spacing (reject, 5pts)
- DSV-003: Hardcoded font-family (warning, 2pts)
- DSV-004: Hardcoded border-radius (reject, 5pts)
- DSV-005: Hardcoded shadow (warning, 2pts)
- DSV-006: Tailwind arbitrary color (reject, 5pts)
"""
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass

from .ui_issue import DesignTokenViolation, UISeverity, UIAuditReport

log = logging.getLogger("ui-agents")


# CSS color patterns
HEX_COLOR_PATTERN = re.compile(r'#([0-9A-Fa-f]{3,8})\b')
RGB_PATTERN = re.compile(r'rgb\s*\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)')
RGBA_PATTERN = re.compile(r'rgba\s*\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*[\d.]+\s*\)')
HSL_PATTERN = re.compile(r'hsl\s*\(\s*\d+\s*,\s*[\d.]+%\s*,\s*[\d.]+%\s*\)')

# Spacing patterns (px, rem, em values)
SPACING_PATTERN = re.compile(r':\s*(\d+(?:\.\d+)?)(px|rem|em)\s*[;}]')

# Border-radius patterns
RADIUS_PATTERN = re.compile(r'border-radius\s*:\s*(\d+(?:\.\d+)?)(px|rem|%)')

# Font-family patterns
FONT_PATTERN = re.compile(r'font-family\s*:\s*([^;]+);')

# Shadow patterns
SHADOW_PATTERN = re.compile(r'box-shadow\s*:\s*([^;]+);')

# Tailwind arbitrary value patterns
TAILWIND_ARBITRARY_COLOR = re.compile(r'(?:bg|text|border|fill|stroke)-\[#[0-9A-Fa-f]+\]')
TAILWIND_ARBITRARY_SPACING = re.compile(r'(?:p|m|w|h|gap)-\[\d+(?:px|rem)\]')

# CSS variable usage (allowed)
CSS_VAR_PATTERN = re.compile(r'var\s*\(\s*--[\w-]+\s*\)')

# Default token extraction patterns (overridable via config prefixes)
TOKEN_COLOR_PATTERN = re.compile(r'--color-[\w-]+:\s*(#[0-9A-Fa-f]{3,8})')
TOKEN_SPACING_PATTERN = re.compile(r'--spacing-(\d+):\s*([\d.]+)(rem|px)')
TOKEN_RADIUS_PATTERN = re.compile(r'--radius-[\w]+:\s*([\d.]+)(rem|px|%)')
TOKEN_SHADOW_PATTERN = re.compile(r'--shadow-[\w]+:\s*([^;]+)')
TOKEN_FONT_PATTERN = re.compile(r'--font-[\w-]+:\s*([^;]+)')


def _build_token_patterns(ds_config: dict) -> dict:
    """Build token extraction regex patterns from config prefixes."""
    color_pfx = ds_config.get("color_tokens_prefix", "--color-")
    spacing_pfx = ds_config.get("spacing_tokens_prefix", "--spacing-")
    radius_pfx = ds_config.get("radius_tokens_prefix", "--radius-")
    shadow_pfx = ds_config.get("shadow_tokens_prefix", "--shadow-")
    font_pfx = ds_config.get("font_tokens_prefix", "--font-")

    # Escape dashes for regex
    def esc(s): return re.escape(s)

    return {
        "color": re.compile(rf'{esc(color_pfx)}[\w-]+:\s*(#[0-9A-Fa-f]{{3,8}})'),
        "color_name": re.compile(rf'({esc(color_pfx)}[\w-]+):'),
        "spacing": re.compile(rf'{esc(spacing_pfx)}[\w-]+:\s*([\d.]+)(rem|px)'),
        "spacing_name": re.compile(rf'({esc(spacing_pfx)}[\w-]+):'),
        "radius": re.compile(rf'{esc(radius_pfx)}[\w-]+:\s*([\d.]+)(rem|px|%)'),
        "radius_name": re.compile(rf'({esc(radius_pfx)}[\w-]+):'),
        "shadow": re.compile(rf'{esc(shadow_pfx)}[\w-]+:\s*([^;]+)'),
        "shadow_name": re.compile(rf'({esc(shadow_pfx)}[\w-]+):'),
        "font": re.compile(rf'{esc(font_pfx)}[\w-]+:\s*([^;]+)'),
        "font_name": re.compile(rf'({esc(font_pfx)}[\w-]+):'),
    }


@dataclass
class DesignTokens:
    """Parsed design tokens from CSS."""
    colors: Dict[str, str]      # token_name -> hex_value
    spacing: Dict[str, str]     # scale_number -> rem_value
    radii: Dict[str, str]       # token_name -> value
    shadows: Dict[str, str]     # token_name -> value
    fonts: Dict[str, str]       # token_name -> value

    # Reverse lookup (value -> token)
    color_lookup: Dict[str, str] = None

    def __post_init__(self):
        # Build reverse lookup for colors
        self.color_lookup = {v.lower(): k for k, v in self.colors.items()}


class DesignSystemValidator:
    """
    Validates CSS/Svelte files against design tokens.

    Usage:
        validator = DesignSystemValidator(project_config)
        violations = validator.validate_file("Button.svelte", content)
    """

    def __init__(self, project_config):
        self.project = project_config
        self.tokens: Optional[DesignTokens] = None
        self._load_tokens()

    def _load_tokens(self):
        """Load design tokens from CSS file (supports configurable prefixes)."""
        ui_config = self.project.raw_config.get("ui_agents", {})
        ds_config = ui_config.get("design_system", {})

        # Build patterns from config (supports --ppz-color-* etc.)
        patterns = _build_token_patterns(ds_config)
        self._scan_extensions = ds_config.get("scan_extensions", [".svelte", ".css", ".scss", ".php"])

        tokens_file = ds_config.get("tokens_file")
        if not tokens_file:
            log.warning("No tokens_file configured in ui_agents.design_system")
            self.tokens = DesignTokens({}, {}, {}, {}, {})
            return

        tokens_path = self.project.root_path / tokens_file
        if not tokens_path.exists():
            log.warning(f"Tokens file not found: {tokens_path}")
            self.tokens = DesignTokens({}, {}, {}, {}, {})
            return

        content = tokens_path.read_text(encoding="utf-8", errors="ignore")

        # Extract tokens using configurable patterns
        colors = {}
        for match in patterns["color"].finditer(content):
            line = content[max(0, match.start()-80):match.end()]
            token_match = patterns["color_name"].search(line)
            if token_match:
                colors[token_match.group(1)] = match.group(1).lower()

        spacing = {}
        for match in patterns["spacing"].finditer(content):
            line = content[max(0, match.start()-80):match.end()]
            token_match = patterns["spacing_name"].search(line)
            if token_match:
                spacing[token_match.group(1)] = f"{match.group(1)}{match.group(2)}"

        radii = {}
        for match in patterns["radius"].finditer(content):
            line = content[max(0, match.start()-80):match.end()]
            token_match = patterns["radius_name"].search(line)
            if token_match:
                radii[token_match.group(1)] = f"{match.group(1)}{match.group(2)}"

        shadows = {}
        for match in patterns["shadow"].finditer(content):
            line = content[max(0, match.start()-80):match.end()]
            token_match = patterns["shadow_name"].search(line)
            if token_match:
                shadows[token_match.group(1)] = match.group(1).strip()

        fonts = {}
        for match in patterns["font"].finditer(content):
            line = content[max(0, match.start()-80):match.end()]
            token_match = patterns["font_name"].search(line)
            if token_match:
                fonts[token_match.group(1)] = match.group(1).strip()

        self.tokens = DesignTokens(
            colors=colors,
            spacing=spacing,
            radii=radii,
            shadows=shadows,
            fonts=fonts,
        )

        log.info(f"Loaded tokens: {len(colors)} colors, {len(spacing)} spacing, "
                 f"{len(radii)} radii, {len(shadows)} shadows, {len(fonts)} fonts")

    def list_tokens(self) -> str:
        """List all available design tokens."""
        if not self.tokens:
            return "No tokens loaded"

        lines = ["# Design Tokens\n"]

        lines.append("## Colors")
        for name, value in sorted(self.tokens.colors.items()):
            lines.append(f"  {name}: {value}")

        lines.append("\n## Spacing")
        for scale, value in sorted(self.tokens.spacing.items(), key=lambda x: int(x[0])):
            lines.append(f"  --spacing-{scale}: {value}")

        lines.append("\n## Border Radius")
        for name, value in sorted(self.tokens.radii.items()):
            lines.append(f"  {name}: {value}")

        lines.append("\n## Shadows")
        for name, value in sorted(self.tokens.shadows.items()):
            lines.append(f"  {name}: {value[:50]}...")

        lines.append("\n## Fonts")
        for name, value in sorted(self.tokens.fonts.items()):
            lines.append(f"  {name}: {value[:50]}...")

        return "\n".join(lines)

    def validate_file(self, file_path: str, content: str = None) -> List[DesignTokenViolation]:
        """
        Validate a file against design tokens.

        Args:
            file_path: Path to the file
            content: File content (optional, will read if not provided)

        Returns:
            List of design token violations
        """
        violations = []

        if content is None:
            path = Path(file_path)
            if not path.is_absolute():
                path = self.project.root_path / file_path
            if not path.exists():
                return violations
            content = path.read_text(encoding="utf-8", errors="ignore")

        lines = content.split("\n")

        for line_num, line in enumerate(lines, 1):
            # Skip comments
            if line.strip().startswith("//") or line.strip().startswith("/*"):
                continue

            # Skip lines with CSS variables (allowed)
            if CSS_VAR_PATTERN.search(line):
                # Still check for hardcoded values alongside var()
                pass

            # DSV-001: Hardcoded hex colors
            for match in HEX_COLOR_PATTERN.finditer(line):
                hex_value = f"#{match.group(1).lower()}"
                if not self._is_color_in_tokens(hex_value):
                    suggested = self._suggest_color_token(hex_value)
                    violations.append(DesignTokenViolation(
                        rule_id="DSV-001",
                        severity=UISeverity.REJECT,
                        points=5,
                        message=f"Hardcoded color {hex_value} not in design tokens",
                        file_path=file_path,
                        line=line_num,
                        context=line.strip()[:80],
                        hardcoded_value=hex_value,
                        suggested_token=suggested,
                        category="color",
                        fix_suggestion=f"Replace with var({suggested})" if suggested else "Add to design tokens",
                    ))

            # DSV-006: Tailwind arbitrary colors
            for match in TAILWIND_ARBITRARY_COLOR.finditer(line):
                violations.append(DesignTokenViolation(
                    rule_id="DSV-006",
                    severity=UISeverity.REJECT,
                    points=5,
                    message=f"Tailwind arbitrary color: {match.group()}",
                    file_path=file_path,
                    line=line_num,
                    context=line.strip()[:80],
                    hardcoded_value=match.group(),
                    suggested_token="Use semantic color class (e.g., bg-primary)",
                    category="color",
                    fix_suggestion="Replace with Tailwind theme color or CSS variable",
                ))

            # DSV-002: Hardcoded spacing (in specific properties)
            if re.search(r'(padding|margin|gap|top|left|right|bottom)\s*:', line):
                for match in SPACING_PATTERN.finditer(line):
                    value = f"{match.group(1)}{match.group(2)}"
                    if not self._is_spacing_in_tokens(value):
                        suggested = self._suggest_spacing_token(value)
                        violations.append(DesignTokenViolation(
                            rule_id="DSV-002",
                            severity=UISeverity.REJECT,
                            points=5,
                            message=f"Hardcoded spacing {value}",
                            file_path=file_path,
                            line=line_num,
                            context=line.strip()[:80],
                            hardcoded_value=value,
                            suggested_token=suggested,
                            category="spacing",
                            fix_suggestion=f"Replace with var(--spacing-{suggested})" if suggested else "Use spacing token",
                        ))

            # DSV-004: Hardcoded border-radius
            for match in RADIUS_PATTERN.finditer(line):
                value = f"{match.group(1)}{match.group(2)}"
                if not self._is_radius_in_tokens(value):
                    violations.append(DesignTokenViolation(
                        rule_id="DSV-004",
                        severity=UISeverity.REJECT,
                        points=5,
                        message=f"Hardcoded border-radius {value}",
                        file_path=file_path,
                        line=line_num,
                        context=line.strip()[:80],
                        hardcoded_value=value,
                        suggested_token="--radius-md",
                        category="radius",
                        fix_suggestion="Use var(--radius-*) token",
                    ))

            # DSV-003: Hardcoded font-family
            for match in FONT_PATTERN.finditer(line):
                font_value = match.group(1).strip()
                if not font_value.startswith("var("):
                    violations.append(DesignTokenViolation(
                        rule_id="DSV-003",
                        severity=UISeverity.WARNING,
                        points=2,
                        message=f"Hardcoded font-family: {font_value[:30]}",
                        file_path=file_path,
                        line=line_num,
                        context=line.strip()[:80],
                        hardcoded_value=font_value[:50],
                        suggested_token="--font-family-base",
                        category="typography",
                        fix_suggestion="Use var(--font-family-*) token",
                    ))

            # DSV-005: Hardcoded box-shadow
            for match in SHADOW_PATTERN.finditer(line):
                shadow_value = match.group(1).strip()
                if not shadow_value.startswith("var(") and shadow_value != "none":
                    violations.append(DesignTokenViolation(
                        rule_id="DSV-005",
                        severity=UISeverity.WARNING,
                        points=2,
                        message="Hardcoded box-shadow",
                        file_path=file_path,
                        line=line_num,
                        context=line.strip()[:80],
                        hardcoded_value=shadow_value[:50],
                        suggested_token="--shadow-md",
                        category="shadow",
                        fix_suggestion="Use var(--shadow-*) token",
                    ))

        return violations

    def _is_color_in_tokens(self, hex_value: str) -> bool:
        """Check if a color is in the design tokens."""
        if not self.tokens or not self.tokens.colors:
            return True  # No tokens loaded = skip validation
        return hex_value.lower() in self.tokens.color_lookup

    def _suggest_color_token(self, hex_value: str) -> Optional[str]:
        """Suggest the closest color token for a given hex value."""
        if not self.tokens:
            return None

        # Exact match
        if hex_value.lower() in self.tokens.color_lookup:
            return self.tokens.color_lookup[hex_value.lower()]

        # TODO: Implement color distance calculation for suggestions
        return None

    def _is_spacing_in_tokens(self, value: str) -> bool:
        """Check if a spacing value is in the tokens."""
        if not self.tokens or not self.tokens.spacing:
            return True
        return value in self.tokens.spacing.values()

    def _suggest_spacing_token(self, value: str) -> Optional[str]:
        """Suggest the closest spacing token."""
        if not self.tokens or not self.tokens.spacing:
            return None

        # Try to find exact match
        for scale, token_value in self.tokens.spacing.items():
            if token_value == value:
                return scale

        # TODO: Suggest closest value
        return None

    def _is_radius_in_tokens(self, value: str) -> bool:
        """Check if a border-radius value is in tokens."""
        if not self.tokens or not self.tokens.radii:
            return True
        return value in self.tokens.radii.values()

    def validate_content(self, content: str, filename: str = "") -> List[DesignTokenViolation]:
        """
        Validate content directly (for adversarial gate integration).

        Args:
            content: The CSS/Svelte code content
            filename: Optional filename for context

        Returns:
            List of design token violations
        """
        return self.validate_file(filename, content=content)

    def validate_project(self) -> UIAuditReport:
        """Validate all UI files in the project."""
        report = UIAuditReport(project_id=self.project.id)

        # Find UI files (configurable extensions for PHP/Svelte/CSS projects)
        extensions = getattr(self, '_scan_extensions', [".svelte", ".css", ".scss", ".php"])
        for ext in extensions:
            for file_path in self.project.root_path.rglob(f"*{ext}"):
                # Skip node_modules and build directories
                if "node_modules" in str(file_path) or "dist" in str(file_path):
                    continue

                report.total_files += 1
                violations = self.validate_file(str(file_path))
                for v in violations:
                    report.add_issue(v)

        return report
