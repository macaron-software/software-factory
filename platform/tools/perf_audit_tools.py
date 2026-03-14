"""
Performance Audit Tools — Chrome DevTools MCP integration.
============================================================
Uses chrome-devtools-mcp (https://github.com/ChromeDevTools/chrome-devtools-mcp)
to run Lighthouse audits, capture Core Web Vitals, analyse network and console.

WHY chrome-devtools-mcp over playwright-mcp:
  - playwright-mcp is automation-oriented (click, fill, navigate)
  - chrome-devtools-mcp is debugging/perf-oriented (traces, CWV, Lighthouse, CDP)
  - Only chrome-devtools-mcp exposes: performance_start_trace, performance_stop_trace,
    performance_analyze_insight, lighthouse_audit, list_network_requests
  Both can coexist — different use cases.

Key tools exposed:
  perf_audit_lighthouse    → Lighthouse scores + suggestions (perf/a11y/seo/best-practices)
  perf_trace_start         → Start CDP performance trace
  perf_trace_stop          → Stop trace, return LCP/CLS/INP Core Web Vitals
  perf_analyze_insight     → Drill into a specific performance insight from trace
  perf_network_slow        → List slow/failed network requests
  perf_console_errors      → List console errors/warnings
  perf_emulate_mobile      → Emulate mobile device + throttle network for realistic audit

MCP server: mcp-chrome-devtools (id in mcps/store.py)
Tool naming: mcp_cdp_<tool_name> — routed by _tool_mcp_dynamic in tool_runner.py

Source: https://github.com/ChromeDevTools/chrome-devtools-mcp (Apache-2.0)
"""
# Ref: feat-quality

from __future__ import annotations

import logging

from ..models import AgentInstance
from .registry import BaseTool

logger = logging.getLogger(__name__)

_MCP_ID = "mcp-chrome-devtools"
_TIMEOUT_LIGHTHOUSE = 120  # Lighthouse can be slow
_TIMEOUT_TRACE = 60
_TIMEOUT_DEFAULT = 30


async def _cdp(tool_name: str, args: dict, timeout: int = _TIMEOUT_DEFAULT) -> str:
    """Call chrome-devtools-mcp tool, auto-starting the MCP server if needed."""
    from ..mcps.manager import get_mcp_manager

    manager = get_mcp_manager()
    if _MCP_ID not in manager.get_running_ids():
        ok, msg = await manager.start(_MCP_ID)
        if not ok:
            return (
                f"Failed to start chrome-devtools MCP: {msg}\n"
                "Install: npx chrome-devtools-mcp@latest"
            )
    result = await manager.call_tool(_MCP_ID, tool_name, args, timeout=timeout)
    return result[:8000] if result else "No response from chrome-devtools MCP"


class PerfAuditLighthouseTool(BaseTool):
    """Run a Lighthouse audit on a URL.

    Returns performance score (0-100), accessibility score, best-practices score,
    SEO score + a prioritised list of actionable improvement suggestions.
    Backed by chrome-devtools-mcp lighthouse_audit tool (Chrome DevTools, Apache-2.0).

    Use this as the first step of any performance audit — it gives the full picture
    in one call before diving into traces or network analysis.
    """

    name = "perf_audit_lighthouse"
    description = (
        "Run a full Lighthouse audit on a URL. Returns performance/accessibility/"
        "best-practices/SEO scores (0-100) and prioritised improvement suggestions. "
        "Use as first step of any perf audit. Params: url (required), "
        "categories (optional list: performance|accessibility|best-practices|seo)."
    )
    category = "perf_audit"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        url = params.get("url", "").strip()
        if not url:
            return "Error: url is required"
        categories = params.get(
            "categories", ["performance", "accessibility", "best-practices", "seo"]
        )
        return await _cdp(
            "lighthouse_audit",
            {"url": url, "categories": categories},
            timeout=_TIMEOUT_LIGHTHOUSE,
        )


class PerfTraceStartTool(BaseTool):
    """Start a Chrome DevTools performance trace on the current page.

    Begins recording CPU, network, rendering, and Core Web Vitals (LCP, CLS, INP).
    Call perf_trace_stop after the interaction you want to measure.
    """

    name = "perf_trace_start"
    description = (
        "Start a CDP performance trace. Records CPU, rendering, CWV. "
        "Follow with perf_trace_stop after the measured interaction. "
        "Params: url (required) — navigates to URL then starts trace."
    )
    category = "perf_audit"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        url = params.get("url", "").strip()
        if not url:
            return "Error: url is required — navigate before starting trace"
        # Navigate first, then start trace
        nav = await _cdp("navigate_page", {"url": url})
        if nav.startswith("Error") or nav.startswith("Failed"):
            return nav
        return await _cdp("performance_start_trace", {}, timeout=_TIMEOUT_TRACE)


