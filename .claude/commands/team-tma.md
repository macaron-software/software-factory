Launch a TMA (maintenance) workflow with the support team: TMA Lead + Devs + QA.

Workflow: `tma-maintenance` (4 phases) or `tma-autoheal` (4 phases, auto-detection)

## Instructions

1. Ask the user for: **project ID**, **issue description**, and **type** (bug fix / routine / autoheal).
2. For bug fix or routine: `tma-maintenance`. For auto-detection: `tma-autoheal`.
3. Call the SF API:

```bash
curl -s -X POST "http://localhost:8099/api/missions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $MACARON_API_KEY" \
  -d '{"project_id": "<PROJECT_ID>", "workflow_id": "<WORKFLOW>", "brief": "<ISSUE>"}'
```

4. Report fix status, test results, and deploy confirmation.

## Team Composition
- **responsable_tma** (triage + prioritization)
- **dev_tma** (fix implementation)
- **testeur** (regression testing)
- **devops** (hotfix deploy)
