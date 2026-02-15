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

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        url = params.get("url", "")
        max_chars = params.get("max_chars", 8000)
        if not url:
            return "Error: url required"
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
