"""SonarQube brick — code quality analysis via REST API."""
# Ref: feat-tool-builder

from __future__ import annotations

import asyncio
import json
import logging
import os

from . import BrickDef, BrickRegistry, ToolDef

logger = logging.getLogger(__name__)

_BASE = os.environ.get("SONAR_URL", "http://localhost:9000")
_TOKEN = os.environ.get("SONAR_TOKEN", "")


async def _sonar_api(endpoint: str) -> str:
    """Call SonarQube REST API."""
    import urllib.request
    import urllib.error
    url = f"{_BASE}/api/{endpoint}"
    req = urllib.request.Request(url)
    if _TOKEN:
        import base64
        creds = base64.b64encode(f"{_TOKEN}:".encode()).decode()
        req.add_header("Authorization", f"Basic {creds}")
    try:
        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(None, urllib.request.urlopen, req)
        return resp.read().decode("utf-8")
    except Exception as e:
        return f"Error: {e}"


async def run_analysis(args: dict, ctx=None) -> str:
    project = args.get("project_key", "")
    path = args.get("path", ".")
    cmd = f"sonar-scanner -Dsonar.projectKey={project} -Dsonar.sources={path}"
    if _TOKEN:
        cmd += f" -Dsonar.token={_TOKEN}"
    if _BASE:
        cmd += f" -Dsonar.host.url={_BASE}"
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        return (stdout or b"").decode("utf-8", errors="replace")[-2000:]
    except Exception as e:
        return f"Error: {e}"


async def get_quality_gate(args: dict, ctx=None) -> str:
    project = args.get("project_key", "")
    return await _sonar_api(f"qualitygates/project_status?projectKey={project}")


async def get_issues(args: dict, ctx=None) -> str:
    project = args.get("project_key", "")
    severity = args.get("severity", "")
    endpoint = f"issues/search?componentKeys={project}&ps=20"
    if severity:
        endpoint += f"&severities={severity}"
    return await _sonar_api(endpoint)


async def get_coverage(args: dict, ctx=None) -> str:
    project = args.get("project_key", "")
    return await _sonar_api(
        f"measures/component?component={project}&metricKeys=coverage,line_coverage,branch_coverage"
    )


BRICK = BrickDef(
    id="sonarqube",
    name="SonarQube",
    description="Code quality analysis: scan, quality gates, issues, coverage",
    tools=[
        ToolDef(name="sonar_analyze", description="Run SonarQube analysis",
                parameters={"project_key": "str", "path": "str"},
                execute=run_analysis, category="quality"),
        ToolDef(name="sonar_quality_gate", description="Get quality gate status",
                parameters={"project_key": "str"},
                execute=get_quality_gate, category="quality"),
        ToolDef(name="sonar_issues", description="List code issues",
                parameters={"project_key": "str", "severity": "str (BLOCKER|CRITICAL|MAJOR|MINOR)"},
                execute=get_issues, category="quality"),
        ToolDef(name="sonar_coverage", description="Get test coverage metrics",
                parameters={"project_key": "str"},
                execute=get_coverage, category="quality"),
    ],
    roles=["qa", "security", "devops"],
    requires_env=["SONAR_TOKEN"],
)


def register(registry: BrickRegistry) -> None:
    registry.register(BRICK)
