"""
Infisical Tools — Secrets Vault for Agents
============================================
Agents can read, list, and rotate secrets via Infisical.
Write operations require the agent to have the 'secrets_manager' role.

All tools are read-mostly and safe by default:
- get_secret: read a single secret value (redacted in logs)
- list_secrets: list secret NAMES only (never values)
- set_secret: create/update a secret (requires elevated role)
- rotate_secret: re-generate a secret (requires elevated role)
"""
# Ref: feat-settings

from __future__ import annotations

import logging
import os

from ..models import AgentInstance
from .registry import BaseTool

log = logging.getLogger(__name__)

_WRITE_ROLES = {"secrets_manager", "devops", "security", "admin"}


def _get_client():
    """Return an authenticated InfisicalClient or raise."""
    token = os.environ.get("INFISICAL_TOKEN")
    if not token:
        raise RuntimeError(
            "INFISICAL_TOKEN not set. Add it to .env or set INFISICAL_TOKEN env var."
        )
    from infisical import InfisicalClient  # type: ignore

    site_url = os.environ.get("INFISICAL_SITE_URL", "https://app.infisical.com")
    return InfisicalClient(token=token, site_url=site_url)


def _default_env() -> str:
    return os.environ.get("INFISICAL_ENVIRONMENT", "dev")


class InfisicalGetSecretTool(BaseTool):
    name = "infisical_get_secret"
    description = (
        "Retrieve a single secret value from the Infisical vault. "
        "Use to fetch API keys, tokens, or credentials needed for a task. "
        "Params: name (str, required), environment (str, optional: dev/staging/prod), "
        "path (str, optional, default '/'). "
        "Returns the secret value. Never log or expose the returned value."
    )
    category = "security"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        name = params.get("name", "").strip()
        if not name:
            return "Error: 'name' is required."
        environment = params.get("environment", _default_env())
        path = params.get("path", "/")
        try:
            client = _get_client()
            secret = client.get_secret(
                secret_name=name,
                environment=environment,
                path=path,
            )
            log.info("infisical_get_secret: retrieved %s (env=%s)", name, environment)
            return secret.secret_value
        except Exception as e:
            return f"Error retrieving secret '{name}': {e}"


class InfisicalListSecretsTool(BaseTool):
    name = "infisical_list_secrets"
    description = (
        "List secret NAMES in the Infisical vault. "
        "Returns only the key names — never the values. Safe to use for auditing. "
        "Params: environment (str, optional: dev/staging/prod), path (str, optional, default '/')."
    )
    category = "security"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        environment = params.get("environment", _default_env())
        path = params.get("path", "/")
        try:
            client = _get_client()
            secrets = client.get_all_secrets(environment=environment, path=path)
            names = [s.secret_name for s in secrets]
            return f"{len(names)} secrets in {environment}{path}:\n" + "\n".join(
                f"  - {n}" for n in sorted(names)
            )
        except Exception as e:
            return f"Error listing secrets: {e}"


class InfisicalSetSecretTool(BaseTool):
    name = "infisical_set_secret"
    description = (
        "Create or update a secret in the Infisical vault. "
        "Requires agent role: secrets_manager, devops, security, or admin. "
        "Params: name (str), value (str), environment (str, optional), path (str, optional)."
    )
    category = "security"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        # Role check
        agent_roles = set(getattr(agent, "tools", []))
        role = getattr(agent, "role", "") or ""
        if role not in _WRITE_ROLES:
            return (
                f"Permission denied: role '{role}' cannot write secrets. "
                f"Required: {_WRITE_ROLES}"
            )

        name = params.get("name", "").strip()
        value = params.get("value", "")
        if not name or not value:
            return "Error: 'name' and 'value' are required."

        environment = params.get("environment", _default_env())
        path = params.get("path", "/")
        try:
            client = _get_client()
            # Try update first, create if not exists
            try:
                client.update_secret(
                    secret_name=name,
                    secret_value=value,
                    environment=environment,
                    path=path,
                )
                action = "updated"
            except Exception:
                client.create_secret(
                    secret_name=name,
                    secret_value=value,
                    environment=environment,
                    path=path,
                )
                action = "created"
            log.info(
                "infisical_set_secret: %s %s (env=%s, agent=%s)",
                action,
                name,
                environment,
                getattr(agent, "id", "?"),
            )
            return f"Secret '{name}' {action} in {environment}{path}."
        except Exception as e:
            return f"Error setting secret '{name}': {e}"


def register_infisical_tools(registry):
    """Register Infisical vault tools (only if INFISICAL_TOKEN is configured)."""
    if not os.environ.get("INFISICAL_TOKEN"):
        return  # Vault not configured — skip registration silently
    registry.register(InfisicalGetSecretTool())
    registry.register(InfisicalListSecretsTool())
    registry.register(InfisicalSetSecretTool())
    log.debug("Infisical tools registered (3 tools)")
