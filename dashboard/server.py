#!/usr/bin/env python3
"""
Software Factory Dashboard - Local Web Interface
================================================

A simple FastAPI dashboard to monitor the Software Factory.

Usage:
    python3 -m dashboard.server
    # or
    factory dashboard

Opens at http://localhost:8080
"""

import asyncio
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from fastapi import FastAPI, Query, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
PROJECTS_DIR = BASE_DIR / "projects"
PID_DIR = Path("/tmp/factory")

# Load .env if present (for AZURE_PLATFORM_URL, OVH_PLATFORM_URL, etc.)
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            if _k.strip() not in os.environ:
                os.environ[_k.strip()] = _v.strip().strip('"').strip("'")

# FastAPI app
app = FastAPI(title="Software Factory Dashboard", version="1.0.0")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# ============================================================================
# SIMPLE TTL CACHE (no external deps)
# ============================================================================

_cache: Dict[str, tuple] = {}  # key -> (value, expires_at)


def _cache_get(key: str):
    entry = _cache.get(key)
    if entry and time.monotonic() < entry[1]:
        return entry[0]
    return None


def _cache_set(key: str, value, ttl: float):
    _cache[key] = (value, time.monotonic() + ttl)


def cached(ttl: float):
    """Decorator: cache the return value for `ttl` seconds. Sync functions only."""

    def decorator(fn):
        def wrapper(*args):
            key = fn.__name__ + str(args)
            hit = _cache_get(key)
            if hit is not None:
                return hit
            result = fn(*args)
            _cache_set(key, result, ttl)
            return result

        wrapper.__name__ = fn.__name__
        return wrapper

    return decorator


# ============================================================================
# DATABASE HELPERS
# ============================================================================


def get_db(db_name: str = "factory.db") -> sqlite3.Connection:
    """Get database connection."""
    conn = sqlite3.connect(DATA_DIR / db_name)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================================
# DEPLOY STATUS (Azure Prod + OVH Demo)
# ============================================================================

_ENVS = [
    {
        "name": "Azure Prod",
        "key": "azure",
        "url": os.environ.get("AZURE_PLATFORM_URL", ""),
        "ssh_host": os.environ.get("AZURE_SSH_HOST", ""),
        "ssh_user": os.environ.get("AZURE_SSH_USER", "macaron"),
    },
    {
        "name": "OVH Demo",
        "key": "ovh",
        "url": os.environ.get("OVH_PLATFORM_URL", ""),
        "ssh_host": os.environ.get("OVH_SSH_HOST", ""),
        "ssh_user": os.environ.get("OVH_SSH_USER", "debian"),
    },
]


