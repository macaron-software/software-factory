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

# Landlock filesystem sandbox — auto-detect binary path
# Binary lives at platform/tools/sandbox/landlock-runner (built from Rust source)
_LANDLOCK_DEFAULT = os.path.join(
    os.path.dirname(__file__), "sandbox", "landlock-runner"
)
_LANDLOCK_PATH = os.environ.get("LANDLOCK_RUNNER_PATH", "") or (
    _LANDLOCK_DEFAULT if os.path.isfile(_LANDLOCK_DEFAULT) else ""
)


def _landlock_enabled() -> bool:
    """Runtime check — respects config override (can be toggled in /settings)."""
    env_val = os.environ.get("LANDLOCK_ENABLED", "auto").lower()
    if env_val in ("false", "0", "no"):
        return False
    if not _LANDLOCK_PATH:
        return False
    # Check platform config for runtime toggle
    try:
        from ..config import get_config

        cfg = get_config()
        return cfg.security.landlock_enabled
    except Exception:
        return True  # default on if binary exists


LANDLOCK_ENABLED = _landlock_enabled()

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
        """Run command, optionally wrapped in Landlock filesystem sandbox + RTK proxy."""
        import shlex

        run_env = None
        if env:
            run_env = {**os.environ, **env}

        # Apply RTK proxy — rewrites known commands (git, grep, pytest, etc.)
        proxied = _rtk_wrap(command)
        was_proxied = proxied != command

        # Apply Landlock sandbox when available and workspace is set
        # Wraps: landlock-runner <workspace> -- sh -c '<command>'
        # Result: filesystem access restricted to workspace + system RO paths
        effective_workspace = cwd or self.workspace
        landlock_applied = False
        if _landlock_enabled() and effective_workspace and effective_workspace != ".":
            ws_abs = os.path.abspath(effective_workspace)
            if os.path.isdir(ws_abs):
                proxied = f"{_LANDLOCK_PATH} {shlex.quote(ws_abs)} -- sh -c {shlex.quote(proxied)}"
                landlock_applied = True
                logger.debug(
                    "Landlock sandbox: workspace=%s cmd=%s", ws_abs, command[:80]
                )

        try:
            r = subprocess.run(
                proxied,
                shell=True,
                capture_output=True,
                text=True,
                cwd=effective_workspace,
                timeout=timeout,
                env=run_env,
                preexec_fn=lambda: os.nice(10),  # low CPU priority
            )
            _track_rtk_stats(was_proxied, len(r.stdout.encode()))
            return SandboxResult(
                stdout=r.stdout[-5000:],
                stderr=r.stderr[-3000:],
                returncode=r.returncode,
                sandboxed=landlock_applied,
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


def run_in_project_docker(
    project_id: str,
    command: str,
    cwd: Optional[str] = None,
    timeout: int = SANDBOX_TIMEOUT,
    env: Optional[dict] = None,
    agent_id: Optional[str] = None,
) -> SandboxResult:
    """Run a command inside the persistent Docker container of the given project.

    Platform Bubble pattern: uses `docker exec` on a long-running project container
    instead of `docker run --rm` (ephemeral). The container persists between calls
    so build caches, node_modules, venvs etc. accumulate normally.

    Falls back to direct subprocess if Docker is unavailable.

    Usage:
        result = run_in_project_docker("software-factory", "pytest tests/")
        result = run_in_project_docker("ac-hello-html", "npm test", cwd=workspace)
    """
    workspace = cwd or ""

    try:
        from ..projects.manager import get_project_store

        proj = get_project_store().get(project_id)
        if proj and proj.path:
            workspace = workspace or proj.path
    except Exception as e:
        logger.debug("run_in_project_docker: project lookup failed: %s", e)

    try:
        from ..projects.container import get_project_container

        pc = get_project_container(project_id, path=workspace)
        exec_cwd = cwd if cwd else "/workspace"
        result = pc.exec(command, cwd=exec_cwd, env=env, timeout=timeout)
        return SandboxResult(
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
        )
    except Exception as e:
        logger.warning(
            "run_in_project_docker: docker exec failed (%s) — falling back to direct", e
        )

    executor = SandboxExecutor(workspace or ".")
    return executor._run_direct(command, cwd or workspace, timeout, env)
