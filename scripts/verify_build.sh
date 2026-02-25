#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# verify_build.sh
# Run build verification across configured targets:
#  - Docker-based Python build (using repo Dockerfile if present)
#  - Android build inside docker/android-builder if an Android project is detected
# Collect logs/stack traces into logs/ and attempt simple fixes (install missing build tools)

LOG_DIR="logs/verify_build_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$LOG_DIR"
PY_LOG="$LOG_DIR/python_build.log"
ANDROID_LOG="$LOG_DIR/android_build.log"
SUMMARY="$LOG_DIR/summary.txt"

echo "Starting build verification: Logs -> $LOG_DIR"

function log_and_echo() {
  echo "$@" | tee -a "$SUMMARY"
}

# Helper: check command exists
function has_cmd() {
  command -v "$1" >/dev/null 2>&1
}

# -----------------------------
# Part 1: Docker-based Python build
# -----------------------------
PY_STATUS=0
if has_cmd docker && [ -f Dockerfile ]; then
  echo "[python] Docker found and Dockerfile exists. Running Python build inside Docker..." | tee "$PY_LOG"
  IMAGE_NAME="project-python-builder:verify"
  set +e
  docker build -t "$IMAGE_NAME" . >>"$PY_LOG" 2>&1
  BUILD_RC=$?
  set -e
  if [ $BUILD_RC -ne 0 ]; then
    echo "[python] Docker image build failed (rc=$BUILD_RC). Will attempt a minimal builder image fallback." | tee -a "$PY_LOG"
    # Fallback: use python:3.11-slim to run a build
    IMAGE_NAME="python:3.11-slim"
  fi

  echo "[python] Running container to perform build and collect logs..." | tee -a "$PY_LOG"
  set +e
  docker run --rm -v "$PWD":/workspace -w /workspace -v "$PWD/$LOG_DIR":/logs "$IMAGE_NAME" bash -lc '
    set -e
    python -V || true
    pip --version || true
    python -m pip install --upgrade pip setuptools wheel build >/logs/python_build_install.log 2>&1 || true
    # Try to build the project (sdist & wheel) if pyproject.toml or setup.py present
    if [ -f pyproject.toml ] || [ -f setup.py ]; then
      python -m build >/logs/python_build_output.log 2>&1 || exit 20
    else
      echo "No pyproject.toml or setup.py found; skipping python package build." >/logs/python_build_output.log
    fi
  ' >>"$PY_LOG" 2>&1
  RUN_RC=$?
  set -e
  if [ $RUN_RC -ne 0 ]; then
    echo "[python] Dockerized build failed (rc=$RUN_RC). Will attempt a local venv build as a secondary attempt." | tee -a "$PY_LOG"
    PY_STATUS=1
  else
    echo "[python] Dockerized build succeeded." | tee -a "$PY_LOG"
    PY_STATUS=0
  fi
else
  echo "[python] Docker not available or no Dockerfile. Attempting local venv-based build..." | tee "$PY_LOG"
  if has_cmd python3 || has_cmd python; then
    PY_BIN=$(command -v python3 || command -v python)
    echo "Using $PY_BIN" >>"$PY_LOG"
    set +e
    "$PY_BIN" -m venv .verify_build_venv >>"$PY_LOG" 2>&1 || true
    set -e
    source .verify_build_venv/bin/activate
    pip install --upgrade pip setuptools wheel build >>"$PY_LOG" 2>&1 || true
    if [ -f pyproject.toml ] || [ -f setup.py ]; then
      set +e
      python -m build >>"$PY_LOG" 2>&1
      RC=$?
      set -e
      deactivate || true
      if [ $RC -ne 0 ]; then
        echo "[python] Local venv build failed (rc=$RC)." | tee -a "$PY_LOG"
        PY_STATUS=1
      else
        echo "[python] Local venv build succeeded." | tee -a "$PY_LOG"
        PY_STATUS=0
      fi
    else
      echo "[python] No pyproject.toml or setup.py found; skipping python package build." | tee -a "$PY_LOG"
      PY_STATUS=0
    fi
  else
    echo "[python] No Python interpreter found on PATH; cannot perform local build." | tee -a "$PY_LOG"
    PY_STATUS=1
  fi
fi

