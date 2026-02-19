---
name: project-management
description: >
  Guides the agent through software project management practices including sprint planning,
  WSJF prioritization, task decomposition, risk identification, dependency management,
  status reporting, and retrospective facilitation. Use this skill when planning work,
  estimating effort, or organizing development tasks.
metadata:
  category: management
  triggers:
    - "when user asks to plan a sprint or iteration"
    - "when prioritizing backlog items"
    - "when decomposing a large feature into tasks"
    - "when user asks about project risks"
    - "when writing status reports"
    - "when facilitating a retrospective"
---

# Project Management

This skill enables the agent to facilitate software project management — sprint planning,
prioritization, task decomposition, risk management, and team ceremonies.

## Use this skill when

- Planning sprints or iterations
- Prioritizing backlog items using WSJF or similar
- Breaking down features into implementable tasks
- Identifying and managing project risks
- Writing status reports for stakeholders
- Facilitating retrospectives
- Managing dependencies between teams/features

## Do not use this skill when

- Reviewing code (use code-review-excellence)
- Writing documentation (use technical-writing)
- Making architectural decisions (use architecture-review)

## Instructions

### Sprint Planning

#### Sprint Goal Template

```
Sprint [number]: [Theme/Goal in one sentence]

Duration: [2 weeks]
Team capacity: [X story points / Y person-days]

Sprint Goals:
1. [Primary goal — must be achieved]
2. [Secondary goal — stretch if time allows]

Definition of Done:
- [ ] Code reviewed and approved
- [ ] Tests written and passing (≥80% coverage)
- [ ] Documentation updated
- [ ] Deployed to staging
- [ ] Smoke tests passing on staging
```

#### User Story Format

```
As a [user type],
I want to [action/capability],
So that [benefit/value].

Acceptance Criteria:
- [ ] Given [context], when [action], then [expected result]
- [ ] Given [context], when [action], then [expected result]

Story Points: [1 | 2 | 3 | 5 | 8 | 13]
Priority: [P0-Critical | P1-High | P2-Medium | P3-Low]
Dependencies: [List any blockers or dependencies]
```

### WSJF Prioritization

**Weighted Shortest Job First** = (Business Value + Time Criticality + Risk Reduction) / Job Size

| Story | Business Value (1-10) | Time Criticality (1-10) | Risk Reduction (1-10) | Job Size (1-10) | WSJF |
|-------|--------------------|----------------------|---------------------|----------------|------|
| Login redesign | 8 | 3 | 5 | 5 | 3.2 |
| API rate limiting | 6 | 9 | 8 | 3 | 7.7 |
| Dashboard charts | 4 | 2 | 1 | 8 | 0.9 |

**Highest WSJF = do first** (API rate limiting in this example).

### Task Decomposition

Break features into tasks that are:
- **Independent** — can be worked on without waiting for others
- **Small** — completable in 1-2 days maximum
- **Testable** — has clear verification criteria
- **Demonstrable** — produces a visible change

```
Feature: User Registration Flow

Tasks:
1. [Backend] Create user registration API endpoint (POST /api/auth/register)
   - Input validation (email, password strength)
   - Password hashing (bcrypt)
   - Duplicate email check
   - Return JWT token
   - Tests: unit + integration
   Estimate: 3 points

2. [Frontend] Build registration form component
   - Email input with validation
   - Password input with strength indicator
   - Submit button with loading state
   - Error display for validation/server errors
   - Tests: component tests
   Estimate: 3 points

3. [Frontend] Registration success flow
   - Redirect to onboarding/dashboard
   - Welcome toast notification
   - Tests: E2E test for full flow
   Estimate: 2 points

4. [Backend] Welcome email sending
   - Email template
   - Queue welcome email on registration
   - Tests: unit test with mocked email service
   Estimate: 2 points

5. [Infra] Email service setup
   - Configure email provider (SendGrid/SES)
   - Environment variables
   - Test in staging
   Estimate: 1 point

Total: 11 points
Dependencies: Task 4 depends on Task 5; Task 3 depends on Tasks 1 + 2
```

### Risk Management

#### Risk Register Template

| ID | Risk | Probability | Impact | Score | Mitigation | Owner | Status |
|----|------|------------|--------|-------|------------|-------|--------|
| R1 | API provider outage | Medium | High | 6 | Implement fallback provider | @backend | Open |
| R2 | Scope creep on dashboard | High | Medium | 6 | Freeze scope after sprint planning | @pm | Monitoring |
| R3 | Key developer on vacation | High | High | 9 | Cross-train + document | @lead | In progress |

**Score** = Probability (1-3) × Impact (1-3)

#### Risk Categories
- **Technical**: Technology uncertainty, integration challenges, performance
- **Resource**: Team availability, skill gaps, tooling
- **Schedule**: Dependencies, external teams, scope changes
- **External**: Vendor reliability, regulatory changes, market shifts

### Status Report Template

```markdown
# Weekly Status Report — [Date]

## Summary
[One paragraph: what was accomplished, what's at risk, what needs attention]

## Progress
### Completed This Week
- ✅ [Task/Story] — [brief description]
- ✅ [Task/Story] — [brief description]

### In Progress
- 🔄 [Task/Story] — [status, % complete, expected completion]
- 🔄 [Task/Story] — [status, blockers if any]

### Blocked
- 🚫 [Task/Story] — [blocker description, who can unblock]

## Metrics
- Sprint burndown: [X of Y points completed]
- Velocity: [current sprint velocity vs average]
- Blockers resolved: [X of Y]

## Risks & Issues
- [New or changed risks]

## Next Week Focus
- [Top priorities for next week]
```

### Retrospective Facilitation

#### Format: Start / Stop / Continue

```markdown
# Sprint [X] Retrospective

## What went well? (Continue)
- [Team contribution 1]
- [Process that worked]

## What didn't go well? (Stop)
- [Problem 1]
- [Problem 2]

## What should we try? (Start)
- [Improvement idea 1]
- [Improvement idea 2]

## Action Items
| Action | Owner | Due Date |
|--------|-------|----------|
| [Specific action] | @person | [Date] |
| [Specific action] | @person | [Date] |
```

### Dependency Management

```
Feature A ──depends on──→ Feature B ──depends on──→ External API v2
    │
    └──depends on──→ Design System v3 (ready ✅)

Critical Path: Feature A → Feature B → External API v2
Risk: External API v2 release date uncertain
Mitigation: Build Feature B with mock API, integrate when ready
```

## Output Format

Depends on the activity — use the appropriate template from above.

## Anti-patterns

- **NEVER** plan more than team capacity allows — leave 20% buffer
- **NEVER** create tasks larger than 2 days — decompose further
- **NEVER** skip estimation — even rough estimates improve planning
- **NEVER** ignore blockers — escalate within 24 hours
- **NEVER** change sprint scope mid-sprint without explicit agreement
- **NEVER** skip retrospectives — continuous improvement requires reflection
- **NEVER** estimate in hours — use relative points for better accuracy
- **NEVER** assign all work to one person — balance load across the team
