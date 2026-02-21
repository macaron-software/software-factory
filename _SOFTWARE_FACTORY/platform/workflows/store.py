"""Workflow store and engine — chains patterns into multi-phase pipelines.

A Workflow is a sequence of phases. Each phase runs a pattern.
Phases can have gates (conditions to proceed) and shared context.
The RTE (Release Train Engineer) agent facilitates transitions via LLM.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Optional

from ..db.migrations import get_db
from ..patterns.store import get_pattern_store, PatternDef
from ..patterns.engine import run_pattern, _push_sse
from ..sessions.store import get_session_store, SessionDef, MessageDef

logger = logging.getLogger(__name__)


@dataclass
class WorkflowPhase:
    """A single phase in a workflow."""
    id: str = ""
    pattern_id: str = ""
    name: str = ""
    description: str = ""
    gate: str = ""  # condition to proceed: "all_approved", "no_veto", "always"
    config: dict = field(default_factory=dict)


@dataclass
class WorkflowDef:
    """A workflow definition — ordered list of phases."""
    id: str = ""
    name: str = ""
    description: str = ""
    phases: list[WorkflowPhase] = field(default_factory=list)
    config: dict = field(default_factory=dict)
    icon: str = "workflow"
    is_builtin: bool = False
    created_at: str = ""


@dataclass
class WorkflowRun:
    """Runtime state of a workflow execution."""
    workflow: WorkflowDef
    session_id: str
    project_id: str = ""
    current_phase: int = 0
    phase_results: list[dict] = field(default_factory=list)
    status: str = "running"  # running, completed, failed, gated
    error: str = ""


class WorkflowStore:
    """CRUD for workflow definitions."""

    def _ensure_table(self):
        conn = get_db()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS workflows (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                phases_json TEXT DEFAULT '[]',
                config_json TEXT DEFAULT '{}',
                icon TEXT DEFAULT 'workflow',
                is_builtin INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()
        conn.close()

    def list_all(self) -> list[WorkflowDef]:
        self._ensure_table()
        conn = get_db()
        rows = conn.execute("SELECT * FROM workflows ORDER BY created_at").fetchall()
        conn.close()
        return [self._row_to_wf(r) for r in rows]

    def get(self, wf_id: str) -> Optional[WorkflowDef]:
        self._ensure_table()
        conn = get_db()
        row = conn.execute("SELECT * FROM workflows WHERE id=?", (wf_id,)).fetchone()
        conn.close()
        return self._row_to_wf(row) if row else None

    def create(self, wf: WorkflowDef) -> WorkflowDef:
        self._ensure_table()
        if not wf.id:
            wf.id = uuid.uuid4().hex[:8]
        conn = get_db()
        conn.execute(
            "INSERT OR REPLACE INTO workflows (id, name, description, phases_json, config_json, icon, is_builtin) VALUES (?,?,?,?,?,?,?)",
            (wf.id, wf.name, wf.description,
             json.dumps([{"id": p.id, "pattern_id": p.pattern_id, "name": p.name,
                          "description": p.description, "gate": p.gate, "config": p.config}
                         for p in wf.phases]),
             json.dumps(wf.config), wf.icon, int(wf.is_builtin)),
        )
        conn.commit()
        conn.close()
        return wf

    def delete(self, wf_id: str):
        conn = get_db()
        conn.execute("DELETE FROM workflows WHERE id=?", (wf_id,))
        conn.commit()
        conn.close()

    def count(self) -> int:
        self._ensure_table()
        conn = get_db()
        c = conn.execute("SELECT COUNT(*) FROM workflows").fetchone()[0]
        conn.close()
        return c

    def seed_builtins(self):
        """Seed pre-built workflow templates (upserts missing ones)."""
        existing_ids = set()
        if self.count() > 0:
            conn = get_db()
            rows = conn.execute("SELECT id FROM workflows WHERE is_builtin=1").fetchall()
            existing_ids = {r["id"] for r in rows}
            conn.close()
        builtins = [
            WorkflowDef(
                id="sf-pipeline", name="Software Factory Pipeline",
                description="Full SF cycle: Brain analysis → TDD development → Adversarial review → Deploy.",
                icon="rocket", is_builtin=True,
                phases=[
                    WorkflowPhase(id="p1", pattern_id="hierarchical", name="Analysis",
                                  description="Brain decomposes the task into subtasks",
                                  gate="always",
                                  config={"agents": ["brain", "lead_dev", "architecte"]}),
                    WorkflowPhase(id="p2", pattern_id="adversarial-pair", name="TDD Development",
                                  description="Writer implements with TDD, reviewer validates",
                                  gate="always",
                                  config={"agents": ["lead_dev", "dev", "dev_backend", "testeur"]}),
                    WorkflowPhase(id="p3", pattern_id="adversarial-cascade", name="Quality Gate",
                                  description="4-layer adversarial review cascade",
                                  gate="no_veto",
                                  config={"agents": ["qa_lead", "securite", "arch-critic", "devops"]}),
                ],
            ),
            WorkflowDef(
                id="review-cycle", name="Code Review Cycle",
                description="Sequential review: code → security → architecture.",
                icon="eye", is_builtin=True,
                phases=[
                    WorkflowPhase(id="p1", pattern_id="sequential", name="Multi-Layer Review",
                                  description="Analyst → Developer → Reviewer pipeline",
                                  gate="always",
                                  config={"agents": ["lead_dev", "securite", "arch-critic"]}),
                    WorkflowPhase(id="p2", pattern_id="adversarial-pair", name="Fix Issues",
                                  description="Fix any issues found in review",
                                  gate="no_veto",
                                  config={"agents": ["dev", "qa_lead"]}),
                ],
            ),
            WorkflowDef(
                id="debate-decide", name="Debate & Decide",
                description="Agents debate, then a judge decides, then implement the decision.",
                icon="briefcase", is_builtin=True,
                phases=[
                    WorkflowPhase(id="p1", pattern_id="debate", name="Debate",
                                  description="Agents argue for/against different approaches",
                                  gate="always",
                                  config={"agents": ["architecte", "lead_dev", "dev_backend", "securite"]}),
                    WorkflowPhase(id="p2", pattern_id="hierarchical", name="Implementation",
                                  description="Execute the decided approach",
                                  gate="always",
                                  config={"agents": ["lead_dev", "dev", "testeur"]}),
                ],
            ),
            WorkflowDef(
                id="migration-sharelook",
                name="Migration Sharelook Angular 16→17",
                description="Migration ISO 100% Angular 16.2→17.3 — SAFe PI: Planning→Sprint→Review→Retro→Release.",
                icon="rocket", is_builtin=True,
                phases=[
                    # ── PI Planning: Vision, scope, risques ──
                    WorkflowPhase(id="pi-planning", pattern_id="sequential",
                                  name="PI Planning",
                                  description="CP présente vision migration. Lead+QA+Sécu définissent scope, risques, acceptance criteria.",
                                  gate="always",
                                  config={"agents": ["chef_projet", "lead_dev", "qa_lead", "securite"]}),
                    # ── Sprint Planning: Lead décompose en stories pour les devs ──
                    WorkflowPhase(id="sprint-planning", pattern_id="hierarchical",
                                  name="Sprint Planning",
                                  description="Lead décompose migration en user stories. Assigne aux devs selon expertise (pilot vs main app).",
                                  gate="always",
                                  config={"agents": ["lead_dev", "dev_frontend", "dev_fullstack"]}),
                    # ── Dev Sprint: Devs codent, Lead review complétude ──
                    WorkflowPhase(id="dev-sprint", pattern_id="hierarchical",
                                  name="Dev Sprint",
                                  description="Devs exécutent migration en //. Lead vérifie complétude. Inner loop jusqu'à COMPLETE.",
                                  gate="always",
                                  config={"agents": ["lead_dev", "dev_frontend", "dev_fullstack", "qa_lead"]}),
                    # ── Sprint Review: QA valide, Sécu audite, CP GO/NOGO ──
                    WorkflowPhase(id="sprint-review", pattern_id="sequential",
                                  name="Sprint Review",
                                  description="Lead présente travail. QA valide ISO 100% (golden files). Sécu audit CVE. CP décide GO/NOGO.",
                                  gate="no_veto",
                                  config={"agents": ["lead_dev", "qa_lead", "securite", "chef_projet"]}),
                    # ── Retrospective: Tous débattent améliorations ──
                    WorkflowPhase(id="retrospective", pattern_id="network",
                                  name="Retrospective",
                                  description="Équipe entière débat: ce qui a marché, ce qui a échoué, améliorations process.",
                                  gate="always",
                                  config={"agents": ["lead_dev", "dev_frontend", "dev_fullstack", "qa_lead", "chef_projet"]}),
                    # ── Release: DevOps deploy, QA smoke, CP valide ──
                    WorkflowPhase(id="release", pattern_id="sequential",
                                  name="Release",
                                  description="DevOps deploy staging→canary. QA smoke test. CP valide mise en prod.",
                                  gate="all_approved",
                                  config={"agents": ["devops", "qa_lead", "chef_projet"]}),
                ],
                config={
                    "graph": {
                        "pattern": "hierarchical",
                        "nodes": [
                            {"id": "n1", "agent_id": "chef_projet", "x": 400, "y": 30, "label": "Chef de Projet"},
                            {"id": "n2", "agent_id": "lead_dev", "x": 250, "y": 170, "label": "Lead Dev Angular"},
                            {"id": "n3", "agent_id": "securite", "x": 550, "y": 170, "label": "Security Audit"},
                            {"id": "n4", "agent_id": "qa_lead", "x": 400, "y": 170, "label": "QA Lead (ISO 100%)"},
                            {"id": "n5", "agent_id": "dev_frontend", "x": 150, "y": 340, "label": "Dev Frontend"},
                            {"id": "n6", "agent_id": "dev_fullstack", "x": 350, "y": 340, "label": "Dev Fullstack"},
                            {"id": "n7", "agent_id": "devops", "x": 550, "y": 340, "label": "DevOps"},
                        ],
                        "edges": [
                            # PI Planning: CP briefs everyone
                            {"from": "n1", "to": "n2", "label": "brief", "type": "sequential", "color": "#3b82f6"},
                            {"from": "n1", "to": "n4", "label": "criteria", "type": "sequential", "color": "#3b82f6"},
                            {"from": "n1", "to": "n3", "label": "audit", "type": "sequential", "color": "#3b82f6"},
                            # Sprint: Lead delegates to devs
                            {"from": "n2", "to": "n5", "label": "stories", "type": "parallel", "color": "#f59e0b"},
                            {"from": "n2", "to": "n6", "label": "stories", "type": "parallel", "color": "#f59e0b"},
                            # Review: Devs report to QA
                            {"from": "n5", "to": "n4", "label": "validate", "type": "sequential", "color": "#10b981"},
                            {"from": "n6", "to": "n4", "label": "validate", "type": "sequential", "color": "#10b981"},
                            # Feedback: QA reports to CP
                            {"from": "n4", "to": "n1", "label": "GO/NOGO", "type": "report", "color": "#ef4444"},
                            {"from": "n3", "to": "n1", "label": "report", "type": "report", "color": "#ef4444"},
                            # Release: CP triggers deploy
                            {"from": "n1", "to": "n7", "label": "deploy", "type": "sequential", "color": "#8b5cf6"},
                        ],
                    },
                    "project_ref": "sharelook",
                    "migration": {"framework": "angular", "from": "16.2.12", "to": "17.3.0"},
                    "agents_permissions": {
                        "qa_lead": {"can_veto": True, "veto_level": "ABSOLUTE"},
                        "securite": {"can_veto": True, "veto_level": "ABSOLUTE"},
                        "lead_dev": {"can_veto": True, "veto_level": "STRONG", "can_delegate": True},
                        "chef_projet": {"can_delegate": True},
                    },
                },
            ),
            # ── Feature Request: Demande métier → MVP ──
            WorkflowDef(
                id="feature-request",
                name="Demande Metier → MVP",
                description="Parcours complet: un metier exprime un besoin → challenge strategique → impact analysis → constitution projet → developpement → mise en prod.",
                icon="inbox", is_builtin=True,
                phases=[
                    WorkflowPhase(id="intake", pattern_id="network",
                                  name="Intake - Comite Strategique",
                                  description="Le metier presente son besoin. Le comite strategique (DSI, CPO, CTO, Business Owner) debat de la valeur, la faisabilite, l'alignement strategique. Chaque membre donne son avis argumente. Le DSI rend la decision GO/NOGO.",
                                  gate="all_approved",
                                  config={"agents": ["metier", "business_owner", "strat-cpo", "strat-cto", "dsi"]}),
                    WorkflowPhase(id="impact-analysis", pattern_id="parallel",
                                  name="Analyse d'Impact",
                                  description="Chaque expert analyse l'impact dans son domaine: architecture SI, securite/RGPD, conformite reglementaire, infrastructure cloud, integration inter-systemes, capacite portfolio. Le CPO agrege les analyses en impact map consolidee.",
                                  gate="always",
                                  config={"agents": ["enterprise_architect", "securite", "compliance_officer", "cloud_architect", "solution_architect", "strat-portfolio"]}),
                    WorkflowPhase(id="project-setup", pattern_id="sequential",
                                  name="Constitution du Projet",
                                  description="Le Dir. Programme alloue les ressources. Le Product Manager decompose en features et user stories. Le Chef de Projet planifie les sprints et les dependances. Le Scrum Master configure les ceremonies.",
                                  gate="always",
                                  config={"agents": ["strat-dirprog", "product_manager", "chef_projet", "scrum_master"]}),
                    WorkflowPhase(id="product-design", pattern_id="hierarchical",
                                  name="Product Design",
                                  description="Le Product Manager pilote: decompose la vision en features avec criteres d'acceptation. L'UX Designer cree les maquettes et parcours utilisateur. Le metier valide la conformite au besoin initial. Le Lead Dev evalue la faisabilite technique de chaque feature.",
                                  gate="always",
                                  config={"agents": ["product_manager", "ux_designer", "metier", "lead_dev"]}),
                    WorkflowPhase(id="dev-sprint", pattern_id="hierarchical",
                                  name="Sprint de Developpement",
                                  description="Le Lead Dev distribue les stories aux devs. Les devs codent en TDD. Le QA valide en continu. Le Lead fait la code review. Adversarial review avant chaque merge.",
                                  gate="always",
                                  config={"agents": ["lead_dev", "dev_frontend", "dev_backend", "qa_lead"]}),
                    WorkflowPhase(id="release", pattern_id="sequential",
                                  name="Mise en Production",
                                  description="Pipeline sequentiel: DevOps deploie staging. QA lance les tests E2E et smoke. Securite fait l'audit OWASP. Performance lance le load test. SRE valide le monitoring. Chef de Projet prononce le GO/NOGO. Business Owner valide la conformite metier.",
                                  gate="all_approved",
                                  config={"agents": ["devops", "qa_lead", "securite", "performance_engineer", "sre", "chef_projet", "business_owner"]}),
                ],
                config={
                    "graph": {
                        "pattern": "hierarchical",
                        "nodes": [
                            {"id": "n1", "agent_id": "dsi", "x": 400, "y": 10, "label": "DSI"},
                            {"id": "n2", "agent_id": "strat-cpo", "x": 250, "y": 10, "label": "Julie - CPO"},
                            {"id": "n3", "agent_id": "strat-cto", "x": 550, "y": 10, "label": "Karim - CTO"},
                            {"id": "n4", "agent_id": "metier", "x": 100, "y": 10, "label": "Metier / PO"},
                            {"id": "n5", "agent_id": "business_owner", "x": 700, "y": 10, "label": "Business Owner"},
                            {"id": "n6", "agent_id": "enterprise_architect", "x": 100, "y": 130, "label": "Enterprise Archi"},
                            {"id": "n7", "agent_id": "securite", "x": 280, "y": 130, "label": "Securite"},
                            {"id": "n8", "agent_id": "compliance_officer", "x": 450, "y": 130, "label": "Compliance"},
                            {"id": "n9", "agent_id": "cloud_architect", "x": 620, "y": 130, "label": "Cloud Archi"},
                            {"id": "n10", "agent_id": "strat-portfolio", "x": 750, "y": 130, "label": "Sofia - Portfolio"},
                            {"id": "n11", "agent_id": "strat-dirprog", "x": 100, "y": 250, "label": "Thomas - Dir Prog"},
                            {"id": "n12", "agent_id": "product_manager", "x": 300, "y": 250, "label": "Product Manager"},
                            {"id": "n13", "agent_id": "chef_projet", "x": 500, "y": 250, "label": "Chef de Projet"},
                            {"id": "n14", "agent_id": "scrum_master", "x": 680, "y": 250, "label": "Scrum Master"},
                            {"id": "n15", "agent_id": "ux_designer", "x": 150, "y": 370, "label": "UX Designer"},
                            {"id": "n16", "agent_id": "lead_dev", "x": 350, "y": 370, "label": "Lead Dev"},
                            {"id": "n17", "agent_id": "dev_frontend", "x": 200, "y": 480, "label": "Dev Frontend"},
                            {"id": "n18", "agent_id": "dev_backend", "x": 400, "y": 480, "label": "Dev Backend"},
                            {"id": "n19", "agent_id": "qa_lead", "x": 550, "y": 480, "label": "QA Lead"},
                            {"id": "n20", "agent_id": "devops", "x": 300, "y": 580, "label": "DevOps"},
                            {"id": "n21", "agent_id": "sre", "x": 500, "y": 580, "label": "SRE"},
                            {"id": "n22", "agent_id": "performance_engineer", "x": 680, "y": 480, "label": "Perf Engineer"},
                            {"id": "n23", "agent_id": "solution_architect", "x": 550, "y": 130, "label": "Solution Archi"},
                        ],
                        "edges": [
                            # Intake: metier → comite strategique (debate)
                            {"from": "n4", "to": "n2", "label": "besoin", "color": "#3b82f6"},
                            {"from": "n4", "to": "n3", "label": "besoin", "color": "#3b82f6"},
                            {"from": "n4", "to": "n1", "label": "besoin", "color": "#3b82f6"},
                            {"from": "n2", "to": "n1", "label": "avis CPO", "color": "#d946ef"},
                            {"from": "n3", "to": "n1", "label": "avis CTO", "color": "#d946ef"},
                            {"from": "n5", "to": "n1", "label": "avis BO", "color": "#d946ef"},
                            # Impact: DSI commande l'analyse
                            {"from": "n1", "to": "n6", "label": "analyser", "color": "#f59e0b"},
                            {"from": "n1", "to": "n7", "label": "analyser", "color": "#f59e0b"},
                            {"from": "n1", "to": "n8", "label": "analyser", "color": "#f59e0b"},
                            {"from": "n1", "to": "n9", "label": "analyser", "color": "#f59e0b"},
                            {"from": "n1", "to": "n23", "label": "analyser", "color": "#f59e0b"},
                            {"from": "n6", "to": "n2", "label": "impact SI", "color": "#10b981"},
                            {"from": "n7", "to": "n2", "label": "impact secu", "color": "#10b981"},
                            {"from": "n8", "to": "n2", "label": "impact regl.", "color": "#10b981"},
                            {"from": "n9", "to": "n2", "label": "impact cloud", "color": "#10b981"},
                            {"from": "n23", "to": "n2", "label": "impact integ.", "color": "#10b981"},
                            {"from": "n10", "to": "n2", "label": "capacite", "color": "#10b981"},
                            # Constitution: DirProg → PM → CP → SM
                            {"from": "n11", "to": "n12", "label": "staffing", "color": "#8b5cf6"},
                            {"from": "n12", "to": "n13", "label": "backlog", "color": "#8b5cf6"},
                            {"from": "n13", "to": "n14", "label": "planning", "color": "#8b5cf6"},
                            # Product Design: PM → UX + Lead
                            {"from": "n12", "to": "n15", "label": "maquettes", "color": "#d946ef"},
                            {"from": "n12", "to": "n16", "label": "features", "color": "#d946ef"},
                            {"from": "n15", "to": "n4", "label": "valider UX", "color": "#06b6d4"},
                            # Sprint: Lead → Devs → QA
                            {"from": "n16", "to": "n17", "label": "stories", "color": "#f59e0b"},
                            {"from": "n16", "to": "n18", "label": "stories", "color": "#f59e0b"},
                            {"from": "n17", "to": "n19", "label": "review", "color": "#10b981"},
                            {"from": "n18", "to": "n19", "label": "review", "color": "#10b981"},
                            # Release: QA + Secu → CP → DevOps → SRE
                            {"from": "n19", "to": "n13", "label": "GO/NOGO", "color": "#ef4444"},
                            {"from": "n13", "to": "n20", "label": "deploy", "color": "#8b5cf6"},
                            {"from": "n20", "to": "n21", "label": "monitoring", "color": "#8b5cf6"},
                            {"from": "n22", "to": "n13", "label": "perf OK", "color": "#10b981"},
                        ],
                    },
                    "agents_permissions": {
                        "dsi": {"can_veto": True, "veto_level": "ABSOLUTE", "can_delegate": True},
                        "strat-cpo": {"can_veto": True, "veto_level": "STRONG", "can_approve": True},
                        "strat-cto": {"can_veto": True, "veto_level": "STRONG"},
                        "qa_lead": {"can_veto": True, "veto_level": "ABSOLUTE"},
                        "securite": {"can_veto": True, "veto_level": "ABSOLUTE"},
                        "business_owner": {"can_veto": True, "veto_level": "STRONG", "can_approve": True},
                        "chef_projet": {"can_delegate": True, "can_approve": True},
                    },
                },
            ),
            # ── Tech Debt Reduction: Audit → Prioritize → Fix → Validate ──
            WorkflowDef(
                id="tech-debt-reduction",
                name="Reduction de la Dette Technique",
                description="Audit cross-projet de la dette technique → priorisation WSJF → sprint de correction → validation metriques.",
                icon="tool", is_builtin=True,
                phases=[
                    WorkflowPhase(id="debt-scan", pattern_id="parallel",
                                  name="Audit de Dette Technique",
                                  description="Scan parallele par domaine: le CTO lance l'audit. L'Enterprise Archi analyse le couplage et les dependances. Le Lead Dev scanne la complexite et la duplication. La Securite cherche les CVE et deps obsoletes. Le SRE analyse les incidents recurrents. Le Perf Engineer cherche les bottlenecks. Le CTO agrege les resultats en inventaire score.",
                                  gate="always",
                                  config={"agents": ["strat-cto", "enterprise_architect", "lead_dev", "securite", "sre", "performance_engineer"]}),
                    WorkflowPhase(id="prioritization", pattern_id="network",
                                  name="Priorisation (Debat WSJF)",
                                  description="Le comite debat de la priorisation: CTO defend l'urgence technique. CPO defend la roadmap produit. Portfolio calcule la capacite. Le Lean Portfolio Manager applique le scoring WSJF. Le Product Manager arbitre feature vs dette. Decision finale: budget temps alloue et items priorises.",
                                  gate="all_approved",
                                  config={"agents": ["strat-cto", "strat-cpo", "strat-portfolio", "lean_portfolio_manager", "product_manager"]}),
                    WorkflowPhase(id="planning", pattern_id="sequential",
                                  name="Planning Sprint Dette",
                                  description="Le Scrum Master decide: sprint dedie (100% dette) ou integre (20% par sprint). Le Lead Dev decompose les items de dette en tasks techniques. Le Chef de Projet planifie et assigne.",
                                  gate="always",
                                  config={"agents": ["scrum_master", "lead_dev", "chef_projet"]}),
                    WorkflowPhase(id="sprint-debt", pattern_id="hierarchical",
                                  name="Sprint de Correction",
                                  description="Le Lead Dev distribue les refactors. Les devs corrigent en TDD. Le QA Lead valide la non-regression (coverage ne doit pas baisser, pas de breaking change). Adversarial review renforcee: VETO si regression perf, VETO si API breaking sans deprecation.",
                                  gate="all_approved",
                                  config={"agents": ["lead_dev", "dev_frontend", "dev_backend", "qa_lead"]}),
                    WorkflowPhase(id="validation", pattern_id="sequential",
                                  name="Validation (Proof of Reduction)",
                                  description="QA presente le rapport de non-regression. Perf Engineer compare les benchmarks avant/apres. Lead Dev montre la reduction de complexite. Le CTO valide que la dette a reellement diminue. Metriques: complexity delta, coverage delta, build time delta, incident rate delta.",
                                  gate="all_approved",
                                  config={"agents": ["qa_lead", "performance_engineer", "lead_dev", "strat-cto"]}),
                ],
                config={
                    "graph": {
                        "pattern": "hierarchical",
                        "nodes": [
                            {"id": "n1", "agent_id": "strat-cto", "x": 400, "y": 10, "label": "Karim - CTO"},
                            {"id": "n2", "agent_id": "strat-cpo", "x": 200, "y": 10, "label": "Julie - CPO"},
                            {"id": "n3", "agent_id": "strat-portfolio", "x": 600, "y": 10, "label": "Sofia - Portfolio"},
                            {"id": "n4", "agent_id": "enterprise_architect", "x": 100, "y": 140, "label": "Enterprise Archi"},
                            {"id": "n5", "agent_id": "lead_dev", "x": 300, "y": 140, "label": "Lead Dev"},
                            {"id": "n6", "agent_id": "securite", "x": 500, "y": 140, "label": "Securite"},
                            {"id": "n7", "agent_id": "sre", "x": 650, "y": 140, "label": "SRE"},
                            {"id": "n8", "agent_id": "performance_engineer", "x": 150, "y": 250, "label": "Perf Engineer"},
                            {"id": "n9", "agent_id": "lean_portfolio_manager", "x": 700, "y": 10, "label": "Lean Portfolio"},
                            {"id": "n10", "agent_id": "product_manager", "x": 100, "y": 10, "label": "Product Manager"},
                            {"id": "n11", "agent_id": "scrum_master", "x": 200, "y": 250, "label": "Scrum Master"},
                            {"id": "n12", "agent_id": "chef_projet", "x": 400, "y": 250, "label": "Chef de Projet"},
                            {"id": "n13", "agent_id": "dev_frontend", "x": 200, "y": 380, "label": "Dev Frontend"},
                            {"id": "n14", "agent_id": "dev_backend", "x": 400, "y": 380, "label": "Dev Backend"},
                            {"id": "n15", "agent_id": "qa_lead", "x": 600, "y": 380, "label": "QA Lead"},
                        ],
                        "edges": [
                            # Scan: CTO commande l'audit en parallele
                            {"from": "n1", "to": "n4", "label": "audit archi", "color": "#f59e0b"},
                            {"from": "n1", "to": "n5", "label": "audit code", "color": "#f59e0b"},
                            {"from": "n1", "to": "n6", "label": "audit secu", "color": "#f59e0b"},
                            {"from": "n1", "to": "n7", "label": "audit ops", "color": "#f59e0b"},
                            {"from": "n1", "to": "n8", "label": "audit perf", "color": "#f59e0b"},
                            # Reports remontent au CTO
                            {"from": "n4", "to": "n1", "label": "rapport", "color": "#10b981"},
                            {"from": "n5", "to": "n1", "label": "rapport", "color": "#10b981"},
                            {"from": "n6", "to": "n1", "label": "rapport", "color": "#10b981"},
                            {"from": "n7", "to": "n1", "label": "rapport", "color": "#10b981"},
                            {"from": "n8", "to": "n1", "label": "rapport", "color": "#10b981"},
                            # Priorisation: debat entre strategiques
                            {"from": "n1", "to": "n2", "label": "dette vs feature", "color": "#d946ef"},
                            {"from": "n2", "to": "n10", "label": "arbitrage", "color": "#d946ef"},
                            {"from": "n3", "to": "n9", "label": "capacite", "color": "#d946ef"},
                            {"from": "n9", "to": "n1", "label": "WSJF", "color": "#d946ef"},
                            # Planning: SM → Lead → CP
                            {"from": "n11", "to": "n5", "label": "sprint scope", "color": "#8b5cf6"},
                            {"from": "n5", "to": "n12", "label": "tasks", "color": "#8b5cf6"},
                            # Sprint: Lead → Devs → QA
                            {"from": "n5", "to": "n13", "label": "refactors", "color": "#f59e0b"},
                            {"from": "n5", "to": "n14", "label": "refactors", "color": "#f59e0b"},
                            {"from": "n13", "to": "n15", "label": "review", "color": "#10b981"},
                            {"from": "n14", "to": "n15", "label": "review", "color": "#10b981"},
                            # Validation: QA + Perf → CTO
                            {"from": "n15", "to": "n1", "label": "non-regression", "color": "#ef4444"},
                            {"from": "n8", "to": "n1", "label": "benchmark", "color": "#ef4444"},
                        ],
                    },
                    "agents_permissions": {
                        "strat-cto": {"can_veto": True, "veto_level": "ABSOLUTE", "can_delegate": True},
                        "strat-cpo": {"can_veto": True, "veto_level": "STRONG"},
                        "qa_lead": {"can_veto": True, "veto_level": "ABSOLUTE"},
                        "securite": {"can_veto": True, "veto_level": "STRONG"},
                        "lead_dev": {"can_delegate": True},
                    },
                },
            ),
            # ── Comité Stratégique ──
            WorkflowDef(
                id="strategic-committee",
                name="Comite Strategique",
                description="Gouvernance portfolio: arbitrage investissements, alignement strategie-execution, GO/NOGO initiatives.",
                icon="target", is_builtin=True,
                phases=[
                    WorkflowPhase(id="p1-intake", pattern_id="network", name="Instruction du Dossier",
                                  description="CPO presente la demande, CTO evalue faisabilite, Portfolio analyse capacite et WSJF.",
                                  gate="always",
                                  config={"agents": ["strat-cpo", "strat-cto", "strat-portfolio", "lean_portfolio_manager"]}),
                    WorkflowPhase(id="p2-debate", pattern_id="network", name="Debat & Arbitrage",
                                  description="Debat ouvert: impact budget, dette technique, alignement roadmap. Dir Programme evalue charge.",
                                  gate="always",
                                  config={"agents": ["dsi", "strat-cpo", "strat-cto", "strat-portfolio", "strat-dirprog", "lean_portfolio_manager"]}),
                    WorkflowPhase(id="p3-decision", pattern_id="hierarchical", name="Decision GO / NOGO",
                                  description="DSI rend la decision finale. GO = lancement projet. NOGO = retour backlog. PIVOT = reformulation.",
                                  gate="all_approved",
                                  config={"agents": ["dsi", "strat-cpo", "strat-cto"]}),
                ],
                config={
                    "graph": {
                        "nodes": [
                            {"id": "n1", "agent_id": "dsi", "x": 400, "y": 20, "label": "DSI"},
                            {"id": "n2", "agent_id": "strat-cpo", "x": 200, "y": 140, "label": "Julie - CPO"},
                            {"id": "n3", "agent_id": "strat-cto", "x": 600, "y": 140, "label": "Karim - CTO"},
                            {"id": "n4", "agent_id": "strat-portfolio", "x": 120, "y": 280, "label": "Sofia - Portfolio"},
                            {"id": "n5", "agent_id": "strat-dirprog", "x": 680, "y": 280, "label": "Thomas - Dir Programme"},
                            {"id": "n6", "agent_id": "lean_portfolio_manager", "x": 400, "y": 330, "label": "Lean Portfolio Mgr"},
                        ],
                        "edges": [
                            # DSI ↔ CPO/CTO: arbitrage stratégique
                            {"from": "n1", "to": "n2", "label": "vision produit", "color": "#a855f7"},
                            {"from": "n1", "to": "n3", "label": "vision tech", "color": "#a855f7"},
                            {"from": "n2", "to": "n1", "label": "proposition", "color": "#8b5cf6"},
                            {"from": "n3", "to": "n1", "label": "faisabilite", "color": "#8b5cf6"},
                            # CPO ↔ CTO: produit vs technique
                            {"from": "n2", "to": "n3", "label": "feature vs dette", "color": "#f59e0b"},
                            {"from": "n3", "to": "n2", "label": "contraintes archi", "color": "#f59e0b"},
                            # Portfolio ↔ CPO: priorisation WSJF
                            {"from": "n4", "to": "n2", "label": "WSJF scoring", "color": "#10b981"},
                            {"from": "n2", "to": "n4", "label": "valeur business", "color": "#10b981"},
                            # Portfolio ↔ Lean: budget & capacity
                            {"from": "n4", "to": "n6", "label": "metriques flux", "color": "#06b6d4"},
                            {"from": "n6", "to": "n4", "label": "budget lean", "color": "#06b6d4"},
                            # CTO ↔ Dir Programme: charge & planning
                            {"from": "n3", "to": "n5", "label": "complexite", "color": "#ef4444"},
                            {"from": "n5", "to": "n3", "label": "capacite equipes", "color": "#ef4444"},
                            # Dir Programme ↔ Lean: staffing
                            {"from": "n5", "to": "n6", "label": "plan staffing", "color": "#d946ef"},
                            {"from": "n6", "to": "n5", "label": "guardrails", "color": "#d946ef"},
                            # DSI ↔ Lean: alignement strategique
                            {"from": "n1", "to": "n6", "label": "themes strat", "color": "#64748b"},
                            {"from": "n6", "to": "n1", "label": "portfolio health", "color": "#64748b"},
                        ],
                    },
                    "agents_permissions": {
                        "dsi": {"can_veto": True, "veto_level": "ABSOLUTE", "can_delegate": True, "can_approve": True},
                        "strat-cpo": {"can_veto": True, "veto_level": "STRONG", "can_delegate": True, "can_approve": True},
                        "strat-cto": {"can_veto": True, "veto_level": "STRONG", "can_delegate": True, "can_approve": True},
                        "strat-portfolio": {"can_veto": False, "can_approve": True},
                        "strat-dirprog": {"can_veto": False, "can_approve": True},
                        "lean_portfolio_manager": {"can_veto": True, "veto_level": "ADVISORY", "can_approve": True},
                    },
                },
            ),
        ]
        # ── Ideation → Production Pipeline ──
        builtins.append(
            WorkflowDef(
                id="ideation-to-prod",
                name="Ideation → Production",
                description="Pipeline complet agentic: Architecture → Codegen (devs ecrivent le code) → Build & Test → Deploy Azure. Les agents utilisent leurs tools (code_write, build, docker_build, deploy_azure).",
                icon="rocket", is_builtin=True,
                phases=[
                    WorkflowPhase(id="architecture", pattern_id="hierarchical",
                                  name="Architecture & Design",
                                  description="L'architecte conçoit l'architecture technique: choix de stack, structure du projet, API design, modèle de données. Le Lead Dev valide la faisabilité et propose les patterns. L'UX Designer définit les écrans principaux. Produisez un document d'architecture avec la liste des fichiers à créer.",
                                  gate="always",
                                  config={"agents": ["enterprise_architect", "lead_dev", "ux_designer"]}),
                    WorkflowPhase(id="codegen", pattern_id="hierarchical",
                                  name="Code Generation",
                                  description="Le Lead Dev distribue les tâches. Les devs ÉCRIVENT LE CODE avec l'outil code_write: fichiers source, templates HTML, CSS, API endpoints, Dockerfile. Chaque dev crée les fichiers dans le répertoire du projet. Le code doit être COMPLET et FONCTIONNEL, pas de placeholder. Incluez requirements.txt/package.json, un Dockerfile, et des données de démo.",
                                  gate="always",
                                  config={"agents": ["lead_dev", "dev_frontend", "dev_backend"]}),
                    WorkflowPhase(id="quality", pattern_id="sequential",
                                  name="Build & Quality Gate",
                                  description="Le QA valide le code: vérifie que tous les fichiers existent, que le code est cohérent. Le dev committe avec git_commit. Le QA lance le build avec l'outil build (docker build). Si le build échoue, le dev corrige.",
                                  gate="always",
                                  config={"agents": ["qa_lead", "dev_backend", "lead_dev"]}),
                    WorkflowPhase(id="deploy", pattern_id="sequential",
                                  name="Deploy Azure VM",
                                  description="Le DevOps construit l'image Docker avec docker_build, puis déploie sur la VM Azure avec deploy_azure. L'outil deploy_azure transfère l'image et lance le container. Le SRE vérifie le health check. Annoncez l'URL publique de l'application déployée.",
                                  gate="all_approved",
                                  config={"agents": ["devops", "sre"]}),
                ],
                config={
                    "graph": {
                        "pattern": "hierarchical",
                        "nodes": [
                            {"id": "n1", "agent_id": "enterprise_architect", "x": 400, "y": 20, "label": "Architecte"},
                            {"id": "n2", "agent_id": "lead_dev", "x": 250, "y": 130, "label": "Lead Dev"},
                            {"id": "n3", "agent_id": "ux_designer", "x": 550, "y": 130, "label": "UX Designer"},
                            {"id": "n4", "agent_id": "dev_frontend", "x": 150, "y": 260, "label": "Dev Frontend"},
                            {"id": "n5", "agent_id": "dev_backend", "x": 350, "y": 260, "label": "Dev Backend"},
                            {"id": "n6", "agent_id": "qa_lead", "x": 550, "y": 260, "label": "QA Lead"},
                            {"id": "n7", "agent_id": "devops", "x": 250, "y": 380, "label": "DevOps"},
                            {"id": "n8", "agent_id": "sre", "x": 450, "y": 380, "label": "SRE"},
                        ],
                        "edges": [
                            {"from": "n1", "to": "n2", "label": "archi", "color": "#a855f7"},
                            {"from": "n1", "to": "n3", "label": "UX specs", "color": "#a855f7"},
                            {"from": "n2", "to": "n4", "label": "stories", "color": "#f59e0b"},
                            {"from": "n2", "to": "n5", "label": "stories", "color": "#f59e0b"},
                            {"from": "n4", "to": "n6", "label": "code", "color": "#10b981"},
                            {"from": "n5", "to": "n6", "label": "code", "color": "#10b981"},
                            {"from": "n6", "to": "n7", "label": "GO build", "color": "#3b82f6"},
                            {"from": "n7", "to": "n8", "label": "deploy", "color": "#ef4444"},
                        ],
                    },
                    "agents_permissions": {
                        "enterprise_architect": {"can_veto": True, "veto_level": "STRONG"},
                        "lead_dev": {"can_delegate": True, "can_veto": True, "veto_level": "STRONG"},
                        "qa_lead": {"can_veto": True, "veto_level": "ABSOLUTE"},
                        "devops": {"can_approve": True},
                        "sre": {"can_veto": True, "veto_level": "STRONG", "can_approve": True},
                    },
                },
            ),
        )
        builtins.append(
            WorkflowDef(
                id="dsi-sharelook-2",
                name="DSI Sharelook 2.0 — Phases",
                description="Workflow phasé: Cadrage → Architecture → Sprint → Delivery",
                icon="briefcase", is_builtin=True,
                phases=[
                    WorkflowPhase(id="p1-cadrage", pattern_id="hierarchical",
                                  name="Cadrage Stratégique",
                                  description="Le DSI cadre la vision avec CPO et CTO. L'architecte analyse la faisabilité. Décision GO/NOGO.",
                                  gate="all_approved",
                                  config={"agents": ["dsi", "strat-cpo", "strat-cto", "architecte", "strat-portfolio"],
                                          "leader": "dsi",
                                          "deliverables": ["Vision validée", "Budget estimé", "Risques identifiés", "Décision GO/NOGO"]}),
                    WorkflowPhase(id="p2-architecture", pattern_id="network",
                                  name="Design & Architecture",
                                  description="L'architecte, le lead dev, la sécu et le DevOps conçoivent la solution. Débat technique sur les choix.",
                                  gate="no_veto",
                                  config={"agents": ["architecte", "lead_dev", "securite", "devops", "strat-cto"],
                                          "leader": "architecte",
                                          "deliverables": ["Architecture validée", "Stack technique", "Plan sécurité", "Infra cible"]}),
                    WorkflowPhase(id="p3-sprint-setup", pattern_id="sequential",
                                  name="Sprint Planning",
                                  description="Le PO structure le backlog, le Scrum Master planifie les sprints, l'équipe estime.",
                                  gate="all_approved",
                                  config={"agents": ["product", "scrum_master", "lead_dev", "dev_frontend", "dev_backend", "qa_lead"],
                                          "leader": "product",
                                          "deliverables": ["Backlog priorisé", "Sprint 1 planifié", "Équipe assignée", "Definition of Done"]}),
                    WorkflowPhase(id="p4-delivery", pattern_id="hierarchical",
                                  name="Delivery & QA",
                                  description="L'équipe développe, les QA testent, le DevOps déploie. Review adversariale avant merge.",
                                  gate="no_veto",
                                  config={"agents": ["lead_dev", "dev_frontend", "dev_backend", "testeur", "qa_lead", "devops", "securite"],
                                          "leader": "lead_dev",
                                          "deliverables": ["Code livré", "Tests passés", "Déployé staging", "Review sécu OK"]}),
                ],
                config={
                    "project_id": "sharelook-2",
                    "graph": {
                        "pattern": "hierarchical",
                        "nodes": [
                            {"id": "n1", "agent_id": "dsi", "x": 400, "y": 30, "label": "DSI", "phase": "p1-cadrage"},
                            {"id": "n2", "agent_id": "strat-cpo", "x": 200, "y": 120, "label": "Julie - CPO", "phase": "p1-cadrage"},
                            {"id": "n3", "agent_id": "strat-cto", "x": 600, "y": 120, "label": "Karim - CTO", "phase": "p1-cadrage"},
                            {"id": "n4", "agent_id": "architecte", "x": 100, "y": 210, "label": "Pierre - Archi", "phase": "p1-cadrage,p2-architecture"},
                            {"id": "n5", "agent_id": "strat-portfolio", "x": 700, "y": 120, "label": "Sofia - Portfolio", "phase": "p1-cadrage"},
                            {"id": "n6", "agent_id": "lead_dev", "x": 300, "y": 300, "label": "Thomas - Lead Dev", "phase": "p2-architecture,p4-delivery"},
                            {"id": "n7", "agent_id": "securite", "x": 500, "y": 300, "label": "Nadia - Sécu", "phase": "p2-architecture,p4-delivery"},
                            {"id": "n8", "agent_id": "devops", "x": 700, "y": 300, "label": "Karim D. - DevOps", "phase": "p2-architecture,p4-delivery"},
                            {"id": "n9", "agent_id": "product", "x": 150, "y": 390, "label": "Laura - PO", "phase": "p3-sprint-setup"},
                            {"id": "n10", "agent_id": "scrum_master", "x": 350, "y": 390, "label": "Inès - SM", "phase": "p3-sprint-setup"},
                            {"id": "n11", "agent_id": "dev_frontend", "x": 200, "y": 480, "label": "Lucas - Front", "phase": "p4-delivery"},
                            {"id": "n12", "agent_id": "dev_backend", "x": 400, "y": 480, "label": "Julien - Back", "phase": "p4-delivery"},
                            {"id": "n13", "agent_id": "qa_lead", "x": 550, "y": 390, "label": "Claire - QA Lead", "phase": "p3-sprint-setup,p4-delivery"},
                            {"id": "n14", "agent_id": "testeur", "x": 600, "y": 480, "label": "Rachid - Testeur", "phase": "p4-delivery"},
                        ],
                        "edges": [
                            {"from": "n1", "to": "n2", "label": "vision produit", "color": "#a855f7"},
                            {"from": "n1", "to": "n3", "label": "vision tech", "color": "#a855f7"},
                            {"from": "n2", "to": "n1", "label": "proposition", "color": "#8b5cf6"},
                            {"from": "n3", "to": "n1", "label": "faisabilité", "color": "#8b5cf6"},
                            {"from": "n1", "to": "n4", "label": "analyse archi", "color": "#a855f7"},
                            {"from": "n4", "to": "n1", "label": "recommandation", "color": "#8b5cf6"},
                            {"from": "n5", "to": "n1", "label": "budget/portfolio", "color": "#f59e0b"},
                            {"from": "n1", "to": "n6", "label": "GO projet", "color": "#34d399"},
                            {"from": "n3", "to": "n4", "label": "contraintes tech", "color": "#f59e0b"},
                            {"from": "n4", "to": "n6", "label": "design archi", "color": "#3b82f6"},
                            {"from": "n4", "to": "n7", "label": "review sécu", "color": "#3b82f6"},
                            {"from": "n4", "to": "n8", "label": "infra cible", "color": "#3b82f6"},
                            {"from": "n6", "to": "n4", "label": "feedback dev", "color": "#8b5cf6"},
                            {"from": "n7", "to": "n4", "label": "exigences sécu", "color": "#ef4444"},
                            {"from": "n8", "to": "n4", "label": "contraintes infra", "color": "#f59e0b"},
                            {"from": "n6", "to": "n9", "label": "specs tech", "color": "#34d399"},
                            {"from": "n4", "to": "n9", "label": "architecture doc", "color": "#34d399"},
                            {"from": "n9", "to": "n10", "label": "backlog", "color": "#a855f7"},
                            {"from": "n10", "to": "n6", "label": "sprint plan", "color": "#3b82f6"},
                            {"from": "n9", "to": "n13", "label": "critères QA", "color": "#3b82f6"},
                            {"from": "n10", "to": "n11", "label": "sprint tasks", "color": "#34d399"},
                            {"from": "n10", "to": "n12", "label": "sprint tasks", "color": "#34d399"},
                            {"from": "n6", "to": "n11", "label": "code review", "color": "#3b82f6"},
                            {"from": "n6", "to": "n12", "label": "code review", "color": "#3b82f6"},
                            {"from": "n11", "to": "n13", "label": "PR ready", "color": "#34d399"},
                            {"from": "n12", "to": "n13", "label": "PR ready", "color": "#34d399"},
                            {"from": "n13", "to": "n14", "label": "test plan", "color": "#3b82f6"},
                            {"from": "n14", "to": "n13", "label": "test results", "color": "#34d399"},
                            {"from": "n13", "to": "n8", "label": "deploy OK", "color": "#34d399"},
                            {"from": "n8", "to": "n1", "label": "prod status", "color": "#34d399"},
                        ],
                    },
                },
            ),
        )
        # ── TMA Maintenance: Triage → Diagnostic → Fix → Validate ──
        builtins.append(
            WorkflowDef(
                id="tma-maintenance",
                name="TMA — Maintenance Applicative",
                description="Triage incidents → diagnostic root cause → correctif TDD → tests de non-régression → hotfix deploy.",
                icon="tool", is_builtin=True,
                phases=[
                    WorkflowPhase(id="triage", pattern_id="hierarchical",
                                  name="Triage & Priorisation",
                                  description="Le Responsable TMA trie les incidents entrants par sévérité (P0-P4). Le QA Lead fournit les logs et steps de reproduction. Le Chef de Projet valide les SLA.",
                                  gate="always",
                                  config={"agents": ["responsable_tma", "qa_lead", "chef_projet"]}),
                    WorkflowPhase(id="diagnostic", pattern_id="parallel",
                                  name="Diagnostic Root Cause",
                                  description="Le Dev TMA analyse le code et reproduit le bug. Le Lead Dev évalue l'impact sur les modules adjacents. Le DBA vérifie les données et les requêtes.",
                                  gate="always",
                                  config={"agents": ["dev_tma", "lead_dev", "dba"]}),
                    WorkflowPhase(id="fix", pattern_id="hierarchical",
                                  name="Correctif TDD",
                                  description="Le Dev TMA écrit le test de non-régression (RED), puis le correctif (GREEN), puis refactorise. Le Lead Dev review le code. Le Test Automation ajoute le test E2E si nécessaire.",
                                  gate="no_veto",
                                  config={"agents": ["dev_tma", "lead_dev", "test_automation"]}),
                    WorkflowPhase(id="validate", pattern_id="sequential",
                                  name="Validation & Deploy",
                                  description="Le Test Manager lance la campagne de non-régression. Le QA valide les tests. Le Pipeline Engineer vérifie le pipeline CI. Le DevOps déploie le hotfix. Le Responsable TMA confirme la résolution.",
                                  gate="all_approved",
                                  config={"agents": ["test_manager", "qa_lead", "pipeline_engineer", "devops", "responsable_tma"]}),
                ],
                config={
                    "graph": {
                        "pattern": "hierarchical",
                        "nodes": [
                            {"id": "n1", "agent_id": "responsable_tma", "x": 400, "y": 20, "label": "Resp. TMA"},
                            {"id": "n2", "agent_id": "qa_lead", "x": 250, "y": 120, "label": "QA Lead"},
                            {"id": "n3", "agent_id": "chef_projet", "x": 550, "y": 120, "label": "Chef de Projet"},
                            {"id": "n4", "agent_id": "dev_tma", "x": 200, "y": 240, "label": "Dev TMA"},
                            {"id": "n5", "agent_id": "lead_dev", "x": 400, "y": 240, "label": "Lead Dev"},
                            {"id": "n6", "agent_id": "dba", "x": 600, "y": 240, "label": "DBA"},
                            {"id": "n7", "agent_id": "test_automation", "x": 150, "y": 360, "label": "Test Automation"},
                            {"id": "n8", "agent_id": "test_manager", "x": 350, "y": 360, "label": "Test Manager"},
                            {"id": "n9", "agent_id": "pipeline_engineer", "x": 550, "y": 360, "label": "Pipeline Eng."},
                            {"id": "n10", "agent_id": "devops", "x": 400, "y": 460, "label": "DevOps"},
                        ],
                        "edges": [
                            {"from": "n1", "to": "n2", "label": "triage", "color": "#ef4444"},
                            {"from": "n1", "to": "n3", "label": "SLA", "color": "#ef4444"},
                            {"from": "n1", "to": "n4", "label": "assigner", "color": "#f59e0b"},
                            {"from": "n4", "to": "n5", "label": "impact?", "color": "#3b82f6"},
                            {"from": "n4", "to": "n6", "label": "query?", "color": "#3b82f6"},
                            {"from": "n5", "to": "n4", "label": "review", "color": "#10b981"},
                            {"from": "n4", "to": "n7", "label": "test E2E", "color": "#8b5cf6"},
                            {"from": "n7", "to": "n8", "label": "résultats", "color": "#10b981"},
                            {"from": "n8", "to": "n9", "label": "GO CI", "color": "#10b981"},
                            {"from": "n9", "to": "n10", "label": "deploy", "color": "#8b5cf6"},
                            {"from": "n10", "to": "n1", "label": "confirmé", "color": "#10b981"},
                        ],
                    },
                    "agents_permissions": {
                        "responsable_tma": {"can_veto": True, "veto_level": "STRONG", "can_delegate": True},
                        "qa_lead": {"can_veto": True, "veto_level": "ABSOLUTE"},
                        "test_manager": {"can_veto": True, "veto_level": "STRONG", "can_approve": True},
                        "lead_dev": {"can_veto": True, "veto_level": "STRONG"},
                    },
                },
            ),
        )
        # ── Test Campaign: Plan → Automate → Execute → Report ──
        builtins.append(
            WorkflowDef(
                id="test-campaign",
                name="Campagne de Tests E2E",
                description="Plan de test → écriture des tests automatisés → exécution → rapport qualité → GO/NOGO release.",
                icon="clipboard", is_builtin=True,
                phases=[
                    WorkflowPhase(id="plan", pattern_id="hierarchical",
                                  name="Plan de Test",
                                  description="Le Test Manager définit la matrice de couverture. Le QA Lead identifie les parcours critiques. Le métier fournit les scénarios fonctionnels.",
                                  gate="always",
                                  config={"agents": ["test_manager", "qa_lead", "metier"]}),
                    WorkflowPhase(id="automate", pattern_id="hierarchical",
                                  name="Automatisation",
                                  description="Le Test Automation écrit les tests Playwright E2E. Le testeur écrit les tests d'API. Le Lead Dev fournit les fixtures et helpers.",
                                  gate="always",
                                  config={"agents": ["test_automation", "testeur", "lead_dev"]}),
                    WorkflowPhase(id="execute", pattern_id="parallel",
                                  name="Exécution",
                                  description="Exécution en parallèle: tests E2E IHM (Playwright), tests API (fetch), tests smoke, tests de performance. Collecte des résultats.",
                                  gate="always",
                                  config={"agents": ["test_automation", "testeur", "performance_engineer"]}),
                    WorkflowPhase(id="report", pattern_id="sequential",
                                  name="Rapport & GO/NOGO",
                                  description="Le Test Manager consolide les résultats. Le QA Lead valide la couverture. Le Chef de Projet décide GO/NOGO release.",
                                  gate="all_approved",
                                  config={"agents": ["test_manager", "qa_lead", "chef_projet"]}),
                ],
                config={
                    "graph": {
                        "pattern": "hierarchical",
                        "nodes": [
                            {"id": "n1", "agent_id": "test_manager", "x": 400, "y": 20, "label": "Test Manager"},
                            {"id": "n2", "agent_id": "qa_lead", "x": 250, "y": 130, "label": "QA Lead"},
                            {"id": "n3", "agent_id": "metier", "x": 550, "y": 130, "label": "Métier"},
                            {"id": "n4", "agent_id": "test_automation", "x": 200, "y": 260, "label": "Test Automation"},
                            {"id": "n5", "agent_id": "testeur", "x": 400, "y": 260, "label": "Testeur"},
                            {"id": "n6", "agent_id": "lead_dev", "x": 600, "y": 260, "label": "Lead Dev"},
                            {"id": "n7", "agent_id": "performance_engineer", "x": 300, "y": 370, "label": "Perf Engineer"},
                            {"id": "n8", "agent_id": "chef_projet", "x": 500, "y": 370, "label": "Chef de Projet"},
                        ],
                        "edges": [
                            {"from": "n1", "to": "n2", "label": "matrice", "color": "#a855f7"},
                            {"from": "n1", "to": "n3", "label": "scénarios", "color": "#a855f7"},
                            {"from": "n2", "to": "n4", "label": "E2E specs", "color": "#3b82f6"},
                            {"from": "n2", "to": "n5", "label": "API specs", "color": "#3b82f6"},
                            {"from": "n6", "to": "n4", "label": "fixtures", "color": "#f59e0b"},
                            {"from": "n4", "to": "n1", "label": "résultats E2E", "color": "#10b981"},
                            {"from": "n5", "to": "n1", "label": "résultats API", "color": "#10b981"},
                            {"from": "n7", "to": "n1", "label": "résultats perf", "color": "#10b981"},
                            {"from": "n1", "to": "n8", "label": "GO/NOGO", "color": "#ef4444"},
                        ],
                    },
                    "agents_permissions": {
                        "test_manager": {"can_veto": True, "veto_level": "ABSOLUTE", "can_delegate": True, "can_approve": True},
                        "qa_lead": {"can_veto": True, "veto_level": "STRONG", "can_approve": True},
                        "chef_projet": {"can_approve": True},
                    },
                },
            ),
        )
        # ── CICD Pipeline: Setup → Build → Quality → Deploy ──
        builtins.append(
            WorkflowDef(
                id="cicd-pipeline",
                name="Pipeline CI/CD",
                description="Configuration pipeline → build & tests → quality gates → déploiement canary → monitoring.",
                icon="zap", is_builtin=True,
                phases=[
                    WorkflowPhase(id="setup", pattern_id="hierarchical",
                                  name="Setup Pipeline",
                                  description="Le Pipeline Engineer conçoit le workflow GitHub Actions/GitLab CI. Le DevOps définit les environments (staging, canary, prod). Le DevSecOps configure les scans de sécurité.",
                                  gate="always",
                                  config={"agents": ["pipeline_engineer", "devops", "devsecops"]}),
                    WorkflowPhase(id="build-test", pattern_id="sequential",
                                  name="Build & Tests",
                                  description="Le Pipeline Engineer configure les jobs: lint → build → unit tests → integration tests. Le Test Automation intègre les tests E2E. Le Lead Dev valide les configurations.",
                                  gate="always",
                                  config={"agents": ["pipeline_engineer", "test_automation", "lead_dev"]}),
                    WorkflowPhase(id="quality-gates", pattern_id="parallel",
                                  name="Quality Gates",
                                  description="En parallèle: le QA valide la couverture (≥80%), la Sécurité lance le SAST/DAST, le Perf Engineer configure les benchmarks. Tous les gates doivent passer.",
                                  gate="all_approved",
                                  config={"agents": ["qa_lead", "securite", "performance_engineer", "pipeline_engineer"]}),
                    WorkflowPhase(id="deploy", pattern_id="sequential",
                                  name="Deploy Canary → Prod",
                                  description="Le DevOps déploie en canary (1%→10%→50%→100%). Le SRE monitore les métriques. Rollback automatique si error_rate > baseline+5%. Le Chef de Projet valide le GO prod.",
                                  gate="all_approved",
                                  config={"agents": ["devops", "sre", "pipeline_engineer", "chef_projet"]}),
                ],
                config={
                    "graph": {
                        "pattern": "sequential",
                        "nodes": [
                            {"id": "n1", "agent_id": "pipeline_engineer", "x": 400, "y": 20, "label": "Pipeline Engineer"},
                            {"id": "n2", "agent_id": "devops", "x": 250, "y": 130, "label": "DevOps"},
                            {"id": "n3", "agent_id": "devsecops", "x": 550, "y": 130, "label": "DevSecOps"},
                            {"id": "n4", "agent_id": "test_automation", "x": 200, "y": 260, "label": "Test Automation"},
                            {"id": "n5", "agent_id": "lead_dev", "x": 400, "y": 260, "label": "Lead Dev"},
                            {"id": "n6", "agent_id": "qa_lead", "x": 150, "y": 370, "label": "QA Lead"},
                            {"id": "n7", "agent_id": "securite", "x": 350, "y": 370, "label": "Sécurité"},
                            {"id": "n8", "agent_id": "performance_engineer", "x": 550, "y": 370, "label": "Perf Engineer"},
                            {"id": "n9", "agent_id": "sre", "x": 300, "y": 480, "label": "SRE"},
                            {"id": "n10", "agent_id": "chef_projet", "x": 500, "y": 480, "label": "Chef de Projet"},
                        ],
                        "edges": [
                            {"from": "n1", "to": "n2", "label": "environments", "color": "#a855f7"},
                            {"from": "n1", "to": "n3", "label": "scans sécu", "color": "#a855f7"},
                            {"from": "n1", "to": "n4", "label": "tests E2E", "color": "#3b82f6"},
                            {"from": "n1", "to": "n5", "label": "config", "color": "#3b82f6"},
                            {"from": "n4", "to": "n6", "label": "couverture", "color": "#10b981"},
                            {"from": "n3", "to": "n7", "label": "SAST/DAST", "color": "#ef4444"},
                            {"from": "n5", "to": "n8", "label": "benchmarks", "color": "#f59e0b"},
                            {"from": "n6", "to": "n1", "label": "GO QA", "color": "#10b981"},
                            {"from": "n7", "to": "n1", "label": "GO sécu", "color": "#10b981"},
                            {"from": "n8", "to": "n1", "label": "GO perf", "color": "#10b981"},
                            {"from": "n2", "to": "n9", "label": "canary", "color": "#8b5cf6"},
                            {"from": "n9", "to": "n10", "label": "GO prod", "color": "#ef4444"},
                        ],
                    },
                    "agents_permissions": {
                        "pipeline_engineer": {"can_veto": True, "veto_level": "STRONG", "can_delegate": True},
                        "devops": {"can_veto": True, "veto_level": "STRONG", "can_approve": True},
                        "qa_lead": {"can_veto": True, "veto_level": "ABSOLUTE"},
                        "securite": {"can_veto": True, "veto_level": "ABSOLUTE"},
                        "sre": {"can_veto": True, "veto_level": "STRONG", "can_approve": True},
                    },
                },
            ),
        )
        # ── Cycle de Vie Produit Complet: Idéation → Comité Strat → Réal → CICD → QA → TMA ──
        builtins.append(
            WorkflowDef(
                id="product-lifecycle",
                name="Cycle de Vie Produit Complet",
                description="Pipeline bout en bout: idéation → comité stratégique GO/NOGO → architecture → sprints dev → CI/CD pipeline → campagne QA → deploy prod → TMA maintenance.",
                icon="rocket", is_builtin=True,
                phases=[
                    # ── Phase 1: Idéation (NETWORK — PO briefe, experts débattent, PO synthétise) ──
                    WorkflowPhase(id="ideation", pattern_id="network",
                                  name="Idéation",
                                  description="Le Product Manager cadre le sujet et briefe l'équipe. Le métier exprime le besoin. L'UX Designer explore les parcours utilisateur. L'Architecte évalue la faisabilité technique. Débat structuré puis synthèse par le PO.",
                                  gate="always",
                                  config={"agents": ["metier", "ux_designer", "architecte", "product_manager"],
                                          "leader": "product_manager"}),
                    # ── Phase 2: Comité Stratégique (HUMAN-IN-THE-LOOP — DSI arbitre avec GO/NOGO humain) ──
                    WorkflowPhase(id="strategic-committee", pattern_id="human-in-the-loop",
                                  name="Comité Stratégique GO/NOGO",
                                  description="Le DSI préside. La CPO défend la valeur produit. Le CTO évalue la faisabilité et les risques techniques. Le Portfolio Manager analyse la capacité et le WSJF. Débat contradictoire. CHECKPOINT: le DSI attend la décision humaine GO, NOGO ou PIVOT.",
                                  gate="all_approved",
                                  config={"agents": ["strat-cpo", "strat-cto", "strat-portfolio", "lean_portfolio_manager", "dsi"],
                                          "leader": "dsi"}),
                    # ── Phase 3: Constitution Projet (SEQUENTIAL — Dir Programme lance la chaîne) ──
                    WorkflowPhase(id="project-setup", pattern_id="sequential",
                                  name="Constitution du Projet",
                                  description="Le Dir. Programme alloue les ressources → le Product Manager décompose en épics → le Chef de Projet planifie les sprints → le Scrum Master configure les cérémonies. Chaque sortie alimente l'entrée du suivant.",
                                  gate="always",
                                  config={"agents": ["strat-dirprog", "product_manager", "chef_projet", "scrum_master"],
                                          "leader": "strat-dirprog"}),
                    # ── Phase 4: Architecture (AGGREGATOR — analyses parallèles → architecte consolide) ──
                    WorkflowPhase(id="architecture", pattern_id="aggregator",
                                  name="Architecture & Design",
                                  description="En parallèle: le Lead Dev analyse la faisabilité, l'UX crée les maquettes, la Sécurité définit les exigences, le DevOps planifie l'infra. L'Architecte agrège toutes les analyses en un document d'architecture consolidé.",
                                  gate="no_veto",
                                  config={"agents": ["lead_dev", "ux_designer", "securite", "devops", "architecte"],
                                          "leader": "architecte"}),
                    # ── Phase 5: Sprints Dev (HIERARCHICAL — Lead distribue, devs codent, QA inner loop) ──
                    WorkflowPhase(id="dev-sprint", pattern_id="hierarchical",
                                  name="Sprints de Développement",
                                  description="Le Lead Dev distribue les stories. Les devs frontend et backend codent en TDD. Le Test Automation écrit les tests E2E en parallèle. Le Lead fait la code review. Boucle interne: si incomplet, le Lead re-distribue.",
                                  gate="always",
                                  config={"agents": ["lead_dev", "dev_frontend", "dev_backend", "test_automation"],
                                          "leader": "lead_dev",
                                          "max_iterations": 3}),
                    # ── Phase 6: CICD (SEQUENTIAL — Pipeline Engineer lance la chaîne) ──
                    WorkflowPhase(id="cicd", pattern_id="sequential",
                                  name="Pipeline CI/CD",
                                  description="Le Pipeline Engineer configure le pipeline: lint → build → unit tests → integration → E2E. Le DevSecOps intègre les scans SAST/DAST. Le DevOps configure les environments staging et prod.",
                                  gate="always",
                                  config={"agents": ["pipeline_engineer", "devsecops", "devops"],
                                          "leader": "pipeline_engineer"}),
                    # ── Phase 7: QA (LOOP — Test Manager planifie, exécution, si KO → reboucle) ──
                    WorkflowPhase(id="qa-campaign", pattern_id="loop",
                                  name="Campagne de Tests QA",
                                  description="Le Test Manager planifie et lance la campagne. Le QA Lead exécute les suites (E2E, API, perf). Si VETO (bugs trouvés): boucle retour au Test Manager qui re-planifie les corrections. Itère jusqu'à APPROVE ou max 5 itérations.",
                                  gate="all_approved",
                                  config={"agents": ["test_manager", "qa_lead"], "max_iterations": 5}),
                    # ── Phase 8: QA Détaillée (PARALLEL — QA Lead dispatche) ──
                    WorkflowPhase(id="qa-execution", pattern_id="parallel",
                                  name="Exécution Tests Parallèle",
                                  description="Le QA Lead dispatche. En parallèle: le Test Automation lance Playwright, le Testeur fait les tests API, le Perf Engineer lance k6. Le QA Lead agrège les résultats.",
                                  gate="all_approved",
                                  config={"agents": ["qa_lead", "test_automation", "testeur", "performance_engineer"],
                                          "leader": "qa_lead"}),
                    # ── Phase 9: Deploy (HUMAN-IN-THE-LOOP — Chef Projet valide) ──
                    WorkflowPhase(id="deploy-prod", pattern_id="human-in-the-loop",
                                  name="Deploy Production",
                                  description="Le DevOps déploie en canary (1%). Le SRE monitore les métriques. Le Pipeline Engineer prépare le rollback. CHECKPOINT: le Chef de Projet valide le GO pour 100% après vérification humaine des métriques.",
                                  gate="all_approved",
                                  config={"agents": ["devops", "sre", "pipeline_engineer", "chef_projet"],
                                          "leader": "chef_projet"}),
                    # ── Phase 10: Incident Router (ROUTER — Resp TMA triage) ──
                    WorkflowPhase(id="tma-router", pattern_id="router",
                                  name="Routage Incidents TMA",
                                  description="Le Responsable TMA reçoit les incidents. Il analyse la nature (bug code, perf, infra, sécu) et route vers le spécialiste approprié: Dev TMA pour les bugs, SRE pour l'infra, Test Automation pour les régressions.",
                                  gate="always",
                                  config={"agents": ["responsable_tma", "dev_tma", "sre", "test_automation"],
                                          "leader": "responsable_tma"}),
                    # ── Phase 11: Fix & Validate (LOOP — Dev TMA corrige, QA valide, reboucle si KO) ──
                    WorkflowPhase(id="tma-fix", pattern_id="loop",
                                  name="Correctif & Validation TMA",
                                  description="Le Dev TMA écrit le correctif avec test de non-régression. Le QA Lead valide. Si VETO: boucle retour au Dev TMA avec le feedback. Itère jusqu'à APPROVE.",
                                  gate="no_veto",
                                  config={"agents": ["dev_tma", "qa_lead"], "max_iterations": 3}),
                ],
                config={
                    "graph": {
                        "pattern": "hierarchical",
                        "nodes": [
                            # Row 1: Idéation
                            {"id": "n1", "agent_id": "metier", "x": 100, "y": 20, "label": "Métier / PO"},
                            {"id": "n2", "agent_id": "ux_designer", "x": 280, "y": 20, "label": "UX Designer"},
                            {"id": "n3", "agent_id": "product_manager", "x": 460, "y": 20, "label": "Product Manager"},
                            {"id": "n4", "agent_id": "architecte", "x": 640, "y": 20, "label": "Architecte"},
                            # Row 2: Comité stratégique
                            {"id": "n5", "agent_id": "dsi", "x": 370, "y": 120, "label": "DSI"},
                            {"id": "n6", "agent_id": "strat-cpo", "x": 200, "y": 120, "label": "CPO"},
                            {"id": "n7", "agent_id": "strat-cto", "x": 540, "y": 120, "label": "CTO"},
                            {"id": "n8", "agent_id": "strat-portfolio", "x": 700, "y": 120, "label": "Portfolio"},
                            # Row 3: Constitution projet
                            {"id": "n9", "agent_id": "strat-dirprog", "x": 100, "y": 220, "label": "Dir Programme"},
                            {"id": "n10", "agent_id": "chef_projet", "x": 300, "y": 220, "label": "Chef de Projet"},
                            {"id": "n11", "agent_id": "scrum_master", "x": 500, "y": 220, "label": "Scrum Master"},
                            # Row 4: Architecture + Dev
                            {"id": "n12", "agent_id": "lead_dev", "x": 200, "y": 320, "label": "Lead Dev"},
                            {"id": "n13", "agent_id": "securite", "x": 400, "y": 320, "label": "Sécurité"},
                            {"id": "n14", "agent_id": "devops", "x": 600, "y": 320, "label": "DevOps"},
                            # Row 5: Devs + Test Automation
                            {"id": "n15", "agent_id": "dev_frontend", "x": 100, "y": 420, "label": "Dev Frontend"},
                            {"id": "n16", "agent_id": "dev_backend", "x": 300, "y": 420, "label": "Dev Backend"},
                            {"id": "n17", "agent_id": "test_automation", "x": 500, "y": 420, "label": "Test Automation"},
                            # Row 6: CICD
                            {"id": "n18", "agent_id": "pipeline_engineer", "x": 400, "y": 520, "label": "Pipeline Eng."},
                            {"id": "n19", "agent_id": "devsecops", "x": 600, "y": 520, "label": "DevSecOps"},
                            # Row 7: QA Campaign
                            {"id": "n20", "agent_id": "test_manager", "x": 200, "y": 620, "label": "Test Manager"},
                            {"id": "n21", "agent_id": "qa_lead", "x": 400, "y": 620, "label": "QA Lead"},
                            {"id": "n22", "agent_id": "testeur", "x": 550, "y": 620, "label": "Testeur"},
                            {"id": "n23", "agent_id": "performance_engineer", "x": 700, "y": 620, "label": "Perf Eng."},
                            # Row 8: Deploy + SRE
                            {"id": "n24", "agent_id": "sre", "x": 500, "y": 720, "label": "SRE"},
                            # Row 9: TMA
                            {"id": "n25", "agent_id": "responsable_tma", "x": 200, "y": 820, "label": "Resp. TMA"},
                            {"id": "n26", "agent_id": "dev_tma", "x": 400, "y": 820, "label": "Dev TMA"},
                            {"id": "n27", "agent_id": "lean_portfolio_manager", "x": 100, "y": 120, "label": "Lean Portfolio"},
                        ],
                        "edges": [
                            # Idéation → Comité Strat
                            {"from": "n1", "to": "n3", "label": "besoin", "color": "#3b82f6"},
                            {"from": "n2", "to": "n3", "label": "UX", "color": "#3b82f6"},
                            {"from": "n4", "to": "n3", "label": "faisabilité", "color": "#3b82f6"},
                            {"from": "n3", "to": "n5", "label": "dossier", "color": "#a855f7"},
                            # Comité Strat interne
                            {"from": "n6", "to": "n5", "label": "avis CPO", "color": "#d946ef"},
                            {"from": "n7", "to": "n5", "label": "avis CTO", "color": "#d946ef"},
                            {"from": "n8", "to": "n5", "label": "WSJF", "color": "#10b981"},
                            {"from": "n27", "to": "n8", "label": "lean", "color": "#06b6d4"},
                            # GO → Constitution
                            {"from": "n5", "to": "n9", "label": "GO", "color": "#10b981"},
                            {"from": "n9", "to": "n10", "label": "staffing", "color": "#8b5cf6"},
                            {"from": "n10", "to": "n11", "label": "planning", "color": "#8b5cf6"},
                            # Architecture
                            {"from": "n10", "to": "n12", "label": "specs", "color": "#f59e0b"},
                            {"from": "n4", "to": "n12", "label": "archi", "color": "#a855f7"},
                            {"from": "n12", "to": "n13", "label": "review sécu", "color": "#ef4444"},
                            {"from": "n12", "to": "n14", "label": "infra", "color": "#8b5cf6"},
                            # Dev Sprint
                            {"from": "n12", "to": "n15", "label": "stories", "color": "#f59e0b"},
                            {"from": "n12", "to": "n16", "label": "stories", "color": "#f59e0b"},
                            {"from": "n12", "to": "n17", "label": "tests E2E", "color": "#3b82f6"},
                            # CICD
                            {"from": "n14", "to": "n18", "label": "pipeline", "color": "#8b5cf6"},
                            {"from": "n18", "to": "n19", "label": "scans sécu", "color": "#ef4444"},
                            {"from": "n17", "to": "n18", "label": "tests CI", "color": "#3b82f6"},
                            # QA Campaign
                            {"from": "n18", "to": "n20", "label": "build OK", "color": "#10b981"},
                            {"from": "n20", "to": "n21", "label": "plan test", "color": "#a855f7"},
                            {"from": "n21", "to": "n22", "label": "API tests", "color": "#3b82f6"},
                            {"from": "n21", "to": "n17", "label": "E2E tests", "color": "#3b82f6"},
                            {"from": "n23", "to": "n20", "label": "perf OK", "color": "#10b981"},
                            {"from": "n22", "to": "n20", "label": "résultats", "color": "#10b981"},
                            # Deploy
                            {"from": "n20", "to": "n10", "label": "GO/NOGO", "color": "#ef4444"},
                            {"from": "n14", "to": "n24", "label": "canary", "color": "#8b5cf6"},
                            {"from": "n24", "to": "n10", "label": "prod OK", "color": "#10b981"},
                            # TMA Handover
                            {"from": "n12", "to": "n25", "label": "transfert", "color": "#d946ef"},
                            {"from": "n25", "to": "n26", "label": "assigner", "color": "#f59e0b"},
                            {"from": "n20", "to": "n25", "label": "tests régression", "color": "#3b82f6"},
                            {"from": "n26", "to": "n24", "label": "hotfix", "color": "#ef4444"},
                        ],
                    },
                    "agents_permissions": {
                        "dsi": {"can_veto": True, "veto_level": "ABSOLUTE", "can_delegate": True, "can_approve": True},
                        "strat-cpo": {"can_veto": True, "veto_level": "STRONG", "can_approve": True},
                        "strat-cto": {"can_veto": True, "veto_level": "STRONG"},
                        "qa_lead": {"can_veto": True, "veto_level": "ABSOLUTE"},
                        "securite": {"can_veto": True, "veto_level": "ABSOLUTE"},
                        "test_manager": {"can_veto": True, "veto_level": "STRONG", "can_approve": True},
                        "responsable_tma": {"can_veto": True, "veto_level": "STRONG", "can_delegate": True},
                        "lead_dev": {"can_delegate": True, "can_veto": True, "veto_level": "STRONG"},
                        "chef_projet": {"can_delegate": True, "can_approve": True},
                        "devops": {"can_veto": True, "veto_level": "STRONG", "can_approve": True},
                        "sre": {"can_veto": True, "veto_level": "STRONG", "can_approve": True},
                        "pipeline_engineer": {"can_veto": True, "veto_level": "STRONG"},
                    },
                },
            ),
        )
        # ── DSI Platform Features: Discovery → Comité → Arch → Sprint → CI/CD → QA → Deploy → Retro ──
        builtins.append(
            WorkflowDef(
                id="dsi-platform-features",
                name="DSI Plateforme — Nouvelles Features",
                description="Pipeline complet pour les nouvelles fonctionnalités de la plateforme Macaron. "
                            "Discovery réseau → Comité stratégique GO/NOGO → Architecture → Sprint Dev (6 devs spécialisés) "
                            "→ CI/CD → QA parallèle → Deploy staging/prod → Rétrospective.",
                icon="star", is_builtin=True,
                phases=[
                    WorkflowPhase(id="discovery", pattern_id="network",
                                  name="Discovery & Idéation",
                                  description="Le DSI, le CPO, le CTO et le PO Plateforme débattent des nouvelles features. "
                                              "L'UX Designer et l'Architecte contribuent. Réseau de discussion ouverte pour faire émerger les idées.",
                                  gate="always",
                                  config={"agents": ["dsi", "strat-cpo", "strat-cto", "plat-product", "ux_designer", "architecte"]}),
                    WorkflowPhase(id="strategic-committee", pattern_id="human-in-the-loop",
                                  name="Comité Stratégique",
                                  description="Le comité stratégique (CPO, CTO, DSI, Portfolio Manager) valide les features proposées. "
                                              "GO/NOGO obligatoire. Seules les features validées passent en développement.",
                                  gate="all_approved",
                                  config={"agents": ["strat-cpo", "strat-cto", "dsi", "strat-portfolio", "lean_portfolio_manager"]}),
                    WorkflowPhase(id="architecture", pattern_id="aggregator",
                                  name="Architecture & Design",
                                  description="L'Architecte, le Lead Dev et les devs spécialisés (agents, patterns) conçoivent la solution. "
                                              "La Sécurité vérifie les impacts. Chacun contribue son expertise, l'Architecte synthétise.",
                                  gate="no_veto",
                                  config={"agents": ["architecte", "plat-lead-dev", "plat-dev-agents", "plat-dev-patterns", "securite"]}),
                    WorkflowPhase(id="sprint-planning", pattern_id="sequential",
                                  name="Sprint Planning",
                                  description="Le PO Plateforme écrit les user stories. Le Scrum Master organise le sprint. "
                                              "Le Lead Dev estime et découpe en tâches techniques.",
                                  gate="always",
                                  config={"agents": ["plat-product", "scrum_master", "plat-lead-dev"]}),
                    WorkflowPhase(id="dev-sprint", pattern_id="hierarchical",
                                  name="Sprint Développement",
                                  description="Le Lead Dev distribue les tâches à 5 devs spécialisés : Backend (routes, DB), "
                                              "Frontend (templates, CSS, HTMX), Agents (executor, loop, bus), Patterns (engine), Infra (deploy, SSE). "
                                              "Chaque dev code dans son domaine avec tests.",
                                  gate="no_veto",
                                  config={"agents": ["plat-lead-dev", "plat-dev-backend", "plat-dev-frontend",
                                                     "plat-dev-agents", "plat-dev-patterns", "plat-dev-infra"],
                                          "leader": "plat-lead-dev"}),
                    WorkflowPhase(id="cicd", pattern_id="sequential",
                                  name="Pipeline CI/CD",
                                  description="Le DevOps configure le pipeline. Le Pipeline Engineer vérifie les étapes. "
                                              "Le DevSecOps scanne les vulnérabilités. Build + lint + tests unitaires.",
                                  gate="always",
                                  config={"agents": ["devops", "pipeline_engineer", "devsecops"]}),
                    WorkflowPhase(id="qa-validation", pattern_id="parallel",
                                  name="QA & Validation",
                                  description="4 experts testent en parallèle : QA Lead (fonctionnel), Test Automation (E2E), "
                                              "Sécurité (OWASP), Performance (charge). Tous doivent valider.",
                                  gate="no_veto",
                                  config={"agents": ["qa_lead", "test_automation", "securite", "performance_engineer"]}),
                    WorkflowPhase(id="deploy-prod", pattern_id="sequential",
                                  name="Deploy Staging → Prod",
                                  description="Le DevOps déploie en staging. Le SRE vérifie la santé. Le QA Lead valide le smoke test. "
                                              "Le Lead Dev donne le GO final pour la prod.",
                                  gate="all_approved",
                                  config={"agents": ["devops", "sre", "qa_lead", "plat-lead-dev"]}),
                    WorkflowPhase(id="retrospective", pattern_id="network",
                                  name="Rétrospective",
                                  description="Le Lead Dev, le PO, le Scrum Master et le QA Lead débattent : "
                                              "ce qui a bien marché, ce qui a échoué, les améliorations à apporter. "
                                              "Les leçons sont stockées en mémoire globale.",
                                  gate="always",
                                  config={"agents": ["plat-lead-dev", "plat-product", "scrum_master", "qa_lead"]}),
                ],
                config={
                    "project_ref": "software-factory",
                    "graph": {
                        "pattern": "hierarchical",
                        "nodes": [
                            {"id": "n1", "agent_id": "dsi", "x": 400, "y": 20, "label": "DSI"},
                            {"id": "n2", "agent_id": "strat-cpo", "x": 250, "y": 20, "label": "CPO"},
                            {"id": "n3", "agent_id": "strat-cto", "x": 550, "y": 20, "label": "CTO"},
                            {"id": "n4", "agent_id": "strat-portfolio", "x": 700, "y": 20, "label": "Portfolio"},
                            {"id": "n5", "agent_id": "plat-product", "x": 100, "y": 120, "label": "PO Plateforme"},
                            {"id": "n6", "agent_id": "architecte", "x": 300, "y": 120, "label": "Architecte"},
                            {"id": "n7", "agent_id": "ux_designer", "x": 500, "y": 120, "label": "UX Designer"},
                            {"id": "n8", "agent_id": "scrum_master", "x": 700, "y": 120, "label": "Scrum Master"},
                            {"id": "n9", "agent_id": "plat-lead-dev", "x": 400, "y": 240, "label": "Lead Dev Platform"},
                            {"id": "n10", "agent_id": "plat-dev-backend", "x": 150, "y": 360, "label": "Dev Backend"},
                            {"id": "n11", "agent_id": "plat-dev-frontend", "x": 300, "y": 360, "label": "Dev Frontend"},
                            {"id": "n12", "agent_id": "plat-dev-agents", "x": 450, "y": 360, "label": "Dev Agents"},
                            {"id": "n13", "agent_id": "plat-dev-patterns", "x": 600, "y": 360, "label": "Dev Patterns"},
                            {"id": "n14", "agent_id": "plat-dev-infra", "x": 750, "y": 360, "label": "Dev Infra"},
                            {"id": "n15", "agent_id": "securite", "x": 100, "y": 120, "label": "Sécurité"},
                            {"id": "n16", "agent_id": "qa_lead", "x": 200, "y": 480, "label": "QA Lead"},
                            {"id": "n17", "agent_id": "test_automation", "x": 400, "y": 480, "label": "Test Automation"},
                            {"id": "n18", "agent_id": "performance_engineer", "x": 600, "y": 480, "label": "Perf Engineer"},
                            {"id": "n19", "agent_id": "devops", "x": 300, "y": 580, "label": "DevOps"},
                            {"id": "n20", "agent_id": "sre", "x": 500, "y": 580, "label": "SRE"},
                            {"id": "n21", "agent_id": "pipeline_engineer", "x": 400, "y": 580, "label": "Pipeline Eng."},
                            {"id": "n22", "agent_id": "devsecops", "x": 600, "y": 580, "label": "DevSecOps"},
                        ],
                        "edges": [
                            {"from": "n1", "to": "n6", "label": "vision", "color": "#a855f7"},
                            {"from": "n2", "to": "n5", "label": "priorités", "color": "#a855f7"},
                            {"from": "n3", "to": "n6", "label": "tech stack", "color": "#3b82f6"},
                            {"from": "n5", "to": "n8", "label": "stories", "color": "#f59e0b"},
                            {"from": "n5", "to": "n9", "label": "sprint", "color": "#f59e0b"},
                            {"from": "n6", "to": "n9", "label": "design", "color": "#3b82f6"},
                            {"from": "n9", "to": "n10", "label": "routes/DB", "color": "#10b981"},
                            {"from": "n9", "to": "n11", "label": "templates", "color": "#10b981"},
                            {"from": "n9", "to": "n12", "label": "executor", "color": "#10b981"},
                            {"from": "n9", "to": "n13", "label": "engine", "color": "#10b981"},
                            {"from": "n9", "to": "n14", "label": "infra", "color": "#10b981"},
                            {"from": "n10", "to": "n16", "label": "tests", "color": "#8b5cf6"},
                            {"from": "n11", "to": "n16", "label": "tests", "color": "#8b5cf6"},
                            {"from": "n12", "to": "n17", "label": "tests", "color": "#8b5cf6"},
                            {"from": "n15", "to": "n9", "label": "audit", "color": "#ef4444"},
                            {"from": "n16", "to": "n19", "label": "GO deploy", "color": "#10b981"},
                            {"from": "n17", "to": "n19", "label": "E2E OK", "color": "#10b981"},
                            {"from": "n19", "to": "n20", "label": "staging", "color": "#f59e0b"},
                            {"from": "n20", "to": "n9", "label": "prod GO", "color": "#10b981"},
                            {"from": "n21", "to": "n19", "label": "pipeline", "color": "#3b82f6"},
                            {"from": "n22", "to": "n19", "label": "scan", "color": "#ef4444"},
                        ],
                    },
                    "agents_permissions": {
                        "dsi": {"can_veto": True, "veto_level": "ABSOLUTE", "can_delegate": True, "can_approve": True},
                        "strat-cpo": {"can_veto": True, "veto_level": "ABSOLUTE", "can_approve": True},
                        "strat-cto": {"can_veto": True, "veto_level": "ABSOLUTE", "can_approve": True},
                        "plat-lead-dev": {"can_veto": True, "veto_level": "STRONG", "can_delegate": True, "can_approve": True},
                        "architecte": {"can_veto": True, "veto_level": "STRONG", "can_approve": True},
                        "qa_lead": {"can_veto": True, "veto_level": "ABSOLUTE"},
                        "securite": {"can_veto": True, "veto_level": "STRONG"},
                    },
                },
            ),
        )
        # ── DSI Platform TMA: Détection → Triage → Diagnostic → Fix → Non-Régression → Hotfix ──
        builtins.append(
            WorkflowDef(
                id="dsi-platform-tma",
                name="DSI Plateforme — TMA Maintenance",
                description="Pipeline réactif de maintenance applicative pour la plateforme Macaron. "
                            "Détection d'incidents (auto + manuel) → Triage P0-P4 → Diagnostic root cause parallèle "
                            "→ Fix TDD itératif → Non-régression complète → Deploy hotfix.",
                icon="tool", is_builtin=True,
                phases=[
                    WorkflowPhase(id="detection", pattern_id="parallel",
                                  name="Détection Incidents",
                                  description="Le TMA Lead analyse les incidents remontés (auto-détection 500, SSE drops, LLM failures + signalements manuels). "
                                              "Le SRE vérifie les métriques serveur. Le QA Lead vérifie les tests automatisés.",
                                  gate="always",
                                  config={"agents": ["plat-tma-lead", "sre", "qa_lead"]}),
                    WorkflowPhase(id="triage", pattern_id="router",
                                  name="Triage & Priorisation P0-P4",
                                  description="Le TMA Lead classifie chaque incident par sévérité (P0=platform down, P1=feature broken, "
                                              "P2=minor, P3=cosmetic, P4=tech debt) et par domaine (backend/frontend/agents/patterns/infra). "
                                              "L'Architecte évalue l'impact systémique. La Sécurité vérifie les aspects sécu.",
                                  gate="always",
                                  config={"agents": ["plat-tma-lead", "architecte", "securite"]}),
                    WorkflowPhase(id="diagnostic", pattern_id="parallel",
                                  name="Diagnostic Root Cause",
                                  description="4 devs TMA analysent en parallèle selon leur domaine : Backend (routes, DB), "
                                              "Frontend (templates, CSS, HTMX), Agents (executor, LLM, bus), DBA (requêtes, migrations). "
                                              "Chacun identifie la root cause dans son périmètre.",
                                  gate="always",
                                  config={"agents": ["plat-tma-dev-back", "plat-tma-dev-front", "plat-tma-dev-agents", "dba"]}),
                    WorkflowPhase(id="fix-tdd", pattern_id="loop",
                                  name="Fix TDD Itératif",
                                  description="Les devs TMA écrivent le test de non-régression (RED), puis le correctif (GREEN). "
                                              "La QA TMA valide. Si échec, on reboucle. Max 3 itérations avant escalation.",
                                  gate="no_veto",
                                  config={"agents": ["plat-tma-dev-back", "plat-tma-dev-front", "plat-tma-dev-agents", "plat-tma-qa"],
                                          "max_iterations": 3}),
                    WorkflowPhase(id="non-regression", pattern_id="parallel",
                                  name="Non-Régression Complète",
                                  description="La QA TMA lance les tests fonctionnels. Le Test Automation vérifie les E2E. "
                                              "La Sécurité fait un scan OWASP. Le Performance Engineer vérifie les benchmarks. "
                                              "TOUS doivent approuver.",
                                  gate="all_approved",
                                  config={"agents": ["plat-tma-qa", "test_automation", "securite", "performance_engineer"]}),
                    WorkflowPhase(id="deploy-hotfix", pattern_id="sequential",
                                  name="Deploy Hotfix",
                                  description="Le DevOps déploie le hotfix en staging. Le SRE vérifie la santé. "
                                              "Le TMA Lead confirme la résolution de l'incident. Le QA Lead donne le GO prod.",
                                  gate="all_approved",
                                  config={"agents": ["devops", "sre", "plat-tma-lead", "qa_lead"]}),
                ],
                config={
                    "project_ref": "software-factory",
                    "graph": {
                        "pattern": "hierarchical",
                        "nodes": [
                            {"id": "n1", "agent_id": "plat-tma-lead", "x": 400, "y": 20, "label": "TMA Lead"},
                            {"id": "n2", "agent_id": "sre", "x": 600, "y": 20, "label": "SRE"},
                            {"id": "n3", "agent_id": "architecte", "x": 250, "y": 120, "label": "Architecte"},
                            {"id": "n4", "agent_id": "securite", "x": 550, "y": 120, "label": "Sécurité"},
                            {"id": "n5", "agent_id": "plat-tma-dev-back", "x": 150, "y": 240, "label": "TMA Backend"},
                            {"id": "n6", "agent_id": "plat-tma-dev-front", "x": 350, "y": 240, "label": "TMA Frontend"},
                            {"id": "n7", "agent_id": "plat-tma-dev-agents", "x": 550, "y": 240, "label": "TMA Agents"},
                            {"id": "n8", "agent_id": "dba", "x": 750, "y": 240, "label": "DBA"},
                            {"id": "n9", "agent_id": "plat-tma-qa", "x": 300, "y": 360, "label": "QA TMA"},
                            {"id": "n10", "agent_id": "test_automation", "x": 500, "y": 360, "label": "Test Auto"},
                            {"id": "n11", "agent_id": "performance_engineer", "x": 700, "y": 360, "label": "Perf Eng."},
                            {"id": "n12", "agent_id": "qa_lead", "x": 200, "y": 20, "label": "QA Lead"},
                            {"id": "n13", "agent_id": "devops", "x": 400, "y": 460, "label": "DevOps"},
                        ],
                        "edges": [
                            {"from": "n1", "to": "n3", "label": "triage", "color": "#ef4444"},
                            {"from": "n1", "to": "n4", "label": "sécu?", "color": "#ef4444"},
                            {"from": "n1", "to": "n5", "label": "fix back", "color": "#f59e0b"},
                            {"from": "n1", "to": "n6", "label": "fix front", "color": "#f59e0b"},
                            {"from": "n1", "to": "n7", "label": "fix agents", "color": "#f59e0b"},
                            {"from": "n3", "to": "n1", "label": "impact", "color": "#3b82f6"},
                            {"from": "n5", "to": "n9", "label": "test", "color": "#10b981"},
                            {"from": "n6", "to": "n9", "label": "test", "color": "#10b981"},
                            {"from": "n7", "to": "n9", "label": "test", "color": "#10b981"},
                            {"from": "n8", "to": "n5", "label": "data", "color": "#3b82f6"},
                            {"from": "n9", "to": "n1", "label": "validé", "color": "#10b981"},
                            {"from": "n9", "to": "n10", "label": "E2E", "color": "#8b5cf6"},
                            {"from": "n10", "to": "n13", "label": "GO", "color": "#10b981"},
                            {"from": "n11", "to": "n13", "label": "perf OK", "color": "#10b981"},
                            {"from": "n12", "to": "n1", "label": "incidents", "color": "#ef4444"},
                            {"from": "n2", "to": "n1", "label": "métriques", "color": "#3b82f6"},
                            {"from": "n13", "to": "n1", "label": "déployé", "color": "#10b981"},
                        ],
                    },
                    "agents_permissions": {
                        "plat-tma-lead": {"can_veto": True, "veto_level": "STRONG", "can_delegate": True, "can_approve": True},
                        "qa_lead": {"can_veto": True, "veto_level": "ABSOLUTE"},
                        "plat-tma-qa": {"can_veto": True, "veto_level": "ABSOLUTE"},
                        "securite": {"can_veto": True, "veto_level": "STRONG"},
                        "architecte": {"can_veto": True, "veto_level": "STRONG"},
                    },
                },
            ),
        )

        # ── Security Hacking Workflow ──
        builtins.append(
            WorkflowDef(
                id="security-hacking",
                name="Security Hacking — Offensive + Défensive",
                description="Pipeline complet de sécurité offensive et défensive. "
                            "Red Team (reconnaissance, exploitation) → Blue Team (threat modeling, analyse) → "
                            "CISO review GO/NOGO → Dev Team (remediation TDD via PR) → "
                            "Verification (re-exploit + compliance) → Deploy hotfix sécurisé. "
                            "Inspiré PentAGI: Orchestrator→Researcher→Developer→Executor.",
                icon="shield", is_builtin=True,
                phases=[
                    WorkflowPhase(id="recon", pattern_id="parallel",
                                  name="Reconnaissance",
                                  description="Le Pentester Lead coordonne la phase de reconnaissance. "
                                              "La Security Researcher cartographie la surface d'attaque (OSINT, ports, services, APIs). "
                                              "L'Exploit Dev identifie les points d'entrée potentiels. Scan passif puis actif.",
                                  gate="always",
                                  config={"agents": ["pentester-lead", "security-researcher", "exploit-dev"]}),
                    WorkflowPhase(id="threat-model", pattern_id="network",
                                  name="Threat Modeling",
                                  description="Débat contradictoire Red Team vs Blue Team. "
                                              "Le Pentester Lead présente les vecteurs d'attaque identifiés. "
                                              "La Security Architect évalue les défenses existantes. "
                                              "La Threat Analyst quantifie les risques (STRIDE/DREAD). "
                                              "Objectif: prioriser les scénarios d'attaque par impact.",
                                  gate="always",
                                  config={"agents": ["pentester-lead", "security-architect", "threat-analyst", "security-researcher"]}),
                    WorkflowPhase(id="exploitation", pattern_id="loop",
                                  name="Exploitation",
                                  description="Le Pentester Lead orchestre les tests d'intrusion. "
                                              "L'Exploit Dev développe et exécute les PoC (SQLi, XSS, SSRF, auth bypass, RCE). "
                                              "Chaque vulnérabilité confirmée est scorée CVSS v3.1. "
                                              "Itération: tester → analyser → adapter → re-tester. Max 5 itérations.",
                                  gate="always",
                                  config={"agents": ["pentester-lead", "exploit-dev", "security-researcher"],
                                          "max_iterations": 5}),
                    WorkflowPhase(id="vuln-report", pattern_id="aggregator",
                                  name="Rapport de Vulnérabilités",
                                  description="Toutes les findings sont consolidées en un rapport structuré. "
                                              "La Security Researcher compile les CVE référencées. "
                                              "La Threat Analyst score et priorise (P0-P3). "
                                              "Le Pentester Lead rédige les recommandations de remédiation. "
                                              "Livrable: rapport CVSS avec PoC, impact, et remediation pour chaque vuln.",
                                  gate="always",
                                  config={"agents": ["pentester-lead", "security-researcher", "threat-analyst"],
                                          "leader": "threat-analyst"}),
                    WorkflowPhase(id="security-review", pattern_id="human-in-the-loop",
                                  name="Security Review — GO/NOGO",
                                  description="Le CISO examine le rapport de vulnérabilités. "
                                              "La Compliance Officer vérifie les implications réglementaires (GDPR, SOC2). "
                                              "La Security Architect recommande les priorités de remédiation. "
                                              "Checkpoint: GO (corriger immédiatement), NOGO (bloquer la release), "
                                              "PIVOT (accepter le risque avec plan de mitigation).",
                                  gate="checkpoint",
                                  config={"agents": ["ciso", "compliance_officer", "security-architect"]}),
                    WorkflowPhase(id="remediation", pattern_id="loop",
                                  name="Remédiation TDD",
                                  description="Le Security Dev Lead distribue les vulnérabilités aux développeurs. "
                                              "Chaque fix suit TDD: RED (test reproduit l'exploit) → GREEN (fix) → REFACTOR. "
                                              "Le Backend Dev corrige SQLi, auth bypass, SSRF. "
                                              "Le Frontend Dev corrige XSS, CSRF, CSP. "
                                              "La QA Security valide chaque PR. Loop max 3 itérations par vuln.",
                                  gate="no_veto",
                                  config={"agents": ["security-dev-lead", "security-backend-dev", "security-frontend-dev", "qa-security"],
                                          "leader": "security-dev-lead",
                                          "max_iterations": 3}),
                    WorkflowPhase(id="verification", pattern_id="parallel",
                                  name="Vérification & Non-Régression",
                                  description="Re-test parallèle multi-aspect. "
                                              "L'Exploit Dev re-exécute tous les PoC originaux — doivent ÉCHOUER. "
                                              "La QA Security lance OWASP ZAP + SAST/DAST + tests de régression. "
                                              "La Compliance Officer vérifie la conformité réglementaire. "
                                              "Le SecOps vérifie les contrôles de sécurité en place. "
                                              "TOUS doivent approuver.",
                                  gate="all_approved",
                                  config={"agents": ["exploit-dev", "qa-security", "compliance_officer", "secops-engineer"]}),
                    WorkflowPhase(id="deploy-secure", pattern_id="sequential",
                                  name="Deploy Sécurisé & Monitoring",
                                  description="Le SecOps déploie le hotfix en staging. "
                                              "La QA Security valide en staging. "
                                              "Le Pentester Lead fait un smoke test sécurité. "
                                              "Le CISO donne le GO final pour la prod. "
                                              "Pipeline: staging → E2E sécu → canary 1% → monitoring → prod 100%.",
                                  gate="all_approved",
                                  config={"agents": ["secops-engineer", "qa-security", "pentester-lead", "ciso"]}),
                ],
                config={
                    "orchestrator": "ciso",
                    "graph": {
                        "pattern": "hierarchical",
                        "nodes": [
                            # Red Team
                            {"id": "n1", "agent_id": "pentester-lead", "x": 400, "y": 20, "label": "Pentester Lead", "phase": "recon"},
                            {"id": "n2", "agent_id": "security-researcher", "x": 200, "y": 120, "label": "Researcher", "phase": "recon"},
                            {"id": "n3", "agent_id": "exploit-dev", "x": 600, "y": 120, "label": "Exploit Dev", "phase": "exploitation"},
                            # Blue Team
                            {"id": "n4", "agent_id": "security-architect", "x": 100, "y": 240, "label": "Security Architect", "phase": "threat-model"},
                            {"id": "n5", "agent_id": "threat-analyst", "x": 400, "y": 240, "label": "Threat Analyst", "phase": "threat-model"},
                            {"id": "n6", "agent_id": "secops-engineer", "x": 700, "y": 240, "label": "SecOps", "phase": "deploy-secure"},
                            # Governance
                            {"id": "n7", "agent_id": "ciso", "x": 250, "y": 360, "label": "CISO", "phase": "security-review"},
                            {"id": "n8", "agent_id": "compliance_officer", "x": 550, "y": 360, "label": "Compliance", "phase": "security-review"},
                            # Dev Team
                            {"id": "n9", "agent_id": "security-dev-lead", "x": 400, "y": 480, "label": "Security Dev Lead", "phase": "remediation"},
                            {"id": "n10", "agent_id": "security-backend-dev", "x": 200, "y": 580, "label": "Backend Dev", "phase": "remediation"},
                            {"id": "n11", "agent_id": "security-frontend-dev", "x": 400, "y": 580, "label": "Frontend Dev", "phase": "remediation"},
                            {"id": "n12", "agent_id": "qa-security", "x": 600, "y": 580, "label": "QA Security", "phase": "verification"},
                        ],
                        "edges": [
                            # Phase 1: Recon
                            {"from": "n1", "to": "n2", "label": "recon OSINT", "color": "#ef4444"},
                            {"from": "n1", "to": "n3", "label": "recon exploit", "color": "#ef4444"},
                            # Phase 2: Threat Model (network/debate)
                            {"from": "n2", "to": "n4", "label": "surface", "color": "#f97316"},
                            {"from": "n2", "to": "n5", "label": "findings", "color": "#f97316"},
                            {"from": "n1", "to": "n5", "label": "vecteurs", "color": "#f97316"},
                            {"from": "n4", "to": "n5", "label": "défenses", "color": "#3b82f6"},
                            {"from": "n5", "to": "n1", "label": "priorités", "color": "#8b5cf6"},
                            # Phase 3: Exploitation
                            {"from": "n1", "to": "n3", "label": "exploit", "color": "#dc2626"},
                            {"from": "n3", "to": "n5", "label": "CVSS", "color": "#dc2626"},
                            # Phase 4: Report → Phase 5: Review
                            {"from": "n5", "to": "n7", "label": "rapport", "color": "#fbbf24"},
                            {"from": "n5", "to": "n8", "label": "compliance?", "color": "#fbbf24"},
                            {"from": "n4", "to": "n7", "label": "recommandations", "color": "#3b82f6"},
                            # Phase 6: Remediation
                            {"from": "n7", "to": "n9", "label": "GO fix", "color": "#22c55e"},
                            {"from": "n9", "to": "n10", "label": "fix backend", "color": "#22c55e"},
                            {"from": "n9", "to": "n11", "label": "fix frontend", "color": "#22c55e"},
                            {"from": "n9", "to": "n12", "label": "validate PR", "color": "#22c55e"},
                            # Phase 7: Verification
                            {"from": "n10", "to": "n12", "label": "PR ready", "color": "#10b981"},
                            {"from": "n11", "to": "n12", "label": "PR ready", "color": "#10b981"},
                            {"from": "n12", "to": "n3", "label": "re-exploit?", "color": "#a78bfa"},
                            {"from": "n3", "to": "n12", "label": "exploit fails", "color": "#10b981"},
                            {"from": "n12", "to": "n8", "label": "compliance OK?", "color": "#64748b"},
                            # Phase 8: Deploy
                            {"from": "n8", "to": "n6", "label": "approved", "color": "#06b6d4"},
                            {"from": "n12", "to": "n6", "label": "QA GO", "color": "#10b981"},
                            {"from": "n6", "to": "n7", "label": "deployed", "color": "#10b981"},
                            {"from": "n6", "to": "n1", "label": "monitoring", "color": "#06b6d4"},
                        ],
                    },
                    "agents_permissions": {
                        "pentester-lead": {"can_veto": True, "veto_level": "STRONG", "can_delegate": True},
                        "ciso": {"can_veto": True, "veto_level": "ABSOLUTE", "can_approve": True},
                        "compliance_officer": {"can_veto": True, "veto_level": "STRONG", "can_approve": True},
                        "qa-security": {"can_veto": True, "veto_level": "ABSOLUTE"},
                        "security-architect": {"can_veto": True, "veto_level": "STRONG"},
                        "threat-analyst": {"can_veto": True, "veto_level": "STRONG"},
                        "security-dev-lead": {"can_delegate": True, "can_approve": True},
                    },
                },
            ),
        )

        # ── RSE Compliance Workflow ──
        builtins.append(
            WorkflowDef(
                id="rse-compliance",
                name="RSE — Audit Responsabilité Sociétale",
                description="Pipeline complet d'audit RSE: RGPD/Privacy → Juridique numérique (DSA/DMA/AI Act) → "
                            "Green IT & Éco-conception (RGESN) → Accessibilité (RGAA/WCAG) → "
                            "Éthique IA (biais, explicabilité) → Audit social (diversité, inclusion) → "
                            "Synthèse RSE avec GO/NOGO. Agents avec accès web pour veille réglementaire.",
                icon="heart", is_builtin=True,
                phases=[
                    WorkflowPhase(id="rgpd-audit", pattern_id="sequential",
                                  name="Audit RGPD & Privacy",
                                  description="La DPO Margaux Leroy audite la conformité RGPD: "
                                              "base légale des traitements, minimisation, durées de conservation, "
                                              "droits des personnes (accès, effacement, portabilité), PIA si nécessaire. "
                                              "Le Juriste complète sur les transferts hors UE et sous-traitants. "
                                              "Recherche web des dernières décisions CNIL.",
                                  gate="always",
                                  config={"agents": ["rse-dpo", "rse-juriste"]}),
                    WorkflowPhase(id="legal-audit", pattern_id="sequential",
                                  name="Audit Juridique Numérique",
                                  description="Le Juriste Étienne Vasseur audite la conformité: "
                                              "DSA (modération, transparence), DMA (interopérabilité), "
                                              "AI Act (classification risque IA), ePrivacy (cookies, traceurs), "
                                              "LCEN (mentions légales), CGU/CGV (clauses abusives), "
                                              "propriété intellectuelle (licences open source). "
                                              "Veille sur les dernières évolutions réglementaires EU.",
                                  gate="always",
                                  config={"agents": ["rse-juriste", "rse-dpo"]}),
                    WorkflowPhase(id="green-it-audit", pattern_id="network",
                                  name="Audit Green IT & Éco-conception",
                                  description="Débat entre l'Expert NR Tristan Beaumont et l'Expert Éco-conception "
                                              "Raphaël Morin. RGESN (79 critères), poids des pages, bundle JS, "
                                              "requêtes optimisées, hébergement vert, dimensionnement infrastructure. "
                                              "Mesures: EcoIndex, Lighthouse, Website Carbon Calculator. "
                                              "Propositions sobres et budget carbone par feature.",
                                  gate="always",
                                  config={"agents": ["rse-nr", "rse-eco", "rse-manager"]}),
                    WorkflowPhase(id="a11y-audit", pattern_id="sequential",
                                  name="Audit Accessibilité — RGAA & WCAG",
                                  description="Noémie Garnier audite selon RGAA 4.1 (106 critères) et WCAG 2.2 AA. "
                                              "Contraste, navigation clavier, lecteur d'écran (NVDA, VoiceOver), "
                                              "formulaires, images alt, focus visible, zoom 200%. "
                                              "Test avec axe-core, pa11y, et manuellement. "
                                              "Directive EAA (European Accessibility Act) applicable juin 2025.",
                                  gate="always",
                                  config={"agents": ["rse-a11y", "accessibility_expert"]}),
                    WorkflowPhase(id="ethique-ia-audit", pattern_id="network",
                                  name="Audit Éthique IA & Biais",
                                  description="Aïssatou Diallo audite les systèmes IA: "
                                              "classification AI Act, biais (disparate impact, equal opportunity), "
                                              "explicabilité (SHAP, LIME), transparence, human oversight. "
                                              "Avec le ML Engineer pour les aspects techniques. "
                                              "Veille AI Act articles et guidelines HLEG via web.",
                                  gate="always",
                                  config={"agents": ["rse-ethique-ia", "ml_engineer", "rse-manager"]}),
                    WorkflowPhase(id="social-audit", pattern_id="sequential",
                                  name="Audit Social & Inclusion",
                                  description="Ibrahim Keïta audite l'impact social: "
                                              "diversité équipes (genre, origines, handicap, index Pénicaud), "
                                              "conditions de travail IT (charge cognitive, on-call equity), "
                                              "inclusion produit (illectronisme, fracture numérique). "
                                              "Avec l'experte accessibilité pour l'inclusion numérique.",
                                  gate="always",
                                  config={"agents": ["rse-audit-social", "rse-a11y"]}),
                    WorkflowPhase(id="rse-synthesis", pattern_id="human-in-the-loop",
                                  name="Synthèse RSE — GO/NOGO",
                                  description="La Directrice RSE Sabrina Okafor consolide tous les audits. "
                                              "Score ESG global, conformité par pilier (E/S/G). "
                                              "Le Juriste confirme les risques juridiques. "
                                              "La DPO valide la conformité RGPD. "
                                              "Checkpoint: GO (conforme), NOGO (non-conformités critiques), "
                                              "PIVOT (plan de remediation avec jalons).",
                                  gate="checkpoint",
                                  config={"agents": ["rse-manager", "rse-dpo", "rse-juriste", "rse-ethique-ia"]}),
                ],
                config={
                    "orchestrator": "rse-manager",
                    "graph": {
                        "pattern": "sequential",
                        "nodes": [
                            {"id": "r1", "agent_id": "rse-dpo", "x": 100, "y": 30, "label": "DPO", "phase": "rgpd-audit"},
                            {"id": "r2", "agent_id": "rse-juriste", "x": 350, "y": 30, "label": "Juriste", "phase": "legal-audit"},
                            {"id": "r3", "agent_id": "rse-nr", "x": 100, "y": 150, "label": "Expert NR", "phase": "green-it-audit"},
                            {"id": "r4", "agent_id": "rse-eco", "x": 350, "y": 150, "label": "Éco-conception", "phase": "green-it-audit"},
                            {"id": "r5", "agent_id": "rse-a11y", "x": 100, "y": 270, "label": "A11Y Lead", "phase": "a11y-audit"},
                            {"id": "r6", "agent_id": "accessibility_expert", "x": 350, "y": 270, "label": "Expert A11Y", "phase": "a11y-audit"},
                            {"id": "r7", "agent_id": "rse-ethique-ia", "x": 100, "y": 390, "label": "Éthique IA", "phase": "ethique-ia-audit"},
                            {"id": "r8", "agent_id": "ml_engineer", "x": 350, "y": 390, "label": "ML Engineer", "phase": "ethique-ia-audit"},
                            {"id": "r9", "agent_id": "rse-audit-social", "x": 225, "y": 500, "label": "Audit Social", "phase": "social-audit"},
                            {"id": "r10", "agent_id": "rse-manager", "x": 225, "y": 620, "label": "Dir. RSE", "phase": "rse-synthesis"},
                        ],
                        "edges": [
                            {"from": "r1", "to": "r2", "label": "privacy → legal", "color": "#8b5cf6"},
                            {"from": "r2", "to": "r3", "label": "compliant → green", "color": "#22c55e"},
                            {"from": "r3", "to": "r4", "label": "NR ↔ éco", "color": "#22c55e"},
                            {"from": "r4", "to": "r5", "label": "green → a11y", "color": "#06b6d4"},
                            {"from": "r5", "to": "r6", "label": "lead ↔ expert", "color": "#06b6d4"},
                            {"from": "r6", "to": "r7", "label": "a11y → éthique", "color": "#f59e0b"},
                            {"from": "r7", "to": "r8", "label": "éthique ↔ ML", "color": "#f59e0b"},
                            {"from": "r8", "to": "r9", "label": "IA → social", "color": "#ec4899"},
                            {"from": "r9", "to": "r10", "label": "all → synthèse", "color": "#8b5cf6"},
                            {"from": "r1", "to": "r10", "label": "RGPD report", "color": "#8b5cf6"},
                            {"from": "r3", "to": "r10", "label": "Green report", "color": "#22c55e"},
                            {"from": "r5", "to": "r10", "label": "A11Y report", "color": "#06b6d4"},
                            {"from": "r7", "to": "r10", "label": "Ethics report", "color": "#f59e0b"},
                        ],
                    },
                    "agents_permissions": {
                        "rse-manager": {"can_veto": True, "veto_level": "STRONG", "can_delegate": True, "can_approve": True},
                        "rse-dpo": {"can_veto": True, "veto_level": "STRONG"},
                        "rse-juriste": {"can_veto": True, "veto_level": "STRONG"},
                        "rse-a11y": {"can_veto": True, "veto_level": "STRONG"},
                        "rse-ethique-ia": {"can_veto": True, "veto_level": "STRONG"},
                    },
                },
            ),
        )

        # ── Epic Decompose (Recursive Mission Orchestration) ────────────
        builtins.append(
            WorkflowDef(
                id="epic-decompose",
                name="Epic Decompose — ART Recursive",
                description=(
                    "Décomposition récursive d'un Epic SAFe en Features parallèles. "
                    "PI Planning → Feature Planning → Sprint Execution (parallel) → Integration → Release. "
                    "8 Feature Teams, WIP limits, build queue globale, traçabilité AO."
                ),
                icon="git-branch",
                is_builtin=True,
                phases=[
                    WorkflowPhase(
                        id="pi-planning",
                        pattern_id="network",
                        name="PI Planning",
                        description="RTE + PM + Archi débattent la décomposition en Features. Input: AO + VISION.md + codebase.",
                        gate="always",
                        config={
                            "agents": ["rte", "product-manager-art", "system-architect-art"],
                            "max_iterations": 3,
                        },
                    ),
                    WorkflowPhase(
                        id="feature-planning",
                        pattern_id="hierarchical",
                        name="Feature Planning",
                        description="RTE délègue aux Feature Leads. Chaque Lead planifie ses Stories avec REQ-IDs.",
                        gate="always",
                        config={
                            "agents": ["rte", "ft-auth-lead", "ft-booking-lead", "ft-payment-lead",
                                       "ft-admin-lead", "ft-user-lead", "ft-infra-lead", "ft-e2e-lead", "ft-proto-lead"],
                            "leader": "rte",
                        },
                    ),
                    WorkflowPhase(
                        id="sprint-execution",
                        pattern_id="parallel",
                        name="Sprint Execution",
                        description="N Feature Teams travaillent en parallèle. WIP max 4. Chaque team exécute son feature-sprint.",
                        gate="no_veto",
                        config={
                            "agents": ["ft-auth-lead", "ft-booking-lead", "ft-payment-lead",
                                       "ft-admin-lead", "ft-user-lead", "ft-infra-lead", "ft-e2e-lead", "ft-proto-lead"],
                            "max_concurrent": 4,
                        },
                    ),
                    WorkflowPhase(
                        id="system-integration",
                        pattern_id="aggregator",
                        name="System Integration",
                        description="System Architect agrège les résultats. Merge branches, build global, tests cross-domain.",
                        gate="all_approved",
                        config={
                            "agents": ["system-architect-art", "ft-e2e-lead", "ft-proto-lead", "ft-infra-lead"],
                        },
                    ),
                    WorkflowPhase(
                        id="pi-review-release",
                        pattern_id="human-in-the-loop",
                        name="PI Review & Release",
                        description="Demo → PM review → Staging → E2E global → Canary → Prod. GO/NOGO checkpoint.",
                        gate="checkpoint",
                        config={
                            "agents": ["product-manager-art", "rte", "system-architect-art", "ft-e2e-lead"],
                        },
                    ),
                ],
                config={
                    "graph": {
                        "nodes": [
                            {"id": "n1", "agent_id": "rte", "x": 400, "y": 20, "label": "RTE Marc", "phase": "pi-planning"},
                            {"id": "n2", "agent_id": "product-manager-art", "x": 200, "y": 20, "label": "PM Isabelle", "phase": "pi-planning"},
                            {"id": "n3", "agent_id": "system-architect-art", "x": 600, "y": 20, "label": "Archi Catherine", "phase": "pi-planning"},
                            {"id": "n4", "agent_id": "ft-auth-lead", "x": 50, "y": 170, "label": "Auth Nicolas", "phase": "feature-planning"},
                            {"id": "n5", "agent_id": "ft-booking-lead", "x": 200, "y": 170, "label": "Booking Antoine", "phase": "feature-planning"},
                            {"id": "n6", "agent_id": "ft-payment-lead", "x": 350, "y": 170, "label": "Payment Caroline", "phase": "feature-planning"},
                            {"id": "n7", "agent_id": "ft-admin-lead", "x": 500, "y": 170, "label": "Admin Olivier", "phase": "feature-planning"},
                            {"id": "n8", "agent_id": "ft-user-lead", "x": 650, "y": 170, "label": "User Sarah", "phase": "feature-planning"},
                            {"id": "n9", "agent_id": "ft-infra-lead", "x": 50, "y": 320, "label": "Infra Francois", "phase": "sprint-execution"},
                            {"id": "n10", "agent_id": "ft-e2e-lead", "x": 250, "y": 320, "label": "E2E Virginie", "phase": "sprint-execution"},
                            {"id": "n11", "agent_id": "ft-proto-lead", "x": 450, "y": 320, "label": "Proto JB", "phase": "sprint-execution"},
                            {"id": "n12", "agent_id": "system-architect-art", "x": 400, "y": 470, "label": "Integration", "phase": "system-integration"},
                            {"id": "n13", "agent_id": "product-manager-art", "x": 400, "y": 570, "label": "PI Review", "phase": "pi-review-release"},
                        ],
                        "edges": [
                            {"from": "n2", "to": "n1", "label": "vision", "color": "#bc8cff"},
                            {"from": "n3", "to": "n1", "label": "arch", "color": "#58a6ff"},
                            {"from": "n1", "to": "n2", "label": "feedback", "color": "#d29922"},
                            {"from": "n1", "to": "n3", "label": "feedback", "color": "#d29922"},
                            {"from": "n1", "to": "n4", "label": "delegate", "color": "#f97316"},
                            {"from": "n1", "to": "n5", "label": "delegate", "color": "#22c55e"},
                            {"from": "n1", "to": "n6", "label": "delegate", "color": "#eab308"},
                            {"from": "n1", "to": "n7", "label": "delegate", "color": "#a855f7"},
                            {"from": "n1", "to": "n8", "label": "delegate", "color": "#06b6d4"},
                            {"from": "n4", "to": "n9", "label": "infra", "color": "#ef4444"},
                            {"from": "n5", "to": "n10", "label": "e2e", "color": "#ec4899"},
                            {"from": "n6", "to": "n11", "label": "proto", "color": "#64748b"},
                            {"from": "n7", "to": "n10", "label": "e2e", "color": "#ec4899"},
                            {"from": "n8", "to": "n10", "label": "e2e", "color": "#ec4899"},
                            {"from": "n9", "to": "n12", "label": "merge", "color": "#58a6ff"},
                            {"from": "n10", "to": "n12", "label": "tests", "color": "#ec4899"},
                            {"from": "n11", "to": "n12", "label": "schemas", "color": "#64748b"},
                            {"from": "n4", "to": "n12", "label": "merge", "color": "#f97316"},
                            {"from": "n5", "to": "n12", "label": "merge", "color": "#22c55e"},
                            {"from": "n6", "to": "n12", "label": "merge", "color": "#eab308"},
                            {"from": "n12", "to": "n13", "label": "release", "color": "#d29922"},
                        ],
                    },
                    "agents_permissions": {
                        "rte": {"can_delegate": True, "can_veto": True, "veto_level": "strong"},
                        "product-manager-art": {"can_veto": True, "veto_level": "advisory"},
                        "system-architect-art": {"can_veto": True, "veto_level": "strong"},
                        "ft-e2e-lead": {"can_veto": True, "veto_level": "absolute"},
                    },
                },
            ),
        )

        # ── Feature Sprint (reusable per Feature) ──────────────────────
        builtins.append(
            WorkflowDef(
                id="feature-sprint",
                name="Feature Sprint — TDD Cycle",
                description=(
                    "Workflow réutilisable pour chaque Feature d'un Epic. "
                    "Design → TDD Sprint → Adversarial Review → E2E Tests → Deploy. "
                    "Utilisé par chaque Feature Team dans le cadre d'un epic-decompose."
                ),
                icon="repeat",
                is_builtin=True,
                phases=[
                    WorkflowPhase(
                        id="feature-design",
                        pattern_id="aggregator",
                        name="Feature Design",
                        description="Lead + Archi définissent l'architecture de la feature. Stories, acceptance criteria, interfaces.",
                        gate="always",
                        config={
                            "agents": ["system-architect-art"],
                            "dynamic_lead": True,
                        },
                    ),
                    WorkflowPhase(
                        id="tdd-sprint",
                        pattern_id="loop",
                        name="TDD Sprint",
                        description="Devs implémentent en TDD. RED→GREEN→REFACTOR. FRACTAL: feature/guards/failures.",
                        gate="no_veto",
                        config={
                            "agents": [],
                            "max_iterations": 10,
                            "dynamic_team": True,
                        },
                    ),
                    WorkflowPhase(
                        id="adversarial-review",
                        pattern_id="sequential",
                        name="Adversarial Review",
                        description="L0 fast checks → L1 code critic → L2 architecture critic. Multi-vendor cascade.",
                        gate="all_approved",
                        config={
                            "agents": ["system-architect-art"],
                            "dynamic_reviewers": True,
                        },
                    ),
                    WorkflowPhase(
                        id="feature-e2e",
                        pattern_id="parallel",
                        name="Tests E2E",
                        description="Tests E2E API + IHM en parallèle. Smoke + journeys.",
                        gate="all_approved",
                        config={
                            "agents": ["ft-e2e-api", "ft-e2e-ihm"],
                        },
                    ),
                    WorkflowPhase(
                        id="feature-deploy",
                        pattern_id="sequential",
                        name="Deploy Feature",
                        description="Build → Staging → Canary. Rollback auto si erreur.",
                        gate="no_veto",
                        config={
                            "agents": ["ft-infra-lead"],
                            "dynamic_deployer": True,
                        },
                    ),
                ],
                config={
                    "graph": {
                        "nodes": [
                            {"id": "n1", "agent_id": "system-architect-art", "x": 400, "y": 20, "label": "Design", "phase": "feature-design"},
                            {"id": "n2", "agent_id": "ft-auth-lead", "x": 200, "y": 150, "label": "TDD Dev 1", "phase": "tdd-sprint"},
                            {"id": "n3", "agent_id": "ft-auth-dev1", "x": 400, "y": 150, "label": "TDD Dev 2", "phase": "tdd-sprint"},
                            {"id": "n4", "agent_id": "ft-auth-dev2", "x": 600, "y": 150, "label": "TDD Dev 3", "phase": "tdd-sprint"},
                            {"id": "n5", "agent_id": "system-architect-art", "x": 400, "y": 280, "label": "Review", "phase": "adversarial-review"},
                            {"id": "n6", "agent_id": "ft-e2e-api", "x": 300, "y": 380, "label": "E2E API", "phase": "feature-e2e"},
                            {"id": "n7", "agent_id": "ft-e2e-ihm", "x": 500, "y": 380, "label": "E2E IHM", "phase": "feature-e2e"},
                            {"id": "n8", "agent_id": "ft-infra-lead", "x": 400, "y": 480, "label": "Deploy", "phase": "feature-deploy"},
                        ],
                        "edges": [
                            {"from": "n1", "to": "n2", "label": "stories", "color": "#58a6ff"},
                            {"from": "n1", "to": "n3", "label": "stories", "color": "#58a6ff"},
                            {"from": "n1", "to": "n4", "label": "stories", "color": "#58a6ff"},
                            {"from": "n2", "to": "n5", "label": "code", "color": "#3fb950"},
                            {"from": "n3", "to": "n5", "label": "code", "color": "#3fb950"},
                            {"from": "n4", "to": "n5", "label": "code", "color": "#3fb950"},
                            {"from": "n5", "to": "n6", "label": "approved", "color": "#ec4899"},
                            {"from": "n5", "to": "n7", "label": "approved", "color": "#ec4899"},
                            {"from": "n6", "to": "n8", "label": "pass", "color": "#d29922"},
                            {"from": "n7", "to": "n8", "label": "pass", "color": "#d29922"},
                        ],
                    },
                },
            ),
        )

        for w in builtins:
            if w.id not in existing_ids:
                self.create(w)

    def _row_to_wf(self, row) -> WorkflowDef:
        phases_data = json.loads(row["phases_json"] or "[]")
        return WorkflowDef(
            id=row["id"],
            name=row["name"],
            description=row["description"] or "",
            phases=[WorkflowPhase(**p) for p in phases_data],
            config=json.loads(row["config_json"] or "{}"),
            icon=row["icon"] or "workflow",
            is_builtin=bool(row["is_builtin"]),
            created_at=row["created_at"] or "",
        )


_store: Optional[WorkflowStore] = None


def get_workflow_store() -> WorkflowStore:
    global _store
    if _store is None:
        _store = WorkflowStore()
        _store.seed_builtins()
    return _store


# ── RTE Facilitator ──────────────────────────────────────────────

_RTE_AGENT_ID = "release_train_engineer"

async def _rte_facilitate(
    session_id: str,
    prompt: str,
    to_agent: str = "",
    project_id: str = "",
) -> str:
    """Call the RTE agent via LLM to facilitate a workflow transition.
    Returns the RTE's message content."""
    from ..agents.store import get_agent_store
    from ..agents.executor import get_executor, ExecutionContext

    store = get_session_store()
    agent_store = get_agent_store()
    rte = agent_store.get(_RTE_AGENT_ID)
    if not rte:
        # Fallback to system message if RTE agent not found
        store.add_message(MessageDef(
            session_id=session_id,
            from_agent="system", to_agent=to_agent or "all",
            message_type="system", content=prompt,
        ))
        return prompt

    # Push thinking status
    await _push_sse(session_id, {
        "type": "agent_status",
        "agent_id": rte.id,
        "status": "thinking",
    })

    ctx = ExecutionContext(
        agent=rte,
        session_id=session_id,
        project_id=project_id,
        tools_enabled=False,  # RTE doesn't need tools, just speaks
    )

    # Stream the RTE response via SSE
    await _push_sse(session_id, {
        "type": "stream_start",
        "agent_id": rte.id,
        "agent_name": rte.name,
        "node_id": rte.id,
        "pattern_type": "workflow",
        "to_agent": to_agent or "all",
        "flow_step": "Facilitation",
        "iteration": 0,
    })

    executor = get_executor()
    accumulated = ""
    try:
        async for kind, value in executor.run_streaming(ctx, prompt):
            if kind == "delta" and value:
                accumulated += value
                await _push_sse(session_id, {
                    "type": "stream_delta",
                    "agent_id": rte.id,
                    "delta": value,
                })
            elif kind == "result":
                accumulated = value.content or accumulated
    except Exception as e:
        logger.error("RTE streaming failed: %s", e)
        # Fallback to non-streaming
        result = await executor.run(ctx, prompt)
        accumulated = result.content

    await _push_sse(session_id, {
        "type": "stream_end",
        "agent_id": rte.id,
        "content": accumulated,
        "message_type": "text",
        "to_agent": to_agent or "all",
    })

    msg = MessageDef(
        session_id=session_id,
        from_agent=rte.id,
        to_agent=to_agent or "all",
        message_type="text",
        content=accumulated,
    )
    store.add_message(msg)
    await _push_sse(session_id, {
        "type": "agent_status",
        "agent_id": rte.id,
        "status": "idle",
    })

    return accumulated


