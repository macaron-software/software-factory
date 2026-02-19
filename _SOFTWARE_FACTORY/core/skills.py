"""
Skills Loader - Load specialized prompts for agents

Skills are markdown files in /skills/ that provide domain-specific
instructions for TDD, UI, UX, testing agents.

Supports Anthropic Agent Skills spec (YAML frontmatter) with progressive disclosure:
  Level 1: Metadata (name + description) - always available (~100 tokens)
  Level 2: Body (SKILL.md content) - loaded on demand (<5K tokens)
  Level 3: References (references/*.md) - loaded on demand (unlimited)

Usage:
    from core.skills import SkillLoader

    loader = SkillLoader()
    skill = loader.get_skill('smoke_ihm')
    prompt = loader.build_prompt(task, skills=['smoke_ihm', 'ux'])
"""

import re
from pathlib import Path
from typing import List, Dict, Optional, NamedTuple
import logging

logger = logging.getLogger(__name__)

# Skill directory relative to this file
SKILLS_DIR = Path(__file__).parent.parent / "skills"

# Frontmatter regex: matches --- ... --- block at start of file
_FRONTMATTER_RE = re.compile(
    r"\A---\s*\n(.*?\n)---\s*\n",
    re.DOTALL,
)


class SkillMeta(NamedTuple):
    """Skill metadata from YAML frontmatter (Level 1 - always in context)"""
    name: str
    description: str


# Mapping: task domain/type → skills to load
DOMAIN_SKILLS: Dict[str, List[str]] = {
    # Test domains
    "e2e": ["e2e_ihm", "smoke_ihm", "webapp-testing"],
    "smoke": ["smoke_ihm"],
    "api_test": ["e2e_api", "tdd"],
    "browser_test": ["e2e_ihm", "webapp-testing", "ux"],

    # Development domains
    "svelte": ["ui", "ux", "tdd", "frontend-design"],
    "frontend": ["ui", "ux", "tdd", "frontend-design"],
    "php": ["ui-ppz", "ux-ppz", "tdd"],
    "css": ["ui-ppz", "frontend-design"],
    "typescript": ["tdd"],
    "rust": ["tdd"],
    "python": ["tdd"],
    "kotlin": ["ui", "tdd"],
    "swift": ["ui", "tdd"],

    # Specialized
    "accessibility": ["ux"],
    "design": ["ui", "frontend-design"],
    "component": ["ui", "tdd", "frontend-design"],
}

# Task type → skills
TYPE_SKILLS: Dict[str, List[str]] = {
    "smoke_test": ["smoke_ihm"],
    "e2e_test": ["e2e_ihm", "webapp-testing"],
    "api_test": ["e2e_api"],
    "unit_test": ["tdd"],
    "component": ["ui", "tdd"],
    "fix": ["tdd"],
    "feature": ["tdd"],
    "refactor": ["tdd"],
    "accessibility": ["ux"],
}


def _parse_frontmatter(content: str) -> tuple[Optional[SkillMeta], str]:
    """Parse YAML frontmatter from skill content.

    Returns (metadata, body). If no frontmatter, returns (None, full_content).
    Parses simple key: value pairs (no nested YAML, no dependency needed).
    """
    m = _FRONTMATTER_RE.match(content)
    if not m:
        return None, content

    yaml_block = m.group(1)
    body = content[m.end():]

    # Simple key: value parsing (handles multiline description with continuation)
    fields: Dict[str, str] = {}
    current_key = None
    current_val_lines: list[str] = []

    for line in yaml_block.split("\n"):
        kv = re.match(r"^(\w[\w-]*)\s*:\s*(.*)", line)
        if kv:
            # Save previous key
            if current_key:
                fields[current_key] = " ".join(current_val_lines).strip()
            current_key = kv.group(1)
            current_val_lines = [kv.group(2).strip()]
        elif current_key and line.startswith("  "):
            # Continuation line
            current_val_lines.append(line.strip())

    if current_key:
        fields[current_key] = " ".join(current_val_lines).strip()

    name = fields.get("name", "")
    description = fields.get("description", "")

    if not name:
        return None, content

    return SkillMeta(name=name, description=description), body


