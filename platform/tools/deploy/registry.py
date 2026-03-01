"""
Deploy Target Registry.

Loads named deploy targets from the DB (deploy_targets table).
Always provides a built-in "docker-local" fallback.
"""

from __future__ import annotations

import json
import logging

from .base import DeployTarget
from .docker_local import DockerLocalTarget

logger = logging.getLogger(__name__)

# Driver name → class mapping (extended at import time for optional drivers)
_DRIVERS: dict[str, type[DeployTarget]] = {
    "docker_local": DockerLocalTarget,
}

try:
    from .ssh_docker import SshDockerTarget
    _DRIVERS["ssh_docker"] = SshDockerTarget
except ImportError:
    pass

try:
    from .aws_ecs import AwsEcsTarget
    _DRIVERS["aws_ecs"] = AwsEcsTarget
except ImportError:
    pass

try:
    from .azure_aca import AzureAcaTarget
    _DRIVERS["azure_aca"] = AzureAcaTarget
except ImportError:
    pass

try:
    from .gcp_cloudrun import GcpCloudRunTarget
    _DRIVERS["gcp_cloudrun"] = GcpCloudRunTarget
except ImportError:
    pass

try:
    from .k8s import K8sTarget
    _DRIVERS["k8s"] = K8sTarget
except ImportError:
    pass


# Builtin singleton
_DOCKER_LOCAL = DockerLocalTarget(name="docker-local")


def get_target(name: str | None = None) -> DeployTarget:
    """
    Return a deploy target by name.

    Looks up the name in the deploy_targets DB table.
    Falls back to the builtin docker-local target if name is None or not found.
    """
    if not name or name == "docker-local":
        return _DOCKER_LOCAL

    try:
        from ...db.adapter import get_connection
        conn = get_connection()
        row = conn.execute(
            "SELECT driver, config_json FROM deploy_targets WHERE name = ?", (name,)
        ).fetchone()
        if row:
            driver_name, config_json = row
            config = json.loads(config_json or "{}")
            cls = _DRIVERS.get(driver_name)
            if cls:
                return cls(name=name, config=config)
            logger.warning("Unknown deploy driver %r for target %r, using docker-local", driver_name, name)
    except Exception as e:
        logger.warning("Error loading deploy target %r: %s", name, e)

    return _DOCKER_LOCAL


def list_targets() -> list[dict]:
    """Return all targets from DB plus the builtin docker-local."""
    targets = [
        {
            "id": "docker-local",
            "name": "docker-local",
            "driver": "docker_local",
            "label": "Docker Local (builtin)",
            "status": "ok",
            "is_default": True,
            "config_json": "{}",
        }
    ]
    try:
        from ...db.adapter import get_connection
        conn = get_connection()
        rows = conn.execute(
            "SELECT id, name, driver, config_json, status, is_default FROM deploy_targets ORDER BY name"
        ).fetchall()
        for row in rows:
            driver_cls = _DRIVERS.get(row[2])
            targets.append({
                "id": row[0],
                "name": row[1],
                "driver": row[2],
                "label": driver_cls.label if driver_cls else row[2],
                "config_json": row[3],
                "status": row[4],
                "is_default": bool(row[5]),
            })
    except Exception as e:
        logger.warning("Error listing deploy targets: %s", e)

    return targets


def register_target(name: str, driver: str, config: dict, target_id: str | None = None) -> str:
    """
    Create or update a deploy target in the DB.
    Returns the target ID.
    """
    import uuid
    from ...db.adapter import get_connection

    tid = target_id or str(uuid.uuid4())
    config_json = json.dumps(config)
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO deploy_targets (id, name, driver, config_json, status)
        VALUES (?, ?, ?, ?, 'unknown')
        ON CONFLICT(name) DO UPDATE SET
            driver = excluded.driver,
            config_json = excluded.config_json,
            status = 'unknown',
            updated_at = CURRENT_TIMESTAMP
        """,
        (tid, name, driver, config_json),
    )
    conn.commit()
    return tid


def available_drivers() -> list[dict]:
    """Return all registered driver classes with their config schema."""
    return [
        {
            "driver": cls.driver,
            "label": cls.label,
            "config_schema": cls.config_schema,
        }
        for cls in _DRIVERS.values()
    ]
