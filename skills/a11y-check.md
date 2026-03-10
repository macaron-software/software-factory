---
name: accessibility-audit
description: >
  Guides the agent through WCAG 2.1 AA accessibility auditing. Use this skill when
  checking web pages or components for accessibility compliance, including semantic HTML,
  ARIA usage, color contrast, keyboard navigation, focus management, and screen reader
  compatibility.
metadata:
  category: testing
  triggers:
    - "when user asks to check accessibility"
    - "when user mentions WCAG compliance"
    - "when auditing a component for keyboard navigation"
    - "when checking color contrast ratios"
    - "when user asks about screen reader compatibility"
---

# Accessibility Audit

This skill enables the agent to perform thorough WCAG 2.1 AA accessibility audits on
web pages and components, covering semantic HTML, ARIA, contrast, keyboard navigation,
focus management, and screen reader compatibility.

## Use this skill when

- Auditing a page or component for WCAG 2.1 AA compliance
- Reviewing PR changes for accessibility regressions
- Checking color contrast ratios
- Validating keyboard navigation patterns
- Ensuring proper ARIA usage
- Verifying form accessibility

## Do not use this skill when

- Creating visual designs (use frontend-design)
- Writing functional E2E tests (use e2e-browser-testing)
- The task has no UI component

## Instructions

### Semantic HTML Checklist

Always verify these fundamentals first:

```html
<!-- ✅ CORRECT semantic structure -->
<header>
  <nav aria-label="Main navigation">
    <ul>
      <li><a href="/">Home</a></li>
      <li><a href="/about">About</a></li>
    </ul>
  </nav>
</header>

<main>
  <h1>Page Title</h1>
  <section aria-labelledby="section-heading">
    <h2 id="section-heading">Section Title</h2>
    <article>
      <h3>Article Title</h3>
      <p>Content...</p>
    </article>
  </section>
</main>

<footer>
  <p>&copy; 2024 Company</p>
</footer>

<!-- ❌ WRONG: divs for everything -->
<div class="header">
  <div class="nav">
    <div class="nav-item" onclick="navigate('/')">Home</div>
  </div>
</div>
```

### ARIA Landmarks and Roles

```html
<!-- Required landmarks on every page -->
<header role="banner">
  <!-- One per page -->
  <nav role="navigation">
    <!-- Label if multiple -->
    <main role="main">
      <!-- One per page -->
      <footer role="contentinfo">
        <!-- One per page -->
        <aside role="complementary">
          <!-- Sidebar content -->
          <form role="search">
            <!-- Search form -->

            <!-- ARIA states for interactive elements -->
            <button aria-expanded="false" aria-controls="menu-panel">Menu</button>
            <div id="menu-panel" role="menu" aria-hidden="true">
              <button role="menuitem">Option 1</button>
              <button role="menuitem">Option 2</button>
            </div>

            <!-- Live regions for dynamic content -->
            <div role="status" aria-live="polite">3 results found</div>
            <div role="alert" aria-live="assertive">Error: Invalid email</div>
          </form>
        </aside>
      </footer>
    </main>
  </nav>
</header>
```

### Color Contrast Requirements

| Element                            | Minimum Ratio | Level |
| ---------------------------------- | ------------- | ----- |
| Body text (< 18px)                 | 4.5:1         | AA    |
| Large text (≥ 18px or ≥ 14px bold) | 3:1           | AA    |
| UI components & graphics           | 3:1           | AA    |
| Body text (enhanced)               | 7:1           | AAA   |

```typescript
// Automated contrast check
function getContrastRatio(fg: string, bg: string): number {
  const fgLum = getRelativeLuminance(fg);
  const bgLum = getRelativeLuminance(bg);
  const lighter = Math.max(fgLum, bgLum);
  const darker = Math.min(fgLum, bgLum);
  return (lighter + 0.05) / (darker + 0.05);
}

// Check: ratio >= 4.5 for normal text, >= 3.0 for large text
```

### Keyboard Navigation

Every interactive element must be:

1. **Focusable** — reachable via Tab key
2. **Operable** — activatable via Enter or Space
3. **Visible** — has a visible focus indicator

```css
/* ✅ GOOD: Visible focus styles */
:focus-visible {
  outline: 2px solid var(--color-primary-500);
  outline-offset: 2px;
}

/* ❌ BAD: Never remove focus outlines */
:focus {
  outline: none; /* NEVER DO THIS without replacement */
}
```

