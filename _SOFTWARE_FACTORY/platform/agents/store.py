"""Agent store — CRUD operations for agent definitions in SQLite."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..db.migrations import get_db


@dataclass
class AgentDef:
    """An agent definition (stored in DB)."""
    id: str = ""
    name: str = ""
    role: str = "worker"
    description: str = ""
    system_prompt: str = ""
    provider: str = "minimax"
    model: str = "MiniMax-M2.5"
    temperature: float = 0.7
    max_tokens: int = 4096
    skills: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    mcps: list[str] = field(default_factory=list)
    permissions: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    icon: str = "bot"
    color: str = "#f78166"
    avatar: str = ""       # emoji or URL to profile image
    tagline: str = ""      # short personality subtitle
    persona: str = ""      # personality traits, character
    motivation: str = ""   # what drives this agent, goals, ambition
    hierarchy_rank: int = 50  # org hierarchy: 0=CEO, 10=director, 20=lead, 30=senior, 40=mid, 50=junior
    is_builtin: bool = False
    created_at: str = ""
    updated_at: str = ""


def _row_to_agent(row) -> AgentDef:
    keys = row.keys() if hasattr(row, 'keys') else []
    return AgentDef(
        id=row["id"],
        name=row["name"],
        role=row["role"],
        description=row["description"] or "",
        system_prompt=row["system_prompt"] or "",
        provider=row["provider"] or "minimax",
        model=row["model"] or "MiniMax-M2.5",
        temperature=row["temperature"],
        max_tokens=row["max_tokens"],
        skills=json.loads(row["skills_json"] or "[]"),
        tools=json.loads(row["tools_json"] or "[]"),
        mcps=json.loads(row["mcps_json"] or "[]"),
        permissions=json.loads(row["permissions_json"] or "{}"),
        tags=json.loads(row["tags_json"] or "[]"),
        icon=row["icon"] or "bot",
        color=row["color"] or "#f78166",
        avatar=row["avatar"] if "avatar" in keys else "",
        tagline=row["tagline"] if "tagline" in keys else "",
        persona=row["persona"] if "persona" in keys else "",
        motivation=row["motivation"] if "motivation" in keys else "",
        hierarchy_rank=row["hierarchy_rank"] if "hierarchy_rank" in keys else 50,
        is_builtin=bool(row["is_builtin"]),
        created_at=row["created_at"] or "",
        updated_at=row["updated_at"] or "",
    )


class AgentStore:
    """CRUD for agent definitions."""

    def list_all(self) -> list[AgentDef]:
        db = get_db()
        try:
            rows = db.execute("SELECT * FROM agents ORDER BY is_builtin DESC, name").fetchall()
            return [_row_to_agent(r) for r in rows]
        finally:
            db.close()

    def get(self, agent_id: str) -> Optional[AgentDef]:
        db = get_db()
        try:
            row = db.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
            return _row_to_agent(row) if row else None
        finally:
            db.close()

    def create(self, agent: AgentDef) -> AgentDef:
        if not agent.id:
            agent.id = str(uuid.uuid4())[:8]
        now = datetime.utcnow().isoformat()
        agent.created_at = now
        agent.updated_at = now
        db = get_db()
        try:
            db.execute(
                """INSERT INTO agents (id, name, role, description, system_prompt,
                   provider, model, temperature, max_tokens, skills_json, tools_json,
                   mcps_json, permissions_json, tags_json, icon, color, avatar, tagline,
                   persona, hierarchy_rank, motivation,
                   is_builtin, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (agent.id, agent.name, agent.role, agent.description, agent.system_prompt,
                 agent.provider, agent.model, agent.temperature, agent.max_tokens,
                 json.dumps(agent.skills), json.dumps(agent.tools),
                 json.dumps(agent.mcps), json.dumps(agent.permissions),
                 json.dumps(agent.tags), agent.icon, agent.color,
                 agent.avatar, agent.tagline, agent.persona, agent.hierarchy_rank,
                 agent.motivation,
                 int(agent.is_builtin), agent.created_at, agent.updated_at),
            )
            db.commit()
        finally:
            db.close()
        return agent

    def update(self, agent: AgentDef) -> AgentDef:
        agent.updated_at = datetime.utcnow().isoformat()
        db = get_db()
        try:
            db.execute(
                """UPDATE agents SET name=?, role=?, description=?, system_prompt=?,
                   provider=?, model=?, temperature=?, max_tokens=?, skills_json=?,
                   tools_json=?, mcps_json=?, permissions_json=?, tags_json=?,
                   icon=?, color=?, avatar=?, tagline=?, persona=?, hierarchy_rank=?,
                   motivation=?,
                   updated_at=?
                   WHERE id=?""",
                (agent.name, agent.role, agent.description, agent.system_prompt,
                 agent.provider, agent.model, agent.temperature, agent.max_tokens,
                 json.dumps(agent.skills), json.dumps(agent.tools),
                 json.dumps(agent.mcps), json.dumps(agent.permissions),
                 json.dumps(agent.tags), agent.icon, agent.color,
                 agent.avatar, agent.tagline, agent.persona, agent.hierarchy_rank,
                 agent.motivation,
                 agent.updated_at, agent.id),
            )
            db.commit()
        finally:
            db.close()
        return agent

    def delete(self, agent_id: str) -> bool:
        db = get_db()
        try:
            cur = db.execute("DELETE FROM agents WHERE id = ? AND is_builtin = 0", (agent_id,))
            db.commit()
            return cur.rowcount > 0
        finally:
            db.close()

    def count(self) -> int:
        db = get_db()
        try:
            return db.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
        finally:
            db.close()

    def seed_builtins(self):
        """Seed built-in agents from hardcoded list + YAML definitions."""
        if self.count() == 0:
            self._seed_hardcoded()
        self._seed_from_yaml()

    def _seed_hardcoded(self):
        builtins = [
            AgentDef(id="brain", name="Gabriel Mercier", role="Strategic Orchestrator",
                     description="Strategic orchestrator. Deep recursive analysis, task decomposition, WSJF prioritization.",
                     provider="minimax", model="MiniMax-M2.5",
                     temperature=0.3, max_tokens=8192,
                     icon="brain", color="#bc8cff",
                     avatar="GM", tagline="I see the big picture",
                     is_builtin=True, tags=["orchestrator", "planning"],
                     system_prompt="You are the Brain — strategic orchestrator of the Software Factory.\n"
                     "Your role: analyze codebases deeply, decompose into atomic tasks (FRACTAL),\n"
                     "prioritize by WSJF, and coordinate workers. Use CoVe (Chain-of-Verification)\n"
                     "to validate every claim before acting. Never hallucinate — verify with tools."),

            AgentDef(id="worker", name="Yann Lefevre", role="TDD Worker",
                     description="Writes code following strict TDD: Red → Green → Refactor. Atomic, KISS.",
                     provider="minimax", model="MiniMax-M2.5",
                     temperature=0.4, max_tokens=4096,
                     icon="code", color="#58a6ff",
                     avatar="YL", tagline="Test first, code second",
                     is_builtin=True, tags=["coding", "tdd"],
                     system_prompt="You are a TDD Worker. Write code following strict Red-Green-Refactor.\n"
                     "Each task is atomic and KISS. Write the test FIRST, then minimal code to pass.\n"
                     "Never skip tests. Never use .unwrap() in Rust. Handle all errors explicitly."),

            AgentDef(id="code-critic", name="Diane Moreau", role="Code Critic",
                     description="Reviews code for quality: SLOP detection, API misuse, syntax/logic errors.",
                     provider="minimax", model="MiniMax-M2.5",
                     temperature=0.2, max_tokens=4096,
                     icon="eye", color="#d29922",
                     avatar="DM", tagline="Nothing escapes my review",
                     is_builtin=True, tags=["review", "quality"],
                     permissions={"can_veto": True, "veto_level": "absolute"},
                     system_prompt="You are the Code Critic. Review code for:\n"
                     "- SLOP (code that compiles but does nothing useful)\n"
                     "- test.skip(), @ts-ignore, #[ignore] — ALWAYS REJECT\n"
                     "- Empty catch blocks, unused imports, dead code\n"
                     "- API misuse (wrong extractors, missing FromRow derives)\n"
                     "Use CoVe: Draft assessment → Verify claims → Final decision."),

            AgentDef(id="security-critic", name="Tariq Haddad", role="Security Critic",
                     description="OWASP Top 10, secrets detection, SQL injection, XSS analysis.",
                     provider="minimax", model="MiniMax-M2.5",
                     temperature=0.1, max_tokens=4096,
                     icon="shield", color="#f85149",
                     avatar="TH", tagline="Zero vulnerabilities tolerated",
                     is_builtin=True, tags=["security", "owasp"],
                     permissions={"can_veto": True, "veto_level": "absolute"},
                     system_prompt="You are the Security Critic (cognitive diversity: different LLM provider).\n"
                     "Analyze code for OWASP Top 10: SQL injection, XSS, command injection,\n"
                     "secrets in code (not in fixtures/tests), insecure auth, CSRF.\n"
                     "Secrets in test fixtures are OK. CLI print() is OK. Focus on REAL vulnerabilities."),

            AgentDef(id="arch-critic", name="Sylvie Dumont", role="Architecture Critic",
                     description="Reviews RBAC, input validation, error handling, API design patterns.",
                     provider="minimax", model="MiniMax-M2.5",
                     temperature=0.3, max_tokens=4096,
                     icon="building", color="#bc8cff",
                     avatar="SD", tagline="Clean architecture, strong foundations",
                     is_builtin=True, tags=["architecture", "design"],
                     permissions={"can_veto": True, "veto_level": "strong"},
                     system_prompt="You are the Architecture Critic. Review for:\n"
                     "- RBAC/Auth coverage on all endpoints\n"
                     "- Input validation completeness\n"
                     "- Error handling (all HTTP status codes covered)\n"
                     "- API design (pagination, rate limiting, versioning)\n"
                     "- Proper separation of concerns"),

            AgentDef(id="devops", name="Karim Diallo", role="DevOps / SRE",
                     description="Build, deploy, infrastructure. Docker, CI/CD, monitoring.",
                     provider="minimax", model="MiniMax-M2.5",
                     temperature=0.3, max_tokens=4096,
                     icon="rocket", color="#3fb950",
                     avatar="KD", tagline="CI/CD, Docker, déploiement canary, monitoring",
                     is_builtin=True, tags=["deploy", "infra", "ci-cd"]),

            AgentDef(id="product", name="Laura Vidal", role="Product Owner",
                     description="Business value, user stories, acceptance criteria. WSJF prioritization.",
                     provider="minimax", model="MiniMax-M2.5",
                     temperature=0.5, max_tokens=4096,
                     icon="clipboard", color="#f78166",
                     avatar="LV", tagline="Value over features",
                     is_builtin=True, tags=["product", "business"]),

            AgentDef(id="tester", name="Éric Fontaine", role="QA Engineer",
                     description="E2E tests, smoke tests, regression. Playwright specialist.",
                     provider="minimax", model="MiniMax-M2.5",
                     temperature=0.3, max_tokens=4096,
                     icon="flask", color="#a371f7",
                     avatar="EF", tagline="If it's not tested, it's broken",
                     is_builtin=True, tags=["testing", "e2e", "qa"]),
        ]

        for agent in builtins:
            self.create(agent)

    def _seed_from_yaml(self):
        """Load agent definitions from YAML files in platform/skills/definitions/."""
        import yaml
        defs_dir = Path(__file__).parent.parent / "skills" / "definitions"
        if not defs_dir.exists():
            return

        # Icon/color mapping by SAFe level or role
        ROLE_STYLES = {
            "portfolio": ("building", "#bc8cff"),
            "solution": ("layers", "#58a6ff"),
            "art": ("users", "#d29922"),
            "team": ("code", "#3fb950"),
            "transverse": ("settings", "#f78166"),
        }

        for path in sorted(defs_dir.glob("*.yaml")):
            if path.stem.startswith("_"):
                continue
            # Skip if already exists in DB (from builtins or prior seed)
            if self.get(path.stem):
                continue
            try:
                raw = yaml.safe_load(path.read_text(encoding="utf-8"))
                if not raw or not isinstance(raw, dict):
                    continue

                agent_id = raw.get("id", path.stem)
                if self.get(agent_id):
                    continue

                tags = raw.get("tags", [])
                level = next((t for t in tags if t in ROLE_STYLES), "team")
                icon, color = ROLE_STYLES.get(level, ("bot", "#f78166"))

                perms = raw.get("permissions", {})
                perm_dict = {}
                if perms.get("can_veto"):
                    perm_dict["can_veto"] = True
                if perms.get("can_approve"):
                    perm_dict["can_approve"] = True
                if perms.get("can_delegate"):
                    perm_dict["can_delegate"] = True

                # Extract persona text from traits or top-level field
                persona_obj = raw.get("persona", {})
                persona_desc = ""
                if isinstance(persona_obj, dict):
                    persona_desc = persona_obj.get("description", "").strip()
                    traits = persona_obj.get("traits", [])
                    if traits:
                        persona_desc += " " + ". ".join(str(t) for t in traits) + "."

                agent = AgentDef(
                    id=agent_id,
                    name=raw.get("name", agent_id),
                    role=raw.get("role", raw.get("id", "worker")),
                    description=persona_desc,
                    system_prompt=raw.get("system_prompt", ""),
                    provider=raw.get("llm", {}).get("provider", "minimax") if isinstance(raw.get("llm"), dict) else "minimax",
                    model=raw.get("llm", {}).get("model", "MiniMax-M2.5") if isinstance(raw.get("llm"), dict) else "MiniMax-M2.5",
                    temperature=raw.get("llm", {}).get("temperature", 0.7) if isinstance(raw.get("llm"), dict) else 0.7,
                    max_tokens=raw.get("llm", {}).get("max_tokens", 4096) if isinstance(raw.get("llm"), dict) else 4096,
                    skills=raw.get("skills", []),
                    tools=raw.get("tools", []),
                    permissions=perm_dict,
                    tags=tags,
                    icon=icon,
                    color=color,
                    avatar=raw.get("avatar", ""),
                    tagline=raw.get("tagline", ""),
                    persona=persona_desc,
                    motivation=raw.get("motivation", "").strip() if raw.get("motivation") else "",
                    hierarchy_rank=raw.get("hierarchy_rank", 50),
                    is_builtin=True,
                )
                self.create(agent)
            except Exception:
                pass

_store: Optional[AgentStore] = None


def get_agent_store() -> AgentStore:
    global _store
    if _store is None:
        _store = AgentStore()
    return _store
