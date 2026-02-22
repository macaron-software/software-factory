#!/usr/bin/env python3
"""
Load demo skills from existing skills markdown files into skills_index
This creates a working demo without needing external GitHub skills
"""

import os
import re
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills_injection.skills_storage import SkillsStorage


def parse_markdown_skill(filepath: Path) -> dict:
    """Parse a markdown skill file and extract metadata."""
    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    # Extract title (first # heading)
    title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    title = title_match.group(1) if title_match else filepath.stem.replace("-", " ").title()

    # Extract description (text after title before next heading)
    desc_match = re.search(r"^#\s+.+?\n\n(.+?)(?=\n#|$)", content, re.DOTALL | re.MULTILINE)
    description = desc_match.group(1).strip()[:500] if desc_match else ""

    # Detect domains from filename and content
    domains = []
    filename_lower = filepath.stem.lower()
    content_lower = content.lower()

    domain_keywords = {
        "frontend": ["react", "vue", "css", "html", "ui", "component", "design"],
        "backend": ["api", "database", "server", "endpoint"],
        "devops": ["docker", "kubernetes", "ci/cd", "deploy", "pipeline"],
        "data": ["data", "analytics", "etl", "warehouse"],
        "security": ["security", "auth", "pentest", "vulnerability"],
        "testing": ["test", "e2e", "qa", "playwright"],
        "mobile": ["mobile", "ios", "android"],
        "design": ["figma", "design", "ui", "ux", "a11y"],
        "architecture": ["architecture", "review", "system"],
    }

    for domain, keywords in domain_keywords.items():
        if any(kw in filename_lower or kw in content_lower for kw in keywords):
            domains.append(domain)

    if not domains:
        domains = ["general"]

    return {
        "title": title,
        "description": description,
        "content": content[:1000],  # First 1000 chars
        "domains": domains,
        "filename": filepath.name,
    }


def load_skills_as_demo():
    """Load markdown skills as demo skills."""

    # Initialize storage
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "platform.db")
    storage = SkillsStorage(db_path)

    # Find skills directory
    skills_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills")

    if not os.path.exists(skills_dir):
        print(f"❌ Skills directory not found: {skills_dir}")
        return

    print(f"📂 Loading skills from: {skills_dir}")

    skills = []
    md_files = list(Path(skills_dir).glob("*.md"))

    print(f"Found {len(md_files)} markdown files")

    for md_file in md_files:
        try:
            parsed = parse_markdown_skill(md_file)

            # Create skill ID
            skill_id = f"skill-{md_file.stem}"

            # Metadata
            metadata = {
                "source": "internal-skills",
                "domains": parsed["domains"],
                "filename": parsed["filename"],
            }

            # Empty embedding (will trigger keyword fallback)
            embedding = [0.0] * 1536

            skills.append(
                {
                    "id": skill_id,
                    "title": parsed["title"],
                    "content": parsed["content"],
                    "embedding": embedding,
                    "metadata": metadata,
                    "source": "internal",
                    "repo": "software-factory",
                }
            )

            print(f"  ✓ {parsed['title']} [{', '.join(parsed['domains'])}]")

        except Exception as e:
            print(f"⚠️  Error loading {md_file}: {e}")
            continue

    if skills:
        print(f"\n📥 Inserting {len(skills)} skills into database...")
        storage.insert_skills_batch(skills)
        print("✅ Demo skills loaded successfully!")
        print("\nNext steps:")
        print("  1. Run tests: make test-skills")
        print("  2. Test with verbose output: make test-skills-verbose")
    else:
        print("❌ No skills extracted from markdown files")

    storage.close()


if __name__ == "__main__":
    load_skills_as_demo()
