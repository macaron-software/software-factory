"""
SF Native Commands — Software Factory specific CLI commands
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


class SFCommandRequest(BaseModel):
    """SF command request."""

    command: str
    args: list[str] = []


class SFCommandResponse(BaseModel):
    """SF command response."""

    success: bool
    output: str
    error: str = ""
    data: dict[str, Any] | None = None


def format_table(headers: list[str], rows: list[list[str]]) -> str:
    """Format data as ASCII table."""
    if not rows:
        return "No data"

    # Calculate column widths
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))

    # Build table
    lines = []

    # Header
    header_line = "  ".join(
        h.ljust(w) for h, w in zip(headers, col_widths, strict=True)
    )
    lines.append(header_line)
    lines.append("-" * len(header_line))

    # Rows
    for row in rows:
        lines.append(
            "  ".join(
                str(cell).ljust(w) for cell, w in zip(row, col_widths, strict=False)
            )
        )

    return "\n".join(lines)


async def cmd_platform_status() -> SFCommandResponse:
    """Get platform status."""
    from ...agents.store import get_agent_store
    from ...epics.store import get_epic_store
    from ...projects.manager import get_project_store
    from ...skills.library import get_skill_library

    try:
        agent_store = get_agent_store()
        epic_store = get_epic_store()
        project_store = get_project_store()
        skill_library = get_skill_library()

        agents = agent_store.list_all()
        missions = epic_store.list_missions(limit=500)
        projects = project_store.list_all()
        skills = skill_library.scan_all()

        # Count running missions
        running = sum(1 for m in missions if m.status in ["running", "in_progress"])

        output = f"""Software Factory Platform Status
================================

✓ Platform: Online
✓ Version: 1.0.0

Resources:
  • Agents:    {len(agents)} active
  • Missions:  {len(missions)} total ({running} running)
  • Projects:  {len(projects)} registered
  • Skills:    {len(skills)} available

System:
  • Database:  SQLite (platform.db)
  • Port:      8099 (dev) / 8090 (prod)
  • Status:    Operational

Last check: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

        return SFCommandResponse(
            success=True,
            output=output,
            data={
                "agents": len(agents),
                "epics": len(missions),
                "projects": len(projects),
                "skills": len(skills),
                "running_missions": running,
            },
        )
    except Exception as e:
        logger.exception("Error in platform status")
        return SFCommandResponse(success=False, output="", error=f"Error: {str(e)}")


async def cmd_missions_list(args: list[str]) -> SFCommandResponse:
    """List missions with filters."""
    from ...epics.store import get_epic_store

    try:
        store = get_epic_store()
        limit = 20
        status_filter = None

        # Parse args
        for arg in args:
            if arg.startswith("--limit="):
                limit = int(arg.split("=")[1])
            elif arg.startswith("--status="):
                status_filter = arg.split("=")[1]

        missions = store.list_missions(limit=limit)

        # Filter by status if specified
        if status_filter:
            missions = [m for m in missions if m.status == status_filter]

        if not missions:
            return SFCommandResponse(
                success=True, output="No missions found", data={"count": 0}
            )

        # Format as table
        headers = ["ID", "Name", "Type", "Status", "Agent", "Created"]
        rows = []
        for m in missions[:limit]:
            rows.append(
                [
                    m.id[:8],
                    getattr(m, "name", getattr(m, "title", "untitled"))[:40],
                    getattr(m, "type", "generic") or "generic",
                    getattr(m, "status", "pending") or "pending",
                    m.agent_id[:15]
                    if hasattr(m, "agent_id") and m.agent_id
                    else "none",
                    str(m.created_at)[:10]
                    if hasattr(m, "created_at") and m.created_at
                    else "unknown",
                ]
            )

        output = f"Missions ({len(missions)} total)\n\n"
        output += format_table(headers, rows)

        if len(missions) > limit:
            output += f"\n\n... {len(missions) - limit} more missions (use --limit=N to see more)"

        return SFCommandResponse(
            success=True, output=output, data={"count": len(missions)}
        )
    except Exception as e:
        logger.exception("Error listing missions")
        return SFCommandResponse(success=False, output="", error=f"Error: {str(e)}")


