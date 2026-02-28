"""
Multi-server mission dispatch — coordinator selects least-loaded worker node.
===========================================================================
Architecture:
  - Coordinator (Azure / main node): receives mission start requests
  - Worker nodes (OVH, etc.): run the actual agent loops
  - Selection: least CPU + active_missions score
  - Each worker node exposes:
      GET  /api/metrics/load   → {"cpu_percent", "ram_percent", "active_missions", "load_score"}
      POST /api/missions/dispatch → same body as /api/missions/start, runs locally

Configuration (platform.yaml or env):
  orchestrator:
    worker_nodes:
      - https://ovh.example.com
      - https://worker2.example.com

  Or via env: PLATFORM_WORKER_NODES=https://node1,https://node2
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..helpers import _parse_body

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Worker node registry ──────────────────────────────────────────────────────

@dataclass
class WorkerNodeInfo:
    url: str
    cpu_percent: float = 100.0
    ram_percent: float = 100.0
    active_missions: int = 0
    load_score: float = 100.0
    available: bool = False


def _get_worker_urls() -> list[str]:
    """Get worker node URLs from config or environment."""
    # Try environment variable first (comma-separated)
    env_nodes = os.environ.get("PLATFORM_WORKER_NODES", "")
    if env_nodes:
        return [u.strip().rstrip("/") for u in env_nodes.split(",") if u.strip()]

    # Try platform config
    try:
        from ....config import get_config
        cfg = get_config()
        nodes = cfg.orchestrator.worker_nodes
        return [str(u).rstrip("/") for u in nodes if u]
    except Exception:
        return []


async def _probe_node(url: str, client: httpx.AsyncClient) -> WorkerNodeInfo:
    """Probe a worker node's load metrics."""
    info = WorkerNodeInfo(url=url)
    try:
        r = await client.get(f"{url}/api/metrics/load", timeout=4.0)
        if r.status_code == 200:
            d = r.json()
            info.cpu_percent = float(d.get("cpu_percent", 100))
            info.ram_percent = float(d.get("ram_percent", 100))
            info.active_missions = int(d.get("active_missions", 0))
            info.load_score = float(d.get("load_score", (info.cpu_percent + info.ram_percent) / 2))
            info.available = info.cpu_percent < 85 and info.ram_percent < 85
    except Exception as e:
        logger.debug("Worker probe failed %s: %s", url, e)
    return info


async def select_worker_node() -> str | None:
    """Select the least-loaded available worker node. Returns URL or None."""
    urls = _get_worker_urls()
    if not urls:
        return None

    async with httpx.AsyncClient() as client:
        infos = await asyncio.gather(*[_probe_node(u, client) for u in urls])

    available = [n for n in infos if n.available]
    if not available:
        # All overloaded — still try the least loaded
        available = list(infos)

    best = min(available, key=lambda n: (n.load_score, n.active_missions))
    logger.info("Dispatch: selected worker %s (cpu=%.1f%% ram=%.1f%% missions=%d)",
                best.url, best.cpu_percent, best.ram_percent, best.active_missions)
    return best.url


async def dispatch_to_worker(worker_url: str, payload: dict) -> dict:
    """Forward a mission start request to a worker node."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Forward platform API key if configured
            headers = {}
            api_key = os.environ.get("PLATFORM_API_KEY", "")
            if api_key:
                headers["X-Platform-Key"] = api_key

            r = await client.post(
                f"{worker_url}/api/missions/dispatch",
                json=payload,
                headers=headers,
            )
            if r.status_code == 200:
                data = r.json()
                data["_dispatched_to"] = worker_url
                return data
            else:
                return {"error": f"Worker returned {r.status_code}: {r.text[:200]}"}
    except Exception as e:
        return {"error": f"Dispatch failed: {e}"}


# ── Coordinator endpoint: /api/missions/start augmented ──────────────────────
# This is called from execution.py after creating the MissionRun locally.
# If worker nodes are configured, the orchestration is delegated.

async def maybe_dispatch(mission_id: str, brief: str, project_id: str, workflow_id: str) -> dict | None:
    """
    If worker nodes are configured, dispatch mission orchestration to a worker.
    Returns dispatch result dict (with _dispatched_to) or None if running locally.
    """
    worker_url = await select_worker_node()
    if not worker_url:
        return None  # No workers → run locally

    payload = {
        "workflow_id": workflow_id,
        "brief": brief,
        "project_id": project_id,
        "_coordinator_mission_id": mission_id,
    }
    result = await dispatch_to_worker(worker_url, payload)
    if "error" in result:
        logger.warning("Dispatch to %s failed: %s — falling back to local", worker_url, result["error"])
        return None  # Fallback to local execution
    return result


# ── Worker endpoint: /api/missions/dispatch ───────────────────────────────────

@router.post("/api/missions/dispatch")
async def api_missions_dispatch(request: Request):
    """
    Worker node endpoint — receives delegated mission from coordinator.
    Validates API key (if configured), creates local MissionRun, and starts orchestration.
    This is identical to /api/missions/start but accepts coordinator metadata.
    """
    # Optional API key check
    api_key = os.environ.get("PLATFORM_API_KEY", "")
    if api_key:
        req_key = request.headers.get("X-Platform-Key", "")
        if req_key != api_key:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)

    data = await _parse_body(request)

    # Forward to the standard mission start endpoint logic
    # Import here to avoid circular imports
    from .execution import api_mission_start
    return await api_mission_start(request)


# ── Status endpoint: list worker nodes + their load ──────────────────────────

@router.get("/api/dispatch/workers")
async def api_dispatch_workers():
    """Return configured worker nodes and their current load metrics."""
    urls = _get_worker_urls()
    if not urls:
        return JSONResponse({"workers": [], "coordinator_only": True})

    async with httpx.AsyncClient() as client:
        infos = await asyncio.gather(*[_probe_node(u, client) for u in urls])

    return JSONResponse({
        "workers": [
            {
                "url": n.url,
                "cpu_percent": n.cpu_percent,
                "ram_percent": n.ram_percent,
                "active_missions": n.active_missions,
                "load_score": n.load_score,
                "available": n.available,
            }
            for n in infos
        ],
        "coordinator_only": False,
    })
