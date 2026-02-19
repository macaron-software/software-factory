"""Docker Sandbox — isolated execution for agent tools.

When SANDBOX_ENABLED=true, wraps subprocess commands in Docker containers
for security isolation. The workspace is mounted as a volume.

Architecture:
  Agent tool call → SandboxExecutor.run() → docker run → result
  - Workspace mounted read-write at /workspace
  - Network access configurable (default: none for security)
  - Auto-selects image based on command/language
  - Timeout enforced via docker stop

Configuration (env vars):
  SANDBOX_ENABLED=true       — enable Docker sandbox (default: false)
  SANDBOX_IMAGE=python:3.12  — default Docker image
  SANDBOX_NETWORK=none       — network mode (none, bridge, host)
  SANDBOX_TIMEOUT=300        — max execution time (seconds)
  SANDBOX_MEMORY=512m        — memory limit
"""
from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Config
SANDBOX_ENABLED = os.environ.get("SANDBOX_ENABLED", "").lower() in ("true", "1", "yes")
SANDBOX_IMAGE = os.environ.get("SANDBOX_IMAGE", "python:3.12-slim")
SANDBOX_NETWORK = os.environ.get("SANDBOX_NETWORK", "none")
SANDBOX_TIMEOUT = int(os.environ.get("SANDBOX_TIMEOUT", "300"))
SANDBOX_MEMORY = os.environ.get("SANDBOX_MEMORY", "512m")

# Image selection by detected language/tool
_IMAGE_MAP = {
    "python": "python:3.12-slim",
    "node": "node:20-slim",
    "npm": "node:20-slim",
    "npx": "node:20-slim",
    "cargo": "rust:1.83-slim",
    "rustc": "rust:1.83-slim",
    "go": "golang:1.23-alpine",
    "swift": "swift:6.0",
    "gradle": "gradle:8.5-jdk21",
    "mvn": "maven:3.9-eclipse-temurin-21",
    "dotnet": "mcr.microsoft.com/dotnet/sdk:9.0",
}


def _detect_image(command: str) -> str:
    """Auto-detect Docker image from command."""
    first_word = command.strip().split()[0] if command.strip() else ""
    # Check direct match
    if first_word in _IMAGE_MAP:
        return _IMAGE_MAP[first_word]
    # Check if command contains known tools
    for tool, image in _IMAGE_MAP.items():
        if tool in command:
            return image
    return SANDBOX_IMAGE


@dataclass
class SandboxResult:
    stdout: str
    stderr: str
    returncode: int
    sandboxed: bool  # True if ran in Docker, False if ran directly
    image: str = ""
    duration_ms: int = 0


class SandboxExecutor:
    """Executes commands in Docker containers or directly on host."""

    def __init__(self, workspace: str = "."):
        self.workspace = os.path.abspath(workspace)

    def run(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: int = SANDBOX_TIMEOUT,
        image: Optional[str] = None,
        network: str = SANDBOX_NETWORK,
        env: Optional[dict] = None,
    ) -> SandboxResult:
        """Execute command — in Docker if sandbox enabled, else direct subprocess."""
        import time
        t0 = time.monotonic()

        if SANDBOX_ENABLED:
            result = self._run_docker(command, cwd, timeout, image, network, env)
        else:
            result = self._run_direct(command, cwd, timeout, env)

        result.duration_ms = int((time.monotonic() - t0) * 1000)
        return result

    def _run_docker(
        self,
        command: str,
        cwd: Optional[str],
        timeout: int,
        image: Optional[str],
        network: str,
        env: Optional[dict],
    ) -> SandboxResult:
        """Run command inside a Docker container."""
        use_image = image or _detect_image(command)
        workdir = cwd or self.workspace

        docker_cmd = [
            "docker", "run", "--rm",
            "--network", network,
            "--memory", SANDBOX_MEMORY,
            "--cpus", "2",
            "-v", f"{self.workspace}:/workspace",
            "-w", f"/workspace/{os.path.relpath(workdir, self.workspace)}" if workdir != self.workspace else "/workspace",
        ]

        # Pass environment variables
        if env:
            for k, v in env.items():
                docker_cmd.extend(["-e", f"{k}={v}"])

        docker_cmd.extend([use_image, "sh", "-c", command])

        logger.info("Sandbox: docker run %s — %s", use_image, command[:100])

        try:
            r = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout + 10,  # docker overhead
            )
            return SandboxResult(
                stdout=r.stdout[-5000:],
                stderr=r.stderr[-3000:],
                returncode=r.returncode,
                sandboxed=True,
                image=use_image,
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(
                stdout="",
                stderr=f"[SANDBOX] TIMEOUT ({timeout}s) — image: {use_image}",
                returncode=-1,
                sandboxed=True,
                image=use_image,
            )
        except FileNotFoundError:
            logger.warning("Docker not found, falling back to direct execution")
            return self._run_direct(command, cwd, timeout, env)
        except Exception as e:
            return SandboxResult(
                stdout="",
                stderr=f"[SANDBOX] Error: {e}",
                returncode=-1,
                sandboxed=True,
                image=use_image,
            )

    def _run_direct(
        self,
        command: str,
        cwd: Optional[str],
        timeout: int,
        env: Optional[dict],
    ) -> SandboxResult:
        """Run command directly on host (no sandbox)."""
        run_env = None
        if env:
            run_env = {**os.environ, **env}

        try:
            r = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=cwd or self.workspace,
                timeout=timeout,
                env=run_env,
            )
            return SandboxResult(
                stdout=r.stdout[-5000:],
                stderr=r.stderr[-3000:],
                returncode=r.returncode,
                sandboxed=False,
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(
                stdout="",
                stderr=f"[TIMEOUT] ({timeout}s)",
                returncode=-1,
                sandboxed=False,
            )
        except Exception as e:
            return SandboxResult(
                stdout="",
                stderr=f"Error: {e}",
                returncode=-1,
                sandboxed=False,
            )


def get_sandbox(workspace: str = ".") -> SandboxExecutor:
    """Get a sandbox executor for the given workspace."""
    return SandboxExecutor(workspace)
