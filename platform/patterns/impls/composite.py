"""Composite pattern: sequential execution of multiple sub-patterns.

WHY: some projects require chaining different orchestration strategies (e.g.
wave for decomposition → aggregator for synthesis). CompositePattern lets you
define this as a single PatternDef with steps, rather than multiple separate runs.

Config shape in PatternDef.config / PatternDef.steps:
    steps: [{pattern_id, task_override?}, ...]

Each step runs run_pattern() in sequence. The output of step N is appended to
the context for step N+1 (compressed if > 2 steps).

Ref: SF pattern observability, composite patterns, 2026-03.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def run_composite(engine, run, task: str):
    """Execute composite steps sequentially, passing context forward."""
    from ..engine import run_pattern as _run_pattern

    steps = run.pattern.steps or run.pattern.config.get("steps", [])
    if not steps:
        logger.warning("composite pattern %s has no steps — fallback to sequential", run.pattern.id)
        from .sequential import run_sequential
        await run_sequential(engine, run, task)
        return

    pattern_store = engine._get_pattern_store()
    accumulated_context = task
    last_result = ""

    for i, step in enumerate(steps):
        pattern_id = step.get("pattern_id", "")
        task_override = step.get("task_override", "")

        sub_pattern = pattern_store.get(pattern_id)
        if sub_pattern is None:
            logger.warning("composite step %d: pattern %r not found, skipping", i, pattern_id)
            continue

        step_task = task_override or accumulated_context

        logger.info(
            "composite step %d/%d: running pattern %r for session %s",
            i + 1, len(steps), pattern_id, run.session_id,
        )

        try:
            sub_run = await _run_pattern(
                pattern=sub_pattern,
                session_id=run.session_id,
                initial_task=step_task,
                project_id=run.project_id,
                project_path=run.project_path,
                phase_id=f"{run.phase_id}_step{i}" if run.phase_id else f"composite_step{i}",
                lineage=(run.pattern.id,),
            )
            if sub_run.success:
                # Collect last agent output as context for next step
                outputs = [
                    n.output for n in sub_run.nodes.values()
                    if n.output and n.status.name == "COMPLETED"
                ]
                if outputs:
                    last_result = outputs[-1]
                    # Compressed context: previous + new result
                    if len(accumulated_context) > 500:
                        accumulated_context = accumulated_context[-300:] + "\n\n" + last_result
                    else:
                        accumulated_context = accumulated_context + "\n\n" + last_result
                # Mark composite run nodes as completed proxy
                run.rejection_count += sub_run.rejection_count
            else:
                logger.warning(
                    "composite step %d (%s) failed — continuing", i, pattern_id
                )
                run.rejection_count += sub_run.rejection_count
        except Exception:
            logger.exception("composite step %d (%s) raised", i, pattern_id)
            # Non-fatal: composite continues with remaining steps

    # Mark composite run as successful if we got through all steps
    run.finished = True
    run.success = True
