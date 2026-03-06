"""Platform package — local software factory modules.

Exposes `system()` for backward compatibility with:
    import platform; platform.system()
in server.py (RTK history DB path detection).
"""

import sys as _sys


def system() -> str:
    """Return OS type: Darwin, Linux, Windows, or '' (mirrors stdlib platform.system())."""
    s = _sys.platform
    if s == "darwin":
        return "Darwin"
    if s.startswith("linux"):
        return "Linux"
    if s in ("win32", "cygwin"):
        return "Windows"
    return ""