@cached(ttl=30)
def _get_deploy_status() -> List[Dict]:
    """Check health of each remote environment (non-blocking, 3s timeout)."""
    import urllib.request
    import urllib.error

    results = []
    local_sha = ""
    try:
        local_sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(BASE_DIR),
            text=True,
            timeout=3,
        ).strip()
    except Exception:
        pass

    for env in _ENVS:
        entry: Dict[str, Any] = {
            "name": env["name"],
            "key": env["key"],
            "url": env["url"],
            "status": "unknown",
            "version": "",
            "local_version": local_sha,
            "up_to_date": None,
            "ssh_ok": False,
        }
        if not env["url"]:
            entry["status"] = "not_configured"
            results.append(entry)
            continue
        # HTTP health check
        try:
            req = urllib.request.Request(
                env["url"].rstrip("/") + "/api/health",
                headers={"User-Agent": "SF-Dashboard/1.0"},
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    entry["status"] = "online"
                    try:
                        data = json.loads(resp.read().decode())
                        entry["version"] = data.get("version", "")
                        if local_sha and entry["version"]:
                            entry["up_to_date"] = entry["version"].startswith(local_sha)
                    except Exception:
                        pass
                else:
                    entry["status"] = "error"
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                entry["status"] = "online"  # Auth required = server is up
            else:
                entry["status"] = "error"
        except Exception:
            entry["status"] = "offline"
        # SSH check (quick)
        if env["ssh_host"]:
            try:
                result = subprocess.run(
                    [
                        "ssh",
                        "-o",
                        "ConnectTimeout=2",
                        "-o",
                        "BatchMode=yes",
                        f"{env['ssh_user']}@{env['ssh_host']}",
                        "echo ok",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=4,
                )
                entry["ssh_ok"] = result.returncode == 0
            except Exception:
                entry["ssh_ok"] = False
        results.append(entry)
    return results


@cached(ttl=15)
def get_project_stats(project_id: str) -> Dict[str, int]:
    """Get task statistics for a project."""
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT status, COUNT(*) as cnt
            FROM tasks
            WHERE project_id = ?
            GROUP BY status
        """,
            (project_id,),
        ).fetchall()

    stats = {row["status"]: row["cnt"] for row in rows}
    return {
        "deployed": stats.get("deployed", 0),
        "pending": stats.get("pending", 0),
        "in_progress": sum(
            stats.get(s, 0)
            for s in [
                "tdd_in_progress",
                "build_in_progress",
                "deploying_staging",
                "deploying_prod",
                "code_written",
                "locked",
            ]
        ),
        "failed": sum(
            stats.get(s, 0)
            for s in ["build_failed", "tdd_failed", "integration_failed"]
        ),
        "completed": stats.get("completed", 0),
        "decomposed": stats.get("decomposed", 0),
        "total": sum(stats.values()),
    }


@cached(ttl=10)
def get_global_stats() -> Dict[str, int]:
    """Get global statistics across all projects."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT status, COUNT(*) as cnt
            FROM tasks
            GROUP BY status
        """).fetchall()

    stats = {row["status"]: row["cnt"] for row in rows}
    deployed = stats.get("deployed", 0)
    completed = stats.get("completed", 0)
    total = sum(stats.values())

    return {
        "total": total,
        "deployed": deployed,
        "completed": completed,
        "pending": stats.get("pending", 0),
        "in_progress": sum(
            stats.get(s, 0)
            for s in [
                "tdd_in_progress",
                "build_in_progress",
                "deploying_staging",
                "deploying_prod",
                "code_written",
                "locked",
                "queued_for_deploy",
            ]
        ),
        "failed": sum(
            stats.get(s, 0)
            for s in ["build_failed", "tdd_failed", "integration_failed"]
        ),
        "success_pct": round((deployed + completed) / total * 100, 1)
        if total > 0
        else 0,
    }


# ============================================================================
# PROJECT HELPERS
# ============================================================================


@cached(ttl=60)
def load_project_config(project_id: str) -> Optional[Dict]:
    """Load project configuration from YAML."""
    yaml_path = PROJECTS_DIR / f"{project_id}.yaml"
    if not yaml_path.exists():
        return None

    with open(yaml_path) as f:
        return yaml.safe_load(f)


@cached(ttl=20)
def get_all_projects() -> List[Dict]:
    """Get all projects with their status."""
    projects = []

    for yaml_file in PROJECTS_DIR.glob("*.yaml"):
        if yaml_file.name.startswith("_"):
            continue

        project_id = yaml_file.stem
        config = load_project_config(project_id)
        if not config:
            continue

        project_config = config.get("project", {})
        stats = get_project_stats(project_id)
        daemon_status = get_daemon_status(project_id)

        # Get domains from config
        domains = list(config.get("domains", {}).keys())

        # Load arch_domain badge
        arch_domain_id = project_config.get("domain", "")
        arch_domain_label = ""
        arch_domain_color = "#6B7280"
        if arch_domain_id:
            try:
                import sys
                import os

                _sf_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                if _sf_root not in sys.path:
                    sys.path.insert(0, _sf_root)
                from platform.projects.domains import load_domain

                d = load_domain(arch_domain_id)
                if d:
                    arch_domain_label = d.name
                    arch_domain_color = d.color
            except Exception:
                arch_domain_label = arch_domain_id

        projects.append(
            {
                "id": project_id,
                "name": project_config.get("name", project_id),
                "display_name": project_config.get("display_name", project_id),
                "root_path": project_config.get("root_path", ""),
                "stats": stats,
                "daemons": daemon_status,
                "domains": domains,
                "running": daemon_status.get("cycle", {}).get("running", False),
                "workers": get_worker_count(project_id),
                "arch_domain": arch_domain_id,
                "arch_domain_label": arch_domain_label,
                "arch_domain_color": arch_domain_color,
            }
        )

    # Sort by running first, then by deployed count
    projects.sort(key=lambda p: (-p["running"], -p["stats"]["deployed"]))
    return projects


# ============================================================================
# DAEMON HELPERS
# ============================================================================


def check_pid_running(pid: int) -> bool:
    """Check if a PID is running."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


@cached(ttl=10)
def get_daemon_status(project_id: str) -> Dict[str, Dict]:
    """Get daemon status for a project."""
    daemons = {}

    # Get alternate project names (e.g., ppz -> popinz)
    project_names = [project_id]
    config = load_project_config(project_id)
    if config and config.get("project", {}).get("name"):
        alt_name = config["project"]["name"]
        if alt_name != project_id:
            project_names.append(alt_name)

    for daemon_type in ["cycle", "wiggum", "deploy", "build"]:
        found = False
        # Try each project name variant
        for pname in project_names:
            pid_file_map = {
                "cycle": f"cycle-{pname}.pid",
                "wiggum": f"wiggum-tdd-{pname}.pid",
                "deploy": f"wiggum-deploy-{pname}.pid",
                "build": f"build-{pname}.pid",
            }
            pid_file = PID_DIR / pid_file_map[daemon_type]

            if pid_file.exists():
                try:
                    pid = int(pid_file.read_text().strip())
                    running = check_pid_running(pid)
                    daemons[daemon_type] = {
                        "running": running,
                        "pid": pid if running else None,
                    }
                    found = True
                    break
                except (ValueError, FileNotFoundError):
                    pass

        if not found:
            daemons[daemon_type] = {"running": False, "pid": None}

    return daemons


@cached(ttl=20)
def get_worker_count(project_id: str) -> int:
    """Get number of active workers for a project."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", f"opencode.*{project_id}"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            return len(result.stdout.strip().split("\n"))
    except Exception:
        pass
    return 0


# ============================================================================
# METRICS HELPERS
# ============================================================================


@cached(ttl=30)
def get_metrics(project_id: str) -> Dict:
    """Get Team of Rivals metrics for a project."""
    metrics_db = DATA_DIR / "metrics.db"
    if not metrics_db.exists():
        return {"l0": {}, "l1_code": {}, "l1_security": {}, "l2_arch": {}, "final": {}}

    # Map project_id to potential names
    project_names = [project_id]
    config = load_project_config(project_id)
    if config and config.get("project", {}).get("name"):
        project_names.append(config["project"]["name"])

    with sqlite3.connect(metrics_db) as conn:
        conn.row_factory = sqlite3.Row

        metrics = {}
        for layer in ["l0", "l1_code", "l1_security", "l2_arch"]:
            placeholders = ",".join("?" * len(project_names))
            row = conn.execute(
                f"""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN result = 'rejected' THEN 1 ELSE 0 END) as rejected,
                    SUM(CASE WHEN result = 'approved' THEN 1 ELSE 0 END) as approved
                FROM critic_metrics
                WHERE project_id IN ({placeholders}) AND layer = ?
            """,
                (*project_names, layer),
            ).fetchone()

            total = row["total"] or 0
            rejected = row["rejected"] or 0
            metrics[layer] = {
                "total": total,
                "rejected": rejected,
                "approved": row["approved"] or 0,
                "catch_rate": round(rejected / total * 100, 1) if total > 0 else 0,
            }

        # Final approved
        placeholders = ",".join("?" * len(project_names))
        final = conn.execute(
            f"""
            SELECT COUNT(*) as cnt FROM critic_metrics
            WHERE project_id IN ({placeholders}) AND layer = 'final' AND result = 'approved'
        """,
            project_names,
        ).fetchone()

        total_started = metrics["l0"]["total"]
        final_approved = final["cnt"] or 0
        metrics["final"] = {
            "approved": final_approved,
            "success_rate": round(final_approved / total_started * 100, 1)
            if total_started > 0
            else 0,
        }

    return metrics


# ============================================================================
# TASKS HELPERS
# ============================================================================


def get_tasks(
    project_id: Optional[str] = None,
    status: Optional[str] = None,
    domain: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict]:
    """Get tasks with filters."""
    with get_db() as conn:
        query = "SELECT * FROM tasks WHERE 1=1"
        params = []

        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)

        if status:
            query += " AND status = ?"
            params.append(status)

        if domain:
            query += " AND domain = ?"
            params.append(domain)

        query += " ORDER BY wsjf_score DESC, created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()

    return [dict(row) for row in rows]


# ============================================================================
# API ENDPOINTS
# ============================================================================


@app.get("/api/projects")
async def api_projects(response: Response):
    """Get all projects with stats."""
    response.headers["Cache-Control"] = "public, max-age=15"
    return await asyncio.to_thread(get_all_projects)


@app.get("/api/projects/{project_id}")
async def api_project(project_id: str):
    """Get single project details."""
    config = await asyncio.to_thread(load_project_config, project_id)
    if not config:
        return {"error": "Project not found"}

    stats, daemons, metrics = await asyncio.gather(
        asyncio.to_thread(get_project_stats, project_id),
        asyncio.to_thread(get_daemon_status, project_id),
        asyncio.to_thread(get_metrics, project_id),
    )
    return {
        "id": project_id,
        "config": config,
        "stats": stats,
        "daemons": daemons,
        "metrics": metrics,
    }


@app.get("/api/stats")
async def api_stats(response: Response):
    """Get global statistics."""
    response.headers["Cache-Control"] = "public, max-age=10"
    return await asyncio.to_thread(get_global_stats)


@app.get("/api/metrics/{project_id}")
async def api_metrics(project_id: str, response: Response):
    """Get Team of Rivals metrics."""
    response.headers["Cache-Control"] = "public, max-age=30"
    return await asyncio.to_thread(get_metrics, project_id)


@app.get("/api/deploy/status")
async def api_deploy_status():
    """Get live deploy status for all environments."""
    return await asyncio.to_thread(_get_deploy_status)


@app.get("/api/daemons")
async def api_daemons():
    """Get all daemon statuses."""
    result = {}
    project_ids = [
        f.stem for f in PROJECTS_DIR.glob("*.yaml") if not f.name.startswith("_")
    ]
    statuses = await asyncio.gather(
        *[asyncio.to_thread(get_daemon_status, pid) for pid in project_ids]
    )
    for pid, status in zip(project_ids, statuses):
        result[pid] = status
    return result


@app.post("/api/daemons/{project_id}/{daemon}/start")
async def api_daemon_start(project_id: str, daemon: str):
    """Start a daemon."""
    if daemon not in ["cycle", "wiggum", "deploy", "build"]:
        return {"error": "Invalid daemon type"}

    try:
        cmd = f"python3 cli/factory.py {project_id} {daemon} start"
        subprocess.Popen(
            cmd,
            shell=True,
            cwd=str(BASE_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        await asyncio.sleep(1)
        return {
            "success": True,
            "status": get_daemon_status(project_id).get(daemon, {}),
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/daemons/{project_id}/{daemon}/stop")
async def api_daemon_stop(project_id: str, daemon: str):
    """Stop a daemon."""
    if daemon not in ["cycle", "wiggum", "deploy", "build"]:
        return {"error": "Invalid daemon type"}

    try:
        cmd = f"python3 cli/factory.py {project_id} {daemon} stop"
        subprocess.run(cmd, shell=True, cwd=str(BASE_DIR), timeout=10)
        await asyncio.sleep(1)
        return {
            "success": True,
            "status": get_daemon_status(project_id).get(daemon, {}),
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/tasks")
async def api_tasks(
    project: Optional[str] = None,
    status: Optional[str] = None,
    domain: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    """Get tasks with filters."""
    return get_tasks(project, status, domain, limit, offset)


@app.get("/api/logs/{project_id}/stream")
async def api_logs_stream(project_id: str):
    """Stream logs via SSE."""
    log_file = DATA_DIR / "logs" / f"cycle-{project_id}.log"

    async def generate():
        if not log_file.exists():
            yield f"data: Log file not found: {log_file}\n\n"
            return

        # Send last 50 lines first
        try:
            with open(log_file) as f:
                lines = f.readlines()[-50:]
                for line in lines:
                    yield f"data: {line.rstrip()}\n\n"
        except Exception as e:
            yield f"data: Error reading log: {e}\n\n"

        # Then tail for new lines
        try:
            process = await asyncio.create_subprocess_exec(
                "tail",
                "-f",
                str(log_file),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                yield f"data: {line.decode().rstrip()}\n\n"
        except asyncio.CancelledError:
            process.terminate()
            raise

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ============================================================================
# HTML PAGES
# ============================================================================


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Dashboard home page."""
    stats, projects = await asyncio.gather(
        asyncio.to_thread(get_global_stats),
        asyncio.to_thread(get_all_projects),
    )
    # Load Azure / OVH deploy status (non-blocking, cached)
    deploy_status = await asyncio.to_thread(_get_deploy_status)

    # Group projects by domain
    domain_groups: dict[str, dict] = {}
    for p in projects:
        key = p.get("arch_domain") or "_none"
        label = p.get("arch_domain_label") or "Sans domaine"
        color = p.get("arch_domain_color") or "#6B7280"
        if key not in domain_groups:
            domain_groups[key] = {
                "id": key,
                "label": label,
                "color": color,
                "projects": [],
            }
        domain_groups[key]["projects"].append(p)
    # Sort groups: known domains first (alphabetically), then _none last
    sorted_groups = sorted(
        domain_groups.values(),
        key=lambda g: ("z" if g["id"] == "_none" else g["label"]),
    )

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "stats": stats,
            "projects": projects,
            "domain_groups": sorted_groups,
            "deploy_status": deploy_status,
        },
    )


