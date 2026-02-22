"""CLI output formatting — tables, colors, JSON mode."""
import json
import os
import sys
from typing import Any

NO_COLOR = os.environ.get("NO_COLOR") or "--no-color" in sys.argv

# ANSI codes
_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RED = "\033[31m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_BLUE = "\033[34m"
_MAGENTA = "\033[35m"
_CYAN = "\033[36m"
_WHITE = "\033[37m"

# Agent color palette (rotating)
AGENT_COLORS = [_CYAN, _MAGENTA, _YELLOW, _GREEN, _BLUE, _RED]
_agent_color_map: dict[str, str] = {}


def c(text: str, code: str) -> str:
    if NO_COLOR:
        return text
    return f"{code}{text}{_RESET}"


def bold(t: str) -> str: return c(t, _BOLD)
def dim(t: str) -> str: return c(t, _DIM)
def red(t: str) -> str: return c(t, _RED)
def green(t: str) -> str: return c(t, _GREEN)
def yellow(t: str) -> str: return c(t, _YELLOW)
def blue(t: str) -> str: return c(t, _BLUE)
def magenta(t: str) -> str: return c(t, _MAGENTA)
def cyan(t: str) -> str: return c(t, _CYAN)


def agent_color(agent_name: str) -> str:
    """Get consistent color for an agent name."""
    if agent_name not in _agent_color_map:
        idx = len(_agent_color_map) % len(AGENT_COLORS)
        _agent_color_map[agent_name] = AGENT_COLORS[idx]
    return _agent_color_map[agent_name]


def status_color(status: str) -> str:
    """Colorize status strings."""
    s = (status or "").lower()
    if s in ("ok", "running", "active", "done", "completed", "healthy", "success"):
        return green(status)
    if s in ("error", "failed", "critical", "p0", "dead"):
        return red(status)
    if s in ("pending", "queued", "waiting", "blocked", "warning"):
        return yellow(status)
    if s in ("in_progress", "started", "working"):
        return blue(status)
    return status


def table(rows: list[dict], columns: list[str] | None = None, max_width: int = 0) -> str:
    """Render a list of dicts as aligned columns."""
    if not rows:
        return dim("(empty)")
    if columns is None:
        columns = list(rows[0].keys())
    # compute column widths
    widths = {col: len(col) for col in columns}
    str_rows = []
    for row in rows:
        sr = {}
        for col in columns:
            val = row.get(col, "")
            if val is None:
                val = ""
            s = str(val)
            if col == "status":
                sr[col] = status_color(s)
                widths[col] = max(widths[col], len(s))
            else:
                sr[col] = s
                widths[col] = max(widths[col], len(s))
        str_rows.append(sr)
    # truncate if needed
    term_w = max_width or _term_width()
    if term_w > 0:
        total = sum(widths[c] for c in columns) + (len(columns) - 1) * 3
        if total > term_w:
            # shrink last column
            excess = total - term_w
            last_col = columns[-1]
            widths[last_col] = max(5, widths[last_col] - excess)
    # header
    hdr = "  ".join(bold(col.upper().ljust(widths[col])) for col in columns)
    sep = "  ".join("─" * widths[col] for col in columns)
    lines = [hdr, sep]
    for sr in str_rows:
        parts = []
        for col in columns:
            val = sr[col]
            raw = _strip_ansi(val)
            pad = widths[col] - len(raw)
            if pad < 0:
                val = raw[:widths[col]-1] + "…"
                pad = 0
            parts.append(val + " " * pad)
        lines.append("  ".join(parts))
    return "\n".join(lines)


def kv(data: dict, keys: list[str] | None = None) -> str:
    """Key-value display."""
    if keys is None:
        keys = list(data.keys())
    max_k = max((len(k) for k in keys), default=0)
    lines = []
    for k in keys:
        v = data.get(k, "")
        if k == "status":
            v = status_color(str(v))
        label = bold(k.ljust(max_k))
        lines.append(f"  {label}  {v}")
    return "\n".join(lines)


def out_json(data: Any) -> None:
    """Print raw JSON to stdout."""
    print(json.dumps(data, indent=2, default=str, ensure_ascii=False))


def info(msg: str) -> None:
    print(f"{green('✓')} {msg}", file=sys.stderr)


def warn(msg: str) -> None:
    print(f"{yellow('⚠')} {msg}", file=sys.stderr)


def error(msg: str) -> None:
    print(f"{red('✗')} {msg}", file=sys.stderr)


def _term_width() -> int:
    try:
        return os.get_terminal_size().columns
    except (ValueError, OSError):
        return 120


def _strip_ansi(s: str) -> str:
    import re
    return re.sub(r'\033\[[0-9;]*m', '', s)
