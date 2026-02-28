---
name: solaris-compliance
description: >
  Validates UI code against Solaris Design System standards and WCAG AA accessibility.
  Used by compliance critic agents on Solaris / La Poste frontend projects.
metadata:
  category: compliance
  domain: solaris
  triggers:
    - "after any milestone with frontend changes"
    - "when reviewing Angular component code"
    - "when checking Solaris DS conformity"
---

# Solaris Design System Compliance Review

## MANDATORY DS RULES — NON-NEGOTIABLE

Solaris is the **official La Poste Design System**. Custom components replacing Solaris components
are FORBIDDEN without explicit DS team waiver.

### Component Usage
| Need | Use Solaris Component | Never use |
|------|----------------------|-----------|
| Button | `<sol-button>` | `<button class="custom-...">` |
| Input | `<sol-input>` | `<input>` with custom CSS |
| Dialog/Modal | `<sol-dialog>` | Custom overlay/modal |
| Alert/Toast | `<sol-alert>` | Custom alert boxes |
| Table | `<sol-table>` | Plain `<table>` with custom style |
| Badge | `<sol-badge>` | Colored `<span>` |
| Tabs | `<sol-tabs>` | Custom tab implementation |
| Accordion | `<sol-accordion>` | Custom expand/collapse |
| Breadcrumb | `<sol-breadcrumb>` | `<nav>` with custom links |

## COMPLIANCE CHECKLIST

### 1. Solaris Components
- [ ] All interactive UI elements use `sol-*` components (not custom)
- [ ] Solaris tokens used for colors, spacing, typography (not hardcoded values)
- [ ] `@solaris/angular` imported at correct version
- [ ] No override of Solaris CSS classes with `!important`

### 2. WCAG 2.1 Level AA
- [ ] Color contrast ≥ 4.5:1 for normal text, ≥ 3:1 for large text / icons
- [ ] All form fields have associated `<label>` or `aria-label`
- [ ] Error messages use `aria-describedby` pointing to error element
- [ ] Focus indicator visible on all interactive elements (not hidden)
- [ ] Keyboard navigation: Tab order logical, no keyboard traps
- [ ] Skip navigation link present on pages with repeated headers
- [ ] Images have meaningful `alt` text (decorative = `alt=""`)
- [ ] Page `<title>` updated on route change (Angular router)
- [ ] No autoplay video/audio without user control

### 3. RGAA 4.1 Specific
- [ ] French language declared: `lang="fr"` on `<html>`
- [ ] Document structure: single `<h1>`, logical heading hierarchy
- [ ] Tables: `<th scope="col|row">` present
- [ ] Time/date displayed with `<time datetime="...">` attribute
- [ ] PDFs linked from page are accessible (tagged PDF)

### 4. Angular Best Practices (La Poste context)
- [ ] Components use `ChangeDetectionStrategy.OnPush`
- [ ] No business logic in template expressions (only in component class)
- [ ] No direct DOM manipulation (`document.querySelector` forbidden — use ViewChild)
- [ ] i18n: all user-visible strings via `@ngx-translate` or Angular i18n
- [ ] TypeScript strict mode: no `any` type

### 5. Performance (accessibility side-effects)
- [ ] No infinite spinner without text (add `aria-busy`, `aria-label`)
- [ ] Large lists virtualized (no 500+ DOM nodes)
- [ ] Lazy loading for route modules

## MCP SOLARIS TOOLS — Use for validation
When reviewing component code, use `solaris_component` to get the exact Figma specs:
```
mcp_tool: solaris_component
args: { "component": "button" }  # or "input", "dialog", etc.
```
Cross-check implementation dimensions/colors against Figma specs.
Use `solaris_wcag` for WCAG pattern reference:
```
mcp_tool: solaris_wcag
args: { "pattern": "button" }  # or "accordion", "dialog", "tabs", etc.
```

## VERDICT FORMAT

```
## Solaris Compliance Report — {milestone_name}

### ✅ DS Conformant
- (components using correct sol-* elements)

### ❌ DS Violations (BLOCKING)
- component: {file}:{line} — uses custom {element} instead of {sol-component}

### ♿ Accessibility Violations (BLOCKING for RGAA AA)
- {file}:{element} — {issue} (WCAG criterion {X.X.X})

### ⚠️ Warnings
- (non-blocking style/perf recommendations)

### Verdict: PASS | FAIL
```