class SkillLoader:
    """Load and manage skill prompts for agents.

    Supports progressive disclosure:
    - get_skill_meta(): Level 1 (name + description, ~100 tokens)
    - get_skill(): Level 2 (full body, <5K tokens)
    - get_references(): Level 3 (on-demand reference files)
    """

    def __init__(self, skills_dir: Optional[Path] = None):
        self.skills_dir = skills_dir or SKILLS_DIR
        self._cache: Dict[str, str] = {}
        self._meta_cache: Dict[str, Optional[SkillMeta]] = {}

    def list_skills(self) -> List[str]:
        """List all available skills"""
        if not self.skills_dir.exists():
            logger.warning(f"Skills directory not found: {self.skills_dir}")
            return []

        skills = []
        for f in self.skills_dir.glob("*.md"):
            skills.append(f.stem)
        return sorted(skills)

    def get_skill_meta(self, name: str) -> Optional[SkillMeta]:
        """Get skill metadata (Level 1 - always cheap to load).

        Returns SkillMeta(name, description) or None.
        For skills without frontmatter, synthesizes metadata from content.
        """
        if name in self._meta_cache:
            return self._meta_cache[name]

        content = self._load_raw(name)
        if content is None:
            self._meta_cache[name] = None
            return None

        meta, _ = _parse_frontmatter(content)

        if meta is None:
            # Backward compat: synthesize from old format
            desc = ""
            for line in content.split("\n"):
                if line.startswith("## Description"):
                    continue
                if line.startswith("## ") and desc:
                    break
                if desc or line.startswith("## Description"):
                    desc_line = line.lstrip("# ").strip()
                    if desc_line:
                        desc = desc_line
                        break
            meta = SkillMeta(name=name, description=desc)

        self._meta_cache[name] = meta
        return meta

    def get_skill(self, name: str) -> Optional[str]:
        """Load skill body (Level 2 - loaded on demand).

        Returns the body content (without frontmatter).
        """
        if name in self._cache:
            return self._cache[name]

        content = self._load_raw(name)
        if content is None:
            return None

        _, body = _parse_frontmatter(content)
        self._cache[name] = body
        return body

    def get_references(self, name: str) -> Dict[str, str]:
        """Load skill references (Level 3 - loaded on demand).

        Looks for references/*.md files next to the skill.
        Returns {filename: content} dict.
        """
        refs_dir = self.skills_dir / name / "references"
        if not refs_dir.exists():
            # Also check for flat references: skills/skillname-ref-*.md
            refs = {}
            for f in self.skills_dir.glob(f"{name}-ref-*.md"):
                try:
                    refs[f.stem] = f.read_text(encoding="utf-8")
                except Exception:
                    pass
            return refs

        refs = {}
        for f in refs_dir.glob("*.md"):
            try:
                refs[f.stem] = f.read_text(encoding="utf-8")
            except Exception as e:
                logger.error(f"Failed to load reference {f}: {e}")
        return refs

    def get_skills_for_domain(self, domain: str) -> List[str]:
        """Get skill names for a domain"""
        return DOMAIN_SKILLS.get(domain, [])

    def get_skills_for_type(self, task_type: str) -> List[str]:
        """Get skill names for a task type"""
        return TYPE_SKILLS.get(task_type, [])

    def get_relevant_skills(self, domain: str, task_type: str = "") -> List[str]:
        """Get all relevant skills for a task (deduplicated)"""
        skills = set()
        skills.update(self.get_skills_for_domain(domain))
        if task_type:
            skills.update(self.get_skills_for_type(task_type))
        return list(skills)

    def build_skill_prompt(self, skill_names: List[str], max_chars: int = 8000) -> str:
        """Build a combined prompt from multiple skills.

        Uses progressive disclosure:
        - Always includes metadata (name + description)
        - Includes key sections (checklist, anti-patterns, template)
        - Truncates if over max_chars budget
        """
        if not skill_names:
            return ""

        sections = []
        total_chars = 0

        for name in skill_names:
            body = self.get_skill(name)
            if not body:
                continue

            meta = self.get_skill_meta(name)

            # Extract key sections from body
            extracted = self._extract_key_sections(name, body, meta)
            if extracted:
                if total_chars + len(extracted) > max_chars:
                    remaining = max_chars - total_chars
                    if remaining > 500:
                        sections.append(extracted[:remaining] + "\n... (truncated)")
                    break
                sections.append(extracted)
                total_chars += len(extracted)

        if not sections:
            return ""

        return f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SKILLS LOADED: {', '.join(skill_names)}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{chr(10).join(sections)}
