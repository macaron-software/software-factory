"""
Agent Registry - Load and manage agent roles from YAML definitions.
===================================================================
Scans platform/skills/definitions/*.yaml and legacy skills/*.md.
Provides hot-reload capability.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import yaml

from ..config import SKILLS_DIR, LEGACY_SKILLS_DIR
from ..models import (
    AgentRole, AgentLLMConfig, AgentPermissions,
    AgentCommunication, AgentTrigger,
)

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Registry of all available agent roles."""

    def __init__(self):
        self._roles: dict[str, AgentRole] = {}
        self._yaml_paths: dict[str, Path] = {}

    def load_all(self):
        """Load all role definitions from YAML files."""
        self._roles.clear()
        self._yaml_paths.clear()

        # Platform skill definitions (YAML)
        if SKILLS_DIR.exists():
            for yaml_path in sorted(SKILLS_DIR.glob("*.yaml")):
                if yaml_path.name.startswith("_"):
                    continue
                try:
                    role = self._load_yaml(yaml_path)
                    self._roles[role.id] = role
                    self._yaml_paths[role.id] = yaml_path
                except Exception as e:
                    logger.error(f"Failed to load {yaml_path.name}: {e}")

        logger.info(f"Loaded {len(self._roles)} agent roles")

    def _load_yaml(self, path: Path) -> AgentRole:
        """Parse a single YAML role definition into AgentRole."""
        with open(path) as f:
            raw = yaml.safe_load(f)

        # Parse nested configs
        llm_raw = raw.get("llm", {})
        llm = AgentLLMConfig(
            model=llm_raw.get("model", "gpt-5.1"),
            temperature=llm_raw.get("temperature", 0.7),
            max_tokens=llm_raw.get("max_tokens", 4096),
            fallback_model=llm_raw.get("fallback_model"),
        )

        perms_raw = raw.get("permissions", {})
        permissions = AgentPermissions(
            can_veto=perms_raw.get("can_veto", False),
            veto_level=perms_raw.get("veto_level", "advisory"),
            can_delegate=perms_raw.get("can_delegate", False),
            can_approve=perms_raw.get("can_approve", False),
            escalation_to=perms_raw.get("escalation_to"),
            require_human_approval_for=perms_raw.get("require_human_approval_for", []),
        )

        comm_raw = raw.get("communication", {})
        communication = AgentCommunication(
            responds_to=comm_raw.get("responds_to", []),
            can_contact=comm_raw.get("can_contact", []),
            broadcast_channels=comm_raw.get("broadcast_channels", []),
        )

        triggers = []
        for t in raw.get("triggers", []):
            if isinstance(t, dict):
                triggers.append(AgentTrigger(
                    event=t.get("event", ""),
                    action=t.get("action", ""),
                    auto=t.get("auto", False),
                ))

        persona_raw = raw.get("persona", {})

        return AgentRole(
            id=raw.get("id", path.stem),
            name=raw.get("name", path.stem.replace("_", " ").title()),
            version=raw.get("version", "1.0"),
            description=persona_raw.get("description", raw.get("description", "")),
            system_prompt=raw.get("system_prompt", ""),
            persona_traits=persona_raw.get("traits", []),
            skills=raw.get("skills", []),
            tools=raw.get("tools", []),
            llm=llm,
            permissions=permissions,
            communication=communication,
            triggers=triggers,
            constraints=raw.get("constraints", {}),
            tags=raw.get("tags", []),
        )

    def get(self, role_id: str) -> Optional[AgentRole]:
        """Get a role by ID."""
        return self._roles.get(role_id)

    def list_roles(self) -> list[AgentRole]:
        """List all available roles."""
        return list(self._roles.values())

    def list_role_ids(self) -> list[str]:
        """List all available role IDs."""
        return list(self._roles.keys())

    def reload(self, role_id: str = None):
        """Reload a specific role or all roles."""
        if role_id and role_id in self._yaml_paths:
            try:
                role = self._load_yaml(self._yaml_paths[role_id])
                self._roles[role.id] = role
                logger.info(f"Reloaded role: {role_id}")
            except Exception as e:
                logger.error(f"Failed to reload {role_id}: {e}")
        else:
            self.load_all()

    def register(self, role: AgentRole):
        """Register a role programmatically (for testing)."""
        self._roles[role.id] = role

    def __len__(self) -> int:
        return len(self._roles)

    def __contains__(self, role_id: str) -> bool:
        return role_id in self._roles


# Singleton
_registry: Optional[AgentRegistry] = None


def get_registry() -> AgentRegistry:
    """Get or create the global agent registry."""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
        _registry.load_all()
    return _registry
