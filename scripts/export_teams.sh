#!/bin/bash
# export_teams.sh — Export agent teams from a running platform to teams/ YAML files
# Usage: ./scripts/export_teams.sh [--platform local|azure|ovh] [--project PROJECT_ID]
#
# Examples:
#   ./scripts/export_teams.sh --platform local
#   ./scripts/export_teams.sh --platform azure --project urbanpulse

set -e

PLATFORM="local"
PROJECT_ID=""
TEAMS_DIR="$(dirname "$0")/../teams"

while [[ $# -gt 0 ]]; do
  case $1 in
    --platform) PLATFORM="$2"; shift 2 ;;
    --project)  PROJECT_ID="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

case "$PLATFORM" in
  local) BASE_URL="http://localhost:8099" ;;
  azure) BASE_URL="http://4.233.64.30" ;;
  ovh)   BASE_URL="http://54.36.183.124:8090" ;;
  *)     BASE_URL="$PLATFORM" ;;  # allow direct URL
esac

mkdir -p "$TEAMS_DIR"

echo "🔍 Listing teams from $BASE_URL..."

# List existing team templates
TEAMS=$(curl -sf "$BASE_URL/api/teams" 2>/dev/null || echo "[]")
echo "   Saved templates: $(echo "$TEAMS" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(len(d))')"

if [[ -n "$PROJECT_ID" ]]; then
  # Export specific project team
  echo "📦 Exporting team for project: $PROJECT_ID"
  FILENAME="${PROJECT_ID}.yaml"
  curl -sf "$BASE_URL/api/teams/export?project_id=${PROJECT_ID}&name=${PROJECT_ID}" \
    -o "$TEAMS_DIR/$FILENAME"
  echo "   ✅ Saved to teams/$FILENAME"
else
  # Export all projects with agent assignments
  echo "📦 Exporting all project teams..."
  PROJECTS=$(curl -sf "$BASE_URL/api/projects" 2>/dev/null | \
    python3 -c 'import json,sys; [print(p["id"]) for p in json.load(sys.stdin)]' 2>/dev/null || echo "")

  COUNT=0
  for proj_id in $PROJECTS; do
    RESULT=$(curl -sf "$BASE_URL/api/teams/export?project_id=${proj_id}&name=${proj_id}" 2>/dev/null || echo "")
    # Only save if it has agents
    AGENT_COUNT=$(echo "$RESULT" | python3 -c 'import yaml,sys; d=yaml.safe_load(sys.stdin.read()); print(len(d.get("agents",[]) if d else []))' 2>/dev/null || echo "0")
    if [[ "$AGENT_COUNT" -gt "0" ]]; then
      echo "$RESULT" > "$TEAMS_DIR/${proj_id}.yaml"
      echo "   ✅ $proj_id — $AGENT_COUNT agents"
      COUNT=$((COUNT+1))
    fi
  done
  echo "   Exported $COUNT teams"
fi

# Optionally commit to git
if [[ -n "$(git -C "$(dirname "$0")/.." status --short teams/ 2>/dev/null)" ]]; then
  echo ""
  echo "📝 Git changes detected in teams/"
  git -C "$(dirname "$0")/.." diff --stat teams/ | head -10
  echo ""
  read -p "Commit these team exports? [y/N] " CONFIRM
  if [[ "$CONFIRM" == "y" || "$CONFIRM" == "Y" ]]; then
    git -C "$(dirname "$0")/.." add teams/
    git -C "$(dirname "$0")/.." commit --no-verify -m "feat(teams): export team templates from ${PLATFORM}

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
    echo "✅ Committed!"
  fi
fi
