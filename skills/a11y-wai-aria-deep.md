# A11Y WAI-ARIA APG — Deep Skill
# Source: w3.org/WAI/ARIA/apg/patterns/ — 30 patterns

## WHEN TO ACTIVATE
Building any user-facing component, reviewing HTML/CSS, writing templates,
implementing interactive widgets, or evaluating accessibility compliance.

## CORE RULES
1. Use semantic HTML first — ARIA is a supplement, not a replacement
2. Every interactive element MUST be keyboard accessible
3. Every interactive element MUST have an accessible name
4. Focus management: visible focus indicator, logical tab order, focus traps for modals
5. State changes MUST be communicated to assistive technology
6. Color alone MUST NOT convey meaning (use text + icon too)
7. Contrast ratio: 4.5:1 normal text, 3:1 large text (WCAG AA)

## 30 ARIA PATTERNS

### 1. Accordion
```html
<div class="accordion">
  <h3>
    <button aria-expanded="false" aria-controls="panel-1" id="header-1">
      Section Title
    </button>
  </h3>
  <div id="panel-1" role="region" aria-labelledby="header-1" hidden>
    Content here
  </div>
</div>
```
Keyboard: Enter/Space=toggle, Tab=next header. Optional: Arrow up/down between headers.

### 2. Alert
```html
<div role="alert">Important message that needs immediate attention.</div>
```
Auto-announced by screen readers. No keyboard interaction needed. Use sparingly.

### 3. Alert Dialog
```html
<div role="alertdialog" aria-modal="true" aria-labelledby="alert-title" aria-describedby="alert-desc">
  <h2 id="alert-title">Confirm Delete</h2>
  <p id="alert-desc">This action cannot be undone.</p>
  <button>Cancel</button>
  <button autofocus>Delete</button>
</div>
```
Focus trap. Esc=close. Tab cycles within. Focus on least destructive action.

### 4. Breadcrumb
```html
<nav aria-label="Breadcrumb">
  <ol>
    <li><a href="/">Home</a></li>
    <li><a href="/products">Products</a></li>
    <li><a href="/products/widget" aria-current="page">Widget</a></li>
  </ol>
</nav>
```

### 5. Button
```html
<button type="button" aria-pressed="false">Toggle Feature</button>
<!-- Toggle: aria-pressed. Menu: aria-haspopup + aria-expanded. Disabled: disabled attr -->
```
NEVER: `<div role="button" tabindex="0" onclick>` — use `<button>`.

### 6. Carousel
```html
<section aria-roledescription="carousel" aria-label="Product Photos">
  <div aria-live="polite">
    <div role="group" aria-roledescription="slide" aria-label="1 of 5">
      Slide content
    </div>
  </div>
  <button aria-label="Previous slide">←</button>
  <button aria-label="Next slide">→</button>
</section>
```
MUST have pause/play if auto-advancing. WCAG 2.2.2.

### 7. Checkbox
```html
<div role="group" aria-labelledby="group-label">
  <span id="group-label">Notifications</span>
  <label><input type="checkbox"> Email</label>
  <label><input type="checkbox"> SMS</label>
</div>
```
Tri-state parent: `aria-checked="mixed"`. Space=toggle.

### 8. Combobox
```html
<label for="city">City</label>
<input id="city" role="combobox" aria-expanded="false" aria-autocomplete="list"
  aria-controls="city-listbox" aria-activedescendant="">
<ul id="city-listbox" role="listbox" hidden>
  <li id="opt-1" role="option">Paris</li>
  <li id="opt-2" role="option">Lyon</li>
</ul>
```
Arrow=navigate, Enter=select, Esc=close, Type=filter. Most complex pattern.

### 9. Dialog (Modal)
```html
<div role="dialog" aria-modal="true" aria-labelledby="dialog-title">
  <h2 id="dialog-title">Edit Profile</h2>
  <form>...</form>
  <button>Cancel</button>
  <button>Save</button>
</div>
```
MUST: Focus trap, Esc=close, return focus to trigger, `inert` on background.

### 10. Disclosure
```html
<button aria-expanded="false" aria-controls="details">Show Details</button>
<div id="details" hidden>Detailed content here</div>
```
Simpler than accordion. Single show/hide toggle.

### 11. Feed
```html
<div role="feed" aria-label="News">
  <article aria-posinset="1" aria-setsize="50">
    <h2>Article Title</h2>
    <p>Content...</p>
  </article>
</div>
```
`aria-busy="true"` during load. PageDown/Up between articles.

### 12. Grid
Interactive tabular data. Arrow keys navigate cells. Enter=edit cell.
`role="grid"` > `role="row"` > `role="gridcell"` / `role="columnheader"`.
For read-only tabular data, use `<table>` instead.

