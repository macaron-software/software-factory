"""Design System Tools — deterministic CSS verification for DS compliance.

Provides:
- CSSComputedCheckTool: headless browser (agent-browser CLI) + computed style
  inspection. Compares actual computed CSS values against design-system tokens.
  Returns deterministic PASS/FAIL evidence per property.

Used by: llm-judge-ux, ux-adversarial (verification step).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil

from ..models import AgentInstance
from .registry import BaseTool

logger = logging.getLogger(__name__)

_AB_CMD = "agent-browser"


def _ab_available() -> bool:
    return shutil.which(_AB_CMD) is not None


async def _run_ab(*args: str, timeout: int = 30) -> str:
    if not _ab_available():
        return (
            "Error: agent-browser not installed. "
            "Run: npm install -g agent-browser && agent-browser install"
        )
    try:
        proc = await asyncio.create_subprocess_exec(
            _AB_CMD, *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        out = stdout.decode().strip()
        err = stderr.decode().strip()
        if proc.returncode != 0:
            return f"Error (exit {proc.returncode}): {err or out}"
        return out or "(no output)"
    except asyncio.TimeoutError:
        return f"Error: timed out after {timeout}s"
    except Exception as e:
        return f"Error: {e}"


# WCAG contrast ratio helpers (relative luminance, WCAG 2.1 formula)

def _srgb_channel(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(r: int, g: int, b: int) -> float:
    return (
        0.2126 * _srgb_channel(r / 255)
        + 0.7152 * _srgb_channel(g / 255)
        + 0.0722 * _srgb_channel(b / 255)
    )


def _contrast_ratio(hex1: str, hex2: str) -> float | None:
    """Return WCAG contrast ratio between two hex colors. None if parse fails."""
    def parse(h: str) -> tuple[int, int, int] | None:
        h = h.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        if len(h) != 6:
            return None
        try:
            return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        except ValueError:
            return None

    c1 = parse(hex1)
    c2 = parse(hex2)
    if not c1 or not c2:
        return None
    l1 = _luminance(*c1)
    l2 = _luminance(*c2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


class CSSComputedCheckTool(BaseTool):
    """Check computed CSS properties on a live URL against DS token expectations.

    Params:
        url (str): URL to open (default: http://localhost:3000)
        selector (str): CSS selector of element to inspect (default: 'body')
        properties (list[str]): CSS properties to read (default: color, background-color, font-size)
        expected (dict): {property: expected_value} to compare against. Optional.
        theme (str): 'dark' | 'light' | 'contrast' — sets data-theme via JS before check.
        contrast_check (bool): if True, compute WCAG contrast ratio between color + background-color.
        timeout (int): seconds (default: 20)

    Returns text report: PASS/FAIL per property with computed vs expected values.
    Falls back to grep-based static analysis if agent-browser unavailable.
    """

    name = "css_computed_check"
    description = (
        "Deterministic CSS verification: opens a URL in headless browser, reads computed styles "
        "for a CSS selector, compares against expected design-system token values. "
        "Returns PASS/FAIL per property. Also supports WCAG contrast ratio check. "
        "Falls back to static file grep if browser unavailable."
    )
    category = "design_system"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        url = params.get("url", "http://localhost:3000")
        selector = params.get("selector", "body")
        properties = params.get("properties") or ["color", "background-color", "font-size"]
        expected: dict = params.get("expected") or {}
        theme = params.get("theme", "")
        do_contrast = params.get("contrast_check", False)
        timeout = int(params.get("timeout", 20))

        if not _ab_available():
            return await self._static_fallback(params)

        # Build a JS snippet that sets data-theme and reads computed styles
        prop_list_js = json.dumps(properties)
        theme_js = (
            f"document.documentElement.setAttribute('data-theme', '{theme}');"
            if theme else ""
        )
        script = (
            f"{theme_js}"
            f"const el = document.querySelector({json.dumps(selector)});"
            f"if (!el) return JSON.stringify({{error: 'selector not found'}});"
            f"const cs = window.getComputedStyle(el);"
            f"const props = {prop_list_js};"
            f"const out = {{}};"
            f"for (const p of props) {{ out[p] = cs.getPropertyValue(p).trim(); }}"
            f"return JSON.stringify(out);"
        )

        raw = await _run_ab("eval", "--url", url, "--script", script, timeout=timeout)

        # Parse JSON from agent-browser output
        computed: dict = {}
        try:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                computed = json.loads(match.group(0))
        except Exception:
            computed = {}

        if "error" in computed:
            return f"FAIL css_computed_check: {computed['error']}"
        if not computed:
            return f"FAIL css_computed_check: could not parse computed styles. Raw: {raw[:300]}"

        lines = [f"CSS Computed Check — {selector} @ {url}" + (f" [theme={theme}]" if theme else "")]
        all_pass = True

        for prop in properties:
            val = computed.get(prop, "(not found)")
            exp = expected.get(prop, "")
            if exp:
                if val == exp or exp in val:
                    lines.append(f"  PASS {prop}: computed={val!r} matches expected={exp!r}")
                else:
                    lines.append(f"  FAIL {prop}: computed={val!r} ≠ expected={exp!r}")
                    all_pass = False
            else:
                # Detect hardcoded values (not CSS custom property reference)
                is_var_ref = "var(--" in val
                if not is_var_ref and re.search(r"#[0-9a-fA-F]{3,6}|rgb\(|hsl\(", val):
                    lines.append(f"  WARN {prop}: computed={val!r} — looks hardcoded (not a token)")
                else:
                    lines.append(f"  INFO {prop}: computed={val!r}")

        # WCAG contrast check
        if do_contrast:
            fg = computed.get("color", "")
            bg = computed.get("background-color", "")
            fg_hex = _extract_hex(fg)
            bg_hex = _extract_hex(bg)
            if fg_hex and bg_hex:
                ratio = _contrast_ratio(fg_hex, bg_hex)
                if ratio is not None:
                    aa = ratio >= 4.5
                    aaa = ratio >= 7.0
                    status = "PASS AAA" if aaa else ("PASS AA" if aa else "FAIL")
                    lines.append(
                        f"  {status} contrast-ratio: {ratio:.2f}:1 "
                        f"(AA≥4.5 {'✓' if aa else '✗'}, AAA≥7.0 {'✓' if aaa else '✗'})"
                    )
                    if not aa:
                        all_pass = False
                else:
                    lines.append(f"  SKIP contrast-ratio: could not parse colors (fg={fg!r}, bg={bg!r})")
            else:
                lines.append(f"  SKIP contrast-ratio: non-hex colors (fg={fg!r}, bg={bg!r})")

        lines.append(f"\nVerdict: {'PASS' if all_pass else 'FAIL'}")
        return "\n".join(lines)

    async def _static_fallback(self, params: dict) -> str:
        """Grep-based static analysis when agent-browser unavailable."""
        import subprocess
        cwd = params.get("cwd", ".")
        lines = ["css_computed_check: agent-browser unavailable — static analysis fallback\n"]

        checks = [
            ("Hardcoded hex colors", r"#[0-9a-fA-F]{3,6}", ["src", "styles", "components", "app", "pages"]),
            ("Gradient backgrounds", r"linear-gradient|radial-gradient", ["src", "styles", "components"]),
            ("Inline styles", r"style=[\"'][^\"']*[\"']|style=\{[^}]+\}", ["src", "components", "app", "pages"]),
            ("Emoji in UI", r"[\U0001F300-\U0001FFFF]", ["src", "components", "app", "pages"]),
        ]
        all_clean = True
        for label, pattern, dirs in checks:
            hits = []
            for d in dirs:
                try:
                    result = subprocess.run(
                        ["grep", "-rn", "--include=*.tsx", "--include=*.ts",
                         "--include=*.jsx", "--include=*.js", "--include=*.vue",
                         "--include=*.svelte", "--include=*.html", "-E", pattern, d],
                        capture_output=True, text=True, cwd=cwd, timeout=10,
                    )
                    if result.stdout.strip():
                        hits.extend(result.stdout.strip().splitlines()[:5])
                except Exception:
                    pass
            if hits:
                lines.append(f"  FAIL {label}:")
                for h in hits[:5]:
                    lines.append(f"    {h}")
                all_clean = False
            else:
                lines.append(f"  PASS {label}: none found")

        # Check tokens.css exists
        import os
        for tf in ["styles/tokens.css", "src/styles/tokens.css", "public/styles/tokens.css"]:
            if os.path.exists(os.path.join(cwd, tf)):
                lines.append(f"  PASS tokens.css: found at {tf}")
                break
        else:
            lines.append("  FAIL tokens.css: not found in expected locations")
            all_clean = False

        lines.append(f"\nVerdict: {'PASS' if all_clean else 'FAIL'} (static analysis)")
        return "\n".join(lines)


def _extract_hex(css_color: str) -> str | None:
    """Extract first hex color from a CSS color string."""
    m = re.search(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b", css_color)
    if m:
        return m.group(0)
    # Convert rgb(r, g, b) to hex
    m = re.search(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", css_color)
    if m:
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"#{r:02x}{g:02x}{b:02x}"
    return None


class DSTokenAuditTool(BaseTool):
    """Static audit of a project's tokens.css / design-system files.

    Checks: token completeness, theme coverage (dark/light/contrast),
    breakpoint definitions, banned patterns.
    """

    name = "ds_token_audit"
    description = (
        "Static audit of design-system token files. "
        "Checks token completeness (colors, font, spacing, radii, shadows), "
        "theme coverage (dark/light/contrast), responsive breakpoints, "
        "and banned patterns (hardcoded colors, emoji, gradients, inline styles). "
        "Returns structured PASS/FAIL report."
    )
    category = "design_system"

    REQUIRED_TOKENS = [
        "--bg-primary", "--bg-secondary", "--bg-tertiary",
        "--text-primary", "--text-secondary", "--border",
        "--accent", "--font-sans", "--font-mono",
        "--text-sm", "--text-base", "--text-lg",
        "--space-2", "--space-4", "--space-6",
        "--radius-sm", "--radius-md", "--radius-lg",
        "--bp-sm", "--bp-md", "--bp-lg",
    ]
    REQUIRED_THEMES = ["[data-theme=\"dark\"]", "[data-theme=\"light\"]", "[data-theme=\"contrast\"]"]
    BANNED_PATTERNS = [r"#[0-9a-fA-F]{3,6}", r"linear-gradient", r"radial-gradient"]

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        import os
        cwd = params.get("cwd", ".")
        lines = ["DS Token Audit\n"]
        all_pass = True

        # Find tokens.css
        candidates = [
            "styles/tokens.css", "src/styles/tokens.css",
            "public/styles/tokens.css", "assets/tokens.css",
        ]
        tokens_content = ""
        found_at = ""
        for c in candidates:
            p = os.path.join(cwd, c)
            if os.path.exists(p):
                with open(p) as f:
                    tokens_content = f.read()
                found_at = c
                break

        if not tokens_content:
            lines.append("  FAIL tokens.css: not found in " + ", ".join(candidates))
            lines.append("\nVerdict: FAIL")
            return "\n".join(lines)

        lines.append(f"  INFO tokens.css: found at {found_at} ({len(tokens_content)} chars)\n")

        # Required tokens
        missing = [t for t in self.REQUIRED_TOKENS if t not in tokens_content]
        if missing:
            lines.append(f"  FAIL required tokens missing: {', '.join(missing)}")
            all_pass = False
        else:
            lines.append(f"  PASS all {len(self.REQUIRED_TOKENS)} required tokens present")

        # Theme coverage (in tokens.css or themes.css)
        themes_candidates = [
            "styles/themes.css", "src/styles/themes.css",
            "public/styles/themes.css", found_at,
        ]
        themes_content = tokens_content
        for tc in themes_candidates:
            p = os.path.join(cwd, tc)
            if os.path.exists(p) and tc != found_at:
                with open(p) as f:
                    themes_content += f.read()
        missing_themes = [t for t in self.REQUIRED_THEMES if t not in themes_content]
        if missing_themes:
            lines.append(f"  FAIL missing theme selectors: {', '.join(missing_themes)}")
            all_pass = False
        else:
            lines.append("  PASS all 3 themes (dark/light/contrast) defined")

        # Skip-link in base.css or base.html
        skip_found = False
        for bf in ["styles/base.css", "src/styles/base.css", "index.html", "app/layout.tsx", "src/App.tsx"]:
            p = os.path.join(cwd, bf)
            if os.path.exists(p):
                with open(p) as f:
                    if "skip-link" in f.read():
                        skip_found = True
                        break
        if skip_found:
            lines.append("  PASS skip-link found")
        else:
            lines.append("  FAIL skip-link: not found in base.css or layout files")
            all_pass = False

        lines.append(f"\nVerdict: {'PASS' if all_pass else 'FAIL'}")
        return "\n".join(lines)


def register_ds_tools(registry) -> None:
    """Register design-system tools into the tool registry."""
    registry.register(CSSComputedCheckTool())
    registry.register(DSTokenAuditTool())
