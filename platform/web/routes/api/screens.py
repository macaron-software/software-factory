"""API routes — Annotation Studio (project screens + annotations)."""
# Ref: feat-annotate

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Optional

from fastapi import Depends,  APIRouter, Request
from fastapi.responses import JSONResponse, Response
from ....auth.middleware import require_auth

router = APIRouter()


def _db():
    from ....db.migrations import get_db

    return get_db()


def _screens_dir(project_id: str) -> Path:
    base = Path(__file__).resolve().parents[4] / "data" / "screens" / project_id
    base.mkdir(parents=True, exist_ok=True)
    return base


# ── Wireframe generation ─────────────────────────────────────────


def _html_to_wireframe_svg(html: str, width: int = 1280, height: int = 800) -> str:
    """Convert HTML to a lo-fi wireframe SVG."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return _empty_wireframe_svg(width, height)

    soup = BeautifulSoup(html, "html.parser")

    elements = []
    y = 0

    # Nav/header
    nav = soup.find(["nav", "header"])
    if nav:
        label = nav.get_text(" ", strip=True)[:60] or "Navigation"
        elements.append(("rect", 0, y, width, 56, "#e8e8e8", "#999", label, 14))
        y += 60

    # Main sections
    for tag in soup.find_all(["main", "section", "article", "div"], limit=15):
        cls = " ".join(tag.get("class", []))
        if not cls and not tag.get("id"):
            continue
        section_h = 120
        headings = tag.find_all(["h1", "h2", "h3"], limit=2)
        buttons = tag.find_all("button", limit=4)
        inputs = tag.find_all("input", limit=4)
        imgs = tag.find_all("img", limit=3)

        label = (
            headings[0].get_text(strip=True)[:50]
            if headings
            else (tag.get("id") or cls[:30] or "Section")
        )
        elements.append(
            ("rect", 16, y, width - 32, section_h, "#f8f8f8", "#ccc", label, 13)
        )

        bx = 32
        for btn in buttons:
            btxt = btn.get_text(strip=True)[:20] or "Button"
            elements.append(
                ("btn", bx, y + section_h - 36, 100, 28, "#d0d0d0", "#888", btxt, 12)
            )
            bx += 116

        ix = 32
        for inp in inputs:
            placeholder = inp.get("placeholder", inp.get("name", "Input"))[:20]
            elements.append(
                ("input", ix, y + 40, 180, 28, "#fff", "#bbb", placeholder, 11)
            )
            ix += 196

        for i, img in enumerate(imgs):
            elements.append(
                ("img", 32 + i * 120, y + 50, 100, 70, "#f0f0f0", "#ccc", "", 0)
            )

        y += section_h + 16
        if y > height - 60:
            break

    # Footer
    elements.append(
        ("rect", 0, height - 48, width, 48, "#e8e8e8", "#999", "Footer", 12)
    )

    # Build SVG
    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="white"/>',
    ]

    for elem in elements:
        kind = elem[0]
        x, ey, w, h, fill, stroke, label, fs = (
            elem[1],
            elem[2],
            elem[3],
            elem[4],
            elem[5],
            elem[6],
            elem[7],
            elem[8],
        )
        rx = 4 if kind in ("btn", "input") else 2
        sid = f"el-{uuid.uuid4().hex[:8]}"
        svg_parts.append(
            f'<rect id="{sid}" x="{x}" y="{ey}" width="{w}" height="{h}" rx="{rx}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1" data-label="{label}"/>'
        )
        if kind == "img":
            svg_parts.append(
                f'<line x1="{x}" y1="{ey}" x2="{x + w}" y2="{ey + h}" stroke="{stroke}" stroke-width="1"/>'
            )
            svg_parts.append(
                f'<line x1="{x + w}" y1="{ey}" x2="{x}" y2="{ey + h}" stroke="{stroke}" stroke-width="1"/>'
            )
        elif label and fs > 0:
            ty = ey + h // 2 + fs // 3
            svg_parts.append(
                f'<text x="{x + 8}" y="{ty}" font-family="system-ui,sans-serif" font-size="{fs}" fill="#555" '
                f'clip-path="inset(0)" style="pointer-events:none">{label[:40]}</text>'
            )

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


def _empty_wireframe_svg(width: int = 1280, height: int = 800) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">'
        f'<rect width="{width}" height="{height}" fill="white"/>'
        f'<text x="{width // 2}" y="{height // 2}" text-anchor="middle" fill="#999" font-size="18" font-family="sans-serif">No preview available</text>'
        f"</svg>"
    )


# ── Wireframe endpoint ───────────────────────────────────────────


@router.post("/api/projects/{project_id}/wireframe", dependencies=[Depends(require_auth())])
async def generate_wireframe(project_id: str, request: Request):
    """Generate SVG wireframe from HTML (POST body: {html?: str, url?: str})."""
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    html = body.get("html", "")
    if not html:
        return JSONResponse({"svg": _empty_wireframe_svg()})

    svg = _html_to_wireframe_svg(html)

    # Save to disk
    screens_dir = _screens_dir(project_id)
    page_url = body.get("url", "")
    screen_id = uuid.uuid4().hex
    svg_path = screens_dir / f"{screen_id}.svg"
    svg_path.write_text(svg)

    # Persist screen record
    db = _db()
    name = body.get("name", page_url or "Page")
    db.execute(
        "INSERT OR IGNORE INTO project_screens (id, project_id, name, page_url, svg_path) VALUES (?,?,?,?,?)",
        (screen_id, project_id, name, page_url, str(svg_path)),
    )
    db.commit()

    return JSONResponse({"screen_id": screen_id, "svg": svg})


# ── Screens CRUD ─────────────────────────────────────────────────


@router.get("/api/projects/{project_id}/screens")
async def list_screens(project_id: str):
    db = _db()
    rows = db.execute(
        "SELECT id, name, page_url, svg_path, created_at FROM project_screens WHERE project_id=? ORDER BY created_at DESC",
        (project_id,),
    ).fetchall()
    return JSONResponse([dict(r) for r in rows])


@router.get("/api/projects/{project_id}/screens/{screen_id}/svg")
async def get_screen_svg(project_id: str, screen_id: str):
    db = _db()
    row = db.execute(
        "SELECT svg_path FROM project_screens WHERE id=? AND project_id=?",
        (screen_id, project_id),
    ).fetchone()
    if not row or not row["svg_path"]:
        return Response(_empty_wireframe_svg(), media_type="image/svg+xml")
    p = Path(row["svg_path"])
    if not p.exists():
        return Response(_empty_wireframe_svg(), media_type="image/svg+xml")
    return Response(p.read_text(), media_type="image/svg+xml")


@router.delete("/api/projects/{project_id}/screens/{screen_id}", dependencies=[Depends(require_auth())])
async def delete_screen(project_id: str, screen_id: str):
    db = _db()
    db.execute(
        "DELETE FROM project_screens WHERE id=? AND project_id=?",
        (screen_id, project_id),
    )
    db.execute("DELETE FROM project_annotations WHERE screen_id=?", (screen_id,))
    db.commit()
    return JSONResponse({"ok": True})


# ── Annotations CRUD ─────────────────────────────────────────────


@router.get("/api/projects/{project_id}/annotations")
async def list_annotations(
    project_id: str, screen_id: Optional[str] = None, page_url: Optional[str] = None
):
    db = _db()
    if screen_id:
        rows = db.execute(
            "SELECT * FROM project_annotations WHERE project_id=? AND screen_id=? ORDER BY seq_num",
            (project_id, screen_id),
        ).fetchall()
    elif page_url:
        rows = db.execute(
            "SELECT * FROM project_annotations WHERE project_id=? AND page_url=? ORDER BY seq_num",
            (project_id, page_url),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM project_annotations WHERE project_id=? ORDER BY created_at DESC",
            (project_id,),
        ).fetchall()
    return JSONResponse([dict(r) for r in rows])


@router.post("/api/projects/{project_id}/annotations", dependencies=[Depends(require_auth())])
async def create_annotation(project_id: str, request: Request):
    body = await request.json()
    db = _db()

    # Get next seq_num for this project
    row = db.execute(
        "SELECT COALESCE(MAX(seq_num),0)+1 as n FROM project_annotations WHERE project_id=?",
        (project_id,),
    ).fetchone()
    seq_num = row["n"] if row else 1

    ann_id = uuid.uuid4().hex
    db.execute(
        """INSERT INTO project_annotations
        (id, screen_id, project_id, type, selector, element_text,
         x_pct, y_pct, w_pct, h_pct, from_x_pct, from_y_pct, to_x_pct, to_y_pct,
         page_url, viewport_w, viewport_h, quoted_text, computed_css, react_tree,
         message, status, seq_num)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            ann_id,
            body.get("screen_id", ""),
            project_id,
            body.get("type", "comment"),
            body.get("selector", ""),
            body.get("element_text", ""),
            body.get("x_pct", 0),
            body.get("y_pct", 0),
            body.get("w_pct", 0),
            body.get("h_pct", 0),
            body.get("from_x_pct", 0),
            body.get("from_y_pct", 0),
            body.get("to_x_pct", 0),
            body.get("to_y_pct", 0),
            body.get("page_url", ""),
            body.get("viewport_w", 1280),
            body.get("viewport_h", 800),
            body.get("quoted_text", ""),
            body.get("computed_css", ""),
            body.get("react_tree", ""),
            body.get("message", ""),
            "open",
            seq_num,
        ),
    )
    db.commit()
    return JSONResponse({"id": ann_id, "seq_num": seq_num})


