#!/bin/bash
# sync-to-laposte.sh — Sync du squelette plateforme vers GitLab La Poste
#
# Source : ~/_MACARON-SOFTWARE/  (GitHub macaron-software)
# Dest   : ~/_LAPOSTE/_SOFTWARE_FACTORY/  (GitLab La Poste (URL dans .env))
#
# Usage : ./sync-to-laposte.sh [--dry-run]

set -e

GITHUB_REPO="$HOME/_MACARON-SOFTWARE"
LAPOSTE_REPO="$HOME/_LAPOSTE/_SOFTWARE_FACTORY"

# URL chargée depuis .env (non commitée) ou variable d'env
[ -f "$GITHUB_REPO/.env" ] && source "$GITHUB_REPO/.env"
LAPOSTE_REMOTE="${GITLAB_LAPOSTE_REMOTE:-git@<gitlab-host>:<group>/software-factory.git}"
DRY_RUN=false

[[ "$1" == "--dry-run" ]] && DRY_RUN=true

echo "=== Sync vers GitLab La Poste ==="
echo "Source : $GITHUB_REPO"
echo "Dest   : $LAPOSTE_REPO"
$DRY_RUN && echo "[DRY-RUN — aucune modification]"
echo ""

# ── 1. Clone si inexistant ────────────────────────────────────────────────────
if [ ! -d "$LAPOSTE_REPO/.git" ]; then
    echo " Clone du repo La Poste..."
    if ! $DRY_RUN; then
        git clone "$LAPOSTE_REMOTE" "$LAPOSTE_REPO" 2>/dev/null || {
            mkdir -p "$LAPOSTE_REPO"
            cd "$LAPOSTE_REPO"
            git init && git remote add origin "$LAPOSTE_REMOTE"
        }
    else
        echo "   [dry-run] git clone $LAPOSTE_REMOTE $LAPOSTE_REPO"
    fi
fi

# ── 2. Sync du code (sans agents/workflows/projets) ───────────────────────────
echo "Synchronisation du code..."
RSYNC_OPTS="-a --delete"
$DRY_RUN && RSYNC_OPTS="-an --delete"

EXCLUDES=(
    "--exclude=.git"
    "--exclude=__pycache__"
    "--exclude=*.pyc"
    "--exclude=*.db" "--exclude=*.db-wal" "--exclude=*.db-shm"
    "--exclude=data/"
    "--exclude=.env"
    "--exclude=CLAUDE.md"
    "--exclude=.github/copilot-instructions.md"
    # Branding Macaron — exclus du squelette La Poste
    "--exclude=SPECS.md"
    "--exclude=macaron-platform.service"
    "--exclude=ops/RUNBOOK.md"
)

DIRS_TO_SYNC=(
    "platform"
    "cli"
    "dashboard"
    "mcp_lrm"
    "deploy"
    "tests"
)

for dir in "${DIRS_TO_SYNC[@]}"; do
    [ -d "$GITHUB_REPO/$dir" ] || continue
    echo "  → $dir/"
    rsync $RSYNC_OPTS "${EXCLUDES[@]}" \
        --exclude="skills/definitions/*.yaml" \
        --exclude="workflows/definitions/*.yaml" \
        "$GITHUB_REPO/$dir/" "$LAPOSTE_REPO/$dir/"
done

# Fichiers racine
ROOT_FILES=(Makefile Dockerfile docker-compose.yml .gitignore .env.example pyproject.toml setup_env.sh nginx.conf)
for f in "${ROOT_FILES[@]}"; do
    [ -f "$GITHUB_REPO/$f" ] || continue
    echo "  → $f"
    $DRY_RUN || cp "$GITHUB_REPO/$f" "$LAPOSTE_REPO/$f"
done

# ── 3. Placeholders vides ─────────────────────────────────────────────────────
echo "  → placeholders vides (skills, workflows, projects)"
if ! $DRY_RUN; then
    mkdir -p "$LAPOSTE_REPO/platform/skills/definitions"
    mkdir -p "$LAPOSTE_REPO/platform/workflows/definitions"
    mkdir -p "$LAPOSTE_REPO/projects"
    rm -f "$LAPOSTE_REPO/platform/skills/definitions/"*.yaml
    touch "$LAPOSTE_REPO/platform/skills/definitions/.gitkeep"
    rm -f "$LAPOSTE_REPO/platform/workflows/definitions/"*.yaml
    touch "$LAPOSTE_REPO/platform/workflows/definitions/.gitkeep"
    rm -f "$LAPOSTE_REPO/projects/"*.yaml
    touch "$LAPOSTE_REPO/projects/.gitkeep"
    cp "$GITHUB_REPO/platform/skills/definitions/_template.yaml" \
       "$LAPOSTE_REPO/platform/skills/definitions/_template.yaml" 2>/dev/null || true
fi

# ── 4. README La Poste (toujours synchronisé depuis README.laposte.md) ────────
echo "  -> README.md"
$DRY_RUN || cp "$GITHUB_REPO/README.laposte.md" "$LAPOSTE_REPO/README.md"

# ── 5. Commit + push ──────────────────────────────────────────────────────────
if ! $DRY_RUN; then
    cd "$LAPOSTE_REPO"
    git add -A
    if git diff --cached --quiet; then
        echo "-> Déjà à jour — aucun changement"
    else
        # Reprendre les messages des commits GitHub depuis le dernier sync
        LAST_SYNC_SHA=$(git log -1 --pretty=%H 2>/dev/null || echo "")
        GITHUB_LOG=$(cd "$GITHUB_REPO" && git log --oneline --no-merges -10 --pretty="%s" 2>/dev/null | head -5)
        COMMIT_MSG=$(echo "$GITHUB_LOG" | head -1)
        EXTRA=$(echo "$GITHUB_LOG" | tail -n +2 | sed 's/^/- /')
        if [ -n "$EXTRA" ]; then
            COMMIT_MSG="$COMMIT_MSG

$EXTRA"
        fi
        git commit -m "sync(laposte): $COMMIT_MSG"
        echo "-> Push vers GitLab La Poste..."
        git push origin main || git push origin HEAD:main
        echo "-> Sync terminé"
    fi
else
    echo ""
    echo "OK [DRY-RUN] Simulation OK — aucune modification"
fi
