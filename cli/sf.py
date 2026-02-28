#!/usr/bin/env python3
"""sf — Software Factory CLI.

Full-featured CLI mirroring all web dashboard functionality.
Dual mode: API (server) or DB (offline/direct sqlite3).

Usage:
    sf status
    sf ideation "site web de suivi de vélo iot gps"
    sf missions list --project myproj
    sf projects chat myproj "ajoute un module auth"
    sf agents list
    sf llm stats
"""

import argparse
import os
import sys

# Ensure cli package is importable
_cli_dir = os.path.dirname(os.path.abspath(__file__))
_sf_dir = os.path.dirname(_cli_dir)
if _sf_dir not in sys.path:
    sys.path.insert(0, _sf_dir)

from cli import _output as out  # noqa: E402

DEFAULT_URL = os.environ.get("MACARON_URL", "http://localhost:8090")


# ── Backend selection ──


def get_backend(args):
    """Auto-detect or force API vs DB backend."""
    if getattr(args, "db", False):
        from cli._db import DBBackend

        db_path = getattr(args, "db_path", None)
        return DBBackend(db_path)

    if getattr(args, "api", False):
        from cli._api import APIBackend

        return APIBackend(args.url, getattr(args, "token", None))

    # Auto-detect: try API first
    try:
        import httpx

        for ep in ("/api/health", "/api/agents"):
            try:
                r = httpx.get(f"{args.url}{ep}", timeout=3)
                if r.status_code in (200, 401):
                    from cli._api import APIBackend

                    return APIBackend(args.url, getattr(args, "token", None))
            except Exception:
                continue
    except Exception:
        pass

    # Fallback to DB
    try:
        from cli._db import DBBackend

        db_path = getattr(args, "db_path", None) or os.environ.get("SF_DB_PATH")
        return DBBackend(db_path)
    except FileNotFoundError:
        out.error(f"No server at {args.url} and no local DB found")
        out.error("Use --url URL or --db-path PATH")
        sys.exit(1)


def output(args, data):
    """Print data as JSON or formatted."""
    if getattr(args, "json_output", False):
        out.out_json(data)
    elif isinstance(data, list):
        if data and isinstance(data[0], dict):
            print(out.table(data))
        else:
            for item in data:
                print(item)
    elif isinstance(data, dict):
        if "error" in data:
            out.error(data["error"])
            sys.exit(1)
        print(out.kv(data))
    else:
        print(data)


# ── Command handlers ──


def cmd_status(args):
    b = get_backend(args)
    health = b.health()
    mon = b.monitoring()
    if getattr(args, "json_output", False):
        health.update(mon)
        out.out_json(health)
        return
    status_val = health.get("status", "?")
    color_fn = out.green if status_val == "ok" else out.red
    print(f"Platform: {color_fn(status_val)}  {b.base_url}")
    db = mon.get("database", {})
    rtk = mon.get("rtk", {})
    db_size = db.get("size_mb", 0)
    print(
        f"DB: {db_size:.1f}MB  tables={db.get('tables', '?')}  schema_version={db.get('schema_version', '?')}"
    )
    if rtk.get("calls", 0) > 0:
        saved_kb = rtk.get("bytes_saved", 0) / 1024
        print(
            f"RTK: {rtk['calls']} calls  {saved_kb:.1f}KB saved  ~{rtk.get('tokens_saved_est', 0)} tokens  {rtk.get('ratio_pct', 0):.1f}% compression"
        )
    agents_count = health.get("agents", {})
    if isinstance(agents_count, dict):
        print(
            f"Agents: {agents_count.get('total', 0)} total  {agents_count.get('active', 0)} active"
        )
    missions_count = health.get("missions", {})
    if isinstance(missions_count, dict):
        print(
            f"Missions: {missions_count.get('running', 0)} running  {missions_count.get('total', 0)} total"
        )


# ── Projects ──


def cmd_projects_list(args):
    b = get_backend(args)
    projs = b.projects_list()
    cols = ["id", "name", "status", "factory_type", "path"]
    rows = [{c: p.get(c, "") for c in cols} for p in projs]
    if getattr(args, "json_output", False):
        out.out_json(projs)
    else:
        print(out.table(rows, cols))


def cmd_projects_create(args):
    b = get_backend(args)
    result = b.project_create(
        args.name,
        getattr(args, "desc", ""),
        getattr(args, "path", ""),
        getattr(args, "type", "web"),
    )
    output(args, result)


def cmd_projects_show(args):
    b = get_backend(args)
    output(args, b.project_show(args.id))


def cmd_projects_vision(args):
    b = get_backend(args)
    text = getattr(args, "set", None)
    output(args, b.project_vision(args.id, text))


def cmd_projects_chat(args):
    b = get_backend(args)
    url = b.project_chat_url(args.id)
    if not url:
        out.error("Chat requires API mode (server must be running)")
        sys.exit(1)
    msg = " ".join(args.message)
    from cli._stream import print_stream

    print_stream(url, "POST", {"message": msg})


def cmd_projects_phase(args):
    """Get or set the current phase of a project."""
    b = get_backend(args)
    phase = getattr(args, "phase", None)
    if phase:
        output(args, b.project_phase_set(args.id, phase))
    else:
        output(args, b.project_phase_get(args.id))


def cmd_projects_health(args):
    """Get project health: mission success rates."""
    b = get_backend(args)
    data = b.project_health(args.id)
    if getattr(args, "json_output", False):
        out.out_json(data)
        return
    score = data.get("health", data.get("health_score", 0))
    total = data.get("stats", {}).get("total", data.get("total", 0))
    color_fn = out.green if score >= 70 else (out.yellow if score >= 40 else out.red)
    print(f"Project {args.id}: health {color_fn(str(score) + '%')}  ({total} missions)")
    counts = data.get("stats", data.get("mission_counts", {}))
    if isinstance(counts, dict):
        for status, cnt in sorted(counts.items()):
            print(f"  {status:15s} {cnt}")


def cmd_projects_missions_suggest(args):
    """Suggest next missions for a project based on current phase."""
    b = get_backend(args)
    data = b.project_missions_suggest(args.id)
    if getattr(args, "json_output", False):
        out.out_json(data)
        return
    phase = data.get("current_phase", "?")
    suggestions = data.get("suggestions", [])
    print(f"Project {args.id} (phase: {phase}) — suggested missions:")
    for i, s in enumerate(suggestions, 1):
        print(f"  {i}. {s}")


