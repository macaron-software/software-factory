#!/usr/bin/env bash
# start-platform.sh — Lance la SF platform locale (port 8099)
# Utilisé par launchd pour auto-start + auto-restart

set -euo pipefail

# Homebrew binaries not in launchd default PATH
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Attendre que PostgreSQL soit prêt (jusqu'à 60s)
for i in $(seq 1 60); do
    if /opt/homebrew/bin/pg_isready -h localhost -p 5434 -q 2>/dev/null; then
        echo "PostgreSQL ready after ${i}s"
        break
    fi
    echo "Waiting for PostgreSQL ($i/60)..."
    sleep 1
done

exec /opt/homebrew/bin/python3 -m uvicorn platform.server:app \
    --host 0.0.0.0 \
    --port 8099 \
    --ws none \
    --log-level warning
