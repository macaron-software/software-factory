#!/usr/bin/env python3
"""Macaron CLI — Command-line interface for the Software Factory.

Usage:
    macaron status                    Show platform health and stats
    macaron agents [--level LEVEL]    List agents
    macaron missions [--status S]     List missions
    macaron projects                  List projects
    macaron mission create NAME       Create a new mission
    macaron logs [--tail N]           Show recent platform logs
"""
import argparse
import json
import sys

try:
    import httpx
except ImportError:
    print("Error: httpx required. Install with: pip install httpx")
    sys.exit(1)


DEFAULT_URL = "http://localhost:8090"


def get_client(base_url: str) -> httpx.Client:
    return httpx.Client(base_url=base_url, timeout=10)


def cmd_status(args):
    """Show platform health and stats."""
    c = get_client(args.url)
    try:
        r = c.get("/api/health")
        health = r.json()
        print(f"Platform: {health.get('status', 'unknown')}")
        print(f"Version:  {health.get('version', '?')}")
        print(f"Uptime:   {health.get('uptime', '?')}")

        r2 = c.get("/api/monitoring/live")
        if r2.status_code == 200:
            m = r2.json()
            print(f"Agents:   {m.get('agents_total', '?')}")
            print(f"Missions: {m.get('missions_total', '?')}")
            print(f"CPU:      {m.get('cpu_percent', '?')}%")
            print(f"Memory:   {m.get('rss_mb', '?')} MB")
    except httpx.ConnectError:
        print(f"Error: Cannot connect to {args.url}")
        sys.exit(1)


def cmd_agents(args):
    """List agents."""
    c = get_client(args.url)
    r = c.get("/api/agents")
    if r.status_code != 200:
        print(f"Error: {r.status_code}")
        sys.exit(1)
    agents = r.json()
    if args.level:
        agents = [a for a in agents if a.get("level") == args.level]

    print(f"{'Name':<30} {'Role':<20} {'Level':<12} {'Status':<10}")
    print("-" * 72)
    for a in agents:
        print(f"{a.get('name', ''):<30} {a.get('role', ''):<20} {a.get('level', ''):<12} {a.get('status', 'idle'):<10}")
    print(f"\nTotal: {len(agents)} agents")


def cmd_missions(args):
    """List missions."""
    c = get_client(args.url)
    r = c.get("/api/missions/list-partial")
    if r.status_code != 200:
        print(f"Error: {r.status_code}")
        sys.exit(1)
    missions = r.json()
    if isinstance(missions, dict):
        missions = missions.get("missions", [])
    if args.status:
        missions = [m for m in missions if m.get("status") == args.status]

    print(f"{'Name':<40} {'Type':<12} {'Status':<15} {'Project':<20}")
    print("-" * 87)
    for m in missions:
        print(f"{m.get('name', '')[:39]:<40} {m.get('type', ''):<12} {m.get('status', ''):<15} {m.get('project_id', '')[:19]:<20}")
    print(f"\nTotal: {len(missions)} missions")


def cmd_projects(args):
    """List projects."""
    c = get_client(args.url)
    r = c.get("/api/projects")
    if r.status_code != 200:
        print(f"Error: {r.status_code}")
        sys.exit(1)
    projects = r.json()
    if isinstance(projects, dict):
        projects = projects.get("projects", [])

    print(f"{'Name':<30} {'Status':<12} {'Description':<40}")
    print("-" * 82)
    for p in projects:
        print(f"{p.get('name', '')[:29]:<30} {p.get('status', ''):<12} {p.get('description', '')[:39]:<40}")
    print(f"\nTotal: {len(projects)} projects")


def cmd_mission_create(args):
    """Create a new mission."""
    c = get_client(args.url)
    payload = {
        "name": args.name,
        "type": args.type,
        "project_id": args.project or "",
    }
    r = c.post("/api/missions/create", json=payload)
    if r.status_code in (200, 201):
        data = r.json()
        print(f"Mission created: {data.get('id', '?')}")
        print(f"Name: {data.get('name', args.name)}")
    else:
        print(f"Error: {r.status_code} — {r.text[:200]}")
        sys.exit(1)


def cmd_logs(args):
    """Show recent platform logs (via monitoring endpoint)."""
    c = get_client(args.url)
    r = c.get("/api/monitoring/live")
    if r.status_code == 200:
        data = r.json()
        print(json.dumps(data, indent=2))
    else:
        print(f"Error: {r.status_code}")


def main():
    parser = argparse.ArgumentParser(
        prog="macaron",
        description="Software Factory CLI",
    )
    parser.add_argument("--url", default=DEFAULT_URL, help=f"Platform URL (default: {DEFAULT_URL})")
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # status
    sub.add_parser("status", help="Show platform health and stats")

    # agents
    p_agents = sub.add_parser("agents", help="List agents")
    p_agents.add_argument("--level", help="Filter by SAFe level (portfolio, program, team, etc.)")

    # missions
    p_missions = sub.add_parser("missions", help="List missions")
    p_missions.add_argument("--status", help="Filter by status (planning, active, completed, etc.)")

    # projects
    sub.add_parser("projects", help="List projects")

    # mission create
    p_create = sub.add_parser("create", help="Create a new mission")
    p_create.add_argument("name", help="Mission name")
    p_create.add_argument("--type", default="feature", help="Mission type (epic, feature, bug, etc.)")
    p_create.add_argument("--project", help="Project ID to attach to")

    # logs
    sub.add_parser("logs", help="Show platform monitoring data")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    commands = {
        "status": cmd_status,
        "agents": cmd_agents,
        "missions": cmd_missions,
        "projects": cmd_projects,
        "create": cmd_mission_create,
        "logs": cmd_logs,
    }
    fn = commands.get(args.command)
    if fn:
        fn(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