async def cmd_missions_show(mission_id: str) -> SFCommandResponse:
    """Show mission details."""
    from ...epics.store import get_epic_store

    try:
        store = get_epic_store()
        mission = store.get(mission_id)

        if not mission:
            return SFCommandResponse(
                success=False, output="", error=f"Mission not found: {mission_id}"
            )

        output = f"""Mission Details
===============

ID:          {mission.id}
Name:        {getattr(mission, "name", getattr(mission, "title", "untitled"))}
Type:        {getattr(mission, "type", "generic") or "generic"}
Status:      {getattr(mission, "status", "pending") or "pending"}
Agent:       {mission.agent_id if hasattr(mission, "agent_id") and mission.agent_id else "none"}
Created:     {mission.created_at if hasattr(mission, "created_at") and mission.created_at else "unknown"}
Updated:     {mission.updated_at if hasattr(mission, "updated_at") and mission.updated_at else "unknown"}

Description:
{mission.description or "No description"}

Context:
{getattr(mission, "context", "No context") or "No context"}
"""

        return SFCommandResponse(
            success=True, output=output, data={"mission": mission.id}
        )
    except Exception as e:
        logger.exception("Error showing mission")
        return SFCommandResponse(success=False, output="", error=f"Error: {str(e)}")


async def cmd_agents_list(args: list[str]) -> SFCommandResponse:
    """List agents."""
    from ...agents.store import get_agent_store

    try:
        store = get_agent_store()
        agents = store.list_all()

        # Parse args for filtering
        role_filter = None
        for arg in args:
            if arg.startswith("--role="):
                role_filter = arg.split("=")[1]

        if role_filter:
            agents = [
                a for a in agents if role_filter.lower() in (a.role or "").lower()
            ]

        if not agents:
            return SFCommandResponse(
                success=True, output="No agents found", data={"count": 0}
            )

        # Format as table
        headers = ["ID", "Name", "Role", "Skills", "Tools"]
        rows = []
        for a in agents[:50]:  # Limit to 50
            rows.append(
                [
                    a.id[:20],
                    a.name[:30],
                    a.role[:30] if a.role else "none",
                    str(len(a.skills or [])),
                    str(len(a.tools or [])),
                ]
            )

        output = f"Agents ({len(agents)} total)\n\n"
        output += format_table(headers, rows)

        if len(agents) > 50:
            output += f"\n\n... {len(agents) - 50} more agents"

        return SFCommandResponse(
            success=True, output=output, data={"count": len(agents)}
        )
    except Exception as e:
        logger.exception("Error listing agents")
        return SFCommandResponse(success=False, output="", error=f"Error: {str(e)}")


async def cmd_agents_show(agent_id: str) -> SFCommandResponse:
    """Show agent details."""
    from ...agents.store import get_agent_store

    try:
        store = get_agent_store()
        agent = store.get(agent_id)

        if not agent:
            return SFCommandResponse(
                success=False, output="", error=f"Agent not found: {agent_id}"
            )

        skills_list = "\n  • ".join(agent.skills or ["None"])
        tools_list = "\n  • ".join(agent.tools or ["None"])

        output = f"""Agent Details
=============

ID:          {agent.id}
Name:        {agent.name}
Role:        {agent.role or "none"}
Access:      {agent.access_level or 0}
Icon:        {agent.icon or "user"}
Color:       {agent.color or "gray"}

Skills ({len(agent.skills or [])}):
  • {skills_list}

Tools ({len(agent.tools or [])}):
  • {tools_list}

System Prompt:
{agent.system_prompt[:200] if agent.system_prompt else "No prompt"}...
"""

        return SFCommandResponse(success=True, output=output, data={"agent": agent.id})
    except Exception as e:
        logger.exception("Error showing agent")
        return SFCommandResponse(success=False, output="", error=f"Error: {str(e)}")


