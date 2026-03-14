"""
Test Tools - Playwright screenshots, simulator captures, and test execution.
=============================================================================
"""
# Ref: feat-tool-builder

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from ..models import AgentInstance
from .registry import BaseTool


def _workspace_screenshot_dir(cwd: str) -> Path:
    """Ensure screenshots/ dir exists under workspace, return it."""
    d = Path(cwd) / "screenshots"
    d.mkdir(parents=True, exist_ok=True)
    return d


class ScreenshotTool(BaseTool):
    name = "screenshot"
    description = (
        "Take a browser screenshot of a URL using Playwright headless Chromium. "
        "Saves PNG to workspace/screenshots/. Returns inline image marker."
    )
    category = "test"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        url = params.get("url", "")
        cwd = params.get("cwd", ".")
        filename = params.get("filename", f"screenshot_{int(time.time())}.png")
        if not url:
            return "Error: url required"

        screenshots_dir = _workspace_screenshot_dir(cwd)
        out_path = screenshots_dir / filename

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
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=60,
            )
            if r.returncode == 0 and out_path.exists():
                title = ""
                for line in r.stdout.split("\n"):
                    if line.startswith("TITLE:"):
                        title = line[6:]
                size_kb = out_path.stat().st_size // 1024
                rel = f"screenshots/{filename}"
                return (
                    f"Screenshot captured: {url}\n"
                    f"Page title: {title}\n"
                    f"Size: {size_kb}KB\n"
                    f"[SCREENSHOT:{rel}]"
                )
            else:
                return f"[FAIL] Screenshot failed:\n{r.stderr[-1500:]}"
        except subprocess.TimeoutExpired:
            return "[FAIL] TIMEOUT (60s)"
        except Exception as e:
            return f"Error: {e}"


class SimulatorScreenshotTool(BaseTool):
    name = "simulator_screenshot"
    description = (
        "Take a screenshot of the running iOS/macOS Simulator using xcrun simctl. "
        "The simulator must be booted. Saves PNG to workspace/screenshots/."
    )
    category = "test"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        cwd = params.get("cwd", ".")
        device = params.get("device", "booted")
        filename = params.get("filename", f"simulator_{int(time.time())}.png")
        app_bundle = params.get("app_bundle", "")

        screenshots_dir = _workspace_screenshot_dir(cwd)
        out_path = screenshots_dir / filename

        # Launch app if bundle specified
        if app_bundle:
            try:
                subprocess.run(
                    ["xcrun", "simctl", "launch", device, app_bundle],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                import asyncio

                await asyncio.sleep(3)
            except Exception:
                pass

        # Capture screenshot via simctl
        try:
            r = subprocess.run(
                ["xcrun", "simctl", "io", device, "screenshot", str(out_path)],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if r.returncode == 0 and out_path.exists():
                size_kb = out_path.stat().st_size // 1024
                # Get device info
                info = subprocess.run(
                    ["xcrun", "simctl", "list", "devices", "booted"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                device_name = "Simulator"
                for line in info.stdout.split("\n"):
                    if "(Booted)" in line:
                        device_name = line.strip().split("(")[0].strip()
                        break
                rel = f"screenshots/{filename}"
                return (
                    f"Simulator screenshot captured: {device_name}\n"
                    f"Size: {size_kb}KB\n"
                    f"[SCREENSHOT:{rel}]"
                )
            else:
                err = r.stderr.strip()
                if "No devices are booted" in err:
                    return "[FAIL] No simulator booted. Boot one with: xcrun simctl boot <device-id>"
                return f"[FAIL] Screenshot failed: {err[-500:]}"
        except subprocess.TimeoutExpired:
            return "[FAIL] TIMEOUT (15s)"
        except FileNotFoundError:
            return "[FAIL] xcrun not found — requires Xcode Command Line Tools"
        except Exception as e:
            return f"Error: {e}"


class PlaywrightTestTool(BaseTool):
    name = "playwright_test"
    description = (
        "Run Playwright E2E tests. Executes a test spec file and returns "
        "pass/fail results with screenshot paths on failure. "
        "IMPORTANT: the app server must be running BEFORE calling this tool. "
        "Use docker_deploy first to start the container and get the URL, "
        "then pass base_url so tests connect to the right server. "
        "A result with status=failed and failedTests=[] means the server was NOT running — this is a FAILURE."
    )
    category = "test"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        spec = params.get("spec", "")
        cwd = params.get("cwd", ".")
        base_url = params.get("base_url", "")  # URL of running app from docker_deploy
        if not spec:
            return "Error: spec file path required"

        screenshots_dir = Path(cwd) / "screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)

        # Pre-flight: if base_url provided, verify server is reachable before launching tests
        if base_url:
            import urllib.request

            try:
                urllib.request.urlopen(base_url, timeout=5)
            except Exception as e:
                return (
                    f"[FAIL] Server not reachable at {base_url} before tests: {e}\n"
                    "Make sure to call docker_deploy first and use the returned URL."
                )

        env = {**os.environ, "CI": "true"}
        if base_url:
            env["BASE_URL"] = base_url
            env["PLAYWRIGHT_BASE_URL"] = base_url

        cmd = (
            f"npx playwright test {spec} "
            f"--reporter=json,line "
            f"--output={screenshots_dir} "
            f"--screenshot on "
            f"--retries=0"
        )
        try:
            r = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=120,
                env=env,
            )
            output = r.stdout[-3000:] + r.stderr[-1000:]

            # Detect false-positive: test runner failed to start (no server, missing deps)
            # When status=failed + failedTests=[] it means zero tests ran — this is NOT a pass
            import json

            json_result = None
            for line in r.stdout.splitlines():
                if line.strip().startswith("{") and "failedTests" in line:
                    try:
                        json_result = json.loads(line)
                    except Exception:
                        pass

            if (
                json_result
                and json_result.get("status") == "failed"
                and not json_result.get("failedTests")
            ):
                return (
                    f"[FAIL] ZERO TESTS RAN — server was likely not running or Playwright not installed.\n"
                    f"This is a FAILURE, not a success. Start the container first with docker_deploy.\n"
                    f"Output:\n{output}"
                )

            status = (
                "[OK] PASS"
                if r.returncode == 0
                else f"[FAIL] FAIL (exit {r.returncode})"
            )

            # List any screenshots produced
            screenshots = list(screenshots_dir.glob("*.png"))
            if screenshots:
                shot_list = "\n".join(
                    f"[SCREENSHOT:{s.relative_to(Path(cwd))}]" for s in screenshots[-5:]
                )
                output += f"\n\nScreenshots:\n{shot_list}"

            return f"{status}\n{output}"
        except subprocess.TimeoutExpired:
            return "[FAIL] TIMEOUT (120s)"
        except Exception as e:
            return f"Error: {e}"


def register_test_tools(registry):
    """Register Playwright test tools and simulator screenshot."""
    registry.register(ScreenshotTool())
    registry.register(SimulatorScreenshotTool())
    registry.register(PlaywrightTestTool())
