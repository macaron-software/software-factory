#!/usr/bin/env python3
"""Presidio global pre-commit hook — detect PII in staged files. Block only, never auto-edit.

Unlike the SF-specific presidio_precommit_hook.py, this one:
- NEVER modifies files (no auto-anonymization — that broke code before)
- Only BLOCKS the commit and reports findings
- Runs fast: only staged files, score threshold 0.75
- Respects SKIP=pii-guard env var (handled by parent bash hook)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ALLOWED_EXTENSIONS = {
    ".py", ".md", ".txt", ".yml", ".yaml", ".json", ".toml", ".ini",
    ".cfg", ".env", ".sh", ".ts", ".tsx", ".js", ".jsx", ".sql",
    ".html", ".css", ".xml", ".rs", ".swift", ".kt",
}

# Only block high-confidence PII — avoid false positives on dates/versions
BLOCK_ENTITIES = {
    "CREDIT_CARD",
    "IBAN_CODE",
    "US_SSN",
    "US_BANK_NUMBER",
}

# Warn but don't block
WARN_ENTITIES = {
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "IP_ADDRESS",
}

ALLOWLIST = (
    "admin@demo.local",
    "security@macaron-software.com",
    "conduct@macaron-software.com",
    "noreply@macaron-software.com",
    "noreply@anthropic.com",
    "example@example.com",
    "user@example.com",
    "postgresql://",
    "127.0.0.1",
    "localhost",
    "0.0.0.0",
    "Co-Authored-By:",
)

SCORE_THRESHOLD = 0.75  # only flag high-confidence matches


def staged_files() -> list[Path]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        check=True, capture_output=True, text=True,
    )
    files = []
    for line in result.stdout.splitlines():
        p = Path(line.strip())
        if p.exists() and not p.is_dir() and p.suffix.lower() in ALLOWED_EXTENSIONS:
            files.append(p)
    return files


def is_allowlisted(snippet: str) -> bool:
    return any(a in snippet for a in ALLOWLIST)


def main() -> int:
    files = staged_files()
    if not files:
        return 0

    try:
        from presidio_analyzer import AnalyzerEngine
    except ImportError:
        # Presidio not available — skip silently
        return 0

    analyzer = AnalyzerEngine()
    all_entities = BLOCK_ENTITIES | WARN_ENTITIES
    blocks = []
    warnings = []

    for file_path in files:
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if not text.strip():
            continue

        results = analyzer.analyze(
            text=text,
            language="en",
            entities=list(all_entities),
            score_threshold=SCORE_THRESHOLD,
        )

        for r in results:
            snippet = text[r.start:r.end]
            if is_allowlisted(snippet):
                continue

            if r.entity_type in BLOCK_ENTITIES:
                blocks.append((str(file_path), r.entity_type, snippet[:40], r.score))
            elif r.entity_type in WARN_ENTITIES:
                warnings.append((str(file_path), r.entity_type, snippet[:40], r.score))

    if warnings:
        print("Presidio warnings (not blocking):", file=sys.stderr)
        for path, entity, snippet, score in warnings[:10]:
            print(f"  WARN: {path}: {entity} ({score:.2f}) → {snippet}", file=sys.stderr)

    if blocks:
        print("Presidio BLOCKED — sensitive data detected:", file=sys.stderr)
        for path, entity, snippet, score in blocks[:10]:
            print(f"  BLOCK: {path}: {entity} ({score:.2f}) → {snippet}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
