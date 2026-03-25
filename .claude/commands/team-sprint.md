Launch a feature-sprint workflow with the full team: Lead Dev + Backend + Frontend + QA + DevOps.

Workflow: `feature-sprint` (6 phases: Design -> Env Setup -> TDD Sprint -> Adversarial Review -> E2E -> Deploy)

## Instructions

1. Ask the user for: **project ID** and **feature brief** (what to build).
2. Call the SF API to launch the workflow:

```bash
curl -s -X POST "http://localhost:8099/api/missions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $MACARON_API_KEY" \
  -d '{"project_id": "<PROJECT_ID>", "workflow_id": "feature-sprint", "brief": "<BRIEF>"}'
```

3. Monitor the run via SSE:
```bash
curl -N "http://localhost:8099/api/sessions/<SESSION_ID>/sse"
```

4. Report phase transitions to the user. Flag any VETO from adversarial review.

## Team Composition
- **system-architect-art** + **lead_frontend** + **lead_backend** (design phase)
- **dev_backend** + **dev_frontend** (TDD sprint, loop pattern)
- **securite** + **code-critic** (adversarial review, cascade pattern)
- **testeur** + **test_automation** (E2E, parallel pattern)
- **devops** (deploy, sequential)
