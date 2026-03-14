"""Loop pattern: writer/reviewer iterate until approval."""
from __future__ import annotations
# Ref: feat-patterns

import uuid
from datetime import datetime


async def run_loop(engine, run, task: str):
    """Loop between writer and reviewer until approval or max iterations.

    Creates a sprint DB record per iteration for observability in mission_detail.
    On VETO: marks sprint rejected, creates next sprint. On approval: marks completed.
    """
    from ..engine import NodeStatus

    nodes = engine._ordered_nodes(run.pattern)
    if len(nodes) < 2:
        from .sequential import run_sequential
        return await run_sequential(engine, run, task)

    writer_id = nodes[0]
    reviewer_id = nodes[1]
    writer_agent = engine._node_agent_id(run, writer_id)
    reviewer_agent = engine._node_agent_id(run, reviewer_id)

    # Sprint tracking: record each iteration as a DB sprint row
    _sprint_store = None
    try:
        from ...epics.store import EpicStore, SprintDef
        _sprint_store = EpicStore()
    except Exception:
        pass

    def _create_sprint(number: int) -> str | None:
        """Insert a sprint row at iteration start. Returns sprint_id or None."""
        if not _sprint_store or not run.session_id:
            return None
        try:
            s = SprintDef(
                id=str(uuid.uuid4())[:8],
                mission_id=run.session_id,
                number=number,
                name=f"Loop sprint {number}",
                goal=task[:200] if task else "",
                status="active",
                started_at=datetime.utcnow().isoformat(),
                type="tdd",
                team_agents="[]",
            )
            _sprint_store.create_sprint(s)
            return s.id
        except Exception:
            return None

    def _finish_sprint(sprint_id: str, rejected: bool, quality: int = 0) -> None:
        """Update sprint status at iteration end."""
        if not _sprint_store or not sprint_id:
            return
        try:
            status = "rejected" if rejected else "completed"
            _sprint_store.update_sprint_status(sprint_id, status)
            # Update quality_score via direct DB write
            from ...db.migrations import get_db
            db = get_db()
            db.execute(
                "UPDATE sprints SET quality_score=?, completed_at=? WHERE id=?",
                (quality, datetime.utcnow().isoformat(), sprint_id),
            )
            db.commit()
            db.close()
        except Exception:
            pass

    prev_output = ""
    sprint_id: str | None = None

    for i in range(run.max_iterations):
        run.iteration = i + 1
        sprint_id = _create_sprint(i + 1)

        # Writer produces → sends to reviewer
        writer_output = await engine._execute_node(
            run, writer_id, task, context_from=prev_output,
            to_agent_id=reviewer_agent,
        )

        # After each writer iteration: auto-run build/tests (stack-agnostic)
        # so the reviewer sees real results, not just the writer's claims
        cicd_context = ""
        if run.project_path:
            try:
                from ..tools.build_tools import CICDRunnerTool
                cicd_tool = CICDRunnerTool()
                cicd_result = await cicd_tool.execute({"cwd": run.project_path}, None)
                cicd_context = (
                    f"\n\n## Build/Test Results (auto-executed after writer)\n"
                    f"```\n{cicd_result}\n```\n"
                )
            except Exception:
                pass

        # Reviewer evaluates → sends to writer
        review_output = await engine._execute_node(
            run, reviewer_id,
            f"Review the following work and either APPROVE or provide specific feedback:\n{writer_output}{cicd_context}",
            to_agent_id=writer_agent,
        )

        # Check for approval or veto
        state = run.nodes[reviewer_id]
        if state.status == NodeStatus.VETOED:
            _finish_sprint(sprint_id, rejected=True, quality=0)
            sprint_id = None
            prev_output = f"[Reviewer feedback, iteration {i+1}]:\n{review_output}"
            if cicd_context:
                prev_output += f"\n[Build/test output from last iteration]:\n{cicd_context}"
            state.status = NodeStatus.PENDING
            run.nodes[writer_id].status = NodeStatus.PENDING
        else:
            _finish_sprint(sprint_id, rejected=False, quality=80)
            sprint_id = None
            break

    # If we exited the loop without approving (max iterations), mark last sprint failed
    if sprint_id:
        _finish_sprint(sprint_id, rejected=False, quality=30)
