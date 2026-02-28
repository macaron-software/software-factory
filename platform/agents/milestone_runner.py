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
    compliance_agents: list[str] | None = None,  # domain-specific critic agent ids
    compliance_blocking: bool = False,  # if True, FAIL verdict stops the pipeline
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
    compliance_agents:
        Optional list of domain-specific critic agent IDs to run after each successful
        milestone. If provided, each agent is spawned as a compliance check on the
        workspace. Violations are logged to PROGRESS.md (non-blocking).
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

        # Run domain compliance critics after each successful milestone
        if m_result.success and compliance_agents:
            compliance_ok = await _run_compliance_checks(
                compliance_agents=compliance_agents,
                executor=executor,
                ctx=ctx,
                session_id=session_id,
                milestone_id=m_id,
                goal=goal,
                project_path=project_path,
                mission_name=mission_name,
                compliance_blocking=compliance_blocking,
            )
            if not compliance_ok:
                logger.warning(
                    "MilestoneRunner: compliance BLOCKING FAIL at milestone %s — stopping pipeline. session=%s",
                    m_id,
                    session_id,
                )
                await _push_sse_safe(
                    session_id,
                    {
                        "type": "pipeline_aborted",
                        "reason": f"Compliance blocking fail at milestone {m_id}",
                        "completed": idx + 1,
                        "total": total,
                    },
                )
                break

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


async def _run_compliance_checks(
    *,
    compliance_agents: list[str],
    executor: "AgentExecutor",
    ctx: "ExecutionContext",
    session_id: str,
    milestone_id: str,
    goal: str,
    project_path: str,
    mission_name: str,
    compliance_blocking: bool = False,
) -> bool:
    """Run domain-specific compliance critic agents after a successful milestone.

    Returns True if all checks passed (or blocking is off), False if a blocking
    FAIL was detected and the caller should pause the mission.
    """
    from ..agents.store import get_agent_store
    from dataclasses import replace

    store = get_agent_store()
    any_blocking_fail = False

    for agent_id in compliance_agents:
        agent_def = store.get(agent_id)
        if not agent_def:
            logger.warning("ComplianceCheck: agent '%s' not found, skipping", agent_id)
            continue

        logger.info(
            "ComplianceCheck: running %s after milestone %s session=%s",
            agent_id,
            milestone_id,
            session_id,
        )
        await _push_sse_safe(
            session_id,
            {
                "type": "compliance_start",
                "agent_id": agent_id,
                "milestone_id": milestone_id,
            },
        )

        blocking_note = (
            (
                "\n\nIMPORTANT: compliance_blocking=true for this domain. "
                "If you find BLOCKING violations, output a line: `BLOCKING VIOLATIONS FOUND`."
            )
            if compliance_blocking
            else ""
        )

        # Load compliance history for this project (last 5 verdicts from same agent)
        history_note = _load_compliance_history(ctx.project_id, agent_id)

        compliance_prompt = (
            f"## Compliance Review — Milestone « {goal} »\n\n"
            f"{history_note}"
            f"The milestone `{milestone_id}` just completed successfully as part of "
            f"mission « {mission_name} ».\n\n"
            f"Review the code produced in this milestone for domain compliance violations.\n"
            f"Focus on changes introduced in this milestone — check files in the workspace.\n\n"
            f"List all violations with file + line. Provide a PASS/FAIL verdict."
            f"{blocking_note}"
        )

        compliance_ctx = replace(ctx, agent=agent_def)
        try:
            result = await executor.run(compliance_ctx, compliance_prompt)
            verdict = "PASS" if not result.error else "ERROR"
            content_upper = (result.content or "").upper()
            if "FAIL" in content_upper:
                verdict = "FAIL"

            # Detect blocking violations
            is_blocking_fail = (
                compliance_blocking
                and verdict == "FAIL"
                and "BLOCKING VIOLATIONS FOUND" in content_upper
            )
            if is_blocking_fail:
                any_blocking_fail = True

            logger.info(
                "ComplianceCheck: %s verdict=%s blocking=%s milestone=%s",
                agent_id,
                verdict,
                is_blocking_fail,
                milestone_id,
            )

            # Persist verdict to DB
            _persist_compliance_verdict(
                session_id=session_id,
                milestone_id=milestone_id,
                agent_id=agent_id,
                goal=goal,
                verdict=verdict,
                content=result.content or "",
                is_blocking=is_blocking_fail,
            )

            await _push_sse_safe(
                session_id,
                {
                    "type": "compliance_done",
                    "agent_id": agent_id,
                    "milestone_id": milestone_id,
                    "verdict": verdict,
                    "blocking": is_blocking_fail,
                    "preview": (result.content or "")[:300],
                },
            )

            # Append compliance report to PROGRESS.md
            if project_path:
                _append_compliance_to_progress(
                    project_path, agent_id, milestone_id, verdict, result.content or ""
                )

            if is_blocking_fail:
                await _push_sse_safe(
                    session_id,
                    {
                        "type": "compliance_blocking_fail",
                        "agent_id": agent_id,
                        "milestone_id": milestone_id,
                        "message": (
                            f"Mission paused: {agent_id} found BLOCKING violations in "
                            f"milestone {milestone_id}. Fix violations before continuing."
                        ),
                    },
                )
                # Stop checking further agents — mission will be paused by caller
                break

        except Exception as exc:
            logger.warning(
                "ComplianceCheck: %s failed with %s — milestone=%s",
                agent_id,
                exc,
                milestone_id,
            )

    return not any_blocking_fail


