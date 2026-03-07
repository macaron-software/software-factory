---
name: risk-metrics-calculation
version: 1.0.0
description: Calculate portfolio risk metrics including VaR, CVaR, Sharpe, Sortino,
  and drawdown analysis. Use when measuring portfolio risk, implementing risk limits,
  or building risk monitoring systems.
metadata:
  category: ops
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - 'measuring portfolio risk, implementing risk limits, or building risk monitoring '
  - implementing risk limits
  - building risk dashboards
eval_cases:
- id: risk-metrics-calculation-approach
  prompt: How should I approach risk metrics calculation for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on risk metrics calculation
  tags:
  - risk
- id: risk-metrics-calculation-best-practices
  prompt: What are the key best practices and pitfalls for risk metrics calculation?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for risk metrics calculation
  tags:
  - risk
  - best-practices
- id: risk-metrics-calculation-antipatterns
  prompt: What are the most common mistakes to avoid with risk metrics calculation?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - risk
  - antipatterns
---
# risk-metrics-calculation

# Risk Metrics Calculation

Comprehensive risk measurement toolkit for portfolio management, including Value at Risk, Expected Shortfall, and drawdown analysis.

## Use this skill when

- Measuring portfolio risk
- Implementing risk limits
- Building risk dashboards
- Calculating risk-adjusted returns
- Setting position sizes
- Regulatory reporting

## Do not use this skill when

- The task is unrelated to risk metrics calculation
- You need a different domain or tool outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.