# ── Missions ──


def cmd_missions_list(args):
    b = get_backend(args)
    missions = b.missions_list(
        getattr(args, "project", None), getattr(args, "status", None)
    )
    cols = ["id", "name", "status", "type", "project_id", "wsjf_score"]
    rows = [{c: m.get(c, "") for c in cols} for m in missions]
    if getattr(args, "json_output", False):
        out.out_json(missions)
    else:
        print(out.table(rows, cols))


def cmd_missions_show(args):
    b = get_backend(args)
    output(args, b.mission_show(args.id))


def cmd_missions_create(args):
    b = get_backend(args)
    output(
        args, b.mission_create(args.name, args.project, getattr(args, "type", "epic"))
    )


def cmd_missions_start(args):
    b = get_backend(args)
    output(args, b.mission_start(args.id))


def cmd_missions_run(args):
    b = get_backend(args)
    if getattr(args, "headless", False):
        from cli._stream import run_headless

        run_headless(sys.argv)
        return
    # Start the mission first
    result = b.mission_run(args.id)
    if "error" in result:
        output(args, result)
        return
    # Then stream SSE
    url = b.mission_run_sse_url(args.id)
    if url:
        out.info(f"Mission {args.id} started — streaming live...")
        from cli._stream import print_stream

        print_stream(url)
    else:
        output(args, result)


def cmd_missions_wsjf(args):
    b = get_backend(args)
    output(args, b.mission_wsjf(args.id, args.bv, args.tc, args.rr, args.jd))


def cmd_missions_chat(args):
    b = get_backend(args)
    url = b.mission_chat_url(args.id)
    if not url:
        out.error("Chat requires API mode")
        sys.exit(1)
    msg = " ".join(args.message)
    from cli._stream import print_stream

    print_stream(url, "POST", {"message": msg})


def cmd_missions_reset(args):
    b = get_backend(args)
    output(args, b.mission_reset(args.id))


def cmd_missions_children(args):
    b = get_backend(args)
    output(args, b.mission_children(args.id))


def cmd_missions_screenshots(args):
    b = get_backend(args)
    data = b.api_get(f"/api/missions/{args.id}/screenshots")
    screenshots = data.get("screenshots", [])
    if not screenshots:
        out.info("No screenshots found for this mission.")
        return
    if getattr(args, "json_output", False):
        out.out_json(data)
    else:
        out.info(f"Screenshots for mission {args.id} ({len(screenshots)}):")
        for s in screenshots:
            name = s.get("name", "")
            size = s.get("size_kb", 0)
            path = s.get("path", "")
            print(f"  {out.CYAN}{name}{out.RESET}  ({size} KB)  {path}")


def cmd_missions_metrics(args):
    b = get_backend(args)
    data = b.api_get(f"/api/metrics/pipeline/{args.id}")
    if getattr(args, "json_output", False):
        out.out_json(data)
        return
    tools = data.get("tools", {})
    out.info(f"Pipeline Metrics — {args.id}")
    print(f"  Tools: {tools.get('total', 0)} calls, {tools.get('rate', 0)}% success")
    print(f"  Screenshots: {data.get('screenshots', 0)}")
    tickets = data.get("tickets", {})
    if tickets:
        print(f"  Tickets: {tickets}")
    print(f"  Phases: {len(data.get('phases', []))}")
    print(f"  Agents: {len(data.get('agents', []))}")


# ── Features ──


def cmd_features_list(args):
    b = get_backend(args)
    output(args, b.features_list(args.epic_id))


def cmd_features_create(args):
    b = get_backend(args)
    output(args, b.feature_create(args.epic_id, args.name, getattr(args, "sp", 3)))


def cmd_features_update(args):
    b = get_backend(args)
    kwargs = {}
    if getattr(args, "sp", None):
        kwargs["story_points"] = args.sp
    if getattr(args, "feat_status", None):
        kwargs["status"] = args.feat_status
    if getattr(args, "name", None):
        kwargs["name"] = args.name
    output(args, b.feature_update(args.id, **kwargs))


def cmd_features_deps(args):
    b = get_backend(args)
    output(args, b.feature_deps(args.id))


def cmd_features_add_dep(args):
    b = get_backend(args)
    output(args, b.feature_add_dep(args.id, args.dep_id))


def cmd_features_rm_dep(args):
    b = get_backend(args)
    output(args, b.feature_rm_dep(args.id, args.dep_id))


# ── Stories ──


def cmd_stories_list(args):
    b = get_backend(args)
    fid = getattr(args, "feature_id", None)
    output(args, b.stories_list(fid))


def cmd_stories_create(args):
    b = get_backend(args)
    output(args, b.story_create(args.feature_id, args.name, getattr(args, "sp", 2)))


def cmd_stories_update(args):
    b = get_backend(args)
    kwargs = {}
    if getattr(args, "sp", None):
        kwargs["story_points"] = args.sp
    if getattr(args, "story_status", None):
        kwargs["status"] = args.story_status
    if getattr(args, "sprint", None):
        kwargs["sprint_id"] = args.sprint
    output(args, b.story_update(args.id, **kwargs))


# ── Sprints ──


def cmd_sprints_create(args):
    b = get_backend(args)
    output(
        args, b.sprint_create(args.mission_id, args.name, getattr(args, "number", 1))
    )


def cmd_sprints_assign(args):
    b = get_backend(args)
    story_ids = args.stories.split(",")
    output(args, b.sprint_assign(args.sprint_id, story_ids))


def cmd_sprints_unassign(args):
    b = get_backend(args)
    output(args, b.sprint_unassign(args.sprint_id, args.story_id))


def cmd_sprints_available(args):
    b = get_backend(args)
    output(args, b.sprint_available(args.sprint_id))


# ── Backlog ──


def cmd_backlog_reorder(args):
    b = get_backend(args)
    ids = args.ids.split(",")
    output(args, b.backlog_reorder(args.type, ids))


# ── Agents ──


