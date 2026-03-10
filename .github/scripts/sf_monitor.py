#!/usr/bin/env python3
"""SF Monitor — AC cycles + SAFe portfolio + Teams leaderboard + Infra."""

import json
import subprocess
import urllib.request
import urllib.error
from datetime import datetime, timezone

# ── Port detection ──────────────────────────────────────────────────────────
BASE_URL = "http://localhost:8090"
for port in [8091, 8090, 8099, 8080, 80]:
    try:
        with urllib.request.urlopen(
            f"http://localhost:{port}/api/health", timeout=3
        ) as r:
            if b"status" in r.read():
                BASE_URL = f"http://localhost:{port}"
                break
    except Exception:
        pass

COOKIES = {}

# ── Auth ────────────────────────────────────────────────────────────────────
try:
    req = urllib.request.Request(
        f"{BASE_URL}/api/auth/demo",
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        for hdr in r.headers.get_all("Set-Cookie") or []:
            if "access_token=" in hdr:
                val = hdr.split("access_token=")[1].split(";")[0]
                COOKIES["access_token"] = val
except Exception:
    pass


def api(path):
    try:
        req = urllib.request.Request(f"{BASE_URL}{path}")
        if COOKIES:
            req.add_header("Cookie", "; ".join(f"{k}={v}" for k, v in COOKIES.items()))
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read())
    except Exception:
        return {}


now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
print(f"====== SF MONITOR {now} ======")
print(f"  platform: {BASE_URL}  auth={'OK' if COOKIES else 'NONE'}")
print()

# ── AC Cycles ───────────────────────────────────────────────────────────────
print("-- AC CYCLES (L2 — SF self-improvement) --")
health = api("/api/health")
cycles = health.get("ac_cycles", [])
running = [c for c in cycles if c.get("status") == "running"]
idle = [c for c in cycles if c.get("status") == "idle"]
print(f"  {len(cycles)} projets | running:{len(running)} idle:{len(idle)}")
for c in sorted(cycles, key=lambda x: -x.get("cycle", 0)):
    tag = "RUN" if c.get("status") == "running" else "IDL"
    upd = c.get("updated_at", "")[:16]
    print(f"  {tag} {c.get('project', '?'):<28} cycle={c.get('cycle', 0):>3}  {upd}")
print()

# ── SAFe Cockpit ────────────────────────────────────────────────────────────
print("-- SAFe COCKPIT --")
cockpit = api("/api/cockpit/summary")
projects = cockpit.get("projects", [])
dora = cockpit.get("dora", {})
pipeline = cockpit.get("pipeline", {})
print(f"  projects: {len(projects)}")
for k, v in dora.items():
    if isinstance(v, (int, float, str)):
        print(f"  dora.{k}: {v}")
for k, v in pipeline.items():
    if isinstance(v, (int, float, str)):
        print(f"  pipeline.{k}: {v}")
for p in projects[:8]:
    name = p.get("name", p.get("id", "?"))[:40]
    print(f"  [{p.get('status', '?'):10}] {name}")
print()

# ── SAFe Epics / Portfolio ───────────────────────────────────────────────────
print("-- SAFe EPICS / PORTFOLIO --")
epics_data = api("/api/missions")  # SAFe epics live at /api/missions
epics = (
    epics_data
    if isinstance(epics_data, list)
    else epics_data.get("epics", epics_data.get("items", []))
)
by_status: dict = {}
for e in epics:
    s = e.get("status", "?")
    by_status[s] = by_status.get(s, 0) + 1
summary = " | ".join(
    f"{k}:{v}" for k, v in sorted(by_status.items(), key=lambda x: -x[1])
)
print(f"  total:{len(epics)} | {summary}")
for e in sorted(
    epics,
    key=lambda x: x.get("updated_at", x.get("created_at", "0")),
    reverse=True,
)[:8]:
    proj = e.get("project_id", "")
    phase = e.get("current_phase", "")
    runs_done = e.get("phases_done", "")
    runs_tot = e.get("phases_total", "")
    print(
        f"  [{e.get('status', '?'):10}] {e.get('name', '?')[:45]}"
        f"  proj={proj}  {runs_done}/{runs_tot}  phase={phase}"
    )
print()

# ── Teams Leaderboard ───────────────────────────────────────────────────────
print("-- TEAMS LEADERBOARD (top 10) --")
# fitness_score by technology — try all technologies
lb_data = api("/api/teams/leaderboard?limit=30")
agents = (
    lb_data
    if isinstance(lb_data, list)
    else lb_data.get("leaderboard", lb_data.get("agents", []))
)
if not agents:
    # try without technology filter (all)
    lb_data2 = api("/api/teams/leaderboard?technology=all&limit=30")
    agents = (
        lb_data2
        if isinstance(lb_data2, list)
        else lb_data2.get("leaderboard", lb_data2.get("agents", []))
    )
print(f"  {len(agents)} agents enregistrés")
for a in agents[:10]:
    name = a.get("agent_id", a.get("name", "?"))
    score = a.get("fitness_score", a.get("score", a.get("total_score", "?")))
    runs = a.get("runs", a.get("total_runs", "?"))
    badge = a.get("badge", "")
    print(f"  {name:<30} score={score}  runs={runs}  {badge}")
print()

# ── Infra ───────────────────────────────────────────────────────────────────
print("-- INFRA --")
try:
    df = subprocess.check_output(["df", "/"], text=True).splitlines()
    parts = df[-1].split()
    print(f"  Disk: {parts[4]} of {parts[1]}")
except Exception:
    pass
try:
    free = subprocess.check_output(["free", "-h"], text=True).splitlines()
    for line in free:
        if line.startswith("Mem:"):
            parts = line.split()
            print(f"  Mem:  {parts[2]} / {parts[1]}")
except Exception:
    pass
try:
    docker_out = subprocess.check_output(
        ["docker", "ps", "--format", "{{.Names}} {{.Status}}"], text=True
    )
    for line in docker_out.splitlines():
        if any(k in line for k in ["unhealthy", "macaron-app", "platform"]):
            print(f"  {line}")
except Exception:
    pass
print()
print("====== END MONITOR ======")
