"""Feedback loops — automated reactions to mission lifecycle events.

- deploy_completed: activate TMA mission for the project
- tma_recurring: create tech debt item after 3+ occurrences of same incident
- security_alert: create priority bug for critical CVE
- Reaction engine integration for CI/deploy/agent events
"""

from __future__ import annotations

import logging

from ..interfaces import EventPayload, ReactionEvent

logger = logging.getLogger(__name__)


def emit_reaction(
    event: ReactionEvent, project_id: str, session_id: str = "", mission_id: str = "", **details
) -> None:
    """Fire a reaction event (non-blocking). Used by deploy/CI/agent code."""
    import asyncio

    from ..reactions import get_reaction_engine

    engine = get_reaction_engine()
    payload = EventPayload(
        event=event,
        project_id=project_id,
        session_id=session_id,
        mission_id=mission_id,
        details=details,
    )
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(engine.emit(payload))
    except RuntimeError:
        pass  # No event loop — skip


def on_deploy_completed(project_id: str, epic_mission_id: str):
    """Post-deploy: activate the project's TMA mission and link it to the deployed epic."""
    from .store import get_mission_store

    ms = get_mission_store()
    missions = ms.list_missions(project_id=project_id)

    tma = next(
        (
            m
            for m in missions
            if m.type == "program"
            and (m.config or {}).get("auto_provisioned")
            and "tma" in m.workflow_id.lower()
        ),
        None,
    )
    if tma and tma.status != "active":
        tma.status = "active"
        tma.config = {**(tma.config or {}), "last_epic": epic_mission_id}
        ms.update_mission(tma)
        logger.info(
            "Activated TMA mission %s for project %s after deploy of %s",
            tma.id,
            project_id,
            epic_mission_id,
        )
        emit_reaction(
            ReactionEvent.DEPLOY_SUCCESS,
            project_id,
            mission_id=epic_mission_id,
            message="Deploy completed, TMA activated",
        )
        return tma

    # Also activate security mission if still in planning
    secu = next(
        (m for m in missions if m.type == "security" and (m.config or {}).get("auto_provisioned")),
        None,
    )
    if secu and secu.status == "planning":
        secu.status = "active"
        ms.update_mission(secu)
        logger.info("Activated security mission %s for project %s", secu.id, project_id)

    return tma


def on_tma_incident_fixed(project_id: str, incident_key: str):
    """Track recurring incidents. After 3+ fixes for the same key, create a debt reduction item."""
    from .store import MissionDef, get_mission_store

    ms = get_mission_store()
    missions = ms.list_missions(project_id=project_id)

    # Find debt mission
    debt = next(
        (m for m in missions if m.type == "debt" and (m.config or {}).get("auto_provisioned")), None
    )
    if not debt:
        return None

    # Track occurrences in debt mission config
    config = dict(debt.config or {})
    incidents = config.get("recurring_incidents", {})
    count = incidents.get(incident_key, 0) + 1
    incidents[incident_key] = count
    config["recurring_incidents"] = incidents
    debt.config = config
    ms.update_mission(debt)

    if count >= 3:
        # Create a child mission for root cause fix
        fix_mission = MissionDef(
            name=f"Fix racine: {incident_key}",
            description=f"Incident récurrent ({count}x): {incident_key}. Corriger la cause racine au lieu de patcher.",
            goal=f"Éliminer la récurrence de l'incident {incident_key}.",
            status="planning",
            type="debt",
            project_id=project_id,
            workflow_id="sf-pipeline",
            parent_mission_id=debt.id,
            wsjf_score=15,  # High priority for recurring issues
            created_by="responsable_tma",
            config={"auto_created": True, "incident_key": incident_key, "occurrences": count},
        )
        fix_mission = ms.create_mission(fix_mission)
        logger.info(
            "Created root-cause fix mission %s for recurring incident %s (%dx)",
            fix_mission.id,
            incident_key,
            count,
        )
        return fix_mission

    return None


