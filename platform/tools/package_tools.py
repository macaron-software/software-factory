"""
Package Registry Tools — npm and PyPI discovery without third-party deps.
=========================================================================
WHY: Agents that scaffold or audit projects need quick access to package
metadata (latest version, license, download stats, homepage) without
leaving the sandbox. All HTTP calls use stdlib urllib.request only.

Covered registries:
  - npm  : search, package info, weekly download stats
  - PyPI : package info (exact name lookup via JSON API)
"""

from __future__ import annotations

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


# ---------------------------------------------------------------------------
# npm tools
# ---------------------------------------------------------------------------


class NpmSearchTool(BaseTool):
    name = "npm_search"
    description = (
        "Search npm registry for packages. "
        "params: query (str). "
        "Returns top 10 packages as JSON list [{name, description, version, keywords, links}]."
    )
    category = "packages"

    async def execute(self, params: dict, agent: "AgentInstance" = None) -> str:
        query = params.get("query", "")
        if not query:
            return json.dumps({"error": "query is required"})
        try:
            url = f"https://registry.npmjs.org/-/v1/search?text={urllib.parse.quote(query)}&size=10"
            data = _get_json(url)
            results = [
                {
                    "name": obj["package"].get("name", ""),
                    "description": obj["package"].get("description", ""),
                    "version": obj["package"].get("version", ""),
                    "keywords": obj["package"].get("keywords", []),
                    "links": obj["package"].get("links", {}),
                }
                for obj in data.get("objects", [])
            ]
            return json.dumps(results)
        except Exception as exc:
            logger.error("npm_search failed: %s", exc)
            return json.dumps({"error": str(exc)})


class NpmPackageInfoTool(BaseTool):
    name = "npm_package_info"
    description = (
        "Get npm package metadata by exact name. "
        "params: package (str). "
        "Returns JSON: {name, description, version, license, homepage, weekly_downloads_url}."
    )
    category = "packages"

    async def execute(self, params: dict, agent: "AgentInstance" = None) -> str:
        package = params.get("package", "")
        if not package:
            return json.dumps({"error": "package is required"})
        try:
            url = f"https://registry.npmjs.org/{urllib.parse.quote(package, safe='@/')}"
            data = _get_json(url)
            latest = data.get("dist-tags", {}).get("latest", "")
            version_data = data.get("versions", {}).get(latest, {})
            return json.dumps(
                {
                    "name": data.get("name", ""),
                    "description": data.get("description", ""),
                    "version": latest,
                    "license": version_data.get("license", data.get("license", "")),
                    "homepage": data.get("homepage", version_data.get("homepage", "")),
                    "weekly_downloads_url": (
                        f"https://api.npmjs.org/downloads/point/last-week/{package}"
                    ),
                }
            )
        except Exception as exc:
            logger.error("npm_package_info failed: %s", exc)
            return json.dumps({"error": str(exc)})


class NpmWeeklyDownloadsTool(BaseTool):
    name = "npm_weekly_downloads"
    description = (
        "Get last-week download count for an npm package. "
        "params: package (str). "
        "Returns JSON: {package, downloads, start, end}."
    )
    category = "packages"

    async def execute(self, params: dict, agent: "AgentInstance" = None) -> str:
        package = params.get("package", "")
        if not package:
            return json.dumps({"error": "package is required"})
        try:
            url = f"https://api.npmjs.org/downloads/point/last-week/{urllib.parse.quote(package, safe='@/')}"
            data = _get_json(url)
            return json.dumps(
                {
                    "package": data.get("package", package),
                    "downloads": data.get("downloads", 0),
                    "start": data.get("start", ""),
                    "end": data.get("end", ""),
                }
            )
        except Exception as exc:
            logger.error("npm_weekly_downloads failed: %s", exc)
            return json.dumps({"error": str(exc)})


# ---------------------------------------------------------------------------
# PyPI tools
# ---------------------------------------------------------------------------


class PypiSearchTool(BaseTool):
    name = "pypi_search"
    description = (
        "Get PyPI package info by exact name. For discovery use pypi_package_info. "
        "params: query (str, treated as exact package name). "
        "Returns JSON: {name, version, summary, home_page, license}."
    )
    category = "packages"

    async def execute(self, params: dict, agent: "AgentInstance" = None) -> str:
        query = params.get("query", "")
        if not query:
            return json.dumps({"error": "query is required"})
        try:
            url = f"https://pypi.org/pypi/{urllib.parse.quote(query)}/json"
            data = _get_json(url)
            info = data.get("info", {})
            return json.dumps(
                {
                    "name": info.get("name", ""),
                    "version": info.get("version", ""),
                    "summary": info.get("summary", ""),
                    "home_page": info.get("home_page", ""),
                    "license": info.get("license", ""),
                }
            )
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return json.dumps({"error": f"Package '{query}' not found on PyPI"})
            return json.dumps({"error": str(exc)})
        except Exception as exc:
            logger.error("pypi_search failed: %s", exc)
            return json.dumps({"error": str(exc)})


class PypiPackageInfoTool(BaseTool):
    name = "pypi_package_info"
    description = (
        "Get detailed PyPI package metadata by exact name. "
        "params: package (str). "
        "Returns JSON: {name, version, summary, author, license, home_page, "
        "requires_python, classifiers (first 5)}."
    )
    category = "packages"

    async def execute(self, params: dict, agent: "AgentInstance" = None) -> str:
        package = params.get("package", "")
        if not package:
            return json.dumps({"error": "package is required"})
        try:
            url = f"https://pypi.org/pypi/{urllib.parse.quote(package)}/json"
            data = _get_json(url)
            info = data.get("info", {})
            return json.dumps(
                {
                    "name": info.get("name", ""),
                    "version": info.get("version", ""),
                    "summary": info.get("summary", ""),
                    "author": info.get("author", ""),
                    "license": info.get("license", ""),
                    "home_page": info.get("home_page", ""),
                    "requires_python": info.get("requires_python", ""),
                    "classifiers": info.get("classifiers", [])[:5],
                }
            )
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return json.dumps({"error": f"Package '{package}' not found on PyPI"})
            return json.dumps({"error": str(exc)})
        except Exception as exc:
            logger.error("pypi_package_info failed: %s", exc)
            return json.dumps({"error": str(exc)})


def register_package_tools(registry) -> None:
    registry.register(NpmSearchTool())
    registry.register(NpmPackageInfoTool())
    registry.register(NpmWeeklyDownloadsTool())
    registry.register(PypiSearchTool())
    registry.register(PypiPackageInfoTool())
    logger.debug("Package tools registered (5 tools)")
