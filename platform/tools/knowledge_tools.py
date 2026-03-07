"""
Knowledge Tools — vulnerability DBs, Hugging Face model hub, web scraping.
==========================================================================
WHY: Agents performing security audits, ML model selection, or data collection
need structured access to external knowledge sources. This module provides:
  - OSV.dev vulnerability database (replaces unauthenticated Snyk API)
  - Hugging Face Hub API for model and dataset discovery
  - Scrapy runner for structured web crawling

All HTTP calls use stdlib urllib.request. Subprocess calls use
asyncio.create_subprocess_shell for non-blocking execution.
"""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import TYPE_CHECKING

from .registry import BaseTool
from ._helpers import get_json as _get_json

if TYPE_CHECKING:
    from ..models import AgentInstance

logger = logging.getLogger(__name__)

_TIMEOUT = 5

_OSV_ECOSYSTEM_MAP = {
    "npm": "npm",
    "pip": "PyPI",
    "maven": "Maven",
    "go": "Go",
}


def _post_json(url: str, payload: dict) -> dict:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "sf-agent/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode())


# ---------------------------------------------------------------------------
# Vulnerability tools (OSV.dev)
# ---------------------------------------------------------------------------


class SnykSearchTool(BaseTool):
    name = "snyk_search"
    description = (
        "Search for known vulnerabilities affecting a package using OSV.dev. "
        "params: package (str), ecosystem (str, default 'npm', options: npm|pip|maven|go). "
        "Returns JSON list of vulnerability summaries."
    )
    category = "security"

    async def execute(self, params: dict, agent: "AgentInstance" = None) -> str:
        package = params.get("package", "")
        ecosystem = params.get("ecosystem", "npm")
        if not package:
            return json.dumps({"error": "package is required"})
        osv_ecosystem = _OSV_ECOSYSTEM_MAP.get(ecosystem, ecosystem)
        try:
            data = _post_json(
                "https://api.osv.dev/v1/query",
                {"package": {"name": package, "ecosystem": osv_ecosystem}},
            )
            vulns = data.get("vulns", [])
            result = [
                {
                    "id": v.get("id", ""),
                    "summary": v.get("summary", ""),
                    "published": v.get("published", ""),
                    "modified": v.get("modified", ""),
                    "severity": (
                        v.get("database_specific", {}).get("severity", "")
                        or (
                            v.get("severity", [{}])[0].get("score", "")
                            if v.get("severity")
                            else ""
                        )
                    ),
                }
                for v in vulns
            ]
            return json.dumps(
                {"package": package, "ecosystem": osv_ecosystem, "vulns": result}
            )
        except Exception as exc:
            logger.error("snyk_search failed: %s", exc)
            return json.dumps({"error": str(exc)})


class SnykVulnGetTool(BaseTool):
    name = "snyk_vuln_get"
    description = (
        "Get details for a specific vulnerability by ID (e.g. 'GHSA-xxx' or 'CVE-xxx'). "
        "params: vuln_id (str). "
        "Returns JSON: {id, summary, severity, affected, references}."
    )
    category = "security"

    async def execute(self, params: dict, agent: "AgentInstance" = None) -> str:
        vuln_id = params.get("vuln_id", "")
        if not vuln_id:
            return json.dumps({"error": "vuln_id is required"})
        try:
            data = _get_json(
                f"https://api.osv.dev/v1/vulns/{urllib.parse.quote(vuln_id)}"
            )
            return json.dumps(
                {
                    "id": data.get("id", ""),
                    "summary": data.get("summary", ""),
                    "severity": data.get("severity", []),
                    "affected": data.get("affected", []),
                    "references": data.get("references", []),
                }
            )
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return json.dumps({"error": f"Vulnerability '{vuln_id}' not found"})
            return json.dumps({"error": str(exc)})
        except Exception as exc:
            logger.error("snyk_vuln_get failed: %s", exc)
            return json.dumps({"error": str(exc)})


# ---------------------------------------------------------------------------
# Hugging Face Hub tools
# ---------------------------------------------------------------------------


class HfModelSearchTool(BaseTool):
    name = "hf_model_search"
    description = (
        "Search Hugging Face Hub for models. "
        "params: query (str), task (str, optional, e.g. 'text-generation'), limit (int, default 10). "
        "Returns JSON list [{id, task, downloads, likes, tags}]."
    )
    category = "ai"

    async def execute(self, params: dict, agent: "AgentInstance" = None) -> str:
        query = params.get("query", "")
        task = params.get("task", "")
        limit = int(params.get("limit", 10))
        try:
            qs = {"search": query, "limit": str(limit)}
            if task:
                qs["task"] = task
            url = "https://huggingface.co/api/models?" + urllib.parse.urlencode(qs)
            data = _get_json(url)
            if not isinstance(data, list):
                data = data.get("models", [])
            return json.dumps(
                [
                    {
                        "id": m.get("id", ""),
                        "task": m.get("pipeline_tag", ""),
                        "downloads": m.get("downloads", 0),
                        "likes": m.get("likes", 0),
                        "tags": m.get("tags", []),
                    }
                    for m in data[:limit]
                ]
            )
        except Exception as exc:
            logger.error("hf_model_search failed: %s", exc)
            return json.dumps({"error": str(exc)})


