"""
Build Tools - Build, test, lint operations (bridges to Factory core).
======================================================================
Uses Docker sandbox for isolation when SANDBOX_ENABLED=true.
"""

from __future__ import annotations

import subprocess
from ..models import AgentInstance
from .registry import BaseTool
from .sandbox import get_sandbox


class BuildTool(BaseTool):
    name = "build"
    description = "Build a project"
    category = "build"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        cmd = params.get("command", "")
        cwd = params.get("cwd", ".")
        if not cmd:
            return "Error: build command required"
        # Command injection guard
        try:
            from ..security.sanitize import sanitize_command

            cmd, err = sanitize_command(cmd, "build")
            if err:
                return err
        except ImportError:
            pass
        # Fix swift command to use Apple Swift (not OpenStack python-swiftclient)
        import os
        import re as _re

        if os.path.isfile("/usr/bin/swift") and _re.search(r'\bswift\s+(?:build|test|package|run)\b', cmd):
            cmd = _re.sub(r'\bswift\b', '/usr/bin/swift', cmd)
        sandbox = get_sandbox(cwd)
        result = sandbox.run(cmd, cwd=cwd, timeout=300)
        prefix = f"[sandbox:{result.image}] " if result.sandboxed else ""
        if result.returncode == 0:
            output = result.stdout[-3000:]
            return f"{prefix}[BUILD] SUCCESS\n$ {cmd}\n{output}"
        # Build failed — extract first unique errors for actionable feedback
        raw = result.stderr or result.stdout or ""
        error_lines = []
        seen_errors = set()
        for line in raw.splitlines():
            if ": error:" in line or "error:" == line.strip()[:6:]:
                # Deduplicate by error message (ignore file/line)
                msg_part = line.split(": error:")[-1].strip() if ": error:" in line else line.strip()
                if msg_part not in seen_errors:
                    seen_errors.add(msg_part)
                    error_lines.append(line.strip())
        total_errors = len(seen_errors) if seen_errors else raw.count("error:")
        # Show first 5 unique errors — keep it focused for the agent
        shown = error_lines[:5]
        output_parts = [f"{prefix}[BUILD] FAILED (exit {result.returncode})", f"$ {cmd}"]
        output_parts.append(f"\n{total_errors} unique errors found. Showing first {len(shown)} — fix these first:")
        for e in shown:
            output_parts.append(f"  {e}")
        if total_errors > 5:
            output_parts.append(f"  ... and {total_errors - 5} more errors (fix above first, then rebuild)")
        output_parts.append(
            "\nACTION REQUIRED: Use code_edit(path=..., old_str=..., new_str=...) to fix each error above, then call build() again."
        )
        return "\n".join(output_parts)


class TestTool(BaseTool):
    name = "test"
    description = "Run tests"
    category = "build"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        cmd = params.get("command", "")
        cwd = params.get("cwd", ".")
        if not cmd:
            return "Error: test command required"
        # Command injection guard
        try:
            from ..security.sanitize import sanitize_command

            cmd, err = sanitize_command(cmd, "test")
            if err:
                return err
        except ImportError:
            pass
        # Fix swift command to use Apple Swift (not OpenStack python-swiftclient)
        import os
        import re as _re

        if os.path.isfile("/usr/bin/swift") and _re.search(r'\bswift\s+(?:build|test|package|run)\b', cmd):
            cmd = _re.sub(r'\bswift\b', '/usr/bin/swift', cmd)
        sandbox = get_sandbox(cwd)
        result = sandbox.run(cmd, cwd=cwd, timeout=300)
        output = result.stdout[-3000:] + result.stderr[-1000:]
        status = (
            "[OK] PASS"
            if result.returncode == 0
            else f"[FAIL] FAIL (exit {result.returncode})"
        )
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
        # Command injection guard
        try:
            from ..security.sanitize import sanitize_command

            cmd, err = sanitize_command(cmd, "lint")
            if err:
                return err
        except ImportError:
            pass
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
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
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
                    page = await browser.new_page(
                        viewport={"width": 1280, "height": 720}
                    )
                    await page.goto(url, wait_until="networkidle", timeout=15000)
                    if wait_ms > 0:
                        await asyncio.sleep(wait_ms / 1000)
                    await page.screenshot(path=filepath, full_page=False)
                    title = await page.title()
                    # Check for console errors
                    console_errors = []
                    page.on(
                        "console",
                        lambda msg: console_errors.append(msg.text)
                        if msg.type == "error"
                        else None,
                    )
                    await browser.close()
                return f"[OK] Screenshot saved: {filepath}\nPage title: {title}\nConsole errors: {len(console_errors)}"
            except ImportError:
                # Fallback: use subprocess with node/playwright CLI
                result = subprocess.run(
                    [
                        "npx",
                        "playwright",
                        "screenshot",
                        url,
                        filepath,
                        "--viewport-size=1280,720",
                    ],
                    capture_output=True,
                    text=True,
                    cwd=cwd,
                    timeout=30,
                )
                if result.returncode == 0:
                    return f"[OK] Screenshot saved: {filepath}"
                return f"[FAIL] Playwright CLI error: {result.stderr[-500:]}"
        except Exception as e:
            return f"[FAIL] Screenshot failed: {e}"
        finally:
            if server_proc:
                server_proc.terminate()


