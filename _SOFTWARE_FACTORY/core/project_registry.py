#!/usr/bin/env python3
"""
Project Registry - YAML-based configuration for Software Factory
================================================================
Loads and validates project configurations from YAML files.

Usage:
    from core.project_registry import get_project, list_projects

    project = get_project("ppz")
    print(project.root_path)
    print(project.domains["rust"].build_cmd)
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

try:
    import yaml
except ImportError:
    yaml = None

try:
    from pydantic import BaseModel, Field, validator
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    BaseModel = object

# Directories
FACTORY_DIR = Path(__file__).parent.parent
PROJECTS_DIR = FACTORY_DIR / "projects"
CONFIG_DIR = Path.home() / ".config" / "factory"


# ============================================================================
# CONFIGURATION MODELS (Pydantic if available, else dataclasses)
# ============================================================================

if PYDANTIC_AVAILABLE:
    class DomainConfig(BaseModel):
        """Domain configuration (rust, typescript, etc.)"""
        paths: List[str]
        extensions: List[str]
        build_cmd: Optional[str] = None
        test_cmd: Optional[str] = None
        lint_cmd: Optional[str] = None

    class DeployConfig(BaseModel):
        """Deployment configuration"""
        strategy: str = "validation-only"  # blue-green | canary | validation-only
        auto_prod: bool = False
        validation_cmd: Optional[str] = None
        rollback_on_fail: bool = True
        gate_approval: bool = False
        staging: Optional[Dict[str, str]] = None  # url, health
        prod: Optional[Dict[str, str]] = None

    class FractalConfig(BaseModel):
        """FRACTAL decomposition thresholds"""
        max_files: int = 5
        max_loc: int = 400
        max_items: int = 10
        max_depth: int = 3

    class AdversarialPattern(BaseModel):
        """Custom adversarial pattern"""
        pattern: str
        score: int
        message: str
        max_occurrences: Optional[int] = None
        required: bool = False

    class AdversarialConfig(BaseModel):
        """Adversarial gate configuration"""
        threshold: int = 5
        core_patterns: bool = True
        custom_patterns: List[AdversarialPattern] = Field(default_factory=list)

    class TenantConfig(BaseModel):
        """Multi-tenant configuration"""
        name: str
        staging_url: Optional[str] = None
        prod_url: Optional[str] = None

    class MCPConfig(BaseModel):
        """MCP server configuration"""
        server: str
        tools: List[str] = Field(default_factory=list)

    class AOComplianceConfig(BaseModel):
        """AO compliance configuration (Veligo)"""
        enabled: bool = False
        refs_file: Optional[str] = None

    class BrainConfig(BaseModel):
        """Brain phase rotation configuration"""
        current_phase: str = "features"  # features | fixes | refactor
        phase_gate: str = "deployed"  # Status required to move to next phase
        auto_rotate: bool = True  # Auto-switch phase when all tasks deployed

    class ProjectInfo(BaseModel):
        """Project metadata"""
        name: str
        display_name: Optional[str] = None
        root_path: str
        vision_doc: str = "CLAUDE.md"

    class ProjectConfigModel(BaseModel):
        """Full project configuration"""
        project: ProjectInfo
        domains: Dict[str, DomainConfig]
        deploy: DeployConfig = Field(default_factory=DeployConfig)
        fractal: FractalConfig = Field(default_factory=FractalConfig)
        adversarial: AdversarialConfig = Field(default_factory=AdversarialConfig)
        tenants: List[TenantConfig] = Field(default_factory=list)
        mcp: Dict[str, MCPConfig] = Field(default_factory=dict)
        ao_compliance: AOComplianceConfig = Field(default_factory=AOComplianceConfig)
        brain: BrainConfig = Field(default_factory=BrainConfig)
        analyzers: List[str] = Field(default_factory=list)

else:
    # Fallback to simple dicts if pydantic not available
    @dataclass
    class DomainConfig:
        paths: List[str]
        extensions: List[str]
        build_cmd: Optional[str] = None
        test_cmd: Optional[str] = None
        lint_cmd: Optional[str] = None


@dataclass
class ProjectConfig:
    """Loaded and validated project configuration"""
    id: str
    name: str
    display_name: str
    root_path: Path
    vision_doc: str
    domains: Dict[str, Any]
    deploy: Dict[str, Any]
    fractal: Dict[str, Any]
    adversarial: Dict[str, Any]
    tenants: List[Dict[str, Any]]
    mcp: Dict[str, Any]
    ao_compliance: Dict[str, Any]
    brain: Dict[str, Any] = None  # Brain phase rotation config
    analyzers: List[str] = field(default_factory=list)
    config_path: Path = None
    raw_config: Dict[str, Any] = None  # Raw YAML config for dynamic access
    cli: Dict[str, Any] = None  # Project-specific CLI commands
    figma: Dict[str, Any] = None  # Figma MCP integration config
    env: Dict[str, str] = None  # Project-specific environment variables
    integrator: Dict[str, Any] = None  # Cross-layer integration config

    @property
    def vision_path(self) -> Path:
        return self.root_path / self.vision_doc

    def get_vision_content(self) -> str:
        """Read vision document for LEAN filtering"""
        if self.vision_path.exists():
            return self.vision_path.read_text()[:20000]
        return ""

    def get_domain(self, name: str) -> Optional[Dict]:
        """Get domain configuration"""
        return self.domains.get(name)

    def is_multi_tenant(self) -> bool:
        """Check if project is multi-tenant"""
        return len(self.tenants) > 0

    # ==================== BRAIN PHASE ROTATION ====================

    PHASE_ORDER = ["features", "fixes", "refactor"]
    PHASE_MODE_MAP = {
        "features": "vision",
        "fixes": "fix",
        "refactor": "refactor"
    }

    def get_brain_phase(self) -> str:
        """Get current brain phase"""
        if self.brain:
            return self.brain.get("current_phase", "features")
        return "features"

    def get_brain_mode(self) -> str:
        """Get brain mode for current phase"""
        phase = self.get_brain_phase()
        return self.PHASE_MODE_MAP.get(phase, "vision")

    def get_next_phase(self) -> str:
        """Get the next phase in rotation"""
        current = self.get_brain_phase()
        try:
            idx = self.PHASE_ORDER.index(current)
            return self.PHASE_ORDER[(idx + 1) % len(self.PHASE_ORDER)]
        except ValueError:
            return self.PHASE_ORDER[0]

    def is_auto_rotate_enabled(self) -> bool:
        """Check if auto-rotation is enabled"""
        if self.brain:
            return self.brain.get("auto_rotate", True)
        return True

    def set_brain_phase(self, phase: str) -> bool:
        """
        Update current brain phase and save to YAML.

        Returns True if successful, False otherwise.
        """
        if phase not in self.PHASE_ORDER:
            return False

        if not self.config_path or not self.config_path.exists():
            return False

        try:
            # Read current YAML
            with open(self.config_path, 'r') as f:
                content = f.read()
                raw = yaml.safe_load(content)

            # Update brain config
            if "brain" not in raw:
                raw["brain"] = {}
            raw["brain"]["current_phase"] = phase

            # Write back with preserved formatting (best effort)
            with open(self.config_path, 'w') as f:
                yaml.dump(raw, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

            # Update local state
            if self.brain is None:
                self.brain = {}
            self.brain["current_phase"] = phase

            return True
        except Exception as e:
            print(f"[BRAIN] Failed to save phase: {e}")
            return False

    # ==================== CLI COMMANDS ====================

    def get_cli_binary(self) -> str:
        """Get the CLI binary name for this project"""
        if self.cli:
            return self.cli.get("binary", self.name)
        return self.name

    def get_env(self) -> Dict[str, str]:
        """
        Get project-specific environment variables.

        Supports variable expansion: ${VAR} or $VAR
        Returns: Dict with resolved env vars
        """
        if not self.env:
            return {}

        import re
        result = {}
        for key, value in self.env.items():
            if isinstance(value, str):
                # Expand ${VAR} or $VAR patterns
                def expand_var(match):
                    var_name = match.group(1) or match.group(2)
                    return os.environ.get(var_name, match.group(0))
                expanded = re.sub(r'\$\{([^}]+)\}|\$([A-Z_][A-Z0-9_]*)', expand_var, value)
                result[key] = expanded
            else:
                result[key] = str(value)
        return result

    def get_build_cmd(self, domain: str = None) -> str:
        """Get build command for domain or all"""
        # PRIORITY 1: cli section (project CLI is preferred)
        if self.cli and "build" in self.cli:
            build_cmds = self.cli["build"]
            if domain and domain in build_cmds:
                return build_cmds[domain]
            if "all" in build_cmds:
                return build_cmds["all"]
        # PRIORITY 2: domain-specific build_cmd in domains section (legacy)
        if domain:
            domain_cfg = self.get_domain(domain)
            if domain_cfg and domain_cfg.get("build_cmd"):
                return domain_cfg["build_cmd"]
        # SAFE FALLBACK: no-op instead of broken CLI command
        return "echo 'No build command configured for this domain'"

    def get_test_cmd(self, domain: str = None) -> str:
        """Get test command for domain or all"""
        # PRIORITY 1: cli section (project CLI is preferred)
        if self.cli and "test" in self.cli:
            test_cmds = self.cli["test"]
            if domain and domain in test_cmds:
                return test_cmds[domain]
            if "all" in test_cmds:
                return test_cmds["all"]
        # PRIORITY 2: domain-specific test_cmd in domains section (legacy)
        if domain:
            domain_cfg = self.get_domain(domain)
            if domain_cfg and domain_cfg.get("test_cmd"):
                return domain_cfg["test_cmd"]
        # SAFE FALLBACK: no-op instead of broken CLI command
        return "echo 'No test command configured for this domain'"

    def get_lint_cmd(self, domain: str = None) -> str:
        """Get lint command for domain or all"""
        # PRIORITY 1: cli section (project CLI is preferred)
        if self.cli and "lint" in self.cli:
            lint_cmds = self.cli["lint"]
            if domain and domain in lint_cmds:
                return lint_cmds[domain]
            if "all" in lint_cmds:
                return lint_cmds["all"]
        # PRIORITY 2: domain-specific lint_cmd in domains section (legacy)
        if domain:
            domain_cfg = self.get_domain(domain)
            if domain_cfg and domain_cfg.get("lint_cmd"):
                return domain_cfg["lint_cmd"]
        # SAFE FALLBACK: no-op instead of broken CLI command
        return "echo 'No lint command configured for this domain'"

    def get_deploy_cmd(self, env: str, tenant: str = None) -> str:
        """
        Get deploy command for environment.

        Args:
            env: staging | prod | rollback
            tenant: For multi-tenant projects, specify tenant name
        """
        if self.cli and "deploy" in self.cli:
            deploy_cmds = self.cli["deploy"]
            cmd = deploy_cmds.get(env, f"{self.get_cli_binary()} deploy {env}")
            # Replace {tenant} placeholder if provided
            if tenant and "{tenant}" in cmd:
                cmd = cmd.replace("{tenant}", tenant)
            return cmd
        return f"{self.get_cli_binary()} deploy {env}"

    def get_e2e_cmd(self, test_type: str = "journeys", tenant: str = None) -> str:
        """
        Get E2E test command.

        Args:
            test_type: smoke | journeys | rbac
            tenant: For multi-tenant projects
        """
        if self.cli and "e2e" in self.cli:
            e2e_cmds = self.cli["e2e"]
            cmd = e2e_cmds.get(test_type, f"{self.get_cli_binary()} test e2e")
            # Replace {tenant} placeholder if provided
            if tenant and "{tenant}" in cmd:
                cmd = cmd.replace("{tenant}", tenant)
            return cmd
        return f"{self.get_cli_binary()} test e2e"

    def get_validate_cmd(self, what: str = "all") -> str:
        """Get validation command (for validation-only projects like Solaris)"""
        if self.cli and "validate" in self.cli:
            validate_cmds = self.cli["validate"]
            return validate_cmds.get(what, f"{self.get_cli_binary()} validate")
        return f"{self.get_cli_binary()} validate"

    def get_status_cmd(self, tenant: str = None) -> str:
        """Get status command"""
        if self.cli:
            if tenant and "status_tenant" in self.cli:
                return self.cli["status_tenant"].replace("{tenant}", tenant)
            return self.cli.get("status", f"{self.get_cli_binary()} status")
        return f"{self.get_cli_binary()} status"


# ============================================================================
# REGISTRY
# ============================================================================

_projects_cache: Dict[str, ProjectConfig] = {}


def _load_yaml(path: Path) -> Dict:
    """Load YAML file"""
    if yaml is None:
        raise ImportError("PyYAML is required. Install with: pip install pyyaml")

    with open(path) as f:
        return yaml.safe_load(f)


def _parse_project(config_path: Path) -> ProjectConfig:
    """Parse a project YAML file into ProjectConfig"""
    raw = _load_yaml(config_path)

    # Extract project info
    project_info = raw.get("project", {})
    project_id = config_path.stem  # Use filename without extension

    return ProjectConfig(
        id=project_id,
        name=project_info.get("name", project_id),
        display_name=project_info.get("display_name", project_info.get("name", project_id)),
        root_path=Path(project_info.get("root_path", ".")),
        vision_doc=project_info.get("vision_doc", "CLAUDE.md"),
        domains=raw.get("domains", {}),
        deploy=raw.get("deploy", {
            "strategy": "validation-only",
            "auto_prod": False
        }),
        fractal=raw.get("fractal", {
            "max_files": 5,
            "max_loc": 400,
            "max_items": 10,
            "max_depth": 3
        }),
        adversarial=raw.get("adversarial", {
            "threshold": 5,
            "core_patterns": True,
            "custom_patterns": []
        }),
        tenants=raw.get("tenants", []),
        mcp=raw.get("mcp", {}),
        ao_compliance=raw.get("ao_compliance", {"enabled": False}),
        brain=raw.get("brain", {
            "current_phase": "features",
            "phase_gate": "deployed",
            "auto_rotate": True
        }),
        analyzers=raw.get("analyzers", []),
        config_path=config_path,
        raw_config=raw,  # Full raw YAML for dynamic access
        cli=raw.get("cli"),  # Project-specific CLI commands
        figma=raw.get("figma", {"enabled": False}),  # Figma MCP integration
        env=raw.get("env", {}),  # Project-specific environment variables
        integrator=raw.get("integrator", {"enabled": False}),  # Cross-layer integration
    )


def _discover_projects() -> Dict[str, Path]:
    """Discover all project YAML files"""
    projects = {}

    if PROJECTS_DIR.exists():
        for yaml_file in PROJECTS_DIR.glob("*.yaml"):
            if not yaml_file.name.startswith("_"):  # Skip templates
                project_id = yaml_file.stem
                projects[project_id] = yaml_file

    return projects


def get_project(name: str = None) -> ProjectConfig:
    """
    Get project configuration by name.

    Args:
        name: Project name (default: FACTORY_PROJECT env var or first available)

    Returns:
        ProjectConfig

    Raises:
        KeyError: If project not found
    """
    if name is None:
        name = os.environ.get("FACTORY_PROJECT")

    # Check cache
    if name and name in _projects_cache:
        return _projects_cache[name]

    # Discover available projects
    available = _discover_projects()

    if not available:
        raise KeyError("No projects found in projects/ directory")

    # If no name specified, use first available
    if name is None:
        name = list(available.keys())[0]

    if name not in available:
        # Try to find by project.name instead of filename
        for proj_id, proj_path in available.items():
            try:
                with open(proj_path, 'r') as f:
                    raw = yaml.safe_load(f) or {}
                    proj_name = raw.get("project", {}).get("name", "")
                    if proj_name == name:
                        name = proj_id  # Use the ID, not the name
                        break
            except:
                pass
        else:
            raise KeyError(
                f"Project '{name}' not found. Available: {', '.join(available.keys())}"
            )

    # Load and cache
    config = _parse_project(available[name])
    _projects_cache[name] = config

    return config


def list_projects() -> List[str]:
    """List all available project names"""
    return list(_discover_projects().keys())


def get_all_projects() -> Dict[str, ProjectConfig]:
    """Load and return all projects"""
    available = _discover_projects()
    for name, path in available.items():
        if name not in _projects_cache:
            _projects_cache[name] = _parse_project(path)
    return _projects_cache.copy()


def reload_project(name: str) -> ProjectConfig:
    """Force reload a project from disk"""
    if name in _projects_cache:
        del _projects_cache[name]
    return get_project(name)


def clear_cache():
    """Clear the project cache"""
    _projects_cache.clear()


# ============================================================================
# LLM CONFIG
# ============================================================================

def get_llm_config() -> Dict:
    """
    Load LLM configuration from ~/.config/factory/llm.yaml

    Returns dict with providers and defaults.
    """
    llm_path = CONFIG_DIR / "llm.yaml"

    if not llm_path.exists():
        # Return sensible defaults
        return {
            "providers": {
                "anthropic": {
                    "models": {"opus": "claude-opus-4-5-20251101"}
                },
                "minimax": {
                    "base_url": "https://api.minimax.io/anthropic/v1",
                    "models": {"m2.1": "MiniMax-M2.1"}
                },
                "local": {
                    "base_url": "http://localhost:8002/v1",
                    "models": {"qwen": "qwen3-30b-a3b"}
                }
            },
            "defaults": {
                "brain": "anthropic/opus",
                "wiggum": "minimax/m2.1",
                "fallback_chain": ["minimax/m2.1", "local/qwen"]
            }
        }

    return _load_yaml(llm_path)


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Software Factory Project Registry")
    parser.add_argument("--list", action="store_true", help="List all projects")
    parser.add_argument("--show", type=str, help="Show config for a project")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.list:
        projects = list_projects()
        if args.json:
            print(json.dumps(projects))
        else:
            print("Available projects:")
            for name in projects:
                try:
                    p = get_project(name)
                    print(f"  {name}: {p.root_path}")
                    print(f"    Domains: {', '.join(p.domains.keys())}")
                    print(f"    Deploy: {p.deploy.get('strategy', 'unknown')}")
                except Exception as e:
                    print(f"  {name}: ERROR - {e}")

    elif args.show:
        try:
            p = get_project(args.show)
            if args.json:
                print(json.dumps({
                    "id": p.id,
                    "name": p.name,
                    "root_path": str(p.root_path),
                    "domains": p.domains,
                    "deploy": p.deploy,
                    "fractal": p.fractal,
                    "adversarial": p.adversarial,
                    "analyzers": p.analyzers,
                }, indent=2))
            else:
                print(f"Project: {p.name} ({p.display_name})")
                print(f"Root: {p.root_path}")
                print(f"Config: {p.config_path}")
                print(f"Vision: {p.vision_doc}")
                print(f"\nDomains:")
                for name, domain in p.domains.items():
                    print(f"  {name}:")
                    print(f"    Paths: {domain.get('paths', [])}")
                    print(f"    Extensions: {domain.get('extensions', [])}")
                    if domain.get('build_cmd'):
                        print(f"    Build: {domain['build_cmd']}")
                    if domain.get('test_cmd'):
                        print(f"    Test: {domain['test_cmd']}")
                print(f"\nDeploy: {p.deploy.get('strategy', 'unknown')}")
                print(f"Analyzers: {', '.join(p.analyzers)}")
                if p.is_multi_tenant():
                    print(f"\nTenants: {', '.join(t['name'] for t in p.tenants)}")
        except Exception as e:
            print(f"Error: {e}")

    else:
        parser.print_help()