@router.patch("/api/projects/{project_id}/annotations/{ann_id}", dependencies=[Depends(require_auth())])
async def update_annotation(project_id: str, ann_id: str, request: Request):
    body = await request.json()
    db = _db()
    fields = []
    vals = []
    for f in ("message", "type", "status"):
        if f in body:
            fields.append(f"{f}=?")
            vals.append(body[f])
    if body.get("status") == "resolved":
        fields.append("resolved_at=CURRENT_TIMESTAMP")
    if not fields:
        return JSONResponse({"ok": True})
    vals += [project_id, ann_id]
    db.execute(
        f"UPDATE project_annotations SET {', '.join(fields)} WHERE project_id=? AND id=?",
        vals,
    )
    db.commit()
    return JSONResponse({"ok": True})


@router.delete("/api/projects/{project_id}/annotations/{ann_id}", dependencies=[Depends(require_auth())])
async def delete_annotation(project_id: str, ann_id: str):
    db = _db()
    db.execute(
        "DELETE FROM project_annotations WHERE id=? AND project_id=?",
        (ann_id, project_id),
    )
    db.commit()
    return JSONResponse({"ok": True})


# ── Export ───────────────────────────────────────────────────────


@router.get("/api/projects/{project_id}/annotations/export")
async def export_annotations(project_id: str):
    db = _db()
    rows = db.execute(
        "SELECT * FROM project_annotations WHERE project_id=? AND status='open' ORDER BY seq_num",
        (project_id,),
    ).fetchall()

    # Group by page_url
    pages: dict[str, list] = {}
    for r in rows:
        key = r["page_url"] or "/"
        pages.setdefault(key, []).append(r)

    # Project name
    try:
        from ....projects.manager import get_project_store

        proj = get_project_store().get(project_id)
        proj_name = proj.name if proj else project_id
    except Exception:
        proj_name = project_id

    lines = [f"## Annotation Studio — {proj_name}", ""]
    for page_url, anns in pages.items():
        if anns:
            vp = f"{anns[0]['viewport_w']}×{anns[0]['viewport_h']}"
            lines.append(f"### Page: {page_url} ({vp})")
            for a in anns:
                typ = a["type"].upper()
                sel = a["selector"] or ""
                etxt = f' ("{a["element_text"]}")' if a["element_text"] else ""
                msg = a["message"]
                if a["type"] == "move" and (a["to_x_pct"] or a["to_y_pct"]):
                    pos = f"from ({a['from_x_pct']:.0f}%,{a['from_y_pct']:.0f}%) → to ({a['to_x_pct']:.0f}%,{a['to_y_pct']:.0f}%)"
                    lines.append(
                        f'**#{a["seq_num"]}** [{typ}] `{sel}`{etxt} — {pos} — "{msg}"'
                    )
                elif a["type"] == "text" and a["quoted_text"]:
                    lines.append(
                        f'**#{a["seq_num"]}** [{typ}] "{a["quoted_text"]}" — "{msg}"'
                    )
                elif a["w_pct"] and a["h_pct"]:
                    lines.append(
                        f'**#{a["seq_num"]}** [{typ}] area ({a["x_pct"]:.0f}%,{a["y_pct"]:.0f}% → {a["x_pct"] + a["w_pct"]:.0f}%,{a["y_pct"] + a["h_pct"]:.0f}%) — "{msg}"'
                    )
                else:
                    lines.append(f'**#{a["seq_num"]}** [{typ}] `{sel}`{etxt} — "{msg}"')
                if a["computed_css"]:
                    lines.append(f"  CSS: {a['computed_css']}")
                if a["react_tree"]:
                    lines.append(f"  React: {a['react_tree']}")
            lines.append("")

    return JSONResponse({"markdown": "\n".join(lines)})