"""

    def _extract_key_sections(self, skill_name: str, body: str, meta: Optional[SkillMeta] = None) -> str:
        """Extract key sections from a skill body for prompt injection."""
        lines = body.split("\n")
        result = []
        current_section = None

        # Sections to extract (in order of priority)
        target_sections = [
            "## Description",
            "## Quand utiliser",
            "## Checklist",
            "## Anti-patterns",
            "## Template",
            # Anthropic-style sections
            "## Design Thinking",
            "## Best Practices",
            "## Common Pitfall",
            "## Decision Tree",
        ]

        section_content: Dict[str, List[str]] = {s: [] for s in target_sections}

        for line in lines:
            # Check for section headers
            matched = False
            for section in target_sections:
                if line.startswith(section):
                    current_section = section
                    matched = True
                    break

            if not matched and line.startswith("## ") and current_section:
                current_section = None

            if current_section:
                section_content[current_section].append(line)

        # Build output with metadata header
        display_name = meta.name if meta else skill_name
        result.append(f"### SKILL: {display_name.upper()}")
        if meta and meta.description:
            result.append(f"_{meta.description}_")
        result.append("")

        for section in target_sections:
            content_lines = section_content[section]
            if content_lines:
                if len(content_lines) > 30:
                    content_lines = content_lines[:30] + ["... (see full skill)"]
                result.extend(content_lines)
                result.append("")

        return "\n".join(result)

    def _load_raw(self, name: str) -> Optional[str]:
        """Load raw file content for a skill."""
        skill_path = self.skills_dir / f"{name}.md"
        if not skill_path.exists():
            logger.warning(f"Skill not found: {name}")
            return None

        try:
            return skill_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to load skill {name}: {e}")
            return None


# Global instance
_loader: Optional[SkillLoader] = None


def get_skill_loader() -> SkillLoader:
    """Get global skill loader instance"""
    global _loader
    if _loader is None:
        _loader = SkillLoader()
    return _loader


def load_skills_for_task(domain: str, task_type: str = "", max_chars: int = 8000) -> str:
    """
    Convenience function: load all relevant skills for a task.

    Args:
        domain: Task domain (e2e, svelte, rust, etc.)
        task_type: Task type (smoke_test, e2e_test, fix, etc.)
        max_chars: Maximum chars for combined prompt

    Returns:
        Combined skill prompt string
    """
    loader = get_skill_loader()
    skill_names = loader.get_relevant_skills(domain, task_type)
    return loader.build_skill_prompt(skill_names, max_chars)


# CLI for testing
if __name__ == "__main__":
    import sys

    loader = SkillLoader()

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "list":
            print("Available skills:")
            for s in loader.list_skills():
                meta = loader.get_skill_meta(s)
                desc = f" - {meta.description[:60]}..." if meta and meta.description else ""
                print(f"  - {s}{desc}")

        elif cmd == "show" and len(sys.argv) > 2:
            skill = loader.get_skill(sys.argv[2])
            if skill:
                print(skill)
            else:
                print(f"Skill not found: {sys.argv[2]}")

        elif cmd == "meta" and len(sys.argv) > 2:
            meta = loader.get_skill_meta(sys.argv[2])
            if meta:
                print(f"Name: {meta.name}")
                print(f"Description: {meta.description}")
            else:
                print(f"Skill not found: {sys.argv[2]}")

        elif cmd == "build" and len(sys.argv) > 2:
            domain = sys.argv[2]
            task_type = sys.argv[3] if len(sys.argv) > 3 else ""
            prompt = load_skills_for_task(domain, task_type)
            print(prompt)

    else:
        print("Usage:")
        print("  python skills.py list              - List all skills with descriptions")
        print("  python skills.py show <skill>      - Show skill body")
        print("  python skills.py meta <skill>      - Show skill metadata")
        print("  python skills.py build <domain>    - Build prompt for domain")
