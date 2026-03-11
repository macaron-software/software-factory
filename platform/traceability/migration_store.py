"""Migration Traceability Store — legacy item inventory + bidirectional links.

Provides CRUD for legacy_items (UUID inventory of every legacy element)
and traceability_links (bidirectional linking: legacy↔story↔code↔test).
Also provides coverage analysis and orphan detection.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..db.migrations import get_db

logger = logging.getLogger(__name__)

# ── Item types ──
LEGACY_ITEM_TYPES = {
    "table", "column", "fk", "pk", "index", "trigger", "rule", "workflow",
    "class", "method", "endpoint", "config", "enum", "view", "procedure",
    "function", "constant", "dto", "entity", "service", "controller",
    "permission", "role", "menu", "page", "report", "scheduler", "listener",
    "validator", "interceptor", "filter", "migration", "seed_data",
}

LINK_TYPES = {
    "migrates_from",   # new code migrates from legacy item
    "implements",      # code implements a story/feature
    "tests",           # test covers a story/AC
    "depends_on",      # item depends on another
    "covers",          # story covers a legacy item
    "maps_to",         # legacy item maps to new item
    "replaces",        # new item replaces legacy item
    "references",      # generic reference
}

TRACEABLE_TYPES = {
    "legacy_item", "feature", "story", "acceptance_criterion",
    "code", "test", "persona", "epic",
}


@dataclass
class LegacyItem:
    id: str
    project_id: str
    item_type: str
    name: str
    parent_id: str = ""
    description: str = ""
    metadata: dict = field(default_factory=dict)
    source_file: str = ""
    source_line: int = 0
    status: str = "identified"
    created_at: str = ""


@dataclass
class TraceabilityLink:
    id: int
    source_id: str
    source_type: str
    target_id: str
    target_type: str
    link_type: str
    coverage_pct: int = 0
    notes: str = ""
    created_at: str = ""


# ── Legacy Items CRUD ──

def create_legacy_item(
    project_id: str,
    item_type: str,
    name: str,
    parent_id: str = "",
    description: str = "",
    metadata: dict | None = None,
    source_file: str = "",
    source_line: int = 0,
) -> str:
    """Create a legacy item with auto-generated UUID. Returns the id."""
    item_id = f"li-{uuid.uuid4().hex[:8]}"
    meta_json = json.dumps(metadata or {}, ensure_ascii=False)
    db = get_db()
    try:
        db.execute(
            """INSERT INTO legacy_items
            (id, project_id, item_type, name, parent_id, description,
             metadata_json, source_file, source_line, status, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'identified',%s)""",
            (item_id, project_id, item_type, name, parent_id, description,
             meta_json, source_file, source_line,
             datetime.now(timezone.utc).isoformat()),
        )
        db.commit()
    finally:
        db.close()
    return item_id


def list_legacy_items(
    project_id: str,
    item_type: str | None = None,
    parent_id: str | None = None,
    status: str | None = None,
) -> list[LegacyItem]:
    """List legacy items with optional filters."""
    clauses = ["project_id = %s"]
    params: list = [project_id]
    if item_type:
        clauses.append("item_type = %s")
        params.append(item_type)
    if parent_id is not None:
        clauses.append("parent_id = %s")
        params.append(parent_id)
    if status:
        clauses.append("status = %s")
        params.append(status)
    where = " AND ".join(clauses)
    db = get_db()
    try:
        rows = db.execute(
            f"SELECT * FROM legacy_items WHERE {where} ORDER BY item_type, name",
            params,
        ).fetchall()
    finally:
        db.close()
    return [_row_to_item(r) for r in rows]


def get_legacy_item(item_id: str) -> LegacyItem | None:
    """Get a single legacy item by id."""
    db = get_db()
    try:
        row = db.execute(
            "SELECT * FROM legacy_items WHERE id = %s", (item_id,)
        ).fetchone()
    finally:
        db.close()
    return _row_to_item(row) if row else None


def update_legacy_item_status(item_id: str, status: str) -> None:
    """Update legacy item status (identified → analyzed → mapped → migrated → verified)."""
    db = get_db()
    try:
        db.execute(
            "UPDATE legacy_items SET status = %s WHERE id = %s",
            (status, item_id),
        )
        db.commit()
    finally:
        db.close()


def count_legacy_items(project_id: str) -> dict[str, int]:
    """Count legacy items grouped by type."""
    db = get_db()
    try:
        rows = db.execute(
            "SELECT item_type, COUNT(*) as cnt FROM legacy_items "
            "WHERE project_id = %s GROUP BY item_type ORDER BY cnt DESC",
            (project_id,),
        ).fetchall()
    finally:
        db.close()
    return {r["item_type"]: r["cnt"] for r in rows}


# ── Traceability Links ──

def create_link(
    source_id: str,
    source_type: str,
    target_id: str,
    target_type: str,
    link_type: str,
    coverage_pct: int = 0,
    notes: str = "",
) -> int:
    """Create a traceability link. Returns the link id."""
    db = get_db()
    try:
        cur = db.execute(
            """INSERT INTO traceability_links
            (source_id, source_type, target_id, target_type, link_type,
             coverage_pct, notes, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (source_id, target_id, link_type) DO UPDATE
            SET coverage_pct = EXCLUDED.coverage_pct, notes = EXCLUDED.notes""",
            (source_id, source_type, target_id, target_type, link_type,
             coverage_pct, notes, datetime.now(timezone.utc).isoformat()),
        )
        db.commit()
        return cur.lastrowid or 0
    finally:
        db.close()


def get_links(
    item_id: str,
    direction: str = "both",
    link_type: str | None = None,
) -> list[TraceabilityLink]:
    """Get traceability links for an item.

    direction: 'outgoing' (source=item), 'incoming' (target=item), 'both'
    """
    db = get_db()
    try:
        results = []
        params: list = []
        if direction in ("outgoing", "both"):
            q = "SELECT * FROM traceability_links WHERE source_id = %s"
            p = [item_id]
            if link_type:
                q += " AND link_type = %s"
                p.append(link_type)
            results.extend(db.execute(q, p).fetchall())

        if direction in ("incoming", "both"):
            q = "SELECT * FROM traceability_links WHERE target_id = %s"
            p = [item_id]
            if link_type:
                q += " AND link_type = %s"
                p.append(link_type)
            results.extend(db.execute(q, p).fetchall())
    finally:
        db.close()
    return [_row_to_link(r) for r in results]


# ── Coverage Analysis ──

def coverage_report(project_id: str) -> dict:
    """Compute traceability coverage for a project.

    Returns per-type stats: how many legacy items have at least one
    outgoing link (covers/maps_to/migrates_from) to a story/feature/code.
    """
    db = get_db()
    try:
        # Total items per type
        totals = db.execute(
            "SELECT item_type, COUNT(*) as cnt FROM legacy_items "
            "WHERE project_id = %s GROUP BY item_type",
            (project_id,),
        ).fetchall()

        # Items with at least one outgoing link
        covered = db.execute(
            "SELECT li.item_type, COUNT(DISTINCT li.id) as cnt "
            "FROM legacy_items li "
            "JOIN traceability_links tl ON tl.source_id = li.id "
            "WHERE li.project_id = %s "
            "GROUP BY li.item_type",
            (project_id,),
        ).fetchall()
    finally:
        db.close()

    total_map = {r["item_type"]: r["cnt"] for r in totals}
    covered_map = {r["item_type"]: r["cnt"] for r in covered}

    report = {}
    grand_total = 0
    grand_covered = 0
    for itype, total in total_map.items():
        cov = covered_map.get(itype, 0)
        pct = round(100 * cov / total) if total > 0 else 0
        report[itype] = {"total": total, "covered": cov, "pct": pct}
        grand_total += total
        grand_covered += cov

    report["_overall"] = {
        "total": grand_total,
        "covered": grand_covered,
        "pct": round(100 * grand_covered / grand_total) if grand_total > 0 else 0,
    }
    return report


def orphan_report(project_id: str) -> dict:
    """Find items with no downstream traceability.

    Returns:
    - legacy_no_story: legacy items with no link to a story/feature
    - stories_no_test: stories with no link to a test
    - stories_no_code: stories with no link to code
    """
    db = get_db()
    try:
        # Legacy items with no outgoing link
        legacy_orphans = db.execute(
            "SELECT li.id, li.item_type, li.name FROM legacy_items li "
            "WHERE li.project_id = %s "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM traceability_links tl "
            "  WHERE tl.source_id = li.id"
            ")",
            (project_id,),
        ).fetchall()

        # Stories with no test link
        stories_no_test = db.execute(
            "SELECT us.id, us.title FROM user_stories us "
            "JOIN features f ON us.feature_id = f.id "
            "WHERE f.epic_id IN (SELECT id FROM epics WHERE project_id = %s) "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM traceability_links tl "
            "  WHERE tl.source_id = us.id AND tl.link_type = 'tests'"
            ")",
            (project_id,),
        ).fetchall()

        # Stories with no code link
        stories_no_code = db.execute(
            "SELECT us.id, us.title FROM user_stories us "
            "JOIN features f ON us.feature_id = f.id "
            "WHERE f.epic_id IN (SELECT id FROM epics WHERE project_id = %s) "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM traceability_links tl "
            "  WHERE tl.source_id = us.id AND tl.link_type = 'implements'"
            ")",
            (project_id,),
        ).fetchall()
    finally:
        db.close()

    return {
        "legacy_no_story": [dict(r) for r in legacy_orphans],
        "stories_no_test": [dict(r) for r in stories_no_test],
        "stories_no_code": [dict(r) for r in stories_no_code],
        "legacy_orphan_count": len(legacy_orphans),
        "story_no_test_count": len(stories_no_test),
        "story_no_code_count": len(stories_no_code),
    }


def traceability_matrix(project_id: str) -> list[dict]:
    """Full traceability matrix: legacy_item → story → code → test.

    Returns a list of dicts, one per legacy item, showing its complete
    traceability chain to stories, code, and tests.
    """
    db = get_db()
    try:
        items = db.execute(
            "SELECT id, item_type, name, status FROM legacy_items "
            "WHERE project_id = %s ORDER BY item_type, name",
            (project_id,),
        ).fetchall()

        matrix = []
        for item in items:
            item_id = item["id"]
            # Find linked stories/features
            story_links = db.execute(
                "SELECT tl.target_id, tl.link_type, tl.coverage_pct "
                "FROM traceability_links tl "
                "WHERE tl.source_id = %s AND tl.target_type IN ('story', 'feature')",
                (item_id,),
            ).fetchall()

            # Find linked code files
            code_links = db.execute(
                "SELECT tl.target_id, tl.link_type "
                "FROM traceability_links tl "
                "WHERE tl.source_id = %s AND tl.target_type = 'code'",
                (item_id,),
            ).fetchall()

            # Find linked tests
            test_links = db.execute(
                "SELECT tl.target_id, tl.link_type "
                "FROM traceability_links tl "
                "WHERE tl.source_id = %s AND tl.target_type = 'test'",
                (item_id,),
            ).fetchall()

            matrix.append({
                "legacy_id": item_id,
                "type": item["item_type"],
                "name": item["name"],
                "status": item["status"],
                "stories": [dict(r) for r in story_links],
                "code": [dict(r) for r in code_links],
                "tests": [dict(r) for r in test_links],
                "fully_traced": bool(story_links and code_links and test_links),
            })
    finally:
        db.close()

    return matrix


# ── Internal helpers ──

def _row_to_item(row) -> LegacyItem:
    meta = {}
    try:
        meta = json.loads(row["metadata_json"] or "{}")
    except (json.JSONDecodeError, KeyError):
        pass
    return LegacyItem(
        id=row["id"],
        project_id=row["project_id"],
        item_type=row["item_type"],
        name=row["name"],
        parent_id=row.get("parent_id", ""),
        description=row.get("description", ""),
        metadata=meta,
        source_file=row.get("source_file", ""),
        source_line=row.get("source_line", 0),
        status=row.get("status", "identified"),
        created_at=str(row.get("created_at", "")),
    )


def _row_to_link(row) -> TraceabilityLink:
    return TraceabilityLink(
        id=row["id"],
        source_id=row["source_id"],
        source_type=row["source_type"],
        target_id=row["target_id"],
        target_type=row["target_type"],
        link_type=row["link_type"],
        coverage_pct=row.get("coverage_pct", 0),
        notes=row.get("notes", ""),
        created_at=str(row.get("created_at", "")),
    )
