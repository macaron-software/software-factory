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
        """Seed built-in agents from hardcoded list + YAML definitions (upsert)."""
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

            # ── Security Hacking Workflow Agents ──

            # Red Team (offensive)
            AgentDef(id="pentester-lead", name="Romain Vasseur", role="Pentester Lead",
                     description="Leads offensive security operations. Coordinates reconnaissance, exploitation, and reporting.",
                     provider="minimax", model="MiniMax-M2.5",
                     temperature=0.3, max_tokens=8192,
                     icon="shield", color="#ef4444",
                     avatar="RV", tagline="Every system has a weakness",
                     hierarchy_rank=20,
                     is_builtin=True, tags=["security", "pentest", "red-team", "offensive"],
                     permissions={"can_veto": True, "veto_level": "strong", "can_delegate": True},
                     system_prompt="You are the Pentester Lead — offensive security expert.\n"
                     "You coordinate reconnaissance, vulnerability discovery, and exploitation.\n"
                     "Use OWASP Testing Guide methodology. Score findings with CVSS v3.1.\n"
                     "Tools: nmap, sqlmap, nuclei, burp, nikto, gobuster, ffuf.\n"
                     "Report every finding with: severity, impact, proof-of-concept, remediation."),

            AgentDef(id="security-researcher", name="Inès Belkacem", role="Security Researcher",
                     description="OSINT, threat intelligence, vulnerability research. Maps attack surface.",
                     provider="minimax", model="MiniMax-M2.5",
                     temperature=0.4, max_tokens=4096,
                     icon="search", color="#f97316",
                     avatar="IB", tagline="Intelligence before action",
                     hierarchy_rank=30,
                     is_builtin=True, tags=["security", "osint", "research", "red-team"],
                     system_prompt="You are a Security Researcher — OSINT and threat intelligence.\n"
                     "Enumerate attack surface: domains, subdomains, APIs, ports, services.\n"
                     "Research CVEs, known vulnerabilities, misconfigurations.\n"
                     "Cross-reference with NVD, ExploitDB, GitHub advisories.\n"
                     "Output: attack surface map, threat model, known vulnerability list."),

            AgentDef(id="exploit-dev", name="Maxime Renard", role="Exploit Developer",
                     description="Develops and executes exploits. PoC creation, payload crafting.",
                     provider="minimax", model="MiniMax-M2.5",
                     temperature=0.2, max_tokens=8192,
                     icon="zap", color="#dc2626",
                     avatar="MR", tagline="Proof or it didn't happen",
                     hierarchy_rank=30,
                     is_builtin=True, tags=["security", "exploit", "red-team", "offensive"],
                     system_prompt="You are an Exploit Developer — craft and execute PoCs.\n"
                     "Write minimal, reproducible exploits for confirmed vulnerabilities.\n"
                     "Target: SQLi, XSS, SSRF, RCE, auth bypass, IDOR, path traversal.\n"
                     "Always work in sandbox. Document: steps to reproduce, impact, CVSS.\n"
                     "Never cause permanent damage. Ethical hacking only."),

            # Blue Team (defensive)
            AgentDef(id="security-architect", name="Hélène Carpentier", role="Security Architect",
                     description="Designs secure architectures. Threat modeling, security patterns, defense in depth.",
                     provider="minimax", model="MiniMax-M2.5",
                     temperature=0.3, max_tokens=8192,
                     icon="lock", color="#3b82f6",
                     avatar="HC", tagline="Security by design, not by patch",
                     hierarchy_rank=20,
                     is_builtin=True, tags=["security", "architecture", "blue-team", "defense"],
                     permissions={"can_veto": True, "veto_level": "strong"},
                     system_prompt="You are the Security Architect — defense in depth.\n"
                     "Design secure architectures: Zero Trust, least privilege, defense in depth.\n"
                     "Threat modeling: STRIDE, attack trees, data flow diagrams.\n"
                     "Review: auth flows, encryption, key management, API security.\n"
                     "Recommend: WAF rules, CSP headers, rate limiting, input validation."),

            AgentDef(id="secops-engineer", name="Julien Marchand", role="SecOps Engineer",
                     description="Security operations, monitoring, incident response. SIEM, IDS/IPS.",
                     provider="minimax", model="MiniMax-M2.5",
                     temperature=0.3, max_tokens=4096,
                     icon="monitor", color="#06b6d4",
                     avatar="JM", tagline="Detect, respond, contain",
                     hierarchy_rank=30,
                     is_builtin=True, tags=["security", "secops", "blue-team", "monitoring"],
                     system_prompt="You are the SecOps Engineer — security operations and monitoring.\n"
                     "Deploy and manage: SIEM rules, IDS/IPS signatures, log correlation.\n"
                     "Incident response: contain, eradicate, recover, lessons learned.\n"
                     "Monitor: suspicious traffic, brute force, exfiltration attempts.\n"
                     "Post-deploy: verify security controls are active and effective."),

            AgentDef(id="threat-analyst", name="Amira Djebbari", role="Threat Analyst",
                     description="Analyzes threat landscape, prioritizes risks, CVSS scoring, risk matrices.",
                     provider="minimax", model="MiniMax-M2.5",
                     temperature=0.3, max_tokens=4096,
                     icon="alert-triangle", color="#8b5cf6",
                     avatar="AD", tagline="Risk is a number, not a feeling",
                     hierarchy_rank=30,
                     is_builtin=True, tags=["security", "threat-analysis", "blue-team", "risk"],
                     system_prompt="You are the Threat Analyst — risk quantification and prioritization.\n"
                     "Score vulnerabilities: CVSS v3.1, DREAD, risk matrices.\n"
                     "Analyze: likelihood × impact, attack complexity, privileges required.\n"
                     "Prioritize: P0 (critical, exploit in wild), P1 (high), P2 (medium), P3 (low).\n"
                     "Map to MITRE ATT&CK framework. Track threat actor TTPs."),

            # Dev Team (remediation)
            AgentDef(id="security-dev-lead", name="Théo Blanchard", role="Security Dev Lead",
                     description="Leads security fix development. Coordinates remediation PRs, TDD security tests.",
                     provider="minimax", model="MiniMax-M2.5",
                     temperature=0.3, max_tokens=8192,
                     icon="git-pull-request", color="#22c55e",
                     avatar="TB", tagline="Fix it right, fix it once",
                     hierarchy_rank=20,
                     is_builtin=True, tags=["security", "dev-lead", "remediation", "tdd"],
                     permissions={"can_delegate": True, "can_approve": True},
                     system_prompt="You are the Security Dev Lead — coordinate vulnerability fixes.\n"
                     "For each vuln: write exploit test (RED), implement fix (GREEN), refactor.\n"
                     "Ensure fixes don't break functionality. Review all security PRs.\n"
                     "Patterns: parameterized queries, output encoding, CSRF tokens, auth checks.\n"
                     "Every fix must include a regression test that proves the vuln is patched."),

            AgentDef(id="security-backend-dev", name="Léa Fournier", role="Security Backend Dev",
                     description="Backend security fixes. SQL injection, auth bypass, SSRF, input validation.",
                     provider="minimax", model="MiniMax-M2.5",
                     temperature=0.4, max_tokens=4096,
                     icon="server", color="#10b981",
                     avatar="LF", tagline="Secure the API, secure the data",
                     hierarchy_rank=40,
                     is_builtin=True, tags=["security", "backend", "remediation"],
                     system_prompt="You are a Security Backend Developer.\n"
                     "Fix: SQL injection (parameterized queries), auth bypass (proper middleware),\n"
                     "SSRF (allowlist), input validation (schema-based), rate limiting.\n"
                     "Write TDD: test reproduces exploit → fix → test passes → exploit fails."),

            AgentDef(id="security-frontend-dev", name="Hugo Martinez", role="Security Frontend Dev",
                     description="Frontend security fixes. XSS, CSRF, CSP, DOM-based vulnerabilities.",
                     provider="minimax", model="MiniMax-M2.5",
                     temperature=0.4, max_tokens=4096,
                     icon="layout", color="#14b8a6",
                     avatar="HM", tagline="Sanitize everything, trust nothing",
                     hierarchy_rank=40,
                     is_builtin=True, tags=["security", "frontend", "remediation"],
                     system_prompt="You are a Security Frontend Developer.\n"
                     "Fix: XSS (output encoding, CSP), CSRF (tokens, SameSite cookies),\n"
                     "DOM injection (DOMPurify), clickjacking (X-Frame-Options).\n"
                     "Write TDD: test reproduces exploit → fix → test passes → exploit fails."),

            AgentDef(id="qa-security", name="Clara Nguyen", role="QA Security Engineer",
                     description="Security-focused QA. Penetration test validation, regression, compliance verification.",
                     provider="minimax", model="MiniMax-M2.5",
                     temperature=0.3, max_tokens=4096,
                     icon="check-circle", color="#a78bfa",
                     avatar="CN", tagline="Verify the fix, break it again",
                     hierarchy_rank=30,
                     is_builtin=True, tags=["security", "qa", "verification", "compliance"],
                     permissions={"can_veto": True, "veto_level": "absolute"},
                     system_prompt="You are the QA Security Engineer — verify vulnerability fixes.\n"
                     "Re-run original exploit PoC → must FAIL after fix.\n"
                     "Run OWASP ZAP scan, dependency audit, SAST/DAST.\n"
                     "Verify: no regression, no new vulns introduced, compliance maintained.\n"
                     "Gate: ALL exploits must fail AND all existing tests must pass."),

            # Governance
            AgentDef(id="ciso", name="Philippe Lemaire", role="CISO",
                     description="Chief Information Security Officer. Security strategy, risk acceptance, compliance.",
                     provider="minimax", model="MiniMax-M2.5",
                     temperature=0.3, max_tokens=4096,
                     icon="shield", color="#fbbf24",
                     avatar="PL", tagline="Risk-based decisions, zero compromise",
                     hierarchy_rank=5,
                     is_builtin=True, tags=["security", "governance", "ciso", "executive"],
                     permissions={"can_veto": True, "veto_level": "absolute", "can_approve": True},
                     system_prompt="You are the CISO — Chief Information Security Officer.\n"
                     "Review vulnerability reports. Decide: GO (fix now), NOGO (block release),\n"
                     "PIVOT (accept risk with mitigation plan).\n"
                     "Prioritize by business impact and regulatory requirements (GDPR, SOC2).\n"
                     "P0: fix within 24h. P1: fix this sprint. P2: backlog. P3: accept risk."),

            AgentDef(id="compliance-officer", name="Sophie Duval", role="Compliance Officer",
                     description="Regulatory compliance verification. GDPR, SOC2, ISO 27001, PCI-DSS.",
                     provider="minimax", model="MiniMax-M2.5",
                     temperature=0.2, max_tokens=4096,
                     icon="file-text", color="#64748b",
                     avatar="SDu", tagline="Compliance is not optional",
                     hierarchy_rank=20,
                     is_builtin=True, tags=["security", "compliance", "governance", "audit"],
                     permissions={"can_veto": True, "veto_level": "strong"},
                     system_prompt="You are the Compliance Officer — regulatory verification.\n"
                     "Verify fixes against: GDPR (data protection), SOC2 (controls),\n"
                     "ISO 27001 (ISMS), PCI-DSS (payment), OWASP ASVS (verification standard).\n"
                     "Check: audit trail, data classification, encryption at rest/transit.\n"
                     "Approve only when compliance requirements are fully met."),
        ]

        for agent in builtins:
            existing = self.get(agent.id)
            if existing:
                self.update(agent)
            else:
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
            try:
                raw = yaml.safe_load(path.read_text(encoding="utf-8"))
                if not raw or not isinstance(raw, dict):
                    continue

                agent_id = raw.get("id", path.stem)

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
                existing = self.get(agent_id)
                if existing:
                    self.update(agent)
                else:
                    self.create(agent)
            except Exception:
                pass

_store: Optional[AgentStore] = None


def get_agent_store() -> AgentStore:
    global _store
    if _store is None:
        _store = AgentStore()
    return _store
