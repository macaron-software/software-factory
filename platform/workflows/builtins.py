"""Builtin workflow definitions for the Software Factory platform."""

from __future__ import annotations

from .store import WorkflowDef, WorkflowPhase


def get_builtin_workflows() -> list[WorkflowDef]:
    """Return all builtin WorkflowDef instances."""
    builtins = [
        WorkflowDef(
            id="sf-pipeline",
            name="Software Factory Pipeline",
            description="Full SF cycle: Brain analysis → TDD development → Adversarial review → Deploy.",
            icon="rocket",
            is_builtin=True,
            phases=[
                WorkflowPhase(
                    id="p1",
                    pattern_id="hierarchical",
                    name="Analysis",
                    description="Brain decomposes the task into subtasks",
                    gate="always",
                    config={"agents": ["brain", "lead_dev", "architecte"]},
                ),
                WorkflowPhase(
                    id="p2",
                    pattern_id="hierarchical",
                    name="TDD Development",
                    description="Lead Dev delegates implementation to devs who write actual code files",
                    gate="always",
                    config={"agents": ["lead_dev", "dev", "dev_backend", "testeur"]},
                ),
                WorkflowPhase(
                    id="p3",
                    pattern_id="adversarial-cascade",
                    name="Quality Gate",
                    description="4-layer adversarial review cascade",
                    gate="no_veto",
                    config={"agents": ["qa_lead", "securite", "arch-critic", "devops"]},
                ),
                WorkflowPhase(
                    id="p4",
                    pattern_id="sequential",
                    name="Deploy & Verify",
                    description="Docker build, deploy, health check, screenshots of user journeys",
                    gate="always",
                    config={"agents": ["devops", "testeur", "qa_lead"]},
                ),
            ],
        ),
        WorkflowDef(
            id="review-cycle",
            name="Code Review Cycle",
            description="Sequential review: code → security → architecture.",
            icon="eye",
            is_builtin=True,
            phases=[
                WorkflowPhase(
                    id="p1",
                    pattern_id="sequential",
                    name="Multi-Layer Review",
                    description="Analyst → Developer → Reviewer pipeline",
                    gate="always",
                    config={"agents": ["lead_dev", "securite", "arch-critic"]},
                ),
                WorkflowPhase(
                    id="p2",
                    pattern_id="adversarial-pair",
                    name="Fix Issues",
                    description="Fix any issues found in review",
                    gate="no_veto",
                    config={"agents": ["dev", "qa_lead"]},
                ),
            ],
        ),
        WorkflowDef(
            id="debate-decide",
            name="Debate & Decide",
            description="Agents debate, then a judge decides, then implement the decision.",
            icon="briefcase",
            is_builtin=True,
            phases=[
                WorkflowPhase(
                    id="p1",
                    pattern_id="debate",
                    name="Debate",
                    description="Agents argue for/against different approaches",
                    gate="always",
                    config={
                        "agents": ["architecte", "lead_dev", "dev_backend", "securite"]
                    },
                ),
                WorkflowPhase(
                    id="p2",
                    pattern_id="hierarchical",
                    name="Implementation",
                    description="Execute the decided approach",
                    gate="always",
                    config={"agents": ["lead_dev", "dev", "testeur"]},
                ),
            ],
        ),
        WorkflowDef(
            id="migration-sharelook",
            name="Migration Sharelook Angular 16→17",
            description="Migration ISO 100% Angular 16.2→17.3 — SAFe PI: Planning→Sprint→Review→Retro→Release.",
            icon="rocket",
            is_builtin=True,
            phases=[
                # ── PI Planning: Vision, scope, risques ──
                WorkflowPhase(
                    id="pi-planning",
                    pattern_id="sequential",
                    name="PI Planning",
                    description="CP présente vision migration. Lead+QA+Sécu définissent scope, risques, acceptance criteria.",
                    gate="always",
                    config={
                        "agents": ["chef_projet", "lead_dev", "qa_lead", "securite"]
                    },
                ),
                # ── Sprint Planning: Lead décompose en stories pour les devs ──
                WorkflowPhase(
                    id="sprint-planning",
                    pattern_id="hierarchical",
                    name="Sprint Planning",
                    description="Lead décompose migration en user stories. Assigne aux devs selon expertise (pilot vs main app).",
                    gate="always",
                    config={"agents": ["lead_dev", "dev_frontend", "dev_fullstack"]},
                ),
                # ── Dev Sprint: Devs codent, Lead review complétude ──
                WorkflowPhase(
                    id="dev-sprint",
                    pattern_id="hierarchical",
                    name="Dev Sprint",
                    description="Devs exécutent migration en //. Lead vérifie complétude. Inner loop jusqu'à COMPLETE.",
                    gate="always",
                    config={
                        "agents": [
                            "lead_dev",
                            "dev_frontend",
                            "dev_fullstack",
                            "qa_lead",
                        ]
                    },
                ),
                # ── Sprint Review: QA valide, Sécu audite, CP GO/NOGO ──
                WorkflowPhase(
                    id="sprint-review",
                    pattern_id="sequential",
                    name="Sprint Review",
                    description="Lead présente travail. QA valide ISO 100% (golden files). Sécu audit CVE. CP décide GO/NOGO.",
                    gate="no_veto",
                    config={
                        "agents": ["lead_dev", "qa_lead", "securite", "chef_projet"]
                    },
                ),
                # ── Retrospective: Tous débattent améliorations ──
                WorkflowPhase(
                    id="retrospective",
                    pattern_id="network",
                    name="Retrospective",
                    description="Équipe entière débat: ce qui a marché, ce qui a échoué, améliorations process.",
                    gate="always",
                    config={
                        "agents": [
                            "lead_dev",
                            "dev_frontend",
                            "dev_fullstack",
                            "qa_lead",
                            "chef_projet",
                        ]
                    },
                ),
                # ── Release: DevOps deploy, QA smoke, CP valide ──
                WorkflowPhase(
                    id="release",
                    pattern_id="sequential",
                    name="Release",
                    description="DevOps deploy staging→canary. QA smoke test. CP valide mise en prod.",
                    gate="all_approved",
                    config={"agents": ["devops", "qa_lead", "chef_projet"]},
                ),
            ],
            config={
                "graph": {
                    "pattern": "hierarchical",
                    "nodes": [
                        {
                            "id": "n1",
                            "agent_id": "chef_projet",
                            "x": 400,
                            "y": 30,
                            "label": "Chef de Projet",
                        },
                        {
                            "id": "n2",
                            "agent_id": "lead_dev",
                            "x": 250,
                            "y": 170,
                            "label": "Lead Dev Angular",
                        },
                        {
                            "id": "n3",
                            "agent_id": "securite",
                            "x": 550,
                            "y": 170,
                            "label": "Security Audit",
                        },
                        {
                            "id": "n4",
                            "agent_id": "qa_lead",
                            "x": 400,
                            "y": 170,
                            "label": "QA Lead (ISO 100%)",
                        },
                        {
                            "id": "n5",
                            "agent_id": "dev_frontend",
                            "x": 150,
                            "y": 340,
                            "label": "Dev Frontend",
                        },
                        {
                            "id": "n6",
                            "agent_id": "dev_fullstack",
                            "x": 350,
                            "y": 340,
                            "label": "Dev Fullstack",
                        },
                        {
                            "id": "n7",
                            "agent_id": "devops",
                            "x": 550,
                            "y": 340,
                            "label": "DevOps",
                        },
                    ],
                    "edges": [
                        # PI Planning: CP briefs everyone
                        {
                            "from": "n1",
                            "to": "n2",
                            "label": "brief",
                            "type": "sequential",
                            "color": "#3b82f6",
                        },
                        {
                            "from": "n1",
                            "to": "n4",
                            "label": "criteria",
                            "type": "sequential",
                            "color": "#3b82f6",
                        },
                        {
                            "from": "n1",
                            "to": "n3",
                            "label": "audit",
                            "type": "sequential",
                            "color": "#3b82f6",
                        },
                        # Sprint: Lead delegates to devs
                        {
                            "from": "n2",
                            "to": "n5",
                            "label": "stories",
                            "type": "parallel",
                            "color": "#f59e0b",
                        },
                        {
                            "from": "n2",
                            "to": "n6",
                            "label": "stories",
                            "type": "parallel",
                            "color": "#f59e0b",
                        },
                        # Review: Devs report to QA
                        {
                            "from": "n5",
                            "to": "n4",
                            "label": "validate",
                            "type": "sequential",
                            "color": "#10b981",
                        },
                        {
                            "from": "n6",
                            "to": "n4",
                            "label": "validate",
                            "type": "sequential",
                            "color": "#10b981",
                        },
                        # Feedback: QA reports to CP
                        {
                            "from": "n4",
                            "to": "n1",
                            "label": "GO/NOGO",
                            "type": "report",
                            "color": "#ef4444",
                        },
                        {
                            "from": "n3",
                            "to": "n1",
                            "label": "report",
                            "type": "report",
                            "color": "#ef4444",
                        },
                        # Release: CP triggers deploy
                        {
                            "from": "n1",
                            "to": "n7",
                            "label": "deploy",
                            "type": "sequential",
                            "color": "#8b5cf6",
                        },
                    ],
                },
                "project_ref": "sharelook",
                "migration": {
                    "framework": "angular",
                    "from": "16.2.12",
                    "to": "17.3.0",
                },
                "agents_permissions": {
                    "qa_lead": {"can_veto": True, "veto_level": "ABSOLUTE"},
                    "securite": {"can_veto": True, "veto_level": "ABSOLUTE"},
                    "lead_dev": {
                        "can_veto": True,
                        "veto_level": "STRONG",
                        "can_delegate": True,
                    },
                    "chef_projet": {"can_delegate": True},
                },
            },
        ),
        # ── Feature Request: Demande métier → MVP ──
        WorkflowDef(
            id="feature-request",
            name="Demande Metier → MVP",
            description="Parcours complet: un metier exprime un besoin → challenge strategique → impact analysis → constitution projet → developpement → mise en prod.",
            icon="inbox",
            is_builtin=True,
            phases=[
                WorkflowPhase(
                    id="intake",
                    pattern_id="network",
                    name="Intake - Comite Strategique",
                    description="Le metier presente son besoin. Le comite strategique (DSI, CPO, CTO, Business Owner) debat de la valeur, la faisabilite, l'alignement strategique. Chaque membre donne son avis argumente. Le DSI rend la decision GO/NOGO.",
                    gate="all_approved",
                    config={
                        "agents": [
                            "metier",
                            "business_owner",
                            "strat-cpo",
                            "strat-cto",
                            "dsi",
                        ]
                    },
                ),
                WorkflowPhase(
                    id="impact-analysis",
                    pattern_id="parallel",
                    name="Analyse d'Impact",
                    description="Chaque expert analyse l'impact dans son domaine: architecture SI, securite/RGPD, conformite reglementaire, infrastructure cloud, integration inter-systemes, capacite portfolio. Le CPO agrege les analyses en impact map consolidee.",
                    gate="always",
                    config={
                        "agents": [
                            "enterprise_architect",
                            "securite",
                            "compliance_officer",
                            "cloud_architect",
                            "solution_architect",
                            "strat-portfolio",
                        ]
                    },
                ),
                WorkflowPhase(
                    id="project-setup",
                    pattern_id="sequential",
                    name="Constitution du Projet",
                    description="Le Dir. Programme alloue les ressources. Le Product Manager decompose en features et user stories. Le Chef de Projet planifie les sprints et les dependances. Le Scrum Master configure les ceremonies.",
                    gate="always",
                    config={
                        "agents": [
                            "strat-dirprog",
                            "product_manager",
                            "chef_projet",
                            "scrum_master",
                        ]
                    },
                ),
                WorkflowPhase(
                    id="product-design",
                    pattern_id="hierarchical",
                    name="Product Design",
                    description="Le Product Manager pilote: decompose la vision en features avec criteres d'acceptation. L'UX Designer cree les maquettes et parcours utilisateur. Le metier valide la conformite au besoin initial. Le Lead Dev evalue la faisabilite technique de chaque feature.",
                    gate="always",
                    config={
                        "agents": [
                            "product_manager",
                            "ux_designer",
                            "metier",
                            "lead_dev",
                        ]
                    },
                ),
                WorkflowPhase(
                    id="dev-sprint",
                    pattern_id="hierarchical",
                    name="Sprint de Developpement",
                    description="Le Lead Dev distribue les stories aux devs. Les devs codent en TDD. Le QA valide en continu. Le Lead fait la code review. Adversarial review avant chaque merge.",
                    gate="always",
                    config={
                        "agents": ["lead_dev", "dev_frontend", "dev_backend", "qa_lead"]
                    },
                ),
                WorkflowPhase(
                    id="qa-validation",
                    pattern_id="loop",
                    name="Validation QA & Tests E2E",
                    description="Le Test Manager definit la campagne. Le QA Lead execute les tests fonctionnels et E2E avec Playwright (navigation, screenshots, assertions). L'API Tester valide les endpoints. Si KO, retour au dev. Max 3 iterations.",
                    gate="qa_approved",
                    config={
                        "agents": [
                            "test_manager",
                            "qa_lead",
                            "test_auto",
                            "api_tester",
                        ],
                        "max_iterations": 3,
                    },
                ),
                WorkflowPhase(
                    id="release",
                    pattern_id="sequential",
                    name="Mise en Production",
                    description="Pipeline sequentiel: DevOps deploie staging. QA lance les tests E2E et smoke. Securite fait l'audit OWASP. Performance lance le load test. SRE valide le monitoring. Chef de Projet prononce le GO/NOGO. Business Owner valide la conformite metier.",
                    gate="all_approved",
                    config={
                        "agents": [
                            "devops",
                            "qa_lead",
                            "securite",
                            "performance_engineer",
                            "sre",
                            "chef_projet",
                            "business_owner",
                        ]
                    },
                ),
            ],
            config={
                "graph": {
                    "pattern": "hierarchical",
                    "nodes": [
                        {
                            "id": "n1",
                            "agent_id": "dsi",
                            "x": 400,
                            "y": 10,
                            "label": "DSI",
                        },
                        {
                            "id": "n2",
                            "agent_id": "strat-cpo",
                            "x": 250,
                            "y": 10,
                            "label": "Julie - CPO",
                        },
                        {
                            "id": "n3",
                            "agent_id": "strat-cto",
                            "x": 550,
                            "y": 10,
                            "label": "Karim - CTO",
                        },
                        {
                            "id": "n4",
                            "agent_id": "metier",
                            "x": 100,
                            "y": 10,
                            "label": "Metier / PO",
                        },
                        {
                            "id": "n5",
                            "agent_id": "business_owner",
                            "x": 700,
                            "y": 10,
                            "label": "Business Owner",
                        },
                        {
                            "id": "n6",
                            "agent_id": "enterprise_architect",
                            "x": 100,
                            "y": 130,
                            "label": "Enterprise Archi",
                        },
                        {
                            "id": "n7",
                            "agent_id": "securite",
                            "x": 280,
                            "y": 130,
                            "label": "Securite",
                        },
                        {
                            "id": "n8",
                            "agent_id": "compliance_officer",
                            "x": 450,
                            "y": 130,
                            "label": "Compliance",
                        },
                        {
                            "id": "n9",
                            "agent_id": "cloud_architect",
                            "x": 620,
                            "y": 130,
                            "label": "Cloud Archi",
                        },
                        {
                            "id": "n10",
                            "agent_id": "strat-portfolio",
                            "x": 750,
                            "y": 130,
                            "label": "Sofia - Portfolio",
                        },
                        {
                            "id": "n11",
                            "agent_id": "strat-dirprog",
                            "x": 100,
                            "y": 250,
                            "label": "Thomas - Dir Prog",
                        },
                        {
                            "id": "n12",
                            "agent_id": "product_manager",
                            "x": 300,
                            "y": 250,
                            "label": "Product Manager",
                        },
                        {
                            "id": "n13",
                            "agent_id": "chef_projet",
                            "x": 500,
                            "y": 250,
                            "label": "Chef de Projet",
                        },
                        {
                            "id": "n14",
                            "agent_id": "scrum_master",
                            "x": 680,
                            "y": 250,
                            "label": "Scrum Master",
                        },
                        {
                            "id": "n15",
                            "agent_id": "ux_designer",
                            "x": 150,
                            "y": 370,
                            "label": "UX Designer",
                        },
                        {
                            "id": "n16",
                            "agent_id": "lead_dev",
                            "x": 350,
                            "y": 370,
                            "label": "Lead Dev",
                        },
                        {
                            "id": "n17",
                            "agent_id": "dev_frontend",
                            "x": 200,
                            "y": 480,
                            "label": "Dev Frontend",
                        },
                        {
                            "id": "n18",
                            "agent_id": "dev_backend",
                            "x": 400,
                            "y": 480,
                            "label": "Dev Backend",
                        },
                        {
                            "id": "n19",
                            "agent_id": "qa_lead",
                            "x": 550,
                            "y": 480,
                            "label": "QA Lead",
                        },
                        {
                            "id": "n20",
                            "agent_id": "devops",
                            "x": 300,
                            "y": 580,
                            "label": "DevOps",
                        },
                        {
                            "id": "n21",
                            "agent_id": "sre",
                            "x": 500,
                            "y": 580,
                            "label": "SRE",
                        },
                        {
                            "id": "n22",
                            "agent_id": "performance_engineer",
                            "x": 680,
                            "y": 480,
                            "label": "Perf Engineer",
                        },
                        {
                            "id": "n23",
                            "agent_id": "solution_architect",
                            "x": 550,
                            "y": 130,
                            "label": "Solution Archi",
                        },
                    ],
                    "edges": [
                        # Intake: metier → comite strategique (debate)
                        {
                            "from": "n4",
                            "to": "n2",
                            "label": "besoin",
                            "color": "#3b82f6",
                        },
                        {
                            "from": "n4",
                            "to": "n3",
                            "label": "besoin",
                            "color": "#3b82f6",
                        },
                        {
                            "from": "n4",
                            "to": "n1",
                            "label": "besoin",
                            "color": "#3b82f6",
                        },
                        {
                            "from": "n2",
                            "to": "n1",
                            "label": "avis CPO",
                            "color": "#d946ef",
                        },
                        {
                            "from": "n3",
                            "to": "n1",
                            "label": "avis CTO",
                            "color": "#d946ef",
                        },
                        {
                            "from": "n5",
                            "to": "n1",
                            "label": "avis BO",
                            "color": "#d946ef",
                        },
                        # Impact: DSI commande l'analyse
                        {
                            "from": "n1",
                            "to": "n6",
                            "label": "analyser",
                            "color": "#f59e0b",
                        },
                        {
                            "from": "n1",
                            "to": "n7",
                            "label": "analyser",
                            "color": "#f59e0b",
                        },
                        {
                            "from": "n1",
                            "to": "n8",
                            "label": "analyser",
                            "color": "#f59e0b",
                        },
                        {
                            "from": "n1",
                            "to": "n9",
                            "label": "analyser",
                            "color": "#f59e0b",
                        },
                        {
                            "from": "n1",
                            "to": "n23",
                            "label": "analyser",
                            "color": "#f59e0b",
                        },
                        {
                            "from": "n6",
                            "to": "n2",
                            "label": "impact SI",
                            "color": "#10b981",
                        },
                        {
                            "from": "n7",
                            "to": "n2",
                            "label": "impact secu",
                            "color": "#10b981",
                        },
                        {
                            "from": "n8",
                            "to": "n2",
                            "label": "impact regl.",
                            "color": "#10b981",
                        },
                        {
                            "from": "n9",
                            "to": "n2",
                            "label": "impact cloud",
                            "color": "#10b981",
                        },
                        {
                            "from": "n23",
                            "to": "n2",
                            "label": "impact integ.",
                            "color": "#10b981",
                        },
                        {
                            "from": "n10",
                            "to": "n2",
                            "label": "capacite",
                            "color": "#10b981",
                        },
                        # Constitution: DirProg → PM → CP → SM
                        {
                            "from": "n11",
                            "to": "n12",
                            "label": "staffing",
                            "color": "#8b5cf6",
                        },
                        {
                            "from": "n12",
                            "to": "n13",
                            "label": "backlog",
                            "color": "#8b5cf6",
                        },
                        {
                            "from": "n13",
                            "to": "n14",
                            "label": "planning",
                            "color": "#8b5cf6",
                        },
                        # Product Design: PM → UX + Lead
                        {
                            "from": "n12",
                            "to": "n15",
                            "label": "maquettes",
                            "color": "#d946ef",
                        },
                        {
                            "from": "n12",
                            "to": "n16",
                            "label": "features",
                            "color": "#d946ef",
                        },
                        {
                            "from": "n15",
                            "to": "n4",
                            "label": "valider UX",
                            "color": "#06b6d4",
                        },
                        # Sprint: Lead → Devs → QA
                        {
                            "from": "n16",
                            "to": "n17",
                            "label": "stories",
                            "color": "#f59e0b",
                        },
                        {
                            "from": "n16",
                            "to": "n18",
                            "label": "stories",
                            "color": "#f59e0b",
                        },
                        {
                            "from": "n17",
                            "to": "n19",
                            "label": "review",
                            "color": "#10b981",
                        },
                        {
                            "from": "n18",
                            "to": "n19",
                            "label": "review",
                            "color": "#10b981",
                        },
                        # Release: QA + Secu → CP → DevOps → SRE
                        {
                            "from": "n19",
                            "to": "n13",
                            "label": "GO/NOGO",
                            "color": "#ef4444",
                        },
                        {
                            "from": "n13",
                            "to": "n20",
                            "label": "deploy",
                            "color": "#8b5cf6",
                        },
                        {
                            "from": "n20",
                            "to": "n21",
                            "label": "monitoring",
                            "color": "#8b5cf6",
                        },
                        {
                            "from": "n22",
                            "to": "n13",
                            "label": "perf OK",
                            "color": "#10b981",
                        },
                    ],
                },
                "agents_permissions": {
                    "dsi": {
                        "can_veto": True,
                        "veto_level": "ABSOLUTE",
                        "can_delegate": True,
                    },
                    "strat-cpo": {
                        "can_veto": True,
                        "veto_level": "STRONG",
                        "can_approve": True,
                    },
                    "strat-cto": {"can_veto": True, "veto_level": "STRONG"},
                    "qa_lead": {"can_veto": True, "veto_level": "ABSOLUTE"},
                    "securite": {"can_veto": True, "veto_level": "ABSOLUTE"},
                    "business_owner": {
                        "can_veto": True,
                        "veto_level": "STRONG",
                        "can_approve": True,
                    },
                    "chef_projet": {"can_delegate": True, "can_approve": True},
                },
            },
        ),
        # ── Tech Debt Reduction: Audit → Prioritize → Fix → Validate ──
        WorkflowDef(
            id="tech-debt-reduction",
            name="Reduction de la Dette Technique",
            description="Audit cross-projet de la dette technique → priorisation WSJF → sprint de correction → validation metriques.",
            icon="tool",
            is_builtin=True,
            phases=[
                WorkflowPhase(
                    id="debt-scan",
                    pattern_id="parallel",
                    name="Audit de Dette Technique",
                    description="Scan parallele par domaine: le CTO lance l'audit. L'Enterprise Archi analyse le couplage et les dependances. Le Lead Dev scanne la complexite et la duplication. La Securite cherche les CVE et deps obsoletes. Le SRE analyse les incidents recurrents. Le Perf Engineer cherche les bottlenecks. Le CTO agrege les resultats en inventaire score.",
                    gate="always",
                    config={
                        "agents": [
                            "strat-cto",
                            "enterprise_architect",
                            "lead_dev",
                            "securite",
                            "sre",
                            "performance_engineer",
                        ]
                    },
                ),
                WorkflowPhase(
                    id="prioritization",
                    pattern_id="network",
                    name="Priorisation (Debat WSJF)",
                    description="Le comite debat de la priorisation: CTO defend l'urgence technique. CPO defend la roadmap produit. Portfolio calcule la capacite. Le Lean Portfolio Manager applique le scoring WSJF. Le Product Manager arbitre feature vs dette. Decision finale: budget temps alloue et items priorises.",
                    gate="all_approved",
                    config={
                        "agents": [
                            "strat-cto",
                            "strat-cpo",
                            "strat-portfolio",
                            "lean_portfolio_manager",
                            "product_manager",
                        ]
                    },
                ),
                WorkflowPhase(
                    id="planning",
                    pattern_id="sequential",
                    name="Planning Sprint Dette",
                    description="Le Scrum Master decide: sprint dedie (100% dette) ou integre (20% par sprint). Le Lead Dev decompose les items de dette en tasks techniques. Le Chef de Projet planifie et assigne.",
                    gate="always",
                    config={"agents": ["scrum_master", "lead_dev", "chef_projet"]},
                ),
                WorkflowPhase(
                    id="sprint-debt",
                    pattern_id="hierarchical",
                    name="Sprint de Correction",
                    description="Le Lead Dev distribue les refactors. Les devs corrigent en TDD. Le QA Lead valide la non-regression (coverage ne doit pas baisser, pas de breaking change). Adversarial review renforcee: VETO si regression perf, VETO si API breaking sans deprecation.",
                    gate="all_approved",
                    config={
                        "agents": ["lead_dev", "dev_frontend", "dev_backend", "qa_lead"]
                    },
                ),
                WorkflowPhase(
                    id="validation",
                    pattern_id="sequential",
                    name="Validation (Proof of Reduction)",
                    description="QA presente le rapport de non-regression. Perf Engineer compare les benchmarks avant/apres. Lead Dev montre la reduction de complexite. Le CTO valide que la dette a reellement diminue. Metriques: complexity delta, coverage delta, build time delta, incident rate delta.",
                    gate="all_approved",
                    config={
                        "agents": [
                            "qa_lead",
                            "performance_engineer",
                            "lead_dev",
                            "strat-cto",
                        ]
                    },
                ),
            ],
            config={
                "graph": {
                    "pattern": "hierarchical",
                    "nodes": [
                        {
                            "id": "n1",
                            "agent_id": "strat-cto",
                            "x": 400,
                            "y": 10,
                            "label": "Karim - CTO",
                        },
                        {
                            "id": "n2",
                            "agent_id": "strat-cpo",
                            "x": 200,
                            "y": 10,
                            "label": "Julie - CPO",
                        },
                        {
                            "id": "n3",
                            "agent_id": "strat-portfolio",
                            "x": 600,
                            "y": 10,
                            "label": "Sofia - Portfolio",
                        },
                        {
                            "id": "n4",
                            "agent_id": "enterprise_architect",
                            "x": 100,
                            "y": 140,
                            "label": "Enterprise Archi",
                        },
                        {
                            "id": "n5",
                            "agent_id": "lead_dev",
                            "x": 300,
                            "y": 140,
                            "label": "Lead Dev",
                        },
                        {
                            "id": "n6",
                            "agent_id": "securite",
                            "x": 500,
                            "y": 140,
                            "label": "Securite",
                        },
                        {
                            "id": "n7",
                            "agent_id": "sre",
                            "x": 650,
                            "y": 140,
                            "label": "SRE",
                        },
                        {
                            "id": "n8",
                            "agent_id": "performance_engineer",
                            "x": 150,
                            "y": 250,
                            "label": "Perf Engineer",
                        },
                        {
                            "id": "n9",
                            "agent_id": "lean_portfolio_manager",
                            "x": 700,
                            "y": 10,
                            "label": "Lean Portfolio",
                        },
                        {
                            "id": "n10",
                            "agent_id": "product_manager",
                            "x": 100,
                            "y": 10,
                            "label": "Product Manager",
                        },
                        {
                            "id": "n11",
                            "agent_id": "scrum_master",
                            "x": 200,
                            "y": 250,
                            "label": "Scrum Master",
                        },
                        {
                            "id": "n12",
                            "agent_id": "chef_projet",
                            "x": 400,
                            "y": 250,
                            "label": "Chef de Projet",
                        },
                        {
                            "id": "n13",
                            "agent_id": "dev_frontend",
                            "x": 200,
                            "y": 380,
                            "label": "Dev Frontend",
                        },
                        {
                            "id": "n14",
                            "agent_id": "dev_backend",
                            "x": 400,
                            "y": 380,
                            "label": "Dev Backend",
                        },
                        {
                            "id": "n15",
                            "agent_id": "qa_lead",
                            "x": 600,
                            "y": 380,
                            "label": "QA Lead",
                        },
                    ],
                    "edges": [
                        # Scan: CTO commande l'audit en parallele
                        {
                            "from": "n1",
                            "to": "n4",
                            "label": "audit archi",
                            "color": "#f59e0b",
                        },
                        {
                            "from": "n1",
                            "to": "n5",
                            "label": "audit code",
                            "color": "#f59e0b",
                        },
                        {
                            "from": "n1",
                            "to": "n6",
                            "label": "audit secu",
                            "color": "#f59e0b",
                        },
                        {
                            "from": "n1",
                            "to": "n7",
                            "label": "audit ops",
                            "color": "#f59e0b",
                        },
                        {
                            "from": "n1",
                            "to": "n8",
                            "label": "audit perf",
                            "color": "#f59e0b",
                        },
                        # Reports remontent au CTO
                        {
                            "from": "n4",
                            "to": "n1",
                            "label": "rapport",
                            "color": "#10b981",
                        },
                        {
                            "from": "n5",
                            "to": "n1",
                            "label": "rapport",
                            "color": "#10b981",
                        },
                        {
                            "from": "n6",
                            "to": "n1",
                            "label": "rapport",
                            "color": "#10b981",
                        },
                        {
                            "from": "n7",
                            "to": "n1",
                            "label": "rapport",
                            "color": "#10b981",
                        },
                        {
                            "from": "n8",
                            "to": "n1",
                            "label": "rapport",
                            "color": "#10b981",
                        },
                        # Priorisation: debat entre strategiques
                        {
                            "from": "n1",
                            "to": "n2",
                            "label": "dette vs feature",
                            "color": "#d946ef",
                        },
                        {
                            "from": "n2",
                            "to": "n10",
                            "label": "arbitrage",
                            "color": "#d946ef",
                        },
                        {
                            "from": "n3",
                            "to": "n9",
                            "label": "capacite",
                            "color": "#d946ef",
                        },
                        {"from": "n9", "to": "n1", "label": "WSJF", "color": "#d946ef"},
                        # Planning: SM → Lead → CP
                        {
                            "from": "n11",
                            "to": "n5",
                            "label": "sprint scope",
                            "color": "#8b5cf6",
                        },
                        {
                            "from": "n5",
                            "to": "n12",
                            "label": "tasks",
                            "color": "#8b5cf6",
                        },
                        # Sprint: Lead → Devs → QA
                        {
                            "from": "n5",
                            "to": "n13",
                            "label": "refactors",
                            "color": "#f59e0b",
                        },
                        {
                            "from": "n5",
                            "to": "n14",
                            "label": "refactors",
                            "color": "#f59e0b",
                        },
                        {
                            "from": "n13",
                            "to": "n15",
                            "label": "review",
                            "color": "#10b981",
                        },
                        {
                            "from": "n14",
                            "to": "n15",
                            "label": "review",
                            "color": "#10b981",
                        },
                        # Validation: QA + Perf → CTO
                        {
                            "from": "n15",
                            "to": "n1",
                            "label": "non-regression",
                            "color": "#ef4444",
                        },
                        {
                            "from": "n8",
                            "to": "n1",
                            "label": "benchmark",
                            "color": "#ef4444",
                        },
                    ],
                },
                "agents_permissions": {
                    "strat-cto": {
                        "can_veto": True,
                        "veto_level": "ABSOLUTE",
                        "can_delegate": True,
                    },
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
            icon="target",
            is_builtin=True,
            phases=[
                WorkflowPhase(
                    id="p1-intake",
                    pattern_id="network",
                    name="Instruction du Dossier",
                    description="CPO presente la demande, CTO evalue faisabilite, Portfolio analyse capacite et WSJF.",
                    gate="always",
                    config={
                        "agents": [
                            "strat-cpo",
                            "strat-cto",
                            "strat-portfolio",
                            "lean_portfolio_manager",
                        ]
                    },
                ),
                WorkflowPhase(
                    id="p2-debate",
                    pattern_id="network",
                    name="Debat & Arbitrage",
                    description="Debat ouvert: impact budget, dette technique, alignement roadmap. Dir Programme evalue charge.",
                    gate="always",
                    config={
                        "agents": [
                            "dsi",
                            "strat-cpo",
                            "strat-cto",
                            "strat-portfolio",
                            "strat-dirprog",
                            "lean_portfolio_manager",
                        ]
                    },
                ),
                WorkflowPhase(
                    id="p3-decision",
                    pattern_id="hierarchical",
                    name="Decision GO / NOGO",
                    description="DSI rend la decision finale. GO = lancement projet. NOGO = retour backlog. PIVOT = reformulation.",
                    gate="all_approved",
                    config={"agents": ["dsi", "strat-cpo", "strat-cto"]},
                ),
            ],
            config={
                "graph": {
                    "nodes": [
                        {
                            "id": "n1",
                            "agent_id": "dsi",
                            "x": 400,
                            "y": 20,
                            "label": "DSI",
                        },
                        {
                            "id": "n2",
                            "agent_id": "strat-cpo",
                            "x": 200,
                            "y": 140,
                            "label": "Julie - CPO",
                        },
                        {
                            "id": "n3",
                            "agent_id": "strat-cto",
                            "x": 600,
                            "y": 140,
                            "label": "Karim - CTO",
                        },
                        {
                            "id": "n4",
                            "agent_id": "strat-portfolio",
                            "x": 120,
                            "y": 280,
                            "label": "Sofia - Portfolio",
                        },
                        {
                            "id": "n5",
                            "agent_id": "strat-dirprog",
                            "x": 680,
                            "y": 280,
                            "label": "Thomas - Program Dir",
                        },
                        {
                            "id": "n6",
                            "agent_id": "lean_portfolio_manager",
                            "x": 400,
                            "y": 330,
                            "label": "Lean Portfolio Mgr",
                        },
                    ],
                    "edges": [
                        # DSI ↔ CPO/CTO: strategic arbitration
                        {
                            "from": "n1",
                            "to": "n2",
                            "label": "product vision",
                            "color": "#a855f7",
                        },
                        {
                            "from": "n1",
                            "to": "n3",
                            "label": "tech vision",
                            "color": "#a855f7",
                        },
                        {
                            "from": "n2",
                            "to": "n1",
                            "label": "proposal",
                            "color": "#8b5cf6",
                        },
                        {
                            "from": "n3",
                            "to": "n1",
                            "label": "feasibility",
                            "color": "#8b5cf6",
                        },
                        # CPO ↔ CTO: product vs tech
                        {
                            "from": "n2",
                            "to": "n3",
                            "label": "feature vs debt",
                            "color": "#f59e0b",
                        },
                        {
                            "from": "n3",
                            "to": "n2",
                            "label": "arch constraints",
                            "color": "#f59e0b",
                        },
                        # Portfolio ↔ CPO: WSJF prioritization
                        {
                            "from": "n4",
                            "to": "n2",
                            "label": "WSJF scoring",
                            "color": "#10b981",
                        },
                        {
                            "from": "n2",
                            "to": "n4",
                            "label": "business value",
                            "color": "#10b981",
                        },
                        # Portfolio ↔ Lean: budget & capacity
                        {
                            "from": "n4",
                            "to": "n6",
                            "label": "flow metrics",
                            "color": "#06b6d4",
                        },
                        {
                            "from": "n6",
                            "to": "n4",
                            "label": "lean budget",
                            "color": "#06b6d4",
                        },
                        # CTO ↔ Dir Programme: charge & planning
                        {
                            "from": "n3",
                            "to": "n5",
                            "label": "complexity",
                            "color": "#ef4444",
                        },
                        {
                            "from": "n5",
                            "to": "n3",
                            "label": "team capacity",
                            "color": "#ef4444",
                        },
                        # Dir Programme ↔ Lean: staffing
                        {
                            "from": "n5",
                            "to": "n6",
                            "label": "staffing plan",
                            "color": "#d946ef",
                        },
                        {
                            "from": "n6",
                            "to": "n5",
                            "label": "guardrails",
                            "color": "#d946ef",
                        },
                        # DSI ↔ Lean: strategic alignment
                        {
                            "from": "n1",
                            "to": "n6",
                            "label": "strat themes",
                            "color": "#64748b",
                        },
                        {
                            "from": "n6",
                            "to": "n1",
                            "label": "portfolio health",
                            "color": "#64748b",
                        },
                    ],
                },
                "agents_permissions": {
                    "dsi": {
                        "can_veto": True,
                        "veto_level": "ABSOLUTE",
                        "can_delegate": True,
                        "can_approve": True,
                    },
                    "strat-cpo": {
                        "can_veto": True,
                        "veto_level": "STRONG",
                        "can_delegate": True,
                        "can_approve": True,
                    },
                    "strat-cto": {
                        "can_veto": True,
                        "veto_level": "STRONG",
                        "can_delegate": True,
                        "can_approve": True,
                    },
                    "strat-portfolio": {"can_veto": False, "can_approve": True},
                    "strat-dirprog": {"can_veto": False, "can_approve": True},
                    "lean_portfolio_manager": {
                        "can_veto": True,
                        "veto_level": "ADVISORY",
                        "can_approve": True,
                    },
                },
            },
        ),
    ]
    # ── Ideation → Production Pipeline ──
    builtins.append(
        WorkflowDef(
            id="ideation-to-prod",
            name="Idéation → Production",
            description="Flux complet SAFe: idéation réseau d'agents → structuration PO → comité stratégique GO/NOGO → setup projet (auto-provision TMA+sécu+CI/CD) → architecture → dev sprint → CI/CD → QA → deploy prod → handoff TMA.",
            icon="zap",
            is_builtin=True,
            phases=[
                WorkflowPhase(
                    id="ideation",
                    pattern_id="network",
                    name="Idéation",
                    description="5 agents débattent l'idée: BA analyse le besoin, Archi évalue la faisabilité, UX pense aux utilisateurs, Sécu identifie les risques, PM synthétise.",
                    gate="always",
                    config={
                        "agents": [
                            "business_analyst",
                            "enterprise_architect",
                            "ux_designer",
                            "securite",
                            "product_manager",
                        ]
                    },
                ),
                WorkflowPhase(
                    id="po-structure",
                    pattern_id="sequential",
                    name="Structuration PO",
                    description="Le Product Owner structure: projet, epic, features avec critères d'acceptation, user stories, estimation story points.",
                    gate="always",
                    config={
                        "agents": [
                            "product_manager",
                            "business_analyst",
                            "scrum_master",
                        ]
                    },
                ),
                WorkflowPhase(
                    id="comite-strat",
                    pattern_id="human-in-the-loop",
                    name="Comité Stratégique — GO/NOGO",
                    description="Le comité de direction évalue: alignement stratégique, ROI, risques, capacité. Décision GO/NOGO/PIVOT.",
                    gate="checkpoint",
                    config={
                        "agents": [
                            "strat-cpo",
                            "strat-cto",
                            "lean_portfolio_manager",
                            "strat-portfolio",
                            "dsi",
                        ]
                    },
                ),
                WorkflowPhase(
                    id="project-setup",
                    pattern_id="sequential",
                    name="Constitution Projet",
                    description="Setup automatique: git repo, CI/CD pipeline, VISION.md, agents assignés. Auto-provision TMA + centre sécurité + suivi dette technique.",
                    gate="always",
                    config={
                        "agents": [
                            "scrum_master",
                            "devops",
                            "lead_dev",
                            "product_manager",
                        ]
                    },
                ),
                WorkflowPhase(
                    id="architecture",
                    pattern_id="aggregator",
                    name="Architecture & Design",
                    description="L'architecte conçoit le système, UX les interfaces, Sécu le modèle de menaces, DevOps l'infra. Le Lead Dev valide l'implémentabilité.",
                    gate="always",
                    config={
                        "agents": [
                            "enterprise_architect",
                            "ux_designer",
                            "securite",
                            "devops",
                            "lead_dev",
                        ]
                    },
                ),
                WorkflowPhase(
                    id="dev-sprint",
                    pattern_id="hierarchical",
                    name="Sprint Dev",
                    description="Le Lead Dev distribue les tâches aux développeurs. Chaque dev implémente en TDD (Red→Green→Refactor). Adversarial review sur chaque commit.",
                    gate="always",
                    config={
                        "agents": ["lead_dev", "dev_backend", "dev_frontend", "testeur"]
                    },
                ),
                WorkflowPhase(
                    id="cicd-pipeline",
                    pattern_id="sequential",
                    name="Pipeline CI/CD",
                    description="Le pipeline CI/CD s'exécute: build → lint → tests unitaires → tests d'intégration → analyse sécurité → artifact.",
                    gate="always",
                    config={"agents": ["pipeline_engineer", "devops", "devsecops"]},
                ),
                WorkflowPhase(
                    id="qa-validation",
                    pattern_id="loop",
                    name="Campagne QA",
                    description="Tests fonctionnels, tests de non-régression, tests de charge. Boucle jusqu'à zéro défaut bloquant.",
                    gate="no_veto",
                    config={
                        "agents": ["qa_lead", "test_automation", "performance_engineer"]
                    },
                ),
                WorkflowPhase(
                    id="deploy-prod",
                    pattern_id="human-in-the-loop",
                    name="Déploiement Production — GO/NOGO",
                    description="Revue pré-production: QA sign-off, sécu sign-off, DevOps plan de déploiement. Décision GO/NOGO.",
                    gate="checkpoint",
                    config={
                        "agents": [
                            "devops",
                            "qa_lead",
                            "securite",
                            "sre",
                            "release_train_engineer",
                        ]
                    },
                ),
                WorkflowPhase(
                    id="tma-handoff",
                    pattern_id="sequential",
                    name="Handoff TMA",
                    description="Documentation opérationnelle, formation équipe TMA, activation monitoring, runbook incident. Le projet passe en maintenance.",
                    gate="always",
                    config={
                        "agents": ["responsable_tma", "dev_tma", "sre", "tech_writer"]
                    },
                ),
            ],
            config={
                "graph": {
                    "nodes": [
                        {
                            "id": "n1",
                            "agent_id": "business_analyst",
                            "x": 50,
                            "y": 100,
                            "label": "BA Idéation",
                            "phase": "ideation",
                        },
                        {
                            "id": "n2",
                            "agent_id": "enterprise_architect",
                            "x": 50,
                            "y": 200,
                            "label": "Archi",
                            "phase": "ideation",
                        },
                        {
                            "id": "n3",
                            "agent_id": "product_manager",
                            "x": 200,
                            "y": 150,
                            "label": "PO Structure",
                            "phase": "po-structure",
                        },
                        {
                            "id": "n4",
                            "agent_id": "strat-cpo",
                            "x": 350,
                            "y": 100,
                            "label": "CPO GO/NOGO",
                            "phase": "comite-strat",
                        },
                        {
                            "id": "n5",
                            "agent_id": "strat-cto",
                            "x": 350,
                            "y": 200,
                            "label": "CTO GO/NOGO",
                            "phase": "comite-strat",
                        },
                        {
                            "id": "n6",
                            "agent_id": "devops",
                            "x": 500,
                            "y": 150,
                            "label": "Setup Projet",
                            "phase": "project-setup",
                        },
                        {
                            "id": "n7",
                            "agent_id": "enterprise_architect",
                            "x": 650,
                            "y": 100,
                            "label": "Archi Design",
                            "phase": "architecture",
                        },
                        {
                            "id": "n8",
                            "agent_id": "lead_dev",
                            "x": 800,
                            "y": 150,
                            "label": "Sprint Dev",
                            "phase": "dev-sprint",
                        },
                        {
                            "id": "n9",
                            "agent_id": "pipeline_engineer",
                            "x": 950,
                            "y": 150,
                            "label": "CI/CD",
                            "phase": "cicd-pipeline",
                        },
                        {
                            "id": "n10",
                            "agent_id": "qa_lead",
                            "x": 1100,
                            "y": 150,
                            "label": "QA Loop",
                            "phase": "qa-validation",
                        },
                        {
                            "id": "n11",
                            "agent_id": "sre",
                            "x": 1250,
                            "y": 100,
                            "label": "Deploy Prod",
                            "phase": "deploy-prod",
                        },
                        {
                            "id": "n12",
                            "agent_id": "responsable_tma",
                            "x": 1400,
                            "y": 150,
                            "label": "TMA Handoff",
                            "phase": "tma-handoff",
                        },
                    ],
                    "edges": [
                        {
                            "from": "n1",
                            "to": "n3",
                            "label": "brief",
                            "color": "#7c3aed",
                        },
                        {
                            "from": "n2",
                            "to": "n3",
                            "label": "feasibility",
                            "color": "#58a6ff",
                        },
                        {"from": "n3", "to": "n4", "label": "epic", "color": "#d29922"},
                        {
                            "from": "n3",
                            "to": "n5",
                            "label": "tech spec",
                            "color": "#d29922",
                        },
                        {"from": "n4", "to": "n6", "label": "GO", "color": "#3fb950"},
                        {"from": "n5", "to": "n6", "label": "GO", "color": "#3fb950"},
                        {
                            "from": "n6",
                            "to": "n7",
                            "label": "project",
                            "color": "#58a6ff",
                        },
                        {
                            "from": "n7",
                            "to": "n8",
                            "label": "design",
                            "color": "#7c3aed",
                        },
                        {"from": "n8", "to": "n9", "label": "code", "color": "#3fb950"},
                        {
                            "from": "n9",
                            "to": "n10",
                            "label": "build ok",
                            "color": "#3fb950",
                        },
                        {
                            "from": "n10",
                            "to": "n11",
                            "label": "qa ok",
                            "color": "#3fb950",
                        },
                        {
                            "from": "n11",
                            "to": "n12",
                            "label": "deployed",
                            "color": "#f97316",
                        },
                    ],
                },
                "agents_permissions": {
                    "strat-cpo": {"can_veto": True, "veto_level": "ABSOLUTE"},
                    "strat-cto": {"can_veto": True, "veto_level": "STRONG"},
                    "enterprise_architect": {"can_veto": True, "veto_level": "STRONG"},
                    "lead_dev": {
                        "can_delegate": True,
                        "can_veto": True,
                        "veto_level": "STRONG",
                    },
                    "qa_lead": {"can_veto": True, "veto_level": "ABSOLUTE"},
                    "securite": {"can_veto": True, "veto_level": "STRONG"},
                    "devops": {"can_approve": True},
                    "sre": {
                        "can_veto": True,
                        "veto_level": "STRONG",
                        "can_approve": True,
                    },
                },
            },
        ),
    )
    builtins.append(
        WorkflowDef(
            id="dsi-sharelook-2",
            name="DSI Sharelook 2.0 — Phases",
            description="Workflow phasé: Cadrage → Architecture → Sprint → Delivery",
            icon="briefcase",
            is_builtin=True,
            phases=[
                WorkflowPhase(
                    id="p1-cadrage",
                    pattern_id="hierarchical",
                    name="Cadrage Stratégique",
                    description="Le DSI cadre la vision avec CPO et CTO. L'architecte analyse la faisabilité. Décision GO/NOGO.",
                    gate="all_approved",
                    config={
                        "agents": [
                            "dsi",
                            "strat-cpo",
                            "strat-cto",
                            "architecte",
                            "strat-portfolio",
                        ],
                        "leader": "dsi",
                        "deliverables": [
                            "Vision validée",
                            "Budget estimé",
                            "Risques identifiés",
                            "Décision GO/NOGO",
                        ],
                    },
                ),
                WorkflowPhase(
                    id="p2-architecture",
                    pattern_id="network",
                    name="Design & Architecture",
                    description="L'architecte, le lead dev, la sécu et le DevOps conçoivent la solution. Débat technique sur les choix.",
                    gate="no_veto",
                    config={
                        "agents": [
                            "architecte",
                            "lead_dev",
                            "securite",
                            "devops",
                            "strat-cto",
                        ],
                        "leader": "architecte",
                        "deliverables": [
                            "Architecture validée",
                            "Stack technique",
                            "Plan sécurité",
                            "Infra cible",
                        ],
                    },
                ),
                WorkflowPhase(
                    id="p3-sprint-setup",
                    pattern_id="sequential",
                    name="Sprint Planning",
                    description="Le PO structure le backlog, le Scrum Master planifie les sprints, l'équipe estime.",
                    gate="all_approved",
                    config={
                        "agents": [
                            "product",
                            "scrum_master",
                            "lead_dev",
                            "dev_frontend",
                            "dev_backend",
                            "qa_lead",
                        ],
                        "leader": "product",
                        "deliverables": [
                            "Backlog priorisé",
                            "Sprint 1 planifié",
                            "Équipe assignée",
                            "Definition of Done",
                        ],
                    },
                ),
                WorkflowPhase(
                    id="p4-delivery",
                    pattern_id="hierarchical",
                    name="Delivery & QA",
                    description="L'équipe développe, les QA testent, le DevOps déploie. Review adversariale avant merge.",
                    gate="no_veto",
                    config={
                        "agents": [
                            "lead_dev",
                            "dev_frontend",
                            "dev_backend",
                            "testeur",
                            "qa_lead",
                            "devops",
                            "securite",
                        ],
                        "leader": "lead_dev",
                        "deliverables": [
                            "Code livré",
                            "Tests passés",
                            "Déployé staging",
                            "Review sécu OK",
                        ],
                    },
                ),
            ],
            config={
                "project_id": "sharelook-2",
                "graph": {
                    "pattern": "hierarchical",
                    "nodes": [
                        {
                            "id": "n1",
                            "agent_id": "dsi",
                            "x": 400,
                            "y": 30,
                            "label": "DSI",
                            "phase": "p1-cadrage",
                        },
                        {
                            "id": "n2",
                            "agent_id": "strat-cpo",
                            "x": 200,
                            "y": 120,
                            "label": "Julie - CPO",
                            "phase": "p1-cadrage",
                        },
                        {
                            "id": "n3",
                            "agent_id": "strat-cto",
                            "x": 600,
                            "y": 120,
                            "label": "Karim - CTO",
                            "phase": "p1-cadrage",
                        },
                        {
                            "id": "n4",
                            "agent_id": "architecte",
                            "x": 100,
                            "y": 210,
                            "label": "Pierre - Archi",
                            "phase": "p1-cadrage,p2-architecture",
                        },
                        {
                            "id": "n5",
                            "agent_id": "strat-portfolio",
                            "x": 700,
                            "y": 120,
                            "label": "Sofia - Portfolio",
                            "phase": "p1-cadrage",
                        },
                        {
                            "id": "n6",
                            "agent_id": "lead_dev",
                            "x": 300,
                            "y": 300,
                            "label": "Thomas - Lead Dev",
                            "phase": "p2-architecture,p4-delivery",
                        },
                        {
                            "id": "n7",
                            "agent_id": "securite",
                            "x": 500,
                            "y": 300,
                            "label": "Nadia - Sécu",
                            "phase": "p2-architecture,p4-delivery",
                        },
                        {
                            "id": "n8",
                            "agent_id": "devops",
                            "x": 700,
                            "y": 300,
                            "label": "Karim D. - DevOps",
                            "phase": "p2-architecture,p4-delivery",
                        },
                        {
                            "id": "n9",
                            "agent_id": "product",
                            "x": 150,
                            "y": 390,
                            "label": "Laura - PO",
                            "phase": "p3-sprint-setup",
                        },
                        {
                            "id": "n10",
                            "agent_id": "scrum_master",
                            "x": 350,
                            "y": 390,
                            "label": "Inès - SM",
                            "phase": "p3-sprint-setup",
                        },
                        {
                            "id": "n11",
                            "agent_id": "dev_frontend",
                            "x": 200,
                            "y": 480,
                            "label": "Lucas - Front",
                            "phase": "p4-delivery",
                        },
                        {
                            "id": "n12",
                            "agent_id": "dev_backend",
                            "x": 400,
                            "y": 480,
                            "label": "Julien - Back",
                            "phase": "p4-delivery",
                        },
                        {
                            "id": "n13",
                            "agent_id": "qa_lead",
                            "x": 550,
                            "y": 390,
                            "label": "Claire - QA Lead",
                            "phase": "p3-sprint-setup,p4-delivery",
                        },
                        {
                            "id": "n14",
                            "agent_id": "testeur",
                            "x": 600,
                            "y": 480,
                            "label": "Rachid - Testeur",
                            "phase": "p4-delivery",
                        },
                    ],
                    "edges": [
                        {
                            "from": "n1",
                            "to": "n2",
                            "label": "vision produit",
                            "color": "#a855f7",
                        },
                        {
                            "from": "n1",
                            "to": "n3",
                            "label": "vision tech",
                            "color": "#a855f7",
                        },
                        {
                            "from": "n2",
                            "to": "n1",
                            "label": "proposition",
                            "color": "#8b5cf6",
                        },
                        {
                            "from": "n3",
                            "to": "n1",
                            "label": "faisabilité",
                            "color": "#8b5cf6",
                        },
                        {
                            "from": "n1",
                            "to": "n4",
                            "label": "analyse archi",
                            "color": "#a855f7",
                        },
                        {
                            "from": "n4",
                            "to": "n1",
                            "label": "recommandation",
                            "color": "#8b5cf6",
                        },
                        {
                            "from": "n5",
                            "to": "n1",
                            "label": "budget/portfolio",
                            "color": "#f59e0b",
                        },
                        {
                            "from": "n1",
                            "to": "n6",
                            "label": "GO projet",
                            "color": "#34d399",
                        },
                        {
                            "from": "n3",
                            "to": "n4",
                            "label": "contraintes tech",
                            "color": "#f59e0b",
                        },
                        {
                            "from": "n4",
                            "to": "n6",
                            "label": "design archi",
                            "color": "#3b82f6",
                        },
                        {
                            "from": "n4",
                            "to": "n7",
                            "label": "review sécu",
                            "color": "#3b82f6",
                        },
                        {
                            "from": "n4",
                            "to": "n8",
                            "label": "infra cible",
                            "color": "#3b82f6",
                        },
                        {
                            "from": "n6",
                            "to": "n4",
                            "label": "feedback dev",
                            "color": "#8b5cf6",
                        },
                        {
                            "from": "n7",
                            "to": "n4",
                            "label": "exigences sécu",
                            "color": "#ef4444",
                        },
                        {
                            "from": "n8",
                            "to": "n4",
                            "label": "contraintes infra",
                            "color": "#f59e0b",
                        },
                        {
                            "from": "n6",
                            "to": "n9",
                            "label": "specs tech",
                            "color": "#34d399",
                        },
                        {
                            "from": "n4",
                            "to": "n9",
                            "label": "architecture doc",
                            "color": "#34d399",
                        },
                        {
                            "from": "n9",
                            "to": "n10",
                            "label": "backlog",
                            "color": "#a855f7",
                        },
                        {
                            "from": "n10",
                            "to": "n6",
                            "label": "sprint plan",
                            "color": "#3b82f6",
                        },
                        {
                            "from": "n9",
                            "to": "n13",
                            "label": "critères QA",
                            "color": "#3b82f6",
                        },
                        {
                            "from": "n10",
                            "to": "n11",
                            "label": "sprint tasks",
                            "color": "#34d399",
                        },
                        {
                            "from": "n10",
                            "to": "n12",
                            "label": "sprint tasks",
                            "color": "#34d399",
                        },
                        {
                            "from": "n6",
                            "to": "n11",
                            "label": "code review",
                            "color": "#3b82f6",
                        },
                        {
                            "from": "n6",
                            "to": "n12",
                            "label": "code review",
                            "color": "#3b82f6",
                        },
                        {
                            "from": "n11",
                            "to": "n13",
                            "label": "PR ready",
                            "color": "#34d399",
                        },
                        {
                            "from": "n12",
                            "to": "n13",
                            "label": "PR ready",
                            "color": "#34d399",
                        },
                        {
                            "from": "n13",
                            "to": "n14",
                            "label": "test plan",
                            "color": "#3b82f6",
                        },
                        {
                            "from": "n14",
                            "to": "n13",
                            "label": "test results",
                            "color": "#34d399",
                        },
                        {
                            "from": "n13",
                            "to": "n8",
                            "label": "deploy OK",
                            "color": "#34d399",
                        },
                        {
                            "from": "n8",
                            "to": "n1",
                            "label": "prod status",
                            "color": "#34d399",
                        },
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
            icon="tool",
            is_builtin=True,
            phases=[
                WorkflowPhase(
                    id="triage",
                    pattern_id="hierarchical",
                    name="Triage & Priorisation",
                    description="Le Responsable TMA trie les incidents entrants par sévérité (P0-P4). Le QA Lead fournit les logs et steps de reproduction. Le Chef de Projet valide les SLA.",
                    gate="always",
                    config={"agents": ["responsable_tma", "qa_lead", "chef_projet"]},
                ),
                WorkflowPhase(
                    id="diagnostic",
                    pattern_id="parallel",
                    name="Diagnostic Root Cause",
                    description="Le Dev TMA analyse le code et reproduit le bug. Le Lead Dev évalue l'impact sur les modules adjacents. Le DBA vérifie les données et les requêtes.",
                    gate="always",
                    config={"agents": ["dev_tma", "lead_dev", "dba"]},
                ),
                WorkflowPhase(
                    id="fix",
                    pattern_id="hierarchical",
                    name="Correctif TDD",
                    description="Le Dev TMA écrit le test de non-régression (RED), puis le correctif (GREEN), puis refactorise. Le Lead Dev review le code. Le Test Automation ajoute le test E2E si nécessaire.",
                    gate="no_veto",
                    config={"agents": ["dev_tma", "lead_dev", "test_automation"]},
                ),
                WorkflowPhase(
                    id="validate",
                    pattern_id="sequential",
                    name="Validation & Deploy",
                    description="Le Test Manager lance la campagne de non-régression. Le QA valide les tests. Le Pipeline Engineer vérifie le pipeline CI. Le DevOps déploie le hotfix. Le Responsable TMA confirme la résolution.",
                    gate="all_approved",
                    config={
                        "agents": [
                            "test_manager",
                            "qa_lead",
                            "pipeline_engineer",
                            "devops",
                            "responsable_tma",
                        ]
                    },
                ),
            ],
            config={
                "graph": {
                    "pattern": "hierarchical",
                    "nodes": [
                        {
                            "id": "n1",
                            "agent_id": "responsable_tma",
                            "x": 400,
                            "y": 20,
                            "label": "Resp. TMA",
                        },
                        {
                            "id": "n2",
                            "agent_id": "qa_lead",
                            "x": 250,
                            "y": 120,
                            "label": "QA Lead",
                        },
                        {
                            "id": "n3",
                            "agent_id": "chef_projet",
                            "x": 550,
                            "y": 120,
                            "label": "Chef de Projet",
                        },
                        {
                            "id": "n4",
                            "agent_id": "dev_tma",
                            "x": 200,
                            "y": 240,
                            "label": "Dev TMA",
                        },
                        {
                            "id": "n5",
                            "agent_id": "lead_dev",
                            "x": 400,
                            "y": 240,
                            "label": "Lead Dev",
                        },
                        {
                            "id": "n6",
                            "agent_id": "dba",
                            "x": 600,
                            "y": 240,
                            "label": "DBA",
                        },
                        {
                            "id": "n7",
                            "agent_id": "test_automation",
                            "x": 150,
                            "y": 360,
                            "label": "Test Automation",
                        },
                        {
                            "id": "n8",
                            "agent_id": "test_manager",
                            "x": 350,
                            "y": 360,
                            "label": "Test Manager",
                        },
                        {
                            "id": "n9",
                            "agent_id": "pipeline_engineer",
                            "x": 550,
                            "y": 360,
                            "label": "Pipeline Eng.",
                        },
                        {
                            "id": "n10",
                            "agent_id": "devops",
                            "x": 400,
                            "y": 460,
                            "label": "DevOps",
                        },
                    ],
                    "edges": [
                        {
                            "from": "n1",
                            "to": "n2",
                            "label": "triage",
                            "color": "#ef4444",
                        },
                        {"from": "n1", "to": "n3", "label": "SLA", "color": "#ef4444"},
                        {
                            "from": "n1",
                            "to": "n4",
                            "label": "assigner",
                            "color": "#f59e0b",
                        },
                        {
                            "from": "n4",
                            "to": "n5",
                            "label": "impact?",
                            "color": "#3b82f6",
                        },
                        {
                            "from": "n4",
                            "to": "n6",
                            "label": "query?",
                            "color": "#3b82f6",
                        },
                        {
                            "from": "n5",
                            "to": "n4",
                            "label": "review",
                            "color": "#10b981",
                        },
                        {
                            "from": "n4",
                            "to": "n7",
                            "label": "test E2E",
                            "color": "#8b5cf6",
                        },
                        {
                            "from": "n7",
                            "to": "n8",
                            "label": "résultats",
                            "color": "#10b981",
                        },
                        {
                            "from": "n8",
                            "to": "n9",
                            "label": "GO CI",
                            "color": "#10b981",
                        },
                        {
                            "from": "n9",
                            "to": "n10",
                            "label": "deploy",
                            "color": "#8b5cf6",
                        },
                        {
                            "from": "n10",
                            "to": "n1",
                            "label": "confirmé",
                            "color": "#10b981",
                        },
                    ],
                },
                "agents_permissions": {
                    "responsable_tma": {
                        "can_veto": True,
                        "veto_level": "STRONG",
                        "can_delegate": True,
                    },
                    "qa_lead": {"can_veto": True, "veto_level": "ABSOLUTE"},
                    "test_manager": {
                        "can_veto": True,
                        "veto_level": "STRONG",
                        "can_approve": True,
                    },
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
            icon="clipboard",
            is_builtin=True,
            phases=[
                WorkflowPhase(
                    id="plan",
                    pattern_id="hierarchical",
                    name="Plan de Test",
                    description="Le Test Manager définit la matrice de couverture. Le QA Lead identifie les parcours critiques. Le métier fournit les scénarios fonctionnels.",
                    gate="always",
                    config={"agents": ["test_manager", "qa_lead", "metier"]},
                ),
                WorkflowPhase(
                    id="automate",
                    pattern_id="hierarchical",
                    name="Automatisation",
                    description="Le Test Automation écrit les tests Playwright E2E. Le testeur écrit les tests d'API. Le Lead Dev fournit les fixtures et helpers.",
                    gate="always",
                    config={"agents": ["test_automation", "testeur", "lead_dev"]},
                ),
                WorkflowPhase(
                    id="execute",
                    pattern_id="parallel",
                    name="Exécution",
                    description="Exécution en parallèle: tests E2E IHM (Playwright), tests API (fetch), tests smoke, tests de performance. Collecte des résultats.",
                    gate="always",
                    config={
                        "agents": ["test_automation", "testeur", "performance_engineer"]
                    },
                ),
                WorkflowPhase(
                    id="report",
                    pattern_id="sequential",
                    name="Rapport & GO/NOGO",
                    description="Le Test Manager consolide les résultats. Le QA Lead valide la couverture. Le Chef de Projet décide GO/NOGO release.",
                    gate="all_approved",
                    config={"agents": ["test_manager", "qa_lead", "chef_projet"]},
                ),
            ],
            config={
                "graph": {
                    "pattern": "hierarchical",
                    "nodes": [
                        {
                            "id": "n1",
                            "agent_id": "test_manager",
                            "x": 400,
                            "y": 20,
                            "label": "Test Manager",
                        },
                        {
                            "id": "n2",
                            "agent_id": "qa_lead",
                            "x": 250,
                            "y": 130,
                            "label": "QA Lead",
                        },
                        {
                            "id": "n3",
                            "agent_id": "metier",
                            "x": 550,
                            "y": 130,
                            "label": "Métier",
                        },
                        {
                            "id": "n4",
                            "agent_id": "test_automation",
                            "x": 200,
                            "y": 260,
                            "label": "Test Automation",
                        },
                        {
                            "id": "n5",
                            "agent_id": "testeur",
                            "x": 400,
                            "y": 260,
                            "label": "Testeur",
                        },
                        {
                            "id": "n6",
                            "agent_id": "lead_dev",
                            "x": 600,
                            "y": 260,
                            "label": "Lead Dev",
                        },
                        {
                            "id": "n7",
                            "agent_id": "performance_engineer",
                            "x": 300,
                            "y": 370,
                            "label": "Perf Engineer",
                        },
                        {
                            "id": "n8",
                            "agent_id": "chef_projet",
                            "x": 500,
                            "y": 370,
                            "label": "Chef de Projet",
                        },
                    ],
                    "edges": [
                        {
                            "from": "n1",
                            "to": "n2",
                            "label": "matrice",
                            "color": "#a855f7",
                        },
                        {
                            "from": "n1",
                            "to": "n3",
                            "label": "scénarios",
                            "color": "#a855f7",
                        },
                        {
                            "from": "n2",
                            "to": "n4",
                            "label": "E2E specs",
                            "color": "#3b82f6",
                        },
                        {
                            "from": "n2",
                            "to": "n5",
                            "label": "API specs",
                            "color": "#3b82f6",
                        },
                        {
                            "from": "n6",
                            "to": "n4",
                            "label": "fixtures",
                            "color": "#f59e0b",
                        },
                        {
                            "from": "n4",
                            "to": "n1",
                            "label": "résultats E2E",
                            "color": "#10b981",
                        },
                        {
                            "from": "n5",
                            "to": "n1",
                            "label": "résultats API",
                            "color": "#10b981",
                        },
                        {
                            "from": "n7",
                            "to": "n1",
                            "label": "résultats perf",
                            "color": "#10b981",
                        },
                        {
                            "from": "n1",
                            "to": "n8",
                            "label": "GO/NOGO",
                            "color": "#ef4444",
                        },
                    ],
                },
                "agents_permissions": {
                    "test_manager": {
                        "can_veto": True,
                        "veto_level": "ABSOLUTE",
                        "can_delegate": True,
                        "can_approve": True,
                    },
                    "qa_lead": {
                        "can_veto": True,
                        "veto_level": "STRONG",
                        "can_approve": True,
                    },
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
            icon="zap",
            is_builtin=True,
            phases=[
                WorkflowPhase(
                    id="setup",
                    pattern_id="hierarchical",
                    name="Setup Pipeline",
                    description="Le Pipeline Engineer conçoit le workflow GitHub Actions/GitLab CI. Le DevOps définit les environments (staging, canary, prod). Le DevSecOps configure les scans de sécurité.",
                    gate="always",
                    config={"agents": ["pipeline_engineer", "devops", "devsecops"]},
                ),
                WorkflowPhase(
                    id="build-test",
                    pattern_id="sequential",
                    name="Build & Tests",
                    description="Le Pipeline Engineer configure les jobs: lint → build → unit tests → integration tests. Le Test Automation intègre les tests E2E. Le Lead Dev valide les configurations.",
                    gate="always",
                    config={
                        "agents": ["pipeline_engineer", "test_automation", "lead_dev"]
                    },
                ),
                WorkflowPhase(
                    id="quality-gates",
                    pattern_id="parallel",
                    name="Quality Gates",
                    description="En parallèle: le QA valide la couverture (≥80%), la Sécurité lance le SAST/DAST, le Perf Engineer configure les benchmarks. Tous les gates doivent passer.",
                    gate="all_approved",
                    config={
                        "agents": [
                            "qa_lead",
                            "securite",
                            "performance_engineer",
                            "pipeline_engineer",
                        ]
                    },
                ),
                WorkflowPhase(
                    id="deploy",
                    pattern_id="sequential",
                    name="Deploy Canary → Prod",
                    description="Le DevOps déploie en canary (1%→10%→50%→100%). Le SRE monitore les métriques. Rollback automatique si error_rate > baseline+5%. Le Chef de Projet valide le GO prod.",
                    gate="all_approved",
                    config={
                        "agents": ["devops", "sre", "pipeline_engineer", "chef_projet"]
                    },
                ),
            ],
            config={
                "graph": {
                    "pattern": "sequential",
                    "nodes": [
                        {
                            "id": "n1",
                            "agent_id": "pipeline_engineer",
                            "x": 400,
                            "y": 20,
                            "label": "Pipeline Engineer",
                        },
                        {
                            "id": "n2",
                            "agent_id": "devops",
                            "x": 250,
                            "y": 130,
                            "label": "DevOps",
                        },
                        {
                            "id": "n3",
                            "agent_id": "devsecops",
                            "x": 550,
                            "y": 130,
                            "label": "DevSecOps",
                        },
                        {
                            "id": "n4",
                            "agent_id": "test_automation",
                            "x": 200,
                            "y": 260,
                            "label": "Test Automation",
                        },
                        {
                            "id": "n5",
                            "agent_id": "lead_dev",
                            "x": 400,
                            "y": 260,
                            "label": "Lead Dev",
                        },
                        {
                            "id": "n6",
                            "agent_id": "qa_lead",
                            "x": 150,
                            "y": 370,
                            "label": "QA Lead",
                        },
                        {
                            "id": "n7",
                            "agent_id": "securite",
                            "x": 350,
                            "y": 370,
                            "label": "Sécurité",
                        },
                        {
                            "id": "n8",
                            "agent_id": "performance_engineer",
                            "x": 550,
                            "y": 370,
                            "label": "Perf Engineer",
                        },
                        {
                            "id": "n9",
                            "agent_id": "sre",
                            "x": 300,
                            "y": 480,
                            "label": "SRE",
                        },
                        {
                            "id": "n10",
                            "agent_id": "chef_projet",
                            "x": 500,
                            "y": 480,
                            "label": "Chef de Projet",
                        },
                    ],
                    "edges": [
                        {
                            "from": "n1",
                            "to": "n2",
                            "label": "environments",
                            "color": "#a855f7",
                        },
                        {
                            "from": "n1",
                            "to": "n3",
                            "label": "scans sécu",
                            "color": "#a855f7",
                        },
                        {
                            "from": "n1",
                            "to": "n4",
                            "label": "tests E2E",
                            "color": "#3b82f6",
                        },
                        {
                            "from": "n1",
                            "to": "n5",
                            "label": "config",
                            "color": "#3b82f6",
                        },
                        {
                            "from": "n4",
                            "to": "n6",
                            "label": "couverture",
                            "color": "#10b981",
                        },
                        {
                            "from": "n3",
                            "to": "n7",
                            "label": "SAST/DAST",
                            "color": "#ef4444",
                        },
                        {
                            "from": "n5",
                            "to": "n8",
                            "label": "benchmarks",
                            "color": "#f59e0b",
                        },
                        {
                            "from": "n6",
                            "to": "n1",
                            "label": "GO QA",
                            "color": "#10b981",
                        },
                        {
                            "from": "n7",
                            "to": "n1",
                            "label": "GO sécu",
                            "color": "#10b981",
                        },
                        {
                            "from": "n8",
                            "to": "n1",
                            "label": "GO perf",
                            "color": "#10b981",
                        },
                        {
                            "from": "n2",
                            "to": "n9",
                            "label": "canary",
                            "color": "#8b5cf6",
                        },
                        {
                            "from": "n9",
                            "to": "n10",
                            "label": "GO prod",
                            "color": "#ef4444",
                        },
                    ],
                },
                "agents_permissions": {
                    "pipeline_engineer": {
                        "can_veto": True,
                        "veto_level": "STRONG",
                        "can_delegate": True,
                    },
                    "devops": {
                        "can_veto": True,
                        "veto_level": "STRONG",
                        "can_approve": True,
                    },
                    "qa_lead": {"can_veto": True, "veto_level": "ABSOLUTE"},
                    "securite": {"can_veto": True, "veto_level": "ABSOLUTE"},
                    "sre": {
                        "can_veto": True,
                        "veto_level": "STRONG",
                        "can_approve": True,
                    },
                },
            },
        ),
    )
    # ── Cycle de Vie Produit Complet: Idéation → Comité Strat → Réal → CICD → QA → TMA ──
    builtins.append(
        WorkflowDef(
            id="product-lifecycle",
            name="Cycle de Vie Produit Complet",
            description="Pipeline bout en bout: ideation → strategic committee GO/NOGO → architecture → dev sprints → CI/CD pipeline → QA campaign → prod deploy → TMA maintenance.",
            icon="rocket",
            is_builtin=True,
            phases=[
                # ── Phase 1: Idéation (NETWORK — PO briefe, experts débattent, PO synthétise) ──
                WorkflowPhase(
                    id="ideation",
                    pattern_id="network",
                    name="Idéation",
                    description="Le Product Manager cadre le sujet et briefe l'équipe. Le métier exprime le besoin. L'UX Designer explore les parcours utilisateur. L'Architecte évalue la faisabilité technique. Débat structuré puis synthèse par le PO.",
                    gate="always",
                    config={
                        "agents": [
                            "metier",
                            "ux_designer",
                            "architecte",
                            "product_manager",
                        ],
                        "leader": "product_manager",
                    },
                ),
                # ── Phase 2: Comité Stratégique (HUMAN-IN-THE-LOOP — DSI arbitre avec GO/NOGO humain) ──
                WorkflowPhase(
                    id="strategic-committee",
                    pattern_id="human-in-the-loop",
                    name="Comité Stratégique GO/NOGO",
                    description="Le DSI préside. La CPO défend la valeur produit. Le CTO évalue la faisabilité et les risques techniques. Le Portfolio Manager analyse la capacité et le WSJF. Débat contradictoire. CHECKPOINT: le DSI attend la décision humaine GO, NOGO ou PIVOT.",
                    gate="all_approved",
                    config={
                        "agents": [
                            "strat-cpo",
                            "strat-cto",
                            "strat-portfolio",
                            "lean_portfolio_manager",
                            "dsi",
                        ],
                        "leader": "dsi",
                    },
                ),
                # ── Phase 3: Constitution Projet (SEQUENTIAL — Dir Programme lance la chaîne) ──
                WorkflowPhase(
                    id="project-setup",
                    pattern_id="sequential",
                    name="Constitution du Projet",
                    description="Le Dir. Programme alloue les ressources → le Product Manager décompose en épics → le Chef de Projet planifie les sprints → le Scrum Master configure les cérémonies. Chaque sortie alimente l'entrée du suivant.",
                    gate="always",
                    config={
                        "agents": [
                            "strat-dirprog",
                            "product_manager",
                            "chef_projet",
                            "scrum_master",
                        ],
                        "leader": "strat-dirprog",
                    },
                ),
                # ── Phase 4: Architecture (AGGREGATOR — analyses parallèles → architecte consolide) ──
                WorkflowPhase(
                    id="architecture",
                    pattern_id="aggregator",
                    name="Architecture & Design",
                    description="En parallèle: le Lead Dev analyse la faisabilité, l'UX crée les maquettes, la Sécurité définit les exigences, le DevOps planifie l'infra. L'Architecte agrège toutes les analyses en un document d'architecture consolidé.",
                    gate="no_veto",
                    config={
                        "agents": [
                            "lead_dev",
                            "ux_designer",
                            "securite",
                            "devops",
                            "architecte",
                        ],
                        "leader": "architecte",
                    },
                ),
                # ── Phase 5: Design System & Tokens (SEQUENTIAL — UX crée le socle UI avant les devs) ──
                WorkflowPhase(
                    id="design-system",
                    pattern_id="sequential",
                    name="Design System & Tokens UI",
                    description="L'UX Designer crée le mini design system: tokens CSS (couleurs, typo, spacing, radius), base layout responsive, composants de base (header, footer, card, button, form). Le Lead Dev valide l'intégration technique. TOUT le code UI des sprints DOIT utiliser ces tokens.",
                    gate="always",
                    config={
                        "agents": ["ux_designer", "lead_dev"],
                        "leader": "ux_designer",
                    },
                ),
                # ── Phase 6: Sprints Dev (HIERARCHICAL — Lead distribue, devs codent, QA inner loop) ──
                WorkflowPhase(
                    id="dev-sprint",
                    pattern_id="hierarchical",
                    name="Sprints de Développement",
                    description="Le Lead Dev distribue les stories. Les devs frontend et backend codent en TDD. Le Test Automation écrit les tests E2E en parallèle. Le Lead fait la code review. Boucle interne: si incomplet, le Lead re-distribue.",
                    gate="always",
                    config={
                        "agents": [
                            "lead_dev",
                            "dev_frontend",
                            "dev_backend",
                            "test_automation",
                        ],
                        "leader": "lead_dev",
                        "max_iterations": 3,
                    },
                ),
                # ── Phase 6b: Build & Verify (SEQUENTIAL — DevOps builds and tests everything) ──
                WorkflowPhase(
                    id="build-verify",
                    pattern_id="sequential",
                    name="Build & Verify",
                    description=(
                        "Le DevOps vérifie que TOUT le code compile et que les dépendances sont complètes. "
                        "Pour chaque langage: install deps (npm install / pip install -r requirements.txt / go mod tidy / cargo build) → compile → run tests. "
                        "Si des fichiers manquent (requirements.txt, go.mod, Dockerfile), les créer. "
                        "Si le build échoue, corriger le code. "
                        "OBJECTIF: le projet doit pouvoir se builder from scratch dans un container Docker propre."
                    ),
                    gate="no_veto",
                    config={
                        "agents": ["devops", "dev_backend", "dev_frontend"],
                        "leader": "devops",
                    },
                ),
                # ── Phase 7: CICD (SEQUENTIAL — Pipeline Engineer lance la chaîne) ──
                WorkflowPhase(
                    id="cicd",
                    pattern_id="sequential",
                    name="Pipeline CI/CD",
                    description="Le Pipeline Engineer configure le pipeline: lint → build → unit tests → integration → E2E. Le DevSecOps intègre les scans SAST/DAST. Le DevOps configure les environments staging et prod.",
                    gate="always",
                    config={
                        "agents": ["pipeline_engineer", "devsecops", "devops"],
                        "leader": "pipeline_engineer",
                    },
                ),
                # ── Phase 7: QA (LOOP — Test Manager planifie, exécution, si KO → reboucle) ──
                WorkflowPhase(
                    id="ux-review",
                    pattern_id="loop",
                    name="Revue UX & Conformité Design",
                    description="L'UX Designer vérifie que le code utilise les design tokens, respecte l'accessibilité WCAG AA (aria-*, contrast ≥ 4.5:1, keyboard nav), et la cohérence visuelle. Si VETO: boucle retour avec les corrections demandées aux devs. MANDATORY: run_e2e_tests() pour captures d'écran des parcours.",
                    gate="no_veto",
                    config={
                        "agents": ["ux_designer", "dev_frontend"],
                        "leader": "ux_designer",
                        "max_iterations": 2,
                    },
                ),
                # ── Phase 8: QA (LOOP — Test Manager planifie, exécution, si KO → reboucle) ──
                WorkflowPhase(
                    id="qa-campaign",
                    pattern_id="loop",
                    name="Campagne de Tests QA",
                    description="The Test Manager plans and launches the campaign. The QA Lead runs suites (E2E, API, perf). On VETO (bugs found): loop back to Test Manager who re-plans fixes. Iterates until APPROVE or max 5 iterations.",
                    gate="all_approved",
                    config={"agents": ["test_manager", "qa_lead"], "max_iterations": 5},
                ),
                # ── Phase 8: QA Détaillée (PARALLEL — QA Lead dispatche) ──
                WorkflowPhase(
                    id="qa-execution",
                    pattern_id="parallel",
                    name="Exécution Tests Parallèle",
                    description="Le QA Lead dispatche. En parallèle: le Test Automation lance Playwright, le Testeur fait les tests API, le Perf Engineer lance k6. Le QA Lead agrège les résultats.",
                    gate="all_approved",
                    config={
                        "agents": [
                            "qa_lead",
                            "test_automation",
                            "testeur",
                            "performance_engineer",
                        ],
                        "leader": "qa_lead",
                    },
                ),
                # ── Phase 9: Deploy (HUMAN-IN-THE-LOOP — Chef Projet valide) ──
                WorkflowPhase(
                    id="deploy-prod",
                    pattern_id="human-in-the-loop",
                    name="Deploy Production",
                    description="Le DevOps déploie en canary (1%). Le SRE monitore les métriques. Le Pipeline Engineer prépare le rollback. CHECKPOINT: le Chef de Projet valide le GO pour 100% après vérification humaine des métriques.",
                    gate="all_approved",
                    config={
                        "agents": ["devops", "sre", "pipeline_engineer", "chef_projet"],
                        "leader": "chef_projet",
                    },
                ),
                # ── Phase 10: Incident Router (ROUTER — Resp TMA triage) ──
                WorkflowPhase(
                    id="tma-router",
                    pattern_id="router",
                    name="Routage Incidents TMA",
                    description="Le Responsable TMA reçoit les incidents. Il analyse la nature (bug code, perf, infra, sécu) et route vers le spécialiste approprié: Dev TMA pour les bugs, SRE pour l'infra, Test Automation pour les régressions.",
                    gate="always",
                    config={
                        "agents": [
                            "responsable_tma",
                            "dev_tma",
                            "sre",
                            "test_automation",
                        ],
                        "leader": "responsable_tma",
                    },
                ),
                # ── Phase 11: Fix & Validate (LOOP — Dev TMA corrige, QA valide, reboucle si KO) ──
                WorkflowPhase(
                    id="tma-fix",
                    pattern_id="loop",
                    name="Correctif & Validation TMA",
                    description="Le Dev TMA écrit le correctif avec test de non-régression. Le QA Lead valide. Si VETO: boucle retour au Dev TMA avec le feedback. Itère jusqu'à APPROVE.",
                    gate="no_veto",
                    config={"agents": ["dev_tma", "qa_lead"], "max_iterations": 3},
                ),
            ],
            config={
                "graph": {
                    "pattern": "hierarchical",
                    "nodes": [
                        # Row 1: Idéation
                        {
                            "id": "n1",
                            "agent_id": "metier",
                            "x": 100,
                            "y": 20,
                            "label": "Métier / PO",
                        },
                        {
                            "id": "n2",
                            "agent_id": "ux_designer",
                            "x": 280,
                            "y": 20,
                            "label": "UX Designer",
                        },
                        {
                            "id": "n3",
                            "agent_id": "product_manager",
                            "x": 460,
                            "y": 20,
                            "label": "Product Manager",
                        },
                        {
                            "id": "n4",
                            "agent_id": "architecte",
                            "x": 640,
                            "y": 20,
                            "label": "Architecte",
                        },
                        # Row 2: Comité stratégique
                        {
                            "id": "n5",
                            "agent_id": "dsi",
                            "x": 370,
                            "y": 120,
                            "label": "DSI",
                        },
                        {
                            "id": "n6",
                            "agent_id": "strat-cpo",
                            "x": 200,
                            "y": 120,
                            "label": "CPO",
                        },
                        {
                            "id": "n7",
                            "agent_id": "strat-cto",
                            "x": 540,
                            "y": 120,
                            "label": "CTO",
                        },
                        {
                            "id": "n8",
                            "agent_id": "strat-portfolio",
                            "x": 700,
                            "y": 120,
                            "label": "Portfolio",
                        },
                        # Row 3: Constitution projet
                        {
                            "id": "n9",
                            "agent_id": "strat-dirprog",
                            "x": 100,
                            "y": 220,
                            "label": "Dir Programme",
                        },
                        {
                            "id": "n10",
                            "agent_id": "chef_projet",
                            "x": 300,
                            "y": 220,
                            "label": "Chef de Projet",
                        },
                        {
                            "id": "n11",
                            "agent_id": "scrum_master",
                            "x": 500,
                            "y": 220,
                            "label": "Scrum Master",
                        },
                        # Row 4: Architecture + Dev
                        {
                            "id": "n12",
                            "agent_id": "lead_dev",
                            "x": 200,
                            "y": 320,
                            "label": "Lead Dev",
                        },
                        {
                            "id": "n13",
                            "agent_id": "securite",
                            "x": 400,
                            "y": 320,
                            "label": "Sécurité",
                        },
                        {
                            "id": "n14",
                            "agent_id": "devops",
                            "x": 600,
                            "y": 320,
                            "label": "DevOps",
                        },
                        # Row 5: Devs + Test Automation
                        {
                            "id": "n15",
                            "agent_id": "dev_frontend",
                            "x": 100,
                            "y": 420,
                            "label": "Dev Frontend",
                        },
                        {
                            "id": "n16",
                            "agent_id": "dev_backend",
                            "x": 300,
                            "y": 420,
                            "label": "Dev Backend",
                        },
                        {
                            "id": "n17",
                            "agent_id": "test_automation",
                            "x": 500,
                            "y": 420,
                            "label": "Test Automation",
                        },
                        # Row 6: CICD
                        {
                            "id": "n18",
                            "agent_id": "pipeline_engineer",
                            "x": 400,
                            "y": 520,
                            "label": "Pipeline Eng.",
                        },
                        {
                            "id": "n19",
                            "agent_id": "devsecops",
                            "x": 600,
                            "y": 520,
                            "label": "DevSecOps",
                        },
                        # Row 7: QA Campaign
                        {
                            "id": "n20",
                            "agent_id": "test_manager",
                            "x": 200,
                            "y": 620,
                            "label": "Test Manager",
                        },
                        {
                            "id": "n21",
                            "agent_id": "qa_lead",
                            "x": 400,
                            "y": 620,
                            "label": "QA Lead",
                        },
                        {
                            "id": "n22",
                            "agent_id": "testeur",
                            "x": 550,
                            "y": 620,
                            "label": "Testeur",
                        },
                        {
                            "id": "n23",
                            "agent_id": "performance_engineer",
                            "x": 700,
                            "y": 620,
                            "label": "Perf Eng.",
                        },
                        # Row 8: Deploy + SRE
                        {
                            "id": "n24",
                            "agent_id": "sre",
                            "x": 500,
                            "y": 720,
                            "label": "SRE",
                        },
                        # Row 9: TMA
                        {
                            "id": "n25",
                            "agent_id": "responsable_tma",
                            "x": 200,
                            "y": 820,
                            "label": "Resp. TMA",
                        },
                        {
                            "id": "n26",
                            "agent_id": "dev_tma",
                            "x": 400,
                            "y": 820,
                            "label": "Dev TMA",
                        },
                        {
                            "id": "n27",
                            "agent_id": "lean_portfolio_manager",
                            "x": 100,
                            "y": 120,
                            "label": "Lean Portfolio",
                        },
                    ],
                    "edges": [
                        # Idéation → Comité Strat
                        {
                            "from": "n1",
                            "to": "n3",
                            "label": "besoin",
                            "color": "#3b82f6",
                        },
                        {"from": "n2", "to": "n3", "label": "UX", "color": "#3b82f6"},
                        {
                            "from": "n4",
                            "to": "n3",
                            "label": "faisabilité",
                            "color": "#3b82f6",
                        },
                        {
                            "from": "n3",
                            "to": "n5",
                            "label": "dossier",
                            "color": "#a855f7",
                        },
                        # Comité Strat interne
                        {
                            "from": "n6",
                            "to": "n5",
                            "label": "avis CPO",
                            "color": "#d946ef",
                        },
                        {
                            "from": "n7",
                            "to": "n5",
                            "label": "avis CTO",
                            "color": "#d946ef",
                        },
                        {"from": "n8", "to": "n5", "label": "WSJF", "color": "#10b981"},
                        {
                            "from": "n27",
                            "to": "n8",
                            "label": "lean",
                            "color": "#06b6d4",
                        },
                        # GO → Constitution
                        {"from": "n5", "to": "n9", "label": "GO", "color": "#10b981"},
                        {
                            "from": "n9",
                            "to": "n10",
                            "label": "staffing",
                            "color": "#8b5cf6",
                        },
                        {
                            "from": "n10",
                            "to": "n11",
                            "label": "planning",
                            "color": "#8b5cf6",
                        },
                        # Architecture
                        {
                            "from": "n10",
                            "to": "n12",
                            "label": "specs",
                            "color": "#f59e0b",
                        },
                        {
                            "from": "n4",
                            "to": "n12",
                            "label": "archi",
                            "color": "#a855f7",
                        },
                        {
                            "from": "n12",
                            "to": "n13",
                            "label": "review sécu",
                            "color": "#ef4444",
                        },
                        {
                            "from": "n12",
                            "to": "n14",
                            "label": "infra",
                            "color": "#8b5cf6",
                        },
                        # Dev Sprint
                        {
                            "from": "n12",
                            "to": "n15",
                            "label": "stories",
                            "color": "#f59e0b",
                        },
                        {
                            "from": "n12",
                            "to": "n16",
                            "label": "stories",
                            "color": "#f59e0b",
                        },
                        {
                            "from": "n12",
                            "to": "n17",
                            "label": "tests E2E",
                            "color": "#3b82f6",
                        },
                        # CICD
                        {
                            "from": "n14",
                            "to": "n18",
                            "label": "pipeline",
                            "color": "#8b5cf6",
                        },
                        {
                            "from": "n18",
                            "to": "n19",
                            "label": "scans sécu",
                            "color": "#ef4444",
                        },
                        {
                            "from": "n17",
                            "to": "n18",
                            "label": "tests CI",
                            "color": "#3b82f6",
                        },
                        # QA Campaign
                        {
                            "from": "n18",
                            "to": "n20",
                            "label": "build OK",
                            "color": "#10b981",
                        },
                        {
                            "from": "n20",
                            "to": "n21",
                            "label": "plan test",
                            "color": "#a855f7",
                        },
                        {
                            "from": "n21",
                            "to": "n22",
                            "label": "API tests",
                            "color": "#3b82f6",
                        },
                        {
                            "from": "n21",
                            "to": "n17",
                            "label": "E2E tests",
                            "color": "#3b82f6",
                        },
                        {
                            "from": "n23",
                            "to": "n20",
                            "label": "perf OK",
                            "color": "#10b981",
                        },
                        {
                            "from": "n22",
                            "to": "n20",
                            "label": "résultats",
                            "color": "#10b981",
                        },
                        # Deploy
                        {
                            "from": "n20",
                            "to": "n10",
                            "label": "GO/NOGO",
                            "color": "#ef4444",
                        },
                        {
                            "from": "n14",
                            "to": "n24",
                            "label": "canary",
                            "color": "#8b5cf6",
                        },
                        {
                            "from": "n24",
                            "to": "n10",
                            "label": "prod OK",
                            "color": "#10b981",
                        },
                        # TMA Handover
                        {
                            "from": "n12",
                            "to": "n25",
                            "label": "transfert",
                            "color": "#d946ef",
                        },
                        {
                            "from": "n25",
                            "to": "n26",
                            "label": "assigner",
                            "color": "#f59e0b",
                        },
                        {
                            "from": "n20",
                            "to": "n25",
                            "label": "tests régression",
                            "color": "#3b82f6",
                        },
                        {
                            "from": "n26",
                            "to": "n24",
                            "label": "hotfix",
                            "color": "#ef4444",
                        },
                    ],
                },
                "agents_permissions": {
                    "dsi": {
                        "can_veto": True,
                        "veto_level": "ABSOLUTE",
                        "can_delegate": True,
                        "can_approve": True,
                    },
                    "strat-cpo": {
                        "can_veto": True,
                        "veto_level": "STRONG",
                        "can_approve": True,
                    },
                    "strat-cto": {"can_veto": True, "veto_level": "STRONG"},
                    "qa_lead": {"can_veto": True, "veto_level": "ABSOLUTE"},
                    "securite": {"can_veto": True, "veto_level": "ABSOLUTE"},
                    "test_manager": {
                        "can_veto": True,
                        "veto_level": "STRONG",
                        "can_approve": True,
                    },
                    "responsable_tma": {
                        "can_veto": True,
                        "veto_level": "STRONG",
                        "can_delegate": True,
                    },
                    "lead_dev": {
                        "can_delegate": True,
                        "can_veto": True,
                        "veto_level": "STRONG",
                    },
                    "chef_projet": {"can_delegate": True, "can_approve": True},
                    "devops": {
                        "can_veto": True,
                        "veto_level": "STRONG",
                        "can_approve": True,
                    },
                    "sre": {
                        "can_veto": True,
                        "veto_level": "STRONG",
                        "can_approve": True,
                    },
                    "pipeline_engineer": {"can_veto": True, "veto_level": "STRONG"},
                },
            },
        ),
    )
    # ── DSI Platform Features: Discovery → Comité → Arch → Sprint → CI/CD → QA → Deploy → Retro ──
    builtins.append(
        WorkflowDef(
            id="dsi-platform-features",
            name="DSI Platform — New Features",
            description="Pipeline complet pour les nouvelles fonctionnalités de la plateforme Macaron. "
            "Discovery réseau → Comité stratégique GO/NOGO → Architecture → Sprint Dev (6 devs spécialisés) "
            "→ CI/CD → QA parallèle → Deploy staging/prod → Rétrospective.",
            icon="star",
            is_builtin=True,
            phases=[
                WorkflowPhase(
                    id="discovery",
                    pattern_id="network",
                    name="Discovery & Idéation",
                    description="Le DSI, le CPO, le CTO et le PO Plateforme débattent des nouvelles features. "
                    "L'UX Designer et l'Architecte contribuent. Réseau de discussion ouverte pour faire émerger les idées.",
                    gate="always",
                    config={
                        "agents": [
                            "dsi",
                            "strat-cpo",
                            "strat-cto",
                            "plat-product",
                            "ux_designer",
                            "architecte",
                        ]
                    },
                ),
                WorkflowPhase(
                    id="strategic-committee",
                    pattern_id="human-in-the-loop",
                    name="Comité Stratégique",
                    description="Le comité stratégique (CPO, CTO, DSI, Portfolio Manager) valide les features proposées. "
                    "GO/NOGO obligatoire. Seules les features validées passent en développement.",
                    gate="all_approved",
                    config={
                        "agents": [
                            "strat-cpo",
                            "strat-cto",
                            "dsi",
                            "strat-portfolio",
                            "lean_portfolio_manager",
                        ]
                    },
                ),
                WorkflowPhase(
                    id="architecture",
                    pattern_id="aggregator",
                    name="Architecture & Design",
                    description="L'Architecte, le Lead Dev et les devs spécialisés (agents, patterns) conçoivent la solution. "
                    "La Sécurité vérifie les impacts. Chacun contribue son expertise, l'Architecte synthétise.",
                    gate="no_veto",
                    config={
                        "agents": [
                            "architecte",
                            "plat-lead-dev",
                            "plat-dev-agents",
                            "plat-dev-patterns",
                            "securite",
                        ]
                    },
                ),
                WorkflowPhase(
                    id="sprint-planning",
                    pattern_id="sequential",
                    name="Sprint Planning",
                    description="Le PO Plateforme écrit les user stories. Le Scrum Master organise le sprint. "
                    "Le Lead Dev estime et découpe en tâches techniques.",
                    gate="always",
                    config={
                        "agents": ["plat-product", "scrum_master", "plat-lead-dev"]
                    },
                ),
                WorkflowPhase(
                    id="dev-sprint",
                    pattern_id="hierarchical",
                    name="Sprint Développement",
                    description="Le Lead Dev distribue les tâches à 5 devs spécialisés : Backend (routes, DB), "
                    "Frontend (templates, CSS, HTMX), Agents (executor, loop, bus), Patterns (engine), Infra (deploy, SSE). "
                    "Chaque dev code dans son domaine avec tests.",
                    gate="no_veto",
                    config={
                        "agents": [
                            "plat-lead-dev",
                            "plat-dev-backend",
                            "plat-dev-frontend",
                            "plat-dev-agents",
                            "plat-dev-patterns",
                            "plat-dev-infra",
                        ],
                        "leader": "plat-lead-dev",
                    },
                ),
                WorkflowPhase(
                    id="cicd",
                    pattern_id="sequential",
                    name="Pipeline CI/CD",
                    description="Le DevOps configure le pipeline. Le Pipeline Engineer vérifie les étapes. "
                    "Le DevSecOps scanne les vulnérabilités. Build + lint + tests unitaires.",
                    gate="always",
                    config={"agents": ["devops", "pipeline_engineer", "devsecops"]},
                ),
                WorkflowPhase(
                    id="qa-validation",
                    pattern_id="parallel",
                    name="QA & Validation",
                    description="4 experts testent en parallèle : QA Lead (fonctionnel), Test Automation (E2E), "
                    "Sécurité (OWASP), Performance (charge). Tous doivent valider.",
                    gate="no_veto",
                    config={
                        "agents": [
                            "qa_lead",
                            "test_automation",
                            "securite",
                            "performance_engineer",
                        ]
                    },
                ),
                WorkflowPhase(
                    id="deploy-prod",
                    pattern_id="sequential",
                    name="Deploy Staging → Prod",
                    description="Le DevOps déploie en staging. Le SRE vérifie la santé. Le QA Lead valide le smoke test. "
                    "Le Lead Dev donne le GO final pour la prod.",
                    gate="all_approved",
                    config={"agents": ["devops", "sre", "qa_lead", "plat-lead-dev"]},
                ),
                WorkflowPhase(
                    id="retrospective",
                    pattern_id="network",
                    name="Rétrospective",
                    description="Le Lead Dev, le PO, le Scrum Master et le QA Lead débattent : "
                    "ce qui a bien marché, ce qui a échoué, les améliorations à apporter. "
                    "Les leçons sont stockées en mémoire globale.",
                    gate="always",
                    config={
                        "agents": [
                            "plat-lead-dev",
                            "plat-product",
                            "scrum_master",
                            "qa_lead",
                        ]
                    },
                ),
            ],
            config={
                "project_ref": "software-factory",
                "graph": {
                    "pattern": "hierarchical",
                    "nodes": [
                        {
                            "id": "n1",
                            "agent_id": "dsi",
                            "x": 400,
                            "y": 20,
                            "label": "DSI",
                        },
                        {
                            "id": "n2",
                            "agent_id": "strat-cpo",
                            "x": 250,
                            "y": 20,
                            "label": "CPO",
                        },
                        {
                            "id": "n3",
                            "agent_id": "strat-cto",
                            "x": 550,
                            "y": 20,
                            "label": "CTO",
                        },
                        {
                            "id": "n4",
                            "agent_id": "strat-portfolio",
                            "x": 700,
                            "y": 20,
                            "label": "Portfolio",
                        },
                        {
                            "id": "n5",
                            "agent_id": "plat-product",
                            "x": 100,
                            "y": 120,
                            "label": "PO Plateforme",
                        },
                        {
                            "id": "n6",
                            "agent_id": "architecte",
                            "x": 300,
                            "y": 120,
                            "label": "Architecte",
                        },
                        {
                            "id": "n7",
                            "agent_id": "ux_designer",
                            "x": 500,
                            "y": 120,
                            "label": "UX Designer",
                        },
                        {
                            "id": "n8",
                            "agent_id": "scrum_master",
                            "x": 700,
                            "y": 120,
                            "label": "Scrum Master",
                        },
                        {
                            "id": "n9",
                            "agent_id": "plat-lead-dev",
                            "x": 400,
                            "y": 240,
                            "label": "Lead Dev Platform",
                        },
                        {
                            "id": "n10",
                            "agent_id": "plat-dev-backend",
                            "x": 150,
                            "y": 360,
                            "label": "Dev Backend",
                        },
                        {
                            "id": "n11",
                            "agent_id": "plat-dev-frontend",
                            "x": 300,
                            "y": 360,
                            "label": "Dev Frontend",
                        },
                        {
                            "id": "n12",
                            "agent_id": "plat-dev-agents",
                            "x": 450,
                            "y": 360,
                            "label": "Dev Agents",
                        },
                        {
                            "id": "n13",
                            "agent_id": "plat-dev-patterns",
                            "x": 600,
                            "y": 360,
                            "label": "Dev Patterns",
                        },
                        {
                            "id": "n14",
                            "agent_id": "plat-dev-infra",
                            "x": 750,
                            "y": 360,
                            "label": "Dev Infra",
                        },
                        {
                            "id": "n15",
                            "agent_id": "securite",
                            "x": 100,
                            "y": 120,
                            "label": "Sécurité",
                        },
                        {
                            "id": "n16",
                            "agent_id": "qa_lead",
                            "x": 200,
                            "y": 480,
                            "label": "QA Lead",
                        },
                        {
                            "id": "n17",
                            "agent_id": "test_automation",
                            "x": 400,
                            "y": 480,
                            "label": "Test Automation",
                        },
                        {
                            "id": "n18",
                            "agent_id": "performance_engineer",
                            "x": 600,
                            "y": 480,
                            "label": "Perf Engineer",
                        },
                        {
                            "id": "n19",
                            "agent_id": "devops",
                            "x": 300,
                            "y": 580,
                            "label": "DevOps",
                        },
                        {
                            "id": "n20",
                            "agent_id": "sre",
                            "x": 500,
                            "y": 580,
                            "label": "SRE",
                        },
                        {
                            "id": "n21",
                            "agent_id": "pipeline_engineer",
                            "x": 400,
                            "y": 580,
                            "label": "Pipeline Eng.",
                        },
                        {
                            "id": "n22",
                            "agent_id": "devsecops",
                            "x": 600,
                            "y": 580,
                            "label": "DevSecOps",
                        },
                    ],
                    "edges": [
                        {
                            "from": "n1",
                            "to": "n6",
                            "label": "vision",
                            "color": "#a855f7",
                        },
                        {
                            "from": "n2",
                            "to": "n5",
                            "label": "priorités",
                            "color": "#a855f7",
                        },
                        {
                            "from": "n3",
                            "to": "n6",
                            "label": "tech stack",
                            "color": "#3b82f6",
                        },
                        {
                            "from": "n5",
                            "to": "n8",
                            "label": "stories",
                            "color": "#f59e0b",
                        },
                        {
                            "from": "n5",
                            "to": "n9",
                            "label": "sprint",
                            "color": "#f59e0b",
                        },
                        {
                            "from": "n6",
                            "to": "n9",
                            "label": "design",
                            "color": "#3b82f6",
                        },
                        {
                            "from": "n9",
                            "to": "n10",
                            "label": "routes/DB",
                            "color": "#10b981",
                        },
                        {
                            "from": "n9",
                            "to": "n11",
                            "label": "templates",
                            "color": "#10b981",
                        },
                        {
                            "from": "n9",
                            "to": "n12",
                            "label": "executor",
                            "color": "#10b981",
                        },
                        {
                            "from": "n9",
                            "to": "n13",
                            "label": "engine",
                            "color": "#10b981",
                        },
                        {
                            "from": "n9",
                            "to": "n14",
                            "label": "infra",
                            "color": "#10b981",
                        },
                        {
                            "from": "n10",
                            "to": "n16",
                            "label": "tests",
                            "color": "#8b5cf6",
                        },
                        {
                            "from": "n11",
                            "to": "n16",
                            "label": "tests",
                            "color": "#8b5cf6",
                        },
                        {
                            "from": "n12",
                            "to": "n17",
                            "label": "tests",
                            "color": "#8b5cf6",
                        },
                        {
                            "from": "n15",
                            "to": "n9",
                            "label": "audit",
                            "color": "#ef4444",
                        },
                        {
                            "from": "n16",
                            "to": "n19",
                            "label": "GO deploy",
                            "color": "#10b981",
                        },
                        {
                            "from": "n17",
                            "to": "n19",
                            "label": "E2E OK",
                            "color": "#10b981",
                        },
                        {
                            "from": "n19",
                            "to": "n20",
                            "label": "staging",
                            "color": "#f59e0b",
                        },
                        {
                            "from": "n20",
                            "to": "n9",
                            "label": "prod GO",
                            "color": "#10b981",
                        },
                        {
                            "from": "n21",
                            "to": "n19",
                            "label": "pipeline",
                            "color": "#3b82f6",
                        },
                        {
                            "from": "n22",
                            "to": "n19",
                            "label": "scan",
                            "color": "#ef4444",
                        },
                    ],
                },
                "agents_permissions": {
                    "dsi": {
                        "can_veto": True,
                        "veto_level": "ABSOLUTE",
                        "can_delegate": True,
                        "can_approve": True,
                    },
                    "strat-cpo": {
                        "can_veto": True,
                        "veto_level": "ABSOLUTE",
                        "can_approve": True,
                    },
                    "strat-cto": {
                        "can_veto": True,
                        "veto_level": "ABSOLUTE",
                        "can_approve": True,
                    },
                    "plat-lead-dev": {
                        "can_veto": True,
                        "veto_level": "STRONG",
                        "can_delegate": True,
                        "can_approve": True,
                    },
                    "architecte": {
                        "can_veto": True,
                        "veto_level": "STRONG",
                        "can_approve": True,
                    },
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
            icon="tool",
            is_builtin=True,
            phases=[
                WorkflowPhase(
                    id="detection",
                    pattern_id="parallel",
                    name="Détection Incidents",
                    description="Le TMA Lead analyse les incidents remontés (auto-détection 500, SSE drops, LLM failures + signalements manuels). "
                    "Le SRE vérifie les métriques serveur. Le QA Lead vérifie les tests automatisés.",
                    gate="always",
                    config={"agents": ["plat-tma-lead", "sre", "qa_lead"]},
                ),
                WorkflowPhase(
                    id="triage",
                    pattern_id="router",
                    name="Triage & Priorisation P0-P4",
                    description="Le TMA Lead classifie chaque incident par sévérité (P0=platform down, P1=feature broken, "
                    "P2=minor, P3=cosmetic, P4=tech debt) et par domaine (backend/frontend/agents/patterns/infra). "
                    "L'Architecte évalue l'impact systémique. La Sécurité vérifie les aspects sécu.",
                    gate="always",
                    config={"agents": ["plat-tma-lead", "architecte", "securite"]},
                ),
                WorkflowPhase(
                    id="diagnostic",
                    pattern_id="parallel",
                    name="Diagnostic Root Cause",
                    description="4 devs TMA analysent en parallèle selon leur domaine : Backend (routes, DB), "
                    "Frontend (templates, CSS, HTMX), Agents (executor, LLM, bus), DBA (requêtes, migrations). "
                    "Chacun identifie la root cause dans son périmètre.",
                    gate="always",
                    config={
                        "agents": [
                            "plat-tma-dev-back",
                            "plat-tma-dev-front",
                            "plat-tma-dev-agents",
                            "dba",
                        ]
                    },
                ),
                WorkflowPhase(
                    id="fix-tdd",
                    pattern_id="loop",
                    name="Fix TDD Itératif",
                    description="Les devs TMA écrivent le test de non-régression (RED), puis le correctif (GREEN). "
                    "La QA TMA valide. Si échec, on reboucle. Max 3 itérations avant escalation.",
                    gate="no_veto",
                    config={
                        "agents": [
                            "plat-tma-dev-back",
                            "plat-tma-dev-front",
                            "plat-tma-dev-agents",
                            "plat-tma-qa",
                        ],
                        "max_iterations": 3,
                    },
                ),
                WorkflowPhase(
                    id="non-regression",
                    pattern_id="parallel",
                    name="Non-Régression Complète",
                    description="La QA TMA lance les tests fonctionnels. Le Test Automation vérifie les E2E. "
                    "La Sécurité fait un scan OWASP. Le Performance Engineer vérifie les benchmarks. "
                    "TOUS doivent approuver.",
                    gate="all_approved",
                    config={
                        "agents": [
                            "plat-tma-qa",
                            "test_automation",
                            "securite",
                            "performance_engineer",
                        ]
                    },
                ),
                WorkflowPhase(
                    id="deploy-hotfix",
                    pattern_id="sequential",
                    name="Deploy Hotfix",
                    description="Le DevOps déploie le hotfix en staging. Le SRE vérifie la santé. "
                    "Le TMA Lead confirme la résolution de l'incident. Le QA Lead donne le GO prod.",
                    gate="all_approved",
                    config={"agents": ["devops", "sre", "plat-tma-lead", "qa_lead"]},
                ),
            ],
            config={
                "project_ref": "software-factory",
                "graph": {
                    "pattern": "hierarchical",
                    "nodes": [
                        {
                            "id": "n1",
                            "agent_id": "plat-tma-lead",
                            "x": 400,
                            "y": 20,
                            "label": "TMA Lead",
                        },
                        {
                            "id": "n2",
                            "agent_id": "sre",
                            "x": 600,
                            "y": 20,
                            "label": "SRE",
                        },
                        {
                            "id": "n3",
                            "agent_id": "architecte",
                            "x": 250,
                            "y": 120,
                            "label": "Architecte",
                        },
                        {
                            "id": "n4",
                            "agent_id": "securite",
                            "x": 550,
                            "y": 120,
                            "label": "Sécurité",
                        },
                        {
                            "id": "n5",
                            "agent_id": "plat-tma-dev-back",
                            "x": 150,
                            "y": 240,
                            "label": "TMA Backend",
                        },
                        {
                            "id": "n6",
                            "agent_id": "plat-tma-dev-front",
                            "x": 350,
                            "y": 240,
                            "label": "TMA Frontend",
                        },
                        {
                            "id": "n7",
                            "agent_id": "plat-tma-dev-agents",
                            "x": 550,
                            "y": 240,
                            "label": "TMA Agents",
                        },
                        {
                            "id": "n8",
                            "agent_id": "dba",
                            "x": 750,
                            "y": 240,
                            "label": "DBA",
                        },
                        {
                            "id": "n9",
                            "agent_id": "plat-tma-qa",
                            "x": 300,
                            "y": 360,
                            "label": "QA TMA",
                        },
                        {
                            "id": "n10",
                            "agent_id": "test_automation",
                            "x": 500,
                            "y": 360,
                            "label": "Test Auto",
                        },
                        {
                            "id": "n11",
                            "agent_id": "performance_engineer",
                            "x": 700,
                            "y": 360,
                            "label": "Perf Eng.",
                        },
                        {
                            "id": "n12",
                            "agent_id": "qa_lead",
                            "x": 200,
                            "y": 20,
                            "label": "QA Lead",
                        },
                        {
                            "id": "n13",
                            "agent_id": "devops",
                            "x": 400,
                            "y": 460,
                            "label": "DevOps",
                        },
                    ],
                    "edges": [
                        {
                            "from": "n1",
                            "to": "n3",
                            "label": "triage",
                            "color": "#ef4444",
                        },
                        {
                            "from": "n1",
                            "to": "n4",
                            "label": "sécu?",
                            "color": "#ef4444",
                        },
                        {
                            "from": "n1",
                            "to": "n5",
                            "label": "fix back",
                            "color": "#f59e0b",
                        },
                        {
                            "from": "n1",
                            "to": "n6",
                            "label": "fix front",
                            "color": "#f59e0b",
                        },
                        {
                            "from": "n1",
                            "to": "n7",
                            "label": "fix agents",
                            "color": "#f59e0b",
                        },
                        {
                            "from": "n3",
                            "to": "n1",
                            "label": "impact",
                            "color": "#3b82f6",
                        },
                        {"from": "n5", "to": "n9", "label": "test", "color": "#10b981"},
                        {"from": "n6", "to": "n9", "label": "test", "color": "#10b981"},
                        {"from": "n7", "to": "n9", "label": "test", "color": "#10b981"},
                        {"from": "n8", "to": "n5", "label": "data", "color": "#3b82f6"},
                        {
                            "from": "n9",
                            "to": "n1",
                            "label": "validé",
                            "color": "#10b981",
                        },
                        {"from": "n9", "to": "n10", "label": "E2E", "color": "#8b5cf6"},
                        {"from": "n10", "to": "n13", "label": "GO", "color": "#10b981"},
                        {
                            "from": "n11",
                            "to": "n13",
                            "label": "perf OK",
                            "color": "#10b981",
                        },
                        {
                            "from": "n12",
                            "to": "n1",
                            "label": "incidents",
                            "color": "#ef4444",
                        },
                        {
                            "from": "n2",
                            "to": "n1",
                            "label": "métriques",
                            "color": "#3b82f6",
                        },
                        {
                            "from": "n13",
                            "to": "n1",
                            "label": "déployé",
                            "color": "#10b981",
                        },
                    ],
                },
                "agents_permissions": {
                    "plat-tma-lead": {
                        "can_veto": True,
                        "veto_level": "STRONG",
                        "can_delegate": True,
                        "can_approve": True,
                    },
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
            icon="shield",
            is_builtin=True,
            phases=[
                WorkflowPhase(
                    id="recon",
                    pattern_id="parallel",
                    name="Reconnaissance",
                    description="Le Pentester Lead coordonne la phase de reconnaissance. "
                    "La Security Researcher cartographie la surface d'attaque (OSINT, ports, services, APIs). "
                    "L'Exploit Dev identifie les points d'entrée potentiels. Scan passif puis actif.",
                    gate="always",
                    config={
                        "agents": [
                            "pentester-lead",
                            "security-researcher",
                            "exploit-dev",
                        ]
                    },
                ),
                WorkflowPhase(
                    id="threat-model",
                    pattern_id="network",
                    name="Threat Modeling",
                    description="Débat contradictoire Red Team vs Blue Team. "
                    "Le Pentester Lead présente les vecteurs d'attaque identifiés. "
                    "La Security Architect évalue les défenses existantes. "
                    "La Threat Analyst quantifie les risques (STRIDE/DREAD). "
                    "Objectif: prioriser les scénarios d'attaque par impact.",
                    gate="always",
                    config={
                        "agents": [
                            "pentester-lead",
                            "security-architect",
                            "threat-analyst",
                            "security-researcher",
                        ]
                    },
                ),
                WorkflowPhase(
                    id="exploitation",
                    pattern_id="loop",
                    name="Exploitation",
                    description="Le Pentester Lead orchestre les tests d'intrusion. "
                    "L'Exploit Dev développe et exécute les PoC (SQLi, XSS, SSRF, auth bypass, RCE). "
                    "Chaque vulnérabilité confirmée est scorée CVSS v3.1. "
                    "Itération: tester → analyser → adapter → re-tester. Max 5 itérations.",
                    gate="always",
                    config={
                        "agents": [
                            "pentester-lead",
                            "exploit-dev",
                            "security-researcher",
                        ],
                        "max_iterations": 5,
                    },
                ),
                WorkflowPhase(
                    id="vuln-report",
                    pattern_id="aggregator",
                    name="Rapport de Vulnérabilités",
                    description="Toutes les findings sont consolidées en un rapport structuré. "
                    "La Security Researcher compile les CVE référencées. "
                    "La Threat Analyst score et priorise (P0-P3). "
                    "Le Pentester Lead rédige les recommandations de remédiation. "
                    "Livrable: rapport CVSS avec PoC, impact, et remediation pour chaque vuln.",
                    gate="always",
                    config={
                        "agents": [
                            "pentester-lead",
                            "security-researcher",
                            "threat-analyst",
                        ],
                        "leader": "threat-analyst",
                    },
                ),
                WorkflowPhase(
                    id="security-review",
                    pattern_id="human-in-the-loop",
                    name="Security Review — GO/NOGO",
                    description="Le CISO examine le rapport de vulnérabilités. "
                    "La Compliance Officer vérifie les implications réglementaires (GDPR, SOC2). "
                    "La Security Architect recommande les priorités de remédiation. "
                    "Checkpoint: GO (corriger immédiatement), NOGO (bloquer la release), "
                    "PIVOT (accepter le risque avec plan de mitigation).",
                    gate="checkpoint",
                    config={
                        "agents": ["ciso", "compliance_officer", "security-architect"]
                    },
                ),
                WorkflowPhase(
                    id="remediation",
                    pattern_id="loop",
                    name="Remédiation TDD",
                    description="Le Security Dev Lead distribue les vulnérabilités aux développeurs. "
                    "Chaque fix suit TDD: RED (test reproduit l'exploit) → GREEN (fix) → REFACTOR. "
                    "Le Backend Dev corrige SQLi, auth bypass, SSRF. "
                    "Le Frontend Dev corrige XSS, CSRF, CSP. "
                    "La QA Security valide chaque PR. Loop max 3 itérations par vuln.",
                    gate="no_veto",
                    config={
                        "agents": [
                            "security-dev-lead",
                            "security-backend-dev",
                            "security-frontend-dev",
                            "qa-security",
                        ],
                        "leader": "security-dev-lead",
                        "max_iterations": 3,
                    },
                ),
                WorkflowPhase(
                    id="verification",
                    pattern_id="parallel",
                    name="Vérification & Non-Régression",
                    description="Re-test parallèle multi-aspect. "
                    "L'Exploit Dev re-exécute tous les PoC originaux — doivent ÉCHOUER. "
                    "La QA Security lance OWASP ZAP + SAST/DAST + tests de régression. "
                    "La Compliance Officer vérifie la conformité réglementaire. "
                    "Le SecOps vérifie les contrôles de sécurité en place. "
                    "TOUS doivent approuver.",
                    gate="all_approved",
                    config={
                        "agents": [
                            "exploit-dev",
                            "qa-security",
                            "compliance_officer",
                            "secops-engineer",
                        ]
                    },
                ),
                WorkflowPhase(
                    id="deploy-secure",
                    pattern_id="sequential",
                    name="Deploy Sécurisé & Monitoring",
                    description="Le SecOps déploie le hotfix en staging. "
                    "La QA Security valide en staging. "
                    "Le Pentester Lead fait un smoke test sécurité. "
                    "Le CISO donne le GO final pour la prod. "
                    "Pipeline: staging → E2E sécu → canary 1% → monitoring → prod 100%.",
                    gate="all_approved",
                    config={
                        "agents": [
                            "secops-engineer",
                            "qa-security",
                            "pentester-lead",
                            "ciso",
                        ]
                    },
                ),
            ],
            config={
                "orchestrator": "ciso",
                "graph": {
                    "pattern": "hierarchical",
                    "nodes": [
                        # Red Team
                        {
                            "id": "n1",
                            "agent_id": "pentester-lead",
                            "x": 400,
                            "y": 20,
                            "label": "Pentester Lead",
                            "phase": "recon",
                        },
                        {
                            "id": "n2",
                            "agent_id": "security-researcher",
                            "x": 200,
                            "y": 120,
                            "label": "Researcher",
                            "phase": "recon",
                        },
                        {
                            "id": "n3",
                            "agent_id": "exploit-dev",
                            "x": 600,
                            "y": 120,
                            "label": "Exploit Dev",
                            "phase": "exploitation",
                        },
                        # Blue Team
                        {
                            "id": "n4",
                            "agent_id": "security-architect",
                            "x": 100,
                            "y": 240,
                            "label": "Security Architect",
                            "phase": "threat-model",
                        },
                        {
                            "id": "n5",
                            "agent_id": "threat-analyst",
                            "x": 400,
                            "y": 240,
                            "label": "Threat Analyst",
                            "phase": "threat-model",
                        },
                        {
                            "id": "n6",
                            "agent_id": "secops-engineer",
                            "x": 700,
                            "y": 240,
                            "label": "SecOps",
                            "phase": "deploy-secure",
                        },
                        # Governance
                        {
                            "id": "n7",
                            "agent_id": "ciso",
                            "x": 250,
                            "y": 360,
                            "label": "CISO",
                            "phase": "security-review",
                        },
                        {
                            "id": "n8",
                            "agent_id": "compliance_officer",
                            "x": 550,
                            "y": 360,
                            "label": "Compliance",
                            "phase": "security-review",
                        },
                        # Dev Team
                        {
                            "id": "n9",
                            "agent_id": "security-dev-lead",
                            "x": 400,
                            "y": 480,
                            "label": "Security Dev Lead",
                            "phase": "remediation",
                        },
                        {
                            "id": "n10",
                            "agent_id": "security-backend-dev",
                            "x": 200,
                            "y": 580,
                            "label": "Backend Dev",
                            "phase": "remediation",
                        },
                        {
                            "id": "n11",
                            "agent_id": "security-frontend-dev",
                            "x": 400,
                            "y": 580,
                            "label": "Frontend Dev",
                            "phase": "remediation",
                        },
                        {
                            "id": "n12",
                            "agent_id": "qa-security",
                            "x": 600,
                            "y": 580,
                            "label": "QA Security",
                            "phase": "verification",
                        },
                    ],
                    "edges": [
                        # Phase 1: Recon
                        {
                            "from": "n1",
                            "to": "n2",
                            "label": "recon OSINT",
                            "color": "#ef4444",
                        },
                        {
                            "from": "n1",
                            "to": "n3",
                            "label": "recon exploit",
                            "color": "#ef4444",
                        },
                        # Phase 2: Threat Model (network/debate)
                        {
                            "from": "n2",
                            "to": "n4",
                            "label": "surface",
                            "color": "#f97316",
                        },
                        {
                            "from": "n2",
                            "to": "n5",
                            "label": "findings",
                            "color": "#f97316",
                        },
                        {
                            "from": "n1",
                            "to": "n5",
                            "label": "vecteurs",
                            "color": "#f97316",
                        },
                        {
                            "from": "n4",
                            "to": "n5",
                            "label": "défenses",
                            "color": "#3b82f6",
                        },
                        {
                            "from": "n5",
                            "to": "n1",
                            "label": "priorités",
                            "color": "#8b5cf6",
                        },
                        # Phase 3: Exploitation
                        {
                            "from": "n1",
                            "to": "n3",
                            "label": "exploit",
                            "color": "#dc2626",
                        },
                        {"from": "n3", "to": "n5", "label": "CVSS", "color": "#dc2626"},
                        # Phase 4: Report → Phase 5: Review
                        {
                            "from": "n5",
                            "to": "n7",
                            "label": "rapport",
                            "color": "#fbbf24",
                        },
                        {
                            "from": "n5",
                            "to": "n8",
                            "label": "compliance?",
                            "color": "#fbbf24",
                        },
                        {
                            "from": "n4",
                            "to": "n7",
                            "label": "recommandations",
                            "color": "#3b82f6",
                        },
                        # Phase 6: Remediation
                        {
                            "from": "n7",
                            "to": "n9",
                            "label": "GO fix",
                            "color": "#22c55e",
                        },
                        {
                            "from": "n9",
                            "to": "n10",
                            "label": "fix backend",
                            "color": "#22c55e",
                        },
                        {
                            "from": "n9",
                            "to": "n11",
                            "label": "fix frontend",
                            "color": "#22c55e",
                        },
                        {
                            "from": "n9",
                            "to": "n12",
                            "label": "validate PR",
                            "color": "#22c55e",
                        },
                        # Phase 7: Verification
                        {
                            "from": "n10",
                            "to": "n12",
                            "label": "PR ready",
                            "color": "#10b981",
                        },
                        {
                            "from": "n11",
                            "to": "n12",
                            "label": "PR ready",
                            "color": "#10b981",
                        },
                        {
                            "from": "n12",
                            "to": "n3",
                            "label": "re-exploit?",
                            "color": "#a78bfa",
                        },
                        {
                            "from": "n3",
                            "to": "n12",
                            "label": "exploit fails",
                            "color": "#10b981",
                        },
                        {
                            "from": "n12",
                            "to": "n8",
                            "label": "compliance OK?",
                            "color": "#64748b",
                        },
                        # Phase 8: Deploy
                        {
                            "from": "n8",
                            "to": "n6",
                            "label": "approved",
                            "color": "#06b6d4",
                        },
                        {
                            "from": "n12",
                            "to": "n6",
                            "label": "QA GO",
                            "color": "#10b981",
                        },
                        {
                            "from": "n6",
                            "to": "n7",
                            "label": "deployed",
                            "color": "#10b981",
                        },
                        {
                            "from": "n6",
                            "to": "n1",
                            "label": "monitoring",
                            "color": "#06b6d4",
                        },
                    ],
                },
                "agents_permissions": {
                    "pentester-lead": {
                        "can_veto": True,
                        "veto_level": "STRONG",
                        "can_delegate": True,
                    },
                    "ciso": {
                        "can_veto": True,
                        "veto_level": "ABSOLUTE",
                        "can_approve": True,
                    },
                    "compliance_officer": {
                        "can_veto": True,
                        "veto_level": "STRONG",
                        "can_approve": True,
                    },
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
            icon="heart",
            is_builtin=True,
            phases=[
                WorkflowPhase(
                    id="rgpd-audit",
                    pattern_id="sequential",
                    name="Audit RGPD & Privacy",
                    description="La DPO Margaux Leroy audite la conformité RGPD: "
                    "base légale des traitements, minimisation, durées de conservation, "
                    "droits des personnes (accès, effacement, portabilité), PIA si nécessaire. "
                    "Le Juriste complète sur les transferts hors UE et sous-traitants. "
                    "Web search for latest CNIL decisions.",
                    gate="always",
                    config={"agents": ["rse-dpo", "rse-juriste"]},
                ),
                WorkflowPhase(
                    id="legal-audit",
                    pattern_id="sequential",
                    name="Audit Juridique Numérique",
                    description="Le Juriste Étienne Vasseur audite la conformité: "
                    "DSA (modération, transparence), DMA (interopérabilité), "
                    "AI Act (classification risque IA), ePrivacy (cookies, traceurs), "
                    "LCEN (mentions légales), CGU/CGV (clauses abusives), "
                    "propriété intellectuelle (licences open source). "
                    "Veille sur les dernières évolutions réglementaires EU.",
                    gate="always",
                    config={"agents": ["rse-juriste", "rse-dpo"]},
                ),
                WorkflowPhase(
                    id="green-it-audit",
                    pattern_id="network",
                    name="Audit Green IT & Éco-conception",
                    description="Débat entre l'Expert NR Tristan Beaumont et l'Expert Éco-conception "
                    "Raphaël Morin. RGESN (79 critères), poids des pages, bundle JS, "
                    "requêtes optimisées, hébergement vert, dimensionnement infrastructure. "
                    "Mesures: EcoIndex, Lighthouse, Website Carbon Calculator. "
                    "Propositions sobres et budget carbone par feature.",
                    gate="always",
                    config={"agents": ["rse-nr", "rse-eco", "rse-manager"]},
                ),
                WorkflowPhase(
                    id="a11y-audit",
                    pattern_id="sequential",
                    name="Audit Accessibilité — RGAA & WCAG",
                    description="Noémie Garnier audite selon RGAA 4.1 (106 critères) et WCAG 2.2 AA. "
                    "Contraste, navigation clavier, lecteur d'écran (NVDA, VoiceOver), "
                    "formulaires, images alt, focus visible, zoom 200%. "
                    "Test avec axe-core, pa11y, et manuellement. "
                    "Directive EAA (European Accessibility Act) applicable juin 2025.",
                    gate="always",
                    config={"agents": ["rse-a11y", "accessibility_expert"]},
                ),
                WorkflowPhase(
                    id="ethique-ia-audit",
                    pattern_id="network",
                    name="Audit Éthique IA & Biais",
                    description="Aïssatou Diallo audite les systèmes IA: "
                    "classification AI Act, biais (disparate impact, equal opportunity), "
                    "explicabilité (SHAP, LIME), transparence, human oversight. "
                    "Avec le ML Engineer pour les aspects techniques. "
                    "Veille AI Act articles et guidelines HLEG via web.",
                    gate="always",
                    config={"agents": ["rse-ethique-ia", "ml_engineer", "rse-manager"]},
                ),
                WorkflowPhase(
                    id="social-audit",
                    pattern_id="sequential",
                    name="Audit Social & Inclusion",
                    description="Ibrahim Keïta audite l'impact social: "
                    "diversité équipes (genre, origines, handicap, index Pénicaud), "
                    "conditions de travail IT (charge cognitive, on-call equity), "
                    "inclusion produit (illectronisme, fracture numérique). "
                    "Avec l'experte accessibilité pour l'inclusion numérique.",
                    gate="always",
                    config={"agents": ["rse-audit-social", "rse-a11y"]},
                ),
                WorkflowPhase(
                    id="rse-synthesis",
                    pattern_id="human-in-the-loop",
                    name="Synthèse RSE — GO/NOGO",
                    description="La Directrice RSE Sabrina Okafor consolide tous les audits. "
                    "Score ESG global, conformité par pilier (E/S/G). "
                    "Le Juriste confirme les risques juridiques. "
                    "La DPO valide la conformité RGPD. "
                    "Checkpoint: GO (conforme), NOGO (non-conformités critiques), "
                    "PIVOT (plan de remediation avec jalons).",
                    gate="checkpoint",
                    config={
                        "agents": [
                            "rse-manager",
                            "rse-dpo",
                            "rse-juriste",
                            "rse-ethique-ia",
                        ]
                    },
                ),
            ],
            config={
                "orchestrator": "rse-manager",
                "graph": {
                    "pattern": "sequential",
                    "nodes": [
                        {
                            "id": "r1",
                            "agent_id": "rse-dpo",
                            "x": 100,
                            "y": 30,
                            "label": "DPO",
                            "phase": "rgpd-audit",
                        },
                        {
                            "id": "r2",
                            "agent_id": "rse-juriste",
                            "x": 350,
                            "y": 30,
                            "label": "Juriste",
                            "phase": "legal-audit",
                        },
                        {
                            "id": "r3",
                            "agent_id": "rse-nr",
                            "x": 100,
                            "y": 150,
                            "label": "Expert NR",
                            "phase": "green-it-audit",
                        },
                        {
                            "id": "r4",
                            "agent_id": "rse-eco",
                            "x": 350,
                            "y": 150,
                            "label": "Éco-conception",
                            "phase": "green-it-audit",
                        },
                        {
                            "id": "r5",
                            "agent_id": "rse-a11y",
                            "x": 100,
                            "y": 270,
                            "label": "A11Y Lead",
                            "phase": "a11y-audit",
                        },
                        {
                            "id": "r6",
                            "agent_id": "accessibility_expert",
                            "x": 350,
                            "y": 270,
                            "label": "Expert A11Y",
                            "phase": "a11y-audit",
                        },
                        {
                            "id": "r7",
                            "agent_id": "rse-ethique-ia",
                            "x": 100,
                            "y": 390,
                            "label": "Éthique IA",
                            "phase": "ethique-ia-audit",
                        },
                        {
                            "id": "r8",
                            "agent_id": "ml_engineer",
                            "x": 350,
                            "y": 390,
                            "label": "ML Engineer",
                            "phase": "ethique-ia-audit",
                        },
                        {
                            "id": "r9",
                            "agent_id": "rse-audit-social",
                            "x": 225,
                            "y": 500,
                            "label": "Audit Social",
                            "phase": "social-audit",
                        },
                        {
                            "id": "r10",
                            "agent_id": "rse-manager",
                            "x": 225,
                            "y": 620,
                            "label": "Dir. RSE",
                            "phase": "rse-synthesis",
                        },
                    ],
                    "edges": [
                        {
                            "from": "r1",
                            "to": "r2",
                            "label": "privacy → legal",
                            "color": "#8b5cf6",
                        },
                        {
                            "from": "r2",
                            "to": "r3",
                            "label": "compliant → green",
                            "color": "#22c55e",
                        },
                        {
                            "from": "r3",
                            "to": "r4",
                            "label": "NR ↔ éco",
                            "color": "#22c55e",
                        },
                        {
                            "from": "r4",
                            "to": "r5",
                            "label": "green → a11y",
                            "color": "#06b6d4",
                        },
                        {
                            "from": "r5",
                            "to": "r6",
                            "label": "lead ↔ expert",
                            "color": "#06b6d4",
                        },
                        {
                            "from": "r6",
                            "to": "r7",
                            "label": "a11y → éthique",
                            "color": "#f59e0b",
                        },
                        {
                            "from": "r7",
                            "to": "r8",
                            "label": "éthique ↔ ML",
                            "color": "#f59e0b",
                        },
                        {
                            "from": "r8",
                            "to": "r9",
                            "label": "IA → social",
                            "color": "#ec4899",
                        },
                        {
                            "from": "r9",
                            "to": "r10",
                            "label": "all → synthèse",
                            "color": "#8b5cf6",
                        },
                        {
                            "from": "r1",
                            "to": "r10",
                            "label": "RGPD report",
                            "color": "#8b5cf6",
                        },
                        {
                            "from": "r3",
                            "to": "r10",
                            "label": "Green report",
                            "color": "#22c55e",
                        },
                        {
                            "from": "r5",
                            "to": "r10",
                            "label": "A11Y report",
                            "color": "#06b6d4",
                        },
                        {
                            "from": "r7",
                            "to": "r10",
                            "label": "Ethics report",
                            "color": "#f59e0b",
                        },
                    ],
                },
                "agents_permissions": {
                    "rse-manager": {
                        "can_veto": True,
                        "veto_level": "STRONG",
                        "can_delegate": True,
                        "can_approve": True,
                    },
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
                        "agents": [
                            "rte",
                            "product-manager-art",
                            "system-architect-art",
                        ],
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
                        "agents": [
                            "rte",
                            "ft-auth-lead",
                            "ft-booking-lead",
                            "ft-payment-lead",
                            "ft-admin-lead",
                            "ft-user-lead",
                            "ft-infra-lead",
                            "ft-e2e-lead",
                            "ft-proto-lead",
                        ],
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
                        "agents": [
                            "ft-auth-lead",
                            "ft-booking-lead",
                            "ft-payment-lead",
                            "ft-admin-lead",
                            "ft-user-lead",
                            "ft-infra-lead",
                            "ft-e2e-lead",
                            "ft-proto-lead",
                        ],
                        "max_concurrent": 4,
                    },
                ),
                WorkflowPhase(
                    id="build-verify",
                    pattern_id="sequential",
                    name="Build & Verify",
                    description=(
                        "DevOps vérifie que le code compile: install deps, build, run tests. "
                        "Crée les fichiers manquants (requirements.txt, go.mod, Dockerfile). "
                        "Le projet doit builder from scratch. Si build fail, corriger le code."
                    ),
                    gate="no_veto",
                    config={
                        "agents": ["ft-infra-lead", "ft-e2e-lead"],
                        "leader": "ft-infra-lead",
                    },
                ),
                WorkflowPhase(
                    id="system-integration",
                    pattern_id="aggregator",
                    name="System Integration",
                    description="System Architect agrège les résultats. Merge branches, build global, tests cross-domain.",
                    gate="all_approved",
                    config={
                        "agents": [
                            "system-architect-art",
                            "ft-e2e-lead",
                            "ft-proto-lead",
                            "ft-infra-lead",
                        ],
                    },
                ),
                WorkflowPhase(
                    id="pi-review-release",
                    pattern_id="human-in-the-loop",
                    name="PI Review & Release",
                    description="Demo → PM review → Staging → E2E global → Canary → Prod. GO/NOGO checkpoint.",
                    gate="checkpoint",
                    config={
                        "agents": [
                            "product-manager-art",
                            "rte",
                            "system-architect-art",
                            "ft-e2e-lead",
                        ],
                    },
                ),
            ],
            config={
                "graph": {
                    "nodes": [
                        {
                            "id": "n1",
                            "agent_id": "rte",
                            "x": 400,
                            "y": 20,
                            "label": "RTE Marc",
                            "phase": "pi-planning",
                        },
                        {
                            "id": "n2",
                            "agent_id": "product-manager-art",
                            "x": 200,
                            "y": 20,
                            "label": "PM Isabelle",
                            "phase": "pi-planning",
                        },
                        {
                            "id": "n3",
                            "agent_id": "system-architect-art",
                            "x": 600,
                            "y": 20,
                            "label": "Archi Catherine",
                            "phase": "pi-planning",
                        },
                        {
                            "id": "n4",
                            "agent_id": "ft-auth-lead",
                            "x": 50,
                            "y": 170,
                            "label": "Auth Nicolas",
                            "phase": "feature-planning",
                        },
                        {
                            "id": "n5",
                            "agent_id": "ft-booking-lead",
                            "x": 200,
                            "y": 170,
                            "label": "Booking Antoine",
                            "phase": "feature-planning",
                        },
                        {
                            "id": "n6",
                            "agent_id": "ft-payment-lead",
                            "x": 350,
                            "y": 170,
                            "label": "Payment Caroline",
                            "phase": "feature-planning",
                        },
                        {
                            "id": "n7",
                            "agent_id": "ft-admin-lead",
                            "x": 500,
                            "y": 170,
                            "label": "Admin Olivier",
                            "phase": "feature-planning",
                        },
                        {
                            "id": "n8",
                            "agent_id": "ft-user-lead",
                            "x": 650,
                            "y": 170,
                            "label": "User Sarah",
                            "phase": "feature-planning",
                        },
                        {
                            "id": "n9",
                            "agent_id": "ft-infra-lead",
                            "x": 50,
                            "y": 320,
                            "label": "Infra Francois",
                            "phase": "sprint-execution",
                        },
                        {
                            "id": "n10",
                            "agent_id": "ft-e2e-lead",
                            "x": 250,
                            "y": 320,
                            "label": "E2E Virginie",
                            "phase": "sprint-execution",
                        },
                        {
                            "id": "n11",
                            "agent_id": "ft-proto-lead",
                            "x": 450,
                            "y": 320,
                            "label": "Proto JB",
                            "phase": "sprint-execution",
                        },
                        {
                            "id": "n12",
                            "agent_id": "system-architect-art",
                            "x": 400,
                            "y": 470,
                            "label": "Integration",
                            "phase": "system-integration",
                        },
                        {
                            "id": "n13",
                            "agent_id": "product-manager-art",
                            "x": 400,
                            "y": 570,
                            "label": "PI Review",
                            "phase": "pi-review-release",
                        },
                    ],
                    "edges": [
                        {
                            "from": "n2",
                            "to": "n1",
                            "label": "vision",
                            "color": "#bc8cff",
                        },
                        {"from": "n3", "to": "n1", "label": "arch", "color": "#58a6ff"},
                        {
                            "from": "n1",
                            "to": "n2",
                            "label": "feedback",
                            "color": "#d29922",
                        },
                        {
                            "from": "n1",
                            "to": "n3",
                            "label": "feedback",
                            "color": "#d29922",
                        },
                        {
                            "from": "n1",
                            "to": "n4",
                            "label": "delegate",
                            "color": "#f97316",
                        },
                        {
                            "from": "n1",
                            "to": "n5",
                            "label": "delegate",
                            "color": "#22c55e",
                        },
                        {
                            "from": "n1",
                            "to": "n6",
                            "label": "delegate",
                            "color": "#eab308",
                        },
                        {
                            "from": "n1",
                            "to": "n7",
                            "label": "delegate",
                            "color": "#a855f7",
                        },
                        {
                            "from": "n1",
                            "to": "n8",
                            "label": "delegate",
                            "color": "#06b6d4",
                        },
                        {
                            "from": "n4",
                            "to": "n9",
                            "label": "infra",
                            "color": "#ef4444",
                        },
                        {"from": "n5", "to": "n10", "label": "e2e", "color": "#ec4899"},
                        {
                            "from": "n6",
                            "to": "n11",
                            "label": "proto",
                            "color": "#64748b",
                        },
                        {"from": "n7", "to": "n10", "label": "e2e", "color": "#ec4899"},
                        {"from": "n8", "to": "n10", "label": "e2e", "color": "#ec4899"},
                        {
                            "from": "n9",
                            "to": "n12",
                            "label": "merge",
                            "color": "#58a6ff",
                        },
                        {
                            "from": "n10",
                            "to": "n12",
                            "label": "tests",
                            "color": "#ec4899",
                        },
                        {
                            "from": "n11",
                            "to": "n12",
                            "label": "schemas",
                            "color": "#64748b",
                        },
                        {
                            "from": "n4",
                            "to": "n12",
                            "label": "merge",
                            "color": "#f97316",
                        },
                        {
                            "from": "n5",
                            "to": "n12",
                            "label": "merge",
                            "color": "#22c55e",
                        },
                        {
                            "from": "n6",
                            "to": "n12",
                            "label": "merge",
                            "color": "#eab308",
                        },
                        {
                            "from": "n12",
                            "to": "n13",
                            "label": "release",
                            "color": "#d29922",
                        },
                    ],
                },
                "agents_permissions": {
                    "rte": {
                        "can_delegate": True,
                        "can_veto": True,
                        "veto_level": "strong",
                    },
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
                        "max_iterations": 3,
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
                        "max_iterations": 2,
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
                        {
                            "id": "n1",
                            "agent_id": "system-architect-art",
                            "x": 400,
                            "y": 20,
                            "label": "Design",
                            "phase": "feature-design",
                        },
                        {
                            "id": "n2",
                            "agent_id": "ft-auth-lead",
                            "x": 200,
                            "y": 150,
                            "label": "TDD Dev 1",
                            "phase": "tdd-sprint",
                        },
                        {
                            "id": "n3",
                            "agent_id": "ft-auth-dev1",
                            "x": 400,
                            "y": 150,
                            "label": "TDD Dev 2",
                            "phase": "tdd-sprint",
                        },
                        {
                            "id": "n4",
                            "agent_id": "ft-auth-dev2",
                            "x": 600,
                            "y": 150,
                            "label": "TDD Dev 3",
                            "phase": "tdd-sprint",
                        },
                        {
                            "id": "n5",
                            "agent_id": "system-architect-art",
                            "x": 400,
                            "y": 280,
                            "label": "Review",
                            "phase": "adversarial-review",
                        },
                        {
                            "id": "n6",
                            "agent_id": "ft-e2e-api",
                            "x": 300,
                            "y": 380,
                            "label": "E2E API",
                            "phase": "feature-e2e",
                        },
                        {
                            "id": "n7",
                            "agent_id": "ft-e2e-ihm",
                            "x": 500,
                            "y": 380,
                            "label": "E2E IHM",
                            "phase": "feature-e2e",
                        },
                        {
                            "id": "n8",
                            "agent_id": "ft-infra-lead",
                            "x": 400,
                            "y": 480,
                            "label": "Deploy",
                            "phase": "feature-deploy",
                        },
                    ],
                    "edges": [
                        {
                            "from": "n1",
                            "to": "n2",
                            "label": "stories",
                            "color": "#58a6ff",
                        },
                        {
                            "from": "n1",
                            "to": "n3",
                            "label": "stories",
                            "color": "#58a6ff",
                        },
                        {
                            "from": "n1",
                            "to": "n4",
                            "label": "stories",
                            "color": "#58a6ff",
                        },
                        {"from": "n2", "to": "n5", "label": "code", "color": "#3fb950"},
                        {"from": "n3", "to": "n5", "label": "code", "color": "#3fb950"},
                        {"from": "n4", "to": "n5", "label": "code", "color": "#3fb950"},
                        {
                            "from": "n5",
                            "to": "n6",
                            "label": "approved",
                            "color": "#ec4899",
                        },
                        {
                            "from": "n5",
                            "to": "n7",
                            "label": "approved",
                            "color": "#ec4899",
                        },
                        {"from": "n6", "to": "n8", "label": "pass", "color": "#d29922"},
                        {"from": "n7", "to": "n8", "label": "pass", "color": "#d29922"},
                    ],
                },
            },
        ),
    )

    # ── Mobile App Epic Workflows ──

    builtins.append(
        WorkflowDef(
            id="mobile-ios-epic",
            name="Epic iOS App (SwiftUI)",
            description="Full Epic workflow for native iOS app: Architecture → Networking → Features → Tests → Integration.",
            icon="smartphone",
            is_builtin=True,
            phases=[
                WorkflowPhase(
                    id="ios-archi",
                    pattern_id="aggregator",
                    name="Architecture & UX",
                    description="Mobile architect + UX define app structure, navigation, API contract",
                    gate="always",
                    config={"agents": ["mobile_archi", "mobile_ux", "mobile_ios_lead"]},
                ),
                WorkflowPhase(
                    id="ios-network",
                    pattern_id="hierarchical",
                    name="Networking Layer",
                    description="Lead iOS delegates: APIClient, SSEClient, DTOs, AuthManager to network dev",
                    gate="always",
                    config={
                        "agents": [
                            "mobile_ios_lead",
                            "mobile_ios_dev_net",
                            "mobile_ios_qa",
                        ]
                    },
                ),
                WorkflowPhase(
                    id="ios-features",
                    pattern_id="hierarchical",
                    name="Features Sprint",
                    description="Lead delegates UI screens to dev: Dashboard, Missions, Agents, Chat, Ideation",
                    gate="always",
                    config={
                        "agents": [
                            "mobile_ios_lead",
                            "mobile_ios_dev_ui",
                            "mobile_ios_dev_net",
                        ]
                    },
                ),
                WorkflowPhase(
                    id="ios-tests",
                    pattern_id="loop",
                    name="Testing & QA",
                    description="QA writes XCTest + Swift Testing, validates coverage > 80%, accessibility audit",
                    gate="always",
                    config={
                        "agents": ["mobile_ios_qa", "mobile_ios_lead"],
                        "max_iterations": 3,
                    },
                ),
                WorkflowPhase(
                    id="ios-integration",
                    pattern_id="sequential",
                    name="Integration & Polish",
                    description="Final integration: navigation flows, dark mode, error states, app shell",
                    gate="always",
                    config={
                        "agents": [
                            "mobile_ios_lead",
                            "mobile_ios_dev_ui",
                            "mobile_ios_qa",
                        ]
                    },
                ),
            ],
            config={
                "type": "epic",
                "stack": "swift-swiftui",
                "graph": {
                    "nodes": [
                        {
                            "id": "n1",
                            "agent_id": "mobile_archi",
                            "x": 300,
                            "y": 20,
                            "label": "Archi",
                            "phase": "ios-archi",
                        },
                        {
                            "id": "n2",
                            "agent_id": "mobile_ux",
                            "x": 500,
                            "y": 20,
                            "label": "UX",
                            "phase": "ios-archi",
                        },
                        {
                            "id": "n3",
                            "agent_id": "mobile_ios_lead",
                            "x": 400,
                            "y": 130,
                            "label": "Lead iOS",
                            "phase": "ios-network",
                        },
                        {
                            "id": "n4",
                            "agent_id": "mobile_ios_dev_net",
                            "x": 250,
                            "y": 240,
                            "label": "Dev Network",
                            "phase": "ios-network",
                        },
                        {
                            "id": "n5",
                            "agent_id": "mobile_ios_dev_ui",
                            "x": 550,
                            "y": 240,
                            "label": "Dev UI",
                            "phase": "ios-features",
                        },
                        {
                            "id": "n6",
                            "agent_id": "mobile_ios_qa",
                            "x": 400,
                            "y": 350,
                            "label": "QA iOS",
                            "phase": "ios-tests",
                        },
                    ],
                    "edges": [
                        {
                            "from": "n1",
                            "to": "n3",
                            "label": "architecture",
                            "color": "#58a6ff",
                        },
                        {
                            "from": "n2",
                            "to": "n3",
                            "label": "ux specs",
                            "color": "#ec4899",
                        },
                        {
                            "from": "n3",
                            "to": "n4",
                            "label": "networking",
                            "color": "#3fb950",
                        },
                        {
                            "from": "n3",
                            "to": "n5",
                            "label": "features",
                            "color": "#3fb950",
                        },
                        {"from": "n4", "to": "n6", "label": "test", "color": "#d29922"},
                        {"from": "n5", "to": "n6", "label": "test", "color": "#d29922"},
                    ],
                },
            },
        ),
    )

    builtins.append(
        WorkflowDef(
            id="mobile-android-epic",
            name="Epic Android App (Kotlin/Compose)",
            description="Full Epic workflow for native Android app: Architecture → Networking → Features → Tests → Integration. Build + emulator tests via android-builder container.",
            icon="smartphone",
            is_builtin=True,
            phases=[
                WorkflowPhase(
                    id="android-archi",
                    pattern_id="aggregator",
                    name="Architecture & UX",
                    description="Mobile architect + UX define app structure, navigation, API contract",
                    gate="always",
                    config={
                        "agents": ["mobile_archi", "mobile_ux", "mobile_android_lead"]
                    },
                ),
                WorkflowPhase(
                    id="android-network",
                    pattern_id="hierarchical",
                    name="Networking Layer",
                    description="Lead Android delegates: ApiClient, SseClient, DTOs, AuthManager to network dev",
                    gate="always",
                    config={
                        "agents": [
                            "mobile_android_lead",
                            "mobile_android_dev_net",
                            "mobile_android_qa",
                        ]
                    },
                ),
                WorkflowPhase(
                    id="android-features",
                    pattern_id="hierarchical",
                    name="Features Sprint",
                    description="Lead delegates Compose screens: Dashboard, Missions, Agents, Chat, Ideation",
                    gate="always",
                    config={
                        "agents": [
                            "mobile_android_lead",
                            "mobile_android_dev_ui",
                            "mobile_android_dev_net",
                        ]
                    },
                ),
                WorkflowPhase(
                    id="android-tests",
                    pattern_id="loop",
                    name="Testing & QA",
                    description="QA writes JUnit + Compose tests, runs android_build + android_test + android_emulator_test, coverage > 80%",
                    gate="always",
                    config={
                        "agents": ["mobile_android_qa", "mobile_android_lead"],
                        "max_iterations": 3,
                    },
                ),
                WorkflowPhase(
                    id="android-integration",
                    pattern_id="sequential",
                    name="Integration & Polish",
                    description="Final: navigation flows, Material 3 theming, error states, app shell. Run android_lint.",
                    gate="always",
                    config={
                        "agents": [
                            "mobile_android_lead",
                            "mobile_android_dev_ui",
                            "mobile_android_qa",
                        ]
                    },
                ),
            ],
            config={
                "type": "epic",
                "stack": "kotlin-compose",
                "graph": {
                    "nodes": [
                        {
                            "id": "n1",
                            "agent_id": "mobile_archi",
                            "x": 300,
                            "y": 20,
                            "label": "Archi",
                            "phase": "android-archi",
                        },
                        {
                            "id": "n2",
                            "agent_id": "mobile_ux",
                            "x": 500,
                            "y": 20,
                            "label": "UX",
                            "phase": "android-archi",
                        },
                        {
                            "id": "n3",
                            "agent_id": "mobile_android_lead",
                            "x": 400,
                            "y": 130,
                            "label": "Lead Android",
                            "phase": "android-network",
                        },
                        {
                            "id": "n4",
                            "agent_id": "mobile_android_dev_net",
                            "x": 250,
                            "y": 240,
                            "label": "Dev Network",
                            "phase": "android-network",
                        },
                        {
                            "id": "n5",
                            "agent_id": "mobile_android_dev_ui",
                            "x": 550,
                            "y": 240,
                            "label": "Dev UI",
                            "phase": "android-features",
                        },
                        {
                            "id": "n6",
                            "agent_id": "mobile_android_qa",
                            "x": 400,
                            "y": 350,
                            "label": "QA Android",
                            "phase": "android-tests",
                        },
                    ],
                    "edges": [
                        {
                            "from": "n1",
                            "to": "n3",
                            "label": "architecture",
                            "color": "#58a6ff",
                        },
                        {
                            "from": "n2",
                            "to": "n3",
                            "label": "ux specs",
                            "color": "#ec4899",
                        },
                        {
                            "from": "n3",
                            "to": "n4",
                            "label": "networking",
                            "color": "#3fb950",
                        },
                        {
                            "from": "n3",
                            "to": "n5",
                            "label": "features",
                            "color": "#3fb950",
                        },
                        {"from": "n4", "to": "n6", "label": "test", "color": "#d29922"},
                        {"from": "n5", "to": "n6", "label": "test", "color": "#d29922"},
                    ],
                },
            },
        ),
    )

    # ── TMA Auto-Heal Workflow ──────────────────────────────────────
    builtins.append(
        WorkflowDef(
            id="tma-autoheal",
            name="TMA Auto-Heal",
            description="Tierce Maintenance Applicative — auto-diagnose and fix platform errors",
            icon="🔧",
            is_builtin=True,
            phases=[
                WorkflowPhase(
                    id="diagnose",
                    pattern_id="hierarchical",
                    name="Diagnostic",
                    description="Analyze error logs, stack traces, and incident context to identify root cause",
                    gate="Root cause identified and documented",
                    config={"agents": ["brain", "architecte", "sre"]},
                ),
                WorkflowPhase(
                    id="fix",
                    pattern_id="adversarial-pair",
                    name="Fix Implementation",
                    description="Implement the fix with TDD: write test → fix code → validate",
                    gate="Fix implemented and all tests pass",
                    config={"agents": ["lead_dev", "testeur"]},
                ),
                WorkflowPhase(
                    id="verify",
                    pattern_id="sequential",
                    name="Verification",
                    description="Run regression tests, check no new incidents introduced",
                    gate="Zero regressions, fix verified in staging",
                    config={"agents": ["testeur", "sre"]},
                ),
                WorkflowPhase(
                    id="close",
                    pattern_id="solo",
                    name="Resolution",
                    description="Document fix, close incidents, update runbook if needed",
                    gate="Incidents resolved, knowledge base updated",
                    config={"agents": ["release_train_engineer"]},
                ),
            ],
            config={
                "autoheal": True,
                "max_duration_minutes": 30,
                "auto_rollback": True,
                "graph": {
                    "nodes": [
                        {
                            "id": "n1",
                            "agent_id": "brain",
                            "x": 100,
                            "y": 150,
                            "label": "Brain Diag",
                            "phase": "diagnose",
                        },
                        {
                            "id": "n2",
                            "agent_id": "lead_dev",
                            "x": 300,
                            "y": 100,
                            "label": "Fix Dev",
                            "phase": "fix",
                        },
                        {
                            "id": "n3",
                            "agent_id": "testeur",
                            "x": 300,
                            "y": 200,
                            "label": "QA Verify",
                            "phase": "fix",
                        },
                        {
                            "id": "n4",
                            "agent_id": "sre",
                            "x": 500,
                            "y": 150,
                            "label": "SRE Verify",
                            "phase": "verify",
                        },
                        {
                            "id": "n5",
                            "agent_id": "release_train_engineer",
                            "x": 700,
                            "y": 150,
                            "label": "RTE Close",
                            "phase": "close",
                        },
                    ],
                    "edges": [
                        {
                            "from": "n1",
                            "to": "n2",
                            "label": "root cause",
                            "color": "#ef4444",
                        },
                        {
                            "from": "n1",
                            "to": "n3",
                            "label": "test spec",
                            "color": "#f97316",
                        },
                        {"from": "n2", "to": "n4", "label": "fix", "color": "#3fb950"},
                        {
                            "from": "n3",
                            "to": "n4",
                            "label": "test results",
                            "color": "#3fb950",
                        },
                        {
                            "from": "n4",
                            "to": "n5",
                            "label": "verified",
                            "color": "#58a6ff",
                        },
                    ],
                },
            },
        ),
    )

    # ── PI Planning (SAFe cadenced) ──
    builtins.append(
        WorkflowDef(
            id="pi-planning",
            name="PI Planning — SAFe Program Increment",
            description="Planification de l'incrément programme SAFe. Présentation vision → estimation features → capacity planning → engagement équipe → publication du plan PI.",
            icon="calendar",
            is_builtin=True,
            phases=[
                WorkflowPhase(
                    id="pi-vision",
                    pattern_id="sequential",
                    name="Présentation Vision & Backlog",
                    description="Le Product Manager présente la vision produit et le backlog priorisé (WSJF). L'architecte présente le runway technique. Le RTE cadre la capacité disponible.",
                    gate="always",
                    config={
                        "agents": [
                            "product_manager",
                            "enterprise_architect",
                            "release_train_engineer",
                        ]
                    },
                ),
                WorkflowPhase(
                    id="pi-estimation",
                    pattern_id="parallel",
                    name="Estimation Features",
                    description="Les équipes estiment en parallèle les features et identifient les dépendances inter-équipes. Chaque lead évalue la complexité et les risques.",
                    gate="always",
                    config={
                        "agents": [
                            "lead_dev",
                            "plat-lead-dev",
                            "qa_lead",
                            "devops",
                            "securite",
                        ]
                    },
                ),
                WorkflowPhase(
                    id="pi-capacity",
                    pattern_id="aggregator",
                    name="Capacity & Dépendances",
                    description="Le RTE agrège les estimations, identifie les conflits de capacité et les dépendances critiques. Le Lean Portfolio Manager valide l'alignement stratégique.",
                    gate="always",
                    config={
                        "agents": [
                            "release_train_engineer",
                            "lean_portfolio_manager",
                            "scrum_master",
                            "chef_projet",
                        ]
                    },
                ),
                WorkflowPhase(
                    id="pi-commitment",
                    pattern_id="human-in-the-loop",
                    name="Engagement Équipe — GO/NOGO",
                    description="Les équipes s'engagent sur les objectifs du PI. Le comité (CPO, CTO, RTE) valide le plan ou demande des ajustements.",
                    gate="checkpoint",
                    config={
                        "agents": [
                            "strat-cpo",
                            "strat-cto",
                            "release_train_engineer",
                            "product_manager",
                            "scrum_master",
                        ]
                    },
                ),
                WorkflowPhase(
                    id="pi-publish",
                    pattern_id="sequential",
                    name="Publication Plan PI",
                    description="Le plan PI est publié: features engagées, sprints planifiés, jalons identifiés, risques ROAM documentés.",
                    gate="always",
                    config={
                        "agents": [
                            "release_train_engineer",
                            "scrum_master",
                            "tech_writer",
                        ]
                    },
                ),
            ],
            config={
                "graph": {
                    "nodes": [
                        {
                            "id": "n1",
                            "agent_id": "product_manager",
                            "x": 100,
                            "y": 100,
                            "label": "PM Vision",
                            "phase": "pi-vision",
                        },
                        {
                            "id": "n2",
                            "agent_id": "enterprise_architect",
                            "x": 100,
                            "y": 200,
                            "label": "Archi Runway",
                            "phase": "pi-vision",
                        },
                        {
                            "id": "n3",
                            "agent_id": "release_train_engineer",
                            "x": 100,
                            "y": 300,
                            "label": "RTE Cadre",
                            "phase": "pi-vision",
                        },
                        {
                            "id": "n4",
                            "agent_id": "lead_dev",
                            "x": 300,
                            "y": 80,
                            "label": "Lead Estim",
                            "phase": "pi-estimation",
                        },
                        {
                            "id": "n5",
                            "agent_id": "qa_lead",
                            "x": 300,
                            "y": 180,
                            "label": "QA Estim",
                            "phase": "pi-estimation",
                        },
                        {
                            "id": "n6",
                            "agent_id": "devops",
                            "x": 300,
                            "y": 280,
                            "label": "DevOps Estim",
                            "phase": "pi-estimation",
                        },
                        {
                            "id": "n7",
                            "agent_id": "release_train_engineer",
                            "x": 500,
                            "y": 150,
                            "label": "RTE Capacity",
                            "phase": "pi-capacity",
                        },
                        {
                            "id": "n8",
                            "agent_id": "lean_portfolio_manager",
                            "x": 500,
                            "y": 250,
                            "label": "LPM Align",
                            "phase": "pi-capacity",
                        },
                        {
                            "id": "n9",
                            "agent_id": "strat-cpo",
                            "x": 700,
                            "y": 100,
                            "label": "CPO GO/NOGO",
                            "phase": "pi-commitment",
                        },
                        {
                            "id": "n10",
                            "agent_id": "strat-cto",
                            "x": 700,
                            "y": 200,
                            "label": "CTO GO/NOGO",
                            "phase": "pi-commitment",
                        },
                        {
                            "id": "n11",
                            "agent_id": "tech_writer",
                            "x": 900,
                            "y": 150,
                            "label": "Publish",
                            "phase": "pi-publish",
                        },
                    ],
                    "edges": [
                        {
                            "from": "n1",
                            "to": "n4",
                            "label": "backlog",
                            "color": "#7c3aed",
                        },
                        {
                            "from": "n2",
                            "to": "n4",
                            "label": "runway",
                            "color": "#58a6ff",
                        },
                        {
                            "from": "n3",
                            "to": "n7",
                            "label": "capacity",
                            "color": "#f97316",
                        },
                        {
                            "from": "n4",
                            "to": "n7",
                            "label": "estimates",
                            "color": "#3fb950",
                        },
                        {
                            "from": "n5",
                            "to": "n7",
                            "label": "qa effort",
                            "color": "#3fb950",
                        },
                        {
                            "from": "n6",
                            "to": "n7",
                            "label": "infra needs",
                            "color": "#3fb950",
                        },
                        {
                            "from": "n7",
                            "to": "n9",
                            "label": "plan draft",
                            "color": "#7c3aed",
                        },
                        {
                            "from": "n8",
                            "to": "n9",
                            "label": "alignment",
                            "color": "#d29922",
                        },
                        {
                            "from": "n9",
                            "to": "n11",
                            "label": "approved",
                            "color": "#3fb950",
                        },
                        {
                            "from": "n10",
                            "to": "n11",
                            "label": "tech ok",
                            "color": "#3fb950",
                        },
                    ],
                },
            },
        ),
    )

    # ──────────────────────────────────────────────────────────────
    # Audit-gap workflows — covering missing quality dimensions
    # ──────────────────────────────────────────────────────────────

    # 1. Documentation Pipeline (covers: doc-api, doc-user, lisib-doc, lisib-adr, lisib-changelog)
    builtins.append(
        WorkflowDef(
            id="documentation-pipeline",
            name="Documentation Pipeline",
            description="End-to-end documentation generation: API specs, user guides, ADRs, changelog, onboarding docs.",
            icon="📝",
            is_builtin=True,
            phases=[
                WorkflowPhase(
                    id="api-docs",
                    pattern_id="sequential",
                    name="API Documentation",
                    description="Scan all routes/endpoints, generate OpenAPI specs, validate with examples",
                    gate="OpenAPI spec generated and validated",
                    config={"agents": ["doc-writer", "architecte"]},
                ),
                WorkflowPhase(
                    id="adr-capture",
                    pattern_id="sequential",
                    name="ADR Capture",
                    description="Review recent architecture decisions, create/update ADR records in docs/adr/",
                    gate="All pending decisions documented as ADRs",
                    config={"agents": ["adr-writer", "architecte"]},
                ),
                WorkflowPhase(
                    id="changelog-gen",
                    pattern_id="sequential",
                    name="Changelog Generation",
                    description="Analyze git history since last release, generate CHANGELOG.md and release notes",
                    gate="CHANGELOG.md updated with all changes since last tag",
                    config={"agents": ["changelog-gen"]},
                ),
                WorkflowPhase(
                    id="user-guide",
                    pattern_id="sequential",
                    name="User Guide",
                    description="Create/update user-facing documentation: getting started, tutorials, FAQ",
                    gate="User guide covers all major features",
                    config={"agents": ["doc-writer"]},
                ),
                WorkflowPhase(
                    id="onboarding",
                    pattern_id="sequential",
                    name="Developer Onboarding",
                    description="Generate CONTRIBUTING.md, dev setup guide, architecture overview for new developers",
                    gate="New developer can set up and contribute within 30 minutes",
                    config={"agents": ["doc-writer", "lead_dev"]},
                ),
                WorkflowPhase(
                    id="doc-review",
                    pattern_id="adversarial-pair",
                    name="Documentation Review",
                    description="Review all generated docs for accuracy, completeness, and clarity",
                    gate="All docs reviewed and approved",
                    config={"agents": ["doc-writer", "architecte"]},
                ),
            ],
            config={
                "graph": {
                    "nodes": [
                        {
                            "id": "n1",
                            "agent_id": "doc-writer",
                            "x": 100,
                            "y": 150,
                            "label": "API Docs",
                            "phase": "api-docs",
                        },
                        {
                            "id": "n2",
                            "agent_id": "adr-writer",
                            "x": 300,
                            "y": 100,
                            "label": "ADR Capture",
                            "phase": "adr-capture",
                        },
                        {
                            "id": "n3",
                            "agent_id": "changelog-gen",
                            "x": 300,
                            "y": 200,
                            "label": "Changelog",
                            "phase": "changelog-gen",
                        },
                        {
                            "id": "n4",
                            "agent_id": "doc-writer",
                            "x": 500,
                            "y": 100,
                            "label": "User Guide",
                            "phase": "user-guide",
                        },
                        {
                            "id": "n5",
                            "agent_id": "doc-writer",
                            "x": 500,
                            "y": 200,
                            "label": "Onboarding",
                            "phase": "onboarding",
                        },
                        {
                            "id": "n6",
                            "agent_id": "architecte",
                            "x": 700,
                            "y": 150,
                            "label": "Doc Review",
                            "phase": "doc-review",
                        },
                    ],
                    "edges": [
                        {
                            "from": "n1",
                            "to": "n6",
                            "label": "review",
                            "color": "#06b6d4",
                        },
                        {
                            "from": "n2",
                            "to": "n6",
                            "label": "review",
                            "color": "#8b5cf6",
                        },
                        {
                            "from": "n3",
                            "to": "n6",
                            "label": "review",
                            "color": "#f59e0b",
                        },
                        {
                            "from": "n4",
                            "to": "n6",
                            "label": "review",
                            "color": "#06b6d4",
                        },
                        {
                            "from": "n5",
                            "to": "n6",
                            "label": "review",
                            "color": "#06b6d4",
                        },
                    ],
                },
            },
        ),
    )

    # 2. Backup & Disaster Recovery (covers: data-backup)
    builtins.append(
        WorkflowDef(
            id="backup-restore",
            name="Backup & Disaster Recovery",
            description="Automated backup strategy, restore verification, and disaster recovery runbook.",
            icon="💾",
            is_builtin=True,
            phases=[
                WorkflowPhase(
                    id="backup-strategy",
                    pattern_id="sequential",
                    name="Backup Strategy",
                    description="Define RPO/RTO targets, backup types (full/incremental), retention policies",
                    gate="RPO and RTO defined, strategy documented",
                    config={"agents": ["backup-ops", "sre"]},
                ),
                WorkflowPhase(
                    id="backup-impl",
                    pattern_id="sequential",
                    name="Backup Implementation",
                    description="Create backup scripts, cron schedules, cloud storage sync, encryption",
                    gate="Backup scripts created and scheduled",
                    config={"agents": ["backup-ops", "devops"]},
                ),
                WorkflowPhase(
                    id="restore-test",
                    pattern_id="adversarial-pair",
                    name="Restore Verification",
                    description="Test restore procedure, verify data integrity, measure actual RTO",
                    gate="Restore tested successfully, RTO within target",
                    config={"agents": ["backup-ops", "testeur"]},
                ),
                WorkflowPhase(
                    id="dr-runbook",
                    pattern_id="sequential",
                    name="DR Runbook",
                    description="Document disaster recovery procedures, escalation paths, communication plan",
                    gate="DR runbook complete with step-by-step instructions",
                    config={"agents": ["backup-ops", "doc-writer"]},
                ),
            ],
            config={
                "critical": True,
                "schedule": "weekly",
                "graph": {
                    "nodes": [
                        {
                            "id": "n1",
                            "agent_id": "backup-ops",
                            "x": 100,
                            "y": 150,
                            "label": "Strategy",
                            "phase": "backup-strategy",
                        },
                        {
                            "id": "n2",
                            "agent_id": "backup-ops",
                            "x": 300,
                            "y": 150,
                            "label": "Implement",
                            "phase": "backup-impl",
                        },
                        {
                            "id": "n3",
                            "agent_id": "testeur",
                            "x": 500,
                            "y": 150,
                            "label": "Test Restore",
                            "phase": "restore-test",
                        },
                        {
                            "id": "n4",
                            "agent_id": "doc-writer",
                            "x": 700,
                            "y": 150,
                            "label": "DR Runbook",
                            "phase": "dr-runbook",
                        },
                    ],
                    "edges": [
                        {
                            "from": "n1",
                            "to": "n2",
                            "label": "strategy defined",
                            "color": "#ef4444",
                        },
                        {
                            "from": "n2",
                            "to": "n3",
                            "label": "scripts ready",
                            "color": "#f59e0b",
                        },
                        {
                            "from": "n3",
                            "to": "n4",
                            "label": "restore ok",
                            "color": "#3fb950",
                        },
                    ],
                },
            },
        ),
    )

    # 3. Performance Testing (covers: perf-load, perf-optim)
    builtins.append(
        WorkflowDef(
            id="performance-testing",
            name="Performance Testing & Optimization",
            description="Load testing with k6, bottleneck analysis, bundle optimization, SLO validation.",
            icon="⚡",
            is_builtin=True,
            phases=[
                WorkflowPhase(
                    id="perf-plan",
                    pattern_id="sequential",
                    name="Performance Plan",
                    description="Define SLOs, identify critical paths, create test scenarios (smoke/load/stress/soak)",
                    gate="SLOs defined, test scenarios documented",
                    config={"agents": ["perf-tester", "architecte"]},
                ),
                WorkflowPhase(
                    id="load-tests",
                    pattern_id="sequential",
                    name="Load Test Execution",
                    description="Write and run k6 scripts: progressive load 10→100→500→1000 VUs",
                    gate="All load test scenarios executed",
                    config={"agents": ["perf-tester"]},
                ),
                WorkflowPhase(
                    id="bottleneck-analysis",
                    pattern_id="parallel",
                    name="Bottleneck Analysis",
                    description="Analyze results: slow queries (N+1), memory leaks, bundle size, Core Web Vitals",
                    gate="Bottlenecks identified and prioritized",
                    config={
                        "agents": ["perf-tester", "lead_dev", "performance_engineer"]
                    },
                ),
                WorkflowPhase(
                    id="perf-fix",
                    pattern_id="loop",
                    name="Performance Fixes",
                    description="Implement optimizations: query tuning, caching, lazy loading, code splitting",
                    gate="All SLOs met after optimization",
                    config={"agents": ["lead_dev", "perf-tester"], "max_iterations": 5},
                ),
                WorkflowPhase(
                    id="perf-report",
                    pattern_id="sequential",
                    name="Performance Report",
                    description="Generate final report: before/after metrics, recommendations, performance budget",
                    gate="Performance report published",
                    config={"agents": ["perf-tester", "doc-writer"]},
                ),
            ],
            config={
                "graph": {
                    "nodes": [
                        {
                            "id": "n1",
                            "agent_id": "perf-tester",
                            "x": 100,
                            "y": 150,
                            "label": "Plan",
                            "phase": "perf-plan",
                        },
                        {
                            "id": "n2",
                            "agent_id": "perf-tester",
                            "x": 300,
                            "y": 150,
                            "label": "Load Tests",
                            "phase": "load-tests",
                        },
                        {
                            "id": "n3",
                            "agent_id": "lead_dev",
                            "x": 500,
                            "y": 100,
                            "label": "Analysis",
                            "phase": "bottleneck-analysis",
                        },
                        {
                            "id": "n4",
                            "agent_id": "lead_dev",
                            "x": 500,
                            "y": 200,
                            "label": "Fix Loop",
                            "phase": "perf-fix",
                        },
                        {
                            "id": "n5",
                            "agent_id": "doc-writer",
                            "x": 700,
                            "y": 150,
                            "label": "Report",
                            "phase": "perf-report",
                        },
                    ],
                    "edges": [
                        {
                            "from": "n1",
                            "to": "n2",
                            "label": "scenarios ready",
                            "color": "#f97316",
                        },
                        {
                            "from": "n2",
                            "to": "n3",
                            "label": "results",
                            "color": "#f97316",
                        },
                        {
                            "from": "n3",
                            "to": "n4",
                            "label": "bottlenecks",
                            "color": "#ef4444",
                        },
                        {
                            "from": "n4",
                            "to": "n2",
                            "label": "re-test",
                            "color": "#d29922",
                            "style": "dashed",
                        },
                        {
                            "from": "n4",
                            "to": "n5",
                            "label": "SLOs met",
                            "color": "#3fb950",
                        },
                    ],
                },
            },
        ),
    )

    # 4. License Compliance (covers: legal-licences)
    builtins.append(
        WorkflowDef(
            id="license-compliance",
            name="License & SBOM Compliance",
            description="Automated dependency license scanning, SBOM generation, and vulnerability audit.",
            icon="📜",
            is_builtin=True,
            phases=[
                WorkflowPhase(
                    id="dep-scan",
                    pattern_id="parallel",
                    name="Dependency Scan",
                    description="Scan all dependency manifests (package.json, requirements.txt, Cargo.toml, go.mod)",
                    gate="All dependencies inventoried with licenses",
                    config={"agents": ["license-scanner"]},
                ),
                WorkflowPhase(
                    id="license-audit",
                    pattern_id="sequential",
                    name="License Audit",
                    description="Classify licenses (permissive/copyleft/proprietary), flag incompatibilities",
                    gate="No license conflicts detected or exceptions documented",
                    config={"agents": ["license-scanner", "compliance_officer"]},
                ),
                WorkflowPhase(
                    id="sbom-gen",
                    pattern_id="sequential",
                    name="SBOM Generation",
                    description="Generate Software Bill of Materials in SPDX/CycloneDX format",
                    gate="SBOM generated and validated",
                    config={"agents": ["license-scanner"]},
                ),
                WorkflowPhase(
                    id="vuln-check",
                    pattern_id="sequential",
                    name="Vulnerability Check",
                    description="Cross-reference dependencies against CVE databases (NVD, GitHub Advisory)",
                    gate="No critical/high CVEs or mitigation plan in place",
                    config={"agents": ["license-scanner", "securite"]},
                ),
            ],
            config={
                "schedule": "per-release",
                "graph": {
                    "nodes": [
                        {
                            "id": "n1",
                            "agent_id": "license-scanner",
                            "x": 100,
                            "y": 150,
                            "label": "Dep Scan",
                            "phase": "dep-scan",
                        },
                        {
                            "id": "n2",
                            "agent_id": "license-scanner",
                            "x": 300,
                            "y": 100,
                            "label": "License Audit",
                            "phase": "license-audit",
                        },
                        {
                            "id": "n3",
                            "agent_id": "license-scanner",
                            "x": 300,
                            "y": 200,
                            "label": "SBOM",
                            "phase": "sbom-gen",
                        },
                        {
                            "id": "n4",
                            "agent_id": "securite",
                            "x": 500,
                            "y": 150,
                            "label": "CVE Check",
                            "phase": "vuln-check",
                        },
                    ],
                    "edges": [
                        {
                            "from": "n1",
                            "to": "n2",
                            "label": "deps found",
                            "color": "#10b981",
                        },
                        {
                            "from": "n1",
                            "to": "n3",
                            "label": "inventory",
                            "color": "#10b981",
                        },
                        {
                            "from": "n2",
                            "to": "n4",
                            "label": "licenses ok",
                            "color": "#3fb950",
                        },
                        {
                            "from": "n3",
                            "to": "n4",
                            "label": "sbom ready",
                            "color": "#3fb950",
                        },
                    ],
                },
            },
        ),
    )

    # 5. Chaos Engineering Scheduled (covers: stab-chaos)
    builtins.append(
        WorkflowDef(
            id="chaos-scheduled",
            name="Scheduled Chaos Engineering",
            description="Periodic resilience testing: inject failures, verify auto-recovery, validate SLOs under stress.",
            icon="🐒",
            is_builtin=True,
            phases=[
                WorkflowPhase(
                    id="chaos-plan",
                    pattern_id="sequential",
                    name="Chaos Plan",
                    description="Select failure scenarios: network partition, disk full, process kill, latency injection",
                    gate="Chaos scenarios selected with blast radius defined",
                    config={"agents": ["sre", "architecte"]},
                ),
                WorkflowPhase(
                    id="steady-state",
                    pattern_id="sequential",
                    name="Steady State Baseline",
                    description="Capture baseline metrics before chaos: latency, error rate, throughput",
                    gate="Baseline metrics captured and SLOs verified",
                    config={"agents": ["monitoring-ops", "sre"]},
                ),
                WorkflowPhase(
                    id="chaos-inject",
                    pattern_id="sequential",
                    name="Fault Injection",
                    description="Inject planned failures, observe system behavior, monitor auto-recovery",
                    gate="Fault injected, system behavior observed",
                    config={"agents": ["sre"]},
                ),
                WorkflowPhase(
                    id="chaos-observe",
                    pattern_id="parallel",
                    name="Impact Observation",
                    description="Monitor recovery: did autoheal trigger? Did SLOs hold? Any cascading failures?",
                    gate="Recovery behavior documented",
                    config={"agents": ["monitoring-ops", "sre", "perf-tester"]},
                ),
                WorkflowPhase(
                    id="chaos-report",
                    pattern_id="sequential",
                    name="Resilience Report",
                    description="Document findings, update runbooks, create hardening tickets for failures",
                    gate="Resilience report published, action items created",
                    config={"agents": ["sre", "doc-writer"]},
                ),
            ],
            config={
                "schedule": "bi-weekly",
                "blast_radius": "staging",
                "graph": {
                    "nodes": [
                        {
                            "id": "n1",
                            "agent_id": "sre",
                            "x": 100,
                            "y": 150,
                            "label": "Plan",
                            "phase": "chaos-plan",
                        },
                        {
                            "id": "n2",
                            "agent_id": "monitoring-ops",
                            "x": 250,
                            "y": 150,
                            "label": "Baseline",
                            "phase": "steady-state",
                        },
                        {
                            "id": "n3",
                            "agent_id": "sre",
                            "x": 400,
                            "y": 150,
                            "label": "Inject",
                            "phase": "chaos-inject",
                        },
                        {
                            "id": "n4",
                            "agent_id": "monitoring-ops",
                            "x": 550,
                            "y": 150,
                            "label": "Observe",
                            "phase": "chaos-observe",
                        },
                        {
                            "id": "n5",
                            "agent_id": "doc-writer",
                            "x": 700,
                            "y": 150,
                            "label": "Report",
                            "phase": "chaos-report",
                        },
                    ],
                    "edges": [
                        {
                            "from": "n1",
                            "to": "n2",
                            "label": "scenarios",
                            "color": "#ef4444",
                        },
                        {
                            "from": "n2",
                            "to": "n3",
                            "label": "baseline ok",
                            "color": "#3fb950",
                        },
                        {
                            "from": "n3",
                            "to": "n4",
                            "label": "fault active",
                            "color": "#ef4444",
                        },
                        {
                            "from": "n4",
                            "to": "n5",
                            "label": "observed",
                            "color": "#d29922",
                        },
                    ],
                },
            },
        ),
    )

    # 6. Monitoring & Observability Setup (covers: stab-monitoring)
    builtins.append(
        WorkflowDef(
            id="monitoring-setup",
            name="Monitoring & Observability",
            description="Setup monitoring stack: SLIs/SLOs, dashboards, alerting, structured logging, health checks.",
            icon="📊",
            is_builtin=True,
            phases=[
                WorkflowPhase(
                    id="slo-define",
                    pattern_id="network",
                    name="SLI/SLO Definition",
                    description="Define Service Level Indicators and Objectives for each service",
                    gate="SLIs and SLOs documented and agreed upon",
                    config={"agents": ["monitoring-ops", "sre", "architecte"]},
                ),
                WorkflowPhase(
                    id="health-checks",
                    pattern_id="sequential",
                    name="Health Check Endpoints",
                    description="Implement /health, /ready, /live endpoints with dependency checks",
                    gate="All services have health check endpoints",
                    config={"agents": ["monitoring-ops", "lead_dev"]},
                ),
                WorkflowPhase(
                    id="logging-setup",
                    pattern_id="sequential",
                    name="Structured Logging",
                    description="Implement JSON structured logging, correlation IDs, log levels",
                    gate="Structured logging in place with correlation IDs",
                    config={"agents": ["monitoring-ops", "lead_dev"]},
                ),
                WorkflowPhase(
                    id="alerting",
                    pattern_id="sequential",
                    name="Alerting Rules",
                    description="Create alerting rules, escalation policies, PagerDuty/Slack integration",
                    gate="Alerts configured with proper thresholds and routing",
                    config={"agents": ["monitoring-ops", "sre"]},
                ),
                WorkflowPhase(
                    id="runbooks",
                    pattern_id="sequential",
                    name="Alert Runbooks",
                    description="Create runbook for each alert: what to check, how to mitigate, escalation",
                    gate="Every alert has a corresponding runbook",
                    config={"agents": ["monitoring-ops", "doc-writer"]},
                ),
            ],
            config={
                "graph": {
                    "nodes": [
                        {
                            "id": "n1",
                            "agent_id": "monitoring-ops",
                            "x": 100,
                            "y": 150,
                            "label": "SLO Def",
                            "phase": "slo-define",
                        },
                        {
                            "id": "n2",
                            "agent_id": "lead_dev",
                            "x": 300,
                            "y": 100,
                            "label": "Health",
                            "phase": "health-checks",
                        },
                        {
                            "id": "n3",
                            "agent_id": "lead_dev",
                            "x": 300,
                            "y": 200,
                            "label": "Logging",
                            "phase": "logging-setup",
                        },
                        {
                            "id": "n4",
                            "agent_id": "monitoring-ops",
                            "x": 500,
                            "y": 150,
                            "label": "Alerting",
                            "phase": "alerting",
                        },
                        {
                            "id": "n5",
                            "agent_id": "doc-writer",
                            "x": 700,
                            "y": 150,
                            "label": "Runbooks",
                            "phase": "runbooks",
                        },
                    ],
                    "edges": [
                        {"from": "n1", "to": "n2", "label": "SLOs", "color": "#ec4899"},
                        {"from": "n1", "to": "n3", "label": "SLOs", "color": "#ec4899"},
                        {
                            "from": "n2",
                            "to": "n4",
                            "label": "endpoints",
                            "color": "#3fb950",
                        },
                        {
                            "from": "n3",
                            "to": "n4",
                            "label": "logs ready",
                            "color": "#3fb950",
                        },
                        {
                            "from": "n4",
                            "to": "n5",
                            "label": "alerts defined",
                            "color": "#d29922",
                        },
                    ],
                },
            },
        ),
    )

    # 7. Canary Deployment (covers: stab-rollback)
    builtins.append(
        WorkflowDef(
            id="canary-deployment",
            name="Canary Deployment & Rollback",
            description="Progressive canary deployment with automated metric-based rollback.",
            icon="🐤",
            is_builtin=True,
            phases=[
                WorkflowPhase(
                    id="pre-deploy",
                    pattern_id="sequential",
                    name="Pre-Deploy Checks",
                    description="Verify all tests pass, no blocking vulnerabilities, changelog updated",
                    gate="All pre-deploy checks green",
                    config={"agents": ["canary-deployer", "testeur"]},
                ),
                WorkflowPhase(
                    id="canary-1pct",
                    pattern_id="sequential",
                    name="Canary 1% Rollout",
                    description="Deploy to 1% of traffic, monitor error rate and latency for 10 minutes",
                    gate="Error rate < 0.1%, p95 latency within SLO",
                    config={"agents": ["canary-deployer", "monitoring-ops"]},
                ),
                WorkflowPhase(
                    id="canary-10pct",
                    pattern_id="sequential",
                    name="Canary 10% Rollout",
                    description="Expand to 10% traffic, monitor for 15 minutes",
                    gate="Metrics stable at 10% traffic",
                    config={"agents": ["canary-deployer", "monitoring-ops"]},
                ),
                WorkflowPhase(
                    id="canary-50pct",
                    pattern_id="human-in-the-loop",
                    name="Canary 50% — Human Checkpoint",
                    description="Expand to 50%, require human approval before full rollout",
                    gate="checkpoint",
                    config={"agents": ["canary-deployer", "sre"]},
                ),
                WorkflowPhase(
                    id="full-rollout",
                    pattern_id="sequential",
                    name="Full Rollout (100%)",
                    description="Complete rollout, post-deploy smoke tests, update release status",
                    gate="100% traffic on new version, all smoke tests pass",
                    config={"agents": ["canary-deployer", "testeur"]},
                ),
            ],
            config={
                "auto_rollback": True,
                "rollback_triggers": {
                    "error_rate_pct": 1.0,
                    "p95_latency_ms": 500,
                    "crash_rate_pct": 0.5,
                },
                "graph": {
                    "nodes": [
                        {
                            "id": "n1",
                            "agent_id": "canary-deployer",
                            "x": 100,
                            "y": 150,
                            "label": "Pre-Deploy",
                            "phase": "pre-deploy",
                        },
                        {
                            "id": "n2",
                            "agent_id": "canary-deployer",
                            "x": 250,
                            "y": 150,
                            "label": "1%",
                            "phase": "canary-1pct",
                        },
                        {
                            "id": "n3",
                            "agent_id": "canary-deployer",
                            "x": 400,
                            "y": 150,
                            "label": "10%",
                            "phase": "canary-10pct",
                        },
                        {
                            "id": "n4",
                            "agent_id": "sre",
                            "x": 550,
                            "y": 150,
                            "label": "50% HITL",
                            "phase": "canary-50pct",
                        },
                        {
                            "id": "n5",
                            "agent_id": "canary-deployer",
                            "x": 700,
                            "y": 150,
                            "label": "100%",
                            "phase": "full-rollout",
                        },
                    ],
                    "edges": [
                        {
                            "from": "n1",
                            "to": "n2",
                            "label": "checks ok",
                            "color": "#3fb950",
                        },
                        {
                            "from": "n2",
                            "to": "n3",
                            "label": "1% stable",
                            "color": "#3fb950",
                        },
                        {
                            "from": "n3",
                            "to": "n4",
                            "label": "10% stable",
                            "color": "#3fb950",
                        },
                        {
                            "from": "n4",
                            "to": "n5",
                            "label": "approved",
                            "color": "#3fb950",
                        },
                        {
                            "from": "n2",
                            "to": "n1",
                            "label": "rollback",
                            "color": "#ef4444",
                            "style": "dashed",
                        },
                        {
                            "from": "n3",
                            "to": "n1",
                            "label": "rollback",
                            "color": "#ef4444",
                            "style": "dashed",
                        },
                    ],
                },
            },
        ),
    )

    # 8. Test Data & Fixtures (covers: repro-seed)
    builtins.append(
        WorkflowDef(
            id="test-data-pipeline",
            name="Test Data & Fixtures Pipeline",
            description="Generate reproducible test data: factories, seeds, fixtures for all environments.",
            icon="🧪",
            is_builtin=True,
            phases=[
                WorkflowPhase(
                    id="model-analysis",
                    pattern_id="sequential",
                    name="Domain Model Analysis",
                    description="Analyze all domain models, relationships, constraints, and validation rules",
                    gate="All models inventoried with relationships mapped",
                    config={"agents": ["fixture-gen", "architecte"]},
                ),
                WorkflowPhase(
                    id="factory-gen",
                    pattern_id="sequential",
                    name="Factory Generation",
                    description="Create factory functions/classes for each model with realistic data (Faker)",
                    gate="Factory for every model, referential integrity maintained",
                    config={"agents": ["fixture-gen"]},
                ),
                WorkflowPhase(
                    id="seed-scripts",
                    pattern_id="sequential",
                    name="Seed Scripts",
                    description="Create SQL/script seeds for dev, staging, and test environments",
                    gate="Seed scripts run without errors in all environments",
                    config={"agents": ["fixture-gen", "devops"]},
                ),
                WorkflowPhase(
                    id="edge-cases",
                    pattern_id="sequential",
                    name="Edge Case Datasets",
                    description="Create pathological datasets: empty, max-length, unicode, concurrent access",
                    gate="Edge case datasets covering all boundary conditions",
                    config={"agents": ["fixture-gen", "testeur"]},
                ),
            ],
            config={
                "graph": {
                    "nodes": [
                        {
                            "id": "n1",
                            "agent_id": "fixture-gen",
                            "x": 100,
                            "y": 150,
                            "label": "Models",
                            "phase": "model-analysis",
                        },
                        {
                            "id": "n2",
                            "agent_id": "fixture-gen",
                            "x": 300,
                            "y": 150,
                            "label": "Factories",
                            "phase": "factory-gen",
                        },
                        {
                            "id": "n3",
                            "agent_id": "fixture-gen",
                            "x": 500,
                            "y": 100,
                            "label": "Seeds",
                            "phase": "seed-scripts",
                        },
                        {
                            "id": "n4",
                            "agent_id": "testeur",
                            "x": 500,
                            "y": 200,
                            "label": "Edge Cases",
                            "phase": "edge-cases",
                        },
                    ],
                    "edges": [
                        {
                            "from": "n1",
                            "to": "n2",
                            "label": "models",
                            "color": "#a855f7",
                        },
                        {
                            "from": "n2",
                            "to": "n3",
                            "label": "factories",
                            "color": "#a855f7",
                        },
                        {
                            "from": "n2",
                            "to": "n4",
                            "label": "factories",
                            "color": "#a855f7",
                        },
                    ],
                },
            },
        ),
    )

    # 9. i18n Validation (covers: i18n-multi)
    builtins.append(
        WorkflowDef(
            id="i18n-validation",
            name="Internationalization Validation",
            description="Validate i18n coverage: hardcoded strings, missing translations, RTL, date/number formatting.",
            icon="🌍",
            is_builtin=True,
            phases=[
                WorkflowPhase(
                    id="string-scan",
                    pattern_id="sequential",
                    name="Hardcoded String Scan",
                    description="Scan source code for user-facing hardcoded strings not going through i18n",
                    gate="All hardcoded strings identified and flagged",
                    config={"agents": ["i18n-checker"]},
                ),
                WorkflowPhase(
                    id="translation-check",
                    pattern_id="parallel",
                    name="Translation Completeness",
                    description="Check translation files for missing keys per locale, detect stale translations",
                    gate="All locales at 100% key coverage or gaps documented",
                    config={"agents": ["i18n-checker"]},
                ),
                WorkflowPhase(
                    id="format-check",
                    pattern_id="sequential",
                    name="Format Validation",
                    description="Verify date, time, number, currency formatting uses Intl API, check RTL support",
                    gate="All formatting uses locale-aware APIs",
                    config={"agents": ["i18n-checker", "ux_designer"]},
                ),
                WorkflowPhase(
                    id="i18n-report",
                    pattern_id="sequential",
                    name="i18n Report",
                    description="Generate coverage report per locale with fix recommendations",
                    gate="i18n coverage report published",
                    config={"agents": ["i18n-checker", "doc-writer"]},
                ),
            ],
            config={
                "graph": {
                    "nodes": [
                        {
                            "id": "n1",
                            "agent_id": "i18n-checker",
                            "x": 100,
                            "y": 150,
                            "label": "String Scan",
                            "phase": "string-scan",
                        },
                        {
                            "id": "n2",
                            "agent_id": "i18n-checker",
                            "x": 300,
                            "y": 100,
                            "label": "Translations",
                            "phase": "translation-check",
                        },
                        {
                            "id": "n3",
                            "agent_id": "i18n-checker",
                            "x": 300,
                            "y": 200,
                            "label": "Formats",
                            "phase": "format-check",
                        },
                        {
                            "id": "n4",
                            "agent_id": "doc-writer",
                            "x": 500,
                            "y": 150,
                            "label": "Report",
                            "phase": "i18n-report",
                        },
                    ],
                    "edges": [
                        {
                            "from": "n1",
                            "to": "n2",
                            "label": "strings found",
                            "color": "#3b82f6",
                        },
                        {
                            "from": "n1",
                            "to": "n3",
                            "label": "strings found",
                            "color": "#3b82f6",
                        },
                        {
                            "from": "n2",
                            "to": "n4",
                            "label": "coverage",
                            "color": "#3fb950",
                        },
                        {
                            "from": "n3",
                            "to": "n4",
                            "label": "formats ok",
                            "color": "#3fb950",
                        },
                    ],
                },
            },
        ),
    )

    # 10. SAST Continuous Security Scan (covers: secu-sast)
    builtins.append(
        WorkflowDef(
            id="sast-continuous",
            name="SAST Continuous Security Scan",
            description="Continuous static application security testing integrated into CI pipeline.",
            icon="🔒",
            is_builtin=True,
            phases=[
                WorkflowPhase(
                    id="sast-scan",
                    pattern_id="parallel",
                    name="SAST Scan",
                    description="Run static analysis tools: semgrep, bandit, eslint-security, CodeQL",
                    gate="All SAST scanners completed",
                    config={"agents": ["securite", "devsecops"]},
                ),
                WorkflowPhase(
                    id="sast-triage",
                    pattern_id="sequential",
                    name="Finding Triage",
                    description="Classify findings by severity (critical/high/medium/low), filter false positives",
                    gate="All findings triaged, critical/high addressed",
                    config={"agents": ["securite", "lead_dev"]},
                ),
                WorkflowPhase(
                    id="sast-fix",
                    pattern_id="loop",
                    name="Security Fixes",
                    description="Fix critical and high findings, verify fixes don't introduce regressions",
                    gate="Zero critical/high findings remaining",
                    config={"agents": ["securite", "lead_dev"], "max_iterations": 3},
                ),
                WorkflowPhase(
                    id="sast-gate",
                    pattern_id="sequential",
                    name="Security Gate",
                    description="Final security gate: verify all critical/high resolved, generate compliance report",
                    gate="Security gate passed, report published",
                    config={"agents": ["securite"]},
                ),
            ],
            config={
                "schedule": "per-commit",
                "graph": {
                    "nodes": [
                        {
                            "id": "n1",
                            "agent_id": "securite",
                            "x": 100,
                            "y": 150,
                            "label": "SAST Scan",
                            "phase": "sast-scan",
                        },
                        {
                            "id": "n2",
                            "agent_id": "securite",
                            "x": 300,
                            "y": 150,
                            "label": "Triage",
                            "phase": "sast-triage",
                        },
                        {
                            "id": "n3",
                            "agent_id": "lead_dev",
                            "x": 500,
                            "y": 150,
                            "label": "Fix Loop",
                            "phase": "sast-fix",
                        },
                        {
                            "id": "n4",
                            "agent_id": "securite",
                            "x": 700,
                            "y": 150,
                            "label": "Gate",
                            "phase": "sast-gate",
                        },
                    ],
                    "edges": [
                        {
                            "from": "n1",
                            "to": "n2",
                            "label": "findings",
                            "color": "#ef4444",
                        },
                        {
                            "from": "n2",
                            "to": "n3",
                            "label": "critical/high",
                            "color": "#ef4444",
                        },
                        {
                            "from": "n3",
                            "to": "n1",
                            "label": "re-scan",
                            "color": "#d29922",
                            "style": "dashed",
                        },
                        {
                            "from": "n3",
                            "to": "n4",
                            "label": "all fixed",
                            "color": "#3fb950",
                        },
                    ],
                },
            },
        ),
    )

    # 11. AO / Contractual Compliance (covers: legal-contrat)
    builtins.append(
        WorkflowDef(
            id="ao-compliance",
            name="AO & Contractual Compliance",
            description="Appel d'Offres traceability: requirement mapping, SLA tracking, acceptance reports (PV de recette).",
            icon="📋",
            is_builtin=True,
            phases=[
                WorkflowPhase(
                    id="ao-parse",
                    pattern_id="sequential",
                    name="AO Requirements Parsing",
                    description="Parse CCTP/CCAP documents, extract all contractual requirements into traceable checklist",
                    gate="All requirements inventoried with unique IDs",
                    config={"agents": ["ao-compliance", "metier"]},
                ),
                WorkflowPhase(
                    id="req-mapping",
                    pattern_id="parallel",
                    name="Requirement → Deliverable Mapping",
                    description="Map each requirement to deliverables, acceptance criteria, and responsible team",
                    gate="Compliance matrix complete (requirement → deliverable → proof → status)",
                    config={"agents": ["ao-compliance", "architecte", "lead_dev"]},
                ),
                WorkflowPhase(
                    id="sla-tracking",
                    pattern_id="sequential",
                    name="SLA Compliance Tracking",
                    description="Verify SLA metrics: availability, response time, MTTR, MTBF against contractual targets",
                    gate="All SLAs measured and documented",
                    config={"agents": ["ao-compliance", "sre", "monitoring-ops"]},
                ),
                WorkflowPhase(
                    id="acceptance-prep",
                    pattern_id="sequential",
                    name="Acceptance Report (PV de Recette)",
                    description="Prepare formal acceptance report: test results, compliance matrix, non-conformity log",
                    gate="PV de recette ready for client signature",
                    config={"agents": ["ao-compliance", "doc-writer"]},
                ),
                WorkflowPhase(
                    id="ao-review",
                    pattern_id="human-in-the-loop",
                    name="Client Review Checkpoint",
                    description="Human review of compliance matrix and acceptance report before submission",
                    gate="checkpoint",
                    config={"agents": ["ao-compliance"]},
                ),
            ],
            config={
                "schedule": "per-milestone",
                "graph": {
                    "nodes": [
                        {
                            "id": "n1",
                            "agent_id": "ao-compliance",
                            "x": 100,
                            "y": 150,
                            "label": "Parse AO",
                            "phase": "ao-parse",
                        },
                        {
                            "id": "n2",
                            "agent_id": "ao-compliance",
                            "x": 300,
                            "y": 100,
                            "label": "Req Map",
                            "phase": "req-mapping",
                        },
                        {
                            "id": "n3",
                            "agent_id": "sre",
                            "x": 300,
                            "y": 200,
                            "label": "SLA Check",
                            "phase": "sla-tracking",
                        },
                        {
                            "id": "n4",
                            "agent_id": "doc-writer",
                            "x": 500,
                            "y": 150,
                            "label": "PV Recette",
                            "phase": "acceptance-prep",
                        },
                        {
                            "id": "n5",
                            "agent_id": "ao-compliance",
                            "x": 700,
                            "y": 150,
                            "label": "Client Review",
                            "phase": "ao-review",
                        },
                    ],
                    "edges": [
                        {
                            "from": "n1",
                            "to": "n2",
                            "label": "requirements",
                            "color": "#6366f1",
                        },
                        {"from": "n1", "to": "n3", "label": "SLAs", "color": "#6366f1"},
                        {
                            "from": "n2",
                            "to": "n4",
                            "label": "matrix",
                            "color": "#3fb950",
                        },
                        {
                            "from": "n3",
                            "to": "n4",
                            "label": "SLA report",
                            "color": "#3fb950",
                        },
                        {
                            "from": "n4",
                            "to": "n5",
                            "label": "PV ready",
                            "color": "#d29922",
                        },
                    ],
                },
            },
        ),
    )

    # 12. Infrastructure as Code (covers: repro-env)
    builtins.append(
        WorkflowDef(
            id="iac-pipeline",
            name="Infrastructure as Code Pipeline",
            description="IaC lifecycle: module creation, environment parity, drift detection, PR-based changes.",
            icon="🏗️",
            is_builtin=True,
            phases=[
                WorkflowPhase(
                    id="iac-design",
                    pattern_id="network",
                    name="Infrastructure Design",
                    description="Define infrastructure components, network topology, security groups, storage tiers",
                    gate="Infrastructure architecture documented and approved",
                    config={"agents": ["iac-engineer", "architecte", "securite"]},
                ),
                WorkflowPhase(
                    id="iac-modules",
                    pattern_id="sequential",
                    name="IaC Module Development",
                    description="Write Terraform/Pulumi modules: networking, compute, storage, monitoring, secrets",
                    gate="All modules written with variables, outputs, and documentation",
                    config={"agents": ["iac-engineer", "devops"]},
                ),
                WorkflowPhase(
                    id="env-parity",
                    pattern_id="parallel",
                    name="Environment Parity",
                    description="Create identical environments (dev/staging/prod) with only variable differences",
                    gate="All environments deployable from same modules",
                    config={"agents": ["iac-engineer"]},
                ),
                WorkflowPhase(
                    id="drift-detect",
                    pattern_id="sequential",
                    name="Drift Detection",
                    description="Implement automated drift detection: terraform plan in CI, alert on unexpected changes",
                    gate="Drift detection automated with alerting",
                    config={"agents": ["iac-engineer", "monitoring-ops"]},
                ),
                WorkflowPhase(
                    id="iac-review",
                    pattern_id="adversarial-pair",
                    name="IaC Security Review",
                    description="Security review of IaC: no hardcoded secrets, least privilege IAM, encryption at rest/transit",
                    gate="Security review passed, no critical findings",
                    config={"agents": ["securite", "iac-engineer"]},
                ),
            ],
            config={
                "graph": {
                    "nodes": [
                        {
                            "id": "n1",
                            "agent_id": "iac-engineer",
                            "x": 100,
                            "y": 150,
                            "label": "Design",
                            "phase": "iac-design",
                        },
                        {
                            "id": "n2",
                            "agent_id": "iac-engineer",
                            "x": 300,
                            "y": 150,
                            "label": "Modules",
                            "phase": "iac-modules",
                        },
                        {
                            "id": "n3",
                            "agent_id": "iac-engineer",
                            "x": 500,
                            "y": 100,
                            "label": "Env Parity",
                            "phase": "env-parity",
                        },
                        {
                            "id": "n4",
                            "agent_id": "monitoring-ops",
                            "x": 500,
                            "y": 200,
                            "label": "Drift Detect",
                            "phase": "drift-detect",
                        },
                        {
                            "id": "n5",
                            "agent_id": "securite",
                            "x": 700,
                            "y": 150,
                            "label": "Security",
                            "phase": "iac-review",
                        },
                    ],
                    "edges": [
                        {
                            "from": "n1",
                            "to": "n2",
                            "label": "architecture",
                            "color": "#0ea5e9",
                        },
                        {
                            "from": "n2",
                            "to": "n3",
                            "label": "modules ready",
                            "color": "#0ea5e9",
                        },
                        {
                            "from": "n2",
                            "to": "n4",
                            "label": "modules ready",
                            "color": "#0ea5e9",
                        },
                        {
                            "from": "n3",
                            "to": "n5",
                            "label": "envs ok",
                            "color": "#3fb950",
                        },
                        {
                            "from": "n4",
                            "to": "n5",
                            "label": "drift ok",
                            "color": "#3fb950",
                        },
                    ],
                },
            },
        ),
    )

    # 13. Generic Data Migration (covers: data-migration)
    builtins.append(
        WorkflowDef(
            id="data-migration",
            name="Data Migration Pipeline",
            description="Generic data migration: schema mapping, ETL, validation, zero-downtime with rollback.",
            icon="🔄",
            is_builtin=True,
            phases=[
                WorkflowPhase(
                    id="migration-plan",
                    pattern_id="network",
                    name="Migration Planning",
                    description="Inventory source/target schemas, define transformation rules, estimate volume, plan timeline",
                    gate="Migration plan approved with go/no-go criteria",
                    config={"agents": ["data-migrator", "architecte", "backup-ops"]},
                ),
                WorkflowPhase(
                    id="pre-migration-backup",
                    pattern_id="sequential",
                    name="Pre-Migration Backup",
                    description="Full backup of source and target databases, verify restore capability",
                    gate="Backup verified with successful test restore",
                    config={"agents": ["backup-ops", "data-migrator"]},
                ),
                WorkflowPhase(
                    id="etl-dev",
                    pattern_id="sequential",
                    name="ETL Development",
                    description="Write migration scripts: extract → transform → load, with reversible up/down migrations",
                    gate="Migration scripts written and unit-tested",
                    config={"agents": ["data-migrator", "lead_dev"]},
                ),
                WorkflowPhase(
                    id="staging-run",
                    pattern_id="sequential",
                    name="Staging Migration Run",
                    description="Execute migration on staging: measure duration, validate row counts, checksums, referential integrity",
                    gate="Staging migration successful, metrics within targets",
                    config={"agents": ["data-migrator", "testeur"]},
                ),
                WorkflowPhase(
                    id="migration-go-nogo",
                    pattern_id="human-in-the-loop",
                    name="Production GO/NO-GO",
                    description="Human checkpoint: review staging results, confirm production migration window",
                    gate="checkpoint",
                    config={"agents": ["data-migrator"]},
                ),
                WorkflowPhase(
                    id="prod-migration",
                    pattern_id="sequential",
                    name="Production Migration",
                    description="Execute production migration with zero-downtime (expand-contract/dual-write), validate post-migration",
                    gate="Production data migrated and validated",
                    config={"agents": ["data-migrator", "sre", "monitoring-ops"]},
                ),
                WorkflowPhase(
                    id="post-validation",
                    pattern_id="adversarial-pair",
                    name="Post-Migration Validation",
                    description="Full data validation: row counts, checksums, business rule verification, performance check",
                    gate="All validation checks passed, rollback window closed",
                    config={"agents": ["data-migrator", "testeur"]},
                ),
            ],
            config={
                "critical": True,
                "requires_backup": True,
                "graph": {
                    "nodes": [
                        {
                            "id": "n1",
                            "agent_id": "data-migrator",
                            "x": 50,
                            "y": 150,
                            "label": "Plan",
                            "phase": "migration-plan",
                        },
                        {
                            "id": "n2",
                            "agent_id": "backup-ops",
                            "x": 180,
                            "y": 150,
                            "label": "Backup",
                            "phase": "pre-migration-backup",
                        },
                        {
                            "id": "n3",
                            "agent_id": "data-migrator",
                            "x": 310,
                            "y": 150,
                            "label": "ETL Dev",
                            "phase": "etl-dev",
                        },
                        {
                            "id": "n4",
                            "agent_id": "data-migrator",
                            "x": 440,
                            "y": 150,
                            "label": "Staging",
                            "phase": "staging-run",
                        },
                        {
                            "id": "n5",
                            "agent_id": "data-migrator",
                            "x": 540,
                            "y": 150,
                            "label": "GO/NOGO",
                            "phase": "migration-go-nogo",
                        },
                        {
                            "id": "n6",
                            "agent_id": "sre",
                            "x": 640,
                            "y": 150,
                            "label": "Prod Run",
                            "phase": "prod-migration",
                        },
                        {
                            "id": "n7",
                            "agent_id": "testeur",
                            "x": 770,
                            "y": 150,
                            "label": "Validate",
                            "phase": "post-validation",
                        },
                    ],
                    "edges": [
                        {
                            "from": "n1",
                            "to": "n2",
                            "label": "plan ok",
                            "color": "#d946ef",
                        },
                        {
                            "from": "n2",
                            "to": "n3",
                            "label": "backup ok",
                            "color": "#3fb950",
                        },
                        {
                            "from": "n3",
                            "to": "n4",
                            "label": "scripts ready",
                            "color": "#d946ef",
                        },
                        {
                            "from": "n4",
                            "to": "n5",
                            "label": "staging ok",
                            "color": "#3fb950",
                        },
                        {
                            "from": "n5",
                            "to": "n6",
                            "label": "approved",
                            "color": "#3fb950",
                        },
                        {
                            "from": "n6",
                            "to": "n7",
                            "label": "migrated",
                            "color": "#d946ef",
                        },
                        {
                            "from": "n6",
                            "to": "n2",
                            "label": "rollback",
                            "color": "#ef4444",
                            "style": "dashed",
                        },
                    ],
                },
            },
        ),
    )

    # ── Quality & Continuous Improvement Workflows (v2.1) ──

    builtins.append(
        WorkflowDef(
            id="quality-improvement",
            name="Quality Improvement Cycle",
            description="Automated quality improvement: scan code quality with deterministic tools, identify worst dimensions, plan and execute improvements, rescan and learn.",
            icon="",
            is_builtin=True,
            phases=[
                WorkflowPhase(
                    id="quality-scan",
                    pattern_id="solo",
                    name="Quality Scan",
                    description="Run full deterministic quality scan: complexity (radon/lizard), coverage (coverage.py/nyc), security (bandit/semgrep), documentation (interrogate), architecture (madge/jscpd/mypy), maintainability (radon MI). Store scorecard in DB.",
                    gate="Quality scorecard computed and stored",
                    config={"agents": ["qa"]},
                ),
                WorkflowPhase(
                    id="quality-analysis",
                    pattern_id="network",
                    name="Root Cause Analysis",
                    description="Analyze quality scorecard. Identify TOP 3 worst dimensions. For each: find specific files/functions causing low scores. Cross-reference with adversarial rejection history and past incidents.",
                    gate="Root causes identified for each low-scoring dimension",
                    config={"agents": ["qa", "architecte", "lead-dev"]},
                ),
                WorkflowPhase(
                    id="rex-digest",
                    pattern_id="solo",
                    name="REX & Memory Digest",
                    description="Search memory_project and memory_global for: past ROTI, retrospective notes, recurring issues, lessons learned. Extract patterns: what keeps failing, what improved, what was tried before.",
                    gate="REX digest compiled with actionable patterns",
                    config={"agents": ["product-owner"]},
                ),
                WorkflowPhase(
                    id="improvement-plan",
                    pattern_id="network",
                    name="Improvement Plan",
                    description="Generate concrete improvement plan based on quality scan + REX digest. For each worst dimension: specific actions (refactor files, add tests, fix deps, improve docs). Prioritize by impact/effort.",
                    gate="Improvement plan with prioritized actions",
                    config={"agents": ["lead-dev", "architecte", "product-owner"]},
                ),
                WorkflowPhase(
                    id="improvement-exec",
                    pattern_id="hierarchical",
                    name="Execute Improvements",
                    description="Execute improvement actions: refactor high-complexity functions, add missing tests, fix dependency vulnerabilities, improve documentation, resolve circular dependencies. MUST use quality tools to verify each fix.",
                    gate="All planned improvements implemented",
                    config={"agents": ["lead-dev", "dev-1", "dev-2", "qa"]},
                ),
                WorkflowPhase(
                    id="quality-rescan",
                    pattern_id="solo",
                    name="Quality Rescan",
                    description="Re-run full quality scan. Compare before/after scores per dimension. Verify improvements are real (not just moving code around). Store new snapshot for trend.",
                    gate="Scores improved or stable (no regression)",
                    config={"agents": ["qa"]},
                ),
                WorkflowPhase(
                    id="quality-learning",
                    pattern_id="solo",
                    name="Learning & Memory",
                    description="Store what worked and what didn't in memory_global. Update project conventions if patterns emerged. Generate quality trend summary for sprint retro.",
                    gate="always",
                    config={"agents": ["product-owner"]},
                ),
            ],
        ),
    )

    builtins.append(
        WorkflowDef(
            id="retrospective-quality",
            name="Quality Retrospective",
            description="End-of-sprint/PI quality retrospective: collect ROTI, REX, incidents, quality metrics. Analyze patterns. Generate and implement improvement actions for the SF itself.",
            icon="",
            is_builtin=True,
            phases=[
                WorkflowPhase(
                    id="retro-collect",
                    pattern_id="solo",
                    name="Collect Feedback",
                    description="Collect all sprint data: quality snapshots, adversarial rejections, platform incidents, session outcomes (success/fail/interrupted), LLM usage, ROTI feedback, retrospective notes from memory.",
                    gate="Sprint data collected and structured",
                    config={"agents": ["rte"]},
                ),
                WorkflowPhase(
                    id="retro-analyze",
                    pattern_id="network",
                    name="Pattern Analysis",
                    description="Analyze collected data for patterns: recurring failures, common adversarial rejections, quality regressions, successful improvements. Identify systemic vs one-off issues. Compute improvement velocity.",
                    gate="Patterns identified with evidence",
                    config={"agents": ["rte", "architecte", "product-owner"]},
                ),
                WorkflowPhase(
                    id="retro-actions",
                    pattern_id="network",
                    name="Generate Actions",
                    description="Generate concrete improvement actions for the SF itself: update agent skills (YAML), modify protocols (_EXEC_PROTOCOL, _DECOMPOSE_PROTOCOL), add new adversarial checks, tune workflow phases, improve tool schemas.",
                    gate="Actionable improvement items with owner and target",
                    config={"agents": ["lead-dev", "architecte", "product-owner"]},
                ),
                WorkflowPhase(
                    id="retro-implement",
                    pattern_id="hierarchical",
                    name="Implement SF Improvements",
                    description="Implement the improvement actions: modify YAML skill definitions, update protocol strings in engine.py, add adversarial checks, tune workflow configurations. Use code_write to make changes.",
                    gate="SF improvements implemented and verified",
                    config={"agents": ["lead-dev", "dev-1"]},
                ),
                WorkflowPhase(
                    id="retro-validate",
                    pattern_id="solo",
                    name="Validate Changes",
                    description="Run quality scan on the SF platform code itself. Verify no regressions. Store improvement results in memory_global for next iteration.",
                    gate="always",
                    config={"agents": ["qa"]},
                ),
            ],
        ),
    )

    builtins.append(
        WorkflowDef(
            id="skill-evolution",
            name="Agent Skill Evolution",
            description="Meta-improvement: analyze agent performance across missions, extract best practices from top performers, update skills and prompts for underperformers. A/B test improvements.",
            icon="",
            is_builtin=True,
            phases=[
                WorkflowPhase(
                    id="skill-audit",
                    pattern_id="solo",
                    name="Agent Performance Audit",
                    description="Analyze all agents: quality scores per agent, adversarial rejection rates, code_write success rates, tool usage patterns. Rank agents by effectiveness. Identify top 5 and bottom 5 performers.",
                    gate="Agent performance report generated",
                    config={"agents": ["rte"]},
                ),
                WorkflowPhase(
                    id="skill-best-practices",
                    pattern_id="network",
                    name="Extract Best Practices",
                    description="Study top-performing agents: what tools do they use, what patterns in their prompts work, how do they structure code, what makes them pass adversarial checks. Extract reusable patterns.",
                    gate="Best practices documented",
                    config={"agents": ["architecte", "lead-dev"]},
                ),
                WorkflowPhase(
                    id="skill-update",
                    pattern_id="hierarchical",
                    name="Update Agent Skills",
                    description="Modify YAML skill definitions for underperforming agents. Update system prompts with best practices. Add new skills if gaps found. Remove redundant/confusing skills.",
                    gate="Skill YAML files updated",
                    config={"agents": ["lead-dev", "dev-1"]},
                ),
                WorkflowPhase(
                    id="prompt-update",
                    pattern_id="solo",
                    name="Update Protocols",
                    description="Refine _EXEC_PROTOCOL, _DECOMPOSE_PROTOCOL, _QA_PROTOCOL, _RESEARCH_PROTOCOL based on analysis. Add or clarify instructions that top agents follow. Remove instructions that cause confusion.",
                    gate="Protocol strings updated in engine.py",
                    config={"agents": ["lead-dev"]},
                ),
                WorkflowPhase(
                    id="skill-validate",
                    pattern_id="parallel",
                    name="Validate Improvements",
                    description="Run a sample mission with updated skills/protocols. Compare output quality with previous runs. Verify adversarial pass rate improved. Store comparison in memory_global.",
                    gate="always",
                    config={"agents": ["qa", "lead-dev"]},
                ),
            ],
        ),
    )

    return builtins
