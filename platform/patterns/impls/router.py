"""Router pattern: first agent routes to best specialist."""
from __future__ import annotations


async def run_router(engine, run, task: str):
    """Router: first agent analyzes input and routes to the best specialist.

    Flow: Router classifies → picks one specialist → specialist executes → reports back.
    """
    nodes = engine._ordered_nodes(run.pattern)
    if len(nodes) < 2:
        from .sequential import run_sequential
        return await run_sequential(engine, run, task)

    router_id = nodes[0]
    specialist_ids = nodes[1:]
    router_agent = engine._node_agent_id(run, router_id)

    # Build specialist roster
    specialist_roster = []
    for sid in specialist_ids:
        ns = run.nodes.get(sid)
        if ns and ns.agent:
            specialist_roster.append(f"- [{sid}] {ns.agent.name} ({ns.agent.role})")
        else:
            specialist_roster.append(f"- [{sid}] (unknown)")
    roster_text = "\n".join(specialist_roster)

    # Router classifies and picks
    run.flow_step = "Routing"
    router_output = await engine._execute_node(
        run, router_id,
        f"Analyse la demande et choisis le spécialiste le plus qualifié.\n\n"
        f"Spécialistes disponibles :\n{roster_text}\n\n"
        f"Réponds avec exactement [ROUTE: <node_id>] pour indiquer ton choix, "
        f"puis explique brièvement pourquoi.\n\n"
        f"Demande :\n{task}",
        to_agent_id="all",
    )

    # Parse route decision
    chosen_id = None
    for sid in specialist_ids:
        if f"[ROUTE: {sid}]" in router_output or f"[ROUTE:{sid}]" in router_output:
            chosen_id = sid
            break
    if not chosen_id:
        chosen_id = specialist_ids[0]

    # Execute chosen specialist
    run.flow_step = f"Exécution ({chosen_id})"
    await engine._execute_node(
        run, chosen_id, task, context_from=router_output,
        to_agent_id=router_agent,
    )
