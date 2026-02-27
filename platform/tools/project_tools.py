"""Project lifecycle tools — for the PM / architect agent to pilot project phases and docs.

Architecture First workflow:
  1. scaffold_project creates docs/ templates (spec, schema, workflows, conventions, security)
  2. Agent Architect fills docs/ via update_project_doc
  3. Agent Security fills docs/security.md
  4. PM calls set_project_phase("mvp") → gate checks Architecture + Audit missions done
  5. Dev agents get docs/ injected into context via read_project_doc
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .registry import BaseTool

logger = logging.getLogger(__name__)


class GetProjectHealthTool(BaseTool):
    name = "get_project_health"
    description = (
        "Get a project's health: missions by category, current phase, docs status. "
        "Use to understand current state before making decisions."
    )
    category = "project"
    allowed_roles = []

    async def execute(self, params: dict, agent=None) -> str:
        project_id = params.get("project_id", "")
        try:
            from ..projects.manager import get_project_store
            from ..missions.store import get_mission_store

            proj = get_project_store().get(project_id)
            if not proj:
                return json.dumps({"error": f"Project '{project_id}' not found"})

            missions = get_mission_store().list_missions(limit=500)
            proj_missions = [m for m in missions if m.project_id == proj.id]

            by_cat: dict[str, list] = {"system": [], "functional": [], "custom": []}
            for m in proj_missions:
                cat = getattr(m, "category", None) or "functional"
                by_cat.setdefault(cat, []).append(
                    {
                        "id": m.id,
                        "name": m.name,
                        "type": m.type,
                        "status": m.status,
                        "wsjf": m.wsjf_score,
                    }
                )

            docs_status = {}
            if proj.path:
                docs_dir = Path(proj.path) / "docs"
                for fname in [
                    "spec.md",
                    "schema.md",
                    "workflows.md",
                    "conventions.md",
                    "security.md",
                ]:
                    doc_path = docs_dir / fname
                    if doc_path.exists():
                        content = doc_path.read_text(encoding="utf-8")
                        filled = "🚧 À compléter" not in content and len(content) > 300
                        docs_status[fname] = "filled" if filled else "template"
                    else:
                        docs_status[fname] = "missing"

            total = len(proj_missions)
            active = sum(1 for m in proj_missions if m.status == "active")
            completed = sum(1 for m in proj_missions if m.status == "completed")
            score = round((active * 0.5 + completed) / max(total, 1) * 100)

            return json.dumps(
                {
                    "project_id": proj.id,
                    "name": proj.name,
                    "current_phase": proj.current_phase or "discovery",
                    "health_score": score,
                    "missions": by_cat,
                    "docs": docs_status,
                    "summary": {
                        "total": total,
                        "active": active,
                        "completed": completed,
                        "planning": sum(
                            1 for m in proj_missions if m.status == "planning"
                        ),
                    },
                },
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps({"error": str(e)})


class GetPhaseGateTool(BaseTool):
    name = "get_phase_gate"
    description = (
        "Check if a project can transition to a target phase. "
        "Returns allowed=true/false and blockers. Always call before set_project_phase."
    )
    category = "project"

    async def execute(self, params: dict, agent=None) -> str:
        project_id = params.get("project_id", "")
        target_phase = params.get("target_phase", "mvp")
        try:
            from ..projects.manager import get_project_store

            result = get_project_store().get_phase_gate(project_id, target_phase)
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})


class SetProjectPhaseTool(BaseTool):
    name = "set_project_phase"
    description = (
        "Transition a project to a new lifecycle phase. "
        "Blocked if gate requirements not met. Use force=true only with user approval."
    )
    category = "project"

    async def execute(self, params: dict, agent=None) -> str:
        project_id = params.get("project_id", "")
        phase = params.get("phase", "")
        force = bool(params.get("force", False))
        try:
            from ..projects.manager import get_project_store

            proj = get_project_store().set_phase(project_id, phase, force=force)
            if not proj:
                return json.dumps({"error": "Project not found"})
            return json.dumps(
                {
                    "ok": True,
                    "project_id": proj.id,
                    "name": proj.name,
                    "current_phase": proj.current_phase,
                },
                ensure_ascii=False,
            )
        except ValueError as e:
            return json.dumps({"ok": False, "blocked": True, "error": str(e)})
        except Exception as e:
            return json.dumps({"error": str(e)})


class SuggestNextMissionsTool(BaseTool):
    name = "suggest_next_missions"
    description = (
        "Suggest next missions to create or activate for a project "
        "based on its current phase and health."
    )
    category = "project"

    async def execute(self, params: dict, agent=None) -> str:
        project_id = params.get("project_id", "")
        try:
            from ..projects.manager import get_project_store
            from ..missions.store import get_mission_store

            proj = get_project_store().get(project_id)
            if not proj:
                return json.dumps({"error": "Project not found"})

            missions = get_mission_store().list_missions(limit=500)
            proj_missions = [m for m in missions if m.project_id == proj.id]
            phase = proj.current_phase or "discovery"
            existing_types = {m.type for m in proj_missions}
            existing_status = {m.type: m.status for m in proj_missions}

            suggestions = []
            if phase == "discovery":
                arch_m = next(
                    (m for m in proj_missions if m.type == "architecture"), None
                )
                audit_m = next((m for m in proj_missions if m.type == "audit"), None)
                if not arch_m or arch_m.status not in ("completed", "done"):
                    suggestions.append(
                        {
                            "type": "architecture",
                            "action": "complete",
                            "priority": "CRITIQUE",
                            "reason": "Compléter docs/spec.md, schema.md, workflows.md, conventions.md — bloque le passage en MVP",
                        }
                    )
                if not audit_m or audit_m.status not in ("completed", "done"):
                    suggestions.append(
                        {
                            "type": "audit",
                            "action": "complete",
                            "priority": "CRITIQUE",
                            "reason": "Compléter docs/security.md — bloque le passage en MVP",
                        }
                    )
                if (
                    arch_m
                    and audit_m
                    and all(
                        m.status in ("completed", "done") for m in [arch_m, audit_m]
                    )
                ):
                    suggestions.append(
                        {
                            "type": "phase_transition",
                            "action": "set_project_phase",
                            "target": "mvp",
                            "priority": "HIGH",
                            "reason": "Gate satisfait — prêt pour MVP",
                        }
                    )
            elif phase == "mvp":
                if "feature" not in existing_types:
                    suggestions.append(
                        {
                            "type": "feature",
                            "action": "create",
                            "priority": "HIGH",
                            "reason": "Créer missions features depuis docs/spec.md",
                        }
                    )
                if existing_status.get("security") == "planning":
                    suggestions.append(
                        {
                            "type": "security",
                            "action": "activate",
                            "priority": "HIGH",
                            "reason": "Activer audit sécurité continu",
                        }
                    )
            elif phase in ("v1", "run"):
                for m in proj_missions:
                    if (
                        getattr(m, "category", None) == "system"
                        and m.status == "planning"
                    ):
                        suggestions.append(
                            {
                                "type": m.type,
                                "name": m.name,
                                "action": "activate",
                                "priority": "MEDIUM",
                                "reason": f"Phase {phase} — activer {m.name}",
                            }
                        )

            return json.dumps(
                {"project_id": project_id, "phase": phase, "suggestions": suggestions},
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps({"error": str(e)})


class ReadProjectDocTool(BaseTool):
    name = "read_project_doc"
    description = (
        "Read a doc from the project's docs/ folder (spec, schema, workflows, conventions, security). "
        "Use to understand the architecture before coding."
    )
    category = "project"

    async def execute(self, params: dict, agent=None) -> str:
        project_id = params.get("project_id", "")
        filename = params.get("filename", "spec.md")
        try:
            from ..projects.manager import get_project_store

            proj = get_project_store().get(project_id)
            if not proj or not proj.path:
                return json.dumps({"error": "Project not found or no workspace"})
            doc_path = Path(proj.path) / "docs" / filename
            if not doc_path.exists():
                return json.dumps(
                    {"error": f"docs/{filename} missing — run scaffold first"}
                )
            content = doc_path.read_text(encoding="utf-8")
            return json.dumps(
                {
                    "filename": filename,
                    "content": content,
                    "filled": "🚧 À compléter" not in content,
                },
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps({"error": str(e)})


class UpdateProjectDocTool(BaseTool):
    name = "update_project_doc"
    description = (
        "Write or update a doc in the project's docs/ folder. "
        "Use to fill spec.md, schema.md, workflows.md, conventions.md or security.md."
    )
    category = "project"

    async def execute(self, params: dict, agent=None) -> str:
        project_id = params.get("project_id", "")
        filename = params.get("filename", "")
        content = params.get("content", "")
        try:
            from ..projects.manager import get_project_store

            proj = get_project_store().get(project_id)
            if not proj or not proj.path:
                return json.dumps({"error": "Project not found or no workspace"})
            docs_dir = Path(proj.path) / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            doc_path = docs_dir / filename
            doc_path.write_text(content, encoding="utf-8")
            logger.info(
                "update_project_doc: wrote docs/%s for %s", filename, project_id
            )
            return json.dumps(
                {
                    "ok": True,
                    "filename": filename,
                    "bytes": len(content.encode()),
                    "path": str(doc_path),
                },
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps({"error": str(e)})


def register_project_tools(registry):
    """Register all project lifecycle tools."""
    registry.register(GetProjectHealthTool())
    registry.register(GetPhaseGateTool())
    registry.register(SetProjectPhaseTool())
    registry.register(SuggestNextMissionsTool())
    registry.register(ReadProjectDocTool())
    registry.register(UpdateProjectDocTool())
