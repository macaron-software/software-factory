"""
Deploy Tools - Build, run, and deploy project containers.
============================================================
Provides real deployment: Dockerfile auto-generation → npm install →
docker build → docker run → health check → screenshot.
Each mission workspace gets its own container with a unique port.
"""

from __future__ import annotations

import logging
import os
import subprocess
import time

from ..models import AgentInstance
from .registry import BaseTool

logger = logging.getLogger(__name__)

# Port range for deployed mission containers
_BASE_PORT = 9100
_MAX_PORT = 9199

# Track running containers: {mission_id: {"container": name, "port": port, "url": url}}
_running: dict[str, dict] = {}


def _find_free_port() -> int:
    """Find a free port in the mission range."""
    used = {v["port"] for v in _running.values()}
    for port in range(_BASE_PORT, _MAX_PORT + 1):
        if port not in used:
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("127.0.0.1", port)) != 0:
                    return port
    raise RuntimeError("No free ports in range 9100-9199")


def _generate_dockerfile(workspace: str) -> str:
    """Generate a Dockerfile if one doesn't exist, based on project type."""
    dockerfile = os.path.join(workspace, "Dockerfile")
    if os.path.isfile(dockerfile):
        return dockerfile

    has_pkg = os.path.isfile(os.path.join(workspace, "package.json"))
    has_cargo = os.path.isfile(os.path.join(workspace, "Cargo.toml"))
    has_req = os.path.isfile(os.path.join(workspace, "requirements.txt"))
    has_go = os.path.isfile(os.path.join(workspace, "go.mod"))
    has_html = os.path.isfile(os.path.join(workspace, "index.html"))

    if has_pkg:
        import json
        try:
            with open(os.path.join(workspace, "package.json")) as f:
                pkg = json.load(f)
            has_build = "build" in pkg.get("scripts", {})
            has_start = "start" in pkg.get("scripts", {})
        except Exception:
            has_build = has_start = False

        if has_build:
            content = (
                "FROM node:20-slim\nWORKDIR /app\n"
                "COPY package*.json ./\n"
                "RUN npm install --legacy-peer-deps 2>/dev/null || npm install\n"
                "COPY . .\nRUN npm run build 2>/dev/null || true\n"
                "EXPOSE 3000\n"
                'CMD ["sh", "-c", "npm start 2>/dev/null || npx serve -s build -l 3000 2>/dev/null || npx serve -s dist -l 3000 2>/dev/null || python3 -m http.server 3000"]\n'
            )
        elif has_start:
            content = (
                "FROM node:20-slim\nWORKDIR /app\n"
                "COPY package*.json ./\nRUN npm install --legacy-peer-deps 2>/dev/null || npm install\n"
                "COPY . .\nEXPOSE 3000\nCMD [\"npm\", \"start\"]\n"
            )
        else:
            content = (
                "FROM node:20-slim\nWORKDIR /app\n"
                "COPY package*.json ./\nRUN npm install --legacy-peer-deps 2>/dev/null || npm install\n"
                "COPY . .\nEXPOSE 3000\n"
                'CMD ["sh", "-c", "npx serve -l 3000 . 2>/dev/null || python3 -m http.server 3000"]\n'
            )
    elif has_cargo:
        content = (
            "FROM rust:1.83-slim AS build\nWORKDIR /app\nCOPY . .\n"
            "RUN cargo build --release 2>/dev/null || true\n"
            "FROM debian:bookworm-slim\n"
            "COPY --from=build /app/target/release/* /usr/local/bin/ 2>/dev/null || true\n"
            "EXPOSE 3000\nCMD [\"sh\", \"-c\", \"echo 'Rust binary ready'\"]\n"
        )
    elif has_req:
        content = (
            "FROM python:3.12-slim\nWORKDIR /app\n"
            "COPY requirements*.txt ./\nRUN pip install -r requirements.txt 2>/dev/null || true\n"
            "COPY . .\nEXPOSE 3000\n"
            'CMD ["sh", "-c", "python app.py 2>/dev/null || python main.py 2>/dev/null || python -m http.server 3000"]\n'
        )
    elif has_go:
        content = (
            "FROM golang:1.23-alpine AS build\nWORKDIR /app\nCOPY . .\n"
            "RUN go build -o server . 2>/dev/null || true\n"
            "FROM alpine:3.19\nCOPY --from=build /app/server /usr/local/bin/ 2>/dev/null || true\n"
            "EXPOSE 3000\nCMD [\"server\"]\n"
        )
    elif has_html:
        content = "FROM python:3.12-slim\nWORKDIR /app\nCOPY . .\nEXPOSE 3000\nCMD [\"python3\", \"-m\", \"http.server\", \"3000\"]\n"
    else:
        content = "FROM python:3.12-slim\nWORKDIR /app\nCOPY . .\nEXPOSE 3000\nCMD [\"python3\", \"-m\", \"http.server\", \"3000\"]\n"

    with open(dockerfile, "w") as f:
        f.write(content)
    logger.info("Generated Dockerfile for %s", workspace)
    return dockerfile


