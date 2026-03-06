"""
Browser Tools — Headless browser exploration for agents.
=========================================================
Uses agent-browser (https://github.com/vercel-labs/agent-browser), a Rust CLI
wrapping Playwright/Chromium. Designed for agent exploration tasks: snapshot an
accessibility tree, click, fill, screenshot, get text — without scripted Playwright.

Why agent-browser over raw Playwright:
- CLI subprocess = stateless, no server to manage
- Accessibility tree snapshot (@refs) = LLM-friendly, no fragile CSS selectors
- Rust core = sub-millisecond CLI overhead

Install once (downloads Chromium):
    npm install -g agent-browser && agent-browser install

For Docker/server:
    RUN npm install -g agent-browser && agent-browser install --with-deps
"""

from __future__ import annotations

import asyncio
import logging
import shutil

from ..models import AgentInstance
from .registry import BaseTool

logger = logging.getLogger(__name__)

_CMD = "agent-browser"


def _ab_available() -> bool:
    return shutil.which(_CMD) is not None


async def _run(*args: str, timeout: int = 30) -> str:
    """Run agent-browser command, return stdout or error string."""
    if not _ab_available():
        return (
            "Error: agent-browser not installed. "
            "Run: npm install -g agent-browser && agent-browser install"
        )
    cmd = [_CMD, *args]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
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


class BrowserSnapshotTool(BaseTool):
    """Navigate to a URL and return the accessibility tree with @refs.

    The snapshot is the preferred way for agents to understand a page: it returns
    semantic element labels with short @ref identifiers (e.g. @e3 = 'Submit' button).
    Use refs with browser_click / browser_fill instead of CSS selectors.
    """

    name = "browser_snapshot"
    description = (
        "Open a URL in a headless browser and return the accessibility tree. "
        "Each interactive element gets a @ref (e.g. @e3). Use refs with "
        "browser_click and browser_fill for stable, selector-free interactions."
    )
    category = "browser"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        url = params.get("url", "").strip()
        if not url:
            return "Error: url required"
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        result = await _run("open", url, timeout=20)
        if result.startswith("Error"):
            return result
        snapshot = await _run("snapshot", timeout=15)
        return snapshot


class BrowserClickTool(BaseTool):
    """Click an element identified by @ref or CSS selector."""

    name = "browser_click"
    description = (
        "Click an element on the current browser page. "
        "Use @ref from browser_snapshot (e.g. '@e5') or a CSS selector."
    )
    category = "browser"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        selector = params.get("selector", "").strip()
        if not selector:
            return "Error: selector required (@ref like '@e3' or CSS selector)"
        result = await _run("click", selector, timeout=15)
        if result.startswith("Error"):
            return result
        # Return updated snapshot so agent sees new page state
        return await _run("snapshot", timeout=15)


class BrowserFillTool(BaseTool):
    """Fill a text input identified by @ref or CSS selector."""

    name = "browser_fill"
    description = (
        "Clear and fill a text input on the current page. "
        "Provide selector (@ref or CSS) and the value to type."
    )
    category = "browser"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        selector = params.get("selector", "").strip()
        value = params.get("value", "")
        if not selector:
            return "Error: selector required"
        result = await _run("fill", selector, value, timeout=15)
        if result.startswith("Error"):
            return result
        return await _run("snapshot", timeout=15)


class BrowserGetTextTool(BaseTool):
    """Extract text content from an element or the full page."""

    name = "browser_get_text"
    description = (
        "Get the visible text content of an element (by @ref or CSS selector). "
        "Omit selector to get full page text."
    )
    category = "browser"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        selector = params.get("selector", "").strip()
        if selector:
            return await _run("get", "text", selector, timeout=15)
        # No selector — get full page text via snapshot
        return await _run("snapshot", timeout=15)


class BrowserScreenshotTool(BaseTool):
    """Take a screenshot of the current page."""

    name = "browser_screenshot"
    description = (
        "Take a screenshot of the current browser page. "
        "Returns the file path where the screenshot was saved."
    )
    category = "browser"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        path = params.get("path", "").strip()
        args = ["screenshot"]
        if path:
            args.append(path)
        return await _run(*args, timeout=20)


class BrowserNavigateTool(BaseTool):
    """Navigate to a new URL in the existing browser session."""

    name = "browser_navigate"
    description = (
        "Navigate the current browser session to a new URL. "
        "Returns the accessibility tree snapshot of the new page."
    )
    category = "browser"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        url = params.get("url", "").strip()
        if not url:
            return "Error: url required"
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        result = await _run("open", url, timeout=20)
        if result.startswith("Error"):
            return result
        return await _run("snapshot", timeout=15)


class BrowserWaitTool(BaseTool):
    """Wait for an element, text, or URL pattern to appear."""

    name = "browser_wait"
    description = (
        "Wait for a condition before proceeding: element visible (selector), "
        "text present (text param), or URL pattern (url_pattern param)."
    )
    category = "browser"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        selector = params.get("selector", "").strip()
        text = params.get("text", "").strip()
        url_pattern = params.get("url_pattern", "").strip()
        timeout_ms = params.get("timeout_ms", 5000)

        if selector:
            result = await _run("wait", selector, timeout=int(timeout_ms / 1000) + 5)
        elif text:
            result = await _run("wait", "--text", text, timeout=int(timeout_ms / 1000) + 5)
        elif url_pattern:
            result = await _run("wait", "--url", url_pattern, timeout=int(timeout_ms / 1000) + 5)
        else:
            return "Error: provide selector, text, or url_pattern"

        if result.startswith("Error"):
            return result
        return await _run("snapshot", timeout=15)


def register_browser_tools(registry) -> None:
    """Register headless browser exploration tools."""
    registry.register(BrowserSnapshotTool())
    registry.register(BrowserClickTool())
    registry.register(BrowserFillTool())
    registry.register(BrowserGetTextTool())
    registry.register(BrowserScreenshotTool())
    registry.register(BrowserNavigateTool())
    registry.register(BrowserWaitTool())
    logger.debug("Browser tools registered (agent-browser backend)")
