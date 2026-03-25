Launch a QA campaign with the full testing team: QA Lead + Testers + Automation + Performance.

Workflow: `test-campaign` or `performance-testing` (depending on focus)

## Instructions

1. Ask the user for: **project ID**, **scope** (what to test), and **type** (functional/performance/security).
2. For functional QA, use `test-campaign`. For performance, use `performance-testing`.
3. Call the SF API:

```bash
curl -s -X POST "http://localhost:8099/api/missions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $MACARON_API_KEY" \
  -d '{"project_id": "<PROJECT_ID>", "workflow_id": "<WORKFLOW>", "brief": "<SCOPE>"}'
```

4. Report test results: pass/fail counts, coverage delta, screenshots if E2E.

## Team Composition
- **qa_lead** (test strategy + plan)
- **testeur** (manual test execution)
- **test_automation** (Playwright/pytest scripting)
- **performance_engineer** (k6 load testing, if perf workflow)
- **accessibility_expert** (WCAG 2.1 AA audit)
