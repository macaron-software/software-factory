#!/usr/bin/env python3
"""Pre-commit hook: detect + anonymize sensitive staged content with Presidio."""

from __future__ import annotations

import subprocess
import sys
import re
from pathlib import Path

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerRegistry
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
from presidio_anonymizer.entities.engine.recognizer_result import RecognizerResult


ALLOWED_EXTENSIONS = {
    ".py",
    ".md",
    ".txt",
    ".yml",
    ".yaml",
    ".json",
    ".toml",
    ".ini",
    ".cfg",
    ".env",
    ".sh",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".sql",
    ".html",
    ".css",
    ".xml",
}

BLOCK_ENTITIES = {
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "IP_ADDRESS",
    "CREDIT_CARD",
}

ALLOWLIST_SNIPPETS = (
    "admin@demo.local",
    "security@macaron-software.com",
    "conduct@macaron-software.com",
    "noreply@macaron-software.com",
    "postgresql://macaron:macaron@",
    "postgresql://${PG_USER:-",
    "postgresql://user:password@",
    "postgresql://user:pass@",
    "postgres://postgres:test@",
    "Authorization: Bearer YOUR_TOKEN",
    "Authorization: Bearer eyJ",
    "Authorization: Bearer sk_live_xxx",
    "-----BEGIN RSA PRIVATE KEY-----",
)

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("PRIVATE_KEY", re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----")),
    ("BEARER_TOKEN", re.compile(r"Authorization:\s*Bearer\s+[A-Za-z0-9._-]{10,}", re.IGNORECASE)),
    ("GITHUB_TOKEN", re.compile(r"\b(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
    ("OPENAI_KEY", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
)

PRESIDIO_PATTERNS: dict[str, str] = {
    "EMAIL_ADDRESS": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    "PHONE_NUMBER": r"\+?\d[\d\s().-]{7,}\d",
    "IP_ADDRESS": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    "CREDIT_CARD": r"\b(?:\d[ -]*?){13,16}\b",
}


def staged_files() -> list[Path]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        check=True,
        capture_output=True,
        text=True,
    )
    files: list[Path] = []
    for line in result.stdout.splitlines():
        p = Path(line.strip())
        if not p.exists() or p.is_dir():
            continue
        if p.suffix.lower() in ALLOWED_EXTENSIONS or p.name == ".env":
            files.append(p)
    return files


def is_allowlisted_text(s: str) -> bool:
    return any(snippet in s for snippet in ALLOWLIST_SNIPPETS)


def find_secret_matches(text: str) -> list[tuple[str, int, int, str]]:
    out: list[tuple[str, int, int, str]] = []
    for label, pattern in SECRET_PATTERNS:
        for m in pattern.finditer(text):
            snippet = m.group(0)
            if is_allowlisted_text(snippet):
                continue
            out.append((label, m.start(), m.end(), snippet))
    return out


def build_analyzer() -> AnalyzerEngine:
    registry = RecognizerRegistry()
    for entity, pattern in PRESIDIO_PATTERNS.items():
        registry.add_recognizer(
            PatternRecognizer(
                supported_entity=entity,
                patterns=[Pattern(name=entity.lower(), regex=pattern, score=0.75)],
            )
        )
    return AnalyzerEngine(registry=registry, nlp_engine=None, supported_languages=["en"])


def main() -> int:
    files = staged_files()
    if not files:
        return 0

    analyzer = build_analyzer()
    anonymizer = AnonymizerEngine()
    violations: list[tuple[str, str, str, float]] = []
    changed_files: list[str] = []

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
            entities=list(BLOCK_ENTITIES),
            score_threshold=0.65,
        )
        replacements: list[tuple[int, int, str]] = []
        for r in results:
            snippet = text[r.start : r.end]
            if is_allowlisted_text(snippet):
                continue
            violations.append((str(file_path), r.entity_type, snippet[:80], float(r.score)))
            replacements.append((r.start, r.end, r.entity_type))

        secret_matches = find_secret_matches(text)
        for label, start, end, snippet in secret_matches:
            violations.append((str(file_path), label, snippet[:80], 1.0))
            replacements.append((start, end, "REDACTED_SECRET"))

        if not replacements:
            continue

        presidio_results = [
            RecognizerResult(entity_type=entity_type, start=start, end=end, score=1.0)
            for start, end, entity_type in replacements
        ]
        anonymized = anonymizer.anonymize(
            text=text,
            analyzer_results=presidio_results,
            operators={"DEFAULT": OperatorConfig("replace", {"new_value": "[REDACTED]"})},
        )
        new_text = anonymized.text
        if new_text != text:
            file_path.write_text(new_text, encoding="utf-8")
            subprocess.run(["git", "add", str(file_path)], check=False)
            changed_files.append(str(file_path))

    if not violations:
        return 0

    print("ERROR: Presidio pre-commit detected sensitive data.")
    for path, entity, snippet, score in violations[:50]:
        preview = snippet.replace("\n", " ").strip()
        print(f" - {path}: {entity} (score={score:.2f}) -> {preview}")
    if len(violations) > 50:
        print(f" ... and {len(violations) - 50} more")
    if changed_files:
        print("Auto-anonymized and re-staged files:")
        for path in sorted(set(changed_files)):
            print(f" - {path}")
    print("Review changes, then re-run commit.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
