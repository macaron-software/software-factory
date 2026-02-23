---
name: wcag-compliance-report
description: >
  Guides the agent through generating a WCAG 2.1 AA compliance report combining automated
  checks with manual review checklists. Use this skill when producing formal accessibility
  compliance documentation, severity assessments, and remediation recommendations.
metadata:
  category: testing
  triggers:
    - "when user asks for a WCAG compliance report"
    - "when producing formal accessibility documentation"
    - "when user needs severity-rated accessibility findings"
    - "when preparing accessibility remediation plan"
---

# WCAG Compliance Report

This skill enables the agent to produce formal WCAG 2.1 AA compliance reports with
automated checks, manual review checklists, severity levels, and remediation plans.

## Use this skill when

- Generating a formal WCAG compliance report
- Preparing for an accessibility audit by a third party
- Documenting compliance status for stakeholders
- Creating remediation roadmaps with severity priorities
- Pre-launch accessibility sign-off

## Do not use this skill when

- Doing a quick accessibility check (use accessibility-audit)
- Implementing accessible components (use design-system-implementation)
- Testing with Playwright (use e2e-browser-testing with a11y checks)

## Instructions

### Report Structure

A WCAG compliance report follows this structure:

1. **Executive Summary** — Overall compliance status
2. **Methodology** — Tools and techniques used
3. **Automated Results** — axe-core, Lighthouse, etc.
4. **Manual Review** — Keyboard, screen reader, cognitive checks
5. **Findings** — Categorized by WCAG criterion
6. **Remediation Plan** — Priority-ordered fixes

### Automated Testing

#### axe-core Integration

```typescript
import AxeBuilder from "@axe-core/playwright";
import { test, expect } from "@playwright/test";

test("WCAG 2.1 AA compliance scan", async ({ page }) => {
  await page.goto("/target-page");

  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();

  // Group by impact
  const critical = results.violations.filter((v) => v.impact === "critical");
  const serious = results.violations.filter((v) => v.impact === "serious");
  const moderate = results.violations.filter((v) => v.impact === "moderate");
  const minor = results.violations.filter((v) => v.impact === "minor");

  console.log(`Critical: ${critical.length}, Serious: ${serious.length}`);
  console.log(`Moderate: ${moderate.length}, Minor: ${minor.length}`);

  // Report all violations with details
  for (const violation of results.violations) {
    console.log(`[${violation.impact}] ${violation.id}: ${violation.description}`);
    console.log(`  WCAG: ${violation.tags.filter((t) => t.startsWith("wcag")).join(", ")}`);
    console.log(`  Nodes: ${violation.nodes.length}`);
    for (const node of violation.nodes) {
      console.log(`    - ${node.target.join(" > ")}`);
      console.log(`      Fix: ${node.failureSummary}`);
    }
  }

  // Fail on critical and serious
  expect(critical).toHaveLength(0);
  expect(serious).toHaveLength(0);
});
```

#### Lighthouse Accessibility Audit

```bash
# Run Lighthouse accessibility audit
npx lighthouse http://localhost:3000 \
  --only-categories=accessibility \
  --output=json \
  --output-path=./lighthouse-a11y.json
```

### Manual Review Checklist

#### Perceivable (WCAG 1.x)

- [ ] **1.1.1 Non-text Content** — All images have `alt` text (or `alt=""` for decorative)
- [ ] **1.2.1 Audio/Video** — Captions provided for multimedia
- [ ] **1.3.1 Info and Relationships** — Semantic HTML conveys structure
- [ ] **1.3.2 Meaningful Sequence** — DOM order matches visual order
- [ ] **1.3.3 Sensory Characteristics** — Instructions don't rely solely on shape/color
- [ ] **1.4.1 Use of Color** — Color is not the only way to convey information
- [ ] **1.4.3 Contrast (Minimum)** — 4.5:1 body text, 3:1 large text
- [ ] **1.4.4 Resize Text** — Page is usable at 200% zoom
- [ ] **1.4.11 Non-text Contrast** — 3:1 for UI components and graphics
- [ ] **1.4.12 Text Spacing** — Content readable with modified text spacing
- [ ] **1.4.13 Content on Hover/Focus** — Dismissible, hoverable, persistent

#### Operable (WCAG 2.x)

