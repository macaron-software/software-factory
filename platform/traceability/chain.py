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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from ..db.migrations import get_db
from .artifacts import make_id

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
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
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
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_nft_project ON nft_tests(project_id);
CREATE INDEX IF NOT EXISTS idx_nft_feature ON nft_tests(feature_id);
CREATE INDEX IF NOT EXISTS idx_nft_type    ON nft_tests(nft_type);
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


def _ensure_tables():
    conn = get_db()
    try:
        for schema in (_PERSONAS_SCHEMA, _NFT_SCHEMA):
            for stmt in schema.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(s)
        # Add coverage flag columns to features (idempotent)
        for col, defn in _FEATURE_COVERAGE_COLS:
            try:
                conn.execute(f"ALTER TABLE features ADD COLUMN IF NOT EXISTS {col} {defn}")
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
        nft_count = conn.execute(
            "SELECT COUNT(*) FROM nft_tests WHERE feature_id=?",
            (feature_id,)
        ).fetchone()[0]

        # Persona: check traceability_links for persona→feature
        persona_count = conn.execute(
            """SELECT COUNT(*) FROM traceability_links
               WHERE target_id=? AND target_type='feature' AND source_type='persona'""",
            (feature_id,)
        ).fetchone()[0]

        # Screen: check project_screens table
        screen_count = conn.execute(
            "SELECT COUNT(*) FROM project_screens WHERE feature_id=?",
            (feature_id,)
        ).fetchone()[0]

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
    feature_id: str
    name: str
    status: str
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


def get_chain_report(epic_id: str) -> dict:
    """Full 13-layer traceability report for an epic."""
    _ensure_tables()
    conn = get_db()
    try:
        features = conn.execute(
            """SELECT id, name, status,
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
            (epic_id,)
        ).fetchall()

        story_counts = {}
        for r in conn.execute(
            "SELECT feature_id, COUNT(*) cnt FROM user_stories WHERE feature_id IN "
            f"(SELECT id FROM features WHERE epic_id=?) GROUP BY feature_id",
            (epic_id,)
        ).fetchall():
            story_counts[r["feature_id"]] = r["cnt"]

        ac_counts = {}
        for r in conn.execute(
            "SELECT feature_id, COUNT(*) cnt FROM acceptance_criteria WHERE feature_id IN "
            f"(SELECT id FROM features WHERE epic_id=?) GROUP BY feature_id",
            (epic_id,)
        ).fetchall():
            ac_counts[r["feature_id"]] = r["cnt"]

        personas = conn.execute(
            "SELECT * FROM personas WHERE epic_id=?", (epic_id,)
        ).fetchall()

        nfts = conn.execute(
            "SELECT nft_type, result, COUNT(*) cnt FROM nft_tests "
            "WHERE epic_id=? GROUP BY nft_type, result",
            (epic_id,)
        ).fetchall()

    finally:
        conn.close()

    feature_statuses = []
    total_coverage = 0.0
    for f in features:
        flags = {
            "has_persona":  bool(f["has_persona"]),
            "has_ihm":      bool(f["has_ihm"]),
            "has_code":     bool(f["has_code"]),
            "has_tu":       bool(f["has_tu"]),
            "has_e2e":      bool(f["has_e2e"]),
            "has_crud":     bool(f["has_crud"]),
            "has_rbac":     bool(f["has_rbac"]),
            "has_screens":  bool(f["has_screens"]),
            "has_nft":      bool(f["has_nft"]),
        }
        missing = [k.replace("has_", "") for k, v in flags.items() if not v]
        fs = FeatureChainStatus(
            feature_id=f["id"], name=f["name"], status=f["status"],
            coverage_pct=float(f["coverage_pct"]),
            story_count=story_counts.get(f["id"], 0),
            ac_count=ac_counts.get(f["id"], 0),
            missing_layers=missing,
            **flags,
        )
        feature_statuses.append(fs)
        total_coverage += fs.coverage_pct

    avg_coverage = round(total_coverage / max(len(feature_statuses), 1), 1)

    return {
        "epic_id": epic_id,
        "feature_count": len(feature_statuses),
        "persona_count": len(personas),
        "avg_coverage_pct": avg_coverage,
        "nft_summary": [dict(r) for r in nfts],
        "features": [
            {
                "id": fs.feature_id,
                "name": fs.name,
                "status": fs.status,
                "coverage_pct": fs.coverage_pct,
                "story_count": fs.story_count,
                "ac_count": fs.ac_count,
                "layers": {
                    "persona":  fs.has_persona,
                    "ihm":      fs.has_ihm,
                    "code":     fs.has_code,
                    "tu":       fs.has_tu,
                    "e2e":      fs.has_e2e,
                    "crud":     fs.has_crud,
                    "rbac":     fs.has_rbac,
                    "screens":  fs.has_screens,
                    "nft":      fs.has_nft,
                },
                "missing": fs.missing_layers,
            }
            for fs in feature_statuses
        ],
    }


def validate_chain(epic_id: str, threshold: int = 80) -> dict:
    """E2E chain validation — returns PASS/FAIL per layer and overall."""
    report = get_chain_report(epic_id)
    features = report["features"]
    total = len(features)
    if total == 0:
        return {"verdict": "SKIP", "reason": "no features", "epic_id": epic_id}

    layer_names = ["persona", "ihm", "code", "tu", "e2e", "crud", "rbac", "screens", "nft"]
    layer_pass = {l: sum(1 for f in features if f["layers"].get(l)) for l in layer_names}
    layer_pct  = {l: round(100 * layer_pass[l] / total) for l in layer_names}

    fully_covered = [f for f in features if f["coverage_pct"] >= threshold]
    fully_pct = round(100 * len(fully_covered) / total)

    gaps = [
        {"feature": f["name"], "missing": f["missing"]}
        for f in features if f["missing"]
    ]

    verdict = "PASS" if fully_pct >= threshold else "FAIL"

    return {
        "verdict": verdict,
        "epic_id": epic_id,
        "total_features": total,
        "avg_coverage_pct": report["avg_coverage_pct"],
        "fully_covered_pct": fully_pct,
        "threshold": threshold,
        "layer_coverage": layer_pct,
        "gaps": gaps[:30],
        "persona_count": report["persona_count"],
        "nft_summary": report["nft_summary"],
    }


# ── Singletons ────────────────────────────────────────────────────

_persona_store: PersonaStore | None = None
_nft_store: NFTStore | None = None


def get_persona_store() -> PersonaStore:
    global _persona_store
    if _persona_store is None:
        _persona_store = PersonaStore()
    return _persona_store


def get_nft_store() -> NFTStore:
    global _nft_store
    if _nft_store is None:
        _nft_store = NFTStore()
    return _nft_store
