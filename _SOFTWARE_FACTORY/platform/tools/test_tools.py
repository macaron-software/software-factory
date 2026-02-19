"""
Test Tools - Playwright screenshots and test execution.
=========================================================
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from ..models import AgentInstance
from .registry import BaseTool


class ScreenshotTool(BaseTool):
    name = "screenshot"
    description = (
        "Take a browser screenshot of a URL using Playwright. "
        "Saves a PNG to workspace/screenshots/. Returns the file path."
    )
    category = "test"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        url = params.get("url", "")
        cwd = params.get("cwd", ".")
        filename = params.get("filename", "screenshot.png")
        if not url:
            return "Error: url required"

        screenshots_dir = Path(cwd) / "screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        out_path = screenshots_dir / filename

        # Playwright script — headless Chromium screenshot
        script = f"""
const {{ chromium }} = require('playwright');
(async () => {{
    const browser = await chromium.launch();
    const page = await browser.newPage({{ viewport: {{ width: 1280, height: 720 }} }});
    await page.goto('{url}', {{ waitUntil: 'networkidle', timeout: 30000 }});
    await page.screenshot({{ path: '{out_path}', fullPage: false }});
    const title = await page.title();
    console.log('TITLE:' + title);
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    console.log('ERRORS:' + errors.length);
    await browser.close();
}})();
"""
        try:
            r = subprocess.run(
                ["node", "-e", script],
                capture_output=True, text=True, cwd=cwd, timeout=60,
            )
            if r.returncode == 0 and out_path.exists():
                title = ""
                for line in r.stdout.split("\n"):
                    if line.startswith("TITLE:"):
                        title = line[6:]
                size_kb = out_path.stat().st_size // 1024
                return (
                    f"[OK] Screenshot saved: {out_path.relative_to(Path(cwd))}\n"
                    f"Page title: {title}\n"
                    f"Size: {size_kb}KB\n"
                    f"[SCREENSHOT:{out_path.relative_to(Path(cwd))}]"
                )
            else:
                return f"[FAIL] Screenshot failed:\n{r.stderr[-1500:]}"
        except subprocess.TimeoutExpired:
            return "[FAIL] TIMEOUT (60s)"
        except Exception as e:
            return f"Error: {e}"


class PlaywrightTestTool(BaseTool):
    name = "playwright_test"
    description = (
        "Run Playwright E2E tests. Executes a test spec file and returns "
        "pass/fail results with screenshot paths on failure."
    )
    category = "test"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        spec = params.get("spec", "")
        cwd = params.get("cwd", ".")
        if not spec:
            return "Error: spec file path required"

        screenshots_dir = Path(cwd) / "screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)

        # Run Playwright test with JSON reporter for structured output
        cmd = (
            f"npx playwright test {spec} "
            f"--reporter=line "
            f"--output={screenshots_dir} "
            f"--screenshot=on "
            f"--retries=0"
        )
        try:
            r = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                cwd=cwd, timeout=120,
                env={**os.environ, "CI": "true"},
            )
            output = r.stdout[-3000:] + r.stderr[-1000:]
            status = "[OK] PASS" if r.returncode == 0 else f"[FAIL] FAIL (exit {r.returncode})"

            # List any screenshots produced
            screenshots = list(screenshots_dir.glob("*.png"))
            if screenshots:
                shot_list = "\n".join(
                    f"[SCREENSHOT:{s.relative_to(Path(cwd))}]"
                    for s in screenshots[-5:]
                )
                output += f"\n\nScreenshots:\n{shot_list}"

            return f"{status}\n{output}"
        except subprocess.TimeoutExpired:
            return "[FAIL] TIMEOUT (120s)"
        except Exception as e:
            return f"Error: {e}"


def register_test_tools(registry):
    """Register Playwright test tools."""
    registry.register(ScreenshotTool())
    registry.register(PlaywrightTestTool())
