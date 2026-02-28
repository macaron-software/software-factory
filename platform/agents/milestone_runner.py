"""MilestoneRunner — long-running mission pipeline executor.

Inspired by Codex's 25-hour uninterrupted runs:
  - A mission config can contain a ``milestones`` list
  - Each milestone has a ``goal``, ``prompt``, and optional ``verify_cmd``
  - The runner calls AgentExecutor sequentially per milestone
  - PROGRESS.md is updated between milestones
  - On failure (lint/build/verify), up to MAX_MILESTONE_RETRIES retries before giving up
  - Stops immediately on 3 consecutive failures

Usage
-----
Add to mission config::

    config = {
        "milestones": [
            {"id": "m1", "goal": "Setup project structure", "prompt": "Create src/ layout..."},
            {"id": "m2", "goal": "Implement auth", "prompt": "Build JWT auth module..."},
        ]
    }

Then launch via ``MilestoneRunner.run()`` — called automatically from
``platform/web/routes/missions/execution.py`` when milestones are present.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..agents.executor import AgentExecutor, ExecutionContext

logger = logging.getLogger(__name__)

MAX_MILESTONE_RETRIES = 3
MAX_CONSECUTIVE_FAILURES = 3


@dataclass
class MilestoneResult:
    milestone_id: str
    goal: str
    success: bool
    content: str = ""
    error: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: int = 0
    retry: int = 0
    tool_calls: list[dict] = field(default_factory=list)


async def run_milestone_pipeline(
    milestones: list[dict],
    *,
    executor: "AgentExecutor",
    ctx: "ExecutionContext",
    session_id: str,
    mission_name: str,
    project_path: str = "",
    on_progress=None,  # async callable(milestone_result) for SSE
) -> list[MilestoneResult]:
    """Run a list of milestones sequentially, with retries and PROGRESS.md updates.

    Each milestone is executed as a full AgentExecutor.run() call.
    After each milestone (success or failure), PROGRESS.md is written to
    ``project_path/PROGRESS.md``.

    Parameters
    ----------
    milestones:
        List of dicts: ``{id, goal, prompt, verify_cmd?}``
    executor:
        Shared AgentExecutor instance (reused across milestones)
    ctx:
        ExecutionContext with agent, project_path, tools, etc.
    session_id:
        Session ID for SSE event routing
    mission_name:
        Human-readable mission name (used in PROGRESS.md)
    project_path:
        Workspace directory path (written to PROGRESS.md + used by tools)
    on_progress:
        Optional async callback called after each milestone with its MilestoneResult
    """
    results: list[MilestoneResult] = []
    consecutive_failures = 0
    total = len(milestones)

    _write_pipeline_header(project_path, mission_name, total)

    for idx, m_def in enumerate(milestones):
        m_id = m_def.get("id") or f"m{idx + 1}"
        goal = m_def.get("goal", m_id)

        logger.info(
            "MilestoneRunner: [%d/%d] %s — %s session=%s",
            idx + 1,
            total,
            m_id,
            goal,
            session_id,
        )

        # Push SSE: milestone started
        await _push_sse_safe(
            session_id,
            {
                "type": "milestone_start",
                "milestone_id": m_id,
                "goal": goal,
                "index": idx,
                "total": total,
            },
        )

        m_result = MilestoneResult(milestone_id=m_id, goal=goal, success=False)
        last_error = ""

        for attempt in range(MAX_MILESTONE_RETRIES):
            try:
                # Inject milestone context into the prompt
                full_prompt = _build_milestone_prompt(m_def, idx, total, results)
                exec_result = await executor.run(ctx, full_prompt)

                m_result.content = exec_result.content or ""
                m_result.tokens_in = exec_result.tokens_in
                m_result.tokens_out = exec_result.tokens_out
                m_result.duration_ms = exec_result.duration_ms
                m_result.tool_calls = exec_result.tool_calls or []
                m_result.retry = attempt

                if exec_result.error:
                    last_error = exec_result.error
                    logger.warning(
                        "Milestone %s attempt %d error: %s",
                        m_id,
                        attempt + 1,
                        last_error,
                    )
                    continue

                # Optional: run verify_cmd if provided
                verify_cmd = m_def.get("verify_cmd")
                if verify_cmd and project_path:
                    verify_ok, verify_out = await _run_verify_cmd(
                        verify_cmd, project_path
                    )
                    if not verify_ok:
                        last_error = f"verify_cmd failed: {verify_out[:300]}"
                        logger.warning(
                            "Milestone %s verify failed (attempt %d): %s",
                            m_id,
                            attempt + 1,
                            last_error,
                        )
                        continue

                m_result.success = True
                consecutive_failures = 0
                break

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                last_error = str(exc)
                logger.exception("Milestone %s attempt %d exception", m_id, attempt + 1)

        if not m_result.success:
            m_result.error = last_error
            consecutive_failures += 1
            logger.error(
                "Milestone %s FAILED after %d attempts (consecutive failures: %d)",
                m_id,
                MAX_MILESTONE_RETRIES,
                consecutive_failures,
            )

        results.append(m_result)

        # Update PROGRESS.md after each milestone
        if project_path:
            _write_pipeline_progress(
                project_path, mission_name, idx + 1, total, results
            )

        # Push SSE: milestone done
        await _push_sse_safe(
            session_id,
            {
                "type": "milestone_done",
                "milestone_id": m_id,
                "goal": goal,
                "success": m_result.success,
                "index": idx,
                "total": total,
                "error": m_result.error,
            },
        )

        if on_progress:
            try:
                await on_progress(m_result)
            except Exception:
                pass

        # Stop on 3 consecutive failures
        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            logger.error(
                "MilestoneRunner: %d consecutive failures — stopping pipeline. session=%s",
                consecutive_failures,
                session_id,
            )
            await _push_sse_safe(
                session_id,
                {
                    "type": "pipeline_aborted",
                    "reason": f"{consecutive_failures} consecutive milestone failures",
                    "completed": idx + 1,
                    "total": total,
                },
            )
            break

    # Final PROGRESS.md summary
    if project_path:
        _write_pipeline_progress(
            project_path, mission_name, len(results), total, results, final=True
        )

    done = sum(1 for r in results if r.success)
    logger.info(
        "MilestoneRunner: pipeline done %d/%d milestones passed session=%s",
        done,
        total,
        session_id,
    )
    return results


def _build_milestone_prompt(
    m_def: dict, idx: int, total: int, prior: list[MilestoneResult]
) -> str:
    """Build the LLM prompt for a single milestone, injecting prior context."""
    goal = m_def.get("goal", "")
    prompt = m_def.get("prompt") or goal
    acceptance = m_def.get("acceptance_criteria", "")

    # Summarize prior completed milestones (last 3)
    prior_summary = ""
    done_prior = [r for r in prior if r.success][-3:]
    if done_prior:
        lines = [f"  - [✓] {r.goal}" for r in done_prior]
        prior_summary = (
            "Milestones précédents complétés :\n" + "\n".join(lines) + "\n\n"
        )

    header = (
        f"## Milestone {idx + 1}/{total} : {goal}\n\n"
        f"{prior_summary}"
        f"**Objectif** : {goal}\n\n"
    )
    if acceptance:
        header += f"**Critères d'acceptation** : {acceptance}\n\n"
    header += f"**Instructions** :\n{prompt}\n\n"
    header += (
        "Après avoir terminé, indique explicitement : `[MILESTONE DONE]` "
        "si le milestone est réussi, ou `[MILESTONE FAILED: <raison>]` sinon."
    )
    return header


async def _run_verify_cmd(cmd: str, cwd: str) -> tuple[bool, str]:
    """Run a shell verify command and return (success, output)."""
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=120.0)
        output = out.decode(errors="replace")
        return proc.returncode == 0, output
    except asyncio.TimeoutError:
        return False, "verify_cmd timed out (120s)"
    except Exception as exc:
        return False, str(exc)


def _write_pipeline_header(project_path: str, mission_name: str, total: int) -> None:
    """Write initial PROGRESS.md before pipeline starts."""
    if not project_path:
        return
    path = os.path.join(project_path, "PROGRESS.md")
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    content = f"""# PROGRESS — {mission_name}

