"""
Tool utilities — shared helpers for all platform tools.
"""

import shutil

# rtk (Rust Token Killer) — if installed, wrap CLI commands to reduce LLM token output
# https://github.com/rtk-ai/rtk
_RTK_BIN = shutil.which("rtk")


def rtk_wrap(cmd: list[str]) -> list[str]:
    """Prepend rtk to a command list if rtk is available in PATH.

    Usage:
        subprocess.run(rtk_wrap(["git", "diff"]), ...)
        subprocess.run(rtk_wrap(["pytest", "tests/"]), ...)
    """
    if _RTK_BIN and cmd:
        return [_RTK_BIN] + cmd
    return cmd
