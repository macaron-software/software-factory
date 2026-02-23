---
name: figma-visual-diff
description: >
  Guides the agent through generating visual difference reports between Figma designs
  and live implementations. Use this skill when producing side-by-side comparisons,
  screenshot overlays, and annotated findings for design review. Covers screenshot
  capture, pixel comparison, and structured reporting.
metadata:
  category: design
  triggers:
    - "when user asks for a visual diff between design and implementation"
    - "when user wants to compare screenshots of Figma vs live"
    - "when producing a visual regression report"
    - "when user mentions pixel-perfect comparison"
---

# Figma Visual Diff

This skill enables the agent to generate structured visual difference reports comparing
Figma design specs with live implementations, including screenshot comparison and
annotated findings.

## Use this skill when

- Producing a visual diff report for stakeholder review
- Comparing screenshots of design vs implementation
- Identifying pixel-level discrepancies
- Documenting visual regressions after code changes
- Pre-release visual QA

## Do not use this skill when

- Doing property-by-property component audits (use figma-component-audit)
- Auditing token usage in code (use figma-design-sync)
- Implementing components (use design-system-implementation)

## Instructions

### Visual Diff Workflow

1. **Capture screenshots** of the live implementation at target breakpoints
2. **Export or reference** the Figma design frames at matching breakpoints
3. **Compare** screenshots side-by-side or as overlays
4. **Annotate** differences with severity and description
5. **Generate report** with findings and recommended fixes

### Screenshot Capture with Playwright

```typescript
import { test, expect } from "@playwright/test";

const VIEWPORTS = [
  { name: "mobile", width: 375, height: 812 },
  { name: "tablet", width: 768, height: 1024 },
  { name: "desktop", width: 1440, height: 900 },
];

for (const viewport of VIEWPORTS) {
  test(`Capture ${viewport.name} screenshot`, async ({ page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await page.goto("/target-page");

    // Wait for all images and fonts to load
    await page.waitForLoadState("networkidle");

    // Hide dynamic content that varies between runs
    await page.evaluate(() => {
      document.querySelectorAll("[data-dynamic]").forEach((el) => {
        (el as HTMLElement).style.visibility = "hidden";
      });
    });

    await page.screenshot({
      path: `screenshots/${viewport.name}-actual.png`,
      fullPage: true,
    });
  });
}
```

### Component-Level Screenshots

```typescript
test("Capture component screenshots", async ({ page }) => {
  await page.goto("/components/button");

  // Screenshot specific component
  const button = page.getByTestId("primary-button");
  await button.screenshot({ path: "screenshots/button-default.png" });

  // Hover state
  await button.hover();
  await button.screenshot({ path: "screenshots/button-hover.png" });

  // Focus state
  await button.focus();
  await button.screenshot({ path: "screenshots/button-focus.png" });
});
```

### Visual Comparison with Playwright

```typescript
// playwright.config.ts
export default defineConfig({
  expect: {
    toHaveScreenshot: {
      maxDiffPixelRatio: 0.01, // 1% tolerance
      threshold: 0.2, // Per-pixel color threshold
    },
  },
  snapshotDir: "./visual-baselines",
});

// Visual regression test
test("Button matches baseline", async ({ page }) => {
  await page.goto("/components/button");
  const button = page.getByTestId("primary-button");

  await expect(button).toHaveScreenshot("button-primary.png");
});
```

### Manual Comparison Technique

When automated pixel diff isn't available:

1. **Side-by-side**: Place Figma export and screenshot next to each other
2. **Overlay**: Layer screenshots at 50% opacity to spot differences
3. **Toggle**: Rapidly switch between the two to catch movement
4. **Grid overlay**: Apply a grid to both to check alignment

### Annotation Categories

| Category   | Symbol | Description                                 |
| ---------- | ------ | ------------------------------------------- |
| Spacing    | 📏     | Padding, margin, gap differences            |
| Color      | 🎨     | Wrong color values                          |
| Typography | 🔤     | Font size, weight, line-height issues       |
| Layout     | 📐     | Alignment, positioning, grid issues         |
| Missing    | ❌     | Element missing from implementation         |
| Extra      | ➕     | Element not in design but in implementation |
| State      | 🔄     | Interactive state mismatch                  |

### Severity Scale

- **Critical**: Layout broken, content unreadable, major visual regression
- **High**: Noticeable to users, wrong colors or spacing
- **Medium**: Subtle differences, minor spacing, slight color shift
- **Low**: Barely noticeable, sub-pixel rendering differences

## Output Format

```
## Visual Diff Report: [Page/Component Name]
### Date: [Date]
### Compared: Figma [Frame Name] vs Live [URL]

### Summary
- Total findings: X
- Critical: X | High: X | Medium: X | Low: X

### Findings

#### Finding 1 — 📏 Spacing (High)
- **Location**: Header section, main CTA area
- **Expected**: padding-bottom: 48px (--space-12)
- **Actual**: padding-bottom: 32px (--space-8)
- **Screenshot**: [reference]
- **Fix**: Change `padding-bottom: var(--space-8)` to `var(--space-12)` in `.hero`

#### Finding 2 — 🎨 Color (Medium)
- **Location**: Card background
- **Expected**: #F8FAFC (--color-surface)
- **Actual**: #F1F5F9 (--color-gray-100)
- **Fix**: Use `var(--color-surface)` instead of `var(--color-gray-100)`

### Responsive Comparison
| Breakpoint | Figma Match | Notes |
|-----------|-------------|-------|
| Mobile (375px) | 85% ✅ | 2 spacing issues |
| Tablet (768px) | 70% ⚠️ | Column layout differs |
| Desktop (1440px) | 95% ✅ | Minor shadow difference |

### Screenshots
- mobile-actual.png vs mobile-figma.png
- tablet-actual.png vs tablet-figma.png
- desktop-actual.png vs desktop-figma.png
```

## Anti-patterns

- **NEVER** compare with dynamic content visible (dates, avatars, counters)
- **NEVER** use only one breakpoint — always check all responsive variants
- **NEVER** set pixel diff tolerance too high (> 5%) — it hides real issues
- **NEVER** compare without waiting for fonts and images to load
- **NEVER** skip annotation — raw screenshots without context are useless
- **NEVER** ignore browser rendering differences between OS (font smoothing)
