#!/bin/bash
# launch_browser.sh — Lance le vrai Chrome avec CDP sur port 18800
# Usage: ./scrapers/launch_browser.sh
#
# Pourquoi le vrai Chrome ?
#   - Chrome for Testing → TLS fingerprint détecté par Crédit Agricole (ERR_CONNECTION_RESET)
#   - Chrome for Testing → SwiftShader GPU → 200%+ CPU
#   - Vrai Chrome → fingerprint standard, GPU natif, CA fonctionne
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$DIR")"
STATE_DIR="$PROJECT_DIR/scrapers/data/.browser_state"
PORT=18800

# Check if already running
if curl -s "http://localhost:$PORT/json" > /dev/null 2>&1; then
    TABS=$(curl -s "http://localhost:$PORT/json" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null)
    echo "✅ Chrome already running on :$PORT ($TABS tabs)"
    echo "   CDP: http://localhost:$PORT"
    exit 0
fi

# Clean stale locks
rm -f "$STATE_DIR/SingletonLock" 2>/dev/null
rm -f "$STATE_DIR/SingletonSocket" 2>/dev/null
rm -f "$STATE_DIR/SingletonCookie" 2>/dev/null

echo "🚀 Launching Chrome on :$PORT..."

# Bank URLs to open
BANKS=(
    "https://www.credit-agricole.fr/ca-languedoc/particulier/acceder-a-mes-comptes.html"
    "https://clients.boursobank.com/"
    "https://www.interactivebrokers.ie/sso/Login"
    "https://app.traderepublic.com/"
)

open -n -a "Google Chrome" --args \
    --remote-debugging-port=$PORT \
    --user-data-dir="$STATE_DIR" \
    --no-first-run \
    --no-default-browser-check \
    --disable-sync \
    --lang=fr-FR \
    "${BANKS[@]}"

# Wait for CDP to be ready
echo -n "   Waiting for CDP..."
for i in $(seq 1 15); do
    if curl -s "http://localhost:$PORT/json" > /dev/null 2>&1; then
        echo " ready!"
        break
    fi
    echo -n "."
    sleep 1
done

if curl -s "http://localhost:$PORT/json" > /dev/null 2>&1; then
    TABS=$(curl -s "http://localhost:$PORT/json" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null)
    echo "✅ Chrome running on :$PORT ($TABS tabs)"
    echo ""
    echo "📋 Login to each bank tab, then run:"
    echo "   ./start.sh"
else
    echo ""
    echo "❌ Chrome didn't start on :$PORT"
    echo "   Try launching manually:"
    echo "   open -n -a 'Google Chrome' --args --remote-debugging-port=$PORT --user-data-dir='$STATE_DIR'"
    exit 1
fi
