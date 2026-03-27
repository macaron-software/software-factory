"""Full E2E Traceability Chain — 13-layer UUID coverage.

Chain: Epic → Persona → Feature → UserStory → AcceptanceCriteria
       → IHM (screen/route) → Code → TU (unit test) → E2E IHM test
       → CRUD endpoint → RBAC rule → Screen → NFT

Tables auto-created on first use. Agents interact via tool_runner tools:
  traceability_record, traceability_chain_report, traceability_check_e2e
"""
# Ref: feat-traceability-chain
from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..db.adapter import is_postgresql
from ..db.migrations import get_db
from .artifacts import make_id, make_trace_uuid

logger = logging.getLogger(__name__)

# ── DB Schemas (auto-migrated) ───────────────────────────────────

_PERSONAS_SCHEMA = """
CREATE TABLE IF NOT EXISTS personas (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL,
    epic_id     TEXT DEFAULT '',
    name        TEXT NOT NULL DEFAULT '',
    role        TEXT DEFAULT '',
    description TEXT DEFAULT '',
    goals       TEXT DEFAULT '',
    frustrations TEXT DEFAULT '',
    created_at  TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_personas_project ON personas(project_id);
CREATE INDEX IF NOT EXISTS idx_personas_epic    ON personas(epic_id);
"""

_NFT_SCHEMA = """
CREATE TABLE IF NOT EXISTS nft_tests (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL,
    epic_id     TEXT DEFAULT '',
    feature_id  TEXT DEFAULT '',
    nft_type    TEXT NOT NULL DEFAULT 'perf',
    name        TEXT NOT NULL DEFAULT '',
    criterion   TEXT DEFAULT '',
    threshold   TEXT DEFAULT '',
    result      TEXT DEFAULT 'pending',
    measured_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_nft_project ON nft_tests(project_id);
CREATE INDEX IF NOT EXISTS idx_nft_feature ON nft_tests(feature_id);
CREATE INDEX IF NOT EXISTS idx_nft_type    ON nft_tests(nft_type);
"""

