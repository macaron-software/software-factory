#!/bin/bash
# Android builder entrypoint scripts
# Usage: docker exec android-builder /scripts/build.sh /workspace/mission-id
# Usage: docker exec android-builder /scripts/test.sh /workspace/mission-id
# Usage: docker exec android-builder /scripts/emulator-test.sh /workspace/mission-id

set -euo pipefail

WORKSPACE="${1:-.}"
cd "$WORKSPACE"

case "${0##*/}" in
  build.sh)
    echo "=== Android Build ==="
    if [ -f gradlew ]; then
      chmod +x gradlew
      ./gradlew assembleDebug --no-daemon --console=plain 2>&1
    else
      echo "ERROR: No gradlew found in $WORKSPACE"
      exit 1
    fi
    ;;

  test.sh)
    echo "=== Android Unit Tests ==="
    if [ -f gradlew ]; then
      chmod +x gradlew
      ./gradlew testDebugUnitTest --no-daemon --console=plain 2>&1
    else
      echo "ERROR: No gradlew found in $WORKSPACE"
      exit 1
    fi
    ;;

  emulator-test.sh)
    echo "=== Starting Headless Emulator ==="
    # Start emulator in background (headless, no audio, no window)
    emulator -avd test_avd \
      -no-window -no-audio -no-boot-anim \
      -gpu swiftshader_indirect \
      -no-snapshot \
      -wipe-data &
    EMULATOR_PID=$!

    echo "Waiting for emulator to boot..."
    adb wait-for-device
    # Wait for boot_completed
    timeout 120 bash -c 'while [ "$(adb shell getprop sys.boot_completed 2>/dev/null)" != "1" ]; do sleep 2; done'
    echo "Emulator booted."

    echo "=== Running Instrumented Tests ==="
    chmod +x gradlew
    ./gradlew connectedDebugAndroidTest --no-daemon --console=plain 2>&1
    TEST_EXIT=$?

    echo "=== Stopping Emulator ==="
    adb emu kill 2>/dev/null || true
    kill $EMULATOR_PID 2>/dev/null || true

    exit $TEST_EXIT
    ;;

  lint.sh)
    echo "=== Android Lint ==="
    if [ -f gradlew ]; then
      chmod +x gradlew
      ./gradlew lintDebug --no-daemon --console=plain 2>&1
    fi
    ;;

  *)
    echo "Unknown script: ${0##*/}"
    echo "Available: build.sh, test.sh, emulator-test.sh, lint.sh"
    exit 1
    ;;
esac
