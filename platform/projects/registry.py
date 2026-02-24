"""Project Registry — discovers projects from SF/MF YAMLs + manual config."""

from __future__ import annotations

import os
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ProjectInfo:
    id: str
    name: str
    path: str
    factory_type: str  # "sf" | "mf" | "standalone"
    domains: list[str] = field(default_factory=list)
    description: str = ""
    yaml_path: Optional[str] = None

    @property
    def exists(self) -> bool:
        return Path(self.path).is_dir()

    @property
    def has_git(self) -> bool:
        p = Path(self.path)
        if (p / ".git").exists():
            return True
        # Check if inside a parent git repo
        try:
            import subprocess
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=self.path, capture_output=True, text=True, timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False


_PERSONAL_IDS = {"fervenza", "finary", "popinz", "psy", "yolonow", "sharelook-2"}

# Local-only projects — only loaded when SF_LOCAL=1 (dev machine)
_LOCAL_PROJECTS: list[dict] = [
    {"id": "factory", "name": "Software Factory (Self)", "path": "", "factory_type": "sf",
     "domains": ["python"], "description": "Self-improving software factory"},
    {"id": "fervenza", "name": "Fervenza IoT Platform", "path": "", "factory_type": "sf",
     "domains": ["rust", "typescript"], "description": "IoT sensor platform"},
    {"id": "finary", "name": "Finary", "path": "", "factory_type": "standalone",
     "domains": ["python", "typescript"], "description": "Personal finance tracker"},
    {"id": "logs-facteur", "name": "Logs Facteur - Support N1 La Poste", "path": "", "factory_type": "sf",
     "domains": ["rust"], "description": "Mail carrier support tool"},
    {"id": "lpd", "name": "LPD", "path": "", "factory_type": "standalone",
     "domains": ["rust"], "description": "La Poste Distribution"},
    {"id": "popinz", "name": "Popinz SaaS", "path": "", "factory_type": "sf",
     "domains": ["rust", "svelte", "swift", "kotlin"], "description": "Event discovery SaaS platform"},
    {"id": "psy", "name": "Macaron-Software PSY Platform", "path": "", "factory_type": "sf",
     "domains": ["rust", "svelte"], "description": "PSY consultation platform"},
    {"id": "sharelook", "name": "Sharelook Platform", "path": "", "factory_type": "sf",
     "domains": ["java", "angular"], "description": "Video collaboration platform"},
    {"id": "sharelook-2", "name": "Sharelook 2.0", "path": "", "factory_type": "sf",
     "domains": ["java", "angular"], "description": "Next-gen Sharelook platform"},
    {"id": "solaris", "name": "Solaris Design System (La Poste)", "path": "", "factory_type": "sf",
     "domains": ["svelte"], "description": "La Poste design system"},
    {"id": "veligo", "name": "Veligo Platform", "path": "", "factory_type": "sf",
     "domains": ["rust", "svelte"], "description": "Bike sharing platform"},
    {"id": "yolonow", "name": "YoloNow - Event Discovery Platform", "path": "", "factory_type": "sf",
     "domains": ["rust", "svelte", "swift", "kotlin"], "description": "Event discovery app"},
]

# Demo projects — realistic fictional projects for fresh/public installs
_DEMO_PROJECTS: list[dict] = [
    {"id": "greenfleet", "name": "GreenFleet — EV Fleet Management", "path": "", "factory_type": "sf",
     "domains": ["python", "typescript", "react"],
     "description": "Real-time EV fleet tracking, route optimization, and charging station management for logistics companies"},
    {"id": "mediboard", "name": "MediBoard — Hospital Dashboard", "path": "", "factory_type": "sf",
     "domains": ["java", "angular"],
     "description": "Clinical dashboard for hospital staff — patient flow, bed occupancy, lab results, and alert management"},
    {"id": "neobank-api", "name": "NeoBank API Platform", "path": "", "factory_type": "sf",
     "domains": ["rust", "typescript"],
     "description": "Core banking API — accounts, payments, KYC/AML compliance, and real-time fraud detection engine"},
    {"id": "eduspark", "name": "EduSpark — E-Learning Platform", "path": "", "factory_type": "sf",
     "domains": ["python", "svelte"],
     "description": "Adaptive learning platform with AI-powered content recommendations, progress analytics, and live classrooms"},
    {"id": "payflow", "name": "PayFlow — Payment Orchestration", "path": "", "factory_type": "sf",
     "domains": ["go", "typescript", "react"],
     "description": "Payment orchestration platform — multi-PSP routing, 3DS2 authentication, reconciliation engine, and real-time fraud scoring"},
    {"id": "dataforge", "name": "DataForge — Real-time Data Pipeline", "path": "", "factory_type": "sf",
     "domains": ["python", "rust", "typescript"],
     "description": "Enterprise data pipeline — ingestion, transformation, quality checks, and lineage tracking with sub-second latency"},
    {"id": "urbanpulse", "name": "UrbanPulse — Smart City Mobility", "path": "", "factory_type": "sf",
     "domains": ["rust", "svelte", "python"],
     "description": "Smart city mobility platform — real-time traffic flow, public transport optimization, bike/scooter fleet management, and air quality monitoring"},
]


