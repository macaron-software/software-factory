"""
RLM Routes - API endpoints for LEAN Requirements Manager.

Provides HTTP access to RLM Brain, Wiggum TDD, and deployment pipeline.
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from ..rlm.brain import RLMBrain
from ..rlm.models import Domain, TaskStatus
from ..rlm.wiggum_tdd import WiggumTDD
from ..rlm.wiggum_deploy import WiggumDeploy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rlm", tags=["rlm"])


# =============================================================================
# RESPONSE MODELS
# =============================================================================


class AnalyzeResponse(BaseModel):
    """Response for analyze endpoint."""

    status: str
    total_tasks: int
    pending: int
    by_domain: dict


class StatusResponse(BaseModel):
    """Response for status endpoint."""

    total_tasks: int
    pending: int
    completed: int
    failed: int
    by_domain: dict
    updated: str


class TddResponse(BaseModel):
    """Response for TDD endpoint."""

    status: str
    processed: Optional[int] = None
    completed: Optional[int] = None
    failed: Optional[int] = None
    remaining: Optional[int] = None
    task_id: Optional[str] = None
    commit: Optional[str] = None
    error: Optional[str] = None


class DeployResponse(BaseModel):
    """Response for deploy endpoint."""

    status: str
    deployed: Optional[int] = None
    failed: Optional[int] = None
    remaining: Optional[int] = None
    task_id: Optional[str] = None
    commit: Optional[str] = None
    domain: Optional[str] = None
    error: Optional[str] = None


# =============================================================================
# Background task tracking
# =============================================================================

_tdd_task: Optional[asyncio.Task] = None
_deploy_task: Optional[asyncio.Task] = None


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_codebase(
    domain: Optional[str] = None,
    quick: bool = False,
) -> AnalyzeResponse:
    """
    Analyze codebase and generate backlog.

    Args:
        domain: Specific domain to analyze (rust, python, proto, sql, e2e)
        quick: Skip slow analyses

    Returns:
        Analysis summary with task counts
    """
    brain = RLMBrain()

    domain_enum = None
    if domain:
        try:
            domain_enum = Domain(domain)
        except ValueError:
            raise HTTPException(400, f"Invalid domain: {domain}")

    # Run analysis in thread pool (has subprocess calls)
    loop = asyncio.get_event_loop()
    backlog = await loop.run_in_executor(
        None, lambda: asyncio.run(brain.analyze(domain=domain_enum, quick=quick))
    )

    return AnalyzeResponse(
        status="completed",
        total_tasks=backlog.total_tasks,
        pending=backlog.pending_count,
        by_domain={d.value: len(backlog.get_tasks_by_domain(d)) for d in Domain},
    )


@router.get("/status", response_model=StatusResponse)
async def get_status() -> StatusResponse:
    """
    Get RLM backlog status.

    Returns:
        Current backlog statistics
    """
    brain = RLMBrain()
    status = brain.get_status()

    return StatusResponse(**status)


@router.get("/tasks")
async def list_tasks(
    domain: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """
    List tasks from backlog.

    Args:
        domain: Filter by domain
        status: Filter by status (pending, completed, failed)
        limit: Max tasks to return

    Returns:
        List of tasks
    """
    brain = RLMBrain()
    brain.load_backlog()

    tasks = brain.backlog.tasks

    if domain:
        try:
            domain_enum = Domain(domain)
            tasks = [t for t in tasks if t.domain == domain_enum]
        except ValueError:
            pass

    if status:
        try:
            status_enum = TaskStatus(status)
            tasks = [t for t in tasks if t.status == status_enum]
        except ValueError:
            pass

    return {
        "tasks": [
            {
                "id": t.id,
                "type": t.type.value,
                "domain": t.domain.value,
                "description": t.description,
                "status": t.status.value,
                "wsjf_score": t.wsjf_score,
                "files": t.files,
                "finding": {
                    "type": t.finding.type,
                    "severity": t.finding.severity,
                    "message": t.finding.message[:200],
                },
            }
            for t in tasks[:limit]
        ],
        "total": len(tasks),
    }


@router.post("/tdd/start", response_model=TddResponse)
async def start_tdd(
    background_tasks: BackgroundTasks,
    workers: int = 5,
) -> TddResponse:
    """
    Start TDD workers in background.

    Args:
        workers: Number of parallel workers

    Returns:
        Status of TDD start
    """
    global _tdd_task

    if _tdd_task and not _tdd_task.done():
        return TddResponse(status="already_running")

    tdd = WiggumTDD(workers=workers)

    async def run_tdd():
        return await tdd.run()

    _tdd_task = asyncio.create_task(run_tdd())

    return TddResponse(status="started", processed=0)


@router.post("/tdd/once", response_model=TddResponse)
async def run_tdd_once(task_id: Optional[str] = None) -> TddResponse:
    """
    Run TDD on a single task.

    Args:
        task_id: Specific task to process (or highest priority)

    Returns:
        Result of TDD run
    """
    tdd = WiggumTDD(workers=1)
    result = await tdd.run_once(task_id=task_id)

    return TddResponse(**result)


@router.post("/tdd/stop")
async def stop_tdd() -> dict:
    """Stop running TDD workers."""
    global _tdd_task

    if _tdd_task and not _tdd_task.done():
        _tdd_task.cancel()
        return {"status": "stopping"}

    return {"status": "not_running"}


@router.get("/tdd/status")
async def get_tdd_status() -> dict:
    """Get TDD worker status."""
    global _tdd_task

    if _tdd_task is None:
        return {"status": "not_started"}

    if _tdd_task.done():
        try:
            result = _tdd_task.result()
            return {"status": "completed", **result}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    return {"status": "running"}


@router.post("/deploy/start", response_model=DeployResponse)
async def start_deploy(background_tasks: BackgroundTasks) -> DeployResponse:
    """
    Start deployment pipeline in background.

    Returns:
        Status of deployment start
    """
    global _deploy_task

    if _deploy_task and not _deploy_task.done():
        return DeployResponse(status="already_running")

    deploy = WiggumDeploy()

    async def run_deploy():
        return await deploy.run()

    _deploy_task = asyncio.create_task(run_deploy())

    return DeployResponse(status="started")


@router.post("/deploy/once", response_model=DeployResponse)
async def deploy_once() -> DeployResponse:
    """
    Deploy a single task.

    Returns:
        Result of deployment
    """
    deploy = WiggumDeploy()
    result = await deploy.run_once()

    return DeployResponse(**result)


@router.get("/deploy/status")
async def get_deploy_status() -> dict:
    """Get deployment pipeline status."""
    deploy = WiggumDeploy()
    return deploy.get_status()