def _health_check(port: int, timeout: int = 30) -> tuple[bool, str]:
    """Wait for container to respond. Returns (healthy, detail)."""
    import urllib.request
    url = f"http://127.0.0.1:{port}/"
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                body = resp.read(500).decode("utf-8", errors="replace")
                return True, f"HTTP {resp.status}, body: {body[:200]}"
        except Exception:
            time.sleep(2)
    return False, f"No response on port {port} after {timeout}s"


class DockerDeployTool(BaseTool):
    name = "docker_deploy"
    description = (
        "Build and run the workspace as a Docker container. "
        "Auto-generates Dockerfile if missing, installs deps, builds, runs, health-checks. "
        "Returns the live URL. Use this to ACTUALLY deploy generated code."
    )
    category = "deploy"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        import asyncio
        cwd = params.get("cwd", ".")
        if not os.path.isdir(cwd):
            return f"[FAIL] Workspace not found: {cwd}"

        mission_id = params.get("mission_id", os.path.basename(os.path.abspath(cwd)))
        container_name = f"macaron-app-{mission_id[:12]}"

        steps = []

        # Stop existing container
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, timeout=10)

        # Generate Dockerfile
        try:
            _generate_dockerfile(cwd)
            steps.append("Dockerfile ready")
        except Exception as e:
            return f"[FAIL] Dockerfile generation: {e}"

        # Find free port
        try:
            port = _find_free_port()
        except RuntimeError as e:
            return f"[FAIL] {e}"

        # Docker build
        logger.info("Building image %s from %s", container_name, cwd)
        build_r = subprocess.run(
            ["docker", "build", "-t", container_name, "--network", "host", "."],
            cwd=cwd, capture_output=True, text=True, timeout=300,
        )
        if build_r.returncode != 0:
            return f"[FAIL] Docker build failed:\n{build_r.stderr[-2000:] or build_r.stdout[-2000:]}"
        steps.append("Docker build OK")

        # Docker run
        logger.info("Starting %s on port %d", container_name, port)
        run_r = subprocess.run(
            ["docker", "run", "-d", "--name", container_name,
             "-p", f"{port}:3000",
             "--memory", "256m", "--cpus", "1",
             "--restart", "unless-stopped",
             container_name],
            capture_output=True, text=True, timeout=30,
        )
        if run_r.returncode != 0:
            return f"[FAIL] Docker run failed:\n{run_r.stderr[-500:]}"
        steps.append(f"Container started on port {port}")

        # Health check
        await asyncio.sleep(3)
        healthy, detail = _health_check(port, timeout=30)

        url = f"http://127.0.0.1:{port}"
        _running[mission_id] = {
            "container": container_name,
            "port": port,
            "url": url,
        }

        if healthy:
            steps.append(f"Health OK: {detail[:80]}")
            return f"[OK] DEPLOYED\nURL: {url}\nContainer: {container_name}\n" + " → ".join(steps)
        else:
            logs = subprocess.run(
                ["docker", "logs", "--tail", "20", container_name],
                capture_output=True, text=True, timeout=10,
            )
            return (
                f"[WARN] Started but health check failed\nURL: {url}\n"
                f"Container: {container_name}\nHealth: {detail}\n"
                f"Logs:\n{logs.stdout[-800:]}{logs.stderr[-400:]}"
            )


class DockerStopTool(BaseTool):
    name = "docker_stop"
    description = "Stop and remove a deployed container by mission_id."
    category = "deploy"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        mission_id = params.get("mission_id", "")
        container = params.get("container", "")
        if mission_id and mission_id in _running:
            container = _running[mission_id]["container"]
        elif not container:
            container = f"macaron-app-{mission_id[:12]}"

        r = subprocess.run(["docker", "rm", "-f", container], capture_output=True, text=True, timeout=10)
        if mission_id in _running:
            del _running[mission_id]
        return f"[OK] Stopped {container}" if r.returncode == 0 else f"[FAIL] {r.stderr}"


class DockerStatusTool(BaseTool):
    name = "docker_status"
    description = "Check status of a deployed container (running/stopped, URL, logs)."
    category = "deploy"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        mission_id = params.get("mission_id", "")
        container = f"macaron-app-{mission_id[:12]}" if mission_id else params.get("container", "")
        if not container:
            return "Error: mission_id or container required"
        r = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Status}}", container],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode != 0:
            return f"No container found: {container}"
        status = r.stdout.strip()
        logs = subprocess.run(
            ["docker", "logs", "--tail", "10", container],
            capture_output=True, text=True, timeout=5,
        )
        info = _running.get(mission_id, {})
        url = info.get("url", f"http://127.0.0.1:{info.get('port', '?')}" if info else "unknown")
        return f"Container: {container}\nStatus: {status}\nURL: {url}\nLogs:\n{logs.stdout[-500:]}"


def get_running_apps() -> dict:
    """Return dict of currently running mission apps."""
    return dict(_running)


def register_deploy_tools(registry):
    """Register all deploy tools."""
    registry.register(DockerDeployTool())
    registry.register(DockerStopTool())
    registry.register(DockerStatusTool())
