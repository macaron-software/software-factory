"""Loop pattern: writer/reviewer iterate until approval."""
from __future__ import annotations


async def run_loop(engine, run, task: str):
    """Loop between writer and reviewer until approval or max iterations."""
    from ..engine import NodeStatus

    nodes = engine._ordered_nodes(run.pattern)
    if len(nodes) < 2:
        from .sequential import run_sequential
        return await run_sequential(engine, run, task)

    writer_id = nodes[0]
    reviewer_id = nodes[1]
    writer_agent = engine._node_agent_id(run, writer_id)
    reviewer_agent = engine._node_agent_id(run, reviewer_id)

    prev_output = ""
    for i in range(run.max_iterations):
        run.iteration = i + 1

        # Writer produces → sends to reviewer
        writer_output = await engine._execute_node(
            run, writer_id, task, context_from=prev_output,
            to_agent_id=reviewer_agent,
        )

        # Reviewer evaluates → sends to writer
        review_output = await engine._execute_node(
            run, reviewer_id,
            f"Review the following work and either APPROVE or provide specific feedback:\n{writer_output}",
            to_agent_id=writer_agent,
        )

        # Check for approval or veto
        state = run.nodes[reviewer_id]
        if state.status == NodeStatus.VETOED:
            prev_output = f"[Reviewer feedback, iteration {i+1}]:\n{review_output}"
            state.status = NodeStatus.PENDING
            run.nodes[writer_id].status = NodeStatus.PENDING
        else:
            break