def _load_compliance_history(project_id: str, agent_id: str) -> str:
    """Load the last 5 compliance verdicts for this project+agent to inject as history context."""
    if not project_id:
        return ""
    try:
        from ..db.migrations import get_db

        db = get_db()
        rows = db.execute(
            """SELECT cv.verdict, cv.milestone_id, cv.goal, cv.created_at,
                      substr(cv.content, 1, 300) as preview
               FROM compliance_verdicts cv
               JOIN mission_runs mr ON cv.session_id = mr.session_id
               WHERE mr.project_id = ? AND cv.agent_id = ?
               ORDER BY cv.created_at DESC LIMIT 5""",
            (project_id, agent_id),
        ).fetchall()
        if not rows:
            return ""
        lines = ["### 📋 Historique compliance précédent (ce projet)\n"]
        for r in reversed(rows):
            icon = "✅" if r["verdict"] == "PASS" else "❌"
            lines.append(
                f"- {icon} **{r['verdict']}** — {r['goal'] or r['milestone_id']} "
                f"({r['created_at'][:10]}): {r['preview'][:150]}\n"
            )
        lines.append(
            "\nTiens compte de ces violations précédentes si elles sont récurrentes.\n\n"
        )
        return "".join(lines)
    except Exception:
        return ""


def _append_compliance_to_progress(
    project_path: str, agent_id: str, milestone_id: str, verdict: str, content: str
) -> None:
    """Append a compliance check result to PROGRESS.md."""
    path = os.path.join(project_path, "PROGRESS.md")
    if not os.path.exists(path):
        return
    icon = "✅" if verdict == "PASS" else ("❌" if verdict == "FAIL" else "⚠️")
    now = datetime.utcnow().strftime("%H:%M UTC")
    section = (
        f"\n### {icon} Compliance: {agent_id} — {milestone_id} ({now}) — {verdict}\n\n"
        f"<details><summary>Rapport</summary>\n\n"
        f"{content[:1500]}\n"
        f"</details>\n"
    )
    with open(path, "a") as f:
        f.write(section)


def _persist_compliance_verdict(
    *,
    session_id: str,
    milestone_id: str,
    agent_id: str,
    goal: str,
    verdict: str,
    content: str,
    is_blocking: bool,
) -> None:
    """Persist compliance verdict to DB for dashboard queries."""
    try:
        from ..db.migrations import get_db

        db = get_db()
        # Ensure table exists
        db.execute("""
            CREATE TABLE IF NOT EXISTS compliance_verdicts (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                milestone_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                goal TEXT,
                verdict TEXT NOT NULL,
                is_blocking INTEGER DEFAULT 0,
                content TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        db.execute(
            """INSERT OR REPLACE INTO compliance_verdicts
               (id, session_id, milestone_id, agent_id, goal, verdict, is_blocking, content)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                f"{session_id}-{milestone_id}-{agent_id}",
                session_id,
                milestone_id,
                agent_id,
                goal,
                verdict,
                1 if is_blocking else 0,
                content[:4000],
            ),
        )
        db.commit()
    except Exception as exc:
        logger.debug("ComplianceCheck: could not persist verdict: %s", exc)
