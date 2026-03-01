"""
Deploy Target — Abstract base class for all deployment drivers.

Every driver must implement:
  - deploy(workspace, mission_id, env, **kwargs) → DeployResult
  - stop(mission_id) → DeployResult
  - status(mission_id) → DeployResult
  - logs(mission_id, lines) → str
  - test_connection() → (ok: bool, message: str)
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DeployResult:
    ok: bool
    url: str = ""
    message: str = ""
    container: str = ""
    port: int = 0
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        tag = "[OK]" if self.ok else "[FAIL]"
        parts = [tag]
        if self.url:
            parts.append(f"URL: {self.url}")
        if self.message:
            parts.append(self.message)
        return "\n".join(parts)


class DeployTarget(abc.ABC):
    """Abstract base for all deploy drivers."""

    #: Short machine identifier, e.g. "docker_local", "ssh_docker", "aws_ecs"
    driver: str = ""
    #: Human-readable label shown in Settings UI
    label: str = ""
    #: Config fields required by this driver (for UI form generation)
    config_schema: list[dict] = []

    def __init__(self, name: str, config: dict | None = None):
        self.name = name
        self.config = config or {}

    @abc.abstractmethod
    async def deploy(
        self,
        workspace: str,
        mission_id: str,
        env: str = "staging",
        **kwargs: Any,
    ) -> DeployResult:
        """Build and deploy workspace. Returns DeployResult."""

    @abc.abstractmethod
    async def stop(self, mission_id: str) -> DeployResult:
        """Stop and clean up a deployed app."""

    @abc.abstractmethod
    async def status(self, mission_id: str) -> DeployResult:
        """Return current status of a deployed app."""

    @abc.abstractmethod
    async def logs(self, mission_id: str, lines: int = 50) -> str:
        """Return last N log lines."""

    @abc.abstractmethod
    async def test_connection(self) -> tuple[bool, str]:
        """
        Test that this target is reachable and configured correctly.
        Returns (ok, message).
        """
