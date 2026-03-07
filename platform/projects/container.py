"""Project container lifecycle — Platform Bubble pattern.

Each project gets a persistent Docker container that agents exec into.
No DinD: the platform talks to the HOST Docker daemon via mounted socket.

Architecture:
  Platform (Debian 13) → docker.sock → HOST daemon
                                      → docker exec sf-{project_id} cmd
                                      → volume sf-workspace-{project_id}

Container naming:  sf-{project_id}
Volume naming:     sf-workspace-{project_id}
Image selection:   sf-{project_id}:latest if Dockerfile present, else auto-detected

Why this pattern instead of docker run --rm:
  - State persists between agent calls (node_modules, build cache, venv)
  - Landlock works natively inside Debian-based project containers
  - The container becomes the deployable artefact (build → push → run)
  - No cold-start overhead per tool call

Source: inspired by GitHub Actions runner, Dagger.io socket pattern.
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Docker socket proxy URL — used when DOCKER_HOST is set by the proxy
DOCKER_HOST = os.environ.get("DOCKER_HOST", "")

# Memory + CPU limits for project containers
PROJECT_MEMORY = os.environ.get("PROJECT_CONTAINER_MEMORY", "1g")
PROJECT_CPUS = os.environ.get("PROJECT_CONTAINER_CPUS", "2")
PROJECT_NETWORK = os.environ.get("PROJECT_CONTAINER_NETWORK", "sf-projects")

# Base images per project type — detected from Dockerfile or tech stack
_BASE_IMAGES = {
    "node": "node:lts-slim",
    "python": "python:3.12-slim",
    "rust": "rust:1-slim",
    "go": "golang:1.23-bookworm",
    "java": "eclipse-temurin:21-jdk-jammy",
    "ruby": "ruby:3.3-slim",
    "default": "debian:bookworm-slim",
}


def container_name(project_id: str) -> str:
    """Canonical Docker container name for a project."""
    return f"sf-{project_id}"


def volume_name(project_id: str) -> str:
    """Canonical Docker volume name for a project workspace."""
    return f"sf-workspace-{project_id}"


def _docker(
    *args: str, check: bool = True, capture: bool = True
) -> subprocess.CompletedProcess:
    """Run a docker CLI command, optionally via DOCKER_HOST proxy."""
    cmd = ["docker"] + list(args)
    env = os.environ.copy()
    if DOCKER_HOST:
        env["DOCKER_HOST"] = DOCKER_HOST
    return subprocess.run(
        cmd,
        env=env,
        capture_output=capture,
        text=True,
        check=check,
    )


def _detect_base_image(project_path: str) -> str:
    """Detect appropriate base image from project Dockerfile or files present."""
    if project_path:
        dockerfile = os.path.join(project_path, "Dockerfile")
        if os.path.isfile(dockerfile):
            # Prefer custom image built from project Dockerfile
            return ""  # caller builds sf-{id}:latest first

        for marker, image in [
            ("package.json", "node"),
            ("requirements.txt", "python"),
            ("pyproject.toml", "python"),
            ("Cargo.toml", "rust"),
            ("go.mod", "go"),
            ("pom.xml", "java"),
            ("Gemfile", "ruby"),
        ]:
            if os.path.isfile(os.path.join(project_path, marker)):
                return _BASE_IMAGES[image]

    return _BASE_IMAGES["default"]


@dataclass
class ContainerResult:
    """Result of a docker exec call."""

    stdout: str
    stderr: str
    exit_code: int
    container_id: str = ""

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    @property
    def output(self) -> str:
        return (self.stdout or "") + (self.stderr or "")


class ProjectContainer:
    """Manages the lifecycle of a project's Docker container.

    Usage:
        pc = ProjectContainer("my-api", path="/workspaces/my-api")
        pc.ensure_running()
        result = pc.exec("pytest tests/ -q")
        if result.ok:
            image = pc.build()
            pc.push(registry="registry.example.com")
    """

    def __init__(self, project_id: str, path: str = "", image: str = ""):
        self.project_id = project_id
        self.path = path or ""
        self._image = image  # override; empty = auto-detect
        self.name = container_name(project_id)
        self.volume = volume_name(project_id)

    @property
    def image(self) -> str:
        if self._image:
            return self._image
        detected = _detect_base_image(self.path)
        return detected or f"sf-{self.project_id}:latest"

    def status(self) -> str:
        """Return container status: running | stopped | missing."""
        try:
            r = _docker(
                "inspect", "--format", "{{.State.Status}}", self.name, check=False
            )
            if r.returncode != 0:
                return "missing"
            return r.stdout.strip()
        except Exception:
            return "missing"

    def ensure_running(self, build_if_needed: bool = True) -> bool:
        """Ensure the project container is running. Creates or starts if needed.

        Returns True if container is running after this call.
        """
        st = self.status()
        if st == "running":
            return True

        if st == "missing":
            return self._create()

        if st in ("exited", "created", "paused"):
            logger.info("Container %s is %s — starting", self.name, st)
            try:
                _docker("start", self.name)
                return True
            except subprocess.CalledProcessError as e:
                logger.error("Failed to start container %s: %s", self.name, e.stderr)
                return False

        logger.warning("Container %s in unknown state: %s", self.name, st)
        return False

    def _create(self) -> bool:
        """Create and start the project container."""
        img = self.image
        if img == f"sf-{self.project_id}:latest":
            # Try to build from Dockerfile first
            built = self.build()
            if not built:
                # Fall back to auto-detected base image
                img = _detect_base_image(self.path) or _BASE_IMAGES["default"]
                logger.info(
                    "No Dockerfile — using base image %s for %s", img, self.project_id
                )

        logger.info("Creating container %s (image=%s)", self.name, img)
        try:
            cmd = [
                "run",
                "-d",
                "--name",
                self.name,
                "--memory",
                PROJECT_MEMORY,
                "--cpus",
                PROJECT_CPUS,
                "--restart",
                "unless-stopped",
                "-v",
                f"{self.volume}:/workspace",
                "-w",
                "/workspace",
                "--label",
                f"sf.project_id={self.project_id}",
            ]
            # Attach to project network if it exists
            try:
                _docker("network", "inspect", PROJECT_NETWORK, check=True)
                cmd.extend(["--network", PROJECT_NETWORK])
            except subprocess.CalledProcessError:
                pass  # network not created yet — skip

            # Keep container alive with sleep infinity (no process to run)
            cmd.extend([img, "sleep", "infinity"])
            _docker(*cmd)
            logger.info("Container %s created and running", self.name)
            return True
        except subprocess.CalledProcessError as e:
            logger.error("Failed to create container %s: %s", self.name, e.stderr)
            return False

    def exec(
        self,
        command: str,
        cwd: str = "/workspace",
        env: Optional[dict] = None,
        user: str = "",
        timeout: int = 300,
    ) -> ContainerResult:
        """Execute a command inside the running project container.

        This replaces docker run --rm (ephemeral) with docker exec (persistent).
        The container must be running (call ensure_running() first).
        """
        if not self.ensure_running():
            return ContainerResult(
                stdout="", stderr=f"Container {self.name} is not running", exit_code=1
            )

        cmd = ["exec"]
        if user:
            cmd.extend(["-u", user])
        if env:
            for k, v in env.items():
                cmd.extend(["-e", f"{k}={v}"])
        cmd.extend(["-w", cwd, self.name, "sh", "-c", command])

        logger.info("docker exec %s — %s", self.name, command[:120])
        try:
            r = subprocess.run(
                ["docker"] + cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={
                    **os.environ,
                    **({"DOCKER_HOST": DOCKER_HOST} if DOCKER_HOST else {}),
                },
            )
            return ContainerResult(
                stdout=r.stdout,
                stderr=r.stderr,
                exit_code=r.returncode,
                container_id=self.name,
            )
        except subprocess.TimeoutExpired:
            return ContainerResult(
                stdout="", stderr=f"Timeout after {timeout}s", exit_code=124
            )
        except Exception as e:
            return ContainerResult(stdout="", stderr=str(e), exit_code=1)

    def build(self, tag: str = "") -> str:
        """Build a Docker image from the project Dockerfile.

        Returns the image tag on success, empty string on failure.
        """
        dockerfile = os.path.join(self.path, "Dockerfile") if self.path else ""
        if not dockerfile or not os.path.isfile(dockerfile):
            logger.debug("No Dockerfile in %s — skipping build", self.path)
            return ""

        tag = tag or f"sf-{self.project_id}:latest"
        logger.info("Building image %s from %s", tag, self.path)
        try:
            _docker("build", "-t", tag, self.path, capture=False)
            return tag
        except subprocess.CalledProcessError as e:
            logger.error("docker build failed for %s: %s", self.project_id, e)
            return ""

    def push(self, registry: str = "", tag: str = "") -> bool:
        """Push the project image to a registry.

        Args:
            registry: e.g. "registry.example.com" or "" for Docker Hub
            tag: local tag (default: sf-{project_id}:latest)
        """
        local_tag = tag or f"sf-{self.project_id}:latest"
        remote_tag = f"{registry}/{self.project_id}:latest" if registry else local_tag

        if registry:
            try:
                _docker("tag", local_tag, remote_tag)
            except subprocess.CalledProcessError as e:
                logger.error("docker tag failed: %s", e)
                return False

        logger.info("Pushing image %s", remote_tag)
        try:
            _docker("push", remote_tag, capture=False)
            return True
        except subprocess.CalledProcessError as e:
            logger.error("docker push failed for %s: %s", self.project_id, e)
            return False

    def stop(self) -> bool:
        """Stop the project container (keeps volume intact)."""
        try:
            _docker("stop", self.name, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def remove(self, force: bool = False) -> bool:
        """Remove the container (not the volume — workspace is preserved)."""
        cmd = ["rm"]
        if force:
            cmd.append("-f")
        cmd.append(self.name)
        try:
            _docker(*cmd, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def logs(self, tail: int = 100) -> str:
        """Return last N lines of container logs."""
        try:
            r = _docker("logs", "--tail", str(tail), self.name, check=False)
            return r.stdout + r.stderr
        except Exception as e:
            return str(e)

    def info(self) -> dict:
        """Return container status info dict for cockpit display."""
        st = self.status()
        return {
            "project_id": self.project_id,
            "container_name": self.name,
            "volume": self.volume,
            "image": self.image,
            "status": st,
            "running": st == "running",
        }


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def get_project_container(project_id: str, path: str = "") -> ProjectContainer:
    """Get or create a ProjectContainer instance for a project."""
    if not path:
        try:
            from .manager import get_project_store

            proj = get_project_store().get(project_id)
            if proj:
                path = proj.path or ""
        except Exception:
            pass
    return ProjectContainer(project_id, path=path)


def list_running_containers() -> list[dict]:
    """List all SF project containers currently running."""
    try:
        r = _docker(
            "ps",
            "--filter",
            "label=sf.project_id",
            "--format",
            "{{.Names}}\t{{.Status}}\t{{.Image}}",
            check=False,
        )
        containers = []
        for line in r.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                containers.append(
                    {
                        "name": parts[0],
                        "status": parts[1],
                        "image": parts[2] if len(parts) > 2 else "",
                    }
                )
        return containers
    except Exception as e:
        logger.debug("list_running_containers: %s", e)
        return []
