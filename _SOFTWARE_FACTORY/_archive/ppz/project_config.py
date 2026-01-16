#!/usr/bin/env python3
"""
Multi-Project Configuration for RLM Chain
==========================================

This module enables the RLM chain to work across multiple projects.
Each project defines its own:
- Root path
- Domains to analyze
- Vision document (for LEAN filtering)
- Backlog location

Usage:
    from project_config import get_project, list_projects

    project = get_project("popinz")
    print(project.root_path)
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import os

@dataclass
class DomainConfig:
    """Configuration for a code domain (rust, typescript, etc.)"""
    paths: List[str]
    extensions: List[str]
    build_cmd: Optional[List[str]] = None
    test_cmd: Optional[List[str]] = None


@dataclass
class ProjectConfig:
    """Configuration for a project"""
    name: str
    root_path: Path
    domains: Dict[str, DomainConfig]
    vision_doc: str = "CLAUDE.md"  # LEAN vision document
    backlog_file: str = "backlog_tasks.json"
    deploy_backlog_file: str = "deploy_backlog.json"

    @property
    def backlog_path(self) -> Path:
        return self.root_path / "rlm" / self.backlog_file

    @property
    def deploy_backlog_path(self) -> Path:
        return self.root_path / "rlm" / self.deploy_backlog_file

    @property
    def vision_path(self) -> Path:
        return self.root_path / self.vision_doc

    def get_vision_content(self) -> str:
        """Read the vision document for LEAN filtering"""
        if self.vision_path.exists():
            return self.vision_path.read_text()[:10000]  # Max 10k chars
        return ""


# ============================================================================
# PROJECT DEFINITIONS
# ============================================================================

POPINZ_DOMAINS = {
    "rust": DomainConfig(
        paths=["popinz-v2-rust"],
        extensions=[".rs"],
        build_cmd=["cargo", "check", "--workspace"],
        test_cmd=["cargo", "test", "--workspace", "--no-run"],
    ),
    "typescript": DomainConfig(
        paths=["popinz-saas", "popinz-entities", "popinz-tasks"],
        extensions=[".ts", ".tsx"],
        build_cmd=["npm", "run", "build"],
        test_cmd=["npm", "run", "test"],
    ),
    "php": DomainConfig(
        paths=["popinz-api-php-archived"],
        extensions=[".php"],
        build_cmd=["php", "-l"],
        test_cmd=["./vendor/bin/phpunit"],
    ),
    "proto": DomainConfig(
        paths=["popinz-v2-rust/proto"],
        extensions=[".proto"],
    ),
    "sql": DomainConfig(
        paths=["docker/migrations", "popinz-v2-rust/migrations"],
        extensions=[".sql"],
    ),
    "e2e": DomainConfig(
        paths=["popinz-tests"],
        extensions=[".spec.ts"],
        test_cmd=["npx", "playwright", "test", "--list"],
    ),
    "mobile-ios": DomainConfig(
        paths=["popinz-mobile-ios"],
        extensions=[".swift"],
        build_cmd=["xcodebuild", "-scheme", "Appel", "-sdk", "iphonesimulator", "build"],
    ),
    "mobile-android": DomainConfig(
        paths=["popinz-mobile-android"],
        extensions=[".kt", ".java"],
        build_cmd=["./gradlew", "build"],
    ),
}

# All registered projects
PROJECTS: Dict[str, ProjectConfig] = {
    "popinz": ProjectConfig(
        name="popinz",
        root_path=Path("/Users/sylvain/_POPINZ/popinz-dev"),
        domains=POPINZ_DOMAINS,
        vision_doc="CLAUDE.md",
    ),
    # Add more projects here as needed
    # "autre-projet": ProjectConfig(
    #     name="autre-projet",
    #     root_path=Path("/Users/sylvain/_AUTRE/projet"),
    #     domains={...},
    #     vision_doc="README.md",
    # ),
}

# Default project (for backwards compatibility)
DEFAULT_PROJECT = "popinz"


# ============================================================================
# PUBLIC API
# ============================================================================

def get_project(name: str = None) -> ProjectConfig:
    """
    Get project configuration by name.

    Args:
        name: Project name (default: uses PPZ_PROJECT env var or DEFAULT_PROJECT)

    Returns:
        ProjectConfig for the project

    Raises:
        KeyError: If project not found
    """
    if name is None:
        name = os.environ.get("PPZ_PROJECT", DEFAULT_PROJECT)

    if name not in PROJECTS:
        available = ", ".join(PROJECTS.keys())
        raise KeyError(f"Project '{name}' not found. Available: {available}")

    return PROJECTS[name]


def list_projects() -> List[str]:
    """List all registered project names"""
    return list(PROJECTS.keys())


def register_project(config: ProjectConfig):
    """
    Register a new project configuration.

    Args:
        config: ProjectConfig to register
    """
    PROJECTS[config.name] = config


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RLM Project Configuration")
    parser.add_argument("--list", action="store_true", help="List all projects")
    parser.add_argument("--show", type=str, help="Show config for a project")

    args = parser.parse_args()

    if args.list:
        print("Registered projects:")
        for name in list_projects():
            project = get_project(name)
            print(f"  - {name}: {project.root_path}")
            print(f"    Domains: {', '.join(project.domains.keys())}")

    elif args.show:
        project = get_project(args.show)
        print(f"Project: {project.name}")
        print(f"Root: {project.root_path}")
        print(f"Vision doc: {project.vision_doc}")
        print(f"Backlog: {project.backlog_path}")
        print(f"\nDomains:")
        for name, domain in project.domains.items():
            print(f"  {name}:")
            print(f"    Paths: {domain.paths}")
            print(f"    Extensions: {domain.extensions}")
            if domain.build_cmd:
                print(f"    Build: {' '.join(domain.build_cmd)}")
            if domain.test_cmd:
                print(f"    Test: {' '.join(domain.test_cmd)}")

    else:
        parser.print_help()