def _is_local_dev() -> bool:
    """Detect if running on developer's local machine (not a public/demo install)."""
    return bool(os.environ.get("SF_LOCAL", ""))


class ProjectRegistry:
    """Discovers and manages all known projects."""

    def __init__(self, sf_root: Optional[str] = None, mf_root: Optional[str] = None):
        self._sf_root = sf_root or os.environ.get(
            "SF_ROOT", "/Users/sylvain/_MACARON-SOFTWARE/_SOFTWARE_FACTORY"
        )
        self._mf_root = mf_root or os.environ.get(
            "MF_ROOT", "/Users/sylvain/_MACARON-SOFTWARE/_MIGRATION_FACTORY"
        )
        self._projects: dict[str, ProjectInfo] = {}
        self._loaded = False

    def load(self) -> None:
        self._projects.clear()

        # Software Factory projects
        sf_dir = Path(self._sf_root) / "projects"
        if sf_dir.is_dir():
            for f in sorted(sf_dir.glob("*.yaml")):
                if f.name.startswith("_"):
                    continue
                try:
                    self._load_sf_yaml(f)
                except Exception:
                    pass

        # Migration Factory projects
        mf_base = Path(self._mf_root)
        mf_dir = mf_base / "projects"
        if not mf_dir.is_dir():
            mf_dir = mf_base  # MF_ROOT might directly contain yaml files
        if mf_dir.is_dir():
            for f in sorted(mf_dir.glob("*.yaml")):
                if f.name.startswith("_"):
                    continue
                try:
                    self._load_mf_yaml(f)
                except Exception:
                    pass

        # Manual additions: local projects on dev machine, demo projects on public installs
        projects_to_add = _LOCAL_PROJECTS if _is_local_dev() else _DEMO_PROJECTS
        is_azure = os.environ.get("AZURE_DEPLOY", "")
        for m in projects_to_add:
            pid = m["id"]
            if is_azure and pid in _PERSONAL_IDS:
                continue
            if pid not in self._projects:
                self._projects[pid] = ProjectInfo(**m)

        self._loaded = True

    def _load_sf_yaml(self, path: Path) -> None:
        with open(path) as fh:
            data = yaml.safe_load(fh) or {}

        # Support both flat and nested structures
        project_section = data.get("project", data)
        pid = project_section.get("project_id") or project_section.get("name") or path.stem
        if pid == "_template":
            return

        root = project_section.get("root_path", data.get("root_path", ""))
        domains_cfg = data.get("domains", {})
        domain_list = list(domains_cfg.keys()) if isinstance(domains_cfg, dict) else []
        display = project_section.get("display_name") or pid.replace("-", " ").title()

        self._projects[pid] = ProjectInfo(
            id=pid,
            name=display,
            path=root,
            factory_type="sf",
            domains=domain_list,
            description=data.get("description", ""),
            yaml_path=str(path),
        )

    def _load_mf_yaml(self, path: Path) -> None:
        with open(path) as fh:
            data = yaml.safe_load(fh) or {}

        project_section = data.get("project", data)
        pid = project_section.get("id") or project_section.get("project_id") or path.stem
        migration = data.get("migration", {})
        root = migration.get("root_path") or project_section.get("root_path", "")
        display = project_section.get("name") or pid.replace("-", " ").title()

        self._projects[pid] = ProjectInfo(
            id=pid,
            name=display,
            path=root,
            factory_type="mf",
            domains=[migration.get("framework", "unknown")],
            description=f"Migration {migration.get('from_version', '?')} → {migration.get('to_version', '?')}",
            yaml_path=str(path),
        )

    def all(self) -> list[ProjectInfo]:
        if not self._loaded:
            self.load()
        return list(self._projects.values())

    def get(self, project_id: str) -> Optional[ProjectInfo]:
        if not self._loaded:
            self.load()
        return self._projects.get(project_id)

    def ids(self) -> list[str]:
        return [p.id for p in self.all()]


_registry: Optional[ProjectRegistry] = None


def get_project_registry() -> ProjectRegistry:
    global _registry
    if _registry is None:
        _registry = ProjectRegistry()
        _registry.load()
    return _registry
