"""Health, sandbox, watchdog & live monitoring endpoints."""

from __future__ import annotations

import json
import logging
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ...schemas import HealthResponse

router = APIRouter()
logger = logging.getLogger(__name__)

# Prime psutil cpu_percent so interval=0 returns meaningful values
try:
    import os as _os

    import psutil as _ps

    _ps.Process(_os.getpid()).cpu_percent()
    _ps.cpu_percent()
except Exception:
    pass


def import_time():
    """Get current time as epoch."""
    import time

    return time.time()


@router.get("/api/health", responses={200: {"model": HealthResponse}})
async def health_check():
    """Liveness/readiness probe for Docker healthcheck."""
    from ....db.migrations import get_db

    try:
        db = get_db()
        db.execute("SELECT 1")
        return JSONResponse({"status": "ok"})
    except Exception as e:
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=503)


@router.get("/api/sandbox/status")
async def sandbox_status():
    """Docker sandbox status."""
    import shutil

    from ....tools.sandbox import (
        SANDBOX_ENABLED,
        SANDBOX_IMAGE,
        SANDBOX_MEMORY,
        SANDBOX_NETWORK,
    )

    docker_available = shutil.which("docker") is not None
    return JSONResponse(
        {
            "enabled": SANDBOX_ENABLED,
            "docker_available": docker_available,
            "default_image": SANDBOX_IMAGE,
            "network": SANDBOX_NETWORK,
            "memory_limit": SANDBOX_MEMORY,
        }
    )


@router.get("/api/watchdog/metrics")
async def watchdog_metrics():
    """Get endurance watchdog metrics."""
    from ....ops.endurance_watchdog import _ensure_table, get_metrics

    try:
        _ensure_table()
    except Exception:
        pass
    return JSONResponse(get_metrics(limit=100))


