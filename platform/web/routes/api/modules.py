"""
Optional Modules API
====================
GET  /api/modules           → list all modules from registry + enabled status
POST /api/modules/{id}/toggle → enable/disable a module
POST /api/modules/{id}/install → run install command
GET  /api/modules/categories → list categories
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import yaml
from fastapi import APIRouter
from fastapi.responses import JSONResponse


try:
    from platform.agents.store import get_db

    _has_db = True
except Exception:
    _has_db = False

router = APIRouter()

REGISTRY_PATH = Path(__file__).parent.parent.parent.parent / "modules" / "registry.yaml"
DATA_DIR = Path(__file__).parent.parent.parent.parent.parent / "data"


def _load_registry() -> list[Dict]:
    if not REGISTRY_PATH.exists():
        return []
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("modules", [])


def _get_enabled_ids() -> set[str]:
    """Read enabled module IDs from DB settings table.
    Default: all builtin modules are enabled.
    NOTE: toggling from UI persists preference in DB but does NOT yet enforce
    at agent runtime — tool registration happens at startup unconditionally.
    """
    builtin_defaults = {m["id"] for m in _load_registry() if m.get("builtin")}
    if not _has_db:
        return builtin_defaults
    try:
        db = get_db()
        rows = db.execute(
            "SELECT value FROM settings WHERE key = 'enabled_modules'"
        ).fetchone()
        if rows:
            import json

            return set(json.loads(rows[0]))
    except Exception:
        pass
    return builtin_defaults


def _set_enabled_ids(ids: set[str]) -> None:
    if not _has_db:
        return
    try:
        import json

        db = get_db()
        db.execute(
            "INSERT OR REPLACE INTO settings(key, value) VALUES('enabled_modules', ?)",
            (json.dumps(sorted(ids)),),
        )
        db.commit()
    except Exception:
        pass


def _is_installed(module: Dict) -> bool:
    """Check whether a module is installed — synchronous, instant (no subprocess).

    Logic:
    - builtin: True  → always installed (bundled with SF)
    - check_cmd starts with "python3 -c import X" → importlib.util.find_spec(X)
    - check_cmd is a binary → shutil.which(binary)
    - data_file  → check file exists
    - otherwise  → True (live API, no install needed)
    """
    if module.get("builtin"):
        return True

    check_cmd = module.get("check_cmd", "")
    if check_cmd:
        # python3 -c "import pkg" or "from pkg import ..."
        if check_cmd.startswith("python"):
            import re

            m = re.search(r"import\s+([\w.]+)", check_cmd)
            if m:
                pkg = m.group(1).split(".")[0]
                return importlib.util.find_spec(pkg) is not None
            return True  # can't parse → assume ok
        # binary check
        binary = check_cmd.split()[0]
        return shutil.which(binary) is not None

    data_file = module.get("data_file")
    if not data_file:
        return True
    path = DATA_DIR / Path(data_file).name
    return path.exists()


def _enrich(module: Dict, enabled_ids: set[str]) -> Dict:
    return {
        **module,
        "enabled": module["id"] in enabled_ids,
        "installed": _is_installed(module),
    }


# ── Routes ──────────────────────────────────────────────────────────────────


@router.get("/api/modules")
async def list_modules():
    modules = _load_registry()
    enabled = _get_enabled_ids()
    return JSONResponse([_enrich(m, enabled) for m in modules])


@router.get("/api/modules/categories")
async def list_categories():
    modules = _load_registry()
    cats: Dict[str, Any] = {}
    for m in modules:
        cat = m.get("category", "other")
        if cat not in cats:
            cats[cat] = {"id": cat, "label": cat.replace("-", " ").title(), "count": 0}
        cats[cat]["count"] += 1
    return JSONResponse(list(cats.values()))


@router.post("/api/modules/{module_id}/toggle")
async def toggle_module(module_id: str):
    modules = _load_registry()
    ids = {m["id"] for m in modules}
    if module_id not in ids:
        return JSONResponse({"ok": False, "error": "Module not found"}, status_code=404)

    enabled = _get_enabled_ids()
    if module_id in enabled:
        enabled.discard(module_id)
        now_enabled = False
    else:
        enabled.add(module_id)
        now_enabled = True

    _set_enabled_ids(enabled)

    # If disabling a module that has a running MCP, stop it immediately
    if not now_enabled:
        _MCP_FOR_MODULE = {"playwright-mcp": "mcp-playwright"}
        mcp_id = _MCP_FOR_MODULE.get(module_id)
        if mcp_id:
            try:
                from platform.mcps.manager import get_mcp_manager

                mgr = get_mcp_manager()
                import asyncio

                asyncio.create_task(mgr.stop(mcp_id))
            except Exception:
                pass

    return JSONResponse({"ok": True, "id": module_id, "enabled": now_enabled})


@router.post("/api/modules/{module_id}/install")
async def install_module(module_id: str):
    modules = _load_registry()
    module = next((m for m in modules if m["id"] == module_id), None)
    if not module:
        return JSONResponse({"ok": False, "error": "Module not found"}, status_code=404)

    install_cmd = module.get("install", "")
    if not install_cmd or install_cmd.startswith("#"):
        return JSONResponse(
            {"ok": True, "message": "No install required", "already_installed": True}
        )

    # Determine how to run the install command
    first_token = install_cmd.split()[0]
    if (
        first_token == "python"
        or first_token == "python3"
        or first_token == sys.executable
    ):
        cmd = [sys.executable] + install_cmd.split()[1:]
    elif first_token in ("pip", "pip3"):
        cmd = [sys.executable, "-m", "pip"] + install_cmd.split()[1:]
    elif first_token == "npm":
        cmd = install_cmd.split()
    elif first_token == "brew":
        cmd = install_cmd.split()
    else:
        cmd = install_cmd.split()

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300, cwd=str(DATA_DIR.parent)
        )
        return JSONResponse(
            {
                "ok": result.returncode == 0,
                "stdout": result.stdout[-3000:] if result.stdout else "",
                "stderr": result.stderr[-2000:] if result.stderr else "",
                "returncode": result.returncode,
            }
        )
    except subprocess.TimeoutExpired:
        return JSONResponse({"ok": False, "error": "Install timed out (300s)"})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)})