@router.post("/api/projects/{project_id}/annotations/fix-all", dependencies=[Depends(require_auth())])
async def fix_all_annotations(project_id: str, request: Request):
    """Create a mission to fix all open annotations."""
    # Get export markdown
    export_resp = await export_annotations(project_id)
    export_data = json.loads(export_resp.body)
    markdown = export_data.get("markdown", "")

    if not markdown.strip():
        return JSONResponse({"error": "No open annotations to fix"}, status_code=400)

    try:
        from ....epics.store import get_epic_store
        from ....projects.manager import get_project_store

        proj = get_project_store().get(project_id)
        proj_name = proj.name if proj else project_id

        epic_store = get_epic_store()
        mission = epic_store.create_mission(
            project_id=project_id,
            title=f"Fix UI Annotations — {proj_name}",
            description=f"Fix all open UI annotations from the Annotation Studio:\n\n{markdown}",
            workflow_id="sf-pipeline",
        )
        return JSONResponse({"mission_id": mission.id, "ok": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── Traceability ─────────────────────────────────────────────────


@router.get("/api/projects/{project_id}/screens/{screen_id}/traceability")
async def get_screen_traceability(project_id: str, screen_id: str):
    """Return full SAFe traceability: programme, epic, feature, stories, persona, rbac."""
    db = _db()

    screen = db.execute(
        "SELECT * FROM project_screens WHERE id=? AND project_id=?",
        (screen_id, project_id),
    ).fetchone()

    result: dict = {
        "programme": None,
        "epic": None,
        "feature": None,
        "user_stories": [],
        "persona": None,
        "rbac_roles": [],
        "specs_url": None,
        # backward-compat kept
        "mission": None,
    }

    if not screen:
        return JSONResponse(result)

    # RBAC from screen
    try:
        import json as _json

        rbac_raw = screen["rbac_roles"] if "rbac_roles" in screen.keys() else "[]"
        result["rbac_roles"] = _json.loads(rbac_raw or "[]")
    except Exception:
        pass

    # Feature + Epic + Programme
    feature_id = (screen["feature_id"] or "") if screen else ""
    if feature_id:
        feat = db.execute("SELECT * FROM features WHERE id=?", (feature_id,)).fetchone()
        if feat:
            result["feature"] = {
                "id": feat["id"],
                "name": feat["name"],
                "description": feat["description"],
                "acceptance_criteria": feat.get("acceptance_criteria", ""),
                "status": feat["status"],
                "story_points": feat.get("story_points", 0),
            }

            # Persona from feature
            try:
                feat_persona = feat["persona"] if "persona" in feat.keys() else ""
                if feat_persona:
                    result["persona"] = feat_persona
            except Exception:
                pass

            # Epic
            epic_id = feat["epic_id"] or ""
            if epic_id:
                try:
                    epic = db.execute(
                        "SELECT * FROM epics WHERE id=?", (epic_id,)
                    ).fetchone()
                    if epic:
                        result["epic"] = {
                            "id": epic["id"],
                            "name": epic["name"],
                            "description": epic["description"],
                        }
                        # Programme
                        prog_id = epic["programme_id"] or ""
                        if prog_id:
                            prog = db.execute(
                                "SELECT id, name, description FROM org_portfolios WHERE id=?",
                                (prog_id,),
                            ).fetchone()
                            if prog:
                                result["programme"] = {
                                    "id": prog["id"],
                                    "name": prog["name"],
                                }
                    else:
                        result["epic"] = {
                            "id": epic_id,
                            "name": epic_id,
                            "description": "",
                        }
                except Exception:
                    result["epic"] = {"id": epic_id, "name": epic_id, "description": ""}

            # User stories
            stories = db.execute(
                "SELECT id, title, status FROM user_stories WHERE feature_id=? ORDER BY priority DESC LIMIT 5",
                (feature_id,),
            ).fetchall()
            result["user_stories"] = [dict(s) for s in stories]

    # Persona fallback: from agents with persona defined on this project's missions
    if not result["persona"]:
        try:
            personas = db.execute(
                "SELECT a.persona FROM agents a JOIN epics m ON m.project_id=? WHERE a.persona != '' LIMIT 1",
                (project_id,),
            ).fetchone()
            if personas:
                result["persona"] = personas["persona"]
        except Exception:
            pass

    result["specs_url"] = f"/projects/{project_id}"
    return JSONResponse(result)


@router.patch("/api/projects/{project_id}/screens/{screen_id}", dependencies=[Depends(require_auth())])
async def update_screen(project_id: str, screen_id: str, request: Request):
    """Update screen metadata (feature_id, mission_id, name)."""
    body = await request.json()
    db = _db()
    fields, vals = [], []
    for f in ("name", "feature_id", "mission_id", "page_url"):
        if f in body:
            fields.append(f"{f}=?")
            vals.append(body[f])
    if not fields:
        return JSONResponse({"ok": True})
    vals += [project_id, screen_id]
    db.execute(
        f"UPDATE project_screens SET {', '.join(fields)} WHERE project_id=? AND id=?",
        vals,
    )
    db.commit()
    return JSONResponse({"ok": True})


# ── Settings ─────────────────────────────────────────────────────


@router.get("/api/settings/general")
async def get_general_settings():
    """Return general platform settings (including self_annotation_enabled)."""
    db = _db()
    rows = db.execute(
        "SELECT key, value FROM platform_settings WHERE key NOT LIKE 'rate_limit_%'"
    ).fetchall()
    return JSONResponse({r["key"]: r["value"] for r in rows})


@router.post("/api/settings/general", dependencies=[Depends(require_auth())])
async def update_general_settings(request: Request):
    """Update one or more general platform settings."""
    body = await request.json()
    db = _db()
    for key, value in body.items():
        db.execute(
            "INSERT INTO platform_settings (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP",
            (key, str(value)),
        )
    db.commit()
    return JSONResponse({"ok": True})