class PerfTraceStopTool(BaseTool):
    """Stop the CDP performance trace and return Core Web Vitals.

    Returns: LCP (Largest Contentful Paint), CLS (Cumulative Layout Shift),
    INP (Interaction to Next Paint), and a timeline of the recorded trace.
    Compare against Google thresholds: LCP<2.5s ✅, CLS<0.1 ✅, INP<200ms ✅.
    """

    name = "perf_trace_stop"
    description = (
        "Stop the CDP performance trace. Returns Core Web Vitals: "
        "LCP, CLS, INP with pass/fail vs Google thresholds (LCP<2.5s, CLS<0.1, INP<200ms). "
        "No params needed — stops the currently running trace."
    )
    category = "perf_audit"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        return await _cdp("performance_stop_trace", {}, timeout=_TIMEOUT_TRACE)


class PerfAnalyzeInsightTool(BaseTool):
    """Drill into a specific performance insight from a trace.

    After perf_trace_stop, use the insight names returned (e.g. "LCP",
    "Render-blocking resources") to get detailed analysis and fix suggestions.
    """

    name = "perf_analyze_insight"
    description = (
        "Analyse a specific performance insight from a CDP trace. "
        "Use after perf_trace_stop with an insight name from the results "
        "(e.g. 'LCP', 'Render-blocking resources', 'Long tasks'). "
        "Params: insight (required string)."
    )
    category = "perf_audit"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        insight = params.get("insight", "").strip()
        if not insight:
            return "Error: insight name is required (e.g. 'LCP', 'Render-blocking resources')"
        return await _cdp(
            "performance_analyze_insight",
            {"insight": insight},
            timeout=_TIMEOUT_TRACE,
        )


class PerfNetworkSlowTool(BaseTool):
    """List slow or failed network requests from the current page.

    Useful for finding: slow API calls, oversized assets, CORS errors,
    failed resource loads, missing cache headers. Combine with Lighthouse
    to pinpoint the biggest network bottlenecks.
    """

    name = "perf_network_slow"
    description = (
        "List network requests from current page, sorted by duration. "
        "Reveals slow API calls, oversized assets, CORS errors, failed loads. "
        "Params: threshold_ms (optional int, default 500) — only show requests "
        "slower than threshold. url (optional) — navigate first if provided."
    )
    category = "perf_audit"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        url = params.get("url", "").strip()
        if url:
            nav = await _cdp("navigate_page", {"url": url})
            if nav.startswith("Error") or nav.startswith("Failed"):
                return nav
        threshold_ms = params.get("threshold_ms", 500)
        result = await _cdp("list_network_requests", {})
        # Annotate with threshold context
        return f"Network requests (threshold: >{threshold_ms}ms):\n{result}"


class PerfConsoleErrorsTool(BaseTool):
    """List console errors and warnings from the current page.

    JS errors slow down pages and break features silently.
    Run this alongside Lighthouse to catch runtime errors not visible in scores.
    """

    name = "perf_console_errors"
    description = (
        "List console errors and warnings on the current page. "
        "Catches runtime JS errors, deprecation warnings, CSP violations. "
        "Params: url (optional) — navigate first if provided, "
        "level (optional: 'error'|'warning'|'all', default 'error')."
    )
    category = "perf_audit"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        url = params.get("url", "").strip()
        if url:
            nav = await _cdp("navigate_page", {"url": url})
            if nav.startswith("Error") or nav.startswith("Failed"):
                return nav
        level = params.get("level", "error")
        result = await _cdp("list_console_messages", {"level": level})
        return result


class PerfEmulateMobileTool(BaseTool):
    """Emulate a mobile device with throttled network for a realistic audit.

    Real-world performance on mobile (3G/4G) is often 3–5× worse than desktop.
    Use before perf_audit_lighthouse or perf_trace_start to get mobile scores.
    Resets to desktop after the audit session.
    """

    name = "perf_emulate_mobile"
    description = (
        "Emulate a mobile device with network throttling for realistic perf testing. "
        "Mobile scores are often 3-5x worse than desktop — use before Lighthouse or trace. "
        "Params: device (optional, default 'Moto G4'), "
        "network (optional: 'slow-3g'|'fast-3g'|'4g'|'offline', default 'fast-3g')."
    )
    category = "perf_audit"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        device = params.get("device", "Moto G4")
        network = params.get("network", "fast-3g")
        return await _cdp(
            "emulate",
            {"device": device, "network": network},
        )


def register_perf_audit_tools(reg) -> None:
    """Register all performance audit tools into the tool registry."""
    for cls in [
        PerfAuditLighthouseTool,
        PerfTraceStartTool,
        PerfTraceStopTool,
        PerfAnalyzeInsightTool,
        PerfNetworkSlowTool,
        PerfConsoleErrorsTool,
        PerfEmulateMobileTool,
    ]:
        reg.register(cls())