async def cmd_skills_sync() -> SFCommandResponse:
    """Sync GitHub skills."""
    from ...skills.library import get_skill_library

    try:
        library = get_skill_library()

        output = "Syncing GitHub skills...\n\n"

        # Get GitHub sources
        sources = library.get_github_sources()

        if not sources:
            return SFCommandResponse(
                success=True,
                output="No GitHub sources configured. Add sources at /skills",
                data={"synced": 0},
            )

        synced = 0
        for source in sources:
            output += f"• {source['repo']}"
            if source.get("path"):
                output += f"/{source['path']}"
            output += f" ... {source.get('files_count', 0)} files\n"
            synced += source.get("files_count", 0)

        output += f"\n✓ Total: {synced} skills synced from {len(sources)} repositories"

        return SFCommandResponse(
            success=True,
            output=output,
            data={"synced": synced, "sources": len(sources)},
        )
    except Exception as e:
        logger.exception("Error syncing skills")
        return SFCommandResponse(success=False, output="", error=f"Error: {str(e)}")


async def cmd_skills_search(query: str) -> SFCommandResponse:
    """Search skills by keyword."""
    from ...skills.library import get_skill_library

    try:
        library = get_skill_library()
        all_skills = library.scan_all()

        # Simple search
        query_lower = query.lower()
        matches = [
            s
            for s in all_skills
            if query_lower in s.name.lower()
            or query_lower in s.description.lower()
            or any(query_lower in tag.lower() for tag in s.tags)
        ]

        if not matches:
            return SFCommandResponse(
                success=True,
                output=f"No skills found matching '{query}'",
                data={"count": 0},
            )

        # Format results
        headers = ["Name", "Source", "Description"]
        rows = []
        for s in matches[:20]:  # Limit to 20
            rows.append([s.name[:30], s.source[:15], s.description[:50]])

        output = f"Skills matching '{query}' ({len(matches)} found)\n\n"
        output += format_table(headers, rows)

        if len(matches) > 20:
            output += f"\n\n... {len(matches) - 20} more matches"

        return SFCommandResponse(
            success=True, output=output, data={"count": len(matches)}
        )
    except Exception as e:
        logger.exception("Error searching skills")
        return SFCommandResponse(success=False, output="", error=f"Error: {str(e)}")


async def cmd_projects_list() -> SFCommandResponse:
    """List projects."""
    from ...projects.manager import get_project_store

    try:
        store = get_project_store()
        projects = store.list_all()

        if not projects:
            return SFCommandResponse(
                success=True, output="No projects found", data={"count": 0}
            )

        headers = ["ID", "Name", "Type", "Status"]
        rows = []
        for p in projects[:30]:
            rows.append([
                p.id[:15],
                p.name[:40],
                getattr(p, "type", "unknown")[:15],
                getattr(p, "status", "unknown")[:15],
            ])

        output = f"Projects ({len(projects)} total)\n\n"
        output += format_table(headers, rows)
        return SFCommandResponse(success=True, output=output, data={"count": len(projects)})
    except Exception as e:
        logger.exception("Error listing projects")
        return SFCommandResponse(success=False, output="", error=f"Error: {str(e)}")


async def cmd_skills_coverage() -> SFCommandResponse:
    """Show skill eval coverage summary.

    WHY: Skills shipped without evals = technical debt. This gives a quick
    snapshot of how many skills have eval_cases and their pass rates.
    Ref: https://www.philschmid.de/testing-skills
    """
    from ...tools.skill_eval_tools import coverage_summary
    try:
        s = coverage_summary()
        out = f"Skills Eval Coverage\n{'='*40}\n"
        out += f"Total skills:      {s['total']}\n"
        out += f"With eval_cases:   {s['with_evals']} ({s['coverage_pct']}%)\n"
        out += f"Run at least once: {s['run']}\n"
        out += f"Passing (≥80%):    {s['passing']}\n"
        if s["needing_work"]:
            out += f"\nNeeding work (pass_rate < 80%):\n"
            for sk in s["needing_work"][:10]:
                rate = f"{int((sk['pass_rate'] or 0)*100)}%" if sk['pass_rate'] is not None else "not run"
                out += f"  • {sk['name']} — {rate}\n"
        if s["without_evals"]:
            out += f"\nWithout eval_cases ({len(s['without_evals'])}):\n"
            for name in s["without_evals"][:15]:
                out += f"  • {name}\n"
        return SFCommandResponse(success=True, output=out, data=s)
    except Exception as exc:
        return SFCommandResponse(success=False, output="", error=str(exc))


