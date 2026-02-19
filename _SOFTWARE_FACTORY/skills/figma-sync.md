---
name: figma-design-sync
description: >
  Guides the agent through comparing Figma design specifications with their code
  implementation. Use this skill when verifying that implemented components match
  design specs, auditing token usage, or performing visual regression checks. Covers
  token validation, component auditing, and responsive fidelity.
metadata:
  category: design
  triggers:
    - "when user asks to compare implementation with Figma specs"
    - "when auditing design token usage in code"
    - "when checking responsive fidelity against designs"
    - "when user mentions Figma sync or design sync"
    - "when validating component implementation matches design"
---

# Figma Design Sync

This skill enables the agent to systematically compare Figma design specifications with
code implementations, identifying discrepancies in tokens, spacing, colors, typography,
and responsive behavior.

## Use this skill when

- Verifying component implementation matches Figma specs
- Auditing that code uses correct design tokens
- Checking responsive behavior matches design breakpoints
- Performing a design QA pass before release
- Validating visual regression after refactoring

## Do not use this skill when

- Creating new designs (use frontend-design)
- Implementing components from scratch (use design-system-implementation)
- Doing accessibility audits (use accessibility-audit)

## Instructions

### Design Sync Workflow

1. **Get the Figma spec** — Use Figma MCP tools to retrieve component specs
2. **Extract tokens** — Identify spacing, colors, typography, radius, shadows
3. **Compare with code** — Check CSS/component code for matching values
4. **Report discrepancies** — Document differences with spec references

### Using Figma MCP Tools

```
# Get component summary
solaris_component(component: "button", summary_only: true)

# Get specific variant details
solaris_variant(component: "button", properties: { "Size": "Large", "Style": "Primary" })

# Check validation status
solaris_validation(component: "button")
```

### Token Comparison Matrix

For each component, verify:

| Property | Figma Spec | Code Value | Token | Match? |
|----------|-----------|------------|-------|--------|
| padding-x | 16px | var(--space-4) | ✅ | ✅ |
| padding-y | 8px | 10px | ❌ hardcoded | ❌ |
| border-radius | 8px | var(--radius-md) | ✅ | ✅ |
| font-size | 14px | var(--text-sm) | ✅ | ✅ |
| color | #3B82F6 | var(--color-primary) | ✅ | ✅ |
| shadow | 0 4px 6px | none | ❌ missing | ❌ |

### Responsive Fidelity Check

Verify at each breakpoint:

```typescript
const BREAKPOINTS = [
  { name: 'mobile', width: 375, figmaFrame: 'Mobile' },
  { name: 'tablet', width: 768, figmaFrame: 'Tablet' },
  { name: 'desktop', width: 1440, figmaFrame: 'Desktop' },
];

for (const bp of BREAKPOINTS) {
  // 1. Get Figma frame for this breakpoint
  // 2. Extract layout properties (columns, gaps, padding)
  // 3. Compare with CSS media query values
  // 4. Report mismatches
}
```

### Component Audit Checklist

For each component:
- [ ] Spacing matches Figma (padding, margin, gap)
- [ ] Colors use correct tokens
- [ ] Typography (font, size, weight, line-height) matches
- [ ] Border radius matches
- [ ] Shadows match (or are intentionally different)
- [ ] All states exist (default, hover, focus, disabled, error)
- [ ] Responsive variants match Figma frames
- [ ] Icons match (size, color, alignment)

### Scanning for Hardcoded Values

```bash
# Find hardcoded pixel values that should be tokens
grep -rn 'padding:\s*[0-9]' --include='*.css' --include='*.scss'
grep -rn 'margin:\s*[0-9]' --include='*.css' --include='*.scss'
grep -rn '#[0-9a-fA-F]\{3,6\}' --include='*.css' --include='*.scss'
grep -rn 'font-size:\s*[0-9]' --include='*.css' --include='*.scss'
```

## Output Format

```
## Design Sync Report: [Component/Page Name]
### Spec Source: [Figma frame/component link]

### Token Compliance
- ✅ Spacing: All values use tokens
- ❌ Colors: 2 hardcoded hex values found
- ✅ Typography: Matches spec
- ❌ Border radius: Using 6px instead of 8px (--radius-md)

### Discrepancies
| Property | Expected (Figma) | Actual (Code) | Severity |
|----------|-----------------|----------------|----------|
| padding | 16px (--space-4) | 14px | Medium |
| bg color | #3B82F6 | #2563EB | High |

### Responsive Check
- Mobile (375px): ✅ Matches
- Tablet (768px): ❌ Missing column change
- Desktop (1440px): ✅ Matches

### Recommended Fixes
1. Replace `padding: 14px` with `var(--space-4)` in `.card`
2. Replace `#2563EB` with `var(--color-primary)` in `.btn`
```

## Anti-patterns

- **NEVER** approve implementation without checking all component states
- **NEVER** ignore small spacing differences — 2px off is still wrong
- **NEVER** compare visually only — check actual CSS values
- **NEVER** skip responsive checks — mobile is often the most different
- **NEVER** accept hardcoded values when tokens exist for that property
- **NEVER** assume the code is right if it "looks close enough"
