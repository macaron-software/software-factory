"""Network/debate pattern: agents discuss in rounds, judge decides."""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


async def run_network(engine, run, task: str):
    """Debate/network: agents discuss in rounds, judge decides."""
    from ..engine import NodeStatus

    nodes = engine._ordered_nodes(run.pattern)
    if len(nodes) < 2:
        from .sequential import run_sequential
        return await run_sequential(engine, run, task)

    max_rounds = run.pattern.config.get("max_rounds", 3)

    # Find judge (node with only incoming "report" edges, or last node)
    judge_id = None
    debaters = []
    for node in run.pattern.agents:
        nid = node["id"]
        has_report_to = any(
            e["from"] == nid and e.get("type") == "report"
            for e in run.pattern.edges
        )
        has_bidirectional = any(
            (e["from"] == nid or e["to"] == nid) and e.get("type") == "bidirectional"
            for e in run.pattern.edges
        )
        if has_bidirectional:
            debaters.append(nid)
        elif not has_bidirectional and has_report_to:
            debaters.append(nid)
        else:
            judge_id = nid

    if not judge_id and nodes:
        judge_id = nodes[-1]
    if not debaters:
        debaters = [n for n in nodes if n != judge_id]

    # ── Step 1: Leader brief (hierarchical) ──
    # The judge/PO frames the discussion and assigns each expert
    leader_brief = ""
    debater_names = []
    for did in debaters:
        ns = run.nodes.get(did)
        if ns and ns.agent:
            debater_names.append(f"@{ns.agent.name} ({ns.agent.role or did})")
    team_list = ", ".join(debater_names) if debater_names else "l'équipe"

    if judge_id:
        run.flow_step = "Brief"
        leader_brief = await engine._execute_node(
            run, judge_id,
            f"Tu diriges cette session d'analyse. Voici ton équipe : {team_list}.\n\n"
            f"1. Cadre le sujet en 2-3 phrases\n"
            f"2. Assigne à CHAQUE expert (@mention) ce que tu attends de lui\n"
            f"3. Pose 1-2 questions clés pour orienter la discussion\n\n"
            f"Sujet soumis par le client :\n{task}",
            to_agent_id="all",
        )
        run.nodes[judge_id].status = NodeStatus.PENDING

    # ── Step 2: Debate rounds (network) ──
    # Experts discuss IN PARALLEL — like a real meeting
    prev_round = leader_brief
    for rnd in range(max_rounds):
        run.iteration = rnd + 1
        run.flow_step = "Analyse" if rnd == 0 else f"Débat round {rnd + 1}"

        if rnd == 0:
            prompt_tpl = (
                "Ton responsable a briefé l'équipe (ci-dessous). "
                "Réponds à ce qui te concerne, pose des questions aux collègues (@mention), "
                "et donne ton analyse d'expert.\n\n"
                f"Sujet : {task}"
            )
        else:
            prompt_tpl = (
                "Poursuis la discussion. Réagis aux points soulevés par tes collègues, "
                "réponds à leurs questions, challenge leurs propositions.\n\n"
                f"Sujet : {task}\n\n[Échanges précédents]:\n{prev_round}"
            )

        # All debaters respond in parallel (like a real meeting)
        async def _run_debater(did, prompt, context):
            peers = [d for d in debaters if d != did]
            to = engine._node_agent_id(run, peers[0]) if len(peers) == 1 else "all"
            output = await engine._execute_node(run, did, prompt, context_from=context, to_agent_id=to)
            return f"[{did}]: {output}"

        tasks = [_run_debater(did, prompt_tpl, prev_round) for did in debaters]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        round_outputs = [r if isinstance(r, str) else f"[error]: {r}" for r in results]
        prev_round = "\n\n".join(round_outputs)

    # ── Step 3: Judge synthesis ──
    # PO consolidates all contributions into a decision
    if judge_id:
        run.flow_step = "Synthèse"
        await engine._execute_node(
            run, judge_id,
            f"Synthétise toutes les contributions de ton équipe.\n\n"
            f"1. Résume les points clés de chaque expert\n"
            f"2. Identifie les consensus et les points de désaccord\n"
            f"3. Propose une décision et les prochaines étapes\n\n"
            f"Contributions :\n{prev_round}",
            to_agent_id="all",
        )
