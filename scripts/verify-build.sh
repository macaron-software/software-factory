#!/usr/bin/env bash
set -euo pipefail

LOG_DIR=logs
mkdir -p "$LOG_DIR"
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
LOGFILE="$LOG_DIR/verify-build-$TIMESTAMP.log"
exec > >(tee -a "$LOGFILE") 2>&1

function die { echo "$1"; exit "$2"; }

command -v npm >/dev/null 2>&1 || die "npm not found" 2

MAX_RETRIES=2
RETRY_DELAY=3

retry_npm_ci() {
  local i=0
  while true; do
    if npm ci; then
      return 0
    fi
    if [ $i -ge $MAX_RETRIES ]; then
      return 1
    fi
    i=$((i+1))
    sleep $((RETRY_DELAY * i))
  done
}

if ! retry_npm_ci; then
  tail -n 200 "$LOGFILE" || true
  die "npm ci failed after retries" 3
fi

# build with timeout if available
BUILD_TIMEOUT=300
if command -v timeout >/dev/null 2>&1; then
  if ! timeout "$BUILD_TIMEOUT" npm run build; then
    tail -n 200 "$LOGFILE" || true
    die "build failed or timed out" 4
  fi
else
  if ! npm run build; then
    tail -n 200 "$LOGFILE" || true
    die "build failed" 4
  fi
fi

# tests
TEST_TIMEOUT=300
if command -v timeout >/dev/null 2>&1; then
  if ! timeout "$TEST_TIMEOUT" npm test; then
    tail -n 200 "$LOGFILE" || true
    die "tests failed or timed out" 5
  fi
else
  if ! npm test; then
    tail -n 200 "$LOGFILE" || true
    die "tests failed" 5
  fi
fi

echo "Verification succeeded"
exit 0