_TRACE_ARTIFACTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS traceability_artifacts (
    id           TEXT PRIMARY KEY,
    project_id   TEXT NOT NULL,
    epic_id      TEXT DEFAULT '',
    feature_id   TEXT DEFAULT '',
    layer        TEXT NOT NULL,
    artifact_key TEXT NOT NULL DEFAULT '',
    artifact_name TEXT NOT NULL DEFAULT '',
    notes        TEXT DEFAULT '',
    metadata_json TEXT DEFAULT '{}',
    created_at   TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, feature_id, layer, artifact_key)
);
CREATE INDEX IF NOT EXISTS idx_tart_project ON traceability_artifacts(project_id);
CREATE INDEX IF NOT EXISTS idx_tart_epic    ON traceability_artifacts(epic_id);
CREATE INDEX IF NOT EXISTS idx_tart_feature ON traceability_artifacts(feature_id);
CREATE INDEX IF NOT EXISTS idx_tart_layer   ON traceability_artifacts(layer);
"""

# Coverage flag columns added to features table
_FEATURE_COVERAGE_COLS = [
    ("has_persona",  "BOOLEAN DEFAULT FALSE"),
    ("has_ihm",      "BOOLEAN DEFAULT FALSE"),
    ("has_code",     "BOOLEAN DEFAULT FALSE"),
    ("has_tu",       "BOOLEAN DEFAULT FALSE"),
    ("has_e2e",      "BOOLEAN DEFAULT FALSE"),
    ("has_crud",     "BOOLEAN DEFAULT FALSE"),
    ("has_rbac",     "BOOLEAN DEFAULT FALSE"),
    ("has_screens",  "BOOLEAN DEFAULT FALSE"),
    ("has_nft",      "BOOLEAN DEFAULT FALSE"),
    ("coverage_pct", "REAL DEFAULT 0"),
]

_TRACE_LAYER_PREFIX = {
    "ihm": "ihm",
    "code": "code",
    "test_tu": "tu",
    "test_e2e": "e2e",
    "crud": "crud",
    "rbac": "rbac",
}


def _epic_table_name() -> str:
    """Return the backlog epic table name for the active database backend."""
    return "epics" if is_postgresql() else "missions"


def _ensure_tables():
    conn = get_db()
    try:
        for schema in (_PERSONAS_SCHEMA, _NFT_SCHEMA, _TRACE_ARTIFACTS_SCHEMA):
            for stmt in schema.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(s)
        # Add coverage flag columns to features (idempotent)
        if is_postgresql():
            for col, defn in _FEATURE_COVERAGE_COLS:
                conn.execute(f"ALTER TABLE features ADD COLUMN IF NOT EXISTS {col} {defn}")
            conn.execute(
                "ALTER TABLE IF EXISTS traceability_links "
                "ADD COLUMN IF NOT EXISTS project_id TEXT DEFAULT ''"
            )
            trace_links = conn.execute(
                "SELECT to_regclass(?) AS table_name",
                ("public.traceability_links",),
            ).fetchone()
            if trace_links and trace_links.get("table_name"):
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_tlinks_project "
                    "ON traceability_links(project_id)"
                )
        else:
            for col, defn in _FEATURE_COVERAGE_COLS:
                try:
                    conn.execute(f"ALTER TABLE features ADD COLUMN {col} {defn}")
                except Exception:
                    pass
            try:
                conn.execute("ALTER TABLE traceability_links ADD COLUMN project_id TEXT DEFAULT ''")
            except Exception:
                pass
            try:
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_tlinks_project ON traceability_links(project_id)"
                )
            except Exception:
                pass
        conn.commit()
    finally:
        conn.close()


# ── Persona Store ─────────────────────────────────────────────────

@dataclass
class Persona:
    id: str = ""
    project_id: str = ""
    epic_id: str = ""
    name: str = ""
    role: str = ""
    description: str = ""
    goals: str = ""
    frustrations: str = ""
    created_at: str = ""
    updated_at: str = ""


class PersonaStore:
    def __init__(self):
        _ensure_tables()

    def create(self, p: Persona) -> Persona:
        if not p.id:
            p.id = make_id("pers")
        now = datetime.now(timezone.utc).isoformat()
        p.created_at = p.created_at or now
        p.updated_at = now
        conn = get_db()
        try:
            conn.execute(
                """INSERT INTO personas
                   (id, project_id, epic_id, name, role, description,
                    goals, frustrations, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT (id) DO NOTHING""",
                (p.id, p.project_id, p.epic_id, p.name, p.role,
                 p.description, p.goals, p.frustrations,
                 p.created_at, p.updated_at),
            )
            conn.commit()
        finally:
            conn.close()
        return p

    def get(self, persona_id: str) -> Optional[Persona]:
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT * FROM personas WHERE id=?", (persona_id,)
            ).fetchone()
        finally:
            conn.close()
        return _row_to_persona(row) if row else None

    def list_by_project(self, project_id: str) -> list[Persona]:
        conn = get_db()
        try:
            rows = conn.execute(
                "SELECT * FROM personas WHERE project_id=? ORDER BY created_at",
                (project_id,)
            ).fetchall()
        finally:
            conn.close()
        return [_row_to_persona(r) for r in rows]

    def list_by_epic(self, epic_id: str) -> list[Persona]:
        conn = get_db()
        try:
            rows = conn.execute(
                "SELECT * FROM personas WHERE epic_id=? ORDER BY created_at",
                (epic_id,)
            ).fetchall()
        finally:
            conn.close()
        return [_row_to_persona(r) for r in rows]


def _row_to_persona(row) -> Persona:
    return Persona(
        id=row["id"], project_id=row["project_id"],
        epic_id=row["epic_id"] or "",
        name=row["name"] or "", role=row["role"] or "",
        description=row["description"] or "",
        goals=row["goals"] or "", frustrations=row["frustrations"] or "",
        created_at=row["created_at"] or "", updated_at=row["updated_at"] or "",
    )


# ── NFT Store ────────────────────────────────────────────────────

@dataclass
class NFTTest:
    id: str = ""
    project_id: str = ""
    epic_id: str = ""
    feature_id: str = ""
    nft_type: str = "perf"    # perf | security | a11y | i18n | load | compliance
    name: str = ""
    criterion: str = ""
    threshold: str = ""
    result: str = "pending"   # pending | pass | fail
    measured_at: str = ""
    created_at: str = ""


class NFTStore:
    def __init__(self):
        _ensure_tables()

    def create(self, t: NFTTest) -> NFTTest:
        if not t.id:
            t.id = make_id("nft")
        t.created_at = t.created_at or datetime.now(timezone.utc).isoformat()
        conn = get_db()
        try:
            conn.execute(
                """INSERT INTO nft_tests
                   (id, project_id, epic_id, feature_id, nft_type,
                    name, criterion, threshold, result, measured_at, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT (id) DO NOTHING""",
                (t.id, t.project_id, t.epic_id, t.feature_id, t.nft_type,
                 t.name, t.criterion, t.threshold, t.result,
                 t.measured_at or None, t.created_at),
            )
            conn.commit()
        finally:
            conn.close()
        return t

    def update_result(self, nft_id: str, result: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        conn = get_db()
        try:
            cur = conn.execute(
                "UPDATE nft_tests SET result=?, measured_at=? WHERE id=?",
                (result, now, nft_id)
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def list_by_feature(self, feature_id: str) -> list[NFTTest]:
        conn = get_db()
        try:
            rows = conn.execute(
                "SELECT * FROM nft_tests WHERE feature_id=? ORDER BY created_at",
                (feature_id,)
            ).fetchall()
        finally:
            conn.close()
        return [_row_to_nft(r) for r in rows]

    def list_by_epic(self, epic_id: str) -> list[NFTTest]:
        conn = get_db()
        try:
            rows = conn.execute(
                "SELECT * FROM nft_tests WHERE epic_id=? ORDER BY created_at",
                (epic_id,)
            ).fetchall()
        finally:
            conn.close()
        return [_row_to_nft(r) for r in rows]


def _row_to_nft(row) -> NFTTest:
    return NFTTest(
        id=row["id"], project_id=row["project_id"],
        epic_id=row["epic_id"] or "", feature_id=row["feature_id"] or "",
        nft_type=row["nft_type"] or "perf",
        name=row["name"] or "", criterion=row["criterion"] or "",
        threshold=row["threshold"] or "", result=row["result"] or "pending",
        measured_at=row["measured_at"] or "", created_at=row["created_at"] or "",
    )


# ── Generic artifact registry (UUID for code/IHM/TU/E2E/CRUD/RBAC) ─────────────

@dataclass
class TraceArtifact:
    id: str = ""
    project_id: str = ""
    epic_id: str = ""
    feature_id: str = ""
    layer: str = ""
    artifact_key: str = ""
    artifact_name: str = ""
    notes: str = ""
    metadata: dict = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""


def record_trace_artifact(
    project_id: str,
    epic_id: str,
    feature_id: str,
    layer: str,
    artifact_key: str = "",
    artifact_name: str = "",
    notes: str = "",
    metadata: dict | None = None,
) -> TraceArtifact:
    """Record a project-scoped traceability artifact with a stable UUID."""
    _ensure_tables()
    if layer not in _TRACE_LAYER_PREFIX:
        raise ValueError(f"Unsupported traceability artifact layer: {layer}")

    key = artifact_key or artifact_name or f"{layer}:{feature_id}"
    name = artifact_name or artifact_key or layer
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    try:
        existing = conn.execute(
            """SELECT * FROM traceability_artifacts
               WHERE project_id=? AND feature_id=? AND layer=? AND artifact_key=?""",
            (project_id, feature_id, layer, key),
        ).fetchone()
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)

        if existing:
            effective_epic_id = existing["epic_id"] or epic_id
            conn.execute(
                """UPDATE traceability_artifacts
                   SET epic_id=?, artifact_name=?, notes=?, metadata_json=?, updated_at=?
                   WHERE id=?""",
                (
                    effective_epic_id,
                    name,
                    notes or existing["notes"] or "",
                    meta_json,
                    now,
                    existing["id"],
                ),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM traceability_artifacts WHERE id=?",
                (existing["id"],),
            ).fetchone()
            return _row_to_trace_artifact(row)

        artifact = TraceArtifact(
            id=make_id(_TRACE_LAYER_PREFIX[layer]),
            project_id=project_id,
            epic_id=epic_id,
            feature_id=feature_id,
            layer=layer,
            artifact_key=key,
            artifact_name=name,
            notes=notes,
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
        )
        conn.execute(
            """INSERT INTO traceability_artifacts
               (id, project_id, epic_id, feature_id, layer, artifact_key,
                artifact_name, notes, metadata_json, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                artifact.id,
                artifact.project_id,
                artifact.epic_id,
                artifact.feature_id,
                artifact.layer,
                artifact.artifact_key,
                artifact.artifact_name,
                artifact.notes,
                json.dumps(artifact.metadata, ensure_ascii=False),
                artifact.created_at,
                artifact.updated_at,
            ),
        )
        conn.commit()
        return artifact
    finally:
        conn.close()


def list_project_trace_artifacts(
    project_id: str,
    layer: str = "",
) -> list[TraceArtifact]:
    """List project-scoped traceability artifacts."""
    _ensure_tables()
    conn = get_db()
    try:
        if layer:
            rows = conn.execute(
                """SELECT * FROM traceability_artifacts
                   WHERE project_id=? AND layer=?
                   ORDER BY feature_id, layer, created_at""",
                (project_id, layer),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM traceability_artifacts
                   WHERE project_id=?
                   ORDER BY feature_id, layer, created_at""",
                (project_id,),
            ).fetchall()
    finally:
        conn.close()
    return [_row_to_trace_artifact(r) for r in rows]


def _row_to_trace_artifact(row) -> TraceArtifact:
    return TraceArtifact(
        id=row["id"],
        project_id=row["project_id"],
        epic_id=row["epic_id"] or "",
        feature_id=row["feature_id"] or "",
        layer=row["layer"] or "",
        artifact_key=row["artifact_key"] or "",
        artifact_name=row["artifact_name"] or "",
        notes=row["notes"] or "",
        metadata=json.loads(row["metadata_json"] or "{}"),
        created_at=row["created_at"] or "",
        updated_at=row["updated_at"] or "",
    )


# ── Coverage computation ─────────────────────────────────────────

# Layer weights for coverage_pct (must sum to 100)
_LAYER_WEIGHTS = {
    "has_persona":  5,
    "has_ihm":      10,
    "has_code":     20,
    "has_tu":       15,
    "has_e2e":      15,
    "has_crud":     10,
    "has_rbac":     10,
    "has_screens":  10,
    "has_nft":      5,
}

# link_type → layer flag
_LINK_TYPE_TO_FLAG = {
    "ihm":           "has_ihm",
    "code":          "has_code",
    "test_tu":       "has_tu",
    "test_e2e":      "has_e2e",
    "crud":          "has_crud",
    "rbac":          "has_rbac",
    "screen":        "has_screens",
    "nft":           "has_nft",
    # legacy compat
    "implements":    "has_code",
    "tests":         "has_tu",
    "covers":        "has_e2e",
}


def update_feature_coverage(feature_id: str) -> dict:
    """Recompute has_* flags and coverage_pct for a feature from traceability_links + nft_tests.
    Returns the updated flags dict."""
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT link_type FROM traceability_links
               WHERE (source_id=? AND source_type='feature')
                  OR (target_id=? AND target_type='feature')""",
            (feature_id, feature_id)
        ).fetchall()
        link_types = {r["link_type"] for r in rows}

        # NFT: check nft_tests table directly
        nft_row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM nft_tests WHERE feature_id=?",
            (feature_id,),
        ).fetchone()
        nft_count = int((nft_row["cnt"] if nft_row else 0) or 0)

        # Persona: check traceability_links for persona→feature
        persona_row = conn.execute(
            """SELECT COUNT(*) AS cnt FROM traceability_links
               WHERE target_id=? AND target_type='feature' AND source_type='persona'""",
            (feature_id,),
        ).fetchone()
        persona_count = int((persona_row["cnt"] if persona_row else 0) or 0)

        # Screen: check project_screens table
        screen_row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM project_screens WHERE feature_id=?",
            (feature_id,),
        ).fetchone()
        screen_count = int((screen_row["cnt"] if screen_row else 0) or 0)

        flags: dict[str, bool] = {}
        for lt in link_types:
            flag = _LINK_TYPE_TO_FLAG.get(lt)
            if flag:
                flags[flag] = True

        flags["has_nft"]     = nft_count > 0
        flags["has_persona"] = persona_count > 0
        flags["has_screens"] = flags.get("has_screens", False) or (screen_count > 0)

        # Compute weighted coverage_pct
        score = sum(w for flag, w in _LAYER_WEIGHTS.items() if flags.get(flag, False))
        coverage_pct = round(score)

        # Persist flags to features table
        set_parts = ", ".join(f"{k}=?" for k in flags)
        set_parts += ", coverage_pct=?"
        values = list(flags.values()) + [coverage_pct, feature_id]
        if set_parts:
            try:
                conn.execute(
                    f"UPDATE features SET {set_parts} WHERE id=?", values
                )
                conn.commit()
            except Exception as e:
                logger.warning("update_feature_coverage write failed: %s", e)

        return {"feature_id": feature_id, "flags": flags, "coverage_pct": coverage_pct}
    finally:
        conn.close()


