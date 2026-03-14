"""Human-in-the-loop pattern: agents work with human validation checkpoints."""
from __future__ import annotations
# Ref: feat-patterns


async def run_human_in_the_loop(engine, run, task: str):
    """Human-in-the-loop: agents work, with human validation checkpoints.

    Checkpoint edges mark where human validation is required.
    Inserts a system message and SSE event for the UI to show a validation prompt,
    then raises WorkflowPaused to actually halt the workflow until the human resumes.
    """
    from ..engine import _sse, WorkflowPaused
    from ...sessions.store import get_session_store, MessageDef
    from ...config import get_config

    # Read yolo_mode dynamically at each checkpoint (not once at start)
    def _is_yolo() -> bool:
        return get_config().orchestrator.yolo_mode

    nodes = engine._ordered_nodes(run.pattern)
    if not nodes:
        return

    store = get_session_store()

    # Find checkpoint edges
    checkpoint_sources = {
        e["from"] for e in run.pattern.edges if e.get("type") == "checkpoint"
    }

    prev_output = ""
    for i, nid in enumerate(nodes):
        ns = run.nodes.get(nid)

        # Skip "human" placeholder nodes (no agent_id)
        if ns and not ns.agent_id:
            checkpoint_msg = run.pattern.config.get(
                "checkpoint_message",
                "Point de contrôle — En attente de votre validation."
            )
            store.add_message(MessageDef(
                session_id=run.session_id,
                from_agent="system",
                to_agent="user",
                message_type="system",
                content=f"**CHECKPOINT HUMAIN**\n\n{checkpoint_msg}\n\n"
                        f"_Résumé du travail effectué :_\n{prev_output[:500]}\n\n"
                        f"▶️ Utilisez **Reprendre** pour valider et continuer le workflow.",
            ))
            await _sse(run, {
                "type": "checkpoint",
                "content": checkpoint_msg,
                "requires_input": True,
            })
            run.flow_step = "Checkpoint humain — en attente"
            # YOLO mode: auto-approve, just log the checkpoint and continue
            if _yolo:
                store.add_message(MessageDef(
                    session_id=run.session_id,
                    from_agent="system",
                    to_agent="user",
                    message_type="system",
                    content=f"**CHECKPOINT AUTO-APPROUVÉ** _(YOLO mode activé)_\n\n{checkpoint_msg}",
                ))
                continue
            # Pause the workflow — the human must explicitly resume it
            raise WorkflowPaused(checkpoint_msg=checkpoint_msg, phase_index=0)

        to_agent = "all"
        if i + 1 < len(nodes):
            next_ns = run.nodes.get(nodes[i + 1])
            if next_ns and next_ns.agent_id:
                to_agent = next_ns.agent_id

        output = await engine._execute_node(
            run, nid, task, context_from=prev_output, to_agent_id=to_agent,
        )
        prev_output = output

        # Insert checkpoint after this node if it has a checkpoint edge
        if nid in checkpoint_sources:
            store.add_message(MessageDef(
                session_id=run.session_id,
                from_agent="system",
                to_agent="user",
                message_type="system",
                content=f"**VALIDATION REQUISE**\n\n"
                        f"L'agent a terminé son travail. Validez ou demandez des corrections.\n\n"
                        f"_Résultat :_\n{output[:500]}\n\n"
                        f"▶️ Utilisez **Reprendre** pour valider et continuer le workflow.",
            ))
            await _sse(run, {
                "type": "checkpoint",
                "content": "Validation humaine requise",
                "requires_input": True,
            })
            # YOLO mode: auto-approve checkpoint edge
            if _yolo:
                store.add_message(MessageDef(
                    session_id=run.session_id,
                    from_agent="system",
                    to_agent="user",
                    message_type="system",
                    content=f"**VALIDATION AUTO-APPROUVÉE** _(YOLO mode activé)_\n\n_Résultat :_\n{output[:500]}",
                ))
                continue
            # Pause the workflow — the human must explicitly resume it
            raise WorkflowPaused(checkpoint_msg="Validation humaine requise", phase_index=0)
