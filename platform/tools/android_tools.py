"""Android build tools — Gradle build, unit test, emulator test via Docker container.

The android-builder container has JDK 17, Android SDK 35, and a headless emulator AVD.
Platform invokes builds via `docker exec android-builder ...` on the shared workspace volume.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from .registry import BaseTool, ToolRegistry

logger = logging.getLogger(__name__)

CONTAINER = os.environ.get("ANDROID_BUILDER_CONTAINER", "android-builder")


async def _docker_exec(workspace: str, command: str, timeout: int = 600) -> dict:
    """Execute a command in the android-builder container."""
    # Workspace paths: /workspace/workspaces/{mission_id} inside container
    cmd = f"docker exec -w {workspace} {CONTAINER} {command}"
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=dict(os.environ),
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        output = stdout.decode("utf-8", errors="replace") if stdout else ""
        return {
            "success": proc.returncode == 0,
            "exit_code": proc.returncode,
            "output": output[-8000:],  # last 8K chars
        }
    except asyncio.TimeoutError:
        return {"success": False, "exit_code": -1, "output": f"Timeout after {timeout}s"}
    except Exception as e:
        return {"success": False, "exit_code": -1, "output": str(e)}


class AndroidBuildTool(BaseTool):
    name = "android_build"
    description = "Build Android project (assembleDebug) via Gradle in the android-builder container."
    category = "build"

    async def execute(self, params: dict[str, Any], agent: Any = None) -> str:
        workspace = params.get("workspace_path", "/workspace")
        result = await _docker_exec(workspace, "sh -c 'chmod +x gradlew && ./gradlew assembleDebug --no-daemon --console=plain'")
        status = "✅ BUILD SUCCESS" if result["success"] else "❌ BUILD FAILED"
        return f"{status}\n\n{result['output']}"


class AndroidTestTool(BaseTool):
    name = "android_test"
    description = "Run Android unit tests (testDebugUnitTest) via Gradle."
    category = "build"

    async def execute(self, params: dict[str, Any], agent: Any = None) -> str:
        workspace = params.get("workspace_path", "/workspace")
        result = await _docker_exec(workspace, "sh -c 'chmod +x gradlew && ./gradlew testDebugUnitTest --no-daemon --console=plain'")
        status = "✅ TESTS PASSED" if result["success"] else "❌ TESTS FAILED"
        return f"{status}\n\n{result['output']}"


class AndroidLintTool(BaseTool):
    name = "android_lint"
    description = "Run Android Lint checks via Gradle."
    category = "build"

    async def execute(self, params: dict[str, Any], agent: Any = None) -> str:
        workspace = params.get("workspace_path", "/workspace")
        result = await _docker_exec(workspace, "sh -c 'chmod +x gradlew && ./gradlew lintDebug --no-daemon --console=plain'")
        status = "✅ LINT OK" if result["success"] else "⚠️ LINT ISSUES"
        return f"{status}\n\n{result['output']}"


class AndroidEmulatorTestTool(BaseTool):
    name = "android_emulator_test"
    description = "Start headless Android emulator and run instrumented/connected tests. Takes ~2-3 min for emulator boot."
    category = "build"

    async def execute(self, params: dict[str, Any], agent: Any = None) -> str:
        workspace = params.get("workspace_path", "/workspace")
        # Emulator boot + tests can take 5-10 min
        script = """sh -c '
set -e
echo "=== Starting headless emulator ==="
emulator -avd test_avd -no-window -no-audio -no-boot-anim -gpu swiftshader_indirect -no-snapshot -wipe-data &
EPID=$!
echo "Waiting for boot..."
adb wait-for-device
timeout 180 sh -c "while [ \\"$(adb shell getprop sys.boot_completed 2>/dev/null)\\" != \\"1\\" ]; do sleep 3; done"
echo "Emulator booted."
chmod +x gradlew
./gradlew connectedDebugAndroidTest --no-daemon --console=plain 2>&1
EXIT=$?
adb emu kill 2>/dev/null || true
kill $EPID 2>/dev/null || true
exit $EXIT
'"""
        result = await _docker_exec(workspace, script, timeout=900)  # 15 min max
        status = "✅ EMULATOR TESTS PASSED" if result["success"] else "❌ EMULATOR TESTS FAILED"
        return f"{status}\n\n{result['output']}"


def register_android_tools(registry: ToolRegistry):
    """Register Android build tools."""
    registry.register(AndroidBuildTool())
    registry.register(AndroidTestTool())
    registry.register(AndroidLintTool())
    registry.register(AndroidEmulatorTestTool())
