"""
Convert platform content to Confluence storage format (XHTML).
Handles: markdown, tables, agent messages, features kanban, SVG graphs, mermaid.
"""
from __future__ import annotations

import html
import re
from typing import Optional


# ── Markdown → Confluence XHTML ────────────────────────────────

def md_to_confluence(md: str) -> str:
    """Convert markdown to Confluence storage format XHTML."""
    if not md:
        return ""
    # Strip emoji (Confluence XHTML rejects them)
    md = re.sub(r'[\U0001F300-\U0001FFFF\u2700-\u27BF\u2600-\u26FF\u2300-\u23FF\u2B50\u2B55\u2934\u2935\u25AA-\u25FF\u2190-\u21FF\u200D\uFE0F]', '', md)
    lines = md.split("\n")
    out = []
    in_code = False
    code_lang = ""
    code_lines: list[str] = []
    in_list = False

    for line in lines:
        # Fenced code blocks
        if line.strip().startswith("```"):
            if in_code:
                out.append(_code_macro(code_lang, "\n".join(code_lines)))
                code_lines = []
                in_code = False
                continue
            else:
                if in_list:
                    in_list = False
                code_lang = line.strip()[3:].strip()
                in_code = True
                continue
        if in_code:
            code_lines.append(line)
            continue

        # Close list if needed
        if in_list and not line.strip().startswith(("- ", "* ", "1.")):
            out.append("</ul>")
            in_list = False

        # Headers
        if m := re.match(r'^(#{1,6})\s+(.+)$', line):
            level = len(m.group(1))
            out.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
            continue

        # List items
        if m := re.match(r'^\s*[-*]\s+(.+)$', line):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline(m.group(1))}</li>")
            continue

        # Table rows
        if "|" in line and line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(re.match(r'^[-:]+$', c) for c in cells):
                continue  # separator row
            row = "".join(f"<td>{_inline(c)}</td>" for c in cells)
            out.append(f"<tr>{row}</tr>")
            continue

        # Empty line
        if not line.strip():
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append("")
            continue

        # Paragraph
        out.append(f"<p>{_inline(line)}</p>")

    if in_list:
        out.append("</ul>")
    if in_code:
        out.append(_code_macro(code_lang, "\n".join(code_lines)))

    # Wrap table rows
    result = "\n".join(out)
    result = _wrap_tables(result)
    return result


def _inline(text: str) -> str:
    """Convert inline markdown (bold, italic, code, links)."""
    t = re.sub(r'[\U0001F300-\U0001FFFF\u2700-\u27BF\u2600-\u26FF\u2300-\u23FF\u2B50\u2B55\u2934\u2935\u25AA-\u25FF\u2190-\u21FF\u200D\uFE0F]', '', text)
    t = html.escape(t)
    t = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', t)
    t = re.sub(r'\*(.+?)\*', r'<em>\1</em>', t)
    t = re.sub(r'`(.+?)`', r'<code>\1</code>', t)
    t = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', t)
    return t


def _code_macro(lang: str, code: str) -> str:
    """Confluence code block macro."""
    lang_attr = f'<ac:parameter ac:name="language">{lang}</ac:parameter>' if lang else ""
    return (
        f'<ac:structured-macro ac:name="code">'
        f'{lang_attr}'
        f'<ac:plain-text-body><![CDATA[{code}]]></ac:plain-text-body>'
        f'</ac:structured-macro>'
    )


def _wrap_tables(xhtml: str) -> str:
    """Wrap consecutive <tr> into <table>."""
    lines = xhtml.split("\n")
    out = []
    in_table = False
    for line in lines:
        if "<tr>" in line and not in_table:
            out.append("<table><tbody>")
            in_table = True
        elif "<tr>" not in line and in_table:
            out.append("</tbody></table>")
            in_table = False
        out.append(line)
    if in_table:
        out.append("</tbody></table>")
    return "\n".join(out)


# ── Structured content converters ──────────────────────────────

