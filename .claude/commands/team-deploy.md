Launch a deployment pipeline with the DevOps team: CI/CD + Canary + Monitoring.

Workflow: `cicd-pipeline` (4 phases) or `canary-deployment` (5 phases with progressive rollout)

## Instructions

1. Ask the user for: **project ID**, **target env** (staging/production), and **deploy type** (standard/canary).
2. For standard deploy: `cicd-pipeline`. For canary: `canary-deployment` (1%->10%->50%->100% + HITL gate).
3. Call the SF API:

```bash
curl -s -X POST "http://localhost:8099/api/missions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $MACARON_API_KEY" \
  -d '{"project_id": "<PROJECT_ID>", "workflow_id": "<WORKFLOW>", "brief": "Deploy to <ENV>"}'
```

4. Monitor deploy stages. Alert on failed health checks or rollback triggers.

## Team Composition
- **devops** (pipeline execution + infra)
- **sre** (monitoring + alerting)
- **pipeline_engineer** (CI/CD config)
- **securite** (pre-deploy security scan)