- [ ] **2.1.1 Keyboard** — All functionality via keyboard
- [ ] **2.1.2 No Keyboard Trap** — Focus can always move away
- [ ] **2.4.1 Bypass Blocks** — Skip navigation link present
- [ ] **2.4.2 Page Titled** — Descriptive `<title>` on every page
- [ ] **2.4.3 Focus Order** — Tab order is logical
- [ ] **2.4.4 Link Purpose** — Link text is descriptive (not "click here")
- [ ] **2.4.6 Headings and Labels** — Descriptive headings
- [ ] **2.4.7 Focus Visible** — Focus indicator is visible
- [ ] **2.5.5 Target Size** — Touch targets at least 44×44px

#### Understandable (WCAG 3.x)

- [ ] **3.1.1 Language of Page** — `lang` attribute on `<html>`
- [ ] **3.2.1 On Focus** — No unexpected context change on focus
- [ ] **3.2.2 On Input** — No unexpected context change on input
- [ ] **3.3.1 Error Identification** — Errors clearly identified
- [ ] **3.3.2 Labels or Instructions** — Forms have clear labels
- [ ] **3.3.3 Error Suggestion** — Errors include correction suggestions
- [ ] **3.3.4 Error Prevention** — Reversible/confirmable for important actions

#### Robust (WCAG 4.x)

- [ ] **4.1.1 Parsing** — Valid HTML
- [ ] **4.1.2 Name, Role, Value** — Custom controls have accessible names and roles
- [ ] **4.1.3 Status Messages** — Dynamic messages announced to screen readers

### Severity Classification

| Severity    | Description                                 | SLA                  |
| ----------- | ------------------------------------------- | -------------------- |
| 🔴 Critical | Prevents task completion for disabled users | Fix within 1 sprint  |
| 🟠 Serious  | Significant barrier, workaround exists      | Fix within 2 sprints |
| 🟡 Moderate | Inconvenient but task is completable        | Fix within 1 quarter |
| 🔵 Minor    | Annoyance, minimal impact                   | Fix in backlog       |

### Screen Reader Testing Protocol

1. Navigate the entire page using VoiceOver (macOS) or NVDA (Windows)
2. Verify all content is read in logical order
3. Check form labels are announced
4. Verify error messages are announced when they appear
5. Check dynamic content changes are announced via `aria-live`
6. Verify modal focus management works correctly

## Output Format

```
# WCAG 2.1 AA Compliance Report
## Page: [URL]
## Date: [Date]
## Methodology: axe-core 4.x + manual review

### Executive Summary
Compliance level: [Partial / Mostly Compliant / Fully Compliant]
Total issues: X (Y critical, Z serious)

### Automated Findings (axe-core)
| ID | Impact | WCAG Criteria | Description | Instances |
|----|--------|--------------|-------------|-----------|
| color-contrast | Serious | 1.4.3 | Insufficient contrast | 5 |
| image-alt | Critical | 1.1.1 | Missing alt text | 3 |

### Manual Findings
| # | WCAG | Severity | Description | Location | Remediation |
|---|------|----------|-------------|----------|-------------|
| 1 | 2.4.7 | 🔴 | No visible focus on cards | .card links | Add :focus-visible styles |
| 2 | 2.1.1 | 🟠 | Dropdown not keyboard accessible | #user-menu | Use proper ARIA pattern |

### Compliance Matrix
| Principle | Criteria Met | Criteria Failed | Compliance |
|-----------|-------------|-----------------|------------|
| Perceivable | 12/14 | 2 | 86% |
| Operable | 8/10 | 2 | 80% |
| Understandable | 7/7 | 0 | 100% |
| Robust | 2/3 | 1 | 67% |

### Remediation Roadmap
Sprint 1: [Critical issues]
Sprint 2: [Serious issues]
Quarter: [Moderate issues]
Backlog: [Minor issues]
```

## Anti-patterns

- **NEVER** rely solely on automated tools — they catch only 30-40% of issues
- **NEVER** skip screen reader testing — it reveals issues automation misses
- **NEVER** ignore cognitive accessibility (clear language, predictable UI)
- **NEVER** rate all issues the same severity — prioritize by user impact
- **NEVER** produce a report without remediation recommendations
- **NEVER** test only on one browser/screen reader — test at least 2 combinations
- **NEVER** assume "no violations" means "fully accessible"
