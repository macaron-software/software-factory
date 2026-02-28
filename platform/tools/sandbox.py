"""Docker Sandbox — isolated execution for agent tools.

When SANDBOX_ENABLED=true, wraps subprocess commands in Docker containers
for security isolation. The workspace is mounted as a volume.

Architecture:
  Agent tool call → SandboxExecutor.run() → [RTK proxy] → docker run → result
  - Workspace mounted read-write at /workspace
  - Network access configurable (default: none for security)
  - Auto-selects image based on command/language
  - Timeout enforced via docker stop
  - RTK proxy compresses stdout before returning to LLM agents (60-90% token savings)

Configuration (env vars):
  SANDBOX_ENABLED=true       — enable Docker sandbox (default: false)
  SANDBOX_IMAGE=python:3.12  — default Docker image
  SANDBOX_NETWORK=none       — network mode (none, bridge, host)
  SANDBOX_TIMEOUT=300        — max execution time (seconds)
  SANDBOX_MEMORY=512m        — memory limit
  RTK_ENABLED=true           — enable RTK token compression proxy (default: auto-detect)
  RTK_PATH=/path/to/rtk      — override RTK binary path
"""

from __future__ import annotations

import logging
import os
import re
import shutil
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
SANDBOX_WORKSPACE_VOLUME = os.environ.get("SANDBOX_WORKSPACE_VOLUME", "")

# RTK proxy — auto-detect unless explicitly set
_RTK_ENABLED_ENV = os.environ.get("RTK_ENABLED", "auto").lower()
_RTK_PATH = os.environ.get("RTK_PATH", "") or shutil.which("rtk") or ""
RTK_ENABLED = (
    bool(_RTK_PATH)
    if _RTK_ENABLED_ENV == "auto"
    else _RTK_ENABLED_ENV in ("true", "1", "yes")
)

# RTK command rewrite rules: (regex_pattern, rtk_subcommand_template)
# First match wins. {rest} = everything after the matched command.
_RTK_RULES: list[tuple[re.Pattern, str]] = [
    # git operations
    (
        re.compile(r"^git\s+(status|diff|log|push|pull|add|commit|show)\b(.*)$"),
        r"rtk git \1\2",
    ),
    # grep / ripgrep
    (re.compile(r"^(grep|rg)\s+(.*)$"), r"rtk grep \2"),
    # ls
    (re.compile(r"^ls(\s+.+)?$"), r"rtk ls\1"),
    # cat → rtk read (full file)
    (re.compile(r"^cat\s+(.+)$"), r"rtk read \1"),
    # tail / head → rtk err (last lines) or keep as-is (rtk read handles files better)
    (re.compile(r"^(head|tail)\s+(.+)$"), r"rtk read \2"),
    # docker logs
    (re.compile(r"^docker\s+logs\b(.*)$"), r"rtk docker logs\1"),
    # docker ps / images
    (re.compile(r"^docker\s+(ps|images)\b(.*)$"), r"rtk docker \1\2"),
    # pytest
    (re.compile(r"^(python3?\s+-m\s+)?pytest\b(.*)$"), r"rtk pytest\2"),
    # cargo test / check / build
    (re.compile(r"^cargo\s+(test|check|build|clippy)\b(.*)$"), r"rtk cargo \1\2"),
    # go test / build / vet
    (re.compile(r"^go\s+(test|build|vet)\b(.*)$"), r"rtk go \1\2"),
    # npm test / run
    (re.compile(r"^npm\s+(test|run)\b(.*)$"), r"rtk npm \1\2"),
    # npx playwright
    (re.compile(r"^npx\s+playwright\b(.*)$"), r"rtk playwright\1"),
    # curl
    (re.compile(r"^curl\b(.*)$"), r"rtk curl\1"),
    # gh cli
    (re.compile(r"^gh\s+(pr|issue|run|repo)\b(.*)$"), r"rtk gh \1\2"),
]