def features_to_confluence(features: list[dict]) -> str:
    """Convert features list to Confluence table."""
    if not features:
        return "<p><em>Aucune feature définie.</em></p>"

    status_colors = {
        "backlog": "#6B7280", "sprint": "#3B82F6",
        "in_progress": "#F59E0B", "done": "#10B981",
        "blocked": "#EF4444",
    }

    rows = []
    rows.append("<tr><th>Feature</th><th>Status</th><th>Points</th><th>Priorité</th><th>Description</th></tr>")
    for f in features:
        status = f.get("status", "backlog")
        color = status_colors.get(status, "#6B7280")
        rows.append(
            f'<tr>'
            f'<td><strong>{html.escape(f.get("name", ""))}</strong></td>'
            f'<td><ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">{_status_confluence_color(status)}</ac:parameter><ac:parameter ac:name="title">{html.escape(status)}</ac:parameter></ac:structured-macro></td>'
            f'<td>{f.get("story_points", 0)}</td>'
            f'<td>{f.get("priority", 5)}</td>'
            f'<td>{html.escape(f.get("description", ""))}</td>'
            f'</tr>'
        )

    return f'<table><tbody>{"".join(rows)}</tbody></table>'


def _status_confluence_color(status: str) -> str:
    """Map status to Confluence status macro color."""
    return {
        "backlog": "Grey", "sprint": "Blue",
        "in_progress": "Yellow", "done": "Green",
        "blocked": "Red",
    }.get(status, "Grey")


def messages_to_confluence(messages: list[dict], title: str = "") -> str:
    """Convert agent messages to formatted discussion thread."""
    if not messages:
        return "<p><em>Aucune discussion.</em></p>"

    parts = []
    if title:
        parts.append(f"<h3>{html.escape(title)}</h3>")

    for msg in messages:
        sender = msg.get("sender_name", msg.get("sender_id", "Agent"))
        role = msg.get("role", "")
        content = msg.get("content", "")
        # Clean LLM artifacts
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        content = re.sub(r'\[TOOL_CALL\].*?\[/TOOL_CALL\]', '', content, flags=re.DOTALL)
        content = re.sub(r'\[DELEGATE:.*?\]', '', content)

        role_badge = f" — <em>{html.escape(role)}</em>" if role else ""
        parts.append(
            f'<ac:structured-macro ac:name="panel">'
            f'<ac:parameter ac:name="title">{html.escape(sender)}{role_badge}</ac:parameter>'
            f'<ac:rich-text-body>{md_to_confluence(content.strip())}</ac:rich-text-body>'
            f'</ac:structured-macro>'
        )

    return "\n".join(parts)


def test_results_to_confluence(test_files: list[dict]) -> str:
    """Convert test results to Confluence table."""
    if not test_files:
        return "<p><em>Aucun test.</em></p>"

    rows = ['<tr><th>Fichier</th><th>Type</th><th>Status</th></tr>']
    for t in test_files:
        name = html.escape(t.get("name", t.get("path", "")))
        ttype = html.escape(t.get("type", "unit"))
        status = t.get("status", "pending")
        color = "Green" if status == "pass" else ("Red" if status == "fail" else "Grey")
        rows.append(
            f'<tr><td><code>{name}</code></td><td>{ttype}</td>'
            f'<td><ac:structured-macro ac:name="status">'
            f'<ac:parameter ac:name="colour">{color}</ac:parameter>'
            f'<ac:parameter ac:name="title">{html.escape(status)}</ac:parameter>'
            f'</ac:structured-macro></td></tr>'
        )

    return f'<table><tbody>{"".join(rows)}</tbody></table>'


def svg_to_confluence_attachment(svg_content: str, filename: str = "graph.svg") -> str:
    """Return XHTML macro that references an SVG attachment."""
    return (
        f'<ac:image ac:width="800">'
        f'<ri:attachment ri:filename="{html.escape(filename)}" />'
        f'</ac:image>'
    )