class HfModelGetTool(BaseTool):
    name = "hf_model_get"
    description = (
        "Get details for a specific Hugging Face model. "
        "params: model_id (str, e.g. 'mistralai/Mistral-7B-v0.1'). "
        "Returns JSON: {id, task, downloads, likes, tags, card_data}."
    )
    category = "ai"

    async def execute(self, params: dict, agent: "AgentInstance" = None) -> str:
        model_id = params.get("model_id", "")
        if not model_id:
            return json.dumps({"error": "model_id is required"})
        try:
            url = f"https://huggingface.co/api/models/{urllib.parse.quote(model_id, safe='/')}"
            data = _get_json(url)
            return json.dumps(
                {
                    "id": data.get("id", ""),
                    "task": data.get("pipeline_tag", ""),
                    "downloads": data.get("downloads", 0),
                    "likes": data.get("likes", 0),
                    "tags": data.get("tags", []),
                    "card_data": data.get("cardData", {}),
                }
            )
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return json.dumps({"error": f"Model '{model_id}' not found"})
            return json.dumps({"error": str(exc)})
        except Exception as exc:
            logger.error("hf_model_get failed: %s", exc)
            return json.dumps({"error": str(exc)})


class HfDatasetSearchTool(BaseTool):
    name = "hf_dataset_search"
    description = (
        "Search Hugging Face Hub for datasets. "
        "params: query (str), limit (int, default 10). "
        "Returns JSON list [{id, downloads, likes, tags}]."
    )
    category = "ai"

    async def execute(self, params: dict, agent: "AgentInstance" = None) -> str:
        query = params.get("query", "")
        limit = int(params.get("limit", 10))
        try:
            url = "https://huggingface.co/api/datasets?" + urllib.parse.urlencode(
                {"search": query, "limit": str(limit)}
            )
            data = _get_json(url)
            if not isinstance(data, list):
                data = data.get("datasets", [])
            return json.dumps(
                [
                    {
                        "id": d.get("id", ""),
                        "downloads": d.get("downloads", 0),
                        "likes": d.get("likes", 0),
                        "tags": d.get("tags", []),
                    }
                    for d in data[:limit]
                ]
            )
        except Exception as exc:
            logger.error("hf_dataset_search failed: %s", exc)
            return json.dumps({"error": str(exc)})


# ---------------------------------------------------------------------------
# Scrapy tools
# ---------------------------------------------------------------------------


class ScrapyRunSpiderTool(BaseTool):
    name = "scrapy_run_spider"
    description = (
        "Run a Scrapy spider file and collect output. "
        "params: spider_file (str, path to .py), output_file (str, default 'output/scrapy_output.jsonl'), "
        "extra_args (str, optional). "
        "Returns JSON: {output_file, lines, returncode, stderr}."
    )
    category = "scraping"

    async def execute(self, params: dict, agent: "AgentInstance" = None) -> str:
        spider_file = params.get("spider_file", "")
        if not spider_file:
            return json.dumps({"error": "spider_file is required"})
        output_file = params.get("output_file", "output/scrapy_output.jsonl")
        extra_args = params.get("extra_args", "")
        cmd = f"scrapy runspider {spider_file} -o {output_file}"
        if extra_args:
            cmd = f"{cmd} {extra_args}"
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr_b = await proc.communicate()
            lines = 0
            try:
                import os

                if os.path.isfile(output_file):
                    with open(output_file) as fh:
                        lines = sum(1 for _ in fh)
            except Exception:
                pass
            return json.dumps(
                {
                    "output_file": output_file,
                    "lines": lines,
                    "returncode": proc.returncode,
                    "stderr": stderr_b.decode(errors="replace")[:1000],
                }
            )
        except Exception as exc:
            logger.error("scrapy_run_spider failed: %s", exc)
            return json.dumps({"error": str(exc)})


class ScrapyFetchUrlTool(BaseTool):
    name = "scrapy_fetch_url"
    description = (
        "Fetch a URL using Scrapy and return its HTML content. "
        "params: url (str), css_selector (str, optional). "
        "Returns JSON: {url, html_length, content_preview (first 2000 chars), "
        "css_matches (if selector provided)}."
    )
    category = "scraping"

    async def execute(self, params: dict, agent: "AgentInstance" = None) -> str:
        url = params.get("url", "")
        if not url:
            return json.dumps({"error": "url is required"})
        css_selector = params.get("css_selector", "")
        try:
            proc = await asyncio.create_subprocess_shell(
                f"scrapy fetch {url}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, _ = await proc.communicate()
            html = stdout_b.decode(errors="replace")
            result: dict = {
                "url": url,
                "html_length": len(html),
                "content_preview": html[:2000],
            }
            if css_selector:
                try:
                    from scrapy import Selector

                    sel = Selector(text=html)
                    result["css_matches"] = sel.css(css_selector).getall()
                except Exception as sel_exc:
                    result["css_matches_error"] = str(sel_exc)
            return json.dumps(result)
        except Exception as exc:
            logger.error("scrapy_fetch_url failed: %s", exc)
            return json.dumps({"error": str(exc)})


def register_knowledge_tools(registry) -> None:
    registry.register(SnykSearchTool())
    registry.register(SnykVulnGetTool())
    registry.register(HfModelSearchTool())
    registry.register(HfModelGetTool())
    registry.register(HfDatasetSearchTool())
    registry.register(ScrapyRunSpiderTool())
    registry.register(ScrapyFetchUrlTool())
    logger.debug("Knowledge tools registered (7 tools)")