def cmd_agents_list(args):
    b = get_backend(args)
    agents = b.agents_list(getattr(args, "level", None))
    cols = ["id", "name", "role", "grade", "provider", "model"]
    rows = [
        {
            "id": a.get("id", ""),
            "name": a.get("name", ""),
            "role": a.get("role", ""),
            "grade": a.get("capability_grade", ""),
            "provider": a.get("provider", ""),
            "model": a.get("model", ""),
        }
        for a in agents
    ]
    if getattr(args, "json_output", False):
        out.out_json(agents)
    else:
        print(out.table(rows, cols))


def cmd_agents_show(args):
    b = get_backend(args)
    output(args, b.agent_show(args.id))


def cmd_agents_delete(args):
    b = get_backend(args)
    output(args, b.agent_delete(args.id))


# ── Sessions ──


def cmd_sessions_list(args):
    b = get_backend(args)
    sessions = b.sessions_list(getattr(args, "project", None))
    cols = ["id", "name", "status", "project_id", "goal"]
    rows = [{c: s.get(c, "") for c in cols} for s in sessions]
    if getattr(args, "json_output", False):
        out.out_json(sessions)
    else:
        print(out.table(rows, cols))


def cmd_sessions_show(args):
    b = get_backend(args)
    output(args, b.session_show(args.id))


def cmd_sessions_create(args):
    b = get_backend(args)
    agents = args.agents.split(",") if getattr(args, "agents", None) else None
    output(
        args,
        b.session_create(
            getattr(args, "project", None), agents, getattr(args, "pattern", "solo")
        ),
    )


def cmd_sessions_chat(args):
    b = get_backend(args)
    url = b.session_chat_url(args.id)
    if not url:
        out.error("Chat requires API mode")
        sys.exit(1)
    msg = " ".join(args.message)
    from cli._stream import print_stream

    print_stream(url, "POST", {"message": msg})


def cmd_sessions_stop(args):
    b = get_backend(args)
    output(args, b.session_stop(args.id))


def cmd_sessions_checkpoints(args):
    """Show live agent activity (step checkpoints) for a session."""
    b = get_backend(args)
    data = b.session_checkpoints(args.id)
    if getattr(args, "json_output", False):
        out.out_json(data)
        return
    checkpoints = data.get("checkpoints", [])
    if not checkpoints:
        print(f"No agent activity recorded for session {args.id}")
        return
    print(f"Agent activity — session {args.id} ({data.get('agent_count', 0)} agents)")
    cols = ["agent_id", "step", "last_tool", "preview"]
    rows = [{c: cp.get(c, "") for c in cols} for cp in checkpoints]
    print(out.table(rows, cols))


# ── Ideation ──


def cmd_ideation_start(args):
    b = get_backend(args)
    prompt = " ".join(args.prompt)
    project = getattr(args, "project", None)

    if getattr(args, "headless", False):
        from cli._stream import run_headless

        run_headless(sys.argv)
        return

    # Start ideation via API
    url = b.ideation_start_url()
    if not url:
        out.error("Ideation requires API mode (server must be running)")
        sys.exit(1)

    out.info(f"Starting ideation: {prompt[:80]}...")

    # POST to start, then SSE to stream
    result = b.ideation_start(prompt, project)
    if "error" in result:
        output(args, result)
        return

    session_id = result.get("session_id", "")
    if not session_id:
        output(args, result)
        return

    out.info(f"Session {session_id} — streaming agent conversation...")
    sse_url = b.ideation_session_url(session_id)
    from cli._stream import print_stream

    print_stream(sse_url)

    # After streaming completes
    print()
    out.info(f"Create epic: sf ideation create-epic {session_id}")


def cmd_ideation_create_epic(args):
    b = get_backend(args)
    output(args, b.ideation_create_epic(args.session_id))


def cmd_ideation_list(args):
    b = get_backend(args)
    output(args, b.ideation_list())


# ── Metrics ──


def cmd_metrics_dora(args):
    b = get_backend(args)
    output(args, b.metrics_dora(getattr(args, "project_id", None)))


def cmd_metrics_velocity(args):
    b = get_backend(args)
    output(args, b.metrics_velocity())


def cmd_metrics_burndown(args):
    b = get_backend(args)
    output(args, b.metrics_burndown(getattr(args, "epic_id", None)))


def cmd_metrics_cycle_time(args):
    b = get_backend(args)
    output(args, b.metrics_cycle_time())


# ── LLM ──


def cmd_llm_stats(args):
    b = get_backend(args)
    output(args, b.llm_stats())


def cmd_llm_rtk(args):
    """Show RTK (Reusable Token Knowledge) compression stats."""
    b = get_backend(args)
    mon = b.monitoring()
    rtk = mon.get("rtk", {})
    if getattr(args, "json_output", False):
        out.out_json(rtk)
        return
    if rtk.get("calls", 0) == 0:
        print("No RTK calls recorded yet.")
        return
    saved_kb = rtk.get("bytes_saved", 0) / 1024
    print("RTK Compression Stats")
    print(f"  Calls:        {rtk.get('calls', 0)}")
    print(f"  Bytes raw:    {rtk.get('bytes_raw', 0):,}")
    print(f"  Bytes saved:  {rtk.get('bytes_saved', 0):,} ({saved_kb:.1f} KB)")
    print(f"  Compression:  {rtk.get('ratio_pct', 0):.1f}%")
    print(f"  Tokens saved: ~{rtk.get('tokens_saved_est', 0):,} (estimated)")


def cmd_llm_usage(args):
    b = get_backend(args)
    output(args, b.llm_usage())


def cmd_llm_traces(args):
    b = get_backend(args)
    output(args, b.llm_traces(getattr(args, "limit", 20)))


# ── Tasks (Copilot→SF delegation) ──


