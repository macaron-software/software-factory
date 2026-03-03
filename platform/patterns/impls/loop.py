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
            prev_output = f"[Reviewer feedback, iteration {i+1}]:\n{review_output}"
            if cicd_context:
                prev_output += f"\n[Build/test output from last iteration]:\n{cicd_context}"
            state.status = NodeStatus.PENDING
            run.nodes[writer_id].status = NodeStatus.PENDING
        else:
            break
