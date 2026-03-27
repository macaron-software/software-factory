"""AC (Acceptance Criteria) web routes."""
from __future__ import annotations
import logging
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .helpers import _templates

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/ac", response_class=HTMLResponse)
async def ac_page(request: Request):
    """Unified AC report page."""
    return _templates(request).TemplateResponse(
        request, "ac.html", {"page_title": "Unified AC Report"}
    )


@router.get("/api/ac/run")
async def api_ac_run(
    scope: str = "",
    project_id: str = "",
    sandbox: bool = True,
    llm_judge: bool = False,
    mode: str = "process",
):
    """Run AC for all (or scoped) component types.

    mode='process' (default): run in-process with ProcessSandbox.
    mode='docker': run full unified AC inside an ephemeral Docker container via DockerSandbox.
    """
    parts = [s.strip() for s in scope.split(",") if s.strip()]
    if not parts or parts == ["all"]:
        scope_list = None
    else:
        scope_list = parts

    if mode == "docker":
        from ...ac.sandbox import DockerSandbox
        docker = DockerSandbox()
        if not docker.available():
            return JSONResponse({"error": "Docker is not available on this host"}, status_code=503)
        try:
            result = docker.run_unified_ac(scope=scope_list, project_id=project_id or None)
            return JSONResponse(result)
        except Exception as e:
            logger.error("Docker AC run failed: %s", e)
            return JSONResponse({"error": str(e)}, status_code=500)

    from ...ac.runner import run_all_ac, ALL_COMPONENT_TYPES

    try:
        report = run_all_ac(
            scope=scope_list,
            project_id=project_id or None,
            sandbox=sandbox,
            use_llm_judge=llm_judge,
        )
        return JSONResponse(report.to_dict())
    except Exception as e:
        logger.error("AC run failed: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/ac/run/{component_type}")
async def api_ac_run_type(
    component_type: str,
    project_id: str = "",
    sandbox: bool = True,
    llm_judge: bool = False,
):
    """Run AC for a single component type."""
    from ...ac.runner import run_all_ac, ALL_COMPONENT_TYPES

    if component_type not in ALL_COMPONENT_TYPES:
        return JSONResponse(
            {"error": f"Unknown component type: {component_type}. Valid: {ALL_COMPONENT_TYPES}"},
            status_code=400,
        )
    try:
        report = run_all_ac(
            scope=[component_type],
            project_id=project_id or None,
            sandbox=sandbox,
            use_llm_judge=llm_judge,
        )
        return JSONResponse(report.to_dict())
    except Exception as e:
        logger.error("AC run failed for %s: %s", component_type, e)
        return JSONResponse({"error": str(e)}, status_code=500)
