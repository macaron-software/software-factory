"""Pattern store — CRUD + pre-built workflow templates."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..db.migrations import get_db


@dataclass
class PatternDef:
    """A workflow pattern definition."""
    id: str = ""
    name: str = ""
    description: str = ""
    type: str = "sequential"
    agents: list[dict] = field(default_factory=list)
    edges: list[dict] = field(default_factory=list)
    config: dict = field(default_factory=dict)
    memory_config: dict = field(default_factory=dict)
    icon: str = "workflow"
    is_builtin: bool = False
    created_at: str = ""
    updated_at: str = ""


def _row_to_pattern(row) -> PatternDef:
    return PatternDef(
        id=row["id"],
        name=row["name"],
        description=row["description"] or "",
        type=row["type"] or "sequential",
        agents=json.loads(row["agents_json"] or "[]"),
        edges=json.loads(row["edges_json"] or "[]"),
        config=json.loads(row["config_json"] or "{}"),
        memory_config=json.loads(row["memory_config_json"] or "{}"),
        icon=row["icon"] or "workflow",
        is_builtin=bool(row["is_builtin"]),
        created_at=row["created_at"] or "",
        updated_at=row["updated_at"] or "",
    )


class PatternStore:
    """CRUD for workflow patterns."""

    def list_all(self) -> list[PatternDef]:
        db = get_db()
        try:
            rows = db.execute("SELECT * FROM patterns ORDER BY is_builtin DESC, name").fetchall()
            return [_row_to_pattern(r) for r in rows]
        finally:
            db.close()

    def get(self, pattern_id: str) -> Optional[PatternDef]:
        db = get_db()
        try:
            row = db.execute("SELECT * FROM patterns WHERE id = ?", (pattern_id,)).fetchone()
            return _row_to_pattern(row) if row else None
        finally:
            db.close()

    def create(self, p: PatternDef) -> PatternDef:
        if not p.id:
            p.id = str(uuid.uuid4())[:8]
        now = datetime.utcnow().isoformat()
        p.created_at = now
        p.updated_at = now
        db = get_db()
        try:
            db.execute(
                """INSERT OR REPLACE INTO patterns (id, name, description, type, agents_json, edges_json,
                   config_json, memory_config_json, icon, is_builtin, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (p.id, p.name, p.description, p.type,
                 json.dumps(p.agents), json.dumps(p.edges),
                 json.dumps(p.config), json.dumps(p.memory_config),
                 p.icon, int(p.is_builtin), p.created_at, p.updated_at),
            )
            db.commit()
        finally:
            db.close()
        return p

    def update(self, p: PatternDef) -> PatternDef:
        p.updated_at = datetime.utcnow().isoformat()
        db = get_db()
        try:
            db.execute(
                """UPDATE patterns SET name=?, description=?, type=?, agents_json=?, edges_json=?,
                   config_json=?, memory_config_json=?, icon=?, updated_at=?
                   WHERE id=?""",
                (p.name, p.description, p.type,
                 json.dumps(p.agents), json.dumps(p.edges),
                 json.dumps(p.config), json.dumps(p.memory_config),
                 p.icon, p.updated_at, p.id),
            )
            db.commit()
        finally:
            db.close()
        return p

    def delete(self, pattern_id: str) -> bool:
        db = get_db()
        try:
            cur = db.execute("DELETE FROM patterns WHERE id = ? AND is_builtin = 0", (pattern_id,))
            db.commit()
            return cur.rowcount > 0
        finally:
            db.close()

    def count(self) -> int:
        db = get_db()
        try:
            return db.execute("SELECT COUNT(*) FROM patterns").fetchone()[0]
        finally:
            db.close()

    def seed_builtins(self):
        """Seed pre-built pattern templates (upsert)."""

        builtins = [
            PatternDef(
                id="solo-chat", name="Solo Chat", type="solo",
                description="Conversation directe avec un agent spécialiste.",
                icon="bot", is_builtin=True,
                agents=[{"id": "n1", "agent_id": "brain", "label": "Agent", "x": 300, "y": 200}],
                edges=[],
            ),
            PatternDef(
                id="sequential", name="Pipeline Séquentiel", type="sequential",
                description="Chaîne d'agents — la sortie de chacun alimente l'entrée du suivant.",
                icon="workflow", is_builtin=True,
                agents=[
                    {"id": "n1", "agent_id": "brain", "label": "Analyste", "x": 100, "y": 200},
                    {"id": "n2", "agent_id": "worker", "label": "Développeur", "x": 300, "y": 200},
                    {"id": "n3", "agent_id": "code-critic", "label": "Reviewer", "x": 500, "y": 200},
                ],
                edges=[
                    {"from": "n1", "to": "n2", "type": "sequential"},
                    {"from": "n2", "to": "n3", "type": "sequential"},
                ],
            ),
            PatternDef(
                id="parallel", name="Parallèle Fan-out", type="parallel",
                description="Plusieurs agents travaillent en parallèle, résultats fusionnés.",
                icon="workflow", is_builtin=True,
                agents=[
                    {"id": "n1", "agent_id": "brain", "label": "Dispatcher", "x": 100, "y": 200},
                    {"id": "n2", "agent_id": "worker", "label": "Worker A", "x": 300, "y": 100},
                    {"id": "n3", "agent_id": "expert-metier", "label": "Worker B", "x": 300, "y": 300},
                    {"id": "n4", "agent_id": "chef-projet", "label": "Aggregator", "x": 500, "y": 200},
                ],
                edges=[
                    {"from": "n1", "to": "n2", "type": "parallel"},
                    {"from": "n1", "to": "n3", "type": "parallel"},
                    {"from": "n2", "to": "n4", "type": "sequential"},
                    {"from": "n3", "to": "n4", "type": "sequential"},
                ],
            ),
            PatternDef(
                id="adversarial-pair", name="Pair Adversarial", type="loop",
                description="Writer et reviewer itèrent jusqu'au consensus.",
                icon="eye", is_builtin=True,
                agents=[
                    {"id": "n1", "agent_id": "worker", "label": "Writer", "x": 200, "y": 200},
                    {"id": "n2", "agent_id": "code-critic", "label": "Reviewer", "x": 450, "y": 200},
                ],
                edges=[
                    {"from": "n1", "to": "n2", "type": "sequential"},
                    {"from": "n2", "to": "n1", "type": "conditional", "condition": "veto"},
                ],
                config={"max_iterations": 5},
            ),
            PatternDef(
                id="adversarial-cascade", name="Cascade Adversariale", type="sequential",
                description="Swiss Cheese — 4 couches de review (L0→L1a→L1b→L2).",
                icon="lock", is_builtin=True,
                agents=[
                    {"id": "n1", "agent_id": "worker", "label": "Code", "x": 50, "y": 200},
                    {"id": "n2", "agent_id": "code-critic", "label": "L1 Code", "x": 200, "y": 200},
                    {"id": "n3", "agent_id": "security-critic", "label": "L1 Sécu", "x": 350, "y": 200},
                    {"id": "n4", "agent_id": "arch-critic", "label": "L2 Arch", "x": 500, "y": 200},
                ],
                edges=[
                    {"from": "n1", "to": "n2", "type": "sequential"},
                    {"from": "n2", "to": "n3", "type": "sequential"},
                    {"from": "n3", "to": "n4", "type": "sequential"},
                ],
            ),
            PatternDef(
                id="hierarchical", name="Hiérarchique", type="hierarchical",
                description="Manager décompose le travail, workers exécutent, résultats intégrés.",
                icon="building", is_builtin=True,
                agents=[
                    {"id": "n1", "agent_id": "brain", "label": "Superviseur", "x": 300, "y": 80},
                    {"id": "n2", "agent_id": "worker", "label": "Worker A", "x": 100, "y": 280},
                    {"id": "n3", "agent_id": "worker", "label": "Worker B", "x": 300, "y": 280},
                    {"id": "n4", "agent_id": "testeur", "label": "Testeur", "x": 500, "y": 280},
                ],
                edges=[
                    {"from": "n1", "to": "n2", "type": "delegation"},
                    {"from": "n1", "to": "n3", "type": "delegation"},
                    {"from": "n1", "to": "n4", "type": "delegation"},
                    {"from": "n2", "to": "n1", "type": "report"},
                    {"from": "n3", "to": "n1", "type": "report"},
                    {"from": "n4", "to": "n1", "type": "report"},
                ],
            ),
            PatternDef(
                id="sf-tdd", name="SF TDD Pipeline", type="sequential",
                description="Macaron Agent Platform complète : Brain → TDD → Adversarial → Deploy.",
                icon="rocket", is_builtin=True,
                agents=[
                    {"id": "n1", "agent_id": "brain", "label": "Brain", "x": 50, "y": 200},
                    {"id": "n2", "agent_id": "worker", "label": "TDD Worker", "x": 180, "y": 200},
                    {"id": "n3", "agent_id": "code-critic", "label": "Code Critic", "x": 310, "y": 200},
                    {"id": "n4", "agent_id": "security-critic", "label": "Sécu Critic", "x": 440, "y": 200},
                    {"id": "n5", "agent_id": "arch-critic", "label": "Arch Critic", "x": 570, "y": 200},
                    {"id": "n6", "agent_id": "devops", "label": "DevOps", "x": 700, "y": 200},
                ],
                edges=[
                    {"from": "n1", "to": "n2", "type": "sequential"},
                    {"from": "n2", "to": "n3", "type": "sequential"},
                    {"from": "n3", "to": "n4", "type": "sequential"},
                    {"from": "n4", "to": "n5", "type": "sequential"},
                    {"from": "n5", "to": "n6", "type": "sequential"},
                ],
            ),
            PatternDef(
                id="debate", name="Débat", type="network",
                description="Agents argumentent des positions opposées, un juge décide.",
                icon="briefcase", is_builtin=True,
                agents=[
                    {"id": "n1", "agent_id": "worker", "label": "Pour", "x": 150, "y": 280},
                    {"id": "n2", "agent_id": "security-critic", "label": "Contre", "x": 450, "y": 280},
                    {"id": "n3", "agent_id": "brain", "label": "Juge", "x": 300, "y": 80},
                ],
                edges=[
                    {"from": "n1", "to": "n2", "type": "bidirectional"},
                    {"from": "n1", "to": "n3", "type": "report"},
                    {"from": "n2", "to": "n3", "type": "report"},
                ],
                config={"max_rounds": 5},
            ),
            # ── Router: single agent routes to specialist based on input analysis ──
            PatternDef(
                id="router", name="Router", type="router",
                description="Un agent routeur analyse l'entrée et dirige vers le spécialiste approprié.",
                icon="git-branch", is_builtin=True,
                agents=[
                    {"id": "n1", "agent_id": "brain", "label": "Router", "x": 300, "y": 80},
                    {"id": "n2", "agent_id": "worker", "label": "Spécialiste A", "x": 100, "y": 280},
                    {"id": "n3", "agent_id": "code-critic", "label": "Spécialiste B", "x": 300, "y": 280},
                    {"id": "n4", "agent_id": "security-critic", "label": "Spécialiste C", "x": 500, "y": 280},
                ],
                edges=[
                    {"from": "n1", "to": "n2", "type": "route"},
                    {"from": "n1", "to": "n3", "type": "route"},
                    {"from": "n1", "to": "n4", "type": "route"},
                ],
            ),
            # ── Aggregator: multiple inputs → single aggregator → output ──
            PatternDef(
                id="aggregator", name="Agrégateur", type="aggregator",
                description="Plusieurs agents travaillent en parallèle, un agrégateur consolide les résultats.",
                icon="layers", is_builtin=True,
                agents=[
                    {"id": "n1", "agent_id": "worker", "label": "Analyse A", "x": 100, "y": 80},
                    {"id": "n2", "agent_id": "code-critic", "label": "Analyse B", "x": 300, "y": 80},
                    {"id": "n3", "agent_id": "security-critic", "label": "Analyse C", "x": 500, "y": 80},
                    {"id": "n4", "agent_id": "brain", "label": "Agrégateur", "x": 300, "y": 280},
                ],
                edges=[
                    {"from": "n1", "to": "n4", "type": "aggregate"},
                    {"from": "n2", "to": "n4", "type": "aggregate"},
                    {"from": "n3", "to": "n4", "type": "aggregate"},
                ],
            ),
            # ── Human-in-the-loop: agents work, human validates at checkpoints ──
            PatternDef(
                id="human-in-the-loop", name="Human-in-the-Loop", type="human-in-the-loop",
                description="Les agents travaillent, l'humain valide aux points de contrôle (GO/NOGO).",
                icon="user-check", is_builtin=True,
                agents=[
                    {"id": "n1", "agent_id": "brain", "label": "Agent", "x": 100, "y": 200},
                    {"id": "n2", "agent_id": "worker", "label": "Exécuteur", "x": 300, "y": 200},
                    {"id": "n3", "agent_id": "", "label": "Humain", "x": 500, "y": 200},
                ],
                edges=[
                    {"from": "n1", "to": "n2", "type": "sequential"},
                    {"from": "n2", "to": "n3", "type": "checkpoint"},
                ],
                config={"checkpoint_message": "En attente de validation humaine..."},
            ),
            # ── Wave: parallel within waves, sequential across ──
            PatternDef(
                id="wave", name="Wave", type="wave",
                description="Les agents independants s'executent en parallele par vagues. Les dependances determinent l'ordre des vagues.",
                icon="layers", is_builtin=True,
                agents=[
                    {"id": "n1", "agent_id": "", "label": "Agent A", "x": 100, "y": 100},
                    {"id": "n2", "agent_id": "", "label": "Agent B", "x": 300, "y": 100},
                    {"id": "n3", "agent_id": "", "label": "Agent C", "x": 200, "y": 300},
                ],
                edges=[
                    {"from": "n1", "to": "n3", "type": "sequential"},
                    {"from": "n2", "to": "n3", "type": "sequential"},
                ],
            ),
        ]

        for p in builtins:
            self.create(p)


_store: Optional[PatternStore] = None


def get_pattern_store() -> PatternStore:
    global _store
    if _store is None:
        _store = PatternStore()
    return _store