# ── Chain Report ─────────────────────────────────────────────────

@dataclass
class FeatureChainStatus:
    feature_id: str = ""
    trace_uuid: str = ""
    epic_id: str = ""
    name: str = ""
    status: str = ""
    has_persona: bool = False
    has_ihm: bool = False
    has_code: bool = False
    has_tu: bool = False
    has_e2e: bool = False
    has_crud: bool = False
    has_rbac: bool = False
    has_screens: bool = False
    has_nft: bool = False
    coverage_pct: float = 0.0
    story_count: int = 0
    ac_count: int = 0
    missing_layers: list[str] = field(default_factory=list)


def _rows_to_dicts(rows) -> list[dict]:
    payload = []
    for row in rows:
        if isinstance(row, dict):
            payload.append(dict(row))
            continue
        keys = getattr(row, "keys", None)
        if callable(keys):
            payload.append({k: row[k] for k in row.keys()})
            continue
        payload.append(dict(row))
    return payload


def _coerce_jsonable(value):
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


_UUID_POLICY = "canonical-v5 + source-id"
_TRACE_LAYER_KEYS = (
    "persona",
    "ihm",
    "code",
    "tu",
    "e2e",
    "crud",
    "rbac",
    "screens",
    "nft",
)

_TRACE_KIND_ALIASES = {
    "mission": "epic",
    "epic": "epic",
    "feature": "feature",
    "story": "user_story",
    "user_story": "user_story",
    "acceptance_criterion": "acceptance_criterion",
    "acceptancecriteria": "acceptance_criterion",
    "persona": "persona",
    "nft_test": "nft_test",
    "screen": "screen",
    "project_screen": "screen",
    "traceability_artifact": "traceability_artifact",
}


