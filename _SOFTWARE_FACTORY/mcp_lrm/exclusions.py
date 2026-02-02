#!/usr/bin/env python3
"""
MCP LRM Exclusions - File patterns to exclude from project access
=================================================================
Excludes build artifacts, caches, and version control directories.
"""

from pathlib import Path
from typing import List, Set
import fnmatch

# Directory names to always exclude
EXCLUDED_DIRS: Set[str] = {
    # Version control
    ".git",
    ".svn",
    ".hg",

    # Build outputs
    "target",
    "build",
    "dist",
    "out",
    ".next",
    ".nuxt",
    ".output",

    # Dependencies
    "node_modules",
    "vendor",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",

    # IDE
    ".idea",
    ".vscode",
    ".vs",

    # Cache
    ".cache",
    ".parcel-cache",
    ".turbo",

    # Logs
    "logs",
    "log",

    # Test artifacts
    "coverage",
    ".nyc_output",
    "playwright-report",
    "test-results",
}

# File patterns to exclude
EXCLUDED_PATTERNS: List[str] = [
    # Compiled files
    "*.pyc",
    "*.pyo",
    "*.class",
    "*.o",
    "*.so",
    "*.dll",
    "*.dylib",

    # Lock files (large, not useful for context)
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "Cargo.lock",
    "poetry.lock",
    "Gemfile.lock",

    # Build artifacts
    "*.min.js",
    "*.min.css",
    "*.bundle.js",
    "*.chunk.js",

    # Binary files
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.ico",
    "*.svg",
    "*.woff",
    "*.woff2",
    "*.ttf",
    "*.eot",
    "*.pdf",
    "*.zip",
    "*.tar.gz",
    "*.rar",

    # Database files
    "*.db",
    "*.sqlite",
    "*.sqlite3",

    # Temp files
    "*.tmp",
    "*.temp",
    "*.swp",
    "*.swo",
    ".DS_Store",
    "Thumbs.db",

    # Secrets (should never be exposed)
    ".env",
    ".env.local",
    ".env.production",
    "*.pem",
    "*.key",
    "credentials.json",
]


def should_exclude_path(path: Path, root: Path = None) -> bool:
    """
    Check if a path should be excluded from MCP access.

    Args:
        path: Path to check (can be str or Path)
        root: Project root (for relative path checking)

    Returns:
        True if path should be excluded
    """
    # Ensure path is Path object
    if isinstance(path, str):
        path = Path(path)

    # Check directory exclusions
    for part in path.parts:
        if part in EXCLUDED_DIRS:
            return True

    # Check file pattern exclusions
    name = path.name
    for pattern in EXCLUDED_PATTERNS:
        if fnmatch.fnmatch(name, pattern):
            return True

    return False


def filter_paths(paths: List[Path], root: Path = None) -> List[Path]:
    """Filter a list of paths, removing excluded ones"""
    return [p for p in paths if not should_exclude_path(p, root)]


def get_included_extensions(domain: str = None) -> Set[str]:
    """
    Get file extensions to include for a domain.

    Args:
        domain: rust, typescript, python, etc.

    Returns:
        Set of extensions (with leading dot)
    """
    common = {".md", ".txt", ".json", ".yaml", ".yml", ".toml"}

    domain_extensions = {
        "rust": {".rs", ".toml"},
        "typescript": {".ts", ".tsx", ".js", ".jsx"},
        "python": {".py", ".pyi"},
        "go": {".go", ".mod"},
        "java": {".java", ".gradle", ".xml"},
        "proto": {".proto"},
        "sql": {".sql"},
        "svelte": {".svelte", ".ts", ".js"},
        "angular": {".ts", ".html", ".scss", ".css"},
    }

    if domain and domain in domain_extensions:
        return common | domain_extensions[domain]

    # All code extensions
    return common | {".rs", ".ts", ".tsx", ".js", ".jsx", ".py", ".go", ".java", ".proto", ".sql", ".svelte", ".html", ".scss", ".css"}


# CLI
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        excluded = should_exclude_path(path)
        print(f"{path}: {'EXCLUDED' if excluded else 'INCLUDED'}")
    else:
        print("Excluded directories:", sorted(EXCLUDED_DIRS))
        print("\nExcluded patterns:", sorted(EXCLUDED_PATTERNS))
