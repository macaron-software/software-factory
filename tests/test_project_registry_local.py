"""Tests for local-only project registry loading."""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def test_registry_loads_private_local_projects(tmp_path, monkeypatch):
    from platform.projects.registry import ProjectRegistry

    private_dir = tmp_path / "local-projects"
    project_root = tmp_path / "psy-local"
    private_dir.mkdir()
    project_root.mkdir()

    (private_dir / "psy.yaml").write_text(
        f"""
project:
  name: psy
  display_name: "PSY"
  root_path: {project_root}

domains:
  rust:
    paths: [backend/]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("SF_LOCAL", "1")
    monkeypatch.setenv("SF_LOCAL_PROJECTS_DIR", str(private_dir))

    registry = ProjectRegistry(sf_root=str(tmp_path / "missing-sf"))
    registry.load()

    project = registry.get("psy")
    assert project is not None
    assert project.name == "PSY"
    assert project.path == str(project_root)
    assert "rust" in project.domains