def _canonical_trace_kind(kind: str) -> str:
    normalized = (kind or "artifact").strip().lower().replace("-", "_")
    return _TRACE_KIND_ALIASES.get(normalized, normalized or "artifact")


def _trace_uuid(project_id: str, artifact_type: str, source_id: str) -> str:
    if not project_id or not source_id:
        return ""
    return make_trace_uuid(_canonical_trace_kind(artifact_type), project_id, source_id)


def _build_layer_coverage(features: list[dict]) -> dict[str, int]:
    total = len(features)
    if total == 0:
        return {layer: 0 for layer in _TRACE_LAYER_KEYS}
    return {
        layer: round(100 * sum(1 for f in features if f.get("layers", {}).get(layer)) / total)
        for layer in _TRACE_LAYER_KEYS
    }


def _build_layer_gap_counts(features: list[dict]) -> dict[str, int]:
    return {
        layer: sum(1 for f in features if layer in f.get("missing", []))
        for layer in _TRACE_LAYER_KEYS
    }


def _build_gap_items(features: list[dict]) -> list[dict]:
    return [
        {
            "feature": f["name"],
            "feature_id": f["id"],
            "trace_uuid": f.get("trace_uuid", ""),
            "missing": f["missing"],
        }
        for f in features
        if f.get("missing")
    ]


def _decorate_rows_with_trace_uuid(
    project_id: str,
    artifact_type: str,
    rows: list[dict],
) -> list[dict]:
    decorated = []
    for row in rows:
        payload = dict(row)
        source_id = str(payload.get("id") or "")
        payload["trace_uuid"] = _trace_uuid(project_id, artifact_type, source_id)
        decorated.append(payload)
    return decorated


def _build_uuid_registry(
    project_id: str,
    artifact_type: str,
    rows: list[dict],
) -> list[dict]:
    registry = []
    for row in rows:
        source_id = str(row.get("id") or "")
        if not source_id:
            continue
        registry.append(
            {
                "artifact_type": _canonical_trace_kind(artifact_type),
                "source_id": source_id,
                "trace_uuid": row.get("trace_uuid") or _trace_uuid(project_id, artifact_type, source_id),
                "display_id": source_id,
                "project_id": project_id,
            }
        )
    return registry


def _load_chain_scope(
    conn,
    feature_query: str,
    feature_params: tuple | list,
    *,
    persona_query: str,
    persona_params: tuple | list,
    nft_query: str,
    nft_params: tuple | list,
    artifact_query: str,
    artifact_params: tuple | list,
):
    features = conn.execute(feature_query, feature_params).fetchall()
    feature_ids = [r["id"] for r in features]

    story_counts: dict[str, int] = {}
    ac_counts: dict[str, int] = {}
    if feature_ids:
        ph = ",".join("?" for _ in feature_ids)
        for r in conn.execute(
            f"""SELECT feature_id, COUNT(*) cnt
                FROM user_stories
                WHERE feature_id IN ({ph})
                GROUP BY feature_id""",
            feature_ids,
        ).fetchall():
            story_counts[r["feature_id"]] = r["cnt"]

        for r in conn.execute(
            f"""SELECT feature_id, COUNT(*) cnt
                FROM acceptance_criteria
                WHERE feature_id IN ({ph})
                GROUP BY feature_id""",
            feature_ids,
        ).fetchall():
            ac_counts[r["feature_id"]] = r["cnt"]

    personas = conn.execute(persona_query, persona_params).fetchall()
    nfts = conn.execute(nft_query, nft_params).fetchall()
    artifact_row = conn.execute(artifact_query, artifact_params).fetchone()
    artifact_count = int((artifact_row["cnt"] if artifact_row else 0) or 0)
    return features, story_counts, ac_counts, personas, nfts, artifact_count


def _build_chain_report(
    *,
    project_id: str,
    scope_key: str,
    scope_id: str,
    features,
    story_counts: dict[str, int],
    ac_counts: dict[str, int],
    personas,
    nfts,
    artifact_count: int,
    epic_count: int | None = None,
    epics: list[dict] | None = None,
) -> dict:
    feature_statuses = []
    total_coverage = 0.0
    for f in features:
        flags = {
            "has_persona": bool(f["has_persona"]),
            "has_ihm": bool(f["has_ihm"]),
            "has_code": bool(f["has_code"]),
            "has_tu": bool(f["has_tu"]),
            "has_e2e": bool(f["has_e2e"]),
            "has_crud": bool(f["has_crud"]),
            "has_rbac": bool(f["has_rbac"]),
            "has_screens": bool(f["has_screens"]),
            "has_nft": bool(f["has_nft"]),
        }
        missing = [k.replace("has_", "") for k, v in flags.items() if not v]
        fs = FeatureChainStatus(
            feature_id=f["id"],
            trace_uuid=_trace_uuid(project_id, "feature", f["id"]),
            epic_id=f["epic_id"] if "epic_id" in f else "",
            name=f["name"],
            status=f["status"],
            coverage_pct=float(f["coverage_pct"]),
            story_count=story_counts.get(f["id"], 0),
            ac_count=ac_counts.get(f["id"], 0),
            missing_layers=missing,
            **flags,
        )
        feature_statuses.append(fs)
        total_coverage += fs.coverage_pct

    avg_coverage = round(total_coverage / max(len(feature_statuses), 1), 1)
    payload = {
        scope_key: scope_id,
        "project_id": project_id,
        "project_trace_uuid": _trace_uuid(project_id, "project", project_id),
        "uuid_policy": _UUID_POLICY,
        "feature_count": len(feature_statuses),
        "persona_count": len(personas),
        "artifact_count": artifact_count,
        "avg_coverage_pct": avg_coverage,
        "nft_summary": [dict(r) for r in nfts],
        "features": [
            {
                "id": fs.feature_id,
                "trace_uuid": fs.trace_uuid,
                "epic_id": fs.epic_id,
                "epic_trace_uuid": _trace_uuid(project_id, "epic", fs.epic_id) if fs.epic_id else "",
                "name": fs.name,
                "status": fs.status,
                "coverage_pct": fs.coverage_pct,
                "story_count": fs.story_count,
                "ac_count": fs.ac_count,
                "layers": {
                    "persona": fs.has_persona,
                    "ihm": fs.has_ihm,
                    "code": fs.has_code,
                    "tu": fs.has_tu,
                    "e2e": fs.has_e2e,
                    "crud": fs.has_crud,
                    "rbac": fs.has_rbac,
                    "screens": fs.has_screens,
                    "nft": fs.has_nft,
                },
                "missing": fs.missing_layers,
            }
            for fs in feature_statuses
        ],
    }
    payload["layer_coverage"] = _build_layer_coverage(payload["features"])
    payload["gap_count"] = sum(1 for item in payload["features"] if item.get("missing"))
    payload["layer_gap_counts"] = _build_layer_gap_counts(payload["features"])
    if epic_count is not None:
        payload["epic_count"] = epic_count
    if epics is not None:
        payload["epics"] = epics
    return payload


