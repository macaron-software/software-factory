"""Domain Context — groups projects by architectural domain and injects tech constraints into agents.

A domain defines the technical environment a project lives in:
  - stack (language, framework, DB, infra)
  - design system
  - compliance rules
  - CI/CD platform
  - MCP tools to activate
  - Confluence space for live spec lookup

Domain files live in: projects/domains/<id>.yaml
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

# Path to domain YAML files (relative to repo root)
_DOMAINS_DIR = Path(__file__).parent.parent.parent / "projects" / "domains"


@dataclass
class DomainStack:
    backend: str = ""
    frontend: str = ""
    database: str = ""
    database_forbidden: list[str] = field(default_factory=list)
    cache: str = ""
    infra: str = ""
    ci: str = ""
    auth: str = ""
    extra: list[str] = field(default_factory=list)


@dataclass
class Domain:
    id: str
    name: str
    env: str = "any"           # "demo" | "prod" | "any"
    description: str = ""
    stack: DomainStack = field(default_factory=DomainStack)
    design_system: str = ""    # e.g. "Solaris (La Poste)"
    compliance: list[str] = field(default_factory=list)  # e.g. ["RGPD", "RGAA 4.1"]
    mcp_tools: list[str] = field(default_factory=list)   # e.g. ["mcp-solaris"]
    confluence_space: str = "" # e.g. "IAN" — for live spec lookup via LRM
    conventions: str = ""      # free-text injected verbatim into agent system prompt
    color: str = "#6B7280"     # UI badge color (hex)
    extends: str = ""          # parent domain id to inherit from

    def to_context_string(self) -> str:
        """Build the domain context string injected into agent system prompts."""
        lines = [f"## Contexte Domaine — {self.name}"]
        if self.description:
            lines.append(self.description)
        lines.append("")

        s = self.stack
        if any([s.backend, s.frontend, s.database, s.cache, s.infra, s.ci, s.auth]):
            lines.append("### Stack obligatoire")
            if s.backend:
                lines.append(f"- **Backend :** {s.backend}")
            if s.frontend:
                lines.append(f"- **Frontend :** {s.frontend}")
            if s.database:
                lines.append(f"- **Base de données :** {s.database}")
            if s.database_forbidden:
                lines.append(f"- **BDD interdites :** {', '.join(s.database_forbidden)}")
            if s.cache:
                lines.append(f"- **Cache :** {s.cache}")
            if s.infra:
                lines.append(f"- **Infra :** {s.infra}")
            if s.ci:
                lines.append(f"- **CI/CD :** {s.ci}")
            if s.auth:
                lines.append(f"- **Auth :** {s.auth}")
            if s.extra:
                for e in s.extra:
                    lines.append(f"- {e}")
            lines.append("")

        if self.design_system:
            lines.append(f"### Design System\n{self.design_system}\n")

        if self.compliance:
            lines.append("### Conformité obligatoire")
            for c in self.compliance:
                lines.append(f"- {c}")
            lines.append("")

        if self.conventions:
            lines.append(f"### Conventions\n{self.conventions}\n")

        return "\n".join(lines)


# ── Cache ────────────────────────────────────────────────────────────────────

_cache: dict[str, Domain] = {}


def load_domain(domain_id: str) -> Optional[Domain]:
    """Load a domain by ID from projects/domains/<id>.yaml. Cached."""
    if not domain_id:
        return None
    if domain_id in _cache:
        return _cache[domain_id]

    yaml_path = _DOMAINS_DIR / f"{domain_id}.yaml"
    if not yaml_path.exists():
        logger.debug("[Domain] No YAML for domain '%s' at %s", domain_id, yaml_path)
        return None

    try:
        with open(yaml_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning("[Domain] Failed to load %s: %s", yaml_path, e)
        return None

    # Resolve inheritance
    base: Optional[Domain] = None
    if raw.get("extends"):
        base = load_domain(raw["extends"])

    stack_raw = raw.get("stack", {})
    stack = DomainStack(
        backend=stack_raw.get("backend", base.stack.backend if base else ""),
        frontend=stack_raw.get("frontend", base.stack.frontend if base else ""),
        database=stack_raw.get("database", base.stack.database if base else ""),
        database_forbidden=stack_raw.get("database_forbidden", base.stack.database_forbidden if base else []),
        cache=stack_raw.get("cache", base.stack.cache if base else ""),
        infra=stack_raw.get("infra", base.stack.infra if base else ""),
        ci=stack_raw.get("ci", base.stack.ci if base else ""),
        auth=stack_raw.get("auth", base.stack.auth if base else ""),
        extra=stack_raw.get("extra", base.stack.extra if base else []),
    )

    domain = Domain(
        id=domain_id,
        name=raw.get("name", domain_id),
        env=raw.get("env", base.env if base else "any"),
        description=raw.get("description", base.description if base else ""),
        stack=stack,
        design_system=raw.get("design_system", base.design_system if base else ""),
        compliance=raw.get("compliance", base.compliance if base else []),
        mcp_tools=raw.get("mcp_tools", base.mcp_tools if base else []),
        confluence_space=raw.get("confluence_space", base.confluence_space if base else ""),
        conventions=raw.get("conventions", base.conventions if base else ""),
        color=raw.get("color", base.color if base else "#6B7280"),
        extends=raw.get("extends", ""),
    )

    _cache[domain_id] = domain
    logger.info("[Domain] Loaded domain '%s' (%s)", domain_id, domain.name)
    return domain


def invalidate_domain_cache(domain_id: str | None = None):
    """Clear domain cache (all or specific id)."""
    if domain_id:
        _cache.pop(domain_id, None)
    else:
        _cache.clear()


def list_domains() -> list[Domain]:
    """List all available domains from the domains directory."""
    if not _DOMAINS_DIR.exists():
        return []
    domains = []
    for p in sorted(_DOMAINS_DIR.glob("*.yaml")):
        if p.stem.startswith("_"):
            continue
        d = load_domain(p.stem)
        if d:
            domains.append(d)
    return domains
