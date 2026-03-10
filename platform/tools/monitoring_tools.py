"""
Error Monitoring Tools — wraps ops/error_clustering, error_state, auto_heal
for use by the monitoring-ops agent.

WHY
---
Les appels LLM dans le pipeline de monitoring d'erreurs doivent passer par
le système agents + patterns + tools de la SF — pas être des appels LLM directs
dans ops/. Ces outils exposent les primitives de monitoring au monitoring-ops agent,
qui fait le raisonnement LLM (clustering sémantique, semantic muting) dans son
propre loop via ses outils naturels.

ARCHITECTURE
------------
  auto_heal.py (background daemon)
    └── scan_open_incidents() → cluster() [stages 1+2 only] → should_alert() [sync]

  error-monitoring-cycle.yaml (workflow)
    └── monitoring-ops agent
          ├── monitoring_scan_incidents   → liste les incidents ouverts
          ├── monitoring_cluster_incidents → stages 1+2, retourne clusters + orphelins
          ├── monitoring_get_error_status  → NEW/REGRESSION/ONGOING
          ├── monitoring_should_alert      → décision suppression (exact mutes)
          ├── monitoring_mark_alerted      → enregistre l'alerte
          ├── monitoring_create_heal_epic  → crée un TMA epic + lance le workflow
          ├── monitoring_add_mute          → ajoute une règle de mute
          └── monitoring_list_mutes        → liste les mutes actifs

  Le clustering sémantique des orphelins (Stage 3 dans Airweave) est fait
  par l'agent directement avec son LLM : il reçoit les orphelins et groupe
  naturellement par cause racine dans son raisonnement.

SECURITY — SBD-09 vs SBD-10 conflict resolution (SecureByDesign v1.1):
-----------------------------------------------------------------------
  SBD-09 (Data Minimization) CONFLICTS with SBD-10 (Security Logging).
  Resolution applied here: LOG THE EVENT, NEVER THE CONTENT.

  CORRECT:
    {"event": "error.incident_created", "error_type": "...", "count": 5,
     "severity": "HIGH", "outcome": "heal_epic_triggered"}
    — log THAT the incident happened, not the raw error payload

  NEVER:
    {"event": "error.incident_created", "payload": <full exception trace with PII>}
    — raw traces may contain user data, tokens, internal paths

  Retention: security/ops logs 90 days minimum.
  PII in logs: pseudonymize user_id → hash after 30 days.
  Source: https://github.com/Yems221/securebydesign-llmskill SBD-09/SBD-10
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from .registry import BaseTool

if TYPE_CHECKING:
    from ..models import AgentInstance

logger = logging.getLogger(__name__)


class ScanIncidentsTool(BaseTool):
    """List open platform incidents from the DB."""

    name = "monitoring_scan_incidents"
    description = (
        "List open platform incidents from the DB. "
        "Returns JSON array of incident groups (error_type, count, severity, sample). "
        "Use this first in any error monitoring workflow."
    )
    category = "monitoring"

    async def execute(self, params: dict, agent: "AgentInstance" = None) -> str:
        limit = int(params.get("limit", 50))
        try:
            from ..ops.auto_heal import scan_open_incidents

            groups = scan_open_incidents()
            result = [
                {
                    "error_type": g.error_type,
                    "count": g.count,
                    "severity": g.severity,
                    "source": g.source,
                    "incident_ids": g.incident_ids[:5],
                    "sample": g.error_detail_sample[:200]
                    if g.error_detail_sample
                    else "",
                }
                for g in groups[:limit]
            ]
            return json.dumps({"total": len(groups), "incidents": result})
        except Exception as exc:
            logger.error("monitoring_scan_incidents failed: %s", exc)
            return json.dumps({"error": str(exc), "incidents": []})


class ClusterIncidentsTool(BaseTool):
    """Cluster incident groups by root cause (stages 1+2: strict + regex, no LLM)."""

    name = "monitoring_cluster_incidents"
    description = (
        "Cluster incident groups by root cause using deterministic stages (strict + regex). "
        "Input: JSON array of incidents [{error_type, error_detail, source, severity, id}]. "
        "Returns: {clusters: [...], orphans: [...]}. "
        "Orphans are unclusterable incidents — group them semantically using your own reasoning."
    )
    category = "monitoring"

    async def execute(self, params: dict, agent: "AgentInstance" = None) -> str:
        incidents = params.get("incidents", [])
        if isinstance(incidents, str):
            try:
                incidents = json.loads(incidents)
            except Exception:
                return json.dumps({"error": "incidents must be JSON array"})

        try:
            from ..ops.error_clustering import ErrorClusterer

            clusterer = ErrorClusterer()
            clusters = await clusterer.cluster(incidents)

            # Separate clusters (≥2 incidents) from orphans (single incident)
            grouped = [c for c in clusters if c["count"] >= 2]
            orphans = [c for c in clusters if c["count"] < 2]

            return json.dumps(
                {
                    "clusters": grouped,
                    "orphans": [
                        o["incident_ids"][0] if o["incident_ids"] else ""
                        for o in orphans
                    ],
                    "orphan_details": orphans,
                }
            )
        except Exception as exc:
            logger.error("monitoring_cluster_incidents failed: %s", exc)
            return json.dumps({"error": str(exc), "clusters": [], "orphans": []})


class GetErrorStatusTool(BaseTool):
    """Get the status of an error signature: NEW, REGRESSION, or ONGOING."""

    name = "monitoring_get_error_status"
    description = (
        "Get the status of an error signature: NEW (first time), REGRESSION (was fixed, came back), "
        "ONGOING (known open issue). Input: {signature: str}. "
        "Returns: {status: 'NEW'|'REGRESSION'|'ONGOING', history: {...}}"
    )
    category = "monitoring"

    async def execute(self, params: dict, agent: "AgentInstance" = None) -> str:
        signature = params.get("signature", "")
        if not signature:
            return json.dumps({"error": "signature required"})
        try:
            from ..ops.error_state import get_error_state_manager

            state = get_error_state_manager()
            status = state.determine_status(signature)
            history = state.get_signature(signature) or {}
            return json.dumps({"status": status, "history": history})
        except Exception as exc:
            return json.dumps({"error": str(exc), "status": "NEW"})


class ShouldAlertTool(BaseTool):
    """Decide whether to alert or suppress an error cluster (exact mutes + rules)."""

    name = "monitoring_should_alert"
    description = (
        "Decide whether to alert on an error cluster or suppress it. "
        "Input: {signature, status ('NEW'|'REGRESSION'|'ONGOING'), severity ('S1'|'S2'|'S3'|'S4'), "
        "has_open_ticket: bool}. "
        "Returns: {should_alert: bool, reason: str}. "
        "Note: semantic mute matching (same root cause, different wording) is YOUR responsibility "
        "— compare the signature against monitoring_list_mutes output using your own reasoning."
    )
    category = "monitoring"

    async def execute(self, params: dict, agent: "AgentInstance" = None) -> str:
        signature = params.get("signature", "")
        status = params.get("status", "NEW")
        severity = params.get("severity", "S3")
        has_open_ticket = bool(params.get("has_open_ticket", False))

        try:
            from ..ops.error_state import get_error_state_manager

            state = get_error_state_manager()
            should, reason = state.should_alert(
                signature=signature,
                status=status,
                severity=severity,
                has_open_ticket=has_open_ticket,
            )
            return json.dumps({"should_alert": should, "reason": reason})
        except Exception as exc:
            return json.dumps(
                {"error": str(exc), "should_alert": True, "reason": "error"}
            )


class MarkAlertedTool(BaseTool):
    """Mark an error signature as alerted (starts the 24h suppression window)."""

    name = "monitoring_mark_alerted"
    description = (
        "Mark an error signature as alerted. Starts the 24h suppression window. "
        "Input: {signature: str}. Call after triggering a TMA epic."
    )
    category = "monitoring"

    async def execute(self, params: dict, agent: "AgentInstance" = None) -> str:
        signature = params.get("signature", "")
        try:
            from ..ops.error_state import get_error_state_manager

            get_error_state_manager().mark_alerted(signature)
            return json.dumps({"status": "ok", "signature": signature})
        except Exception as exc:
            return json.dumps({"error": str(exc)})


class CreateHealEpicTool(BaseTool):
    """Create a TMA epic + launch auto-heal workflow for an incident cluster."""

    name = "monitoring_create_heal_epic"
    description = (
        "Create a TMA epic and launch the auto-heal TMA workflow for an incident cluster. "
        "Input: {error_type, error_detail, incident_ids: [str], count: int, severity: str, "
        "source: str, signature: str, error_status: str}. "
        "Returns: {mission_id, session_id}."
    )
    category = "monitoring"

    async def execute(self, params: dict, agent: "AgentInstance" = None) -> str:
        try:
            from ..ops.auto_heal import (
                create_heal_epic,
                launch_tma_workflow,
                IncidentGroup,
            )

            group = IncidentGroup(
                error_type=params.get("error_type", "unknown"),
                error_detail_sample=params.get("error_detail", "")[:200],
                incident_ids=params.get("incident_ids", []),
                count=int(params.get("count", 1)),
                severity=params.get("severity", "P2"),
                source=params.get("source", "monitoring-ops"),
                signature=params.get("signature", ""),
                error_status=params.get("error_status", "NEW"),
            )
            mission_id = create_heal_epic(group)
            session_id = await launch_tma_workflow(mission_id)
            return json.dumps({"mission_id": mission_id, "session_id": session_id})
        except Exception as exc:
            logger.error("monitoring_create_heal_epic failed: %s", exc)
            return json.dumps({"error": str(exc)})


class AddMuteTool(BaseTool):
    """Add a mute rule for an error signature pattern."""

    name = "monitoring_add_mute"
    description = (
        "Add a mute rule to suppress alerts matching this signature for N hours. "
        "Input: {signature: str, hours: int (default 24), reason: str, muted_by: str}."
    )
    category = "monitoring"

    async def execute(self, params: dict, agent: "AgentInstance" = None) -> str:
        signature = params.get("signature", "")
        hours = int(params.get("hours", 24))
        reason = params.get("reason", "")
        muted_by = params.get("muted_by", agent.id if agent else "agent")
        try:
            from ..ops.error_state import get_error_state_manager

            get_error_state_manager().add_mute(
                signature, hours, muted_by=muted_by, reason=reason
            )
            return json.dumps({"status": "ok", "signature": signature, "hours": hours})
        except Exception as exc:
            return json.dumps({"error": str(exc)})


class ListMutesTool(BaseTool):
    """List all active mute rules."""

    name = "monitoring_list_mutes"
    description = (
        "List all active error mute rules. "
        "Returns: {mutes: [{signature, muted_until, reason, muted_by}]}. "
        "Use this to identify mute candidates for semantic matching."
    )
    category = "monitoring"

    async def execute(self, params: dict, agent: "AgentInstance" = None) -> str:
        try:
            from ..ops.error_state import get_error_state_manager

            mutes = get_error_state_manager().get_active_mutes()
            return json.dumps({"mutes": list(mutes.values()) if mutes else []})
        except Exception as exc:
            return json.dumps({"error": str(exc), "mutes": []})


def register_monitoring_tools(registry) -> None:
    registry.register(ScanIncidentsTool())
    registry.register(ClusterIncidentsTool())
    registry.register(GetErrorStatusTool())
    registry.register(ShouldAlertTool())
    registry.register(MarkAlertedTool())
    registry.register(CreateHealEpicTool())
    registry.register(AddMuteTool())
    registry.register(ListMutesTool())
    logger.debug("Monitoring tools registered (8 tools)")