def cmd_tasks_brief(args):
    """Submit a task brief to the SF — creates a TMA mission for agents to execute."""
    b = get_backend(args)
    brief = {
        "type": getattr(args, "type", "chore"),
        "title": " ".join(args.title),
        "description": getattr(args, "description", ""),
        "project_id": getattr(args, "project", "software-factory"),
    }
    if getattr(args, "files", None):
        brief["files"] = args.files.split(",")
    if getattr(args, "expected", None):
        brief["expected"] = args.expected
    if getattr(args, "test_cmd", None):
        brief["test_cmd"] = args.test_cmd
    result = b.task_brief_submit(brief)
    if getattr(args, "json_output", False):
        out.out_json(result)
        return
    mid = result.get("mission_id", "?")
    status = result.get("status", "?")
    url = result.get("session_url", "")
    print(f"Mission created: {mid}  status={status}")
    print(f"  sf missions show {mid}")
    print(f"  sf missions start {mid}   (to launch agents)")
    if url:
        print(f"  URL: {b.base_url}{url}")


def cmd_tasks_status(args):
    """Get status of a copilot-brief mission."""
    b = get_backend(args)
    output(args, b.task_brief_status(args.id))


# ── Memory ──


def cmd_memory_search(args):
    b = get_backend(args)
    output(args, b.memory_search(" ".join(args.query)))


def cmd_memory_project(args):
    b = get_backend(args)
    output(args, b.memory_project(args.project_id))


def cmd_memory_global(args):
    b = get_backend(args)
    key = getattr(args, "set_key", None)
    val = getattr(args, "set_value", None)
    if key and val:
        output(args, b.memory_global_set(key, val))
    else:
        output(args, b.memory_global())


# ── Chaos ──


def cmd_chaos_history(args):
    b = get_backend(args)
    output(args, b.chaos_history())


def cmd_chaos_trigger(args):
    b = get_backend(args)
    output(args, b.chaos_trigger(getattr(args, "scenario", None)))


# ── Watchdog ──


def cmd_watchdog_metrics(args):
    b = get_backend(args)
    output(args, b.watchdog_metrics())


# ── Incidents ──


def cmd_incidents_list(args):
    b = get_backend(args)
    output(args, b.incidents_list())


def cmd_incidents_create(args):
    b = get_backend(args)
    output(args, b.incident_create(args.title, getattr(args, "severity", "P2")))


# ── Autoheal ──


def cmd_autoheal_stats(args):
    b = get_backend(args)
    output(args, b.autoheal_stats())


def cmd_autoheal_trigger(args):
    b = get_backend(args)
    output(args, b.autoheal_trigger())


# ── Search ──


def cmd_search(args):
    b = get_backend(args)
    result = b.search(" ".join(args.query))
    if getattr(args, "json_output", False):
        out.out_json(result)
        return
    for cat, items in result.items():
        if items:
            print(out.bold(f"\n{cat.upper()}"))
            if isinstance(items, list) and items and isinstance(items[0], dict):
                print(out.table(items))
            else:
                for i in items:
                    print(f"  {i}")


# ── Export ──


def cmd_export(args):
    b = get_backend(args)
    fmt = getattr(args, "format", "json")
    if args.what == "epics":
        data = b.export_epics(fmt)
    else:
        data = b.export_features(fmt)
    if fmt == "csv" and isinstance(data, str):
        print(data)
    else:
        out.out_json(data)


# ── Releases ──


def cmd_releases(args):
    b = get_backend(args)
    output(args, b.releases(args.project_id))


# ── Notifications ──


def cmd_notifications_status(args):
    b = get_backend(args)
    output(args, b.notifications_status())


def cmd_notifications_test(args):
    b = get_backend(args)
    output(args, b.notifications_test())


# ── Runs (headless) ──


def cmd_runs_list(args):
    from cli._stream import list_runs

    runs = list_runs()
    if getattr(args, "json_output", False):
        out.out_json(runs)
    elif runs:
        print(out.table(runs, ["id", "pid", "status", "cmd"]))
    else:
        print(out.dim("No background runs"))


def cmd_runs_show(args):
    log_dir = os.path.expanduser("~/.sf/runs")
    log_file = os.path.join(log_dir, f"{args.run_id}.log")
    if os.path.exists(log_file):
        with open(log_file) as f:
            print(f.read())
    else:
        out.error(f"Run {args.run_id} not found")


def cmd_runs_tail(args):
    from cli._stream import tail_run

    tail_run(args.run_id)


def cmd_runs_stop(args):
    from cli._stream import stop_run

    stop_run(args.run_id)


# ── Workflows ──


def cmd_workflows_list(args):
    b = get_backend(args)
    workflows = b.workflows_list()
    if getattr(args, "json_output", False):
        out.out_json(workflows)
    elif workflows:
        cols = ["id", "name", "pattern_type"]
        rows = [{c: w.get(c, "") for c in cols} for w in workflows]
        print(out.table(rows, cols))
    else:
        print(out.dim("No workflows"))


def cmd_workflows_show(args):
    b = get_backend(args)
    output(args, b.workflow_show(args.id))


# ── Patterns ──


def cmd_patterns_list(args):
    b = get_backend(args)
    patterns = b.patterns_list()
    if getattr(args, "json_output", False):
        out.out_json(patterns)
    elif patterns:
        cols = ["id", "name", "description"]
        rows = [{c: p.get(c, "") for c in cols} for p in patterns]
        print(out.table(rows, cols))
    else:
        print(out.dim("No patterns"))


def cmd_patterns_show(args):
    b = get_backend(args)
    output(args, b.pattern_show(args.id))


# ── Darwin Teams ──


def cmd_teams_leaderboard(args):
    b = get_backend(args)
    d = b.teams_leaderboard(
        technology=getattr(args, "technology", "generic") or "generic",
        phase_type=getattr(args, "phase_type", "generic") or "generic",
        limit=getattr(args, "limit", 20),
    )
    teams = d.get("data", []) if isinstance(d, dict) else d
    if getattr(args, "json_output", False):
        out.out_json(teams)
    elif teams:
        cols = [
            "agent_name",
            "pattern_id",
            "fitness_score",
            "runs",
            "wins",
            "losses",
            "badge",
        ]
        rows = [{c: str(t.get(c, "")) for c in cols} for t in teams]
        print(
            out.bold(
                f"Leaderboard — {d.get('technology', '?')} / {d.get('phase_type', '?')}"
            )
        )
        print(out.table(rows, cols))
    else:
        print(
            out.dim("No fitness data yet. Run missions with skill:* agent references.")
        )


