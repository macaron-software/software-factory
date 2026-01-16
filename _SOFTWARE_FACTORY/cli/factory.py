#!/usr/bin/env python3
"""
Software Factory CLI
====================
Unified command-line interface for the multi-project Software Factory.

Commands:
    factory brain run          # Run Brain analysis
    factory wiggum             # Start TDD workers
    factory status             # Show project status
    factory projects           # List projects

Usage:
    factory ppz brain run                    # Brain for PPZ project
    factory ppz wiggum -w 50                 # 50 TDD workers
    factory solaris brain run -q "tabs"      # Focus analysis
    factory status --all                     # All projects status
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import click
    CLICK_AVAILABLE = True
except ImportError:
    CLICK_AVAILABLE = False
    print("Warning: click not installed. Run: pip install click", file=sys.stderr)


# ============================================================================
# CLI HELPERS
# ============================================================================

def get_factory_root() -> Path:
    """Get the Software Factory root directory"""
    return Path(__file__).parent.parent


def format_table(headers: list, rows: list) -> str:
    """Format data as ASCII table"""
    if not rows:
        return "No data"

    # Calculate column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))

    # Build table
    lines = []

    # Header
    header_line = " │ ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
    lines.append("┌─" + "─┬─".join("─" * w for w in widths) + "─┐")
    lines.append("│ " + header_line + " │")
    lines.append("├─" + "─┼─".join("─" * w for w in widths) + "─┤")

    # Rows
    for row in rows:
        row_line = " │ ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row))
        lines.append("│ " + row_line + " │")

    lines.append("└─" + "─┴─".join("─" * w for w in widths) + "─┘")

    return "\n".join(lines)


# ============================================================================
# CLI COMMANDS (with click)
# ============================================================================

if CLICK_AVAILABLE:

    @click.group()
    @click.option("--project", "-p", envvar="FACTORY_PROJECT", help="Project name")
    @click.pass_context
    def cli(ctx, project):
        """Software Factory - Multi-project RLM System"""
        ctx.ensure_object(dict)
        ctx.obj["project"] = project

    # --- BRAIN ---
    @cli.group()
    @click.pass_context
    def brain(ctx):
        """Brain commands - project analysis and task generation"""
        pass

    @brain.command("run")
    @click.option("--question", "-q", help="Focus question for analysis")
    @click.option("--domain", "-d", help="Specific domain to analyze")
    @click.option("--legacy", is_flag=True, help="Use legacy Brain (regex-based)")
    @click.pass_context
    def brain_run(ctx, question, domain, legacy):
        """Run Brain analysis using MCP LRM tools (MIT CSAIL RLM adaptation)"""
        project = ctx.obj.get("project")
        domains = [domain] if domain else None

        if legacy:
            # Legacy mode (regex-based, not using MCP)
            from core.brain import RLMBrain
            brain = RLMBrain(project)
            tasks = asyncio.run(brain.run(question=question, domains=domains))
        else:
            # MCP mode (Claude + MCP LRM tools)
            from core.brain_mcp import MCPBrain
            brain = MCPBrain(project)
            tasks = asyncio.run(brain.run(focus=question, domains=domains))

        click.echo(f"\n✅ Created {len(tasks)} tasks")
        for task in tasks[:5]:
            click.echo(f"  - [{task.domain}] {task.description[:60]}...")

    @brain.command("status")
    @click.pass_context
    def brain_status(ctx):
        """Show Brain status"""
        from core.brain import RLMBrain

        project = ctx.obj.get("project")
        brain = RLMBrain(project)
        status = brain.get_status()
        click.echo(json.dumps(status, indent=2))

    # --- WIGGUM TDD ---
    @cli.group()
    @click.pass_context
    def wiggum(ctx):
        """Wiggum TDD daemon - parallel workers for code generation"""
        pass

    @wiggum.command("start")
    @click.option("--workers", "-w", default=50, help="Number of workers")
    @click.option("--foreground", "-f", is_flag=True, help="Run in foreground")
    @click.pass_context
    def wiggum_start(ctx, workers, foreground):
        """Start Wiggum TDD daemon"""
        from core.wiggum_tdd import WiggumTDDDaemon

        project = ctx.obj.get("project")
        if not project:
            click.echo("Error: --project/-p required")
            return

        daemon = WiggumTDDDaemon(project, workers=workers)
        daemon.start(foreground=foreground)

    @wiggum.command("stop")
    @click.pass_context
    def wiggum_stop(ctx):
        """Stop Wiggum TDD daemon"""
        from core.wiggum_tdd import WiggumTDDDaemon

        project = ctx.obj.get("project")
        if not project:
            click.echo("Error: --project/-p required")
            return

        daemon = WiggumTDDDaemon(project)
        daemon.stop()

    @wiggum.command("restart")
    @click.option("--workers", "-w", default=50, help="Number of workers")
    @click.pass_context
    def wiggum_restart(ctx, workers):
        """Restart Wiggum TDD daemon"""
        from core.wiggum_tdd import WiggumTDDDaemon

        project = ctx.obj.get("project")
        if not project:
            click.echo("Error: --project/-p required")
            return

        daemon = WiggumTDDDaemon(project, workers=workers)
        daemon.restart()

    @wiggum.command("status")
    @click.option("--all", "-a", "show_all", is_flag=True, help="Show all projects")
    @click.pass_context
    def wiggum_status(ctx, show_all):
        """Show Wiggum TDD daemon status"""
        from core.wiggum_tdd import WiggumTDDDaemon, WiggumPool
        from core.daemon import DaemonManager, print_daemon_status, print_all_status

        project = ctx.obj.get("project")

        if show_all or not project:
            manager = DaemonManager(project or "default")
            print_all_status(manager.status_all())
        else:
            daemon = WiggumTDDDaemon(project)
            status = daemon.status()
            print_daemon_status(status)

            # Show task stats
            pool = WiggumPool(project)
            pool_status = pool.get_status()
            click.echo(f"\n   Tasks: {pool_status['total_tasks']} total")
            for s, count in pool_status.get("by_status", {}).items():
                click.echo(f"     - {s}: {count}")

    @wiggum.command("once")
    @click.option("--workers", "-w", default=50, help="Number of workers")
    @click.option("--task", "-t", help="Specific task ID")
    @click.pass_context
    def wiggum_once(ctx, workers, task):
        """Process single task and exit"""
        from core.wiggum_tdd import WiggumPool

        project = ctx.obj.get("project")
        if not project:
            click.echo("Error: --project/-p required")
            return

        pool = WiggumPool(project, workers=workers)
        result = asyncio.run(pool.run_once(task))
        if result:
            icon = "✅" if result.success else "❌"
            click.echo(f"\n{icon} Task: {result.task_id}")
            click.echo(f"   Iterations: {result.iterations}")
            if result.error:
                click.echo(f"   Error: {result.error}")

    # --- WIGGUM DEPLOY ---
    @cli.group()
    @click.pass_context
    def deploy(ctx):
        """Deploy daemon - E2E validation and deployment"""
        pass

    @deploy.command("start")
    @click.option("--foreground", "-f", is_flag=True, help="Run in foreground")
    @click.pass_context
    def deploy_start(ctx, foreground):
        """Start Deploy daemon"""
        from core.wiggum_deploy import WiggumDeployDaemon

        project = ctx.obj.get("project")
        if not project:
            click.echo("Error: --project/-p required")
            return

        daemon = WiggumDeployDaemon(project)
        daemon.start(foreground=foreground)

    @deploy.command("stop")
    @click.pass_context
    def deploy_stop(ctx):
        """Stop Deploy daemon"""
        from core.wiggum_deploy import WiggumDeployDaemon

        project = ctx.obj.get("project")
        if not project:
            click.echo("Error: --project/-p required")
            return

        daemon = WiggumDeployDaemon(project)
        daemon.stop()

    @deploy.command("restart")
    @click.pass_context
    def deploy_restart(ctx):
        """Restart Deploy daemon"""
        from core.wiggum_deploy import WiggumDeployDaemon

        project = ctx.obj.get("project")
        if not project:
            click.echo("Error: --project/-p required")
            return

        daemon = WiggumDeployDaemon(project)
        daemon.restart()

    @deploy.command("status")
    @click.option("--all", "-a", "show_all", is_flag=True, help="Show all projects")
    @click.pass_context
    def deploy_status(ctx, show_all):
        """Show Deploy daemon status"""
        from core.wiggum_deploy import WiggumDeployDaemon, DeployPool
        from core.daemon import DaemonManager, print_daemon_status, print_all_status

        project = ctx.obj.get("project")

        if show_all or not project:
            manager = DaemonManager(project or "default")
            print_all_status(manager.status_all())
        else:
            daemon = WiggumDeployDaemon(project)
            status = daemon.status()
            print_daemon_status(status)

            # Show deployable tasks
            pool = DeployPool(project)
            deployable = pool.task_store.get_deployable_tasks(pool.project.id, limit=100)
            click.echo(f"\n   Deployable tasks: {len(deployable)}")

    @deploy.command("once")
    @click.option("--task", "-t", help="Specific task ID")
    @click.pass_context
    def deploy_once(ctx, task):
        """Process single deploy and exit"""
        from core.wiggum_deploy import DeployPool

        project = ctx.obj.get("project")
        if not project:
            click.echo("Error: --project/-p required")
            return

        pool = DeployPool(project)
        result = asyncio.run(pool.run_once(task))
        if result:
            icon = "✅" if result.success else "❌"
            click.echo(f"\n{icon} Deploy: {result.task_id}")
            click.echo(f"   Stages passed: {result.stages_passed}")
            click.echo(f"   Stages failed: {result.stages_failed}")
            if result.feedback_tasks:
                click.echo(f"   Feedback tasks: {len(result.feedback_tasks)}")

    # --- EXPERIENCE LEARNING AGENT ---
    @cli.group()
    @click.pass_context
    def xp(ctx):
        """Experience Learning Agent - Factory self-improvement"""
        pass

    @xp.command("analyze")
    @click.option("--days", "-d", default=7, help="Days of history to analyze")
    @click.option("--no-llm", is_flag=True, help="Skip LLM deep analysis")
    @click.option("--apply", "-a", is_flag=True, help="Apply auto-fixable improvements")
    @click.pass_context
    def xp_analyze(ctx, days, no_llm, apply):
        """Analyze factory experience and generate insights"""
        from core.experience_agent import ExperienceAgent

        agent = ExperienceAgent()
        insights = asyncio.run(agent.analyze(use_llm=not no_llm))

        if apply:
            fixed = asyncio.run(agent.apply_auto_fixes())
            click.echo(f"\n🔧 Applied {fixed} auto-fixes")

        click.echo(f"\n📊 Found {len(insights)} insights:")
        for i in insights[:15]:
            icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}[i.severity]
            auto = "🔧" if i.auto_fixable else ""
            click.echo(f"  {icon} [{i.type.value}] {i.title} {auto}")

        if agent.improvements:
            click.echo(f"\n💡 {len(agent.improvements)} suggested improvements")

    @xp.command("report")
    @click.option("--days", "-d", default=7, help="Days of history to analyze")
    @click.option("--output", "-o", help="Output file path")
    @click.pass_context
    def xp_report(ctx, days, output):
        """Generate detailed experience report"""
        from core.experience_agent import ExperienceAgent

        agent = ExperienceAgent()
        asyncio.run(agent.analyze(use_llm=True))
        report = agent.generate_report()

        if output:
            Path(output).write_text(report)
            click.echo(f"Report saved to: {output}")
        else:
            click.echo(report)

    @xp.command("fix")
    @click.pass_context
    def xp_fix(ctx):
        """Apply auto-fixable improvements (reset stuck tasks, etc.)"""
        from core.experience_agent import ExperienceAgent

        agent = ExperienceAgent()
        asyncio.run(agent.analyze(use_llm=False))
        fixed = asyncio.run(agent.apply_auto_fixes())
        click.echo(f"✅ Applied {fixed} auto-fixes")

    @xp.command("impact")
    @click.option("--days", "-d", default=7, help="Days of history to analyze")
    @click.pass_context
    def xp_impact(ctx, days):
        """Measure ROI and impact of factory learning"""
        from core.experience_agent import ExperienceAgent

        agent = ExperienceAgent()
        impact = agent.measure_impact(days=days)

        click.echo(f"\n📈 Factory Impact Report (last {days} days)")
        click.echo("=" * 50)

        perf = impact.get("recent_performance", {})
        click.echo(f"\n🎯 Task Performance:")
        click.echo(f"   Completed: {perf.get('completed', 0)}")
        click.echo(f"   Failed: {perf.get('failed', 0)}")
        click.echo(f"   Success rate: {perf.get('success_rate', 0):.1f}%")

        learn = impact.get("learning_progress", {})
        click.echo(f"\n🧠 Learning Progress:")
        click.echo(f"   Insights applied: {learn.get('applied', 0)}")
        click.echo(f"   Insights pending: {learn.get('pending', 0)}")

        patterns = impact.get("pattern_effectiveness", [])
        if patterns:
            click.echo(f"\n🛡️ Top Adversarial Patterns:")
            for p in patterns[:5]:
                click.echo(f"   - {p.get('rule', 'unknown')}: {p.get('hit_count', 0)} hits")

    @xp.command("learn")
    @click.pass_context
    def xp_learn(ctx):
        """Run full learning cycle: analyze → persist → apply patterns"""
        from core.experience_agent import ExperienceAgent

        agent = ExperienceAgent()
        click.echo("🔍 Analyzing experience...")
        asyncio.run(agent.analyze(use_llm=True))

        click.echo("💾 Persisting insights...")
        insights_saved = agent.persist_insights()
        patterns_saved = agent.persist_patterns()

        click.echo("🔧 Applying auto-fixes...")
        fixed = asyncio.run(agent.apply_auto_fixes())

        click.echo(f"\n✅ Learning cycle complete:")
        click.echo(f"   - {len(agent.insights)} insights found")
        click.echo(f"   - {insights_saved} new insights saved")
        click.echo(f"   - {patterns_saved} new patterns learned")
        click.echo(f"   - {fixed} auto-fixes applied")

    # --- STATUS ---
    @cli.command()
    @click.option("--all", "-a", "show_all", is_flag=True, help="Show all projects")
    @click.pass_context
    def status(ctx, show_all):
        """Show project status"""
        from core.project_registry import list_projects, get_project
        from core.task_store import TaskStore

        store = TaskStore()

        if show_all:
            projects = list_projects()
        else:
            project_name = ctx.obj.get("project")
            if project_name:
                projects = [project_name]
            else:
                projects = list_projects()

        headers = ["Project", "Pending", "TDD", "Deploy", "Done", "Failed"]
        rows = []

        for name in projects:
            try:
                project = get_project(name)
                tasks = store.get_tasks_by_project(project.id)

                # Count by status
                counts = {"pending": 0, "tdd": 0, "deploy": 0, "done": 0, "failed": 0}
                for task in tasks:
                    s = task.status.lower()
                    if s == "pending" or s == "locked":
                        counts["pending"] += 1
                    elif "tdd" in s or s == "adversarial_rejected":
                        counts["tdd"] += 1
                    elif s in ("merged", "queued_for_deploy") or "staging" in s or "prod" in s or "e2e" in s or "chaos" in s or "load" in s:
                        counts["deploy"] += 1
                    elif s in ("completed", "deployed"):
                        counts["done"] += 1
                    elif "failed" in s or s == "blocked":
                        counts["failed"] += 1

                rows.append([
                    name,
                    counts["pending"],
                    counts["tdd"],
                    counts["deploy"],
                    counts["done"],
                    counts["failed"],
                ])
            except Exception as e:
                rows.append([name, "ERROR", "-", "-", "-", str(e)[:20]])

        click.echo("\n" + format_table(headers, rows))

    # --- PROJECTS ---
    @cli.command()
    @click.option("--json", "as_json", is_flag=True, help="Output as JSON")
    def projects(as_json):
        """List available projects"""
        from core.project_registry import list_projects, get_project

        project_names = list_projects()

        if as_json:
            click.echo(json.dumps(project_names))
            return

        click.echo("\nAvailable projects:")
        for name in project_names:
            try:
                p = get_project(name)
                click.echo(f"  {name}: {p.root_path}")
                click.echo(f"    Domains: {', '.join(p.domains.keys())}")
                click.echo(f"    Deploy: {p.deploy.get('strategy', 'unknown')}")
            except Exception as e:
                click.echo(f"  {name}: ERROR - {e}")

    # --- INIT ---
    @cli.command()
    @click.option("--llm-config", is_flag=True, help="Create LLM config template")
    def init(llm_config):
        """Initialize configuration"""
        if llm_config:
            from core.llm_client import create_config_template
            create_config_template()
            click.echo("LLM config template created at ~/.config/factory/llm.yaml")
            click.echo("Edit the file and set your API keys as environment variables.")

    # Allow project name as first argument
    @cli.command(hidden=True)
    @click.argument("project_name")
    @click.argument("args", nargs=-1, type=click.UNPROCESSED)
    @click.pass_context
    def project_shortcut(ctx, project_name, args):
        """Shortcut: factory <project> <command>"""
        ctx.obj["project"] = project_name
        # Re-invoke with remaining args
        if args:
            ctx.invoke(cli, args=args)


# ============================================================================
# FALLBACK CLI (without click)
# ============================================================================

def main_fallback():
    """Fallback CLI without click"""
    import argparse

    parser = argparse.ArgumentParser(description="Software Factory CLI")
    parser.add_argument("--project", "-p", help="Project name")

    subparsers = parser.add_subparsers(dest="command")

    # Brain
    brain_parser = subparsers.add_parser("brain", help="Brain commands")
    brain_parser.add_argument("action", choices=["run", "status"])
    brain_parser.add_argument("--question", "-q", help="Focus question")
    brain_parser.add_argument("--quick", action="store_true")

    # Wiggum
    wiggum_parser = subparsers.add_parser("wiggum", help="TDD workers")
    wiggum_parser.add_argument("--workers", "-w", type=int, default=50)
    wiggum_parser.add_argument("--once", action="store_true")

    # Status
    status_parser = subparsers.add_parser("status", help="Show status")
    status_parser.add_argument("--all", "-a", action="store_true")

    # Projects
    subparsers.add_parser("projects", help="List projects")

    args = parser.parse_args()

    if args.command == "brain":
        from core.brain import RLMBrain
        brain = RLMBrain(args.project)
        if args.action == "run":
            tasks = asyncio.run(brain.run(question=args.question, quick=args.quick))
            print(f"Created {len(tasks)} tasks")
        else:
            print(json.dumps(brain.get_status(), indent=2))

    elif args.command == "wiggum":
        from core.wiggum_tdd import WiggumPool
        pool = WiggumPool(args.project, workers=args.workers)
        if args.once:
            asyncio.run(pool.run_once())
        else:
            asyncio.run(pool.run())

    elif args.command == "status":
        from core.project_registry import list_projects, get_project
        from core.task_store import TaskStore
        store = TaskStore()
        for name in list_projects():
            try:
                p = get_project(name)
                tasks = store.get_tasks_by_project(p.id)
                print(f"{name}: {len(tasks)} tasks")
            except Exception as e:
                print(f"{name}: ERROR - {e}")

    elif args.command == "projects":
        from core.project_registry import list_projects
        for name in list_projects():
            print(name)

    else:
        parser.print_help()


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main entry point"""
    if CLICK_AVAILABLE:
        # Handle shortcut: factory <project> <command>
        if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
            # Check if first arg is a project name
            try:
                from core.project_registry import list_projects
                projects = list_projects()
                if sys.argv[1] in projects:
                    # Insert --project before the command
                    sys.argv.insert(1, "--project")
            except Exception:
                pass

        cli()
    else:
        main_fallback()


if __name__ == "__main__":
    main()
