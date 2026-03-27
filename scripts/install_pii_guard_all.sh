#!/usr/bin/env bash
# install_pii_guard_all.sh — Install PII guard pre-commit hook on all repos
#
# Copies pii_guard_lite.sh as .git/hooks/pre-commit to every git repo
# under _MACARON-SOFTWARE/. Skips repos that already have a pre-commit hook.
#
# Usage: bash scripts/install_pii_guard_all.sh [--force]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOK_SRC="$SCRIPT_DIR/pii_guard_lite.sh"
BASE_DIR="/Users/sylvain/_MACARON-SOFTWARE"
FORCE="${1:-}"

if [ ! -f "$HOOK_SRC" ]; then
    echo "ERROR: $HOOK_SRC not found"
    exit 1
fi

installed=0
skipped=0
forced=0

find "$BASE_DIR" -maxdepth 3 -name ".git" -type d 2>/dev/null | while read gitdir; do
    repo=$(dirname "$gitdir")
    name=$(basename "$repo")
    hook_dst="$gitdir/hooks/pre-commit"

    # Skip if hook already exists (unless --force)
    if [ -f "$hook_dst" ] && [ "$FORCE" != "--force" ]; then
        echo "  SKIP: $name (pre-commit hook exists)"
        skipped=$((skipped + 1))
        continue
    fi

    # Create hooks dir if needed
    mkdir -p "$gitdir/hooks"

    # Copy hook
    cp "$HOOK_SRC" "$hook_dst"
    chmod +x "$hook_dst"

    if [ "$FORCE" = "--force" ] && [ -f "$hook_dst" ]; then
        echo "  FORCE: $name"
        forced=$((forced + 1))
    else
        echo "  INSTALLED: $name"
        installed=$((installed + 1))
    fi
done

echo ""
echo "Done. PII guard deployed."
