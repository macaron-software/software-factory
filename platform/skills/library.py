"""Skills library — scans local SF skills (.md) + YAML role definitions + GitHub repos."""
from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from ..config import SKILLS_DIR, LEGACY_SKILLS_DIR, DATA_DIR
from ..db.migrations import get_db

logger = logging.getLogger(__name__)

# GitHub skills cache directory
GITHUB_SKILLS_DIR = DATA_DIR / "github_skills"

# Default GitHub repos to pull skills from (owner/repo + optional path)
DEFAULT_GITHUB_SOURCES = [
    {"repo": "anthropics/claude-plugins-official", "path": "plugins", "branch": "main", "label": "Anthropic Official Plugins (code-review, frontend-design, security…)"},
    {"repo": "sickn33/antigravity-awesome-skills", "path": "skills", "branch": "main", "label": "Antigravity 800+ Skills (architect, testing, devops, security…)"},
    {"repo": "dontriskit/awesome-ai-system-prompts", "path": "", "branch": "main", "label": "AI System Prompts (Claude, Cursor, v0, Devin, Manus…)"},
    {"repo": "danielmiessler/fabric", "path": "data/patterns", "branch": "main", "label": "Fabric Patterns (extract_wisdom, analyze_code, summarize…)"},
]


@dataclass
class SkillInfo:
    """Unified skill/role descriptor."""
    id: str = ""
    name: str = ""
    description: str = ""
    content: str = ""
    source: str = ""          # "local-md" | "local-yaml" | "github"
    source_url: str = ""      # GitHub URL or file path
    repo: str = ""            # e.g. "make-roro/skills"
    tags: list[str] = field(default_factory=list)
    file_path: str = ""
    updated_at: str = ""
    category: str = ""        # development|testing|security|design|ops|management
    triggers: list[str] = field(default_factory=list)  # when to activate


# ── Frontmatter parser for .md files ────────────────────────────

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_md_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter from markdown text."""
    m = _FM_RE.match(text)
    if m:
        try:
            return yaml.safe_load(m.group(1)) or {}
        except Exception:
            pass
    return {}


def _first_heading(text: str) -> str:
    """Return the first # heading from markdown."""
    for line in text.splitlines():
        if line.startswith("# "):
            return line.lstrip("# ").strip()
    return ""


def _first_paragraph(text: str) -> str:
    """Return the first non-heading paragraph after frontmatter."""
    body = _FM_RE.sub("", text)
    para = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            if para:
                break
            continue
        if not stripped:
            if para:
                break
            continue
        para.append(stripped)
    return " ".join(para)


# ── Library ──────────────────────────────────────────────────────

