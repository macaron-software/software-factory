Launch a design system or UX workflow with the design team: UX + UI + Accessibility + Solaris DS.

Workflow: `design-system-component` (5 phases: Discovery -> Design -> Implement -> Review -> Document)

## Instructions

1. Ask the user for: **project ID**, **component/page name**, and **design brief**.
2. Call the SF API:

```bash
curl -s -X POST "http://localhost:8099/api/missions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $MACARON_API_KEY" \
  -d '{"project_id": "<PROJECT_ID>", "workflow_id": "design-system-component", "brief": "<BRIEF>"}'
```

3. Report design decisions, token values, and accessibility compliance.

## Team Composition
- **ux_designer** (user research + wireframes)
- **solaris_ux_designer** (Solaris DS tokens + patterns)
- **solaris_ui_developer** (component implementation)
- **solaris_design_qa** (visual QA + token compliance)
- **accessibility_expert** (WCAG 2.1 AA validation)