def get_chain_report(epic_id: str) -> dict:
    """Full 13-layer traceability report for an epic."""
    _ensure_tables()
    epic_table = _epic_table_name()
    conn = get_db()
    try:
        epic_row = conn.execute(
            f"SELECT project_id FROM {epic_table} WHERE id=?",
            (epic_id,),
        ).fetchone()
        project_id = (epic_row["project_id"] if epic_row else "") or ""
        features, story_counts, ac_counts, personas, nfts, artifact_count = _load_chain_scope(
            conn,
            """SELECT id, epic_id, name, status,
                       COALESCE(has_persona, FALSE)  has_persona,
                       COALESCE(has_ihm, FALSE)       has_ihm,
                       COALESCE(has_code, FALSE)      has_code,
                      COALESCE(has_tu, FALSE)        has_tu,
                      COALESCE(has_e2e, FALSE)       has_e2e,
                      COALESCE(has_crud, FALSE)      has_crud,
                      COALESCE(has_rbac, FALSE)      has_rbac,
                      COALESCE(has_screens, FALSE)   has_screens,
                      COALESCE(has_nft, FALSE)       has_nft,
                      COALESCE(coverage_pct, 0)      coverage_pct
               FROM features WHERE epic_id=? ORDER BY created_at""",
            (epic_id,),
            persona_query="SELECT * FROM personas WHERE epic_id=?",
            persona_params=(epic_id,),
            nft_query=(
                "SELECT nft_type, result, COUNT(*) cnt FROM nft_tests "
                "WHERE epic_id=? GROUP BY nft_type, result"
            ),
            nft_params=(epic_id,),
            artifact_query="SELECT COUNT(*) cnt FROM traceability_artifacts WHERE epic_id=?",
            artifact_params=(epic_id,),
        )
    finally:
        conn.close()

    return _build_chain_report(
        project_id=project_id,
        scope_key="epic_id",
        scope_id=epic_id,
        features=features,
        story_counts=story_counts,
        ac_counts=ac_counts,
        personas=personas,
        nfts=nfts,
        artifact_count=artifact_count,
    )


def get_project_chain_report(project_id: str) -> dict:
    """Full 13-layer traceability report across all epics of a project."""
    _ensure_tables()
    epic_table = _epic_table_name()
    conn = get_db()
    try:
        epic_rows = conn.execute(
            f"""SELECT id, name, status
               FROM {epic_table}
               WHERE project_id=?
               ORDER BY created_at""",
            (project_id,),
        ).fetchall()
        features, story_counts, ac_counts, personas, nfts, artifact_count = _load_chain_scope(
            conn,
            f"""SELECT id, epic_id, name, status,
                       COALESCE(has_persona, FALSE)  has_persona,
                       COALESCE(has_ihm, FALSE)       has_ihm,
                       COALESCE(has_code, FALSE)      has_code,
                      COALESCE(has_tu, FALSE)        has_tu,
                      COALESCE(has_e2e, FALSE)       has_e2e,
                      COALESCE(has_crud, FALSE)      has_crud,
                      COALESCE(has_rbac, FALSE)      has_rbac,
                      COALESCE(has_screens, FALSE)   has_screens,
                      COALESCE(has_nft, FALSE)       has_nft,
                      COALESCE(coverage_pct, 0)      coverage_pct
                FROM features
                WHERE epic_id IN (SELECT id FROM {epic_table} WHERE project_id=?)
                ORDER BY created_at""",
            (project_id,),
            persona_query="SELECT * FROM personas WHERE project_id=?",
            persona_params=(project_id,),
            nft_query=(
                "SELECT nft_type, result, COUNT(*) cnt FROM nft_tests "
                "WHERE project_id=? GROUP BY nft_type, result"
            ),
            nft_params=(project_id,),
            artifact_query="SELECT COUNT(*) cnt FROM traceability_artifacts WHERE project_id=?",
            artifact_params=(project_id,),
        )
    finally:
        conn.close()

    return _build_chain_report(
        project_id=project_id,
        scope_key="project_id",
        scope_id=project_id,
        features=features,
        story_counts=story_counts,
        ac_counts=ac_counts,
        personas=personas,
        nfts=nfts,
        artifact_count=artifact_count,
        epic_count=len(epic_rows),
        epics=[
            {
                "id": r["id"],
                "trace_uuid": _trace_uuid(project_id, "epic", r["id"]),
                "name": r["name"] or "",
                "status": r["status"] or "",
            }
            for r in epic_rows
        ],
    )


def validate_chain(epic_id: str, threshold: int = 80) -> dict:
    """E2E chain validation — returns PASS/FAIL per layer and overall."""
    report = get_chain_report(epic_id)
    features = report["features"]
    total = len(features)
    if total == 0:
        return {"verdict": "SKIP", "reason": "no features", "epic_id": epic_id}

    fully_covered = [f for f in features if not f.get("missing")]
    fully_pct = round(100 * len(fully_covered) / total)
    gaps = _build_gap_items(features)
    gap_count = len(gaps)

    verdict = "PASS" if fully_pct >= threshold else "FAIL"

    return {
        "verdict": verdict,
        "epic_id": epic_id,
        "total_features": total,
        "avg_coverage_pct": report["avg_coverage_pct"],
        "fully_covered_count": len(fully_covered),
        "fully_covered_pct": fully_pct,
        "threshold": threshold,
        "layer_coverage": report.get("layer_coverage", _build_layer_coverage(features)),
        "layer_gap_counts": report.get("layer_gap_counts", _build_layer_gap_counts(features)),
        "gap_count": gap_count,
        "gaps_truncated": gap_count > 30,
        "gaps": gaps[:30],
        "persona_count": report["persona_count"],
        "nft_summary": report["nft_summary"],
    }


