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
    is_builtin: bool = False
    created_at: str = ""
    updated_at: str = ""


def _row_to_agent(row) -> AgentDef:
    return AgentDef(
        id=row["id"],
        name=row["name"],
        role=row["role"],
        description=row["description"] or "",
        system_prompt=row["system_prompt"] or "",
        provider=row["provider"] or "minimax",
        model=row["model"] or "claude-sonnet-4-20250514",
        temperature=row["temperature"],
        max_tokens=row["max_tokens"],
        skills=json.loads(row["skills_json"] or "[]"),
        tools=json.loads(row["tools_json"] or "[]"),
        mcps=json.loads(row["mcps_json"] or "[]"),
        permissions=json.loads(row["permissions_json"] or "{}"),
        tags=json.loads(row["tags_json"] or "[]"),
        icon=row["icon"] or "bot",
        color=row["color"] or "#f78166",
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
                   mcps_json, permissions_json, tags_json, icon, color, is_builtin,
                   created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (agent.id, agent.name, agent.role, agent.description, agent.system_prompt,
                 agent.provider, agent.model, agent.temperature, agent.max_tokens,
                 json.dumps(agent.skills), json.dumps(agent.tools),
                 json.dumps(agent.mcps), json.dumps(agent.permissions),
                 json.dumps(agent.tags), agent.icon, agent.color,
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
                   icon=?, color=?, updated_at=?
                   WHERE id=?""",
                (agent.name, agent.role, agent.description, agent.system_prompt,
                 agent.provider, agent.model, agent.temperature, agent.max_tokens,
                 json.dumps(agent.skills), json.dumps(agent.tools),
                 json.dumps(agent.mcps), json.dumps(agent.permissions),
                 json.dumps(agent.tags), agent.icon, agent.color,
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
        """Seed built-in agents from YAML definitions if DB is empty."""
        if self.count() > 0:
            return

        builtins = [
            AgentDef(id="brain", name="Brain", role="brain",
                     description="Strategic orchestrator. Deep recursive analysis, task decomposition, WSJF prioritization.",
                     provider="minimax", model="MiniMax-M2.5",
                     temperature=0.3, max_tokens=8192,
                     icon="building", color="#bc8cff", is_builtin=True,
                     tags=["orchestrator", "planning"],
                     system_prompt="You are the Brain — strategic orchestrator of the Software Factory.\n"
                     "Your role: analyze codebases deeply, decompose into atomic tasks (FRACTAL),\n"
                     "prioritize by WSJF, and coordinate workers. Use CoVe (Chain-of-Verification)\n"
                     "to validate every claim before acting. Never hallucinate — verify with tools."),

            AgentDef(id="worker", name="TDD Worker", role="worker",
                     description="Writes code following strict TDD: Red → Green → Refactor. Atomic, KISS.",
                     provider="minimax", model="MiniMax-M2.5",
                     temperature=0.4, max_tokens=4096,
                     icon="code", color="#58a6ff", is_builtin=True,
                     tags=["coding", "tdd"],
                     system_prompt="You are a TDD Worker. Write code following strict Red-Green-Refactor.\n"
                     "Each task is atomic and KISS. Write the test FIRST, then minimal code to pass.\n"
                     "Never skip tests. Never use .unwrap() in Rust. Handle all errors explicitly."),

            AgentDef(id="code-critic", name="Code Critic", role="critic",
                     description="Reviews code for quality: SLOP detection, API misuse, syntax/logic errors.",
                     provider="minimax", model="MiniMax-M2.5",
                     temperature=0.2, max_tokens=4096,
                     icon="eye", color="#d29922", is_builtin=True,
                     tags=["review", "quality"],
                     permissions={"can_veto": True, "veto_level": "absolute"},
                     system_prompt="You are the Code Critic. Review code for:\n"
                     "- SLOP (code that compiles but does nothing useful)\n"
                     "- test.skip(), @ts-ignore, #[ignore] — ALWAYS REJECT\n"
                     "- Empty catch blocks, unused imports, dead code\n"
                     "- API misuse (wrong extractors, missing FromRow derives)\n"
                     "Use CoVe: Draft assessment → Verify claims → Final decision."),

            AgentDef(id="security-critic", name="Security Critic", role="critic",
                     description="OWASP Top 10, secrets detection, SQL injection, XSS analysis.",
                     provider="minimax", model="MiniMax-M2.5",
                     temperature=0.1, max_tokens=4096,
                     icon="lock", color="#f85149", is_builtin=True,
                     tags=["security", "owasp"],
                     permissions={"can_veto": True, "veto_level": "absolute"},
                     system_prompt="You are the Security Critic (cognitive diversity: different LLM provider).\n"
                     "Analyze code for OWASP Top 10: SQL injection, XSS, command injection,\n"
                     "secrets in code (not in fixtures/tests), insecure auth, CSRF.\n"
                     "Secrets in test fixtures are OK. CLI print() is OK. Focus on REAL vulnerabilities."),

            AgentDef(id="arch-critic", name="Architecture Critic", role="critic",
                     description="Reviews RBAC, input validation, error handling, API design patterns.",
                     provider="nvidia", model="moonshotai/kimi-k2-instruct",
                     temperature=0.3, max_tokens=4096,
                     icon="building", color="#bc8cff", is_builtin=True,
                     tags=["architecture", "design"],
                     permissions={"can_veto": True, "veto_level": "strong"},
                     system_prompt="You are the Architecture Critic. Review for:\n"
                     "- RBAC/Auth coverage on all endpoints\n"
                     "- Input validation completeness\n"
                     "- Error handling (all HTTP status codes covered)\n"
                     "- API design (pagination, rate limiting, versioning)\n"
                     "- Proper separation of concerns"),

            AgentDef(id="devops", name="DevOps", role="devops",
                     description="Infrastructure, deployment pipelines, Docker, nginx, monitoring.",
                     provider="nvidia", model="moonshotai/kimi-k2-instruct",
                     temperature=0.3, max_tokens=4096,
                     icon="rocket", color="#3fb950", is_builtin=True,
                     tags=["infra", "deploy", "docker"],
                     system_prompt="You are the DevOps agent. Handle:\n"
                     "- Docker builds, compose files, multi-stage optimization\n"
                     "- Nginx configuration (proxy_pass, SSL, caching)\n"
                     "- CI/CD pipelines, deployment stages\n"
                     "- Infrastructure health checks (CoVe-based diagnosis)\n"
                     "NEVER skip infrastructure checks. FIX > SKIP."),

            AgentDef(id="chef-projet", name="Chef de Projet", role="pm",
                     description="Project management: planning, priorities, deadlines, team coordination.",
                     provider="minimax", model="MiniMax-M2.5",
                     temperature=0.5, max_tokens=4096,
                     icon="clipboard", color="#58a6ff", is_builtin=True,
                     tags=["planning", "coordination"],
                     system_prompt="You are the Chef de Projet. Your role:\n"
                     "- Plan sprints and prioritize backlog (WSJF)\n"
                     "- Track progress and identify blockers\n"
                     "- Coordinate between Brain, Workers, and Critics\n"
                     "- Ensure AO traceability on all features"),

            AgentDef(id="testeur", name="Testeur", role="tester",
                     description="E2E testing: Playwright smoke, API tests, browser workflows.",
                     provider="minimax", model="MiniMax-M2.5",
                     temperature=0.3, max_tokens=4096,
                     icon="flask", color="#d29922", is_builtin=True,
                     tags=["testing", "e2e", "playwright"],
                     system_prompt="You are the Testeur. Write and run tests:\n"
                     "- Smoke IHM: page loads, HTTP 200, 0 console errors\n"
                     "- E2E API: fetch direct, guards 401/403, failures 400/404/409\n"
                     "- E2E IHM: real clicks, full workflows, multi-user scenarios\n"
                     "NEVER use test.skip(). All tests MUST run."),

            AgentDef(id="metier", name="Expert Métier", role="domain",
                     description="Domain expertise: business rules, AO compliance, user needs.",
                     provider="nvidia", model="moonshotai/kimi-k2-instruct",
                     temperature=0.5, max_tokens=4096,
                     icon="briefcase", color="#f78166", is_builtin=True,
                     tags=["business", "domain", "ao"],
                     system_prompt="You are the Expert Métier. Your role:\n"
                     "- Define business rules and validate implementations\n"
                     "- Ensure AO (Appel d'Offres) compliance on all features\n"
                     "- Validate user stories against real user needs\n"
                     "- Challenge technical decisions from business perspective"),
        ]

        for agent in builtins:
            self.create(agent)


_store: Optional[AgentStore] = None


def get_agent_store() -> AgentStore:
    global _store
    if _store is None:
        _store = AgentStore()
    return _store
