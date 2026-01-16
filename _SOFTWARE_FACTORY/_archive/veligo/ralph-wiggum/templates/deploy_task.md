# Task {TASK_ID}: {TASK_TITLE}

**Priority**: {PRIORITY}
**WSJF Score**: {WSJF}
**Complexity**: {COMPLEXITY}
**Queue**: DEPLOY

## Description
{DESCRIPTION}

## Environment
{ENVIRONMENT}

## Success Criteria
- [ ] Build réussi
- [ ] Deploy réussi
- [ ] Health check OK
- [ ] E2E journeys passent

## Deploy Process
1. Build: `{BUILD_COMMAND}`
2. Deploy: `{DEPLOY_COMMAND}`
3. Health: `curl {HEALTH_URL}`
4. E2E: `{E2E_COMMAND}`
5. Si erreur → rollback et corriger

## E2E Journeys to Validate
{E2E_JOURNEYS}

## Ralph Status Block
---RALPH_STATUS---
STATUS: PENDING
COMPLEXITY: {COMPLEXITY}
MODEL_TIER: TIER2
WSJF: {WSJF}
---END_RALPH_STATUS---