class SkillLibrary:
    """Scans and indexes SF skills (.md), role definitions (.yaml), and GitHub repos."""

    def __init__(self, md_dir: Path | None = None, yaml_dir: Path | None = None):
        self._md_dir = md_dir or LEGACY_SKILLS_DIR
        self._yaml_dir = yaml_dir or SKILLS_DIR
        self._cache: dict[str, SkillInfo] = {}
        self._github_sources: list[dict] = list(DEFAULT_GITHUB_SOURCES)
        self._load_github_sources()

    def _load_github_sources(self):
        """Load saved GitHub sources from DB."""
        try:
            db = get_db()
            rows = db.execute(
                "SELECT repo, path, branch FROM skill_github_sources"
            ).fetchall()
            for r in rows:
                src = {"repo": r[0], "path": r[1] or "", "branch": r[2] or "main"}
                if not any(s["repo"] == src["repo"] for s in self._github_sources):
                    self._github_sources.append(src)
            db.close()
        except Exception:
            pass  # Table may not exist yet

    # -- public API --

    def scan_all(self) -> list[SkillInfo]:
        """Scan all sources and return unified sorted list."""
        self._cache.clear()
        self.scan_md_skills()
        self.scan_yaml_roles()
        self.scan_github_cache()
        return sorted(self._cache.values(), key=lambda s: (s.source, s.name.lower()))

    def scan_md_skills(self) -> list[SkillInfo]:
        """Read all .md files from the SF skills directory."""
        results = []
        if not self._md_dir.exists():
            logger.warning("MD skills dir not found: %s", self._md_dir)
            return results
        for path in sorted(self._md_dir.glob("*.md")):
            try:
                text = path.read_text(encoding="utf-8")
                fm = _parse_md_frontmatter(text)
                skill_id = path.stem
                heading = _first_heading(text)
                meta = fm.get("metadata", {}) if isinstance(fm.get("metadata"), dict) else {}
                cat = meta.get("category", "")
                trigs = meta.get("triggers", [])
                tags = fm.get("tags", [])
                if cat and cat not in tags:
                    tags = [cat] + tags
                info = SkillInfo(
                    id=skill_id,
                    name=fm.get("name", heading or skill_id),
                    description=fm.get("description", _first_paragraph(text)),
                    content=text,
                    source="local-md",
                    source_url=str(path),
                    tags=tags,
                    file_path=str(path),
                    category=cat,
                    triggers=trigs,
                )
                self._cache[info.id] = info
                results.append(info)
            except Exception:
                logger.exception("Failed to read skill: %s", path)
        return results

    def scan_yaml_roles(self) -> list[SkillInfo]:
        """Read all .yaml files from platform/skills/definitions (skip _template)."""
        results = []
        if not self._yaml_dir.exists():
            logger.warning("YAML roles dir not found: %s", self._yaml_dir)
            return results
        for path in sorted(self._yaml_dir.glob("*.yaml")):
            if path.stem.startswith("_"):
                continue
            try:
                raw = yaml.safe_load(path.read_text(encoding="utf-8"))
                if not raw or not isinstance(raw, dict):
                    continue
                role_id = raw.get("id", path.stem)
                info = SkillInfo(
                    id=role_id,
                    name=raw.get("name", role_id),
                    description=raw.get("persona", {}).get("description", "").strip(),
                    content=raw.get("system_prompt", ""),
                    source="local-yaml",
                    source_url=str(path),
                    tags=raw.get("skills", []) + raw.get("tags", []),
                    file_path=str(path),
                )
                self._cache[info.id] = info
                results.append(info)
            except Exception:
                logger.exception("Failed to read role: %s", path)
        return results

    def scan_github_cache(self) -> list[SkillInfo]:
        """Read skills previously fetched from GitHub (cached on disk)."""
        results = []
        if not GITHUB_SKILLS_DIR.exists():
            return results
        for repo_dir in sorted(GITHUB_SKILLS_DIR.iterdir()):
            if not repo_dir.is_dir():
                continue
            repo_name = repo_dir.name.replace("__", "/")
            meta_file = repo_dir / "_meta.json"
            meta = {}
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text())
                except Exception:
                    pass
            for path in sorted(repo_dir.glob("*.md")):
                if path.stem.startswith("_"):
                    continue
                try:
                    text = path.read_text(encoding="utf-8")
                    fm = _parse_md_frontmatter(text)
                    skill_id = f"gh-{repo_dir.name}-{path.stem}"
                    heading = _first_heading(text)
                    info = SkillInfo(
                        id=skill_id,
                        name=fm.get("name", heading or path.stem),
                        description=fm.get("description", _first_paragraph(text)),
                        content=text,
                        source="github",
                        source_url=f"https://github.com/{repo_name}",
                        repo=repo_name,
                        tags=fm.get("tags", []),
                        file_path=str(path),
                        updated_at=meta.get("fetched_at", ""),
                    )
                    self._cache[info.id] = info
                    results.append(info)
                except Exception:
                    logger.exception("Failed to read GH skill: %s", path)
            for path in sorted(repo_dir.glob("*.yaml")):
                if path.stem.startswith("_"):
                    continue
                try:
                    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
                    if not raw or not isinstance(raw, dict):
                        continue
                    skill_id = f"gh-{repo_dir.name}-{path.stem}"
                    info = SkillInfo(
                        id=skill_id,
                        name=raw.get("name", path.stem),
                        description=raw.get("description", raw.get("persona", {}).get("description", "")),
                        content=raw.get("system_prompt", yaml.dump(raw)),
                        source="github",
                        source_url=f"https://github.com/{repo_name}",
                        repo=repo_name,
                        tags=raw.get("skills", []) + raw.get("tags", []),
                        file_path=str(path),
                        updated_at=meta.get("fetched_at", ""),
                    )
                    self._cache[info.id] = info
                    results.append(info)
                except Exception:
                    logger.exception("Failed to read GH skill yaml: %s", path)
        return results

    # -- GitHub sync --

    def add_github_source(self, repo: str, path: str = "", branch: str = "main") -> dict:
        """Add a GitHub repo as skill source and fetch its skills."""
        src = {"repo": repo, "path": path, "branch": branch}
        if not any(s["repo"] == repo for s in self._github_sources):
            self._github_sources.append(src)
        # Persist to DB
        try:
            db = get_db()
            db.execute(
                "INSERT OR REPLACE INTO skill_github_sources (repo, path, branch) VALUES (?,?,?)",
                (repo, path, branch),
            )
            db.commit()
            db.close()
        except Exception:
            logger.exception("Failed to save GH source")
        return self.fetch_github_repo(repo, path, branch)

    def remove_github_source(self, repo: str):
        """Remove a GitHub repo source."""
        self._github_sources = [s for s in self._github_sources if s["repo"] != repo]
        try:
            db = get_db()
            db.execute("DELETE FROM skill_github_sources WHERE repo=?", (repo,))
            db.commit()
            db.close()
        except Exception:
            pass
        # Remove cached files
        import shutil
        repo_dir = GITHUB_SKILLS_DIR / repo.replace("/", "__")
        if repo_dir.exists():
            shutil.rmtree(repo_dir)

    def fetch_github_repo(self, repo: str, path: str = "", branch: str = "main") -> dict:
        """Fetch skill files from a GitHub repo via shallow git clone, cache locally."""
        import shutil
        import subprocess
        import tempfile

        repo_dir = GITHUB_SKILLS_DIR / repo.replace("/", "__")
        SKILL_EXTS = {".md", ".yaml", ".yml", ".txt", ".js", ".py", ".json"}
        errors = []

        clone_url = f"https://github.com/{repo}.git"
        with tempfile.TemporaryDirectory(prefix="macaron_gh_") as tmp:
            clone_dir = Path(tmp) / "repo"
            try:
                # Shallow clone (fast, no history)
                cmd = ["git", "clone", "--depth", "1", "--branch", branch, clone_url, str(clone_dir)]
                subprocess.run(cmd, capture_output=True, timeout=120, check=True)
            except subprocess.CalledProcessError as e:
                errors.append(f"git clone failed: {e.stderr.decode()[:200]}")
                return {"fetched": 0, "errors": errors, "repo": repo}
            except subprocess.TimeoutExpired:
                errors.append("git clone timed out (120s)")
                return {"fetched": 0, "errors": errors, "repo": repo}

            # Source directory within the clone
            src_dir = clone_dir / path if path else clone_dir

            if not src_dir.exists():
                errors.append(f"Path '{path}' not found in repo")
                return {"fetched": 0, "errors": errors, "repo": repo}

            # Clear previous cache and rebuild
            if repo_dir.exists():
                shutil.rmtree(repo_dir)
            repo_dir.mkdir(parents=True, exist_ok=True)

            fetched = 0
            for item in sorted(src_dir.iterdir()):
                if item.name.startswith(".") or item.name.startswith("_") or item.name == "LICENSE":
                    continue
                if item.is_dir():
                    # Look for SKILL.md or system.md inside subdirectories
                    for candidate in ["SKILL.md", "system.md"]:
                        skill_file = item / candidate
                        if skill_file.exists():
                            dest = repo_dir / f"{item.name}.md"
                            dest.write_text(skill_file.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
                            fetched += 1
                            break
                    else:
                        # Copy any skill-type files from subdir
                        for f in sorted(item.rglob("*")):
                            if f.is_file() and f.suffix.lower() in SKILL_EXTS and not f.name.startswith((".", "_")):
                                flat = f"{item.name}__{f.name}"
                                dest = repo_dir / flat
                                dest.write_text(f.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
                                fetched += 1
                elif item.is_file() and item.suffix.lower() in SKILL_EXTS:
                    dest = repo_dir / item.name
                    dest.write_text(item.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
                    fetched += 1

        # Save meta
        meta = {
            "repo": repo, "path": path, "branch": branch,
            "fetched_at": datetime.utcnow().isoformat(),
            "files_count": fetched,
        }
        (repo_dir / "_meta.json").write_text(json.dumps(meta, indent=2))
        return {"fetched": fetched, "errors": errors, "repo": repo}

    def sync_all_github(self) -> list[dict]:
        """Fetch all registered GitHub sources."""
        results = []
        for src in self._github_sources:
            r = self.fetch_github_repo(src["repo"], src.get("path", ""), src.get("branch", "main"))
            results.append(r)
        return results

    def get_github_sources(self) -> list[dict]:
        """Return list of registered GitHub sources with meta info."""
        sources = []
        for src in self._github_sources:
            repo_dir = GITHUB_SKILLS_DIR / src["repo"].replace("/", "__")
            meta = {}
            meta_file = repo_dir / "_meta.json"
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text())
                except Exception:
                    pass
            sources.append({
                **src,
                "fetched_at": meta.get("fetched_at", "never"),
                "files_count": meta.get("files_count", 0),
            })
        return sources

    def get(self, skill_id: str) -> Optional[SkillInfo]:
        """Get a single skill by ID."""
        if not self._cache:
            self.scan_all()
        return self._cache.get(skill_id)

    def seed_db(self) -> int:
        """Insert all skills into the DB skills table if empty."""
        db = get_db()
        try:
            count = db.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
            if count > 0:
                return 0
            skills = self.scan_all()
            now = datetime.utcnow().isoformat()
            for s in skills:
                db.execute(
                    """INSERT OR IGNORE INTO skills
                       (id, name, description, content, source, source_url, tags_json, created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (s.id, s.name, s.description, s.content, s.source,
                     s.source_url or s.file_path, json.dumps(s.tags), now, now),
                )
            db.commit()
            return len(skills)
        finally:
            db.close()


# ── Singleton ────────────────────────────────────────────────────

_library: Optional[SkillLibrary] = None


def get_skill_library() -> SkillLibrary:
    global _library
    if _library is None:
        _library = SkillLibrary()
    return _library
