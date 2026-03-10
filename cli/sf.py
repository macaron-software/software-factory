#!/usr/bin/env python3
"""sf — Software Factory CLI.

Full-featured CLI mirroring all web dashboard functionality.
Dual mode: API (server) or DB (direct PostgreSQL via DATABASE_URL).

Usage:
    sf status
    sf ideation "site web de suivi de vélo iot gps"
    sf jarvis "quelle stack pour un jeu 3D temps-réel ?"
    sf missions list --project myproj
    sf projects chat myproj "ajoute un module auth"
    sf agents list
    sf llm stats
"""

import argparse
import os
import subprocess
import sys

# Ensure cli package is importable
_cli_dir = os.path.dirname(os.path.abspath(__file__))
_sf_dir = os.path.dirname(_cli_dir)
if _sf_dir not in sys.path:
    sys.path.insert(0, _sf_dir)

from cli import _output as out  # noqa: E402

DEFAULT_URL = os.environ.get("MACARON_URL", "http://localhost:8090")

# Simplify axes — single source of truth used in cmd_simplify and build_parser
_SIMPLIFY_AXES = ("reuse", "quality", "efficiency")


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

        pg_url = (
            getattr(args, "db_path", None)
            or os.environ.get("SF_DB_PATH")
            or os.environ.get("DATABASE_URL")
        )
        return DBBackend(pg_url)
    except (RuntimeError, ImportError) as e:
        out.error(f"No server at {args.url} and no PostgreSQL connection available")
        out.error(str(e))
        out.error("Set DATABASE_URL or use --url URL")
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
    missions_count = health.get("epics", {})
    if isinstance(missions_count, dict):
        print(
            f"Epics: {missions_count.get('running', 0)} running  {missions_count.get('total', 0)} total"
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
    result = b.epic_run(args.id)
    if "error" in result:
        output(args, result)
        return
    # Then stream SSE
    url = b.epic_run_sse_url(args.id)
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


# ── CTO / Jarvis ──


def cmd_jarvis(args):
    """Send a message to Jarvis (CTO agent) via /api/cto/message — stored in Jarvis history."""
    b = get_backend(args)
    message = " ".join(args.message)
    session_id = getattr(args, "session_id", None) or ""

    if not message:
        out.error('Usage: sf jarvis "your question"')
        sys.exit(1)

    url = b.cto_message_url()
    if not url:
        out.error("Jarvis requires API mode (server must be running)")
        sys.exit(1)

    # Create a new session if none specified
    if not session_id:
        result = b.cto_new_session()
        session_id = result.get("session_id", "")

    out.info(f"Jarvis [{session_id[:8]}] — {message[:80]}...")

    from cli._stream import print_stream

    auth_headers = b._auth_headers() if hasattr(b, "_auth_headers") else {}

    # Stream the CTO message — events: user_html (skip), chunk (text), done, error
    print_stream(
        url,
        method="POST",
        json_body={"content": message, "session_id": session_id},
        headers=auth_headers,
    )
    print()


def cmd_jarvis_list(args):
    b = get_backend(args)
    sessions = b.cto_sessions()
    if not sessions:
        out.info("No Jarvis sessions found.")
        return
    for s in sessions[:20]:
        sid = s.get("id", s.get("session_id", "?"))[:8]
        title = s.get("title") or s.get("name") or "(no title)"
        ts = (s.get("updated_at") or s.get("created_at") or "")[:16]
        print(f"  {sid}  {ts}  {title}")


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


# ── Simplify ──


def _auth_headers(args) -> dict:
    """Build auth headers from token or MACARON_TOKEN env var."""
    token = getattr(args, "token", None) or os.environ.get("MACARON_TOKEN")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


# ── AC (Amélioration Continue) ──
# ⚠️  AC = SUPERVISION, NOT EXECUTION
# Pilot projects run as NORMAL projects (feature-sprint, RTE+PM+Feature Teams).
# AC agents observe in // → analyze → fix SF-only issues (skills, prompts, configs).
# AC agents NEVER build/deploy/commit project code.
# See CLAUDE.md "RÈGLE ABSOLUE — AC = SUPERVISION" for full spec.

_AC_PROJECT_IDS = [
    "ac-hello-html",
    "ac-hello-vue",
    "ac-fullstack-rs",
    "ac-docsign-clone",
    "ac-ecommerce-solaris",
    "ac-game-threejs",
    "ac-game-native",
    "ac-migration-php",
]


def cmd_ac_list(args):
    """List all AC pilot projects with cycle, score, status."""
    b = get_backend(args)
    cycles = b.ac_list()
    # Build a map from health data
    health_map = {c["project"]: c for c in cycles}
    rows = []
    for pid in _AC_PROJECT_IDS:
        h = health_map.get(pid, {})
        rows.append(
            {
                "project": pid.replace("ac-", ""),
                "id": pid,
                "cycle": h.get("cycle", 0),
                "status": h.get("status", "idle"),
                "updated": (h.get("updated_at") or "")[:16],
            }
        )
    if getattr(args, "json_output", False):
        out.out_json(rows)
    else:
        print(out.table(rows, ["project", "cycle", "status", "updated"]))


def cmd_ac_status(args):
    """Detailed AC status for one project."""
    b = get_backend(args)
    data = b.ac_project(args.project_id)
    if getattr(args, "json_output", False):
        out.out_json(data)
        return
    pid = data.get("project_id", args.project_id)
    cycle = data.get("current_cycle", 0)
    status = data.get("status", "idle")
    score = data.get("total_score_avg", 0)
    conv = (data.get("convergence") or {}).get("status", "?")
    recent = data.get("recent_scores", [])
    hint = data.get("next_cycle_hint")
    skill_eval = data.get("skill_eval_pending")

    status_fn = (
        out.green
        if status in ("idle", "completed")
        else out.yellow
        if status == "running"
        else out.red
    )
    print(
        f"{out.bold(pid)}  cycle={cycle}  status={status_fn(status)}  avg_score={score:.1f}"
    )
    print(f"Convergence: {conv}")
    if recent:
        scores_str = " → ".join(str(s) for s in recent)
        print(f"Recent scores: {scores_str}")
    if hint:
        action = hint.get("action", "?") if isinstance(hint, dict) else hint
        conf = hint.get("confidence", "") if isinstance(hint, dict) else ""
        conf_str = f"  conf={conf:.2f}" if conf else ""
        print(f"RL hint: {out.yellow(str(action))}{conf_str}")
    if skill_eval:
        skills = (
            skill_eval.get("skills", skill_eval)
            if isinstance(skill_eval, dict)
            else skill_eval
        )
        print(
            f"Skill eval pending: {', '.join(skills) if isinstance(skills, list) else skills}"
        )


def cmd_ac_start(args):
    """Start one or all AC pilot project cycles (dual sessions: BUILD + SUPERVISE)."""
    b = get_backend(args)
    ids = _AC_PROJECT_IDS if getattr(args, "all", False) else [args.project_id]
    for pid in ids:
        result = b.ac_start(pid)
        if "error" in result:
            print(f"{out.red('✗')} {pid}: {result['error']}")
        else:
            cycle = result.get("cycle_num", "?")
            build_id = result.get("builder_session_id", "")
            sup_id = result.get("supervisor_session_id", "")
            if build_id and sup_id:
                # Dual session mode (new architecture)
                print(f"{out.green('✓')} {pid}  cycle={cycle}")
                print(f"  [BUILD]     session={build_id}  workflow=feature-sprint")
                print(f"  [SUPERVISE] session={sup_id}  workflow=ac-supervision-cycle")
            else:
                # Legacy single session (backward compat)
                session_id = result.get("session_id", result.get("id", "?"))
                print(f"{out.green('✓')} {pid}  cycle={cycle}  session={session_id}")


def cmd_ac_stop(args):
    """Stop a running AC cycle."""
    b = get_backend(args)
    result = b.ac_stop(args.project_id)
    output(args, result)


def cmd_ac_rollback(args):
    """Rollback the last AC cycle (git revert + delete record)."""
    b = get_backend(args)
    result = b.ac_rollback(args.project_id)
    output(args, result)


def cmd_ac_cycles(args):
    """Show recent cycle score history for a project."""
    b = get_backend(args)
    data = b.ac_project(args.project_id)
    if getattr(args, "json_output", False):
        out.out_json(data)
        return
    recent = data.get("recent_scores", [])
    cycle_count = data.get("cycle_count", 0)
    print(f"{out.bold(args.project_id)}  total cycles: {cycle_count}")
    if recent:
        for i, score in enumerate(recent):
            start_cycle = max(1, cycle_count - len(recent) + 1)
            bar = "█" * int(score / 5) if score else ""
            print(f"  cy{start_cycle + i:>3}  {score:>3}  {bar}")
    else:
        print("  No cycle data yet.")


# AC scope rules: AC agents are SUPERVISORS — they should NEVER write project files.
# Any file_write/code_write from an AC agent = SCOPE VIOLATION (they only observe).
# ac-codex and ac-cicd are BUILDERS — they run via [BUILD] feature-sprint, NOT AC supervision.
_AC_SCOPE_FORBIDDEN: dict[str, list[str]] = {
    # Supervision agents: NEVER write ANY project file
    "ac-architect": ["src/", "tests/", "Dockerfile", "package.json", "skills/"],
    "ac-adversarial": ["src/", "tests/", "Dockerfile", "package.json", "skills/"],
    "ac-qa-agent": ["src/", "tests/", "Dockerfile", "package.json", "skills/"],
    "ac-coach": ["src/", "tests/", "Dockerfile", "package.json", "skills/"],
}

# Supervision phases (parallel to [BUILD] sprint — read-only observation)
_AC_SUPERVISION_PHASES = [
    "specs-review",
    "quality-gates",
    "strategic-review",
]
_AC_SUPERVISION_AGENTS = {
    "specs-review": ["ac-architect"],
    "quality-gates": ["ac-adversarial", "ac-qa-agent"],
    "strategic-review": ["ac-coach"],
}
# All supervision agent IDs (flat set for quick lookup)
_AC_SUPERVISOR_IDS = {"ac-architect", "ac-adversarial", "ac-qa-agent", "ac-coach"}
# Build phases (normal feature-sprint — done by Feature Teams)
_AC_BUILD_PHASES = [
    "feature-design",
    "env-setup",
    "tdd-sprint",
    "adversarial-review",
    "e2e-tests",
    "deploy",
]


def _ac_detect_scope_violation(
    agent_id: str, last_tool: str, preview: str
) -> str | None:
    """AC agents are SUPERVISORS — any write operation is a scope violation."""
    if last_tool not in ("code_write", "file_write", "code_apply"):
        return None
    # ANY write from an AC agent is suspicious — they should only READ/OBSERVE
    if agent_id.startswith("ac-"):
        return f"⚠ {agent_id} used {last_tool} — AC agents are SUPERVISORS, should not write"
    forbidden = _AC_SCOPE_FORBIDDEN.get(agent_id, [])
    for pattern in forbidden:
        if pattern.lower() in preview.lower():
            return f"{agent_id} used {last_tool} on forbidden path '{pattern}'"
    return None


def cmd_ac_watch(args):
    """Watch AC dual sessions (BUILD + SUPERVISE) in real time.

    Dual architecture:
    - [BUILD]     Feature Team running feature-sprint (normal project build)
    - [SUPERVISE] AC agents running ac-supervision-cycle (read-only grading)
    Any AC supervisor writing files = scope violation.
    """
    import time

    b = get_backend(args)
    project_id = args.project_id
    interval = getattr(args, "interval", 10)

    cycle_num = None
    start_ts = None
    builder_session_id = None
    supervisor_session_id = None

    # Start cycle if requested
    if getattr(args, "start", False):
        print(out.bold(f"Starting AC cycle for {project_id}..."))
        result = b.ac_start(project_id)
        if "error" in result:
            out.error(result["error"])
            return
        cycle_num = result.get("cycle_num")
        builder_session_id = result.get("builder_session_id", "")
        supervisor_session_id = result.get("supervisor_session_id", "")
        if builder_session_id and supervisor_session_id:
            print(f"{out.green('✓')} cycle={cycle_num}  dual-track")
            print(f"  [BUILD]     {builder_session_id}")
            print(f"  [SUPERVISE] {supervisor_session_id}")
        else:
            session_id = result.get("session_id", "?")
            print(f"{out.green('✓')} cycle={cycle_num}  session={session_id}")
        from datetime import datetime, timezone, timedelta

        start_ts = (datetime.now(timezone.utc) - timedelta(minutes=1)).strftime(
            "%Y-%m-%d %H:%M"
        )
    else:
        state = b.ac_project(project_id)
        if "error" in state:
            out.error(state["error"])
            return
        cycle_num = state.get("current_cycle", 0)
        status = state.get("status", "idle")
        if status not in ("running",):
            print(out.yellow(f"Project {project_id} is not running (status={status})."))
            print(out.dim("Tip: use --start to launch a new cycle."))
            return
        print(f"{out.bold(project_id)}  cycle={cycle_num}  status={out.yellow(status)}")
        start_ts = "2000-01-01"
        # Try to find session IDs for current cycle from project state
        builder_session_id = state.get("builder_session_id", "")
        supervisor_session_id = state.get("supervisor_session_id", "")

    print(out.dim(f"Polling every {interval}s — Ctrl+C to stop\n"))

    seen_violations: set[str] = set()
    seen_activity_ts: set[str] = set()
    completed_build_phases: set[str] = set()
    completed_sup_phases: set[str] = set()
    active_build_phase: str | None = None
    active_sup_phase: str | None = None
    prev_cycle = cycle_num

    def _dual_phase_line() -> str:
        """Show both BUILD and SUPERVISE phase progress."""
        # Build track
        build_parts = []
        for ph in _AC_BUILD_PHASES:
            if ph in completed_build_phases:
                build_parts.append(out.green("✓"))
            elif ph == active_build_phase:
                build_parts.append(out.yellow("►"))
            else:
                build_parts.append(out.dim("○"))
        build_line = f"  [BUILD]     {''.join(build_parts)}  {active_build_phase or ''}"

        # Supervise track
        sup_parts = []
        for ph in _AC_SUPERVISION_PHASES:
            if ph in completed_sup_phases:
                sup_parts.append(out.green("✓"))
            elif ph == active_sup_phase:
                sup_parts.append(out.yellow("►"))
            else:
                sup_parts.append(out.dim("○"))
        sup_line = f"  [SUPERVISE] {''.join(sup_parts)}  {active_sup_phase or ''}"

        return f"{build_line}\n{sup_line}"

    def _detect_phase_from_agent(agent: str, label: str):
        """Detect which track/phase an activity belongs to."""
        nonlocal active_build_phase, active_sup_phase
        # AC supervision agents
        if agent in _AC_SUPERVISOR_IDS:
            for ph, agents in _AC_SUPERVISION_AGENTS.items():
                if agent in agents:
                    if active_sup_phase and active_sup_phase != ph:
                        completed_sup_phases.add(active_sup_phase)
                    active_sup_phase = ph
                    return "[SUPERVISE]"
        # Build agents — detect from known feature-sprint agent names
        build_agents = {
            "product",
            "ft-infra-lead",
            "dev",
            "qa",
            "devops",
            "release_train_engineer",
            "ac-codex",
            "ac-cicd-agent",
        }
        if agent in build_agents:
            # Try to detect phase from label keywords
            phase_map = {
                "feature-design": ["inception", "user stories", "persona"],
                "env-setup": ["docker", "environment", "setup"],
                "tdd-sprint": ["code_write", "test", "tdd", "src/"],
                "adversarial-review": ["adversarial", "review", "dimension"],
                "e2e-tests": ["e2e", "playwright", "screenshot", "lighthouse"],
                "deploy": ["deploy", "git_commit", "git_push"],
            }
            for ph, keywords in phase_map.items():
                if any(kw in label.lower() for kw in keywords):
                    if active_build_phase and active_build_phase != ph:
                        completed_build_phases.add(active_build_phase)
                    active_build_phase = ph
                    break
            return "[BUILD]"
        return ""

    net_errors = 0
    try:
        while True:
            try:
                state = b.ac_project(project_id)
                status = state.get("status", "idle")
                cur_cycle = state.get("current_cycle", cycle_num)
                # Refresh session IDs from state (set during ac_start)
                if not builder_session_id:
                    builder_session_id = state.get("builder_session_id") or ""
                if not supervisor_session_id:
                    supervisor_session_id = state.get("supervisor_session_id") or ""
                net_errors = 0

                try:
                    activity = b.cockpit_activity(limit=40)
                except Exception:
                    activity = []

                # Fallback: if cockpit activity is empty, build activity
                # from session checkpoints + messages (AC sessions don't
                # populate the cockpit activity log)
                if not activity and (builder_session_id or supervisor_session_id):
                    synth = []
                    for sid, track_label in [
                        (builder_session_id, "BUILD"),
                        (supervisor_session_id, "SUPERVISE"),
                    ]:
                        if not sid:
                            continue
                        try:
                            msgs = b.session_messages(sid)
                            for m in msgs:
                                synth.append(
                                    {
                                        "ts": m.get("timestamp", m.get("ts", "")),
                                        "agent": m.get(
                                            "from_agent", m.get("agent", "")
                                        ),
                                        "label": (m.get("content") or "")[:120],
                                        "project_id": project_id,
                                        "_track": track_label,
                                    }
                                )
                        except Exception:
                            pass
                        try:
                            chks = b.session_checkpoints(sid)
                            for ck in chks:
                                agent = ck.get("agent_id", "")
                                step = ck.get("step", 0)
                                tool = ck.get("last_tool", "")
                                synth.append(
                                    {
                                        "ts": ck.get("created_at", ck.get("ts", "")),
                                        "agent": agent,
                                        "label": f"step {step} → {tool}"
                                        if tool
                                        else f"step {step}",
                                        "project_id": project_id,
                                        "_track": track_label,
                                    }
                                )
                        except Exception:
                            pass
                    if synth:
                        activity = sorted(synth, key=lambda x: x.get("ts", ""))

                # Filter: only our project, only since start
                relevant = []
                for a in activity:
                    ts = a.get("ts", "")
                    if start_ts and ts and ts < start_ts:
                        continue
                    a_project = a.get("project_id", "")
                    agent = a.get("agent", "")
                    label = a.get("label", "")
                    if (
                        a_project == project_id
                        or project_id in label
                        or agent in _AC_SUPERVISOR_IDS
                    ):
                        relevant.append(a)

                # Detect phases from activity
                for a in reversed(relevant):
                    agent = a.get("agent", "")
                    label = a.get("label", "")
                    _detect_phase_from_agent(agent, label)

                # Header
                status_fn = (
                    out.green
                    if status in ("idle", "completed")
                    else out.yellow
                    if status == "running"
                    else out.red
                )
                print(f"{out.bold(project_id)}  cy={cur_cycle}  {status_fn(status)}")
                print(_dual_phase_line())

                # New activity entries (dedup by agent+content hash)
                new_entries = []
                for a in relevant:
                    ts = a.get("ts", "")
                    agent = a.get("agent", "")
                    label = a.get("label", "")
                    dedup_key = f"{ts}|{agent}|{label[:60]}"
                    if dedup_key in seen_activity_ts:
                        continue
                    seen_activity_ts.add(dedup_key)
                    new_entries.append(a)

                for a in new_entries:
                    ts = a.get("ts", "")[11:19] or "        "
                    agent = a.get("agent", "")[:25]
                    # Clean label: strip markdown, compress whitespace
                    raw_label = a.get("label", "")
                    clean = (
                        raw_label.replace("#", "").replace("*", "").replace("\n", " ")
                    )
                    clean = " ".join(clean.split())[:100]

                    # Tag with track (prefer _track from synth, else infer)
                    synth_track = a.get("_track", "")
                    track = ""
                    if synth_track == "SUPERVISE" or agent in _AC_SUPERVISOR_IDS:
                        track = out.cyan("[SUP]")
                        agent_str = out.yellow(f"{agent:<22}")
                    elif synth_track == "BUILD" or agent in (
                        "product",
                        "dev",
                        "qa",
                        "devops",
                        "ft-infra-lead",
                        "ac-codex",
                        "ac-cicd-agent",
                    ):
                        track = out.dim("[BLD]")
                        agent_str = f"{agent:<22}"
                    elif agent == "release_train_engineer":
                        track = out.dim("[RTE]")
                        agent_str = out.dim(f"{agent:<22}")
                    else:
                        agent_str = f"{agent:<22}"

                    print(f"    {out.dim(ts)} {track} {agent_str}  {clean}")

                    # Scope violation check
                    for tool_kw in ("code_write", "file_write", "code_apply"):
                        if tool_kw in raw_label:
                            violation = _ac_detect_scope_violation(
                                agent, tool_kw, raw_label
                            )
                            if violation and violation not in seen_violations:
                                seen_violations.add(violation)
                                print(
                                    f"    {out.red('⚠  SCOPE VIOLATION:')} {violation}"
                                )

                # Done?
                if (
                    status in ("idle", "completed")
                    and cur_cycle
                    and cur_cycle > (prev_cycle or 0)
                ):
                    if active_build_phase:
                        completed_build_phases.add(active_build_phase)
                    if active_sup_phase:
                        completed_sup_phases.add(active_sup_phase)

                    print(f"\n{out.green('═' * 60)}")
                    print(
                        f"{out.bold('Cycle complete!')}  cy={cur_cycle}  {out.green(status)}"
                    )
                    score = state.get("total_score_avg", 0)
                    convergence = (state.get("convergence") or {}).get("status", "?")
                    print(f"  avg_score={score:.1f}  convergence={convergence}")
                    hint = state.get("next_cycle_hint")
                    if hint:
                        action = (
                            hint.get("action", hint) if isinstance(hint, dict) else hint
                        )
                        print(f"  RL hint: {out.yellow(str(action))}")
                    recent = state.get("recent_scores", [])
                    if recent:
                        print(f"  scores: {' → '.join(str(s) for s in recent)}")
                    print(
                        f"\n  [BUILD]     phases: {', '.join(sorted(completed_build_phases)) or 'n/a'}"
                    )
                    print(
                        f"  [SUPERVISE] phases: {', '.join(sorted(completed_sup_phases)) or 'n/a'}"
                    )
                    print(f"  Activity events: {len(seen_activity_ts)}")
                    print(
                        f"\n  Screenshot: sf ac screenshot {project_id} --cycle {cur_cycle}"
                    )
                    if seen_violations:
                        print(
                            f"\n  {out.red(f'⚠  {len(seen_violations)} scope violation(s):')}"
                        )
                        for v in seen_violations:
                            print(f"    - {v}")
                    else:
                        print(f"\n  {out.green('✓ No scope violations detected')}")
                    print(out.green("═" * 60))
                    break

                if status in ("idle",) and not getattr(args, "start", False):
                    break

                print()
                time.sleep(interval)

            except KeyboardInterrupt:
                raise
            except Exception as e:
                net_errors += 1
                if net_errors >= 5:
                    print(f"\n{out.red('Too many consecutive errors, stopping.')}")
                    break
                print(f"  {out.dim(f'[retry {net_errors}/5] {type(e).__name__}: {e}')}")
                time.sleep(interval)

    except KeyboardInterrupt:
        print(f"\n\n{out.dim('Stopped. Run again to resume watching.')}")
        if completed_build_phases or completed_sup_phases:
            print(f"  [BUILD]     {', '.join(sorted(completed_build_phases))}")
            print(f"  [SUPERVISE] {', '.join(sorted(completed_sup_phases))}")
        if seen_violations:
            print(
                out.red(
                    f"⚠  {len(seen_violations)} scope violation(s) detected so far."
                )
            )


def cmd_ac_screenshot(args):
    """Download and open the QA screenshot for a cycle."""
    import os
    import platform as _platform

    b = get_backend(args)
    project_id = args.project_id

    # Determine cycle number
    cycle_num = getattr(args, "cycle", None)
    if not cycle_num:
        state = b.ac_project(project_id)
        cycle_num = state.get("current_cycle", 1)

    print(f"Downloading screenshot for {project_id} cy{cycle_num}...")
    data = b.ac_screenshot_download(project_id, cycle_num)
    if not data:
        out.error(f"No screenshot found for {project_id} cycle {cycle_num}")
        return

    out_path = f"/tmp/ac-screenshot-{project_id}-cy{cycle_num}.png"
    with open(out_path, "wb") as f:
        f.write(data)

    print(f"{out.green('✓')} Saved: {out_path}  ({len(data) // 1024}KB)")

    # Open on macOS
    if _platform.system() == "Darwin":
        os.system(f"open '{out_path}'")
    else:
        print(out.dim(f"Open manually: {out_path}"))


# ── Bench commands ─────────────────────────────────────────────────────────────


def cmd_bench_list(args):
    b = get_backend(args)
    is_team = getattr(args, "teams", False)
    data = b.team_bench_list() if is_team else b.agent_bench_list()
    if getattr(args, "json_output", False):
        out.out_json(data)
        return
    rows = data if isinstance(data, list) else data.get("results", [])
    if not rows:
        out.info("No bench results found.")
        return
    headers = ["id", "pass_rate", "overall", "cases", "ran_at"]
    table = []
    for r in rows:
        rate = r.get("pass_rate", r.get("overall", "?"))
        color = out.green if isinstance(rate, float) and rate >= 0.6 else out.red
        table.append(
            [
                r.get("agent_id", r.get("team_id", r.get("id", "?"))),
                color(f"{rate:.2f}") if isinstance(rate, float) else str(rate),
                f"{r.get('overall', '?'):.2f}"
                if isinstance(r.get("overall"), float)
                else "?",
                str(r.get("cases_total", r.get("cases", "?"))),
                str(r.get("ran_at", r.get("created_at", "?")))[:19],
            ]
        )
    out.table(headers, table)


def cmd_bench_run(args):
    b = get_backend(args)
    is_team = getattr(args, "team", False)
    if is_team:
        result = b.team_bench_run(args.id)
    else:
        result = b.agent_bench_run(args.id, trials=getattr(args, "trials", 1))
    if "error" in result:
        out.error(result["error"])
        return
    job_id = result.get("job_id", "")
    if not job_id:
        output(args, result)
        return
    out.info(f"Bench job {job_id} started — polling...")
    import time

    while True:
        job = b.team_bench_job(job_id) if is_team else b.agent_bench_job(job_id)
        status = job.get("status", "?")
        if status in ("done", "error", "completed"):
            break
        print(f"  [{status}] …", end="\r")
        time.sleep(8)
    print()
    if getattr(args, "json_output", False):
        out.out_json(job)
        return
    _print_bench_job(job)


def cmd_bench_show(args):
    b = get_backend(args)
    is_team = getattr(args, "team", False)
    data = b.team_bench_show(args.id) if is_team else b.agent_bench_show(args.id)
    if getattr(args, "json_output", False):
        out.out_json(data)
        return
    _print_bench_job(data)


def cmd_bench_status(args):
    b = get_backend(args)
    is_team = getattr(args, "team", False)
    data = b.team_bench_job(args.job_id) if is_team else b.agent_bench_job(args.job_id)
    if getattr(args, "json_output", False):
        out.out_json(data)
        return
    _print_bench_job(data)


def _print_bench_job(data: dict):
    """Pretty-print a bench job/result dict."""
    if not data:
        out.info("(no data)")
        return
    status = data.get("status", "?")
    agent_id = data.get("agent_id", data.get("team_id", "?"))
    overall = data.get("overall", data.get("pass_rate", None))
    color = out.green if isinstance(overall, float) and overall >= 0.6 else out.red
    print(f"Bench: {out.bold(agent_id)}  status={status}", end="")
    if isinstance(overall, float):
        print(f"  overall={color(f'{overall:.2f}')}")
    else:
        print()
    cases = data.get("cases", data.get("case_results", []))
    if cases:
        headers = ["case", "checks", "judge", "overall", "error"]
        rows = []
        for c in cases:
            cr = c.get("check_pass_rate", "?")
            jr = c.get("judge_score", "?")
            ov = c.get("overall", "?")
            err = (c.get("error", "") or "")[:40]
            ov_color = out.green if isinstance(ov, float) and ov >= 0.6 else out.red
            rows.append(
                [
                    c.get("case_id", "?"),
                    f"{cr:.2f}" if isinstance(cr, float) else str(cr),
                    f"{jr:.2f}" if isinstance(jr, float) else str(jr),
                    ov_color(f"{ov:.2f}") if isinstance(ov, float) else str(ov),
                    err,
                ]
            )
        out.table(headers, rows)
    notes = data.get("judge_notes", data.get("notes", ""))
    if notes:
        print(f"Notes: {notes[:200]}")


# ── Skill commands ─────────────────────────────────────────────────────────────


def cmd_skill_list(args):
    b = get_backend(args)
    data = b.skill_eval_list()
    if getattr(args, "json_output", False):
        out.out_json(data)
        return
    rows = data if isinstance(data, list) else data.get("skills", [])
    if not rows:
        out.info("No skill evals found.")
        return
    headers = ["skill", "pass", "trials", "ran_at"]
    table = []
    for r in rows:
        rate = r.get("pass_rate", r.get("overall", "?"))
        color = out.green if isinstance(rate, float) and rate >= 0.6 else out.red
        table.append(
            [
                r.get("skill", r.get("name", "?")),
                color(f"{rate:.2f}") if isinstance(rate, float) else str(rate),
                str(r.get("trials", "?")),
                str(r.get("ran_at", "?"))[:19],
            ]
        )
    out.table(headers, table)


def cmd_skill_eval(args):
    b = get_backend(args)
    import time

    if getattr(args, "all", False):
        data = b.skill_eval_list()
        rows = data if isinstance(data, list) else data.get("skills", [])
        skills = [
            r.get("skill", r.get("name"))
            for r in rows
            if r.get("skill") or r.get("name")
        ]
    else:
        skills = [args.skill]
    for skill in skills:
        if not skill:
            continue
        out.info(f"Evaluating skill: {skill}")
        result = b.skill_eval_run(skill, trials=getattr(args, "trials", 3))
        if "error" in result:
            out.error(result["error"])
            continue
        job_id = result.get("job_id", "")
        if not job_id:
            output(args, result)
            continue
        while True:
            job = b.skill_eval_job(job_id)
            status = job.get("status", "?")
            if status in ("done", "error", "completed"):
                break
            print(f"  [{skill}] {status} …", end="\r")
            time.sleep(5)
        print()
        overall = job.get("overall", job.get("pass_rate", "?"))
        color = out.green if isinstance(overall, float) and overall >= 0.6 else out.red
        print(
            f"  {skill}: {color(f'{overall:.2f}') if isinstance(overall, float) else overall}"
        )
        if getattr(args, "all", False):
            time.sleep(5)


def cmd_skill_show(args):
    b = get_backend(args)
    data = b.skill_eval_show(args.skill)
    if getattr(args, "json_output", False):
        out.out_json(data)
        return
    _print_bench_job(data)


def cmd_simplify(args):
    """Analyze code changes with 3 parallel agents (reuse, quality, efficiency)."""
    # ── Get the diff ──
    if getattr(args, "staged", False):
        diff_cmd = ["git", "diff", "--staged"]
        diff_label = "staged changes"
    elif getattr(args, "last", False):
        diff_cmd = ["git", "diff", "HEAD~1", "HEAD"]
        diff_label = "last commit"
    else:
        diff_cmd = ["git", "diff", "HEAD"]
        diff_label = "uncommitted changes"

    result = subprocess.run(diff_cmd, capture_output=True, text=True)
    diff = result.stdout.strip()

    if not diff:
        out.info(f"No {diff_label} to analyze.")
        return

    lines = diff.count("\n")
    out.info(f"Analyzing {diff_label} ({lines} lines) with 3 parallel agents…")

    # ── Focus filter ──
    focus = [a for a in _SIMPLIFY_AXES if getattr(args, f"focus_{a}", False)] or list(
        _SIMPLIFY_AXES
    )

    project = getattr(args, "project", "") or ""

    # ── Call platform ──
    import httpx

    url = args.url.rstrip("/")
    try:
        with httpx.Client(timeout=60) as client:
            resp = client.post(
                f"{url}/api/simplify",
                json={"diff": diff, "project": project, "focus": focus},
                headers=_auth_headers(args),
            )
        resp.raise_for_status()
        data = resp.json()
    except httpx.ConnectError:
        out.error(
            "Platform not reachable. Start with: cd _SOFTWARE_FACTORY && python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8090 --ws none"
        )
        return
    except Exception as e:
        out.error(f"simplify request failed: {e}")
        return

    findings = data.get("findings", [])
    stats = data.get("stats", {})

    if getattr(args, "json_output", False):
        out.out_json(data)
        return

    if not findings:
        out.success("✅ Nothing to simplify — code looks clean!")
        return

    # ── Display ──
    _AXIS_COLORS = {
        "reuse": "\033[36m",  # cyan
        "quality": "\033[33m",  # yellow
        "efficiency": "\033[35m",  # magenta
    }
    _SEV_COLORS = {"high": "\033[31m", "medium": "\033[33m", "low": "\033[90m"}
    RESET = "\033[0m"

    current_file = None
    for f in findings:
        fname = f.get("file", "?")
        if fname != current_file:
            current_file = fname
            print(f"\n\033[1m{fname}\033[0m")

        axis = f.get("axis", "?")
        sev = f.get("severity", "low")
        cat = f.get("category", "?")
        line = f.get("line", 0)
        msg = f.get("message", "")
        suggestion = f.get("suggestion", "")

        axis_col = _AXIS_COLORS.get(axis, "")
        sev_col = _SEV_COLORS.get(sev, "")

        line_str = f":{line}" if line else ""
        print(
            f"  {sev_col}[{sev}]{RESET} {axis_col}[{axis}/{cat}]{RESET}{line_str}  {msg}"
        )
        if suggestion:
            print(f"    \033[90m→ {suggestion}{RESET}")

    # ── Summary ──
    print()
    total = stats.get("total", len(findings))
    by_sev = stats.get("by_severity", {})
    by_axis = stats.get("by_axis", {})
    out.info(
        f"Found {total} suggestion(s): "
        f"{by_sev.get('high', 0)} high, {by_sev.get('medium', 0)} medium, {by_sev.get('low', 0)} low"
    )
    for ax, count in by_axis.items():
        col = _AXIS_COLORS.get(ax, "")
        print(f"  {col}● {ax}{RESET}: {count}")

    if getattr(args, "apply", False):
        out.warn(
            "--apply mode: not yet implemented. Review suggestions and apply manually."
        )


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
    p.add_argument(
        "--db-path", dest="db_path", help="PostgreSQL URL (or DATABASE_URL env var)"
    )
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
    miss = sub.add_parser("epics", help="Mission management")
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

    # ── jarvis ──
    jar = sub.add_parser(
        "jarvis", help="Chat with Jarvis (CTO agent) — stored in Jarvis history"
    )
    jar_sub = jar.add_subparsers(dest="subcmd")

    jar_msg = jar_sub.add_parser("ask", help="Ask Jarvis a question")
    jar_msg.add_argument("message", nargs="+")
    jar_msg.add_argument(
        "--session",
        "-s",
        dest="session_id",
        default="",
        help="Reuse existing session ID",
    )
    jar_msg.set_defaults(func=cmd_jarvis)

    jar_list = jar_sub.add_parser("sessions", help="List Jarvis chat sessions")
    jar_list.set_defaults(func=cmd_jarvis_list)

    # ── jarvis shortcut: sf jarvis "message" ──
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

    # ── ac (Amélioration Continue — SUPERVISION, not execution) ──
    ac = sub.add_parser(
        "ac",
        help="AC supervision of pilot projects (observe, analyze, fix SF issues only)",
    )
    ac_sub = ac.add_subparsers(dest="subcmd")

    ac_list_p = ac_sub.add_parser("list", help="List all 8 AC pilot projects")
    ac_list_p.set_defaults(func=cmd_ac_list)

    ac_status_p = ac_sub.add_parser("status", help="Detailed status of a pilot project")
    ac_status_p.add_argument("project_id", help="Project ID (e.g. ac-hello-html)")
    ac_status_p.set_defaults(func=cmd_ac_status)

    ac_start_p = ac_sub.add_parser("start", help="Start AC cycle(s)")
    ac_start_g = ac_start_p.add_mutually_exclusive_group(required=True)
    ac_start_g.add_argument("project_id", nargs="?", help="Single project ID")
    ac_start_g.add_argument("--all", action="store_true", help="Start all 8 projects")
    ac_start_p.set_defaults(func=cmd_ac_start)

    ac_stop_p = ac_sub.add_parser("stop", help="Stop a running AC cycle")
    ac_stop_p.add_argument("project_id", help="Project ID")
    ac_stop_p.set_defaults(func=cmd_ac_stop)

    ac_rb_p = ac_sub.add_parser("rollback", help="Rollback last AC cycle")
    ac_rb_p.add_argument("project_id", help="Project ID")
    ac_rb_p.set_defaults(func=cmd_ac_rollback)

    ac_cy_p = ac_sub.add_parser("cycles", help="Cycle score history for a project")
    ac_cy_p.add_argument("project_id", help="Project ID")
    ac_cy_p.set_defaults(func=cmd_ac_cycles)

    ac_watch_p = ac_sub.add_parser(
        "watch",
        help="Watch AC supervision in real time (agents observe sprint, detect SF issues)",
    )
    ac_watch_p.add_argument("project_id", help="Project ID (e.g. ac-hello-html)")
    ac_watch_p.add_argument(
        "--start", action="store_true", help="Start a new cycle before watching"
    )
    ac_watch_p.add_argument(
        "--interval", type=int, default=5, help="Poll interval in seconds (default 5)"
    )
    ac_watch_p.set_defaults(func=cmd_ac_watch)

    ac_ss_p = ac_sub.add_parser("screenshot", help="Download QA screenshot for a cycle")
    ac_ss_p.add_argument("project_id", help="Project ID")
    ac_ss_p.add_argument(
        "--cycle", type=int, default=None, help="Cycle number (default: latest)"
    )
    ac_ss_p.set_defaults(func=cmd_ac_screenshot)

    # ── simplify ──
    simp = sub.add_parser(
        "simplify",
        help="Analyze code changes with 3 parallel agents (reuse, quality, efficiency)",
    )
    simp.add_argument("--staged", action="store_true", help="Analyze staged diff only")
    simp.add_argument("--last", action="store_true", help="Analyze last commit diff")
    simp.add_argument(
        "--apply", action="store_true", help="Apply suggestions (experimental)"
    )
    simp.add_argument("--project", default="", help="Project context")
    for _ax in _SIMPLIFY_AXES:
        simp.add_argument(
            f"--{_ax}",
            dest=f"focus_{_ax}",
            action="store_true",
            help=f"Focus on {_ax} axis only",
        )
    simp.set_defaults(func=cmd_simplify)

    # ── bench ──
    bnch = sub.add_parser("bench", help="Agent & team benchmarks (AC evals)")
    bnch_sub = bnch.add_subparsers(dest="subcmd")

    bl = bnch_sub.add_parser("list", help="List latest bench results")
    bl.add_argument(
        "--teams",
        action="store_true",
        help="Show team benches instead of agent benches",
    )
    bl.set_defaults(func=cmd_bench_list)

    br = bnch_sub.add_parser("run", help="Run a bench (polls until done)")
    br.add_argument("id", help="Agent ID (or team ID with --team)")
    br.add_argument("--team", action="store_true", help="Run a team bench")
    br.add_argument("--trials", type=int, default=1, help="Number of trials per case")
    br.set_defaults(func=cmd_bench_run)

    bsh = bnch_sub.add_parser("show", help="Show last bench result for an agent/team")
    bsh.add_argument("id", help="Agent ID (or team ID with --team)")
    bsh.add_argument("--team", action="store_true")
    bsh.set_defaults(func=cmd_bench_show)

    bst = bnch_sub.add_parser("status", help="Poll a bench job by ID")
    bst.add_argument("job_id")
    bst.add_argument("--team", action="store_true")
    bst.set_defaults(func=cmd_bench_status)

    # ── skill ──
    skl = sub.add_parser("skill", help="Skill evaluations")
    skl_sub = skl.add_subparsers(dest="subcmd")

    skl_sub.add_parser("list", help="List all skill eval results").set_defaults(
        func=cmd_skill_list
    )

    ske = skl_sub.add_parser("eval", help="Evaluate a skill (or all skills)")
    ske.add_argument(
        "skill", nargs="?", default="", help="Skill name (omit with --all)"
    )
    ske.add_argument(
        "--all", action="store_true", help="Evaluate all skills sequentially"
    )
    ske.add_argument("--trials", type=int, default=3, help="Trials per skill")
    ske.set_defaults(func=cmd_skill_eval)

    sksh = skl_sub.add_parser("show", help="Show last skill eval result")
    sksh.add_argument("skill")
    sksh.set_defaults(func=cmd_skill_show)

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

    # Handle jarvis shortcut: sf [options] jarvis "message..."
    try:
        idx = sys.argv.index("jarvis")
        if idx + 1 < len(sys.argv) and sys.argv[idx + 1] not in (
            "ask",
            "sessions",
            "--help",
            "-h",
        ):
            sys.argv.insert(idx + 1, "ask")
    except ValueError:
        pass

    # Handle ac shortcut: sf ac <project_id> → sf ac status <project_id>
    try:
        idx = sys.argv.index("ac")
        if idx + 1 < len(sys.argv) and sys.argv[idx + 1] not in (
            "list",
            "status",
            "start",
            "stop",
            "rollback",
            "cycles",
            "watch",
            "screenshot",
            "--help",
            "-h",
        ):
            sys.argv.insert(idx + 1, "status")
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