> Pipeline de milestones démarré le {now} ({total} milestones prévus).

## Statut : 🔄 En cours

| # | Milestone | Statut |
|---|-----------|--------|
"""
    os.makedirs(project_path, exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def _write_pipeline_progress(
    project_path: str,
    mission_name: str,
    done_count: int,
    total: int,
    results: list[MilestoneResult],
    *,
    final: bool = False,
) -> None:
    """Update PROGRESS.md with current pipeline state."""
    if not project_path:
        return
    path = os.path.join(project_path, "PROGRESS.md")
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    status_icon = "✅ Terminé" if final else "🔄 En cours"
    success_count = sum(1 for r in results if r.success)

    rows = ""
    for i, r in enumerate(results):
        icon = "✅" if r.success else "❌"
        retry_note = f" (retry {r.retry})" if r.retry else ""
        err_note = f" — {r.error[:60]}" if r.error else ""
        rows += f"| {i + 1} | {r.goal} | {icon}{retry_note}{err_note} |\n"

    # Tokens summary
    total_in = sum(r.tokens_in for r in results)
    total_out = sum(r.tokens_out for r in results)

    content = f"""# PROGRESS — {mission_name}

> Dernière mise à jour : {now}

## Statut : {status_icon}

**{success_count}/{done_count}** milestones réussis · Tokens: {total_in} in / {total_out} out

| # | Milestone | Statut |
|---|-----------|--------|
{rows}
## Décisions

_(à compléter par l'agent au fil de l'exécution)_
"""
    os.makedirs(project_path, exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


async def _push_sse_safe(session_id: str, event: dict) -> None:
    """Push SSE event, ignoring errors."""
    try:
        from ..sessions.runner import _push_sse

        await _push_sse(session_id, event)
    except Exception:
        pass