async def cmd_skills_eval(args: list[str]) -> SFCommandResponse:
    """Run eval harness for a skill (or all skills).

    Usage:
      sf skills eval <skill-name>           run eval for one skill
      sf skills eval --all                  run all skills with eval_cases
      sf skills eval <name> --trials=5      use 5 trials per case (default: 3)

    WHY: Deterministic checks + LLM-as-judge to measure skill quality.
    Pass rate ≥ 80% = ready to ship. < 80% = iterate on the skill.
    Ref: https://www.philschmid.de/testing-skills
    """
    import asyncio
    from ...tools.skill_eval_tools import run_skill_eval, list_skills_with_evals

    trials = 3
    run_all = "--all" in args
    skill_name = next((a for a in args if not a.startswith("--")), None)

    for a in args:
        if a.startswith("--trials="):
            try:
                trials = int(a.split("=")[1])
            except ValueError:
                pass

    try:
        if run_all:
            skills = [s["name"] for s in list_skills_with_evals() if s["has_evals"]]
            if not skills:
                return SFCommandResponse(success=False, output="", error="No skills with eval_cases found")
            out = f"Running evals for {len(skills)} skills ({trials} trials each)...\n\n"
            passed = 0
            for name in skills:
                result = await run_skill_eval(name, trials=trials)
                status = "[OK]  " if result.pass_rate >= 0.8 else "[WARN]" if result.pass_rate >= 0.6 else "[FAIL]"
                out += f"  {status} {name}: {int(result.pass_rate*100)}% ({result.eval_cases_total} cases, {result.duration_s}s)\n"
                if result.pass_rate >= 0.8:
                    passed += 1
            out += f"\nResult: {passed}/{len(skills)} skills passing (≥80%)"
            return SFCommandResponse(success=True, output=out)

        if not skill_name:
            return SFCommandResponse(
                success=False, output="",
                error="Usage: sf skills eval <skill-name> | --all"
            )

        result = await run_skill_eval(skill_name, trials=trials)

        if result.status == "no_cases":
            return SFCommandResponse(
                success=False, output="",
                error=f"Skill '{skill_name}' has no eval_cases. Add them to the frontmatter."
            )
        if result.status == "error":
            return SFCommandResponse(success=False, output="", error=result.error)

        status_icon = "[OK] " if result.pass_rate >= 0.8 else "[WARN]" if result.pass_rate >= 0.6 else "[FAIL]"
        out = f"{status_icon} {skill_name} v{result.skill_version}\n"
        out += f"Pass rate: {int(result.pass_rate*100)}% ({result.eval_cases_total} cases, {trials} trials, {result.duration_s}s)\n\n"

        for c in result.case_results:
            icon = "[OK] " if c.overall_pass_rate >= 0.8 else "[FAIL]"
            out += f"{icon} [{c.case_id}] overall={int(c.overall_pass_rate*100)}%"
            out += f"  checks={int(c.checks_pass_rate*100)}%"
            if c.llm_judge_score >= 0:
                out += f"  judge={int(c.llm_judge_score*100)}%"
            out += f"  ~{c.avg_tokens}tok {int(c.avg_latency_ms)}ms\n"
            # Show failing checks
            for ch in c.check_details:
                if not ch.passed:
                    out += f"     x {ch.check_spec}: {ch.notes}\n"
            if c.judge_notes and c.llm_judge_score < 0.8:
                out += f"     judge: {c.judge_notes[:100]}\n"

        if result.coverage_gap:
            out += f"\nCoverage gaps: {', '.join(result.coverage_gap)}"

        return SFCommandResponse(success=True, output=out, data={
            "skill_name": skill_name, "pass_rate": result.pass_rate,
        })
    except Exception as exc:
        logger.exception("Error running skill eval")
        return SFCommandResponse(success=False, output="", error=str(exc))

    """List projects."""
    from ...projects.manager import get_project_store

    try:
        store = get_project_store()
        projects = store.list_all()

        if not projects:
            return SFCommandResponse(
                success=True, output="No projects found", data={"count": 0}
            )

        # Format as table
        headers = ["ID", "Name", "Type", "Status"]
        rows = []
        for p in projects[:30]:
            rows.append(
                [
                    p.id[:15],
                    p.name[:40],
                    getattr(p, "type", "unknown")[:15],
                    getattr(p, "status", "unknown")[:15],
                ]
            )

        output = f"Projects ({len(projects)} total)\n\n"
        output += format_table(headers, rows)

        return SFCommandResponse(
            success=True, output=output, data={"count": len(projects)}
        )
    except Exception as e:
        logger.exception("Error listing projects")
        return SFCommandResponse(success=False, output="", error=f"Error: {str(e)}")