def _rtk_wrap(command: str) -> str:
    """Rewrite a shell command to use RTK if a matching rule exists."""
    if not RTK_ENABLED or not _RTK_PATH:
        return command
    cmd = command.strip()
    for pattern, template in _RTK_RULES:
        m = pattern.match(cmd)
        if m:
            rewritten = pattern.sub(template, cmd)
            # Prefix with full path to rtk binary
            if rewritten.startswith("rtk "):
                rewritten = f"{_RTK_PATH} {rewritten[4:]}"
            logger.debug("RTK proxy: %s → %s", cmd[:80], rewritten[:80])
            return rewritten
    return command


def _track_rtk_stats(proxied: bool, output_bytes: int) -> None:
    """Persist RTK proxy counters to platform.db (best-effort, non-blocking)."""
    try:
        from ..db.migrations import get_db

        db = get_db()
        db.execute(
            """UPDATE rtk_stats SET
                cmds_total = cmds_total + 1,
                cmds_proxied = cmds_proxied + ?,
                bytes_saved_est = bytes_saved_est + ?,
                updated_at = datetime('now')
               WHERE id = 1""",
            (1 if proxied else 0, output_bytes // 2 if proxied else 0),
        )
        db.commit()
    except Exception:
        pass  # never block agent execution for stats


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
    rtk_proxied: bool = False  # True if RTK compressed the output


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
        agent_id: Optional[str] = None,
    ) -> SandboxResult:
        """Execute command — in Docker if sandbox enabled, else direct subprocess."""
        import time

        t0 = time.monotonic()

        if SANDBOX_ENABLED:
            result = self._run_docker(
                command, cwd, timeout, image, network, env, agent_id
            )
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
        agent_id: Optional[str] = None,
    ) -> SandboxResult:
        """Run command inside a Docker container with per-agent isolation."""
        use_image = image or _detect_image(command)
        workdir = cwd or self.workspace

        # Per-agent UID isolation: hash agent_id to a stable UID (10000-60000 range)
        uid = None
        if agent_id:
            uid = 10000 + (hash(agent_id) % 50000)

        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "--network",
            network,
            "--memory",
            SANDBOX_MEMORY,
            "--cpus",
            "2",
            "--tmpfs",
            "/tmp:rw,nosuid,size=200m",
        ]

        # Mount workspace: use named volume if configured (Docker-in-Docker),
        # otherwise bind-mount the container's workspace directory
        if SANDBOX_WORKSPACE_VOLUME:
            # Named volume mount — works with Docker socket sharing
            docker_cmd.extend(["-v", f"{SANDBOX_WORKSPACE_VOLUME}:/workspace"])
            # Compute workdir relative to workspace root (/app/workspace → volume root)
            ws_root = os.environ.get("SF_ROOT", "/app") + "/workspace"
            if workdir.startswith(ws_root):
                rel = os.path.relpath(workdir, ws_root)
                docker_cmd.extend(["-w", f"/workspace/{rel}"])
            else:
                docker_cmd.extend(["-w", "/workspace"])
        else:
            docker_cmd.extend(
                [
                    "-v",
                    f"{self.workspace}:/workspace",
                    "-w",
                    f"/workspace/{os.path.relpath(workdir, self.workspace)}"
                    if workdir != self.workspace
                    else "/workspace",
                ]
            )

        # Run as non-root agent-specific user
        if uid:
            docker_cmd.extend(["--user", str(uid)])
            logger.debug("Sandbox agent=%s uid=%d", agent_id, uid)

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
        """Run command directly on host (no sandbox), with RTK proxy for token compression."""
        run_env = None
        if env:
            run_env = {**os.environ, **env}

        # Apply RTK proxy — rewrites known commands (git, grep, pytest, etc.)
        # to compress stdout before it reaches the LLM agent context
        proxied = _rtk_wrap(command)
        was_proxied = proxied != command

        try:
            r = subprocess.run(
                proxied,
                shell=True,
                capture_output=True,
                text=True,
                cwd=cwd or self.workspace,
                timeout=timeout,
                env=run_env,
                preexec_fn=lambda: os.nice(10),  # low CPU priority
            )
            _track_rtk_stats(was_proxied, len(r.stdout.encode()))
            return SandboxResult(
                stdout=r.stdout[-5000:],
                stderr=r.stderr[-3000:],
                returncode=r.returncode,
                sandboxed=False,
                rtk_proxied=was_proxied,
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
