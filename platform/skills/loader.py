"""Skills loader — loads agent role definitions from YAML files.

Extends the existing core/skills.py pattern with full Pydantic validation
and hot-reload capability for the platform's richer YAML format.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DEFINITIONS_DIR = Path(__file__).parent / "definitions"


# ---------- Sub-models for YAML structure ----------

class PersonaConfig(BaseModel):
    description: str = ""
    traits: list[str] = Field(default_factory=list)


class LLMConfig(BaseModel):
    model: str = "gpt-5.1"
    temperature: float = 0.7
    max_tokens: int = 4096
    fallback_model: str | None = None


class PermissionsConfig(BaseModel):
    can_veto: bool = False
    veto_level: str | None = None  # absolute, strong, advisory
    can_delegate: bool = False
    can_approve: bool = False
    escalation_to: str | None = None
    require_human_approval_for: list[str] = Field(default_factory=list)


class CommunicationConfig(BaseModel):
    responds_to: list[str] = Field(default_factory=list)
    can_contact: list[str] = Field(default_factory=list)
    broadcast_channels: list[str] = Field(default_factory=list)


class TriggerConfig(BaseModel):
    event: str
    action: str
    auto: bool = False


class ConstraintsConfig(BaseModel):
    max_concurrent_tasks: int = 3
    max_tokens_per_day: int = 200_000


class SkillDefinition(BaseModel):
    """Full agent role definition loaded from YAML."""

    id: str
    name: str
    version: str = "1.0"
    persona: PersonaConfig = Field(default_factory=PersonaConfig)
    system_prompt: str = ""
    skills: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    permissions: PermissionsConfig = Field(default_factory=PermissionsConfig)
    communication: CommunicationConfig = Field(default_factory=CommunicationConfig)
    triggers: list[TriggerConfig] = Field(default_factory=list)
    constraints: ConstraintsConfig = Field(default_factory=ConstraintsConfig)
    tags: list[str] = Field(default_factory=list)


# ---------- Loader ----------

class SkillLoader:
    """Loads and caches agent skill definitions from YAML files."""

    def __init__(self, definitions_dir: Path | None = None):
        self._dir = definitions_dir or DEFINITIONS_DIR
        self._cache: dict[str, SkillDefinition] = {}
        self._mtimes: dict[str, float] = {}

    # -- public API --

    def load_all(self) -> dict[str, SkillDefinition]:
        """Load all YAML definitions (skipping _template)."""
        if not self._dir.exists():
            logger.warning("Definitions dir not found: %s", self._dir)
            return {}
        for path in sorted(self._dir.glob("*.yaml")):
            if path.stem.startswith("_"):
                continue
            self._load_one(path)
        return dict(self._cache)

    def get(self, role_id: str) -> SkillDefinition | None:
        """Get a role definition by ID, auto-loading if needed."""
        if not self._cache:
            self.load_all()
        return self._cache.get(role_id)

    def list_roles(self) -> list[str]:
        """List all available role IDs."""
        if not self._cache:
            self.load_all()
        return sorted(self._cache.keys())

    def reload(self) -> int:
        """Hot-reload changed YAML files. Returns count of reloaded."""
        count = 0
        for path in self._dir.glob("*.yaml"):
            if path.stem.startswith("_"):
                continue
            mtime = path.stat().st_mtime
            if path.name not in self._mtimes or self._mtimes[path.name] < mtime:
                self._load_one(path)
                count += 1
        return count

    def load_custom(self, yaml_content: str) -> SkillDefinition:
        """Load a role definition from raw YAML string."""
        raw = yaml.safe_load(yaml_content)
        return self._parse(raw, source="<custom>")

    # -- internal --

    def _load_one(self, path: Path) -> None:
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            defn = self._parse(raw, source=str(path))
            self._cache[defn.id] = defn
            self._mtimes[path.name] = path.stat().st_mtime
            logger.debug("Loaded skill: %s from %s", defn.id, path.name)
        except Exception:
            logger.exception("Failed to load skill from %s", path)

    def _parse(self, raw: dict[str, Any], source: str = "") -> SkillDefinition:
        # Normalize triggers from list of dicts
        if "triggers" in raw and isinstance(raw["triggers"], list):
            raw["triggers"] = [
                t if isinstance(t, dict) else {"event": str(t), "action": "handle", "auto": False}
                for t in raw["triggers"]
            ]
        return SkillDefinition.model_validate(raw)


# ---------- Singleton ----------

_loader: SkillLoader | None = None


def get_skill_loader() -> SkillLoader:
    global _loader
    if _loader is None:
        _loader = SkillLoader()
        _loader.load_all()
    return _loader