def validate_project_chain(project_id: str, threshold: int = 80) -> dict:
    """Project-wide E2E chain validation across all project epics."""
    report = get_project_chain_report(project_id)
    features = report["features"]
    total = len(features)
    if total == 0:
        return {"verdict": "SKIP", "reason": "no features", "project_id": project_id}

    fully_covered = [f for f in features if not f.get("missing")]
    fully_pct = round(100 * len(fully_covered) / total)
    gaps = _build_gap_items(features)
    gap_count = len(gaps)
    verdict = "PASS" if fully_pct >= threshold else "FAIL"

    return {
        "verdict": verdict,
        "project_id": project_id,
        "epic_count": report.get("epic_count", 0),
        "total_features": total,
        "avg_coverage_pct": report["avg_coverage_pct"],
        "fully_covered_count": len(fully_covered),
        "fully_covered_pct": fully_pct,
        "threshold": threshold,
        "layer_coverage": report.get("layer_coverage", _build_layer_coverage(features)),
        "layer_gap_counts": report.get("layer_gap_counts", _build_layer_gap_counts(features)),
        "gap_count": gap_count,
        "gaps_truncated": gap_count > 30,
        "gaps": gaps[:30],
        "persona_count": report["persona_count"],
        "artifact_count": report.get("artifact_count", 0),
        "nft_summary": report["nft_summary"],
    }


_EXPORT_SQLITE_SCHEMAS = {
    "export_meta": """
        CREATE TABLE export_meta (
            project_id TEXT PRIMARY KEY,
            exported_at TEXT NOT NULL,
            uuid_policy TEXT DEFAULT '',
            epic_count INTEGER DEFAULT 0,
            feature_count INTEGER DEFAULT 0,
            persona_count INTEGER DEFAULT 0,
            artifact_count INTEGER DEFAULT 0,
            avg_coverage_pct REAL DEFAULT 0,
            e2e_verdict TEXT DEFAULT 'SKIP',
            fully_covered_pct INTEGER DEFAULT 0,
            summary_json TEXT DEFAULT '{}'
        )
    """,
    "epics": """
        CREATE TABLE epics (
            id TEXT PRIMARY KEY,
            trace_uuid TEXT DEFAULT '',
            project_id TEXT NOT NULL,
            name TEXT DEFAULT '',
            description TEXT DEFAULT '',
            goal TEXT DEFAULT '',
            status TEXT DEFAULT '',
            workflow_id TEXT DEFAULT '',
            created_at TEXT DEFAULT '',
            completed_at TEXT DEFAULT ''
        )
    """,
    "features": """
        CREATE TABLE features (
            id TEXT PRIMARY KEY,
            trace_uuid TEXT DEFAULT '',
            epic_id TEXT DEFAULT '',
            name TEXT DEFAULT '',
            description TEXT DEFAULT '',
            acceptance_criteria TEXT DEFAULT '',
            priority INTEGER DEFAULT 0,
            status TEXT DEFAULT '',
            story_points INTEGER DEFAULT 0,
            assigned_to TEXT DEFAULT '',
            has_persona INTEGER DEFAULT 0,
            has_ihm INTEGER DEFAULT 0,
            has_code INTEGER DEFAULT 0,
            has_tu INTEGER DEFAULT 0,
            has_e2e INTEGER DEFAULT 0,
            has_crud INTEGER DEFAULT 0,
            has_rbac INTEGER DEFAULT 0,
            has_screens INTEGER DEFAULT 0,
            has_nft INTEGER DEFAULT 0,
            coverage_pct REAL DEFAULT 0,
            created_at TEXT DEFAULT '',
            completed_at TEXT DEFAULT ''
        )
    """,
    "user_stories": """
        CREATE TABLE user_stories (
            id TEXT PRIMARY KEY,
            trace_uuid TEXT DEFAULT '',
            feature_id TEXT DEFAULT '',
            title TEXT DEFAULT '',
            description TEXT DEFAULT '',
            acceptance_criteria TEXT DEFAULT '',
            story_points INTEGER DEFAULT 0,
            priority INTEGER DEFAULT 0,
            status TEXT DEFAULT '',
            sprint_id TEXT DEFAULT '',
            assigned_to TEXT DEFAULT '',
            created_at TEXT DEFAULT '',
            completed_at TEXT DEFAULT ''
        )
    """,
    "acceptance_criteria": """
        CREATE TABLE acceptance_criteria (
            id TEXT PRIMARY KEY,
            trace_uuid TEXT DEFAULT '',
            feature_id TEXT DEFAULT '',
            story_id TEXT DEFAULT '',
            title TEXT DEFAULT '',
            given_text TEXT DEFAULT '',
            when_text TEXT DEFAULT '',
            then_text TEXT DEFAULT '',
            and_text TEXT DEFAULT '',
            status TEXT DEFAULT '',
            verified_by TEXT DEFAULT '',
            created_at TEXT DEFAULT '',
            updated_at TEXT DEFAULT ''
        )
    """,
    "personas": """
        CREATE TABLE personas (
            id TEXT PRIMARY KEY,
            trace_uuid TEXT DEFAULT '',
            project_id TEXT DEFAULT '',
            epic_id TEXT DEFAULT '',
            name TEXT DEFAULT '',
            role TEXT DEFAULT '',
            description TEXT DEFAULT '',
            goals TEXT DEFAULT '',
            frustrations TEXT DEFAULT '',
            created_at TEXT DEFAULT '',
            updated_at TEXT DEFAULT ''
        )
    """,
    "nft_tests": """
        CREATE TABLE nft_tests (
            id TEXT PRIMARY KEY,
            trace_uuid TEXT DEFAULT '',
            project_id TEXT DEFAULT '',
            epic_id TEXT DEFAULT '',
            feature_id TEXT DEFAULT '',
            nft_type TEXT DEFAULT '',
            name TEXT DEFAULT '',
            criterion TEXT DEFAULT '',
            threshold TEXT DEFAULT '',
            result TEXT DEFAULT '',
            measured_at TEXT DEFAULT '',
            created_at TEXT DEFAULT ''
        )
    """,
    "project_screens": """
        CREATE TABLE project_screens (
            id TEXT PRIMARY KEY,
            trace_uuid TEXT DEFAULT '',
            project_id TEXT DEFAULT '',
            name TEXT DEFAULT '',
            page_url TEXT DEFAULT '',
            svg_path TEXT DEFAULT '',
            feature_id TEXT DEFAULT '',
            mission_id TEXT DEFAULT '',
            created_at TEXT DEFAULT ''
        )
    """,
    "traceability_artifacts": """
        CREATE TABLE traceability_artifacts (
            id TEXT PRIMARY KEY,
            trace_uuid TEXT DEFAULT '',
            project_id TEXT DEFAULT '',
            epic_id TEXT DEFAULT '',
            feature_id TEXT DEFAULT '',
            layer TEXT DEFAULT '',
            artifact_key TEXT DEFAULT '',
            artifact_name TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            metadata_json TEXT DEFAULT '{}',
            created_at TEXT DEFAULT '',
            updated_at TEXT DEFAULT ''
        )
    """,
    "traceability_links": """
        CREATE TABLE traceability_links (
            source_id TEXT DEFAULT '',
            source_trace_uuid TEXT DEFAULT '',
            source_type TEXT DEFAULT '',
            target_id TEXT DEFAULT '',
            target_trace_uuid TEXT DEFAULT '',
            target_type TEXT DEFAULT '',
            link_type TEXT DEFAULT '',
            coverage_pct INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            project_id TEXT DEFAULT '',
            created_at TEXT DEFAULT ''
        )
    """,
    "feature_traceability_status": """
        CREATE TABLE feature_traceability_status (
            feature_id TEXT PRIMARY KEY,
            trace_uuid TEXT DEFAULT '',
            name TEXT DEFAULT '',
            status TEXT DEFAULT '',
            coverage_pct REAL DEFAULT 0,
            story_count INTEGER DEFAULT 0,
            ac_count INTEGER DEFAULT 0,
            has_persona INTEGER DEFAULT 0,
            has_ihm INTEGER DEFAULT 0,
            has_code INTEGER DEFAULT 0,
            has_tu INTEGER DEFAULT 0,
            has_e2e INTEGER DEFAULT 0,
            has_crud INTEGER DEFAULT 0,
            has_rbac INTEGER DEFAULT 0,
            has_screens INTEGER DEFAULT 0,
            has_nft INTEGER DEFAULT 0,
            missing_json TEXT DEFAULT '[]'
        )
    """,
    "uuid_registry": """
        CREATE TABLE uuid_registry (
            artifact_type TEXT NOT NULL,
            source_id TEXT NOT NULL,
            trace_uuid TEXT NOT NULL,
            display_id TEXT DEFAULT '',
            project_id TEXT DEFAULT '',
            PRIMARY KEY (artifact_type, source_id, project_id)
        )
    """,
}