# ── Workflow Engine ──────────────────────────────────────────────

async def run_workflow(
    workflow: WorkflowDef,
    session_id: str,
    initial_task: str,
    project_id: str = "",
) -> WorkflowRun:
    """Execute a workflow — RTE facilitates each phase transition."""
    run = WorkflowRun(
        workflow=workflow,
        session_id=session_id,
        project_id=project_id,
    )

    store = get_session_store()
    pattern_store = get_pattern_store()

    # Workflow leader = first agent of first phase (typically CP)
    leader = ""
    if workflow.phases:
        first_agents = workflow.phases[0].config.get("agents", [])
        if first_agents:
            leader = first_agents[0]

    # RTE kicks off the sprint
    ceremony_names = [p.name for p in workflow.phases]
    await _rte_facilitate(
        session_id,
        f"Tu lances le sprint **{workflow.name}** — {len(workflow.phases)} cérémonies: {', '.join(ceremony_names)}.\n"
        f"Objectif du sprint: {initial_task}\n\n"
        f"Annonce le démarrage à l'équipe. Le Scrum Master facilite, le CP priorise, l'équipe s'organise.",
        to_agent=leader,
        project_id=project_id,
    )

    task = initial_task
    accumulated_context = []
    for i, phase in enumerate(workflow.phases):
        run.current_phase = i

        phase_agents = phase.config.get("agents", [])
        phase_leader = phase_agents[0] if phase_agents else leader or "all"

        # RTE facilitates ceremony transition
        prev_summary = ""
        if accumulated_context:
            prev_summary = "\n".join(f"- {c}" for c in accumulated_context[-3:])
        await _rte_facilitate(
            session_id,
            f"**{phase.name}**\n"
            f"{phase.description}\n"
            f"Participants: {', '.join(phase_agents)}\n"
            f"{f'Contexte:{chr(10)}{prev_summary}' if prev_summary else ''}\n\n"
            f"Facilite la cérémonie. Donne la parole à {phase_leader}.",
            to_agent=phase_leader,
            project_id=project_id,
        )

        pattern = pattern_store.get(phase.pattern_id)
        if not pattern:
            await _rte_facilitate(
                session_id,
                f"Le pattern '{phase.pattern_id}' n'existe pas. On passe à la phase suivante.",
                to_agent=phase_leader,
                project_id=project_id,
            )
            continue

        # Override pattern agents with the phase's workflow agents
        if phase_agents:
            from ..patterns.store import PatternDef as PD
            pattern = PD(
                id=f"{workflow.id}-{phase.id}",
                name=f"{phase.name}",
                description=phase.description,
                type=pattern.type,
                agents=[{"id": f"n{j}", "agent_id": aid} for j, aid in enumerate(phase_agents)],
                edges=[],
                config=pattern.config,
                icon=pattern.icon,
            )

        # Build ceremony-specific task with accumulated context
        phase_task = f"## {phase.name}\n{phase.description}\n\n"
        if accumulated_context:
            phase_task += "## Previous phases summary:\n"
            for ctx in accumulated_context[-3:]:
                phase_task += f"- {ctx}\n"
            phase_task += "\n"
        phase_task += f"## Original goal:\n{initial_task}"

        try:
            result = await run_pattern(pattern, session_id, phase_task, project_id)
            run.phase_results.append({
                "phase": phase.name,
                "success": result.success,
                "error": result.error,
            })

            # RTE reacts to gate results
            if phase.gate == "all_approved" and not result.success:
                run.status = "gated"
                await _rte_facilitate(
                    session_id,
                    f"La phase **{phase.name}** n'a pas obtenu l'approbation de tous. "
                    f"Des vetos non résolus subsistent après les boucles de correction. "
                    f"Le workflow est bloqué. Synthétise la situation et propose les prochaines étapes.",
                    to_agent=leader,
                    project_id=project_id,
                )
                break
            elif phase.gate == "no_veto" and not result.success:
                await _rte_facilitate(
                    session_id,
                    f"La phase **{phase.name}** a eu des retours mais on continue. "
                    f"Le feedback a été adressé dans la boucle. On passe à la suite.",
                    to_agent=phase_leader,
                    project_id=project_id,
                )

            # Accumulate context from this phase's output
            last_msgs = store.get_messages(session_id, limit=5)
            for m in reversed(last_msgs):
                if m.from_agent not in ("system", "user", _RTE_AGENT_ID):
                    summary = (m.content or "")[:300].replace("\n", " ")
                    accumulated_context.append(f"[{phase.name}] {m.from_agent}: {summary}")
                    break

        except Exception as e:
            run.status = "failed"
            run.error = str(e)
            logger.error("Workflow phase %s failed: %s", phase.name, e)
            await _rte_facilitate(
                session_id,
                f"Erreur technique sur la phase **{phase.name}**: {e}\n"
                f"Annonce l'erreur à l'équipe et propose un plan de recovery.",
                to_agent=leader,
                project_id=project_id,
            )
            break

    if run.status == "running":
        run.status = "completed"

    # RTE closes the workflow
    status_emoji = {"completed": "[OK]", "failed": "[FAIL]", "gated": "[BLOCKED]"}.get(run.status, "[DONE]")
    phase_summary = "\n".join(
        f"- {r['phase']}: {'[OK]' if r['success'] else '[FAIL]'}" for r in run.phase_results
    )
    await _rte_facilitate(
        session_id,
        f"{status_emoji} Le workflow **{workflow.name}** est terminé ({run.status}).\n"
        f"Bilan des phases:\n{phase_summary}\n\n"
        f"Fais la synthèse finale pour l'équipe. Mets en avant les livrables et les prochaines étapes.",
        to_agent=leader,
        project_id=project_id,
    )

    return run