def create_platform_incident(
    title: str,
    severity: str = "P3",
    source: str = "pipeline",
    error_type: str = "",
    error_detail: str = "",
    mission_id: str = "",
    agent_id: str = "",
    project_id: str = "",
) -> str:
    """Insert a row into platform_incidents. Returns incident id."""
    import uuid

    from ..db.migrations import get_db

    inc_id = str(uuid.uuid4())[:12]
    try:
        db = get_db()
        db.execute(
            "INSERT INTO platform_incidents "
            "(id, title, severity, status, source, error_type, error_detail, mission_id, agent_id) "
            "VALUES (?, ?, ?, 'open', ?, ?, ?, ?, ?)",
            (
                inc_id,
                title[:200],
                severity,
                source,
                error_type[:100],
                error_detail[:2000],
                mission_id,
                agent_id,
            ),
        )
        db.commit()
        logger.info("Created platform_incident %s: %s (%s)", inc_id, title[:80], severity)
    except Exception as exc:
        logger.warning("Failed to create platform_incident: %s", exc)
    return inc_id


def on_phase_failed(
    mission_id: str,
    phase_name: str,
    phase_error: str,
    project_id: str = "",
    agent_id: str = "",
):
    """Create a platform_incident when any pipeline phase fails."""
    severity = (
        "P2" if any(k in phase_name.lower() for k in ("deploy", "prod", "security")) else "P3"
    )
    create_platform_incident(
        title=f"Phase failed: {phase_name}",
        severity=severity,
        source="orchestrator",
        error_type="phase_failure",
        error_detail=f"Mission {mission_id}, phase «{phase_name}»: {phase_error[:500]}",
        mission_id=mission_id,
        agent_id=agent_id,
        project_id=project_id,
    )


def on_deploy_failed(project_id: str, epic_mission_id: str, error: str = ""):
    """Post-deploy failure: create a TMA incident ticket with error details."""
    from .store import MissionDef, get_mission_store

    ms = get_mission_store()
    missions = ms.list_missions(project_id=project_id)

    # Find TMA mission, activate it
    tma = next(
        (
            m
            for m in missions
            if m.type == "program"
            and (m.config or {}).get("auto_provisioned")
            and "tma" in m.workflow_id.lower()
        ),
        None,
    )
    if tma and tma.status != "active":
        tma.status = "active"
        ms.update_mission(tma)

    # Create platform_incident DB entry
    create_platform_incident(
        title=f"Deploy failure: {error[:80]}",
        severity="P2",
        source="deploy_pipeline",
        error_type="deploy_failure",
        error_detail=f"Docker deployment failed for mission {epic_mission_id}.\n{error[:1000]}",
        mission_id=epic_mission_id,
        project_id=project_id,
    )

    # Create incident bug mission
    incident = MissionDef(
        name=f"Deploy failure: {error[:80]}",
        description=f"Docker deployment failed for mission {epic_mission_id}.\nError: {error[:500]}",
        goal="Fix the deployment error and redeploy successfully.",
        status="active",
        type="bug",
        project_id=project_id,
        workflow_id="sf-pipeline",
        parent_mission_id=tma.id if tma else None,
        wsjf_score=18,
        created_by="deploy_pipeline",
        config={"auto_created": True, "deploy_error": True, "source_mission": epic_mission_id},
    )
    incident = ms.create_mission(incident)
    logger.info("Created deploy failure incident %s for project %s", incident.id, project_id)
    emit_reaction(
        ReactionEvent.DEPLOY_FAILED,
        project_id,
        mission_id=epic_mission_id,
        message=f"Deploy failed: {error[:200]}",
    )
    return incident


def on_security_alert(
    project_id: str, cve_id: str, severity: str = "critical", description: str = ""
):
    """Create a priority bug mission for critical security vulnerabilities."""
    if severity.lower() not in ("critical", "high"):
        return None

    from .store import MissionDef, get_mission_store

    ms = get_mission_store()

    # Check if already tracked
    missions = ms.list_missions(project_id=project_id)
    existing = [m for m in missions if m.type == "bug" and (m.config or {}).get("cve_id") == cve_id]
    if existing:
        return existing[0]

    wsjf = 20 if severity.lower() == "critical" else 15
    bug = MissionDef(
        name=f"CVE {cve_id} — {severity.upper()}",
        description=description
        or f"Vulnérabilité {severity} détectée: {cve_id}. Correction urgente requise.",
        goal=f"Corriger la vulnérabilité {cve_id} et valider par scan de sécurité.",
        status="active",
        type="bug",
        project_id=project_id,
        workflow_id="sf-pipeline",
        wsjf_score=wsjf,
        created_by="devsecops",
        config={"auto_created": True, "cve_id": cve_id, "severity": severity},
    )
    bug = ms.create_mission(bug)
    logger.info(
        "Created security bug %s for %s (%s) in project %s", bug.id, cve_id, severity, project_id
    )
    return bug
