"""Team & Workflow Generator — LLM-driven team composition from natural language."""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..agents.store import get_agent_store, AgentDef
from ..llm.client import get_llm_client, LLMMessage
from ..patterns.store import PatternDef
from ..sessions.store import get_session_store, SessionDef, MessageDef
from ..workflows.store import get_workflow_store, WorkflowDef, WorkflowPhase

logger = logging.getLogger(__name__)

# ── Agent Catalog ────────────────────────────────────────────────

_SKILLS_DIR = Path(__file__).parent.parent / "skills" / "definitions"

_ROLE_LAYERS = {
    # layer 0: strategic (top)
    "dsi": 0, "lean_portfolio_manager": 0, "enterprise_architect": 0,
    "release_train_engineer": 0,
    # layer 1: management
    "chef_projet": 1, "product_manager": 1, "scrum_master": 1,
    "agile_coach": 1, "pmo": 1, "epic_owner": 1,
    "solution_train_engineer": 1, "solution_manager": 1,
    "business_owner": 1, "metier": 1, "change_manager": 1,
    # layer 2: leads / architects
    "lead_dev": 2, "tech_lead_mobile": 2,
    "architecte": 2, "solution_architect": 2,
    "system_architect_art": 2, "cloud_architect": 2,
    # layer 3: developers
    "dev": 3, "dev_frontend": 3, "dev_backend": 3,
    "dev_fullstack": 3, "dev_mobile": 3,
    "ux_designer": 3, "tech_writer": 3,
    "data_analyst": 3, "data_engineer": 3, "ml_engineer": 3, "dba": 3,
    # layer 4: quality / security
    "qa_lead": 4, "testeur": 4, "performance_engineer": 4,
    "securite": 4, "compliance_officer": 4, "devsecops": 4,
    "accessibility_expert": 4,
    # layer 5: ops
    "devops": 5, "sre": 5,
}

# Colors per layer for visual distinction
_LAYER_COLORS = {
    0: ["#7c3aed"],
    1: ["#2563eb", "#0369a1", "#1d4ed8"],
    2: ["#0891b2", "#0e7490"],
    3: ["#16a34a", "#0d9488", "#4f46e5", "#059669", "#0284c7", "#7c3aed"],
    4: ["#dc2626", "#ea580c", "#b91c1c"],
    5: ["#ea580c", "#d97706"],
}


@dataclass
class TeamMember:
    role_id: str
    agent_id: str = ""  # actual id in DB (may be cloned: dev_frontend_1)
    count: int = 1
    label: str = ""


@dataclass
class TeamSpec:
    mission_name: str = ""
    mission_goal: str = ""
    team: list[TeamMember] = field(default_factory=list)
    phases: list[dict] = field(default_factory=list)
    pattern: str = "hierarchical"
    project_path: str = ""


# ── Catalog Builder ──────────────────────────────────────────────

def _build_role_catalog() -> str:
    """Build a concise catalog of available roles for the LLM."""
    lines = []
    for yamlf in sorted(_SKILLS_DIR.glob("*.yaml")):
        if yamlf.stem.startswith("_"):
            continue
        try:
            data = yaml.safe_load(yamlf.read_text())
        except Exception:
            continue
        if not data or not data.get("id"):
            continue
        rid = data["id"]
        role = data.get("role", data.get("name", rid))
        tags = data.get("tags", [])
        tools = data.get("tools", [])
        desc = (data.get("description") or data.get("tagline") or "")[:80]
        lines.append(f"- **{rid}**: {role} — {desc} (tags: {', '.join(tags[:4])}, tools: {', '.join(tools[:4])})")
    return "\n".join(lines)


