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


# ── Markdown rendering for streamed content ──

def render_md(text: str) -> str:
    """Render markdown text for terminal: tables, headers, bold, lists."""
    lines = text.split("\n")
    out_lines = []
    i = 0
    while i < len(lines):
        # Detect markdown table (row starting with |)
        if lines[i].strip().startswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            out_lines.append(_render_md_table(table_lines))
            continue
        out_lines.append(_render_md_line(lines[i]))
        i += 1
    return "\n".join(out_lines)


def _render_md_table(lines: list[str]) -> str:
    """Render a markdown table with aligned columns and box drawing."""
    # Parse cells
    rows = []
    sep_idx = -1
    for idx, line in enumerate(lines):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and all(c.replace("-", "").replace(":", "") == "" for c in cells):
            sep_idx = idx
            continue
        rows.append(cells)
    if not rows:
        return "\n".join(lines)

    # Normalize column count
    n_cols = max(len(r) for r in rows)
    for r in rows:
        while len(r) < n_cols:
            r.append("")

    # Apply inline markdown to cells
    for r in rows:
        for j in range(len(r)):
            r[j] = _render_md_inline(r[j])

    # Compute column widths (on stripped text)
    widths = [0] * n_cols
    for r in rows:
        for j, cell in enumerate(r):
            widths[j] = max(widths[j], len(_strip_ansi(cell)))

    # Render
    result = []
    # Top border
    top = "  ┌" + "┬".join("─" * (w + 2) for w in widths) + "┐"
    result.append(dim(top))

    for ri, r in enumerate(rows):
        parts = []
        for j, cell in enumerate(r):
            raw_len = len(_strip_ansi(cell))
            pad = widths[j] - raw_len
            parts.append(f" {cell}{' ' * pad} ")
        line = dim("  │") + dim("│").join(parts) + dim("│")
        result.append(line)
        # Header separator after first row
        if ri == 0 and len(rows) > 1:
            sep = "  ├" + "┼".join("─" * (w + 2) for w in widths) + "┤"
            result.append(dim(sep))

    # Bottom border
    bot = "  └" + "┴".join("─" * (w + 2) for w in widths) + "┘"
    result.append(dim(bot))
    return "\n".join(result)


def _render_md_inline(text: str) -> str:
    """Render inline markdown: **bold**, `code`, *italic*."""
    import re
    # Bold **text**
    text = re.sub(r'\*\*(.+?)\*\*', lambda m: bold(m.group(1)), text)
    # Code `text`
    text = re.sub(r'`([^`]+)`', lambda m: c(m.group(1), _CYAN), text)
    # Italic *text* (but not inside bold)
    text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', lambda m: c(m.group(1), _DIM), text)
    return text


def _render_md_line(line: str) -> str:
    """Render a single markdown line: headers, bullets, hr."""
    stripped = line.strip()
    # Headers
    if stripped.startswith("### "):
        return "  " + bold(stripped[4:])
    if stripped.startswith("## "):
        return "\n  " + c(stripped[3:], _BOLD + _MAGENTA)
    if stripped.startswith("# "):
        return "\n  " + c(stripped[2:], _BOLD + _CYAN)
    # Horizontal rule
    if stripped in ("---", "***", "___"):
        tw = _term_width()
        return "  " + dim("─" * min(tw - 4, 60))
    # Bullets
    if stripped.startswith("- ") or stripped.startswith("* "):
        return "  • " + _render_md_inline(stripped[2:])
    # Numbered lists
    import re
    m = re.match(r'^(\d+)\.\s+(.+)', stripped)
    if m:
        return f"  {dim(m.group(1) + '.')} {_render_md_inline(m.group(2))}"
    return _render_md_inline(line)