def cmd_teams_okr(args):
    b = get_backend(args)
    d = b.teams_okr(
        technology=getattr(args, "technology", "") or "",
        phase_type=getattr(args, "phase_type", "") or "",
    )
    okrs = d if isinstance(d, list) else []
    if getattr(args, "json_output", False):
        out.out_json(okrs)
    elif okrs:
        cols = [
            "team_key",
            "phase_type",
            "kpi_name",
            "kpi_current",
            "kpi_target",
            "kpi_unit",
            "progress_pct",
        ]
        rows = [{c: str(o.get(c, "")) for c in cols} for o in okrs]
        print(out.table(rows, cols))
    else:
        print(out.dim("No OKRs found."))


def cmd_teams_selections(args):
    b = get_backend(args)
    d = b.teams_selections(limit=getattr(args, "limit", 20))
    sels = d.get("data", []) if isinstance(d, dict) else []
    if getattr(args, "json_output", False):
        out.out_json(sels)
    elif sels:
        cols = [
            "selected_at",
            "agent_id",
            "pattern_id",
            "selection_mode",
            "technology",
            "phase_type",
        ]
        rows = [{c: str(s.get(c, "")) for c in cols} for s in sels]
        print(out.table(rows, cols))
    else:
        print(out.dim("No selections yet."))


def cmd_teams_ab_tests(args):
    b = get_backend(args)
    d = b.teams_ab_tests(
        status=getattr(args, "status", "") or "", limit=getattr(args, "limit", 20)
    )
    tests = d.get("data", []) if isinstance(d, dict) else []
    if getattr(args, "json_output", False):
        out.out_json(tests)
    elif tests:
        cols = [
            "started_at",
            "technology",
            "phase_type",
            "team_a_agent",
            "team_b_agent",
            "status",
            "winner",
        ]
        rows = [{c: str(t.get(c, "")) for c in cols} for t in tests]
        print(out.table(rows, cols))
    else:
        print(out.dim("No A/B tests yet."))


def cmd_teams_retire(args):
    b = get_backend(args)
    r = b.teams_retire(
        args.agent_id,
        args.pattern_id,
        getattr(args, "technology", "generic") or "generic",
        getattr(args, "phase_type", "generic") or "generic",
    )
    output(args, r)


def cmd_teams_unretire(args):
    b = get_backend(args)
    r = b.teams_unretire(
        args.agent_id,
        args.pattern_id,
        getattr(args, "technology", "generic") or "generic",
        getattr(args, "phase_type", "generic") or "generic",
    )
    output(args, r)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sf",
        description="Software Factory CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  sf status                                    Platform health
  sf ideation "app de suivi vélo iot"          Launch multi-agent ideation
  sf missions list --project myproj            List missions
  sf missions run abc123                       Run mission with live streaming
  sf projects chat myproj "ajoute un auth"     Chat with PM agent
  sf agents list                               List all agents
  sf llm stats                                 LLM usage statistics