@router.get("/api/monitoring/live")
async def monitoring_live(request: Request, hours: int = 24):
    """Live monitoring data: system, LLM, agents, missions, memory.
    Cached for 5 seconds to avoid hammering DB on rapid polling."""
    import os
    import time as _time

    import psutil

    hours = max(1, min(hours, 8760))

    # ── TTL cache (5s) ──
    cache = getattr(monitoring_live, "_cache", None)
    now = _time.monotonic()
    if cache and cache.get("hours") == hours and now - cache.get("ts", 0) < 5:
        return JSONResponse(cache["data"])

    # System metrics — primed at module load, interval=0 measures since last call
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    cpu_percent = process.cpu_percent(interval=0)
    sys_cpu = psutil.cpu_percent(interval=0)
    sys_mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    system = {
        "cpu_percent": round(cpu_percent, 1),
        "mem_rss_mb": round(mem_info.rss / 1024 / 1024, 1),
        "sys_cpu_percent": round(sys_cpu, 1),
        "sys_mem_percent": round(sys_mem.percent, 1),
        "disk_percent": round(disk.percent, 1),
        "uptime_seconds": round(import_time() - process.create_time()),
        "threads": process.num_threads(),
    }

    # LLM stats
    try:
        from ....llm.observability import get_tracer

        llm = get_tracer().stats(hours=hours)
        # Hourly breakdown for chart
        from ....db.migrations import get_db

        db = get_db()
        # Use day grouping for periods > 48h, else hourly
        if hours > 48:
            hourly = db.execute(f"""
                SELECT strftime('%m-%d', created_at) as hour,
                       COUNT(*) as calls,
                       COALESCE(SUM(tokens_in + tokens_out), 0) as tokens,
                       COALESCE(SUM(cost_usd), 0) as cost
                FROM llm_traces
                WHERE created_at > datetime('now', '-{hours} hours')
                GROUP BY hour ORDER BY hour
            """).fetchall()
        else:
            hourly = db.execute(f"""
                SELECT strftime('%H', created_at) as hour,
                       COUNT(*) as calls,
                       COALESCE(SUM(tokens_in + tokens_out), 0) as tokens,
                       COALESCE(SUM(cost_usd), 0) as cost
                FROM llm_traces
                WHERE created_at > datetime('now', '-{hours} hours')
                GROUP BY hour ORDER BY hour
            """).fetchall()
        llm["hourly"] = [dict(r) for r in hourly]
        db.close()
    except Exception:
        llm = {
            "total_calls": 0,
            "total_tokens_in": 0,
            "total_tokens_out": 0,
            "total_cost_usd": 0,
            "avg_duration_ms": 0,
            "error_count": 0,
            "by_provider": [],
            "by_agent": [],
            "hourly": [],
        }

    # Active agents (runtime from AgentLoopManager + historical from DB — single connection)
    agents_runtime = {"active": 0, "loops": 0}
    agents_historical = {
        "total_registered": 0,
        "participated": 0,
        "sessions_with_agents": 0,
    }
    missions = []
    sessions = []
    sprints = []
    features = []
    msg_count = {"cnt": 0}
    msg_total = {"cnt": 0}
    try:
        from ....agents.loop import get_loop_manager

        mgr = get_loop_manager()
        active_loops = {
            k: {"status": v.status, "agent_id": v.agent_id}
            for k, v in mgr._loops.items()
            if v.status in ("thinking", "acting")
        }
        agents_runtime = {"active": len(active_loops), "loops": len(mgr._loops)}
    except Exception:
        active_loops = {}
    try:
        from ....db.migrations import get_db

        adb = get_db()
        agents_historical["total_registered"] = adb.execute(
            "SELECT COUNT(*) FROM agents"
        ).fetchone()[0]
        agents_historical["participated"] = adb.execute(
            "SELECT COUNT(DISTINCT from_agent) FROM messages WHERE from_agent IS NOT NULL AND from_agent != 'system'"
        ).fetchone()[0]
        agents_historical["sessions_with_agents"] = adb.execute(
            "SELECT COUNT(DISTINCT session_id) FROM messages WHERE from_agent IS NOT NULL AND from_agent != 'system'"
        ).fetchone()[0]
        agents_historical["total_messages"] = adb.execute(
            "SELECT COUNT(*) FROM messages WHERE from_agent IS NOT NULL AND from_agent != 'system'"
        ).fetchone()[0]
        top = adb.execute(
            "SELECT from_agent, COUNT(*) as cnt FROM messages WHERE from_agent IS NOT NULL AND from_agent != 'system' GROUP BY from_agent ORDER BY cnt DESC LIMIT 5"
        ).fetchall()
        agents_historical["top_agents"] = [
            {"agent": r[0], "messages": r[1]} for r in top
        ]
        # Reuse same connection for missions/sessions/sprints/features/messages
        missions = adb.execute(
            "SELECT status, COUNT(*) as cnt FROM missions GROUP BY status"
        ).fetchall()
        sessions = adb.execute(
            "SELECT status, COUNT(*) as cnt FROM sessions GROUP BY status"
        ).fetchall()
        sprints = adb.execute(
            "SELECT status, COUNT(*) as cnt FROM sprints GROUP BY status"
        ).fetchall()
        features = adb.execute(
            "SELECT status, COUNT(*) as cnt FROM features GROUP BY status"
        ).fetchall()
        msg_count = adb.execute(
            "SELECT COUNT(*) as cnt FROM messages WHERE timestamp > datetime('now', '-24 hours')"
        ).fetchone()
        msg_total = adb.execute("SELECT COUNT(*) as cnt FROM messages").fetchone()
        adb.close()
    except Exception:
        pass

    # Memory stats
    try:
        from ....memory.manager import get_memory_manager

        mem_stats = get_memory_manager().stats()
    except Exception:
        mem_stats = {}

    # Projects count
    try:
        from ....projects.manager import get_project_store

        projects = get_project_store().list_all()
        project_count = len(projects)
    except Exception:
        projects = []
        project_count = 0

    # SSE connections (from bus)
    try:
        from ....a2a.bus import get_bus

        bus = get_bus()
        sse_connections = len(getattr(bus, "_sse_listeners", []))
    except Exception:
        sse_connections = 0

    # ── Database stats (single pass — no N+1) ──
    db_stats = {}
    try:
        from ....db.migrations import get_db

        db = get_db()
        tables = [
            r[0]
            for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        ]
        # Single query for all table counts via UNION ALL
        if tables:
            union = " UNION ALL ".join(
                f"SELECT '{t}' as tbl, COUNT(*) as cnt FROM [{t}]" for t in tables
            )
            rows = db.execute(union).fetchall()
            table_counts = {r[0]: r[1] for r in rows}
            total_rows = sum(table_counts.values())
        else:
            table_counts = {}
            total_rows = 0
        # DB file size
        db_path = (
            str(db.execute("PRAGMA database_list").fetchone()[2])
            if db.execute("PRAGMA database_list").fetchone()
            else ""
        )
        db_size_mb = 0
        if db_path:
            import pathlib

            p = pathlib.Path(db_path)
            if p.exists():
                db_size_mb = round(p.stat().st_size / 1024 / 1024, 2)
                # Include WAL
                wal = p.with_suffix(".db-wal")
                if wal.exists():
                    db_size_mb += round(wal.stat().st_size / 1024 / 1024, 2)
        # Page stats
        page_size = db.execute("PRAGMA page_size").fetchone()[0]
        page_count = db.execute("PRAGMA page_count").fetchone()[0]
        freelist = db.execute("PRAGMA freelist_count").fetchone()[0]
        journal_mode = db.execute("PRAGMA journal_mode").fetchone()[0]
        db.close()
        db_stats = {
            "size_mb": db_size_mb,
            "tables": len(tables),
            "total_rows": total_rows,
            "top_tables": sorted(table_counts.items(), key=lambda x: -x[1])[:10],
            "page_size": page_size,
            "page_count": page_count,
            "freelist_pages": freelist,
            "journal_mode": journal_mode,
        }
    except Exception as e:
        db_stats = {"error": str(e)}

    # ── Vector store stats ──
    vector_stats = {}
    try:
        from ....db.migrations import get_db

        db = get_db()
        vr = db.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN embedding IS NOT NULL AND embedding != '' THEN 1 ELSE 0 END) as embedded,
                   COUNT(DISTINCT scope_id) as scopes
            FROM memory_vectors
        """).fetchone()
        vector_stats = {
            "total_vectors": vr["total"] if vr else 0,
            "with_embedding": vr["embedded"] if vr else 0,
            "scopes": vr["scopes"] if vr else 0,
            "dimension": 1536,
            "provider": os.environ.get("EMBEDDING_ENDPOINT", "azure-openai")[:60],
        }
        db.close()
    except Exception:
        vector_stats = {"total_vectors": 0, "with_embedding": 0, "scopes": 0}

    # ── MCP server status (unified SF server) ──
    mcp_status = {}
    try:
        import urllib.request

        try:
            r = urllib.request.urlopen("http://127.0.0.1:9501/health", timeout=2)
            mcp_sf = json.loads(r.read().decode())
            mcp_status["mcp_sf"] = {"status": "up", "port": 9501, **mcp_sf}
        except Exception:
            mcp_status["mcp_sf"] = {"status": "down", "port": 9501}

        # RLM Cache DB
        import pathlib

        rlm_cache = pathlib.Path(os.environ.get("DATA_DIR", "data")) / "rlm_cache.db"
        if not rlm_cache.exists():
            rlm_cache = (
                pathlib.Path(__file__).resolve().parents[4] / "data" / "rlm_cache.db"
            )
        if rlm_cache.exists():
            import sqlite3

            cdb = sqlite3.connect(str(rlm_cache))
            cdb.row_factory = sqlite3.Row
            try:
                cc = cdb.execute("SELECT COUNT(*) as cnt FROM rlm_cache").fetchone()
                # Anonymization stats from RLM cache
                anon_stats = {}
                try:
                    anon_rows = cdb.execute(
                        "SELECT COALESCE(scope, 'default') as scope, COUNT(*) as cnt "
                        "FROM rlm_cache GROUP BY scope"
                    ).fetchall()
                    anon_stats = {r["scope"]: r["cnt"] for r in anon_rows}
                except Exception:
                    pass
                mcp_status["rlm_cache"] = {
                    "status": "ok",
                    "entries": cc["cnt"] if cc else 0,
                    "size_mb": round(rlm_cache.stat().st_size / 1024 / 1024, 2),
                    "by_scope": anon_stats,
                }
            except Exception:
                mcp_status["rlm_cache"] = {"status": "empty", "entries": 0}
            cdb.close()
    except Exception as e:
        mcp_status["error"] = str(e)

    # ── Incidents stats ──
    incidents = {}
    try:
        from ....db.migrations import get_db

        db = get_db()
        inc_rows = db.execute("""
            SELECT severity, status, COUNT(*) as cnt
            FROM platform_incidents
            GROUP BY severity, status
        """).fetchall()
        open_count = sum(r["cnt"] for r in inc_rows if r["status"] == "open")
        total_count = sum(r["cnt"] for r in inc_rows)
        incidents = {
            "open": open_count,
            "total": total_count,
            "by_severity_status": [dict(r) for r in inc_rows],
        }
        db.close()
    except Exception:
        incidents = {"open": 0, "total": 0}

    # ── Live metrics from collector ──
    metrics_snapshot = {}
    try:
        from ....metrics.collector import get_collector

        metrics_snapshot = get_collector().snapshot()
    except Exception:
        pass

    # ── Docker containers (via Docker socket API) — cached 5 min ──
    docker_info = []
    docker_system = {}
    _docker_cache = getattr(monitoring_live, "_docker_cache", None)
    if _docker_cache and now - _docker_cache.get("ts", 0) < 300:
        docker_info = _docker_cache["data"]["containers"]
        docker_system = _docker_cache["data"]["system"]
    else:
      try:
        import pathlib

        sock_path = "/var/run/docker.sock"
        if pathlib.Path(sock_path).exists():
            import http.client
            import urllib.parse

            class DockerSocket(http.client.HTTPConnection):
                def __init__(self):
                    super().__init__("localhost")

                def connect(self):
                    import socket as _sock

                    self.sock = _sock.socket(_sock.AF_UNIX, _sock.SOCK_STREAM)
                    self.sock.connect(sock_path)
                    self.sock.settimeout(5)

            # --- Container list ---
            conn = DockerSocket()
            conn.request("GET", "/containers/json?all=true")
            resp = conn.getresponse()
            containers_raw = []
            if resp.status == 200:
                containers_raw = json.loads(resp.read().decode())
            conn.close()

            for c in containers_raw:
                cid = c.get("Id", "")[:12]
                name = (c.get("Names", ["/?"]) or ["/?"])[0].lstrip("/")
                state = c.get("State", "?")
                status = c.get("Status", "?")
                image = (c.get("Image", "?") or "?")[:40]
                ports_raw = c.get("Ports", [])
                ports_str = (
                    ", ".join(
                        f"{p.get('PublicPort', '')}→{p.get('PrivatePort', '')}"
                        for p in ports_raw
                        if p.get("PublicPort")
                    )
                    if ports_raw
                    else ""
                )
                restarts = (
                    c.get("RestartCount", 0)
                    if c.get("HostConfig", {}).get("RestartPolicy")
                    else 0
                )
                created = c.get("Created", 0)

                # Per-container stats (stream=false = single snapshot)
                cpu_pct = 0.0
                mem_mb = 0.0
                mem_limit_mb = 0.0
                net_rx_mb = 0.0
                net_tx_mb = 0.0
                pids = 0
                if state == "running":
                    try:
                        sc = DockerSocket()
                        sc.request("GET", f"/containers/{cid}/stats?stream=false")
                        sr = sc.getresponse()
                        if sr.status == 200:
                            st = json.loads(sr.read().decode())
                            # CPU %
                            cpu_delta = st.get("cpu_stats", {}).get(
                                "cpu_usage", {}
                            ).get("total_usage", 0) - st.get("precpu_stats", {}).get(
                                "cpu_usage", {}
                            ).get("total_usage", 0)
                            sys_delta = st.get("cpu_stats", {}).get(
                                "system_cpu_usage", 0
                            ) - st.get("precpu_stats", {}).get("system_cpu_usage", 0)
                            ncpus = st.get("cpu_stats", {}).get("online_cpus", 1) or 1
                            if sys_delta > 0 and cpu_delta > 0:
                                cpu_pct = round(
                                    (cpu_delta / sys_delta) * ncpus * 100, 1
                                )
                            # Memory
                            mem_usage = st.get("memory_stats", {}).get("usage", 0)
                            mem_cache = (
                                st.get("memory_stats", {})
                                .get("stats", {})
                                .get("cache", 0)
                            )
                            mem_mb = round((mem_usage - mem_cache) / 1048576, 1)
                            mem_limit_mb = round(
                                st.get("memory_stats", {}).get("limit", 0) / 1048576, 0
                            )
                            # Network I/O
                            nets = st.get("networks", {})
                            for iface in nets.values():
                                net_rx_mb += iface.get("rx_bytes", 0) / 1048576
                                net_tx_mb += iface.get("tx_bytes", 0) / 1048576
                            net_rx_mb = round(net_rx_mb, 1)
                            net_tx_mb = round(net_tx_mb, 1)
                            pids = st.get("pids_stats", {}).get("current", 0)
                        sc.close()
                    except Exception:
                        pass

                docker_info.append(
                    {
                        "name": name,
                        "id": cid,
                        "status": status,
                        "state": state,
                        "image": image,
                        "ports": ports_str,
                        "restarts": restarts,
                        "cpu_pct": cpu_pct,
                        "mem_mb": mem_mb,
                        "mem_limit_mb": mem_limit_mb,
                        "net_rx_mb": net_rx_mb,
                        "net_tx_mb": net_tx_mb,
                        "pids": pids,
                        "created": created,
                    }
                )

            # --- Docker system info (images, disk) ---
            try:
                conn2 = DockerSocket()
                conn2.request("GET", "/info")
                resp2 = conn2.getresponse()
                if resp2.status == 200:
                    info = json.loads(resp2.read().decode())
                    docker_system["containers_total"] = info.get("Containers", 0)
                    docker_system["containers_running"] = info.get(
                        "ContainersRunning", 0
                    )
                    docker_system["containers_stopped"] = info.get(
                        "ContainersStopped", 0
                    )
                    docker_system["images"] = info.get("Images", 0)
                    docker_system["server_version"] = info.get("ServerVersion", "?")
                    docker_system["os"] = info.get("OperatingSystem", "?")
                    docker_system["kernel"] = info.get("KernelVersion", "?")
                    docker_system["cpus"] = info.get("NCPU", 0)
                    docker_system["mem_total_gb"] = round(
                        info.get("MemTotal", 0) / 1073741824, 1
                    )
                conn2.close()
            except Exception:
                pass

            # --- Docker disk usage ---
            try:
                conn3 = DockerSocket()
                conn3.request("GET", "/system/df")
                resp3 = conn3.getresponse()
                if resp3.status == 200:
                    df = json.loads(resp3.read().decode())
                    # Images disk
                    img_size = sum(i.get("Size", 0) for i in df.get("Images", []))
                    img_shared = sum(
                        i.get("SharedSize", 0) for i in df.get("Images", [])
                    )
                    docker_system["images_size_gb"] = round(img_size / 1073741824, 2)
                    docker_system["images_shared_gb"] = round(
                        img_shared / 1073741824, 2
                    )
                    # Containers disk
                    ct_size = sum(c.get("SizeRw", 0) for c in df.get("Containers", []))
                    docker_system["containers_disk_mb"] = round(ct_size / 1048576, 1)
                    # Volumes
                    vols = df.get("Volumes", [])
                    docker_system["volumes_count"] = len(vols)
                    vol_size = sum(v.get("UsageData", {}).get("Size", 0) for v in vols)
                    docker_system["volumes_size_gb"] = round(vol_size / 1073741824, 2)
                    # Build cache
                    bc = df.get("BuildCache", [])
                    bc_size = sum(b.get("Size", 0) for b in bc)
                    docker_system["build_cache_gb"] = round(bc_size / 1073741824, 2)
                    docker_system["total_disk_gb"] = round(
                        (img_size + ct_size + vol_size + bc_size) / 1073741824, 2
                    )
                conn3.close()
            except Exception:
                pass
        monitoring_live._docker_cache = {"data": {"containers": docker_info, "system": docker_system}, "ts": now}
      except Exception:
        pass

    # Git info (all workspace repos) - cached 5 min
    git_info = []
    _git_cache = getattr(monitoring_live, "_git_cache", None)
    if _git_cache and now - _git_cache.get("ts", 0) < 300:
        git_info = _git_cache["data"]
    else:
        try:
            import pathlib
            import subprocess

            def _git_repo_info(repo_path: str, label: str) -> dict | None:
                p = pathlib.Path(repo_path)
                if not p.exists():
                    return None
                r = subprocess.run(
                    ["git", "log", "--oneline", "-5", "--no-decorate"],
                    capture_output=True, text=True, timeout=5, cwd=repo_path,
                )
                if r.returncode != 0 or not r.stdout.strip():
                    return None
                commits = [
                    {"hash": line[:7], "message": line[8:]}
                    for line in r.stdout.strip().split("\n") if line
                ]
                branch = ""
                r2 = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    capture_output=True, text=True, timeout=5, cwd=repo_path,
                )
                if r2.returncode == 0:
                    branch = r2.stdout.strip()
                last_time = ""
                r3 = subprocess.run(
                    ["git", "log", "-1", "--format=%ci"],
                    capture_output=True, text=True, timeout=5, cwd=repo_path,
                )
                if r3.returncode == 0:
                    last_time = r3.stdout.strip()
                return {
                    "label": label,
                    "path": repo_path,
                    "branch": branch,
                    "last_commit_time": last_time,
                    "recent_commits": commits,
                }

            # Platform repo candidates
            for candidate, lbl in [("/app", "platform"), ("/opt/macaron", "platform"), (os.getcwd(), "platform")]:
                info = _git_repo_info(candidate, lbl)
                if info:
                    git_info.append(info)
                    break

            # All project workspaces
            try:
                from ....projects.manager import get_project_store
                for proj in get_project_store().list_all():
                    if not proj.path or proj.path in ("/app", "/opt/macaron", os.getcwd()):
                        continue
                    ppath = pathlib.Path(proj.path)
                    if not ppath.exists():
                        continue
                    # Check has_git
                    has = (ppath / ".git").exists()
                    if not has:
                        r_chk = subprocess.run(
                            ["git", "rev-parse", "--git-dir"],
                            capture_output=True, text=True, timeout=3, cwd=proj.path,
                        )
                        has = r_chk.returncode == 0
                    if has:
                        info = _git_repo_info(proj.path, proj.name or proj.id)
                        if info:
                            git_info.append(info)
            except Exception:
                pass

            monitoring_live._git_cache = {"data": git_info, "ts": now}
        except Exception:
            pass

    # ── Mission phase durations (from mission_runs.phases_json) ──
    phase_stats = []
    try:
        from ....db.migrations import get_db

        db = get_db()
        runs = db.execute("""
            SELECT phases_json, status, current_phase
            FROM mission_runs WHERE phases_json IS NOT NULL
        """).fetchall()
        phase_counts = {}
        for run in runs:
            try:
                phases = json.loads(run["phases_json"]) if run["phases_json"] else []
                for p in phases:
                    key = p.get("phase_name") or p.get("name", "?")
                    st = p.get("status", "pending")
                    k = (key, st)
                    phase_counts[k] = phase_counts.get(k, 0) + 1
            except Exception:
                pass
        phase_stats = [
            {"phase_name": k[0], "status": k[1], "cnt": v}
            for k, v in sorted(phase_counts.items())
        ]
        db.close()
    except Exception:
        pass

    # ── Azure infrastructure ──
    azure_infra = {"vm": {}, "backup": {}, "costs": {}, "servers": []}
    try:
        azure_infra["vm"] = {
            "name": "vm-macaron",
            "ip": "4.233.64.30",
            "rg": "RG-MACARON",
            "region": "francecentral",
            "size": "Standard_B2ms",
            "os": "Ubuntu 24.04",
            "disk_gb": 64,
        }
        # Backup info from config
        azure_infra["backup"] = {
            "storage_account": "macaronbackups",
            "replication": "GRS (francesouth)",
            "containers": ["db-backups", "pg-dumps", "secrets"],
            "sqlite_dbs": 7,
            "retention": {"daily": "90d", "weekly": "365d", "monthly": "forever"},
        }
        # Servers running on VM (probe ports)
        import socket

        def _port_up(port, host="127.0.0.1"):
            try:
                with socket.create_connection((host, port), timeout=1):
                    return "up"
            except Exception:
                return "down"

        azure_infra["servers"] = [
            {"name": "Platform (uvicorn)", "port": 8090, "status": "up"},
            {
                "name": "MCP SF (unified)",
                "port": 9501,
                "status": "up"
                if mcp_status.get("mcp_sf", {}).get("status") in ("up", "ok")
                else "down",
            },
            {"name": "PostgreSQL", "port": 5432, "status": _port_up(5432)},
            {"name": "Nginx (reverse proxy)", "port": 80, "status": _port_up(80)},
        ]
        # LLM cost summary by provider type (Azure vs non-Azure)
        azure_cost = 0.0
        other_cost = 0.0
        for p in llm.get("by_provider", []):
            prov = p.get("provider", "")
            cost = p.get("cost_usd", 0)
            if "azure" in prov.lower():
                azure_cost += cost
            else:
                other_cost += cost
        azure_infra["costs"] = {
            "azure_llm_usd": round(azure_cost, 4),
            "other_llm_usd": round(other_cost, 4),
            "total_llm_usd": round(azure_cost + other_cost, 4),
            # Azure infra monthly estimates (Standard_B2ms + PG B1ms + storage)
            "vm_monthly_usd": 60.74,  # Standard_B2ms francecentral
            "disk_monthly_usd": 9.50,  # P6 Premium SSD 64GB
            "pg_monthly_usd": 12.34,  # PG B1ms 1vCPU/2GB
            "storage_monthly_usd": 2.50,  # Blob GRS ~50GB
            "total_infra_monthly_usd": 85.08,
        }
    except Exception:
        pass

    # Redact sensitive infrastructure details for unauthenticated requests
    is_authed = (
        getattr(request.state, "authenticated", False)
        if hasattr(request, "state")
        else False
    )
    if not is_authed and os.getenv("MACARON_API_KEY"):
        # Strip container IDs, kernel, server version, git branch, Azure details
        for d in docker_info:
            d.pop("id", None)
            d.pop("pids", None)
        docker_system.pop("kernel", None)
        docker_system.pop("server_version", None)
        docker_system.pop("os", None)
        git_info = []
        azure_infra = {}

    result = {
        "timestamp": datetime.utcnow().isoformat(),
        "hours": hours,
        "system": system,
        "llm": llm,
        "agents": {
            "active": agents_runtime["active"],
            "loops": agents_runtime["loops"],
            "registered": agents_historical.get("total_registered", 0),
            "participated": agents_historical.get("participated", 0),
            "sessions_with_agents": agents_historical.get("sessions_with_agents", 0),
            "total_messages": agents_historical.get("total_messages", 0),
            "top_agents": agents_historical.get("top_agents", []),
        },
        "missions": {s["status"]: s["cnt"] for s in missions},
        "sessions": {s["status"]: s["cnt"] for s in sessions},
        "sprints": {s["status"]: s["cnt"] for s in sprints},
        "features": {s["status"]: s["cnt"] for s in features},
        "messages": {
            "last_24h": msg_count["cnt"] if msg_count else 0,
            "total": msg_total["cnt"] if msg_total else 0,
        },
        "memory": mem_stats,
        "projects": project_count,
        "sse_connections": sse_connections,
        "database": db_stats,
        "vectors": vector_stats,
        "mcp": mcp_status,
        "incidents": incidents,
        "requests": metrics_snapshot.get("http", {}),
        "mcp_calls": metrics_snapshot.get("mcp", {}),
        "anonymization": metrics_snapshot.get("anonymization", {}),
        "llm_costs": metrics_snapshot.get("llm_costs", {}),
        "azure": azure_infra,
        "docker": docker_info,
        "docker_system": docker_system,
        "git": git_info,
        "phase_stats": phase_stats,
    }

    # Store in cache
    monitoring_live._cache = {"data": result, "hours": hours, "ts": _time.monotonic()}
    return JSONResponse(result)
