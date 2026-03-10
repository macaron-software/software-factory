"""
Web Tools - Web search and fetch for agent research.
=====================================================
"""

from __future__ import annotations

import logging
import re
from ..models import AgentInstance
from .registry import BaseTool

logger = logging.getLogger(__name__)


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the web for information. Returns summarized results."
    category = "research"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        query = params.get("query", "")
        if not query:
            return "Error: query required"
        try:
            import aiohttp
            # Use DuckDuckGo HTML (no API key needed)
            url = "https://html.duckduckgo.com/html/"
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    data={"q": query},
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    html = await resp.text()
            # Extract result snippets
            results = []
            for m in re.finditer(
                r'class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?'
                r'class="result__snippet">(.*?)</span>',
                html, re.DOTALL,
            ):
                href, title, snippet = m.group(1), m.group(2), m.group(3)
                title = re.sub(r"<[^>]+>", "", title).strip()
                snippet = re.sub(r"<[^>]+>", "", snippet).strip()
                if title and snippet:
                    results.append(f"**{title}**\n{snippet}\n{href}")
                if len(results) >= 8:
                    break
            if not results:
                return f"No results found for: {query}"
            return f"## Web search: {query}\n\n" + "\n\n---\n\n".join(results)
        except ImportError:
            return "Error: aiohttp not installed"
        except Exception as e:
            logger.error(f"Web search error: {e}")
            return f"Web search error: {e}"


class WebFetchTool(BaseTool):
    name = "web_fetch"
    description = "Fetch a URL and return its text content (HTML stripped)."
    category = "research"

    # Private/internal IP ranges blocked to prevent SSRF
    _BLOCKED_PREFIXES = (
        "http://127.", "https://127.",
        "http://0.", "https://0.",
        "http://10.", "https://10.",
        "http://172.16.", "http://172.17.", "http://172.18.", "http://172.19.",
        "http://172.20.", "http://172.21.", "http://172.22.", "http://172.23.",
        "http://172.24.", "http://172.25.", "http://172.26.", "http://172.27.",
        "http://172.28.", "http://172.29.", "http://172.30.", "http://172.31.",
        "https://172.1", "https://172.2", "https://172.3",
        "http://192.168.", "https://192.168.",
        "http://169.254.", "https://169.254.",   # Cloud IMDS (AWS/Azure/GCP)
        "http://metadata.", "https://metadata.",
        "http://localhost", "https://localhost",
        "http://[", "https://[",  # IPv6 loopback
    )

    def _is_ssrf_blocked(self, url: str) -> bool:
        """Return True if URL targets a private/internal address."""
        url_lower = url.lower()
        return any(url_lower.startswith(p) for p in self._BLOCKED_PREFIXES)

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        url = params.get("url", "")
        max_chars = params.get("max_chars", 8000)
        if not url:
            return "Error: url required"
        # SSRF protection: block private/internal IPs
        if self._is_ssrf_blocked(url):
            logger.warning("SSRF blocked: agent=%s url=%s", getattr(agent, 'id', '?'), url)
            return f"Error: URL blocked — private/internal addresses not allowed"
        if not url.startswith(("http://", "https://")):
            return "Error: URL must start with http:// or https://"
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    html = await resp.text()
            # Strip tags, compress whitespace
            text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            if len(text) > max_chars:
                text = text[:max_chars] + "... (truncated)"
            return text
        except ImportError:
            return "Error: aiohttp not installed"
        except Exception as e:
            logger.error(f"Web fetch error: {e}")
            return f"Web fetch error: {e}"


def register_web_tools(registry):
    """Register web research tools."""
    registry.register(WebSearchTool())
    registry.register(WebFetchTool())
