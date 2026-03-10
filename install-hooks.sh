#!/bin/bash
# install-hooks.sh — Installe les git hooks locaux depuis hooks/
# Usage : ./install-hooks.sh
# À relancer après un `git clone`

set -e

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
HOOKS_SRC="$REPO_ROOT/hooks"
HOOKS_DST="$REPO_ROOT/.git/hooks"

echo "=== Installation des git hooks ==="

for hook in "$HOOKS_SRC"/*; do
    name="$(basename "$hook")"
    dest="$HOOKS_DST/$name"

    if [ -f "$dest" ] && ! cmp -s "$hook" "$dest"; then
        echo "  ⚠️  $name — déjà présent et différent → sauvegarde en $name.bak"
        cp "$dest" "$dest.bak"
    fi

    cp "$hook" "$dest"
    chmod +x "$dest"
    echo "  ✅ $name installé"
done

echo ""
echo "Hooks actifs :"
ls -1 "$HOOKS_DST" | grep -v "\.sample\|\.bak" | sed 's/^/  - /'
echo ""
echo "✅ Installation terminée"
