"""
Docker Local Deploy Driver.

Runs containers on the local Docker daemon (dev / CI usage).
Ported from the original DockerDeployTool.
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import time

from .base import DeployResult, DeployTarget

logger = logging.getLogger(__name__)

_BASE_PORT = 9100
_MAX_PORT = 9199
_running: dict[str, dict] = {}


def _find_free_port() -> int:
    import socket
    used = {v["port"] for v in _running.values()}
    for port in range(_BASE_PORT, _MAX_PORT + 1):
        if port not in used:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("127.0.0.1", port)) != 0:
                    return port
    raise RuntimeError("No free ports in range 9100-9199")


def _generate_dockerfile(workspace: str) -> None:
    dockerfile = os.path.join(workspace, "Dockerfile")
    if os.path.isfile(dockerfile):
        return

    has_pkg = os.path.isfile(os.path.join(workspace, "package.json"))
    has_cargo = os.path.isfile(os.path.join(workspace, "Cargo.toml"))
    has_req = os.path.isfile(os.path.join(workspace, "requirements.txt"))
    has_go = os.path.isfile(os.path.join(workspace, "go.mod"))

    if has_pkg:
        import json
        try:
            with open(os.path.join(workspace, "package.json")) as f:
                pkg = json.load(f)
            has_build = "build" in pkg.get("scripts", {})
        except Exception:
            has_build = False
        if has_build:
            content = (
                "FROM node:20-slim\nWORKDIR /app\n"
                "COPY package*.json ./\n"
                "RUN npm install --legacy-peer-deps 2>/dev/null || npm install\n"
                "COPY . .\nRUN npm run build 2>/dev/null || true\n"
                "EXPOSE 3000\n"
                'CMD ["sh", "-c", "npm start 2>/dev/null || npx serve -s build -l 3000 2>/dev/null || npx serve -s dist -l 3000 2>/dev/null || python3 -m http.server 3000"]\n'
            )
        else:
            content = (
                "FROM node:20-slim\nWORKDIR /app\n"
                "COPY package*.json ./\n"
                "RUN npm install --legacy-peer-deps 2>/dev/null || npm install\n"
                "COPY . .\nEXPOSE 3000\n"
                'CMD ["sh", "-c", "npm start 2>/dev/null || npx serve -l 3000 ."]\n'
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
            'CMD ["sh", "-c", "python app.py 2>/dev/null || python main.py 2>/dev/null || python3 -m http.server 3000"]\n'
        )
    elif has_go:
        content = (
            "FROM golang:1.23-alpine AS build\nWORKDIR /app\nCOPY . .\n"
            "RUN go build -o server . 2>/dev/null || true\n"
            "FROM alpine:3.19\nCOPY --from=build /app/server /usr/local/bin/ 2>/dev/null || true\n"
            "EXPOSE 3000\nCMD [\"server\"]\n"
        )
    else:
        content = "FROM python:3.12-slim\nWORKDIR /app\nCOPY . .\nEXPOSE 3000\nCMD [\"python3\", \"-m\", \"http.server\", \"3000\"]\n"

    with open(dockerfile, "w") as f:
        f.write(content)


def _health_check(port: int, timeout: int = 30) -> tuple[bool, str]:
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


class DockerLocalTarget(DeployTarget):
    driver = "docker_local"
    label = "Docker Local"
    config_schema = []  # No config required

    async def deploy(self, workspace: str, mission_id: str, env: str = "staging", **kwargs) -> DeployResult:
        if not os.path.isdir(workspace):
            return DeployResult(ok=False, message=f"Workspace not found: {workspace}")

        container_name = f"macaron-app-{mission_id[:12].rstrip('-_')}"
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, timeout=10)

        try:
            _generate_dockerfile(workspace)
        except Exception as e:
            return DeployResult(ok=False, message=f"Dockerfile generation: {e}")

        try:
            port = _find_free_port()
        except RuntimeError as e:
            return DeployResult(ok=False, message=str(e))

        build_r = subprocess.run(
            ["docker", "build", "-t", container_name, "--network", "host", "."],
            cwd=workspace, capture_output=True, text=True, timeout=300,
        )
        if build_r.returncode != 0:
            return DeployResult(
                ok=False,
                message=f"Docker build failed:\n{(build_r.stderr or build_r.stdout)[-2000:]}",
            )

        run_r = subprocess.run(
            ["docker", "run", "-d", "--name", container_name,
             "-p", f"{port}:3000",
             "--memory", "256m", "--cpus", "1",
             "--restart", "unless-stopped",
             container_name],
            capture_output=True, text=True, timeout=30,
        )
        if run_r.returncode != 0:
            return DeployResult(ok=False, message=f"Docker run failed:\n{run_r.stderr[-500:]}")

        await asyncio.sleep(3)
        healthy, detail = _health_check(port, timeout=30)

        url = f"http://127.0.0.1:{port}"
        _running[mission_id] = {"container": container_name, "port": port, "url": url}

        return DeployResult(
            ok=True,
            url=url,
            container=container_name,
            port=port,
            message=f"Health: {detail[:120]}" if healthy else f"Started, health check failed: {detail}",
        )

    async def stop(self, mission_id: str) -> DeployResult:
        info = _running.pop(mission_id, None)
        container = info["container"] if info else f"macaron-app-{mission_id[:12]}"
        r = subprocess.run(["docker", "rm", "-f", container], capture_output=True, text=True, timeout=15)
        return DeployResult(ok=r.returncode == 0, message=r.stdout.strip() or r.stderr.strip())

    async def status(self, mission_id: str) -> DeployResult:
        info = _running.get(mission_id)
        if not info:
            return DeployResult(ok=False, message="Not running")
        r = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Status}}", info["container"]],
            capture_output=True, text=True, timeout=10,
        )
        state = r.stdout.strip()
        return DeployResult(ok=state == "running", url=info["url"], container=info["container"], message=state)

    async def logs(self, mission_id: str, lines: int = 50) -> str:
        info = _running.get(mission_id)
        container = info["container"] if info else f"macaron-app-{mission_id[:12]}"
        r = subprocess.run(
            ["docker", "logs", "--tail", str(lines), container],
            capture_output=True, text=True, timeout=10,
        )
        return r.stdout + r.stderr

    async def test_connection(self) -> tuple[bool, str]:
        r = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            return True, "Docker daemon is running"
        return False, r.stderr.strip() or "Docker not available"
