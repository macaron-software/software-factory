"""
Tool utilities — shared helpers for all platform tools.
"""

import shutil
import subprocess
from typing import Any

# rtk (Rust Token Killer) — if installed, wrap CLI commands to reduce LLM token output
# https://github.com/rtk-ai/rtk
_RTK_BIN = shutil.which("rtk")


def rtk_wrap(cmd: list[str]) -> list[str]:
    """Prepend rtk to a command list if rtk is available in PATH."""
    if _RTK_BIN and cmd:
        return [_RTK_BIN] + cmd
    return cmd


def rtk_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
    """Drop-in for subprocess.run that wraps with rtk and tracks byte savings.

    Runs the raw command first to measure baseline, then re-runs with rtk for
    the compressed output. Tracks savings in MetricsCollector.
    Only applies when rtk is installed AND stdout is captured.

    Usage:
        result = rtk_run(["git", "--no-pager", "diff"],
                         capture_output=True, text=True, cwd=cwd, timeout=30)
        return result.stdout
    """
    capture = kwargs.get("capture_output") or (kwargs.get("stdout") == subprocess.PIPE)

    if not _RTK_BIN or not capture:
        return subprocess.run(cmd, **kwargs)

    # Run raw command to measure baseline
    raw = subprocess.run(cmd, **kwargs)
    raw_out = raw.stdout or ""
    bytes_raw = len(raw_out.encode() if isinstance(raw_out, str) else raw_out)

    if not bytes_raw:
        return raw

    # Run rtk-wrapped version for compressed output
    try:
        rtk = subprocess.run([_RTK_BIN] + cmd, **kwargs)
        rtk_out = rtk.stdout or ""
        bytes_compressed = len(
            rtk_out.encode() if isinstance(rtk_out, str) else rtk_out
        )

        try:
            from ..metrics.collector import get_collector

            get_collector().track_rtk_call(bytes_raw, bytes_compressed)
        except Exception:
            pass

        return rtk
    except Exception:
        return raw
