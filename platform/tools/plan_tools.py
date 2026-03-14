"""Agent Plan Tools — TodoList middleware for agent task planning (inspired by DeerFlow).

Allows agents to externalize their execution plan before tackling complex tasks.
Plans are stored in DB, visible in dashboard, and updated in real-time.
"""
# Ref: feat-backlog

from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone

from ..models import AgentInstance
from .registry import BaseTool

logger = logging.getLogger(__name__)


def _db():
    from ..db.migrations import get_db

    return get_db()


class PlanCreateTool(BaseTool):
    name = "plan_create"
    description = "Create an execution plan before tackling a complex task. List all steps you will take."
    category = "planning"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        return "Error: plan_create must be called via executor"


class PlanUpdateTool(BaseTool):
    name = "plan_update"
    description = "Update the status of a plan step (in_progress, done, blocked)."
    category = "planning"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        return "Error: plan_update must be called via executor"


class PlanGetTool(BaseTool):
    name = "plan_get"
    description = "Get the current plan and step statuses."
    category = "planning"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        return "Error: plan_get must be called via executor"


def register_plan_tools(registry):
    registry.register(PlanCreateTool())
    registry.register(PlanUpdateTool())
    registry.register(PlanGetTool())


async def _tool_plan_create(args: dict, ctx) -> str:
    """Create a new agent plan with steps."""
    title = args.get("title", "Execution Plan")
    steps = args.get("steps", [])
    if not steps:
        return "Error: steps list is required"

    plan_id = str(uuid.uuid4())[:12]
    db = _db()
    now = datetime.now(timezone.utc).isoformat()
    try:
        db.execute(
            "INSERT INTO agent_plans (id, session_id, project_id, agent_id, title, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
            (
                plan_id,
                ctx.session_id,
                ctx.project_id or "",
                ctx.agent.id,
                title,
                now,
                now,
            ),
        )
        for i, step in enumerate(steps):
            step_id = f"{plan_id}-{i + 1}"
            desc = step if isinstance(step, str) else step.get("description", str(step))
            db.execute(
                "INSERT INTO agent_plan_steps (id, plan_id, step_num, description, status, updated_at) VALUES (?,?,?,?,?,?)",
                (step_id, plan_id, i + 1, desc, "pending", now),
            )
        # Persist plan_id in ctx for subsequent plan_update calls
        ctx._active_plan_id = plan_id
        lines = [f"Plan created: {title} [{plan_id}]"]
        for i, step in enumerate(steps):
            desc = step if isinstance(step, str) else step.get("description", str(step))
            lines.append(f"  {i + 1}. [ ] {desc}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error creating plan: {e}"


async def _tool_plan_update(args: dict, ctx) -> str:
    """Update a step status in the active plan."""
    step_num = args.get("step")
    status = args.get("status", "done")
    result_text = args.get("result", "")
    plan_id = getattr(ctx, "_active_plan_id", None) or args.get("plan_id")

    if not plan_id:
        return "Error: no active plan. Call plan_create first."
    if step_num is None:
        return "Error: step number required"

    valid_statuses = {"pending", "in_progress", "done", "blocked", "skipped"}
    if status not in valid_statuses:
        return f"Error: status must be one of {valid_statuses}"

    now = datetime.now(timezone.utc).isoformat()
    db = _db()
    try:
        db.execute(
            "UPDATE agent_plan_steps SET status=?, result=?, updated_at=? WHERE plan_id=? AND step_num=?",
            (status, result_text or None, now, plan_id, int(step_num)),
        )
        db.execute("UPDATE agent_plans SET updated_at=? WHERE id=?", (now, plan_id))
        icon = {"done": "x", "in_progress": ">", "blocked": "!", "skipped": "-"}.get(
            status, " "
        )
        return f"Step {step_num} [{icon}] {status}"
    except Exception as e:
        return f"Error updating plan: {e}"


async def _tool_plan_get(args: dict, ctx) -> str:
    """Get the current plan status."""
    plan_id = getattr(ctx, "_active_plan_id", None) or args.get("plan_id")
    if not plan_id:
        return "No active plan."

    db = _db()
    try:
        plan = db.execute("SELECT * FROM agent_plans WHERE id=?", (plan_id,)).fetchone()
        if not plan:
            return f"Plan {plan_id} not found."
        steps = db.execute(
            "SELECT * FROM agent_plan_steps WHERE plan_id=? ORDER BY step_num",
            (plan_id,),
        ).fetchall()
        lines = [f"Plan: {plan['title']} [{plan_id}]"]
        for s in steps:
            icon = {
                "done": "x",
                "in_progress": ">",
                "blocked": "!",
                "skipped": "-",
            }.get(s["status"], " ")
            result_note = f" — {s['result'][:60]}" if s.get("result") else ""
            lines.append(f"  {s['step_num']}. [{icon}] {s['description']}{result_note}")
        done = sum(1 for s in steps if s["status"] == "done")
        lines.append(f"Progress: {done}/{len(steps)}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error getting plan: {e}"