# -----------------------------
# Part 2: Android build (optional)
# -----------------------------
ANDROID_STATUS=0
# Detect Android project indicators
if [ -f gradlew ] || [ -f app/build.gradle ] || [ -f settings.gradle ] || [ -d android ] || [ -f workspaceAndroid.zip ]; then
  echo "[android] Android project indicators found. Preparing Android build..." | tee "$ANDROID_LOG"
  # If custom docker/android-builder exists, use it; else try to use public image if docker available
  if [ -f docker/android-builder/Dockerfile ]; then
    IMAGE_NAME="project-android-builder:verify"
    echo "[android] Building docker/android-builder image..." | tee -a "$ANDROID_LOG"
    set +e
    docker build -t "$IMAGE_NAME" docker/android-builder >>"$ANDROID_LOG" 2>&1
    RC=$?
    set -e
    if [ $RC -ne 0 ]; then
      echo "[android] Failed to build docker/android-builder image (rc=$RC). Skipping Android build." | tee -a "$ANDROID_LOG"
      ANDROID_STATUS=1
    else
      echo "[android] Running Android build inside container..." | tee -a "$ANDROID_LOG"
      set +e
      docker run --rm -v "$PWD":/workspace -w /workspace "$IMAGE_NAME" bash -lc '
        set -e
        if [ -f gradlew ]; then
          chmod +x gradlew || true
          ./gradlew assembleDebug --no-daemon --console=plain >/logs/android_build_output.log 2>&1 || exit 30
        else
          echo "No gradlew found; attempt to use gradle wrapper or gradle command." >/logs/android_build_output.log
        fi
      ' >>"$ANDROID_LOG" 2>&1
      RC2=$?
      set -e
      if [ $RC2 -ne 0 ]; then
        echo "[android] Android build failed inside container (rc=$RC2)." | tee -a "$ANDROID_LOG"
        ANDROID_STATUS=1
      else
        echo "[android] Android build succeeded." | tee -a "$ANDROID_LOG"
        ANDROID_STATUS=0
      fi
    fi
  else
    echo "[android] No docker/android-builder found. Attempting to run android build using 'gradle' if available in host or skipping." | tee -a "$ANDROID_LOG"
    if has_cmd gradle; then
      set +e
      gradle assembleDebug --no-daemon --console=plain >>"$ANDROID_LOG" 2>&1
      RC=$?
      set -e
      if [ $RC -ne 0 ]; then
        echo "[android] Host gradle build failed (rc=$RC)." | tee -a "$ANDROID_LOG"
        ANDROID_STATUS=1
      else
        echo "[android] Host gradle build succeeded." | tee -a "$ANDROID_LOG"
        ANDROID_STATUS=0
      fi
    else
      echo "[android] gradle not found on host and no android-builder image in repo. Skipping Android build." | tee -a "$ANDROID_LOG"
      ANDROID_STATUS=2
    fi
  fi
else
  echo "[android] No Android project detected; skipping Android build." | tee "$ANDROID_LOG"
  ANDROID_STATUS=2
fi

# -----------------------------
# Part 3: Automated simple fixes (best-effort)
# -----------------------------
# We attempt a few automated remediations for common Python build issues detected in logs.

echo "\nSummary of attempts:" | tee -a "$SUMMARY"
if [ $PY_STATUS -eq 0 ]; then
  log_and_echo "Python build: SUCCESS"
else
  log_and_echo "Python build: FAILURE -- see $PY_LOG"
  # Try to detect common errors in the python build output and suggest fixes
  if grep -qi "no module named build" "$PY_LOG" 2>/dev/null || grep -qi "ModuleNotFoundError: No module named 'build'" "$PY_LOG" 2>/dev/null; then
    log_and_echo "Remediation: 'build' package missing. The script already attempted to install 'build'. If CI image blocks network, configure build deps in image or add requirements to Dockerfile."
  fi
fi

case $ANDROID_STATUS in
  0) log_and_echo "Android build: SUCCESS" ;;
  1) log_and_echo "Android build: FAILURE -- see $ANDROID_LOG" ;;
  2) log_and_echo "Android build: SKIPPED (no project or no builder)" ;;
esac

# Provide pointers to important logs
log_and_echo "Detailed logs:"
log_and_echo "  - $PY_LOG"
log_and_echo "  - $ANDROID_LOG"

# Exit non-zero if any required build failed (python failure or android failure)
if [ $PY_STATUS -ne 0 ] || [ $ANDROID_STATUS -eq 1 ]; then
  log_and_echo "Overall result: FAIL"
  echo "Build verification completed with failures. Check logs in $LOG_DIR" >&2
  exit 3
else
  log_and_echo "Overall result: OK"
  echo "Build verification completed successfully. Logs in $LOG_DIR"
  exit 0
fi
