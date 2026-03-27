"""DAG visualization API — convert workflow definitions to graph data (nodes + edges).

Endpoints:
  GET /api/workflows/<id>/dag   — returns {nodes: [...], edges: [...]} for rendering
  GET /api/workflows/<id>/dag/svg — returns SVG text representation
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["dag"])
logger = logging.getLogger(__name__)


def _workflow_to_dag(workflow: dict) -> dict:
    """Convert a workflow definition to DAG format (nodes + edges)."""
    phases = workflow.get("phases", [])
    if not phases:
        return {"nodes": [], "edges": [], "workflow_id": workflow.get("id", "?")}

    nodes = []
    edges = []

    for i, phase in enumerate(phases):
        phase_id = phase.get("id") or phase.get("name", f"phase-{i}")
        node = {
            "id": phase_id,
            "label": phase.get("name", phase_id),
            "type": phase.get("type", "task"),
            "agent": phase.get("agent", ""),
            "status": phase.get("status", "pending"),
            "order": i,
        }
        nodes.append(node)

        # Sequential edges (default)
        if i > 0:
            prev_id = phases[i - 1].get("id") or phases[i - 1].get("name", f"phase-{i - 1}")
            edge = {"from": prev_id, "to": phase_id, "type": "sequence"}
            edges.append(edge)

        # Conditional edges (from depends_on or conditions)
        depends = phase.get("depends_on", [])
        if isinstance(depends, str):
            depends = [depends]
        for dep in depends:
            edge = {"from": dep, "to": phase_id, "type": "dependency"}
            edges.append(edge)

        # Condition edges
        conditions = phase.get("conditions", {})
        if isinstance(conditions, dict):
            on_success = conditions.get("on_success")
            on_failure = conditions.get("on_failure")
            if on_success:
                edges.append({"from": phase_id, "to": on_success, "type": "success"})
            if on_failure:
                edges.append({"from": phase_id, "to": on_failure, "type": "failure"})

    return {
        "workflow_id": workflow.get("id", "?"),
        "workflow_name": workflow.get("name", "?"),
        "nodes": nodes,
        "edges": edges,
        "total_phases": len(nodes),
    }


def _dag_to_ascii(dag: dict) -> str:
    """Render a DAG as ASCII art."""
    nodes = dag.get("nodes", [])
    if not nodes:
        return "(empty workflow)"

    lines = []
    lines.append(f"  Workflow: {dag.get('workflow_name', '?')}")
    lines.append(f"  Phases: {dag.get('total_phases', 0)}")
    lines.append("")

    max_label = max(len(n["label"]) for n in nodes)
    box_w = max(max_label + 4, 20)

    for i, node in enumerate(nodes):
        label = node["label"]
        agent = node.get("agent", "")
        status_map = {"completed": "+", "running": ">", "failed": "!", "pending": " "}
        status_char = status_map.get(node.get("status", ""), " ")

        top = "+" + "-" * box_w + "+"
        mid = f"|{status_char} {label:<{box_w - 3}}|"
        if agent:
            agent_line = f"|  [{agent}]{' ' * max(0, box_w - len(agent) - 5)}|"
        else:
            agent_line = "|" + " " * box_w + "|"
        bot = "+" + "-" * box_w + "+"

        lines.append(f"  {top}")
        lines.append(f"  {mid}")
        lines.append(f"  {agent_line}")
        lines.append(f"  {bot}")

        if i < len(nodes) - 1:
            arrow = "|"
            lines.append(f"  {' ' * (box_w // 2)}{arrow}")
            lines.append(f"  {' ' * (box_w // 2)}v")

    return "\n".join(lines)


@router.get("/api/workflows/{workflow_id}/dag")
async def get_workflow_dag(workflow_id: str):
    """Return workflow as DAG nodes + edges for visualization."""
    try:
        from platform.workflows.store import get_workflow

        wf = get_workflow(workflow_id)
        if not wf:
            raise HTTPException(404, f"Workflow not found: {workflow_id}")
        wf_dict = wf if isinstance(wf, dict) else wf.__dict__
    except ImportError:
        # Fallback: try loading from YAML
        try:
            from platform.workflows.yaml_loader import load_yaml_workflows

            all_wf = load_yaml_workflows()
            wf_dict = None
            for w in all_wf:
                wd = w if isinstance(w, dict) else w.__dict__
                if wd.get("id") == workflow_id:
                    wf_dict = wd
                    break
            if not wf_dict:
                raise HTTPException(404, f"Workflow not found: {workflow_id}")
        except ImportError:
            raise HTTPException(500, "Workflow store not available")

    return _workflow_to_dag(wf_dict)


@router.get("/api/workflows/{workflow_id}/dag/ascii")
async def get_workflow_dag_ascii(workflow_id: str):
    """Return workflow DAG as ASCII art."""
    dag_data = await get_workflow_dag(workflow_id)
    ascii_art = _dag_to_ascii(dag_data)
    return {"workflow_id": workflow_id, "ascii": ascii_art}
