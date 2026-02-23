---
name: figma-component-audit
description: >
  Guides the agent through auditing a single UI component by comparing its Figma design
  spec with its code implementation. Use this skill for detailed component-level audits
  covering padding, margin, border-radius, colors, typography, and interactive states
  (hover, focus, disabled, error).
metadata:
  category: design
  triggers:
    - "when user asks to audit a specific component against Figma"
    - "when comparing component padding/margin with design specs"
    - "when checking component states match Figma variants"
    - "when user asks to verify a single component matches design"
---

# Figma Component Audit

This skill enables the agent to perform a detailed audit of a single UI component,
comparing every property of its Figma spec against the code implementation.

## Use this skill when

- Auditing one specific component (button, card, input, etc.)
- Comparing padding, margin, border-radius, colors with Figma specs
- Verifying all interactive states exist (hover, focus, disabled, error)
- Checking responsive variants of a component
- Pre-release QA of a newly implemented component

## Do not use this skill when

- Auditing an entire page (use figma-design-sync)
- Creating visual diff reports (use figma-visual-diff)
- Implementing a component from scratch (use design-system-implementation)

## Instructions

### Audit Workflow

1. **Identify the component** — Get the component name and Figma reference
2. **Retrieve Figma spec** — Use solaris tools to get all variants and properties
3. **Inspect code** — Find the component CSS/SCSS and markup
4. **Property-by-property comparison** — Check every token
5. **State audit** — Verify all interactive states
6. **Report findings** — Generate structured audit report

### Step 1: Retrieve Figma Spec

```
# Get component overview
solaris_component(component: "button", summary_only: false)

# Get specific variant
solaris_variant(component: "button", properties: { "Size": "Medium", "Style": "Primary" })

# Check current validation status
solaris_validation(component: "button")
```

### Step 2: Property Extraction

Extract these properties from BOTH Figma and code:

#### Box Model

- `padding-top`, `padding-right`, `padding-bottom`, `padding-left`
- `margin-top`, `margin-right`, `margin-bottom`, `margin-left`
- `width`, `height` (or `min-width`, `min-height`)
- `border-width`, `border-style`, `border-color`
- `border-radius` (all corners)

#### Typography

- `font-family`
- `font-size`
- `font-weight`
- `line-height`
- `letter-spacing`
- `text-transform`
- `text-decoration`

#### Visual

- `background-color`
- `color` (text)
- `box-shadow`
- `opacity`

### Step 3: State Comparison Matrix

| State          | Figma Exists? | Code Exists? | Properties Match? |
| -------------- | ------------- | ------------ | ----------------- |
| Default        | ✅            | ✅           | Check below       |
| Hover          | ✅            | ?            | Check below       |
| Focus          | ✅            | ?            | Check below       |
| Active/Pressed | ✅            | ?            | Check below       |
| Disabled       | ✅            | ?            | Check below       |
| Error          | ✅            | ?            | Check below       |
| Loading        | ✅            | ?            | Check below       |

For each state, verify:

```css
/* Example: Button hover state */
.btn:hover {
  /* Figma spec: background #2563EB, translateY -1px, shadow 0 4px 6px */
  background-color: var(--color-primary-600); /* ✅ matches */
  transform: translateY(-1px); /* ✅ matches */
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); /* ✅ matches */
}
```

### Step 4: Responsive Variant Check

```typescript
// Check component at each breakpoint
const variants = [
  { breakpoint: "mobile", properties: { Size: "Small" } },
  { breakpoint: "tablet", properties: { Size: "Medium" } },
  { breakpoint: "desktop", properties: { Size: "Large" } },
];

for (const variant of variants) {
  // Compare Figma variant with CSS media query styles
}
```

### Step 5: Code Quality Check

Beyond visual properties, also verify:

- Component uses design tokens (not hardcoded values)
- Component has `data-testid` attribute
- Component handles `aria-*` attributes properly
- Component forwards `className` and `ref` props
- Component handles `disabled` state semantically (`disabled` attribute, not just CSS)

### Tolerance Rules

| Property      | Tolerance         | Notes                           |
| ------------- | ----------------- | ------------------------------- |
| Spacing       | 0px               | Must be exact token match       |
| Colors        | Exact             | Must match token or hex exactly |
| Font size     | 0px               | Must be exact                   |
| Border radius | 0px               | Must be exact token             |
| Shadows       | ±1px, ±5% opacity | Small rendering differences OK  |
| Line height   | ±0.05             | Minor rendering differences OK  |

## Output Format

```
## Component Audit: [Component Name]
### Figma Source: [Frame/Component reference]
### Code Location: [File path]

### Property Comparison (Default State)
| Property | Figma | Code | Token Used | Match |
|----------|-------|------|------------|-------|
| padding | 12px 16px | 12px 16px | --space-3 --space-4 | ✅ |
| border-radius | 8px | 6px | --radius-sm (wrong) | ❌ |
| font-size | 14px | 14px | --text-sm | ✅ |
| background | #3B82F6 | #3B82F6 | --color-primary | ✅ |
| color | #FFFFFF | #FFFFFF | --color-white | ✅ |

### State Coverage
| State | Exists | Matches | Notes |
|-------|--------|---------|-------|
| Default | ✅ | ✅ | - |
| Hover | ✅ | ❌ | Missing translateY effect |
| Focus | ✅ | ✅ | - |
| Disabled | ✅ | ❌ | Opacity 0.4 instead of 0.5 |
| Error | ❌ | ❌ | Not in Figma or code |

### Issues Found: 3
1. **[High]** Border radius uses --radius-sm (6px) instead of --radius-md (8px)
2. **[Medium]** Hover state missing translateY(-1px) effect
3. **[Low]** Disabled opacity 0.4 vs Figma 0.5

### Recommended Fixes
1. Change `border-radius: var(--radius-sm)` to `var(--radius-md)`
2. Add `transform: translateY(-1px)` to hover state
3. Change disabled opacity from 0.4 to 0.5
```

## Anti-patterns

- **NEVER** eyeball comparisons — measure exact values
- **NEVER** skip interactive states — they're often where bugs hide
- **NEVER** accept "close enough" — either it matches the spec or it doesn't
- **NEVER** audit without the actual Figma spec — don't guess what it should be
- **NEVER** ignore responsive variants — components often change across breakpoints
- **NEVER** skip the token check — hardcoded values that happen to match are still wrong
