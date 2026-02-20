"""
Confluence sync engine — syncs mission control tabs to Confluence pages.
Idempotent: creates or updates pages by title match.
Tracks page IDs in `confluence_pages` DB table.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from ..db.migrations import get_db
from ..missions.store import get_mission_store, MissionDef
from ..sessions.store import get_session_store
from .client import ConfluenceClient, get_confluence_client, HOMEPAGE_ID
from . import converter

log = logging.getLogger(__name__)

# Tab names matching mission_control.html
TABS = ["po", "qa", "archi", "wiki", "projet"]


class ConfluenceSyncEngine:
    """Sync mission control content to Confluence."""

    def __init__(self, client: ConfluenceClient = None):
        self.client = client or get_confluence_client()

    # ── Page hierarchy ─────────────────────────────────────────

    def _ensure_hierarchy(self, mission: MissionDef) -> dict[str, str]:
        """Ensure page hierarchy exists, return tab → page_id mapping."""
        project_name = mission.project_id or "Macaron Platform"
        epic_name = mission.name

        # Create hierarchy: PROJETS / project / epic
        projets_id = self._get_or_create("PROJETS", HOMEPAGE_ID)
        project_id = self._get_or_create(project_name, projets_id)
        epic_id = self._get_or_create(epic_name, project_id)

        return {"_epic": epic_id, "_project": project_id, "_projets": projets_id}

    def _get_or_create(self, title: str, parent_id: str) -> str:
        """Get page by title or create under parent."""
        existing = self.client.find_page(title)
        if existing:
            return existing["id"]
        page = self.client.create_page(title, "<p></p>", parent_id)
        return page["id"]

    # ── Tab content builders ───────────────────────────────────

    def _build_po_content(self, mission: MissionDef) -> str:
        """Build PO tab content (features kanban)."""
        db = get_db()
        features = db.execute(
            "SELECT * FROM features WHERE epic_id = ? ORDER BY priority",
            (mission.id,)
        ).fetchall()
        db.close()

        features_list = [dict(f) for f in features]
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        body = converter.page_header("Product Owner — Features", mission.name,
                                      mission.project_id, now)

        # Group by status
        for status, label in [("backlog", "Backlog"), ("sprint", "Sprint"),
                               ("in_progress", "En cours"), ("done", "Terminé")]:
            filtered = [f for f in features_list if f.get("status") == status]
            body += f"<h2>{label} ({len(filtered)})</h2>"
            body += converter.features_to_confluence(filtered)

        return body

    def _build_qa_content(self, mission: MissionDef, session_id: str = None) -> str:
        """Build QA tab content (test results)."""
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        body = converter.page_header("QA — Tests & Qualité", mission.name,
                                      mission.project_id, now)

        # Get QA messages from mission sessions
        messages = self._get_phase_messages(mission.id, "qa")
        if messages:
            body += "<h2>Résultats QA</h2>"
            body += converter.messages_to_confluence(messages, "Discussion QA")

        return body

    def _build_archi_content(self, mission: MissionDef) -> str:
        """Build Architecture tab content."""
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        body = converter.page_header("Architecture", mission.name,
                                      mission.project_id, now)

        messages = self._get_phase_messages(mission.id, "archi")
        if messages:
            body += "<h2>Décisions architecturales</h2>"
            body += converter.messages_to_confluence(messages, "Architecture")

        # Get architecture artifacts from workspace
        body += self._get_workspace_file_content(mission, "Architecture.md", "Architecture détaillée")
        return body

    def _build_wiki_content(self, mission: MissionDef) -> str:
        """Build Wiki/documentation tab content."""
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        body = converter.page_header("Wiki — Documentation", mission.name,
                                      mission.project_id, now)

        messages = self._get_phase_messages(mission.id, "wiki")
        if messages:
            body += converter.messages_to_confluence(messages, "Documentation")

        # Get docs from workspace
        for fname in ["README.md", "SPECS.md", "VISION.md", "CHANGELOG.md"]:
            body += self._get_workspace_file_content(mission, fname, fname)

        return body

    def _build_projet_content(self, mission: MissionDef) -> str:
        """Build Project tab content (overview, stats)."""
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        body = converter.page_header("Projet — Vue d'ensemble", mission.name,
                                      mission.project_id, now)

        # Mission metadata
        body += converter.info_macro("Métadonnées", (
            f"<p>ID: <code>{mission.id}</code></p>"
            f"<p>Status: <strong>{mission.status}</strong></p>"
            f"<p>Type: {mission.type}</p>"
            f"<p>WSJF: {mission.wsjf_score}</p>"
            f"<p>Créé: {mission.created_at}</p>"
        ))

        # Description & Goal
        if mission.description:
            body += "<h2>Description</h2>"
            body += converter.md_to_confluence(mission.description)
        if mission.goal:
            body += "<h2>Objectif</h2>"
            body += converter.md_to_confluence(mission.goal)

        # Phase status from mission runs
        body += self._get_phase_summary(mission.id)

        return body

    # ── Helpers ────────────────────────────────────────────────

    def _get_phase_messages(self, mission_id: str, tab_keyword: str) -> list[dict]:
        """Get messages relevant to a tab from mission sessions."""
        db = get_db()
        try:
            # Get mission run sessions
            runs = db.execute(
                "SELECT session_id FROM mission_runs WHERE id = ? ORDER BY created_at DESC LIMIT 1",
                (mission_id,)
            ).fetchall()

            if not runs or not runs[0]["session_id"]:
                return []

            session_id = runs[0]["session_id"]
            messages = db.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at",
                (session_id,)
            ).fetchall()

            result = []
            for msg in messages:
                m = dict(msg)
                content = m.get("content", "")
                sender = m.get("sender_id", "")
                # Filter by tab relevance
                if tab_keyword == "qa" and any(k in sender.lower() for k in ["qa", "test", "quality"]):
                    result.append(m)
                elif tab_keyword == "archi" and any(k in sender.lower() for k in ["archi", "lead", "sre"]):
                    result.append(m)
                elif tab_keyword == "wiki" and any(k in sender.lower() for k in ["tech_writer", "doc", "wiki"]):
                    result.append(m)
                elif tab_keyword == "po" and any(k in sender.lower() for k in ["product", "po", "owner"]):
                    result.append(m)

            return result[-20:]  # Last 20 messages max
        finally:
            db.close()

    def _get_workspace_file_content(self, mission: MissionDef, filename: str,
                                     heading: str) -> str:
        """Read a file from workspace and convert to Confluence format."""
        from pathlib import Path
        from ..config import FACTORY_ROOT

        # Try workspace path from mission runs
        db = get_db()
        try:
            runs = db.execute(
                "SELECT workspace_path FROM mission_runs WHERE id = ? ORDER BY created_at DESC LIMIT 1",
                (mission.id,)
            ).fetchall()
            if runs and runs[0]["workspace_path"]:
                ws_path = Path(runs[0]["workspace_path"])
            else:
                ws_path = FACTORY_ROOT / "data" / "workspaces" / mission.id[:8]
        finally:
            db.close()

        fpath = ws_path / filename
        if fpath.exists():
            content = fpath.read_text(errors="replace")[:20000]  # 20K max
            return f"<h2>{heading}</h2>" + converter.md_to_confluence(content)
        return ""

    def _get_phase_summary(self, mission_id: str) -> str:
        """Get phase execution summary."""
        db = get_db()
        try:
            runs = db.execute(
                "SELECT phases_json, status FROM mission_runs WHERE id = ? ORDER BY created_at DESC LIMIT 1",
                (mission_id,)
            ).fetchall()
            if not runs:
                return "<p><em>Aucune exécution.</em></p>"

            run = dict(runs[0])
            phases_raw = run.get("phases_json", "[]")
            try:
                phases = json.loads(phases_raw) if phases_raw else []
            except (json.JSONDecodeError, TypeError):
                phases = []

            if not phases:
                return "<p><em>Aucune phase exécutée.</em></p>"

            rows = ['<tr><th>Phase</th><th>Status</th><th>Résumé</th></tr>']
            for p in phases:
                name = p.get("name", p.get("phase_id", "?"))
                status = p.get("status", "pending")
                summary = p.get("summary", "")[:200]
                color = {"completed": "Green", "running": "Blue",
                         "failed": "Red", "skipped": "Grey"}.get(status, "Grey")
                rows.append(
                    f'<tr><td>{name}</td>'
                    f'<td><ac:structured-macro ac:name="status">'
                    f'<ac:parameter ac:name="colour">{color}</ac:parameter>'
                    f'<ac:parameter ac:name="title">{status}</ac:parameter>'
                    f'</ac:structured-macro></td>'
                    f'<td>{converter._inline(summary)}</td></tr>'
                )

            return f'<h2>Phases</h2><table><tbody>{"".join(rows)}</tbody></table>'
        finally:
            db.close()

    # ── DB tracking ────────────────────────────────────────────

    def _save_page_ref(self, mission_id: str, tab: str, page_id: str):
        """Track synced page in DB."""
        db = get_db()
        try:
            db.execute(
                """INSERT INTO confluence_pages (mission_id, tab, confluence_page_id, last_synced)
                   VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(mission_id, tab) DO UPDATE SET
                   confluence_page_id = excluded.confluence_page_id,
                   last_synced = CURRENT_TIMESTAMP""",
                (mission_id, tab, page_id)
            )
            db.commit()
        finally:
            db.close()

    def _get_page_ref(self, mission_id: str, tab: str) -> Optional[str]:
        """Get tracked Confluence page ID."""
        db = get_db()
        try:
            row = db.execute(
                "SELECT confluence_page_id FROM confluence_pages WHERE mission_id = ? AND tab = ?",
                (mission_id, tab)
            ).fetchone()
            return row["confluence_page_id"] if row else None
        finally:
            db.close()

    # ── Main sync ──────────────────────────────────────────────

    def sync_tab(self, mission_id: str, tab: str) -> dict:
        """Sync a single tab to Confluence. Returns {page_id, url, status}."""
        ms = get_mission_store()
        mission = ms.get_mission(mission_id)
        if not mission:
            return {"status": "error", "error": f"Mission {mission_id} not found"}

        # Ensure hierarchy
        hierarchy = self._ensure_hierarchy(mission)
        epic_page_id = hierarchy["_epic"]

        # Build content
        builders = {
            "po": self._build_po_content,
            "qa": self._build_qa_content,
            "archi": self._build_archi_content,
            "wiki": self._build_wiki_content,
            "projet": self._build_projet_content,
        }
        builder = builders.get(tab)
        if not builder:
            return {"status": "error", "error": f"Unknown tab: {tab}"}

        body = builder(mission)

        # Title format: "Epic Name — Tab"
        tab_labels = {"po": "PO — Features", "qa": "QA — Tests",
                       "archi": "Architecture", "wiki": "Wiki", "projet": "Projet"}
        title = f"{mission.name} — {tab_labels.get(tab, tab)}"

        # Create or update
        page = self.client.create_or_update(title, body, epic_page_id)
        page_id = page["id"]

        # Track in DB
        self._save_page_ref(mission_id, tab, page_id)

        url = f"{self.client.base_url}/pages/viewpage.action?pageId={page_id}"
        log.info("Synced tab %s for mission %s → page %s", tab, mission_id[:8], page_id)
        return {"status": "ok", "page_id": page_id, "url": url, "tab": tab}

    def sync_mission(self, mission_id: str) -> dict:
        """Sync all tabs for a mission."""
        results = {}
        for tab in TABS:
            try:
                results[tab] = self.sync_tab(mission_id, tab)
            except Exception as e:
                log.error("Failed to sync tab %s: %s", tab, e)
                results[tab] = {"status": "error", "error": str(e)}
        return results

    def get_sync_status(self, mission_id: str) -> dict:
        """Get sync status for all tabs of a mission."""
        db = get_db()
        try:
            rows = db.execute(
                "SELECT tab, confluence_page_id, last_synced FROM confluence_pages WHERE mission_id = ?",
                (mission_id,)
            ).fetchall()
            return {r["tab"]: {"page_id": r["confluence_page_id"],
                               "last_synced": r["last_synced"]} for r in rows}
        finally:
            db.close()


# Singleton
_engine: Optional[ConfluenceSyncEngine] = None

def get_sync_engine() -> ConfluenceSyncEngine:
    global _engine
    if _engine is None:
        _engine = ConfluenceSyncEngine()
    return _engine