@app.get("/project/{project_id}", response_class=HTMLResponse)
async def project_page(request: Request, project_id: str):
    """Project detail page."""
    config = await asyncio.to_thread(load_project_config, project_id)
    if not config:
        return HTMLResponse("<h1>Project not found</h1>", status_code=404)

    stats, daemons, metrics, tasks = await asyncio.gather(
        asyncio.to_thread(get_project_stats, project_id),
        asyncio.to_thread(get_daemon_status, project_id),
        asyncio.to_thread(get_metrics, project_id),
        asyncio.to_thread(get_tasks, project_id, None, None, 100),
    )
    return templates.TemplateResponse(
        "project.html",
        {
            "request": request,
            "project_id": project_id,
            "config": config,
            "stats": stats,
            "daemons": daemons,
            "metrics": metrics,
            "tasks": tasks,
        },
    )


@app.get("/tasks", response_class=HTMLResponse)
async def tasks_page(
    request: Request,
    project: Optional[str] = None,
    status: Optional[str] = None,
):
    """Tasks listing page."""
    projects, tasks = await asyncio.gather(
        asyncio.to_thread(get_all_projects),
        asyncio.to_thread(get_tasks, project, status, None, 100),
    )
    return templates.TemplateResponse(
        "tasks.html",
        {
            "request": request,
            "projects": projects,
            "tasks": tasks,
            "filter_project": project,
            "filter_status": status,
        },
    )


# ============================================================================
# MAIN
# ============================================================================


def main():
    """Run the dashboard server."""
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    print("\n🏭 Software Factory Dashboard")
    print(f"   http://localhost:{port}\n")

    uvicorn.run(
        "dashboard.server:app",
        host="127.0.0.1",
        port=port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