_SYSTEM_PROMPT = """Tu es un **Team Generator** expert en composition d'équipes agiles/SAFe.

L'utilisateur décrit une mission en langage naturel. Tu dois composer l'équipe optimale
et le workflow en puisant dans les rôles disponibles.

## Rôles disponibles
{catalog}

## Patterns de workflow disponibles
- **sequential**: Pipeline A → B → C (chaque agent passe au suivant)
- **parallel**: Fan-out: un dispatcher répartit le travail entre N agents en parallèle
- **hierarchical**: Manager délègue aux workers, collecte les résultats, QA valide
- **network**: Tous les agents discutent librement (brainstorm, retrospective)
- **adversarial-pair**: Writer ↔ Reviewer en boucle (max 5 itérations)
- **loop**: Boucle itérative entre agents

## Phases SAFe standard (optionnel)
1. PI Planning (sequential: CP/PM, agents stratégiques)
2. Sprint Planning (sequential: Lead, devs)
3. Dev Sprint (hierarchical: Lead → devs //, QA valide)
4. Sprint Review (sequential: QA → Lead → CP, gate=all_approved)
5. Retrospective (network: toute l'équipe)
6. Release (sequential: DevOps, QA smoke test)

## Règles de sizing
- Max 8 développeurs en parallèle
- Toujours 1 Lead Dev si ≥2 devs
- Toujours 1 QA Lead si l'équipe a des devs
- 1 Chef de Projet ou Scrum Master pour la coordination
- DevOps si CI/CD ou déploiement mentionné
- Sécurité si audit/OWASP/compliance mentionné
- Product Manager si product discovery/backlog mentionné

## Format de sortie OBLIGATOIRE (JSON strict)
```json
{{
  "mission_name": "Nom court de la mission",
  "mission_goal": "Objectif détaillé en 1-2 phrases",
  "team": [
    {{"role_id": "chef_projet", "count": 1, "label": "Chef de Projet"}},
    {{"role_id": "dev_frontend", "count": 3, "label": "Dev Frontend"}},
    {{"role_id": "qa_lead", "count": 1, "label": "QA Lead"}}
  ],
  "phases": [
    {{
      "name": "Sprint Planning",
      "pattern": "sequential",
      "agents": ["chef_projet", "lead_dev"],
      "gate": "always",
      "description": "Planification du sprint"
    }},
    {{
      "name": "Dev Sprint",
      "pattern": "hierarchical",
      "agents": ["lead_dev", "dev_frontend_1", "dev_frontend_2", "dev_frontend_3", "qa_lead"],
      "gate": "no_veto",
      "description": "Développement en parallèle"
    }}
  ],
  "pattern": "hierarchical",
  "project_path": ""
}}
```

IMPORTANT:
- Si count > 1 pour un rôle, les agents dans les phases doivent être suffixés: dev_frontend_1, dev_frontend_2, etc.
- Réponds UNIQUEMENT avec le JSON, aucun texte avant ou après.
- Adapte le nombre de phases au besoin réel (pas toujours 6).
"""


# ── Team Generator ───────────────────────────────────────────────