#### Keyboard Patterns by Component

| Component | Tab                 | Enter/Space | Escape     | Arrow Keys       |
| --------- | ------------------- | ----------- | ---------- | ---------------- |
| Button    | Focus               | Activate    | -          | -                |
| Link      | Focus               | Navigate    | -          | -                |
| Menu      | Focus trigger       | Open/Select | Close      | Navigate items   |
| Dialog    | Focus first element | -           | Close      | -                |
| Tabs      | Focus active tab    | Select tab  | -          | Switch tabs      |
| Accordion | Focus header        | Toggle      | -          | Navigate headers |
| Combobox  | Focus input         | Select      | Close list | Navigate options |

### Focus Management

```typescript
// After opening a modal
dialog.showModal();
dialog.querySelector("[autofocus]")?.focus();

// After closing a modal — return focus to trigger
const trigger = document.activeElement;
dialog.close();
trigger?.focus();

// After deleting an item — focus the next item or heading
const nextItem = deletedItem.nextElementSibling || deletedItem.previousElementSibling;
nextItem?.focus();
```

### Form Accessibility

```html
<!-- Every input needs a label -->
<label for="email">Email address</label>
<input id="email" type="email" required aria-describedby="email-hint email-error" />
<span id="email-hint" class="hint">We'll never share your email</span>
<span id="email-error" class="error" role="alert" aria-live="polite"></span>

<!-- Group related inputs -->
<fieldset>
  <legend>Shipping Address</legend>
  <label for="street">Street</label>
  <input id="street" type="text" />
  <label for="city">City</label>
  <input id="city" type="text" />
</fieldset>

<!-- Error messages must be associated -->
<input id="password" type="password" aria-invalid="true" aria-describedby="pw-error" />
<span id="pw-error" role="alert">Password must be at least 8 characters</span>
```

### Skip Links

```html
<!-- First element in body -->
<a href="#main-content" class="skip-link">Skip to main content</a>

<style>
  .skip-link {
    position: absolute;
    top: -100%;
    left: 0;
    padding: 0.5rem 1rem;
    background: var(--color-primary-500);
    color: white;
    z-index: 9999;
  }
  .skip-link:focus {
    top: 0;
  }
</style>
```

### Screen Reader Testing Checklist

- [ ] Page has a descriptive `<title>`
- [ ] Headings follow logical hierarchy (h1 → h2 → h3, no skips)
- [ ] Images have meaningful `alt` text (or `alt=""` for decorative)
- [ ] Links have descriptive text (not "click here")
- [ ] Tables have `<caption>` and `<th scope>` attributes
- [ ] Dynamic content updates are announced via `aria-live`
- [ ] SVG icons have `aria-hidden="true"` or accessible labels
- [ ] Error messages are announced when they appear

## Output Format

```
## Accessibility Audit Report
### Page: [URL or component name]

| Category | Check | Status | Severity | Notes |
|----------|-------|--------|----------|-------|
| Semantic HTML | Landmarks present | ✅ | - | - |
| Semantic HTML | Heading hierarchy | ❌ | High | h3 follows h1, missing h2 |
| ARIA | Live regions | ✅ | - | - |
| Contrast | Body text | ❌ | High | 3.2:1 (needs 4.5:1) |
| Keyboard | Tab order | ✅ | - | - |
| Keyboard | Focus visible | ❌ | Medium | Missing on .card links |
| Forms | Labels | ✅ | - | - |

### Remediation Priority
1. [Critical] Fix heading hierarchy — h3 after h1 skips h2
2. [High] Increase body text contrast from 3.2:1 to 4.5:1
3. [Medium] Add focus-visible styles to .card links
```

## Anti-patterns

- **NEVER** remove `:focus` outlines without providing a visible alternative
- **NEVER** use `div` or `span` for interactive elements — use `button` and `a`
- **NEVER** rely solely on color to convey information
- **NEVER** use `aria-label` on non-interactive elements (it's ignored)
- **NEVER** skip heading levels (h1 → h3 without h2)
- **NEVER** use `tabindex` values greater than 0
- **NEVER** hide content from screen readers that sighted users can see
- **NEVER** auto-play audio or video without user control
- **NEVER** use `role="presentation"` or `aria-hidden="true"` on focusable elements