async def cmd_db_status() -> SFCommandResponse:
    """Show database status."""
    from ...db.migrations import get_db

    try:
        db = get_db()

        # Query table stats
        tables_query = """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema='public' AND table_name NOT LIKE 'pg_%'
            ORDER BY table_name
        """
        tables = db.execute(tables_query).fetchall()

        output = "Database Status\n===============\n\n"
        output += "Database: platform.db\n"
        output += f"Tables:   {len(tables)}\n\n"

        # Count rows in each table
        headers = ["Table", "Rows"]
        rows = []
        total_rows = 0

        for (table_name,) in tables:
            try:
                count_result = db.execute(
                    f"SELECT COUNT(*) FROM {table_name}"
                ).fetchone()
                count = count_result[0] if count_result else 0
                rows.append([table_name, str(count)])
                total_rows += count
            except Exception:
                rows.append([table_name, "error"])

        output += format_table(headers, rows)
        output += f"\n\nTotal rows: {total_rows}"

        return SFCommandResponse(
            success=True,
            output=output,
            data={"tables": len(tables), "total_rows": total_rows},
        )
    except Exception as e:
        logger.exception("Error getting DB status")
        return SFCommandResponse(success=False, output="", error=f"Error: {str(e)}")


async def cmd_guide(args: list[str]) -> SFCommandResponse:
    """Context-aware guidance on what to do next.
    Inspired by BMAD /bmad-help — reads current state, recommends next steps.
    Usage: guide [context hint, e.g. 'I just finished architecture, what next?']
    """
    from ...epics.store import get_epic_store
    from ...projects.manager import get_project_store

    context_hint = " ".join(args) if args else ""

    try:
        project_store = get_project_store()
        epic_store = get_epic_store()

        projects = project_store.list_all()
        missions = epic_store.list_missions(limit=50)

        running = [m for m in missions if m.status in ["running", "in_progress"]]
        pending = [m for m in missions if m.status == "pending"]
        done = [m for m in missions if m.status in ["completed", "done"]]

        output = "SF Guide — What's next?\n"
        output += "========================\n\n"

        if context_hint:
            output += f"Context: {context_hint}\n\n"

        # Situation
        output += "Current state:\n"
        output += f"  • {len(projects)} project(s)\n"
        output += f"  • {len(running)} mission(s) running  |  {len(pending)} pending  |  {len(done)} done\n"

        if running:
            for m in running[:3]:
                name = getattr(m, "name", getattr(m, "title", "untitled"))
                output += f"    → {name[:40]} [{m.status}]\n"
        output += "\n"

        # Recommendations based on state
        output += "Recommended next steps:\n"
        output += "-----------------------\n"

        if not projects:
            output += "1. Create a project: Projects → New Project\n"
            output += "2. Pick a workflow: Workflows → Browse 46 workflows\n"
            output += "3. Launch first mission\n"
        elif not missions:
            output += "1. Launch first mission via a workflow:\n"
            output += "   → ideation-to-prod   full lifecycle (5 phases)\n"
            output += "   → feature-sprint     implement a feature (TDD)\n"
            output += "   → skill-eval         test skill quality\n"
        elif running:
            output += "1. Monitor missions: sf$ missions list --status=running\n"
            output += "2. Review agent outputs in project chat\n"
            output += "3. Respond to human-in-the-loop checkpoints if blocked\n"
            output += "4. Use complexity=simple for quick tasks, complexity=enterprise for big ones\n"
        else:
            output += "1. Review completed missions for follow-up actions\n"
            output += "2. Launch next workflow phase\n"
            output += "3. Run skill-eval to verify skill quality\n"

        # Context-specific advice
        if context_hint:
            kw = context_hint.lower()
            output += "\n"
            if any(w in kw for w in ["architect", "design", "system", "archi"]):
                output += "For architecture:\n"
                output += "  → Agent: architecte + skills/architecture-review.md\n"
                output += "  → Workflow: feature-sprint (phase solutioning)\n"
            elif any(w in kw for w in ["test", "qa", "quality", "eval"]):
                output += "For QA / testing:\n"
                output += "  → Workflow: test-campaign or skill-eval\n"
                output += "  → Skills: tdd.md, qa-adversarial-llm.md\n"
            elif any(w in kw for w in ["deploy", "prod", "release", "ship"]):
                output += "For deployment:\n"
                output += "  → Workflow: canary-deployment (1%→10%→50%→100% + HITL)\n"
                output += "  → Agents: sre + devops\n"
            elif any(w in kw for w in ["security", "audit", "pentest", "vuln"]):
                output += "For security:\n"
                output += (
                    "  → Workflow: security-hacking (8 phases: recon→exploit→report)\n"
                )
                output += "  → Skills: security-audit.md, qa-adversarial-llm.md\n"
            elif any(w in kw for w in ["skill", "agent", "prompt"]):
                output += "For skill/agent improvement:\n"
                output += (
                    "  → Workflow: skill-eval (write eval_cases → grade → iterate)\n"
                )
                output += "  → Workflow: skill-evolution (audit all agents, extract best practices)\n"
            elif any(w in kw for w in ["simple", "quick", "small", "bug", "fix"]):
                output += "For quick tasks (simple complexity):\n"
                output += "  → Launch workflow with complexity=simple\n"
                output += "  → Heavy planning phases (min_complexity=enterprise) are auto-skipped\n"
            elif any(w in kw for w in ["enterprise", "big", "large", "complex"]):
                output += "For large projects (enterprise complexity):\n"
                output += "  → Launch workflow with complexity=enterprise\n"
                output += "  → All phases including heavyweight planning are included\n"

        output += "\nTip: ask any agent in chat for deeper context-aware guidance.\n"
        output += (
            "     'sf$ missions list', 'sf$ agents list', 'sf$ skills search <topic>'\n"
        )

        return SFCommandResponse(
            success=True,
            output=output,
            data={
                "running": len(running),
                "pending": len(pending),
                "projects": len(projects),
            },
        )
    except Exception as e:
        logger.exception("Error in guide command")
        return SFCommandResponse(success=False, output="", error=str(e))