""",
    )

    # Global flags
    p.add_argument("--url", default=DEFAULT_URL, help="Platform URL")
    p.add_argument(
        "--json", dest="json_output", action="store_true", help="Raw JSON output"
    )
    p.add_argument(
        "--token", default=os.environ.get("MACARON_TOKEN"), help="Auth token"
    )
    p.add_argument("--api", action="store_true", help="Force API mode")
    p.add_argument("--db", action="store_true", help="Force DB mode")
    p.add_argument("--db-path", dest="db_path", help="SQLite DB path")
    p.add_argument("--no-color", action="store_true", help="Disable colors")
    p.add_argument("-v", "--verbose", action="store_true")

    sub = p.add_subparsers(dest="command", help="Command")

    # status
    sub.add_parser("status", help="Platform health and stats").set_defaults(
        func=cmd_status
    )

    # ── projects ──
    proj = sub.add_parser("projects", help="Project management")
    proj_sub = proj.add_subparsers(dest="subcmd")

    proj_sub.add_parser("list", help="List projects").set_defaults(
        func=cmd_projects_list
    )

    pc = proj_sub.add_parser("create", help="Create project")
    pc.add_argument("name")
    pc.add_argument("--desc", default="")
    pc.add_argument("--path", default="")
    pc.add_argument("--type", default="web")
    pc.set_defaults(func=cmd_projects_create)

    ps = proj_sub.add_parser("show", help="Show project")
    ps.add_argument("id")
    ps.set_defaults(func=cmd_projects_show)

    pv = proj_sub.add_parser("vision", help="Get/set vision")
    pv.add_argument("id")
    pv.add_argument("--set", dest="set", default=None)
    pv.set_defaults(func=cmd_projects_vision)

    pch = proj_sub.add_parser("chat", help="Chat with PM agent")
    pch.add_argument("id")
    pch.add_argument("message", nargs="+")
    pch.set_defaults(func=cmd_projects_chat)

    pph = proj_sub.add_parser("phase", help="Get or set project phase")
    pph.add_argument("id")
    pph.add_argument(
        "phase", nargs="?", default=None, help="New phase (omit to get current)"
    )
    pph.set_defaults(func=cmd_projects_phase)

    phlt = proj_sub.add_parser("health", help="Project health score")
    phlt.add_argument("id")
    phlt.set_defaults(func=cmd_projects_health)

    pms = proj_sub.add_parser("missions-suggest", help="Suggest next missions")
    pms.add_argument("id")
    pms.set_defaults(func=cmd_projects_missions_suggest)

    # ── missions ──
    miss = sub.add_parser("missions", help="Mission management")
    miss_sub = miss.add_subparsers(dest="subcmd")

    ml = miss_sub.add_parser("list", help="List missions")
    ml.add_argument("--project", "-p")
    ml.add_argument("--status", "-s")
    ml.set_defaults(func=cmd_missions_list)

    ms = miss_sub.add_parser("show", help="Show mission")
    ms.add_argument("id")
    ms.set_defaults(func=cmd_missions_show)

    mc = miss_sub.add_parser("create", help="Create mission")
    mc.add_argument("name")
    mc.add_argument("--project", "-p", required=True)
    mc.add_argument("--type", default="epic")
    mc.set_defaults(func=cmd_missions_create)

    mst = miss_sub.add_parser("start", help="Start mission")
    mst.add_argument("id")
    mst.set_defaults(func=cmd_missions_start)

    mr = miss_sub.add_parser("run", help="Run mission (stream live)")
    mr.add_argument("id")
    mr.add_argument("--headless", action="store_true")
    mr.set_defaults(func=cmd_missions_run)

    mw = miss_sub.add_parser("wsjf", help="Calculate WSJF")
    mw.add_argument("id")
    mw.add_argument("--bv", type=int, default=5, help="Business value")
    mw.add_argument("--tc", type=int, default=5, help="Time criticality")
    mw.add_argument("--rr", type=int, default=5, help="Risk reduction")
    mw.add_argument("--jd", type=int, default=5, help="Job duration")
    mw.set_defaults(func=cmd_missions_wsjf)

    mch = miss_sub.add_parser("chat", help="Chat with mission")
    mch.add_argument("id")
    mch.add_argument("message", nargs="+")
    mch.set_defaults(func=cmd_missions_chat)

    mre = miss_sub.add_parser("reset", help="Reset mission")
    mre.add_argument("id")
    mre.set_defaults(func=cmd_missions_reset)

    mchi = miss_sub.add_parser("children", help="List sub-missions")
    mchi.add_argument("id")
    mchi.set_defaults(func=cmd_missions_children)

    mss = miss_sub.add_parser("screenshots", help="List mission screenshots")
    mss.add_argument("id")
    mss.set_defaults(func=cmd_missions_screenshots)

    mme = miss_sub.add_parser("metrics", help="Pipeline metrics for mission")
    mme.add_argument("id")
    mme.set_defaults(func=cmd_missions_metrics)

    # ── features ──
    feat = sub.add_parser("features", help="Feature management")
    feat_sub = feat.add_subparsers(dest="subcmd")

    fl = feat_sub.add_parser("list", help="List features in epic")
    fl.add_argument("epic_id")
    fl.set_defaults(func=cmd_features_list)

    fc = feat_sub.add_parser("create", help="Create feature")
    fc.add_argument("epic_id")
    fc.add_argument("name")
    fc.add_argument("--sp", type=int, default=3)
    fc.set_defaults(func=cmd_features_create)

    fu = feat_sub.add_parser("update", help="Update feature")
    fu.add_argument("id")
    fu.add_argument("--sp", type=int)
    fu.add_argument("--status", dest="feat_status")
    fu.add_argument("--name")
    fu.set_defaults(func=cmd_features_update)

    fd = feat_sub.add_parser("deps", help="List dependencies")
    fd.add_argument("id")
    fd.set_defaults(func=cmd_features_deps)

    fad = feat_sub.add_parser("add-dep", help="Add dependency")
    fad.add_argument("id")
    fad.add_argument("dep_id")
    fad.set_defaults(func=cmd_features_add_dep)

    frd = feat_sub.add_parser("rm-dep", help="Remove dependency")
    frd.add_argument("id")
    frd.add_argument("dep_id")
    frd.set_defaults(func=cmd_features_rm_dep)

    # ── stories ──
    stor = sub.add_parser("stories", help="User story management")
    stor_sub = stor.add_subparsers(dest="subcmd")

    sl = stor_sub.add_parser("list", help="List stories")
    sl.add_argument("--feature", dest="feature_id", help="Filter by feature ID")
    sl.set_defaults(func=cmd_stories_list)

    sc = stor_sub.add_parser("create", help="Create story")
    sc.add_argument("feature_id")
    sc.add_argument("name")
    sc.add_argument("--sp", type=int, default=2)
    sc.set_defaults(func=cmd_stories_create)

    su = stor_sub.add_parser("update", help="Update story")
    su.add_argument("id")
    su.add_argument("--sp", type=int)
    su.add_argument("--status", dest="story_status")
    su.add_argument("--sprint")
    su.set_defaults(func=cmd_stories_update)

    # ── sprints ──
    spr = sub.add_parser("sprints", help="Sprint management")
    spr_sub = spr.add_subparsers(dest="subcmd")

    spc = spr_sub.add_parser("create", help="Create sprint")
    spc.add_argument("mission_id")
    spc.add_argument("name")
    spc.add_argument("--number", type=int, default=1)
    spc.set_defaults(func=cmd_sprints_create)

    spa = spr_sub.add_parser("assign", help="Assign stories to sprint")
    spa.add_argument("sprint_id")
    spa.add_argument("--stories", required=True, help="Comma-separated story IDs")
    spa.set_defaults(func=cmd_sprints_assign)

    spu = spr_sub.add_parser("unassign", help="Remove story from sprint")
    spu.add_argument("sprint_id")
    spu.add_argument("story_id")
    spu.set_defaults(func=cmd_sprints_unassign)

    spav = spr_sub.add_parser("available", help="Available stories for sprint")
    spav.add_argument("sprint_id")
    spav.set_defaults(func=cmd_sprints_available)

    # ── backlog ──
    blg = sub.add_parser("backlog", help="Backlog management")
    blg_sub = blg.add_subparsers(dest="subcmd")

    bro = blg_sub.add_parser("reorder", help="Reorder backlog items")
    bro.add_argument("--type", required=True, choices=["features", "stories"])
    bro.add_argument("--ids", required=True, help="Comma-separated IDs in order")
    bro.set_defaults(func=cmd_backlog_reorder)

    # ── agents ──
    agt = sub.add_parser("agents", help="Agent management")
    agt_sub = agt.add_subparsers(dest="subcmd")

    al = agt_sub.add_parser("list", help="List agents")
    al.add_argument("--level", "-l")
    al.set_defaults(func=cmd_agents_list)

    ash = agt_sub.add_parser("show", help="Show agent details")
    ash.add_argument("id")
    ash.set_defaults(func=cmd_agents_show)

    ad = agt_sub.add_parser("delete", help="Delete agent")
    ad.add_argument("id")
    ad.set_defaults(func=cmd_agents_delete)

    # ── sessions ──
    sess = sub.add_parser("sessions", help="Session management")
    sess_sub = sess.add_subparsers(dest="subcmd")

    sl = sess_sub.add_parser("list", help="List sessions")
    sl.add_argument("--project", "-p")
    sl.set_defaults(func=cmd_sessions_list)

    ssh = sess_sub.add_parser("show", help="Show session")
    ssh.add_argument("id")
    ssh.set_defaults(func=cmd_sessions_show)

    scr = sess_sub.add_parser("create", help="Create session")
    scr.add_argument("--project", "-p")
    scr.add_argument("--agents")
    scr.add_argument("--pattern", default="solo")
    scr.set_defaults(func=cmd_sessions_create)

    sch = sess_sub.add_parser("chat", help="Chat in session")
    sch.add_argument("id")
    sch.add_argument("message", nargs="+")
    sch.set_defaults(func=cmd_sessions_chat)

    sst = sess_sub.add_parser("stop", help="Stop session")
    sst.add_argument("id")
    sst.set_defaults(func=cmd_sessions_stop)

    scp = sess_sub.add_parser("checkpoints", help="Live agent activity for a session")
    scp.add_argument("id")
    scp.set_defaults(func=cmd_sessions_checkpoints)

    # ── ideation ──
    ide = sub.add_parser("ideation", help="Multi-agent ideation")
    ide_sub = ide.add_subparsers(dest="subcmd")

    ist = ide_sub.add_parser("start", help="Start ideation session")
    ist.add_argument("prompt", nargs="+")
    ist.add_argument("--project", "-p")
    ist.add_argument("--headless", action="store_true")
    ist.set_defaults(func=cmd_ideation_start)

    ice = ide_sub.add_parser("create-epic", help="Create epic from ideation")
    ice.add_argument("session_id")
    ice.set_defaults(func=cmd_ideation_create_epic)

    il = ide_sub.add_parser("list", help="List ideation sessions")
    il.set_defaults(func=cmd_ideation_list)

    # ── ideation shortcut: sf ideation "prompt" ──
    # handled in main() below

    # ── metrics ──
    met = sub.add_parser("metrics", help="Platform metrics")
    met_sub = met.add_subparsers(dest="subcmd")

    md = met_sub.add_parser("dora", help="DORA metrics")
    md.add_argument("--project-id", "-p")
    md.set_defaults(func=cmd_metrics_dora)

    met_sub.add_parser("velocity", help="Sprint velocity").set_defaults(
        func=cmd_metrics_velocity
    )

    mb = met_sub.add_parser("burndown", help="Burndown chart")
    mb.add_argument("--epic-id", "-e")
    mb.set_defaults(func=cmd_metrics_burndown)

    met_sub.add_parser("cycle-time", help="Cycle time").set_defaults(
        func=cmd_metrics_cycle_time
    )

    # ── llm ──
    llm = sub.add_parser("llm", help="LLM monitoring")
    llm_sub = llm.add_subparsers(dest="subcmd")

    llm_sub.add_parser("stats", help="LLM statistics").set_defaults(func=cmd_llm_stats)
    llm_sub.add_parser("usage", help="LLM usage/cost").set_defaults(func=cmd_llm_usage)

    lt = llm_sub.add_parser("traces", help="LLM call traces")
    lt.add_argument("--limit", "-n", type=int, default=20)
    lt.set_defaults(func=cmd_llm_traces)

    llm_sub.add_parser("rtk", help="RTK token compression stats").set_defaults(
        func=cmd_llm_rtk
    )

    # ── tasks (Copilot→SF delegation) ──
    tasks = sub.add_parser("tasks", help="Delegate tasks to SF agents")
    tasks_sub = tasks.add_subparsers(dest="subcmd")

    tb = tasks_sub.add_parser("brief", help="Submit a task brief to the SF")
    tb.add_argument("title", nargs="+", help="Task title")
    tb.add_argument(
        "--type",
        "-t",
        default="chore",
        choices=["bug_fix", "feature", "refactor", "docs", "test", "chore"],
        help="Task type",
    )
    tb.add_argument("--desc", "-d", dest="description", default="", help="Description")
    tb.add_argument(
        "--files", "-f", default=None, help="Comma-separated file:line refs"
    )
    tb.add_argument("--expected", "-e", default=None, help="Expected behavior")
    tb.add_argument(
        "--test-cmd", default=None, dest="test_cmd", help="Test command to run"
    )
    tb.add_argument("--project", "-p", default="software-factory", help="Project ID")
    tb.set_defaults(func=cmd_tasks_brief)

    ts = tasks_sub.add_parser("status", help="Status of a copilot-brief mission")
    ts.add_argument("id")
    ts.set_defaults(func=cmd_tasks_status)

    # ── memory ──
    mem = sub.add_parser("memory", help="Memory/knowledge management")
    mem_sub = mem.add_subparsers(dest="subcmd")

    ms = mem_sub.add_parser("search", help="Search memory")
    ms.add_argument("query", nargs="+")
    ms.set_defaults(func=cmd_memory_search)

    mp = mem_sub.add_parser("project", help="Project memory")
    mp.add_argument("project_id")
    mp.set_defaults(func=cmd_memory_project)

    mg = mem_sub.add_parser("global", help="Global memory")
    mg.add_argument("--set-key")
    mg.add_argument("--set-value")
    mg.set_defaults(func=cmd_memory_global)

    # ── workflows ──
    wf = sub.add_parser("workflows", help="Workflow management")
    wf_sub = wf.add_subparsers(dest="subcmd")

    wf_sub.add_parser("list", help="List workflows").set_defaults(
        func=cmd_workflows_list
    )

    wfs = wf_sub.add_parser("show", help="Show workflow")
    wfs.add_argument("id")
    wfs.set_defaults(func=cmd_workflows_show)

    # ── patterns ──
    pat = sub.add_parser("patterns", help="Pattern management")
    pat_sub = pat.add_subparsers(dest="subcmd")

    pat_sub.add_parser("list", help="List patterns").set_defaults(
        func=cmd_patterns_list
    )

    pts = pat_sub.add_parser("show", help="Show pattern")
    pts.add_argument("id")
    pts.set_defaults(func=cmd_patterns_show)

    # ── chaos ──
    cha = sub.add_parser("chaos", help="Chaos testing")
    cha_sub = cha.add_subparsers(dest="subcmd")

    cha_sub.add_parser("history", help="Chaos run history").set_defaults(
        func=cmd_chaos_history
    )

    ct = cha_sub.add_parser("trigger", help="Trigger chaos scenario")
    ct.add_argument("--scenario", "-s")
    ct.set_defaults(func=cmd_chaos_trigger)

    # ── watchdog ──
    wd = sub.add_parser("watchdog", help="Watchdog monitoring")
    wd_sub = wd.add_subparsers(dest="subcmd")
    wd_sub.add_parser("metrics", help="Watchdog metrics").set_defaults(
        func=cmd_watchdog_metrics
    )

    # ── incidents ──
    inc = sub.add_parser("incidents", help="Incident management")
    inc_sub = inc.add_subparsers(dest="subcmd")

    inc_sub.add_parser("list", help="List incidents").set_defaults(
        func=cmd_incidents_list
    )

    icr = inc_sub.add_parser("create", help="Create incident")
    icr.add_argument("title")
    icr.add_argument("--severity", default="P2", choices=["P0", "P1", "P2", "P3"])
    icr.set_defaults(func=cmd_incidents_create)

    # ── autoheal ──
    ah = sub.add_parser("autoheal", help="Auto-healing")
    ah_sub = ah.add_subparsers(dest="subcmd")
    ah_sub.add_parser("stats", help="Autoheal statistics").set_defaults(
        func=cmd_autoheal_stats
    )
    ah_sub.add_parser("trigger", help="Trigger autoheal").set_defaults(
        func=cmd_autoheal_trigger
    )

    # ── search ──
    srch = sub.add_parser("search", help="Global search")
    srch.add_argument("query", nargs="+")
    srch.set_defaults(func=cmd_search)

    # ── export ──
    exp = sub.add_parser("export", help="Export data")
    exp.add_argument("what", choices=["epics", "features"])
    exp.add_argument("--format", default="json", choices=["json", "csv"])
    exp.set_defaults(func=cmd_export)

    # ── releases ──
    rel = sub.add_parser("releases", help="Project releases")
    rel.add_argument("project_id")
    rel.set_defaults(func=cmd_releases)

    # ── notifications ──
    notif = sub.add_parser("notifications", help="Notification management")
    notif_sub = notif.add_subparsers(dest="subcmd")
    notif_sub.add_parser("status", help="Notification status").set_defaults(
        func=cmd_notifications_status
    )
    notif_sub.add_parser("test", help="Send test notification").set_defaults(
        func=cmd_notifications_test
    )

    # ── runs (headless) ──
    runs = sub.add_parser("runs", help="Background runs")
    runs_sub = runs.add_subparsers(dest="subcmd")
    runs_sub.add_parser("list", help="List active runs").set_defaults(
        func=cmd_runs_list
    )

    rsh = runs_sub.add_parser("show", help="Show run output")
    rsh.add_argument("run_id")
    rsh.set_defaults(func=cmd_runs_show)

    rt = runs_sub.add_parser("tail", help="Tail run log")
    rt.add_argument("run_id")
    rt.set_defaults(func=cmd_runs_tail)

    rsp = runs_sub.add_parser("stop", help="Stop run")
    rsp.add_argument("run_id")
    rsp.set_defaults(func=cmd_runs_stop)

    # ── teams (Darwin) ──
    teams = sub.add_parser("teams", help="Darwin team fitness (Thompson Sampling)")
    teams_sub = teams.add_subparsers(dest="subcmd")

    tlb = teams_sub.add_parser("leaderboard", help="Fitness leaderboard")
    tlb.add_argument("--technology", "-t", default="generic")
    tlb.add_argument("--phase", dest="phase_type", default="generic")
    tlb.add_argument("--limit", type=int, default=20)
    tlb.set_defaults(func=cmd_teams_leaderboard)

    tokr = teams_sub.add_parser("okr", help="OKR / KPI objectives")
    tokr.add_argument("--technology", "-t", default="")
    tokr.add_argument("--phase", dest="phase_type", default="")
    tokr.set_defaults(func=cmd_teams_okr)

    tsel = teams_sub.add_parser("selections", help="Recent selection log")
    tsel.add_argument("--limit", type=int, default=20)
    tsel.set_defaults(func=cmd_teams_selections)

    tab = teams_sub.add_parser("ab-tests", help="A/B test results")
    tab.add_argument("--status", default="")
    tab.add_argument("--limit", type=int, default=20)
    tab.set_defaults(func=cmd_teams_ab_tests)

    tret = teams_sub.add_parser("retire", help="Soft-retire a team")
    tret.add_argument("agent_id")
    tret.add_argument("pattern_id")
    tret.add_argument("--technology", "-t", default="generic")
    tret.add_argument("--phase", dest="phase_type", default="generic")
    tret.set_defaults(func=cmd_teams_retire)

    tunret = teams_sub.add_parser("unretire", help="Restore a retired team")
    tunret.add_argument("agent_id")
    tunret.add_argument("pattern_id")
    tunret.add_argument("--technology", "-t", default="generic")
    tunret.add_argument("--phase", dest="phase_type", default="generic")
    tunret.set_defaults(func=cmd_teams_unretire)

    return p


def main():
    # Handle help shortcut: sf help [command]
    if len(sys.argv) >= 2 and sys.argv[1] == "help":
        if len(sys.argv) == 2:
            # sf help -> show full help
            sys.argv[1] = "--help"
        else:
            # sf help <command> -> sf <command> --help
            cmd = sys.argv[2]
            sys.argv = [sys.argv[0], cmd, "--help"]

    # Handle ideation shortcut: sf [options] ideation "prompt..."
    # Find "ideation" anywhere in argv, then check next arg
    try:
        idx = sys.argv.index("ideation")
        if idx + 1 < len(sys.argv) and sys.argv[idx + 1] not in (
            "start",
            "create-epic",
            "list",
            "--help",
            "-h",
        ):
            sys.argv.insert(idx + 1, "start")
    except ValueError:
        pass

    parser = build_parser()
    args = parser.parse_args()

    if getattr(args, "no_color", False):
        out.NO_COLOR = True

    if not hasattr(args, "func") or args.func is None:
        parser.print_help()
        sys.exit(0)

    try:
        args.func(args)
    except KeyboardInterrupt:
        print()
        sys.exit(130)
    except Exception as e:
        if getattr(args, "verbose", False):
            import traceback

            traceback.print_exc()
        else:
            out.error(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
