#!/usr/bin/env bash
# detect-gaps.sh — Detect missing elements in the SF project at session start.
# Outputs warnings as JSON for Claude Code to surface.
# Runs fast (<2s) — only checks file existence, no heavy analysis.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
GAPS=()

# ── Platform structure gaps ──────────────────────────────────────────────────

# DB schema must exist
[ -f "$ROOT/platform/db/schema_pg.sql" ] || GAPS+=("Missing platform/db/schema_pg.sql — no PG schema defined")

# Migrations must exist
[ -f "$ROOT/platform/db/migrations.py" ] || GAPS+=("Missing platform/db/migrations.py — no migration runner")

# Config must exist
[ -f "$ROOT/platform/config.py" ] || GAPS+=("Missing platform/config.py — no platform configuration")

# Server entry point
[ -f "$ROOT/platform/server.py" ] || GAPS+=("Missing platform/server.py — no server entry point")

# ── Test coverage gaps ───────────────────────────────────────────────────────

# At least some tests must exist
PYTEST_COUNT=$(find "$ROOT/tests" -name "test_*.py" -maxdepth 1 2>/dev/null | wc -l | tr -d ' ')
[ "$PYTEST_COUNT" -gt 0 ] || GAPS+=("No tests found in tests/ — add pytest test files")

# E2E tests
E2E_COUNT=$(find "$ROOT/platform/tests/e2e" -name "*.spec.ts" -maxdepth 1 2>/dev/null | wc -l | tr -d ' ')
[ "$E2E_COUNT" -gt 0 ] || GAPS+=("No E2E specs in platform/tests/e2e/ — add Playwright specs")

# ── Documentation gaps ───────────────────────────────────────────────────────

# CLAUDE.md must exist (project instructions)
[ -f "$ROOT/CLAUDE.md" ] || GAPS+=("Missing CLAUDE.md — no project instructions for AI agents")

# Architecture doc
[ -f "$ROOT/.ai/ARCHITECTURE.md" ] || [ -f "$ROOT/ARCHITECTURE.md" ] || GAPS+=("Missing architecture doc (.ai/ARCHITECTURE.md or ARCHITECTURE.md)")

# ── Security gaps ────────────────────────────────────────────────────────────

# .env must not be tracked
if [ -f "$ROOT/.env" ] && git -C "$ROOT" ls-files --error-unmatch .env >/dev/null 2>&1; then
    GAPS+=("CRITICAL: .env is tracked by git — remove it and add to .gitignore")
fi

# .gitignore must exist
[ -f "$ROOT/.gitignore" ] || GAPS+=("Missing .gitignore — sensitive files may be committed")

# ── Skill quality gaps ───────────────────────────────────────────────────────

# Count skills without eval_cases
if [ -d "$ROOT/platform/skills/definitions" ]; then
    TOTAL_SKILLS=$(find "$ROOT/platform/skills/definitions" -name "*.yaml" ! -name "_*" | wc -l | tr -d ' ')
    SKILLS_WITH_EVAL=$(grep -rl "eval_cases:" "$ROOT/platform/skills/definitions" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$TOTAL_SKILLS" -gt 0 ]; then
        COVERAGE=$((SKILLS_WITH_EVAL * 100 / TOTAL_SKILLS))
        if [ "$COVERAGE" -lt 50 ]; then
            GAPS+=("Skill eval coverage: ${COVERAGE}% (${SKILLS_WITH_EVAL}/${TOTAL_SKILLS}) — target 80%+")
        fi
    fi
fi

# ── Workflow definition gaps ─────────────────────────────────────────────────

if [ -d "$ROOT/platform/workflows/definitions" ]; then
    WF_COUNT=$(find "$ROOT/platform/workflows/definitions" -name "*.yaml" | wc -l | tr -d ' ')
    [ "$WF_COUNT" -gt 0 ] || GAPS+=("No workflow definitions in platform/workflows/definitions/")
fi

# ── Agent bench gaps ─────────────────────────────────────────────────────────

if [ -d "$ROOT/platform/agents/benchmarks" ]; then
    BENCH_COUNT=$(find "$ROOT/platform/agents/benchmarks" -name "*.yaml" -maxdepth 1 | wc -l | tr -d ' ')
    AGENT_COUNT=$(find "$ROOT/platform/skills/definitions" -name "*.yaml" ! -name "_*" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$AGENT_COUNT" -gt 0 ] && [ "$BENCH_COUNT" -lt 5 ]; then
        GAPS+=("Agent bench coverage: ${BENCH_COUNT} benchmarks for ${AGENT_COUNT} agents — add more YAML bench defs")
    fi
fi

# ── Output ───────────────────────────────────────────────────────────────────

if [ ${#GAPS[@]} -eq 0 ]; then
    exit 0
fi

# Output as text warnings (Claude Code reads stderr)
echo "--- Project Gap Detection ---" >&2
for gap in "${GAPS[@]}"; do
    echo "  WARNING: $gap" >&2
done
echo "--- ${#GAPS[@]} gap(s) detected ---" >&2

exit 0
