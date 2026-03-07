---
id: secrets-management
name: Secrets & Credentials Management
version: "1.0"
category: security
icon: "🔐"
author: SF Platform

description: |
  Skill for managing secrets, API keys, and credentials via Infisical vault.
  Agents with this skill can read secrets for task execution, audit secret usage,
  and (with elevated roles) rotate or update credentials.

triggers:
  - "retrieve API key for"
  - "get credentials for"
  - "what's the token for"
  - "list all secrets"
  - "rotate the"
  - "update secret"
  - "vault"
  - "credentials"
  - "secret expired"
  - "API key invalid"

tools:
  - infisical_get_secret
  - infisical_list_secrets
  - infisical_set_secret

personas:
  - security
  - devops
  - backend_developer

anti_patterns:
  - Never log or print secret values — only use them directly in API calls
  - Never store secrets in code, comments, or task descriptions
  - Never pass secrets between agents as plain text
  - Don't use infisical_set_secret to store temporary values — use only for real credentials

patterns:
  - name: fetch-and-use
    description: Retrieve a secret and use it immediately without storing
    steps:
      - infisical_get_secret(name="OPENAI_API_KEY", environment="prod")
      - Use value directly in HTTP call — do not assign to variable in code

  - name: pre-task-audit
    description: Before a deployment, list secrets to verify all required keys are present
    steps:
      - infisical_list_secrets(environment="prod", path="/")
      - Check required keys are in the list
      - Report missing keys to human operator

  - name: key-rotation
    description: Rotate an API key after security incident (requires secrets_manager role)
    steps:
      - infisical_list_secrets() → identify the key to rotate
      - Generate new key value (external API or random)
      - infisical_set_secret(name=key, value=new_value)
      - Verify the updated secret works
      - Log rotation event in platform audit trail

environments:
  dev: local development — uses .env fallback if INFISICAL_TOKEN not set
  staging: pre-prod — should use Infisical with dedicated staging project
  prod: production — Infisical mandatory, .env forbidden for secrets

sf_secrets_catalog:
  # Secrets the SF platform itself uses — should all live in Infisical
  llm_providers:
    - ANTHROPIC_API_KEY
    - AZURE_OPENAI_API_KEY
    - AZURE_OPENAI_ENDPOINT
    - MINIMAX_API_KEY
    - GLM_API_KEY
  infrastructure:
    - DATABASE_URL
    - REDIS_URL
    - JWT_SECRET
    - SF_ENCRYPTION_KEY
    - MACARON_API_KEY
    - PLATFORM_API_KEY
  integrations:
    - GITHUB_TOKEN
    - GITHUB_WEBHOOK_SECRET
    - GITLAB_LAPOSTE_TOKEN
    - JIRA_TOKEN
    - JIRA_WEBHOOK_SECRET
    - ATLASSIAN_TOKEN
    - CONFLUENCE_TOKEN
  notifications:
    - NOTIFY_SLACK_WEBHOOK
    - NOTIFY_EMAIL_PASSWORD
    - NOTIFY_TWILIO_AUTH_TOKEN
    - NOTIFY_VAPID_PRIVATE_KEY
  infra_ssh:
    - VM_PASS
    - STABILITY_SSH_AZ_KEY
    - STABILITY_SSH_OVH_KEY
  oauth:
    - AZURE_AD_CLIENT_ID
    - AZURE_AD_CLIENT_SECRET
    - GITHUB_CLIENT_ID
    - GITHUB_CLIENT_SECRET
  # These stay in .env (not secrets, just config)
  env_only:
    - PLATFORM_PORT
    - PLATFORM_HOST
    - PLATFORM_LLM_PROVIDER
    - PLATFORM_LLM_MODEL
    - PLATFORM_ENV
    - LOG_LEVEL
    - INFISICAL_TOKEN      # bootstrap secret — stays in .env only
    - INFISICAL_SITE_URL
    - INFISICAL_ENVIRONMENT
---

# Secrets & Credentials Management

Agents with this skill interact with the **Infisical vault** to fetch, audit, and rotate secrets.

## Core principle

> Secrets never appear in agent memory, task descriptions, logs, or A2A messages.
> They are fetched just-in-time and used directly.

## When to use this skill

- Fetching API keys before making external API calls
- Auditing that all required credentials are present before a deployment
- Rotating a compromised or expired key (requires `secrets_manager` role)
- Migrating a new secret from `.env` to vault

## Bootstrap

The SF itself uses Infisical: only `INFISICAL_TOKEN` stays in `.env`.
All other secrets are fetched at startup via `platform/config.py._load_infisical()`.

```bash
# Minimal .env for prod:
INFISICAL_TOKEN=st.xxxxxxxx
INFISICAL_SITE_URL=https://vault.your-domain.com   # or app.infisical.com
INFISICAL_ENVIRONMENT=prod
```
