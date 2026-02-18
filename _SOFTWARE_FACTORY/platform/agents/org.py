"""Org Tree Store — SAFe hierarchy: Portfolio → ART → Team.

Provides CRUD and seeding for organizational structure.
Maps agents to teams for capacity planning and governance.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from ..db.migrations import get_db

logger = logging.getLogger(__name__)


@dataclass
class Portfolio:
    id: str = ""
    name: str = ""
    description: str = ""
    lead_agent_id: str = ""
    budget_allocated: float = 0
    budget_consumed: float = 0
    fiscal_year: int = 2025
    created_at: str = ""


@dataclass
class ART:
    """Agile Release Train — groups teams under a portfolio."""
    id: str = ""
    name: str = ""
    portfolio_id: str = ""
    description: str = ""
    lead_agent_id: str = ""
    pi_cadence_weeks: int = 10
    created_at: str = ""


@dataclass
class Team:
    id: str = ""
    name: str = ""
    art_id: str = ""
    description: str = ""
    scrum_master_id: str = ""
    capacity: int = 5
    wip_limit: int = 3
    members: list[dict] = field(default_factory=list)
    created_at: str = ""


class OrgStore:
    """CRUD for organizational hierarchy."""

    # ── Portfolios ───────────────────────────────────────────────

    def list_portfolios(self) -> list[Portfolio]:
        db = get_db()
        try:
            rows = db.execute("SELECT * FROM org_portfolios ORDER BY name").fetchall()
            return [Portfolio(**{k: r[k] for k in r.keys()}) for r in rows]
        except Exception:
            return []
        finally:
            db.close()

    def get_portfolio(self, pid: str) -> Optional[Portfolio]:
        db = get_db()
        try:
            r = db.execute("SELECT * FROM org_portfolios WHERE id=?", (pid,)).fetchone()
            return Portfolio(**{k: r[k] for k in r.keys()}) if r else None
        except Exception:
            return None
        finally:
            db.close()

    def create_portfolio(self, p: Portfolio) -> Portfolio:
        db = get_db()
        try:
            db.execute(
                "INSERT OR REPLACE INTO org_portfolios (id,name,description,lead_agent_id,budget_allocated,budget_consumed,fiscal_year) VALUES (?,?,?,?,?,?,?)",
                (p.id, p.name, p.description, p.lead_agent_id, p.budget_allocated, p.budget_consumed, p.fiscal_year))
            db.commit()
        finally:
            db.close()
        return p

    # ── ARTs ─────────────────────────────────────────────────────

    def list_arts(self, portfolio_id: str = "") -> list[ART]:
        db = get_db()
        try:
            if portfolio_id:
                rows = db.execute("SELECT * FROM org_arts WHERE portfolio_id=? ORDER BY name", (portfolio_id,)).fetchall()
            else:
                rows = db.execute("SELECT * FROM org_arts ORDER BY name").fetchall()
            return [ART(**{k: r[k] for k in r.keys()}) for r in rows]
        except Exception:
            return []
        finally:
            db.close()

    def create_art(self, a: ART) -> ART:
        db = get_db()
        try:
            db.execute(
                "INSERT OR REPLACE INTO org_arts (id,name,portfolio_id,description,lead_agent_id,pi_cadence_weeks) VALUES (?,?,?,?,?,?)",
                (a.id, a.name, a.portfolio_id, a.description, a.lead_agent_id, a.pi_cadence_weeks))
            db.commit()
        finally:
            db.close()
        return a

    # ── Teams ────────────────────────────────────────────────────

    def list_teams(self, art_id: str = "") -> list[Team]:
        db = get_db()
        try:
            if art_id:
                rows = db.execute("SELECT * FROM org_teams WHERE art_id=? ORDER BY name", (art_id,)).fetchall()
            else:
                rows = db.execute("SELECT * FROM org_teams ORDER BY name").fetchall()
            teams = []
            for r in rows:
                t = Team(id=r["id"], name=r["name"], art_id=r["art_id"],
                         description=r["description"] or "", scrum_master_id=r["scrum_master_id"] or "",
                         capacity=r["capacity"] or 5, wip_limit=r["wip_limit"] or 3,
                         created_at=r["created_at"] or "")
                # Load members
                members = db.execute(
                    "SELECT tm.agent_id, tm.role, a.name as agent_name FROM org_team_members tm LEFT JOIN agents a ON tm.agent_id=a.id WHERE tm.team_id=?",
                    (t.id,)).fetchall()
                t.members = [{"agent_id": m["agent_id"], "role": m["role"], "name": m["agent_name"] or m["agent_id"]} for m in members]
                teams.append(t)
            return teams
        except Exception:
            return []
        finally:
            db.close()

    def create_team(self, t: Team) -> Team:
        db = get_db()
        try:
            db.execute(
                "INSERT OR REPLACE INTO org_teams (id,name,art_id,description,scrum_master_id,capacity,wip_limit) VALUES (?,?,?,?,?,?,?)",
                (t.id, t.name, t.art_id, t.description, t.scrum_master_id, t.capacity, t.wip_limit))
            for m in t.members:
                db.execute(
                    "INSERT OR REPLACE INTO org_team_members (team_id,agent_id,role) VALUES (?,?,?)",
                    (t.id, m.get("agent_id", ""), m.get("role", "member")))
            db.commit()
        finally:
            db.close()
        return t

    # ── Full tree ────────────────────────────────────────────────

    def get_org_tree(self) -> list[dict]:
        """Return full org tree: portfolios → arts → teams with agents."""
        tree = []
        for portfolio in self.list_portfolios():
            p_node = {
                "type": "portfolio", "id": portfolio.id, "name": portfolio.name,
                "lead": portfolio.lead_agent_id, "budget": portfolio.budget_allocated,
                "budget_consumed": portfolio.budget_consumed,
                "children": [],
            }
            for art in self.list_arts(portfolio.id):
                a_node = {
                    "type": "art", "id": art.id, "name": art.name,
                    "lead": art.lead_agent_id, "pi_cadence": art.pi_cadence_weeks,
                    "children": [],
                }
                for team in self.list_teams(art.id):
                    t_node = {
                        "type": "team", "id": team.id, "name": team.name,
                        "scrum_master": team.scrum_master_id,
                        "capacity": team.capacity, "wip_limit": team.wip_limit,
                        "members": team.members,
                    }
                    a_node["children"].append(t_node)
                p_node["children"].append(a_node)
            tree.append(p_node)
        return tree

    # ── Seed default org ─────────────────────────────────────────

    def seed_default(self):
        """Seed a default DSI org structure if empty."""
        existing = self.list_portfolios()
        if existing:
            return

        # Portfolio: Macaron DSI
        self.create_portfolio(Portfolio(
            id="portfolio-dsi", name="DSI Macaron",
            description="Portefeuille principal de la DSI — tous projets logiciels",
            lead_agent_id="dsi", budget_allocated=500000, fiscal_year=2025,
        ))

        # ART 1: Platform & Core
        self.create_art(ART(
            id="art-platform", name="ART Platform & Core",
            portfolio_id="portfolio-dsi",
            description="Plateformes internes: Factory, Macaron Platform, Solaris Design System",
            lead_agent_id="release_train_engineer",
            pi_cadence_weeks=10,
        ))

        # ART 2: Products
        self.create_art(ART(
            id="art-products", name="ART Produits",
            portfolio_id="portfolio-dsi",
            description="Produits métier: Popinz, YoloNow, Finary, Veligo, PSY",
            lead_agent_id="release_train_engineer",
            pi_cadence_weeks=10,
        ))

        # ART 3: Services
        self.create_art(ART(
            id="art-services", name="ART Services & Support",
            portfolio_id="portfolio-dsi",
            description="Services: LPD, Logs Facteur, Sharelook, Fervenza IoT",
            lead_agent_id="release_train_engineer",
            pi_cadence_weeks=10,
        ))

        # Teams
        platform_teams = [
            Team(id="team-factory", name="Team Factory", art_id="art-platform",
                 description="Software Factory self-improvement", scrum_master_id="scrum_master",
                 members=[
                     {"agent_id": "lead-dev", "role": "lead"},
                     {"agent_id": "dev-senior-1", "role": "senior"},
                     {"agent_id": "dev-backend", "role": "member"},
                     {"agent_id": "qa-lead", "role": "qa"},
                 ]),
            Team(id="team-platform", name="Team Platform", art_id="art-platform",
                 description="Macaron Agent Platform development", scrum_master_id="scrum_master",
                 members=[
                     {"agent_id": "lead-dev", "role": "lead"},
                     {"agent_id": "dev-fullstack", "role": "member"},
                     {"agent_id": "dev-frontend", "role": "member"},
                     {"agent_id": "devops", "role": "devops"},
                 ]),
            Team(id="team-design", name="Team Design System", art_id="art-platform",
                 description="Solaris Design System for La Poste", scrum_master_id="scrum_master",
                 members=[
                     {"agent_id": "ux-designer", "role": "lead"},
                     {"agent_id": "dev-frontend", "role": "member"},
                     {"agent_id": "accessibility", "role": "a11y"},
                 ]),
        ]
        product_teams = [
            Team(id="team-popinz", name="Team Popinz", art_id="art-products",
                 description="Popinz SaaS", scrum_master_id="scrum_master",
                 members=[
                     {"agent_id": "lead-dev", "role": "lead"},
                     {"agent_id": "dev-mobile", "role": "mobile"},
                     {"agent_id": "dev-backend", "role": "backend"},
                 ]),
            Team(id="team-veligo", name="Team Veligo", art_id="art-products",
                 description="Veligo Platform", scrum_master_id="scrum_master",
                 members=[
                     {"agent_id": "lead-dev", "role": "lead"},
                     {"agent_id": "dev-fullstack", "role": "member"},
                     {"agent_id": "qa-lead", "role": "qa"},
                 ]),
        ]
        service_teams = [
            Team(id="team-sharelook", name="Team Sharelook", art_id="art-services",
                 description="Sharelook & Migrations", scrum_master_id="scrum_master",
                 members=[
                     {"agent_id": "lead-dev", "role": "lead"},
                     {"agent_id": "dev-frontend", "role": "frontend"},
                     {"agent_id": "devsecops", "role": "security"},
                 ]),
            Team(id="team-services", name="Team Services", art_id="art-services",
                 description="LPD, Logs Facteur, Fervenza IoT", scrum_master_id="scrum_master",
                 members=[
                     {"agent_id": "dev-backend", "role": "backend"},
                     {"agent_id": "devops", "role": "devops"},
                 ]),
        ]
        for t in platform_teams + product_teams + service_teams:
            self.create_team(t)

        logger.info("[Org] Seeded default org: 1 portfolio, 3 ARTs, %d teams",
                    len(platform_teams) + len(product_teams) + len(service_teams))


# Singleton
_store: Optional[OrgStore] = None


def get_org_store() -> OrgStore:
    global _store
    if _store is None:
        _store = OrgStore()
    return _store