def _write_export_rows(sqlite_conn: sqlite3.Connection, table: str, rows: list[dict]) -> None:
    sqlite_conn.execute(f"DELETE FROM {table}")
    if not rows:
        return
    columns = list(rows[0].keys())
    placeholders = ", ".join("?" for _ in columns)
    sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
    sqlite_conn.executemany(
        sql,
        [tuple(_coerce_jsonable(row.get(col)) for col in columns) for row in rows],
    )


def export_project_traceability_sqlite(project_id: str, output_path: str) -> dict:
    """Export project traceability into a standalone SQLite DB."""
    _ensure_tables()
    epic_table = _epic_table_name()
    report = get_project_chain_report(project_id)
    check = validate_project_chain(project_id)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    main = get_db()
    try:
        epics = _decorate_rows_with_trace_uuid(
            project_id,
            "epic",
            _rows_to_dicts(
                main.execute(
                f"""SELECT id, project_id, name, description, goal, status,
                          workflow_id, created_at, completed_at
                   FROM {epic_table}
                   WHERE project_id=?
                   ORDER BY created_at""",
                (project_id,),
                ).fetchall()
            ),
        )
        features = _decorate_rows_with_trace_uuid(
            project_id,
            "feature",
            _rows_to_dicts(
                main.execute(
                f"""SELECT id, epic_id, name, description, acceptance_criteria,
                          priority, status, story_points, assigned_to,
                          COALESCE(has_persona, FALSE)  AS has_persona,
                          COALESCE(has_ihm, FALSE)      AS has_ihm,
                          COALESCE(has_code, FALSE)     AS has_code,
                          COALESCE(has_tu, FALSE)       AS has_tu,
                          COALESCE(has_e2e, FALSE)      AS has_e2e,
                          COALESCE(has_crud, FALSE)     AS has_crud,
                          COALESCE(has_rbac, FALSE)     AS has_rbac,
                          COALESCE(has_screens, FALSE)  AS has_screens,
                          COALESCE(has_nft, FALSE)      AS has_nft,
                          COALESCE(coverage_pct, 0)     AS coverage_pct,
                          created_at, completed_at
                   FROM features
                   WHERE epic_id IN (SELECT id FROM {epic_table} WHERE project_id=?)
                   ORDER BY created_at""",
                (project_id,),
                ).fetchall()
            ),
        )
        stories = _decorate_rows_with_trace_uuid(
            project_id,
            "user_story",
            _rows_to_dicts(
                main.execute(
                f"""SELECT us.id, us.feature_id, us.title, us.description,
                          us.acceptance_criteria, us.story_points, us.priority,
                          us.status, us.sprint_id, us.assigned_to,
                          us.created_at, us.completed_at
                   FROM user_stories us
                   JOIN features f ON us.feature_id = f.id
                   JOIN {epic_table} m ON f.epic_id = m.id
                   WHERE m.project_id=?
                   ORDER BY us.created_at""",
                (project_id,),
                ).fetchall()
            ),
        )
        acs = _decorate_rows_with_trace_uuid(
            project_id,
            "acceptance_criterion",
            _rows_to_dicts(
                main.execute(
                f"""SELECT ac.id, ac.feature_id, ac.story_id, ac.title,
                          ac.given_text, ac.when_text, ac.then_text, ac.and_text,
                          ac.status, ac.verified_by, ac.created_at, ac.updated_at
                   FROM acceptance_criteria ac
                   JOIN features f ON ac.feature_id = f.id
                   JOIN {epic_table} m ON f.epic_id = m.id
                   WHERE m.project_id=?
                   ORDER BY ac.created_at""",
                (project_id,),
                ).fetchall()
            ),
        )
        personas = _decorate_rows_with_trace_uuid(
            project_id,
            "persona",
            _rows_to_dicts(
                main.execute(
                "SELECT * FROM personas WHERE project_id=? ORDER BY created_at",
                (project_id,),
                ).fetchall()
            ),
        )
        nfts = _decorate_rows_with_trace_uuid(
            project_id,
            "nft_test",
            _rows_to_dicts(
                main.execute(
                "SELECT * FROM nft_tests WHERE project_id=? ORDER BY created_at",
                (project_id,),
                ).fetchall()
            ),
        )
        screens = _decorate_rows_with_trace_uuid(
            project_id,
            "screen",
            _rows_to_dicts(
                main.execute(
                "SELECT * FROM project_screens WHERE project_id=? ORDER BY created_at",
                (project_id,),
                ).fetchall()
            ),
        )
        artifacts = _decorate_rows_with_trace_uuid(
            project_id,
            "traceability_artifact",
            _rows_to_dicts(
                main.execute(
                    """SELECT * FROM traceability_artifacts
                       WHERE project_id=?
                       ORDER BY feature_id, layer, created_at""",
                    (project_id,),
                ).fetchall()
            ),
        )

        known_ids = {
            row["id"] for row in epics + features + stories + acs + personas + nfts + screens + artifacts
            if row.get("id")
        }
        if known_ids:
            placeholders = ", ".join("?" for _ in known_ids)
            link_rows = _rows_to_dicts(
                main.execute(
                    f"""SELECT DISTINCT source_id, source_type, target_id, target_type,
                               link_type, coverage_pct, notes,
                               COALESCE(project_id, '') AS project_id,
                               created_at
                        FROM traceability_links
                        WHERE COALESCE(project_id, '') = ?
                           OR source_id IN ({placeholders})
                           OR target_id IN ({placeholders})
                        ORDER BY created_at""",
                    [project_id, *known_ids, *known_ids],
                ).fetchall()
            )
        else:
            link_rows = _rows_to_dicts(
                main.execute(
                    """SELECT source_id, source_type, target_id, target_type,
                              link_type, coverage_pct, notes,
                              COALESCE(project_id, '') AS project_id,
                              created_at
                       FROM traceability_links
                       WHERE COALESCE(project_id, '') = ?
                       ORDER BY created_at""",
                    (project_id,),
                ).fetchall()
            )
        for row in link_rows:
            scope_project_id = row.get("project_id") or project_id
            row["source_trace_uuid"] = _trace_uuid(
                scope_project_id,
                row.get("source_type", ""),
                row.get("source_id", ""),
            )
            row["target_trace_uuid"] = _trace_uuid(
                scope_project_id,
                row.get("target_type", ""),
                row.get("target_id", ""),
            )
    finally:
        main.close()

    feature_status_rows = [
        {
            "feature_id": item["id"],
            "trace_uuid": item.get("trace_uuid", _trace_uuid(project_id, "feature", item["id"])),
            "name": item["name"],
            "status": item["status"],
            "coverage_pct": item["coverage_pct"],
            "story_count": item["story_count"],
            "ac_count": item["ac_count"],
            "has_persona": item["layers"]["persona"],
            "has_ihm": item["layers"]["ihm"],
            "has_code": item["layers"]["code"],
            "has_tu": item["layers"]["tu"],
            "has_e2e": item["layers"]["e2e"],
            "has_crud": item["layers"]["crud"],
            "has_rbac": item["layers"]["rbac"],
            "has_screens": item["layers"]["screens"],
            "has_nft": item["layers"]["nft"],
            "missing_json": json.dumps(item["missing"], ensure_ascii=False),
        }
        for item in report["features"]
    ]
    uuid_registry_rows = []
    for artifact_type, rows in (
        ("epic", epics),
        ("feature", features),
        ("user_story", stories),
        ("acceptance_criterion", acs),
        ("persona", personas),
        ("nft_test", nfts),
        ("screen", screens),
        ("traceability_artifact", artifacts),
    ):
        uuid_registry_rows.extend(_build_uuid_registry(project_id, artifact_type, rows))

    export_db = sqlite3.connect(str(output))
    try:
        for table, schema in _EXPORT_SQLITE_SCHEMAS.items():
            export_db.execute(schema)
        _write_export_rows(
            export_db,
            "export_meta",
            [
                {
                    "project_id": project_id,
                    "exported_at": datetime.now(timezone.utc).isoformat(),
                    "uuid_policy": _UUID_POLICY,
                    "epic_count": report.get("epic_count", 0),
                    "feature_count": report["feature_count"],
                    "persona_count": report["persona_count"],
                    "artifact_count": report.get("artifact_count", 0),
                    "avg_coverage_pct": report["avg_coverage_pct"],
                    "e2e_verdict": check["verdict"],
                    "fully_covered_pct": check.get("fully_covered_pct", 0),
                    "summary_json": json.dumps(
                        {"report": report, "check": check},
                        ensure_ascii=False,
                    ),
                }
            ],
        )
        _write_export_rows(export_db, "epics", epics)
        _write_export_rows(export_db, "features", features)
        _write_export_rows(export_db, "user_stories", stories)
        _write_export_rows(export_db, "acceptance_criteria", acs)
        _write_export_rows(export_db, "personas", personas)
        _write_export_rows(export_db, "nft_tests", nfts)
        _write_export_rows(export_db, "project_screens", screens)
        _write_export_rows(export_db, "traceability_artifacts", artifacts)
        _write_export_rows(export_db, "traceability_links", link_rows)
        _write_export_rows(export_db, "feature_traceability_status", feature_status_rows)
        _write_export_rows(export_db, "uuid_registry", uuid_registry_rows)
        export_db.commit()
    finally:
        export_db.close()

    return {
        "project_id": project_id,
        "path": str(output),
        "uuid_policy": _UUID_POLICY,
        "epic_count": len(epics),
        "feature_count": len(features),
        "story_count": len(stories),
        "acceptance_criteria_count": len(acs),
        "artifact_count": len(artifacts),
        "screen_count": len(screens),
        "nft_count": len(nfts),
        "link_count": len(link_rows),
        "avg_coverage_pct": report["avg_coverage_pct"],
        "verdict": check["verdict"],
        "gap_count": check.get("gap_count", 0),
    }


# ── Singletons ────────────────────────────────────────────────────

def get_persona_store() -> PersonaStore:
    return PersonaStore()


def get_nft_store() -> NFTStore:
    return NFTStore()