class CICDRunnerTool(BaseTool):
    name = "cicd_run"
    description = (
        "Run the full CI/CD pipeline for a project: lint → build → test → report. "
        "Detects stack from project files and runs appropriate commands."
    )
    category = "build"

    _STACK_CMDS = {
        "Cargo.toml": [
            ("cargo fmt -- --check", "lint"),
            ("cargo build --release", "build"),
            ("cargo test", "test"),
        ],
        "pyproject.toml": [("ruff check .", "lint"), ("python -m pytest -q", "test")],
        "requirements.txt": [("python -m pytest -q", "test")],
        "package.json": [
            ("npm run lint", "lint"),
            ("npm run build", "build"),
            ("npm test", "test"),
        ],
        "go.mod": [
            ("go vet ./...", "lint"),
            ("go build ./...", "build"),
            ("go test ./...", "test"),
        ],
    }

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        import asyncio
        import os

        cwd = params.get("cwd", ".")
        if not os.path.isdir(cwd):
            return f"[FAIL] Directory not found: {cwd}"

        steps = []
        for marker, cmds in self._STACK_CMDS.items():
            if os.path.isfile(os.path.join(cwd, marker)):
                steps.extend(cmds)
                break
        if not steps:
            return "[SKIP] No recognized project markers found"

        results, passed, failed = [], 0, 0
        sandbox = get_sandbox(cwd)
        loop = asyncio.get_event_loop()
        for cmd, stage in steps:
            # Run blocking subprocess in thread pool to avoid blocking event loop
            r = await loop.run_in_executor(
                None, lambda c=cmd: sandbox.run(c, cwd=cwd, timeout=300)
            )
            ok = r.returncode == 0
            results.append(f"{'✓' if ok else '✗'} {stage}: {cmd}")
            if not ok:
                results.append(f"  {(r.stderr or r.stdout)[-500:]}")
                failed += 1
            else:
                passed += 1

        status = (
            "[OK] PIPELINE PASSED"
            if failed == 0
            else f"[FAIL] {failed} stage(s) failed"
        )
        return f"{status} ({passed}/{passed + failed})\n" + "\n".join(results)


class DockerBuildVerifyTool(BaseTool):
    name = "docker_build_verify"
    description = (
        "Verify a project builds successfully as a Docker image. "
        "Runs 'docker build' in the workspace directory and returns SUCCESS or FAIL with compiler errors. "
        "Use this in env-setup phase to gate the TDD sprint. "
        "Unlike docker_deploy, does NOT start a container — just verifies the build compiles."
    )
    category = "build"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        import asyncio
        import os

        cwd = params.get("cwd", ".")
        mission_id = params.get("mission_id", os.path.basename(os.path.abspath(cwd)))
        tag = f"macaron-verify-{mission_id[:12]}"

        if not os.path.isdir(cwd):
            return f"[FAIL] Directory not found: {cwd}"

        if not os.path.isfile(os.path.join(cwd, "Dockerfile")):
            return "[FAIL] No Dockerfile found in workspace — create one before calling docker_build_verify"

        loop = asyncio.get_event_loop()
        r = await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                ["docker", "build", "-t", tag, "."],
                cwd=cwd, capture_output=True, text=True, timeout=600,
            ),
        )

        # Cleanup image regardless of result
        subprocess.run(["docker", "rmi", "-f", tag], capture_output=True, timeout=15)

        if r.returncode == 0:
            lines = [l for l in (r.stdout + r.stderr).splitlines() if l.strip()]
            summary = "\n".join(lines[-5:]) if lines else "Build succeeded"
            return f"[OK] Docker build SUCCESS\n{summary}"
        else:
            error_output = (r.stderr or r.stdout)[-3000:]
            return (
                f"[FAIL] Docker build FAILED (exit {r.returncode})\n"
                f"Fix these errors before proceeding to tdd-sprint:\n{error_output}"
            )


def register_build_tools(registry):
    """Register all build tools."""
    registry.register(BuildTool())
    registry.register(TestTool())
    registry.register(LintTool())
    registry.register(BrowserScreenshotTool())
    registry.register(CICDRunnerTool())
    registry.register(DockerBuildVerifyTool())