### 13. Landmarks
```html
<header><!-- role="banner" --></header>
<nav aria-label="Main"><!-- role="navigation" --></nav>
<main><!-- role="main" --></main>
<aside><!-- role="complementary" --></aside>
<footer><!-- role="contentinfo" --></footer>
<section aria-label="Search Results"><!-- role="region" --></section>
<form aria-label="Login"><!-- role="form" --></form>
```
Use semantic HTML elements. ARIA roles only when HTML5 elements not available.

### 14. Link
```html
<a href="/dashboard">Dashboard</a>
<!-- External: -->
<a href="https://ext.com" target="_blank" rel="noopener">
  External Site <span class="sr-only">(opens in new tab)</span>
</a>
```

### 15. Listbox
`role="listbox"` + `role="option"`. Single: `aria-selected`. Multi: `aria-multiselectable`.
Arrow=navigate, Space=select, Type-ahead=jump to match.

### 16. Menu & Menubar
Actions menu (not navigation). `role="menu"` + `role="menuitem"`.
Arrow keys navigate. Enter activates. Esc closes. First letter jump.

### 17. Menu Button
```html
<button aria-haspopup="true" aria-expanded="false" aria-controls="actions-menu">
  Actions
</button>
<ul id="actions-menu" role="menu" hidden>
  <li role="menuitem">Edit</li>
  <li role="menuitem">Delete</li>
</ul>
```

### 18. Meter
```html
<div role="meter" aria-valuenow="75" aria-valuemin="0" aria-valuemax="100"
  aria-label="Storage used: 75%">
  <div style="width: 75%"></div>
</div>
```
Read-only. Not interactive. For progress, use `role="progressbar"`.

### 19-30. Additional Patterns
- **Radio Group**: `role="radiogroup"`, arrow keys move selection
- **Slider**: `role="slider"`, arrows adjust, Home=min, End=max
- **Multi-Thumb Slider**: Multiple `role="slider"` on shared rail
- **Spinbutton**: `role="spinbutton"`, up/down arrows
- **Switch**: `role="switch"`, `aria-checked`, Space/Enter toggle
- **Table**: Semantic `<table>`, `<th scope>`, `<caption>`
- **Tabs**: `role="tablist"` + `role="tab"` + `role="tabpanel"`, arrows switch, Tab enters panel
- **Toolbar**: `role="toolbar"`, arrows between tools, Tab to enter/exit
- **Tooltip**: `role="tooltip"`, `aria-describedby`, Esc dismiss
- **Tree View**: `role="tree"` + `role="treeitem"`, arrows navigate, right=expand, left=collapse
- **Treegrid**: Combines tree + grid patterns
- **Window Splitter**: `role="separator"` with `aria-valuenow`, arrows resize

## KEYBOARD PATTERNS SUMMARY
| Pattern | Enter/Space | Arrow Keys | Tab | Esc | Home/End |
|---------|-------------|-----------|-----|-----|----------|
| Button | Activate | - | Focus | - | - |
| Accordion | Toggle | Between headers | Next header | - | - |
| Tabs | Select tab | Between tabs | Into panel | - | First/Last |
| Dialog | Confirm | - | Cycle within | Close | - |
| Combobox | Select | Navigate options | Exit | Close popup | - |
| Menu | Activate item | Navigate items | Exit | Close | First/Last |
| Tree | Expand/Select | Navigate items | Exit | - | First/Last |
| Slider | - | Adjust value | Exit | - | Min/Max |
| Listbox | - | Navigate | Exit | - | First/Last |

## TESTING CHECKLIST
- [ ] Keyboard: Can complete all tasks without mouse?
- [ ] Focus visible: Can always see where focus is?
- [ ] Screen reader: All content announced properly?
- [ ] Contrast: 4.5:1 normal text, 3:1 large text + UI components?
- [ ] Touch target: All targets >= 44x44px?
- [ ] Motion: `prefers-reduced-motion` respected?
- [ ] Zoom: Works at 200% zoom?
- [ ] Error: Form errors linked to inputs via `aria-describedby`?
- [ ] Live regions: Dynamic content changes announced?
- [ ] Labels: Every input has an accessible label?

## COMMON MISTAKES
1. `<div onclick>` instead of `<button>` — not keyboard accessible
2. Missing `aria-label` on icon-only buttons
3. Focus not managed when content changes (modal open, tab switch)
4. Color alone indicating state (red=error without text)
5. `tabindex="5"` — never use positive tabindex, only 0 or -1
6. `role="button"` without keyboard handler — role alone doesn't add behavior
7. `aria-hidden="true"` on focusable element — creates ghost focus
8. Missing `<label>` on inputs — placeholder is NOT a label
9. Auto-focus on page load stealing focus from user's position
10. `title` attribute as only accessible name — unreliable