def graph_to_svg(nodes: list[dict], edges: list[dict], title: str = "") -> str:
    """Generate SVG from workflow graph data (nodes + edges)."""
    if not nodes:
        return ""

    # Calculate viewBox from node positions
    xs = [n.get("x", 0) for n in nodes]
    ys = [n.get("y", 0) for n in nodes]
    min_x, max_x = min(xs) - 40, max(xs) + 200
    min_y, max_y = min(ys) - 40, max(ys) + 80
    w = max_x - min_x + 80
    h = max_y - min_y + 80

    # Build node lookup
    node_map = {n["id"]: n for n in nodes}

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{min_x} {min_y} {w} {h}" '
        f'width="{w}" height="{h}" style="font-family:sans-serif;background:#1a1128">',
        '<defs>',
        '<marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">',
        '<path d="M 0 0 L 10 5 L 0 10 z" fill="#666"/></marker>',
        '</defs>',
    ]

    if title:
        parts.append(f'<text x="{min_x + 10}" y="{min_y + 20}" fill="#c084fc" font-size="14" font-weight="bold">{html.escape(title)}</text>')

    # Draw edges
    for edge in edges:
        src = node_map.get(edge["from"])
        dst = node_map.get(edge["to"])
        if not src or not dst:
            continue
        x1, y1 = src["x"] + 70, src["y"] + 25
        x2, y2 = dst["x"] + 70, dst["y"] + 25
        color = edge.get("color", "#666")
        label = edge.get("label", "")
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1.5" marker-end="url(#arrow)" opacity="0.7"/>')
        if label:
            parts.append(f'<text x="{mx}" y="{my - 4}" fill="{color}" font-size="8" text-anchor="middle" opacity="0.9">{html.escape(label)}</text>')

    # Draw nodes
    for n in nodes:
        x, y = n["x"], n["y"]
        label = n.get("label", n.get("agent_id", "?"))
        parts.append(f'<rect x="{x}" y="{y}" width="140" height="50" rx="8" fill="#251a35" stroke="#7c3aed" stroke-width="1.5"/>')
        parts.append(f'<text x="{x + 70}" y="{y + 20}" fill="#e2e8f0" font-size="10" text-anchor="middle" font-weight="bold">{html.escape(label)}</text>')
        agent_id = n.get("agent_id", "")
        if agent_id:
            parts.append(f'<text x="{x + 70}" y="{y + 35}" fill="#a78bfa" font-size="7" text-anchor="middle">{html.escape(agent_id)}</text>')

    parts.append('</svg>')
    return "\n".join(parts)


def mermaid_to_confluence(mermaid_code: str) -> str:
    """Convert mermaid diagram to Confluence code block (viewable with Mermaid plugin)."""
    return _code_macro("mermaid", mermaid_code)


# ── Info/warning/note macros ───────────────────────────────────

def info_macro(title: str, body: str) -> str:
    return (
        f'<ac:structured-macro ac:name="info">'
        f'<ac:parameter ac:name="title">{html.escape(title)}</ac:parameter>'
        f'<ac:rich-text-body>{body}</ac:rich-text-body>'
        f'</ac:structured-macro>'
    )


def warning_macro(title: str, body: str) -> str:
    return (
        f'<ac:structured-macro ac:name="warning">'
        f'<ac:parameter ac:name="title">{html.escape(title)}</ac:parameter>'
        f'<ac:rich-text-body>{body}</ac:rich-text-body>'
        f'</ac:structured-macro>'
    )


def toc_macro() -> str:
    """Table of contents macro."""
    return '<ac:structured-macro ac:name="toc" />'


def page_header(title: str, mission_name: str, project: str, synced_at: str) -> str:
    """Standard page header with metadata."""
    return (
        f'<h1>{html.escape(title)}</h1>'
        f'{info_macro("Sync automatique", f"<p>Epic: <strong>{html.escape(mission_name)}</strong> | Projet: <strong>{html.escape(project)}</strong> | Dernière sync: {html.escape(synced_at)}</p>")}'
        f'{toc_macro()}'
    )