class TeamGenerator:
    """Generates teams and workflows from natural language prompts."""

    def __init__(self):
        self._catalog = _build_role_catalog()
        self._system_prompt = _SYSTEM_PROMPT.format(catalog=self._catalog)

    async def generate(self, prompt: str) -> dict:
        """Full pipeline: prompt → team spec → agents → workflow → session → launch."""
        spec = await self.analyze_prompt(prompt)
        agents = self.resolve_agents(spec)
        workflow = self.build_workflow(spec, agents)
        session = self._create_session(spec, workflow)
        return {
            "spec": spec,
            "agents": [a.id for a in agents],
            "workflow_id": workflow.id,
            "session_id": session.id,
            "team_size": sum(m.count for m in spec.team),
        }

    async def analyze_prompt(self, prompt: str) -> TeamSpec:
        """Call LLM to analyze the prompt and produce a TeamSpec."""
        client = get_llm_client()
        resp = await client.chat(
            messages=[LLMMessage(role="user", content=prompt)],
            system_prompt=self._system_prompt,
            provider="azure",
            temperature=0.3,
            max_tokens=4096,
        )

        raw = resp.content.strip()
        # Extract JSON from possible markdown fences
        if "```json" in raw:
            raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in raw:
            raw = raw.split("```", 1)[1].split("```", 1)[0].strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error("TeamGenerator: LLM returned invalid JSON: %s", raw[:200])
            raise ValueError(f"LLM returned invalid JSON: {e}") from e

        spec = TeamSpec(
            mission_name=data.get("mission_name", "Mission"),
            mission_goal=data.get("mission_goal", prompt),
            pattern=data.get("pattern", "hierarchical"),
            project_path=data.get("project_path", ""),
        )

        for t in data.get("team", []):
            spec.team.append(TeamMember(
                role_id=t["role_id"],
                count=t.get("count", 1),
                label=t.get("label", t["role_id"]),
            ))

        for p in data.get("phases", []):
            spec.phases.append(p)

        return spec

    def resolve_agents(self, spec: TeamSpec) -> list[AgentDef]:
        """Match team roles to existing YAML agents, cloning if count > 1."""
        agent_store = get_agent_store()
        created = []
        color_idx = {}

        for member in spec.team:
            base_agent = agent_store.get(member.role_id)
            if not base_agent:
                # Try loading from YAML
                yaml_path = _SKILLS_DIR / f"{member.role_id}.yaml"
                if yaml_path.exists():
                    base_agent = self._agent_from_yaml(yaml_path)
                else:
                    logger.warning("Agent role %s not found, skipping", member.role_id)
                    continue

            if member.count == 1:
                agent_id = member.role_id
                member.agent_id = agent_id
                layer = _ROLE_LAYERS.get(member.role_id, 3)
                colors = _LAYER_COLORS.get(layer, ["#6b7280"])
                ci = color_idx.get(layer, 0)
                color = colors[ci % len(colors)]
                color_idx[layer] = ci + 1

                # Ensure agent exists in DB with proper color
                existing = agent_store.get(agent_id)
                if existing:
                    existing.color = color
                    agent_store.update(existing)
                    created.append(existing)
                else:
                    base_agent.id = agent_id
                    base_agent.color = color
                    base_agent.is_builtin = False
                    agent_store.create(base_agent)
                    created.append(base_agent)
            else:
                # Clone N instances
                for i in range(1, member.count + 1):
                    clone_id = f"{member.role_id}_{i}"
                    layer = _ROLE_LAYERS.get(member.role_id, 3)
                    colors = _LAYER_COLORS.get(layer, ["#6b7280"])
                    ci = color_idx.get(layer, 0)
                    color = colors[ci % len(colors)]
                    color_idx[layer] = ci + 1

                    clone = AgentDef(
                        id=clone_id,
                        name=f"{base_agent.name} #{i}",
                        role=base_agent.role,
                        description=base_agent.description,
                        system_prompt=base_agent.system_prompt,
                        provider=base_agent.provider,
                        model=base_agent.model,
                        temperature=base_agent.temperature,
                        max_tokens=base_agent.max_tokens,
                        skills=list(base_agent.skills),
                        tools=list(base_agent.tools),
                        mcps=list(base_agent.mcps),
                        permissions=dict(base_agent.permissions),
                        tags=list(base_agent.tags),
                        icon=base_agent.icon,
                        color=color,
                        avatar=base_agent.avatar,
                        tagline=base_agent.tagline,
                        persona=base_agent.persona,
                        hierarchy_rank=base_agent.hierarchy_rank,
                        is_builtin=False,
                    )
                    existing = agent_store.get(clone_id)
                    if existing:
                        agent_store.update(clone)
                    else:
                        agent_store.create(clone)
                    created.append(clone)

        return created

    def build_workflow(self, spec: TeamSpec, agents: list[AgentDef]) -> WorkflowDef:
        """Build a WorkflowDef with phases and auto-laid-out graph."""
        wf_id = f"gen-{uuid.uuid4().hex[:6]}"

        phases = []
        for i, p in enumerate(spec.phases):
            phases.append(WorkflowPhase(
                id=f"p{i+1}",
                pattern_id=p.get("pattern", spec.pattern),
                name=p.get("name", f"Phase {i+1}"),
                description=p.get("description", ""),
                gate=p.get("gate", "always"),
                config={"agents": p.get("agents", [])},
            ))

        # Collect all unique agent IDs from phases
        all_agent_ids = []
        for p in spec.phases:
            for aid in p.get("agents", []):
                if aid not in all_agent_ids:
                    all_agent_ids.append(aid)

        graph = self._auto_layout_graph(all_agent_ids, agents, spec)

        wf = WorkflowDef(
            id=wf_id,
            name=spec.mission_name,
            description=spec.mission_goal,
            phases=phases,
            config={"graph": graph, "project_path": spec.project_path},
            icon="rocket",
        )

        wf_store = get_workflow_store()
        wf_store.create(wf)
        return wf

    def _auto_layout_graph(
        self, agent_ids: list[str], agents: list[AgentDef], spec: TeamSpec
    ) -> dict:
        """Auto-layout graph nodes by role layer."""
        agent_map = {a.id: a for a in agents}

        # Group agents by layer
        layers: dict[int, list[str]] = {}
        for aid in agent_ids:
            # For cloned agents (dev_frontend_1), use base role
            base = aid.rsplit("_", 1)[0] if aid.rsplit("_", 1)[-1].isdigit() else aid
            layer = _ROLE_LAYERS.get(base, 3)
            layers.setdefault(layer, []).append(aid)

        nodes = []
        node_id_map = {}
        LAYER_Y = {0: 30, 1: 150, 2: 280, 3: 410, 4: 550, 5: 680}
        NODE_W = 230

        for layer_num in sorted(layers.keys()):
            layer_agents = layers[layer_num]
            y = LAYER_Y.get(layer_num, 30 + layer_num * 140)
            total_width = len(layer_agents) * (NODE_W + 40)
            start_x = max(30, (800 - total_width) // 2)

            for j, aid in enumerate(layer_agents):
                nid = f"n{len(nodes)}"
                node_id_map[aid] = nid
                agent = agent_map.get(aid)
                label = agent.name if agent else aid
                nodes.append({
                    "id": nid,
                    "agent_id": aid,
                    "label": label,
                    "x": start_x + j * (NODE_W + 40),
                    "y": y,
                })

        # Build edges: connect layers sequentially (top→bottom)
        edges = []
        sorted_layers = sorted(layers.keys())
        edge_colors = ["#3b82f6", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6", "#06b6d4"]

        for li in range(len(sorted_layers) - 1):
            upper = layers[sorted_layers[li]]
            lower = layers[sorted_layers[li + 1]]
            color = edge_colors[li % len(edge_colors)]

            # Connect each upper agent to each lower agent
            for ua in upper:
                for la in lower:
                    if ua in node_id_map and la in node_id_map:
                        edges.append({
                            "from": node_id_map[ua],
                            "to": node_id_map[la],
                            "type": "delegation" if li == 0 else "sequential",
                            "color": color,
                        })

        return {
            "pattern": spec.pattern,
            "nodes": nodes,
            "edges": edges,
        }

    def _create_session(self, spec: TeamSpec, workflow: WorkflowDef) -> SessionDef:
        """Create a session linked to the generated workflow."""
        store = get_session_store()
        session = SessionDef(
            name=spec.mission_name,
            goal=spec.mission_goal,
            status="active",
            config={
                "workflow_id": workflow.id,
                "generated": True,
            },
        )
        session = store.create(session)

        store.add_message(MessageDef(
            session_id=session.id,
            from_agent="system",
            message_type="system",
            content=(
                f"**Équipe générée** pour: {spec.mission_name}\n\n"
                f"**Objectif**: {spec.mission_goal}\n\n"
                f"**Équipe** ({sum(m.count for m in spec.team)} agents): "
                + ", ".join(f"{m.label} ×{m.count}" if m.count > 1 else m.label for m in spec.team)
                + f"\n\n**Workflow**: {len(spec.phases)} phases"
            ),
        ))
        return session

    def _agent_from_yaml(self, path: Path) -> AgentDef:
        """Load an AgentDef from a YAML skill definition."""
        data = yaml.safe_load(path.read_text())
        llm = data.get("llm", {})
        return AgentDef(
            id=data.get("id", path.stem),
            name=data.get("name", path.stem),
            role=data.get("role", ""),
            description=data.get("description", ""),
            system_prompt=data.get("system_prompt", ""),
            provider=llm.get("provider", "azure"),
            model=llm.get("model", "gpt-5.1"),
            temperature=llm.get("temperature", 0.5),
            max_tokens=llm.get("max_tokens", 4096),
            skills=data.get("skills", []),
            tools=data.get("tools", []),
            mcps=data.get("mcps", []),
            permissions=data.get("permissions", {}),
            tags=data.get("tags", []),
            icon=data.get("icon", "bot"),
            color="#6b7280",
            avatar=data.get("avatar", ""),
            tagline=data.get("tagline", ""),
            persona=data.get("persona", {}).get("description", "") if isinstance(data.get("persona"), dict) else str(data.get("persona", "")),
            hierarchy_rank=data.get("hierarchy_rank", 40),
            is_builtin=False,
        )