async def cmd_help() -> SFCommandResponse:
    """Show SF CLI help."""
    output = """Software Factory CLI Help
=========================

PLATFORM:
  platform status                    Show platform status (agents, missions, projects, skills)
  
MISSIONS:
  missions list                      List all missions
  missions list --status=running     Filter missions by status
  missions list --limit=50           Limit number of results
  missions show <id>                 Show mission details
  
AGENTS:
  agents list                        List all agents
  agents list --role=backend         Filter agents by role
  agents show <id>                   Show agent details
  
SKILLS:
  skills sync                        Sync GitHub skills
  skills search <query>              Search skills by keyword
  
PROJECTS:
  projects list                      List all projects
  
DATABASE:
  db status                          Show database tables and row counts
  
SYSTEM:
  help                               Show this help message
  guide                              What's next? Context-aware guidance (inspired by BMAD /bmad-help)
  guide <context>                    Guidance with context (e.g. guide I just finished architecture)
  clear                              Clear terminal

Examples:
  sf$ platform status
  sf$ missions list --status=running
  sf$ agents show product-manager
  sf$ skills search "react"
  sf$ db status
  
Tips:
  • Use ↑/↓ arrows for command history
  • Use Tab for autocomplete
  • Commands are case-sensitive
"""

    return SFCommandResponse(success=True, output=output)


