"""
Build Tools - Build, test, lint operations (bridges to Factory core).
======================================================================
Uses Docker sandbox for isolation when SANDBOX_ENABLED=true.
"""

from __future__ import annotations

import subprocess
from ..models import AgentInstance
from .registry import BaseTool
from .sandbox import get_sandbox, SANDBOX_ENABLED


class BuildTool(BaseTool):
    name = "build"
    description = "Build a project"
    category = "build"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        cmd = params.get("command", "")
        cwd = params.get("cwd", ".")
        if not cmd:
            return "Error: build command required"
        # Fix swift command to use Apple Swift (not OpenStack CLI)
        import os
        if cmd.strip().startswith("swift ") and os.path.isfile("/usr/bin/swift"):
            cmd = "/usr/bin/" + cmd.strip()
        sandbox = get_sandbox(cwd)
        result = sandbox.run(cmd, cwd=cwd, timeout=300)
        output = result.stdout[-3000:] if result.returncode == 0 else (result.stderr[-3000:] or result.stdout[-3000:])
        status = "[OK] SUCCESS" if result.returncode == 0 else f"[FAIL] FAILED (exit {result.returncode})"
        prefix = f"[sandbox:{result.image}] " if result.sandboxed else ""
        return f"{prefix}{status}\n{output}"


class TestTool(BaseTool):
    name = "test"
    description = "Run tests"
    category = "build"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        cmd = params.get("command", "")
        cwd = params.get("cwd", ".")
        if not cmd:
            return "Error: test command required"
        # Fix swift command to use Apple Swift (not OpenStack CLI)
        import os
        if cmd.strip().startswith("swift ") and os.path.isfile("/usr/bin/swift"):
            cmd = "/usr/bin/" + cmd.strip()
        sandbox = get_sandbox(cwd)
        result = sandbox.run(cmd, cwd=cwd, timeout=300)
        output = result.stdout[-3000:] + result.stderr[-1000:]
        status = "[OK] PASS" if result.returncode == 0 else f"[FAIL] FAIL (exit {result.returncode})"
        prefix = f"[sandbox:{result.image}] " if result.sandboxed else ""
        return f"{prefix}{status}\n{output}"


class LintTool(BaseTool):
    name = "lint"
    description = "Run linter"
    category = "build"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        cmd = params.get("command", "")
        cwd = params.get("cwd", ".")
        if not cmd:
            return "Error: lint command required"
        sandbox = get_sandbox(cwd)
        result = sandbox.run(cmd, cwd=cwd, timeout=120)
        output = result.stdout[-3000:] + result.stderr[-1000:]
        status = "[OK] CLEAN" if result.returncode == 0 else "[WARN] ISSUES"
        prefix = f"[sandbox:{result.image}] " if result.sandboxed else ""
        return f"{prefix}{status}\n{output}"


class BrowserScreenshotTool(BaseTool):
    name = "browser_screenshot"
    description = "Take a real browser screenshot of a web page. Starts a local server if needed, opens Playwright headless, captures screenshot. Use this to verify UI rendering."
    category = "build"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        import os
        import asyncio
        cwd = params.get("cwd", ".")
        url = params.get("url", "")
        filename = params.get("filename", "screenshot.png")
        wait_ms = int(params.get("wait_ms", 2000))

        screenshots_dir = os.path.join(cwd, "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)
        filepath = os.path.join(screenshots_dir, filename)

        server_proc = None
        try:
            # If no URL, start a local server
            if not url:
                if os.path.isfile(os.path.join(cwd, "index.html")):
                    server_proc = subprocess.Popen(
                        ["python3", "-m", "http.server", "8765", "--directory", cwd],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                    await asyncio.sleep(1)
                    url = "http://localhost:8765"
                else:
                    return "Error: no URL provided and no index.html found in workspace"

            # Try Playwright
            try:
                from playwright.async_api import async_playwright
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    page = await browser.new_page(viewport={"width": 1280, "height": 720})
                    await page.goto(url, wait_until="networkidle", timeout=15000)
                    if wait_ms > 0:
                        await asyncio.sleep(wait_ms / 1000)
                    await page.screenshot(path=filepath, full_page=False)
                    title = await page.title()
                    # Check for console errors
                    console_errors = []
                    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
                    await browser.close()
                return f"[OK] Screenshot saved: {filepath}\nPage title: {title}\nConsole errors: {len(console_errors)}"
            except ImportError:
                # Fallback: use subprocess with node/playwright CLI
                result = subprocess.run(
                    ["npx", "playwright", "screenshot", url, filepath, "--viewport-size=1280,720"],
                    capture_output=True, text=True, cwd=cwd, timeout=30,
                )
                if result.returncode == 0:
                    return f"[OK] Screenshot saved: {filepath}"
                return f"[FAIL] Playwright CLI error: {result.stderr[-500:]}"
        except Exception as e:
            return f"[FAIL] Screenshot failed: {e}"
        finally:
            if server_proc:
                server_proc.terminate()


def register_build_tools(registry):
    """Register all build tools."""
    registry.register(BuildTool())
    registry.register(TestTool())
    registry.register(LintTool())
    registry.register(BrowserScreenshotTool())