# Command dispatcher
SF_COMMANDS = {
    "platform": {
        "status": cmd_platform_status,
    },
    "epics": {
        "list": cmd_missions_list,
        "show": cmd_missions_show,
    },
    "agents": {
        "list": cmd_agents_list,
        "show": cmd_agents_show,
    },
    "skills": {
        "sync": cmd_skills_sync,
        "search": cmd_skills_search,
        "eval": cmd_skills_eval,
        "coverage": cmd_skills_coverage,
    },
    "projects": {
        "list": cmd_projects_list,
    },
    "db": {
        "status": cmd_db_status,
    },
    "guide": cmd_guide,
    "help": cmd_help,
}


@router.post("/api/sf/execute")
async def execute_sf_command(request: SFCommandRequest) -> SFCommandResponse:
    """Execute SF native command."""
    try:
        cmd_parts = request.command.split()
        if not cmd_parts:
            return SFCommandResponse(success=False, output="", error="Empty command")

        # Parse command
        cmd_group = cmd_parts[0]  # e.g., "platform", "epics"
        cmd_action = cmd_parts[1] if len(cmd_parts) > 1 else None
        cmd_args = cmd_parts[2:] if len(cmd_parts) > 2 else []
        cmd_args.extend(request.args)  # Add args from API

        # Special case: help
        if cmd_group == "help":
            return await cmd_help()

        # Find command handler
        if cmd_group not in SF_COMMANDS:
            return SFCommandResponse(
                success=False,
                output="",
                error=f"Unknown command group: {cmd_group}. Type 'help' for available commands.",
            )

        cmd_handlers = SF_COMMANDS[cmd_group]

        # If no action specified and only one handler, use it
        if cmd_action is None:
            if isinstance(cmd_handlers, dict) and len(cmd_handlers) == 1:
                handler = list(cmd_handlers.values())[0]
                return await handler()
            if callable(cmd_handlers):
                return await cmd_handlers()
            return SFCommandResponse(
                success=False,
                output="",
                error=f"Action required for {cmd_group}. Try: {', '.join(cmd_handlers.keys())}",
            )

        if cmd_action not in cmd_handlers:
            available = ", ".join(cmd_handlers.keys())
            return SFCommandResponse(
                success=False,
                output="",
                error=f"Unknown action: {cmd_group} {cmd_action}. Available: {available}",
            )

        handler = cmd_handlers[cmd_action]

        # Call handler with appropriate args
        import inspect

        sig = inspect.signature(handler)
        params = sig.parameters

        if len(params) == 0:
            # No args
            return await handler()
        if len(params) == 1:
            param_name = list(params.keys())[0]
            if "args" in param_name.lower():
                # Takes args list
                return await handler(cmd_args)
            # Takes single arg (e.g., mission_id)
            if not cmd_args:
                return SFCommandResponse(
                    success=False,
                    output="",
                    error=f"Missing required argument for {cmd_group} {cmd_action}",
                )
            return await handler(cmd_args[0])
        return await handler(*cmd_args)

    except Exception as e:
        logger.exception("Error executing SF command")
        return SFCommandResponse(success=False, output="", error=f"Error: {str(e)}")


@router.get("/api/sf/commands")
async def list_sf_commands() -> dict[str, Any]:
    """List available SF commands."""
    commands = {}
    for group, handlers in SF_COMMANDS.items():
        if callable(handlers):
            commands[group] = {"actions": ["default"], "description": "Single command"}
        else:
            commands[group] = {
                "actions": list(handlers.keys()),
                "description": f"{group.capitalize()} commands",
            }

    return {"success": True, "commands": commands, "count": len(commands)}
